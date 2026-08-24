"""OTLP/HTTP logs and traces ingestion.

Same posture as the metrics suite: these endpoints take bytes from something
SentinelX does not control, so most of what is pinned here is what happens when
those bytes are hostile or merely careless. Two properties get extra attention
because they are specific to these signals - that a credential arriving as a
log attribute never reaches storage, and that a trace's parent/child structure
survives spans arriving in the wrong order.
"""

from __future__ import annotations

import gzip
import time
import uuid

import pytest
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
from opentelemetry.proto.common.v1 import common_pb2
from opentelemetry.proto.logs.v1 import logs_pb2
from opentelemetry.proto.resource.v1 import resource_pb2
from opentelemetry.proto.trace.v1 import trace_pb2
from sqlalchemy import select

from app.core.config import get_settings
from app.models.log_record import LogRecord
from app.models.organization import Organization
from app.models.resource import Resource
from app.models.span import Span
from app.services import ingest_credential_service as ics

LOGS_PATH = "/v1/logs"
TRACES_PATH = "/v1/traces"
PROTOBUF = "application/x-protobuf"

DEFAULT_RESOURCE = {
    "service.name": "checkout-api",
    "service.version": "2.1.0",
    "deployment.environment.name": "production",
}


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


def _log(
    body="checkout failed",
    *,
    severity=17,
    severity_text="ERROR",
    attributes=None,
    trace_id=None,
    span_id=None,
    nanos=None,
):
    stamp = nanos if nanos is not None else _now_nanos()
    record = logs_pb2.LogRecord(
        severity_number=severity,
        severity_text=severity_text,
        time_unix_nano=stamp,
        observed_time_unix_nano=stamp,
    )
    record.body.string_value = body
    for key, value in (attributes or {}).items():
        record.attributes.append(_attr(key, value))
    if trace_id:
        record.trace_id = bytes.fromhex(trace_id)
    if span_id:
        record.span_id = bytes.fromhex(span_id)
    return record


def _logs_request(records, resource_attributes=None, scope_name="pytest.logger"):
    request = logs_service_pb2.ExportLogsServiceRequest()
    resource_logs = request.resource_logs.add()
    attributes = DEFAULT_RESOURCE if resource_attributes is None else resource_attributes
    resource_logs.resource.CopyFrom(
        resource_pb2.Resource(attributes=[_attr(k, v) for k, v in attributes.items()])
    )
    scope_logs = resource_logs.scope_logs.add()
    scope_logs.scope.name = scope_name
    scope_logs.scope.version = "1.0.0"
    for record in records:
        scope_logs.log_records.append(record)
    return request.SerializeToString()


def _span(
    *,
    trace_id,
    span_id,
    parent_span_id=None,
    name="POST /checkout",
    kind=2,
    status=0,
    status_message="",
    duration_ms=120,
    attributes=None,
    events=None,
    start_nanos=None,
):
    start = start_nanos if start_nanos is not None else _now_nanos(-1)
    span = trace_pb2.Span(
        trace_id=bytes.fromhex(trace_id),
        span_id=bytes.fromhex(span_id),
        name=name,
        kind=kind,
        start_time_unix_nano=start,
        end_time_unix_nano=start + duration_ms * 1_000_000,
    )
    if parent_span_id:
        span.parent_span_id = bytes.fromhex(parent_span_id)
    span.status.code = status
    if status_message:
        span.status.message = status_message
    for key, value in (attributes or {}).items():
        span.attributes.append(_attr(key, value))
    for event_name, event_attributes in events or []:
        event = span.events.add()
        event.name = event_name
        event.time_unix_nano = start
        for key, value in event_attributes.items():
            event.attributes.append(_attr(key, value))
    return span


def _traces_request(spans, resource_attributes=None):
    request = trace_service_pb2.ExportTraceServiceRequest()
    resource_spans = request.resource_spans.add()
    attributes = DEFAULT_RESOURCE if resource_attributes is None else resource_attributes
    resource_spans.resource.CopyFrom(
        resource_pb2.Resource(attributes=[_attr(k, v) for k, v in attributes.items()])
    )
    scope_spans = resource_spans.scope_spans.add()
    scope_spans.scope.name = "pytest.tracer"
    for span in spans:
        scope_spans.spans.append(span)
    return request.SerializeToString()


