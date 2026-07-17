import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.device import Device
from app.models.device_credential import DeviceCredential
from app.models.enrollment_code import EnrollmentCode
from app.models.user import User
from app.schemas.device import DeviceResponse
from app.schemas.enrollment import (
    DeviceEnrollRequest,
    DeviceEnrollResponse,
    EnrollmentCodeCreateRequest,
    EnrollmentCodeCreateResponse,
    EnrollmentCodeResponse,
)
from app.services.audit_log_service import create_audit_log
from app.services.device_token_service import (
    generate_device_token,
    generate_enrollment_code,
    token_preview,
)
from app.services.security_log_service import create_security_log
from app.services.tenant import require_org_user

router = APIRouter(prefix="/devices", tags=["Device Enrollment"])

_settings = get_settings()

_ENROLLMENT_CODE = re.compile(r"^sxe_([0-9a-f]{32})\.[A-Za-z0-9_\-]+$")


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


@router.post(
    "/enrollment-codes",
    response_model=EnrollmentCodeCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_enrollment_code(
    payload: EnrollmentCodeCreateRequest,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> EnrollmentCodeCreateResponse:
    """Mint a single-use enrolment code. The raw code is returned once only."""
    if current_user.role == "platform_admin" and payload.organization_id is not None:
        org_id = payload.organization_id
    else:
        org_id = require_org_user(current_user)

    code_id = uuid.uuid4()
    raw_code = generate_enrollment_code(code_id)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=payload.expires_in_minutes)

    code = EnrollmentCode(
        id=code_id,
        organization_id=org_id,
        name=payload.name.strip(),
        code_hash=hash_password(raw_code),
        code_preview=token_preview(raw_code),
        created_by=current_user.id,
        expires_at=expires_at,
    )

    db.add(code)
    db.flush()

    create_audit_log(
        db,
        organization_id=org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="enrollment_code_created",
        target_type="enrollment_code",
        target_id=str(code.id),
        severity="warning",
        message=f"Enrolment code created: {code.name}",
        metadata={"expires_at": expires_at.isoformat(), "code_preview": code.code_preview},
    )

    db.commit()
    db.refresh(code)

    return EnrollmentCodeCreateResponse(
        id=code.id,
        organization_id=code.organization_id,
        name=code.name,
        code=raw_code,
        code_preview=code.code_preview,
        expires_at=code.expires_at,
        created_at=code.created_at,
    )


@router.get("/enrollment-codes", response_model=list[EnrollmentCodeResponse])
def list_enrollment_codes(
    limit: int = 100,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> list[EnrollmentCode]:
    safe_limit = min(max(limit, 1), 500)
    statement = select(EnrollmentCode).order_by(EnrollmentCode.created_at.desc()).limit(safe_limit)
    if current_user.role != "platform_admin":
        statement = statement.where(EnrollmentCode.organization_id == require_org_user(current_user))
    return list(db.scalars(statement))


@router.delete("/enrollment-codes/{code_id}", response_model=EnrollmentCodeResponse)
def revoke_enrollment_code(
    code_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> EnrollmentCode:
    code = db.get(EnrollmentCode, code_id)
    if not code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrolment code not found.")
    if current_user.role != "platform_admin" and code.organization_id != require_org_user(current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrolment code not found.")

    code.revoked_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        organization_id=code.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="enrollment_code_revoked",
        target_type="enrollment_code",
        target_id=str(code.id),
        severity="warning",
        message=f"Enrolment code revoked: {code.name}",
        metadata={"code_preview": code.code_preview},
    )

    db.commit()
    db.refresh(code)
    return code


def _reject_enrollment(
    db: Session,
    request: Request,
    *,
    reason: str,
    organization_id: uuid.UUID | None = None,
) -> HTTPException:
    """Record a failed enrolment attempt in the security log, return the 401."""
    create_security_log(
        db,
        event_type="device_enrollment",
        action="device_enroll_rejected",
        message=f"Device enrolment rejected: {reason}",
        severity="warning",
        actor_type="agent",
        ip_address=_client_ip(request),
        organization_id=organization_id,
        status="failure",
        metadata={"reason": reason},
    )
    db.commit()
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid, expired, or already-used enrolment code.",
    )


@router.post("/enroll", response_model=DeviceEnrollResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(_settings.rate_limit_enroll)
def enroll_device(
    request: Request,
    payload: DeviceEnrollRequest,
    db: Session = Depends(get_db),
) -> DeviceEnrollResponse:
    """Exchange a single-use enrolment code for a device record + device token.

    This replaces anonymous /devices/register for agents: the code proves an
    admin authorised the enrolment, and it is invalidated atomically with the
    credential creation. The device token is returned once only.
    """
    now = datetime.now(timezone.utc)

    match = _ENROLLMENT_CODE.match(payload.enrollment_code)
    if not match:
        raise _reject_enrollment(db, request, reason="malformed_code")

    code = db.get(EnrollmentCode, uuid.UUID(hex=match.group(1)))
    if code is None or not verify_password(payload.enrollment_code, code.code_hash):
        raise _reject_enrollment(db, request, reason="unknown_code")
    if code.revoked_at is not None:
        raise _reject_enrollment(db, request, reason="revoked_code", organization_id=code.organization_id)
    if code.used_at is not None:
        raise _reject_enrollment(db, request, reason="already_used", organization_id=code.organization_id)
    expires_at = code.expires_at if code.expires_at.tzinfo else code.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise _reject_enrollment(db, request, reason="expired_code", organization_id=code.organization_id)

    # Idempotent by (hostname, org): re-enrolling an existing device refreshes
    # it and issues a fresh credential rather than duplicating the device.
    device = db.scalar(
        select(Device).where(
            Device.hostname == payload.hostname,
            Device.organization_id == code.organization_id,
        )
    )

    if device:
        device.ip_address = payload.ip_address
        device.os_name = payload.os_name
        device.status = "online"
        device.last_seen_at = now
        if payload.agent_version:
            device.agent_version = payload.agent_version
    else:
        device = Device(
            hostname=payload.hostname,
            display_name=payload.display_name or payload.hostname,
            ip_address=payload.ip_address,
            os_name=payload.os_name,
            status="online",
            last_seen_at=now,
            organization_id=code.organization_id,
            device_type=payload.device_type,
            agent_type=payload.agent_type,
            agent_version=payload.agent_version,
        )
        db.add(device)
        db.flush()

    credential_id = uuid.uuid4()
    raw_token = generate_device_token(credential_id)
    credential = DeviceCredential(
        id=credential_id,
        organization_id=code.organization_id,
        device_id=device.id,
        name=f"{device.hostname} (enrolled)",
        token_hash=hash_password(raw_token),
        token_preview=token_preview(raw_token),
        is_active=True,
    )
    db.add(credential)

    code.used_at = now
    code.used_by_device_id = device.id

    create_audit_log(
        db,
        organization_id=code.organization_id,
        actor_type="agent",
        actor_id=payload.hostname,
        action="device_enrolled",
        target_type="device",
        target_id=str(device.id),
        severity="info",
        message=f"Device enrolled via code '{code.name}': {payload.hostname}",
        metadata={
            "hostname": payload.hostname,
            "enrollment_code_id": str(code.id),
            "credential_id": str(credential_id),
        },
    )

    create_security_log(
        db,
        event_type="device_enrollment",
        action="device_enrolled",
        message=f"Device enrolled: {payload.hostname}",
        severity="info",
        actor_type="agent",
        actor_id=payload.hostname,
        ip_address=_client_ip(request),
        organization_id=code.organization_id,
        resource_type="device",
        resource_id=str(device.id),
        status="success",
        metadata={"enrollment_code_id": str(code.id)},
    )

    db.commit()
    db.refresh(device)

    return DeviceEnrollResponse(
        device=DeviceResponse.model_validate(device),
        credential_id=credential_id,
        device_token=raw_token,
    )
