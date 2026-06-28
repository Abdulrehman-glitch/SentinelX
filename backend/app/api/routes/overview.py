from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.alert import Alert
from app.models.alert_rule import AlertRule
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.incident import Incident
from app.models.recovery_action import RecoveryAction
from app.models.system_metric import SystemMetric

router = APIRouter(prefix="/overview", tags=["Overview"])


@router.get("")
def get_overview(db: Session = Depends(get_db)) -> dict:
    """
    Returns summary data for the dashboard.

    Existing response sections are preserved. New operational sections are
    added for incidents, audit logs, and alert rules.
    """

    total_devices = db.scalar(select(func.count(Device.id))) or 0
    online_devices = db.scalar(select(func.count(Device.id)).where(Device.status == "online")) or 0
    offline_devices = db.scalar(select(func.count(Device.id)).where(Device.status == "offline")) or 0

    total_metrics = db.scalar(select(func.count(SystemMetric.id))) or 0
    unresolved_alerts = db.scalar(select(func.count(Alert.id)).where(Alert.resolved.is_(False))) or 0
    recovery_actions = db.scalar(select(func.count(RecoveryAction.id))) or 0

    total_incidents = db.scalar(select(func.count(Incident.id))) or 0
    open_incidents = db.scalar(select(func.count(Incident.id)).where(Incident.status == "open")) or 0
    investigating_incidents = (
        db.scalar(select(func.count(Incident.id)).where(Incident.status == "investigating")) or 0
    )
    resolved_incidents = db.scalar(select(func.count(Incident.id)).where(Incident.status == "resolved")) or 0

    total_audit_logs = db.scalar(select(func.count(AuditLog.id))) or 0

    total_alert_rules = db.scalar(select(func.count(AlertRule.id))) or 0
    enabled_alert_rules = db.scalar(select(func.count(AlertRule.id)).where(AlertRule.enabled.is_(True))) or 0
    disabled_alert_rules = db.scalar(select(func.count(AlertRule.id)).where(AlertRule.enabled.is_(False))) or 0

    return {
        "devices": {
            "total": total_devices,
            "online": online_devices,
            "offline": offline_devices,
        },
        "metrics": {
            "total": total_metrics,
        },
        "alerts": {
            "unresolved": unresolved_alerts,
        },
        "recovery_actions": {
            "total": recovery_actions,
        },
        "incidents": {
            "total": total_incidents,
            "open": open_incidents,
            "investigating": investigating_incidents,
            "resolved": resolved_incidents,
        },
        "audit_logs": {
            "total": total_audit_logs,
        },
        "alert_rules": {
            "total": total_alert_rules,
            "enabled": enabled_alert_rules,
            "disabled": disabled_alert_rules,
        },
    }