from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agent_heartbeat import AgentHeartbeat
from app.models.device import Device
from app.schemas.heartbeat import HeartbeatCreateRequest, HeartbeatResponse

router = APIRouter(prefix="/heartbeats", tags=["Heartbeats"])


@router.post("", response_model=HeartbeatResponse, status_code=status.HTTP_201_CREATED)
def create_heartbeat(payload: HeartbeatCreateRequest, db: Session = Depends(get_db)) -> AgentHeartbeat:
    """
    Stores an agent heartbeat and updates the device's latest status.
    """

    device = db.get(Device, payload.device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    heartbeat = AgentHeartbeat(
        device_id=payload.device_id,
        status=payload.status,
        message=payload.message,
    )

    device.status = payload.status
    device.last_seen_at = datetime.now(timezone.utc)

    db.add(heartbeat)
    db.commit()
    db.refresh(heartbeat)

    return heartbeat