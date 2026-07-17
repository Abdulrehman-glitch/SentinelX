import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.device import DeviceResponse


class EnrollmentCodeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    expires_in_minutes: int = Field(default=15, ge=1, le=10080)
    # platform_admin only — tenant admins always mint for their own org.
    organization_id: uuid.UUID | None = None


class EnrollmentCodeCreateResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    # Shown once; only the hash is stored.
    code: str
    code_preview: str
    expires_at: datetime
    created_at: datetime


class EnrollmentCodeResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code_preview: str
    expires_at: datetime
    used_at: datetime | None
    used_by_device_id: uuid.UUID | None
    revoked_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceEnrollRequest(BaseModel):
    enrollment_code: str = Field(..., min_length=8, max_length=255)
    hostname: str = Field(..., min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=100)
    os_name: str | None = Field(default=None, max_length=255)
    device_type: str = Field(default="desktop", max_length=50)
    agent_type: str = Field(default="python_desktop_agent", max_length=100)
    agent_version: str | None = Field(default=None, max_length=50)


class DeviceEnrollResponse(BaseModel):
    device: DeviceResponse
    credential_id: uuid.UUID
    # Shown once; store it securely on the agent.
    device_token: str
