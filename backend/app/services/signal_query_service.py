"""Reading logs and traces back out.

Written to the same rule as `metric_query_service`: nothing is unbounded, and
anything that would be expensive is either bounded or refused with a reason. A
log explorer is the easiest place in an observability product to write an
accidental full-table scan, so the constraints here are deliberate rather than
defensive habit.

Three decisions worth stating.

**Keyset pagination, never OFFSET.** `OFFSET 50000` makes PostgreSQL walk and
discard fifty thousand rows on every page, so paging deep into a busy tenant's
logs gets slower the further you go. Every listing here pages on `(time, id)` -
the leading columns of the primary key - so page one thousand costs what page
one costs.

**Body search is a bounded substring match, not regex.** A caller-supplied
regex is a CPU denial-of-service with a friendly interface. The search term is
escaped, length-bounded, and always paired with a time range the index does
serve, so the substring match only ever runs over rows the range has already
narrowed.

**A trace is assembled at read time.** Spans are stored flat; `get_trace`
fetches every span sharing an id, bounded, and derives parent/child depth in
Python. That is precisely why a child arriving before its parent is not a
problem.
"""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import get_settings

# Severity bands a caller may filter on, in ascending order of seriousness.
SEVERITY_ORDER = ("trace", "debug", "info", "warn", "error", "fatal")

MAX_PAGE_SIZE = 200
MAX_SEARCH_TERM = 128
# A trace with more spans than this is pathological, and rendering it would
# hang a browser long before the query became the problem.
MAX_SPANS_PER_TRACE = 2000


class SignalQueryError(ValueError):
    """A query that is invalid rather than merely empty."""


class SignalQueryTimeout(RuntimeError):
    """The query exceeded its statement timeout and was cancelled."""


@dataclass(frozen=True)
class Page:
    items: list[dict[str, Any]]
    next_cursor: str | None
    truncated: bool = False


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _encode_cursor(when: datetime, row_id: uuid.UUID) -> str:
    """Opaque, but not secret - it is a position, not a capability.

    Base64 so a client is never tempted to construct one by hand and end up
    depending on the column layout.
    """
    payload = json.dumps({"t": _as_utc(when).isoformat(), "i": str(row_id)})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    if not cursor:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return _as_utc(datetime.fromisoformat(payload["t"])), uuid.UUID(payload["i"])
    except Exception as exc:
        raise SignalQueryError("That page cursor is not valid.") from exc


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _validate_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    settings = get_settings()
    start, end = _as_utc(start), _as_utc(end)
    if end <= start:
        raise SignalQueryError("`end` must be after `start`.")
    if (end - start).days > settings.signal_query_max_range_days:
        raise SignalQueryError(
            f"Requested range spans {(end - start).days} days; the maximum is "
            f"{settings.signal_query_max_range_days}. Narrow the range or page through it."
        )
    return start, end


def _run(db: Session, sql, params):
    try:
        db.execute(
            text(f"SET LOCAL statement_timeout = {int(get_settings().signal_query_timeout_ms)}")
        )
        return db.execute(sql, params).all()
    except DBAPIError as exc:
        if "statement timeout" in str(exc.orig or exc).lower():
            raise SignalQueryTimeout(
                "The query exceeded its time budget. Narrow the time range, add a service "
                "or severity filter, or search for a more specific term."
            ) from exc
        raise


# ── logs ────────────────────────────────────────────────────────────────────


