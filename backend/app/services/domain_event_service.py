"""Recording the operational events the live stream replays.

An event is written into the **caller's** transaction, exactly like
`outbox_service.enqueue`. That is the whole design: the thing that happened and
the record that it happened commit together or not at all, so the stream can
never claim an alert fired that was subsequently rolled back, and can never
lose one that was not.

This is deliberately not a telemetry firehose. `DOMAIN_EVENT_TYPES` is a short
list of state changes an operator would want to know about within seconds. A
CPU sample is not one of them - it belongs in `metric_points`, and the browser
reads it through the query API when it decides to.

The payload is a summary, never the data. Its job is to tell the browser which
view is now stale so it can refetch through the normal API; if it carried the
state itself, the stream would become a second source of truth that could
disagree with the first.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain_event import DOMAIN_EVENT_TYPES, DomainEvent

# Resuming reads back over a short overlap rather than strictly after the
# client's cursor. Identity sequences are allocated at INSERT and become
# visible at COMMIT, so a transaction holding 41 can commit after one holding
# 42; a strict `sequence > 42` would step over 41 forever. Re-sending a handful
# of events the client already has is free - it de-duplicates by id - whereas
# dropping one is not.
RESUME_OVERLAP = 50

# What one poll may return. A client that has been away for a long time gets
# its backlog in pages rather than one enormous frame.
MAX_EVENTS_PER_POLL = 200


def record(
    db: Session,
    *,
    organization_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any] | None = None,
    device_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | None = None,
) -> DomainEvent:
    """Add an event to the caller's transaction. Does not commit."""
    if event_type not in DOMAIN_EVENT_TYPES:
        # A typo here would produce an event no client filters on, which is
        # worse than a loud failure because it looks like it worked.
        raise ValueError(
            f"Unknown domain event type '{event_type}'. "
            f"Known types: {', '.join(sorted(DOMAIN_EVENT_TYPES))}."
        )

    event = DomainEvent(
        organization_id=organization_id,
        event_type=event_type,
        device_id=device_id,
        resource_id=resource_id,
        payload=payload or {},
    )
    db.add(event)
    return event


def record_safely(db: Session, **kwargs: Any) -> DomainEvent | None:
    """Record an event without letting it break the thing it describes.

    Used on paths where the event is a nicety and the surrounding work is not:
    a heartbeat must still be accepted if the stream row cannot be written.
    Producers that genuinely need the event to be atomic with their change call
    `record` directly and let the failure propagate.
    """
    try:
        return record(db, **kwargs)
    except Exception:
        return None


def latest_sequence(db: Session, organization_id: uuid.UUID) -> int:
    """The newest cursor for a tenant, or 0 when nothing has happened yet."""
    value = db.scalar(
        select(DomainEvent.sequence)
        .where(DomainEvent.organization_id == organization_id)
        .order_by(DomainEvent.sequence.desc())
        .limit(1)
    )
    return int(value or 0)


def events_since(
    db: Session,
    organization_id: uuid.UUID,
    after_sequence: int,
    *,
    limit: int = MAX_EVENTS_PER_POLL,
) -> list[DomainEvent]:
    """One tenant's events after a cursor, oldest first.

    The organisation filter is not a convenience - it is the tenant boundary.
    No code path here reads events for an organisation the caller did not
    authenticate against.
    """
    return list(
        db.scalars(
            select(DomainEvent)
            .where(
                DomainEvent.organization_id == organization_id,
                DomainEvent.sequence > after_sequence,
            )
            .order_by(DomainEvent.sequence.asc())
            .limit(min(limit, MAX_EVENTS_PER_POLL))
        )
    )


def resume_from(db: Session, organization_id: uuid.UUID, last_event_id: str | None) -> int:
    """Translate a client's Last-Event-ID into a starting cursor.

    An unparseable or absent cursor means "start from now": a browser opening
    the stream for the first time wants live events, not a day of history. A
    real cursor is walked back over the overlap window for the visibility
    reason described at the top of this module.
    """
    if not last_event_id:
        return latest_sequence(db, organization_id)
    try:
        cursor = int(last_event_id)
    except (TypeError, ValueError):
        return latest_sequence(db, organization_id)
    if cursor < 0:
        return latest_sequence(db, organization_id)
    return max(cursor - RESUME_OVERLAP, 0)
