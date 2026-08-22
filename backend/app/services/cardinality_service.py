"""Bounding what ingestion is allowed to create.

The failure this exists to prevent is mundane and catastrophic. Someone adds a
request id, a full file path or a timestamp as a metric attribute. Each sample
now has a different attribute set, so each sample creates a new series. One
misconfigured service turns a steady thousand points per minute into a thousand
*series* per minute, and the first symptom is a full disk.

Rate limiting does not help: the request volume is unchanged and entirely
legitimate-looking. The only thing that helps is refusing to create unbounded
series, which is what the budget below does.

Two deliberate choices:

Rejection, not truncation. Silently dropping the 33rd attribute would change
what a series *means* while still accepting it, and the operator would never
learn their instrumentation is wrong. A rejection with a reason is recoverable;
a quietly mangled series is not.

Partial rejection. One bad datapoint in a batch of five hundred must not
discard the other 499. Every check returns a reason per item, and the caller
assembles those into an OTLP partial-success response.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.metric_series import MetricSeries
from app.services.telemetry_identity import AttributeValue

# Machine-readable rejection codes. These reach clients (in OTLP partial
# success) and security logs, so they are part of the contract and must not be
# renamed casually.
REJECT_METRIC_NAME_EMPTY = "metric_name_empty"
REJECT_METRIC_NAME_TOO_LONG = "metric_name_too_long"
REJECT_TOO_MANY_ATTRIBUTES = "too_many_attributes"
REJECT_ATTRIBUTE_KEY_TOO_LONG = "attribute_key_too_long"
REJECT_ATTRIBUTE_VALUE_TOO_LONG = "attribute_value_too_long"
REJECT_VALUE_NOT_FINITE = "value_not_finite"
REJECT_TIMESTAMP_TOO_FAR_FUTURE = "timestamp_too_far_future"
REJECT_TIMESTAMP_TOO_OLD = "timestamp_too_old"
REJECT_SERIES_BUDGET_EXHAUSTED = "series_budget_exhausted"
REJECT_TOO_MANY_POINTS = "too_many_points"
REJECT_TOO_MANY_SERIES = "too_many_series"


@dataclass(frozen=True)
class Rejection:
    """Why one item was refused. `subject` names it well enough to fix."""

    reason: str
    subject: str
    detail: str


@dataclass
class SeriesBudget:
    """How many new series this organisation may still create in the window.

    Checked once per request and then decremented locally, so a batch
    introducing 900 new series costs one count query rather than 900.
    """

    limit: int
    used: int
    window_seconds: int
    _granted: int = field(default=0, repr=False)

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used - self._granted)

    def try_grant(self) -> bool:
        """Reserve room for one new series. False when the budget is spent."""
        if self.remaining <= 0:
            return False
        self._granted += 1
        return True

    @property
    def granted(self) -> int:
        return self._granted


def validate_metric_name(name: str, settings: Settings) -> Rejection | None:
    if not name or not name.strip():
        return Rejection(REJECT_METRIC_NAME_EMPTY, "<unnamed>", "Metric name is empty.")
    if len(name) > settings.ingest_max_metric_name_length:
        return Rejection(
            REJECT_METRIC_NAME_TOO_LONG,
            name[:64],
            f"Metric name is {len(name)} characters; the limit is "
            f"{settings.ingest_max_metric_name_length}.",
        )
    return None


def validate_attributes(
    attributes: Mapping[str, AttributeValue],
    settings: Settings,
    *,
    subject: str,
) -> Rejection | None:
    """Check a canonical attribute bag against the shape limits.

    Returns the first problem found rather than a list: the caller rejects the
    item either way, and one precise reason is more useful to whoever has to fix
    the instrumentation than a wall of them.
    """
    if len(attributes) > settings.ingest_max_attributes:
        return Rejection(
            REJECT_TOO_MANY_ATTRIBUTES,
            subject,
            f"{len(attributes)} attributes; the limit is {settings.ingest_max_attributes}. "
            "A per-sample value such as a request id or timestamp is almost always the cause.",
        )

    for key, value in attributes.items():
        if len(key) > settings.ingest_max_attribute_key_length:
            return Rejection(
                REJECT_ATTRIBUTE_KEY_TOO_LONG,
                subject,
                f"Attribute key '{key[:48]}...' is {len(key)} characters; the limit is "
                f"{settings.ingest_max_attribute_key_length}.",
            )
        if isinstance(value, str) and len(value) > settings.ingest_max_attribute_value_length:
            return Rejection(
                REJECT_ATTRIBUTE_VALUE_TOO_LONG,
                subject,
                f"Attribute '{key}' has a {len(value)}-character value; the limit is "
                f"{settings.ingest_max_attribute_value_length}. Long values are usually paths or "
                "payloads, which belong in logs rather than in a dimension.",
            )

    return None


def validate_value(value: float, settings: Settings, *, subject: str) -> Rejection | None:
    """NaN and the infinities are not storable measurements.

    Postgres `double precision` accepts NaN, so this is not the database
    protecting itself — it is refusing to let a value that breaks every
    downstream aggregate (avg, percentile, comparison) enter the store at all.
    """
    if value != value or value in (float("inf"), float("-inf")):
        return Rejection(
            REJECT_VALUE_NOT_FINITE,
            subject,
            "Value is NaN or infinite; only finite numbers are storable.",
        )
    return None


def validate_timestamp(
    recorded_at: datetime,
    settings: Settings,
    *,
    subject: str,
    now: datetime | None = None,
) -> Rejection | None:
    now = now or datetime.now(timezone.utc)

    if recorded_at > now + timedelta(seconds=settings.ingest_max_future_skew_seconds):
        return Rejection(
            REJECT_TIMESTAMP_TOO_FAR_FUTURE,
            subject,
            f"Timestamp {recorded_at.isoformat()} is more than "
            f"{settings.ingest_max_future_skew_seconds}s ahead of the server clock.",
        )

    if recorded_at < now - timedelta(days=settings.ingest_max_backfill_age_days):
        return Rejection(
            REJECT_TIMESTAMP_TOO_OLD,
            subject,
            f"Timestamp {recorded_at.isoformat()} is older than the "
            f"{settings.ingest_max_backfill_age_days}-day backfill window.",
        )

    return None


def load_series_budget(db: Session, organization_id, settings: Settings) -> SeriesBudget:
    """How many new series this tenant has created in the current window.

    One indexed count per request, served by (organization_id, first_seen_at).
    """
    window_start = datetime.now(timezone.utc) - timedelta(
        seconds=settings.ingest_new_series_window_seconds
    )
    used = db.scalar(
        select(func.count())
        .select_from(MetricSeries)
        .where(
            MetricSeries.organization_id == organization_id,
            MetricSeries.first_seen_at >= window_start,
        )
    )
    return SeriesBudget(
        limit=settings.ingest_max_new_series_per_window,
        used=int(used or 0),
        window_seconds=settings.ingest_new_series_window_seconds,
    )


def budget_exhausted_rejection(budget: SeriesBudget, *, subject: str) -> Rejection:
    return Rejection(
        REJECT_SERIES_BUDGET_EXHAUSTED,
        subject,
        f"This organisation has created {budget.used + budget.granted} new metric series in the "
        f"last {budget.window_seconds}s; the limit is {budget.limit}. Existing series continue to "
        "accept points — only new ones are refused.",
    )
