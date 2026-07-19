"""Sprint-3 coverage: command state machine, policy engine, Ed25519 signing,
recovery-command API, agent command API, AI-proposal boundary, tenant
isolation and RBAC."""

import uuid
from base64 import b64decode
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.core.security import create_access_token, get_recovery_public_key_b64, hash_password
from app.models.anomaly_model import AnomalyModel
from app.models.anomaly_prediction import AnomalyPrediction
from app.models.organization import Organization
from app.models.recovery_command import RecoveryCommand
from app.models.recovery_command_event import RecoveryCommandEvent
from app.models.recovery_policy import RecoveryPolicy
from app.models.telemetry_feature_window import TelemetryFeatureWindow
from app.models.user import User
from app.services import agent_capability_service, recovery_command_service
from app.services.recovery_command_service import RecoveryCommandError, build_canonical_payload
from app.services.recovery_command_state_machine import (
    TERMINAL_STATUSES,
    VALID_TRANSITIONS,
    IllegalTransitionError,
    transition,
)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_policy(
    db,
    *,
    action_type: str,
    risk_level: str = "low",
    approval_mode: str = "auto",
    cooldown_seconds: int = 300,
    daily_execution_limit: int = 5,
    verification_window_seconds: int = 300,
    organization_id=None,
) -> RecoveryPolicy:
    existing = (
        db.query(RecoveryPolicy)
        .filter(RecoveryPolicy.organization_id == organization_id, RecoveryPolicy.action_type == action_type)
        .first()
    )
    if existing is not None:
        return existing

    policy = RecoveryPolicy(
        id=uuid.uuid4(),
        organization_id=organization_id,
        device_class=None,
        action_type=action_type,
        trigger_conditions=None,
        risk_level=risk_level,
        approval_mode=approval_mode,
        cooldown_seconds=cooldown_seconds,
        daily_execution_limit=daily_execution_limit,
        verification_window_seconds=verification_window_seconds,
        enabled=True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def _register_capability(db, *, device_id, organization_id, action_type: str) -> None:
    agent_capability_service.upsert_capabilities(
        db,
        device_id=device_id,
        organization_id=organization_id,
        agent_type="python_desktop_agent",
        agent_version="3.1.0",
        capabilities=[{"action_type": action_type, "action_version": "1", "local_risk_level": "low"}],
    )
    db.commit()


class TestStateMachine:
    def test_legal_transition_applies_and_logs_event(self, db, org, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="collect_diagnostics")

        cmd = recovery_command_service.create_command(
            db,
            organization_id=org.id,
            device_id=device.id,
            action_type="collect_diagnostics",
            parameters={},
            reason="test",
            decision_source="manual",
            actor_type="user",
            actor_id=None,
        )
        db.commit()

        assert cmd.status == "approved"
        events = db.query(RecoveryCommandEvent).filter(RecoveryCommandEvent.command_id == cmd.id).all()
        assert len(events) >= 1
        assert events[-1].new_status == "approved"

    def test_illegal_transition_raises(self, db, org, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="collect_diagnostics")

        cmd = recovery_command_service.create_command(
            db,
            organization_id=org.id,
            device_id=device.id,
            action_type="collect_diagnostics",
            parameters={},
            reason="test",
            decision_source="manual",
            actor_type="user",
            actor_id=None,
        )
        db.commit()

        with pytest.raises(IllegalTransitionError):
            transition(db, cmd, "verified", actor_type="system")

    def test_terminal_states_have_no_outgoing_edges(self):
        for status in TERMINAL_STATUSES:
            assert VALID_TRANSITIONS[status] == set()


class TestPolicyEngine:
    def test_unknown_action_has_no_policy(self, db, org, enrolled_device):
        device, _ = enrolled_device
        with pytest.raises(RecoveryCommandError):
            recovery_command_service.create_command(
                db,
                organization_id=org.id,
                device_id=device.id,
                action_type="nonexistent_action",
                parameters={},
                reason="test",
                decision_source="manual",
                actor_type="user",
                actor_id=None,
            )

    def test_active_command_lock_blocks_second_in_flight_command(self, db, org, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="repair_agent_queue", cooldown_seconds=3600)

        cmd1 = recovery_command_service.create_command(
            db,
            organization_id=org.id,
            device_id=device.id,
            action_type="repair_agent_queue",
            parameters={},
            reason="first",
            decision_source="manual",
            actor_type="user",
            actor_id=None,
        )
        db.commit()
        assert cmd1.status == "approved"

        cmd2 = recovery_command_service.create_command(
            db,
            organization_id=org.id,
            device_id=device.id,
            action_type="repair_agent_queue",
            parameters={},
            reason="second",
            decision_source="manual",
            actor_type="user",
            actor_id=None,
        )
        db.commit()
        assert cmd2.status == "rejected"

    def test_daily_limit_enforced(self, db, org, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="reset_api_connection", cooldown_seconds=0, daily_execution_limit=1)

        prior = RecoveryCommand(
            id=uuid.uuid4(),
            organization_id=org.id,
            device_id=device.id,
            action_type="reset_api_connection",
            parameters_json={},
            risk_level="low",
            decision_source="manual",
            status="verified",
            approval_mode="auto",
        )
        db.add(prior)
        db.commit()

        cmd = recovery_command_service.create_command(
            db,
            organization_id=org.id,
            device_id=device.id,
            action_type="reset_api_connection",
            parameters={},
            reason="second today",
            decision_source="manual",
            actor_type="user",
            actor_id=None,
        )
        db.commit()
        assert cmd.status == "rejected"

    def test_circuit_breaker_opens_after_three_consecutive_failures(self, db, org, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="rotate_agent_logs", cooldown_seconds=0, daily_execution_limit=100)

        now = datetime.now(timezone.utc)
        for i in range(3):
            db.add(
                RecoveryCommand(
                    id=uuid.uuid4(),
                    organization_id=org.id,
                    device_id=device.id,
                    action_type="rotate_agent_logs",
                    parameters_json={},
                    risk_level="low",
                    decision_source="manual",
                    status="failed",
                    approval_mode="auto",
                    created_at=now - timedelta(minutes=i + 1),
                )
            )
        db.commit()

        cmd = recovery_command_service.create_command(
            db,
            organization_id=org.id,
            device_id=device.id,
            action_type="rotate_agent_logs",
            parameters={},
            reason="after 3 failures",
            decision_source="manual",
            actor_type="user",
            actor_id=None,
        )
        db.commit()
        assert cmd.status == "rejected"


class TestSigningAndDispatch:
    def test_sign_verify_roundtrip(self, db, org, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="collect_diagnostics")
        _register_capability(db, device_id=device.id, organization_id=org.id, action_type="collect_diagnostics")

        recovery_command_service.create_command(
            db,
            organization_id=org.id,
            device_id=device.id,
            action_type="collect_diagnostics",
            parameters={"x": 1},
            reason="sign test",
            decision_source="manual",
            actor_type="user",
            actor_id=None,
        )
        db.commit()

        dispatched = recovery_command_service.get_next_command_for_device(db, device)
        db.commit()

        assert dispatched is not None
        assert dispatched.status == "dispatched"
        assert dispatched.signature is not None
        assert dispatched.command_nonce is not None

        canonical = build_canonical_payload(dispatched)
        public_key = Ed25519PublicKey.from_public_bytes(b64decode(get_recovery_public_key_b64()))
        public_key.verify(b64decode(dispatched.signature), canonical.encode("utf-8"))

    def test_tampered_payload_rejected(self, db, org, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="collect_diagnostics")
        _register_capability(db, device_id=device.id, organization_id=org.id, action_type="collect_diagnostics")

        recovery_command_service.create_command(
            db,
            organization_id=org.id,
            device_id=device.id,
            action_type="collect_diagnostics",
            parameters={},
            reason="tamper test",
            decision_source="manual",
            actor_type="user",
            actor_id=None,
        )
        db.commit()

        dispatched = recovery_command_service.get_next_command_for_device(db, device)
        db.commit()

        canonical = build_canonical_payload(dispatched)
        public_key = Ed25519PublicKey.from_public_bytes(b64decode(get_recovery_public_key_b64()))
        with pytest.raises(InvalidSignature):
            public_key.verify(b64decode(dispatched.signature), (canonical + "tampered").encode("utf-8"))

    def test_unsupported_action_rejected_at_dispatch(self, db, org, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="repair_agent_queue")
        # Deliberately no capability registered for this device/action.

        cmd = recovery_command_service.create_command(
            db,
            organization_id=org.id,
            device_id=device.id,
            action_type="repair_agent_queue",
            parameters={},
            reason="no capability",
            decision_source="manual",
            actor_type="user",
            actor_id=None,
        )
        db.commit()
        assert cmd.status == "approved"

        dispatched = recovery_command_service.get_next_command_for_device(db, device)
        db.commit()
        assert dispatched is None
        db.refresh(cmd)
        assert cmd.status == "rejected"

    def test_expired_command_rejected_on_next_touch(self, db, org, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="collect_diagnostics")
        _register_capability(db, device_id=device.id, organization_id=org.id, action_type="collect_diagnostics")

        recovery_command_service.create_command(
            db,
            organization_id=org.id,
            device_id=device.id,
            action_type="collect_diagnostics",
            parameters={},
            reason="expiry test",
            decision_source="manual",
            actor_type="user",
            actor_id=None,
        )
        db.commit()

        dispatched = recovery_command_service.get_next_command_for_device(db, device)
        db.commit()
        assert dispatched.status == "dispatched"

        dispatched.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

        with pytest.raises(RecoveryCommandError):
            recovery_command_service.acknowledge_command(db, dispatched)
        db.commit()
        db.refresh(dispatched)
        assert dispatched.status == "expired"


class TestRecoveryCommandApi:
    def test_create_approve_flow_and_event_history(self, client, db, org, admin_headers, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="restart_sentinelx_agent", risk_level="medium", approval_mode="manual")
        db.commit()

        create_resp = client.post(
            "/api/v1/recovery-commands",
            json={"device_id": str(device.id), "action_type": "restart_sentinelx_agent", "parameters": {}, "reason": "api test"},
            headers=admin_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        command_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == "awaiting_approval"

        approve_resp = client.patch(f"/api/v1/recovery-commands/{command_id}/approve", headers=admin_headers)
        assert approve_resp.status_code == 200, approve_resp.text
        assert approve_resp.json()["status"] == "approved"

        events_resp = client.get(f"/api/v1/recovery-commands/{command_id}/events", headers=admin_headers)
        assert events_resp.status_code == 200, events_resp.text
        assert len(events_resp.json()) >= 2

    def test_reject_and_cancel_and_retry(self, client, db, org, admin_headers, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="restart_allowlisted_service", risk_level="medium", approval_mode="manual")
        db.commit()

        create_resp = client.post(
            "/api/v1/recovery-commands",
            json={"device_id": str(device.id), "action_type": "restart_allowlisted_service", "parameters": {}},
            headers=admin_headers,
        )
        command_id = create_resp.json()["id"]

        reject_resp = client.patch(
            f"/api/v1/recovery-commands/{command_id}/reject",
            json={"reason": "not needed right now"},
            headers=admin_headers,
        )
        assert reject_resp.status_code == 200, reject_resp.text
        assert reject_resp.json()["status"] == "rejected"

        retry_resp = client.post(f"/api/v1/recovery-commands/{command_id}/retry", headers=admin_headers)
        assert retry_resp.status_code == 201, retry_resp.text
        new_id = retry_resp.json()["id"]
        assert new_id != command_id

        cancel_resp = client.patch(f"/api/v1/recovery-commands/{new_id}/cancel", headers=admin_headers)
        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json()["status"] == "rejected"

    def test_viewer_can_read_but_not_create(self, client, db, org, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="collect_diagnostics")

        viewer = User(
            id=uuid.uuid4(),
            organization_id=org.id,
            email=f"viewer-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Test Viewer",
            password_hash=hash_password("Password123!"),
            role="viewer",
            is_active=True,
        )
        db.add(viewer)
        db.commit()
        viewer_headers = _auth(create_access_token(subject=str(viewer.id)))

        list_resp = client.get("/api/v1/recovery-commands", headers=viewer_headers)
        assert list_resp.status_code == 200

        create_resp = client.post(
            "/api/v1/recovery-commands",
            json={"device_id": str(device.id), "action_type": "collect_diagnostics", "parameters": {}},
            headers=viewer_headers,
        )
        assert create_resp.status_code == 403

    def test_tenant_isolation_cross_org_404(self, client, db, org, admin_headers, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="collect_diagnostics")

        create_resp = client.post(
            "/api/v1/recovery-commands",
            json={"device_id": str(device.id), "action_type": "collect_diagnostics", "parameters": {}},
            headers=admin_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        command_id = create_resp.json()["id"]

        other_org = Organization(id=uuid.uuid4(), name="Other Org", slug=f"org-{uuid.uuid4().hex[:8]}")
        db.add(other_org)
        db.commit()
        other_admin = User(
            id=uuid.uuid4(),
            organization_id=other_org.id,
            email=f"admin-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Other Org Admin",
            password_hash=hash_password("Password123!"),
            role="admin",
            is_active=True,
        )
        db.add(other_admin)
        db.commit()
        other_headers = _auth(create_access_token(subject=str(other_admin.id)))

        get_resp = client.get(f"/api/v1/recovery-commands/{command_id}", headers=other_headers)
        assert get_resp.status_code == 404

        list_resp = client.get("/api/v1/recovery-commands", headers=other_headers)
        assert list_resp.status_code == 200
        assert list_resp.json() == []


class TestAgentCommandApi:
    def test_full_agent_lifecycle_completes_and_verifies(self, client, db, org, admin_headers, enrolled_device):
        device, device_token = enrolled_device
        _seed_policy(db, action_type="collect_diagnostics")
        db.commit()

        device_headers = _auth(device_token)
        cap_resp = client.post(
            "/api/v1/agent/capabilities",
            json={
                "agent_type": "python_desktop_agent",
                "agent_version": "3.1.0",
                "capabilities": [{"action_type": "collect_diagnostics", "action_version": "1", "local_risk_level": "low"}],
            },
            headers=device_headers,
        )
        assert cap_resp.status_code == 204, cap_resp.text

        create_resp = client.post(
            "/api/v1/recovery-commands",
            json={"device_id": str(device.id), "action_type": "collect_diagnostics", "parameters": {}},
            headers=admin_headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        assert create_resp.json()["status"] == "approved"
        command_id = create_resp.json()["id"]

        next_resp = client.get("/api/v1/agent/commands/next", headers=device_headers)
        assert next_resp.status_code == 200, next_resp.text
        assert next_resp.json()["id"] == command_id
        assert next_resp.json()["status"] == "dispatched"
        assert next_resp.json()["signature"] is not None

        ack_resp = client.post(f"/api/v1/agent/commands/{command_id}/acknowledge", headers=device_headers)
        assert ack_resp.status_code == 200, ack_resp.text
        assert ack_resp.json()["status"] == "acknowledged"

        # Replay: acknowledging an already-acknowledged command is an illegal
        # transition, rejected with 409 — this is how the state machine
        # blocks a replayed acknowledge without needing a separate ledger.
        replay_resp = client.post(f"/api/v1/agent/commands/{command_id}/acknowledge", headers=device_headers)
        assert replay_resp.status_code == 409

        start_resp = client.post(f"/api/v1/agent/commands/{command_id}/start", headers=device_headers)
        assert start_resp.status_code == 200, start_resp.text
        assert start_resp.json()["status"] == "running"

        complete_resp = client.post(
            f"/api/v1/agent/commands/{command_id}/complete",
            json={
                "result_code": "success",
                "result_message": "diagnostics collected",
                "result_data": {"cpu_percent": 10.0, "memory_percent": 40.0, "disk_percent": 55.0, "uptime_seconds": 3600},
            },
            headers=device_headers,
        )
        assert complete_resp.status_code == 200, complete_resp.text
        assert complete_resp.json()["status"] == "verified"
        assert complete_resp.json()["verification_status"] == "verified"

    def test_wrong_device_cannot_touch_another_devices_command(self, client, db, org, admin_headers, enrolled_device):
        device, _ = enrolled_device
        _seed_policy(db, action_type="collect_diagnostics")
        db.commit()

        create_resp = client.post(
            "/api/v1/recovery-commands",
            json={"device_id": str(device.id), "action_type": "collect_diagnostics", "parameters": {}},
            headers=admin_headers,
        )
        command_id = create_resp.json()["id"]

        code_resp = client.post(
            "/api/v1/devices/enrollment-codes", json={"name": "second-device"}, headers=admin_headers
        )
        assert code_resp.status_code == 201, code_resp.text
        code = code_resp.json()["code"]

        enroll_resp = client.post(
            "/api/v1/devices/enroll",
            json={
                "enrollment_code": code,
                "hostname": f"other-host-{uuid.uuid4().hex[:8]}",
                "os_name": "TestOS",
                "device_type": "desktop",
                "agent_type": "python_desktop_agent",
                "agent_version": "3.1.0",
            },
        )
        assert enroll_resp.status_code == 201, enroll_resp.text
        other_headers = _auth(enroll_resp.json()["device_token"])

        ack_resp = client.post(f"/api/v1/agent/commands/{command_id}/acknowledge", headers=other_headers)
        assert ack_resp.status_code == 404

    def test_unsupported_action_command_is_not_dispatched(self, client, db, org, admin_headers, enrolled_device):
        device, device_token = enrolled_device
        _seed_policy(db, action_type="repair_agent_queue")
        db.commit()

        create_resp = client.post(
            "/api/v1/recovery-commands",
            json={"device_id": str(device.id), "action_type": "repair_agent_queue", "parameters": {}},
            headers=admin_headers,
        )
        assert create_resp.json()["status"] == "approved"

        device_headers = _auth(device_token)
        next_resp = client.get("/api/v1/agent/commands/next", headers=device_headers)
        assert next_resp.status_code == 200
        assert next_resp.json() is None


class TestAIBoundary:
    def test_propose_from_anomaly_goes_through_policy_and_cannot_bypass_approval(
        self, client, db, org, admin_headers, enrolled_device
    ):
        device, _ = enrolled_device
        _seed_policy(db, action_type="restart_sentinelx_agent", risk_level="medium", approval_mode="manual")

        window = TelemetryFeatureWindow(
            id=uuid.uuid4(),
            organization_id=org.id,
            device_id=device.id,
            device_class="laptop_windows_v1",
            feature_schema_version="v1",
            window_start=datetime.now(timezone.utc),
            window_end=datetime.now(timezone.utc),
            sample_count=10,
            quality_score=1.0,
            quality_flags=None,
            features={},
        )
        db.add(window)
        model = AnomalyModel(
            id=uuid.uuid4(),
            name="test_model",
            version="1.0.0",
            device_class="laptop_windows_v1",
            feature_schema_version="v1",
            algorithm="statistical_baseline",
            hyperparameters={},
            dataset_hash="deterministic",
            code_commit=None,
            trained_at=datetime.now(timezone.utc),
            artifact_path=None,
            is_active=True,
        )
        db.add(model)
        db.commit()

        prediction = AnomalyPrediction(
            id=uuid.uuid4(),
            organization_id=org.id,
            device_id=device.id,
            feature_window_id=window.id,
            model_name=model.name,
            model_version=model.version,
            feature_schema_version="v1",
            anomaly_score=5.0,
            threshold=3.0,
            is_anomalous=True,
            confidence="high",
            feature_comparison={},
            explanation="CPU sustained above baseline.",
            shadow_mode=True,
        )
        db.add(prediction)
        db.commit()

        resp = client.post(
            f"/api/v1/recovery-commands/from-anomaly/{prediction.id}",
            json={"action_type": "restart_sentinelx_agent", "parameters": {}},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["decision_source"] == "ai_proposal"
        # Policy demands manual approval — the AI proposal did not bypass it.
        assert body["status"] == "awaiting_approval"
        assert body["model_name"] == "test_model"
        assert body["anomaly_prediction_id"] == str(prediction.id)

    def test_viewer_cannot_propose_recovery(self, client, db, org, enrolled_device):
        device, _ = enrolled_device
        viewer = User(
            id=uuid.uuid4(),
            organization_id=org.id,
            email=f"viewer-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Test Viewer",
            password_hash=hash_password("Password123!"),
            role="viewer",
            is_active=True,
        )
        db.add(viewer)
        db.commit()
        viewer_headers = _auth(create_access_token(subject=str(viewer.id)))

        resp = client.post(
            f"/api/v1/recovery-commands/from-anomaly/{uuid.uuid4()}",
            json={"action_type": "collect_diagnostics", "parameters": {}},
            headers=viewer_headers,
        )
        assert resp.status_code == 403
