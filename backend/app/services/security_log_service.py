import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.security_log import SecurityLog


def create_security_log(
    db: Session,
    *,
    event_type: str,
    action: str,
    message: str,
    severity: str = "info",
    actor_type: str = "system",
    actor_id: str | None = None,
    ip_address: str | None = None,
    organization_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    status: str = "success",
    metadata: dict[str, Any] | None = None,
) -> SecurityLog:
    log = SecurityLog(
        event_type=event_type,
        severity=severity,
        actor_type=actor_type,
        actor_id=actor_id,
        ip_address=ip_address,
        organization_id=organization_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        message=message,
        metadata_json=metadata,
    )
    db.add(log)
    return log
