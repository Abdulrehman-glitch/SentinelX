import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_device_from_token, require_role
from app.db.session import get_db
from app.models.alert import Alert
from app.models.device import Device
from app.models.user import User
from app.schemas.alert import AlertResponse
from app.services.audit_log_service import create_audit_log
from app.services.tenant import assert_same_org, require_org_user

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    unresolved_only: bool = False,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Alert]:
    safe_limit = min(max(limit, 1), 500)
    conditions = []
    if current_user.role != "platform_admin":
        conditions.append(Alert.organization_id == require_org_user(current_user))
    if unresolved_only:
        conditions.append(Alert.resolved.is_(False))

    q = select(Alert).order_by(Alert.created_at.desc()).limit(safe_limit)
    if conditions:
        q = q.where(*conditions)
    return list(db.scalars(q))


@router.get("/device/me", response_model=list[AlertResponse])
def list_my_device_alerts(
    unresolved_only: bool = False,
    limit: int = 50,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> list[Alert]:
    """Alerts for the calling device, authenticated by its own device token —
    lets the mobile agent show its alerts without a user session."""
    safe_limit = min(max(limit, 1), 200)
    conditions = [Alert.device_id == authenticated_device.id]
    if unresolved_only:
        conditions.append(Alert.resolved.is_(False))

    q = select(Alert).where(*conditions).order_by(Alert.created_at.desc()).limit(safe_limit)
    return list(db.scalars(q))


@router.patch("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "engineer", "owner"])),
    db: Session = Depends(get_db),
) -> Alert:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    assert_same_org(alert.organization_id, current_user)

    was_unresolved = not alert.resolved
    alert.resolved = True
    alert.resolved_at = datetime.now(timezone.utc)

    if was_unresolved:
        create_audit_log(
            db,
            organization_id=alert.organization_id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="alert_resolved",
            target_type="alert",
            target_id=str(alert.id),
            severity="info",
            message=f"Alert resolved: {alert.message}",
            metadata={"device_id": str(alert.device_id), "alert_type": alert.alert_type, "alert_severity": alert.severity},
        )

    db.commit()
    db.refresh(alert)
    return alert
