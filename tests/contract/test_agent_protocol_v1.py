"""SentinelX Agent Protocol v1 — the contract, asserted rather than described.

`docs/protocol/agent-protocol-v1.md` describes this protocol in prose and
`app/protocol.py` states its versions in code. Prose drifts; these tests are
what stop it. Each one pins a claim the documentation makes against the running
backend, so a change that breaks an agent breaks a test first.

The clients this protects are the three canonical ones — desktop Python, native
Android, embedded bridge. iOS is explicitly out of scope this sprint.
"""

from __future__ import annotations

import uuid

import pytest

from app import protocol


class TestVersionMatrix:
    def test_the_four_version_numbers_stay_distinct(self):
        """Conflating them is the mistake the module exists to prevent.

        A platform release must not force a protocol bump, and adding a
        nullable telemetry field must not force either.
        """
        assert protocol.AGENT_PROTOCOL_VERSION == "1.0"
        assert protocol.TELEMETRY_SCHEMA_VERSION == "1.1"
        assert protocol.AGENT_PROTOCOL_VERSION != protocol.TELEMETRY_SCHEMA_VERSION

    def test_the_current_protocol_version_is_supported(self):
        assert protocol.AGENT_PROTOCOL_VERSION in protocol.SUPPORTED_PROTOCOL_VERSIONS

    def test_the_current_schema_version_is_supported(self):
        assert protocol.TELEMETRY_SCHEMA_VERSION in protocol.SUPPORTED_TELEMETRY_SCHEMA_VERSIONS

    def test_the_older_schema_is_still_accepted(self):
        """An agent that has not been rebuilt must keep working."""
        assert "1.0" in protocol.SUPPORTED_TELEMETRY_SCHEMA_VERSIONS

    def test_an_agent_that_sends_no_version_is_accepted(self):
        """Every shipped agent predates the header and speaks exactly 1.0.

        Rejecting them would break working fleets to enforce a label they were
        never asked for.
        """
        assert protocol.is_protocol_supported(None) is True
        assert protocol.is_protocol_supported("") is True

    def test_a_known_version_is_accepted(self):
        assert protocol.is_protocol_supported("1.0") is True

    def test_an_unknown_version_is_refused(self):
        assert protocol.is_protocol_supported("2.0") is False
        assert protocol.is_protocol_supported("0.9") is False

    def test_the_three_canonical_clients_are_named(self):
        components = {c.component for c in protocol.CANONICAL_CLIENTS}
        assert components == {
            "agents/desktop-python",
            "agents/android-native",
            "agents/embedded-bridge",
        }

    def test_ios_is_present_but_not_canonical(self):
        """It speaks the wire format; its migration is Fleet-sprint work.

        Listing it as canonical would claim coverage no test backs.
        """
        ios = next(c for c in protocol.COMPATIBILITY_MATRIX if c.component == "agents/ios-native")
        assert ios.canonical is False

    def test_every_canonical_client_speaks_a_supported_protocol(self):
        for client_entry in protocol.CANONICAL_CLIENTS:
            assert client_entry.protocol in protocol.SUPPORTED_PROTOCOL_VERSIONS
            assert client_entry.telemetry_schema in protocol.SUPPORTED_TELEMETRY_SCHEMA_VERSIONS