def _trace_id():
    return uuid.uuid4().hex


def _span_id():
    return uuid.uuid4().hex[:16]


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def logs_key(db, org):
    issued = ics.create_credential(
        db, organization_id=org.id, name="log collector", scopes=["logs:write"]
    )
    db.commit()
    return issued.plaintext


@pytest.fixture()
def traces_key(db, org):
    issued = ics.create_credential(
        db, organization_id=org.id, name="trace collector", scopes=["traces:write"]
    )
    db.commit()
    return issued.plaintext


def _post(client, path, key, payload, *, encoding=None, content_type=PROTOBUF):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": content_type}
    if encoding:
        headers["Content-Encoding"] = encoding
    return client.post(path, content=payload, headers=headers)


def _logs_partial(response):
    parsed = logs_service_pb2.ExportLogsServiceResponse()
    parsed.ParseFromString(response.content)
    return parsed.partial_success


def _traces_partial(response):
    parsed = trace_service_pb2.ExportTraceServiceResponse()
    parsed.ParseFromString(response.content)
    return parsed.partial_success


def _stored_logs(db, org_id):
    return list(db.scalars(select(LogRecord).where(LogRecord.organization_id == org_id)))


def _stored_spans(db, org_id):
    return list(db.scalars(select(Span).where(Span.organization_id == org_id)))


# ── logs ────────────────────────────────────────────────────────────────────


class TestLogIngestion:
    def test_a_log_record_is_stored_with_its_severity_and_body(self, client, db, org, logs_key):
        response = _post(client, LOGS_PATH, logs_key, _logs_request([_log()]))
        assert response.status_code == 200, response.text

        records = _stored_logs(db, org.id)
        assert len(records) == 1
        record = records[0]
        assert record.body == "checkout failed"
        assert record.severity_number == 17
        assert record.severity_text == "ERROR"
        # The band is what a filter uses; 17 is the bottom of "error".
        assert record.severity_band == "error"

    def test_service_environment_and_version_come_off_the_resource(
        self, client, db, org, logs_key
    ):
        _post(client, LOGS_PATH, logs_key, _logs_request([_log()]))
        record = _stored_logs(db, org.id)[0]
        assert record.service_name == "checkout-api"
        assert record.environment == "production"
        assert record.service_version == "2.1.0"

    def test_the_scope_that_emitted_the_record_is_kept(self, client, db, org, logs_key):
        _post(client, LOGS_PATH, logs_key, _logs_request([_log()]))
        record = _stored_logs(db, org.id)[0]
        assert record.scope_name == "pytest.logger"
        assert record.scope_version == "1.0.0"

    def test_trace_and_span_ids_survive_as_hex(self, client, db, org, logs_key):
        trace_id, span_id = _trace_id(), _span_id()
        _post(
            client, LOGS_PATH, logs_key, _logs_request([_log(trace_id=trace_id, span_id=span_id)])
        )
        record = _stored_logs(db, org.id)[0]
        # Hex exactly as sent, so an id pasted from a trace matches without
        # conversion.
        assert record.trace_id == trace_id
        assert record.span_id == span_id

    def test_a_resource_is_created_once_and_reused(self, client, db, org, logs_key):
        _post(client, LOGS_PATH, logs_key, _logs_request([_log()]))
        _post(client, LOGS_PATH, logs_key, _logs_request([_log(body="second")]))

        resources = list(
            db.scalars(
                select(Resource).where(
                    Resource.organization_id == org.id, Resource.resource_type == "service"
                )
            )
        )
        assert len(resources) == 1

    def test_a_severity_of_zero_is_unspecified_not_info(self, client, db, org, logs_key):
        """Promoting an unset severity to info would hide it from a filter that
        excludes info - exactly the wrong direction to be wrong in."""
        _post(client, LOGS_PATH, logs_key, _logs_request([_log(severity=0, severity_text="")]))
        assert _stored_logs(db, org.id)[0].severity_band == "unspecified"

    def test_severity_numbers_map_onto_bands(self, client, db, org, logs_key):
        _post(
            client,
            LOGS_PATH,
            logs_key,
            _logs_request(
                [
                    _log(body="t", severity=1),
                    _log(body="d", severity=5),
                    _log(body="i", severity=9),
                    _log(body="w", severity=13),
                    _log(body="e", severity=17),
                    _log(body="f", severity=21),
                ]
            ),
        )
        bands = {r.body: r.severity_band for r in _stored_logs(db, org.id)}
        assert bands == {
            "t": "trace",
            "d": "debug",
            "i": "info",
            "w": "warn",
            "e": "error",
            "f": "fatal",
        }

    def test_a_structured_body_is_rendered_rather_than_dropped(self, client, db, org, logs_key):
        record = logs_pb2.LogRecord(severity_number=9, observed_time_unix_nano=_now_nanos())
        entry = record.body.kvlist_value.values.add()
        entry.key = "event"
        entry.value.string_value = "order_placed"
        _post(client, LOGS_PATH, logs_key, _logs_request([record]))

        stored = _stored_logs(db, org.id)[0]
        assert stored.body and "order_placed" in stored.body

    def test_gzip_is_accepted(self, client, db, org, logs_key):
        payload = gzip.compress(_logs_request([_log()]))
        response = _post(client, LOGS_PATH, logs_key, payload, encoding="gzip")
        assert response.status_code == 200
        assert len(_stored_logs(db, org.id)) == 1

    def test_a_full_success_returns_an_empty_partial_success(self, client, logs_key):
        """The specification is explicit: empty means fully successful, and
        some clients read a present-but-zero field as a partial failure."""
        response = _post(client, LOGS_PATH, logs_key, _logs_request([_log()]))
        assert _logs_partial(response).rejected_log_records == 0
        assert _logs_partial(response).error_message == ""


