import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MetricCreateRequest(BaseModel):
    device_id: uuid.UUID
    # Client-generated UUID for idempotent ingestion; retries with the same
    # event_id are acknowledged but not stored twice.
    event_id: uuid.UUID | None = None
    # None means "could not be read" — never report unknown CPU as 0%.
    cpu_percent: float | None = Field(None, ge=0, le=100)
    memory_percent: float = Field(..., ge=0, le=100)
    disk_percent: float = Field(..., ge=0, le=100)
    battery_percent: float | None = Field(None, ge=0, le=100)
    battery_charging: bool | None = None
    battery_temperature_c: float | None = Field(None, ge=-40, le=120)
    thermal_status: str | None = Field(None, max_length=32)
    network_transport: str | None = Field(None, max_length=32)
    network_validated: bool | None = None
    network_metered: bool | None = None
    latency_ms: float | None = Field(None, ge=0)


class MetricSample(BaseModel):
    event_id: uuid.UUID | None = None
    cpu_percent: float | None = Field(None, ge=0, le=100)
    memory_percent: float = Field(..., ge=0, le=100)
    disk_percent: float = Field(..., ge=0, le=100)
    battery_percent: float | None = Field(None, ge=0, le=100)
    battery_charging: bool | None = None
    battery_temperature_c: float | None = Field(None, ge=-40, le=120)
    thermal_status: str | None = Field(None, max_length=32)
    network_transport: str | None = Field(None, max_length=32)
    network_validated: bool | None = None
    network_metered: bool | None = None
    latency_ms: float | None = Field(None, ge=0)
    # Client capture time; lets an offline queue flush preserve real history.
    recorded_at: datetime | None = None


class MetricBatchRequest(BaseModel):
    device_id: uuid.UUID
    samples: list[MetricSample] = Field(..., min_length=1, max_length=500)


class MetricResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    device_id: uuid.UUID
    event_id: uuid.UUID | None = None
    cpu_percent: float | None = None
    memory_percent: float
    disk_percent: float
    battery_percent: float | None = None
    battery_charging: bool | None = None
    battery_temperature_c: float | None = None
    thermal_status: str | None = None
    network_transport: str | None = None
    network_validated: bool | None = None
    network_metered: bool | None = None
    latency_ms: float | None = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MetricIngestResponse(BaseModel):
    metric: MetricResponse
    alerts_created: int
    duplicate: bool = False


class MetricBatchIngestResponse(BaseModel):
    stored: int
    duplicates: int = 0
    alerts_created: int
    latest: MetricResponse | None
