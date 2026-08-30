"""Pairing sessions: QR payload shape, live status derivation, tenant scoping.

A pairing session is an enrollment_codes row plus derived status — these tests
walk the whole console flow: open a session, enrol with its code through the
real /devices/enroll path, post telemetry, and watch the status move
waiting → enrolled → telemetry_live.
"""

import json
import uuid

from app.core.security import hash_password
from app.models.user import User
from helpers import auth_headers_for


def _open_session(client, admin_headers, **overrides):
    payload = {"platform": "android", **overrides}
    resp = client.post("/api/v1/pairing/sessions", json=payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestPairingSession:
    def test_qr_payload_carries_code_and_url_never_a_token(self, client, admin_headers):
        session = _open_session(client, admin_headers)
        qr = json.loads(session["qr_payload"])
        assert qr["t"] == "sentinelx-pair"
        assert qr["v"] == 1
        assert qr["code"] == session["code"]
        assert qr["code"].startswith("sxe_")
        assert qr["url"] == session["backend_url"]
        # No device token exists yet, and nothing sxa_-shaped may appear.
        assert "sxa_" not in session["qr_payload"]

    def test_backend_url_rejects_non_host_shapes(self, client, admin_headers):
        resp = client.post(
            "/api/v1/pairing/sessions",
            json={"platform": "android", "backend_url": "192.168.1.5:8000/steal?x=1"},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_chosen_host_is_used_verbatim(self, client, admin_headers):
        session = _open_session(client, admin_headers, backend_url="192.168.7.7:8000")
        assert session["backend_url"] == "http://192.168.7.7:8000"

    def test_status_walks_waiting_enrolled_telemetry_live(self, client, admin_headers):
        session = _open_session(client, admin_headers)

        status = client.get(f"/api/v1/pairing/sessions/{session['id']}", headers=admin_headers)
        assert status.status_code == 200
        assert status.json()["status"] == "waiting"

        enroll = client.post(
            "/api/v1/devices/enroll",
            json={
                "enrollment_code": session["code"],
                "hostname": f"paired-{uuid.uuid4().hex[:8]}",
                "os_name": "TestOS",
                "device_type": "mobile",
                "agent_type": "android_mobile_agent",
            },
        )
        assert enroll.status_code == 201, enroll.text
        device_token = enroll.json()["device_token"]
        device_id = enroll.json()["device"]["id"]

        status = client.get(f"/api/v1/pairing/sessions/{session['id']}", headers=admin_headers).json()
        assert status["status"] == "enrolled"
        assert status["device"] is not None

        metrics = client.post(
            "/api/v1/metrics",
            json={"device_id": device_id, "cpu_percent": 10.0, "memory_percent": 20.0, "disk_percent": 30.0},
            headers={"Authorization": f"Bearer {device_token}"},
        )
        assert metrics.status_code in (200, 201), metrics.text

        status = client.get(f"/api/v1/pairing/sessions/{session['id']}", headers=admin_headers).json()
        assert status["status"] == "telemetry_live"
        assert status["last_telemetry_at"] is not None

    def test_other_org_admin_cannot_see_session(self, client, admin_headers, db):
        session = _open_session(client, admin_headers)

        from app.models.organization import Organization

        other_org = Organization(name=f"Other {uuid.uuid4().hex[:6]}", slug=f"other-{uuid.uuid4().hex[:6]}")
        db.add(other_org)
        db.flush()
        outsider = User(
            email=f"outsider-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Outside Admin",
            password_hash=hash_password("Password123!"),
            role="admin",
            is_active=True,
            organization_id=other_org.id,
        )
        db.add(outsider)
        db.commit()
        db.refresh(outsider)

        resp = client.get(
            f"/api/v1/pairing/sessions/{session['id']}",
            headers=auth_headers_for(db, outsider),
        )
        assert resp.status_code == 404

    def test_viewer_cannot_open_sessions(self, client, db, org):
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

        resp = client.post(
            "/api/v1/pairing/sessions",
            json={"platform": "android"},
            headers=auth_headers_for(db, viewer),
        )
        assert resp.status_code == 403

    def test_hosts_endpoint_returns_port(self, client, admin_headers):
        resp = client.get("/api/v1/pairing/hosts", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["hosts"], list)
        assert isinstance(body["port"], int)
