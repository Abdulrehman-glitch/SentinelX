import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.alert import Alert
from app.models.device import Device
from app.models.system_metric import SystemMetric
from app.schemas.metric import MetricCreateRequest, MetricIngestResponse, MetricResponse
from app.services.anomaly_service import analyse_system_metrics

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.post("", response_model=MetricIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_metric(payload: MetricCreateRequest, db: Session = Depends(get_db)) -> MetricIngestResponse:
    """
    Stores system metrics and generates alerts when thresholds are exceeded.
    """

    device = db.get(Device, payload.device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    metric = SystemMetric(
        device_id=payload.device_id,
        cpu_percent=payload.cpu_percent,
        memory_percent=payload.memory_percent,
        disk_percent=payload.disk_percent,
    )

    device.status = "online"
    device.last_seen_at = datetime.now(timezone.utc)

    db.add(metric)
    db.flush()

    alert_candidates = analyse_system_metrics(
        cpu_percent=payload.cpu_percent,
        memory_percent=payload.memory_percent,
        disk_percent=payload.disk_percent,
    )

    alerts_created = 0

    for candidate in alert_candidates:
        alert = Alert(
            device_id=payload.device_id,
            alert_type=candidate.alert_type,
            severity=candidate.severity,
            message=candidate.message,
        )
        db.add(alert)
        alerts_created += 1

    db.commit()
    db.refresh(metric)

    return MetricIngestResponse(
        metric=MetricResponse.model_validate(metric),
        alerts_created=alerts_created,
    )


@router.get("/device/{device_id}", response_model=list[MetricResponse])
def list_device_metrics(
    device_id: uuid.UUID,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[SystemMetric]:
    """
    Returns recent metrics for a specific device.
    """

    device = db.get(Device, device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    safe_limit = min(max(limit, 1), 200)

    statement = (
        select(SystemMetric)
        .where(SystemMetric.device_id == device_id)
        .order_by(SystemMetric.recorded_at.desc())
        .limit(safe_limit)
    )

    return list(db.scalars(statement))