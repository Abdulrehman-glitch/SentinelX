"""Tests for the Sprint 7 Phase 6 data retention dry-run report."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.data_retention_prune import prune
from app.db.data_retention_report import RETENTION_RULES, generate_report
from app.models.security_log import SecurityLog


def test_report_covers_every_retention_rule():
    rows = generate_report()
    labels = {row["table"] for row in rows}
    assert labels == {rule.label for rule in RETENTION_RULES}
    for row in rows:
        assert row["total_rows"] >= 0
        assert row["rows_past_retention"] >= 0
        assert row["rows_past_retention"] <= row["total_rows"]


def test_report_counts_a_stale_row_without_deleting_it(db):
    stale_created_at = datetime.now(timezone.utc) - timedelta(days=800)  # past every rule's cutoff
    stale_log = SecurityLog(
        id=uuid.uuid4(),
        event_type="test_retention_probe",
        severity="info",
        actor_type="system",
        action="test",
        status="success",
        message="probe row for the retention report test",
        created_at=stale_created_at,
    )
    db.add(stale_log)
    db.commit()

    before = next(row for row in generate_report() if row["table"] == "security_logs")
    assert before["rows_past_retention"] >= 1

    # Read-only: the row must still be there after generating the report.
    still_present = db.get(SecurityLog, stale_log.id)
    assert still_present is not None
    assert still_present.created_at == stale_created_at


# --- retention enforcement (prune) ---

def _probe(db, *, age_days: int) -> SecurityLog:
    row = SecurityLog(
        id=uuid.uuid4(),
        event_type="test_retention_prune_probe",
        severity="info",
        actor_type="system",
        action="test",
        status="success",
        message="probe row for the retention prune test",
        created_at=datetime.now(timezone.utc) - timedelta(days=age_days),
    )
    db.add(row)
    db.commit()
    return row


def test_prune_dry_run_deletes_nothing(db):
    """The default must be safe: report the damage, do none of it."""
    stale = _probe(db, age_days=800)

    result = next(
        row for row in prune(only="security_logs") if row["table"] == "security_logs"
    )

    assert result["would_delete"] >= 1
    assert result["deleted"] == 0

    db.expire_all()
    assert db.get(SecurityLog, stale.id) is not None


def test_prune_execute_removes_only_rows_past_the_cutoff(db):
    stale_id = _probe(db, age_days=800).id  # security_logs retention is 730 days
    fresh_id = _probe(db, age_days=1).id

    result = next(
        row
        for row in prune(execute=True, only="security_logs")
        if row["table"] == "security_logs"
    )
    assert result["deleted"] >= 1

    # prune() ran in its own session; drop this one's identity map so the
    # assertions below hit the database rather than stale in-memory objects.
    db.expunge_all()

    def _exists(row_id) -> bool:
        return db.query(SecurityLog).filter(SecurityLog.id == row_id).first() is not None

    assert not _exists(stale_id), "row past its retention should be gone"
    assert _exists(fresh_id), "row inside retention must survive"


def test_prune_refuses_an_unknown_table():
    with pytest.raises(SystemExit):
        prune(only="not_a_real_table")
