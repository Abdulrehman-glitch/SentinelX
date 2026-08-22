"""The canonical resource + series model.

These tests pin the properties the rest of the data plane assumes: that the same
thing always resolves to the same row, that two different things never resolve
to the same row, that runaway cardinality is refused rather than absorbed, and
that a hash collision would be detected rather than trusted.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.metric_series import MetricSeries
from app.services import cardinality_service as cs
from app.services.metric_series_service import SeriesResolver
from app.services.resource_service import (
    ResourceResolutionError,
    device_resource_attributes,
    resolve_resource,
)
from app.services.telemetry_identity import (
    canonical_attributes,
    resource_identity_hash,
    split_resource_identity,
)


def _budget(limit=1000, used=0):
    return cs.SeriesBudget(limit=limit, used=used, window_seconds=3600)


def _resolver(db, org, budget=None):
    return SeriesResolver(db=db, organization_id=org.id, budget=budget or _budget())


def _identity(attrs):
    identifying, _, _ = split_resource_identity(attrs)
    return resource_identity_hash(identifying)


class TestResourceResolution:
    def test_same_host_resolves_to_one_resource(self, db, org):
        first = resolve_resource(db, organization_id=org.id, attributes={"host.name": "web-1"})
        db.commit()
        second = resolve_resource(db, organization_id=org.id, attributes={"host.name": "web-1"})
        db.commit()
        assert first.id == second.id

    def test_descriptive_drift_does_not_create_a_second_resource(self, db, org):
        """An OS upgrade or an agent version bump is not a new machine."""
        first = resolve_resource(
            db,
            organization_id=org.id,
            attributes={"host.name": "web-2", "os.type": "linux", "os.version": "6.1"},
        )
        db.commit()
        second = resolve_resource(
            db,
            organization_id=org.id,
            attributes={"host.name": "web-2", "os.type": "linux", "os.version": "6.8"},
        )
        db.commit()

        assert first.id == second.id
        assert second.attributes["os.version"] == "6.8"

    def test_descriptive_attributes_merge_rather_than_replace(self, db, org):
        resolve_resource(
            db, organization_id=org.id, attributes={"host.name": "web-3", "os.type": "linux"}
        )
        db.commit()
        again = resolve_resource(
            db,
            organization_id=org.id,
            attributes={"host.name": "web-3", "host.arch": "arm64"},
        )
        db.commit()

        # A payload mentioning only the architecture must not erase the OS.
        assert again.attributes["os.type"] == "linux"
        assert again.attributes["host.arch"] == "arm64"

    def test_different_hosts_are_different_resources(self, db, org):
        a = resolve_resource(db, organization_id=org.id, attributes={"host.name": "web-4"})
        b = resolve_resource(db, organization_id=org.id, attributes={"host.name": "web-5"})
        db.commit()
        assert a.id != b.id

    def test_the_same_host_name_in_two_tenants_stays_separate(self, db, org):
        from app.models.organization import Organization

        suffix = uuid.uuid4().hex[:8]
        other = Organization(name=f"Other {suffix}", slug=f"other-{suffix}")
        db.add(other)
        db.commit()

        mine = resolve_resource(db, organization_id=org.id, attributes={"host.name": "shared"})
        theirs = resolve_resource(db, organization_id=other.id, attributes={"host.name": "shared"})
        db.commit()

        assert mine.id != theirs.id
        assert mine.organization_id != theirs.organization_id

    def test_a_service_is_typed_as_a_service(self, db, org):
        resource = resolve_resource(
            db,
            organization_id=org.id,
            attributes={"service.name": "checkout", "service.version": "2.1", "host.name": "web-6"},
        )
        db.commit()

        assert resource.resource_type == "service"
        # host.name is present but describes where the service runs; it must
        # not participate in the service's identity.
        assert resource.identifying_attributes == {"service.name": "checkout"}
        assert resource.attributes["host.name"] == "web-6"

    def test_the_same_service_on_two_hosts_is_one_resource(self, db, org):
        a = resolve_resource(
            db, organization_id=org.id, attributes={"service.name": "api", "host.name": "h1"}
        )
        db.commit()
        b = resolve_resource(
            db, organization_id=org.id, attributes={"service.name": "api", "host.name": "h2"}
        )
        db.commit()
        assert a.id == b.id

    def test_environments_separate_the_same_service(self, db, org):
        prod = resolve_resource(
            db,
            organization_id=org.id,
            attributes={"service.name": "api2", "deployment.environment.name": "production"},
        )
        staging = resolve_resource(
            db,
            organization_id=org.id,
            attributes={"service.name": "api2", "deployment.environment.name": "staging"},
        )
        db.commit()
        assert prod.id != staging.id

    def test_a_payload_with_no_identity_is_refused(self, db, org):
        """Better a loud rejection than a resource nobody can find again."""
        with pytest.raises(ResourceResolutionError):
            resolve_resource(db, organization_id=org.id, attributes={"colour": "blue"})

    def test_an_untrusted_client_cannot_pin_a_sentinelx_identity(self, db, org):
        """`sentinelx.*` carries authority, so an OTLP client may not set it."""
        forged = resolve_resource(
            db,
            organization_id=org.id,
            attributes={"sentinelx.resource.id": str(uuid.uuid4()), "host.name": "web-7"},
            trusted=False,
        )
        db.commit()
        assert forged.identifying_attributes == {"host.name": "web-7"}

    def test_a_renamed_device_keeps_its_identity(self, db, enrolled_device):
        """Pinned by device id, so a hostname change is not a new resource."""
        device, _token = enrolled_device
        before = resolve_resource(
            db,
            organization_id=device.organization_id,
            attributes=device_resource_attributes(device),
            device=device,
            trusted=True,
        )
        db.commit()

        device.hostname = "renamed-host"
        db.commit()

        after = resolve_resource(
            db,
            organization_id=device.organization_id,
            attributes=device_resource_attributes(device),
            device=device,
            trusted=True,
        )
        db.commit()

        assert before.id == after.id
        assert after.device_id == device.id

    def test_collision_seq_starts_at_zero(self, db, org):
        resource = resolve_resource(db, organization_id=org.id, attributes={"host.name": "web-8"})
        db.commit()
        assert resource.collision_seq == 0

    def test_a_hash_collision_does_not_fuse_two_resources(self, db, org, monkeypatch):
        """The property the whole design rests on.

        Force two genuinely different attribute sets to share a hash. The lookup
        must notice the attributes differ and allocate a second row, rather than
        trusting the hash and merging two machines into one.
        """
        import app.services.resource_service as rs

        monkeypatch.setattr(rs, "resource_identity_hash", lambda _identifying: "f" * 64)

        a = rs.resolve_resource(db, organization_id=org.id, attributes={"host.name": "collide-a"})
        db.commit()
        b = rs.resolve_resource(db, organization_id=org.id, attributes={"host.name": "collide-b"})
        db.commit()

        assert a.id != b.id
        assert a.identity_hash == b.identity_hash == "f" * 64
        assert {a.collision_seq, b.collision_seq} == {0, 1}

        # And each still resolves back to its own row.
        again_a = rs.resolve_resource(
            db, organization_id=org.id, attributes={"host.name": "collide-a"}
        )
        db.commit()
        assert again_a.id == a.id


class TestSeriesResolution:
    def test_the_same_measurement_resolves_to_one_series(self, db, org):
        resource = resolve_resource(db, organization_id=org.id, attributes={"host.name": "s-1"})
        db.commit()
        identity = _identity({"host.name": "s-1"})

        first, _ = _resolver(db, org).resolve(
            resource=resource,
            resource_identity=identity,
            metric_name="system.cpu.utilization",
            metric_unit="1",
            metric_kind="gauge",
            attributes={},
        )
        db.commit()

        # A fresh resolver, so the per-request cache cannot be what matches.
        second, _ = _resolver(db, org).resolve(
            resource=resource,
            resource_identity=identity,
            metric_name="system.cpu.utilization",
            metric_unit="1",
            metric_kind="gauge",
            attributes={},
        )
        db.commit()

        assert first.id == second.id

    def test_attributes_separate_series(self, db, org):
        resource = resolve_resource(db, organization_id=org.id, attributes={"host.name": "s-2"})
        db.commit()
        identity = _identity({"host.name": "s-2"})
        resolver = _resolver(db, org)

        c_drive, _ = resolver.resolve(
            resource=resource,
            resource_identity=identity,
            metric_name="system.disk.utilization",
            metric_unit="1",
            metric_kind="gauge",
            attributes=canonical_attributes({"disk.device": "C:"}),
        )
        d_drive, _ = resolver.resolve(
            resource=resource,
            resource_identity=identity,
            metric_name="system.disk.utilization",
            metric_unit="1",
            metric_kind="gauge",
            attributes=canonical_attributes({"disk.device": "D:"}),
        )
        db.commit()

        assert c_drive.id != d_drive.id

    def test_unit_and_kind_are_part_of_identity(self, db, org):
        """A gauge and a counter of the same name are not the same series."""
        resource = resolve_resource(db, organization_id=org.id, attributes={"host.name": "s-3"})
        db.commit()
        identity = _identity({"host.name": "s-3"})
        resolver = _resolver(db, org)

        gauge, _ = resolver.resolve(
            resource=resource, resource_identity=identity, metric_name="requests",
            metric_unit="1", metric_kind="gauge", attributes={},
        )
        counter, _ = resolver.resolve(
            resource=resource, resource_identity=identity, metric_name="requests",
            metric_unit="1", metric_kind="sum", attributes={},
        )
        different_unit, _ = resolver.resolve(
            resource=resource, resource_identity=identity, metric_name="requests",
            metric_unit="ms", metric_kind="gauge", attributes={},
        )
        db.commit()

        assert len({gauge.id, counter.id, different_unit.id}) == 3

    def test_the_request_cache_avoids_repeated_lookups(self, db, org):
        resource = resolve_resource(db, organization_id=org.id, attributes={"host.name": "s-4"})
        db.commit()
        identity = _identity({"host.name": "s-4"})
        resolver = _resolver(db, org)

        for _ in range(50):
            _series, rejection = resolver.resolve(
                resource=resource, resource_identity=identity, metric_name="cpu",
                metric_unit="1", metric_kind="gauge", attributes={},
            )
            assert rejection is None
        db.commit()

        # 50 resolutions of one series must have created exactly one.
        assert resolver.created_count == 1
        count = db.scalar(
            select(func.count()).select_from(MetricSeries).where(
                MetricSeries.organization_id == org.id, MetricSeries.metric_name == "cpu"
            )
        )
        assert count == 1


class TestCardinalityLimits:
    def test_an_established_series_ignores_an_exhausted_budget(self, db, org):
        """The limit targets runaway creation, not ordinary volume."""
        resource = resolve_resource(db, organization_id=org.id, attributes={"host.name": "c-1"})
        db.commit()
        identity = _identity({"host.name": "c-1"})

        created, _ = _resolver(db, org, _budget(limit=10)).resolve(
            resource=resource, resource_identity=identity, metric_name="established",
            metric_unit="1", metric_kind="gauge", attributes={},
        )
        db.commit()

        # Budget fully spent, yet the existing series still accepts points.
        found, rejection = _resolver(db, org, _budget(limit=1, used=1)).resolve(
            resource=resource, resource_identity=identity, metric_name="established",
            metric_unit="1", metric_kind="gauge", attributes={},
        )
        db.commit()

        assert rejection is None
        assert found.id == created.id

    def test_a_new_series_is_refused_once_the_budget_is_spent(self, db, org):
        resource = resolve_resource(db, organization_id=org.id, attributes={"host.name": "c-2"})
        db.commit()
        identity = _identity({"host.name": "c-2"})

        series, rejection = _resolver(db, org, _budget(limit=1, used=1)).resolve(
            resource=resource, resource_identity=identity, metric_name="brand.new",
            metric_unit="1", metric_kind="gauge", attributes={},
        )
        db.commit()

        assert series is None
        assert rejection.reason == cs.REJECT_SERIES_BUDGET_EXHAUSTED

    def test_a_refused_series_writes_nothing(self, db, org):
        resource = resolve_resource(db, organization_id=org.id, attributes={"host.name": "c-3"})
        db.commit()
        identity = _identity({"host.name": "c-3"})

        before = db.scalar(select(func.count()).select_from(MetricSeries))
        _resolver(db, org, _budget(limit=0)).resolve(
            resource=resource, resource_identity=identity, metric_name="refused",
            metric_unit="1", metric_kind="gauge", attributes={},
        )
        db.commit()
        assert db.scalar(select(func.count()).select_from(MetricSeries)) == before

    def test_a_uuid_attribute_burns_the_budget_and_then_stops(self, db, org):
        """The exact accident the budget exists for.

        A request id used as a dimension makes every sample its own series. The
        request volume looks entirely normal, so only a series budget can see
        it — and it must stop, not merely slow down.
        """
        resource = resolve_resource(db, organization_id=org.id, attributes={"host.name": "c-4"})
        db.commit()
        identity = _identity({"host.name": "c-4"})
        resolver = _resolver(db, org, _budget(limit=5))

        accepted, refused = 0, 0
        for _ in range(40):
            _series, rejection = resolver.resolve(
                resource=resource, resource_identity=identity, metric_name="http.duration",
                metric_unit="ms", metric_kind="gauge",
                attributes=canonical_attributes({"request.id": str(uuid.uuid4())}),
            )
            if rejection is not None:
                refused += 1
            else:
                accepted += 1
        db.commit()

        assert accepted == 5
        assert refused == 35

    def test_budget_counts_only_the_configured_window(self, db, org):
        settings = get_settings()
        resource = resolve_resource(db, organization_id=org.id, attributes={"host.name": "c-5"})
        db.commit()
        identity = _identity({"host.name": "c-5"})

        series, _ = _resolver(db, org).resolve(
            resource=resource, resource_identity=identity, metric_name="old.series",
            metric_unit="1", metric_kind="gauge", attributes={},
        )
        db.commit()

        # Age it out of the window; it should stop counting against the budget.
        series.first_seen_at = datetime.now(timezone.utc) - timedelta(
            seconds=settings.ingest_new_series_window_seconds + 60
        )
        db.commit()

        budget = cs.load_series_budget(db, org.id, settings)
        assert budget.used == 0


class TestValidationLimits:
    def _settings(self):
        return get_settings()

    def test_too_many_attributes_is_refused(self):
        attrs = {f"k{i}": "v" for i in range(200)}
        rejection = cs.validate_attributes(attrs, self._settings(), subject="m")
        assert rejection.reason == cs.REJECT_TOO_MANY_ATTRIBUTES

    def test_an_overlong_attribute_value_is_refused(self):
        s = self._settings()
        attrs = {"path": "x" * (s.ingest_max_attribute_value_length + 1)}
        rejection = cs.validate_attributes(attrs, s, subject="m")
        assert rejection.reason == cs.REJECT_ATTRIBUTE_VALUE_TOO_LONG

    def test_an_overlong_attribute_key_is_refused(self):
        s = self._settings()
        attrs = {"k" * (s.ingest_max_attribute_key_length + 1): "v"}
        rejection = cs.validate_attributes(attrs, s, subject="m")
        assert rejection.reason == cs.REJECT_ATTRIBUTE_KEY_TOO_LONG

    def test_an_ordinary_attribute_set_passes(self):
        attrs = canonical_attributes({"disk.device": "C:", "host.name": "web-1"})
        assert cs.validate_attributes(attrs, self._settings(), subject="m") is None

    @pytest.mark.parametrize("name", ["", "   "])
    def test_an_empty_metric_name_is_refused(self, name):
        assert cs.validate_metric_name(name, self._settings()).reason == cs.REJECT_METRIC_NAME_EMPTY

    def test_an_overlong_metric_name_is_refused(self):
        s = self._settings()
        rejection = cs.validate_metric_name("m" * (s.ingest_max_metric_name_length + 1), s)
        assert rejection.reason == cs.REJECT_METRIC_NAME_TOO_LONG

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_values_are_refused(self, value):
        """Postgres would store NaN happily; every aggregate over it is wrong."""
        rejection = cs.validate_value(value, self._settings(), subject="m")
        assert rejection.reason == cs.REJECT_VALUE_NOT_FINITE

    def test_a_finite_value_passes(self):
        assert cs.validate_value(42.5, self._settings(), subject="m") is None

    def test_a_far_future_timestamp_is_refused(self):
        s = self._settings()
        future = datetime.now(timezone.utc) + timedelta(days=1)
        rejection = cs.validate_timestamp(future, s, subject="m")
        assert rejection.reason == cs.REJECT_TIMESTAMP_TOO_FAR_FUTURE

    def test_small_clock_skew_is_tolerated(self):
        """Agent clocks drift by seconds; that is not an attack."""
        s = self._settings()
        near = datetime.now(timezone.utc) + timedelta(seconds=5)
        assert cs.validate_timestamp(near, s, subject="m") is None

    def test_an_ancient_timestamp_is_refused(self):
        s = self._settings()
        old = datetime.now(timezone.utc) - timedelta(days=s.ingest_max_backfill_age_days + 1)
        assert cs.validate_timestamp(old, s, subject="m").reason == cs.REJECT_TIMESTAMP_TOO_OLD

    def test_an_offline_queue_flush_is_accepted(self):
        """A mobile agent back from two days offline is a normal case."""
        s = self._settings()
        recent = datetime.now(timezone.utc) - timedelta(days=2)
        assert cs.validate_timestamp(recent, s, subject="m") is None
