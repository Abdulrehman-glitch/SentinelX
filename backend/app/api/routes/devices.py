import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_device_from_token, require_role
from app.db.session import get_db
from app.models.agent_heartbeat import AgentHeartbeat
from app.models.alert import Alert
from app.models.device import Device
from app.models.organization import Organization
from app.models.recovery_action import RecoveryAction
from app.models.system_metric import SystemMetric
from app.models.user import User
from app.schemas.alert import AlertResponse
from app.schemas.device import (
    DeviceRegisterRequest,
    DeviceResponse,
    DeviceStatusUpdateRequest,
)
from app.schemas.device_detail import (
    DeviceHealthResponse,
    DeviceSummaryCounts,
    DeviceSummaryResponse,
)
from app.schemas.metric import MetricResponse
from app.schemas.recovery_action import RecoveryActionResponse
from app.services.audit_log_service import create_audit_log
from app.services.health_score_service import calculate_device_health
from app.services.tenant import require_org_user

router = APIRouter(prefix="/devices", tags=["Devices"])


def _get_device_or_404(device_id: uuid.UUID, db: Session, *, org_id: uuid.UUID | None = None) -> Device:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    if org_id and device.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


def _safe_limit(limit: int, minimum: int = 1, maximum: int = 500) -> int:
    return min(max(limit, minimum), maximum)


def _get_latest_metric(device_id: uuid.UUID, db: Session) -> SystemMetric | None:
    return db.scalar(
        select(SystemMetric)
        .where(SystemMetric.device_id == device_id)
        .order_by(SystemMetric.recorded_at.desc())
        .limit(1)
    )


def _build_health_response(device: Device, db: Session) -> DeviceHealthResponse:
    latest_metric = _get_latest_metric(device.id, db)

    unresolved_warning = db.scalar(
        select(func.count(Alert.id)).where(
            Alert.device_id == device.id, Alert.resolved.is_(False), Alert.severity == "warning"
        )
    ) or 0

    unresolved_critical = db.scalar(
        select(func.count(Alert.id)).where(
            Alert.device_id == device.id, Alert.resolved.is_(False), Alert.severity == "critical"
        )
    ) or 0

    health_result = calculate_device_health(
        latest_metric=latest_metric,
        last_seen_at=device.last_seen_at,
        unresolved_warning_alerts=unresolved_warning,
        unresolved_critical_alerts=unresolved_critical,
    )

    return DeviceHealthResponse(
        device_id=device.id,
        hostname=device.hostname,
        device_status=device.status,
        health_score=health_result.health_score,
        health_status=health_result.health_status,
        last_seen_at=device.last_seen_at,
        latest_metric=MetricResponse.model_validate(latest_metric) if latest_metric else None,
        unresolved_warning_alerts=unresolved_warning,
        unresolved_critical_alerts=unresolved_critical,
        reasons=health_result.reasons,
        evaluated_at=datetime.now(timezone.utc),
    )


@router.post("/register", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def register_device(
    payload: DeviceRegisterRequest,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> Device:
    """
    Manually registers or refreshes a monitored device (admin action).

    Agents no longer call this anonymously — they enrol via POST /devices/enroll
    with a single-use code, then keep their record fresh via /devices/agent-sync.
    Tenant admins always register into their own organization; only a
    platform_admin may target another org via the slug.
    """
    if current_user.role == "platform_admin":
        org = None
        if payload.organization_slug:
            org = db.scalar(select(Organization).where(Organization.slug == payload.organization_slug))
    else:
        org = db.get(Organization, require_org_user(current_user))

    existing_device = db.scalar(
        select(Device).where(
            Device.hostname == payload.hostname,
            Device.organization_id == (org.id if org else None),
        )
    )

    if existing_device:
        existing_device.ip_address = payload.ip_address
        existing_device.os_name = payload.os_name
        existing_device.status = "online"
        existing_device.last_seen_at = datetime.now(timezone.utc)
        if hasattr(payload, "agent_version") and payload.agent_version:
            existing_device.agent_version = payload.agent_version

        create_audit_log(
            db,
            organization_id=existing_device.organization_id,
            actor_type="agent",
            actor_id=payload.hostname,
            action="device_refreshed",
            target_type="device",
            target_id=str(existing_device.id),
            severity="info",
            message=f"Device refreshed by agent: {payload.hostname}",
            metadata={"hostname": payload.hostname, "ip_address": payload.ip_address},
        )

        db.commit()
        db.refresh(existing_device)
        return existing_device

    device = Device(
        hostname=payload.hostname,
        display_name=getattr(payload, "display_name", None) or payload.hostname,
        ip_address=payload.ip_address,
        os_name=payload.os_name,
        status="online",
        last_seen_at=datetime.now(timezone.utc),
        organization_id=org.id if org else None,
        device_type=getattr(payload, "device_type", "desktop"),
        agent_type=getattr(payload, "agent_type", "python_desktop_agent"),
        agent_version=getattr(payload, "agent_version", None),
    )

    db.add(device)
    db.flush()

    create_audit_log(
        db,
        organization_id=device.organization_id,
        actor_type="agent",
        actor_id=payload.hostname,
        action="device_registered",
        target_type="device",
        target_id=str(device.id),
        severity="info",
        message=f"Device registered: {payload.hostname}",
        metadata={"hostname": payload.hostname, "ip_address": payload.ip_address},
    )

    db.commit()
    db.refresh(device)
    return device


@router.post("/agent-sync", response_model=DeviceResponse)
def agent_sync(
    payload: DeviceRegisterRequest,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> Device:
    """Device-token-authenticated refresh of the agent's own device record.

    Replaces the old anonymous register-on-startup: an enrolled agent proves
    who it is with its token and can only update itself.
    """
    device = authenticated_device
    device.ip_address = payload.ip_address or device.ip_address
    device.os_name = payload.os_name or device.os_name
    device.status = "online"
    device.last_seen_at = datetime.now(timezone.utc)
    if payload.agent_version:
        device.agent_version = payload.agent_version

    db.commit()
    db.refresh(device)
    return device


@router.get("", response_model=list[DeviceResponse])
def list_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Device]:
    q = select(Device).order_by(Device.created_at.desc())
    if current_user.role != "platform_admin":
        q = q.where(Device.organization_id == require_org_user(current_user))
    return list(db.scalars(q))


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Device:
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)
    return _get_device_or_404(device_id=device_id, db=db, org_id=org_id)


@router.get("/{device_id}/metrics/latest", response_model=MetricResponse | None)
def get_latest_device_metric(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SystemMetric | None:
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)
    _get_device_or_404(device_id=device_id, db=db, org_id=org_id)
    return _get_latest_metric(device_id=device_id, db=db)


@router.get("/{device_id}/metrics/history", response_model=list[MetricResponse])
def get_device_metric_history(
    device_id: uuid.UUID,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SystemMetric]:
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)
    _get_device_or_404(device_id=device_id, db=db, org_id=org_id)

    return list(
        db.scalars(
            select(SystemMetric)
            .where(SystemMetric.device_id == device_id)
            .order_by(SystemMetric.recorded_at.desc())
            .limit(_safe_limit(limit, maximum=500))
        )
    )


