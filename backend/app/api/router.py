from fastapi import APIRouter

from app.api.routes import alerts, devices, health, heartbeats, metrics, overview, recovery_actions

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(devices.router)
api_router.include_router(heartbeats.router)
api_router.include_router(metrics.router)
api_router.include_router(alerts.router)
api_router.include_router(recovery_actions.router)
api_router.include_router(overview.router)