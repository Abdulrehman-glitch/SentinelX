"""
Combines the existing detectors — deterministic alert rules, the
statistical baseline, and IsolationForest — plus telemetry quality, anomaly
persistence, device class/criticality, and recent incident/recovery
activity into one deterministic, versioned HybridDecision per feature
window. Reuses telemetry_feature_windows and idempotently (re-)scores them
with statistical_baseline_service/isolation_forest_service exactly like
observability_pipeline_service does — this module never creates
Alert/Incident/RecoveryCommand rows itself; alert_id/incident_id/
recovery_command_id on a HybridDecision are read-only references to
whatever the authoritative pipelines already produced.

Rules stay authoritative: combined_severity can only be raised above a
fired rule's severity by strong AI-only agreement, never lowered below it
(see _combined_severity). anomaly_score/baseline_score/model_prediction are
never probabilities — see docs/ai_observability_architecture.md.
"""

import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.alert import Alert
from app.models.anomaly_prediction import AnomalyPrediction
from app.models.device import Device
from app.models.hybrid_decision import HybridDecision
from app.models.incident import Incident
from app.models.recovery_command import RecoveryCommand
from app.models.telemetry_feature_window import TelemetryFeatureWindow
from app.services import ai_recommendation_service, device_class_service, feature_window_service, isolation_forest_service, statistical_baseline_service
from app.services.telemetry_quality_service import MIN_QUALITY_SCORE_FOR_SCORING

HYBRID_SCORING_POLICY_VERSION = "v1"

_SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}
_RANK_TO_SEVERITY = {v: k for k, v in _SEVERITY_RANK.items()}
_CRITICALITY_RISK_WEIGHT = {"low": 0.0, "medium": 0.2, "high": 0.5}

PERSISTENCE_LOOKBACK_MAX = 10
RECENT_RECOVERY_LOOKBACK_HOURS = 24

# Commands still "in flight" — mirrors recovery_policy_service._ACTIVE_STATUSES.
# Duplicated locally (rather than importing a private name) since this is the
# only thing this module needs from that set.
_ACTIVE_RECOVERY_STATUSES = {
    "proposed", "awaiting_approval", "approved", "dispatched",
    "acknowledged", "running", "succeeded", "verifying",
}


@dataclass
class DeviceHybridRunResult:
    device_id: str
    device_class: str | None
    windows_built: int = 0
    windows_scored: int = 0
    decisions_created: int = 0
    errors: list[str] = field(default_factory=list)
    skipped_reason: str | None = None


@dataclass
class HybridRunResult:
    devices_processed: int = 0
    windows_built: int = 0
    windows_scored: int = 0
    decisions_created: int = 0
    device_results: list[DeviceHybridRunResult] = field(default_factory=list)


def _lookup_rule_result(db: Session, window: TelemetryFeatureWindow) -> dict:
    """Read-only view of whatever Alert rows the deterministic pipeline (metrics.py) already raised for this window's time span."""
    alerts = list(
        db.scalars(
            select(Alert).where(
                Alert.device_id == window.device_id,
                Alert.created_at >= window.window_start,
                Alert.created_at < window.window_end,
            )
        )
    )
    if not alerts:
        return {"fired": False, "severity": None, "alert_ids": [], "alert_types": [], "top_alert_id": None}

    top_alert = max(alerts, key=lambda a: _SEVERITY_RANK.get(a.severity, 0))
    return {
        "fired": True,
        "severity": top_alert.severity,
        "alert_ids": [str(a.id) for a in alerts],
        "alert_types": sorted({a.alert_type for a in alerts}),
        "top_alert_id": str(top_alert.id),
    }


def _detector_agreement(
    quality_score: float,
    rule_fired: bool,
    baseline_anomalous: bool | None,
    model_anomalous: bool | None,
) -> str:
    baseline_available = baseline_anomalous is not None
    model_available = model_anomalous is not None

    if quality_score < MIN_QUALITY_SCORE_FOR_SCORING or (not baseline_available and not model_available):
        return "insufficient_data"

    if not rule_fired and baseline_available and model_available and baseline_anomalous != model_anomalous:
        return "detector_conflict"

    votes = {"rule": rule_fired, "baseline": bool(baseline_anomalous), "model": bool(model_anomalous)}
    true_names = [name for name, voted in votes.items() if voted]
    n_true = len(true_names)

    if n_true == 0:
        return "all_normal"
    if n_true == 1:
        return f"{true_names[0]}_only"
    if n_true == 2:
        return "two_agree"
    return "all_agree"


def _confidence(agreement: str, quality_score: float, persistence: int) -> str:
    if agreement == "all_agree" and quality_score >= 0.85 and persistence >= 2:
        return "high"
    if agreement in ("all_agree", "two_agree", "rule_only") and quality_score >= 0.6:
        return "medium"
    return "low"


