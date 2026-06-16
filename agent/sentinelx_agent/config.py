import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


AGENT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = AGENT_DIR / ".env"

load_dotenv(ENV_FILE)


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    try:
        return float(value)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    return value.strip().lower() in {"true", "1", "yes", "y"}


@dataclass(frozen=True)
class AgentConfig:
    """
    Runtime configuration for the SentinelX monitoring agent.

    The agent reads settings from agent/.env so values can be changed
    without editing source code.
    """

    api_base_url: str
    agent_hostname: str | None
    interval_seconds: int
    request_timeout_seconds: int

    enable_recovery_logging: bool
    recovery_cooldown_seconds: int

    cpu_recovery_threshold: float
    memory_recovery_threshold: float
    disk_recovery_threshold: float


def get_config() -> AgentConfig:
    api_base_url = os.getenv("SENTINELX_API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
    agent_hostname = os.getenv("SENTINELX_AGENT_HOSTNAME") or None

    return AgentConfig(
        api_base_url=api_base_url,
        agent_hostname=agent_hostname,
        interval_seconds=_get_int("SENTINELX_INTERVAL_SECONDS", 10),
        request_timeout_seconds=_get_int("SENTINELX_REQUEST_TIMEOUT_SECONDS", 10),
        enable_recovery_logging=_get_bool("SENTINELX_ENABLE_RECOVERY_LOGGING", True),
        recovery_cooldown_seconds=_get_int("SENTINELX_RECOVERY_COOLDOWN_SECONDS", 120),
        cpu_recovery_threshold=_get_float("SENTINELX_CPU_RECOVERY_THRESHOLD", 95.0),
        memory_recovery_threshold=_get_float("SENTINELX_MEMORY_RECOVERY_THRESHOLD", 95.0),
        disk_recovery_threshold=_get_float("SENTINELX_DISK_RECOVERY_THRESHOLD", 95.0),
    )