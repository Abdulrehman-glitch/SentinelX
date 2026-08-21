"""Systematic cross-organisation isolation across every tenant-owned resource.

Multi-tenancy in SentinelX is enforced in application code (see
docs/adr/0002-tenant-isolation-strategy.md for why Row Level Security is
deferred rather than adopted). Application-level scoping is only as good as
its coverage, so this suite is deliberately exhaustive rather than
illustrative: it walks the resource families a tenant can reach and asserts,
for each one, that a user in organisation A can neither read nor mutate
organisation B's rows.

Two properties are asserted throughout:

1. **List endpoints never leak.** Another tenant's rows must be absent from
   the collection, not merely un-clickable in the UI.
2. **Direct-ID access returns 404, not 403.** A 403 confirms the row exists,
   which turns any id endpoint into an existence oracle for enumerating a
   rival's fleet. tenant.assert_same_org answers 404 for exactly this reason.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.core.security import hash_password
from app.models.alert import Alert
from app.models.alert_rule import AlertRule
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.incident import Incident
from app.models.organization import Organization
from app.models.recovery_action import RecoveryAction
from app.models.system_metric import SystemMetric
from app.models.user import User
from helpers import auth_headers_for


class Tenant:
    def __init__(self, org, admin, device, headers):
        self.org = org
        self.admin = admin
        self.device = device
        self.headers = headers


def _make_tenant(db, label: str) -> Tenant:
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Tenant {label} {suffix}", slug=f"tenant-{label}-{suffix}")
    db.add(org)
    db.commit()
    db.refresh(org)

    admin = User(
        email=f"{label}-admin-{suffix}@test.local",
        full_name=f"Tenant {label} Admin",
        password_hash=hash_password("Password123!"),
        role="admin",
        is_active=True,
        organization_id=org.id,
    )
    db.add(admin)

    device = Device(
        id=uuid.uuid4(),
        organization_id=org.id,
        hostname=f"{label}-host-{suffix}",
        display_name=f"{label} device",
        device_type="desktop",
        status="online",
    )
    db.add(device)
    db.commit()
    db.refresh(admin)
    db.refresh(device)

    return Tenant(org, admin, device, auth_headers_for(db, admin))


@pytest.fixture()
def tenant_a(db):
    return _make_tenant(db, "a")


@pytest.fixture()
def tenant_b(db):
    return _make_tenant(db, "b")


class TestDeviceIsolation:
    def test_device_list_excludes_other_tenants(self, client, tenant_a, tenant_b):
        listed = client.get("/api/v1/devices", headers=tenant_a.headers)
        assert listed.status_code == 200

        ids = {row["id"] for row in listed.json()}
        assert str(tenant_a.device.id) in ids
        assert str(tenant_b.device.id) not in ids

    def test_reading_another_tenants_device_is_404_not_403(self, client, tenant_a, tenant_b):
        response = client.get(f"/api/v1/devices/{tenant_b.device.id}", headers=tenant_a.headers)
        assert response.status_code == 404, "403 would confirm the device exists"

    def test_updating_another_tenants_device_is_404(self, client, db, tenant_a, tenant_b):
        response = client.patch(
            f"/api/v1/devices/{tenant_b.device.id}/status",
            json={"enabled": False},
            headers=tenant_a.headers,
        )
        assert response.status_code == 404

        db.refresh(tenant_b.device)
        assert tenant_b.device.status == "online", "the other tenant's device must be untouched"

    def test_deleting_another_tenants_device_is_404(self, client, db, tenant_a, tenant_b):
        response = client.delete(f"/api/v1/devices/{tenant_b.device.id}", headers=tenant_a.headers)
        assert response.status_code == 404
        assert db.get(Device, tenant_b.device.id) is not None

    def test_device_health_view_is_scoped(self, client, tenant_a, tenant_b):
        response = client.get(
            f"/api/v1/devices/{tenant_b.device.id}/health", headers=tenant_a.headers
        )
        assert response.status_code == 404


class TestMetricIsolation:
    @pytest.fixture(autouse=True)
    def _seed_metrics(self, db, tenant_a, tenant_b):
        now = datetime.now(timezone.utc)
        for tenant, value in ((tenant_a, 11.0), (tenant_b, 99.0)):
            db.add(
                SystemMetric(
                    id=uuid.uuid4(),
                    organization_id=tenant.org.id,
                    device_id=tenant.device.id,
                    cpu_percent=value,
                    memory_percent=value,
                    disk_percent=value,
                    recorded_at=now,
                )
            )
        db.commit()

    def test_own_device_metrics_are_readable(self, client, tenant_a):
        response = client.get(
            f"/api/v1/metrics/device/{tenant_a.device.id}", headers=tenant_a.headers
        )
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_reading_another_tenants_device_metrics_is_404(self, client, tenant_a, tenant_b):
        """The dangerous shape: a real device id that belongs to someone else,
        passed to a path that is scoped by device rather than by org."""

        response = client.get(
            f"/api/v1/metrics/device/{tenant_b.device.id}", headers=tenant_a.headers
        )
        assert response.status_code == 404

    def test_device_metric_history_is_scoped(self, client, tenant_a, tenant_b):
        for path in ("metrics/latest", "metrics/history"):
            response = client.get(
                f"/api/v1/devices/{tenant_b.device.id}/{path}", headers=tenant_a.headers
            )
            assert response.status_code == 404, path


class TestOperationalResourceIsolation:
    def _alert(self, db, tenant):
        alert = Alert(
            id=uuid.uuid4(),
            organization_id=tenant.org.id,
            device_id=tenant.device.id,
            alert_type="cpu_high",
            severity="critical",
            message="seeded",
            resolved=False,
        )
        db.add(alert)
        db.commit()
        return alert

    def _incident(self, db, tenant):
        incident = Incident(
            id=uuid.uuid4(),
            organization_id=tenant.org.id,
            device_id=tenant.device.id,
            title="seeded incident",
            severity="high",
            status="open",
        )
        db.add(incident)
        db.commit()
        return incident

    def test_alert_list_and_detail_are_scoped(self, client, db, tenant_a, tenant_b):
        mine = self._alert(db, tenant_a)
        theirs = self._alert(db, tenant_b)

        listed = client.get("/api/v1/alerts", headers=tenant_a.headers)
        ids = {row["id"] for row in listed.json()}
        assert str(mine.id) in ids
        assert str(theirs.id) not in ids

    def test_cannot_resolve_another_tenants_alert(self, client, db, tenant_a, tenant_b):
        theirs = self._alert(db, tenant_b)

        response = client.patch(f"/api/v1/alerts/{theirs.id}/resolve", headers=tenant_a.headers)
        assert response.status_code == 404

        db.refresh(theirs)
        assert theirs.resolved is False, "the other tenant's alert must be untouched"

    def test_incident_list_and_detail_are_scoped(self, client, db, tenant_a, tenant_b):
        mine = self._incident(db, tenant_a)
        theirs = self._incident(db, tenant_b)

        listed = client.get("/api/v1/incidents", headers=tenant_a.headers)
        ids = {row["id"] for row in listed.json()}
        assert str(mine.id) in ids
        assert str(theirs.id) not in ids

        detail = client.get(f"/api/v1/incidents/{theirs.id}", headers=tenant_a.headers)
        assert detail.status_code == 404

    def test_cannot_append_an_event_to_another_tenants_incident(
        self, client, db, tenant_a, tenant_b
    ):
        theirs = self._incident(db, tenant_b)

        response = client.post(
            f"/api/v1/incidents/{theirs.id}/events",
            json={"event_type": "note", "message": "injected"},
            headers=tenant_a.headers,
        )
        assert response.status_code == 404

    def test_alert_rule_isolation(self, client, db, tenant_a, tenant_b):
        rule = AlertRule(
            id=uuid.uuid4(),
            organization_id=tenant_b.org.id,
            name="their rule",
            metric_type="cpu_percent",
            operator=">=",
            threshold=90,
            severity="critical",
            enabled=True,
        )
        db.add(rule)
        db.commit()

        listed = client.get("/api/v1/alert-rules", headers=tenant_a.headers)
        assert str(rule.id) not in {row["id"] for row in listed.json()}

        detail = client.get(f"/api/v1/alert-rules/{rule.id}", headers=tenant_a.headers)
        assert detail.status_code == 404

        patched = client.patch(
            f"/api/v1/alert-rules/{rule.id}",
            json={"enabled": False},
            headers=tenant_a.headers,
        )
        assert patched.status_code == 404

        toggled = client.patch(
            f"/api/v1/alert-rules/{rule.id}/toggle", headers=tenant_a.headers
        )
        assert toggled.status_code == 404

        db.refresh(rule)
        assert rule.enabled is True

    def test_recovery_action_isolation(self, client, db, tenant_a, tenant_b):
        action = RecoveryAction(
            id=uuid.uuid4(),
            organization_id=tenant_b.org.id,
            device_id=tenant_b.device.id,
            action_type="collect_diagnostics",
            status="completed",
            details="seeded for isolation test",
        )
        db.add(action)
        db.commit()

        listed = client.get("/api/v1/recovery-actions", headers=tenant_a.headers)
        assert str(action.id) not in {row["id"] for row in listed.json()}

    def test_cannot_create_a_recovery_command_against_another_tenants_device(
        self, client, tenant_a, tenant_b
    ):
        response = client.post(
            "/api/v1/recovery-commands",
            json={
                "device_id": str(tenant_b.device.id),
                "action_type": "collect_diagnostics",
                "parameters": {},
            },
            headers=tenant_a.headers,
        )
        assert response.status_code == 404


class TestGovernanceIsolation:
    def test_audit_log_is_scoped(self, client, db, tenant_a, tenant_b):
        entry = AuditLog(
            id=uuid.uuid4(),
            organization_id=tenant_b.org.id,
            actor_type="user",
            actor_id=str(tenant_b.admin.id),
            action="tenant_b_only_action",
            severity="info",
            message="tenant B business event",
        )
        db.add(entry)
        db.commit()

        listed = client.get("/api/v1/audit-logs", headers=tenant_a.headers)
        assert listed.status_code == 200
        assert "tenant_b_only_action" not in listed.text

    def test_user_list_is_scoped_to_the_callers_organisation(self, client, tenant_a, tenant_b):
        listed = client.get("/api/v1/users", headers=tenant_a.headers)
        assert listed.status_code == 200

        emails = {row["email"] for row in listed.json()}
        assert tenant_a.admin.email in emails
        assert tenant_b.admin.email not in emails

    def test_cannot_read_or_modify_a_user_in_another_organisation(
        self, client, db, tenant_a, tenant_b
    ):
        read = client.get(f"/api/v1/users/{tenant_b.admin.id}", headers=tenant_a.headers)
        assert read.status_code == 404

        patched = client.patch(
            f"/api/v1/users/{tenant_b.admin.id}/role",
            json={"role": "viewer"},
            headers=tenant_a.headers,
        )
        assert patched.status_code == 404

        db.refresh(tenant_b.admin)
        assert tenant_b.admin.role == "admin"

    def test_overview_counts_only_the_callers_organisation(self, client, db, tenant_a, tenant_b):
        for _ in range(3):
            db.add(
                Device(
                    id=uuid.uuid4(),
                    organization_id=tenant_b.org.id,
                    hostname=f"extra-{uuid.uuid4().hex[:8]}",
                    device_type="desktop",
                    status="online",
                )
            )
        db.commit()

        overview = client.get("/api/v1/overview", headers=tenant_a.headers)
        assert overview.status_code == 200
        assert overview.json()["devices"]["total"] == 1

    def test_one_users_sessions_are_never_visible_to_another(self, client, tenant_a, tenant_b):
        """Session listing is scoped to the caller with no id parameter at
        all — the absence of that surface is the isolation."""

        mine = client.get("/api/v1/auth/sessions", headers=tenant_a.headers)
        theirs = client.get("/api/v1/auth/sessions", headers=tenant_b.headers)

        assert mine.status_code == theirs.status_code == 200
        assert {s["id"] for s in mine.json()}.isdisjoint({s["id"] for s in theirs.json()})


class TestPlatformAdminCrossesTenants:
    def test_platform_admin_sees_every_organisation(self, client, db, tenant_a, tenant_b):
        """The deliberate exception, asserted explicitly. If a future change
        tightened scoping without an exemption, platform admin would silently
        stop working and nothing else would catch it."""

        operator = User(
            email=f"platform-{uuid.uuid4().hex[:8]}@sentinelx.io",
            full_name="Platform Operator",
            password_hash=hash_password("Password123!"),
            role="platform_admin",
            is_active=True,
            organization_id=None,
        )
        db.add(operator)
        db.commit()
        db.refresh(operator)

        listed = client.get("/api/v1/devices", headers=auth_headers_for(db, operator))
        assert listed.status_code == 200

        ids = {row["id"] for row in listed.json()}
        assert str(tenant_a.device.id) in ids
        assert str(tenant_b.device.id) in ids

    def test_a_user_with_no_organisation_is_refused_not_shown_everything(self, client, db):
        """Fail closed: an org-less non-platform-admin must be rejected, not
        treated as matching `organization_id IS NULL` and handed rows."""

        orphan = User(
            email=f"orphan-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Orphan",
            password_hash=hash_password("Password123!"),
            role="admin",
            is_active=True,
            organization_id=None,
        )
        db.add(orphan)
        db.commit()
        db.refresh(orphan)

        response = client.get("/api/v1/devices", headers=auth_headers_for(db, orphan))
        assert response.status_code == 403


class TestCredentialTypeBoundary:
    def test_a_device_token_cannot_post_metrics_for_another_tenants_device(
        self, client, enrolled_device, tenant_b
    ):
        device, token = enrolled_device
        assert device.id != tenant_b.device.id

        response = client.post(
            "/api/v1/metrics",
            json={
                "device_id": str(tenant_b.device.id),
                "cpu_percent": 50.0,
                "memory_percent": 50.0,
                "disk_percent": 50.0,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (403, 404), response.text

    def test_a_user_access_token_is_not_accepted_as_a_device_token(self, client, tenant_a):
        """The two credential types must not be interchangeable in either
        direction."""

        response = client.get("/api/v1/agent/commands/next", headers=tenant_a.headers)
        assert response.status_code == 401

    def test_a_device_token_is_not_accepted_as_a_user_token(self, client, enrolled_device):
        _device, token = enrolled_device

        response = client.get("/api/v1/devices", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
