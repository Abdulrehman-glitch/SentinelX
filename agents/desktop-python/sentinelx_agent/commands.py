"""Signed recovery-command polling and execution for the desktop agent.

Called once per main-loop tick (main.py). Fetches the single active command
for this device (if any), verifies its Ed25519 signature and expiry,
executes the allowlisted action, and reports the result back — every step
persisted to SQLite (store.py) before the network call that reports it, so a
process restart mid-command resumes from durable state rather than
re-executing or silently losing the result.
"""

from __future__ import annotations

import logging
from typing import Any

from sentinelx_agent import executors
from sentinelx_agent.client import SentinelXClient, SentinelXClientError
from sentinelx_agent.config import AgentConfig
from sentinelx_agent.executors import ExecutorContext
from sentinelx_agent.signing import is_expired, verify_command_signature
from sentinelx_agent.store import AgentStore

log = logging.getLogger("sentinelx.agent.commands")


def report_capabilities(client: SentinelXClient, config: AgentConfig) -> None:
    """Report the agent's supported actions — called at enrolment and on
    every process start (idempotent upsert on the backend)."""

    try:
        client.report_capabilities(
            agent_type=config.agent_type,
            agent_version=config.agent_version,
            capabilities=[
                {"action_type": action_type, "action_version": "1", "local_risk_level": risk}
                for action_type, risk in executors.ACTION_RISK_LEVELS.items()
            ],
        )
        log.info("Reported %d supported recovery action(s) to the backend.", len(executors.ACTION_RISK_LEVELS))
    except SentinelXClientError as exc:
        log.warning("Could not report agent capabilities: %s", exc)


def _get_public_key(client: SentinelXClient, store: AgentStore, *, force_refresh: bool = False) -> str | None:
    if not force_refresh:
        cached = store.get_state("recovery_public_key")
        if cached:
            return cached
    try:
        public_key = client.get_recovery_public_key()
    except SentinelXClientError as exc:
        log.warning("Could not fetch recovery signing public key: %s", exc)
        return None
    store.set_state("recovery_public_key", public_key)
    return public_key


def _reject(client: SentinelXClient, command_id: str, reason: str) -> None:
    try:
        client.reject_command(command_id, reason=reason)
    except SentinelXClientError as exc:
        log.warning("Could not report rejection for command %s: %s", command_id, exc)


def poll_and_execute(client: SentinelXClient, config: AgentConfig, store: AgentStore, device_id: str) -> None:
    try:
        command = client.get_next_command()
    except SentinelXClientError as exc:
        if exc.is_fatal_auth_error:
            raise
        log.warning("Command poll failed: %s", exc)
        return

    if command is None:
        return

    command_id: str = command["id"]

    # Idempotency / restart-safety: never re-execute a command this process
    # already durably recorded as completed, even if somehow re-delivered.
    if store.get_command_status(command_id) == "completed":
        return

    if is_expired(command):
        _reject(client, command_id, "Command already expired when received.")
        return

    public_key = _get_public_key(client, store)
    if public_key is None:
        log.warning("No recovery public key available yet; skipping command %s this cycle.", command_id)
        return

    if not verify_command_signature(command, public_key):
        # Retry once with a freshly-fetched key in case of server-side rotation.
        public_key = _get_public_key(client, store, force_refresh=True)
        if public_key is None or not verify_command_signature(command, public_key):
            _reject(client, command_id, "Signature verification failed.")
            return

    action_type: str = command["action_type"]
    if action_type not in executors.EXECUTORS:
        _reject(client, command_id, f"Action '{action_type}' is not supported by this agent build.")
        return

    nonce = command.get("command_nonce")
    already_received = store.get_command_status(command_id) is not None
    if nonce and store.nonce_seen(nonce) and not already_received:
        _reject(client, command_id, "Nonce already processed (replay).")
        return

    if not already_received:
        store.record_command_received(command_id, nonce, action_type)

    try:
        client.acknowledge_command(command_id)
    except SentinelXClientError as exc:
        log.warning("Could not acknowledge command %s: %s", command_id, exc)
        return
    store.update_command_status(command_id, "acknowledged")

    try:
        client.start_command(command_id)
    except SentinelXClientError as exc:
        log.warning("Could not mark command %s as started: %s", command_id, exc)
        return
    store.update_command_status(command_id, "running")

    context = ExecutorContext(config=config, store=store, client=client, device_id=device_id)
    parameters: dict[str, Any] = command.get("parameters_json") or {}
    try:
        result = executors.EXECUTORS[action_type](parameters, context)
    except Exception as exc:  # noqa: BLE001 - an executor bug must never crash the agent loop
        log.exception("Executor for '%s' raised unexpectedly.", action_type)
        result = executors.ExecutionResult("failure", f"Executor error: {exc}")

    try:
        client.complete_command(
            command_id,
            result_code=result.result_code,
            result_message=result.message,
            result_data=result.data,
            post_action_snapshot=result.post_snapshot,
        )
    except SentinelXClientError as exc:
        log.warning("Could not report completion for command %s: %s", command_id, exc)
        return

    store.mark_command_completed(command_id)
    log.info("Command %s (%s) completed: %s", command_id, action_type, result.message)
