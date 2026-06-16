import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HeartbeatCreateRequest(BaseModel):
    device_id: uuid.UUID
    status: str = Field(default="online", max_length=50)
    message: str | None = Field(default=None, max_length=500)


class HeartbeatResponse(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    status: str
    message: str | None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)