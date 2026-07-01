import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    device_id: uuid.UUID
    alert_type: str
    severity: str
    message: str
    resolved: bool
    created_at: datetime
    resolved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
