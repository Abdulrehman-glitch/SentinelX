import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SecurityLogResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    severity: str
    actor_type: str
    actor_id: str | None
    ip_address: str | None
    organization_id: uuid.UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    status: str
    message: str
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_json")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
