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
