from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_device_from_token, require_role
from app.db.session import get_db
from app.models.device import Device
from app.models.recovery_action import RecoveryAction
from app.models.user import User
from app.schemas.recovery_action import RecoveryActionCreateRequest, RecoveryActionResponse
from app.services.audit_log_service import create_audit_log
from app.services.tenant import assert_same_org, require_org_user

router = APIRouter(prefix="/recovery-actions", tags=["Recovery Actions"])


@router.post("", response_model=RecoveryActionResponse, status_code=status.HTTP_201_CREATED)
def create_recovery_action(
    payload: RecoveryActionCreateRequest,
    current_user: User = Depends(require_role(["admin", "engineer", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> RecoveryAction:
    device = db.get(Device, payload.device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    assert_same_org(device.organization_id, current_user)

    recovery_action = RecoveryAction(
        organization_id=device.organization_id,
        device_id=device.id,
        action_type=payload.action_type,
        status=payload.status,
        details=payload.details,
    )

    db.add(recovery_action)
    db.flush()

    create_audit_log(
        db,
        organization_id=device.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="recovery_action_logged",
        target_type="recovery_action",
        target_id=str(recovery_action.id),
        severity="info",
        message=f"Recovery action logged: {payload.action_type}",
        metadata={"device_id": str(device.id), "action_type": payload.action_type, "status": payload.status},
    )

    db.commit()
    db.refresh(recovery_action)
    return recovery_action


@router.post("/agent-log", response_model=RecoveryActionResponse, status_code=status.HTTP_201_CREATED)
def create_agent_recovery_action(
    payload: RecoveryActionCreateRequest,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> RecoveryAction:
    """Allow a device agent to log a recovery action only for itself."""
    if payload.device_id != authenticated_device.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device token does not match payload device_id.")
    if authenticated_device.organization_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Device is not associated with an organization.")

    recovery_action = RecoveryAction(
        organization_id=authenticated_device.organization_id,
        device_id=authenticated_device.id,
        action_type=payload.action_type,
        status=payload.status,
        details=payload.details,
    )
    db.add(recovery_action)
    db.flush()

    create_audit_log(
        db,
        organization_id=authenticated_device.organization_id,
        actor_type="agent",
        actor_id=str(authenticated_device.id),
        action="recovery_action_logged",
        target_type="recovery_action",
        target_id=str(recovery_action.id),
        severity="info",
        message=f"Agent recovery action logged: {payload.action_type}",
        metadata={"device_id": str(authenticated_device.id), "status": payload.status},
    )

    db.commit()
    db.refresh(recovery_action)
    return recovery_action


@router.get("", response_model=list[RecoveryActionResponse])
def list_recovery_actions(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecoveryAction]:
    safe_limit = min(max(limit, 1), 200)
    q = select(RecoveryAction).order_by(RecoveryAction.created_at.desc()).limit(safe_limit)
    if current_user.role != "platform_admin":
        q = q.where(RecoveryAction.organization_id == require_org_user(current_user))
    return list(db.scalars(q))
