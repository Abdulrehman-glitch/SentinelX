import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceRegisterRequest(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=255)
    ip_address: str | None = Field(default=None, max_length=100)
    os_name: str | None = Field(default=None, max_length=255)


class DeviceResponse(BaseModel):
    id: uuid.UUID
    hostname: str
    ip_address: str | None
    os_name: str | None
    status: str
    last_seen_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)