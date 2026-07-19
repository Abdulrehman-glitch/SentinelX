from __future__ import annotations

import httpx
import respx

from sentinelx_agent import commands
from sentinelx_agent.client import SentinelXClient
from sentinelx_agent.store import AgentStore


def _make_client(agent_config) -> SentinelXClient:
    return SentinelXClient(agent_config)


@respx.mock
def test_poll_and_execute_happy_path_completes_and_persists(store: AgentStore, agent_config, sign_command, keypair):
    _, public_key_b64 = keypair
    command = sign_command(device_id=agent_config.device_id, action_type="collect_diagnostics")

    respx.get(f"{agent_config.api_base_url}/agent/commands/next").mock(
        return_value=httpx.Response(200, json=command)
    )
    respx.get(f"{agent_config.api_base_url}/agent/public-key").mock(
        return_value=httpx.Response(200, json={"public_key": public_key_b64})
    )
    respx.post(f"{agent_config.api_base_url}/agent/commands/{command['id']}/acknowledge").mock(
        return_value=httpx.Response(200, json={**command, "status": "acknowledged"})
    )
    respx.post(f"{agent_config.api_base_url}/agent/commands/{command['id']}/start").mock(
        return_value=httpx.Response(200, json={**command, "status": "running"})
    )
    complete_route = respx.post(f"{agent_config.api_base_url}/agent/commands/{command['id']}/complete").mock(
        return_value=httpx.Response(200, json={**command, "status": "verified"})
    )

    client = _make_client(agent_config)
    try:
        commands.poll_and_execute(client, agent_config, store, agent_config.device_id)
    finally:
        client.close()

    assert complete_route.called
    assert store.get_command_status(command["id"]) == "completed"


@respx.mock
def test_poll_and_execute_rejects_invalid_signature(store: AgentStore, agent_config, sign_command, keypair):
    command = sign_command(device_id=agent_config.device_id, action_type="collect_diagnostics")
    command["signature"] = "aW52YWxpZC1zaWduYXR1cmU="  # base64 garbage, will not verify

    respx.get(f"{agent_config.api_base_url}/agent/commands/next").mock(
        return_value=httpx.Response(200, json=command)
    )
    respx.get(f"{agent_config.api_base_url}/agent/public-key").mock(
        return_value=httpx.Response(200, json={"public_key": keypair[1]})
    )
    reject_route = respx.post(f"{agent_config.api_base_url}/agent/commands/{command['id']}/reject").mock(
        return_value=httpx.Response(200, json={**command, "status": "rejected"})
    )

    client = _make_client(agent_config)
    try:
        commands.poll_and_execute(client, agent_config, store, agent_config.device_id)
    finally:
        client.close()

    assert reject_route.called
    assert store.get_command_status(command["id"]) is None  # never durably "received" — rejected pre-storage


@respx.mock
def test_poll_and_execute_rejects_unsupported_action(store: AgentStore, agent_config, sign_command, keypair):
    command = sign_command(device_id=agent_config.device_id, action_type="delete_everything")

    respx.get(f"{agent_config.api_base_url}/agent/commands/next").mock(
        return_value=httpx.Response(200, json=command)
    )
    respx.get(f"{agent_config.api_base_url}/agent/public-key").mock(
        return_value=httpx.Response(200, json={"public_key": keypair[1]})
    )
    reject_route = respx.post(f"{agent_config.api_base_url}/agent/commands/{command['id']}/reject").mock(
        return_value=httpx.Response(200, json={**command, "status": "rejected"})
    )

    client = _make_client(agent_config)
    try:
        commands.poll_and_execute(client, agent_config, store, agent_config.device_id)
    finally:
        client.close()

    assert reject_route.called
    request_body = reject_route.calls.last.request.content.decode()
    assert "not supported" in request_body


