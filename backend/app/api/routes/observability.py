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
from app.models.model_evaluation_report import ModelEvaluationReport
from app.schemas.observability import (
    AnomalyModelResponse,
    AnomalyPredictionResponse,
    AnomalyPredictionReviewRequest,
    DeviceRunResultResponse,
    ModelEvaluationReportResponse,
    ModelEvaluationRequest,
    ModelPromoteRequest,
    ModelRetireRequest,
    PipelineRunRequest,
    PipelineRunResponse,
)
from app.services import model_evaluation_service, observability_pipeline_service
from app.services.model_promotion_service import PromotionError, promote, retire
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


def _get_model_or_404(db: Session, model_id: uuid.UUID) -> AnomalyModel:
    model = db.get(AnomalyModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found.")
    return model


@router.post("/models/{model_id}/evaluate", response_model=ModelEvaluationReportResponse)
def evaluate_model(
    model_id: uuid.UUID,
    payload: ModelEvaluationRequest,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> ModelEvaluationReport:
    model = _get_model_or_404(db, model_id)
    report = model_evaluation_service.generate_report(
        db,
        model,
        period_start=payload.period_start,
        period_end=payload.period_end,
        created_by=current_user.id,
    )
    db.commit()
    db.refresh(report)
    return report


@router.get("/models/{model_id}/evaluations", response_model=list[ModelEvaluationReportResponse])
def list_model_evaluations(
    model_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> list[ModelEvaluationReport]:
    _get_model_or_404(db, model_id)
    return list(
        db.scalars(
            select(ModelEvaluationReport)
            .where(ModelEvaluationReport.model_id == model_id)
            .order_by(ModelEvaluationReport.created_at.desc())
        )
    )


@router.post("/models/{model_id}/promote", response_model=AnomalyModelResponse)
def promote_model(
    model_id: uuid.UUID,
    payload: ModelPromoteRequest,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> AnomalyModel:
    model = _get_model_or_404(db, model_id)

    evaluation = None
    if payload.evaluation_report_id is not None:
        evaluation = db.get(ModelEvaluationReport, payload.evaluation_report_id)
        if evaluation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation report not found.")

    try:
        promote(db, model, target_status=payload.target_status, actor_id=str(current_user.id), evaluation=evaluation)
    except PromotionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    db.commit()
    db.refresh(model)
    return model


@router.post("/models/{model_id}/retire", response_model=AnomalyModelResponse)
def retire_model(
    model_id: uuid.UUID,
    payload: ModelRetireRequest,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> AnomalyModel:
    model = _get_model_or_404(db, model_id)

    try:
        retire(db, model, actor_id=str(current_user.id), reason=payload.reason)
    except PromotionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    db.commit()
    db.refresh(model)
    return model
