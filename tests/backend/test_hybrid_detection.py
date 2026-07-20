"""Sprint 4-6 Stage 1 coverage: hybrid detector deterministic scoring, agreement
states, rule precedence (no suppression of critical rules), data-quality
gating, tenant isolation, RBAC."""

import uuid
from datetime import datetime, timedelta, timezone

from app.ml.feature_schemas import LAPTOP_WINDOWS_V1
from app.models.alert import Alert
from app.models.device import Device
from app.models.organization import Organization
from app.models.system_metric import SystemMetric
from app.services import feature_window_service, hybrid_detection_service


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_laptop_device(db, org: Organization, *, criticality: str = "medium") -> Device:
    device = Device(
        hostname=f"laptop-{uuid.uuid4().hex[:8]}",
        display_name="Test Laptop",
        os_name="Windows 11 Pro",
        device_type="desktop",
        agent_type="python_desktop_agent",
        status="online",
        organization_id=org.id,
        criticality=criticality,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def _seed_history(db, device: Device, *, hours: int = 12, interval_minutes: int = 5) -> None:
    now = datetime.now(timezone.utc)
    count = int(hours * 60 / interval_minutes)
    start = now - timedelta(hours=hours)
    for i in range(count):
        db.add(
            SystemMetric(
                organization_id=device.organization_id,
                device_id=device.id,
                event_id=uuid.uuid4(),
                cpu_percent=40.0 + (i % 7),
                memory_percent=55.0 + (i % 5),
                disk_percent=65.0,
                recorded_at=start + timedelta(minutes=i * interval_minutes),
            )
        )
    db.commit()


_NO_RULE = {"fired": False, "severity": None, "alert_ids": [], "alert_types": [], "top_alert_id": None}


def _rule(severity: str) -> dict:
    return {"fired": True, "severity": severity, "alert_ids": ["x"], "alert_types": ["high_cpu"], "top_alert_id": "x"}


# -- deterministic combined scoring (pure functions) ----------------------------


class TestDetectorAgreement:
    def test_all_normal_when_nothing_fires(self):
        assert hybrid_detection_service._detector_agreement(0.9, False, False, False) == "all_normal"

    def test_rule_only(self):
        assert hybrid_detection_service._detector_agreement(0.9, True, False, False) == "rule_only"

    def test_baseline_only(self):
        assert hybrid_detection_service._detector_agreement(0.9, False, True, None) == "baseline_only"

    def test_model_only(self):
        assert hybrid_detection_service._detector_agreement(0.9, False, None, True) == "model_only"

    def test_two_agree(self):
        assert hybrid_detection_service._detector_agreement(0.9, True, True, False) == "two_agree"

    def test_all_agree(self):
        assert hybrid_detection_service._detector_agreement(0.9, True, True, True) == "all_agree"

    def test_detector_conflict_when_rule_silent_and_ml_disagree(self):
        assert hybrid_detection_service._detector_agreement(0.9, False, True, False) == "detector_conflict"

    def test_insufficient_data_when_quality_too_low(self):
        assert hybrid_detection_service._detector_agreement(0.3, False, True, True) == "insufficient_data"

    def test_insufficient_data_when_no_statistical_detector_available(self):
        assert hybrid_detection_service._detector_agreement(0.9, False, None, None) == "insufficient_data"


# -- rule precedence: AI must never suppress or downgrade a critical rule -------


class TestCombinedSeverity:
    def test_rule_never_suppressed_even_when_ai_says_normal(self):
        assert hybrid_detection_service._combined_severity(_rule("critical"), "rule_only", "low") == "critical"

    def test_critical_rule_wins_even_against_conflicting_ai_signal(self):
        assert hybrid_detection_service._combined_severity(_rule("critical"), "detector_conflict", "low") == "critical"

    def test_warning_rule_not_downgraded_by_normal_ai(self):
        assert hybrid_detection_service._combined_severity(_rule("warning"), "all_normal", "low") == "warning"

    def test_ai_all_agree_raises_to_warning_without_a_rule(self):
        assert hybrid_detection_service._combined_severity(_NO_RULE, "all_agree", "high") == "warning"

    def test_single_weak_signal_alone_stays_info(self):
        assert hybrid_detection_service._combined_severity(_NO_RULE, "baseline_only", "low") == "info"
        assert hybrid_detection_service._combined_severity(_NO_RULE, "model_only", "low") == "info"


class TestOperationalRisk:
    def test_low_criticality_no_persistence_is_low_risk(self):
        assert hybrid_detection_service._operational_risk("info", "low", 0, False, 0) == "low"

    def test_high_criticality_persistence_incident_and_failures_is_high_risk(self):
        assert hybrid_detection_service._operational_risk("critical", "high", 5, True, 2) == "high"


# -- API: pipeline run, rule precedence, review, tenant isolation, RBAC ---------


class TestHybridDetectionApi:
    def test_pipeline_run_creates_decisions(self, client, db, org, admin_headers):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)

        run_resp = client.post(
            "/api/v1/hybrid/decisions/run", json={"device_id": str(device.id)}, headers=admin_headers
        )
        assert run_resp.status_code == 200, run_resp.text
        body = run_resp.json()
        assert body["devices_processed"] == 1
        assert body["windows_scored"] > 0
        assert body["decisions_created"] > 0

        list_resp = client.get(f"/api/v1/hybrid/decisions?device_id={device.id}", headers=admin_headers)
        assert list_resp.status_code == 200
        decisions = list_resp.json()
        assert len(decisions) > 0
        assert all(d["scoring_policy_version"] == "v1" for d in decisions)
        assert all(d["review_status"] == "unreviewed" for d in decisions)

    def test_pipeline_run_is_idempotent(self, client, db, org, admin_headers):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)

        first = client.post(
            "/api/v1/hybrid/decisions/run", json={"device_id": str(device.id)}, headers=admin_headers
        ).json()
        second = client.post(
            "/api/v1/hybrid/decisions/run", json={"device_id": str(device.id)}, headers=admin_headers
        ).json()

        assert first["decisions_created"] > 0
        assert second["decisions_created"] == 0

    def test_critical_rule_alert_is_never_suppressed_by_hybrid_pipeline(self, client, db, org, admin_headers):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()
        assert len(windows) >= 6

        target_window = windows[-1]
        alert = Alert(
            organization_id=device.organization_id,
            device_id=device.id,
            alert_type="high_cpu",
            severity="critical",
            message="CPU at 97%",
            created_at=target_window.window_start + timedelta(minutes=1),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        run_resp = client.post(
            "/api/v1/hybrid/decisions/run", json={"device_id": str(device.id)}, headers=admin_headers
        )
        assert run_resp.status_code == 200, run_resp.text

        list_resp = client.get(f"/api/v1/hybrid/decisions?device_id={device.id}", headers=admin_headers)
        by_window = {d["feature_window_id"]: d for d in list_resp.json()}
        target_decision = by_window[str(target_window.id)]

        assert target_decision["combined_severity"] == "critical"
        assert target_decision["rule_result"]["fired"] is True
        assert target_decision["alert_id"] == str(alert.id)

    def test_review_sets_reviewer_and_timestamp(self, client, db, org, admin_headers, admin_user):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        client.post("/api/v1/hybrid/decisions/run", json={"device_id": str(device.id)}, headers=admin_headers)
        decision_id = client.get(
            f"/api/v1/hybrid/decisions?device_id={device.id}", headers=admin_headers
        ).json()[0]["id"]

        review_resp = client.patch(
            f"/api/v1/hybrid/decisions/{decision_id}/review",
            json={"review_status": "expected_change", "review_note": "planned maintenance window"},
            headers=admin_headers,
        )
        assert review_resp.status_code == 200, review_resp.text
        body = review_resp.json()
        assert body["review_status"] == "expected_change"
        assert body["reviewed_by"] == str(admin_user.id)
        assert body["reviewed_at"] is not None

    def test_tenant_isolation_cross_org_404(self, client, db, org, admin_headers):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        client.post("/api/v1/hybrid/decisions/run", json={"device_id": str(device.id)}, headers=admin_headers)
        decision_id = client.get(
            f"/api/v1/hybrid/decisions?device_id={device.id}", headers=admin_headers
        ).json()[0]["id"]

        from app.core.security import create_access_token, hash_password
        from app.models.user import User

        other_org = Organization(name=f"Other {uuid.uuid4().hex[:8]}", slug=f"other-{uuid.uuid4().hex[:8]}")
        db.add(other_org)
        db.commit()
        other_admin = User(
            email=f"other-admin-{uuid.uuid4().hex[:6]}@test.local",
            full_name="Other Admin",
            password_hash=hash_password("x"),
            role="admin",
            organization_id=other_org.id,
        )
        db.add(other_admin)
        db.commit()
        other_headers = _auth(create_access_token(subject=str(other_admin.id)))

        resp = client.get(f"/api/v1/hybrid/decisions/{decision_id}", headers=other_headers)
        assert resp.status_code == 404

        list_resp = client.get("/api/v1/hybrid/decisions", headers=other_headers)
        assert list_resp.status_code == 200
        assert list_resp.json() == []

    def test_viewer_can_read_but_not_review_or_run_pipeline(self, client, db, org, admin_headers):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        client.post("/api/v1/hybrid/decisions/run", json={"device_id": str(device.id)}, headers=admin_headers)

        from app.core.security import create_access_token, hash_password
        from app.models.user import User

        viewer = User(
            email=f"viewer-{uuid.uuid4().hex[:6]}@test.local",
            full_name="Viewer",
            password_hash=hash_password("x"),
            role="viewer",
            organization_id=org.id,
        )
        db.add(viewer)
        db.commit()
        viewer_headers = _auth(create_access_token(subject=str(viewer.id)))

        list_resp = client.get("/api/v1/hybrid/decisions", headers=viewer_headers)
        assert list_resp.status_code == 200

        run_resp = client.post(
            "/api/v1/hybrid/decisions/run", json={"device_id": str(device.id)}, headers=viewer_headers
        )
        assert run_resp.status_code == 403

        decision_id = list_resp.json()[0]["id"]
        review_resp = client.patch(
            f"/api/v1/hybrid/decisions/{decision_id}/review",
            json={"review_status": "true_positive"},
            headers=viewer_headers,
        )
        assert review_resp.status_code == 403
