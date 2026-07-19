"""
Orchestrates the RecoveryCommand lifecycle: creation (manual or AI-proposed),
human approval/rejection/cancellation/retry, and the agent-facing
next/acknowledge/start/complete/reject flow (signing, expiry, capability
gating, post-action verification). The state machine
(recovery_command_state_machine.py) owns transition legality; this module
owns the business rules around *when* to request which transition.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import sign_command_payload
from app.models.device import Device
from app.models.recovery_command import RecoveryCommand
from app.models.recovery_policy import RecoveryPolicy
from app.services import agent_capability_service, recovery_policy_service, recovery_verification_service
from app.services.audit_log_service import create_audit_log
from app.services.recovery_command_state_machine import (
    TERMINAL_STATUSES,
    IllegalTransitionError,
    transition,
)


class RecoveryCommandError(Exception):
    """Raised for business-rule violations that aren't illegal state transitions."""


def build_canonical_payload(command: RecoveryCommand) -> str:
    """
    Fixed-order, newline-delimited canonical string — exactly reproducible by
    the desktop (Python) and Android (Kotlin) verifiers without relying on
    cross-language canonical-JSON agreement. Only parameters_json itself is
    JSON-canonicalized (sorted keys, no whitespace).
    """

    canonical_params = json.dumps(command.parameters_json or {}, sort_keys=True, separators=(",", ":"))
    # Always normalize to UTC before serializing: the same instant round-trips
    # through Postgres with the session's local TimeZone offset (e.g. BST,
    # +01:00) rather than +00:00, which would otherwise silently change the
    # canonical string (and therefore break signature verification) purely
    # because the value was re-fetched from the database.
    expires_at_iso = command.expires_at.astimezone(timezone.utc).isoformat() if command.expires_at else ""
    return "\n".join(
        [
            str(command.id),
            str(command.device_id),
            command.action_type,
            canonical_params,
            command.command_nonce or "",
            expires_at_iso,
            expires_at_iso,
            str(command.policy_id) if command.policy_id else "",
        ]
    )


def create_command(
    db: Session,
    *,
    organization_id: uuid.UUID | None,
    device_id: uuid.UUID,
    action_type: str,
    parameters: dict,
    reason: str | None,
    decision_source: str,
    actor_type: str,
    actor_id: str | None,
    confidence: float | None = None,
    incident_id: uuid.UUID | None = None,
    alert_id: uuid.UUID | None = None,
    anomaly_prediction_id: uuid.UUID | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
) -> RecoveryCommand:
    """
    Creates a proposed command and immediately evaluates it through the
    deterministic policy engine — the exact same call path regardless of
    decision_source, so an AI proposal can never bypass policy. risk_level
    and policy_id always come from the matched policy row, never from the
    caller, so a client cannot forge a lower risk level.
    """

    decision = recovery_policy_service.evaluate(
        db, organization_id=organization_id, device_id=device_id, action_type=action_type
    )

    if decision.policy_id is None:
        raise RecoveryCommandError(f"No recovery policy configured for action '{action_type}'.")

    policy = db.get(RecoveryPolicy, decision.policy_id)
    risk_level = policy.risk_level if policy is not None else "medium"

    command = RecoveryCommand(
        id=uuid.uuid4(),
        organization_id=organization_id,
        device_id=device_id,
        incident_id=incident_id,
        alert_id=alert_id,
        anomaly_prediction_id=anomaly_prediction_id,
        action_type=action_type,
        parameters_json=parameters or {},
        risk_level=risk_level,
        reason=reason,
        decision_source=decision_source,
        confidence=confidence,
        status="proposed",
        approval_mode=decision.approval_mode,
        policy_id=decision.policy_id,
        model_name=model_name,
        model_version=model_version,
    )
    db.add(command)

    # proposed -> {rejected | approved | awaiting_approval}, decided purely by
    # the policy engine's output, independent of who/what proposed it.
    if not decision.allowed:
        transition(db, command, "rejected", actor_type="policy", message=decision.reason)
    elif decision.approval_mode == "auto":
        transition(db, command, "approved", actor_type="policy", message="Auto-approved by policy.")
    else:
        transition(db, command, "awaiting_approval", actor_type="policy", message="Awaiting human approval per policy.")

    create_audit_log(
        db,
        organization_id=organization_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action="recovery_command_created",
        target_type="recovery_command",
        target_id=str(command.id),
        message=f"Recovery command '{action_type}' proposed for device {device_id} (status={command.status}).",
        metadata={"decision_source": decision_source, "policy_reason": decision.reason},
    )

    return command


