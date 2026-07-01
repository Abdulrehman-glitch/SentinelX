import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    *,
    organization_id: uuid.UUID | None = None,
    actor_type: str = "system",
    actor_id: str | None = None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    severity: str = "info",
    message: str,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Add a tenant-scoped business audit log row.

    This function intentionally does not commit. The route/service that performs
    the business action owns the transaction. Always pass organization_id for
    tenant-owned actions. Platform-wide actions may use None.
    """

    audit_log = AuditLog(
        organization_id=organization_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        severity=severity,
        message=message,
        metadata_json=metadata,
    )

    db.add(audit_log)
    return audit_log