class TestSensitiveAttributes:
    def test_an_authorization_header_never_reaches_storage(self, client, db, org, logs_key):
        _post(
            client,
            LOGS_PATH,
            logs_key,
            _logs_request(
                [
                    _log(
                        attributes={
                            "http.request.header.authorization": "Bearer not-a-real-token",
                            "http.route": "/checkout",
                        }
                    )
                ]
            ),
        )
        record = _stored_logs(db, org.id)[0]
        assert "not-a-real-token" not in str(record.attributes)
        assert record.attributes["http.request.header.authorization"].startswith("[redacted")
        # Everything else is untouched.
        assert record.attributes["http.route"] == "/checkout"

    def test_the_redacted_keys_are_recorded(self, client, db, org, logs_key):
        """So an operator can tell an empty field from a refused one."""
        _post(client, LOGS_PATH, logs_key, _logs_request([_log(attributes={"db.password": "x"})]))
        assert _stored_logs(db, org.id)[0].redacted_keys == ["db.password"]

    @pytest.mark.parametrize(
        "key",
        [
            "authorization",
            "Authorization",
            "api_key",
            "x-api-key",
            "set-cookie",
            "user.password",
            "aws.secret",
            "refresh_token",
        ],
    )
    def test_credential_shaped_keys_are_caught_case_insensitively(
        self, client, db, org, logs_key, key
    ):
        _post(client, LOGS_PATH, logs_key, _logs_request([_log(attributes={key: "sensitive"})]))
        record = _stored_logs(db, org.id)[0]
        assert "sensitive" not in str(record.attributes)

    def test_ordinary_application_text_is_never_touched(self, client, db, org, logs_key):
        """The matcher looks at keys, not bodies. A log line that happens to
        contain the word "password" is a legitimate log."""
        _post(
            client,
            LOGS_PATH,
            logs_key,
            _logs_request(
                [
                    _log(
                        body="user reset their password successfully",
                        attributes={"user.id": "42", "http.route": "/reset"},
                    )
                ]
            ),
        )
        record = _stored_logs(db, org.id)[0]
        assert record.body == "user reset their password successfully"
        assert record.redacted_keys is None

    def test_reject_mode_drops_the_whole_record(self, client, db, org, logs_key, monkeypatch):
        monkeypatch.setattr(get_settings(), "ingest_sensitive_attribute_mode", "reject")
        response = _post(
            client,
            LOGS_PATH,
            logs_key,
            _logs_request(
                [_log(attributes={"authorization": "secret"}), _log(body="clean", attributes={})]
            ),
        )
        assert response.status_code == 200
        assert [r.body for r in _stored_logs(db, org.id)] == ["clean"]
        assert _logs_partial(response).rejected_log_records == 1


