import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models.anomaly_model import AnomalyModel
from app.models.anomaly_prediction import AnomalyPrediction
from app.models.device import Device
from app.models.user import User
from app.schemas.observability import (
    AnomalyModelResponse,
    AnomalyPredictionResponse,
    AnomalyPredictionReviewRequest,
    DeviceRunResultResponse,
    PipelineRunRequest,
    PipelineRunResponse,
)
from app.services import observability_pipeline_service
from app.services.tenant import assert_same_org, get_scoped_device_or_404, require_org_user

router = APIRouter(prefix="/observability", tags=["AI Observability"])


@router.post("/pipeline/run", response_model=PipelineRunResponse)
def run_pipeline(
    payload: PipelineRunRequest,
    current_user: User = Depends(require_role(["admin", "owner", "engineer", "platform_admin"])),
    db: Session = Depends(get_db),
) -> PipelineRunResponse:
    """Run the shadow-mode observability pipeline for one device or every device in scope."""
    if not get_settings().observability_shadow_mode_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI observability shadow mode is disabled.")

    if payload.device_id is not None:
        devices = [get_scoped_device_or_404(db=db, device_id=payload.device_id, current_user=current_user)]
    else:
        org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)
        statement = select(Device)
        if org_id is not None:
            statement = statement.where(Device.organization_id == org_id)
        devices = list(db.scalars(statement))

    summary = observability_pipeline_service.run_for_devices(db, devices)
    db.commit()

    return PipelineRunResponse(
        devices_processed=summary.devices_processed,
        windows_built=summary.windows_built,
        windows_scored=summary.windows_scored,
        predictions_created=summary.predictions_created,
        device_results=[
            DeviceRunResultResponse(
                device_id=uuid.UUID(r.device_id),
                device_class=r.device_class,
                windows_built=r.windows_built,
                windows_scored=r.windows_scored,
                predictions_created=r.predictions_created,
                errors=r.errors,
                skipped_reason=r.skipped_reason,
            )
            for r in summary.device_results
        ],
    )


@router.get("/anomaly-predictions", response_model=list[AnomalyPredictionResponse])
def list_anomaly_predictions(
    device_id: uuid.UUID | None = None,
    review_status: str | None = None,
    model_name: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AnomalyPrediction]:
    safe_limit = min(max(limit, 1), 500)
    statement = select(AnomalyPrediction).order_by(AnomalyPrediction.created_at.desc()).limit(safe_limit)

    if current_user.role != "platform_admin":
        statement = statement.where(AnomalyPrediction.organization_id == require_org_user(current_user))
    if device_id is not None:
        statement = statement.where(AnomalyPrediction.device_id == device_id)
    if review_status is not None:
        statement = statement.where(AnomalyPrediction.review_status == review_status)
    if model_name is not None:
        statement = statement.where(AnomalyPrediction.model_name == model_name)

    return list(db.scalars(statement))


def _get_scoped_prediction_or_404(db: Session, prediction_id: uuid.UUID, current_user: User) -> AnomalyPrediction:
    prediction = db.get(AnomalyPrediction, prediction_id)
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly prediction not found.")
    assert_same_org(prediction.organization_id, current_user)
    return prediction


@router.get("/anomaly-predictions/{prediction_id}", response_model=AnomalyPredictionResponse)
def get_anomaly_prediction(
    prediction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnomalyPrediction:
    return _get_scoped_prediction_or_404(db, prediction_id, current_user)


@router.patch("/anomaly-predictions/{prediction_id}/review", response_model=AnomalyPredictionResponse)
def review_anomaly_prediction(
    prediction_id: uuid.UUID,
    payload: AnomalyPredictionReviewRequest,
    current_user: User = Depends(require_role(["admin", "owner", "engineer", "platform_admin"])),
    db: Session = Depends(get_db),
) -> AnomalyPrediction:
    prediction = _get_scoped_prediction_or_404(db, prediction_id, current_user)

    prediction.review_status = payload.review_status
    prediction.review_note = payload.review_note
    prediction.reviewed_by = current_user.id
    prediction.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(prediction)
    return prediction


@router.get("/models", response_model=list[AnomalyModelResponse])
def list_anomaly_models(
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> list[AnomalyModel]:
    return list(db.scalars(select(AnomalyModel).order_by(AnomalyModel.created_at.desc())))
