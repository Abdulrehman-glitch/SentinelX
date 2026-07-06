"""Pydantic request/response models mirroring docs/spec/03 (API contract)
and docs/spec/05 (data models). Wire format is snake_case JSON."""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Platform(str, Enum):
    ios = "ios"
    android = "android"
    macos = "macos"
    windows = "windows"
    linux = "linux"
    raspberry_pi = "raspberry_pi"


class DeviceStatus(str, Enum):
    active = "active"
    disabled = "disabled"
    pending = "pending"
    retired = "retired"


class TelemetryCategory(str, Enum):
    device = "device"
    battery = "battery"
    thermal = "thermal"
    storage = "storage"
    network = "network"
    location = "location"
    motion = "motion"
    activity = "activity"
    bluetooth = "bluetooth"
    metrickit = "metrickit"
    alert = "alert"
    diagnostic = "diagnostic"


class RegisterRequest(BaseModel):
    platform: Platform
    device_name: str = Field(min_length=1, max_length=120)
    device_model: str = Field(min_length=1, max_length=120)
    os_version: str = Field(min_length=1, max_length=60)
    app_version: str = Field(min_length=1, max_length=60)
    vendor_identifier: str = Field(min_length=1, max_length=200)
    timezone: str = Field(default="UTC", max_length=60)
    locale: str = Field(default="en_GB", max_length=20)


class RegisterResponse(BaseModel):
    device_id: str
    device_secret: str
    registered_at: str
    status: DeviceStatus


class LoginRequest(BaseModel):
    device_id: str
    device_secret: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class ProfileResponse(BaseModel):
    device_id: str
    platform: Platform
    device_name: str
    device_model: str | None
    os_version: str | None
    app_version: str | None
    status: DeviceStatus
    last_seen: str | None


class ProfileUpdateRequest(BaseModel):
    device_name: str | None = Field(default=None, min_length=1, max_length=120)
    app_version: str | None = Field(default=None, min_length=1, max_length=60)
    os_version: str | None = Field(default=None, min_length=1, max_length=60)


class ProfileUpdateResponse(BaseModel):
    success: bool
    updated_at: str


class TelemetryEvent(BaseModel):
    # Envelope per spec 03 §11 / 05 §10. Extra keys are rejected so client
    # drift surfaces as a contract failure instead of silently passing.
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    device_id: str
    timestamp: str
    category: TelemetryCategory
    type: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=120)
    sequence: int | None = None
    payload: dict[str, Any]
    metadata: dict[str, Any] | None = None


class TelemetryAccepted(BaseModel):
    accepted: bool
    event_id: UUID
    stored_at: str
    duplicate: bool = False


class BatchEvent(BaseModel):
    # Batch items omit device_id (it comes from the batch envelope).
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    timestamp: str
    category: TelemetryCategory
    type: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=120)
    sequence: int | None = None
    payload: dict[str, Any]
    metadata: dict[str, Any] | None = None


class BatchRequest(BaseModel):
    device_id: str
    batch_id: str
    sent_at: str
    events: list[BatchEvent] = Field(max_length=500)


class RejectedEvent(BaseModel):
    event_id: str
    reason: str


class BatchResponse(BaseModel):
    accepted: bool
    batch_id: str
    accepted_count: int
    rejected_count: int
    rejected_events: list[RejectedEvent]


class DeviceSummary(BaseModel):
    device_id: str
    device_name: str
    platform: Platform
    status: str
    last_seen: str | None
    battery: int | None = None
    thermal: str | None = None
    network: str | None = None
    active_alerts: int = 0


class DeviceList(BaseModel):
    items: list[DeviceSummary]


class TelemetryPage(BaseModel):
    items: list[dict[str, Any]]
    page: int
    limit: int
    total: int


class Alert(BaseModel):
    alert_id: str
    device_id: str
    severity: str
    category: str
    rule: str
    message: str
    created_at: str
    resolved: bool
    resolved_at: str | None = None


class AlertList(BaseModel):
    items: list[Alert]
