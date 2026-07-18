import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TelemetryFeatureWindow(Base):
    """
    A rolling, tumbling window of telemetry rolled up into a feature vector.

    One row per (device, feature schema version, window_start). ML models
    never see raw system_metrics samples directly — only these windows.
    """

    __tablename__ = "telemetry_feature_windows"
    __table_args__ = (
        UniqueConstraint(
            "device_id", "feature_schema_version", "window_start", name="uq_feature_window_device_schema_start"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )

    device_class: Mapped[str] = mapped_column(String(50), index=True)
    feature_schema_version: Mapped[str] = mapped_column(String(20), index=True)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sample_count: Mapped[int] = mapped_column(Integer)

    quality_score: Mapped[float] = mapped_column(Float)
    quality_flags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device = relationship("Device")
