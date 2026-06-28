from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    *,
    actor_type: str = "system",
    actor_id: str | None = None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    severity: str = "info",
    message: str,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """
    Adds an audit log row to the current database transaction.

    This function does not commit. The route/service that performs the
    business action controls the transaction boundary.
    """

    audit_log = AuditLog(
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