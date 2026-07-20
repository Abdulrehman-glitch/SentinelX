import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReplayRun(Base):
    """
    Audit-only record of a historical replay request: who ran it, with what
    parameters, over how many windows. Never stores per-window decisions —
    those are returned to the caller (and optionally exported to
    JSON/Markdown) but never persisted, so replay can never collide with or
    overwrite a real AnomalyPrediction or HybridDecision row.
    """

    __tablename__ = "replay_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    device_class: Mapped[str] = mapped_column(String(50), index=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scoring_policy_version: Mapped[str] = mapped_column(String(20))

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    windows_considered: Mapped[int] = mapped_column(Integer)
    decisions_count: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
