"""OTLP/HTTP metrics ingestion.

Ingestion is the one endpoint that accepts bytes from something SentinelX does
not control, so most of what is pinned here is what happens when those bytes
are hostile: bombs, garbage, forged identities and runaway cardinality. The
happy path matters too, but it is the smaller half.
"""

from __future__ import annotations

import gzip
import math
import time
import uuid
import zlib
from datetime import datetime, timedelta, timezone

import pytest
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
from opentelemetry.proto.common.v1 import common_pb2
from opentelemetry.proto.metrics.v1 import metrics_pb2
from opentelemetry.proto.resource.v1 import resource_pb2
from sqlalchemy import select

from app.models.metric_point import MetricPoint
from app.models.metric_series import MetricSeries
from app.models.resource import Resource
from app.models.security_log import SecurityLog
from app.services import ingest_credential_service as ics

OTLP_PATH = "/v1/metrics"
PROTOBUF = "application/x-protobuf"


# ── payload builders ────────────────────────────────────────────────────────


def _attr(key, value):
    kv = common_pb2.KeyValue(key=key)
    if isinstance(value, bool):
        kv.value.bool_value = value
    elif isinstance(value, int):
        kv.value.int_value = value
    elif isinstance(value, float):
        kv.value.double_value = value
    else:
        kv.value.string_value = str(value)
    return kv


def _now_nanos(offset_seconds: float = 0.0) -> int:
    return int((time.time() + offset_seconds) * 1_000_000_000)


def _gauge(name, value, *, unit="1", attributes=None, nanos=None):
    metric = metrics_pb2.Metric(name=name, unit=unit)
    point = metric.gauge.data_points.add()
    point.as_double = value
    point.time_unix_nano = nanos if nanos is not None else _now_nanos()
    for k, v in (attributes or {}).items():
        point.attributes.append(_attr(k, v))
    return metric


def _sum(name, value, *, temporality, unit="1"):
    metric = metrics_pb2.Metric(name=name, unit=unit)
    metric.sum.aggregation_temporality = temporality
    metric.sum.is_monotonic = True
    point = metric.sum.data_points.add()
    point.as_int = value
    point.time_unix_nano = _now_nanos()
    return metric


def _histogram(name):
    metric = metrics_pb2.Metric(name=name, unit="ms")
    point = metric.histogram.data_points.add()
    point.count = 3
    point.sum = 10.0
    point.time_unix_nano = _now_nanos()
    return metric


def _request(metrics, resource_attributes=None):
    request = metrics_service_pb2.ExportMetricsServiceRequest()
    resource_metrics = request.resource_metrics.add()
    attributes = (
        resource_attributes
        if resource_attributes is not None
        else {"service.name": "checkout", "service.version": "1.4.2"}
    )
    resource_metrics.resource.CopyFrom(
        resource_pb2.Resource(attributes=[_attr(k, v) for k, v in attributes.items()])
    )
    scope_metrics = resource_metrics.scope_metrics.add()
    for metric in metrics:
        scope_metrics.metrics.append(metric)
    return request.SerializeToString()


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def ingest_key(db, org):
    issued = ics.create_credential(db, organization_id=org.id, name="pytest collector")
    db.commit()
    return issued.plaintext


def _post(client, key, payload, *, encoding=None, content_type=PROTOBUF):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": content_type}
    if encoding:
        headers["Content-Encoding"] = encoding
    return client.post(OTLP_PATH, content=payload, headers=headers)


def _partial(response):
    parsed = metrics_service_pb2.ExportMetricsServiceResponse()
    parsed.ParseFromString(response.content)
    return parsed.partial_success


def _values(db, org_id, name):
    return sorted(
        db.scalars(
            select(MetricPoint.value)
            .join(MetricSeries, MetricSeries.id == MetricPoint.series_id)
            .where(MetricSeries.organization_id == org_id, MetricSeries.metric_name == name)
        )
    )


# ── tests ───────────────────────────────────────────────────────────────────


