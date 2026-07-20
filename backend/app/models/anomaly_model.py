import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnomalyModel(Base):
    """
    Versioned registry entry for an anomaly-detection model.

    Both the deterministic statistical baseline and trained ML models get a
    row here, so every AnomalyPrediction traces back to reproducible
    provenance (hyperparameters, dataset hash, code commit).
    """

    __tablename__ = "anomaly_models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_anomaly_model_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(50))
    device_class: Mapped[str] = mapped_column(String(50), index=True)
    feature_schema_version: Mapped[str] = mapped_column(String(20))

    # "statistical_baseline" | "isolation_forest"
    algorithm: Mapped[str] = mapped_column(String(50))
    hyperparameters: Mapped[dict[str, Any]] = mapped_column(JSONB)

    dataset_hash: Mapped[str] = mapped_column(String(64))
    code_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Null for the stateless statistical baseline; set for serialized ML models.
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # candidate | shadow | advisory | alert_eligible | retired — governed
    # promotion ladder (model_promotion_service.py). Defaults to "shadow" so
    # pre-existing rows (registered before this column existed) keep their
    # current shadow-mode behavior unchanged.
    lifecycle_status: Mapped[str] = mapped_column(String(20), default="shadow", index=True)
    # SHA-256 of the artifact file at artifact_path, verified before every
    # inference load (app/ml/model_loader.py) and before promotion. Null for
    # the stateless statistical baseline (no artifact to hash).
    artifact_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    promoted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
