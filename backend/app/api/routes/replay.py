from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models.replay_run import ReplayRun
from app.models.user import User
from app.schemas.replay import ReplayDecisionResponse, ReplayRunRequest, ReplayRunResponse
from app.services import replay_service

router = APIRouter(prefix="/replay", tags=["Historical Replay"])


@router.post("/run", response_model=ReplayRunResponse)
def run_historical_replay(
    payload: ReplayRunRequest,
    current_user: User = Depends(require_role(["admin", "owner", "engineer", "platform_admin"])),
    db: Session = Depends(get_db),
) -> ReplayRunResponse:
    """
    Read-only replay: reuses stored feature windows, never creates an
    Alert/Incident/RecoveryCommand, and never writes to
    AnomalyPrediction/HybridDecision. Only an audit-only ReplayRun summary
    row is persisted.
    """
    if not get_settings().historical_replay_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Historical replay is disabled.")

    result = replay_service.run_replay(
        db,
        device_class=payload.device_class,
        period_start=payload.period_start,
        period_end=payload.period_end,
        model_version=payload.model_version,
    )

    export = None
    if payload.export_format == "json":
        export = replay_service.export_json(result)
    elif payload.export_format == "markdown":
        export = replay_service.export_markdown(result)

    run_log = ReplayRun(
        requested_by=current_user.id,
        device_class=result.device_class,
        model_version=result.model_version,
        scoring_policy_version=result.scoring_policy_version,
        period_start=result.period_start,
        period_end=result.period_end,
        windows_considered=result.windows_considered,
        decisions_count=len(result.decisions),
    )
    db.add(run_log)
    db.commit()
    db.refresh(run_log)

    return ReplayRunResponse(
        replay_run_id=run_log.id,
        device_class=result.device_class,
        scoring_policy_version=result.scoring_policy_version,
        model_version=result.model_version,
        period_start=result.period_start,
        period_end=result.period_end,
        windows_considered=result.windows_considered,
        decisions=[ReplayDecisionResponse(**asdict(d)) for d in result.decisions],
        skipped=result.skipped,
        export=export,
    )
