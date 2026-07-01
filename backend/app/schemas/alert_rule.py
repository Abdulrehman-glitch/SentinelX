import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MetricType = Literal[
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "temperature_c",
    "humidity_percent",
    "pressure_hpa",
    "impact_detected",
]
RuleOperator = Literal[">", ">=", "<", "<=", "=="]
RuleSeverity = Literal["info", "warning", "critical"]


class AlertRuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    metric_type: MetricType
    operator: RuleOperator = ">="
    threshold: float = Field(..., ge=0, le=5000)
    severity: RuleSeverity = "warning"
    enabled: bool = True
    description: str | None = None
    cooldown_seconds: int = Field(default=300, ge=0, le=86400)
    device_id: uuid.UUID | None = None


class AlertRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    metric_type: MetricType | None = None
    operator: RuleOperator | None = None
    threshold: float | None = Field(default=None, ge=0, le=5000)
    severity: RuleSeverity | None = None
    enabled: bool | None = None
    description: str | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0, le=86400)


class AlertRuleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    device_id: uuid.UUID | None = None
    name: str
    metric_type: str
    operator: str
    threshold: float
    severity: str
    enabled: bool
    description: str | None
    cooldown_seconds: int
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
