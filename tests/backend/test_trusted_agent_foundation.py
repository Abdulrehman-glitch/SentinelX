"""Sprint-1 coverage: enrolment, credential lifecycle, idempotent ingestion."""

import uuid
from datetime import datetime, timedelta, timezone

from app.models.device_credential import DeviceCredential
from app.models.enrollment_code import EnrollmentCode
from app.models.system_metric import SystemMetric


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _sample(event_id=None, cpu=50.0, memory=60.0, disk=70.0, **extra):
    body = {"cpu_percent": cpu, "memory_percent": memory, "disk_percent": disk, **extra}
    if event_id is not None:
        body["event_id"] = event_id
    return body


# -- registration & enrolment ------------------------------------------------

class TestRegistrationSecurity:
    def test_anonymous_register_rejected(self, client):
        resp = client.post("/api/v1/devices/register", json={"hostname": "rogue-host"})
        assert resp.status_code == 401

    def test_enroll_with_bad_code_rejected(self, client):
        resp = client.post(
            "/api/v1/devices/enroll",
            json={"enrollment_code": "sxe_deadbeef", "hostname": "x", "os_name": "y"},
        )
        assert resp.status_code == 401

    def test_enroll_happy_path_issues_v2_token(self, enrolled_device):
        device, token = enrolled_device
        assert token.startswith("sxa_")
        assert device.status == "online"

    def test_enrollment_code_is_single_use(self, client, admin_headers):
        code = client.post(
            "/api/v1/devices/enrollment-codes",
            json={"name": "single use", "expires_in_minutes": 10},
            headers=admin_headers,
        ).json()["code"]

        first = client.post(
            "/api/v1/devices/enroll",
            json={"enrollment_code": code, "hostname": f"h-{uuid.uuid4().hex[:8]}", "os_name": "t"},
        )
        assert first.status_code == 201

        second = client.post(
            "/api/v1/devices/enroll",
            json={"enrollment_code": code, "hostname": f"h-{uuid.uuid4().hex[:8]}", "os_name": "t"},
        )
        assert second.status_code == 401

    def test_expired_code_rejected(self, client, admin_headers, db):
        resp = client.post(
            "/api/v1/devices/enrollment-codes",
            json={"name": "expiring", "expires_in_minutes": 10},
            headers=admin_headers,
        )
        code_id = uuid.UUID(resp.json()["id"])
        code_row = db.get(EnrollmentCode, code_id)
        code_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

        enroll = client.post(
            "/api/v1/devices/enroll",
            json={"enrollment_code": resp.json()["code"], "hostname": "late-host", "os_name": "t"},
        )
        assert enroll.status_code == 401

    def test_viewer_cannot_mint_codes(self, client, db, org):
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
        token = create_access_token(subject=str(viewer.id))
        resp = client.post(
            "/api/v1/devices/enrollment-codes",
            json={"name": "nope"},
            headers=_auth(token),
        )
        assert resp.status_code == 403


# -- device token auth & credential lifecycle --------------------------------

