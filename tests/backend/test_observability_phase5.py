"""Tests for Sprint 7 Phase 5 (Observability): the request-correlation-ID
middleware, the extended /health payload, device-token auth-failure
logging, and the admin security counters endpoint.
"""

import uuid

from app.core.security import create_access_token, hash_password
from app.models.security_log import SecurityLog
from app.models.user import User


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _metric_payload(**extra) -> dict:
    return {"cpu_percent": 50.0, "memory_percent": 60.0, "disk_percent": 70.0, **extra}


def test_health_reports_uptime_and_readiness(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_status"] == "online"
    assert body["database_status"] == "online"
    assert body["ready"] is True
    assert isinstance(body["uptime_seconds"], (int, float))
    assert body["uptime_seconds"] >= 0


def test_request_id_is_generated_when_absent(client):
    resp = client.get("/api/v1/health")
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) >= 32


def test_request_id_is_echoed_back_when_supplied(client):
    resp = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc-123"})
    assert resp.headers["x-request-id"] == "trace-abc-123"


class TestDeviceAuthFailureLogging:
    def test_missing_device_token_is_logged(self, client, db):
        before = db.query(SecurityLog).filter_by(event_type="device_auth_failure").count()
        resp = client.post(
            "/api/v1/metrics",
            json={"device_id": str(uuid.uuid4()), **_metric_payload()},
        )
        assert resp.status_code == 401
        after = db.query(SecurityLog).filter_by(event_type="device_auth_failure").count()
        assert after == before + 1

    def test_invalid_device_token_is_logged(self, client, db):
        before = db.query(SecurityLog).filter_by(event_type="device_auth_failure").count()
        resp = client.post(
            "/api/v1/metrics",
            json={"device_id": str(uuid.uuid4()), **_metric_payload()},
            headers=_auth("sxa_deadbeefdeadbeefdeadbeefdeadbeef.notreal"),
        )
        assert resp.status_code == 401
        after = db.query(SecurityLog).filter_by(event_type="device_auth_failure").count()
        assert after == before + 1


class TestSecurityCounters:
    def test_viewer_role_forbidden(self, db, org, client):
        viewer = User(
            email=f"viewer-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Viewer",
            password_hash=hash_password("Password123!"),
            role="viewer",
            is_active=True,
            organization_id=org.id,
        )
        db.add(viewer)
        db.commit()
        db.refresh(viewer)
        token = create_access_token(subject=str(viewer.id))

        resp = client.get("/api/v1/security-logs/counters", headers=_auth(token))
        assert resp.status_code == 403

    def test_platform_admin_sees_device_auth_failures_counted(self, db, client):
        platform_admin = User(
            email=f"pa-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Platform Admin",
            password_hash=hash_password("Password123!"),
            role="platform_admin",
            is_active=True,
            organization_id=None,
        )
        db.add(platform_admin)
        db.commit()
        db.refresh(platform_admin)
        pa_headers = _auth(create_access_token(subject=str(platform_admin.id)))

        before = client.get("/api/v1/security-logs/counters", headers=pa_headers).json()

        client.post(
            "/api/v1/metrics",
            json={"device_id": str(uuid.uuid4()), **_metric_payload()},
        )  # missing token -> device_auth_failure, org-agnostic

        after = client.get("/api/v1/security-logs/counters", headers=pa_headers).json()
        assert after["failed_auth_count"] == before["failed_auth_count"] + 1

    def test_tenant_admin_counters_are_scoped_to_a_fresh_org(self, org, admin_headers, client):
        # A brand-new org/admin (unique per test via conftest fixtures) has
        # never had a login failure or recovery command in it.
        resp = client.get("/api/v1/security-logs/counters", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["failed_auth_count"] == 0
        assert body["recovery_command_verification_failures"] == 0
        assert body["telemetry_samples"] == 0
        assert body["window_minutes"] == 1440

    def test_window_minutes_is_capped(self, admin_headers, client):
        resp = client.get(
            "/api/v1/security-logs/counters",
            params={"window_minutes": 999_999},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["window_minutes"] == 10_080