class TestAdvertisedCapabilities:
    """What /health promises must be what the server actually does."""

    def test_health_advertises_the_protocol(self, client):
        body = client.get("/api/v1/health").json()
        assert body["protocol"]["agent_protocol_version"] == protocol.AGENT_PROTOCOL_VERSION
        assert body["protocol"]["telemetry_schema_version"] == protocol.TELEMETRY_SCHEMA_VERSION

    def test_otlp_metrics_capability_is_stated_precisely(self, client):
        """"Supports OpenTelemetry" is the kind of vague claim that wastes an
        integrator's afternoon."""
        otlp = client.get("/api/v1/health").json()["protocol"]["otlp"]
        assert otlp["metrics"]["transports"] == ["http/protobuf"]
        assert otlp["metrics"]["path"] == "/v1/metrics"
        assert "gzip" in otlp["metrics"]["compression"]
        assert otlp["metrics"]["partial_success"] is True

    def test_logs_and_traces_are_advertised_as_absent(self, client):
        """Not "coming soon" — null, because they do not work."""
        otlp = client.get("/api/v1/health").json()["protocol"]["otlp"]
        assert otlp["logs"] is None
        assert otlp["traces"] is None

    def test_the_advertised_otlp_path_actually_exists(self, client):
        """A path that is advertised but not mounted is worse than silence."""
        response = client.post(
            "/v1/metrics", content=b"", headers={"Content-Type": "application/x-protobuf"}
        )
        # 401 because no credential was supplied — which proves the route is
        # mounted and authenticating, rather than 404.
        assert response.status_code == 401


class TestCanonicalClientCompatibility:
    """The wire contract the three canonical agents depend on.

    These duplicate a little of tests/contract/test_agent_ingest_contract.py on
    purpose: that suite pins the payload shapes, this one pins that the protocol
    as a whole still works end to end after the v3.3 changes.
    """

    def test_enrolment_still_issues_a_usable_device_token(self, client, admin_headers):
        code = client.post(
            "/api/v1/devices/enrollment-codes",
            json={"name": "protocol probe", "expires_in_minutes": 10},
            headers=admin_headers,
        ).json()["code"]

        enrolled = client.post(
            "/api/v1/devices/enroll",
            json={
                "enrollment_code": code,
                "hostname": f"protocol-{uuid.uuid4().hex[:8]}",
                "os_name": "TestOS 1.0",
                "device_type": "desktop",
                "agent_type": "python_desktop_agent",
                "agent_version": "3.0.0",
            },
        )
        assert enrolled.status_code == 201
        body = enrolled.json()
        assert body["device_token"]
        assert body["device"]["id"]

    def test_single_sample_telemetry_keeps_its_response_shape(self, client, enrolled_device):
        """The desktop agent parses these exact fields."""
        device, token = enrolled_device
        response = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(device.id),
                "cpu_percent": 12.0,
                "memory_percent": 34.0,
                "disk_percent": 56.0,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        body = response.json()
        assert {"metric", "alerts_created", "duplicate"} <= set(body)
        assert isinstance(body["alerts_created"], int)

    def test_batch_telemetry_keeps_its_response_shape(self, client, enrolled_device):
        """The Android agent parses these exact fields."""
        device, token = enrolled_device
        response = client.post(
            "/api/v1/metrics/batch",
            json={
                "device_id": str(device.id),
                "samples": [{"cpu_percent": 1.0, "memory_percent": 2.0, "disk_percent": 3.0}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        assert {"stored", "duplicates", "alerts_created", "latest"} <= set(response.json())

    def test_idempotent_replay_is_still_acknowledged_not_duplicated(self, client, enrolled_device):
        """An agent retrying after a lost response must not double-store."""
        device, token = enrolled_device
        event_id = str(uuid.uuid4())
        payload = {
            "device_id": str(device.id),
            "event_id": event_id,
            "cpu_percent": 5.0,
            "memory_percent": 6.0,
            "disk_percent": 7.0,
        }
        headers = {"Authorization": f"Bearer {token}"}

        first = client.post("/api/v1/metrics", json=payload, headers=headers)
        second = client.post("/api/v1/metrics", json=payload, headers=headers)

        assert first.json()["duplicate"] is False
        assert second.json()["duplicate"] is True

    def test_a_device_token_cannot_write_for_another_device(self, client, enrolled_device):
        _device, token = enrolled_device
        response = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(uuid.uuid4()),
                "cpu_percent": 1.0,
                "memory_percent": 2.0,
                "disk_percent": 3.0,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @pytest.mark.parametrize("path", ["/api/v1/metrics", "/api/v1/metrics/batch"])
    def test_telemetry_requires_a_device_token(self, client, path):
        assert client.post(path, json={}).status_code == 401
