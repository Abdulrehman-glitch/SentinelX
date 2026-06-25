import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.alert import AlertResponse
from app.schemas.device import DeviceResponse
from app.schemas.metric import MetricResponse
from app.schemas.recovery_action import RecoveryActionResponse


class DeviceHealthResponse(BaseModel):
    """
    Health score response used by the device detail page.
    """

    device_id: uuid.UUID
    hostname: str
    device_status: str
    health_score: int | None
    health_status: str
    last_seen_at: datetime | None
    latest_metric: MetricResponse | None
    unresolved_warning_alerts: int
    unresolved_critical_alerts: int
    reasons: list[str]
    evaluated_at: datetime


class DeviceSummaryCounts(BaseModel):
    """
    Aggregated counters for a single device.
    """

    metrics: int
    heartbeats: int
    alerts_total: int
    alerts_unresolved: int
    recovery_actions: int


class DeviceSummaryResponse(BaseModel):
    """
    Combined response for the frontend device detail page.

    This avoids the frontend needing to make many requests before it can
    render a useful device view.
    """

    device: DeviceResponse
    latest_metric: MetricResponse | None
    recent_metrics: list[MetricResponse]
    recent_alerts: list[AlertResponse]
    recent_recovery_actions: list[RecoveryActionResponse]
    health: DeviceHealthResponse
    counts: DeviceSummaryCounts