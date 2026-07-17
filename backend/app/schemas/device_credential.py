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
    last_used_at: datetime | None = None
    revoked_at: datetime | None
    replaces_credential_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class DeviceCredentialRotateResponse(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID | None
    # Shown once; the previous token stays valid until this one is first used.
    token: str
    token_preview: str
    replaces_credential_id: uuid.UUID
