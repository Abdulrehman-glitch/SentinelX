"""
Advisory AI recommendations (Sprint 4-6, Stage 5 spec section 5). Given a
HybridDecision, deterministically recommends at most one of a narrow,
hardcoded allowlist of low-risk action types — never anything else. The
recommendation is only ever a suggestion of *which* action_type to try;
every recommendation is submitted through the exact same
recovery_command_service.create_command() call path used for manual and
from-anomaly proposals, so it always passes through the deterministic
policy engine, capability validation, cooldown/circuit-breaker checks, and
signed command lifecycle unchanged. This module never:
  - executes a command directly,
  - approves a command,
  - changes risk_level or command state,
  - generates parameters or shell/PowerShell content,
  - bypasses any existing check.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.hybrid_decision import HybridDecision
from app.models.recovery_command import RecoveryCommand
from app.services import recovery_command_service
from app.services.recovery_command_service import RecoveryCommandError

# Initially permitted AI recommendations (spec section 5) — deliberately far
# narrower than the full recovery_policies allowlist (12 action types).
ALLOWED_AI_ACTIONS = {"collect_diagnostics", "retry_telemetry_sync"}

_CONFIDENCE_BUCKET_TO_FLOAT = {"low": 0.33, "medium": 0.66, "high": 0.9}


class AIRecommendationError(Exception):
    """Raised if a recommendation would fall outside the allowlist — should never happen, defensive only."""


def recommend_action(decision: HybridDecision) -> str | None:
    """
    Deterministic, explainable mapping from detected conditions to at most
    one allowlisted action. Returns None when there's nothing actionable to
    recommend (normal conditions, or conditions the allowlist can't address).
    """
    if decision.detector_agreement in ("all_normal", "detector_conflict"):
        return None

    if decision.detector_agreement == "insufficient_data":
        # Not enough/low-quality telemetry to judge anything else — the one
        # thing worth trying is getting fresher data.
        return "retry_telemetry_sync"

    if decision.combined_severity == "info":
        return None

    # Any other detected condition (warning/critical) — gather diagnostics
    # first; this is the safest, least-invasive default and matches what a
    # human would do before picking a more specific remediation.
    return "collect_diagnostics"


def propose_from_hybrid_decision(
    db: Session,
    decision: HybridDecision,
    *,
    actor_id: str | None = None,
) -> RecoveryCommand | None:
    """Returns the created RecoveryCommand, or None if nothing was recommended."""
    action_type = recommend_action(decision)
    if action_type is None:
        return None

    if action_type not in ALLOWED_AI_ACTIONS:
        # Defensive — recommend_action() is the only caller of create_command
        # here and is hardcoded to the allowlist above, so this should be
        # unreachable in practice.
        raise AIRecommendationError(f"AI attempted to recommend a non-allowlisted action '{action_type}'.")

    try:
        command = recovery_command_service.create_command(
            db,
            organization_id=decision.organization_id,
            device_id=decision.device_id,
            action_type=action_type,
            parameters={},
            reason=decision.explanation,
            decision_source="ai_proposal",
            actor_type="system",
            actor_id=actor_id,
            confidence=_CONFIDENCE_BUCKET_TO_FLOAT.get(decision.confidence),
        )
    except RecoveryCommandError:
        # Policy engine rejected it (cooldown, daily limit, circuit breaker,
        # active-command lock, disabled policy) — that's a normal, expected
        # outcome, not a bug; nothing to propagate beyond "no command created".
        return None

    decision.recovery_command_id = command.id
    return command
