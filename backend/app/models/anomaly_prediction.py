import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnomalyPrediction(Base):
    """
    A single model's scoring of a single feature window. Always shadow mode
    in this sprint — never creates Alert/Incident/RecoveryAction rows.
    """

    __tablename__ = "anomaly_predictions"
    __table_args__ = (
        UniqueConstraint("feature_window_id", "model_name", name="uq_anomaly_prediction_window_model"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    feature_window_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telemetry_feature_windows.id", ondelete="CASCADE"), index=True
    )

    model_name: Mapped[str] = mapped_column(String(100), index=True)
    model_version: Mapped[str] = mapped_column(String(50))
    feature_schema_version: Mapped[str] = mapped_column(String(20))

    # Raw detector output — never a probability. See docs/ai_observability_architecture.md.
    anomaly_score: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    is_anomalous: Mapped[bool] = mapped_column(Boolean)
    # Qualitative bucket ("low"|"medium"|"high"), not derived from anomaly_score via sigmoid.
    confidence: Mapped[str] = mapped_column(String(20))

    # Per-tracked-feature {baseline, actual, z_score, is_affected} — serves both
    # "affected features" and "baseline comparison" from one column.
    feature_comparison: Mapped[dict[str, Any]] = mapped_column(JSONB)
    explanation: Mapped[str] = mapped_column(Text)

    shadow_mode: Mapped[bool] = mapped_column(Boolean, default=True)

    review_status: Mapped[str] = mapped_column(String(30), default="unreviewed", index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    device = relationship("Device")
    feature_window = relationship("TelemetryFeatureWindow")
