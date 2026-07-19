import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_device_from_token
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import get_recovery_public_key_b64
from app.db.session import get_db
from app.models.device import Device
from app.models.recovery_command import RecoveryCommand
from app.schemas.recovery_command import (
    AgentCapabilitiesRequest,
    AgentRejectRequest,
    CompleteCommandRequest,
    PublicKeyResponse,
    RecoveryCommandResponse,
)
from app.services import agent_capability_service, recovery_command_service
from app.services.recovery_command_service import CompletionInput, RecoveryCommandError

router = APIRouter(prefix="/agent", tags=["Agent Commands"])
_settings = get_settings()


def _require_enabled() -> None:
    if not get_settings().recovery_orchestration_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Safe recovery orchestration is disabled."
        )


def _get_own_command_or_404(db: Session, command_id: uuid.UUID, device: Device) -> RecoveryCommand:
    # Scoped strictly by the authenticated device's own id — never a
    # client-supplied device id (spec: "Do not trust a client-supplied
    # device ID"). A command belonging to another device 404s, same as a
    # nonexistent one, to avoid leaking cross-device command existence.
    command = db.get(RecoveryCommand, command_id)
    if command is None or command.device_id != device.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found.")
    return command


@router.get("/public-key", response_model=PublicKeyResponse)
def get_public_key(
    authenticated_device: Device = Depends(get_device_from_token),
) -> PublicKeyResponse:
    return PublicKeyResponse(public_key=get_recovery_public_key_b64())


@router.post("/capabilities", status_code=status.HTTP_204_NO_CONTENT)
def report_capabilities(
    payload: AgentCapabilitiesRequest,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> None:
    agent_capability_service.upsert_capabilities(
        db,
        device_id=authenticated_device.id,
        organization_id=authenticated_device.organization_id,
        agent_type=payload.agent_type,
        agent_version=payload.agent_version,
        capabilities=[item.model_dump() for item in payload.capabilities],
    )
    db.commit()


@router.get("/commands/next", response_model=RecoveryCommandResponse | None)
@limiter.limit(_settings.rate_limit_telemetry)
def get_next_command(
    request: Request,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> RecoveryCommand | None:
    _require_enabled()
    command = recovery_command_service.get_next_command_for_device(db, authenticated_device)
    db.commit()
    if command is not None:
        db.refresh(command)
    return command


@router.post("/commands/{command_id}/acknowledge", response_model=RecoveryCommandResponse)
def acknowledge_command(
    command_id: uuid.UUID,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    _require_enabled()
    command = _get_own_command_or_404(db, command_id, authenticated_device)
    try:
        recovery_command_service.acknowledge_command(db, command)
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(command)
    return command


@router.post("/commands/{command_id}/start", response_model=RecoveryCommandResponse)
def start_command(
    command_id: uuid.UUID,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    _require_enabled()
    command = _get_own_command_or_404(db, command_id, authenticated_device)
    try:
        recovery_command_service.start_command(db, command)
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(command)
    return command


@router.post("/commands/{command_id}/complete", response_model=RecoveryCommandResponse)
def complete_command(
    command_id: uuid.UUID,
    payload: CompleteCommandRequest,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    _require_enabled()
    command = _get_own_command_or_404(db, command_id, authenticated_device)
    try:
        recovery_command_service.complete_command(
            db,
            command,
            CompletionInput(
                result_code=payload.result_code,
                result_message=payload.result_message,
                result_data=payload.result_data,
                post_action_snapshot=payload.post_action_snapshot,
            ),
        )
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(command)
    return command


@router.post("/commands/{command_id}/reject", response_model=RecoveryCommandResponse)
def reject_command(
    command_id: uuid.UUID,
    payload: AgentRejectRequest,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> RecoveryCommand:
    _require_enabled()
    command = _get_own_command_or_404(db, command_id, authenticated_device)
    try:
        recovery_command_service.reject_command_by_agent(db, command, reason=payload.reason)
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(command)
    return command
