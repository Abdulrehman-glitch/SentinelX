"""Tests for the Sprint 7 Phase 6 data retention dry-run report."""

import uuid
from datetime import datetime, timedelta, timezone

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
