import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SecurityLog(Base):
    """
    Backend security event log — not visible to end users.

    Records authentication events, authorization failures, rate-limit
    violations, and other security-relevant signals for forensics and
    incident response.
    """

    __tablename__ = "security_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    event_type: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(50), default="info", index=True)

    actor_type: Mapped[str] = mapped_column(String(50), default="system")
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(100), nullable=True)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(String(200))
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="success", index=True)
    message: Mapped[str] = mapped_column(Text)

    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
