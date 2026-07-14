"""Configuration helpers for the SentinelX desktop monitoring agent.

The agent is intentionally configured through environment variables so that
secrets such as device tokens are never hardcoded in source code. Values are
loaded from ``agents/desktop-python/.env`` when the file exists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


AGENT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = AGENT_DIR / ".env"

load_dotenv(ENV_FILE)


def _clean(value: str | None) -> str | None:
    """Return a stripped string or ``None`` for empty values."""

    if value is None:
        return None
    value = value.strip()
    return value or None


def _get_int(name: str, default: int, *, minimum: int | None = None) -> int:
    """Read an integer environment value with a safe fallback."""

    raw_value = _clean(os.getenv(name))
    if raw_value is None:
        return default

    try:
        parsed = int(raw_value)
    except ValueError:
        return default

    if minimum is not None:
        return max(parsed, minimum)
    return parsed


def _get_float(name: str, default: float, *, minimum: float | None = None) -> float:
    """Read a float environment value with a safe fallback."""

    raw_value = _clean(os.getenv(name))
    if raw_value is None:
        return default

    try:
        parsed = float(raw_value)
    except ValueError:
        return default

    if minimum is not None:
        return max(parsed, minimum)
    return parsed


def _get_bool(name: str, default: bool) -> bool:
    """Read a boolean environment value."""

    raw_value = _clean(os.getenv(name))
    if raw_value is None:
        return default

    return raw_value.lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class AgentConfig:
    """Runtime settings for the SentinelX desktop/laptop agent."""

    api_base_url: str

    # Secure device identity. ``device_token`` is required for telemetry writes.
    device_id: str | None
    device_token: str | None

    # Reported device metadata.
    agent_hostname: str | None
    display_name: str | None
    organization_slug: str | None
    device_type: str
    agent_type: str
    agent_version: str

    # Runtime loop settings.
    metrics_interval_seconds: int
    heartbeat_interval_seconds: int
    request_timeout_seconds: int

    # Safe retry/backoff settings.
    retry_max_attempts: int
    retry_initial_delay_seconds: float
    retry_max_delay_seconds: float

    # Non-destructive recovery logging settings.
    enable_recovery_logging: bool
    recovery_cooldown_seconds: int
    cpu_recovery_threshold: float
    memory_recovery_threshold: float
    disk_recovery_threshold: float


def get_config() -> AgentConfig:
    """Build an :class:`AgentConfig` from environment variables."""

    return AgentConfig(
        api_base_url=(os.getenv("SENTINELX_API_BASE_URL", "http://127.0.0.1:8000/api/v1").strip().rstrip("/")),
        device_id=_clean(os.getenv("SENTINELX_DEVICE_ID")),
        device_token=_clean(os.getenv("SENTINELX_DEVICE_TOKEN")),
        agent_hostname=_clean(os.getenv("SENTINELX_AGENT_HOSTNAME")),
        display_name=_clean(os.getenv("SENTINELX_AGENT_DISPLAY_NAME")),
        organization_slug=_clean(os.getenv("SENTINELX_ORGANIZATION_SLUG")),
        device_type=os.getenv("SENTINELX_DEVICE_TYPE", "desktop").strip() or "desktop",
        agent_type=os.getenv("SENTINELX_AGENT_TYPE", "python_desktop_agent").strip() or "python_desktop_agent",
        agent_version=os.getenv("SENTINELX_AGENT_VERSION", "2.1.0").strip() or "2.1.0",
        metrics_interval_seconds=_get_int("SENTINELX_METRICS_INTERVAL_SECONDS", 10, minimum=5),
        heartbeat_interval_seconds=_get_int("SENTINELX_HEARTBEAT_INTERVAL_SECONDS", 30, minimum=10),
        request_timeout_seconds=_get_int("SENTINELX_REQUEST_TIMEOUT_SECONDS", 10, minimum=3),
        retry_max_attempts=_get_int("SENTINELX_RETRY_MAX_ATTEMPTS", 3, minimum=1),
        retry_initial_delay_seconds=_get_float("SENTINELX_RETRY_INITIAL_DELAY_SECONDS", 2.0, minimum=0.5),
        retry_max_delay_seconds=_get_float("SENTINELX_RETRY_MAX_DELAY_SECONDS", 30.0, minimum=1.0),
        enable_recovery_logging=_get_bool("SENTINELX_ENABLE_RECOVERY_LOGGING", True),
        recovery_cooldown_seconds=_get_int("SENTINELX_RECOVERY_COOLDOWN_SECONDS", 120, minimum=30),
        cpu_recovery_threshold=_get_float("SENTINELX_CPU_RECOVERY_THRESHOLD", 95.0, minimum=1.0),
        memory_recovery_threshold=_get_float("SENTINELX_MEMORY_RECOVERY_THRESHOLD", 95.0, minimum=1.0),
        disk_recovery_threshold=_get_float("SENTINELX_DISK_RECOVERY_THRESHOLD", 95.0, minimum=1.0),
    )
