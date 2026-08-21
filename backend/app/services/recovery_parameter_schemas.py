"""Server-side, per-action parameter schemas for recovery commands.

Before this existed, `parameters` went straight from the request body into
`RecoveryCommand.parameters_json` and from there into the canonical payload
that gets Ed25519-signed. Nothing checked the keys. That meant a caller with
permission to propose *any* action could attach arbitrary attacker-chosen
JSON to a **signed** command, and every agent would verify the signature
happily — the signature only proves the server said it, not that the server
meant it.

The rules here are deliberately strict:

* an action not listed below cannot be proposed at all;
* unknown keys are rejected rather than dropped, so a typo or an injection
  attempt surfaces as a 422 instead of silently producing a command whose
  parameters differ from what the operator believed they approved;
* required keys must be present and correctly typed;
* validation runs inside create_command, which is the single funnel every
  proposal passes through (manual, AI-proposed, and retry alike), so there
  is no path that reaches signing unvalidated.

Canonical-payload compatibility is untouched. This module only constrains
what may appear in `parameters_json`; it does not change the field order,
the JSON canonicalisation, or the duplicated `expires_at` entry in
build_canonical_payload — the shipped desktop and Android verifiers
reproduce that duplication deliberately, and changing it would invalidate
every agent in the field without a coordinated protocol version bump.
"""

import re
from dataclasses import dataclass, field
from typing import Any


class RecoveryParameterError(ValueError):
    """Raised when parameters do not match the action's schema."""


# A logical service key, resolved against the agent's LOCAL
# service_allowlist.json — never a real Windows service name, and never
# anything that could be read as a path or command fragment.
_SERVICE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class ParameterSpec:
    type: type
    required: bool = False
    pattern: re.Pattern[str] | None = None
    max_length: int | None = None
    choices: tuple[Any, ...] | None = None


@dataclass(frozen=True)
class ActionSchema:
    """Allowed parameters for one action type. An empty `parameters` means
    the action takes none — and, because unknown keys are rejected, that the
    command's parameter object must be exactly {}."""

    parameters: dict[str, ParameterSpec] = field(default_factory=dict)


# Mirrors the executor implementations:
#   agents/desktop-python/sentinelx_agent/executors.py  (EXECUTORS)
#   agents/android-native/.../CommandExecutor.kt
# and the policy rows seeded by scripts/seed_recovery_policies.py.
#
# Every action currently shipped is parameterless except
# restart_allowlisted_service. Listing them explicitly rather than defaulting
# to "no parameters" is the point: adding an action here is a conscious act.
ACTION_SCHEMAS: dict[str, ActionSchema] = {
    # ── Desktop (python_desktop_agent) ────────────────────────────────
    "collect_diagnostics": ActionSchema(),
    "rotate_agent_logs": ActionSchema(),
    "retry_telemetry_sync": ActionSchema(),
    "repair_agent_queue": ActionSchema(),
    "restart_sentinelx_agent": ActionSchema(),
    "restart_allowlisted_service": ActionSchema(
        parameters={
            "service_key": ParameterSpec(
                type=str,
                required=True,
                pattern=_SERVICE_KEY_PATTERN,
                max_length=64,
            )
        }
    ),
    # ── Android (android_native_agent) ────────────────────────────────
    "reset_api_connection": ActionSchema(),
    "repair_local_database": ActionSchema(),
    "reschedule_sync_workers": ActionSchema(),
    "restart_monitoring_service": ActionSchema(),
    "enter_safe_monitoring_mode": ActionSchema(),
    "restore_normal_monitoring_mode": ActionSchema(),
}


def known_action_types() -> frozenset[str]:
    return frozenset(ACTION_SCHEMAS)


def validate_parameters(action_type: str, parameters: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and return the parameter object to persist and sign.

    Returns a NEW dict rather than the caller's, so a mutation after
    validation cannot change what gets signed.
    """

    schema = ACTION_SCHEMAS.get(action_type)
    if schema is None:
        raise RecoveryParameterError(
            f"Unknown recovery action '{action_type}'. Allowed actions: "
            f"{', '.join(sorted(ACTION_SCHEMAS))}."
        )

    supplied = parameters or {}
    if not isinstance(supplied, dict):
        raise RecoveryParameterError("Recovery command parameters must be a JSON object.")

    unknown = sorted(set(supplied) - set(schema.parameters))
    if unknown:
        allowed = ", ".join(sorted(schema.parameters)) or "(none - this action takes no parameters)"
        raise RecoveryParameterError(
            f"Unexpected parameter(s) for '{action_type}': {', '.join(unknown)}. Allowed: {allowed}."
        )

    validated: dict[str, Any] = {}

    for name, spec in schema.parameters.items():
        if name not in supplied:
            if spec.required:
                raise RecoveryParameterError(
                    f"Missing required parameter '{name}' for action '{action_type}'."
                )
            continue

        value = supplied[name]

        # bool is a subclass of int in Python; an explicit check stops True
        # from satisfying an int-typed parameter.
        if spec.type is not bool and isinstance(value, bool):
            raise RecoveryParameterError(f"Parameter '{name}' must be of type {spec.type.__name__}.")
        if not isinstance(value, spec.type):
            raise RecoveryParameterError(f"Parameter '{name}' must be of type {spec.type.__name__}.")

        if isinstance(value, str):
            if spec.max_length is not None and len(value) > spec.max_length:
                raise RecoveryParameterError(
                    f"Parameter '{name}' exceeds the maximum length of {spec.max_length}."
                )
            if spec.pattern is not None and not spec.pattern.match(value):
                raise RecoveryParameterError(
                    f"Parameter '{name}' has an invalid format for action '{action_type}'."
                )

        if spec.choices is not None and value not in spec.choices:
            raise RecoveryParameterError(
                f"Parameter '{name}' must be one of: {', '.join(str(c) for c in spec.choices)}."
            )

        validated[name] = value

    return validated
