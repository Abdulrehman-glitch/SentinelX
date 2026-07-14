"""HTTP client for communicating with the SentinelX backend API."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

import httpx

from sentinelx_agent.collector import DeviceIdentity, SystemMetrics
from sentinelx_agent.config import AgentConfig


class SentinelXClientError(RuntimeError):
    """Raised when the agent cannot communicate correctly with the backend."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

    @property
    def is_fatal_auth_error(self) -> bool:
        """Return True for errors that usually require config/token repair."""

        return self.status_code in {401, 403, 422}


class SentinelXClient:
    """Small resilient client used by the desktop monitoring agent."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.client = httpx.Client(
            base_url=config.api_base_url,
            timeout=config.request_timeout_seconds,
            headers={"User-Agent": f"SentinelX-Agent/{config.agent_version}"},
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""

        self.client.close()

    def _auth_headers(self) -> dict[str, str]:
        """Return Authorization headers for device-token protected routes."""

        if not self.config.device_token:
            raise SentinelXClientError(
                "SENTINELX_DEVICE_TOKEN is missing. Agent telemetry endpoints require a device token.",
                status_code=401,
            )
        return {"Authorization": f"Bearer {self.config.device_token}"}

    def _response_detail(self, response: httpx.Response) -> str:
        """Extract a readable error message from a backend response."""

        try:
            body = response.json()
        except ValueError:
            return response.text.strip() or response.reason_phrase

        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, str):
            return detail
        return str(body)

    def _sleep_before_retry(self, attempt: int, response: httpx.Response | None = None) -> None:
        """Sleep using a bounded exponential backoff.

        ``Retry-After`` is respected when present, which avoids aggressive
        retrying after rate-limit responses.
        """

        retry_after = None
        if response is not None:
            retry_after_header = response.headers.get("Retry-After")
            if retry_after_header:
                try:
                    retry_after = float(retry_after_header)
                except ValueError:
                    retry_after = None

        delay = retry_after if retry_after is not None else self.config.retry_initial_delay_seconds * (2 ** max(attempt - 1, 0))
        delay = min(max(delay, 0.5), self.config.retry_max_delay_seconds)
        time.sleep(delay)

    def _request(self, method: str, url: str, *, json: dict[str, Any] | None = None, auth: bool = False) -> httpx.Response:
        """Send a request with safe retry/backoff for transient failures."""

        headers = self._auth_headers() if auth else None
        max_attempts = self.config.retry_max_attempts

        for attempt in range(1, max_attempts + 1):
            response: httpx.Response | None = None
            try:
                response = self.client.request(method, url, json=json, headers=headers)

                if response.status_code < 400:
                    return response

                # Do not retry invalid credentials, tenant mismatch or bad payloads.
                if response.status_code in {400, 401, 403, 404, 409, 422}:
                    raise SentinelXClientError(
                        f"Backend returned HTTP {response.status_code}: {self._response_detail(response)}",
                        status_code=response.status_code,
                    )

                # Retry rate limits and temporary server failures only.
                if response.status_code in {429, 500, 502, 503, 504} and attempt < max_attempts:
                    self._sleep_before_retry(attempt, response)
                    continue

                raise SentinelXClientError(
                    f"Backend returned HTTP {response.status_code}: {self._response_detail(response)}",
                    status_code=response.status_code,
                )

            except httpx.RequestError as exc:
                if attempt < max_attempts:
                    self._sleep_before_retry(attempt, response)
                    continue
                raise SentinelXClientError(f"Could not reach SentinelX backend: {exc}") from exc

        raise SentinelXClientError("Request failed after retries.")

    def register_device(self, identity: DeviceIdentity) -> str:
        """Register or refresh this machine as a monitored SentinelX device."""

        response = self._request("POST", "/devices/register", json=asdict(identity), auth=False)
        payload: dict[str, Any] = response.json()
        return str(payload["id"])

    def send_heartbeat(self, device_id: str, *, status: str = "online", message: str = "Agent heartbeat received") -> None:
        """Send a device-token authenticated heartbeat."""

        self._request(
            "POST",
            "/heartbeats",
            json={"device_id": device_id, "status": status, "message": message},
            auth=True,
        )

    def send_metrics(self, device_id: str, metrics: SystemMetrics) -> int:
        """Send device-token authenticated CPU, memory and disk metrics."""

        response = self._request(
            "POST",
            "/metrics",
            json={
                "device_id": device_id,
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent,
                "disk_percent": metrics.disk_percent,
            },
            auth=True,
        )
        payload: dict[str, Any] = response.json()
        return int(payload.get("alerts_created", 0))

    def log_recovery_action(self, device_id: str, action_type: str, details: str) -> None:
        """Log a non-destructive recovery action through the safe agent route."""

        self._request(
            "POST",
            "/recovery-actions/agent-log",
            json={
                "device_id": device_id,
                "action_type": action_type,
                "status": "logged",
                "details": details,
            },
            auth=True,
        )