def search_logs(
    db: Session,
    organization_id: uuid.UUID,
    *,
    start: datetime,
    end: datetime,
    search: str | None = None,
    severities: tuple[str, ...] = (),
    min_severity: str | None = None,
    services: tuple[str, ...] = (),
    environments: tuple[str, ...] = (),
    resource_ids: tuple[uuid.UUID, ...] = (),
    trace_id: str | None = None,
    attributes: dict[str, str] | None = None,
    limit: int = 100,
    cursor: str | None = None,
) -> Page:
    """One page of logs, newest first."""
    start, end = _validate_range(start, end)
    limit = max(1, min(limit, MAX_PAGE_SIZE))

    clauses = ["l.organization_id = :org_id", "l.observed_at >= :start", "l.observed_at < :end"]
    params: dict[str, Any] = {
        "org_id": str(organization_id),
        "start": start,
        "end": end,
        "limit": limit + 1,
    }

    if search:
        if len(search) > MAX_SEARCH_TERM:
            raise SignalQueryError(f"Search terms are limited to {MAX_SEARCH_TERM} characters.")
        # Substring, escaped, and only ever evaluated over rows the time range
        # already narrowed. Not regex: a caller-supplied pattern is a CPU
        # denial-of-service with a friendly interface.
        clauses.append("l.body ILIKE :search")
        params["search"] = f"%{_escape_like(search)}%"

    if severities:
        unknown = set(severities) - set(SEVERITY_ORDER) - {"unspecified"}
        if unknown:
            raise SignalQueryError(
                f"Unknown severity {', '.join(sorted(unknown))}. "
                f"Valid: {', '.join(SEVERITY_ORDER)}, unspecified."
            )
        clauses.append("l.severity_band = ANY(CAST(:severities AS text[]))")
        params["severities"] = list(severities)
    elif min_severity:
        if min_severity not in SEVERITY_ORDER:
            raise SignalQueryError(
                f"Unknown severity '{min_severity}'. Valid: {', '.join(SEVERITY_ORDER)}."
            )
        # "warn and worse" expands to an explicit set rather than a range,
        # because the stored band is a name and the index is an equality index.
        clauses.append("l.severity_band = ANY(CAST(:severities AS text[]))")
        params["severities"] = list(SEVERITY_ORDER[SEVERITY_ORDER.index(min_severity) :])

    if services:
        clauses.append("l.service_name = ANY(CAST(:services AS text[]))")
        params["services"] = list(services)
    if environments:
        clauses.append("l.environment = ANY(CAST(:environments AS text[]))")
        params["environments"] = list(environments)
    if resource_ids:
        clauses.append("l.resource_id = ANY(CAST(:resource_ids AS uuid[]))")
        params["resource_ids"] = [str(r) for r in resource_ids]
    if trace_id:
        clauses.append("l.trace_id = :trace_id")
        params["trace_id"] = trace_id
    if attributes:
        clauses.append("l.attributes @> CAST(:attr_filter AS jsonb)")
        params["attr_filter"] = json.dumps(attributes)

    position = _decode_cursor(cursor)
    if position:
        # Keyset, on the leading columns of the primary key. Descending, so
        # "the next page" is strictly older.
        clauses.append("(l.observed_at, l.id) < (:cursor_t, CAST(:cursor_i AS uuid))")
        params["cursor_t"], params["cursor_i"] = position[0], str(position[1])

    rows = _run(
        db,
        text(
            f"""
            SELECT l.id, l.observed_at, l.timestamp, l.severity_number, l.severity_text,
                   l.severity_band, l.body, l.attributes, l.trace_id, l.span_id,
                   l.service_name, l.environment, l.service_version, l.resource_id,
                   l.scope_name, l.dropped_attributes_count, l.redacted_keys
            FROM log_records l
            WHERE {' AND '.join(clauses)}
            ORDER BY l.observed_at DESC, l.id DESC
            LIMIT :limit
            """
        ),
        params,
    )

    has_more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[_log_row(row) for row in rows],
        next_cursor=(
            _encode_cursor(rows[-1].observed_at, rows[-1].id) if has_more and rows else None
        ),
    )


def _log_row(row) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "observed_at": row.observed_at,
        "timestamp": row.timestamp,
        "severity_number": row.severity_number,
        "severity_text": row.severity_text,
        "severity": row.severity_band,
        "body": row.body,
        "attributes": row.attributes or {},
        "trace_id": row.trace_id,
        "span_id": row.span_id,
        "service_name": row.service_name,
        "environment": row.environment,
        "service_version": row.service_version,
        "resource_id": str(row.resource_id),
        "scope_name": row.scope_name,
        "dropped_attributes_count": row.dropped_attributes_count,
        "redacted_keys": row.redacted_keys,
    }


def log_facets(
    db: Session, organization_id: uuid.UUID, *, start: datetime, end: datetime
) -> dict[str, list[dict[str, Any]]]:
    """Counts per service, environment and severity for the current range.

    Facets are what make a log explorer navigable rather than a search box over
    a void. Bounded to the same range as the listing, so they cost what the
    listing costs.
    """
    start, end = _validate_range(start, end)
    params = {"org_id": str(organization_id), "start": start, "end": end}

    def counts(column: str) -> list[dict[str, Any]]:
        # Column names are literals chosen here, never caller input.
        rows = _run(
            db,
            text(
                f"""
                SELECT {column} AS value, count(*) AS n
                FROM log_records
                WHERE organization_id = :org_id
                  AND observed_at >= :start AND observed_at < :end
                  AND {column} IS NOT NULL
                GROUP BY {column}
                ORDER BY n DESC
                LIMIT 50
                """
            ),
            params,
        )
        return [{"value": r.value, "count": int(r.n)} for r in rows]

    return {
        "service_name": counts("service_name"),
        "environment": counts("environment"),
        "severity": counts("severity_band"),
    }


# ── traces ──────────────────────────────────────────────────────────────────


