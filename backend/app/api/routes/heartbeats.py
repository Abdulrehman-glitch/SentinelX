from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_device_from_token
from app.db.session import get_db
from app.models.agent_heartbeat import AgentHeartbeat
from app.models.device import Device
from app.schemas.heartbeat import HeartbeatCreateRequest, HeartbeatResponse
from app.services.audit_log_service import create_audit_log

router = APIRouter(prefix="/heartbeats", tags=["Heartbeats"])


@router.post("", response_model=HeartbeatResponse, status_code=status.HTTP_201_CREATED)
def create_heartbeat(
    payload: HeartbeatCreateRequest,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> AgentHeartbeat:
    """Store an agent heartbeat using device-token authentication."""
    if authenticated_device.id != payload.device_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device token does not match payload device_id.")

    device = authenticated_device
    if device.organization_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Device is not associated with an organization.")

    heartbeat = AgentHeartbeat(organization_id=device.organization_id, device_id=device.id, status=payload.status, message=payload.message)

    device.status = payload.status
    device.last_seen_at = datetime.now(timezone.utc)

    db.add(heartbeat)

    # Avoid noisy audit spam: only log non-online heartbeats.
    if payload.status.lower() != "online":
        create_audit_log(
            db,
            organization_id=device.organization_id,
            actor_type="agent",
            actor_id=str(device.id),
            action="heartbeat_status_changed",
            target_type="device",
            target_id=str(device.id),
            severity="warning",
            message=f"Agent heartbeat status changed to {payload.status}: {device.hostname}",
            metadata={"message": payload.message},
        )

    db.commit()
    db.refresh(heartbeat)

    return heartbeat
