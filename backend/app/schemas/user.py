import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


UserRole = Literal["platform_admin", "owner", "admin", "engineer", "operator", "viewer"]


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    organization_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime | None
    last_login_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class UserPublicResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    organization_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class UserRoleUpdateRequest(BaseModel):
    role: UserRole


class UserCreateRequest(BaseModel):
    """Admin-initiated creation of a user inside the admin's organization.

    platform_admin may target another organization via organization_slug
    (e.g. to bootstrap the first admin of a newly created org).
    """

    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["owner", "admin", "engineer", "operator", "viewer"] = "viewer"
    organization_slug: str | None = None
