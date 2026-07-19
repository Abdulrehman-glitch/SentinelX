from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sentinelx_agent.config import AgentConfig
from sentinelx_agent.store import AgentStore


@pytest.fixture
def store(tmp_path):
    agent_store = AgentStore(tmp_path / "agent-test.db")
    yield agent_store
    agent_store.close()


@pytest.fixture
def keypair():
    private_key = Ed25519PrivateKey.generate()
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return private_key, base64.b64encode(public_raw).decode("ascii")


@pytest.fixture
def sign_command(keypair):
    """Returns a function that builds+signs a command dict exactly like the
    backend's build_canonical_payload/sign_command_payload would."""

    private_key, _ = keypair

    def _sign(
        *,
        command_id: str | None = None,
        device_id: str = "device-1",
        action_type: str = "collect_diagnostics",
        parameters: dict | None = None,
        nonce: str | None = None,
        expires_in_seconds: int = 300,
        policy_id: str = "policy-1",
    ) -> dict:
        import json

        cmd_id = command_id or str(uuid.uuid4())
        nonce_value = nonce or uuid.uuid4().hex
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).isoformat()
        params = parameters or {}

        canonical_params = json.dumps(params, sort_keys=True, separators=(",", ":"))
        canonical = "\n".join(
            [cmd_id, device_id, action_type, canonical_params, nonce_value, expires_at, expires_at, policy_id]
        )
        signature = base64.b64encode(private_key.sign(canonical.encode("utf-8"))).decode("ascii")

        return {
            "id": cmd_id,
            "device_id": device_id,
            "action_type": action_type,
            "parameters_json": params,
            "command_nonce": nonce_value,
            "expires_at": expires_at,
            "policy_id": policy_id,
            "signature": signature,
            "status": "dispatched",
        }

    return _sign


@pytest.fixture
def agent_config(tmp_path):
    allowlist_path = tmp_path / "service_allowlist.json"
    allowlist_path.write_text('{"sentinelx_agent": "SentinelXAgent"}', encoding="utf-8")

    return AgentConfig(
        api_base_url="http://testserver/api/v1",
        device_id="device-1",
        device_token="sxa_test.token",
        enrollment_code=None,
        agent_hostname="test-host",
        display_name="Test Host",
        organization_slug="test-org",
        device_type="desktop",
        agent_type="python_desktop_agent",
        agent_version="3.1.0",
        metrics_interval_seconds=10,
        heartbeat_interval_seconds=30,
        request_timeout_seconds=10,
        retry_max_attempts=1,
        retry_initial_delay_seconds=0.01,
        retry_max_delay_seconds=0.1,
        queue_flush_batch_size=100,
        queue_max_rows=10000,
        enable_recovery_logging=False,
        recovery_cooldown_seconds=120,
        recovery_sustained_samples=3,
        cpu_recovery_threshold=95.0,
        memory_recovery_threshold=95.0,
        disk_recovery_threshold=95.0,
        command_polling_enabled=True,
        service_allowlist_path=str(allowlist_path),
    )
