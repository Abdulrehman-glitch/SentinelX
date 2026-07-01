import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceCredentialCreateRequest(BaseModel):
    device_id: uuid.UUID | None = None
    name: str = Field(..., min_length=1, max_length=255)


class DeviceCredentialCreateResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    device_id: uuid.UUID | None
    name: str
    token: str
    token_preview: str
    is_active: bool
    created_at: datetime


class DeviceCredentialResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    device_id: uuid.UUID | None
    name: str
    token_preview: str
    is_active: bool
    created_at: datetime
    revoked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
