import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models.device import Device
from app.models.hybrid_decision import HybridDecision
from app.models.recovery_command import RecoveryCommand
from app.models.telemetry_feature_window import TelemetryFeatureWindow
from app.models.user import User
from app.schemas.recovery_command import RecoveryCommandResponse
from app.schemas.hybrid_detection import (
    DeviceHybridRunResultResponse,
    HybridDecisionResponse,
    HybridDecisionReviewRequest,
    HybridRunRequest,
    HybridRunResponse,
)
from app.services import ai_recommendation_service, hybrid_detection_service
from app.services.recovery_command_service import RecoveryCommandError
from app.services.tenant import assert_same_org, get_scoped_device_or_404, require_org_user

router = APIRouter(prefix="/hybrid", tags=["Hybrid Detection"])


def _require_enabled() -> None:
    if not get_settings().hybrid_detection_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hybrid detection is disabled.")


@router.post("/decisions/run", response_model=HybridRunResponse)
def run_hybrid_pipeline(
    payload: HybridRunRequest,
    current_user: User = Depends(require_role(["admin", "owner", "engineer", "platform_admin"])),
    db: Session = Depends(get_db),
) -> HybridRunResponse:
    """Run the hybrid detection pipeline for one device or every device in scope."""
    _require_enabled()

    if payload.device_id is not None:
        devices = [get_scoped_device_or_404(db=db, device_id=payload.device_id, current_user=current_user)]
    else:
        org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)
        statement = select(Device)
        if org_id is not None:
            statement = statement.where(Device.organization_id == org_id)
        devices = list(db.scalars(statement))

    summary = hybrid_detection_service.run_for_devices(db, devices)
    db.commit()

    return HybridRunResponse(
        devices_processed=summary.devices_processed,
        windows_built=summary.windows_built,
        windows_scored=summary.windows_scored,
        decisions_created=summary.decisions_created,
        device_results=[
            DeviceHybridRunResultResponse(
                device_id=uuid.UUID(r.device_id),
                device_class=r.device_class,
                windows_built=r.windows_built,
                windows_scored=r.windows_scored,
                decisions_created=r.decisions_created,
                errors=r.errors,
                skipped_reason=r.skipped_reason,
            )
            for r in summary.device_results
        ],
    )


@router.get("/decisions", response_model=list[HybridDecisionResponse])
def list_hybrid_decisions(
    device_id: uuid.UUID | None = None,
    device_class: str | None = None,
    severity: str | None = None,
    detector_agreement: str | None = None,
    model_version: str | None = None,
    review_status: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HybridDecision]:
    safe_limit = min(max(limit, 1), 500)
    statement = select(HybridDecision).order_by(HybridDecision.created_at.desc()).limit(safe_limit)

    if current_user.role != "platform_admin":
        statement = statement.where(HybridDecision.organization_id == require_org_user(current_user))
    if device_id is not None:
        statement = statement.where(HybridDecision.device_id == device_id)
    if severity is not None:
        statement = statement.where(HybridDecision.combined_severity == severity)
    if detector_agreement is not None:
        statement = statement.where(HybridDecision.detector_agreement == detector_agreement)
    if model_version is not None:
        statement = statement.where(HybridDecision.model_version == model_version)
    if review_status is not None:
        statement = statement.where(HybridDecision.review_status == review_status)
    if device_class is not None:
        statement = statement.join(
            TelemetryFeatureWindow, HybridDecision.feature_window_id == TelemetryFeatureWindow.id
        ).where(TelemetryFeatureWindow.device_class == device_class)

    return list(db.scalars(statement))


def _get_scoped_decision_or_404(db: Session, decision_id: uuid.UUID, current_user: User) -> HybridDecision:
    decision = db.get(HybridDecision, decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hybrid decision not found.")
    assert_same_org(decision.organization_id, current_user)
    return decision


@router.get("/decisions/{decision_id}", response_model=HybridDecisionResponse)
def get_hybrid_decision(
    decision_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HybridDecision:
    return _get_scoped_decision_or_404(db, decision_id, current_user)


@router.patch("/decisions/{decision_id}/review", response_model=HybridDecisionResponse)
def review_hybrid_decision(
    decision_id: uuid.UUID,
    payload: HybridDecisionReviewRequest,
    current_user: User = Depends(require_role(["admin", "owner", "engineer", "platform_admin"])),
    db: Session = Depends(get_db),
) -> HybridDecision:
    decision = _get_scoped_decision_or_404(db, decision_id, current_user)

    decision.review_status = payload.review_status
    decision.review_note = payload.review_note
    decision.reviewed_by = current_user.id
    decision.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(decision)
    return decision


@router.post("/decisions/{decision_id}/propose-recovery", response_model=RecoveryCommandResponse | None)
def propose_recovery_from_hybrid_decision(
    decision_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "owner", "engineer", "platform_admin"])),
    db: Session = Depends(get_db),
) -> RecoveryCommand | None:
    """
    Human-triggered equivalent of the automatic proposal that runs during
    `/hybrid/decisions/run` when self_healing_automation_enabled is True.
    Restricted to the same allowlist (collect_diagnostics,
    retry_telemetry_sync) and the same unmodified policy/signing pipeline —
    returns None (not an error) if nothing is recommended or the policy
    engine rejects the proposal (cooldown/limit/breaker/disabled).
    """
    _require_enabled()
    decision = _get_scoped_decision_or_404(db, decision_id, current_user)

    try:
        command = ai_recommendation_service.propose_from_hybrid_decision(
            db, decision, actor_id=str(current_user.id)
        )
    except RecoveryCommandError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    db.commit()
    if command is not None:
        db.refresh(command)
    return command
