"""Local system metric collection for the SentinelX desktop agent."""

from __future__ import annotations

import os
import platform
import socket
import sys
from dataclasses import dataclass

import psutil

from sentinelx_agent.config import AgentConfig


@dataclass(frozen=True)
class DeviceIdentity:
    """Device metadata sent to the backend registration endpoint."""

    hostname: str
    display_name: str | None
    ip_address: str
    os_name: str
    organization_slug: str | None
    device_type: str
    agent_type: str
    agent_version: str


@dataclass(frozen=True)
class SystemMetrics:
    """System utilisation values collected from the host machine."""

    cpu_percent: float
    memory_percent: float
    disk_percent: float


def get_ip_address() -> str:
    """Return the machine's preferred local IP address.

    ``socket.gethostbyname(socket.gethostname())`` often returns ``127.0.0.1`` on
    Windows. Opening a UDP socket to a public address does not send traffic, but
    it helps the OS reveal the active interface IP. A loopback fallback is used
    when no network interface is available.
    """

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def _disk_root() -> str:
    """Return the disk root path to inspect on the current OS."""

    if sys.platform == "win32":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


def collect_device_identity(config: AgentConfig) -> DeviceIdentity:
    """Collect stable device metadata for backend registration/refresh."""

    hostname = config.agent_hostname or socket.gethostname()
    display_name = config.display_name or hostname

    return DeviceIdentity(
        hostname=hostname,
        display_name=display_name,
        ip_address=get_ip_address(),
        os_name=f"{platform.system()} {platform.release()}",
        organization_slug=config.organization_slug,
        device_type=config.device_type,
        agent_type=config.agent_type,
        agent_version=config.agent_version,
    )


def collect_system_metrics() -> SystemMetrics:
    """Collect CPU, memory and disk usage using psutil.

    ``psutil.cpu_percent(interval=1)`` waits briefly to produce a meaningful
    value instead of returning a misleading first-call reading.
    """

    cpu_percent = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent
    disk_percent = psutil.disk_usage(_disk_root()).percent

    return SystemMetrics(
        cpu_percent=round(float(cpu_percent), 2),
        memory_percent=round(float(memory_percent), 2),
        disk_percent=round(float(disk_percent), 2),
    )
