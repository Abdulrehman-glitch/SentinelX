from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.alert import Alert
from app.models.device import Device
from app.models.recovery_action import RecoveryAction
from app.models.system_metric import SystemMetric

router = APIRouter(prefix="/overview", tags=["Overview"])


@router.get("")
def get_overview(db: Session = Depends(get_db)) -> dict:
    """
    Returns summary data for the future dashboard.

    This endpoint is intentionally simple so the frontend can display
    useful information without needing many separate requests.
    """

    total_devices = db.scalar(select(func.count(Device.id))) or 0
    online_devices = db.scalar(select(func.count(Device.id)).where(Device.status == "online")) or 0
    offline_devices = db.scalar(select(func.count(Device.id)).where(Device.status == "offline")) or 0

    total_metrics = db.scalar(select(func.count(SystemMetric.id))) or 0
    unresolved_alerts = db.scalar(select(func.count(Alert.id)).where(Alert.resolved.is_(False))) or 0
    recovery_actions = db.scalar(select(func.count(RecoveryAction.id))) or 0

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
    }