"""
IsolationForest inference for laptop_windows_v1 windows only (the first,
and currently only, ML model in this sprint).

Training happens offline (scripts/train_laptop_isolation_forest.py), never
here — this module only loads an already-trained artifact and scores. If no
active model is registered for the device class yet, score() returns None
so the pipeline simply skips ML scoring for that window (the statistical
baseline still runs) rather than erroring.
"""

import joblib
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import model_loader
from app.ml.feature_schemas import FEATURE_SCHEMAS, LAPTOP_WINDOWS_V1
from app.models.anomaly_model import AnomalyModel
from app.models.anomaly_prediction import AnomalyPrediction
from app.models.telemetry_feature_window import TelemetryFeatureWindow

# In-process cache so repeated pipeline runs don't re-deserialize the
# artifact from disk every time. Keyed by "name:version".
_estimator_cache: dict[str, object] = {}


def _load_active_model(db: Session, device_class: str) -> AnomalyModel | None:
    return db.scalar(
        select(AnomalyModel)
        .where(
            AnomalyModel.device_class == device_class,
            AnomalyModel.algorithm == "isolation_forest",
            AnomalyModel.is_active.is_(True),
            AnomalyModel.lifecycle_status != model_loader.RETIRED_STATUS,
        )
        .order_by(AnomalyModel.trained_at.desc())
        .limit(1)
    )


def _get_estimator(model_row: AnomalyModel):
    if not model_row.artifact_path:
        return None
    cache_key = f"{model_row.name}:{model_row.version}"
    if cache_key not in _estimator_cache:
        _estimator_cache[cache_key] = joblib.load(model_row.artifact_path)
    return _estimator_cache[cache_key]


def score(db: Session, window: TelemetryFeatureWindow) -> AnomalyPrediction | None:
    if window.device_class != LAPTOP_WINDOWS_V1:
        return None

    expected_model_name = f"isolation_forest_{window.device_class}"
    existing = db.scalar(
        select(AnomalyPrediction).where(
            AnomalyPrediction.feature_window_id == window.id,
            AnomalyPrediction.model_name == expected_model_name,
        )
    )
    if existing is not None:
        return existing

    model_row = _load_active_model(db, window.device_class)
    if model_row is None:
        return None

    validation = model_loader.validate(model_row, expected_feature_schema_version=window.feature_schema_version)
    if not validation.ok:
        return None

    estimator = _get_estimator(model_row)
    if estimator is None:
        return None

    feature_order = FEATURE_SCHEMAS[window.device_class]
    vector = [window.features.get(name) for name in feature_order]
    if any(value is None for value in vector):
        return None

    # sklearn convention: decision_function is HIGHER for normal points and
    # LOWER for anomalies. Negated once here so a higher anomaly_score always
    # means "more anomalous", matching the statistical baseline's convention.
    # This raw score is never converted into a probability (see req. #10).
    raw_score = float(estimator.decision_function([vector])[0])
    anomaly_score = -raw_score

    threshold = float(model_row.hyperparameters.get("score_threshold", 0.0))
    is_anomalous = anomaly_score > threshold

    # IsolationForest is an ensemble black box — unlike the statistical
    # baseline, it has no clean per-feature z-score, so is_affected/baseline
    # are left None here rather than fabricated. The aggregate score is the
    # honest unit of explanation for this model.
    feature_comparison = {name: {"actual": value, "is_affected": None} for name, value in zip(feature_order, vector)}

    explanation = (
        f"IsolationForest scored this window {anomaly_score:.3f} against a trained threshold of "
        f"{threshold:.3f}, indicating an anomalous combination of features for this device class."
        if is_anomalous
        else f"IsolationForest scored this window {anomaly_score:.3f}, within the trained normal range "
        f"(threshold {threshold:.3f})."
    )

    prediction = AnomalyPrediction(
        organization_id=window.organization_id,
        device_id=window.device_id,
        feature_window_id=window.id,
        model_name=model_row.name,
        model_version=model_row.version,
        feature_schema_version=window.feature_schema_version,
        anomaly_score=anomaly_score,
        threshold=threshold,
        is_anomalous=is_anomalous,
        confidence="medium" if is_anomalous else "low",
        feature_comparison=feature_comparison,
        explanation=explanation,
        shadow_mode=True,
        review_status="unreviewed",
    )
    db.add(prediction)
    db.flush()
    return prediction
