"""The live operations channel.

The stream is an optimisation over the REST view, so the properties worth
pinning are the ones that make it safe to rely on: a tenant sees only its own
events, a reconnecting client loses nothing, a revoked session stops receiving,
and the events themselves are atomic with the changes they describe.
"""

import uuid

import pytest

from app.core.security import hash_password
from app.models.device import Device
from app.models.organization import Organization
from app.models.user import User
from app.services import domain_event_service as des
from app.services import session_service
from helpers import auth_headers_for


def _device(db, org):
    device = Device(
        organization_id=org.id,
        hostname=f"evt-{uuid.uuid4().hex[:8]}",
        device_type="desktop",
        status="online",
    )
    db.add(device)
    db.flush()
    return device


class TestRecording:
    def test_an_event_joins_the_callers_transaction(self, db, org):
        """No commit here: the event exists only once the caller commits."""
        des.record(db, organization_id=org.id, event_type="alert.created", payload={"x": 1})
        db.rollback()
        assert des.latest_sequence(db, org.id) == 0

    def test_a_committed_event_is_visible(self, db, org):
        des.record(db, organization_id=org.id, event_type="alert.created", payload={"x": 1})
        db.commit()
        assert des.latest_sequence(db, org.id) > 0

    def test_an_unknown_event_type_is_refused(self, db, org):
        with pytest.raises(ValueError):
            des.record(db, organization_id=org.id, event_type="alert.invented")
        db.rollback()

    def test_record_safely_swallows_the_failure(self, db, org):
        assert des.record_safely(db, organization_id=org.id, event_type="nope") is None
        db.rollback()

    def test_sequences_increase(self, db, org):
        des.record(db, organization_id=org.id, event_type="alert.created")
        db.commit()
        first = des.latest_sequence(db, org.id)
        des.record(db, organization_id=org.id, event_type="alert.updated")
        db.commit()
        assert des.latest_sequence(db, org.id) > first


