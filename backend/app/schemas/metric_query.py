"""Request and response shapes for the canonical metric read path."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MetricQueryRequest(BaseModel):
    """A bounded timeseries request.

    Deliberately a POST body rather than a query string: `filters` and
    `group_by` are structured, and a URL long enough to hold them is a URL that
    something in the middle eventually truncates.
    """

    model_config = ConfigDict(extra="forbid")

    metric: str = Field(min_length=1, max_length=255)
    start: datetime
    end: datetime

    aggregation: Literal[
        "avg", "min", "max", "sum", "count", "p50", "p75", "p90", "p95", "p99"
    ] = "avg"

    resource_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    device_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    resource_types: list[str] = Field(default_factory=list, max_length=10)
    sources: list[str] = Field(default_factory=list, max_length=10)

    # Exact-match dimension filters against the series attribute set.
    filters: dict[str, str] = Field(default_factory=dict)

    # Attribute keys, or the literal "resource" for one line per resource.
    group_by: list[str] = Field(default_factory=list, max_length=3)

    bucket_seconds: int | None = Field(default=None, ge=1, le=604800)
    max_points: int = Field(default=500, ge=1, le=5000)


class MetricPointOut(BaseModel):
    # Short names: this is the one payload where the field name is repeated
    # once per datapoint, so `timestamp`/`value` would cost more than the data.
    t: datetime
    v: float


class MetricSeriesOut(BaseModel):
    key: str
    labels: dict[str, str]
    sample_count: int
    points: list[MetricPointOut]


class MetricQueryResponse(BaseModel):
    metric: str
    aggregation: str
    unit: str | None
    kind: str | None
    start: datetime
    end: datetime
    bucket_seconds: int
    series: list[MetricSeriesOut]
    total_points: int
    series_truncated: bool
    warnings: list[str]


class MetricCatalogEntry(BaseModel):
    metric_name: str
    unit: str | None
    kind: str | None
    series_count: int
    last_seen_at: datetime | None


class MetricCatalogResponse(BaseModel):
    items: list[MetricCatalogEntry]
    next_cursor: str | None


class SeriesEntry(BaseModel):
    series_id: uuid.UUID
    resource_id: uuid.UUID
    resource_name: str | None
    resource_type: str
    device_id: uuid.UUID | None
    attributes: dict[str, str | int | float | bool | None]
    unit: str | None
    kind: str
    source: str
    last_seen_at: datetime | None


class SeriesListResponse(BaseModel):
    items: list[SeriesEntry]
    next_cursor: str | None
