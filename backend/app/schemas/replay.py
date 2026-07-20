import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReplayRunRequest(BaseModel):
    device_class: str = Field(..., max_length=50)
    period_start: datetime
    period_end: datetime
    model_version: str | None = Field(default=None, max_length=50)
    export_format: str | None = Field(default=None, pattern="^(json|markdown)$")


class ReplayDecisionResponse(BaseModel):
    feature_window_id: uuid.UUID
    device_id: uuid.UUID
    window_start: str
    window_end: str
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

    model_config = ConfigDict(from_attributes=True)


class ReplayRunResponse(BaseModel):
    replay_run_id: uuid.UUID
    device_class: str
    scoring_policy_version: str
    model_version: str | None
    period_start: datetime
    period_end: datetime
    windows_considered: int
    decisions: list[ReplayDecisionResponse]
    skipped: list[str]
    export: str | None
