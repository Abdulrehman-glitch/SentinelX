"""The transactional outbox.

The properties pinned here are the ones the whole async design depends on: that
enqueueing is part of the caller's transaction, that two workers never process
the same job, that a crashed worker's work comes back, and that a job which
kills workers eventually stops being handed to them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.outbox_job import OutboxJob
from app.services import outbox_service as ob


@pytest.fixture(autouse=True)
def _clean_queue(db):
    """The queue is global, so tests must not see each other's jobs."""
    db.query(OutboxJob).delete()
    db.commit()
    yield
    db.query(OutboxJob).delete()
    db.commit()


def _enqueue(db, job_type="test.job", **kwargs):
    ok = ob.enqueue(db, job_type, {"n": 1}, **kwargs)
    db.commit()
    return ok


class TestEnqueue:
    def test_enqueue_joins_the_callers_transaction(self, db):
        """The property the outbox exists for.

        If the caller's transaction rolls back, the job must vanish with it. A
        job that survived a rolled-back ingest would describe work about data
        that was never stored.
        """
        ob.enqueue(db, "test.job", {"n": 1})
        db.rollback()
        assert db.scalar(select(func.count()).select_from(OutboxJob)) == 0

    def test_enqueue_commits_with_the_caller(self, db):
        ob.enqueue(db, "test.job", {"n": 1})
        db.commit()
        assert db.scalar(select(func.count()).select_from(OutboxJob)) == 1

    def test_a_dedupe_key_makes_enqueue_idempotent(self, db):
        """Re-ingesting a batch must not schedule the same work twice."""
        assert _enqueue(db, dedupe_key="batch-1") is True
        assert _enqueue(db, dedupe_key="batch-1") is False
        assert db.scalar(select(func.count()).select_from(OutboxJob)) == 1

    def test_different_dedupe_keys_are_separate_jobs(self, db):
        _enqueue(db, dedupe_key="batch-1")
        _enqueue(db, dedupe_key="batch-2")
        assert db.scalar(select(func.count()).select_from(OutboxJob)) == 2

    def test_no_dedupe_key_always_enqueues(self, db):
        """Scheduled maintenance ticks are meant to repeat."""
        _enqueue(db)
        _enqueue(db)
        assert db.scalar(select(func.count()).select_from(OutboxJob)) == 2


class TestClaiming:
    def test_a_due_job_is_claimed(self, db):
        _enqueue(db)
        claimed = ob.claim_batch(db, worker_id="w1")
        db.commit()
        assert len(claimed) == 1
        assert claimed[0].status == "claimed"
        assert claimed[0].claimed_by == "w1"

    def test_a_future_job_is_not_claimed(self, db):
        _enqueue(db, run_after=datetime.now(timezone.utc) + timedelta(minutes=5))
        assert ob.claim_batch(db, worker_id="w1") == []

    def test_claiming_increments_attempts(self, db):
        """Counted at claim time so a worker-killing job still ages out."""
        _enqueue(db)
        claimed = ob.claim_batch(db, worker_id="w1")
        db.commit()
        assert claimed[0].attempts == 1

    def test_the_limit_is_respected(self, db):
        for i in range(10):
            ob.enqueue(db, "test.job", {"n": i})
        db.commit()
        assert len(ob.claim_batch(db, worker_id="w1", limit=3)) == 3

    def test_two_workers_never_get_the_same_job(self, db):
        """`FOR UPDATE SKIP LOCKED`, proven with two real transactions.

        Worker A claims inside an open transaction. Worker B, running
        concurrently, must skip A's locked rows rather than block on them or
        take them, and the two claim sets must be disjoint.
        """
        for i in range(10):
            ob.enqueue(db, "test.job", {"n": i})
        db.commit()

        a, b = SessionLocal(), SessionLocal()
        try:
            claimed_a = ob.claim_batch(a, worker_id="worker-a", limit=5)
            # A's transaction is still open and holding those rows.
            claimed_b = ob.claim_batch(b, worker_id="worker-b", limit=5)

            ids_a = {j.id for j in claimed_a}
            ids_b = {j.id for j in claimed_b}

            assert len(ids_a) == 5
            assert len(ids_b) == 5
            assert ids_a.isdisjoint(ids_b)

            a.commit()
            b.commit()
        finally:
            a.close()
            b.close()

    def test_an_expired_lease_is_reclaimed(self, db):
        """A worker that crashed mid-job must not strand the work forever."""
        _enqueue(db)
        claimed = ob.claim_batch(db, worker_id="crashed", lease_seconds=60)
        db.commit()

        # Simulate the crash: the row stays `claimed`, the lease lapses.
        claimed[0].lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

        reclaimed = ob.claim_batch(db, worker_id="healthy")
        db.commit()

        assert len(reclaimed) == 1
        assert reclaimed[0].id == claimed[0].id
        assert reclaimed[0].claimed_by == "healthy"
        # The crashed attempt still counted, which is what bounds the retries.
        assert reclaimed[0].attempts == 2

    def test_a_live_lease_is_not_stolen(self, db):
        _enqueue(db)
        ob.claim_batch(db, worker_id="w1", lease_seconds=300)
        db.commit()
        assert ob.claim_batch(db, worker_id="w2") == []


