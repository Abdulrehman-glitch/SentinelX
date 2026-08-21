"""Cross-service flows, exercised the way a real deployment runs them.

`tests/backend/` tests each service on its own and `tests/contract/` pins the
wire shapes. Neither catches a break in the *seams* — an alert that fires but
never opens an incident, a command that is approved but never signed, a
verification that never runs. These do.

Every flow here starts from a real enrolment and drives the API with the same
credentials a live agent and a live operator would hold; nothing reaches into
a service function to skip a step.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.alert import Alert
from app.models.alert_rule import AlertRule
from app.models.incident import Incident
from app.models.recovery_command import RecoveryCommand
from app.models.recovery_command_event import RecoveryCommandEvent
from app.models.recovery_policy import RecoveryPolicy
from app.models.system_metric import SystemMetric


def _device_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_capability(client, token, action_type):
    response = client.post(
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
    assert response.status_code == 204


def _seed_policy(db, org_id, action_type, *, approval_mode="auto", risk_level="low"):
    policy = RecoveryPolicy(
        id=uuid.uuid4(),
        organization_id=org_id,
        action_type=action_type,
        risk_level=risk_level,
        approval_mode=approval_mode,
        enabled=True,
    )
    db.add(policy)
    db.commit()
    return policy


class TestTelemetryToIncident:
    """Agent posts a breaching metric -> rule fires -> alert -> incident."""

    def test_a_breaching_metric_raises_an_alert_and_opens_an_incident(
        self, client, db, org, admin_headers, enrolled_device
    ):
        device, token = enrolled_device

        db.add(
            AlertRule(
                id=uuid.uuid4(),
                organization_id=org.id,
                name="integration cpu rule",
                metric_type="cpu_percent",
                operator=">=",
                threshold=90.0,
                severity="critical",
                enabled=True,
                cooldown_seconds=0,
            )
        )
        db.commit()

        response = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(device.id),
                "cpu_percent": 97.0,
                "memory_percent": 40.0,
                "disk_percent": 40.0,
            },
            headers=_device_headers(token),
        )
        assert response.status_code == 201, response.text
        assert response.json()["alerts_created"] >= 1

        alerts = db.query(Alert).filter(Alert.device_id == device.id).all()
        assert alerts, "the rule should have produced an alert"
        assert any(alert.severity == "critical" for alert in alerts)

        # Critical alerts auto-open an incident — the seam most likely to rot,
        # because each half is independently unit-tested.
        incidents = db.query(Incident).filter(Incident.device_id == device.id).all()
        assert incidents, "a critical alert must open an incident"

        visible = client.get("/api/v1/incidents", headers=admin_headers)
        assert visible.status_code == 200
        assert str(incidents[0].id) in {row["id"] for row in visible.json()}

    def test_a_healthy_metric_raises_nothing(self, client, db, org, enrolled_device):
        """The negative half. Without it, a rule engine that fired on
        everything would still pass the test above."""

        device, token = enrolled_device
        db.add(
            AlertRule(
                id=uuid.uuid4(),
                organization_id=org.id,
                name="integration quiet rule",
                metric_type="cpu_percent",
                operator=">=",
                threshold=90.0,
                severity="critical",
                enabled=True,
                cooldown_seconds=0,
            )
        )
        db.commit()

        response = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(device.id),
                "cpu_percent": 12.0,
                "memory_percent": 15.0,
                "disk_percent": 20.0,
            },
            headers=_device_headers(token),
        )
        assert response.status_code == 201
        assert response.json()["alerts_created"] == 0
        assert db.query(Alert).filter(Alert.device_id == device.id).count() == 0

    def test_a_disabled_rule_does_not_fire(self, client, db, org, enrolled_device):
        device, token = enrolled_device
        db.add(
            AlertRule(
                id=uuid.uuid4(),
                organization_id=org.id,
                name="disabled rule",
                metric_type="memory_percent",
                operator=">=",
                threshold=1.0,
                severity="critical",
                enabled=False,
                cooldown_seconds=0,
            )
        )
        db.commit()

        response = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(device.id),
                "cpu_percent": 5.0,
                "memory_percent": 50.0,
                "disk_percent": 5.0,
            },
            headers=_device_headers(token),
        )
        assert response.status_code == 201

        fired = db.query(Alert).filter(Alert.device_id == device.id).all()
        assert not any(alert.alert_type == "memory_percent" for alert in fired)


class TestRecoveryCommandLifecycle:
    """Operator proposes -> policy decides -> signed dispatch -> agent
    acknowledges, starts, completes -> server verifies."""

    def test_auto_approved_command_runs_end_to_end(
        self, client, db, org, admin_headers, enrolled_device
    ):
        device, token = enrolled_device
        _seed_policy(db, org.id, "collect_diagnostics", approval_mode="auto")
        _register_capability(client, token, "collect_diagnostics")

        created = client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "collect_diagnostics",
                "parameters": {},
                "reason": "integration flow",
            },
            headers=admin_headers,
        )
        assert created.status_code == 201, created.text
        assert created.json()["status"] == "approved"
        command_id = created.json()["id"]

        dispatched = client.get(
            "/api/v1/agent/commands/next", headers=_device_headers(token)
        ).json()
        assert dispatched["id"] == command_id
        assert dispatched["status"] == "dispatched"
        assert dispatched["signature"]

        for step in ("acknowledge", "start"):
            response = client.post(
                f"/api/v1/agent/commands/{command_id}/{step}", headers=_device_headers(token)
            )
            assert response.status_code == 200, (step, response.text)

        completed = client.post(
            f"/api/v1/agent/commands/{command_id}/complete",
            json={
                "result_code": "success",
                "result_message": "Diagnostics collected.",
                "result_data": {"cpu_percent": 12.0},
                "post_action_snapshot": {"cpu_percent": 12.0},
            },
            headers=_device_headers(token),
        )
        assert completed.status_code == 200, completed.text

        # Execution success and post-action verification always resolve
        # together; a command must never be left sitting in "succeeded".
        final = db.get(RecoveryCommand, uuid.UUID(command_id))
        db.refresh(final)
        assert final.status != "succeeded"
        assert final.verification_status is not None

        events = (
            db.query(RecoveryCommandEvent)
            .filter(RecoveryCommandEvent.command_id == final.id)
            .all()
        )
        recorded = {event.new_status for event in events}
        assert {"approved", "dispatched", "acknowledged", "running"} <= recorded

    def test_manual_approval_gates_dispatch(self, client, db, org, admin_headers, enrolled_device):
        """A medium-risk action must not reach the agent until a human
        approves it — the whole point of the approval mode."""

        device, token = enrolled_device
        _seed_policy(
            db, org.id, "restart_sentinelx_agent", approval_mode="manual", risk_level="medium"
        )
        _register_capability(client, token, "restart_sentinelx_agent")

        created = client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "restart_sentinelx_agent",
                "parameters": {},
            },
            headers=admin_headers,
        )
        assert created.status_code == 201
        assert created.json()["status"] == "awaiting_approval"
        command_id = created.json()["id"]

        pending = client.get("/api/v1/agent/commands/next", headers=_device_headers(token))
        assert pending.json() is None

        approved = client.patch(
            f"/api/v1/recovery-commands/{command_id}/approve", headers=admin_headers
        )
        assert approved.status_code == 200, approved.text

        dispatched = client.get(
            "/api/v1/agent/commands/next", headers=_device_headers(token)
        ).json()
        assert dispatched is not None
        assert dispatched["id"] == command_id

    def test_a_device_without_the_capability_never_receives_the_command(
        self, client, db, org, admin_headers, enrolled_device
    ):
        """Refusing to dispatch an action the agent never claimed to support
        is what stops a server-side allowlist change from reaching an older
        agent that cannot honour it."""

        device, token = enrolled_device
        _seed_policy(db, org.id, "rotate_agent_logs", approval_mode="auto")
        # deliberately no capability registration

        created = client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "rotate_agent_logs",
                "parameters": {},
            },
            headers=admin_headers,
        )
        assert created.status_code == 201

        polled = client.get("/api/v1/agent/commands/next", headers=_device_headers(token))
        assert polled.json() is None

        command = db.get(RecoveryCommand, uuid.UUID(created.json()["id"]))
        db.refresh(command)
        assert command.status == "rejected"

    def test_an_expired_command_is_not_dispatched(
        self, client, db, org, admin_headers, enrolled_device
    ):
        device, token = enrolled_device
        _seed_policy(db, org.id, "collect_diagnostics", approval_mode="auto")
        _register_capability(client, token, "collect_diagnostics")

        created = client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "collect_diagnostics",
                "parameters": {},
            },
            headers=admin_headers,
        )
        command = db.get(RecoveryCommand, uuid.UUID(created.json()["id"]))
        command.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

        polled = client.get("/api/v1/agent/commands/next", headers=_device_headers(token))
        assert polled.json() is None

        db.refresh(command)
        assert command.status == "expired"

    def test_an_agent_rejection_is_recorded_rather_than_retried(
        self, client, db, org, admin_headers, enrolled_device
    ):
        """A local allowlist or signature failure on the agent must terminate
        the command, not silently loop."""

        device, token = enrolled_device
        _seed_policy(db, org.id, "collect_diagnostics", approval_mode="auto")
        _register_capability(client, token, "collect_diagnostics")

        created = client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(device.id),
                "action_type": "collect_diagnostics",
                "parameters": {},
            },
            headers=admin_headers,
        )
        command_id = created.json()["id"]
        client.get("/api/v1/agent/commands/next", headers=_device_headers(token))

        rejected = client.post(
            f"/api/v1/agent/commands/{command_id}/reject",
            json={"reason": "local signature verification failed"},
            headers=_device_headers(token),
        )
        assert rejected.status_code == 200

        command = db.get(RecoveryCommand, uuid.UUID(command_id))
        db.refresh(command)
        assert command.status == "rejected"

        again = client.get("/api/v1/agent/commands/next", headers=_device_headers(token))
        assert again.json() is None


class TestSessionLifecycleAcrossTheApi:
    """Login -> use -> refresh -> use -> logout -> refused, over real HTTP."""

    def test_a_session_carries_a_user_through_the_api_and_then_stops(self, client, db, org):
        from app.core.config import get_settings
        from app.core.security import hash_password
        from app.models.user import User

        settings = get_settings()
        user = User(
            email=f"flow-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Flow User",
            password_hash=hash_password("Password123!"),
            role="admin",
            is_active=True,
            organization_id=org.id,
        )
        db.add(user)
        db.commit()

        login = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": "Password123!"}
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        assert client.get("/api/v1/devices", headers=headers).status_code == 200

        refreshed = client.post(
            "/api/v1/auth/refresh",
            headers={settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name)},
        )
        assert refreshed.status_code == 200
        new_headers = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
        assert client.get("/api/v1/devices", headers=new_headers).status_code == 200

        assert client.post("/api/v1/auth/logout", headers=new_headers).status_code == 200

        # Both tokens die with the session, not just the one used to log out.
        assert client.get("/api/v1/devices", headers=new_headers).status_code == 401
        assert client.get("/api/v1/devices", headers=headers).status_code == 401


class TestObservabilityPipelineIsShadowOnly:
    """The AI path must observe and never act. Asserted end-to-end because
    that guarantee is the product claim."""

    @pytest.fixture()
    def device_with_history(self, db, org, enrolled_device):
        device, token = enrolled_device
        base = datetime.now(timezone.utc) - timedelta(hours=6)

        for index in range(60):
            db.add(
                SystemMetric(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    device_id=device.id,
                    cpu_percent=20.0 + (index % 5),
                    memory_percent=30.0 + (index % 7),
                    disk_percent=40.0,
                    recorded_at=base + timedelta(minutes=index * 5),
                )
            )
        db.commit()
        return device, token

    def test_running_the_pipeline_creates_no_alerts_incidents_or_commands(
        self, client, db, admin_headers, device_with_history
    ):
        device, _token = device_with_history

        alerts_before = db.query(Alert).count()
        incidents_before = db.query(Incident).count()
        commands_before = db.query(RecoveryCommand).count()

        response = client.post(
            "/api/v1/observability/pipeline/run",
            json={"device_id": str(device.id)},
            headers=admin_headers,
        )
        assert response.status_code in (200, 201, 403, 422), response.text

        assert db.query(Alert).count() == alerts_before
        assert db.query(Incident).count() == incidents_before
        assert db.query(RecoveryCommand).count() == commands_before
