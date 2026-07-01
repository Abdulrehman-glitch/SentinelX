import uuid
from collections.abc import Callable

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


def get_device_from_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Device:
    """
    Resolves a device from a Bearer device credential token.

    Used by agent-facing endpoints (metric ingestion, heartbeats, embedded telemetry).
    The token is verified against stored hashes. Returns the associated device.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device token required.",
        )

    raw_token = credentials.credentials

    active_creds = db.scalars(
        select(DeviceCredential).where(
            DeviceCredential.is_active.is_(True),
            DeviceCredential.device_id.isnot(None),
        )
    )

    for cred in active_creds:
        try:
            if verify_password(raw_token, cred.token_hash):
                device = db.get(Device, cred.device_id)
                if device:
                    return device
        except Exception:
            continue

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or revoked device token.",
    )
