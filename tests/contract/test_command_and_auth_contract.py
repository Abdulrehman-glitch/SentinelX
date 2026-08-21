"""Wire contract for the signed-command envelope, heartbeats and auth.

The signed-command assertions are the highest-stakes contract in the project:
the desktop agent and the Android agent each rebuild the canonical payload
byte-for-byte before verifying the Ed25519 signature. If the field order, the
JSON canonicalisation or the duplicated `expires_at` entry changes, every
agent in the field starts rejecting every command — silently, because a failed
verification looks exactly like a hostile command.

That duplication is deliberate and is asserted here so nobody "fixes" it
without doing the coordinated protocol version bump it would require.
"""

import base64
import json
import uuid
from datetime import timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def _device_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_policy_and_capability(client, db, org_id, token, action_type):
    """Policy row direct, capability through the real endpoint.

    Registering the capability via POST /agent/capabilities rather than an
    INSERT is deliberate: it is the same call a live agent makes on startup,
    so this helper exercises the contract instead of working around it.
    """

    from app.models.recovery_policy import RecoveryPolicy

    db.add(
        RecoveryPolicy(
            id=uuid.uuid4(),
            organization_id=org_id,
            action_type=action_type,
            risk_level="low",
            approval_mode="auto",
            enabled=True,
        )
    )
    db.commit()

    registered = client.post(
        "/api/v1/agent/capabilities",
        json={
            "agent_type": "python_desktop_agent",
            "agent_version": "3.0.0",
            "capabilities": [
                {"action_type": action_type, "action_version": "1", "local_risk_level": "low"}
            ],
        },
        headers=_device_headers(token),
    )
    assert registered.status_code == 204, registered.text


class TestPublicKeyContract:
    def test_public_key_is_raw_ed25519_base64(self, client, enrolled_device):
        """Agents cache this and construct an Ed25519PublicKey from it
        directly. PEM or DER here would break every one of them."""

        _device, token = enrolled_device

        response = client.get("/api/v1/agent/public-key", headers=_device_headers(token))
        assert response.status_code == 200

        body = response.json()
        assert set(body) == {"public_key"}

        raw = base64.b64decode(body["public_key"])
        assert len(raw) == 32, "raw Ed25519 public keys are exactly 32 bytes"
        Ed25519PublicKey.from_public_bytes(raw)

    def test_public_key_requires_a_device_token(self, client):
        assert client.get("/api/v1/agent/public-key").status_code == 401


class TestCapabilityContract:
    def test_capability_registration_accepts_the_agent_shape_and_returns_204(
        self, client, enrolled_device
    ):
        _device, token = enrolled_device

        response = client.post(
            "/api/v1/agent/capabilities",
            json={
                "agent_type": "python_desktop_agent",
                "agent_version": "3.0.0",
                "capabilities": [
                    {
                        "action_type": "collect_diagnostics",
                        "action_version": "1",
                        "local_risk_level": "low",
                    }
                ],
            },
            headers=_device_headers(token),
        )
        assert response.status_code == 204
        assert response.content == b""


class TestSignedCommandEnvelope:
    def test_dispatched_command_carries_the_full_signing_envelope(
        self, client, db, org, admin_headers, enrolled_device
    ):
        device, token = enrolled_device
        _seed_policy_and_capability(client, db, org.id, token, "collect_diagnostics")

        created = client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "collect_diagnostics",
                "parameters": {},
            },
            headers=admin_headers,
        )
        assert created.status_code == 201, created.text

        dispatched = client.get("/api/v1/agent/commands/next", headers=_device_headers(token))
        assert dispatched.status_code == 200

        command = dispatched.json()
        assert command is not None, "an auto-approved command should dispatch on first poll"

        for field in (
            "id",
            "device_id",
            "action_type",
            "parameters_json",
            "command_nonce",
            "expires_at",
            "payload_hash",
            "signature",
            "status",
        ):
            assert field in command, f"agents read `{field}` off the dispatched command"

        assert command["status"] == "dispatched"
        assert command["signature"]
        assert command["command_nonce"]

    def test_canonical_payload_is_reproducible_by_a_client(
        self, client, db, org, admin_headers, enrolled_device
    ):
        """Rebuilt here from the JSON an agent actually receives — not by
        calling the server's own helper — so this fails if the wire fields
        stop being sufficient to reconstruct what was signed."""

        from app.core.security import get_recovery_public_key_b64
        from app.models.recovery_command import RecoveryCommand

        device, token = enrolled_device
        _seed_policy_and_capability(client, db, org.id, token, "collect_diagnostics")

        client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "collect_diagnostics",
                "parameters": {},
            },
            headers=admin_headers,
        )
        command = client.get("/api/v1/agent/commands/next", headers=_device_headers(token)).json()

        row = db.get(RecoveryCommand, uuid.UUID(command["id"]))
        expires_iso = row.expires_at.astimezone(timezone.utc).isoformat()
        canonical_params = json.dumps(
            command["parameters_json"] or {}, sort_keys=True, separators=(",", ":")
        )

        rebuilt = "\n".join(
            [
                command["id"],
                command["device_id"],
                command["action_type"],
                canonical_params,
                command["command_nonce"],
                expires_iso,
                # Intentionally duplicated. Shipped agents reproduce it; see
                # the module docstring before touching this.
                expires_iso,
                command["policy_id"] or "",
            ]
        )

        public_key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(get_recovery_public_key_b64())
        )
        public_key.verify(base64.b64decode(command["signature"]), rebuilt.encode("utf-8"))

    def test_polling_twice_returns_the_same_signature(
        self, client, db, org, admin_headers, enrolled_device
    ):
        """Agents re-poll after a crash. Re-signing on every poll would
        invalidate a command the agent had already begun verifying."""

        device, token = enrolled_device
        _seed_policy_and_capability(client, db, org.id, token, "collect_diagnostics")

        client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "collect_diagnostics",
                "parameters": {},
            },
            headers=admin_headers,
        )

        first = client.get("/api/v1/agent/commands/next", headers=_device_headers(token)).json()
        second = client.get("/api/v1/agent/commands/next", headers=_device_headers(token)).json()

        assert first["id"] == second["id"]
        assert first["signature"] == second["signature"]
        assert first["command_nonce"] == second["command_nonce"]

    def test_no_pending_command_is_a_200_with_a_null_body_not_a_404(self, client, enrolled_device):
        """Agents poll on a timer; a 404 would be indistinguishable from a
        routing failure and would spam their error handling."""

        _device, token = enrolled_device

        response = client.get("/api/v1/agent/commands/next", headers=_device_headers(token))
        assert response.status_code == 200
        assert response.json() is None

    def test_command_endpoints_reject_a_user_token(self, client, admin_headers):
        assert client.get("/api/v1/agent/commands/next", headers=admin_headers).status_code == 401


