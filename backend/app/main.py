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
from app.db.session import SessionLocal
from app.services.security_log_service import create_security_log

settings = get_settings()

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
    return await _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

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
