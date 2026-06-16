import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.device import Device
from app.schemas.device import DeviceRegisterRequest, DeviceResponse

router = APIRouter(prefix="/devices", tags=["Devices"])


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

    device = db.get(Device, device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    return device