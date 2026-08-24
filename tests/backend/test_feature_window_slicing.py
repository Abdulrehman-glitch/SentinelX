"""The feature-window builder reads one span and slices it, rather than
issuing a query per window. These tests pin the behaviour that rewrite had to
preserve: window boundaries, gap handling, idempotence, and the bound on how
much backlog a single call will chew through.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from app.models.device import Device
from app.models.system_metric import SystemMetric
from app.models.telemetry_feature_window import TelemetryFeatureWindow
from app.services import feature_window_service as fws

CLASS = "laptop_windows_v1"


def _device(db, org):
    device = Device(
        organization_id=org.id,
        hostname=f"fw-host-{uuid.uuid4().hex[:8]}",
        device_type="desktop",
        status="online",
    )
    db.add(device)
    db.flush()
    return device


def _samples(db, org, device, start, count, *, step_seconds=60):
    for index in range(count):
        db.add(
            SystemMetric(
                organization_id=org.id,
                device_id=device.id,
                cpu_percent=20.0 + (index % 10),
                memory_percent=40.0,
                disk_percent=55.0,
                recorded_at=start + timedelta(seconds=index * step_seconds),
            )
        )
    db.flush()


def _aligned_start(hours_ago):
    now = datetime.now(timezone.utc)
    floored = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
    return floored - timedelta(hours=hours_ago)


class TestSlicing:
    def test_windows_are_thirty_minutes_and_aligned(self, db, org):
        device = _device(db, org)
        _samples(db, org, device, _aligned_start(3), 90)  # 90 one-minute samples
        db.commit()

        windows = fws.build_pending_windows(db, device, CLASS)
        db.commit()

        assert len(windows) == 3
        for window in windows:
            assert window.window_end - window.window_start == timedelta(minutes=30)
            assert window.window_start.minute in (0, 30)
        assert [w.sample_count for w in windows] == [30, 30, 30]

    def test_a_gap_produces_no_window_for_the_empty_span(self, db, org):
        device = _device(db, org)
        start = _aligned_start(4)
        _samples(db, org, device, start, 30)                          # first half hour
        _samples(db, org, device, start + timedelta(minutes=90), 30)  # skips two windows
        db.commit()

        windows = fws.build_pending_windows(db, device, CLASS)
        db.commit()

        assert len(windows) == 2
        assert windows[1].window_start - windows[0].window_start == timedelta(minutes=90)

    def test_incomplete_trailing_window_is_not_built(self, db, org):
        device = _device(db, org)
        now = datetime.now(timezone.utc)
        # Starts 20 minutes ago: the window it falls in has not closed yet.
        _samples(db, org, device, now - timedelta(minutes=20), 10)
        db.commit()

        windows = fws.build_pending_windows(db, device, CLASS)
        db.commit()
        assert all(w.window_end <= now for w in windows)

    def test_rerunning_creates_nothing_new(self, db, org):
        device = _device(db, org)
        _samples(db, org, device, _aligned_start(2), 60)
        db.commit()

        first = fws.build_pending_windows(db, device, CLASS)
        db.commit()
        second = fws.build_pending_windows(db, device, CLASS)
        db.commit()

        assert len(first) == 2
        assert second == []
        stored = (
            db.query(TelemetryFeatureWindow)
            .filter(TelemetryFeatureWindow.device_id == device.id)
            .count()
        )
        assert stored == 2

    def test_a_device_with_no_samples_produces_nothing(self, db, org):
        device = _device(db, org)
        db.commit()
        assert fws.build_pending_windows(db, device, CLASS) == []

    def test_backlog_is_bounded_per_call(self, db, org, monkeypatch):
        device = _device(db, org)
        monkeypatch.setattr(fws, "MAX_WINDOWS_PER_CALL", 3)
        _samples(db, org, device, _aligned_start(5), 300, step_seconds=60)
        db.commit()

        windows = fws.build_pending_windows(db, device, CLASS)
        db.commit()
        assert len(windows) == 3


class TestQueryEconomy:
    def test_a_long_backlog_costs_a_constant_number_of_round_trips(self, db, org):
        """Ten windows must not cost ten queries.

        This is the regression the rewrite exists to prevent: the old builder
        issued one SELECT per window, so an agent that had been offline
        overnight turned into dozens of round trips per pipeline run.
        """
        device = _device(db, org)
        _samples(db, org, device, _aligned_start(6), 330, step_seconds=60)
        db.commit()

        # Touch the device before counting: the commit above expired it, and a
        # lazy reload would otherwise be counted as pipeline work.
        assert device.hostname

        statements: list[str] = []
        engine = db.get_bind()

        def _record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", _record)
        try:
            windows = fws.build_pending_windows(db, device, CLASS)
            db.flush()
        finally:
            event.remove(engine, "before_cursor_execute", _record)
        db.commit()

        assert len(windows) >= 10
        selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
        # Cursor lookup + sample stream. Never proportional to window count.
        assert len(selects) <= 3, selects
