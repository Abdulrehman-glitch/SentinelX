"""
Safe, read-only historical replay of the hybrid detection pipeline for a
selected model version, scoring-policy version, device class, and date
range. Reuses hybrid_detection_service's pure combination logic (rule
lookup, agreement, severity, risk, persistence, incident/recovery context —
none of which ever write to the database) but never persists a decision:
no AnomalyPrediction, no HybridDecision, no Alert/Incident/RecoveryCommand
row is ever created or modified. Reproducible for a fixed DB state.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

import joblib
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import model_loader
from app.ml.feature_schemas import FEATURE_SCHEMAS
from app.models.anomaly_model import AnomalyModel
from app.models.device import Device
from app.models.telemetry_feature_window import TelemetryFeatureWindow
from app.services import hybrid_detection_service, statistical_baseline_service


@dataclass(frozen=True)
class ReplayDecision:
    feature_window_id: str
    device_id: str
    window_start: str
    window_end: str
    rule_result: dict
    baseline_score: float | None
    model_prediction: float | None
    model_name: str | None
    model_version: str | None
    detector_agreement: str
    combined_severity: str
    operational_risk: str
    confidence: str
    affected_features: list[str]
    explanation: str


@dataclass
class ReplayResult:
    device_class: str
    scoring_policy_version: str
    model_version: str | None
    period_start: datetime
    period_end: datetime
    windows_considered: int = 0
    decisions: list[ReplayDecision] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _replay_baseline(db: Session, window: TelemetryFeatureWindow) -> tuple[float | None, bool | None, dict]:
    """Read-only equivalent of statistical_baseline_service.score() — never writes."""
    prior = statistical_baseline_service._prior_windows(db, window)
    if len(prior) < statistical_baseline_service.MIN_PRIOR_WINDOWS:
        return None, None, {}

    feature_comparison = statistical_baseline_service._build_feature_comparison(window, prior)
    if not feature_comparison:
        return None, None, {}

    anomaly_score = max((abs(info["z_score"]) for info in feature_comparison.values()), default=0.0)
    is_anomalous = anomaly_score > statistical_baseline_service.Z_SCORE_THRESHOLD
    return anomaly_score, is_anomalous, feature_comparison


def _replay_model(model_row: AnomalyModel | None, window: TelemetryFeatureWindow) -> tuple[float | None, bool | None]:
    """Read-only equivalent of isolation_forest_service.score() for a *specific*
    (possibly retired/historical) model version — never writes."""
    if model_row is None or not model_row.artifact_path:
        return None, None

    validation = model_loader.validate(model_row, expected_feature_schema_version=window.feature_schema_version)
    if not validation.ok:
        return None, None

    feature_order = FEATURE_SCHEMAS.get(window.device_class)
    if not feature_order:
        return None, None

    vector = [window.features.get(name) for name in feature_order]
    if any(value is None for value in vector):
        return None, None

    estimator = joblib.load(model_row.artifact_path)
    raw_score = float(estimator.decision_function([vector])[0])
    anomaly_score = -raw_score
    threshold = float(model_row.hyperparameters.get("score_threshold", 0.0))
    return anomaly_score, anomaly_score > threshold


def run_replay(
    db: Session,
    *,
    device_class: str,
    period_start: datetime,
    period_end: datetime,
    model_version: str | None = None,
    scoring_policy_version: str = hybrid_detection_service.HYBRID_SCORING_POLICY_VERSION,
) -> ReplayResult:
    result = ReplayResult(
        device_class=device_class,
        scoring_policy_version=scoring_policy_version,
        model_version=model_version,
        period_start=period_start,
        period_end=period_end,
    )

    model_row = None
    if model_version is not None:
        model_row = db.scalar(
            select(AnomalyModel).where(
                AnomalyModel.device_class == device_class,
                AnomalyModel.algorithm == "isolation_forest",
                AnomalyModel.version == model_version,
            )
        )
        if model_row is None:
            result.skipped.append(f"no_model_found_for_version:{model_version}")

    windows = list(
        db.scalars(
            select(TelemetryFeatureWindow)
            .where(
                TelemetryFeatureWindow.device_class == device_class,
                TelemetryFeatureWindow.window_start >= period_start,
                TelemetryFeatureWindow.window_start < period_end,
            )
            .order_by(TelemetryFeatureWindow.device_id, TelemetryFeatureWindow.window_start)
        )
    )
    result.windows_considered = len(windows)

    device_cache: dict[str, Device] = {}

    for window in windows:
        device_key = str(window.device_id)
        if device_key not in device_cache:
            device_cache[device_key] = db.get(Device, window.device_id)
        device = device_cache[device_key]
        criticality = device.criticality if device is not None else "medium"

        rule_result = hybrid_detection_service._lookup_rule_result(db, window)
        baseline_score, baseline_anomalous, baseline_comparison = _replay_baseline(db, window)
        model_score, model_anomalous = _replay_model(model_row, window)

        agreement = hybrid_detection_service._detector_agreement(
            window.quality_score, rule_result["fired"], baseline_anomalous, model_anomalous
        )
        persistence = hybrid_detection_service._anomaly_persistence(
            db, window, agreement not in ("all_normal", "insufficient_data")
        )
        confidence = hybrid_detection_service._confidence(agreement, window.quality_score, persistence)
        combined_severity = hybrid_detection_service._combined_severity(rule_result, agreement, confidence)

        linked_incident = hybrid_detection_service._linked_open_incident(db, window.device_id)
        recovery_activity = hybrid_detection_service._recent_recovery_activity(db, window)
        operational_risk = hybrid_detection_service._operational_risk(
            combined_severity, criticality, persistence, linked_incident is not None, recovery_activity["recent_failed"]
        )

        affected_features = sorted(
            name for name, info in baseline_comparison.items() if info.get("is_affected")
        )
        if model_anomalous:
            affected_features = sorted(set(affected_features) | set(FEATURE_SCHEMAS.get(window.device_class, [])))

        explanation = (
            f"[REPLAY] Detector agreement: {agreement}; combined severity: {combined_severity}; "
            f"operational risk: {operational_risk}; confidence: {confidence}."
        )

        result.decisions.append(
            ReplayDecision(
                feature_window_id=str(window.id),
                device_id=str(window.device_id),
                window_start=window.window_start.isoformat(),
                window_end=window.window_end.isoformat(),
                rule_result=rule_result,
                baseline_score=baseline_score,
                model_prediction=model_score,
                model_name=model_row.name if model_row else None,
                model_version=model_row.version if model_row else None,
                detector_agreement=agreement,
                combined_severity=combined_severity,
                operational_risk=operational_risk,
                confidence=confidence,
                affected_features=affected_features,
                explanation=explanation,
            )
        )

    return result


def export_json(result: ReplayResult) -> str:
    payload = asdict(result)
    payload["period_start"] = result.period_start.isoformat()
    payload["period_end"] = result.period_end.isoformat()
    return json.dumps(payload, indent=2)


def export_markdown(result: ReplayResult) -> str:
    lines = [
        f"# Historical Replay — {result.device_class}",
        f"- Scoring policy version: `{result.scoring_policy_version}`",
        f"- Model version: `{result.model_version or 'n/a (rule + baseline only)'}`",
        f"- Period: {result.period_start.isoformat()} to {result.period_end.isoformat()}",
        f"- Windows considered: {result.windows_considered}",
        "",
        "| Device | Window Start | Agreement | Severity | Risk | Confidence |",
        "|---|---|---|---|---|---|",
    ]
    for d in result.decisions:
        lines.append(
            f"| {d.device_id} | {d.window_start} | {d.detector_agreement} | {d.combined_severity} | "
            f"{d.operational_risk} | {d.confidence} |"
        )
    return "\n".join(lines)
