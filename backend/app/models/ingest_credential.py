import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Everything a key can be allowed to do. Deliberately tiny: this sprint ships
# metric ingestion, so `metrics:write` is the only scope that means anything.
# Adding `logs:write` here before logs actually work would be a lie.
INGEST_SCOPES = ("metrics:write",)

# Printed at the front of every issued key so a leaked string is recognisable
# on sight — in a log, a support ticket, or a secret scanner's ruleset.
INGEST_KEY_PREFIX = "sxi_live"


class IngestCredential(Base):
    """An organisation-scoped API key for OTLP metric ingestion.

    Deliberately a third credential type, separate from both browser sessions
    and device tokens, because it answers a different question. A device token
    says "I am this one machine". A session says "I am this human". An ingest
    credential says "I am some OpenTelemetry client this organisation authorised
    to write metrics" — it is not tied to a device, may be shared by a fleet of
    collectors, and must never grant read access to anything.

    Only the SHA-256 of the key is stored. The plaintext is returned exactly
    once, at creation, and cannot be recovered afterwards. SHA-256 is correct
    here rather than argon2 (which device credentials use): the key is 32 bytes
    of `secrets.token_urlsafe` entropy, so there is no dictionary to attack, and
    a fast hash is what lets ingestion look the key up by hash in one indexed
    query instead of verifying against every row.
    """

    __tablename__ = "ingest_credentials"
    __table_args__ = (
        # The ingest hot path: hash lookup, then an active-and-unexpired check.
        Index("ix_ingest_credentials_token_hash", "token_hash", unique=True),
        Index("ix_ingest_credentials_org_active", "organization_id", "revoked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )

    name: Mapped[str] = mapped_column(String(120))

    # Shown in the UI so an operator can tell two keys apart without seeing
    # either secret. Four characters are not enough to attack a 32-byte key,
    # and they are what people actually recognise.
    key_prefix: Mapped[str] = mapped_column(String(16), default=INGEST_KEY_PREFIX)
    key_last_four: Mapped[str] = mapped_column(String(4))

    token_hash: Mapped[str] = mapped_column(String(64))

    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Written on use, but not on every single request — the ingest path
    # coalesces the update so a busy collector does not turn every metric POST
    # into a credential row write.
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Optional hard expiry, so a key issued for a migration stops working
    # without anyone having to remember to revoke it.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization")
