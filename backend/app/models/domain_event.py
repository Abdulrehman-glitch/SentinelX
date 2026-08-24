import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Operationally interesting things a dashboard should learn about promptly.
# Deliberately not "every metric point": the stream exists to keep an operator's
# view fresh, not to move telemetry to the browser.
DOMAIN_EVENT_TYPES = (
    "device.status_changed",
    "telemetry.batch_accepted",
    "alert.created",
    "alert.updated",
    "incident.created",
    "incident.updated",
    "recovery.state_changed",
    "system.degraded",
)


class DomainEvent(Base):
    """The durable, replayable record behind the live event stream.

    Valkey pub/sub delivers these to connected browsers quickly, but pub/sub
    forgets: a subscriber that was disconnected for ten seconds never learns
    what it missed. So the event is written here first and published second.
    Postgres is the history; Valkey is only the fast path.

    `sequence` is what a client sends back as `Last-Event-ID` to resume.

    One honest caveat about that sequence. It comes from a Postgres identity
    column, and identity values are allocated at INSERT while rows become
    visible at COMMIT — so a transaction that took sequence 41 can commit after
    one that took 42, and a reader polling strictly for `sequence > 42` could
    step over 41. The SSE route therefore resumes over a short overlap window
    rather than a strict cursor, and the browser de-duplicates by event id.
    That makes a missed event recoverable, which is the actual requirement;
    REST queries remain the source of truth for state either way.
    """

    __tablename__ = "domain_events"
    __table_args__ = (
        # The resume query: one tenant's events after a given cursor, in order.
        Index("ix_domain_events_org_sequence", "organization_id", "sequence"),
        # Retention prunes by age.
        Index("ix_domain_events_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Monotonic within the database. Unique so a client cursor is unambiguous.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=False), unique=True)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )

    event_type: Mapped[str] = mapped_column(String(64))

    # Optional subjects, so a client can filter without parsing the payload.
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=True
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=True
    )

    # A summary, not the data itself. The browser uses it to decide which
    # TanStack query to invalidate, then refetches through the normal API.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
