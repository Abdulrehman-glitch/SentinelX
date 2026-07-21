import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

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

    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "commit_sha": settings.commit_sha,
        "environment": settings.app_env,
        "api_status": "online",
        "database_status": database_status,
        "ready": database_status == "online",
        "uptime_seconds": round(time.time() - _process_started_at, 3),
    }