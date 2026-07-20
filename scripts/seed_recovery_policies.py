"""
Seeds the global default recovery_policies rows (organization_id IS NULL —
applies to every org unless overridden) for the Sprint 3 allowlisted actions.
Idempotent: safe to re-run, skips any (organization_id IS NULL, action_type)
pair that already exists.

Usage (from the repo root, with backend/.venv active):
    python scripts/seed_recovery_policies.py
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.recovery_policy import RecoveryPolicy  # noqa: E402

# action_type -> (risk_level, approval_mode)
# Per the approved Sprint 3 plan: low-risk actions auto-approve, medium-risk
# actions require explicit human approval. No high-risk actions ship in v1.
LAPTOP_POLICIES = {
    "collect_diagnostics": ("low", "auto"),
    "rotate_agent_logs": ("low", "auto"),
    "retry_telemetry_sync": ("low", "auto"),
    "repair_agent_queue": ("low", "auto"),
    "restart_sentinelx_agent": ("medium", "manual"),
    "restart_allowlisted_service": ("medium", "manual"),
}

ANDROID_POLICIES = {
    "collect_diagnostics": ("low", "auto"),
    "retry_telemetry_sync": ("low", "auto"),
    "reset_api_connection": ("low", "auto"),
    "repair_local_database": ("low", "auto"),
    "reschedule_sync_workers": ("low", "auto"),
    "restart_monitoring_service": ("medium", "manual"),
    # Sprint 4-6, Stage 4: re-tiered from medium/manual to low/auto — these
    # are monitoring-mode toggles, not restarts, so they're eligible for
    # verified low-risk self-healing. Restart actions above stay manual.
    "enter_safe_monitoring_mode": ("low", "auto"),
    "restore_normal_monitoring_mode": ("low", "auto"),
}


def seed() -> tuple[int, int, int]:
    """Idempotent and self-healing: inserts missing global policy rows, and
    corrects the risk_level/approval_mode of existing rows that drifted from
    the intended values above (e.g. after a re-tier like Stage 4's)."""
    db = SessionLocal()
    created = 0
    updated = 0
    unchanged = 0
    try:
        for action_type, (risk_level, approval_mode) in {**LAPTOP_POLICIES, **ANDROID_POLICIES}.items():
            existing = db.scalar(
                select(RecoveryPolicy).where(
                    RecoveryPolicy.organization_id.is_(None),
                    RecoveryPolicy.action_type == action_type,
                )
            )
            if existing is not None:
                if existing.risk_level != risk_level or existing.approval_mode != approval_mode:
                    existing.risk_level = risk_level
                    existing.approval_mode = approval_mode
                    updated += 1
                else:
                    unchanged += 1
                continue

            db.add(
                RecoveryPolicy(
                    id=uuid.uuid4(),
                    organization_id=None,
                    device_class=None,
                    action_type=action_type,
                    trigger_conditions=None,
                    risk_level=risk_level,
                    approval_mode=approval_mode,
                    cooldown_seconds=300,
                    daily_execution_limit=5,
                    verification_window_seconds=300,
                    enabled=True,
                )
            )
            created += 1

        db.commit()
    finally:
        db.close()

    return created, updated, unchanged


def main() -> None:
    created, updated, unchanged = seed()
    print(
        f"Seeded {created} new, updated {updated} drifted, left {unchanged} unchanged "
        "global recovery_policies row(s)."
    )


if __name__ == "__main__":
    main()
