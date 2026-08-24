import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.api.routes.events import MAX_CONCURRENT_STREAMS, open_stream_count
from app.core.limiter import limiter_health
from app.db.session import SessionLocal, engine
from app.protocol import protocol_summary
from app.services import outbox_service

router = APIRouter(prefix="/health", tags=["Health"])

# Process start time, captured once at import (module load = process start
# for a single-worker uvicorn process). Powers uptime_seconds below.
_process_started_at = time.time()


@router.get("")
def health_check() -> dict:
    """
    Basic API and database health check.

    This endpoint proves that:
    - the FastAPI backend is running (liveness — true for any response);
    - application configuration is loading;
    - PostgreSQL is reachable from the backend (readiness — `ready` below).
    """

    settings = get_settings()

    database_status = "offline"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_status = "online"
    except Exception:
        database_status = "offline"

    # Queue health is part of readiness, not a separate dashboard concern. An
    # API that accepts telemetry it cannot process is not healthy just because
    # its database answers SELECT 1 — so a backlog the worker is visibly
    # failing to drain degrades this endpoint, and the OTLP path sheds load on
    # the same signal.
    queue: dict = {"status": "unknown"}
    if database_status == "online":
        try:
            with SessionLocal() as session:
                stats = outbox_service.queue_stats(session)
            degraded = stats.backlog >= settings.ingest_backlog_degraded_threshold
            shedding = stats.backlog >= settings.ingest_backlog_shed_threshold
            queue = {
                "status": "shedding" if shedding else ("degraded" if degraded else "healthy"),
                "backlog": stats.backlog,
                "pending": stats.pending,
                "failed": stats.failed,
                "dead": stats.dead,
                "oldest_pending_age_seconds": stats.oldest_pending_age_seconds,
            }
        except Exception:
            # A queue read failing must not make the whole probe fail; the
            # database check above is what liveness actually turns on.
            queue = {"status": "unknown"}

    # Shared rate limiting is a security control, so its degradation is
    # reported rather than absorbed: an operator needs to know that limits
    # have quietly become per-process.
    rate_limiting = limiter_health()

    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "commit_sha": settings.commit_sha,
        "environment": settings.app_env,
        "api_status": "online",
        "database_status": database_status,
        # Ready means "can accept work", which is narrower than "is healthy".
        # A degraded queue still accepts telemetry; only `shedding` does not.
        "ready": database_status == "online" and queue.get("status") != "shedding",
        "degraded": queue.get("status") in {"degraded", "shedding"}
        or rate_limiting.get("status") == "degraded",
        "queue": queue,
        "rate_limiting": rate_limiting,
        # Per process, not per cluster. An operator watching this climb toward
        # the limit is watching the reason streams will start being refused.
        "live_streams": {"open": open_stream_count(), "limit": MAX_CONCURRENT_STREAMS},
        "uptime_seconds": round(time.time() - _process_started_at, 3),
        "protocol": protocol_summary(),
    }