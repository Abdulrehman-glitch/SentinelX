import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserSession(Base):
    """A server-side browser session backing one refresh-token family.

    This is what makes logout and revocation real rather than advisory: every
    access token carries the owning session's id in its `sid` claim, and
    get_current_user refuses a token whose session has been revoked or has
    expired. Killing the row therefore kills the credential immediately,
    without waiting for the access token's own expiry.

    Only the SHA-256 of the refresh token is stored. Unlike a password, a
    refresh token is 48 bytes of CSPRNG output, so it has no guessable
    structure for an offline attacker to exploit and does not need a slow
    KDF — and the fast hash matters, because this lookup sits on the hot path
    of every refresh.
    """

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # The hash this one replaced. A refresh presented against a *previous*
    # hash is a replay of a token that was already spent — see
    # session_service.rotate_session, which treats that as compromise and
    # revokes the whole family rather than silently issuing a new token.
    previous_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    rotation_counter: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Coarse client fingerprint for the "your active sessions" surface and for
    # security-log correlation. Deliberately not used as an auth factor: both
    # values are client-controlled and change legitimately (roaming, UA
    # updates), so binding a session to them causes false logouts.
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    user = relationship("User")

    def is_usable(self, now: datetime | None = None) -> bool:
        moment = now or datetime.now(timezone.utc)
        if not self.is_active or self.revoked_at is not None:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return moment < expires
