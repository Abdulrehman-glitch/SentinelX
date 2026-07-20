"""
Centralized inference guard shared by every model that scores a
TelemetryFeatureWindow (IsolationForest today; future predictive models in
Stage 5). A failed check means "skip inference for this window" — this
module never raises, matching the rest of the AI pipeline's fail-closed-
but-quiet design (a missing/invalid model must never crash a pipeline run).
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.models.anomaly_model import AnomalyModel

RETIRED_STATUS = "retired"


@dataclass(frozen=True)
class ModelValidation:
    ok: bool
    reason: str | None


def compute_artifact_checksum(artifact_path: str) -> str:
    return hashlib.sha256(Path(artifact_path).read_bytes()).hexdigest()


def validate(model_row: AnomalyModel, *, expected_feature_schema_version: str) -> ModelValidation:
    """Reject inference when the model is retired, the feature schema has
    moved on, or the artifact on disk no longer matches its registered
    checksum (tampered or corrupted since registration)."""
    if model_row.lifecycle_status == RETIRED_STATUS:
        return ModelValidation(False, "model_retired")

    if model_row.feature_schema_version != expected_feature_schema_version:
        return ModelValidation(False, "feature_schema_mismatch")

    if model_row.artifact_checksum:
        if not model_row.artifact_path:
            return ModelValidation(False, "no_artifact_to_verify")
        try:
            actual_checksum = compute_artifact_checksum(model_row.artifact_path)
        except OSError:
            return ModelValidation(False, "artifact_unreadable")
        if actual_checksum != model_row.artifact_checksum:
            return ModelValidation(False, "artifact_checksum_mismatch")

    return ModelValidation(True, None)