class TestLogBounds:
    def test_an_enormous_body_is_truncated_not_refused(self, client, db, org, logs_key):
        """Losing a stack trace entirely is worse than losing its tail."""
        _post(client, LOGS_PATH, logs_key, _logs_request([_log(body="x" * 100_000)]))
        stored = _stored_logs(db, org.id)[0]
        assert len(stored.body) == get_settings().ingest_max_log_body_length

    def test_too_many_attributes_are_bounded_and_counted(self, client, db, org, logs_key):
        attributes = {f"attr.{i}": str(i) for i in range(200)}
        _post(client, LOGS_PATH, logs_key, _logs_request([_log(attributes=attributes)]))
        stored = _stored_logs(db, org.id)[0]
        assert len(stored.attributes) <= get_settings().ingest_max_attributes
        assert stored.dropped_attributes_count > 0

    def test_a_record_with_no_resource_identity_is_rejected(self, client, db, org, logs_key):
        response = _post(
            client, LOGS_PATH, logs_key, _logs_request([_log()], resource_attributes={})
        )
        assert response.status_code == 200
        assert _logs_partial(response).rejected_log_records == 1
        assert _stored_logs(db, org.id) == []

    def test_a_timestamp_far_in_the_future_is_rejected(self, client, db, org, logs_key):
        response = _post(
            client, LOGS_PATH, logs_key, _logs_request([_log(nanos=_now_nanos(86_400))])
        )
        assert _logs_partial(response).rejected_log_records == 1
        assert _stored_logs(db, org.id) == []

    def test_malformed_protobuf_is_a_400(self, client, logs_key):
        response = _post(client, LOGS_PATH, logs_key, b"\xff\xff\xff not protobuf")
        assert response.status_code == 400

    def test_otlp_json_is_refused_rather_than_mis_parsed(self, client, logs_key):
        response = _post(client, LOGS_PATH, logs_key, b"{}", content_type="application/json")
        assert response.status_code == 415


# ── traces ──────────────────────────────────────────────────────────────────


