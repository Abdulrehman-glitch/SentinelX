"""Allowlisted, typed recovery-command executors for the desktop agent.

Every function takes validated parameters plus an ExecutorContext and returns
an ExecutionResult. None of these accept or construct a shell command,
script, or arbitrary service name — restart_allowlisted_service only ever
acts on a logical key present in the local service_allowlist.json file.

Explicitly NOT implemented (never will be, in this file): arbitrary CMD or
PowerShell, arbitrary process termination, arbitrary file deletion, registry
modification, machine reboot, firewall changes, security-software changes.
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import psutil

if TYPE_CHECKING:
    from sentinelx_agent.client import SentinelXClient
    from sentinelx_agent.config import AgentConfig
    from sentinelx_agent.store import AgentStore


@dataclass
class ExecutionResult:
    result_code: str  # "success" | "failure"
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    post_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutorContext:
    config: "AgentConfig"
    store: "AgentStore"
    client: "SentinelXClient"
    device_id: str


# Mirrors the risk-level assignment seeded server-side by
# scripts/seed_recovery_policies.py — kept in sync manually, documented here.
ACTION_RISK_LEVELS: dict[str, str] = {
    "collect_diagnostics": "low",
    "rotate_agent_logs": "low",
    "retry_telemetry_sync": "low",
    "repair_agent_queue": "low",
    "restart_sentinelx_agent": "medium",
    "restart_allowlisted_service": "medium",
}


def _disk_usage_percent() -> float:
    anchor = Path.home().anchor or ("C:\\" if platform.system() == "Windows" else "/")
    return psutil.disk_usage(anchor).percent


def _load_service_allowlist(config: "AgentConfig") -> dict[str, str]:
    path = Path(config.service_allowlist_path)
    if not path.is_absolute():
        from sentinelx_agent.config import AGENT_DIR

        path = AGENT_DIR / path
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def collect_diagnostics(parameters: dict[str, Any], ctx: ExecutorContext) -> ExecutionResult:
    data = {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": _disk_usage_percent(),
        "uptime_seconds": int(time.time() - psutil.boot_time()),
        "platform": platform.platform(),
        "queue_depth": ctx.store.queue_depth(),
    }
    return ExecutionResult("success", "Diagnostics collected.", data=data, post_snapshot=data)


def rotate_agent_logs(parameters: dict[str, Any], ctx: ExecutorContext) -> ExecutionResult:
    from sentinelx_agent.store import default_data_dir

    log_file = default_data_dir() / "logs" / "agent.log"
    if not log_file.exists():
        return ExecutionResult("success", "No log file present to rotate.", data={"rotated": False})

    archive_name = f"agent.{time.strftime('%Y%m%d%H%M%S')}.log"
    archive_path = log_file.with_name(archive_name)
    archive_path.write_bytes(log_file.read_bytes())
    log_file.write_text("", encoding="utf-8")

    return ExecutionResult(
        "success", f"Rotated agent log to {archive_name}.", data={"rotated": True, "archive": archive_name}
    )


def retry_telemetry_sync(parameters: dict[str, Any], ctx: ExecutorContext) -> ExecutionResult:
    depth_before = ctx.store.queue_depth()
    batch = ctx.store.next_batch(limit=ctx.config.queue_flush_batch_size)
    if not batch:
        return ExecutionResult("success", "Queue already empty; nothing to retry.", data={"queue_depth": 0})

    event_ids = [item.event_id for item in batch]
    result = ctx.client.send_metrics_batch(ctx.device_id, [item.to_sample() for item in batch])
    ctx.store.mark_delivered(event_ids)
    depth_after = ctx.store.queue_depth()

    return ExecutionResult(
        "success",
        f"Telemetry retry flushed {len(event_ids)} sample(s); queue depth {depth_before} -> {depth_after}.",
        data={"queue_depth_before": depth_before, "queue_depth_after": depth_after, **result},
    )


def repair_agent_queue(parameters: dict[str, Any], ctx: ExecutorContext) -> ExecutionResult:
    depth_before = ctx.store.queue_depth()
    dropped = ctx.store.drop_exhausted(max_attempts=20)
    depth_after = ctx.store.queue_depth()
    return ExecutionResult(
        "success",
        f"Repaired queue: dropped {dropped} exhausted row(s).",
        data={"queue_depth_before": depth_before, "queue_depth_after": depth_after, "dropped": dropped},
    )


def restart_sentinelx_agent(parameters: dict[str, Any], ctx: ExecutorContext) -> ExecutionResult:
    """
    The agent cannot synchronously restart its own process. It records intent
    and reports success; the WinSW service wrapper (service/sentinelx-agent.xml,
    <onfailure action="restart">) is responsible for actually bringing the
    process back after a clean exit is requested by the caller (main.py) once
    this command completes. This function only marks the request as durable.
    """
    ctx.store.set_state("pending_self_restart", True)
    return ExecutionResult(
        "success",
        "Restart requested — agent will exit cleanly after reporting this result; the WinSW "
        "service supervisor will restart the process automatically.",
        data={"scheduled": True},
    )


def restart_allowlisted_service(parameters: dict[str, Any], ctx: ExecutorContext) -> ExecutionResult:
    service_key = parameters.get("service_key")
    if not service_key or not isinstance(service_key, str):
        return ExecutionResult("failure", "Missing required 'service_key' parameter.")

    allowlist = _load_service_allowlist(ctx.config)
    real_service_name = allowlist.get(service_key)
    if real_service_name is None:
        return ExecutionResult("failure", f"'{service_key}' is not present in the local service allowlist.")

    if platform.system() != "Windows":
        return ExecutionResult("failure", "Service restart is only supported on Windows.")

    try:
        subprocess.run(["net", "stop", real_service_name], check=True, capture_output=True, timeout=30)
        subprocess.run(["net", "start", real_service_name], check=True, capture_output=True, timeout=30)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode(errors="replace")[:500]
        return ExecutionResult("failure", f"Service restart failed: {stderr}")
    except subprocess.TimeoutExpired:
        return ExecutionResult("failure", "Service restart timed out.")

    return ExecutionResult(
        "success", f"Service '{service_key}' restarted.", data={"service_key": service_key}
    )


EXECUTORS: dict[str, Callable[[dict[str, Any], ExecutorContext], ExecutionResult]] = {
    "collect_diagnostics": collect_diagnostics,
    "rotate_agent_logs": rotate_agent_logs,
    "retry_telemetry_sync": retry_telemetry_sync,
    "repair_agent_queue": repair_agent_queue,
    "restart_sentinelx_agent": restart_sentinelx_agent,
    "restart_allowlisted_service": restart_allowlisted_service,
}
