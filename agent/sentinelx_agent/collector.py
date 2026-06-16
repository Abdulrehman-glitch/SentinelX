import platform
import socket
from dataclasses import dataclass

import psutil

from sentinelx_agent.config import AgentConfig


@dataclass(frozen=True)
class DeviceIdentity:
    """
    Identity data used when registering this machine with the backend.
    """

    hostname: str
    ip_address: str
    os_name: str


@dataclass(frozen=True)
class SystemMetrics:
    """
    System utilisation values collected by the local monitoring agent.
    """

    cpu_percent: float
    memory_percent: float
    disk_percent: float


def get_ip_address() -> str:
    """
    Attempts to identify the local IP address.

    If network detection fails, 127.0.0.1 is used as a safe fallback.
    """

    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except OSError:
        return "127.0.0.1"


def collect_device_identity(config: AgentConfig) -> DeviceIdentity:
    """
    Collects stable device identity data for backend registration.
    """

    hostname = config.agent_hostname or socket.gethostname()

    return DeviceIdentity(
        hostname=hostname,
        ip_address=get_ip_address(),
        os_name=f"{platform.system()} {platform.release()}",
    )


def collect_system_metrics() -> SystemMetrics:
    """
    Collects CPU, memory, and disk usage from the host machine.

    psutil.cpu_percent(interval=1) waits briefly to calculate a meaningful
    CPU percentage rather than returning an instant unreliable value.
    """

    cpu_percent = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent
    disk_percent = psutil.disk_usage("/").percent

    return SystemMetrics(
        cpu_percent=round(cpu_percent, 2),
        memory_percent=round(memory_percent, 2),
        disk_percent=round(disk_percent, 2),
    )