def approve_command(db: Session, command: RecoveryCommand, *, actor_id: str) -> RecoveryCommand:
    try:
        transition(db, command, "approved", actor_type="user", actor_id=actor_id, message="Approved by operator.")
    except IllegalTransitionError as exc:
        raise RecoveryCommandError(str(exc)) from exc

    command.approved_by = uuid.UUID(actor_id)

    create_audit_log(
        db,
        organization_id=command.organization_id,
        actor_type="user",
        actor_id=actor_id,
        action="recovery_command_approved",
        target_type="recovery_command",
        target_id=str(command.id),
        message=f"Recovery command {command.id} approved.",
    )
    return command


def reject_command(
    db: Session, command: RecoveryCommand, *, actor_type: str, actor_id: str | None, reason: str
) -> RecoveryCommand:
    try:
        transition(db, command, "rejected", actor_type=actor_type, actor_id=actor_id, message=reason)
    except IllegalTransitionError as exc:
        raise RecoveryCommandError(str(exc)) from exc

    create_audit_log(
        db,
        organization_id=command.organization_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action="recovery_command_rejected",
        target_type="recovery_command",
        target_id=str(command.id),
        message=f"Recovery command {command.id} rejected: {reason}",
    )
    return command


def cancel_command(db: Session, command: RecoveryCommand, *, actor_id: str) -> RecoveryCommand:
    """
    Cancel is a user-facing alias for rejection. Only legal from states that
    can transition to 'rejected' (proposed/awaiting_approval/approved/
    running) — once a command has been dispatched to a device it cannot be
    recalled; it will expire via TTL or be rejected by the agent itself.
    """
    return reject_command(db, command, actor_type="user", actor_id=actor_id, reason="Cancelled by operator.")


def retry_command(db: Session, original: RecoveryCommand, *, actor_id: str) -> RecoveryCommand:
    """
    Creates a brand-new command cloned from a terminal one, rather than
    resurrecting it — preserves immutable event history on the original.
    """

    if original.status not in TERMINAL_STATUSES:
        raise RecoveryCommandError(f"Cannot retry a command in non-terminal status '{original.status}'.")

    new_command = create_command(
        db,
        organization_id=original.organization_id,
        device_id=original.device_id,
        action_type=original.action_type,
        parameters=original.parameters_json,
        reason=f"Retry of command {original.id}. Original reason: {original.reason or 'n/a'}",
        decision_source=original.decision_source,
        actor_type="user",
        actor_id=actor_id,
        confidence=original.confidence,
        incident_id=original.incident_id,
        alert_id=original.alert_id,
        anomaly_prediction_id=original.anomaly_prediction_id,
        model_name=original.model_name,
        model_version=original.model_version,
    )
    return new_command


def _expire_if_needed(db: Session, command: RecoveryCommand) -> bool:
    """Lazy expiry check — called whenever an in-flight command is touched."""
    if command.status not in {"awaiting_approval", "approved", "dispatched", "acknowledged", "running"}:
        return False
    if command.expires_at is None:
        return False
    if datetime.now(timezone.utc) <= command.expires_at:
        return False

    transition(db, command, "expired", actor_type="system", message="Command expired (TTL elapsed).")
    return True


def _policy_ttl_seconds(db: Session, policy_id: uuid.UUID | None) -> int | None:
    if policy_id is None:
        return None
    policy = db.get(RecoveryPolicy, policy_id)
    return policy.verification_window_seconds if policy is not None else None


