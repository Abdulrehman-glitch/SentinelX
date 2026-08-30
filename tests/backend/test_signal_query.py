"""Reading logs and traces back.

The properties worth pinning are the ones a log explorer gets wrong quietly:
that paging stays correct and cheap as it goes deeper, that a search box cannot
be turned into a full-table scan, that a trace assembles correctly even when
its spans arrived out of order, and that none of it ever crosses a tenant
boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.log_record import LogRecord, severity_band
from app.models.organization import Organization
from app.models.resource import Resource
from app.models.span import Span
from app.services import signal_query_service as sq

NOW = datetime.now(timezone.utc).replace(microsecond=0)
WINDOW_START = NOW - timedelta(hours=1)
WINDOW_END = NOW + timedelta(minutes=1)


def _resource(db, org_id, *, service="checkout-api", environment="production"):
    resource = Resource(
        organization_id=org_id,
        resource_type="service",
        identity_hash=uuid.uuid4().hex,
        identifying_attributes={"service.name": service},
        attributes={"deployment.environment.name": environment},
        display_name=service,
    )
    db.add(resource)
    db.flush()
    return resource


def _log(
    db,
    org_id,
    resource,
    *,
    body="something happened",
    severity=9,
    when=None,
    trace_id=None,
    span_id=None,
    service=None,
    environment="production",
    attributes=None,
):
    record = LogRecord(
        organization_id=org_id,
        resource_id=resource.id,
        observed_at=when or NOW,
        timestamp=when or NOW,
        severity_number=severity,
        severity_text=None,
        severity_band=severity_band(severity),
        body=body,
        attributes=attributes or {},
        trace_id=trace_id,
        span_id=span_id,
        service_name=service or resource.display_name,
        environment=environment,
    )
    db.add(record)
    db.flush()
    return record


def _span(
    db,
    org_id,
    resource,
    *,
    trace_id,
    span_id=None,
    parent_span_id=None,
    name="POST /checkout",
    started=None,
    duration_ms=100,
    status="unset",
    service=None,
    environment="production",
):
    start = started or NOW
    span = Span(
        organization_id=org_id,
        resource_id=resource.id,
        trace_id=trace_id,
        span_id=span_id or uuid.uuid4().hex[:16],
        parent_span_id=parent_span_id,
        name=name,
        kind="server",
        start_time=start,
        end_time=start + timedelta(milliseconds=duration_ms),
        duration_ns=duration_ms * 1_000_000,
        status_code=status,
        attributes={},
        service_name=service or resource.display_name,
        environment=environment,
    )
    db.add(span)
    db.flush()
    return span


@pytest.fixture()
def service(db, org):
    resource = _resource(db, org.id)
    db.commit()
    return resource


class TestLogSearch:
    def test_logs_come_back_newest_first(self, db, org, service):
        for minutes in (30, 10, 20):
            _log(db, org.id, service, body=f"m{minutes}", when=NOW - timedelta(minutes=minutes))
        db.commit()

        page = sq.search_logs(db, org.id, start=WINDOW_START, end=WINDOW_END)
        assert [i["body"] for i in page.items] == ["m10", "m20", "m30"]

    def test_a_substring_search_matches_the_body(self, db, org, service):
        _log(db, org.id, service, body="payment gateway timeout")
        _log(db, org.id, service, body="order placed")
        db.commit()

        page = sq.search_logs(db, org.id, start=WINDOW_START, end=WINDOW_END, search="gateway")
        assert [i["body"] for i in page.items] == ["payment gateway timeout"]

    def test_a_wildcard_in_the_search_term_is_literal(self, db, org, service):
        """A bare % must not match everything - that is the difference between
        a search box and an accidental full scan."""
        _log(db, org.id, service, body="ordinary line")
        db.commit()

        page = sq.search_logs(db, org.id, start=WINDOW_START, end=WINDOW_END, search="%")
        assert page.items == []

    def test_an_overlong_search_term_is_refused(self, db, org, service):
        with pytest.raises(sq.SignalQueryError):
            sq.search_logs(db, org.id, start=WINDOW_START, end=WINDOW_END, search="x" * 500)

    def test_min_severity_includes_everything_worse(self, db, org, service):
        for severity, label in ((5, "debug"), (9, "info"), (13, "warn"), (17, "error")):
            _log(db, org.id, service, body=label, severity=severity)
        db.commit()

        page = sq.search_logs(db, org.id, start=WINDOW_START, end=WINDOW_END, min_severity="warn")
        assert sorted(i["body"] for i in page.items) == ["error", "warn"]

    def test_an_unknown_severity_is_refused_rather_than_ignored(self, db, org, service):
        with pytest.raises(sq.SignalQueryError):
            sq.search_logs(
                db, org.id, start=WINDOW_START, end=WINDOW_END, severities=("catastrophic",)
            )

    def test_filtering_by_service_narrows_the_result(self, db, org):
        checkout = _resource(db, org.id, service="checkout-api")
        billing = _resource(db, org.id, service="billing-api")
        _log(db, org.id, checkout, body="checkout")
        _log(db, org.id, billing, body="billing")
        db.commit()

        page = sq.search_logs(
            db, org.id, start=WINDOW_START, end=WINDOW_END, services=("billing-api",)
        )
        assert [i["body"] for i in page.items] == ["billing"]

    def test_an_attribute_filter_uses_containment(self, db, org, service):
        _log(db, org.id, service, body="a", attributes={"http.route": "/checkout"})
        _log(db, org.id, service, body="b", attributes={"http.route": "/health"})
        db.commit()

        page = sq.search_logs(
            db,
            org.id,
            start=WINDOW_START,
            end=WINDOW_END,
            attributes={"http.route": "/checkout"},
        )
        assert [i["body"] for i in page.items] == ["a"]

    def test_a_range_wider_than_the_maximum_is_refused(self, db, org, service):
        with pytest.raises(sq.SignalQueryError) as exc:
            sq.search_logs(db, org.id, start=NOW - timedelta(days=90), end=NOW)
        assert "maximum" in str(exc.value)

    def test_an_inverted_range_is_refused(self, db, org, service):
        with pytest.raises(sq.SignalQueryError):
            sq.search_logs(db, org.id, start=NOW, end=NOW - timedelta(hours=1))


class TestPagination:
    def test_paging_walks_the_whole_result_without_repeats(self, db, org, service):
        for index in range(10):
            _log(db, org.id, service, body=f"line-{index}", when=NOW - timedelta(minutes=index))
        db.commit()

        seen: list[str] = []
        cursor = None
        for _ in range(10):
            page = sq.search_logs(
                db, org.id, start=WINDOW_START, end=WINDOW_END, limit=3, cursor=cursor
            )
            seen.extend(i["body"] for i in page.items)
            cursor = page.next_cursor
            if cursor is None:
                break

        assert len(seen) == len(set(seen)) == 10

    def test_the_last_page_has_no_cursor(self, db, org, service):
        _log(db, org.id, service, body="only")
        db.commit()
        page = sq.search_logs(db, org.id, start=WINDOW_START, end=WINDOW_END, limit=50)
        assert page.next_cursor is None

    def test_a_corrupt_cursor_is_refused_rather_than_ignored(self, db, org, service):
        """Silently starting from the beginning would show the caller a page
        they had already seen, and look like data loss."""
        with pytest.raises(sq.SignalQueryError):
            sq.search_logs(
                db, org.id, start=WINDOW_START, end=WINDOW_END, cursor="not-a-real-cursor"
            )

    def test_an_oversized_page_is_clamped_not_refused(self, db, org, service):
        for index in range(5):
            _log(db, org.id, service, body=f"n{index}")
        db.commit()
        page = sq.search_logs(db, org.id, start=WINDOW_START, end=WINDOW_END, limit=100_000)
        assert len(page.items) == 5


class TestFacets:
    def test_facets_count_by_service_environment_and_severity(self, db, org):
        checkout = _resource(db, org.id, service="checkout-api")
        billing = _resource(db, org.id, service="billing-api", environment="staging")
        _log(db, org.id, checkout, severity=17)
        _log(db, org.id, checkout, severity=17)
        _log(db, org.id, billing, severity=9, environment="staging")
        db.commit()

        facets = sq.log_facets(db, org.id, start=WINDOW_START, end=WINDOW_END)
        services = {f["value"]: f["count"] for f in facets["service_name"]}
        assert services == {"checkout-api": 2, "billing-api": 1}
        severities = {f["value"]: f["count"] for f in facets["severity"]}
        assert severities == {"error": 2, "info": 1}
        assert {f["value"] for f in facets["environment"]} == {"production", "staging"}


class TestTraceSearch:
    def test_a_trace_list_returns_traces_not_spans(self, db, org, service):
        trace_id = uuid.uuid4().hex
        root = _span(db, org.id, service, trace_id=trace_id, name="POST /checkout")
        _span(db, org.id, service, trace_id=trace_id, parent_span_id=root.span_id, name="charge")
        _span(db, org.id, service, trace_id=trace_id, parent_span_id=root.span_id, name="ship")
        db.commit()

        page = sq.search_traces(db, org.id, start=WINDOW_START, end=WINDOW_END)
        assert len(page.items) == 1
        assert page.items[0]["span_count"] == 3
        assert page.items[0]["root_operation"] == "POST /checkout"

    def test_a_trace_is_flagged_when_any_span_errored(self, db, org, service):
        trace_id = uuid.uuid4().hex
        root = _span(db, org.id, service, trace_id=trace_id)
        _span(db, org.id, service, trace_id=trace_id, parent_span_id=root.span_id, status="error")
        db.commit()

        page = sq.search_traces(db, org.id, start=WINDOW_START, end=WINDOW_END)
        assert page.items[0]["has_error"] is True
        assert page.items[0]["error_count"] == 1

    def test_a_duration_filter_selects_slow_traces(self, db, org, service):
        fast, slow = uuid.uuid4().hex, uuid.uuid4().hex
        _span(db, org.id, service, trace_id=fast, duration_ms=10)
        _span(db, org.id, service, trace_id=slow, duration_ms=900)
        db.commit()

        page = sq.search_traces(db, org.id, start=WINDOW_START, end=WINDOW_END, min_duration_ms=500)
        assert [i["trace_id"] for i in page.items] == [slow]

    def test_a_status_filter_selects_errors(self, db, org, service):
        ok, bad = uuid.uuid4().hex, uuid.uuid4().hex
        _span(db, org.id, service, trace_id=ok, status="ok")
        _span(db, org.id, service, trace_id=bad, status="error")
        db.commit()

        page = sq.search_traces(db, org.id, start=WINDOW_START, end=WINDOW_END, status="error")
        assert [i["trace_id"] for i in page.items] == [bad]

    def test_an_unknown_status_is_refused(self, db, org, service):
        with pytest.raises(sq.SignalQueryError):
            sq.search_traces(db, org.id, start=WINDOW_START, end=WINDOW_END, status="broken")


    def test_a_status_filter_selects_traces_not_spans(self, db, org, service):
        """Found by running it: filtering by status used to narrow the spans
        before aggregating, so a two-span trace with one error reported
        span_count=1 and no root operation - derived from real data and
        completely misleading. The filter picks which traces are interesting;
        the summary must still describe the whole trace."""
        trace_id = uuid.uuid4().hex
        root = _span(db, org.id, service, trace_id=trace_id, name="POST /checkout")
        _span(
            db,
            org.id,
            service,
            trace_id=trace_id,
            parent_span_id=root.span_id,
            name="charge",
            status="error",
        )
        db.commit()

        page = sq.search_traces(db, org.id, start=WINDOW_START, end=WINDOW_END, status="error")
        assert len(page.items) == 1
        summary = page.items[0]
        assert summary["span_count"] == 2, "the whole trace, not just the matching span"
        assert summary["root_operation"] == "POST /checkout"
        assert summary["error_count"] == 1

    def test_a_service_filter_also_summarises_the_whole_trace(self, db, org):
        """Same shape for a multi-service trace: filtering on the downstream
        service must still report the upstream root."""
        gateway = _resource(db, org.id, service="gateway")
        billing = _resource(db, org.id, service="billing-api")
        trace_id = uuid.uuid4().hex
        root = _span(db, org.id, gateway, trace_id=trace_id, name="GET /pay")
        _span(
            db,
            org.id,
            billing,
            trace_id=trace_id,
            parent_span_id=root.span_id,
            name="charge",
        )
        db.commit()

        page = sq.search_traces(
            db, org.id, start=WINDOW_START, end=WINDOW_END, services=("billing-api",)
        )
        summary = page.items[0]
        assert summary["span_count"] == 2
        assert summary["root_operation"] == "GET /pay"
        assert summary["service_count"] == 2

    def test_a_trace_missing_its_root_says_so(self, db, org, service):
        """Inventing a name for a trace whose entry point never arrived would
        be worse than admitting it is partial."""
        trace_id = uuid.uuid4().hex
        _span(db, org.id, service, trace_id=trace_id, parent_span_id="ffffffffffffffff")
        db.commit()

        page = sq.search_traces(db, org.id, start=WINDOW_START, end=WINDOW_END)
        assert page.items[0]["root_operation"] == "(root span not received)"


class TestTraceAssembly:
    def test_depth_is_derived_from_the_parent_chain(self, db, org, service):
        trace_id = uuid.uuid4().hex
        root = _span(db, org.id, service, trace_id=trace_id, name="root")
        child = _span(
            db, org.id, service, trace_id=trace_id, parent_span_id=root.span_id, name="child"
        )
        _span(
            db, org.id, service, trace_id=trace_id, parent_span_id=child.span_id, name="grandchild"
        )
        db.commit()

        trace = sq.get_trace(db, org.id, trace_id)
        depths = {s["name"]: s["depth"] for s in trace["spans"]}
        assert depths == {"root": 0, "child": 1, "grandchild": 2}

    def test_spans_stored_out_of_order_still_assemble(self, db, org, service):
        """The child was written first. Depth is computed at read time, so the
        order rows were inserted in is irrelevant."""
        trace_id = uuid.uuid4().hex
        parent_id = uuid.uuid4().hex[:16]
        _span(
            db,
            org.id,
            service,
            trace_id=trace_id,
            parent_span_id=parent_id,
            name="child",
            started=NOW + timedelta(milliseconds=5),
        )
        _span(db, org.id, service, trace_id=trace_id, span_id=parent_id, name="root")
        db.commit()

        trace = sq.get_trace(db, org.id, trace_id)
        depths = {s["name"]: s["depth"] for s in trace["spans"]}
        assert depths == {"root": 0, "child": 1}

    def test_an_orphan_is_marked_rather_than_hidden(self, db, org, service):
        trace_id = uuid.uuid4().hex
        _span(db, org.id, service, trace_id=trace_id, parent_span_id="aaaaaaaaaaaaaaaa")
        db.commit()

        assert sq.get_trace(db, org.id, trace_id)["spans"][0]["orphaned"] is True

    def test_a_root_span_is_not_an_orphan(self, db, org, service):
        trace_id = uuid.uuid4().hex
        _span(db, org.id, service, trace_id=trace_id)
        db.commit()
        assert sq.get_trace(db, org.id, trace_id)["spans"][0]["orphaned"] is False

    def test_offsets_are_relative_to_the_start_of_the_trace(self, db, org, service):
        trace_id = uuid.uuid4().hex
        _span(db, org.id, service, trace_id=trace_id, name="first")
        _span(
            db,
            org.id,
            service,
            trace_id=trace_id,
            name="second",
            started=NOW + timedelta(milliseconds=250),
        )
        db.commit()

        trace = sq.get_trace(db, org.id, trace_id)
        offsets = {s["name"]: s["offset_ms"] for s in trace["spans"]}
        assert offsets["first"] == 0
        assert offsets["second"] == pytest.approx(250, abs=1)

    def test_a_cyclic_parent_chain_cannot_hang_the_reader(self, db, org, service):
        """A hostile client can send a cycle. Depth resolution must terminate."""
        trace_id = uuid.uuid4().hex
        a, b = uuid.uuid4().hex[:16], uuid.uuid4().hex[:16]
        _span(db, org.id, service, trace_id=trace_id, span_id=a, parent_span_id=b, name="a")
        _span(db, org.id, service, trace_id=trace_id, span_id=b, parent_span_id=a, name="b")
        db.commit()

        assert len(sq.get_trace(db, org.id, trace_id)["spans"]) == 2

    def test_an_unknown_trace_reports_not_found_rather_than_raising(self, db, org):
        result = sq.get_trace(db, org.id, uuid.uuid4().hex)
        assert result["found"] is False
        assert result["spans"] == []

    def test_a_malformed_trace_id_is_refused(self, db, org):
        with pytest.raises(sq.SignalQueryError):
            sq.get_trace(db, org.id, "x" * 100)


class TestCorrelation:
    def test_logs_can_be_reached_from_a_trace_id(self, db, org, service):
        trace_id = uuid.uuid4().hex
        _span(db, org.id, service, trace_id=trace_id)
        _log(db, org.id, service, body="charging card", trace_id=trace_id)
        _log(db, org.id, service, body="unrelated")
        db.commit()

        assert [e["body"] for e in sq.logs_for_trace(db, org.id, trace_id)] == ["charging card"]

    def test_correlated_logs_come_back_oldest_first(self, db, org, service):
        """A trace's logs are read as a narrative, so they run forwards - the
        opposite of the explorer's newest-first default."""
        trace_id = uuid.uuid4().hex
        _log(db, org.id, service, body="second", trace_id=trace_id, when=NOW)
        _log(db, org.id, service, body="first", trace_id=trace_id, when=NOW - timedelta(seconds=5))
        db.commit()

        assert [e["body"] for e in sq.logs_for_trace(db, org.id, trace_id)] == ["first", "second"]

    def test_the_span_id_survives_for_span_level_correlation(self, db, org, service):
        trace_id, span_id = uuid.uuid4().hex, uuid.uuid4().hex[:16]
        _log(db, org.id, service, trace_id=trace_id, span_id=span_id)
        db.commit()
        assert sq.logs_for_trace(db, org.id, trace_id)[0]["span_id"] == span_id


