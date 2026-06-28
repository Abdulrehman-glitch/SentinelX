import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.alert import Alert
from app.models.device import Device
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.system_metric import SystemMetric
from app.schemas.metric import MetricCreateRequest, MetricIngestResponse, MetricResponse
from app.services.alert_rule_service import (
    AlertRuleCandidate,
    evaluate_enabled_alert_rules,
    is_alert_suppressed_by_cooldown,
)
from app.services.anomaly_service import analyse_system_metrics
from app.services.audit_log_service import create_audit_log

router = APIRouter(prefix="/metrics", tags=["Metrics"])


def _create_auto_incident_for_critical_alert(
    db: Session,
    *,
    device: Device,
    alert: Alert,
    candidate_message: str,
) -> None:
    """
    Creates one open automatic incident for a critical alert type.

    This is safe because it only creates database records. It does not
    perform recovery commands on the monitored device.
    """

    auto_title = f"Critical {alert.alert_type} incident"

    existing_open_incident = db.scalar(
        select(Incident)
        .where(
            Incident.device_id == device.id,
            Incident.title == auto_title,
            Incident.status.in_(["open", "investigating"]),
        )
        .limit(1)
    )

    if existing_open_incident:
        return

    incident = Incident(
        device_id=device.id,
        title=auto_title,
        description=candidate_message,
        severity="critical",
        status="open",
        source="alert",
        linked_alert_id=alert.id,
        assigned_to=None,
    )

    db.add(incident)
    db.flush()

    db.add(
        IncidentEvent(
            incident_id=incident.id,
            event_type="incident_created",
            message=f"Automatic incident created from critical alert: {alert.message}",
            actor_type="system",
            metadata_json={
                "alert_id": str(alert.id),
                "alert_type": alert.alert_type,
                "device_id": str(device.id),
            },
        )
    )

    create_audit_log(
        db,
        actor_type="system",
        action="incident_created",
        target_type="incident",
        target_id=str(incident.id),
        severity="critical",
        message=f"Automatic incident created from critical alert: {auto_title}",
        metadata={
            "device_id": str(device.id),
            "alert_id": str(alert.id),
            "source": "alert",
        },
    )


def _fallback_candidates(cpu_percent: float, memory_percent: float, disk_percent: float) -> list[AlertRuleCandidate]:
    """
    Converts the original built-in anomaly service output into the same
    candidate structure used by alert-rule evaluation.
    """

    built_in_alerts = analyse_system_metrics(
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        disk_percent=disk_percent,
    )

    return [
        AlertRuleCandidate(
            alert_type=item.alert_type,
            severity=item.severity,
            message=item.message,
            rule_id=None,
            cooldown_seconds=0,
        )
        for item in built_in_alerts
    ]


@router.post("", response_model=MetricIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_metric(payload: MetricCreateRequest, db: Session = Depends(get_db)) -> MetricIngestResponse:
    """
    Stores system metrics and generates alerts.

    If enabled alert rules exist, they are evaluated first. If no enabled
    rules match, the original built-in anomaly detection thresholds are
    used as a fallback.
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

    rule_candidates = evaluate_enabled_alert_rules(
        db,
        cpu_percent=payload.cpu_percent,
        memory_percent=payload.memory_percent,
        disk_percent=payload.disk_percent,
    )

    alert_candidates = rule_candidates or _fallback_candidates(
        cpu_percent=payload.cpu_percent,
        memory_percent=payload.memory_percent,
        disk_percent=payload.disk_percent,
    )

    alerts_created = 0

    for candidate in alert_candidates:
        if candidate.rule_id and is_alert_suppressed_by_cooldown(
            db,
            device_id=payload.device_id,
            alert_type=candidate.alert_type,
            cooldown_seconds=candidate.cooldown_seconds,
        ):
            continue

        alert = Alert(
            device_id=payload.device_id,
            alert_type=candidate.alert_type,
            severity=candidate.severity,
            message=candidate.message,
        )

        db.add(alert)
        db.flush()

        create_audit_log(
            db,
            actor_type="system",
            action="alert_generated",
            target_type="alert",
            target_id=str(alert.id),
            severity=candidate.severity,
            message=f"Alert generated: {candidate.message}",
            metadata={
                "device_id": str(payload.device_id),
                "metric_id": str(metric.id),
                "alert_type": candidate.alert_type,
                "rule_id": str(candidate.rule_id) if candidate.rule_id else None,
            },
        )

        if candidate.severity == "critical":
            _create_auto_incident_for_critical_alert(
                db,
                device=device,
                alert=alert,
                candidate_message=candidate.message,
            )

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