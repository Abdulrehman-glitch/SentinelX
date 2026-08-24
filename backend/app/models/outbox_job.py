import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Lifecycle. A job is only ever in one of these.
#   pending    — eligible to be claimed once run_after has passed
#   claimed    — a worker holds a lease on it right now
#   succeeded  — handler returned cleanly; kept briefly for visibility
#   failed     — handler raised, will be retried after backoff
#   dead       — retries exhausted, or the handler declared it poison
JOB_STATUSES = ("pending", "claimed", "succeeded", "failed", "dead")


class OutboxJob(Base):
    """Durable downstream work, written in the same transaction as the data.

    The point of this table is a guarantee a message broker cannot give without
    two-phase commit: when ingestion commits the telemetry, it commits the
    obligation to process it *in the same transaction*. There is no window where
    the sample is stored but the follow-up work has evaporated because a publish
    call failed. Either both are durable or neither is.

    Claiming uses `SELECT ... FOR UPDATE SKIP LOCKED`, which lets several
    workers drain the queue concurrently without coordinating: each takes rows
    the others are not already holding, and a crashed worker's rows become
    claimable again when its lease expires rather than being stuck forever.

    `dedupe_key` makes enqueueing idempotent. Ingesting the same batch twice
    must not schedule the same alert evaluation twice, so the caller supplies a
    key derived from what the work is about, and a duplicate insert is a no-op.
    """

    __tablename__ = "outbox_jobs"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_outbox_dedupe_key"),
        # The claim query: pending/failed rows whose run_after has passed,
        # oldest first. This index is the whole hot path of the worker.
        Index("ix_outbox_claimable", "status", "run_after"),
        # Reclaiming leases abandoned by a crashed worker.
        Index("ix_outbox_lease_expiry", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Nullable because some maintenance jobs are platform-wide rather than
    # belonging to one tenant (expired-session purge, retention upkeep).
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )

    job_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # NULL means "always enqueue this one" (scheduled maintenance ticks).
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="pending")

    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)

    # Both the initial schedule and the retry backoff live here, so the claim
    # query never needs to know which of the two it is looking at.
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Set while claimed. A worker that dies mid-job leaves this in the past,
    # which is how the row becomes claimable again.
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
