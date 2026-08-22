"""The transactional outbox: enqueue, claim, settle.

`enqueue` deliberately does not commit. That is the entire point of the pattern
— the job row joins the caller's transaction, so the telemetry and the
obligation to process it become durable together or not at all. A version of
this that opened its own session and committed would reintroduce exactly the
window the outbox exists to close.

Claiming is `SELECT ... FOR UPDATE SKIP LOCKED`. Several workers can drain the
queue at once without coordinating: each takes rows the others are not holding,
and no worker waits behind another's row.

One decision worth stating plainly, because it looks like a bug until you see
the failure it prevents: `attempts` is incremented when a job is **claimed**,
not when it fails. A job that segfaults the worker, exhausts its memory or
wedges it never reaches a failure handler, so a failure-time counter would stay
at zero and the job would be retried forever, killing every worker that touches
it. Counting at claim time means such a job burns through `max_attempts` and
lands in `dead` like any other — poison-job isolation without needing to
classify the poison.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.outbox_job import OutboxJob

# Job types. Kept as constants because they are persisted in rows that outlive
# a deploy: renaming one strands whatever is already queued under the old name.
JOB_BUILD_FEATURE_WINDOWS = "telemetry.build_feature_windows"
JOB_PURGE_EXPIRED_SESSIONS = "maintenance.purge_expired_sessions"
JOB_PRUNE_OUTBOX = "maintenance.prune_outbox"
JOB_PRUNE_DOMAIN_EVENTS = "maintenance.prune_domain_events"

# Retry backoff. Exponential from 5s, capped so a job never disappears for
# hours, with jitter so a burst of simultaneous failures does not retry in
# lockstep and reproduce the thundering herd that caused them.
_BACKOFF_BASE_SECONDS = 5
_BACKOFF_CAP_SECONDS = 900


class PoisonJob(Exception):
    """Raised by a handler that knows retrying cannot help.

    A malformed payload does not become well-formed on the fourth attempt, so
    the job goes straight to `dead` instead of burning its whole retry budget.
    """


@dataclass(frozen=True)
class QueueStats:
    """What readiness and the operator dashboard need to know."""

    pending: int
    claimed: int
    failed: int
    dead: int
    oldest_pending_age_seconds: float | None

    @property
    def backlog(self) -> int:
        """Work that still has to happen. Excludes dead, which never will."""
        return self.pending + self.claimed + self.failed


def enqueue(
    db: Session,
    job_type: str,
    payload: dict[str, Any] | None = None,
    *,
    organization_id: uuid.UUID | None = None,
    dedupe_key: str | None = None,
    run_after: datetime | None = None,
    max_attempts: int = 5,
) -> bool:
    """Add a job to the caller's open transaction. Does not commit.

    Returns False when `dedupe_key` collided with an already-queued job, which
    is a success: it means the work is already scheduled.
    """
    values = {
        "id": uuid.uuid4(),
        "organization_id": organization_id,
        "job_type": job_type,
        "payload": payload or {},
        "dedupe_key": dedupe_key,
        "status": "pending",
        "attempts": 0,
        "max_attempts": max_attempts,
        "run_after": run_after or datetime.now(timezone.utc),
    }

    stmt = pg_insert(OutboxJob).values(**values)
    if dedupe_key is not None:
        stmt = stmt.on_conflict_do_nothing(constraint="uq_outbox_dedupe_key")

    # RETURNING, not rowcount. For an INSERT without RETURNING this driver
    # reports rowcount as -1, which is truthy, so a deduped insert would have
    # reported itself as a fresh enqueue. RETURNING yields no row on conflict,
    # which is unambiguous.
    inserted = db.execute(stmt.returning(OutboxJob.id)).scalar_one_or_none()
    return inserted is not None


def claim_batch(
    db: Session,
    *,
    worker_id: str,
    limit: int = 10,
    lease_seconds: int = 120,
    now: datetime | None = None,
) -> list[OutboxJob]:
    """Atomically take up to `limit` runnable jobs.

    Runnable means pending/failed and due, OR claimed by a worker whose lease
    has expired — which is how a crashed worker's work comes back rather than
    being stranded in `claimed` forever.
    """
    now = now or datetime.now(timezone.utc)
    lease_until = now + timedelta(seconds=lease_seconds)

    candidate_ids = (
        db.execute(
            text(
                """
                SELECT id FROM outbox_jobs
                WHERE (status IN ('pending', 'failed') AND run_after <= :now)
                   OR (status = 'claimed' AND lease_expires_at IS NOT NULL
                       AND lease_expires_at < :now)
                ORDER BY run_after
                LIMIT :limit
                FOR UPDATE SKIP LOCKED
                """
            ),
            {"now": now, "limit": limit},
        )
        .scalars()
        .all()
    )

    if not candidate_ids:
        return []

    db.execute(
        update(OutboxJob)
        .where(OutboxJob.id.in_(candidate_ids))
        .values(
            status="claimed",
            claimed_by=worker_id,
            lease_expires_at=lease_until,
            # Counted at claim time — see the module docstring.
            attempts=OutboxJob.attempts + 1,
        )
    )
    db.flush()

    return list(db.scalars(select(OutboxJob).where(OutboxJob.id.in_(candidate_ids))))


def mark_succeeded(db: Session, job: OutboxJob, *, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    job.status = "succeeded"
    job.completed_at = now
    job.lease_expires_at = None
    job.claimed_by = None
    job.last_error = None


def mark_failed(
    db: Session,
    job: OutboxJob,
    error: str,
    *,
    poison: bool = False,
    now: datetime | None = None,
) -> None:
    """Schedule a retry, or give up.

    `attempts` was already incremented at claim time, so it reflects how many
    times this job has actually been handed to a worker.
    """
    now = now or datetime.now(timezone.utc)
    # Postgres TEXT is unbounded, but a multi-megabyte traceback in a queue row
    # helps nobody and bloats every claim that reads it.
    job.last_error = error[:4000]
    job.lease_expires_at = None
    job.claimed_by = None

    if poison or job.attempts >= job.max_attempts:
        job.status = "dead"
        job.completed_at = now
        return

    job.status = "failed"
    job.run_after = now + timedelta(seconds=backoff_seconds(job.attempts))


def backoff_seconds(attempts: int) -> float:
    """Exponential with full jitter, capped.

    The jitter is not decoration. When a dependency blips, every in-flight job
    fails at once; without jitter they all retry at the same instant and
    recreate the load that broke it.
    """
    ceiling = min(_BACKOFF_BASE_SECONDS * (2 ** max(0, attempts - 1)), _BACKOFF_CAP_SECONDS)
    return random.uniform(ceiling / 2, ceiling)


def queue_stats(db: Session, *, now: datetime | None = None) -> QueueStats:
    """One pass over the status index, for readiness and dashboards."""
    now = now or datetime.now(timezone.utc)

    counts = dict(
        db.execute(select(OutboxJob.status, func.count()).group_by(OutboxJob.status)).all()
    )

    oldest = db.scalar(
        select(func.min(OutboxJob.run_after)).where(
            OutboxJob.status.in_(("pending", "failed", "claimed"))
        )
    )
    age = (now - oldest).total_seconds() if oldest is not None else None

    return QueueStats(
        pending=int(counts.get("pending", 0)),
        claimed=int(counts.get("claimed", 0)),
        failed=int(counts.get("failed", 0)),
        dead=int(counts.get("dead", 0)),
        oldest_pending_age_seconds=age,
    )


def prune_settled(
    db: Session,
    *,
    succeeded_older_than: timedelta = timedelta(hours=6),
    dead_older_than: timedelta = timedelta(days=14),
    batch_size: int = 5000,
    now: datetime | None = None,
) -> int:
    """Delete settled rows, in bounded batches.

    Succeeded jobs go quickly — they are only kept long enough to be visible
    after the fact. Dead ones linger far longer, because they are evidence of
    a bug somebody still has to look at.
    """
    now = now or datetime.now(timezone.utc)

    doomed = (
        db.execute(
            select(OutboxJob.id)
            .where(
                case(
                    (
                        OutboxJob.status == "succeeded",
                        OutboxJob.completed_at < now - succeeded_older_than,
                    ),
                    (
                        OutboxJob.status == "dead",
                        OutboxJob.completed_at < now - dead_older_than,
                    ),
                    else_=False,
                )
            )
            .limit(batch_size)
        )
        .scalars()
        .all()
    )

    if not doomed:
        return 0

    db.execute(OutboxJob.__table__.delete().where(OutboxJob.id.in_(doomed)))
    return len(doomed)
