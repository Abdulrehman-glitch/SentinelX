"""Organisation-scoped API keys for OTLP metric ingestion.

A third credential type, deliberately separate from the other two. A device
token says "I am this one machine". A browser session says "I am this human".
An ingest credential says "I am some OpenTelemetry client this organisation
authorised to write metrics" — not bound to a device, possibly shared across a
fleet of collectors, and never granting read access to anything.

Why SHA-256 here when device credentials use argon2. Argon2 exists to make
*guessable* secrets expensive to attack, and it does so by being slow. These
keys are 32 bytes from `secrets.token_urlsafe`, so there is no dictionary and
nothing to guess: the search space is the problem, not the hash speed. Using a
fast hash also lets ingestion find the key with one indexed lookup, instead of
verifying a slow hash against every active credential in the table — precisely
the amplification the legacy device-token path had to be turned off for. The
comparison is still constant-time, because the lookup is by digest and never a
byte-wise compare of the secret.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingest_credential import (
    INGEST_KEY_PREFIX,
    INGEST_SCOPES,
    IngestCredential,
)

SCOPE_METRICS_WRITE = "metrics:write"

# 32 bytes of entropy. token_urlsafe returns 43 characters for that.
_SECRET_BYTES = 32

# `last_used_at` is useful for spotting a key nobody uses any more; it is not
# an audit trail. Writing it on every request would turn a busy collector's
# metric POSTs into a row update each, so it is coarsened to this.
_LAST_USED_RESOLUTION = timedelta(minutes=5)


@dataclass(frozen=True)
class IssuedCredential:
    """The one and only time the plaintext exists outside the client."""

    credential: IngestCredential
    plaintext: str


class IngestCredentialError(ValueError):
    pass


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_key() -> str:
    """`sxi_live_<43 url-safe chars>`.

    The prefix is not decoration: it makes a leaked key recognisable on sight in
    a log, a support ticket or a secret-scanning ruleset, and it lets the server
    reject an obviously-wrong credential without a database round trip.
    """
    return f"{INGEST_KEY_PREFIX}_{secrets.token_urlsafe(_SECRET_BYTES)}"


def create_credential(
    db: Session,
    *,
    organization_id: uuid.UUID,
    name: str,
    scopes: list[str] | None = None,
    created_by_user_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> IssuedCredential:
    """Mint a key. The caller must surface `plaintext` once and then drop it."""
    requested = scopes or [SCOPE_METRICS_WRITE]
    unknown = set(requested) - set(INGEST_SCOPES)
    if unknown:
        raise IngestCredentialError(
            f"Unknown ingest scope(s): {', '.join(sorted(unknown))}. "
            f"Supported: {', '.join(INGEST_SCOPES)}."
        )

    plaintext = generate_key()
    credential = IngestCredential(
        organization_id=organization_id,
        name=name.strip()[:120],
        key_prefix=INGEST_KEY_PREFIX,
        key_last_four=plaintext[-4:],
        token_hash=hash_key(plaintext),
        scopes=requested,
        created_by_user_id=created_by_user_id,
        expires_at=expires_at,
    )
    db.add(credential)
    db.flush()

    return IssuedCredential(credential=credential, plaintext=plaintext)


def resolve_credential(
    db: Session, plaintext: str, *, now: datetime | None = None
) -> IngestCredential | None:
    """Find the active credential for this key, or None.

    Returns None for every failure mode — unknown, revoked, expired — so the
    caller cannot accidentally leak which one it was in a response.
    """
    if not plaintext or not plaintext.startswith(f"{INGEST_KEY_PREFIX}_"):
        return None

    now = now or datetime.now(timezone.utc)
    credential = db.scalar(
        select(IngestCredential).where(IngestCredential.token_hash == hash_key(plaintext))
    )
    if credential is None:
        return None
    if credential.revoked_at is not None:
        return None
    if credential.expires_at is not None and credential.expires_at <= now:
        return None

    return credential


def touch_last_used(credential: IngestCredential, *, now: datetime | None = None) -> bool:
    """Record use, at most once per resolution window. True if it changed."""
    now = now or datetime.now(timezone.utc)
    if (
        credential.last_used_at is not None
        and now - credential.last_used_at < _LAST_USED_RESOLUTION
    ):
        return False
    credential.last_used_at = now
    return True


def has_scope(credential: IngestCredential, scope: str) -> bool:
    return scope in (credential.scopes or [])


def revoke(credential: IngestCredential, *, now: datetime | None = None) -> None:
    """Idempotent: revoking twice keeps the original moment."""
    if credential.revoked_at is None:
        credential.revoked_at = now or datetime.now(timezone.utc)


def rotate(
    db: Session,
    credential: IngestCredential,
    *,
    created_by_user_id: uuid.UUID | None = None,
    overlap: timedelta = timedelta(hours=24),
) -> IssuedCredential:
    """Issue a replacement and retire the old key after an overlap.

    Rotation is not revocation. Revoking first would break every collector using
    the key until each is reconfigured, so the old key keeps working for the
    overlap window and then expires on its own.
    """
    replacement = create_credential(
        db,
        organization_id=credential.organization_id,
        name=credential.name,
        scopes=list(credential.scopes or [SCOPE_METRICS_WRITE]),
        created_by_user_id=created_by_user_id,
        expires_at=credential.expires_at,
    )

    deadline = datetime.now(timezone.utc) + overlap
    # Never extend an expiry that was already sooner than the overlap.
    if credential.expires_at is None or credential.expires_at > deadline:
        credential.expires_at = deadline

    return replacement


def list_for_organization(db: Session, organization_id: uuid.UUID) -> list[IngestCredential]:
    return list(
        db.scalars(
            select(IngestCredential)
            .where(IngestCredential.organization_id == organization_id)
            .order_by(IngestCredential.created_at.desc())
        )
    )
