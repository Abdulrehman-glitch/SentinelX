"""Log and trace exploration.

Every route is organisation-scoped from the authenticated session, never from a
caller-supplied organisation id, so a tenant cannot reach another tenant's logs
by guessing a UUID - the id is not an input.

The correlation routes are the reason the other two exist. A metric spike is
only useful if it leads somewhere: `/signals/traces/{trace_id}` assembles the
waterfall, `/signals/traces/{trace_id}/logs` returns what that request printed
while it ran, and both are reachable from an id that appears on a log line.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_org_scoped_user
from app.db.session import get_db
from app.models.user import User
from app.services import signal_query_service as sq

router = APIRouter(prefix="/signals", tags=["Logs & Traces"])


def _organization_id(user: User) -> uuid.UUID:
    if user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This account is not attached to an organization, so it has no signals to query.",
        )
    return user.organization_id


def _translate(exc: Exception) -> HTTPException:
    """Validation failures are 400 with the reason; timeouts are 504.

    504 rather than 500 for a timeout because the request was valid and the
    server ran out of time, which is a different thing for a client to act on.
    """
    if isinstance(exc, sq.SignalQueryError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc))


@router.get("/logs")
def search_logs(
    start: datetime = Query(...),
    end: datetime = Query(...),
    search: str | None = Query(default=None, max_length=128),
    severity: list[str] = Query(default_factory=list),
    min_severity: str | None = Query(default=None),
    service: list[str] = Query(default_factory=list),
    environment: list[str] = Query(default_factory=list),
    resource_id: list[uuid.UUID] = Query(default_factory=list),
    trace_id: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=200),
    cursor: str | None = Query(default=None, max_length=512),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_org_scoped_user),
) -> dict:
    """Logs for one organisation, newest first, keyset-paged."""
    try:
        page = sq.search_logs(
            db,
            _organization_id(current_user),
            start=start,
            end=end,
            search=search,
            severities=tuple(severity),
            min_severity=min_severity,
            services=tuple(service),
            environments=tuple(environment),
            resource_ids=tuple(resource_id),
            trace_id=trace_id,
            limit=limit,
            cursor=cursor,
        )
    except (sq.SignalQueryError, sq.SignalQueryTimeout) as exc:
        raise _translate(exc) from exc

    return {"items": page.items, "next_cursor": page.next_cursor}


@router.get("/logs/facets")
def log_facets(
    start: datetime = Query(...),
    end: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_org_scoped_user),
) -> dict:
    """Counts per service, environment and severity - what makes the explorer
    navigable rather than a search box over a void."""
    try:
        return sq.log_facets(db, _organization_id(current_user), start=start, end=end)
    except (sq.SignalQueryError, sq.SignalQueryTimeout) as exc:
        raise _translate(exc) from exc


@router.get("/traces")
def search_traces(
    start: datetime = Query(...),
    end: datetime = Query(...),
    service: list[str] = Query(default_factory=list),
    environment: list[str] = Query(default_factory=list),
    operation: str | None = Query(default=None, max_length=128),
    status_code: str | None = Query(default=None, alias="status"),
    min_duration_ms: float | None = Query(default=None, ge=0),
    max_duration_ms: float | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None, max_length=512),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_org_scoped_user),
) -> dict:
    """Traces, not spans: one row per trace, summarised by its root."""
    try:
        page = sq.search_traces(
            db,
            _organization_id(current_user),
            start=start,
            end=end,
            services=tuple(service),
            environments=tuple(environment),
            operation=operation,
            status=status_code,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            limit=limit,
            cursor=cursor,
        )
    except (sq.SignalQueryError, sq.SignalQueryTimeout) as exc:
        raise _translate(exc) from exc

    return {"items": page.items, "next_cursor": page.next_cursor}


@router.get("/traces/{trace_id}")
def get_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_org_scoped_user),
) -> dict:
    """One trace, assembled into a waterfall.

    A trace with no spans in this organisation returns `found: false` rather
    than 404, because "this id is not yours" and "this id has expired" must
    look identical from outside - a 404 that appears only for ids existing
    elsewhere is an existence oracle.
    """
    try:
        return sq.get_trace(db, _organization_id(current_user), trace_id)
    except (sq.SignalQueryError, sq.SignalQueryTimeout) as exc:
        raise _translate(exc) from exc


@router.get("/traces/{trace_id}/logs")
def logs_for_trace(
    trace_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_org_scoped_user),
) -> dict:
    """What this request printed while it ran."""
    try:
        items = sq.logs_for_trace(db, _organization_id(current_user), trace_id, limit=limit)
    except (sq.SignalQueryError, sq.SignalQueryTimeout) as exc:
        raise _translate(exc) from exc

    return {"items": items, "trace_id": trace_id}
