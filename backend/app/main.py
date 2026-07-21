import inspect
import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
except Exception:  # pragma: no cover - defensive fallback
    class RateLimitExceeded(Exception):
        pass

    async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
        return Response(
            content='{"detail":"Too many requests. Please wait and try again."}',
            media_type="application/json",
            status_code=429,
        )

from app.api.router import api_router
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.logging_config import configure_logging
from app.core.request_context import reset_request_id, set_request_id
from app.db.session import SessionLocal
from app.services.security_log_service import create_security_log

settings = get_settings()
configure_logging()
_access_logger = logging.getLogger("sentinelx.access")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend API for SentinelX distributed monitoring and self-healing platform.",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

# Rate limiter state
app.state.limiter = limiter


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return 429 and record a security log entry where possible."""
    ip = request.client.host if request.client else "unknown"
    try:
        db = SessionLocal()
        try:
            create_security_log(
                db,
                event_type="rate_limit_violation",
                action="rate_limit",
                message=f"Rate limit exceeded on {request.method} {request.url.path}",
                severity="warning",
                actor_type="anonymous",
                ip_address=ip,
                resource_type="http_request",
                resource_id=request.url.path,
                status="failure",
                metadata={"method": request.method, "path": request.url.path},
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        # Do not make rate-limit responses fail because logging failed.
        pass
    # slowapi's real _rate_limit_exceeded_handler is sync (returns a
    # JSONResponse directly); only the "slowapi not installed" fallback
    # stub above is async. Handle both rather than assuming either.
    result = _rate_limit_exceeded_handler(request, exc)
    if inspect.isawaitable(result):
        result = await result
    return result


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


@app.middleware("http")
async def add_request_id(request: Request, call_next) -> Response:
    """Tag every request with a correlation ID (accepted from the client if
    present, generated otherwise), thread it through logging for the
    duration of the request, and echo it back on the response so a client
    or upstream proxy can correlate its own logs against ours."""
    incoming_id = request.headers.get("X-Request-ID", "").strip()
    request_id = incoming_id or str(uuid.uuid4())
    token = set_request_id(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        _access_logger.info(
            "request completed",
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
    finally:
        reset_request_id(token)


# CORS
allowed_origins = [origin.strip() for origin in settings.backend_cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    if settings.security_headers_enabled:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "message": "SentinelX API is running",
        "version": settings.app_version,
        "docs": "/docs" if settings.app_env != "production" else None,
        "health": "/api/v1/health",
    }


app.include_router(api_router, prefix="/api/v1")
