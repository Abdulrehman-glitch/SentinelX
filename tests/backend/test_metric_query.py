"""The canonical metric read path.

These tests care about three things in roughly this order: that a tenant can
only ever see its own series, that the engine refuses to answer a question
whose answer would be wrong or unbounded, and that the numbers it does return
are arithmetically correct rather than merely plausible.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.models.metric_point import MetricPoint
from app.models.metric_series import MetricSeries
from app.models.organization import Organization
from app.models.resource import Resource
from app.models.user import User
from app.services import metric_query_service as mqs
from helpers import auth_headers_for

BASE = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_series(
    db,
    org_id,
    *,
    metric="system.cpu.utilization",
    kind="gauge",
    unit="%",
    attributes=None,
    resource_name="host-a",
    resource_type="host",
    source="sentinelx_agent",
):
    resource = Resource(
        organization_id=org_id,
        resource_type=resource_type,
        identity_hash=uuid.uuid4().hex,
        identifying_attributes={"host.name": resource_name},
        attributes={},
        display_name=resource_name,
    )
    db.add(resource)
    db.flush()
    series = MetricSeries(
        organization_id=org_id,
        resource_id=resource.id,
        metric_name=metric,
        metric_unit=unit,
        metric_kind=kind,
        attributes=attributes or {},
        series_hash=uuid.uuid4().hex,
        source=source,
    )
    db.add(series)
    db.flush()
    return resource, series


def _add_points(db, org_id, series, values, *, start=BASE, step_seconds=60):
    for index, value in enumerate(values):
        db.add(
            MetricPoint(
                organization_id=org_id,
                series_id=series.id,
                recorded_at=start + timedelta(seconds=index * step_seconds),
                value=float(value),
            )
        )
    db.flush()


@pytest.fixture()
def cpu_series(db, org):
    resource, series = _make_series(db, org.id)
    _add_points(db, org.id, series, [10, 20, 30, 40, 50, 60])
    db.commit()
    return resource, series


class TestResolution:
    def test_bucket_width_is_chosen_so_the_point_budget_is_respected(self):
        # One day at 100 points would need 864s buckets; the ladder rounds up
        # to 900 rather than inventing an unreadable axis.
        assert mqs.choose_bucket_seconds(86400, 100) == 900

    def test_a_tiny_range_still_gets_the_finest_ladder_step(self):
        assert mqs.choose_bucket_seconds(60, 500) == 10

    def test_an_absurdly_wide_range_falls_back_to_whole_weeks(self):
        ten_years = 86400 * 3650
        assert mqs.choose_bucket_seconds(ten_years, 10) % 604800 == 0


class TestAggregationCorrectness:
    def test_avg_over_one_bucket_is_the_mean_of_the_samples(self, db, org, cpu_series):
        result = mqs.run_query(
            db,
            mqs.MetricQuery(
                organization_id=org.id,
                metric_name="system.cpu.utilization",
                start=BASE,
                end=BASE + timedelta(minutes=6),
                aggregation="avg",
                bucket_seconds=3600,
                max_points=10,
            ),
        )
        assert len(result.series) == 1
        assert result.series[0].points[0][1] == pytest.approx(35.0)
        assert result.series[0].sample_count == 6

    def test_min_and_max_pick_the_extremes(self, db, org, cpu_series):
        def value_for(aggregation):
            result = mqs.run_query(
                db,
                mqs.MetricQuery(
                    organization_id=org.id,
                    metric_name="system.cpu.utilization",
                    start=BASE,
                    end=BASE + timedelta(minutes=6),
                    aggregation=aggregation,
                    bucket_seconds=3600,
                    max_points=10,
                ),
            )
            return result.series[0].points[0][1]

        assert value_for("min") == pytest.approx(10.0)
        assert value_for("max") == pytest.approx(60.0)
        assert value_for("count") == pytest.approx(6.0)

    def test_percentiles_interpolate_rather_than_pick_a_sample(self, db, org, cpu_series):
        result = mqs.run_query(
            db,
            mqs.MetricQuery(
                organization_id=org.id,
                metric_name="system.cpu.utilization",
                start=BASE,
                end=BASE + timedelta(minutes=6),
                aggregation="p50",
                bucket_seconds=3600,
                max_points=10,
            ),
        )
        # Median of 10..60 is 35, which is not any individual sample.
        assert result.series[0].points[0][1] == pytest.approx(35.0)

    def test_buckets_split_the_range_at_the_requested_width(self, db, org, cpu_series):
        result = mqs.run_query(
            db,
            mqs.MetricQuery(
                organization_id=org.id,
                metric_name="system.cpu.utilization",
                start=BASE,
                end=BASE + timedelta(minutes=6),
                aggregation="avg",
                bucket_seconds=180,
                max_points=10,
            ),
        )
        points = result.series[0].points
        assert len(points) == 2
        assert points[0][1] == pytest.approx(20.0)  # 10, 20, 30
        assert points[1][1] == pytest.approx(50.0)  # 40, 50, 60

    def test_the_first_bucket_starts_exactly_at_the_requested_start(self, db, org, cpu_series):
        odd_start = BASE + timedelta(seconds=7)
        result = mqs.run_query(
            db,
            mqs.MetricQuery(
                organization_id=org.id,
                metric_name="system.cpu.utilization",
                start=odd_start,
                end=odd_start + timedelta(minutes=5),
                aggregation="avg",
                bucket_seconds=60,
                max_points=10,
            ),
        )
        assert result.series[0].points[0][0] == odd_start


class TestMeaninglessAggregationsAreRefused:
    def test_summing_a_gauge_is_rejected_with_a_reason(self, db, org, cpu_series):
        with pytest.raises(mqs.MetricQueryError) as exc:
            mqs.run_query(
                db,
                mqs.MetricQuery(
                    organization_id=org.id,
                    metric_name="system.cpu.utilization",
                    start=BASE,
                    end=BASE + timedelta(minutes=6),
                    aggregation="sum",
                ),
            )
        assert "delta sums" in str(exc.value)

    def test_summing_a_cumulative_counter_is_rejected(self, db, org):
        _, series = _make_series(
            db, org.id, metric="http.server.requests", kind="sum_cumulative", unit="1"
        )
        _add_points(db, org.id, series, [1, 2, 3])
        db.commit()
        with pytest.raises(mqs.MetricQueryError):
            mqs.run_query(
                db,
                mqs.MetricQuery(
                    organization_id=org.id,
                    metric_name="http.server.requests",
                    start=BASE,
                    end=BASE + timedelta(minutes=6),
                    aggregation="sum",
                ),
            )

    def test_summing_a_delta_counter_is_allowed(self, db, org):
        _, series = _make_series(db, org.id, metric="http.server.errors", kind="sum_delta", unit="1")
        _add_points(db, org.id, series, [1, 2, 3])
        db.commit()
        result = mqs.run_query(
            db,
            mqs.MetricQuery(
                organization_id=org.id,
                metric_name="http.server.errors",
                start=BASE,
                end=BASE + timedelta(minutes=6),
                aggregation="sum",
                bucket_seconds=3600,
                max_points=10,
            ),
        )
        assert result.series[0].points[0][1] == pytest.approx(6.0)

    def test_an_unknown_aggregation_is_rejected(self, db, org, cpu_series):
        with pytest.raises(mqs.MetricQueryError):
            mqs.run_query(
                db,
                mqs.MetricQuery(
                    organization_id=org.id,
                    metric_name="system.cpu.utilization",
                    start=BASE,
                    end=BASE + timedelta(minutes=6),
                    aggregation="median",
                ),
            )


class TestBounds:
    def test_a_range_wider_than_the_maximum_is_refused(self, db, org, cpu_series):
        with pytest.raises(mqs.MetricQueryError) as exc:
            mqs.run_query(
                db,
                mqs.MetricQuery(
                    organization_id=org.id,
                    metric_name="system.cpu.utilization",
                    start=BASE - timedelta(days=400),
                    end=BASE,
                ),
            )
        assert "maximum" in str(exc.value)

    def test_an_inverted_range_is_refused(self, db, org, cpu_series):
        with pytest.raises(mqs.MetricQueryError):
            mqs.run_query(
                db,
                mqs.MetricQuery(
                    organization_id=org.id,
                    metric_name="system.cpu.utilization",
                    start=BASE,
                    end=BASE - timedelta(minutes=1),
                ),
            )

    def test_an_explicit_bucket_that_would_blow_the_budget_is_refused(self, db, org, cpu_series):
        with pytest.raises(mqs.MetricQueryError) as exc:
            mqs.run_query(
                db,
                mqs.MetricQuery(
                    organization_id=org.id,
                    metric_name="system.cpu.utilization",
                    start=BASE,
                    end=BASE + timedelta(days=7),
                    bucket_seconds=10,
                    max_points=100,
                ),
            )
        assert "max_points" in str(exc.value)

    def test_automatic_resolution_never_exceeds_max_points(self, db, org, cpu_series):
        result = mqs.run_query(
            db,
            mqs.MetricQuery(
                organization_id=org.id,
                metric_name="system.cpu.utilization",
                start=BASE - timedelta(days=30),
                end=BASE + timedelta(days=1),
                max_points=50,
            ),
        )
        assert all(len(s.points) <= 50 for s in result.series)

    def test_too_many_group_by_keys_are_refused(self, db, org, cpu_series):
        with pytest.raises(mqs.MetricQueryError):
            mqs.run_query(
                db,
                mqs.MetricQuery(
                    organization_id=org.id,
                    metric_name="system.cpu.utilization",
                    start=BASE,
                    end=BASE + timedelta(minutes=6),
                    group_by=("a", "b", "c", "d"),
                ),
            )


class TestGrouping:
    def test_grouping_by_an_attribute_splits_the_result(self, db, org):
        _, disk_c = _make_series(
            db, org.id, metric="system.disk.utilization", attributes={"disk.device": "C:"}
        )
        _, disk_d = _make_series(
            db, org.id, metric="system.disk.utilization", attributes={"disk.device": "D:"}
        )
        _add_points(db, org.id, disk_c, [10, 10, 10])
        _add_points(db, org.id, disk_d, [90, 90, 90])
        db.commit()

        result = mqs.run_query(
            db,
            mqs.MetricQuery(
                organization_id=org.id,
                metric_name="system.disk.utilization",
                start=BASE,
                end=BASE + timedelta(minutes=6),
                group_by=("disk.device",),
                bucket_seconds=3600,
                max_points=10,
            ),
        )
        by_label = {s.labels["disk.device"]: s.points[0][1] for s in result.series}
        assert by_label == {"C:": pytest.approx(10.0), "D:": pytest.approx(90.0)}

    def test_an_attribute_filter_narrows_the_selection(self, db, org):
        _, disk_c = _make_series(db, org.id, metric="disk.free", attributes={"disk.device": "C:"})
        _, disk_d = _make_series(db, org.id, metric="disk.free", attributes={"disk.device": "D:"})
        _add_points(db, org.id, disk_c, [1, 1])
        _add_points(db, org.id, disk_d, [99, 99])
        db.commit()

        result = mqs.run_query(
            db,
            mqs.MetricQuery(
                organization_id=org.id,
                metric_name="disk.free",
                start=BASE,
                end=BASE + timedelta(minutes=6),
                filters={"disk.device": "C:"},
                bucket_seconds=3600,
                max_points=10,
            ),
        )
        assert result.series[0].points[0][1] == pytest.approx(1.0)

    def test_an_attribute_key_that_looks_like_sql_is_treated_as_data(self, db, org, cpu_series):
        # The group key reaches SQL as a bind parameter, so this is a lookup
        # that finds nothing rather than an injection.
        result = mqs.run_query(
            db,
            mqs.MetricQuery(
                organization_id=org.id,
                metric_name="system.cpu.utilization",
                start=BASE,
                end=BASE + timedelta(minutes=6),
                group_by=("x'; DROP TABLE metric_points; --",),
                bucket_seconds=3600,
                max_points=10,
            ),
        )
        assert result.series[0].labels == {"x'; DROP TABLE metric_points; --": "(none)"}
        # The table is very much still there.
        assert db.query(MetricPoint).count() > 0


class TestTenantIsolation:
    def test_one_organisation_cannot_see_another_organisations_points(self, db, org, cpu_series):
        other = Organization(name=f"Other {uuid.uuid4().hex[:8]}", slug=f"other-{uuid.uuid4().hex[:8]}")
        db.add(other)
        db.flush()
        _, other_series = _make_series(db, other.id, metric="system.cpu.utilization")
        _add_points(db, other.id, other_series, [99, 99, 99])
        db.commit()

        result = mqs.run_query(
            db,
            mqs.MetricQuery(
                organization_id=org.id,
                metric_name="system.cpu.utilization",
                start=BASE,
                end=BASE + timedelta(minutes=6),
                bucket_seconds=3600,
                max_points=10,
            ),
        )
        assert result.series[0].points[0][1] == pytest.approx(35.0)

    def test_the_catalog_is_organisation_scoped(self, db, org, cpu_series):
        other = Organization(name=f"Other {uuid.uuid4().hex[:8]}", slug=f"other-{uuid.uuid4().hex[:8]}")
        db.add(other)
        db.flush()
        _make_series(db, other.id, metric="secret.internal.metric")
        db.commit()

        page = mqs.list_metric_catalog(db, org.id)
        assert "secret.internal.metric" not in {i["metric_name"] for i in page.items}


class TestDiscovery:
    def test_the_catalog_reports_kind_unit_and_series_count(self, db, org, cpu_series):
        page = mqs.list_metric_catalog(db, org.id, search="cpu")
        entry = next(i for i in page.items if i["metric_name"] == "system.cpu.utilization")
        assert entry["kind"] == "gauge"
        assert entry["unit"] == "%"
        assert entry["series_count"] == 1

    def test_catalog_search_treats_wildcards_as_literal_text(self, db, org, cpu_series):
        # A bare "%" must not match everything.
        page = mqs.list_metric_catalog(db, org.id, search="%")
        assert page.items == []

    def test_series_listing_exposes_the_dimensions(self, db, org):
        _, series = _make_series(db, org.id, metric="queue.depth", attributes={"queue": "outbox"})
        db.commit()
        page = mqs.list_series(db, org.id, "queue.depth")
        assert page.items[0]["attributes"] == {"queue": "outbox"}
        assert page.items[0]["series_id"] == series.id

    def test_the_catalog_pages_with_a_stable_cursor(self, db, org):
        for name in ("mzz.a", "mzz.b", "mzz.c"):
            _make_series(db, org.id, metric=name)
        db.commit()

        first = mqs.list_metric_catalog(db, org.id, search="mzz.", limit=2)
        assert [i["metric_name"] for i in first.items] == ["mzz.a", "mzz.b"]
        assert first.next_cursor == "mzz.b"

        second = mqs.list_metric_catalog(db, org.id, search="mzz.", limit=2, cursor=first.next_cursor)
        assert [i["metric_name"] for i in second.items] == ["mzz.c"]
        assert second.next_cursor is None


class TestThroughTheApi:
    def test_a_query_returns_downsampled_series(self, client, admin_headers, cpu_series):
        response = client.post(
            "/api/v1/metric-query",
            headers=admin_headers,
            json={
                "metric": "system.cpu.utilization",
                "start": BASE.isoformat(),
                "end": (BASE + timedelta(minutes=6)).isoformat(),
                "aggregation": "avg",
                "bucket_seconds": 3600,
                "max_points": 10,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["unit"] == "%"
        assert body["kind"] == "gauge"
        assert body["series"][0]["points"][0]["v"] == pytest.approx(35.0)

    def test_an_invalid_aggregation_is_a_400_not_a_500(self, client, admin_headers, cpu_series):
        response = client.post(
            "/api/v1/metric-query",
            headers=admin_headers,
            json={
                "metric": "system.cpu.utilization",
                "start": BASE.isoformat(),
                "end": (BASE + timedelta(minutes=6)).isoformat(),
                "aggregation": "sum",
            },
        )
        assert response.status_code == 400
        assert "delta sums" in response.json()["detail"]

    def test_an_unknown_field_in_the_body_is_rejected(self, client, admin_headers):
        response = client.post(
            "/api/v1/metric-query",
            headers=admin_headers,
            json={
                "metric": "x",
                "start": BASE.isoformat(),
                "end": (BASE + timedelta(minutes=6)).isoformat(),
                "sneaky_organization_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 422

    def test_the_endpoint_requires_authentication(self, client):
        response = client.post(
            "/api/v1/metric-query",
            json={
                "metric": "x",
                "start": BASE.isoformat(),
                "end": (BASE + timedelta(minutes=6)).isoformat(),
            },
        )
        assert response.status_code == 401

    def test_a_viewer_may_read_metrics(self, client, db, org, cpu_series):
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
        response = client.post(
            "/api/v1/metric-query",
            headers=auth_headers_for(db, viewer),
            json={
                "metric": "system.cpu.utilization",
                "start": BASE.isoformat(),
                "end": (BASE + timedelta(minutes=6)).isoformat(),
                "bucket_seconds": 3600,
                "max_points": 10,
            },
        )
        assert response.status_code == 200

    def test_the_catalog_endpoint_pages(self, client, admin_headers, cpu_series):
        response = client.get("/api/v1/metric-query/catalog?limit=1", headers=admin_headers)
        assert response.status_code == 200
        assert len(response.json()["items"]) <= 1