class TestTenantIsolation:
    def test_events_never_cross_organisations(self, db, org):
        other = Organization(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
        db.add(other)
        db.flush()
        des.record(
            db,
            organization_id=other.id,
            event_type="incident.created",
            payload={"secret": "their-incident"},
        )
        db.commit()

        mine = des.events_since(db, org.id, 0)
        assert all(e.organization_id == org.id for e in mine)
        assert not any((e.payload or {}).get("secret") for e in mine)

    def test_the_rest_endpoint_is_scoped_to_the_callers_org(self, client, db, org, admin_headers):
        other = Organization(name="Other2", slug=f"o-{uuid.uuid4().hex[:8]}")
        db.add(other)
        db.flush()
        des.record(
            db,
            organization_id=other.id,
            event_type="incident.created",
            payload={"title": "not yours"},
        )
        des.record(
            db, organization_id=org.id, event_type="incident.created", payload={"title": "mine"}
        )
        db.commit()

        body = client.get("/api/v1/events/recent", headers=admin_headers).json()
        titles = {(i["payload"] or {}).get("title") for i in body["items"]}
        assert "not yours" not in titles

    def test_the_stream_requires_authentication(self, client):
        assert client.get("/api/v1/events/stream").status_code == 401

    def test_the_recent_endpoint_requires_authentication(self, client):
        assert client.get("/api/v1/events/recent").status_code == 401


class TestResume:
    def test_no_cursor_starts_from_now_rather_than_from_history(self, db, org):
        for _ in range(3):
            des.record(db, organization_id=org.id, event_type="alert.created")
        db.commit()
        latest = des.latest_sequence(db, org.id)
        # A browser opening the stream fresh wants live events, not a backlog.
        assert des.resume_from(db, org.id, None) == latest

    def test_a_cursor_is_walked_back_over_the_overlap_window(self, db, org):
        assert des.resume_from(db, org.id, "1000") == 1000 - des.RESUME_OVERLAP

    def test_a_cursor_inside_the_overlap_cannot_go_negative(self, db, org):
        assert des.resume_from(db, org.id, "3") == 0

    def test_a_garbage_cursor_is_treated_as_no_cursor(self, db, org):
        des.record(db, organization_id=org.id, event_type="alert.created")
        db.commit()
        latest = des.latest_sequence(db, org.id)
        assert des.resume_from(db, org.id, "not-a-number") == latest
        assert des.resume_from(db, org.id, "-5") == latest

    def test_events_after_a_cursor_come_back_oldest_first(self, db, org):
        base = des.latest_sequence(db, org.id)
        for index in range(5):
            des.record(
                db, organization_id=org.id, event_type="alert.created", payload={"n": index}
            )
        db.commit()

        events = des.events_since(db, org.id, base)
        assert [e.payload["n"] for e in events] == [0, 1, 2, 3, 4]

    def test_a_poll_is_bounded(self, db, org):
        base = des.latest_sequence(db, org.id)
        for _ in range(5):
            des.record(db, organization_id=org.id, event_type="alert.created")
        db.commit()
        assert len(des.events_since(db, org.id, base, limit=2)) == 2

    def test_an_absurd_limit_is_clamped(self, db, org):
        assert len(des.events_since(db, org.id, 0, limit=10_000)) <= des.MAX_EVENTS_PER_POLL


class TestProducers:
    def test_a_critical_alert_produces_a_stream_event(self, client, db, enrolled_device):
        device, token = enrolled_device
        before = des.latest_sequence(db, device.organization_id)

        response = client.post(
            "/api/v1/metrics",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_id": str(device.id),
                "cpu_percent": 99.0,
                "memory_percent": 99.0,
                "disk_percent": 99.0,
            },
        )
        assert response.status_code in (200, 201), response.text

        events = des.events_since(db, device.organization_id, before)
        assert any(e.event_type == "alert.created" for e in events)

    def test_an_alert_event_carries_a_summary_not_the_row(self, client, db, enrolled_device):
        device, token = enrolled_device
        before = des.latest_sequence(db, device.organization_id)
        client.post(
            "/api/v1/metrics",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_id": str(device.id),
                "cpu_percent": 99.0,
                "memory_percent": 99.0,
                "disk_percent": 99.0,
            },
        )
        events = [
            e
            for e in des.events_since(db, device.organization_id, before)
            if e.event_type == "alert.created"
        ]
        assert events
        # Enough to decide what is stale, not a copy of the alert row.
        assert set(events[0].payload) == {"alert_id", "alert_type", "severity", "message"}

    def test_disabling_a_device_produces_a_status_event(self, client, db, org, admin_headers):
        device = _device(db, org)
        db.commit()
        before = des.latest_sequence(db, org.id)

        response = client.patch(
            f"/api/v1/devices/{device.id}/status",
            headers=admin_headers,
            json={"enabled": False},
        )
        assert response.status_code == 200, response.text

        status_events = [
            e
            for e in des.events_since(db, org.id, before)
            if e.event_type == "device.status_changed"
        ]
        assert status_events
        assert status_events[0].payload["to"] == "disabled"

    def test_creating_an_incident_produces_an_event(self, client, db, org, admin_headers):
        before = des.latest_sequence(db, org.id)
        response = client.post(
            "/api/v1/incidents",
            headers=admin_headers,
            json={"title": "Disk pressure", "severity": "critical", "source": "manual"},
        )
        assert response.status_code == 201, response.text
        events = des.events_since(db, org.id, before)
        assert any(e.event_type == "incident.created" for e in events)


class TestRestCatchUp:
    def test_recent_reports_a_cursor_the_stream_can_resume_from(
        self, client, db, org, admin_headers
    ):
        des.record(db, organization_id=org.id, event_type="alert.created")
        db.commit()

        body = client.get("/api/v1/events/recent", headers=admin_headers).json()
        assert body["latest"] >= body["cursor"]
        assert body["items"]

    def test_recent_pages_forward(self, client, db, org, admin_headers):
        base = des.latest_sequence(db, org.id)
        for _ in range(4):
            des.record(db, organization_id=org.id, event_type="alert.created")
        db.commit()

        first = client.get(
            f"/api/v1/events/recent?after={base}&limit=2", headers=admin_headers
        ).json()
        assert len(first["items"]) == 2
        second = client.get(
            f"/api/v1/events/recent?after={first['cursor']}&limit=2", headers=admin_headers
        ).json()
        assert len(second["items"]) == 2
        assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})

    def test_an_oversized_page_is_rejected(self, client, admin_headers):
        response = client.get("/api/v1/events/recent?limit=5000", headers=admin_headers)
        assert response.status_code == 422


class TestSessionRevocation:
    def test_a_revoked_session_cannot_open_a_stream(self, client, db, org):
        user = User(
            email=f"sse-{uuid.uuid4().hex[:8]}@test.local",
            full_name="SSE user",
            password_hash=hash_password("Password123!"),
            role="engineer",
            is_active=True,
            organization_id=org.id,
        )
        db.add(user)
        db.commit()

        headers = auth_headers_for(db, user)
        for session in session_service.list_active_sessions(db, user.id):
            session_service.revoke_session(db, session, reason="test")
        db.commit()

        assert client.get("/api/v1/events/stream", headers=headers).status_code == 401
