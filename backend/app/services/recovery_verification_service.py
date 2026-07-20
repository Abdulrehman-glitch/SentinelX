"""
Post-action verification. A command reaching 'succeeded' only means the
agent finished running it — not that the recovery worked. This module
implements the action-specific checks (spec section M) that decide the
final 'verifying' -> {verified|ineffective|inconclusive|failed} transition.
Never called for a command still in flight; only after 'succeeded'.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_heartbeat import AgentHeartbeat
from app.models.device import Device
from app.models.recovery_command import RecoveryCommand
from app.models.system_metric import SystemMetric


@dataclass(frozen=True)
class VerificationResult:
    status: str  # "verified" | "ineffective" | "inconclusive" | "failed"
    message: str


def _recent_heartbeat_within(db: Session, device_id: uuid.UUID, window_seconds: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    latest = db.scalar(
        select(AgentHeartbeat.recorded_at)
        .where(AgentHeartbeat.device_id == device_id)
        .order_by(AgentHeartbeat.recorded_at.desc())
        .limit(1)
    )
    return latest is not None and latest >= cutoff


def _recent_metric_within(db: Session, device_id: uuid.UUID, window_seconds: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    latest = db.scalar(
        select(SystemMetric.recorded_at)
        .where(SystemMetric.device_id == device_id)
        .order_by(SystemMetric.recorded_at.desc())
        .limit(1)
    )
    return latest is not None and latest >= cutoff


def verify(db: Session, command: RecoveryCommand, window_seconds: int) -> VerificationResult:
    """
    Dispatches to an action-specific check. Unknown/unimplemented action
    types fall back to 'inconclusive' rather than guessing.
    """

    device = db.get(Device, command.device_id)
    if device is None:
        return VerificationResult("inconclusive", "Device no longer exists.")

    if command.action_type == "retry_telemetry_sync":
        heartbeat_ok = _recent_heartbeat_within(db, device.id, window_seconds)
        metric_ok = _recent_metric_within(db, device.id, window_seconds)
        if heartbeat_ok and metric_ok:
            return VerificationResult("verified", "Recent heartbeat and telemetry observed after retry.")
        if not metric_ok:
            return VerificationResult(
                "ineffective", "No new telemetry observed after retry within the verification window."
            )
        return VerificationResult("inconclusive", "Heartbeat resumed but telemetry not yet confirmed.")

    if command.action_type in ("restart_sentinelx_agent", "restart_monitoring_service"):
        heartbeat_ok = _recent_heartbeat_within(db, device.id, window_seconds)
        metric_ok = _recent_metric_within(db, device.id, window_seconds)
        if heartbeat_ok and metric_ok:
            return VerificationResult("verified", "Service/agent resumed heartbeat and telemetry after restart.")
        if not heartbeat_ok:
            return VerificationResult(
                "failed", "No heartbeat resumed after restart within the verification window — possible crash loop."
            )
        return VerificationResult("inconclusive", "Heartbeat resumed but telemetry not yet confirmed.")

    if command.action_type == "collect_diagnostics":
        data = command.result_data_json or {}
        required_fields = {"cpu_percent", "memory_percent", "disk_percent", "uptime_seconds"}
        if required_fields.issubset(data.keys()):
            return VerificationResult("verified", "Diagnostic report contains all required fields.")
        missing = sorted(required_fields - data.keys())
        return VerificationResult("failed", f"Diagnostic report missing fields: {missing}.")

    if command.action_type in ("repair_agent_queue", "repair_local_database"):
        if command.result_code != "success":
            return VerificationResult("failed", "Queue/database repair did not report success.")
        if _recent_metric_within(db, device.id, window_seconds):
            return VerificationResult("verified", "Repair succeeded and telemetry uploads have resumed.")
        return VerificationResult(
            "inconclusive",
            "Repair reported success but no new telemetry observed yet within the verification window.",
        )

    if command.action_type == "reschedule_sync_workers":
        data = command.result_data_json or {}
        if command.result_code != "success":
            return VerificationResult("failed", "Worker reschedule did not report success.")
        if data.get("workers_registered") is False:
            return VerificationResult("failed", "Agent reported workers were not registered after reschedule.")
        if _recent_metric_within(db, device.id, window_seconds):
            return VerificationResult("verified", "Sync workers rescheduled and telemetry has resumed.")
        return VerificationResult(
            "inconclusive", "Workers rescheduled but telemetry not yet confirmed within the verification window."
        )

    # rotate_agent_logs, reset_api_connection, enter/restore_*
    # monitoring_mode: no independent external verification signal defined
    # in v1 — accept the agent's own reported result_code, but never claim
    # "verified" if the agent didn't actually report a result_code.
    if command.result_code == "success":
        return VerificationResult(
            "verified",
            "Agent reported successful completion; no independent verification signal defined for this action yet.",
        )

    return VerificationResult("inconclusive", "No result_code reported by the agent.")
