from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.device import Device
from app.models.recovery_action import RecoveryAction
from app.schemas.recovery_action import RecoveryActionCreateRequest, RecoveryActionResponse
from app.services.audit_log_service import create_audit_log

router = APIRouter(prefix="/recovery-actions", tags=["Recovery Actions"])


@router.post("", response_model=RecoveryActionResponse, status_code=status.HTTP_201_CREATED)
def create_recovery_action(
    payload: RecoveryActionCreateRequest,
    db: Session = Depends(get_db),
) -> RecoveryAction:
    device = db.get(Device, payload.device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    recovery_action = RecoveryAction(
        device_id=payload.device_id,
        action_type=payload.action_type,
        status=payload.status,
        details=payload.details,
    )

    db.add(recovery_action)
    db.flush()

    create_audit_log(
        db,
        actor_type="system",
        action="recovery_action_logged",
        target_type="recovery_action",
        target_id=str(recovery_action.id),
        severity="info",
        message=f"Recovery action logged: {payload.action_type}",
        metadata={
            "device_id": str(payload.device_id),
            "action_type": payload.action_type,
            "status": payload.status,
        },
    )

    db.commit()
    db.refresh(recovery_action)

    return recovery_action


@router.get("", response_model=list[RecoveryActionResponse])
def list_recovery_actions(
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[RecoveryAction]:
    safe_limit = min(max(limit, 1), 200)

    statement = (
        select(RecoveryAction)
        .order_by(RecoveryAction.created_at.desc())
        .limit(safe_limit)
    )

    return list(db.scalars(statement))