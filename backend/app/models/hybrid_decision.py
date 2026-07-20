import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HybridDecision(Base):
    """
    One combined judgement per (feature window, scoring policy version):
    deterministic alert rules + statistical baseline + IsolationForest +
    telemetry quality + anomaly persistence + device class/criticality +
    recent incidents/recovery activity, folded into a single deterministic,
    versioned decision. Never writes Alert/Incident/RecoveryCommand rows —
    alert_id/incident_id/recovery_command_id are read-only references to
    whatever the authoritative pipelines already produced.
    """

    __tablename__ = "hybrid_decisions"
    __table_args__ = (
        UniqueConstraint("feature_window_id", "scoring_policy_version", name="uq_hybrid_decision_window_policy"),
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

    # {fired, severity, alert_ids, alert_types, top_alert_id} — read-only view
    # of whatever the deterministic pipeline (metrics.py) already raised.
    rule_result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    baseline_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_prediction: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # all_normal | rule_only | baseline_only | model_only | two_agree |
    # all_agree | detector_conflict | insufficient_data
    detector_agreement: Mapped[str] = mapped_column(String(30), index=True)
    # info | warning | critical — a fired critical rule always wins (see
    # hybrid_detection_service._combined_severity).
    combined_severity: Mapped[str] = mapped_column(String(20), index=True)
    # low | medium | high — severity + device criticality + persistence +
    # recent incident/recovery activity.
    operational_risk: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[str] = mapped_column(String(20))

    affected_features: Mapped[list] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    scoring_policy_version: Mapped[str] = mapped_column(String(20), index=True)

    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )
    recovery_command_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recovery_commands.id", ondelete="SET NULL"), nullable=True
    )

    review_status: Mapped[str] = mapped_column(String(30), default="unreviewed", index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    device = relationship("Device")
    feature_window = relationship("TelemetryFeatureWindow")
