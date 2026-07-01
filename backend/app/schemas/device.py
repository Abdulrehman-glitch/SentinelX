import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceRegisterRequest(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    ip_address: str | None = Field(default=None, max_length=100)
    os_name: str | None = Field(default=None, max_length=255)
    organization_slug: str | None = Field(default=None, max_length=100)
    device_type: str = Field(default="desktop", max_length=50)
    agent_type: str = Field(default="python_desktop_agent", max_length=100)
    agent_version: str | None = Field(default=None, max_length=50)


class DeviceResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    hostname: str
    display_name: str | None
    ip_address: str | None
    os_name: str | None
    device_type: str
    agent_type: str
    agent_version: str | None
    status: str
    last_seen_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
