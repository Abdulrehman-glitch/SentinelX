"""Issuing, rotating and revoking OTLP ingest keys.

An ingest key lets whatever holds it write telemetry into a tenant, so the
things worth pinning are: who may create one, that the secret is shown exactly
once and never again, that revocation is immediate, and that rotating does not
knock every collector offline the moment it happens.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.ingest_credential import IngestCredential
from app.models.user import User
from app.services import ingest_credential_service as ics
from helpers import auth_headers_for

BASE = "/api/v1/ingest-credentials"


@pytest.fixture()
def viewer_headers(db, org):
    user = User(
        email=f"viewer-{uuid.uuid4().hex[:8]}@test.local",
        full_name="Test Viewer",
        password_hash=hash_password("Password123!"),
        role="viewer",
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    return auth_headers_for(db, user)


def _create(client, headers, name="collector", **body):
    return client.post(BASE, json={"name": name, **body}, headers=headers)


class TestCreation:
    def test_an_admin_can_issue_a_key(self, client, admin_headers):
        response = _create(client, admin_headers)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["ingest_key"].startswith("sxi_live_")
        assert body["credential"]["scopes"] == ["metrics:write"]

    def test_the_prefix_makes_a_leaked_key_recognisable(self, client, admin_headers):
        """So it can be spotted in a log, a ticket or a scanner ruleset."""
        key = _create(client, admin_headers).json()["ingest_key"]
        assert key.startswith("sxi_live_")
        # 32 bytes of entropy is 43 url-safe characters.
        assert len(key.split("_", 2)[2]) >= 43

    def test_two_keys_are_never_the_same(self, client, admin_headers):
        a = _create(client, admin_headers, name="a").json()["ingest_key"]
        b = _create(client, admin_headers, name="b").json()["ingest_key"]
        assert a != b

    def test_only_the_hash_is_stored(self, client, admin_headers, db):
        key = _create(client, admin_headers).json()["ingest_key"]

        stored = db.scalar(
            select(IngestCredential).where(IngestCredential.token_hash == ics.hash_key(key))
        )
        assert stored is not None
        # The secret itself must appear in no column.
        assert key not in (stored.token_hash, stored.name, stored.key_prefix)
        assert stored.key_last_four == key[-4:]

    def test_an_unknown_scope_is_refused(self, client, admin_headers):
        response = _create(client, admin_headers, scopes=["logs:write"])
        assert response.status_code == 422
        assert "logs:write" in response.text

    def test_issuing_is_audited(self, client, admin_headers, db):
        _create(client, admin_headers, name="audited")
        logs = db.scalars(
            select(AuditLog).where(AuditLog.action == "ingest_credential_created")
        ).all()
        assert logs
        assert any("audited" in log.message for log in logs)


class TestAccessControl:
    def test_a_viewer_cannot_issue_a_key(self, client, viewer_headers):
        assert _create(client, viewer_headers).status_code == 403

    def test_a_viewer_cannot_list_keys(self, client, viewer_headers):
        assert client.get(BASE, headers=viewer_headers).status_code == 403

    def test_an_anonymous_caller_is_rejected(self, client):
        assert client.get(BASE).status_code == 401


class TestListing:
    def test_listing_never_returns_a_secret(self, client, admin_headers):
        """The one-time display is the whole security model."""
        key = _create(client, admin_headers).json()["ingest_key"]

        listed = client.get(BASE, headers=admin_headers).json()
        assert listed
        serialized = str(listed)
        assert key not in serialized
        assert "token_hash" not in serialized

    def test_the_last_four_identify_a_key_without_revealing_it(self, client, admin_headers):
        key = _create(client, admin_headers, name="identifiable").json()["ingest_key"]
        listed = client.get(BASE, headers=admin_headers).json()
        match = next(c for c in listed if c["name"] == "identifiable")
        assert match["key_last_four"] == key[-4:]

    def test_another_tenants_keys_are_not_listed(self, client, admin_headers, db):
        from app.models.organization import Organization

        suffix = uuid.uuid4().hex[:8]
        other = Organization(name=f"Other {suffix}", slug=f"cred-other-{suffix}")
        db.add(other)
        db.commit()
        ics.create_credential(db, organization_id=other.id, name="theirs")
        db.commit()

        listed = client.get(BASE, headers=admin_headers).json()
        assert all(c["name"] != "theirs" for c in listed)


class TestRevocation:
    def test_revoking_stops_the_key_immediately(self, client, admin_headers, db):
        created = _create(client, admin_headers).json()
        key = created["ingest_key"]

        response = client.delete(f"{BASE}/{created['credential']['id']}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["revoked_at"] is not None

        db.expire_all()
        assert ics.resolve_credential(db, key) is None

    def test_the_row_survives_revocation(self, client, admin_headers, db):
        """`last_used_at` and the audit trail are how a leak gets investigated."""
        created = _create(client, admin_headers).json()
        credential_id = uuid.UUID(created["credential"]["id"])

        client.delete(f"{BASE}/{credential_id}", headers=admin_headers)

        db.expire_all()
        assert db.get(IngestCredential, credential_id) is not None

    def test_revoking_twice_keeps_the_original_moment(self, client, admin_headers):
        created = _create(client, admin_headers).json()
        first = client.delete(
            f"{BASE}/{created['credential']['id']}", headers=admin_headers
        ).json()
        second = client.delete(
            f"{BASE}/{created['credential']['id']}", headers=admin_headers
        ).json()
        assert first["revoked_at"] == second["revoked_at"]

    def test_revoking_is_audited(self, client, admin_headers, db):
        created = _create(client, admin_headers).json()
        client.delete(f"{BASE}/{created['credential']['id']}", headers=admin_headers)

        logs = db.scalars(
            select(AuditLog).where(AuditLog.action == "ingest_credential_revoked")
        ).all()
        assert logs

    def test_another_tenants_key_is_a_404_not_a_403(self, client, admin_headers, db):
        """A 403 would confirm the id exists."""
        from app.models.organization import Organization

        suffix = uuid.uuid4().hex[:8]
        other = Organization(name=f"Other {suffix}", slug=f"cred-x-{suffix}")
        db.add(other)
        db.commit()
        theirs = ics.create_credential(db, organization_id=other.id, name="theirs")
        db.commit()

        response = client.delete(f"{BASE}/{theirs.credential.id}", headers=admin_headers)
        assert response.status_code == 404


class TestRotation:
    def test_rotation_issues_a_working_replacement(self, client, admin_headers, db):
        created = _create(client, admin_headers).json()
        rotated = client.post(
            f"{BASE}/{created['credential']['id']}/rotate", headers=admin_headers
        ).json()

        assert rotated["ingest_key"] != created["ingest_key"]
        db.expire_all()
        assert ics.resolve_credential(db, rotated["ingest_key"]) is not None

    def test_the_old_key_keeps_working_during_the_overlap(self, client, admin_headers, db):
        """Revoking first would break every collector until each is reconfigured."""
        created = _create(client, admin_headers).json()
        client.post(f"{BASE}/{created['credential']['id']}/rotate", headers=admin_headers)

        db.expire_all()
        old = ics.resolve_credential(db, created["ingest_key"])
        assert old is not None
        assert old.revoked_at is None
        assert old.expires_at is not None

    def test_the_old_key_stops_after_the_overlap(self, client, admin_headers, db):
        created = _create(client, admin_headers).json()
        client.post(f"{BASE}/{created['credential']['id']}/rotate", headers=admin_headers)

        db.expire_all()
        later = datetime.now(timezone.utc) + timedelta(hours=25)
        assert ics.resolve_credential(db, created["ingest_key"], now=later) is None

    def test_rotation_preserves_the_scopes(self, client, admin_headers):
        created = _create(client, admin_headers, scopes=["metrics:write"]).json()
        rotated = client.post(
            f"{BASE}/{created['credential']['id']}/rotate", headers=admin_headers
        ).json()
        assert rotated["credential"]["scopes"] == ["metrics:write"]

    def test_a_revoked_key_cannot_be_rotated(self, client, admin_headers):
        created = _create(client, admin_headers).json()
        client.delete(f"{BASE}/{created['credential']['id']}", headers=admin_headers)

        response = client.post(
            f"{BASE}/{created['credential']['id']}/rotate", headers=admin_headers
        )
        assert response.status_code == 409

    def test_rotation_is_audited(self, client, admin_headers, db):
        created = _create(client, admin_headers).json()
        client.post(f"{BASE}/{created['credential']['id']}/rotate", headers=admin_headers)

        logs = db.scalars(
            select(AuditLog).where(AuditLog.action == "ingest_credential_rotated")
        ).all()
        assert logs
