import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_REVIEW_STATUS_PATTERN = "^(true_positive|false_positive|expected_change|insufficient_context)$"


class PipelineRunRequest(BaseModel):
    device_id: uuid.UUID | None = None


class DeviceRunResultResponse(BaseModel):
    device_id: uuid.UUID
    device_class: str | None
    windows_built: int
    windows_scored: int
    predictions_created: int
    errors: list[str]
    skipped_reason: str | None


class PipelineRunResponse(BaseModel):
    devices_processed: int
    windows_built: int
    windows_scored: int
    predictions_created: int
    device_results: list[DeviceRunResultResponse]


class AnomalyPredictionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    device_id: uuid.UUID
    feature_window_id: uuid.UUID
    model_name: str
    model_version: str
    feature_schema_version: str
    anomaly_score: float
    threshold: float
    is_anomalous: bool
    confidence: str
    feature_comparison: dict[str, Any]
    explanation: str
    shadow_mode: bool
    review_status: str
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnomalyPredictionReviewRequest(BaseModel):
    review_status: str = Field(..., pattern=_REVIEW_STATUS_PATTERN)
    review_note: str | None = Field(default=None, max_length=2000)


class AnomalyModelResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    device_class: str
    feature_schema_version: str
    algorithm: str
    hyperparameters: dict[str, Any]
    dataset_hash: str
    code_commit: str | None
    trained_at: datetime
    artifact_path: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