@router.get("/{device_id}/health", response_model=DeviceHealthResponse)
def get_device_health(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceHealthResponse:
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)
    device = _get_device_or_404(device_id=device_id, db=db, org_id=org_id)
    return _build_health_response(device=device, db=db)


@router.get("/{device_id}/summary", response_model=DeviceSummaryResponse)
def get_device_summary(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceSummaryResponse:
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)
    device = _get_device_or_404(device_id=device_id, db=db, org_id=org_id)

    latest_metric = _get_latest_metric(device_id=device.id, db=db)

    recent_metrics = list(
        db.scalars(
            select(SystemMetric).where(SystemMetric.device_id == device.id)
            .order_by(SystemMetric.recorded_at.desc()).limit(25)
        )
    )

    recent_alerts = list(
        db.scalars(
            select(Alert).where(Alert.device_id == device.id)
            .order_by(Alert.created_at.desc()).limit(10)
        )
    )

    recent_recovery_actions = list(
        db.scalars(
            select(RecoveryAction).where(RecoveryAction.device_id == device.id)
            .order_by(RecoveryAction.created_at.desc()).limit(10)
        )
    )

    metrics_count = db.scalar(select(func.count(SystemMetric.id)).where(SystemMetric.device_id == device.id)) or 0
    heartbeats_count = db.scalar(select(func.count(AgentHeartbeat.id)).where(AgentHeartbeat.device_id == device.id)) or 0
    alerts_total = db.scalar(select(func.count(Alert.id)).where(Alert.device_id == device.id)) or 0
    alerts_unresolved = db.scalar(select(func.count(Alert.id)).where(Alert.device_id == device.id, Alert.resolved.is_(False))) or 0
    recovery_actions_count = db.scalar(select(func.count(RecoveryAction.id)).where(RecoveryAction.device_id == device.id)) or 0

    health = _build_health_response(device=device, db=db)

    return DeviceSummaryResponse(
        device=DeviceResponse.model_validate(device),
        latest_metric=MetricResponse.model_validate(latest_metric) if latest_metric else None,
        recent_metrics=[MetricResponse.model_validate(m) for m in recent_metrics],
        recent_alerts=[AlertResponse.model_validate(a) for a in recent_alerts],
        recent_recovery_actions=[RecoveryActionResponse.model_validate(r) for r in recent_recovery_actions],
        health=health,
        counts=DeviceSummaryCounts(
            metrics=metrics_count,
            heartbeats=heartbeats_count,
            alerts_total=alerts_total,
            alerts_unresolved=alerts_unresolved,
            recovery_actions=recovery_actions_count,
        ),
    )


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> None:
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)
    device = _get_device_or_404(device_id=device_id, db=db, org_id=org_id)

    create_audit_log(
        db,
        organization_id=device.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="device_deleted",
        target_type="device",
        target_id=str(device.id),
        severity="warning",
        message=f"Device deleted: {device.hostname}",
        metadata={"hostname": device.hostname, "device_id": str(device.id)},
    )

    db.delete(device)
    db.commit()


@router.patch("/{device_id}/status", response_model=DeviceResponse)
def set_device_status(
    device_id: uuid.UUID,
    payload: DeviceStatusUpdateRequest,
    current_user: User = Depends(
        require_role(["platform_admin", "owner", "admin", "engineer"])
    ),
    db: Session = Depends(get_db),
) -> Device:
    """Administratively enable or disable a device (admin & engineer)."""
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)
    device = _get_device_or_404(device_id=device_id, db=db, org_id=org_id)

    new_status = "online" if payload.enabled else "disabled"
    device.status = new_status

    create_audit_log(
        db,
        organization_id=device.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="device_enabled" if payload.enabled else "device_disabled",
        target_type="device",
        target_id=str(device.id),
        severity="info" if payload.enabled else "warning",
        message=(
            f"Device {'enabled' if payload.enabled else 'disabled'}: {device.hostname}"
        ),
        metadata={"hostname": device.hostname, "status": new_status},
    )

    db.commit()
    db.refresh(device)
    return device