def _combined_severity(rule_result: dict, agreement: str, confidence: str) -> str:
    """Rules are authoritative: a fired rule's severity is always included via
    max() below, so AI evidence can raise the combined severity but never
    suppress or downgrade what a critical rule already established."""
    rule_rank = _SEVERITY_RANK.get(rule_result["severity"], 0) if rule_result["fired"] else 0

    ai_rank = 0
    if agreement == "all_agree":
        ai_rank = 1
    elif agreement == "two_agree" and confidence in ("medium", "high"):
        ai_rank = 1

    return _RANK_TO_SEVERITY[max(rule_rank, ai_rank)]


def _operational_risk(
    combined_severity: str,
    criticality: str,
    persistence: int,
    incident_open: bool,
    recent_failed: int,
) -> str:
    score = _SEVERITY_RANK.get(combined_severity, 0) * 1.0
    score += _CRITICALITY_RISK_WEIGHT.get(criticality, 0.2)
    score += 0.3 if persistence >= 3 else 0.0
    score += 0.3 if incident_open else 0.0
    score += 0.2 if recent_failed > 0 else 0.0

    if score >= 2.0:
        return "high"
    if score >= 1.0:
        return "medium"
    return "low"


def _affected_features(baseline_pred: AnomalyPrediction | None, model_pred: AnomalyPrediction | None) -> list[str]:
    features: set[str] = set()
    if baseline_pred is not None:
        features.update(name for name, info in baseline_pred.feature_comparison.items() if info.get("is_affected"))
    if model_pred is not None and model_pred.is_anomalous:
        features.update(model_pred.feature_comparison.keys())
    return sorted(features)


def _explanation(
    rule_result: dict,
    baseline_pred: AnomalyPrediction | None,
    model_pred: AnomalyPrediction | None,
    agreement: str,
    combined_severity: str,
    persistence: int,
    affected_features: list[str],
) -> str:
    parts: list[str] = []
    if rule_result["fired"]:
        parts.append(
            f"Deterministic rule(s) fired: {', '.join(rule_result['alert_types'])} (severity {rule_result['severity']})."
        )
    if baseline_pred is not None:
        parts.append(
            f"Statistical baseline {'flagged' if baseline_pred.is_anomalous else 'did not flag'} "
            f"this window (score {baseline_pred.anomaly_score:.2f})."
        )
    if model_pred is not None:
        parts.append(
            f"IsolationForest {'flagged' if model_pred.is_anomalous else 'did not flag'} "
            f"this window (score {model_pred.anomaly_score:.2f})."
        )
    if not parts:
        parts.append("No detector produced a definitive signal for this window.")

    parts.append(f"Detector agreement: {agreement}; combined severity: {combined_severity}.")
    if persistence >= 2:
        parts.append(f"Sustained across {persistence} consecutive windows.")
    if affected_features:
        parts.append(f"Affected features: {', '.join(affected_features)}.")

    return " ".join(parts)


def _anomaly_persistence(db: Session, window: TelemetryFeatureWindow, current_anomalous: bool) -> int:
    if not current_anomalous:
        return 0

    count = 1
    cursor = window
    for _ in range(PERSISTENCE_LOOKBACK_MAX):
        prior_decision = db.scalar(
            select(HybridDecision)
            .join(TelemetryFeatureWindow, HybridDecision.feature_window_id == TelemetryFeatureWindow.id)
            .where(
                HybridDecision.scoring_policy_version == HYBRID_SCORING_POLICY_VERSION,
                HybridDecision.device_id == window.device_id,
                TelemetryFeatureWindow.window_end == cursor.window_start,
            )
            .limit(1)
        )
        if prior_decision is None or prior_decision.detector_agreement in ("all_normal", "insufficient_data"):
            break
        count += 1
        cursor = db.get(TelemetryFeatureWindow, prior_decision.feature_window_id)
        if cursor is None:
            break

    return count


def _linked_open_incident(db: Session, device_id: uuid.UUID) -> Incident | None:
    return db.scalar(
        select(Incident)
        .where(Incident.device_id == device_id, Incident.status.in_(["open", "investigating"]))
        .order_by(Incident.created_at.desc())
        .limit(1)
    )


def _recent_recovery_activity(db: Session, window: TelemetryFeatureWindow) -> dict:
    since = window.window_end - timedelta(hours=RECENT_RECOVERY_LOOKBACK_HOURS)
    recent = list(
        db.scalars(
            select(RecoveryCommand)
            .where(RecoveryCommand.device_id == window.device_id, RecoveryCommand.created_at >= since)
            .order_by(RecoveryCommand.created_at.desc())
            .limit(10)
        )
    )
    active = next((c for c in recent if c.status in _ACTIVE_RECOVERY_STATUSES), None)
    return {
        "recent_count": len(recent),
        "recent_failed": sum(1 for c in recent if c.status == "failed"),
        "active_command": active,
    }


