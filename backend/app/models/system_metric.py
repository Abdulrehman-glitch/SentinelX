import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SystemMetric(Base):
    """System-level telemetry collected by a desktop/server monitoring agent."""

    __tablename__ = "system_metrics"
    __table_args__ = (
        # Idempotent ingestion: an agent retrying a batch after a lost response
        # cannot store the same sample twice. NULL event_ids (legacy agents)
        # are exempt — Postgres treats NULLs as distinct in unique constraints.
        UniqueConstraint("device_id", "event_id", name="uq_metric_device_event"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Client-generated sample UUID used for upload deduplication.
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        index=True,
    )

    # Nullable: mobile devices can't always read true CPU utilisation, and an
    # unknown reading must stay unknown — never a fabricated 0%.
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_percent: Mapped[float] = mapped_column(Float)
    disk_percent: Mapped[float] = mapped_column(Float)

    # Mobile-agent extras; null for desktop agents that don't report them.
    battery_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_charging: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    battery_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    thermal_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    network_transport: Mapped[str | None] = mapped_column(String(32), nullable=True)
    network_validated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    network_metered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    device = relationship("Device", back_populates="metrics")
