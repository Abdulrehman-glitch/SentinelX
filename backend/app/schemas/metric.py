import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MetricCreateRequest(BaseModel):
    device_id: uuid.UUID
    cpu_percent: float = Field(..., ge=0, le=100)
    memory_percent: float = Field(..., ge=0, le=100)
    disk_percent: float = Field(..., ge=0, le=100)


class MetricResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    device_id: uuid.UUID
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MetricIngestResponse(BaseModel):
    metric: MetricResponse
    alerts_created: int
