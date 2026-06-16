from dataclasses import asdict
from typing import Any

import httpx

from sentinelx_agent.collector import DeviceIdentity, SystemMetrics
from sentinelx_agent.config import AgentConfig


class SentinelXClientError(RuntimeError):
    """
    Raised when the agent cannot communicate correctly with the backend.
    """


class SentinelXClient:
    """
    HTTP client used by the monitoring agent to communicate with the
    SentinelX FastAPI backend.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.client = httpx.Client(
            base_url=config.api_base_url,
            timeout=config.request_timeout_seconds,
        )

    def close(self) -> None:
        self.client.close()

    def _raise_for_bad_response(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SentinelXClientError(
                f"Backend returned HTTP {response.status_code}: {response.text}"
            ) from exc

    def register_device(self, identity: DeviceIdentity) -> str:
        """
        Registers this machine as a monitored device.

        The backend returns the device UUID, which is then used for
        heartbeats, metrics, alerts, and recovery action logs.
        """

        response = self.client.post("/devices/register", json=asdict(identity))
        self._raise_for_bad_response(response)

        payload: dict[str, Any] = response.json()
        return str(payload["id"])

    def send_heartbeat(self, device_id: str, message: str = "Agent heartbeat received") -> None:
        """
        Sends an online heartbeat for the registered device.
        """

        response = self.client.post(
            "/heartbeats",
            json={
                "device_id": device_id,
                "status": "online",
                "message": message,
            },
        )
        self._raise_for_bad_response(response)

    def send_metrics(self, device_id: str, metrics: SystemMetrics) -> int:
        """
        Sends system metrics to the backend.

        Returns the number of alerts created by the backend.
        """

        response = self.client.post(
            "/metrics",
            json={
                "device_id": device_id,
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent,
                "disk_percent": metrics.disk_percent,
            },
        )
        self._raise_for_bad_response(response)

        payload: dict[str, Any] = response.json()
        return int(payload.get("alerts_created", 0))

    def log_recovery_action(self, device_id: str, action_type: str, details: str) -> None:
        """
        Logs a non-destructive recovery action.

        The MVP only records that a recovery action would be required.
        It does not restart services, kill processes, or reboot the machine.
        """

        response = self.client.post(
            "/recovery-actions",
            json={
                "device_id": device_id,
                "action_type": action_type,
                "status": "logged",
                "details": details,
            },
        )
        self._raise_for_bad_response(response)