@respx.mock
def test_poll_and_execute_rejects_expired_command(store: AgentStore, agent_config, sign_command, keypair):
    command = sign_command(device_id=agent_config.device_id, expires_in_seconds=-30)

    respx.get(f"{agent_config.api_base_url}/agent/commands/next").mock(
        return_value=httpx.Response(200, json=command)
    )
    reject_route = respx.post(f"{agent_config.api_base_url}/agent/commands/{command['id']}/reject").mock(
        return_value=httpx.Response(200, json={**command, "status": "rejected"})
    )

    client = _make_client(agent_config)
    try:
        commands.poll_and_execute(client, agent_config, store, agent_config.device_id)
    finally:
        client.close()

    assert reject_route.called


@respx.mock
def test_poll_and_execute_replayed_nonce_rejected(store: AgentStore, agent_config, sign_command, keypair):
    # A previous cycle already recorded this exact nonce under a *different*
    # command_id — simulating a captured-and-replayed signed payload.
    store.record_command_received("some-other-command-id", "reused-nonce", "collect_diagnostics")

    command = sign_command(device_id=agent_config.device_id, nonce="reused-nonce")

    respx.get(f"{agent_config.api_base_url}/agent/commands/next").mock(
        return_value=httpx.Response(200, json=command)
    )
    respx.get(f"{agent_config.api_base_url}/agent/public-key").mock(
        return_value=httpx.Response(200, json={"public_key": keypair[1]})
    )
    reject_route = respx.post(f"{agent_config.api_base_url}/agent/commands/{command['id']}/reject").mock(
        return_value=httpx.Response(200, json={**command, "status": "rejected"})
    )

    client = _make_client(agent_config)
    try:
        commands.poll_and_execute(client, agent_config, store, agent_config.device_id)
    finally:
        client.close()

    assert reject_route.called
    request_body = reject_route.calls.last.request.content.decode()
    assert "replay" in request_body.lower()


@respx.mock
def test_poll_and_execute_no_command_available(store: AgentStore, agent_config):
    respx.get(f"{agent_config.api_base_url}/agent/commands/next").mock(
        return_value=httpx.Response(200, json=None)
    )

    client = _make_client(agent_config)
    try:
        commands.poll_and_execute(client, agent_config, store, agent_config.device_id)
    finally:
        client.close()
    # Nothing to assert beyond "did not raise" — no command means a no-op cycle.


@respx.mock
def test_completion_upload_retries_on_transient_failure(store: AgentStore, agent_config, sign_command, keypair):
    command = sign_command(device_id=agent_config.device_id, action_type="collect_diagnostics")

    respx.get(f"{agent_config.api_base_url}/agent/commands/next").mock(
        return_value=httpx.Response(200, json=command)
    )
    respx.get(f"{agent_config.api_base_url}/agent/public-key").mock(
        return_value=httpx.Response(200, json={"public_key": keypair[1]})
    )
    respx.post(f"{agent_config.api_base_url}/agent/commands/{command['id']}/acknowledge").mock(
        return_value=httpx.Response(200, json={**command, "status": "acknowledged"})
    )
    respx.post(f"{agent_config.api_base_url}/agent/commands/{command['id']}/start").mock(
        return_value=httpx.Response(200, json={**command, "status": "running"})
    )
    # First attempt: transient 503. client.py's built-in backoff retries;
    # second attempt succeeds. retry_max_attempts defaults to 1 in the
    # agent_config fixture, so bump it here to actually exercise the retry.
    object.__setattr__(agent_config, "retry_max_attempts", 2)
    complete_route = respx.post(f"{agent_config.api_base_url}/agent/commands/{command['id']}/complete").mock(
        side_effect=[
            httpx.Response(503, json={"detail": "temporarily unavailable"}),
            httpx.Response(200, json={**command, "status": "verified"}),
        ]
    )

    client = _make_client(agent_config)
    try:
        commands.poll_and_execute(client, agent_config, store, agent_config.device_id)
    finally:
        client.close()

    assert complete_route.call_count == 2
    assert store.get_command_status(command["id"]) == "completed"
