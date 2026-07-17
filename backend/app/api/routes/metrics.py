import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_device_from_token
from app.db.session import get_db
from app.models.alert import Alert
from app.models.device import Device
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.system_metric import SystemMetric
from app.models.user import User
from app.schemas.metric import (
    MetricBatchIngestResponse,
    MetricBatchRequest,
    MetricCreateRequest,
    MetricIngestResponse,
    MetricResponse,
    MetricSample,
)
from app.services.alert_rule_service import (
    AlertRuleCandidate,
    evaluate_enabled_alert_rules,
    is_alert_suppressed_by_cooldown,
)
from app.services.anomaly_service import FALLBACK_ALERT_COOLDOWN_SECONDS, analyse_system_metrics
from app.services.audit_log_service import create_audit_log
from app.services.tenant import get_scoped_device_or_404

router = APIRouter(prefix="/metrics", tags=["Metrics"])


def _create_auto_incident_for_critical_alert(
    db: Session,
    *,
    device: Device,
    alert: Alert,
    candidate_message: str,
) -> None:
    auto_title = f"Critical {alert.alert_type} incident"

    existing_open_incident = db.scalar(
        select(Incident)
        .where(
            Incident.organization_id == device.organization_id,
            Incident.device_id == device.id,
            Incident.title == auto_title,
            Incident.status.in_(["open", "investigating"]),
        )
        .limit(1)
    )
    if existing_open_incident:
        return

    incident = Incident(
        organization_id=device.organization_id,
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
            metadata_json={"alert_id": str(alert.id), "alert_type": alert.alert_type, "device_id": str(device.id)},
        )
    )

    create_audit_log(
        db,
        organization_id=device.organization_id,
        actor_type="system",
        action="incident_created",
        target_type="incident",
        target_id=str(incident.id),
        severity="critical",
        message=f"Automatic incident created from critical alert: {auto_title}",
        metadata={"device_id": str(device.id), "alert_id": str(alert.id), "source": "alert"},
    )


def _fallback_candidates(cpu_percent: float | None, memory_percent: float, disk_percent: float) -> list[AlertRuleCandidate]:
    built_in_alerts = analyse_system_metrics(cpu_percent=cpu_percent, memory_percent=memory_percent, disk_percent=disk_percent)
    return [
        AlertRuleCandidate(
            alert_type=item.alert_type,
            severity=item.severity,
            message=item.message,
            rule_id=None,
            cooldown_seconds=FALLBACK_ALERT_COOLDOWN_SECONDS,
        )
        for item in built_in_alerts
    ]


def _raise_alerts_for_sample(
    db: Session,
    *,
    device: Device,
    metric: SystemMetric,
    cpu_percent: float | None,
    memory_percent: float,
    disk_percent: float,
) -> int:
    """Evaluate alert rules (or fallback thresholds) for one stored sample."""
    rule_candidates = evaluate_enabled_alert_rules(
        db,
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        disk_percent=disk_percent,
        organization_id=device.organization_id,
        device_id=device.id,
    )

    alert_candidates = rule_candidates or _fallback_candidates(
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        disk_percent=disk_percent,
    )

    alerts_created = 0

    for candidate in alert_candidates:
        # Cooldown applies to built-in fallback alerts too, not just configured
        # rules — otherwise sustained pressure creates an alert per sample.
        if is_alert_suppressed_by_cooldown(
            db,
            device_id=device.id,
            alert_type=candidate.alert_type,
            cooldown_seconds=candidate.cooldown_seconds,
        ):
            continue

        alert = Alert(
            organization_id=device.organization_id,
            device_id=device.id,
            alert_type=candidate.alert_type,
            severity=candidate.severity,
            message=candidate.message,
        )

        db.add(alert)
        db.flush()

        create_audit_log(
            db,
            organization_id=device.organization_id,
            actor_type="system",
            action="alert_generated",
            target_type="alert",
            target_id=str(alert.id),
            severity=candidate.severity,
            message=f"Alert generated: {candidate.message}",
            metadata={
                "device_id": str(device.id),
                "metric_id": str(metric.id),
                "alert_type": candidate.alert_type,
                "rule_id": str(candidate.rule_id) if candidate.rule_id else None,
            },
        )

        if candidate.severity == "critical":
            _create_auto_incident_for_critical_alert(db, device=device, alert=alert, candidate_message=candidate.message)

        alerts_created += 1

    return alerts_created


