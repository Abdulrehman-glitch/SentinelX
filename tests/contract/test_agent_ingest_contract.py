"""Wire contract for the agent-facing ingestion endpoints.

Breaking any assertion in this file means a shipped agent stops working. The
desktop agent, the Android agent and the embedded bridge all encode these
shapes; none of them can be updated in lockstep with the backend, so the
contract has to be the thing that stays still.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest


def _device_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestEnrolmentContract:
    def test_enrolment_code_is_returned_once_and_only_previewed_afterwards(
        self, client, admin_headers
    ):
        created = client.post(
            "/api/v1/devices/enrollment-codes",
            json={"name": "contract device", "expires_in_minutes": 10},
            headers=admin_headers,
        )
        assert created.status_code == 201

        body = created.json()
        assert set(body) >= {
            "id",
            "organization_id",
            "name",
            "code",
            "code_preview",
            "expires_at",
            "created_at",
        }
        raw_code = body["code"]

        listed = client.get("/api/v1/devices/enrollment-codes", headers=admin_headers)
        assert listed.status_code == 200
        assert raw_code not in listed.text, "the raw code must never be readable again"

    def test_enrolment_response_carries_the_device_and_a_one_time_token(
        self, client, admin_headers
    ):
        code = client.post(
            "/api/v1/devices/enrollment-codes",
            json={"name": "contract device", "expires_in_minutes": 10},
            headers=admin_headers,
        ).json()["code"]

        response = client.post(
            "/api/v1/devices/enroll",
            json={
                "enrollment_code": code,
                "hostname": f"contract-{uuid.uuid4().hex[:8]}",
                "os_name": "TestOS 1.0",
                "device_type": "desktop",
                "agent_type": "python_desktop_agent",
                "agent_version": "3.0.0",
            },
        )
        assert response.status_code == 201

        body = response.json()
        assert set(body) == {"device", "credential_id", "device_token"}
        assert set(body["device"]) >= {"id", "organization_id", "hostname", "status"}

    def test_device_token_uses_the_v2_self_identifying_format(self, enrolled_device):
        """`sxa_<32 hex>.<secret>` — the embedded credential id is what makes
        resolution O(1) instead of one argon2 verification per active
        credential in the fleet. An agent storing a token of another shape
        would be rejected."""

        _device, token = enrolled_device

        assert token.startswith("sxa_")
        prefix, _, secret = token.partition(".")
        assert len(prefix) == len("sxa_") + 32
        int(prefix[4:], 16)  # raises if the credential id is not hex
        assert secret

    def test_an_enrolment_code_is_single_use(self, client, admin_headers):
        code = client.post(
            "/api/v1/devices/enrollment-codes",
            json={"name": "single use", "expires_in_minutes": 10},
            headers=admin_headers,
        ).json()["code"]

        payload = {
            "enrollment_code": code,
            "hostname": f"first-{uuid.uuid4().hex[:8]}",
            "device_type": "desktop",
            "agent_type": "python_desktop_agent",
        }
        assert client.post("/api/v1/devices/enroll", json=payload).status_code == 201

        payload["hostname"] = f"second-{uuid.uuid4().hex[:8]}"
        second = client.post("/api/v1/devices/enroll", json=payload)
        assert second.status_code in (400, 401, 403, 409), second.text

    def test_enrolment_rejects_an_unknown_code(self, client):
        response = client.post(
            "/api/v1/devices/enroll",
            json={
                "enrollment_code": "sxe_" + uuid.uuid4().hex,
                "hostname": f"nope-{uuid.uuid4().hex[:8]}",
                "device_type": "desktop",
                "agent_type": "python_desktop_agent",
            },
        )
        assert response.status_code in (400, 401, 403)


class TestSingleMetricContract:
    def test_accepted_shape_and_response_envelope(self, client, enrolled_device):
        device, token = enrolled_device

        response = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(device.id),
                "cpu_percent": 42.5,
                "memory_percent": 61.0,
                "disk_percent": 70.25,
            },
            headers=_device_headers(token),
        )
        assert response.status_code == 201, response.text

        body = response.json()
        assert set(body) == {"metric", "alerts_created", "duplicate"}
        assert body["duplicate"] is False

        metric = body["metric"]
        assert set(metric) >= {
            "id",
            "organization_id",
            "device_id",
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "recorded_at",
        }
        assert metric["cpu_percent"] == 42.5

    def test_null_cpu_is_accepted_and_preserved_as_null(self, client, enrolled_device):
        """None means "could not be read". Coercing it to 0 would look like an
        idle machine, which silently poisons the statistical baseline — the
        Android agent relies on this distinction."""

        device, token = enrolled_device

        response = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(device.id),
                "cpu_percent": None,
                "memory_percent": 10.0,
                "disk_percent": 10.0,
            },
            headers=_device_headers(token),
        )
        assert response.status_code == 201
        assert response.json()["metric"]["cpu_percent"] is None

    @pytest.mark.parametrize(
        "field,value",
        [
            ("memory_percent", 101),
            ("memory_percent", -1),
            ("disk_percent", 100.1),
            ("cpu_percent", 1000),
        ],
    )
    def test_out_of_range_percentages_are_refused(self, client, enrolled_device, field, value):
        device, token = enrolled_device
        payload = {
            "device_id": str(device.id),
            "cpu_percent": 1.0,
            "memory_percent": 1.0,
            "disk_percent": 1.0,
            field: value,
        }

        response = client.post("/api/v1/metrics", json=payload, headers=_device_headers(token))
        assert response.status_code == 422

    def test_event_id_makes_ingestion_idempotent(self, client, enrolled_device):
        """An agent that retries after a timeout must not double-count. This
        is what lets the offline queue flush safely."""

        device, token = enrolled_device
        payload = {
            "device_id": str(device.id),
            "event_id": str(uuid.uuid4()),
            "cpu_percent": 5.0,
            "memory_percent": 5.0,
            "disk_percent": 5.0,
        }

        first = client.post("/api/v1/metrics", json=payload, headers=_device_headers(token))
        second = client.post("/api/v1/metrics", json=payload, headers=_device_headers(token))

        assert first.status_code == 201
        assert first.json()["duplicate"] is False
        assert second.json()["duplicate"] is True
        assert second.json()["metric"]["id"] == first.json()["metric"]["id"]


class TestBatchMetricContract:
    def test_batch_preserves_each_samples_own_recorded_at(self, client, db, enrolled_device):
        """The property the whole offline-queue design rests on: a late flush
        must land as real history, not as a spike at upload time."""

        from app.models.system_metric import SystemMetric

        device, token = enrolled_device
        base = datetime.now(timezone.utc) - timedelta(hours=2)
        samples = [
            {
                "event_id": str(uuid.uuid4()),
                "cpu_percent": 10.0 + index,
                "memory_percent": 20.0,
                "disk_percent": 30.0,
                "recorded_at": (base + timedelta(minutes=index)).isoformat(),
            }
            for index in range(3)
        ]

        response = client.post(
            "/api/v1/metrics/batch",
            json={"device_id": str(device.id), "samples": samples},
            headers=_device_headers(token),
        )
        assert response.status_code == 201, response.text

        body = response.json()
        assert set(body) == {"stored", "duplicates", "alerts_created", "latest"}
        assert body["stored"] == 3

        stored = db.query(SystemMetric).filter(SystemMetric.device_id == device.id).all()
        earliest = min(row.recorded_at for row in stored)
        if earliest.tzinfo is None:
            earliest = earliest.replace(tzinfo=timezone.utc)

        # Stored roughly two hours ago, not "now" — a minute of tolerance.
        assert abs((earliest - base).total_seconds()) < 60

    def test_batch_deduplicates_by_event_id(self, client, enrolled_device):
        device, token = enrolled_device
        payload = {
            "device_id": str(device.id),
            "samples": [
                {
                    "event_id": str(uuid.uuid4()),
                    "cpu_percent": 1.0,
                    "memory_percent": 2.0,
                    "disk_percent": 3.0,
                }
            ],
        }

        client.post("/api/v1/metrics/batch", json=payload, headers=_device_headers(token))
        again = client.post("/api/v1/metrics/batch", json=payload, headers=_device_headers(token))

        assert again.status_code == 201
        assert again.json()["duplicates"] == 1
        assert again.json()["stored"] == 0

    def test_batch_size_is_bounded(self, client, enrolled_device):
        """An unbounded batch is a free amplification primitive for an
        authenticated-but-hostile agent."""

        device, token = enrolled_device
        oversized = [
            {"cpu_percent": 1.0, "memory_percent": 1.0, "disk_percent": 1.0} for _ in range(501)
        ]

        response = client.post(
            "/api/v1/metrics/batch",
            json={"device_id": str(device.id), "samples": oversized},
            headers=_device_headers(token),
        )
        assert response.status_code == 422

    def test_empty_batch_is_refused(self, client, enrolled_device):
        device, token = enrolled_device

        response = client.post(
            "/api/v1/metrics/batch",
            json={"device_id": str(device.id), "samples": []},
            headers=_device_headers(token),
        )
        assert response.status_code == 422


class TestCredentialBoundaryContract:
    def test_ingestion_requires_a_device_token(self, client, enrolled_device):
        device, _token = enrolled_device

        response = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(device.id),
                "cpu_percent": 1.0,
                "memory_percent": 1.0,
                "disk_percent": 1.0,
            },
        )
        assert response.status_code == 401

    def test_a_revoked_device_token_stops_working_immediately(self, client, db, enrolled_device):
        from app.models.device_credential import DeviceCredential

        device, token = enrolled_device
        payload = {
            "device_id": str(device.id),
            "cpu_percent": 1.0,
            "memory_percent": 1.0,
            "disk_percent": 1.0,
        }
        first = client.post("/api/v1/metrics", json=payload, headers=_device_headers(token))
        assert first.status_code == 201

        credential = db.query(DeviceCredential).filter_by(device_id=device.id).one()
        credential.is_active = False
        db.commit()

        after = client.post("/api/v1/metrics", json=payload, headers=_device_headers(token))
        assert after.status_code == 401

    def test_a_garbage_token_is_rejected_without_a_fleet_wide_scan(self, client, enrolled_device):
        """Legacy opaque tokens cost one argon2 verification per active
        credential, which is an unauthenticated CPU-exhaustion amplifier. The
        v2 format is required, so an unrecognised shape fails fast."""

        device, _token = enrolled_device

        response = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(device.id),
                "cpu_percent": 1.0,
                "memory_percent": 1.0,
                "disk_percent": 1.0,
            },
            headers=_device_headers("not-a-sentinelx-token"),
        )
        assert response.status_code == 401
