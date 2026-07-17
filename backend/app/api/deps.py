import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token, verify_password
from app.db.session import get_db
from app.models.device import Device
from app.models.device_credential import DeviceCredential
from app.models.user import User

# v2 device tokens embed the credential id for O(1) lookup: sxa_<32hex>.<secret>
_V2_DEVICE_TOKEN = re.compile(r"^sxa_([0-9a-f]{32})\.[A-Za-z0-9_\-]+$")


ROLE_HIERARCHY = {
    "platform_admin": 100,
    "owner": 80,
    "admin": 60,
    "engineer": 40,
    "operator": 30,
    "viewer": 10,
}

bearer_scheme = HTTPBearer(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is required.",
        )

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
            )

        user_uuid = uuid.UUID(str(user_id))

    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from exc

    user = db.get(User, user_uuid)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return user


def require_role(allowed_roles: list[str]) -> Callable:
    """
    Dependency factory that gates endpoints by role.

    Platform admins bypass all role checks — they can access everything.
    """

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == "platform_admin":
            return current_user

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker


def require_min_role(min_role: str) -> Callable:
    """
    Dependency factory that gates endpoints by minimum role level.
    """

    min_level = ROLE_HIERARCHY.get(min_role, 0)

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(current_user.role, 0)

        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have sufficient permissions for this action.",
            )

        return current_user

    return role_checker


def get_org_scoped_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Returns the current user and validates they belong to an organization.
    Platform admins pass through without an org requirement.
    """
    if current_user.role != "platform_admin" and current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with any organization.",
        )
    return current_user


@dataclass(frozen=True)
class DeviceAuthContext:
    device: Device
    credential: DeviceCredential


def _resolve_device_credential(raw_token: str, db: Session) -> DeviceCredential | None:
    """Match a raw Bearer token to an active credential.

    v2 tokens carry their credential id so the lookup is a single fetch plus
    one hash verification. Legacy opaque tokens fall back to scanning active
    credentials (kept only until existing agents rotate).
    """
    match = _V2_DEVICE_TOKEN.match(raw_token)
    if match:
        cred = db.get(DeviceCredential, uuid.UUID(hex=match.group(1)))
        if (
            cred is not None
            and cred.is_active
            and cred.device_id is not None
            and verify_password(raw_token, cred.token_hash)
        ):
            return cred
        return None

    active_creds = db.scalars(
        select(DeviceCredential).where(
            DeviceCredential.is_active.is_(True),
            DeviceCredential.device_id.isnot(None),
        )
    )
    for cred in active_creds:
        try:
            if verify_password(raw_token, cred.token_hash):
                return cred
        except Exception:
            continue
    return None


def get_device_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> DeviceAuthContext:
    """
    Resolves the device AND credential from a Bearer device token.

    Used by agent-facing endpoints (metric ingestion, heartbeats, embedded
    telemetry, credential rotation). Stamps last_used_at, and completes a
    pending rotation: the first successful use of a rotated token revokes the
    credential it replaced. The stamp/revocation persist on the route's commit.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device token required.",
        )

    cred = _resolve_device_credential(credentials.credentials, db)
    device = db.get(Device, cred.device_id) if cred is not None else None

    if cred is None or device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked device token.",
        )

    now = datetime.now(timezone.utc)

    if cred.replaces_credential_id is not None and cred.last_used_at is None:
        replaced = db.get(DeviceCredential, cred.replaces_credential_id)
        if replaced is not None and replaced.is_active:
            replaced.is_active = False
            replaced.revoked_at = now

    cred.last_used_at = now

    return DeviceAuthContext(device=device, credential=cred)


def get_device_from_token(
    auth: DeviceAuthContext = Depends(get_device_auth),
) -> Device:
    """Back-compat dependency for routes that only need the device."""
    return auth.device