class TestSettlement:
    def _claim_one(self, db):
        _enqueue(db)
        job = ob.claim_batch(db, worker_id="w1")[0]
        db.commit()
        return job

    def test_success_is_terminal(self, db):
        job = self._claim_one(db)
        ob.mark_succeeded(db, job)
        db.commit()
        assert job.status == "succeeded"
        assert job.completed_at is not None
        assert ob.claim_batch(db, worker_id="w2") == []

    def test_failure_schedules_a_retry(self, db):
        job = self._claim_one(db)
        ob.mark_failed(db, job, "boom")
        db.commit()

        assert job.status == "failed"
        assert job.last_error == "boom"
        assert job.run_after > datetime.now(timezone.utc)
        # Released, so the reclaim path is not what picks it up.
        assert job.claimed_by is None

    def test_a_retried_job_is_claimable_once_due(self, db):
        job = self._claim_one(db)
        ob.mark_failed(db, job, "boom")
        job.run_after = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

        again = ob.claim_batch(db, worker_id="w2")
        db.commit()
        assert len(again) == 1
        assert again[0].id == job.id

    def test_exhausted_attempts_become_dead(self, db):
        _enqueue(db, max_attempts=2)
        job = None
        for _ in range(2):
            job = ob.claim_batch(db, worker_id="w1")[0]
            ob.mark_failed(db, job, "still broken")
            job.run_after = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

        assert job.status == "dead"
        assert ob.claim_batch(db, worker_id="w1") == []

    def test_a_poison_job_dies_immediately(self, db):
        """A malformed payload will not become well-formed on attempt four."""
        job = self._claim_one(db)
        ob.mark_failed(db, job, "unparseable payload", poison=True)
        db.commit()

        assert job.status == "dead"
        assert job.attempts == 1

    def test_a_long_error_is_truncated(self, db):
        job = self._claim_one(db)
        ob.mark_failed(db, job, "x" * 100_000)
        db.commit()
        assert len(job.last_error) == 4000

    def test_backoff_grows_and_is_capped(self):
        assert ob.backoff_seconds(1) <= ob.backoff_seconds(10)
        assert ob.backoff_seconds(50) <= 900

    def test_backoff_is_jittered(self):
        """Without jitter, a dependency blip retries in lockstep."""
        samples = {ob.backoff_seconds(6) for _ in range(30)}
        assert len(samples) > 1


class TestVisibility:
    def test_stats_count_each_state(self, db):
        for i in range(5):
            ob.enqueue(db, "test.job", {"n": i})
        db.commit()

        claimed = ob.claim_batch(db, worker_id="w1", limit=2)
        ob.mark_succeeded(db, claimed[0])
        ob.mark_failed(db, claimed[1], "boom")
        db.commit()

        stats = ob.queue_stats(db)
        assert stats.pending == 3
        assert stats.failed == 1
        assert stats.backlog == 4  # succeeded is done; it is not backlog

    def test_oldest_age_reflects_the_backlog(self, db):
        ob.enqueue(db, "test.job", {}, run_after=datetime.now(timezone.utc) - timedelta(minutes=10))
        db.commit()
        stats = ob.queue_stats(db)
        assert stats.oldest_pending_age_seconds >= 600

    def test_an_empty_queue_has_no_age(self, db):
        assert ob.queue_stats(db).oldest_pending_age_seconds is None

    def test_dead_jobs_are_not_backlog(self, db):
        """Backlog means work that will still happen."""
        _enqueue(db, max_attempts=1)
        job = ob.claim_batch(db, worker_id="w1")[0]
        ob.mark_failed(db, job, "boom")
        db.commit()

        stats = ob.queue_stats(db)
        assert stats.dead == 1
        assert stats.backlog == 0


class TestPruning:
    def test_old_succeeded_jobs_are_removed(self, db):
        _enqueue(db)
        job = ob.claim_batch(db, worker_id="w1")[0]
        ob.mark_succeeded(db, job)
        job.completed_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()

        assert ob.prune_settled(db) == 1
        db.commit()
        assert db.scalar(select(func.count()).select_from(OutboxJob)) == 0

    def test_recent_succeeded_jobs_are_kept(self, db):
        _enqueue(db)
        job = ob.claim_batch(db, worker_id="w1")[0]
        ob.mark_succeeded(db, job)
        db.commit()
        assert ob.prune_settled(db) == 0

    def test_dead_jobs_are_kept_far_longer(self, db):
        """They are evidence of a bug somebody still has to look at."""
        _enqueue(db, max_attempts=1)
        job = ob.claim_batch(db, worker_id="w1")[0]
        ob.mark_failed(db, job, "boom")
        job.completed_at = datetime.now(timezone.utc) - timedelta(days=2)
        db.commit()

        assert ob.prune_settled(db) == 0

    def test_pending_jobs_are_never_pruned(self, db):
        _enqueue(db)
        assert ob.prune_settled(db) == 0
