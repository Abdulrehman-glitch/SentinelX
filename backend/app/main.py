from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend API for SentinelX distributed monitoring and recovery system.",
)

allowed_origins = [
    origin.strip()
    for origin in settings.backend_cors_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    """
    Root endpoint used to confirm that the backend API is reachable.
    """
    return {
        "message": "SentinelX API is running",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


app.include_router(api_router, prefix="/api/v1")