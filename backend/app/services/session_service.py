"""Server-side browser sessions and refresh-token rotation.

The security properties this module is responsible for:

* **Real logout.** Access tokens carry `sid`; revoking the row here makes
  every outstanding access token for that session unusable on its next
  request, rather than leaving it valid until it expires.
* **Rotation.** Each refresh spends the presented token and issues a new one,
  so a stolen refresh token is only useful until the legitimate client next
  refreshes.
* **Replay detection.** The hash a session was rotated *away from* is kept.
  Presenting it again means two parties hold tokens from the same family —
  one of them is an attacker, and we cannot tell which — so the whole family
  is revoked and the user must sign in again. Failing closed is the point.
* **Absolute lifetime.** Rotation alone would let one sign-in live forever.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import generate_refresh_token, hash_refresh_token
from app.models.user import User
from app.models.user_session import UserSession
from app.services.security_log_service import create_security_log


class SessionError(Exception):
    """Base class for refresh failures. Never leaks which case occurred to
    the client — every one produces the same 401."""


class InvalidSessionError(SessionError):
    """No live session matches the presented refresh token."""


class SessionReuseError(SessionError):
    """An already-rotated refresh token was presented again."""


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    # Deliberately request.client.host, not X-Forwarded-For: this value is
    # stored and shown back to the user, and a forgeable header would let an
    # attacker write arbitrary text into someone's session list.
    return request.client.host if request.client else None


def _user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    return (request.headers.get("user-agent") or "")[:300] or None


def create_session(db: Session, user: User, request: Request | None = None) -> tuple[UserSession, str]:
    """Opens a new session and returns it with the RAW refresh token.

    The raw token is returned exactly once and never stored; only its SHA-256
    is persisted.
    """

    settings = get_settings()
    now = datetime.now(timezone.utc)
    raw_token = generate_refresh_token()

    session = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=user.organization_id,
        refresh_token_hash=hash_refresh_token(raw_token),
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        issued_at=now,
        user_agent=_user_agent(request),
        ip_address=_client_ip(request),
        is_active=True,
    )
    db.add(session)
    # Make the row visible to the caller's transaction — routes read
    # session.id back to mint the access token before committing.
    db.flush()

    return session, raw_token


def load_active_session(db: Session, session_id: uuid.UUID) -> UserSession | None:
    """Fetch a session for access-token validation. Returns None for
    missing, revoked, or expired sessions alike."""

    session = db.get(UserSession, session_id)
    if session is None or not session.is_usable():
        return None
    return session


def rotate_session(
    db: Session,
    raw_refresh_token: str,
    request: Request | None = None,
) -> tuple[UserSession, str]:
    """Spend the presented refresh token and issue its successor.

    Raises SessionReuseError if the token was already rotated away from, and
    InvalidSessionError for everything else.
    """

    settings = get_settings()
    presented_hash = hash_refresh_token(raw_refresh_token)
    now = datetime.now(timezone.utc)

    session = db.scalar(select(UserSession).where(UserSession.refresh_token_hash == presented_hash))

    if session is None:
        # Not the current token. If it is a token this family already rotated
        # past, that is a replay — kill the family.
        replayed = db.scalar(
            select(UserSession).where(UserSession.previous_token_hash == presented_hash)
        )
        if replayed is not None:
            revoke_session(db, replayed, reason="refresh_token_reuse")
            create_security_log(
                db,
                event_type="session_reuse_detected",
                action="refresh_session",
                message="Refresh token replay detected; session family revoked.",
                severity="critical",
                actor_type="user",
                actor_id=str(replayed.user_id),
                organization_id=replayed.organization_id,
                ip_address=_client_ip(request),
                resource_type="user_session",
                resource_id=str(replayed.id),
                status="failure",
                metadata={"rotation_counter": replayed.rotation_counter},
            )
            raise SessionReuseError("Refresh token has already been used.")
        raise InvalidSessionError("Unknown refresh token.")

    if not session.is_usable(now):
        raise InvalidSessionError("Session is revoked or expired.")

    issued = session.issued_at
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    if now - issued > timedelta(days=settings.session_absolute_max_days):
        revoke_session(db, session, reason="absolute_lifetime_reached")
        raise InvalidSessionError("Session has reached its absolute maximum lifetime.")

    new_raw = generate_refresh_token()
    session.previous_token_hash = session.refresh_token_hash
    session.refresh_token_hash = hash_refresh_token(new_raw)
    session.rotation_counter += 1
    session.last_used_at = now
    # Sliding expiry, still bounded by session_absolute_max_days above.
    session.expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    session.user_agent = _user_agent(request) or session.user_agent
    session.ip_address = _client_ip(request) or session.ip_address

    db.flush()
    return session, new_raw


def revoke_session(db: Session, session: UserSession, *, reason: str) -> UserSession:
    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        session.revoked_reason = reason[:100]
    session.is_active = False
    return session


def revoke_all_user_sessions(
    db: Session,
    user_id: uuid.UUID,
    *,
    reason: str,
    except_session_id: uuid.UUID | None = None,
) -> int:
    """Sign a user out everywhere. Used by logout-all, and worth calling from
    any future password-change or role-revocation path."""

    query = select(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.is_active.is_(True),
    )
    revoked = 0
    for session in db.scalars(query):
        if except_session_id is not None and session.id == except_session_id:
            continue
        revoke_session(db, session, reason=reason)
        revoked += 1
    return revoked


def list_active_sessions(db: Session, user_id: uuid.UUID) -> list[UserSession]:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_active.is_(True))
        .order_by(UserSession.issued_at.desc())
    )
    return [row for row in rows if row.is_usable(now)]


def purge_expired_sessions(db: Session) -> int:
    """Delete sessions that are past expiry. Called by the retention prune
    job; never on a request path."""

    now = datetime.now(timezone.utc)
    stale = db.scalars(select(UserSession).where(UserSession.expires_at < now)).all()
    for session in stale:
        db.delete(session)
    return len(stale)
