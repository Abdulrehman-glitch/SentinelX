import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserSettings(Base):
    """
    Stores accessibility and dashboard preferences for one user.
    """

    __tablename__ = "user_settings"

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_settings_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    theme: Mapped[str] = mapped_column(String(50), default="light")
    density: Mapped[str] = mapped_column(String(50), default="comfortable")
    font_size: Mapped[str] = mapped_column(String(50), default="normal")

    reduce_motion: Mapped[bool] = mapped_column(Boolean, default=False)
    high_contrast: Mapped[bool] = mapped_column(Boolean, default=False)
    color_blind_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    table_page_size: Mapped[int] = mapped_column(Integer, default=10)
    auto_refresh_seconds: Mapped[int] = mapped_column(Integer, default=30)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    user = relationship("User", back_populates="settings")