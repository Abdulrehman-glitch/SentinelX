"""
Computes a ModelEvaluationReport for one registered model over a review
period, using human-reviewed AnomalyPrediction rows as labels. Never
computes recall — there is no reliable "known positive" ground truth in
this system, only what a human has chosen to review (see
docs/ai_observability_architecture.md). Fields this system genuinely can't
measure yet (e.g. inference_failures) are left null, never fabricated.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml.feature_schemas import FEATURE_SCHEMAS
from app.models.anomaly_model import AnomalyModel
from app.models.anomaly_prediction import AnomalyPrediction
from app.models.hybrid_decision import HybridDecision
from app.models.incident import Incident
from app.models.model_evaluation_report import ModelEvaluationReport
from app.models.telemetry_feature_window import TelemetryFeatureWindow

_LABELED_REVIEW_STATUSES = {"true_positive", "false_positive", "expected_change", "insufficient_context", "duplicate"}


def _detector_agreement_breakdown(db: Session, feature_window_ids: list[uuid.UUID]) -> dict[str, int]:
    if not feature_window_ids:
        return {}
    rows = db.execute(
        select(HybridDecision.detector_agreement, func.count())
        .where(HybridDecision.feature_window_id.in_(feature_window_ids))
        .group_by(HybridDecision.detector_agreement)
    ).all()
    return {agreement: count for agreement, count in rows}


def _missing_feature_rate(db: Session, model: AnomalyModel, period_start: datetime, period_end: datetime) -> float | None:
    expected_features = FEATURE_SCHEMAS.get(model.device_class)
    if not expected_features:
        return None

    windows = list(
        db.scalars(
            select(TelemetryFeatureWindow).where(
                TelemetryFeatureWindow.device_class == model.device_class,
                TelemetryFeatureWindow.window_start >= period_start,
                TelemetryFeatureWindow.window_start < period_end,
            )
        )
    )
    if not windows:
        return None

    missing = sum(1 for w in windows if any(name not in w.features for name in expected_features))
    return missing / len(windows)


def _anomaly_lead_time_seconds_avg(db: Session, true_positive_predictions: list[AnomalyPrediction]) -> float | None:
    """Proxy lead time: seconds between a confirmed true-positive prediction
    and the next Incident opened for that device afterwards. Best-effort —
    not every true positive has a linked incident."""
    lead_times: list[float] = []
    for prediction in true_positive_predictions:
        following_incident = db.scalar(
            select(Incident)
            .where(Incident.device_id == prediction.device_id, Incident.created_at >= prediction.created_at)
            .order_by(Incident.created_at.asc())
            .limit(1)
        )
        if following_incident is not None:
            lead_times.append((following_incident.created_at - prediction.created_at).total_seconds())

    return (sum(lead_times) / len(lead_times)) if lead_times else None


def generate_report(
    db: Session,
    model: AnomalyModel,
    *,
    period_start: datetime,
    period_end: datetime,
    created_by: uuid.UUID | None,
) -> ModelEvaluationReport:
    predictions = list(
        db.scalars(
            select(AnomalyPrediction).where(
                AnomalyPrediction.model_name == model.name,
                AnomalyPrediction.model_version == model.version,
                AnomalyPrediction.created_at >= period_start,
                AnomalyPrediction.created_at < period_end,
            )
        )
    )

    reviewed = [p for p in predictions if p.review_status in _LABELED_REVIEW_STATUSES]
    true_positive_predictions = [p for p in reviewed if p.review_status == "true_positive"]
    false_positive_count = sum(1 for p in reviewed if p.review_status == "false_positive")
    expected_change_count = sum(1 for p in reviewed if p.review_status == "expected_change")

    labeled_for_precision = len(true_positive_predictions) + false_positive_count
    precision = (len(true_positive_predictions) / labeled_for_precision) if labeled_for_precision else None
    false_positive_rate = (false_positive_count / labeled_for_precision) if labeled_for_precision else None

    report = ModelEvaluationReport(
        model_id=model.id,
        period_start=period_start,
        period_end=period_end,
        prediction_count=len(predictions),
        reviewed_count=len(reviewed),
        true_positives=len(true_positive_predictions),
        false_positives=false_positive_count,
        expected_changes=expected_change_count,
        precision=precision,
        false_positive_rate=false_positive_rate,
        detector_agreement_breakdown=_detector_agreement_breakdown(
            db, [p.feature_window_id for p in predictions]
        ),
        supported_device_coverage=len({p.device_id for p in predictions}),
        missing_feature_rate=_missing_feature_rate(db, model, period_start, period_end),
        inference_failures=None,
        anomaly_lead_time_seconds_avg=_anomaly_lead_time_seconds_avg(db, true_positive_predictions),
        created_by=created_by,
    )
    db.add(report)
    db.flush()
    return report
