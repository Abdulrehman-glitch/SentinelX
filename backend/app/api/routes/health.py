from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health_check() -> dict:
    """
    Basic API and database health check.

    This endpoint proves that:
    - the FastAPI backend is running;
    - application configuration is loading;
    - PostgreSQL is reachable from the backend.
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
        "environment": settings.app_env,
        "api_status": "online",
        "database_status": database_status,
    }