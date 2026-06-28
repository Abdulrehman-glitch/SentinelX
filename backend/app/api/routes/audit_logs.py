from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    limit: int = 100,
    severity: str | None = None,
    action: str | None = None,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    safe_limit = min(max(limit, 1), 500)

    conditions = []

    if severity:
        conditions.append(AuditLog.severity == severity.lower())

    if action:
        conditions.append(AuditLog.action == action)

    statement = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(safe_limit)

    if conditions:
        statement = (
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .limit(safe_limit)
        )

    return list(db.scalars(statement))