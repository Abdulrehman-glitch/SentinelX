from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.user_settings import UserSettingsResponse, UserSettingsUpdateRequest
from app.services.audit_log_service import create_audit_log

router = APIRouter(prefix="/user-settings", tags=["User Settings"])


def _get_or_create_settings(user: User, db: Session) -> UserSettings:
    settings = db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))

    if settings:
        return settings

    settings = UserSettings(user_id=user.id)
    db.add(settings)
    db.flush()

    return settings


@router.get("/me", response_model=UserSettingsResponse)
def get_my_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettings:
    settings = _get_or_create_settings(user=current_user, db=db)
    db.commit()
    db.refresh(settings)

    return settings


@router.patch("/me", response_model=UserSettingsResponse)
def update_my_settings(
    payload: UserSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettings:
    settings = _get_or_create_settings(user=current_user, db=db)

    changes = payload.model_dump(exclude_unset=True)

    for field_name, value in changes.items():
        setattr(settings, field_name, value)

    create_audit_log(
        db,
        actor_type="user",
        actor_id=str(current_user.id),
        action="user_settings_updated",
        target_type="user_settings",
        target_id=str(settings.id),
        severity="info",
        message=f"User settings updated: {current_user.email}",
        metadata={"changed_fields": sorted(changes.keys())},
    )

    db.commit()
    db.refresh(settings)

    return settings