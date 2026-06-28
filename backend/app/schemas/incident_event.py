import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class IncidentEventCreateRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1)
    actor_type: Literal["system", "agent", "user"] = "user"
    actor_id: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] | None = None


class IncidentEventResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    event_type: str
    message: str
    actor_type: str
    actor_id: str | None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_json")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)