@router.post("", response_model=MetricIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_metric(
    payload: MetricCreateRequest,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> MetricIngestResponse:
    """Store desktop/laptop agent metrics using device-token auth.

    The device id in the payload must match the device resolved from the token,
    preventing one agent from writing telemetry for another tenant/device.
    """
    if authenticated_device.id != payload.device_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device token does not match payload device_id.")

    device = authenticated_device
    if device.organization_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Device is not associated with an organization.")

    # Idempotent retry: acknowledge the already-stored sample instead of
    # duplicating it when the agent resends after a lost response.
    if payload.event_id is not None:
        existing = db.scalar(
            select(SystemMetric).where(
                SystemMetric.device_id == device.id,
                SystemMetric.event_id == payload.event_id,
            )
        )
        if existing is not None:
            return MetricIngestResponse(
                metric=MetricResponse.model_validate(existing),
                alerts_created=0,
                duplicate=True,
            )

    metric = SystemMetric(
        organization_id=device.organization_id,
        device_id=device.id,
        event_id=payload.event_id,
        cpu_percent=payload.cpu_percent,
        memory_percent=payload.memory_percent,
        disk_percent=payload.disk_percent,
        battery_percent=payload.battery_percent,
        battery_charging=payload.battery_charging,
        battery_temperature_c=payload.battery_temperature_c,
        thermal_status=payload.thermal_status,
        network_transport=payload.network_transport,
        network_validated=payload.network_validated,
        network_metered=payload.network_metered,
        latency_ms=payload.latency_ms,
    )

    device.status = "online"
    device.last_seen_at = datetime.now(timezone.utc)

    db.add(metric)
    db.flush()

    alerts_created = _raise_alerts_for_sample(
        db,
        device=device,
        metric=metric,
        cpu_percent=payload.cpu_percent,
        memory_percent=payload.memory_percent,
        disk_percent=payload.disk_percent,
    )

    db.commit()
    db.refresh(metric)

    return MetricIngestResponse(metric=MetricResponse.model_validate(metric), alerts_created=alerts_created)


@router.post("/batch", response_model=MetricBatchIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_metric_batch(
    payload: MetricBatchRequest,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> MetricBatchIngestResponse:
    """Store a batch of samples in one request (mobile offline-queue flush).

    Client-side capture timestamps are preserved so a queue flushed after an
    offline window lands as real history instead of a burst at "now". Alert
    rules run only against the newest sample — a backlog describes the past
    and must not fire a storm of stale alerts.
    """
    if authenticated_device.id != payload.device_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device token does not match payload device_id.")

    device = authenticated_device
    if device.organization_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Device is not associated with an organization.")

    now = datetime.now(timezone.utc)
    ordered = sorted(payload.samples, key=lambda s: s.recorded_at or now)

    # Deduplicate against already-stored event_ids (lost-response retries) and
    # within the batch itself. The DB unique constraint remains the backstop.
    batch_event_ids = [s.event_id for s in ordered if s.event_id is not None]
    existing_event_ids: set[uuid.UUID] = set()
    if batch_event_ids:
        existing_event_ids = set(
            db.scalars(
                select(SystemMetric.event_id).where(
                    SystemMetric.device_id == device.id,
                    SystemMetric.event_id.in_(batch_event_ids),
                )
            )
        )

    seen_event_ids: set[uuid.UUID] = set()
    duplicates = 0
    latest_metric: SystemMetric | None = None
    latest_sample: MetricSample | None = None

    for sample in ordered:
        if sample.event_id is not None:
            if sample.event_id in existing_event_ids or sample.event_id in seen_event_ids:
                duplicates += 1
                continue
            seen_event_ids.add(sample.event_id)

        recorded_at = sample.recorded_at or now
        # Reject client clocks from writing the future into history.
        if recorded_at > now:
            recorded_at = now
        metric = SystemMetric(
            organization_id=device.organization_id,
            device_id=device.id,
            event_id=sample.event_id,
            cpu_percent=sample.cpu_percent,
            memory_percent=sample.memory_percent,
            disk_percent=sample.disk_percent,
            battery_percent=sample.battery_percent,
            battery_charging=sample.battery_charging,
            battery_temperature_c=sample.battery_temperature_c,
            thermal_status=sample.thermal_status,
            network_transport=sample.network_transport,
            network_validated=sample.network_validated,
            network_metered=sample.network_metered,
            latency_ms=sample.latency_ms,
            recorded_at=recorded_at,
        )
        db.add(metric)
        latest_metric = metric
        latest_sample = sample

    device.status = "online"
    device.last_seen_at = now
    db.flush()

    alerts_created = 0
    if latest_metric is not None and latest_sample is not None:
        alerts_created = _raise_alerts_for_sample(
            db,
            device=device,
            metric=latest_metric,
            cpu_percent=latest_sample.cpu_percent,
            memory_percent=latest_sample.memory_percent,
            disk_percent=latest_sample.disk_percent,
        )

    db.commit()
    if latest_metric is not None:
        db.refresh(latest_metric)

    return MetricBatchIngestResponse(
        stored=len(ordered) - duplicates,
        duplicates=duplicates,
        alerts_created=alerts_created,
        latest=MetricResponse.model_validate(latest_metric) if latest_metric else None,
    )


@router.get("/device/{device_id}", response_model=list[MetricResponse])
def list_device_metrics(
    device_id: uuid.UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SystemMetric]:
    get_scoped_device_or_404(db=db, device_id=device_id, current_user=current_user)
    safe_limit = min(max(limit, 1), 200)

    statement = (
        select(SystemMetric)
        .where(SystemMetric.device_id == device_id)
        .order_by(SystemMetric.recorded_at.desc())
        .limit(safe_limit)
    )

    return list(db.scalars(statement))
