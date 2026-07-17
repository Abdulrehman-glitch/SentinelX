from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.system_metric import SystemMetric


@dataclass(frozen=True)
class HealthScoreResult:
    """
    Result object returned by the health score calculation service.

    health_score can be None when a device has registered but has not
    reported metrics yet. This prevents the frontend from incorrectly
    showing a new device as unhealthy.
    """

    health_score: int | None
    health_status: str
    reasons: list[str]


def _ensure_timezone_aware(value: datetime | None) -> datetime | None:
    """
    Converts naive datetimes to UTC-aware datetimes.

    PostgreSQL timezone behaviour can vary depending on driver/database
    settings, so this helper keeps age calculations safe.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def _resource_pressure_penalty(value: float | None) -> float:
    """
    Calculates a penalty for a single resource usage value.

    The score is deliberately explainable:
    - 0-70% usage is treated as normal.
    - 70-85% begins warning pressure.
    - 85-95% becomes high pressure.
    - 95-100% becomes critical pressure.
    """

    # Unknown readings (e.g. mobile CPU) contribute no penalty either way.
    if value is None:
        return 0.0

    if value <= 70:
        return 0.0

    if value <= 85:
        return ((value - 70) / 15) * 10

    if value <= 95:
        return 10 + (((value - 85) / 10) * 15)

    return 25 + min(((value - 95) / 5) * 10, 10)


def _freshness_penalty(last_seen_at: datetime | None, now: datetime) -> tuple[float, list[str]]:
    """
    Penalises devices that have not sent a heartbeat recently.
    """

    reasons: list[str] = []
    last_seen_at = _ensure_timezone_aware(last_seen_at)

    if last_seen_at is None:
        return 40.0, ["No heartbeat has been recorded for this device."]

    age_seconds = (now - last_seen_at).total_seconds()

    if age_seconds <= 30:
        return 0.0, reasons

    if age_seconds <= 120:
        reasons.append("Device heartbeat is delayed.")
        return 10.0, reasons

    if age_seconds <= 300:
        reasons.append("Device has not reported recently.")
        return 25.0, reasons

    reasons.append("Device appears offline based on heartbeat age.")
    return 50.0, reasons


def _status_from_score(score: int) -> str:
    """
    Converts a numeric health score into a dashboard status.
    """

    if score >= 90:
        return "healthy"

    if score >= 70:
        return "warning"

    if score >= 40:
        return "degraded"

    return "critical"


def calculate_device_health(
    latest_metric: SystemMetric | None,
    last_seen_at: datetime | None,
    unresolved_warning_alerts: int,
    unresolved_critical_alerts: int,
) -> HealthScoreResult:
    """
    Calculates a simple, explainable health score for a monitored device.

    The score is based on:
    - latest CPU, memory, and disk pressure;
    - heartbeat freshness;
    - unresolved warning and critical alerts.

    This is intentionally rule-based for the MVP because it is transparent,
    testable, and easy to explain in the COM668 code walkthrough.
    """

    now = datetime.now(timezone.utc)

    if latest_metric is None:
        freshness_penalty, freshness_reasons = _freshness_penalty(last_seen_at, now)

        if last_seen_at is None:
            return HealthScoreResult(
                health_score=None,
                health_status="unknown",
                reasons=["No metrics have been recorded for this device.", *freshness_reasons],
            )

        provisional_score = max(0, round(100 - freshness_penalty))
        return HealthScoreResult(
            health_score=provisional_score,
            health_status=_status_from_score(provisional_score),
            reasons=["No metrics have been recorded for this device.", *freshness_reasons],
        )

    resource_penalties = {
        "cpu": _resource_pressure_penalty(latest_metric.cpu_percent),
        "memory": _resource_pressure_penalty(latest_metric.memory_percent),
        "disk": _resource_pressure_penalty(latest_metric.disk_percent),
    }

    resource_penalty = max(resource_penalties.values())
    freshness_penalty, freshness_reasons = _freshness_penalty(last_seen_at, now)

    alert_penalty = min(
        (unresolved_warning_alerts * 5) + (unresolved_critical_alerts * 15),
        30,
    )

    score = max(0, round(100 - resource_penalty - freshness_penalty - alert_penalty))

    reasons: list[str] = []

    if latest_metric.cpu_percent is not None and latest_metric.cpu_percent >= 85:
        reasons.append(f"CPU usage is high at {latest_metric.cpu_percent:.1f}%.")

    if latest_metric.memory_percent >= 85:
        reasons.append(f"Memory usage is high at {latest_metric.memory_percent:.1f}%.")

    if latest_metric.disk_percent >= 85:
        reasons.append(f"Disk usage is high at {latest_metric.disk_percent:.1f}%.")

    if unresolved_warning_alerts > 0:
        reasons.append(f"{unresolved_warning_alerts} unresolved warning alert(s) are active.")

    if unresolved_critical_alerts > 0:
        reasons.append(f"{unresolved_critical_alerts} unresolved critical alert(s) are active.")

    reasons.extend(freshness_reasons)

    if not reasons:
        reasons.append("Device is reporting normally.")

    return HealthScoreResult(
        health_score=score,
        health_status=_status_from_score(score),
        reasons=reasons,
    )