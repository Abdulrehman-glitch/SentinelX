from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alert import Alert
from app.models.alert_rule import AlertRule
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.incident import Incident
from app.models.recovery_action import RecoveryAction
from app.models.system_metric import SystemMetric
from app.models.user import User
from app.services.tenant import require_org_user

router = APIRouter(prefix="/overview", tags=["Overview"])


def _count_tenant_owned(db: Session, model, current_user: User, *conditions) -> int:
    statement = select(func.count(model.id))
    where = list(conditions)
    if current_user.role != "platform_admin":
        where.append(model.organization_id == require_org_user(current_user))
    if where:
        statement = statement.where(*where)
    return db.scalar(statement) or 0


def _count_system_metrics(db: Session, current_user: User) -> int:
    statement = select(func.count(SystemMetric.id)).join(Device, SystemMetric.device_id == Device.id)
    if current_user.role != "platform_admin":
        statement = statement.where(Device.organization_id == require_org_user(current_user))
    return db.scalar(statement) or 0


@router.get("")
def get_overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if current_user.role == "platform_admin":
        total_devices = db.scalar(select(func.count(Device.id))) or 0
        online_devices = db.scalar(select(func.count(Device.id)).where(Device.status == "online")) or 0
        offline_devices = db.scalar(select(func.count(Device.id)).where(Device.status == "offline")) or 0
    else:
        org_id = require_org_user(current_user)
        total_devices = db.scalar(select(func.count(Device.id)).where(Device.organization_id == org_id)) or 0
        online_devices = db.scalar(select(func.count(Device.id)).where(Device.organization_id == org_id, Device.status == "online")) or 0
        offline_devices = db.scalar(select(func.count(Device.id)).where(Device.organization_id == org_id, Device.status == "offline")) or 0

    return {
        "devices": {"total": total_devices, "online": online_devices, "offline": offline_devices},
        "metrics": {"total": _count_system_metrics(db, current_user)},
        "alerts": {"unresolved": _count_tenant_owned(db, Alert, current_user, Alert.resolved.is_(False))},
        "recovery_actions": {"total": _count_tenant_owned(db, RecoveryAction, current_user)},
        "incidents": {
            "total": _count_tenant_owned(db, Incident, current_user),
            "open": _count_tenant_owned(db, Incident, current_user, Incident.status == "open"),
            "investigating": _count_tenant_owned(db, Incident, current_user, Incident.status == "investigating"),
            "resolved": _count_tenant_owned(db, Incident, current_user, Incident.status == "resolved"),
        },
        "audit_logs": {"total": _count_tenant_owned(db, AuditLog, current_user)},
        "alert_rules": {
            "total": _count_tenant_owned(db, AlertRule, current_user),
            "enabled": _count_tenant_owned(db, AlertRule, current_user, AlertRule.enabled.is_(True)),
            "disabled": _count_tenant_owned(db, AlertRule, current_user, AlertRule.enabled.is_(False)),
        },
    }
