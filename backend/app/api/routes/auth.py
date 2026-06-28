from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.auth import LoginRequest, LoginResponse, MessageResponse, SignupRequest
from app.schemas.user import UserPublicResponse
from app.services.audit_log_service import create_audit_log

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserPublicResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> User:
    """
    Creates a new user account.

    Development note:
    This endpoint is intentionally simple for the coursework MVP. In a
    production system, public admin signup should be disabled after initial
    setup or restricted by invitation.
    """

    email = payload.email.lower().strip()

    existing_user = db.scalar(select(User).where(User.email == email))

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    total_users = db.scalar(select(func.count(User.id))) or 0

    # First user can be admin. After that, public signup is restricted to the requested role
    # for development/demo convenience. This should become invitation/admin-created later.
    user = User(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role if total_users >= 0 else "viewer",
        is_active=True,
    )

    db.add(user)
    db.flush()

    settings = UserSettings(user_id=user.id)
    db.add(settings)

    create_audit_log(
        db,
        actor_type="system",
        actor_id=str(user.id),
        action="user_signup",
        target_type="user",
        target_id=str(user.id),
        severity="info",
        message=f"User signed up: {user.email}",
        metadata={"email": user.email, "role": user.role},
    )

    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """
    Authenticates a user and returns a JWT access token.
    """

    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))

    if not user or not verify_password(payload.password, user.password_hash):
        create_audit_log(
            db,
            actor_type="user",
            actor_id=email,
            action="login_failure",
            target_type="user",
            target_id=email,
            severity="warning",
            message=f"Failed login attempt for: {email}",
            metadata={"email": email},
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        create_audit_log(
            db,
            actor_type="user",
            actor_id=str(user.id),
            action="login_failure",
            target_type="user",
            target_id=str(user.id),
            severity="warning",
            message=f"Inactive user attempted login: {email}",
            metadata={"email": email, "reason": "inactive"},
        )
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    user.last_login_at = datetime.now(timezone.utc)

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "email": user.email,
            "role": user.role,
        },
    )

    create_audit_log(
        db,
        actor_type="user",
        actor_id=str(user.id),
        action="login_success",
        target_type="user",
        target_id=str(user.id),
        severity="info",
        message=f"User logged in: {user.email}",
        metadata={"email": user.email, "role": user.role},
    )

    db.commit()
    db.refresh(user)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserPublicResponse.model_validate(user),
    )


@router.get("/me", response_model=UserPublicResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """
    Returns the authenticated user.
    """

    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """
    Log-only logout endpoint.

    JWTs remain stateless in this MVP. Token blacklist can be added later if
    required.
    """

    create_audit_log(
        db,
        actor_type="user",
        actor_id=str(current_user.id),
        action="logout",
        target_type="user",
        target_id=str(current_user.id),
        severity="info",
        message=f"User logged out: {current_user.email}",
        metadata={"email": current_user.email},
    )

    db.commit()

    return MessageResponse(message="Logout recorded successfully.")