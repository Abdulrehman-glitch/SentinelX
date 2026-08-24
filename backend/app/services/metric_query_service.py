"""Bounded reads over the canonical metric model.

This is the query half of `resources -> metric_series -> metric_points`. It
exists so readers can move off `system_metrics` without anyone inventing their
own SQL, and so every read has a ceiling: a browser asking for "CPU, last 30
days" gets downsampled buckets, not four million rows.

Three rules shape the whole module.

**Nothing is unbounded.** A range wider than the configured maximum, a page
larger than the cap, or a bucket count above `max_points` is a 4xx, not a slow
query. Bucket width is chosen from the range so the point count stays within
budget whatever the caller asks for.

**Aggregations that would lie are refused.** Summing a gauge across a time
bucket produces a number with no physical meaning, and so does summing a
cumulative counter. `_validate_aggregation` rejects those combinations with an
explanation rather than returning a plausible-looking wrong answer.

**Group keys are bound, never interpolated.** Callers choose which series
attribute to group by, and that value reaches SQL as a bind parameter
(`attributes ->> :gb0`), so an attribute key is data even though it decides the
shape of the result.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import get_settings

# Aggregations the engine can evaluate. Percentiles use percentile_cont, which
# interpolates - correct for latency-shaped data and the reason p99 of two
# samples is not simply the larger one.
AGGREGATIONS = ("avg", "min", "max", "sum", "count", "p50", "p75", "p90", "p95", "p99")

_PERCENTILES = {"p50": 0.5, "p75": 0.75, "p90": 0.9, "p95": 0.95, "p99": 0.99}

# Bucket widths the resolver may choose, in seconds. Round numbers only: a
# 47-second bucket is technically fine and impossible to reason about.
_RESOLUTION_LADDER = (
    10, 15, 30, 60, 120, 300, 600, 900, 1800,
    3600, 7200, 10800, 21600, 43200, 86400, 604800,
)

# The special group key meaning "one series per resource" rather than per
# attribute value.
GROUP_BY_RESOURCE = "resource"

# Grouping by more than a handful of dimensions produces a chart nobody can
# read and a result set that grows multiplicatively.
MAX_GROUP_BY_KEYS = 3


class MetricQueryError(ValueError):
    """A query that is invalid rather than merely empty."""


class MetricQueryTimeout(RuntimeError):
    """The query exceeded its statement timeout and was cancelled."""


@dataclass(frozen=True)
class MetricQuery:
    organization_id: uuid.UUID
    metric_name: str
    start: datetime
    end: datetime
    aggregation: str = "avg"
    resource_ids: tuple[uuid.UUID, ...] = ()
    device_ids: tuple[uuid.UUID, ...] = ()
    resource_types: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    filters: dict[str, str] = field(default_factory=dict)
    group_by: tuple[str, ...] = ()
    bucket_seconds: int | None = None
    max_points: int = 500


@dataclass(frozen=True)
class MetricSeriesResult:
    key: str
    labels: dict[str, str]
    points: list[tuple[datetime, float]]
    sample_count: int


@dataclass(frozen=True)
class MetricQueryResult:
    metric_name: str
    aggregation: str
    unit: str | None
    kind: str | None
    start: datetime
    end: datetime
    bucket_seconds: int
    series: list[MetricSeriesResult]
    total_points: int
    series_truncated: bool
    warnings: list[str]


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def choose_bucket_seconds(range_seconds: float, max_points: int) -> int:
    """Smallest ladder width that keeps the bucket count within budget."""
    if max_points <= 0:
        raise MetricQueryError("max_points must be positive.")
    ideal = range_seconds / max_points
    for candidate in _RESOLUTION_LADDER:
        if candidate >= ideal:
            return candidate
    # Range so wide that even weekly buckets overflow - round up to whole weeks.
    return int(math.ceil(ideal / 604800) * 604800)


def _validate_aggregation(aggregation: str, kinds: set[str]) -> list[str]:
    """Refuse aggregations that would produce a meaningless number.

    Returns advisory warnings for combinations that are defensible but worth
    flagging; raises for the ones that are simply wrong.
    """
    if aggregation not in AGGREGATIONS:
        raise MetricQueryError(
            f"Unsupported aggregation '{aggregation}'. Supported: {', '.join(AGGREGATIONS)}."
        )

    warnings: list[str] = []
    if aggregation == "sum":
        bad = kinds & {"gauge", "sum_cumulative"}
        if bad:
            raise MetricQueryError(
                "Summing samples across a time bucket is only meaningful for delta sums. "
                f"This metric is stored as {'/'.join(sorted(bad))}; use avg, max or min instead."
            )
    if aggregation in _PERCENTILES and "sum_cumulative" in kinds:
        warnings.append(
            "Percentiles of a cumulative counter describe the counter's value, not the rate "
            "of increase; interpret with care."
        )
    if len(kinds) > 1:
        warnings.append(
            "Selected series mix metric kinds ("
            + ", ".join(sorted(kinds))
            + "); aggregating across them may not be comparable."
        )
    return warnings


def _aggregate_expression(aggregation: str) -> str:
    if aggregation in _PERCENTILES:
        return f"percentile_cont({_PERCENTILES[aggregation]}) WITHIN GROUP (ORDER BY mp.value)"
    if aggregation == "count":
        return "count(*)::double precision"
    return f"{aggregation}(mp.value)"


def _series_filter_sql(query: MetricQuery, params: dict[str, Any]) -> str:
    clauses = ["ms.organization_id = :org_id", "ms.metric_name = :metric_name"]
    params["org_id"] = str(query.organization_id)
    params["metric_name"] = query.metric_name

    if query.resource_ids:
        clauses.append("ms.resource_id = ANY(CAST(:resource_ids AS uuid[]))")
        params["resource_ids"] = [str(r) for r in query.resource_ids]
    if query.device_ids:
        clauses.append("r.device_id = ANY(CAST(:device_ids AS uuid[]))")
        params["device_ids"] = [str(d) for d in query.device_ids]
    if query.resource_types:
        clauses.append("r.resource_type = ANY(CAST(:resource_types AS text[]))")
        params["resource_types"] = list(query.resource_types)
    if query.sources:
        clauses.append("ms.source = ANY(CAST(:sources AS text[]))")
        params["sources"] = list(query.sources)
    if query.filters:
        # Containment against the JSONB attribute set: one indexable predicate
        # regardless of how many dimensions the caller pinned.
        clauses.append("ms.attributes @> CAST(:attr_filter AS jsonb)")
        params["attr_filter"] = json.dumps(query.filters)
    return " AND ".join(clauses)


def _validate(query: MetricQuery) -> MetricQuery:
    settings = get_settings()

    start = _as_utc(query.start)
    end = _as_utc(query.end)
    if end <= start:
        raise MetricQueryError("`end` must be after `start`.")

    range_seconds = (end - start).total_seconds()
    max_range = settings.metric_query_max_range_days * 86400
    if range_seconds > max_range:
        raise MetricQueryError(
            f"Requested range spans {range_seconds / 86400:.1f} days; the maximum is "
            f"{settings.metric_query_max_range_days} days. Narrow the range or query in pages."
        )

    if query.max_points < 1 or query.max_points > settings.metric_query_max_points:
        raise MetricQueryError(
            f"max_points must be between 1 and {settings.metric_query_max_points}."
        )

    if len(query.group_by) > MAX_GROUP_BY_KEYS:
        raise MetricQueryError(f"At most {MAX_GROUP_BY_KEYS} group_by keys are allowed.")
    if len(set(query.group_by)) != len(query.group_by):
        raise MetricQueryError("group_by keys must be unique.")

    if not query.metric_name.strip():
        raise MetricQueryError("`metric` is required.")

    bucket = query.bucket_seconds
    if bucket is not None:
        if bucket < _RESOLUTION_LADDER[0]:
            raise MetricQueryError(f"bucket_seconds must be at least {_RESOLUTION_LADDER[0]}.")
        if range_seconds / bucket > query.max_points:
            raise MetricQueryError(
                f"bucket_seconds={bucket} over this range yields "
                f"{int(range_seconds / bucket)} points, above max_points={query.max_points}. "
                "Widen the bucket, narrow the range, or omit bucket_seconds for automatic resolution."
            )
    else:
        bucket = choose_bucket_seconds(range_seconds, query.max_points)

    return MetricQuery(
        organization_id=query.organization_id,
        metric_name=query.metric_name.strip(),
        start=start,
        end=end,
        aggregation=query.aggregation,
        resource_ids=query.resource_ids,
        device_ids=query.device_ids,
        resource_types=query.resource_types,
        sources=query.sources,
        filters=query.filters,
        group_by=query.group_by,
        bucket_seconds=bucket,
        max_points=query.max_points,
    )


def _describe_selected_series(
    db: Session, query: MetricQuery
) -> tuple[set[str], set[str | None], int]:
    params: dict[str, Any] = {}
    where = _series_filter_sql(query, params)
    rows = db.execute(
        text(
            f"""
            SELECT ms.metric_kind, ms.metric_unit, count(*) AS n
            FROM metric_series ms
            JOIN resources r ON r.id = ms.resource_id
            WHERE {where}
            GROUP BY ms.metric_kind, ms.metric_unit
            """
        ),
        params,
    ).all()
    return {r.metric_kind for r in rows}, {r.metric_unit for r in rows}, sum(r.n for r in rows)


def run_query(db: Session, query: MetricQuery) -> MetricQueryResult:
    """Execute a bounded, downsampled timeseries query."""
    settings = get_settings()
    query = _validate(query)
    bucket_seconds = query.bucket_seconds or 60

    kinds, units, series_count = _describe_selected_series(db, query)
    if series_count == 0:
        return MetricQueryResult(
            metric_name=query.metric_name,
            aggregation=query.aggregation,
            unit=None,
            kind=None,
            start=query.start,
            end=query.end,
            bucket_seconds=bucket_seconds,
            series=[],
            total_points=0,
            series_truncated=False,
            warnings=["No series matched this selection."],
        )

    warnings = _validate_aggregation(query.aggregation, kinds)
    if len(units) > 1:
        warnings.append(
            "Selected series report different units ("
            + ", ".join(sorted(str(u) for u in units))
            + ")."
        )

    params: dict[str, Any] = {}
    series_where = _series_filter_sql(query, params)
    params["start"] = query.start
    params["end"] = query.end
    params["bucket"] = timedelta(seconds=bucket_seconds)
    # Bucket boundaries are anchored to the range start, so the first bucket
    # always begins exactly at `start` and two queries over the same range
    # line up point-for-point.
    params["origin"] = query.start

    group_exprs: list[str] = []
    for index, key in enumerate(query.group_by):
        if key == GROUP_BY_RESOURCE:
            group_exprs.append("COALESCE(r.display_name, r.id::text)")
        else:
            params[f"gb{index}"] = key
            group_exprs.append(f"ms.attributes ->> :gb{index}")

    if group_exprs:
        select_head = ", ".join(f"{expr} AS g{i}" for i, expr in enumerate(group_exprs)) + ", "
        keys_sql = ", ".join(str(i + 1) for i in range(len(group_exprs)))
        group_sql = f"GROUP BY {keys_sql}, bucket ORDER BY {keys_sql}, bucket"
    else:
        select_head = ""
        group_sql = "GROUP BY bucket ORDER BY bucket"

    max_buckets = int((query.end - query.start).total_seconds() // bucket_seconds) + 1
    row_cap = settings.metric_query_max_series * max_buckets + 1
    params["row_cap"] = row_cap

    sql = text(
        f"""
        SELECT {select_head}
               date_bin(CAST(:bucket AS interval), mp.recorded_at, CAST(:origin AS timestamptz)) AS bucket,
               {_aggregate_expression(query.aggregation)} AS value,
               count(*) AS sample_count
        FROM metric_points mp
        JOIN metric_series ms ON ms.id = mp.series_id
        JOIN resources r ON r.id = ms.resource_id
        WHERE mp.organization_id = :org_id
          AND mp.recorded_at >= :start
          AND mp.recorded_at < :end
          AND {series_where}
        {group_sql}
        LIMIT :row_cap
        """
    )

    try:
        # A pathological query must cost a bounded amount of database time, not
        # hold a connection until the client gives up. LOCAL scopes this to the
        # surrounding transaction, so it cannot leak into the pooled session.
        db.execute(text(f"SET LOCAL statement_timeout = {int(settings.metric_query_timeout_ms)}"))
        rows = db.execute(sql, params).all()
    except DBAPIError as exc:
        if "statement timeout" in str(exc.orig or exc).lower():
            raise MetricQueryTimeout(
                "The metric query exceeded its time budget. Narrow the range, "
                "add filters, or request a coarser resolution."
            ) from exc
        raise

    grouped: dict[tuple[str, ...], list[tuple[datetime, float]]] = {}
    samples: dict[tuple[str, ...], int] = {}
    for row in rows:
        key = tuple(
            "(none)" if getattr(row, f"g{i}") is None else str(getattr(row, f"g{i}"))
            for i in range(len(group_exprs))
        )
        grouped.setdefault(key, []).append((row.bucket, float(row.value)))
        samples[key] = samples.get(key, 0) + int(row.sample_count)

    series_truncated = len(rows) >= row_cap or len(grouped) > settings.metric_query_max_series
    ordered_keys = sorted(grouped)[: settings.metric_query_max_series]

    results: list[MetricSeriesResult] = []
    for key in ordered_keys:
        labels = {k: key[i] for i, k in enumerate(query.group_by)}
        results.append(
            MetricSeriesResult(
                key=" / ".join(key) if key else query.metric_name,
                labels=labels,
                points=grouped[key],
                sample_count=samples[key],
            )
        )

    if series_truncated:
        warnings.append(
            f"Result truncated to {settings.metric_query_max_series} series. "
            "Add filters or group by fewer dimensions to see the rest."
        )

    return MetricQueryResult(
        metric_name=query.metric_name,
        aggregation=query.aggregation,
        unit=next(iter(units)) if len(units) == 1 else None,
        kind=next(iter(kinds)) if len(kinds) == 1 else None,
        start=query.start,
        end=query.end,
        bucket_seconds=bucket_seconds,
        series=results,
        total_points=sum(len(s.points) for s in results),
        series_truncated=series_truncated,
        warnings=warnings,
    )


# ── Discovery ────────────────────────────────────────────────────────────
# A chart cannot be built until the caller knows what exists. These are
# cursor-paged rather than "return everything": a busy tenant's metric catalog
# is itself unbounded data.


@dataclass(frozen=True)
class Page:
    items: list[dict[str, Any]]
    next_cursor: str | None


def _escape_like(value: str) -> str:
    """Neutralise LIKE metacharacters so a search box cannot become a scan."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_metric_catalog(
    db: Session,
    organization_id: uuid.UUID,
    *,
    search: str | None = None,
    resource_id: uuid.UUID | None = None,
    limit: int = 100,
    cursor: str | None = None,
) -> Page:
    """Metric names available to one organisation, with kind and unit."""
    limit = max(1, min(limit, 500))
    params: dict[str, Any] = {"org_id": str(organization_id), "limit": limit + 1}
    clauses = ["ms.organization_id = :org_id"]
    if search:
        clauses.append("ms.metric_name ILIKE :search")
        params["search"] = f"%{_escape_like(search)}%"
    if resource_id:
        clauses.append("ms.resource_id = CAST(:resource_id AS uuid)")
        params["resource_id"] = str(resource_id)
    if cursor:
        clauses.append("ms.metric_name > :cursor")
        params["cursor"] = cursor

    rows = db.execute(
        text(
            f"""
            SELECT ms.metric_name,
                   min(ms.metric_unit) AS metric_unit,
                   min(ms.metric_kind) AS metric_kind,
                   count(*) AS series_count,
                   max(ms.last_seen_at) AS last_seen_at
            FROM metric_series ms
            WHERE {' AND '.join(clauses)}
            GROUP BY ms.metric_name
            ORDER BY ms.metric_name
            LIMIT :limit
            """
        ),
        params,
    ).all()

    has_more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[
            {
                "metric_name": r.metric_name,
                "unit": r.metric_unit,
                "kind": r.metric_kind,
                "series_count": int(r.series_count),
                "last_seen_at": r.last_seen_at,
            }
            for r in rows
        ],
        next_cursor=rows[-1].metric_name if has_more and rows else None,
    )