class TestAuthentication:
    def test_no_credential_is_rejected(self, client):
        response = client.post(
            OTLP_PATH, content=_request([_gauge("m", 1.0)]), headers={"Content-Type": PROTOBUF}
        )
        assert response.status_code == 401

    def test_a_garbage_credential_is_rejected(self, client):
        response = _post(client, "sxi_live_notarealkey", _request([_gauge("m", 1.0)]))
        assert response.status_code == 401

    def test_a_device_token_is_not_an_ingest_credential(self, client, enrolled_device):
        """The two credential types must not be interchangeable."""
        _device, device_token = enrolled_device
        response = _post(client, device_token, _request([_gauge("m", 1.0)]))
        assert response.status_code == 401

    def test_a_revoked_credential_stops_working(self, client, db, org, ingest_key):
        credential = ics.resolve_credential(db, ingest_key)
        ics.revoke(credential)
        db.commit()

        assert _post(client, ingest_key, _request([_gauge("m", 1.0)])).status_code == 401

    def test_an_expired_credential_stops_working(self, client, db, org):
        issued = ics.create_credential(
            db,
            organization_id=org.id,
            name="expiring",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.commit()

        assert _post(client, issued.plaintext, _request([_gauge("m", 1.0)])).status_code == 401

    def test_a_failed_authentication_is_logged(self, client, db):
        _post(client, "sxi_live_bogus", _request([_gauge("m", 1.0)]))
        logs = db.scalars(
            select(SecurityLog).where(SecurityLog.event_type == "ingest_auth_failure")
        ).all()
        assert logs


class TestHappyPath:
    def test_a_gauge_is_stored(self, client, db, org, ingest_key):
        response = _post(
            client, ingest_key, _request([_gauge("http.server.duration", 12.5, unit="ms")])
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith(PROTOBUF)
        assert _values(db, org.id, "http.server.duration") == [12.5]

    def test_full_success_returns_an_empty_partial_success(self, client, ingest_key):
        """The specification is explicit: empty means fully accepted.

        A present-but-zero partial_success is read by some clients as a partial
        failure, so it must not be emitted on success.
        """
        response = _post(client, ingest_key, _request([_gauge("m", 1.0)]))
        assert _partial(response).rejected_data_points == 0
        assert _partial(response).error_message == ""

    def test_the_resource_is_created_from_otel_attributes(self, client, db, org, ingest_key):
        _post(client, ingest_key, _request([_gauge("m", 1.0)]))

        resource = db.scalar(
            select(Resource).where(
                Resource.organization_id == org.id, Resource.resource_type == "service"
            )
        )
        assert resource is not None
        assert resource.identifying_attributes == {"service.name": "checkout"}
        # Version describes rather than identifies, so a deploy is not a new
        # service.
        assert resource.attributes["service.version"] == "1.4.2"

    def test_an_int_point_is_accepted(self, client, db, org, ingest_key):
        payload = _request([_sum("requests.total", 42, temporality=2)])
        assert _post(client, ingest_key, payload).status_code == 200
        assert _values(db, org.id, "requests.total") == [42.0]

    def test_point_attributes_separate_series(self, client, db, org, ingest_key):
        payload = _request(
            [
                _gauge("http.duration", 1.0, attributes={"http.route": "/a"}),
                _gauge("http.duration", 2.0, attributes={"http.route": "/b"}),
            ]
        )
        _post(client, ingest_key, payload)

        series = db.scalars(
            select(MetricSeries).where(
                MetricSeries.organization_id == org.id,
                MetricSeries.metric_name == "http.duration",
            )
        ).all()
        assert len(series) == 2

    def test_delta_and_cumulative_sums_are_different_series(self, client, db, org, ingest_key):
        """One is an increment, the other a running total.

        Averaging one into the other would be meaningless, so temporality is
        part of series identity.
        """
        _post(client, ingest_key, _request([_sum("ops", 1, temporality=1)]))
        _post(client, ingest_key, _request([_sum("ops", 100, temporality=2)]))

        kinds = set(
            db.scalars(
                select(MetricSeries.metric_kind).where(
                    MetricSeries.organization_id == org.id, MetricSeries.metric_name == "ops"
                )
            )
        )
        assert kinds == {"sum_delta", "sum_cumulative"}

    def test_the_client_timestamp_is_preserved(self, client, db, org, ingest_key):
        earlier = _now_nanos(-3600)
        _post(client, ingest_key, _request([_gauge("m", 1.0, nanos=earlier)]))

        recorded = db.scalar(
            select(MetricPoint.recorded_at)
            .join(MetricSeries, MetricSeries.id == MetricPoint.series_id)
            .where(MetricSeries.organization_id == org.id)
        )
        assert abs((datetime.now(timezone.utc) - recorded).total_seconds() - 3600) < 120

    def test_last_used_is_recorded(self, client, db, org, ingest_key):
        _post(client, ingest_key, _request([_gauge("m", 1.0)]))
        db.expire_all()
        assert ics.resolve_credential(db, ingest_key).last_used_at is not None


class TestCompression:
    def test_gzip_is_accepted(self, client, db, org, ingest_key):
        payload = gzip.compress(_request([_gauge("gz.metric", 7.0)]))
        response = _post(client, ingest_key, payload, encoding="gzip")

        assert response.status_code == 200
        assert _values(db, org.id, "gz.metric") == [7.0]

    def test_a_decompression_bomb_is_refused(self, client, ingest_key):
        """Small on the wire, enormous inflated — the classic shape.

        The ceiling has to be enforced DURING inflation; checking afterwards is
        checking after the memory has already been allocated.
        """
        bomb = gzip.compress(b"\0" * (64 * 1024 * 1024))
        assert len(bomb) < 100_000  # tiny on the wire

        response = _post(client, ingest_key, bomb, encoding="gzip")
        assert response.status_code == 413

    def test_corrupt_gzip_is_a_bad_request_not_a_crash(self, client, ingest_key):
        response = _post(client, ingest_key, b"\x1f\x8b\x08 not really gzip", encoding="gzip")
        assert response.status_code == 400

    def test_gzip_body_declared_but_absent(self, client, ingest_key):
        response = _post(client, ingest_key, _request([_gauge("m", 1.0)]), encoding="gzip")
        assert response.status_code == 400


class TestMalformedInput:
    def test_random_bytes_are_rejected(self, client, ingest_key):
        response = _post(client, ingest_key, b"\xff\xfe\xfd\xfc" * 100)
        assert response.status_code == 400

    def test_an_oversized_body_is_refused(self, client, ingest_key):
        response = _post(client, ingest_key, b"\x00" * (2 * 1024 * 1024))
        assert response.status_code == 413

    def test_json_content_type_is_refused_honestly(self, client, ingest_key):
        """OTLP/JSON is real; this build does not implement it.

        Accepting the content type and then mis-parsing would be worse than an
        honest 415.
        """
        response = _post(client, ingest_key, b"{}", content_type="application/json")
        assert response.status_code == 415

    def test_an_empty_body_is_a_valid_empty_export(self, client, ingest_key):
        assert _post(client, ingest_key, b"").status_code == 200


class TestPartialSuccess:
    def test_one_bad_point_does_not_discard_the_good_ones(self, client, db, org, ingest_key):
        """The whole reason partial success exists.

        A blanket rejection makes the client retry the entire batch forever and
        never learn which point to fix.
        """
        payload = _request(
            [
                _gauge("good.one", 1.0),
                _histogram("unsupported.hist"),
                _gauge("good.two", 2.0),
            ]
        )
        response = _post(client, ingest_key, payload)

        assert response.status_code == 200
        assert _partial(response).rejected_data_points == 1
        assert _values(db, org.id, "good.one") == [1.0]
        assert _values(db, org.id, "good.two") == [2.0]

    def test_the_rejection_names_the_reason(self, client, ingest_key):
        response = _post(client, ingest_key, _request([_histogram("h")]))
        message = _partial(response).error_message
        assert "unsupported_metric_type" in message
        assert "histogram" in message

    def test_a_nan_value_is_refused(self, client, db, org, ingest_key):
        """Postgres would store NaN happily; every aggregate over it is wrong."""
        response = _post(client, ingest_key, _request([_gauge("nan.metric", math.nan)]))
        assert _partial(response).rejected_data_points == 1
        assert _values(db, org.id, "nan.metric") == []

    def test_an_infinite_value_is_refused(self, client, db, org, ingest_key):
        response = _post(client, ingest_key, _request([_gauge("inf.metric", math.inf)]))
        assert _partial(response).rejected_data_points == 1

    def test_a_far_future_timestamp_is_refused(self, client, db, org, ingest_key):
        payload = _request([_gauge("future", 1.0, nanos=_now_nanos(86_400))])
        response = _post(client, ingest_key, payload)
        assert _partial(response).rejected_data_points == 1
        assert _values(db, org.id, "future") == []

    def test_an_ancient_timestamp_is_refused(self, client, db, org, ingest_key):
        payload = _request([_gauge("ancient", 1.0, nanos=_now_nanos(-86_400 * 400))])
        response = _post(client, ingest_key, payload)
        assert _partial(response).rejected_data_points == 1

    def test_excess_attributes_are_refused(self, client, db, org, ingest_key):
        payload = _request([_gauge("wide", 1.0, attributes={f"k{i}": "v" for i in range(200)})])
        response = _post(client, ingest_key, payload)
        assert _partial(response).rejected_data_points == 1
        assert _values(db, org.id, "wide") == []

    def test_a_resource_with_no_identity_is_refused(self, client, db, org, ingest_key):
        payload = _request([_gauge("orphan", 1.0)], resource_attributes={"colour": "blue"})
        response = _post(client, ingest_key, payload)
        assert _partial(response).rejected_data_points == 1
        assert _values(db, org.id, "orphan") == []

    def test_rejections_are_recorded_as_security_events(self, client, db, ingest_key):
        _post(client, ingest_key, _request([_histogram("h")]))
        logs = db.scalars(
            select(SecurityLog).where(SecurityLog.event_type == "telemetry_rejected")
        ).all()
        assert logs


class TestTenantIsolation:
    def test_the_organisation_comes_from_the_credential(self, client, db, org, ingest_key):
        """An attribute claiming another tenant is just an attribute."""
        other_org_id = uuid.uuid4()
        # Unique name: the test database is shared, and a generic one would
        # sweep up series other tests created in other organisations.
        name = f"tenant.probe.{uuid.uuid4().hex[:8]}"
        payload = _request(
            [_gauge(name, 1.0)],
            resource_attributes={
                "service.name": "checkout",
                "sentinelx.organization.id": str(other_org_id),
            },
        )
        _post(client, ingest_key, payload)

        series = db.scalars(select(MetricSeries).where(MetricSeries.metric_name == name)).all()
        assert series
        assert all(s.organization_id == org.id for s in series)
        assert not any(s.organization_id == other_org_id for s in series)

    def test_a_client_cannot_forge_a_sentinelx_resource_identity(self, client, db, org, ingest_key):
        """`sentinelx.*` can pin an identity, so it carries authority."""
        payload = _request(
            [_gauge("forge", 1.0)],
            resource_attributes={
                "sentinelx.resource.id": str(uuid.uuid4()),
                "host.name": "attacker-host",
            },
        )
        _post(client, ingest_key, payload)

        resource = db.scalar(
            select(Resource).where(
                Resource.organization_id == org.id,
                Resource.identifying_attributes["host.name"].astext == "attacker-host",
            )
        )
        assert resource is not None
        assert "sentinelx.resource.id" not in resource.identifying_attributes

    def test_two_tenants_keep_separate_series(self, client, db, org, ingest_key):
        from app.models.organization import Organization

        suffix = uuid.uuid4().hex[:8]
        other = Organization(name=f"Other {suffix}", slug=f"otlp-other-{suffix}")
        db.add(other)
        db.commit()
        other_key = ics.create_credential(
            db, organization_id=other.id, name="other collector"
        ).plaintext
        db.commit()

        _post(client, ingest_key, _request([_gauge("shared.name", 1.0)]))
        _post(client, other_key, _request([_gauge("shared.name", 2.0)]))

        assert _values(db, org.id, "shared.name") == [1.0]
        assert _values(db, other.id, "shared.name") == [2.0]


class TestSafeGunzip:
    """The bomb guard, exercised directly as well as through the endpoint."""

    def test_a_normal_payload_round_trips(self):
        from app.services.otlp_ingest_service import safe_gunzip

        assert safe_gunzip(gzip.compress(b"hello"), max_output=1024) == b"hello"

    def test_output_over_the_ceiling_raises(self):
        from app.services.otlp_ingest_service import PayloadTooLarge, safe_gunzip

        with pytest.raises(PayloadTooLarge):
            safe_gunzip(gzip.compress(b"x" * 10_000), max_output=1_000)

    def test_exactly_at_the_ceiling_is_allowed(self):
        from app.services.otlp_ingest_service import safe_gunzip

        assert len(safe_gunzip(gzip.compress(b"x" * 1000), max_output=1000)) == 1000

    def test_raw_deflate_is_not_mistaken_for_gzip(self):
        from app.services.otlp_ingest_service import MalformedPayload, safe_gunzip

        with pytest.raises(MalformedPayload):
            safe_gunzip(zlib.compress(b"hello"), max_output=1024)
