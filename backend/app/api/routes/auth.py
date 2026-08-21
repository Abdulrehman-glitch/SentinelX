import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.limiter import client_ip_key, limiter
from app.core.security import (
    create_access_token,
    csrf_tokens_match,
    derive_csrf_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.models.user_session import UserSession
from app.models.user_settings import UserSettings
from app.schemas.auth import (
    LoginResponse,
    MessageResponse,
    SessionResponse,
    SignupRequest,
    TokenResponse,
)
from app.schemas.user import UserPublicResponse
from app.services import session_service
from app.services.audit_log_service import create_audit_log
from app.services.security_log_service import create_security_log
from app.services.session_service import InvalidSessionError, SessionError, SessionReuseError

router = APIRouter(prefix="/auth", tags=["Authentication"])

_settings = get_settings()


# ── Session cookies ───────────────────────────────────────────────────────
#
# The refresh token lives in an HttpOnly, path-scoped cookie. That is the
# whole point of this design: JavaScript cannot read it, so an XSS payload
# that would previously have exfiltrated a 24-hour bearer token from
# localStorage now gets, at worst, a 15-minute access token held in a closure
# — and cannot mint a new one after the tab closes.


def _cookie_attributes() -> dict[str, Any]:
    settings = get_settings()
    return {
        "domain": settings.session_cookie_domain,
        "path": settings.session_cookie_path,
        "secure": bool(settings.session_cookie_secure),
        "samesite": settings.session_cookie_samesite,
    }


def _issue_session_cookies(response: Response, session: UserSession, raw_refresh: str) -> None:
    settings = get_settings()
    max_age = settings.refresh_token_expire_days * 24 * 60 * 60
    attributes = _cookie_attributes()

    response.set_cookie(
        settings.session_cookie_name,
        raw_refresh,
        httponly=True,
        max_age=max_age,
        **attributes,
    )
    # Deliberately readable by JavaScript — the SPA has to echo it back in
    # the X-CSRF-Token header. Its value is derived from the session, so a
    # forged cookie cannot produce a matching header (see derive_csrf_token).
    response.set_cookie(
        settings.csrf_cookie_name,
        derive_csrf_token(session.refresh_token_hash),
        httponly=False,
        max_age=max_age,
        **attributes,
    )


def _clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    attributes = _cookie_attributes()
    attributes.pop("secure", None)
    attributes.pop("samesite", None)
    response.delete_cookie(settings.session_cookie_name, **attributes)
    response.delete_cookie(settings.csrf_cookie_name, **attributes)


def _normalise_email(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def _basic_email_check(email: str) -> bool:
    return "@" in email and "." in email.split("@")[-1] and len(email) <= 255


def _get_client_ip(request: Request) -> str:
    # Delegates to the shared trusted-proxy resolver rather than blindly
    # taking X-Forwarded-For[0], which any caller can forge — these values end
    # up in the security log and are used for abuse investigations, so an
    # attacker must not be able to choose what gets attributed to them.
    return client_ip_key(request)


def _resolve_refresh_session(request: Request, db: Session) -> tuple[UserSession | None, str]:
    """Find the session named by the refresh cookie and enforce CSRF.

    Returns (session_or_None, raw_refresh_token). A missing cookie is a 401;
    a cookie that resolves to a session with a bad CSRF header is a 403. An
    unrecognised cookie value returns (None, raw) so the caller can run
    rotate_session, which is what detects a replayed token.
    """

    settings = get_settings()
    raw_refresh = request.cookies.get(settings.session_cookie_name)
    if not raw_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No active session.")

    session = db.scalar(
        select(UserSession).where(UserSession.refresh_token_hash == hash_refresh_token(raw_refresh))
    )

    # CSRF is checked against the session the server actually resolved, not
    # against whatever cookie value the caller supplied.
    if session is not None:
        presented = request.headers.get(settings.csrf_header_name)
        if not csrf_tokens_match(derive_csrf_token(session.refresh_token_hash), presented):
            create_security_log(
                db,
                event_type="csrf_validation_failure",
                action="refresh_session",
                message="Refresh rejected: CSRF token missing or incorrect.",
                severity="warning",
                actor_type="user",
                actor_id=str(session.user_id),
                organization_id=session.organization_id,
                ip_address=_get_client_ip(request),
                resource_type="user_session",
                resource_id=str(session.id),
                status="failure",
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed.")

    return session, raw_refresh


def _access_claims(user: User) -> dict[str, Any]:
    claims: dict[str, Any] = {"email": user.email, "role": user.role}
    if user.organization_id:
        claims["organization_id"] = str(user.organization_id)
    return claims


async def _extract_login_payload(request: Request) -> tuple[str, str]:
    content_type = request.headers.get("content-type", "").lower()
    raw_data: dict[str, Any] = {}

    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                raw_data = body
        except Exception:
            raw_data = {}
    else:
        try:
            form = await request.form()
            raw_data = dict(form)
        except Exception:
            raw_data = {}

    email_or_username = raw_data.get("email") or raw_data.get("username")
    password = raw_data.get("password")

    email = _normalise_email(str(email_or_username) if email_or_username else None)
    password_value = str(password) if password is not None else ""

    if not email or not password_value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email/username and password are required.",
        )

    return email, password_value


@router.post("/signup", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(_settings.rate_limit_signup, key_func=client_ip_key)
def signup(
    request: Request,
    payload: SignupRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    email = _normalise_email(payload.email)
    ip = _get_client_ip(request)

    # Read live rather than via the module-level _settings so the flag can be
    # flipped without a restart in tests and by a config reload in deployment.
    if not get_settings().public_signup_enabled:
        create_security_log(
            db,
            event_type="signup_disabled",
            action="user_signup_attempt",
            message="Signup attempt while public registration is disabled.",
            severity="warning",
            actor_type="anonymous",
            ip_address=ip,
            status="failure",
            metadata={"email": email},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled. Ask an administrator for an account.",
        )

    if not _basic_email_check(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A valid email address is required.",
        )

    existing_user = db.scalar(select(User).where(User.email == email))

    if existing_user:
        create_security_log(
            db,
            event_type="signup_duplicate",
            action="user_signup_attempt",
            message=f"Signup attempt with existing email: {email}",
            severity="warning",
            actor_type="anonymous",
            ip_address=ip,
            status="failure",
            metadata={"email": email},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    total_users = db.scalar(select(func.count(User.id))) or 0

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role="admin" if total_users == 0 else "viewer",
        is_active=True,
    )

    db.add(user)
    db.flush()

    db.add(UserSettings(user_id=user.id))

    create_audit_log(
        db,
        organization_id=user.organization_id,
        actor_type="system",
        actor_id=str(user.id),
        action="user_signup",
        target_type="user",
        target_id=str(user.id),
        severity="info",
        message=f"New user registered: {user.email}",
        metadata={"email": user.email, "role": user.role},
    )

    create_security_log(
        db,
        event_type="user_created",
        action="user_signup",
        message=f"New user signed up: {user.email}",
        severity="info",
        actor_type="user",
        actor_id=str(user.id),
        ip_address=ip,
        resource_type="user",
        resource_id=str(user.id),
        status="success",
        metadata={"email": user.email, "role": user.role},
    )

    session, raw_refresh = session_service.create_session(db, user, request)

    db.commit()
    db.refresh(user)
    db.refresh(session)

    access_token = create_access_token(
        subject=str(user.id),
        session_id=str(session.id),
        extra_claims=_access_claims(user),
    )
    _issue_session_cookies(response, session, raw_refresh)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=get_settings().access_token_expire_minutes * 60,
        user=UserPublicResponse.model_validate(user),
    )


def _login_user(
    request: Request,
    response: Response,
    db: Session,
    *,
    email: str,
    password: str,
) -> LoginResponse:
    ip = _get_client_ip(request)

    user = db.scalar(select(User).where(User.email == email))

    if not user or not verify_password(password, user.password_hash):
        create_audit_log(
            db,
            organization_id=user.organization_id if user else None,
            actor_type="user",
            actor_id=email,
            action="login_failure",
            target_type="user",
            target_id=email,
            severity="warning",
            message=f"Failed login attempt for: {email}",
            metadata={"email": email, "ip": ip},
        )
        create_security_log(
            db,
            event_type="login_failure",
            action="authenticate",
            message=f"Failed login for: {email}",
            severity="warning",
            actor_type="anonymous",
            actor_id=email,
            ip_address=ip,
            status="failure",
            metadata={"email": email},
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        create_security_log(
            db,
            event_type="login_inactive_user",
            action="authenticate",
            message=f"Inactive user login attempt: {email}",
            severity="warning",
            actor_type="user",
            actor_id=str(user.id),
            ip_address=ip,
            organization_id=user.organization_id,
            status="failure",
            metadata={"email": email},
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    user.last_login_at = datetime.now(timezone.utc)

    session, raw_refresh = session_service.create_session(db, user, request)
    access_token = create_access_token(
        subject=str(user.id),
        session_id=str(session.id),
        extra_claims=_access_claims(user),
    )

    create_audit_log(
        db,
        organization_id=user.organization_id,
        actor_type="user",
        actor_id=str(user.id),
        action="login_success",
        target_type="user",
        target_id=str(user.id),
        severity="info",
        message=f"User logged in: {user.email}",
        metadata={"email": user.email, "role": user.role},
    )

    create_security_log(
        db,
        event_type="login_success",
        action="authenticate",
        message=f"Successful login: {user.email}",
        severity="info",
        actor_type="user",
        actor_id=str(user.id),
        ip_address=ip,
        organization_id=user.organization_id,
        status="success",
        metadata={"email": user.email, "role": user.role},
    )

    db.commit()
    db.refresh(user)
    db.refresh(session)

    _issue_session_cookies(response, session, raw_refresh)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=get_settings().access_token_expire_minutes * 60,
        user=UserPublicResponse.model_validate(user),
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit(_settings.rate_limit_login, key_func=client_ip_key)
async def login(request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    email, password = await _extract_login_payload(request)
    return _login_user(request, response, db, email=email, password=password)


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
@limiter.limit(_settings.rate_limit_login, key_func=client_ip_key)
def token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """OAuth2 password-flow token endpoint used by Swagger UI's Authorize form.

    Opens a real session like every other login path, so a token minted here
    is revocable and expires on the same 15-minute clock.
    """

    login_result = _login_user(
        request,
        response,
        db,
        email=_normalise_email(form_data.username),
        password=form_data.password,
    )
    return TokenResponse(
        access_token=login_result.access_token,
        token_type=login_result.token_type,
        expires_in=login_result.expires_in,
    )


@router.post("/refresh", response_model=LoginResponse)
@limiter.limit(_settings.rate_limit_login, key_func=client_ip_key)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    """Exchange the HttpOnly refresh cookie for a fresh access token.

    Rotates the refresh token on every call. Replaying a spent token revokes
    the entire session family (session_service.rotate_session) — the client
    is signed out rather than quietly re-issued, because at that point the
    server cannot tell the legitimate client from the thief.
    """

    ip = _get_client_ip(request)
    _existing, raw_refresh = _resolve_refresh_session(request, db)

    try:
        session, new_raw = session_service.rotate_session(db, raw_refresh, request)
    except SessionReuseError as exc:
        db.commit()
        _clear_session_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ended for security reasons. Please sign in again.",
        ) from exc
    except (InvalidSessionError, SessionError) as exc:
        _clear_session_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is no longer valid. Please sign in again.",
        ) from exc

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        session_service.revoke_session(db, session, reason="user_inactive_or_deleted")
        db.commit()
        _clear_session_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is no longer valid. Please sign in again.",
        )

    # Claims are rebuilt from the live user row, so a role or org change takes
    # effect on the next refresh instead of persisting for the token's life.
    access_token = create_access_token(
        subject=str(user.id),
        session_id=str(session.id),
        extra_claims=_access_claims(user),
    )

    create_security_log(
        db,
        event_type="session_refreshed",
        action="refresh_session",
        message=f"Session refreshed for {user.email}.",
        severity="info",
        actor_type="user",
        actor_id=str(user.id),
        ip_address=ip,
        organization_id=user.organization_id,
        resource_type="user_session",
        resource_id=str(session.id),
        status="success",
        metadata={"rotation_counter": session.rotation_counter},
    )

    db.commit()
    db.refresh(session)
    db.refresh(user)

    _issue_session_cookies(response, session, new_raw)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=get_settings().access_token_expire_minutes * 60,
        user=UserPublicResponse.model_validate(user),
    )


@router.get("/me", response_model=UserPublicResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def _session_from_bearer(request: Request, db: Session) -> UserSession | None:
    """Best-effort: read the session id out of the presented access token.

    Tolerates an expired or malformed token — logout must still work when the
    access token has already lapsed, which is exactly when a user is most
    likely to click "sign out".
    """

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None

    import jwt

    from app.core.security import decode_access_token

    raw = header.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(raw)
    except jwt.ExpiredSignatureError:
        # Signature was valid; only the clock ran out. Safe to read `sid`
        # without verifying expiry, because revoking a session the caller
        # already proved they held is not a privilege escalation.
        try:
            settings = get_settings()
            payload = jwt.decode(
                raw,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
                options={"verify_exp": False},
            )
        except jwt.PyJWTError:
            return None
    except jwt.PyJWTError:
        return None

    try:
        return db.get(UserSession, uuid.UUID(str(payload.get("sid"))))
    except (TypeError, ValueError):
        return None


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Ends the session server-side and clears the cookies.

    Unauthenticated on purpose: it resolves the session from the access token
    when one is present and falls back to the refresh cookie otherwise, so an
    expired token still produces a real logout instead of a 401 that leaves
    the session alive. It always returns 200 — telling an anonymous caller
    whether a session existed would be an oracle.
    """

    ip = _get_client_ip(request)
    settings = get_settings()

    session = _session_from_bearer(request, db)

    if session is None:
        raw_refresh = request.cookies.get(settings.session_cookie_name)
        if raw_refresh:
            session = db.scalar(
                select(UserSession).where(
                    UserSession.refresh_token_hash == hash_refresh_token(raw_refresh)
                )
            )

    if session is None:
        _clear_session_cookies(response)
        return MessageResponse(message="Signed out.")

    current_user = db.get(User, session.user_id)
    session_service.revoke_session(db, session, reason="user_logout")

    if current_user is None:
        db.commit()
        _clear_session_cookies(response)
        return MessageResponse(message="Signed out.")

    create_audit_log(
        db,
        organization_id=current_user.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="logout",
        target_type="user",
        target_id=str(current_user.id),
        severity="info",
        message=f"User logged out: {current_user.email}",
        metadata={"email": current_user.email},
    )

    create_security_log(
        db,
        event_type="logout",
        action="logout",
        message=f"User logged out: {current_user.email}",
        severity="info",
        actor_type="user",
        actor_id=str(current_user.id),
        ip_address=ip,
        organization_id=current_user.organization_id,
        status="success",
        resource_type="user_session",
        resource_id=str(session.id),
    )

    db.commit()
    _clear_session_cookies(response)

    return MessageResponse(message="Signed out.")


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Revoke every session for the signed-in user, including this one.

    The lever to pull after a suspected credential compromise; also the
    correct follow-up to a password change.
    """

    revoked = session_service.revoke_all_user_sessions(
        db, current_user.id, reason="user_logout_all"
    )

    create_audit_log(
        db,
        organization_id=current_user.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="logout_all_sessions",
        target_type="user",
        target_id=str(current_user.id),
        severity="warning",
        message=f"All sessions revoked for {current_user.email} ({revoked} session(s)).",
        metadata={"revoked_sessions": revoked},
    )
    create_security_log(
        db,
        event_type="sessions_revoked",
        action="logout_all",
        message=f"All sessions revoked for {current_user.email}.",
        severity="warning",
        actor_type="user",
        actor_id=str(current_user.id),
        ip_address=_get_client_ip(request),
        organization_id=current_user.organization_id,
        status="success",
        metadata={"revoked_sessions": revoked},
    )

    db.commit()
    _clear_session_cookies(response)

    return MessageResponse(message=f"Revoked {revoked} session(s).")


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserSession]:
    """The signed-in user's own live sessions. Scoped to the caller only —
    there is deliberately no way to list another user's sessions here."""

    return session_service.list_active_sessions(db, current_user.id)
