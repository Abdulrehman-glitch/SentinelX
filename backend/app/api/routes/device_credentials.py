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

router = APIRouter(prefix="/device-credentials", tags=["Device Credentials"])


def _generate_agent_token() -> str:
    return f"sx_agent_{secrets.token_urlsafe(32)}"


def _token_preview(token: str) -> str:
    return f"{token[:16]}..."


@router.post("", response_model=DeviceCredentialCreateResponse, status_code=status.HTTP_201_CREATED)
def create_device_credential(
    payload: DeviceCredentialCreateRequest,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
) -> DeviceCredentialCreateResponse:
    """
    Creates a new agent API token.

    The raw token is returned once only. The database stores only a hash.
    """

    if payload.device_id and not db.get(Device, payload.device_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked device not found.",
        )

    raw_token = _generate_agent_token()
    preview = _token_preview(raw_token)

    credential = DeviceCredential(
        device_id=payload.device_id,
        name=payload.name,
        token_hash=hash_password(raw_token),
        token_preview=preview,
        is_active=True,
    )

    db.add(credential)
    db.flush()

    create_audit_log(
        db,
        actor_type="user",
        actor_id=str(current_user.id),
        action="device_credential_created",
        target_type="device_credential",
        target_id=str(credential.id),
        severity="warning",
        message=f"Device credential created: {credential.name}",
        metadata={
            "device_id": str(payload.device_id) if payload.device_id else None,
            "token_preview": preview,
        },
    )

    db.commit()
    db.refresh(credential)

    return DeviceCredentialCreateResponse(
        id=credential.id,
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
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
) -> list[DeviceCredential]:
    safe_limit = min(max(limit, 1), 500)

    statement = (
        select(DeviceCredential)
        .order_by(DeviceCredential.created_at.desc())
        .limit(safe_limit)
    )

    return list(db.scalars(statement))


@router.patch("/{credential_id}/revoke", response_model=DeviceCredentialResponse)
def revoke_device_credential(
    credential_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
) -> DeviceCredential:
    credential = db.get(DeviceCredential, credential_id)

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device credential not found.",
        )

    credential.is_active = False
    credential.revoked_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
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