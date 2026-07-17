import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DeviceCredential(Base):
    """
    Hashed agent API tokens scoped to one organization.

    The raw token is shown only once at creation. Agents authenticate
    with Bearer <token>, resolved to an org via the hash.
    """

    __tablename__ = "device_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), index=True)
    token_hash: Mapped[str] = mapped_column(String(500))
    token_preview: Mapped[str] = mapped_column(String(100), index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Rotation: the new credential points at the one it replaces; the old one
    # is revoked on the new token's first successful use (implicit ack).
    replaces_credential_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("device_credentials.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    device = relationship("Device")
