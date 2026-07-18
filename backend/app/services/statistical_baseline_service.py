"""
Deterministic statistical baseline anomaly detector.

Compares a feature window against a rolling baseline (median/MAD) built
from its own device's recent prior windows, using a robust modified
z-score per tracked feature. Sustained deviation across >=2 consecutive
windows gates single-window noise before is_anomalous is set. Always
shadow_mode; never raises Alert/Incident — see docs/ai_observability_architecture.md.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import statistics as stats
from app.ml.feature_schemas import FEATURE_SCHEMA_VERSION
from app.models.anomaly_model import AnomalyModel
from app.models.anomaly_prediction import AnomalyPrediction
from app.models.telemetry_feature_window import TelemetryFeatureWindow

MODEL_NAME = "statistical_baseline_v1"
MODEL_VERSION = "1.0.0"

MIN_PRIOR_WINDOWS = 5
BASELINE_LOOKBACK = 20
Z_SCORE_THRESHOLD = 3.5
SUSTAINED_MIN_WINDOWS = 2
SUSTAINED_LOOKBACK_MAX = 10


def _ensure_model_registered(db: Session) -> AnomalyModel:
    model = db.scalar(
        select(AnomalyModel).where(AnomalyModel.name == MODEL_NAME, AnomalyModel.version == MODEL_VERSION)
    )
    if model is not None:
        return model

    # Applies uniformly across device classes — the math is generic over
    # whatever features a window carries, so one registry row covers both.
    model = AnomalyModel(
        name=MODEL_NAME,
        version=MODEL_VERSION,
        device_class="*",
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        algorithm="statistical_baseline",
        hyperparameters={
            "min_prior_windows": MIN_PRIOR_WINDOWS,
            "baseline_lookback": BASELINE_LOOKBACK,
            "z_score_threshold": Z_SCORE_THRESHOLD,
            "sustained_min_windows": SUSTAINED_MIN_WINDOWS,
            "mad_floor": stats.MAD_FLOOR,
        },
        dataset_hash="deterministic",
        code_commit=None,
        trained_at=datetime.now(timezone.utc),
        artifact_path=None,
        is_active=True,
    )
    db.add(model)
    db.flush()
    return model


def _prior_windows(db: Session, window: TelemetryFeatureWindow) -> list[TelemetryFeatureWindow]:
    return list(
        db.scalars(
            select(TelemetryFeatureWindow)
            .where(
                TelemetryFeatureWindow.device_id == window.device_id,
                TelemetryFeatureWindow.feature_schema_version == window.feature_schema_version,
                TelemetryFeatureWindow.window_start < window.window_start,
            )
            .order_by(TelemetryFeatureWindow.window_start.desc())
            .limit(BASELINE_LOOKBACK)
        )
    )


def _build_feature_comparison(window: TelemetryFeatureWindow, prior: list[TelemetryFeatureWindow]) -> dict:
    comparison: dict[str, dict] = {}
    for feature_name, actual in window.features.items():
        history = [w.features[feature_name] for w in prior if feature_name in w.features]
        if len(history) < MIN_PRIOR_WINDOWS:
            continue
        baseline_median = stats.median(history)
        baseline_mad = stats.mad(history, center=baseline_median)
        z = stats.modified_z_score(actual, baseline_median=baseline_median, baseline_mad=baseline_mad)
        comparison[feature_name] = {
            "baseline": baseline_median,
            "actual": actual,
            "z_score": z,
            "is_affected": abs(z) > Z_SCORE_THRESHOLD,
        }
    return comparison


def _sustained_duration(db: Session, window: TelemetryFeatureWindow, raw_exceeds_threshold: bool) -> int:
    if not raw_exceeds_threshold:
        return 0

    count = 1
    cursor = window
    for _ in range(SUSTAINED_LOOKBACK_MAX):
        prior_prediction = db.scalar(
            select(AnomalyPrediction)
            .join(TelemetryFeatureWindow, AnomalyPrediction.feature_window_id == TelemetryFeatureWindow.id)
            .where(
                AnomalyPrediction.model_name == MODEL_NAME,
                AnomalyPrediction.device_id == window.device_id,
                TelemetryFeatureWindow.window_end == cursor.window_start,
            )
            .limit(1)
        )
        if prior_prediction is None or not prior_prediction.is_anomalous:
            break
        count += 1
        cursor = db.get(TelemetryFeatureWindow, prior_prediction.feature_window_id)
        if cursor is None:
            break

    return count


def _confidence(sustained_duration: int, quality_score: float) -> str:
    if sustained_duration >= 3 and quality_score >= 0.9:
        return "high"
    if sustained_duration >= 2 and quality_score >= 0.7:
        return "medium"
    return "low"


def _explanation(is_anomalous: bool, affected: list[tuple[str, dict]], sustained_duration: int) -> str:
    if not is_anomalous or not affected:
        return "No sustained deviation from the device's recent baseline was detected in tracked features."

    parts = [
        f"{name} {'rose' if info['actual'] > info['baseline'] else 'fell'} from a baseline of "
        f"{info['baseline']:.2f} to {info['actual']:.2f} (z={info['z_score']:.2f})"
        for name, info in affected
    ]
    return f"{'; '.join(parts)}, sustained over {sustained_duration} consecutive 30-minute windows."


def score(db: Session, window: TelemetryFeatureWindow) -> AnomalyPrediction | None:
    """Idempotent: returns the existing prediction if this window was already scored."""
    existing = db.scalar(
        select(AnomalyPrediction).where(
            AnomalyPrediction.feature_window_id == window.id,
            AnomalyPrediction.model_name == MODEL_NAME,
        )
    )
    if existing is not None:
        return existing

    prior = _prior_windows(db, window)
    if len(prior) < MIN_PRIOR_WINDOWS:
        return None

    feature_comparison = _build_feature_comparison(window, prior)
    if not feature_comparison:
        return None

    model = _ensure_model_registered(db)

    anomaly_score = max((abs(info["z_score"]) for info in feature_comparison.values()), default=0.0)
    raw_exceeds_threshold = anomaly_score > Z_SCORE_THRESHOLD

    sustained_duration = _sustained_duration(db, window, raw_exceeds_threshold)
    is_anomalous = raw_exceeds_threshold and sustained_duration >= SUSTAINED_MIN_WINDOWS

    affected = sorted(
        ((name, info) for name, info in feature_comparison.items() if info["is_affected"]),
        key=lambda pair: abs(pair[1]["z_score"]),
        reverse=True,
    )

    prediction = AnomalyPrediction(
        organization_id=window.organization_id,
        device_id=window.device_id,
        feature_window_id=window.id,
        model_name=MODEL_NAME,
        model_version=model.version,
        feature_schema_version=window.feature_schema_version,
        anomaly_score=anomaly_score,
        threshold=Z_SCORE_THRESHOLD,
        is_anomalous=is_anomalous,
        confidence=_confidence(sustained_duration, window.quality_score),
        feature_comparison=feature_comparison,
        explanation=_explanation(is_anomalous, affected, sustained_duration),
        shadow_mode=True,
        review_status="unreviewed",
    )
    db.add(prediction)
    db.flush()
    return prediction
