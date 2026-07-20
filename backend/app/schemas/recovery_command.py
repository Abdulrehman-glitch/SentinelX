import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RecoveryCommandCreateRequest(BaseModel):
    device_id: uuid.UUID
    action_type: str = Field(..., max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=2000)


class ProposeFromAnomalyRequest(BaseModel):
    """
    A human (engineer/admin/owner/platform_admin) selects the action to
    propose based on an AnomalyPrediction's explanation — the AI never picks
    the action_type or parameters itself. confidence/model_name/model_version
    /reason are populated server-side from the prediction, not from this body.
    """

    action_type: str = Field(..., max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)


class RejectRequest(BaseModel):
    reason: str = Field(..., max_length=2000)


class RecoveryCommandResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    device_id: uuid.UUID
    incident_id: uuid.UUID | None
    alert_id: uuid.UUID | None
    anomaly_prediction_id: uuid.UUID | None

    action_type: str
    parameters_json: dict[str, Any]
    risk_level: str
    reason: str | None
    decision_source: str
    confidence: float | None

    status: str
    approval_mode: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None

    command_nonce: str | None
    payload_hash: str | None
    signature: str | None
    expires_at: datetime | None

    created_at: datetime
    dispatched_at: datetime | None
    acknowledged_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None

    result_code: str | None
    result_message: str | None
    result_data_json: dict[str, Any] | None
    pre_action_snapshot_json: dict[str, Any] | None
    post_action_snapshot_json: dict[str, Any] | None

    verification_status: str | None
    verification_message: str | None

    model_name: str | None
    model_version: str | None
    policy_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


class RecoveryCommandEventResponse(BaseModel):
    id: uuid.UUID
    command_id: uuid.UUID
    organization_id: uuid.UUID | None
    event_type: str
    previous_status: str | None
    new_status: str | None
    actor_type: str
    actor_id: str | None
    message: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Agent-facing ──────────────────────────────────────────────────────────


class CapabilityItem(BaseModel):
    action_type: str = Field(..., max_length=100)
    action_version: str = Field(default="1", max_length=20)
    local_risk_level: str = Field(..., max_length=20)


class AgentCapabilitiesRequest(BaseModel):
    agent_type: str = Field(..., max_length=50)
    agent_version: str = Field(..., max_length=50)
    capabilities: list[CapabilityItem]


class CompleteCommandRequest(BaseModel):
    result_code: str = Field(..., max_length=50)
    result_message: str | None = Field(default=None, max_length=2000)
    result_data: dict[str, Any] | None = None
    pre_action_snapshot: dict[str, Any] | None = None
    post_action_snapshot: dict[str, Any] | None = None


class AgentRejectRequest(BaseModel):
    reason: str = Field(..., max_length=2000)


class PublicKeyResponse(BaseModel):
    public_key: str
