import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Supported roles (ordered by privilege, descending)
# platform_admin: SentinelX system operator — sees all orgs
# owner:          org owner, manages billing and top-level settings
# admin:          manages users, devices, rules within org
# engineer:       view + ack/resolve alerts and incidents
# operator:       view + acknowledge alerts
# viewer:         read-only
VALID_ROLES = {"platform_admin", "owner", "admin", "engineer", "operator", "viewer"}


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(500))

    role: Mapped[str] = mapped_column(String(50), default="viewer", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="users")
