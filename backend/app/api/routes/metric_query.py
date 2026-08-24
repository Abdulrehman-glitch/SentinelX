"""The read side of the canonical telemetry model.

Every route here is organisation-scoped from the authenticated session, never
from a caller-supplied organisation id — a tenant cannot ask for another
tenant's series by guessing a UUID, because the id is never an input.

Validation failures come back as 400 with the reason stated in words
("summing a gauge is meaningless", "that range is 120 days"), because the
caller is usually a chart that can correct itself if it is told what is wrong.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_org_scoped_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.metric_query import (
    MetricCatalogResponse,
    MetricQueryRequest,
    MetricQueryResponse,
    MetricSeriesOut,
    SeriesListResponse,
)
from app.services import metric_query_service as mqs

router = APIRouter(prefix="/metric-query", tags=["Metric Query"])


def _organization_id(user: User) -> uuid.UUID:
    if user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This account is not attached to an organization, so it has no telemetry to query.",
        )
    return user.organization_id


@router.post("", response_model=MetricQueryResponse)
def query_metric(
    payload: MetricQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_org_scoped_user),
) -> MetricQueryResponse:
    """Downsampled timeseries for one metric, grouped by up to three dimensions."""
    query = mqs.MetricQuery(
        organization_id=_organization_id(current_user),
        metric_name=payload.metric,
        start=payload.start,
        end=payload.end,
        aggregation=payload.aggregation,
        resource_ids=tuple(payload.resource_ids),
        device_ids=tuple(payload.device_ids),
        resource_types=tuple(payload.resource_types),
        sources=tuple(payload.sources),
        filters=dict(payload.filters),
        group_by=tuple(payload.group_by),
        bucket_seconds=payload.bucket_seconds,
        max_points=payload.max_points,
    )

    try:
        result = mqs.run_query(db, query)
    except mqs.MetricQueryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except mqs.MetricQueryTimeout as exc:
        # 504 rather than 500: the request was valid and the server gave up on
        # time, which is a different thing for a client to retry.
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc

    return MetricQueryResponse(
        metric=result.metric_name,
        aggregation=result.aggregation,
        unit=result.unit,
        kind=result.kind,
        start=result.start,
        end=result.end,
        bucket_seconds=result.bucket_seconds,
        series=[
            MetricSeriesOut(
                key=s.key,
                labels=s.labels,
                sample_count=s.sample_count,
                points=[{"t": t, "v": v} for t, v in s.points],
            )
            for s in result.series
        ],
        total_points=result.total_points,
        series_truncated=result.series_truncated,
        warnings=result.warnings,
    )


@router.get("/catalog", response_model=MetricCatalogResponse)
def metric_catalog(
    search: str | None = Query(default=None, max_length=128),
    resource_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_org_scoped_user),
) -> MetricCatalogResponse:
    """Which metrics this organisation actually has, cursor-paged by name."""
    page = mqs.list_metric_catalog(
        db,
        _organization_id(current_user),
        search=search,
        resource_id=resource_id,
        limit=limit,
        cursor=cursor,
    )
    return MetricCatalogResponse(items=page.items, next_cursor=page.next_cursor)


@router.get("/series", response_model=SeriesListResponse)
def series_for_metric(
    metric: str = Query(min_length=1, max_length=255),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_org_scoped_user),
) -> SeriesListResponse:
    """The concrete series behind one metric name, for building facet filters."""
    page = mqs.list_series(
        db,
        _organization_id(current_user),
        metric,
        limit=limit,
        cursor=str(cursor) if cursor else None,
    )
    return SeriesListResponse(items=page.items, next_cursor=page.next_cursor)
