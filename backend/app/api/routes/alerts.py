import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertResponse

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    unresolved_only: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[Alert]:
    """
    Returns recent alerts.

    Use unresolved_only=true to show only active dashboard alerts.
    """

    safe_limit = min(max(limit, 1), 200)

    statement = select(Alert).order_by(Alert.created_at.desc()).limit(safe_limit)

    if unresolved_only:
        statement = (
            select(Alert)
            .where(Alert.resolved.is_(False))
            .order_by(Alert.created_at.desc())
            .limit(safe_limit)
        )

    return list(db.scalars(statement))


@router.patch("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)) -> Alert:
    """
    Marks an alert as resolved.
    """

    alert = db.get(Alert, alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    alert.resolved = True
    alert.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)

    return alert