class TestTraceIngestion:
    def test_a_span_is_stored_with_its_timing_and_status(self, client, db, org, traces_key):
        trace_id, span_id = _trace_id(), _span_id()
        response = _post(
            client,
            TRACES_PATH,
            traces_key,
            _traces_request([_span(trace_id=trace_id, span_id=span_id, duration_ms=250)]),
        )
        assert response.status_code == 200, response.text

        spans = _stored_spans(db, org.id)
        assert len(spans) == 1
        span = spans[0]
        assert span.trace_id == trace_id
        assert span.span_id == span_id
        assert span.duration_ns == 250 * 1_000_000
        assert span.kind == "server"
        assert span.status_code == "unset"

    def test_a_multi_span_trace_keeps_its_parent_links(self, client, db, org, traces_key):
        trace_id = _trace_id()
        root, child, grandchild = _span_id(), _span_id(), _span_id()
        _post(
            client,
            TRACES_PATH,
            traces_key,
            _traces_request(
                [
                    _span(trace_id=trace_id, span_id=root, name="POST /checkout"),
                    _span(
                        trace_id=trace_id,
                        span_id=child,
                        parent_span_id=root,
                        name="charge card",
                        kind=3,
                    ),
                    _span(
                        trace_id=trace_id,
                        span_id=grandchild,
                        parent_span_id=child,
                        name="SELECT card",
                        kind=3,
                    ),
                ]
            ),
        )
        by_id = {s.span_id: s for s in _stored_spans(db, org.id)}
        assert by_id[root].parent_span_id is None
        assert by_id[child].parent_span_id == root
        assert by_id[grandchild].parent_span_id == child

    def test_a_child_arriving_before_its_parent_is_fine(self, client, db, org, traces_key):
        """Spans are stored flat precisely so this works. A stored tree would
        have to be rewritten when the parent finally showed up."""
        trace_id = _trace_id()
        root, child = _span_id(), _span_id()

        _post(
            client,
            TRACES_PATH,
            traces_key,
            _traces_request([_span(trace_id=trace_id, span_id=child, parent_span_id=root)]),
        )
        _post(
            client, TRACES_PATH, traces_key, _traces_request([_span(trace_id=trace_id, span_id=root)])
        )

        spans = {s.span_id: s for s in _stored_spans(db, org.id)}
        assert set(spans) == {root, child}
        assert spans[child].parent_span_id == root

    def test_an_error_span_keeps_its_status_message(self, client, db, org, traces_key):
        _post(
            client,
            TRACES_PATH,
            traces_key,
            _traces_request(
                [
                    _span(
                        trace_id=_trace_id(),
                        span_id=_span_id(),
                        status=2,
                        status_message="upstream timeout",
                    )
                ]
            ),
        )
        span = _stored_spans(db, org.id)[0]
        assert span.status_code == "error"
        assert span.status_message == "upstream timeout"

    def test_span_events_are_stored(self, client, db, org, traces_key):
        _post(
            client,
            TRACES_PATH,
            traces_key,
            _traces_request(
                [
                    _span(
                        trace_id=_trace_id(),
                        span_id=_span_id(),
                        events=[("exception", {"exception.type": "TimeoutError"})],
                    )
                ]
            ),
        )
        span = _stored_spans(db, org.id)[0]
        assert span.events
        assert span.events[0]["name"] == "exception"
        assert span.events[0]["attributes"]["exception.type"] == "TimeoutError"

    def test_span_kinds_map_to_names(self, client, db, org, traces_key):
        trace_id = _trace_id()
        _post(
            client,
            TRACES_PATH,
            traces_key,
            _traces_request(
                [
                    _span(trace_id=trace_id, span_id=_span_id(), kind=1, name="internal"),
                    _span(trace_id=trace_id, span_id=_span_id(), kind=2, name="server"),
                    _span(trace_id=trace_id, span_id=_span_id(), kind=3, name="client"),
                    _span(trace_id=trace_id, span_id=_span_id(), kind=4, name="producer"),
                    _span(trace_id=trace_id, span_id=_span_id(), kind=5, name="consumer"),
                ]
            ),
        )
        kinds = {s.name: s.kind for s in _stored_spans(db, org.id)}
        assert kinds == {
            "internal": "internal",
            "server": "server",
            "client": "client",
            "producer": "producer",
            "consumer": "consumer",
        }

    def test_a_retried_batch_does_not_duplicate_spans(self, client, db, org, traces_key):
        """A collector retrying after a timeout must be idempotent, or every
        network blip permanently inflates the trace."""
        payload = _traces_request([_span(trace_id=_trace_id(), span_id=_span_id())])

        assert _post(client, TRACES_PATH, traces_key, payload).status_code == 200
        assert _post(client, TRACES_PATH, traces_key, payload).status_code == 200

        assert len(_stored_spans(db, org.id)) == 1


