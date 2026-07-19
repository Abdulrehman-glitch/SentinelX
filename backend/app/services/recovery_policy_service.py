"""
Deterministic policy evaluation for recovery commands. The policy engine —
never the AI model, never the client — decides whether a command may be
created/approved and what approval_mode it gets. See
scripts/seed_recovery_policies.py for the default global policy set.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.recovery_command import RecoveryCommand
from app.models.recovery_policy import RecoveryPolicy

# Commands still "in flight" — used for active-command locking.
_ACTIVE_STATUSES = {
    "proposed", "awaiting_approval", "approved", "dispatched",
    "acknowledged", "running", "succeeded", "verifying",
}

# Every status that represents a command that actually got approved and
# entered the pipeline — used for cooldown/daily-limit/circuit-breaker
# counting. Rejected-before-approval proposals don't count against limits.
_EXECUTED_STATUSES = _ACTIVE_STATUSES | {
    "failed", "expired", "verified", "ineffective", "inconclusive", "rolled_back",
}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    approval_mode: str  # "auto" | "manual" | "disabled"
    policy_id: uuid.UUID | None
    reason: str


def _get_policy(db: Session, organization_id: uuid.UUID | None, action_type: str) -> RecoveryPolicy | None:
    if organization_id is not None:
        org_policy = db.scalar(
            select(RecoveryPolicy).where(
                RecoveryPolicy.organization_id == organization_id,
                RecoveryPolicy.action_type == action_type,
            )
        )
        if org_policy is not None:
            return org_policy

    return db.scalar(
        select(RecoveryPolicy).where(
            RecoveryPolicy.organization_id.is_(None),
            RecoveryPolicy.action_type == action_type,
        )
    )


def evaluate(
    db: Session,
    *,
    organization_id: uuid.UUID | None,
    device_id: uuid.UUID,
    action_type: str,
) -> PolicyDecision:
    """
    Checks, in order: policy exists + enabled, active-command locking,
    cooldown, daily execution limit, circuit breaker (3 consecutive
    failures). Returns a PolicyDecision the caller uses to pick the
    command's next status (awaiting_approval / approved / rejected).
    """

    policy = _get_policy(db, organization_id, action_type)

    if policy is None:
        return PolicyDecision(False, "disabled", None, f"No recovery policy configured for '{action_type}'.")

    if not policy.enabled or policy.approval_mode == "disabled":
        return PolicyDecision(False, "disabled", policy.id, f"'{action_type}' is disabled by policy.")

    active_count = db.scalar(
        select(func.count()).select_from(RecoveryCommand).where(
            RecoveryCommand.device_id == device_id,
            RecoveryCommand.action_type == action_type,
            RecoveryCommand.status.in_(_ACTIVE_STATUSES),
        )
    )
    if active_count:
        return PolicyDecision(
            False, policy.approval_mode, policy.id, "Another command for this action is already active."
        )

    now = datetime.now(timezone.utc)

    last_executed_at = db.scalar(
        select(func.max(RecoveryCommand.created_at)).where(
            RecoveryCommand.device_id == device_id,
            RecoveryCommand.action_type == action_type,
            RecoveryCommand.status.in_(_EXECUTED_STATUSES),
        )
    )
    if last_executed_at is not None:
        elapsed = (now - last_executed_at).total_seconds()
        if elapsed < policy.cooldown_seconds:
            return PolicyDecision(
                False, policy.approval_mode, policy.id,
                f"Cooldown active ({int(policy.cooldown_seconds - elapsed)}s remaining).",
            )

    day_start = now - timedelta(hours=24)
    executed_today = db.scalar(
        select(func.count()).select_from(RecoveryCommand).where(
            RecoveryCommand.device_id == device_id,
            RecoveryCommand.action_type == action_type,
            RecoveryCommand.status.in_(_EXECUTED_STATUSES),
            RecoveryCommand.created_at >= day_start,
        )
    )
    if executed_today and executed_today >= policy.daily_execution_limit:
        return PolicyDecision(False, policy.approval_mode, policy.id, "Daily execution limit reached for this action.")

    recent_statuses = db.scalars(
        select(RecoveryCommand.status)
        .where(
            RecoveryCommand.device_id == device_id,
            RecoveryCommand.action_type == action_type,
            RecoveryCommand.status.in_(_EXECUTED_STATUSES),
        )
        .order_by(RecoveryCommand.created_at.desc())
        .limit(3)
    ).all()
    if len(recent_statuses) == 3 and all(status == "failed" for status in recent_statuses):
        return PolicyDecision(
            False, "manual", policy.id,
            "Circuit breaker open: 3 consecutive failures for this action. Manual approval required.",
        )

    return PolicyDecision(True, policy.approval_mode, policy.id, "Policy allows this command.")
