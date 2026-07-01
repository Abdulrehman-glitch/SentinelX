"""Embedded device telemetry endpoint.

Accepts sensor readings from Arduino/IoT bridge agents. Authentication is via
Bearer device credential token. The organization_id is always derived from the
registered device/token and never trusted from the payload.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_device_from_token
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.alert import Alert
from app.models.device import Device
from app.models.embedded_telemetry import EmbeddedTelemetry
from app.models.user import User
from app.services.audit_log_service import create_audit_log
from app.services.tenant import get_scoped_device_or_404

_settings = get_settings()
router = APIRouter(prefix="/telemetry", tags=["Embedded Telemetry"])


class EmbeddedTelemetryPayload(BaseModel):
    device_id: str
    agent_type: str = "embedded"
    temperature_c: float | None = Field(default=None, ge=-40, le=125)
    humidity_percent: float | None = Field(default=None, ge=0, le=100)
    pressure_hpa: float | None = Field(default=None, ge=300, le=1200)
    accel_x: float | None = None
    accel_y: float | None = None
    accel_z: float | None = None
    gyro_x: float | None = None
    gyro_y: float | None = None
    gyro_z: float | None = None
    impact_detected: bool = False
    raw_payload: dict[str, Any] | None = None


class EmbeddedTelemetryResponse(BaseModel):
    id: str
    device_id: str
    organization_id: str
    alerts_created: int
    recorded_at: str

    model_config = {"from_attributes": True}


def _recent_unresolved_alert_exists(db: Session, *, device_id, alert_type: str, cooldown_seconds: int = 300) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=cooldown_seconds)
    existing = db.scalar(
        select(Alert)
        .where(
            Alert.device_id == device_id,
            Alert.alert_type == alert_type,
            Alert.resolved.is_(False),
            Alert.created_at >= cutoff,
        )
        .limit(1)
    )
    return existing is not None


@router.post("/embedded", response_model=EmbeddedTelemetryResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(_settings.rate_limit_telemetry)
async def ingest_embedded_telemetry(
    request: Request,
    payload: EmbeddedTelemetryPayload,
    authenticated_device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
) -> dict:
    """Accept Arduino bridge telemetry using device-token auth."""
    device = authenticated_device

    if str(device.id) != payload.device_id and device.hostname != payload.device_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device token does not match payload device_id.")

    org_id = device.organization_id
    if not org_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Device is not associated with an organization.")

    device.status = "online"
    device.last_seen_at = datetime.now(timezone.utc)

    telemetry = EmbeddedTelemetry(
        organization_id=org_id,
        device_id=device.id,
        temperature_c=payload.temperature_c,
        humidity_percent=payload.humidity_percent,
        pressure_hpa=payload.pressure_hpa,
        accel_x=payload.accel_x,
        accel_y=payload.accel_y,
        accel_z=payload.accel_z,
        gyro_x=payload.gyro_x,
        gyro_y=payload.gyro_y,
        gyro_z=payload.gyro_z,
        impact_detected=payload.impact_detected,
        raw_payload=payload.raw_payload or payload.model_dump(exclude_none=True),
    )

    db.add(telemetry)
    db.flush()

    alerts_created = 0

    if payload.impact_detected and not _recent_unresolved_alert_exists(
        db, device_id=device.id, alert_type="impact_detected", cooldown_seconds=30
    ):
        db.add(
            Alert(
                organization_id=org_id,
                device_id=device.id,
                alert_type="impact_detected",
                severity="critical",
                message=f"Impact event detected on {device.display_name or device.hostname}",
            )
        )
        alerts_created += 1

    if payload.temperature_c is not None:
        if payload.temperature_c > 50 and not _recent_unresolved_alert_exists(
            db, device_id=device.id, alert_type="temperature_critical", cooldown_seconds=120
        ):
            db.add(
                Alert(
                    organization_id=org_id,
                    device_id=device.id,
                    alert_type="temperature_critical",
                    severity="critical",
                    message=f"Critical temperature {payload.temperature_c:.1f}°C on {device.display_name or device.hostname}",
                )
            )
            alerts_created += 1
        elif payload.temperature_c > 40 and not _recent_unresolved_alert_exists(
            db, device_id=device.id, alert_type="temperature_warning", cooldown_seconds=300
        ):
            db.add(
                Alert(
                    organization_id=org_id,
                    device_id=device.id,
                    alert_type="temperature_warning",
                    severity="warning",
                    message=f"Elevated temperature {payload.temperature_c:.1f}°C on {device.display_name or device.hostname}",
                )
            )
            alerts_created += 1

    if payload.pressure_hpa is not None and payload.pressure_hpa >= 1030 and not _recent_unresolved_alert_exists(
        db, device_id=device.id, alert_type="pressure_anomaly", cooldown_seconds=600
    ):
        db.add(
            Alert(
                organization_id=org_id,
                device_id=device.id,
                alert_type="pressure_anomaly",
                severity="warning",
                message=f"Pressure anomaly {payload.pressure_hpa:.1f} hPa on {device.display_name or device.hostname}",
            )
        )
        alerts_created += 1

    create_audit_log(
        db,
        organization_id=org_id,
        actor_type="agent",
        actor_id=str(device.id),
        action="embedded_telemetry_received",
        target_type="device",
        target_id=str(device.id),
        severity="info",
        message=f"Embedded telemetry received from {device.hostname}",
        metadata={"alerts_created": alerts_created, "has_impact": payload.impact_detected},
    )

    db.commit()
    db.refresh(telemetry)

    return {
        "id": str(telemetry.id),
        "device_id": str(device.id),
        "organization_id": str(org_id),
        "alerts_created": alerts_created,
        "recorded_at": telemetry.recorded_at.isoformat(),
    }


@router.get("/embedded/{device_id}")
def list_embedded_telemetry(
    device_id: str,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return embedded telemetry history with tenant isolation."""
    try:
        device_uuid = uuid.UUID(device_id)
        device = get_scoped_device_or_404(db=db, device_id=device_uuid, current_user=current_user)
    except (ValueError, HTTPException):
        # Allow lookup by hostname for Arduino bridge/frontend convenience.
        statement = select(Device).where(Device.hostname == device_id).limit(1)
        if current_user.role != "platform_admin":
            statement = statement.where(Device.organization_id == current_user.organization_id)
        device = db.scalar(statement)
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")

    safe_limit = min(max(limit, 1), 500)
    rows = list(
        db.scalars(
            select(EmbeddedTelemetry)
            .where(EmbeddedTelemetry.device_id == device.id)
            .order_by(EmbeddedTelemetry.recorded_at.desc())
            .limit(safe_limit)
        )
    )

    return [
        {
            "id": str(row.id),
            "organization_id": str(row.organization_id),
            "device_id": str(row.device_id),
            "temperature_c": row.temperature_c,
            "humidity_percent": row.humidity_percent,
            "pressure_hpa": row.pressure_hpa,
            "accel_x": row.accel_x,
            "accel_y": row.accel_y,
            "accel_z": row.accel_z,
            "gyro_x": row.gyro_x,
            "gyro_y": row.gyro_y,
            "gyro_z": row.gyro_z,
            "impact_detected": row.impact_detected,
            "raw_payload": row.raw_payload,
            "recorded_at": row.recorded_at.isoformat(),
        }
        for row in rows
    ]
