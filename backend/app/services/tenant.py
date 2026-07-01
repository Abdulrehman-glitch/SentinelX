"""Shared tenant and RBAC helpers for SentinelX API routes."""

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.user import User


def require_org_user(current_user: User) -> uuid.UUID | None:
    """Return current user's organization id or allow platform admin.

    Tenant users must always be attached to exactly one organization. Platform
    admins are allowed to return None because they can operate across tenants.
    """
    if current_user.role == "platform_admin":
        return None
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an organization.",
        )
    return current_user.organization_id


def is_platform_admin(current_user: User) -> bool:
    return current_user.role == "platform_admin"


def org_condition(model: Any, current_user: User):
    """Return an SQLAlchemy org filter for tenant-owned models.

    Platform admins receive None, meaning no tenant filter should be applied.
    Tenant users must be scoped to current_user.organization_id.
    """
    if is_platform_admin(current_user):
        return None
    org_id = require_org_user(current_user)
    if hasattr(model, "organization_id"):
        return model.organization_id == org_id
    return None


def assert_same_org(resource_org_id: uuid.UUID | None, current_user: User) -> None:
    """Hide cross-tenant resources as 404 to prevent ID enumeration."""
    if is_platform_admin(current_user):
        return
    org_id = require_org_user(current_user)
    if resource_org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")


def get_scoped_device_or_404(db: Session, device_id: uuid.UUID, current_user: User) -> Device:
    """Load a device while enforcing tenant isolation."""
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    assert_same_org(device.organization_id, current_user)
    return device
