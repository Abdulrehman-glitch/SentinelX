"""The worker runtime.

The outbox tests cover the queue's semantics; these cover the process that
drains it — that a handler's writes and its job's status change land together,
that a failing handler cannot leave half its work behind, that shutdown never
abandons a job mid-flight, and that periodic maintenance is scheduled exactly
once no matter how many workers are running.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.outbox_job import OutboxJob
from app.models.user_session import UserSession
from app.services import outbox_service as ob
from app.worker import handlers as h
from app.worker.runner import MAINTENANCE_SCHEDULE, Worker, ensure_maintenance_scheduled


@pytest.fixture(autouse=True)
def _clean_queue(db):
    db.query(OutboxJob).delete()
    db.commit()
    yield
    db.query(OutboxJob).delete()
    db.commit()


@pytest.fixture()
def temp_handler():
    """Register a handler for the duration of one test."""
    registered: list[str] = []

    def register(job_type, fn):
        h.HANDLERS[job_type] = fn
        registered.append(job_type)

    yield register

    for job_type in registered:
        h.HANDLERS.pop(job_type, None)


def _worker(**kwargs):
    return Worker(worker_id="test-worker", idle_sleep_seconds=0.01, **kwargs)


def _job(db, job_type, payload=None, **kwargs):
    ob.enqueue(db, job_type, payload or {}, **kwargs)
    db.commit()


class TestJobExecution:
    def test_a_successful_job_is_marked_succeeded(self, db, temp_handler):
        temp_handler("t.ok", lambda _db, _job: "done")
        _job(db, "t.ok")

        assert _worker().run_once() == 1

        db.expire_all()
        job = db.scalar(select(OutboxJob))
        assert job.status == "succeeded"
        assert job.completed_at is not None

    def test_handler_writes_commit_with_the_job(self, db, temp_handler):
        """The property that makes at-least-once safe."""

        def creates_a_row(session, job):
            session.add(Organization(name="Made by worker", slug=f"w-{job.id.hex[:8]}"))
            return "created"

        temp_handler("t.writes", creates_a_row)
        _job(db, "t.writes")

        _worker().run_once()

        db.expire_all()
        assert db.scalar(select(OutboxJob)).status == "succeeded"
        assert (
            db.scalar(
                select(func.count())
                .select_from(Organization)
                .where(Organization.name == "Made by worker")
            )
            == 1
        )

    def test_a_failing_handler_leaves_no_partial_writes(self, db, temp_handler):
        """Roll back the work, keep the failure record."""

        def writes_then_raises(session, job):
            session.add(Organization(name="Should not survive", slug=f"x-{job.id.hex[:8]}"))
            session.flush()
            raise RuntimeError("boom")

        temp_handler("t.partial", writes_then_raises)
        _job(db, "t.partial")

        _worker().run_once()

        db.expire_all()
        job = db.scalar(select(OutboxJob))
        assert job.status == "failed"
        assert "boom" in job.last_error
        assert (
            db.scalar(
                select(func.count())
                .select_from(Organization)
                .where(Organization.name == "Should not survive")
            )
            == 0
        )

    def test_a_failing_job_is_retried_then_dies(self, db, temp_handler):
        def always_fails(_db, _job):
            raise RuntimeError("nope")

        temp_handler("t.fail", always_fails)
        _job(db, "t.fail", max_attempts=3)

        worker = _worker()
        for _ in range(3):
            worker.run_once()
            db.expire_all()
            job = db.scalar(select(OutboxJob))
            job.run_after = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

        db.expire_all()
        job = db.scalar(select(OutboxJob))
        assert job.status == "dead"
        assert job.attempts == 3

    def test_a_poison_job_dies_on_the_first_attempt(self, db, temp_handler):
        def poison(_db, _job):
            raise ob.PoisonJob("payload will never parse")

        temp_handler("t.poison", poison)
        _job(db, "t.poison")

        _worker().run_once()

        db.expire_all()
        job = db.scalar(select(OutboxJob))
        assert job.status == "dead"
        assert job.attempts == 1

    def test_an_unknown_job_type_dies_rather_than_looping(self, db):
        """Usually a rollback that removed a handler with work still queued."""
        _job(db, "t.no.such.handler")

        _worker().run_once()

        db.expire_all()
        job = db.scalar(select(OutboxJob))
        assert job.status == "dead"
        assert "no handler registered" in job.last_error

    def test_an_empty_queue_does_nothing(self, db):
        assert _worker().run_once() == 0

    def test_a_handler_running_twice_is_harmless(self, db, temp_handler):
        """At-least-once delivery is the contract; handlers absorb it."""
        calls = []

        def record(_db, job):
            calls.append(job.id)
            return "ok"

        temp_handler("t.twice", record)

        _job(db, "t.twice")
        _worker().run_once()

        # Force the job back to runnable, as a lease expiry would.
        db.expire_all()
        job = db.scalar(select(OutboxJob))
        job.status = "pending"
        job.run_after = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

        _worker().run_once()
        assert len(calls) == 2

        db.expire_all()
        assert db.scalar(select(OutboxJob)).status == "succeeded"


class TestGracefulShutdown:
    def test_shutdown_stops_before_the_next_job(self, db, temp_handler):
        """A stop request must not abandon work mid-flight."""
        processed = []
        worker = _worker(batch_size=5)

        def stop_after_first(_db, job):
            processed.append(job.id)
            worker.request_stop()
            return "ok"

        temp_handler("t.stop", stop_after_first)
        for _ in range(5):
            ob.enqueue(db, "t.stop", {})
        db.commit()

        worker.run_once()

        # One ran; the rest stay claimed and are recovered via lease expiry.
        assert len(processed) == 1
        db.expire_all()
        assert (
            db.scalar(
                select(func.count()).select_from(OutboxJob).where(OutboxJob.status == "claimed")
            )
            == 4
        )

    def test_jobs_left_claimed_at_shutdown_are_recovered(self, db, temp_handler):
        temp_handler("t.recover", lambda _db, _job: "ok")
        _job(db, "t.recover")

        # A worker claims, then the process dies without settling the job.
        claimed = ob.claim_batch(db, worker_id="doomed", lease_seconds=1)
        db.commit()
        claimed[0].lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

        assert _worker().run_once() == 1
        db.expire_all()
        assert db.scalar(select(OutboxJob)).status == "succeeded"


class TestMaintenanceScheduling:
    def test_maintenance_is_scheduled(self, db):
        assert ensure_maintenance_scheduled(db) == len(MAINTENANCE_SCHEDULE)
        db.commit()

        queued = set(db.scalars(select(OutboxJob.job_type)))
        assert queued == set(MAINTENANCE_SCHEDULE)

    def test_the_same_tick_is_only_scheduled_once(self, db):
        """Every worker races to schedule; the unique key picks one winner.

        This is what replaces leader election — no lease, nothing to go stale.
        """
        now = datetime.now(timezone.utc)
        assert ensure_maintenance_scheduled(db, now=now) == len(MAINTENANCE_SCHEDULE)
        db.commit()

        for _ in range(5):
            assert ensure_maintenance_scheduled(db, now=now) == 0
            db.commit()

        assert db.scalar(select(func.count()).select_from(OutboxJob)) == len(MAINTENANCE_SCHEDULE)

    def test_concurrent_workers_do_not_double_schedule(self, db):
        now = datetime.now(timezone.utc)
        a, b = SessionLocal(), SessionLocal()
        try:
            scheduled_a = ensure_maintenance_scheduled(a, now=now)
            a.commit()
            scheduled_b = ensure_maintenance_scheduled(b, now=now)
            b.commit()
        finally:
            a.close()
            b.close()

        assert scheduled_a == len(MAINTENANCE_SCHEDULE)
        assert scheduled_b == 0

    def test_a_later_bucket_schedules_again(self, db):
        now = datetime.now(timezone.utc)
        ensure_maintenance_scheduled(db, now=now)
        db.commit()

        later = now + max(MAINTENANCE_SCHEDULE.values()) * 2
        assert ensure_maintenance_scheduled(db, now=later) == len(MAINTENANCE_SCHEDULE)


class TestMaintenanceHandlers:
    def test_expired_sessions_are_purged(self, db, admin_user):
        """Wired up at last — this existed since v3.2 but nothing called it."""
        from app.services import session_service

        session, _raw = session_service.create_session(db, admin_user)
        session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
        session_id = session.id

        _job(db, ob.JOB_PURGE_EXPIRED_SESSIONS)
        _worker().run_once()

        db.expire_all()
        assert db.get(UserSession, session_id) is None

    def test_a_live_session_survives_the_purge(self, db, admin_user):
        from app.services import session_service

        session, _raw = session_service.create_session(db, admin_user)
        db.commit()
        session_id = session.id

        _job(db, ob.JOB_PURGE_EXPIRED_SESSIONS)
        _worker().run_once()

        db.expire_all()
        assert db.get(UserSession, session_id) is not None

    def test_feature_window_job_tolerates_a_deleted_device(self, db):
        """Enqueue and execution are not simultaneous; the subject can vanish."""
        import uuid as _uuid

        _job(db, ob.JOB_BUILD_FEATURE_WINDOWS, {"device_id": str(_uuid.uuid4())})
        _worker().run_once()

        db.expire_all()
        assert db.scalar(select(OutboxJob)).status == "succeeded"

    def test_a_feature_window_job_without_a_device_is_poison(self, db):
        _job(db, ob.JOB_BUILD_FEATURE_WINDOWS, {})
        _worker().run_once()

        db.expire_all()
        job = db.scalar(select(OutboxJob))
        assert job.status == "dead"
        assert job.attempts == 1

    def test_a_malformed_device_id_is_poison(self, db):
        _job(db, ob.JOB_BUILD_FEATURE_WINDOWS, {"device_id": "not-a-uuid"})
        _worker().run_once()

        db.expire_all()
        assert db.scalar(select(OutboxJob)).status == "dead"
