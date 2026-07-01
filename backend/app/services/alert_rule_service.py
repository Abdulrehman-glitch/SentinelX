import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
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


def _metric_value(metric_type: str, *, cpu_percent: float, memory_percent: float, disk_percent: float) -> float | None:
    if metric_type == "cpu_percent":
        return cpu_percent
    if metric_type == "memory_percent":
        return memory_percent
    if metric_type == "disk_percent":
        return disk_percent
    # Embedded metric rules are evaluated in the embedded telemetry endpoint.
    return None


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    if operator == "==":
        return value == threshold
    return False


def evaluate_enabled_alert_rules(
    db: Session,
    *,
    cpu_percent: float,
    memory_percent: float,
    disk_percent: float,
    organization_id: uuid.UUID | None = None,
    device_id: uuid.UUID | None = None,
) -> list[AlertRuleCandidate]:
    """Evaluate enabled system-metric rules against incoming desktop-agent metrics.

    A rule applies when it is organization-wide (``device_id`` is NULL) or when
    its ``device_id`` matches the reporting device.
    """
    statement = select(AlertRule).where(AlertRule.enabled.is_(True))
    if organization_id is not None:
        statement = statement.where(AlertRule.organization_id == organization_id)
    if device_id is not None:
        statement = statement.where(
            or_(AlertRule.device_id.is_(None), AlertRule.device_id == device_id)
        )
    else:
        statement = statement.where(AlertRule.device_id.is_(None))
    statement = statement.order_by(AlertRule.created_at.asc())
    rules = list(db.scalars(statement))

    candidates: list[AlertRuleCandidate] = []

    for rule in rules:
        value = _metric_value(
            rule.metric_type,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_percent=disk_percent,
        )
        if value is None:
            continue
        if not _compare(value=value, operator=rule.operator, threshold=rule.threshold):
            continue

        candidates.append(
            AlertRuleCandidate(
                alert_type=f"alert_rule:{rule.id}",
                severity=rule.severity,
                message=(
                    f"{rule.name} triggered: {rule.metric_type} "
                    f"is {value:.1f}% and rule is {rule.operator} {rule.threshold:.1f}."
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
    """Prevent repeated alert creation within a rule cooldown window."""
    if cooldown_seconds <= 0:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=cooldown_seconds)

    recent_alert = db.scalar(
        select(Alert)
        .where(Alert.device_id == device_id, Alert.alert_type == alert_type, Alert.created_at >= cutoff)
        .order_by(Alert.created_at.desc())
        .limit(1)
    )

    return recent_alert is not None
