"""SentinelX mobile-API dev server. Contract reference for the iOS agent —
not the production backend (that integration is a later, user-approved
phase). Run: uvicorn app.main:app --reload --port 8100  (from server/)."""

from fastapi import FastAPI

from . import database
from .config import Settings
from .errors import install_error_handlers
from .routes import auth, config, devices, telemetry, websocket


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    database.init_schema(settings.database_path)

    app = FastAPI(
        title="SentinelX Mobile API (dev server)",
        version="1.0",
        docs_url="/docs",
    )
    app.state.settings = settings
    install_error_handlers(app)

    prefix = "/api/v1/mobile"
    app.include_router(auth.router, prefix=prefix, tags=["auth"])
    app.include_router(telemetry.router, prefix=prefix, tags=["telemetry"])
    app.include_router(devices.router, prefix=prefix, tags=["devices"])
    app.include_router(config.router, prefix=prefix, tags=["config"])
    app.include_router(websocket.router, prefix=prefix, tags=["websocket"])

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