class TestTraceBounds:
    def test_a_span_without_ids_is_rejected(self, client, db, org, traces_key):
        span = trace_pb2.Span(
            name="orphan",
            start_time_unix_nano=_now_nanos(-1),
            end_time_unix_nano=_now_nanos(),
        )
        response = _post(client, TRACES_PATH, traces_key, _traces_request([span]))
        assert _traces_partial(response).rejected_spans == 1
        assert _stored_spans(db, org.id) == []

    def test_a_span_ending_before_it_started_is_rejected(self, client, db, org, traces_key):
        span = _span(trace_id=_trace_id(), span_id=_span_id())
        span.end_time_unix_nano = span.start_time_unix_nano - 1_000_000
        response = _post(client, TRACES_PATH, traces_key, _traces_request([span]))
        assert _traces_partial(response).rejected_spans == 1

    def test_span_events_are_capped(self, client, db, org, traces_key):
        events = [(f"event-{i}", {"i": str(i)}) for i in range(200)]
        _post(
            client,
            TRACES_PATH,
            traces_key,
            _traces_request([_span(trace_id=_trace_id(), span_id=_span_id(), events=events)]),
        )
        span = _stored_spans(db, org.id)[0]
        assert len(span.events) == get_settings().ingest_max_span_events

    def test_span_attributes_are_redacted_too(self, client, db, org, traces_key):
        _post(
            client,
            TRACES_PATH,
            traces_key,
            _traces_request(
                [
                    _span(
                        trace_id=_trace_id(),
                        span_id=_span_id(),
                        attributes={"http.request.header.authorization": "Bearer nope"},
                    )
                ]
            ),
        )
        span = _stored_spans(db, org.id)[0]
        assert "nope" not in str(span.attributes)


# ── authorisation ───────────────────────────────────────────────────────────


class TestScopes:
    def test_a_metrics_key_cannot_write_logs(self, client, db, org):
        issued = ics.create_credential(
            db, organization_id=org.id, name="metrics only", scopes=["metrics:write"]
        )
        db.commit()
        response = _post(client, LOGS_PATH, issued.plaintext, _logs_request([_log()]))
        assert response.status_code == 403

    def test_a_logs_key_cannot_write_traces(self, client, logs_key):
        response = _post(
            client,
            TRACES_PATH,
            logs_key,
            _traces_request([_span(trace_id=_trace_id(), span_id=_span_id())]),
        )
        assert response.status_code == 403

    def test_an_unauthenticated_export_is_refused(self, client):
        assert client.post(LOGS_PATH, content=_logs_request([_log()])).status_code == 401
        traces = _traces_request([_span(trace_id=_trace_id(), span_id=_span_id())])
        assert client.post(TRACES_PATH, content=traces).status_code == 401

    def test_a_device_token_is_not_an_ingest_credential(self, client, enrolled_device):
        _device, device_token = enrolled_device
        response = _post(client, LOGS_PATH, device_token, _logs_request([_log()]))
        assert response.status_code == 401


class TestTenantIsolation:
    def test_logs_are_written_to_the_credentials_organisation_only(self, client, db, org):
        other = Organization(name=f"Other {uuid.uuid4().hex[:8]}", slug=f"o-{uuid.uuid4().hex[:8]}")
        db.add(other)
        db.flush()
        other_key = ics.create_credential(
            db, organization_id=other.id, name="theirs", scopes=["logs:write"]
        )
        db.commit()

        _post(client, LOGS_PATH, other_key.plaintext, _logs_request([_log(body="theirs")]))

        # Nothing landed in the fixture organisation, whatever the payload said.
        assert _stored_logs(db, org.id) == []
        assert [r.body for r in _stored_logs(db, other.id)] == ["theirs"]

    def test_spans_are_written_to_the_credentials_organisation_only(self, client, db, org):
        other = Organization(name=f"Other {uuid.uuid4().hex[:8]}", slug=f"o-{uuid.uuid4().hex[:8]}")
        db.add(other)
        db.flush()
        other_key = ics.create_credential(
            db, organization_id=other.id, name="theirs", scopes=["traces:write"]
        )
        db.commit()

        _post(
            client,
            TRACES_PATH,
            other_key.plaintext,
            _traces_request([_span(trace_id=_trace_id(), span_id=_span_id())]),
        )
        assert _stored_spans(db, org.id) == []
        assert len(_stored_spans(db, other.id)) == 1
