"""Managing the organisation-scoped keys that OTLP clients authenticate with.

Admin and above only. An ingest key lets anything holding it write telemetry
into a tenant, so issuing one is an administrative act, and every issue,
rotation and revocation lands in the audit log.

The plaintext appears in exactly one response, at creation. Everything after
that shows the prefix and last four characters — enough for an operator to tell
two keys apart, useless to anyone trying to guess one.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.ingest_credential import IngestCredential
from app.models.user import User
from app.schemas.ingest_credential import (
    IngestCredentialCreatedResponse,
    IngestCredentialCreateRequest,
    IngestCredentialResponse,
)
from app.services import ingest_credential_service as ics
from app.services.audit_log_service import create_audit_log

router = APIRouter(prefix="/ingest-credentials", tags=["Ingest Credentials"])

_ADMIN = ["admin", "owner", "platform_admin"]


def _organization_id(user: User) -> uuid.UUID:
    if user.organization_id is None:
        # A platform admin has no organisation of their own, so there is no
        # tenant to scope a key to. Making them pick one explicitly is a
        # separate feature; guessing would be worse.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This account is not attached to an organization, so it cannot own an "
            "ingest credential.",
        )
    return user.organization_id


def _scoped_or_404(db: Session, credential_id: uuid.UUID, user: User) -> IngestCredential:
    """Never reveal that a key exists in another tenant.

    A 403 here would confirm the id is real, so a miss and a cross-tenant hit
    are both 404.
    """
    credential = db.get(IngestCredential, credential_id)
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ingest credential not found."
        )

    if user.role != "platform_admin" and credential.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ingest credential not found."
        )

    return credential


@router.post(
    "", response_model=IngestCredentialCreatedResponse, status_code=status.HTTP_201_CREATED
)
def create_ingest_credential(
    payload: IngestCredentialCreateRequest,
    current_user: User = Depends(require_role(_ADMIN)),
    db: Session = Depends(get_db),
) -> IngestCredentialCreatedResponse:
    """Issue a key. The plaintext is in this response and nowhere else, ever."""
    organization_id = _organization_id(current_user)

    try:
        issued = ics.create_credential(
            db,
            organization_id=organization_id,
            name=payload.name,
            scopes=payload.scopes,
            created_by_user_id=current_user.id,
            expires_at=payload.expires_at,
        )
    except ics.IngestCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    create_audit_log(
        db,
        organization_id=organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="ingest_credential_created",
        target_type="ingest_credential",
        target_id=str(issued.credential.id),
        severity="warning",
        message=f"OTLP ingest credential '{issued.credential.name}' issued.",
        metadata={
            "scopes": issued.credential.scopes,
            "key_last_four": issued.credential.key_last_four,
        },
    )
    db.commit()
    db.refresh(issued.credential)

    return IngestCredentialCreatedResponse(
        credential=IngestCredentialResponse.model_validate(issued.credential),
        ingest_key=issued.plaintext,
    )


@router.get("", response_model=list[IngestCredentialResponse])
def list_ingest_credentials(
    current_user: User = Depends(require_role(_ADMIN)),
    db: Session = Depends(get_db),
) -> list[IngestCredential]:
    return ics.list_for_organization(db, _organization_id(current_user))


@router.post("/{credential_id}/rotate", response_model=IngestCredentialCreatedResponse)
def rotate_ingest_credential(
    credential_id: uuid.UUID,
    current_user: User = Depends(require_role(_ADMIN)),
    db: Session = Depends(get_db),
) -> IngestCredentialCreatedResponse:
    """Issue a replacement and retire the old key after an overlap window.

    Not the same as revoke-then-create: revoking first would break every
    collector using the key until each is reconfigured. The old key keeps
    working for 24 hours and then expires on its own.
    """
    credential = _scoped_or_404(db, credential_id, current_user)
    if credential.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This credential is revoked; issue a new one instead of rotating it.",
        )

    replacement = ics.rotate(db, credential, created_by_user_id=current_user.id)

    create_audit_log(
        db,
        organization_id=credential.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="ingest_credential_rotated",
        target_type="ingest_credential",
        target_id=str(credential.id),
        severity="warning",
        message=f"OTLP ingest credential '{credential.name}' rotated.",
        metadata={
            "replacement_id": str(replacement.credential.id),
            "old_key_expires_at": (
                credential.expires_at.isoformat() if credential.expires_at else None
            ),
        },
    )
    db.commit()
    db.refresh(replacement.credential)

    return IngestCredentialCreatedResponse(
        credential=IngestCredentialResponse.model_validate(replacement.credential),
        ingest_key=replacement.plaintext,
    )


@router.delete("/{credential_id}", response_model=IngestCredentialResponse)
def revoke_ingest_credential(
    credential_id: uuid.UUID,
    current_user: User = Depends(require_role(_ADMIN)),
    db: Session = Depends(get_db),
) -> IngestCredential:
    """Stop the key working immediately.

    The row is kept rather than deleted: `last_used_at` and the audit trail are
    how someone later works out what a leaked key actually did.
    """
    credential = _scoped_or_404(db, credential_id, current_user)
    already_revoked = credential.revoked_at is not None

    ics.revoke(credential)

    if not already_revoked:
        create_audit_log(
            db,
            organization_id=credential.organization_id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="ingest_credential_revoked",
            target_type="ingest_credential",
            target_id=str(credential.id),
            severity="warning",
            message=f"OTLP ingest credential '{credential.name}' revoked.",
            metadata={"key_last_four": credential.key_last_four},
        )

    db.commit()
    db.refresh(credential)
    return credential
