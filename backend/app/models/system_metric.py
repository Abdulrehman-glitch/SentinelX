import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SystemMetric(Base):
    """System-level telemetry collected by a desktop/server monitoring agent."""

    __tablename__ = "system_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

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

    cpu_percent: Mapped[float] = mapped_column(Float)
    memory_percent: Mapped[float] = mapped_column(Float)
    disk_percent: Mapped[float] = mapped_column(Float)

    # Mobile-agent extras; null for desktop agents that don't report them.
    battery_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_charging: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    network_transport: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    device = relationship("Device", back_populates="metrics")
