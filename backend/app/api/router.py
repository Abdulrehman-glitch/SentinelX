from fastapi import APIRouter

from app.api.routes import (
    agent_commands,
    alert_rules,
    alerts,
    audit_logs,
    auth,
    device_credentials,
    devices,
    enrollment,
    health,
    heartbeats,
    incidents,
    metrics,
    observability,
    organizations,
    overview,
    recovery_actions,
    recovery_commands,
    security_logs,
    telemetry,
    user_settings,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(users.router)
api_router.include_router(user_settings.router)
api_router.include_router(device_credentials.router)
api_router.include_router(enrollment.router)
api_router.include_router(devices.router)
api_router.include_router(heartbeats.router)
api_router.include_router(metrics.router)
api_router.include_router(telemetry.router)
api_router.include_router(alerts.router)
api_router.include_router(recovery_actions.router)
api_router.include_router(security_logs.router)
api_router.include_router(overview.router)
api_router.include_router(audit_logs.router)
api_router.include_router(incidents.router)
api_router.include_router(alert_rules.router)
api_router.include_router(observability.router)
api_router.include_router(recovery_commands.router)
api_router.include_router(agent_commands.router)
