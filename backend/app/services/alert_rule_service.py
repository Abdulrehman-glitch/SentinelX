import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.alert_rule import AlertRule


@dataclass(frozen=True)
class AlertRuleCandidate:
    alert_type: str
    severity: str
    message: str
    rule_id: uuid.UUID | None
    cooldown_seconds: int


def _metric_value(metric_type: str, cpu_percent: float, memory_percent: float, disk_percent: float) -> float:
    if metric_type == "cpu_percent":
        return cpu_percent

    if metric_type == "memory_percent":
        return memory_percent

    if metric_type == "disk_percent":
        return disk_percent

    raise ValueError(f"Unsupported metric type: {metric_type}")


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == ">":
        return value > threshold

    if operator == ">=":
        return value >= threshold

    if operator == "<":
        return value < threshold

    if operator == "<=":
        return value <= threshold

    return False


def evaluate_enabled_alert_rules(
    db: Session,
    *,
    cpu_percent: float,
    memory_percent: float,
    disk_percent: float,
) -> list[AlertRuleCandidate]:
    """
    Evaluates enabled alert rules against incoming metric values.

    If no enabled rules exist or none match, the caller can fall back to
    the original built-in anomaly detection thresholds.
    """

    rules = list(
        db.scalars(
            select(AlertRule)
            .where(AlertRule.enabled.is_(True))
            .order_by(AlertRule.created_at.asc())
        )
    )

    candidates: list[AlertRuleCandidate] = []

    for rule in rules:
        value = _metric_value(
            rule.metric_type,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_percent=disk_percent,
        )

        if not _compare(value=value, operator=rule.operator, threshold=rule.threshold):
            continue

        candidates.append(
            AlertRuleCandidate(
                alert_type=f"alert_rule:{rule.id}",
                severity=rule.severity,
                message=(
                    f"{rule.name} triggered: {rule.metric_type} "
                    f"is {value:.1f}% and rule is {rule.operator} {rule.threshold:.1f}%."
                ),
                rule_id=rule.id,
                cooldown_seconds=rule.cooldown_seconds,
            )
        )

    return candidates


def is_alert_suppressed_by_cooldown(
    db: Session,
    *,
    device_id: uuid.UUID,
    alert_type: str,
    cooldown_seconds: int,
) -> bool:
    """
    Prevents enabled alert rules from generating repeated alerts too quickly.
    """

    if cooldown_seconds <= 0:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=cooldown_seconds)

    recent_alert = db.scalar(
        select(Alert)
        .where(
            Alert.device_id == device_id,
            Alert.alert_type == alert_type,
            Alert.created_at >= cutoff,
        )
        .order_by(Alert.created_at.desc())
        .limit(1)
    )

    return recent_alert is not None