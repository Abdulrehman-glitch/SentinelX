import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agent_heartbeat import AgentHeartbeat
from app.models.alert import Alert
from app.models.device import Device
from app.models.recovery_action import RecoveryAction
from app.models.system_metric import SystemMetric
from app.schemas.alert import AlertResponse
from app.schemas.device import DeviceRegisterRequest, DeviceResponse
from app.schemas.device_detail import (
    DeviceHealthResponse,
    DeviceSummaryCounts,
    DeviceSummaryResponse,
)
from app.schemas.metric import MetricResponse
from app.schemas.recovery_action import RecoveryActionResponse
from app.services.health_score_service import calculate_device_health

router = APIRouter(prefix="/devices", tags=["Devices"])


def _get_device_or_404(device_id: uuid.UUID, db: Session) -> Device:
    """
    Shared lookup helper for device-specific endpoints.
    """

    device = db.get(Device, device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    return device


def _safe_limit(limit: int, minimum: int = 1, maximum: int = 500) -> int:
    """
    Prevents unbounded history queries from accidentally returning too much data.
    """

    return min(max(limit, minimum), maximum)


def _get_latest_metric(device_id: uuid.UUID, db: Session) -> SystemMetric | None:
    """
    Returns the most recent metric row for a device.
    """

    statement = (
        select(SystemMetric)
        .where(SystemMetric.device_id == device_id)
        .order_by(SystemMetric.recorded_at.desc())
        .limit(1)
    )

    return db.scalar(statement)


def _build_health_response(device: Device, db: Session) -> DeviceHealthResponse:
    """
    Builds the health response for a device using its latest metric,
    unresolved alerts, and heartbeat freshness.
    """

    latest_metric = _get_latest_metric(device.id, db)

    unresolved_warning_alerts = (
        db.scalar(
            select(func.count(Alert.id)).where(
                Alert.device_id == device.id,
                Alert.resolved.is_(False),
                Alert.severity == "warning",
            )
        )
        or 0
    )

    unresolved_critical_alerts = (
        db.scalar(
            select(func.count(Alert.id)).where(
                Alert.device_id == device.id,
                Alert.resolved.is_(False),
                Alert.severity == "critical",
            )
        )
        or 0
    )

    health_result = calculate_device_health(
        latest_metric=latest_metric,
        last_seen_at=device.last_seen_at,
        unresolved_warning_alerts=unresolved_warning_alerts,
        unresolved_critical_alerts=unresolved_critical_alerts,
    )

    return DeviceHealthResponse(
        device_id=device.id,
        hostname=device.hostname,
        device_status=device.status,
        health_score=health_result.health_score,
        health_status=health_result.health_status,
        last_seen_at=device.last_seen_at,
        latest_metric=MetricResponse.model_validate(latest_metric) if latest_metric else None,
        unresolved_warning_alerts=unresolved_warning_alerts,
        unresolved_critical_alerts=unresolved_critical_alerts,
        reasons=health_result.reasons,
        evaluated_at=datetime.now(timezone.utc),
    )


@router.post("/register", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def register_device(payload: DeviceRegisterRequest, db: Session = Depends(get_db)) -> Device:
    """
    Registers a new monitored device or refreshes an existing device.

    The first version uses hostname as the unique identity. Later, this can
    be upgraded to use signed agent tokens.
    """

    existing_device = db.scalar(select(Device).where(Device.hostname == payload.hostname))

    if existing_device:
        existing_device.ip_address = payload.ip_address
        existing_device.os_name = payload.os_name
        existing_device.status = "online"
        existing_device.last_seen_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(existing_device)
        return existing_device

    device = Device(
        hostname=payload.hostname,
        ip_address=payload.ip_address,
        os_name=payload.os_name,
        status="online",
        last_seen_at=datetime.now(timezone.utc),
    )

    db.add(device)
    db.commit()
    db.refresh(device)

    return device


@router.get("", response_model=list[DeviceResponse])
def list_devices(db: Session = Depends(get_db)) -> list[Device]:
    """
    Returns all registered devices.
    """

    return list(db.scalars(select(Device).order_by(Device.created_at.desc())))


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: uuid.UUID, db: Session = Depends(get_db)) -> Device:
    """
    Returns one registered device by ID.
    """

    return _get_device_or_404(device_id=device_id, db=db)


@router.get("/{device_id}/metrics/latest", response_model=MetricResponse | None)
def get_latest_device_metric(
    device_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SystemMetric | None:
    """
    Returns the latest metric for a device.

    If the device exists but has not reported metrics yet, null is returned.
    This lets the frontend show a proper empty state instead of treating it
    as an API failure.
    """

    _get_device_or_404(device_id=device_id, db=db)
    return _get_latest_metric(device_id=device_id, db=db)


@router.get("/{device_id}/metrics/history", response_model=list[MetricResponse])
def get_device_metric_history(
    device_id: uuid.UUID,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[SystemMetric]:
    """
    Returns recent metric history for a device.

    The frontend can use this data for metric cards and future charts.
    """

    _get_device_or_404(device_id=device_id, db=db)

    safe_limit = _safe_limit(limit=limit, maximum=500)

    statement = (
        select(SystemMetric)
        .where(SystemMetric.device_id == device_id)
        .order_by(SystemMetric.recorded_at.desc())
        .limit(safe_limit)
    )

    return list(db.scalars(statement))


@router.get("/{device_id}/health", response_model=DeviceHealthResponse)
def get_device_health(
    device_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DeviceHealthResponse:
    """
    Returns the calculated health score for a device.

    The score is derived from the latest telemetry, unresolved alerts,
    and heartbeat freshness.
    """

    device = _get_device_or_404(device_id=device_id, db=db)
    return _build_health_response(device=device, db=db)


@router.get("/{device_id}/summary", response_model=DeviceSummaryResponse)
def get_device_summary(
    device_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DeviceSummaryResponse:
    """
    Returns a combined device detail summary for the frontend.

    This endpoint is designed for the Device Detail page so the frontend
    can render the main screen using a single API call.
    """

    device = _get_device_or_404(device_id=device_id, db=db)

    latest_metric = _get_latest_metric(device_id=device.id, db=db)

    recent_metrics_statement = (
        select(SystemMetric)
        .where(SystemMetric.device_id == device.id)
        .order_by(SystemMetric.recorded_at.desc())
        .limit(25)
    )

    recent_alerts_statement = (
        select(Alert)
        .where(Alert.device_id == device.id)
        .order_by(Alert.created_at.desc())
        .limit(10)
    )

    recent_recovery_actions_statement = (
        select(RecoveryAction)
        .where(RecoveryAction.device_id == device.id)
        .order_by(RecoveryAction.created_at.desc())
        .limit(10)
    )

    recent_metrics = list(db.scalars(recent_metrics_statement))
    recent_alerts = list(db.scalars(recent_alerts_statement))
    recent_recovery_actions = list(db.scalars(recent_recovery_actions_statement))

    metrics_count = (
        db.scalar(select(func.count(SystemMetric.id)).where(SystemMetric.device_id == device.id))
        or 0
    )

    heartbeats_count = (
        db.scalar(select(func.count(AgentHeartbeat.id)).where(AgentHeartbeat.device_id == device.id))
        or 0
    )

    alerts_total = (
        db.scalar(select(func.count(Alert.id)).where(Alert.device_id == device.id))
        or 0
    )

    alerts_unresolved = (
        db.scalar(
            select(func.count(Alert.id)).where(
                Alert.device_id == device.id,
                Alert.resolved.is_(False),
            )
        )
        or 0
    )

    recovery_actions_count = (
        db.scalar(select(func.count(RecoveryAction.id)).where(RecoveryAction.device_id == device.id))
        or 0
    )

    health = _build_health_response(device=device, db=db)

    return DeviceSummaryResponse(
        device=DeviceResponse.model_validate(device),
        latest_metric=MetricResponse.model_validate(latest_metric) if latest_metric else None,
        recent_metrics=[MetricResponse.model_validate(metric) for metric in recent_metrics],
        recent_alerts=[AlertResponse.model_validate(alert) for alert in recent_alerts],
        recent_recovery_actions=[
            RecoveryActionResponse.model_validate(action)
            for action in recent_recovery_actions
        ],
        health=health,
        counts=DeviceSummaryCounts(
            metrics=metrics_count,
            heartbeats=heartbeats_count,
            alerts_total=alerts_total,
            alerts_unresolved=alerts_unresolved,
            recovery_actions=recovery_actions_count,
        ),
    )