def search_traces(
    db: Session,
    organization_id: uuid.UUID,
    *,
    start: datetime,
    end: datetime,
    services: tuple[str, ...] = (),
    environments: tuple[str, ...] = (),
    operation: str | None = None,
    status: str | None = None,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> Page:
    """One page of traces, newest first, summarised by their root span.

    A trace list is a list of *traces*, not spans, so this aggregates: one row
    per trace id carrying the root operation, span count, whether anything in
    it errored, and how long the whole thing took.
    """
    start, end = _validate_range(start, end)
    limit = max(1, min(limit, MAX_PAGE_SIZE))

    clauses = ["s.organization_id = :org_id", "s.start_time >= :start", "s.start_time < :end"]
    params: dict[str, Any] = {
        "org_id": str(organization_id),
        "start": start,
        "end": end,
        "limit": limit + 1,
    }

    if services:
        clauses.append("s.service_name = ANY(CAST(:services AS text[]))")
        params["services"] = list(services)
    if environments:
        clauses.append("s.environment = ANY(CAST(:environments AS text[]))")
        params["environments"] = list(environments)
    if operation:
        if len(operation) > MAX_SEARCH_TERM:
            raise SignalQueryError(
                f"Operation filters are limited to {MAX_SEARCH_TERM} characters."
            )
        clauses.append("s.name ILIKE :operation")
        params["operation"] = f"%{_escape_like(operation)}%"
    if status:
        if status not in ("ok", "error", "unset"):
            raise SignalQueryError("Status must be one of ok, error, unset.")
        clauses.append("s.status_code = :status")
        params["status"] = status

    having = []
    if min_duration_ms is not None:
        having.append("max(s.duration_ns) >= :min_duration")
        params["min_duration"] = int(min_duration_ms * 1_000_000)
    if max_duration_ms is not None:
        having.append("max(s.duration_ns) <= :max_duration")
        params["max_duration"] = int(max_duration_ms * 1_000_000)

    position = _decode_cursor(cursor)
    if position:
        # PostgreSQL has no min(uuid), so the tiebreaker compares the text
        # form. It only has to be deterministic, not meaningful.
        having.append(
            "(min(s.start_time), min(s.id::text)) < (:cursor_t, CAST(:cursor_i AS text))"
        )
        params["cursor_t"], params["cursor_i"] = position[0], str(position[1])

    having_sql = f"HAVING {' AND '.join(having)}" if having else ""

    # Two stages, and the reason is a correctness one rather than a
    # performance one. Filters like `status=error` or `service=billing` select
    # *which traces are interesting*, but the summary has to describe the whole
    # trace. Applying the filter directly to the aggregation would summarise
    # only the matching spans, so a two-span trace with one error would report
    # span_count=1 and no root operation - technically derived from the data
    # and completely misleading.
    #
    # So: an inner scan picks candidate trace ids using the filters, and the
    # outer aggregation describes every span of those traces. The candidate set
    # is capped, because a filter matching everything must not collect an
    # unbounded list of ids.
    params["candidate_cap"] = limit * 20

    rows = _run(
        db,
        text(
            f"""
            WITH matching AS (
                SELECT DISTINCT s.trace_id
                FROM spans s
                WHERE {' AND '.join(clauses)}
                LIMIT :candidate_cap
            )
            SELECT s.trace_id,
                   min(s.start_time)  AS started_at,
                   CAST(min(s.id::text) AS uuid) AS anchor_id,
                   max(s.duration_ns) AS duration_ns,
                   count(*)           AS span_count,
                   count(*) FILTER (WHERE s.status_code = 'error') AS error_count,
                   min(s.service_name) FILTER (WHERE s.parent_span_id IS NULL) AS root_service,
                   min(s.name)         FILTER (WHERE s.parent_span_id IS NULL) AS root_operation,
                   count(DISTINCT s.service_name) AS service_count
            FROM spans s
            JOIN matching m ON m.trace_id = s.trace_id
            WHERE s.organization_id = :org_id
              AND s.start_time >= :start
              AND s.start_time < :end
            GROUP BY s.trace_id
            {having_sql}
            ORDER BY started_at DESC, anchor_id DESC
            LIMIT :limit
            """
        ),
        params,
    )

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [
        {
            "trace_id": r.trace_id,
            "started_at": r.started_at,
            "duration_ms": round((r.duration_ns or 0) / 1_000_000, 3),
            "span_count": int(r.span_count),
            "error_count": int(r.error_count),
            "root_service": r.root_service,
            # A trace with no root span is one whose entry point has not
            # arrived, or was sampled away. Saying so beats inventing a name.
            "root_operation": r.root_operation or "(root span not received)",
            "service_count": int(r.service_count),
            "has_error": int(r.error_count) > 0,
        }
        for r in rows
    ]
    return Page(
        items=items,
        next_cursor=(
            _encode_cursor(rows[-1].started_at, rows[-1].anchor_id) if has_more and rows else None
        ),
    )


def get_trace(db: Session, organization_id: uuid.UUID, trace_id: str) -> dict[str, Any]:
    """Every span in one trace, ordered for a waterfall.

    Depth is derived here rather than stored, because it is a property of the
    assembled trace and not of any single span - a span's depth changes the
    moment a missing ancestor arrives.
    """
    if not trace_id or len(trace_id) > 32:
        raise SignalQueryError("That is not a valid trace id.")

    rows = _run(
        db,
        text(
            """
            SELECT s.id, s.trace_id, s.span_id, s.parent_span_id, s.name, s.kind,
                   s.start_time, s.end_time, s.duration_ns, s.status_code, s.status_message,
                   s.attributes, s.events, s.service_name, s.environment, s.service_version,
                   s.resource_id, s.scope_name
            FROM spans s
            WHERE s.organization_id = :org_id AND s.trace_id = :trace_id
            ORDER BY s.start_time ASC
            LIMIT :limit
            """
        ),
        {"org_id": str(organization_id), "trace_id": trace_id, "limit": MAX_SPANS_PER_TRACE + 1},
    )

    truncated = len(rows) > MAX_SPANS_PER_TRACE
    rows = rows[:MAX_SPANS_PER_TRACE]
    if not rows:
        return {"trace_id": trace_id, "spans": [], "found": False}

    by_span_id = {r.span_id: r for r in rows}

    def depth_of(row) -> int:
        """Walk to the root, guarding against a cycle a hostile client could send."""
        depth = 0
        seen = {row.span_id}
        parent = row.parent_span_id
        while parent and parent in by_span_id and parent not in seen:
            seen.add(parent)
            depth += 1
            parent = by_span_id[parent].parent_span_id
            if depth > 64:
                break
        return depth

    trace_start = min(r.start_time for r in rows)
    spans = [
        {
            "id": str(r.id),
            "span_id": r.span_id,
            "parent_span_id": r.parent_span_id,
            "name": r.name,
            "kind": r.kind,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "duration_ms": round((r.duration_ns or 0) / 1_000_000, 3),
            # Offset from the start of the trace: what a waterfall positions
            # its bars by.
            "offset_ms": round((r.start_time - trace_start).total_seconds() * 1000, 3),
            "depth": depth_of(r),
            "status_code": r.status_code,
            "status_message": r.status_message,
            "attributes": r.attributes or {},
            "events": r.events or [],
            "service_name": r.service_name,
            "environment": r.environment,
            "service_version": r.service_version,
            "resource_id": str(r.resource_id),
            "scope_name": r.scope_name,
            # An orphan is a span whose parent is genuinely missing, not one
            # that is simply a root. The distinction matters when reading a
            # partial trace.
            "orphaned": bool(r.parent_span_id and r.parent_span_id not in by_span_id),
        }
        for r in rows
    ]

    total_ms = max((r.end_time - trace_start).total_seconds() * 1000 for r in rows)
    return {
        "trace_id": trace_id,
        "found": True,
        "started_at": trace_start,
        "duration_ms": round(total_ms, 3),
        "span_count": len(spans),
        "error_count": sum(1 for s in spans if s["status_code"] == "error"),
        "services": sorted({s["service_name"] for s in spans if s["service_name"]}),
        "spans": spans,
        "truncated": truncated,
    }


# ── correlation ─────────────────────────────────────────────────────────────


def logs_for_trace(
    db: Session, organization_id: uuid.UUID, trace_id: str, *, limit: int = 100
) -> list[dict[str, Any]]:
    """The log lines a trace produced.

    This is the whole point of storing trace_id on a log record: it turns
    "this request was slow" into "and here is what it printed while it was".
    """
    if not trace_id or len(trace_id) > 32:
        raise SignalQueryError("That is not a valid trace id.")

    rows = _run(
        db,
        text(
            """
            SELECT l.id, l.observed_at, l.timestamp, l.severity_number, l.severity_text,
                   l.severity_band, l.body, l.attributes, l.trace_id, l.span_id,
                   l.service_name, l.environment, l.service_version, l.resource_id,
                   l.scope_name, l.dropped_attributes_count, l.redacted_keys
            FROM log_records l
            WHERE l.organization_id = :org_id AND l.trace_id = :trace_id
            ORDER BY l.observed_at ASC
            LIMIT :limit
            """
        ),
        {
            "org_id": str(organization_id),
            "trace_id": trace_id,
            "limit": max(1, min(limit, MAX_PAGE_SIZE)),
        },
    )
    return [_log_row(row) for row in rows]
