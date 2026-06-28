import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.incident_event import IncidentEventResponse


IncidentSeverity = Literal["info", "warning", "critical"]
IncidentStatus = Literal["open", "investigating", "resolved"]
IncidentSource = Literal["manual", "alert", "system"]


class IncidentCreateRequest(BaseModel):
    device_id: uuid.UUID | None = None
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    severity: IncidentSeverity = "warning"
    source: IncidentSource = "manual"
    linked_alert_id: uuid.UUID | None = None
    assigned_to: str | None = Field(default=None, max_length=255)


class IncidentStatusUpdateRequest(BaseModel):
    status: IncidentStatus


class IncidentResponse(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID | None
    title: str
    description: str | None
    severity: str
    status: str
    source: str
    linked_alert_id: uuid.UUID | None
    assigned_to: str | None
    created_at: datetime
    updated_at: datetime | None
    resolved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class IncidentDetailResponse(IncidentResponse):
    events: list[IncidentEventResponse] = []