def list_series(
    db: Session,
    organization_id: uuid.UUID,
    metric_name: str,
    *,
    limit: int = 100,
    cursor: str | None = None,
) -> Page:
    """The concrete series behind one metric name, for facet discovery."""
    limit = max(1, min(limit, 500))
    params: dict[str, Any] = {
        "org_id": str(organization_id),
        "metric_name": metric_name,
        "limit": limit + 1,
    }
    clauses = ["ms.organization_id = :org_id", "ms.metric_name = :metric_name"]
    if cursor:
        clauses.append("ms.id > CAST(:cursor AS uuid)")
        params["cursor"] = cursor

    rows = db.execute(
        text(
            f"""
            SELECT ms.id, ms.attributes, ms.metric_unit, ms.metric_kind, ms.source,
                   ms.last_seen_at, r.id AS resource_id, r.display_name, r.resource_type,
                   r.device_id
            FROM metric_series ms
            JOIN resources r ON r.id = ms.resource_id
            WHERE {' AND '.join(clauses)}
            ORDER BY ms.id
            LIMIT :limit
            """
        ),
        params,
    ).all()

    has_more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[
            {
                "series_id": r.id,
                "resource_id": r.resource_id,
                "resource_name": r.display_name,
                "resource_type": r.resource_type,
                "device_id": r.device_id,
                "attributes": r.attributes or {},
                "unit": r.metric_unit,
                "kind": r.metric_kind,
                "source": r.source,
                "last_seen_at": r.last_seen_at,
            }
            for r in rows
        ],
        next_cursor=str(rows[-1].id) if has_more and rows else None,
    )
