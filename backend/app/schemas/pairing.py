import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.device import DeviceResponse


class PairingSessionCreateRequest(BaseModel):
    platform: Literal["android", "windows"] = "android"
    # The LAN address the agent should reach the backend on, chosen from
    # /pairing/hosts. A bare host or host:port — never a token.
    backend_url: str | None = Field(default=None, max_length=200)
    expires_in_minutes: int = Field(default=10, ge=1, le=60)


class PairingSessionCreateResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    platform: str
    # Shown once; only the hash is stored server-side.
    code: str
    code_preview: str
    backend_url: str
    # The exact string to render as a QR code for the Android app.
    qr_payload: str
    expires_at: datetime
    created_at: datetime


class PairingSessionStatusResponse(BaseModel):
    id: uuid.UUID
    status: Literal["waiting", "expired", "revoked", "enrolled", "telemetry_live"]
    expires_at: datetime
    enrolled_at: datetime | None = None
    device: DeviceResponse | None = None
    last_telemetry_at: datetime | None = None


class PairingHost(BaseModel):
    address: str
    url: str


class PairingHostsResponse(BaseModel):
    hosts: list[PairingHost]
    port: int
