import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_REVIEW_STATUS_PATTERN = "^(true_positive|false_positive|expected_change|insufficient_context|duplicate)$"


class HybridRunRequest(BaseModel):
    device_id: uuid.UUID | None = None


class DeviceHybridRunResultResponse(BaseModel):
    device_id: uuid.UUID
    device_class: str | None
    windows_built: int
    windows_scored: int
    decisions_created: int
    errors: list[str]
    skipped_reason: str | None


class HybridRunResponse(BaseModel):
    devices_processed: int
    windows_built: int
    windows_scored: int
    decisions_created: int
    device_results: list[DeviceHybridRunResultResponse]


class HybridDecisionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    device_id: uuid.UUID
    feature_window_id: uuid.UUID

    rule_result: dict[str, Any]
    baseline_score: float | None
    model_prediction: float | None
    model_name: str | None
    model_version: str | None

    detector_agreement: str
    combined_severity: str
    operational_risk: str
    confidence: str

    affected_features: list[str]
    explanation: str
    scoring_policy_version: str

    alert_id: uuid.UUID | None
    incident_id: uuid.UUID | None
    recovery_command_id: uuid.UUID | None

    review_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_note: str | None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HybridDecisionReviewRequest(BaseModel):
    review_status: str = Field(..., pattern=_REVIEW_STATUS_PATTERN)
    review_note: str | None = Field(default=None, max_length=2000)