class TestTenantIsolation:
    def _other_org(self, db):
        other = Organization(name=f"Other {uuid.uuid4().hex[:8]}", slug=f"o-{uuid.uuid4().hex[:8]}")
        db.add(other)
        db.flush()
        return other

    def test_logs_never_cross_organisations(self, db, org, service):
        other = self._other_org(db)
        other_resource = _resource(db, other.id, service="their-secret-service")
        _log(db, other.id, other_resource, body="their log")
        _log(db, org.id, service, body="my log")
        db.commit()

        page = sq.search_logs(db, org.id, start=WINDOW_START, end=WINDOW_END)
        assert [i["body"] for i in page.items] == ["my log"]

    def test_facets_never_leak_another_tenants_service_names(self, db, org, service):
        """Autocomplete is a surprisingly effective way to enumerate someone
        else's architecture, so it gets its own test."""
        other = self._other_org(db)
        other_resource = _resource(db, other.id, service="their-secret-service")
        _log(db, other.id, other_resource)
        _log(db, org.id, service)
        db.commit()

        facets = sq.log_facets(db, org.id, start=WINDOW_START, end=WINDOW_END)
        assert "their-secret-service" not in {f["value"] for f in facets["service_name"]}

    def test_a_trace_id_from_another_tenant_reports_not_found(self, db, org):
        other = self._other_org(db)
        other_resource = _resource(db, other.id)
        trace_id = uuid.uuid4().hex
        _span(db, other.id, other_resource, trace_id=trace_id)
        db.commit()

        # From this tenant the id simply does not exist, which is what stops
        # the endpoint being an existence oracle.
        assert sq.get_trace(db, org.id, trace_id)["found"] is False

    def test_trace_search_never_crosses_organisations(self, db, org, service):
        other = self._other_org(db)
        other_resource = _resource(db, other.id)
        _span(db, other.id, other_resource, trace_id=uuid.uuid4().hex)
        mine = uuid.uuid4().hex
        _span(db, org.id, service, trace_id=mine)
        db.commit()

        page = sq.search_traces(db, org.id, start=WINDOW_START, end=WINDOW_END)
        assert [i["trace_id"] for i in page.items] == [mine]