class TestCredentialLifecycle:
    def test_device_token_authenticates_and_stamps_last_used(self, client, enrolled_device, db):
        device, token = enrolled_device
        resp = client.post(
            "/api/v1/metrics",
            json={"device_id": str(device.id), **_sample()},
            headers=_auth(token),
        )
        assert resp.status_code == 201

        cred = db.query(DeviceCredential).filter_by(device_id=device.id).one()
        assert cred.last_used_at is not None

    def test_rotation_revokes_old_on_first_use_of_new(self, client, enrolled_device, db):
        device, old_token = enrolled_device

        rotate = client.post("/api/v1/device-credentials/rotate", headers=_auth(old_token))
        assert rotate.status_code == 201
        new_token = rotate.json()["token"]
        assert new_token.startswith("sxa_")

        # Old token still valid until the new one is used (agent-safe handover).
        assert client.post(
            "/api/v1/metrics",
            json={"device_id": str(device.id), **_sample(event_id=str(uuid.uuid4()))},
            headers=_auth(old_token),
        ).status_code == 201

        # First use of the new token acknowledges rotation and kills the old one.
        assert client.post(
            "/api/v1/metrics",
            json={"device_id": str(device.id), **_sample(event_id=str(uuid.uuid4()))},
            headers=_auth(new_token),
        ).status_code == 201

        assert client.post(
            "/api/v1/metrics",
            json={"device_id": str(device.id), **_sample(event_id=str(uuid.uuid4()))},
            headers=_auth(old_token),
        ).status_code == 401

    def test_revoke_self_invalidates_token(self, client, enrolled_device):
        device, token = enrolled_device
        assert client.post("/api/v1/device-credentials/revoke-self", headers=_auth(token)).status_code == 204
        assert client.post(
            "/api/v1/metrics",
            json={"device_id": str(device.id), **_sample()},
            headers=_auth(token),
        ).status_code == 401


# -- idempotent ingestion & telemetry contract --------------------------------

class TestIdempotentIngestion:
    def test_single_metric_retry_is_deduplicated(self, client, enrolled_device):
        device, token = enrolled_device
        event_id = str(uuid.uuid4())
        body = {"device_id": str(device.id), **_sample(event_id=event_id)}

        first = client.post("/api/v1/metrics", json=body, headers=_auth(token))
        assert first.status_code == 201
        assert first.json()["duplicate"] is False

        retry = client.post("/api/v1/metrics", json=body, headers=_auth(token))
        assert retry.status_code == 201
        assert retry.json()["duplicate"] is True
        assert retry.json()["metric"]["id"] == first.json()["metric"]["id"]

    def test_batch_retry_and_intra_batch_dupes(self, client, enrolled_device, db):
        device, token = enrolled_device
        e1, e2 = str(uuid.uuid4()), str(uuid.uuid4())
        samples = [_sample(event_id=e1), _sample(event_id=e2), _sample(event_id=e2)]

        first = client.post(
            "/api/v1/metrics/batch",
            json={"device_id": str(device.id), "samples": samples},
            headers=_auth(token),
        )
        assert first.status_code == 201
        assert first.json()["stored"] == 2
        assert first.json()["duplicates"] == 1

        retry = client.post(
            "/api/v1/metrics/batch",
            json={"device_id": str(device.id), "samples": samples},
            headers=_auth(token),
        )
        assert retry.json()["stored"] == 0
        assert retry.json()["duplicates"] == 3

        stored = db.query(SystemMetric).filter_by(device_id=device.id).count()
        assert stored == 2

    def test_null_cpu_and_mobile_extras_accepted(self, client, enrolled_device):
        device, token = enrolled_device
        resp = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(device.id),
                **_sample(
                    event_id=str(uuid.uuid4()),
                    cpu=None,
                    battery_percent=44,
                    battery_charging=True,
                    battery_temperature_c=31.5,
                    thermal_status="light",
                    network_transport="wifi",
                    network_validated=True,
                    network_metered=False,
                ),
            },
            headers=_auth(token),
        )
        assert resp.status_code == 201
        metric = resp.json()["metric"]
        assert metric["cpu_percent"] is None
        assert metric["thermal_status"] == "light"
        assert metric["network_metered"] is False

    def test_fallback_alerts_respect_cooldown(self, client, enrolled_device, db):
        device, token = enrolled_device
        hot = lambda: _sample(event_id=str(uuid.uuid4()), cpu=99.0)  # noqa: E731

        first = client.post(
            "/api/v1/metrics", json={"device_id": str(device.id), **hot()}, headers=_auth(token)
        )
        assert first.json()["alerts_created"] >= 1

        # Same breach seconds later must be suppressed, not re-alerted.
        second = client.post(
            "/api/v1/metrics", json={"device_id": str(device.id), **hot()}, headers=_auth(token)
        )
        assert second.json()["alerts_created"] == 0
