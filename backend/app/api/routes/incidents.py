import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.alert import Alert
from app.models.device import Device
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.user import User
from app.schemas.incident import IncidentCreateRequest, IncidentDetailResponse, IncidentResponse, IncidentStatusUpdateRequest
from app.schemas.incident_event import IncidentEventCreateRequest, IncidentEventResponse
from app.services.audit_log_service import create_audit_log
from app.services.tenant import assert_same_org, require_org_user

router = APIRouter(prefix="/incidents", tags=["Incidents"])


def _get_incident_or_404(incident_id: uuid.UUID, current_user: User, db: Session) -> Incident:
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    assert_same_org(incident.organization_id, current_user)
    return incident


def _validate_optional_links(payload: IncidentCreateRequest, current_user: User, db: Session) -> uuid.UUID | None:
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)

    if payload.device_id:
        device = db.get(Device, payload.device_id)
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked device not found")
        assert_same_org(device.organization_id, current_user)
        org_id = device.organization_id

    if payload.linked_alert_id:
        alert = db.get(Alert, payload.linked_alert_id)
        if not alert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked alert not found")
        assert_same_org(alert.organization_id, current_user)
        org_id = alert.organization_id if org_id is None else org_id

    return org_id


def _add_incident_event(
    db: Session,
    *,
    incident_id: uuid.UUID,
    event_type: str,
    message: str,
    actor_type: str = "system",
    actor_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> IncidentEvent:
    event = IncidentEvent(
        incident_id=incident_id,
        event_type=event_type,
        message=message,
        actor_type=actor_type,
        actor_id=actor_id,
        metadata_json=metadata,
    )
    db.add(event)
    return event


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreateRequest,
    current_user: User = Depends(require_role(["admin", "engineer", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> Incident:
    org_id = _validate_optional_links(payload=payload, current_user=current_user, db=db)
    if current_user.role != "platform_admin" and org_id is None:
        org_id = require_org_user(current_user)

    incident = Incident(
        organization_id=org_id,
        device_id=payload.device_id,
        title=payload.title.strip(),
        description=payload.description,
        severity=payload.severity,
        status="open",
        source=payload.source,
        linked_alert_id=payload.linked_alert_id,
        assigned_to=payload.assigned_to,
    )

    db.add(incident)
    db.flush()

    _add_incident_event(
        db,
        incident_id=incident.id,
        event_type="incident_created",
        message=f"Incident created: {incident.title}",
        actor_type="user",
        actor_id=str(current_user.id),
        metadata={
            "severity": incident.severity,
            "source": incident.source,
            "device_id": str(incident.device_id) if incident.device_id else None,
            "linked_alert_id": str(incident.linked_alert_id) if incident.linked_alert_id else None,
        },
    )

    create_audit_log(
        db,
        organization_id=incident.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="incident_created",
        target_type="incident",
        target_id=str(incident.id),
        severity=incident.severity,
        message=f"Incident created: {incident.title}",
        metadata={"device_id": str(incident.device_id) if incident.device_id else None, "source": incident.source},
    )

    db.commit()
    db.refresh(incident)
    return incident


@router.get("", response_model=list[IncidentResponse])
def list_incidents(
    limit: int = 100,
    status_filter: str | None = None,
    severity: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Incident]:
    safe_limit = min(max(limit, 1), 500)
    conditions = []
    if current_user.role != "platform_admin":
        conditions.append(Incident.organization_id == require_org_user(current_user))
    if status_filter:
        conditions.append(Incident.status == status_filter.lower())
    if severity:
        conditions.append(Incident.severity == severity.lower())

    statement = select(Incident).order_by(Incident.created_at.desc()).limit(safe_limit)
    if conditions:
        statement = statement.where(*conditions)
    return list(db.scalars(statement))


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
def get_incident(
    incident_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Incident:
    incident = db.scalar(select(Incident).options(selectinload(Incident.events)).where(Incident.id == incident_id))
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    assert_same_org(incident.organization_id, current_user)
    incident.events.sort(key=lambda event: event.created_at)
    return incident


@router.patch("/{incident_id}/status", response_model=IncidentResponse)
def update_incident_status(
    incident_id: uuid.UUID,
    payload: IncidentStatusUpdateRequest,
    current_user: User = Depends(require_role(["admin", "engineer", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> Incident:
    incident = _get_incident_or_404(incident_id=incident_id, current_user=current_user, db=db)

    previous_status = incident.status
    incident.status = payload.status
    if payload.status == "resolved":
        incident.resolved_at = datetime.now(timezone.utc)

    _add_incident_event(
        db,
        incident_id=incident.id,
        event_type="status_changed",
        message=f"Incident status changed from {previous_status} to {payload.status}.",
        actor_type="user",
        actor_id=str(current_user.id),
        metadata={"previous_status": previous_status, "new_status": payload.status},
    )

    create_audit_log(
        db,
        organization_id=incident.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="incident_status_changed",
        target_type="incident",
        target_id=str(incident.id),
        severity="info",
        message=f"Incident status changed from {previous_status} to {payload.status}.",
        metadata={"previous_status": previous_status, "new_status": payload.status},
    )

    db.commit()
    db.refresh(incident)
    return incident


@router.patch("/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_incident(
    incident_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "engineer", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> Incident:
    incident = _get_incident_or_404(incident_id=incident_id, current_user=current_user, db=db)

    if incident.status != "resolved":
        previous_status = incident.status
        incident.status = "resolved"
        incident.resolved_at = datetime.now(timezone.utc)

        _add_incident_event(
            db,
            incident_id=incident.id,
            event_type="incident_resolved",
            message=f"Incident resolved from previous status: {previous_status}.",
            actor_type="user",
            actor_id=str(current_user.id),
            metadata={"previous_status": previous_status, "new_status": "resolved"},
        )

        create_audit_log(
            db,
            organization_id=incident.organization_id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="incident_resolved",
            target_type="incident",
            target_id=str(incident.id),
            severity="info",
            message=f"Incident resolved: {incident.title}",
            metadata={"previous_status": previous_status},
        )

    db.commit()
    db.refresh(incident)
    return incident


@router.get("/{incident_id}/events", response_model=list[IncidentEventResponse])
def list_incident_events(
    incident_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IncidentEvent]:
    _get_incident_or_404(incident_id=incident_id, current_user=current_user, db=db)
    statement = select(IncidentEvent).where(IncidentEvent.incident_id == incident_id).order_by(IncidentEvent.created_at.asc())
    return list(db.scalars(statement))


@router.post("/{incident_id}/events", response_model=IncidentEventResponse, status_code=status.HTTP_201_CREATED)
def create_incident_event(
    incident_id: uuid.UUID,
    payload: IncidentEventCreateRequest,
    current_user: User = Depends(require_role(["admin", "engineer", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> IncidentEvent:
    incident = _get_incident_or_404(incident_id=incident_id, current_user=current_user, db=db)

    event = _add_incident_event(
        db,
        incident_id=incident.id,
        event_type=payload.event_type,
        message=payload.message,
        actor_type="user",
        actor_id=str(current_user.id),
        metadata=payload.metadata,
    )

    create_audit_log(
        db,
        organization_id=incident.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="incident_event_added",
        target_type="incident",
        target_id=str(incident.id),
        severity="info",
        message=f"Incident event added: {payload.event_type}",
        metadata={"event_type": payload.event_type},
    )

    db.commit()
    db.refresh(event)
    return event
