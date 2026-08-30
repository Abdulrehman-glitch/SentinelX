"""Device pairing sessions — the human-friendly wrapper around enrolment codes.

A pairing session is an enrolment code plus everything the console needs to
show a QR code and watch the enrolment happen live: the LAN address the agent
should call back on, the payload to render as a QR, and a polled status that
moves waiting → enrolled → telemetry_live as the device comes up. No new
tables — the session IS the enrollment_codes row; status is derived.
"""

import json
import re
import socket
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.device import Device
from app.models.enrollment_code import EnrollmentCode
from app.models.system_metric import SystemMetric
from app.models.user import User
from app.schemas.device import DeviceResponse
from app.schemas.pairing import (
    PairingHost,
    PairingHostsResponse,
    PairingSessionCreateRequest,
    PairingSessionCreateResponse,
    PairingSessionStatusResponse,
)
from app.services.audit_log_service import create_audit_log
from app.services.device_token_service import generate_enrollment_code, token_preview
from app.services.tenant import require_org_user

router = APIRouter(prefix="/pairing", tags=["Device Pairing"])

# Session names are parseable so pairing sessions can be told apart from
# hand-minted enrolment codes without a schema change.
_SESSION_NAME_PREFIX = "pairing:"

_HOST_PATTERN = re.compile(r"^[A-Za-z0-9.\-]+(:\d{1,5})?$")


def _normalise_backend_url(raw: str | None, request: Request) -> str:
    """Turn a chosen host (or nothing) into the URL agents should call.

    Only host[:port] shapes are accepted — this string ends up inside a QR
    code, so it must never be able to smuggle a path or credentials.
    """
    port = request.url.port or 8000
    if raw is None or not raw.strip():
        return f"http://{_default_lan_address() or '127.0.0.1'}:{port}"

    candidate = raw.strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    if not _HOST_PATTERN.match(candidate):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="backend_url must be a host or host:port.",
        )
    if ":" not in candidate:
        candidate = f"{candidate}:{port}"
    scheme = "https" if raw.strip().startswith("https://") else "http"
    return f"{scheme}://{candidate}"


def _default_lan_address() -> str | None:
    """The interface the OS would route external traffic through — usually the
    LAN adapter a phone on the same Wi-Fi can reach. UDP connect sends nothing."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            return probe.getsockname()[0]
    except OSError:
        return None


def _lan_addresses() -> list[str]:
    addresses: list[str] = []
    primary = _default_lan_address()
    if primary:
        addresses.append(primary)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = info[4][0]
            if addr not in addresses:
                addresses.append(addr)
    except OSError:
        pass
    # Loopback and link-local addresses are useless to another device.
    return [a for a in addresses if not a.startswith(("127.", "169.254."))]


@router.get("/hosts", response_model=PairingHostsResponse)
def list_pairing_hosts(
    request: Request,
    _: User = Depends(require_role(["admin", "owner", "platform_admin"])),
) -> PairingHostsResponse:
    port = request.url.port or 8000
    return PairingHostsResponse(
        hosts=[PairingHost(address=a, url=f"http://{a}:{port}") for a in _lan_addresses()],
        port=port,
    )


@router.post("/sessions", response_model=PairingSessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_pairing_session(
    payload: PairingSessionCreateRequest,
    request: Request,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> PairingSessionCreateResponse:
    org_id = require_org_user(current_user)

    backend_url = _normalise_backend_url(payload.backend_url, request)

    code_id = uuid.uuid4()
    raw_code = generate_enrollment_code(code_id)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=payload.expires_in_minutes)

    session = EnrollmentCode(
        id=code_id,
        organization_id=org_id,
        name=f"{_SESSION_NAME_PREFIX}{payload.platform}",
        code_hash=hash_password(raw_code),
        code_preview=token_preview(raw_code),
        created_by=current_user.id,
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()

    create_audit_log(
        db,
        organization_id=org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="pairing_session_created",
        target_type="enrollment_code",
        target_id=str(session.id),
        severity="info",
        message=f"Pairing session opened for a {payload.platform} device",
        metadata={"platform": payload.platform, "expires_at": expires_at.isoformat()},
    )

    db.commit()
    db.refresh(session)

    qr_payload = json.dumps(
        {"v": 1, "t": "sentinelx-pair", "url": backend_url, "code": raw_code},
        separators=(",", ":"),
    )

    return PairingSessionCreateResponse(
        id=session.id,
        organization_id=session.organization_id,
        platform=payload.platform,
        code=raw_code,
        code_preview=session.code_preview,
        backend_url=backend_url,
        qr_payload=qr_payload,
        expires_at=session.expires_at,
        created_at=session.created_at,
    )


@router.get("/sessions/{session_id}", response_model=PairingSessionStatusResponse)
def get_pairing_session_status(
    session_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> PairingSessionStatusResponse:
    session = db.get(EnrollmentCode, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pairing session not found.")
    if current_user.role != "platform_admin" and session.organization_id != require_org_user(current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pairing session not found.")

    now = datetime.now(timezone.utc)

    device: Device | None = None
    last_telemetry_at: datetime | None = None
    if session.used_by_device_id is not None:
        device = db.get(Device, session.used_by_device_id)

    used_at = session.used_at
    if used_at is not None and used_at.tzinfo is None:
        used_at = used_at.replace(tzinfo=timezone.utc)

    if device is not None and used_at is not None:
        last_telemetry_at = db.scalar(
            select(SystemMetric.recorded_at)
            .where(SystemMetric.device_id == device.id, SystemMetric.recorded_at >= used_at)
            .order_by(SystemMetric.recorded_at.desc())
            .limit(1)
        )

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if session.revoked_at is not None:
        session_status = "revoked"
    elif used_at is not None:
        session_status = "telemetry_live" if last_telemetry_at is not None else "enrolled"
    elif expires_at < now:
        session_status = "expired"
    else:
        session_status = "waiting"

    return PairingSessionStatusResponse(
        id=session.id,
        status=session_status,
        expires_at=expires_at,
        enrolled_at=used_at,
        device=DeviceResponse.model_validate(device) if device is not None else None,
        last_telemetry_at=last_telemetry_at,
    )