def _pending_hybrid_windows(db: Session, device: Device, device_class: str) -> list[TelemetryFeatureWindow]:
    """All quality-eligible windows for this device/class that don't yet have a
    HybridDecision at the current scoring policy version — includes windows
    built by this call *and* any built earlier (e.g. by the observability
    pipeline) that haven't been hybrid-scored yet."""
    scored_subquery = select(HybridDecision.feature_window_id).where(
        HybridDecision.scoring_policy_version == HYBRID_SCORING_POLICY_VERSION
    )
    return list(
        db.scalars(
            select(TelemetryFeatureWindow)
            .where(
                TelemetryFeatureWindow.device_id == device.id,
                TelemetryFeatureWindow.device_class == device_class,
                TelemetryFeatureWindow.id.not_in(scored_subquery),
            )
            .order_by(TelemetryFeatureWindow.window_start.asc())
            .limit(feature_window_service.MAX_WINDOWS_PER_CALL)
        )
    )


def _score_window(db: Session, window: TelemetryFeatureWindow, device: Device) -> HybridDecision | None:
    """Idempotent: returns the existing decision if this window was already scored at this policy version."""
    existing = db.scalar(
        select(HybridDecision).where(
            HybridDecision.feature_window_id == window.id,
            HybridDecision.scoring_policy_version == HYBRID_SCORING_POLICY_VERSION,
        )
    )
    if existing is not None:
        return existing

    baseline_pred = statistical_baseline_service.score(db, window)
    model_pred = isolation_forest_service.score(db, window)

    rule_result = _lookup_rule_result(db, window)
    baseline_anomalous = baseline_pred.is_anomalous if baseline_pred is not None else None
    model_anomalous = model_pred.is_anomalous if model_pred is not None else None

    agreement = _detector_agreement(window.quality_score, rule_result["fired"], baseline_anomalous, model_anomalous)
    persistence = _anomaly_persistence(db, window, agreement not in ("all_normal", "insufficient_data"))
    confidence = _confidence(agreement, window.quality_score, persistence)
    combined_severity = _combined_severity(rule_result, agreement, confidence)

    linked_incident = _linked_open_incident(db, window.device_id)
    recovery_activity = _recent_recovery_activity(db, window)

    operational_risk = _operational_risk(
        combined_severity,
        device.criticality,
        persistence,
        linked_incident is not None,
        recovery_activity["recent_failed"],
    )

    affected_features = _affected_features(baseline_pred, model_pred)
    explanation = _explanation(
        rule_result, baseline_pred, model_pred, agreement, combined_severity, persistence, affected_features
    )

    decision = HybridDecision(
        organization_id=window.organization_id,
        device_id=window.device_id,
        feature_window_id=window.id,
        rule_result=rule_result,
        baseline_score=baseline_pred.anomaly_score if baseline_pred is not None else None,
        model_prediction=model_pred.anomaly_score if model_pred is not None else None,
        model_name=model_pred.model_name if model_pred is not None else None,
        model_version=model_pred.model_version if model_pred is not None else None,
        detector_agreement=agreement,
        combined_severity=combined_severity,
        operational_risk=operational_risk,
        confidence=confidence,
        affected_features=affected_features,
        explanation=explanation,
        scoring_policy_version=HYBRID_SCORING_POLICY_VERSION,
        alert_id=uuid.UUID(rule_result["top_alert_id"]) if rule_result["top_alert_id"] else None,
        incident_id=linked_incident.id if linked_incident is not None else None,
        recovery_command_id=recovery_activity["active_command"].id if recovery_activity["active_command"] else None,
        review_status="unreviewed",
    )
    db.add(decision)
    db.flush()
    return decision


def run_for_device(db: Session, device: Device) -> DeviceHybridRunResult:
    device_class = device_class_service.classify(device)
    result = DeviceHybridRunResult(device_id=str(device.id), device_class=device_class)

    if device_class is None:
        result.skipped_reason = "unclassified_device_type"
        return result

    try:
        built = feature_window_service.build_pending_windows(db, device, device_class)
    except Exception as exc:  # noqa: BLE001 - one device's failure must not abort the batch
        result.errors.append(f"feature_window_build_failed: {exc}")
        return result

    result.windows_built = len(built)

    pending = _pending_hybrid_windows(db, device, device_class)
    for window in pending:
        if window.quality_score < MIN_QUALITY_SCORE_FOR_SCORING or window.sample_count < feature_window_service.MIN_SAMPLES_PER_WINDOW:
            continue

        result.windows_scored += 1
        try:
            decision = _score_window(db, window, device)
            if decision is not None:
                result.decisions_created += 1
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"hybrid_scoring_failed:{window.id}:{exc}")
            continue

        if decision is not None and get_settings().self_healing_automation_enabled:
            try:
                ai_recommendation_service.propose_from_hybrid_decision(db, decision)
            except Exception as exc:  # noqa: BLE001 - a failed proposal must not abort the batch
                result.errors.append(f"ai_recommendation_failed:{window.id}:{exc}")

    return result


def run_for_devices(db: Session, devices: list[Device]) -> HybridRunResult:
    summary = HybridRunResult()
    for device in devices:
        device_result = run_for_device(db, device)
        summary.devices_processed += 1
        summary.windows_built += device_result.windows_built
        summary.windows_scored += device_result.windows_scored
        summary.decisions_created += device_result.decisions_created
        summary.device_results.append(device_result)
    return summary
