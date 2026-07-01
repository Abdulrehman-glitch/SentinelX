import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.device import Device
from app.models.device_credential import DeviceCredential
from app.models.user import User
from app.schemas.device_credential import (
    DeviceCredentialCreateRequest,
    DeviceCredentialCreateResponse,
    DeviceCredentialResponse,
)
from app.services.audit_log_service import create_audit_log
from app.services.tenant import assert_same_org, require_org_user

router = APIRouter(prefix="/device-credentials", tags=["Device Credentials"])


def _generate_agent_token() -> str:
    return f"sx_agent_{secrets.token_urlsafe(32)}"


def _token_preview(token: str) -> str:
    return f"{token[:16]}..."


def _get_credential_or_404(credential_id: uuid.UUID, current_user: User, db: Session) -> DeviceCredential:
    credential = db.get(DeviceCredential, credential_id)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device credential not found.")
    assert_same_org(credential.organization_id, current_user)
    return credential


@router.post("", response_model=DeviceCredentialCreateResponse, status_code=status.HTTP_201_CREATED)
def create_device_credential(
    payload: DeviceCredentialCreateRequest,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> DeviceCredentialCreateResponse:
    """Create a new agent/device token.

    Tenant users can only create tokens for devices inside their own
    organization. The raw token is returned once only; only its hash is stored.
    """
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)

    device: Device | None = None
    if payload.device_id:
        device = db.get(Device, payload.device_id)
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked device not found.")
        assert_same_org(device.organization_id, current_user)
        org_id = device.organization_id

    if current_user.role != "platform_admin" and org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization is required.")

    raw_token = _generate_agent_token()
    preview = _token_preview(raw_token)

    credential = DeviceCredential(
        organization_id=org_id,
        device_id=payload.device_id,
        name=payload.name.strip(),
        token_hash=hash_password(raw_token),
        token_preview=preview,
        is_active=True,
    )

    db.add(credential)
    db.flush()

    create_audit_log(
        db,
        organization_id=org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="device_credential_created",
        target_type="device_credential",
        target_id=str(credential.id),
        severity="warning",
        message=f"Device credential created: {credential.name}",
        metadata={"device_id": str(payload.device_id) if payload.device_id else None, "token_preview": preview},
    )

    db.commit()
    db.refresh(credential)

    return DeviceCredentialCreateResponse(
        id=credential.id,
        organization_id=credential.organization_id,
        device_id=credential.device_id,
        name=credential.name,
        token=raw_token,
        token_preview=credential.token_preview,
        is_active=credential.is_active,
        created_at=credential.created_at,
    )


@router.get("", response_model=list[DeviceCredentialResponse])
def list_device_credentials(
    limit: int = 100,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> list[DeviceCredential]:
    safe_limit = min(max(limit, 1), 500)
    statement = select(DeviceCredential).order_by(DeviceCredential.created_at.desc()).limit(safe_limit)
    if current_user.role != "platform_admin":
        statement = statement.where(DeviceCredential.organization_id == require_org_user(current_user))
    return list(db.scalars(statement))


@router.patch("/{credential_id}/revoke", response_model=DeviceCredentialResponse)
def revoke_device_credential(
    credential_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> DeviceCredential:
    credential = _get_credential_or_404(credential_id=credential_id, current_user=current_user, db=db)

    credential.is_active = False
    credential.revoked_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        organization_id=credential.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="device_credential_revoked",
        target_type="device_credential",
        target_id=str(credential.id),
        severity="warning",
        message=f"Device credential revoked: {credential.name}",
        metadata={"token_preview": credential.token_preview},
    )

    db.commit()
    db.refresh(credential)

    return credential