class TestThroughTheApi:
    def _range(self):
        return {"start": WINDOW_START.isoformat(), "end": WINDOW_END.isoformat()}

    def test_the_log_endpoint_returns_records(self, client, db, org, admin_headers, service):
        _log(db, org.id, service, body="via the api")
        db.commit()

        response = client.get("/api/v1/signals/logs", params=self._range(), headers=admin_headers)
        assert response.status_code == 200, response.text
        assert [i["body"] for i in response.json()["items"]] == ["via the api"]

    def test_an_invalid_range_is_a_400(self, client, admin_headers):
        response = client.get(
            "/api/v1/signals/logs",
            params={"start": NOW.isoformat(), "end": (NOW - timedelta(hours=1)).isoformat()},
            headers=admin_headers,
        )
        assert response.status_code == 400

    def test_the_trace_endpoint_assembles_a_waterfall(
        self, client, db, org, admin_headers, service
    ):
        trace_id = uuid.uuid4().hex
        root = _span(db, org.id, service, trace_id=trace_id, name="root")
        _span(db, org.id, service, trace_id=trace_id, parent_span_id=root.span_id, name="child")
        db.commit()

        response = client.get(f"/api/v1/signals/traces/{trace_id}", headers=admin_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["found"] is True
        assert body["span_count"] == 2

    def test_correlated_logs_are_reachable_over_http(self, client, db, org, admin_headers, service):
        trace_id = uuid.uuid4().hex
        _log(db, org.id, service, body="correlated", trace_id=trace_id)
        db.commit()

        response = client.get(f"/api/v1/signals/traces/{trace_id}/logs", headers=admin_headers)
        assert response.status_code == 200
        assert [i["body"] for i in response.json()["items"]] == ["correlated"]

    def test_the_endpoints_require_authentication(self, client):
        assert client.get("/api/v1/signals/logs", params=self._range()).status_code == 401
        assert client.get("/api/v1/signals/traces", params=self._range()).status_code == 401
