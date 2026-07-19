import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RecoveryPolicy(Base):
    """
    Deterministic policy for a given action type: approval mode, cooldown,
    daily limit, verification window. organization_id NULL = global default,
    applied to every org unless an org-specific row overrides it.
    """

    __tablename__ = "recovery_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    device_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_type: Mapped[str] = mapped_column(String(100), index=True)

    trigger_conditions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20))
    approval_mode: Mapped[str] = mapped_column(String(20))

    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300)
    daily_execution_limit: Mapped[int] = mapped_column(Integer, default=5)
    verification_window_seconds: Mapped[int] = mapped_column(Integer, default=300)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
