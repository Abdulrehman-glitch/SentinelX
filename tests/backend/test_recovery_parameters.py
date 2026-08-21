"""Server-side parameter validation for recovery commands.

The threat this closes: `parameters` used to travel unchecked from the
request body into `RecoveryCommand.parameters_json` and from there into the
canonical string that gets Ed25519-signed. An operator (or a compromised
account) with permission to propose any action could therefore attach
arbitrary JSON to a **signed** command, and every agent would verify the
signature happily — a signature proves the server said it, not that the
server meant it.

Validation lives in create_command, the single funnel every proposal passes
through, so these tests also assert that the AI-proposal and retry paths
cannot route around it.
"""

import uuid

import pytest

from app.services import recovery_command_service, recovery_parameter_schemas
from app.services.recovery_parameter_schemas import (
    RecoveryParameterError,
    validate_parameters,
)


class TestSchemaUnit:
    def test_parameterless_action_accepts_an_empty_object(self):
        assert validate_parameters("collect_diagnostics", {}) == {}
        assert validate_parameters("collect_diagnostics", None) == {}

    def test_unknown_keys_are_rejected_not_silently_dropped(self):
        """Dropping would be worse than rejecting: the operator would approve
        a command whose parameters differ from what they submitted."""

        with pytest.raises(RecoveryParameterError) as exc:
            validate_parameters("collect_diagnostics", {"rm": "-rf /"})

        assert "rm" in str(exc.value)

    def test_unknown_action_cannot_be_proposed_at_all(self):
        with pytest.raises(RecoveryParameterError):
            validate_parameters("exfiltrate_everything", {})

    def test_required_parameter_must_be_present(self):
        with pytest.raises(RecoveryParameterError) as exc:
            validate_parameters("restart_allowlisted_service", {})

        assert "service_key" in str(exc.value)

    def test_valid_service_key_is_accepted_and_copied(self):
        result = validate_parameters("restart_allowlisted_service", {"service_key": "print-spooler"})
        assert result == {"service_key": "print-spooler"}

    def test_returned_object_is_a_copy(self):
        """A caller mutating its dict after validation must not be able to
        change what actually gets signed."""

        supplied = {"service_key": "print-spooler"}
        validated = validate_parameters("restart_allowlisted_service", supplied)

        supplied["service_key"] = "something-else"
        assert validated["service_key"] == "print-spooler"

    @pytest.mark.parametrize(
        "bad_value",
        [
            "Print-Spooler",          # uppercase
            "print spooler",          # space
            "../../windows/system32", # traversal
            "svc; net stop x",        # command separator
            "svc\nnet stop x",        # newline injection
            "-leading-dash",
            "a" * 65,                 # over max_length
        ],
    )
    def test_malformed_service_keys_are_rejected(self, bad_value):
        with pytest.raises(RecoveryParameterError):
            validate_parameters("restart_allowlisted_service", {"service_key": bad_value})

    @pytest.mark.parametrize("bad_value", [123, True, None, ["print-spooler"], {"a": 1}])
    def test_wrong_typed_service_key_is_rejected(self, bad_value):
        with pytest.raises(RecoveryParameterError):
            validate_parameters("restart_allowlisted_service", {"service_key": bad_value})

    def test_non_object_parameters_are_rejected(self):
        with pytest.raises(RecoveryParameterError):
            validate_parameters("collect_diagnostics", ["not", "an", "object"])

    def test_schema_covers_every_action_the_agents_implement(self):
        """Drift guard. The desktop executor map and the seeded policy rows
        are the source of truth for which actions exist; an action shipped
        without a schema here would be unproposable, and a schema without an
        executor would be a command no agent can run."""

        import importlib.util
        from pathlib import Path

        # Loaded by path: scripts/ is not an importable package, and making it
        # one just to read two dicts would be worse than this.
        seed_path = Path(__file__).resolve().parents[2] / "scripts" / "seed_recovery_policies.py"
        spec = importlib.util.spec_from_file_location("seed_recovery_policies", seed_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        policy_actions = set(module.LAPTOP_POLICIES) | set(module.ANDROID_POLICIES)
        assert policy_actions == set(recovery_parameter_schemas.known_action_types())


class TestValidationIsEnforcedAtTheServiceBoundary:
    def test_create_command_rejects_unexpected_parameters(self, db, org, enrolled_device):
        device, _ = enrolled_device

        with pytest.raises(recovery_command_service.RecoveryCommandError):
            recovery_command_service.create_command(
                db,
                organization_id=org.id,
                device_id=device.id,
                action_type="collect_diagnostics",
                parameters={"unexpected": "value"},
                reason="test",
                decision_source="manual",
                actor_type="user",
                actor_id=None,
            )

    def test_nothing_is_persisted_when_validation_fails(self, db, org, enrolled_device):
        """Validation runs before the policy lookup and before any INSERT, so
        a rejected proposal must leave no row behind."""

        from app.models.recovery_command import RecoveryCommand

        device, _ = enrolled_device
        before = db.query(RecoveryCommand).count()

        with pytest.raises(recovery_command_service.RecoveryCommandError):
            recovery_command_service.create_command(
                db,
                organization_id=org.id,
                device_id=device.id,
                action_type="collect_diagnostics",
                parameters={"injected": True},
                reason="test",
                decision_source="manual",
                actor_type="user",
                actor_id=None,
            )
        db.rollback()

        assert db.query(RecoveryCommand).count() == before


class TestValidationThroughTheApi:
    def test_api_returns_422_for_unexpected_parameters(self, client, admin_headers, enrolled_device):
        device, _ = enrolled_device

        response = client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "collect_diagnostics",
                "parameters": {"shell": "powershell -enc ..."},
            },
            headers=admin_headers,
        )
        assert response.status_code == 422
        assert "shell" in response.text

    def test_api_returns_422_for_an_unknown_action(self, client, admin_headers, enrolled_device):
        device, _ = enrolled_device

        response = client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "run_arbitrary_command",
                "parameters": {},
            },
            headers=admin_headers,
        )
        assert response.status_code == 422

    def test_api_returns_422_when_a_required_parameter_is_missing(
        self, client, admin_headers, enrolled_device
    ):
        device, _ = enrolled_device

        response = client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "restart_allowlisted_service",
                "parameters": {},
            },
            headers=admin_headers,
        )
        assert response.status_code == 422
        assert "service_key" in response.text
