import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentCapability(Base):
    """
    What a specific device's agent binary can actually execute. The backend
    refuses to issue a command for an action_type with no matching row here.
    Upserted at enrolment and on every agent process start.
    """

    __tablename__ = "agent_capabilities"
    __table_args__ = (
        UniqueConstraint("device_id", "action_type", name="uq_agent_capability_device_action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )

    agent_type: Mapped[str] = mapped_column(String(50))
    agent_version: Mapped[str] = mapped_column(String(50))
    action_type: Mapped[str] = mapped_column(String(100), index=True)
    action_version: Mapped[str] = mapped_column(String(20), default="1")
    local_risk_level: Mapped[str] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
