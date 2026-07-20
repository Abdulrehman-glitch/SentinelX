"""Sprint 4-6 Stage 3 coverage: historical replay reproducibility and zero
side-effects on production tables (never creates alerts, incidents,
recovery commands, or overwrites anomaly_predictions/hybrid_decisions)."""

import json
import uuid
from datetime import datetime, timedelta, timezone

from app.ml.feature_schemas import LAPTOP_WINDOWS_V1
from app.models.alert import Alert
from app.models.anomaly_prediction import AnomalyPrediction
from app.models.device import Device
from app.models.hybrid_decision import HybridDecision
from app.models.incident import Incident
from app.models.organization import Organization
from app.models.recovery_command import RecoveryCommand
from app.models.system_metric import SystemMetric
from app.services import feature_window_service, replay_service


def _make_laptop_device(db, org: Organization) -> Device:
    device = Device(
        hostname=f"laptop-{uuid.uuid4().hex[:8]}",
        os_name="Windows 11 Pro",
        device_type="desktop",
        agent_type="python_desktop_agent",
        organization_id=org.id,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def _seed_history(db, device: Device, *, hours: int = 12, interval_minutes: int = 5) -> None:
    now = datetime.now(timezone.utc)
    count = int(hours * 60 / interval_minutes)
    start = now - timedelta(hours=hours)
    for i in range(count):
        db.add(
            SystemMetric(
                organization_id=device.organization_id,
                device_id=device.id,
                event_id=uuid.uuid4(),
                cpu_percent=40.0 + (i % 7),
                memory_percent=55.0 + (i % 5),
                disk_percent=65.0,
                recorded_at=start + timedelta(minutes=i * interval_minutes),
            )
        )
    db.commit()


class TestReplaySafety:
    def test_replay_never_creates_or_modifies_production_rows(self, db, org):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()
        assert len(windows) >= 6

        before_predictions = db.query(AnomalyPrediction).count()
        before_decisions = db.query(HybridDecision).count()
        before_alerts = db.query(Alert).count()
        before_incidents = db.query(Incident).count()
        before_commands = db.query(RecoveryCommand).count()

        result = replay_service.run_replay(
            db,
            device_class=LAPTOP_WINDOWS_V1,
            period_start=windows[0].window_start,
            period_end=windows[-1].window_end + timedelta(minutes=1),
        )
        db.commit()

        # Replay scopes by device_class + date range, not a single device
        # (per spec), so other laptop devices created by other tests in this
        # shared session may also fall in range — assert inclusion, not count.
        assert result.windows_considered >= len(windows)
        returned_window_ids = {d.feature_window_id for d in result.decisions}
        assert {str(w.id) for w in windows}.issubset(returned_window_ids)
        assert db.query(AnomalyPrediction).count() == before_predictions
        assert db.query(HybridDecision).count() == before_decisions
        assert db.query(Alert).count() == before_alerts
        assert db.query(Incident).count() == before_incidents
        assert db.query(RecoveryCommand).count() == before_commands

    def test_replay_is_reproducible_for_fixed_db_state(self, db, org):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()

        kwargs = dict(
            device_class=LAPTOP_WINDOWS_V1,
            period_start=windows[0].window_start,
            period_end=windows[-1].window_end + timedelta(minutes=1),
        )
        first = replay_service.run_replay(db, **kwargs)
        second = replay_service.run_replay(db, **kwargs)

        assert [d.detector_agreement for d in first.decisions] == [d.detector_agreement for d in second.decisions]
        assert [d.combined_severity for d in first.decisions] == [d.combined_severity for d in second.decisions]
        assert [d.baseline_score for d in first.decisions] == [d.baseline_score for d in second.decisions]

    def test_unknown_model_version_is_reported_as_skipped_not_an_error(self, db, org):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()

        result = replay_service.run_replay(
            db,
            device_class=LAPTOP_WINDOWS_V1,
            period_start=windows[0].window_start,
            period_end=windows[-1].window_end + timedelta(minutes=1),
            model_version="nonexistent-9.9.9",
        )
        assert "no_model_found_for_version:nonexistent-9.9.9" in result.skipped
        assert all(d.model_prediction is None for d in result.decisions)


class TestReplayExport:
    def test_export_json_and_markdown(self, db, org):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()

        result = replay_service.run_replay(
            db,
            device_class=LAPTOP_WINDOWS_V1,
            period_start=windows[0].window_start,
            period_end=windows[-1].window_end + timedelta(minutes=1),
        )

        parsed = json.loads(replay_service.export_json(result))
        assert parsed["device_class"] == LAPTOP_WINDOWS_V1
        assert len(parsed["decisions"]) == len(result.decisions)

        md = replay_service.export_markdown(result)
        assert "Historical Replay" in md
        assert LAPTOP_WINDOWS_V1 in md


class TestReplayApi:
    def test_replay_run_endpoint_works_and_exports(self, client, db, org, admin_headers):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()

        resp = client.post(
            "/api/v1/replay/run",
            json={
                "device_class": LAPTOP_WINDOWS_V1,
                "period_start": windows[0].window_start.isoformat(),
                "period_end": (windows[-1].window_end + timedelta(minutes=1)).isoformat(),
                "export_format": "markdown",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Replay scopes by device_class + date range, not a single device
        # (per spec), so other laptop devices created earlier in this shared
        # test session may also fall in range — assert inclusion, not count.
        assert body["windows_considered"] >= len(windows)
        returned_window_ids = {d["feature_window_id"] for d in body["decisions"]}
        assert {str(w.id) for w in windows}.issubset(returned_window_ids)
        assert body["export"] is not None
        assert "Historical Replay" in body["export"]

    def test_viewer_cannot_run_replay(self, client, db, org):
        from app.core.security import create_access_token, hash_password
        from app.models.user import User

        viewer = User(
            email=f"viewer-{uuid.uuid4().hex[:6]}@test.local",
            full_name="Viewer",
            password_hash=hash_password("x"),
            role="viewer",
            organization_id=org.id,
        )
        db.add(viewer)
        db.commit()
        viewer_headers = {"Authorization": f"Bearer {create_access_token(subject=str(viewer.id))}"}

        resp = client.post(
            "/api/v1/replay/run",
            json={
                "device_class": LAPTOP_WINDOWS_V1,
                "period_start": "2020-01-01T00:00:00Z",
                "period_end": "2020-01-02T00:00:00Z",
            },
            headers=viewer_headers,
        )
        assert resp.status_code == 403
