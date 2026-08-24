"""What the worker actually does, and the registry that finds it.

Every handler here must be safe to run twice. The outbox guarantees at-least-
once delivery, not exactly-once: a worker can finish a job and then die before
committing the status change, and the next worker will run it again. Rather
than trying to make delivery exact — which needs distributed consensus — each
handler is written so a second run is a no-op.

Handlers receive an open session and must not commit. The runner owns the
transaction so that the work and the job's status change land together: if the
handler's writes committed separately, a crash in between would mark a job done
whose effects were lost, or leave effects behind for a job that then retried.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.domain_event import DomainEvent
from app.models.outbox_job import OutboxJob
from app.services import outbox_service as ob
from app.services import session_service
from app.services.device_class_service import classify
from app.services.feature_window_service import build_pending_windows

Handler = Callable[[Session, OutboxJob], str]

HANDLERS: dict[str, Handler] = {}


def handler(job_type: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        HANDLERS[job_type] = fn
        return fn

    return register


def _require_uuid(job: OutboxJob, key: str) -> uuid.UUID:
    """Pull a UUID from the payload, or declare the job poison.

    A payload missing its subject will still be missing it on the fifth
    attempt, so there is nothing to gain from the retry budget.
    """
    raw = (job.payload or {}).get(key)
    if not raw:
        raise ob.PoisonJob(f"{job.job_type}: payload has no '{key}'")
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise ob.PoisonJob(f"{job.job_type}: '{key}' is not a UUID: {raw!r}") from exc


@handler(ob.JOB_BUILD_FEATURE_WINDOWS)
def build_feature_windows(db: Session, job: OutboxJob) -> str:
    """Roll raw samples into feature windows, off the ingest request path.

    This is the work that used to make ingestion pay for the AI pipeline's
    reads. It is naturally idempotent: build_pending_windows advances a cursor
    derived from the newest stored window, so a repeat run finds nothing to do.
    """
    device_id = _require_uuid(job, "device_id")
    device = db.get(Device, device_id)
    if device is None:
        # Deleted between enqueue and execution. Not an error, and retrying
        # will not bring it back.
        return "device no longer exists"

    device_class = classify(device)
    if device_class is None:
        return "device has no feature schema"

    created = build_pending_windows(db, device, device_class)
    return f"built {len(created)} window(s) for {device.hostname}"


@handler(ob.JOB_PURGE_EXPIRED_SESSIONS)
def purge_expired_sessions(db: Session, _job: OutboxJob) -> str:
    """Delete user sessions past expiry.

    This has existed since the v3.2 session work but nothing ever called it, so
    expired rows accumulated forever. Being scheduled here is the whole fix.
    """
    removed = session_service.purge_expired_sessions(db)
    return f"purged {removed} expired session(s)"


@handler(ob.JOB_PRUNE_OUTBOX)
def prune_outbox(db: Session, _job: OutboxJob) -> str:
    """Keep the queue table from growing without bound.

    Bounded per run: a single unbounded DELETE over a large backlog would hold
    locks long enough to stall the claim query the worker depends on.
    """
    removed = ob.prune_settled(db)
    return f"pruned {removed} settled job(s)"


@handler(ob.JOB_PRUNE_DOMAIN_EVENTS)
def prune_domain_events(db: Session, job: OutboxJob) -> str:
    """Trim the live-stream history.

    Retention has to outlast any plausible browser disconnection, because this
    table is what makes a missed pub/sub message recoverable. A day is far more
    than a reconnect needs and still bounds the table.
    """
    keep_hours = int((job.payload or {}).get("keep_hours", 24))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=keep_hours)

    doomed = (
        db.execute(select(DomainEvent.id).where(DomainEvent.created_at < cutoff).limit(5000))
        .scalars()
        .all()
    )
    if not doomed:
        return "no expired events"

    db.execute(delete(DomainEvent).where(DomainEvent.id.in_(doomed)))
    return f"pruned {len(doomed)} event(s) older than {keep_hours}h"


@handler(ob.JOB_PRUNE_RATE_LIMITS)
def prune_rate_limits(db: Session, _job: OutboxJob) -> str:
    """Discard rate-limit windows that have already expired.

    Correctness never depended on this: an expired row is treated as a fresh
    window by the UPSERT that reads it. This only stops the table from
    accumulating one row per (caller, endpoint) pair seen since the process
    started.
    """
    removed = db.execute(
        text(
            "DELETE FROM rate_limit_counters WHERE bucket_key IN ("
            "  SELECT bucket_key FROM rate_limit_counters"
            "  WHERE expires_at <= now() LIMIT 5000"
            ")"
        )
    ).rowcount
    return f"pruned {removed} expired rate-limit window(s)"
