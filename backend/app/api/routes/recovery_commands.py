import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models.anomaly_prediction import AnomalyPrediction
from app.models.recovery_command import RecoveryCommand
from app.models.recovery_command_event import RecoveryCommandEvent
from app.models.user import User
from app.schemas.recovery_command import (
    ProposeFromAnomalyRequest,
    RecoveryCommandCreateRequest,
    RecoveryCommandEventResponse,
    RecoveryCommandResponse,
    RejectRequest,
)
from app.services import recovery_command_service
from app.services.recovery_command_service import RecoveryCommandError
from app.services.tenant import assert_same_org, get_scoped_device_or_404, require_org_user

router = APIRouter(prefix="/recovery-commands", tags=["Recovery Commands"])

_MUTATING_ROLES = ["admin", "owner", "engineer", "platform_admin"]

# AnomalyPrediction.confidence is a qualitative bucket, not a probability
# (see docs/ai_observability_architecture.md) — mapped to an indicative
# float only for display/sorting on the RecoveryCommand row, never used in
# policy decisions.
_CONFIDENCE_BUCKET_TO_FLOAT = {"low": 0.33, "medium": 0.66, "high": 0.9}


def _require_enabled() -> None:
    if not get_settings().recovery_orchestration_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Safe recovery orchestration is disabled."
        )


def _get_scoped_command_or_404(db: Session, command_id: uuid.UUID, current_user: User) -> RecoveryCommand:
    command = db.get(RecoveryCommand, command_id)
    if command is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery command not found.")
    assert_same_org(command.organization_id, current_user)
    return command


@router.post("", response_model=RecoveryCommandResponse, status_code=status.HTTP_201_CREATED)
def create_recovery_command(
    payload: RecoveryCommandCreateRequest,
    current_user: User = Depends(require_role(_MUTATING_ROLES)),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    _require_enabled()
    device = get_scoped_device_or_404(db=db, device_id=payload.device_id, current_user=current_user)

    try:
        command = recovery_command_service.create_command(
            db,
            organization_id=device.organization_id,
            device_id=device.id,
            action_type=payload.action_type,
            parameters=payload.parameters,
            reason=payload.reason,
            decision_source="manual",
            actor_type="user",
            actor_id=str(current_user.id),
        )
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    db.commit()
    db.refresh(command)
    return command


@router.post(
    "/from-anomaly/{prediction_id}",
    response_model=RecoveryCommandResponse,
    status_code=status.HTTP_201_CREATED,
)
def propose_recovery_from_anomaly(
    prediction_id: uuid.UUID,
    payload: ProposeFromAnomalyRequest,
    current_user: User = Depends(require_role(_MUTATING_ROLES)),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    """
    A human reads an AnomalyPrediction's explanation and decides to propose a
    recovery action. The AI supplies inert context (explanation, model
    name/version, confidence) copied onto the new command; it never picks
    the action_type/parameters and cannot bypass the policy engine below —
    create_command() runs the identical evaluate() call for every
    decision_source.
    """

    _require_enabled()

    prediction = db.get(AnomalyPrediction, prediction_id)
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly prediction not found.")
    assert_same_org(prediction.organization_id, current_user)

    try:
        command = recovery_command_service.create_command(
            db,
            organization_id=prediction.organization_id,
            device_id=prediction.device_id,
            action_type=payload.action_type,
            parameters=payload.parameters,
            reason=prediction.explanation,
            decision_source="ai_proposal",
            actor_type="user",
            actor_id=str(current_user.id),
            confidence=_CONFIDENCE_BUCKET_TO_FLOAT.get(prediction.confidence),
            anomaly_prediction_id=prediction.id,
            model_name=prediction.model_name,
            model_version=prediction.model_version,
        )
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    db.commit()
    db.refresh(command)
    return command


@router.get("", response_model=list[RecoveryCommandResponse])
def list_recovery_commands(
    device_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    risk_level: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecoveryCommand]:
    safe_limit = min(max(limit, 1), 500)
    statement = select(RecoveryCommand).order_by(RecoveryCommand.created_at.desc()).limit(safe_limit)

    if current_user.role != "platform_admin":
        statement = statement.where(RecoveryCommand.organization_id == require_org_user(current_user))
    if device_id is not None:
        statement = statement.where(RecoveryCommand.device_id == device_id)
    if status_filter is not None:
        statement = statement.where(RecoveryCommand.status == status_filter)
    if risk_level is not None:
        statement = statement.where(RecoveryCommand.risk_level == risk_level)

    return list(db.scalars(statement))


@router.get("/{command_id}", response_model=RecoveryCommandResponse)
def get_recovery_command(
    command_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    return _get_scoped_command_or_404(db, command_id, current_user)


@router.get("/{command_id}/events", response_model=list[RecoveryCommandEventResponse])
def list_recovery_command_events(
    command_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecoveryCommandEvent]:
    command = _get_scoped_command_or_404(db, command_id, current_user)
    statement = (
        select(RecoveryCommandEvent)
        .where(RecoveryCommandEvent.command_id == command.id)
        .order_by(RecoveryCommandEvent.created_at.asc())
    )
    return list(db.scalars(statement))


@router.patch("/{command_id}/approve", response_model=RecoveryCommandResponse)
def approve_recovery_command(
    command_id: uuid.UUID,
    current_user: User = Depends(require_role(_MUTATING_ROLES)),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    _require_enabled()
    command = _get_scoped_command_or_404(db, command_id, current_user)
    try:
        recovery_command_service.approve_command(db, command, actor_id=str(current_user.id))
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(command)
    return command


@router.patch("/{command_id}/reject", response_model=RecoveryCommandResponse)
def reject_recovery_command(
    command_id: uuid.UUID,
    payload: RejectRequest,
    current_user: User = Depends(require_role(_MUTATING_ROLES)),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    _require_enabled()
    command = _get_scoped_command_or_404(db, command_id, current_user)
    try:
        recovery_command_service.reject_command(
            db, command, actor_type="user", actor_id=str(current_user.id), reason=payload.reason
        )
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(command)
    return command


@router.patch("/{command_id}/cancel", response_model=RecoveryCommandResponse)
def cancel_recovery_command(
    command_id: uuid.UUID,
    current_user: User = Depends(require_role(_MUTATING_ROLES)),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    _require_enabled()
    command = _get_scoped_command_or_404(db, command_id, current_user)
    try:
        recovery_command_service.cancel_command(db, command, actor_id=str(current_user.id))
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(command)
    return command


@router.post("/{command_id}/retry", response_model=RecoveryCommandResponse, status_code=status.HTTP_201_CREATED)
def retry_recovery_command(
    command_id: uuid.UUID,
    current_user: User = Depends(require_role(_MUTATING_ROLES)),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    _require_enabled()
    original = _get_scoped_command_or_404(db, command_id, current_user)
    try:
        new_command = recovery_command_service.retry_command(db, original, actor_id=str(current_user.id))
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(new_command)
    return new_command