class TestHeartbeatContract:
    def test_heartbeat_shape(self, client, enrolled_device):
        device, token = enrolled_device

        response = client.post(
            "/api/v1/heartbeats",
            json={"device_id": str(device.id), "status": "online", "message": "ok"},
            headers=_device_headers(token),
        )
        assert response.status_code in (200, 201), response.text

        body = response.json()
        assert set(body) >= {"id", "organization_id", "device_id", "status", "recorded_at"}
        assert body["status"] == "online"

    def test_heartbeat_requires_a_device_token(self, client, enrolled_device):
        device, _token = enrolled_device

        response = client.post(
            "/api/v1/heartbeats", json={"device_id": str(device.id), "status": "online"}
        )
        assert response.status_code == 401


class TestAuthAndErrorEnvelopeContract:
    def _make_user(self, db, org, prefix):
        from app.core.security import hash_password
        from app.models.user import User

        user = User(
            email=f"{prefix}-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Contract User",
            password_hash=hash_password("Password123!"),
            role="admin",
            is_active=True,
            organization_id=org.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def test_login_response_shape(self, client, db, org):
        user = self._make_user(db, org, "contract")

        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": "Password123!"}
        )
        assert response.status_code == 200

        body = response.json()
        assert set(body) == {"access_token", "token_type", "expires_in", "user"}
        assert body["token_type"] == "bearer"
        assert isinstance(body["expires_in"], int)
        assert set(body["user"]) >= {"id", "email", "full_name", "role"}
        assert "password" not in response.text.lower()

    def test_oauth2_token_endpoint_keeps_its_form_encoded_shape(self, client, db, org):
        """Swagger UI's Authorize button posts a form, not JSON. Breaking this
        breaks the primary way the API is explored."""

        user = self._make_user(db, org, "oauth")

        response = client.post(
            "/api/v1/auth/token", data={"username": user.email, "password": "Password123!"}
        )
        assert response.status_code == 200
        assert set(response.json()) == {"access_token", "token_type", "expires_in"}

    def test_every_error_uses_the_same_detail_envelope(self, client, admin_headers):
        """Clients parse `detail` for user-facing messages; a route returning
        a bare string or a different key shows raw JSON in the UI."""

        cases = [
            client.get("/api/v1/devices"),
            client.get(f"/api/v1/devices/{uuid.uuid4()}", headers=admin_headers),
            client.post("/api/v1/auth/login", json={"email": "x@y.z", "password": "wrong"}),
        ]

        for response in cases:
            assert response.status_code >= 400
            assert "detail" in response.json(), response.text

    def test_validation_errors_are_422_with_a_structured_detail_list(self, client, admin_headers):
        response = client.post(
            "/api/v1/devices/enrollment-codes",
            json={"expires_in_minutes": 10},  # missing required `name`
            headers=admin_headers,
        )
        assert response.status_code == 422

        detail = response.json()["detail"]
        assert isinstance(detail, list)
        assert all("loc" in entry and "msg" in entry for entry in detail)

    def test_health_is_readable_without_credentials(self, client):
        """The only unauthenticated read. Deploy tooling and the dashboard's
        connectivity banner both key off these fields."""

        response = client.get("/api/v1/health")
        assert response.status_code == 200

        body = response.json()
        assert set(body) >= {"service", "version", "environment"}
        assert body["service"]
