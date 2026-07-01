from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.auth import LoginResponse, MessageResponse, SignupRequest, TokenResponse
from app.schemas.user import UserPublicResponse
from app.services.audit_log_service import create_audit_log
from app.services.security_log_service import create_security_log

router = APIRouter(prefix="/auth", tags=["Authentication"])

_settings = get_settings()


def _normalise_email(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def _basic_email_check(email: str) -> bool:
    return "@" in email and "." in email.split("@")[-1] and len(email) <= 255


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


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
@limiter.limit(_settings.rate_limit_signup)
def signup(request: Request, payload: SignupRequest, db: Session = Depends(get_db)) -> LoginResponse:
    email = _normalise_email(payload.email)
    ip = _get_client_ip(request)

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

    db.commit()
    db.refresh(user)

    extra_claims = {"email": user.email, "role": user.role}
    if user.organization_id:
        extra_claims["organization_id"] = str(user.organization_id)

    access_token = create_access_token(subject=str(user.id), extra_claims=extra_claims)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserPublicResponse.model_validate(user),
    )


def _login_user(request: Request, db: Session, *, email: str, password: str) -> LoginResponse:
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

    extra_claims = {"email": user.email, "role": user.role}
    if user.organization_id:
        extra_claims["organization_id"] = str(user.organization_id)

    access_token = create_access_token(subject=str(user.id), extra_claims=extra_claims)

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

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserPublicResponse.model_validate(user),
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit(_settings.rate_limit_login)
async def login(request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    email, password = await _extract_login_payload(request)
    return _login_user(request, db, email=email, password=password)


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
@limiter.limit(_settings.rate_limit_login)
def token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """OAuth2 password-flow token endpoint used by Swagger UI's Authorize form."""

    response = _login_user(
        request,
        db,
        email=_normalise_email(form_data.username),
        password=form_data.password,
    )
    return TokenResponse(access_token=response.access_token, token_type=response.token_type)


@router.get("/me", response_model=UserPublicResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    ip = _get_client_ip(request)

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
    )

    db.commit()

    return MessageResponse(message="Logout recorded successfully.")
