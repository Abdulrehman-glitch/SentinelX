import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecoveryActionCreateRequest(BaseModel):
    device_id: uuid.UUID
    action_type: str = Field(..., min_length=1, max_length=100)
    status: str = Field(default="logged", max_length=50)
    details: str | None = None


class RecoveryActionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    device_id: uuid.UUID
    action_type: str
    status: str
    details: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
