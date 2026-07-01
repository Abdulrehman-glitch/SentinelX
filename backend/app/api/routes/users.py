import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserRoleUpdateRequest, UserUpdateRequest
from app.services.audit_log_service import create_audit_log
from app.services.tenant import assert_same_org, require_org_user

router = APIRouter(prefix="/users", tags=["Users"])


def _get_user_or_404(user_id: uuid.UUID, current_user: User, db: Session) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    assert_same_org(user.organization_id, current_user)
    return user


@router.get("", response_model=list[UserResponse])
def list_users(
    limit: int = 100,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> list[User]:
    safe_limit = min(max(limit, 1), 500)
    statement = select(User).order_by(User.created_at.desc()).limit(safe_limit)
    if current_user.role != "platform_admin":
        statement = statement.where(User.organization_id == require_org_user(current_user))
    return list(db.scalars(statement))


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> User:
    return _get_user_or_404(user_id=user_id, current_user=current_user, db=db)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> User:
    user = _get_user_or_404(user_id=user_id, current_user=current_user, db=db)

    # Tenant admins cannot edit platform admins.
    if current_user.role != "platform_admin" and user.role == "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify platform admin users.")

    changes = payload.model_dump(exclude_unset=True)
    if "email" in changes and changes["email"]:
        changes["email"] = changes["email"].lower().strip()

    for field_name, value in changes.items():
        setattr(user, field_name, value)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists.") from exc

    create_audit_log(
        db,
        organization_id=user.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="user_updated",
        target_type="user",
        target_id=str(user.id),
        severity="info",
        message=f"User updated: {user.email}",
        metadata={"changed_fields": sorted(changes.keys())},
    )

    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdateRequest,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> User:
    user = _get_user_or_404(user_id=user_id, current_user=current_user, db=db)

    if current_user.role != "platform_admin" and (payload.role == "platform_admin" or user.role == "platform_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only platform admins can manage platform admin roles.")

    previous_role = user.role
    user.role = payload.role

    create_audit_log(
        db,
        organization_id=user.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="role_change",
        target_type="user",
        target_id=str(user.id),
        severity="warning",
        message=f"User role changed from {previous_role} to {payload.role}: {user.email}",
        metadata={"previous_role": previous_role, "new_role": payload.role, "email": user.email},
    )

    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> User:
    user = _get_user_or_404(user_id=user_id, current_user=current_user, db=db)

    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account.")
    if current_user.role != "platform_admin" and user.role == "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot deactivate platform admin users.")

    user.is_active = False

    create_audit_log(
        db,
        organization_id=user.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="user_deactivation",
        target_type="user",
        target_id=str(user.id),
        severity="warning",
        message=f"User deactivated: {user.email}",
        metadata={"email": user.email, "role": user.role},
    )

    db.commit()
    db.refresh(user)
    return user
