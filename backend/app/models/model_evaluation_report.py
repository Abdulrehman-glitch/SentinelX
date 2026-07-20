import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ModelEvaluationReport(Base):
    """
    A point-in-time evaluation of one registered model over a review period,
    computed from human-reviewed AnomalyPrediction rows
    (model_evaluation_service.py). Never computes recall — there's no
    reliable known-positive label in this system, only what a human chose
    to review. Fields that can't be measured yet are left null rather than
    fabricated.
    """

    __tablename__ = "model_evaluation_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anomaly_models.id", ondelete="CASCADE"), index=True
    )

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    prediction_count: Mapped[int] = mapped_column(Integer)
    reviewed_count: Mapped[int] = mapped_column(Integer)
    true_positives: Mapped[int] = mapped_column(Integer)
    false_positives: Mapped[int] = mapped_column(Integer)
    expected_changes: Mapped[int] = mapped_column(Integer)

    # Null when there aren't enough true/false-positive labels to compute.
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    false_positive_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    detector_agreement_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    supported_device_coverage: Mapped[int] = mapped_column(Integer)
    missing_feature_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Null until Stage 6 drift monitoring adds failure logging — not
    # fabricated as zero when it simply isn't tracked yet.
    inference_failures: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anomaly_lead_time_seconds_avg: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    model = relationship("AnomalyModel")
