"""
Governs AnomalyModel lifecycle transitions: candidate -> shadow -> advisory
-> alert_eligible, plus retirement from any non-retired state. Every
promotion beyond "shadow" must reference a passing ModelEvaluationReport
for that model; candidate -> shadow has no prediction history to evaluate
yet, so it only enforces the always-applicable structural gates (schema
match, artifact checksum). Never invoked automatically — a human always
calls this, and every call is audit-logged.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ml import model_loader
from app.ml.feature_schemas import FEATURE_SCHEMA_VERSION
from app.models.anomaly_model import AnomalyModel
from app.models.model_evaluation_report import ModelEvaluationReport
from app.services.audit_log_service import create_audit_log

LIFECYCLE_ORDER = ["candidate", "shadow", "advisory", "alert_eligible", "retired"]
RETIRED = "retired"

MIN_REVIEWED_PREDICTIONS = 20
MAX_FALSE_POSITIVE_RATE = 0.3


class PromotionError(Exception):
    """Raised when a promotion/retirement request is invalid or blocked by a gate."""


def _structural_gate_failures(model: AnomalyModel) -> list[str]:
    failures: list[str] = []

    if model.feature_schema_version != FEATURE_SCHEMA_VERSION:
        failures.append(
            f"Feature schema mismatch: model is '{model.feature_schema_version}', current is '{FEATURE_SCHEMA_VERSION}'."
        )

    if model.artifact_path:
        try:
            actual_checksum = model_loader.compute_artifact_checksum(model.artifact_path)
        except OSError:
            failures.append("Model artifact file could not be read.")
        else:
            if model.artifact_checksum and actual_checksum != model.artifact_checksum:
                failures.append("Model artifact checksum mismatch (file changed since registration).")

    return failures


def _evaluation_gate_failures(evaluation: ModelEvaluationReport) -> list[str]:
    failures: list[str] = []

    if evaluation.reviewed_count < MIN_REVIEWED_PREDICTIONS:
        failures.append(
            f"Insufficient reviewed predictions: {evaluation.reviewed_count} < {MIN_REVIEWED_PREDICTIONS}."
        )

    if evaluation.false_positive_rate is not None and evaluation.false_positive_rate > MAX_FALSE_POSITIVE_RATE:
        failures.append(
            f"False-positive rate too high: {evaluation.false_positive_rate:.2f} > {MAX_FALSE_POSITIVE_RATE}."
        )

    return failures


def promote(
    db: Session,
    model: AnomalyModel,
    *,
    target_status: str,
    actor_id: str,
    evaluation: ModelEvaluationReport | None = None,
) -> AnomalyModel:
    if target_status == RETIRED:
        raise PromotionError("Use retire() to retire a model.")
    if target_status not in LIFECYCLE_ORDER:
        raise PromotionError(f"Unknown lifecycle status '{target_status}'.")
    if model.lifecycle_status == RETIRED:
        raise PromotionError("Cannot promote a retired model.")

    current_index = LIFECYCLE_ORDER.index(model.lifecycle_status)
    target_index = LIFECYCLE_ORDER.index(target_status)
    if target_index != current_index + 1:
        raise PromotionError(
            f"Cannot promote from '{model.lifecycle_status}' directly to '{target_status}'; "
            "promotion must move exactly one stage forward."
        )

    failures = _structural_gate_failures(model)

    # candidate -> shadow has no prediction history yet to evaluate; every
    # later stage requires a passing evaluation tied to this exact model.
    if target_status != "shadow":
        if evaluation is None:
            raise PromotionError(f"Promotion to '{target_status}' requires a linked evaluation report.")
        if evaluation.model_id != model.id:
            raise PromotionError("Evaluation report does not belong to this model.")
        failures += _evaluation_gate_failures(evaluation)

    if failures:
        raise PromotionError("Promotion blocked: " + "; ".join(failures))

    if model.artifact_path and not model.artifact_checksum:
        # First promotion past candidate backfills the checksum baseline.
        model.artifact_checksum = model_loader.compute_artifact_checksum(model.artifact_path)

    previous_status = model.lifecycle_status
    model.lifecycle_status = target_status
    model.promoted_by = uuid.UUID(actor_id)
    model.promoted_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        organization_id=None,
        actor_type="user",
        actor_id=actor_id,
        action="model_promoted",
        target_type="anomaly_model",
        target_id=str(model.id),
        message=f"Model {model.name}:{model.version} promoted {previous_status} -> {target_status}.",
        metadata={
            "evaluation_report_id": str(evaluation.id) if evaluation else None,
            "previous_status": previous_status,
        },
    )
    return model


def retire(db: Session, model: AnomalyModel, *, actor_id: str, reason: str) -> AnomalyModel:
    if model.lifecycle_status == RETIRED:
        raise PromotionError("Model is already retired.")

    previous_status = model.lifecycle_status
    model.lifecycle_status = RETIRED
    model.promoted_by = uuid.UUID(actor_id)
    model.promoted_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        organization_id=None,
        actor_type="user",
        actor_id=actor_id,
        action="model_retired",
        target_type="anomaly_model",
        target_id=str(model.id),
        message=f"Model {model.name}:{model.version} retired from '{previous_status}': {reason}",
    )
    return model