def get_next_command_for_device(db: Session, device: Device) -> RecoveryCommand | None:
    """
    Returns the single active command for this device, signing it on first
    fetch (approved -> dispatched). Idempotent on re-poll of an already
    dispatched command (same signature returned, not re-signed).
    """

    command = db.scalar(
        select(RecoveryCommand)
        .where(
            RecoveryCommand.device_id == device.id,
            RecoveryCommand.status.in_(["approved", "dispatched"]),
        )
        .order_by(RecoveryCommand.created_at.asc())
        .limit(1)
    )
    if command is None:
        return None

    if _expire_if_needed(db, command):
        return None

    if command.status == "dispatched":
        return command

    # status == "approved": refuse to dispatch an action this device hasn't
    # reported support for.
    if not agent_capability_service.device_supports(db, device_id=device.id, action_type=command.action_type):
        transition(
            db,
            command,
            "rejected",
            actor_type="system",
            message=f"Device does not report capability for action '{command.action_type}'.",
        )
        return None

    ttl_seconds = _policy_ttl_seconds(db, command.policy_id) or get_settings().recovery_command_default_ttl_seconds

    now = datetime.now(timezone.utc)
    command.command_nonce = uuid.uuid4().hex
    command.expires_at = now + timedelta(seconds=ttl_seconds)

    canonical = build_canonical_payload(command)
    command.payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    command.signature = sign_command_payload(canonical)

    transition(db, command, "dispatched", actor_type="system", message="Signed and dispatched to device.")
    return command


def acknowledge_command(db: Session, command: RecoveryCommand) -> RecoveryCommand:
    if _expire_if_needed(db, command):
        raise RecoveryCommandError("Command has expired.")
    try:
        transition(db, command, "acknowledged", actor_type="agent", message="Acknowledged by agent.")
    except IllegalTransitionError as exc:
        raise RecoveryCommandError(str(exc)) from exc
    return command


def start_command(db: Session, command: RecoveryCommand) -> RecoveryCommand:
    if _expire_if_needed(db, command):
        raise RecoveryCommandError("Command has expired.")
    try:
        transition(db, command, "running", actor_type="agent", message="Execution started.")
    except IllegalTransitionError as exc:
        raise RecoveryCommandError(str(exc)) from exc
    return command


@dataclass(frozen=True)
class CompletionInput:
    result_code: str
    result_message: str | None
    result_data: dict | None
    post_action_snapshot: dict | None


def complete_command(db: Session, command: RecoveryCommand, completion: CompletionInput) -> RecoveryCommand:
    """
    running -> succeeded|failed, then (if succeeded) immediately through
    verifying -> the action-specific verification outcome. Never leaves a
    command sitting in 'succeeded' — execution success and recovery
    verification are always resolved together server-side.
    """

    command.result_code = completion.result_code
    command.result_message = completion.result_message
    command.result_data_json = completion.result_data
    command.post_action_snapshot_json = completion.post_action_snapshot

    if completion.result_code != "success":
        try:
            transition(db, command, "failed", actor_type="agent", message=completion.result_message)
        except IllegalTransitionError as exc:
            raise RecoveryCommandError(str(exc)) from exc
        return command

    try:
        transition(db, command, "succeeded", actor_type="agent", message="Execution completed successfully.")
        transition(db, command, "verifying", actor_type="system", message="Running post-action verification.")
    except IllegalTransitionError as exc:
        raise RecoveryCommandError(str(exc)) from exc

    window_seconds = _policy_ttl_seconds(db, command.policy_id) or 300
    result = recovery_verification_service.verify(db, command, window_seconds)

    command.verification_status = result.status
    command.verification_message = result.message

    transition(db, command, result.status, actor_type="system", message=result.message)
    return command


def reject_command_by_agent(db: Session, command: RecoveryCommand, *, reason: str) -> RecoveryCommand:
    """Agent-side refusal — e.g. local allowlist/param/signature check failed."""
    try:
        transition(db, command, "rejected", actor_type="agent", message=reason)
    except IllegalTransitionError as exc:
        raise RecoveryCommandError(str(exc)) from exc
    return command
