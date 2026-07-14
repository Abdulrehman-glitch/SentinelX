from __future__ import annotations

import asyncio
from dataclasses import dataclass

from server.tools import demo
from server.tools.device_simulator import SendStats, SimulatorState


def test_health_url_points_to_root_healthcheck() -> None:
    assert demo.health_url("http://127.0.0.1:8100/api/v1/mobile") == "http://127.0.0.1:8100/healthz"


@dataclass
class FakeSimulator:
    api_base: str
    state_file: object
    seed: int | None = None
    start_time: object | None = None

    def load_state(self) -> SimulatorState:
        return SimulatorState("dev_demo", "secret", "vendor")

    async def register(self, vendor_identifier: str | None = None) -> SimulatorState:
        return SimulatorState("dev_demo", "secret", vendor_identifier or "vendor")

    async def run_websocket(self, **kwargs) -> SendStats:
        return SendStats(events_sent=3, reconnects=1)


def test_demo_runner_verifies_stored_events(monkeypatch, tmp_path) -> None:
    totals = iter([10, 13])
    alerts = iter([2, 4])

    async def fake_total(api_base: str, device_id: str) -> int:
        return next(totals)

    async def fake_alerts(api_base: str, device_id: str) -> int:
        return next(alerts)

    monkeypatch.setattr(demo, "telemetry_total", fake_total)
    monkeypatch.setattr(demo, "alert_count", fake_alerts)

    result = asyncio.run(demo.DemoRunner(
        api_base="http://testserver/api/v1/mobile",
        state_file=tmp_path / "state.json",
        simulator_cls=FakeSimulator,
    ).run(duration_seconds=3))

    assert result.device_id == "dev_demo"
    assert result.events_sent == 3
    assert result.stored_events == 3
    assert result.alerts_fired == 2
    assert result.reconnects == 1


def test_demo_runner_fails_when_events_do_not_land(monkeypatch, tmp_path) -> None:
    totals = iter([10, 11])

    async def fake_total(api_base: str, device_id: str) -> int:
        return next(totals)

    async def fake_alerts(api_base: str, device_id: str) -> int:
        return 0

    monkeypatch.setattr(demo, "telemetry_total", fake_total)
    monkeypatch.setattr(demo, "alert_count", fake_alerts)

    try:
        asyncio.run(demo.DemoRunner(
            api_base="http://testserver/api/v1/mobile",
            state_file=tmp_path / "state.json",
            simulator_cls=FakeSimulator,
        ).run(duration_seconds=3))
    except RuntimeError as exc:
        assert "stored 1 events but sent 3" in str(exc)
    else:
        raise AssertionError("expected demo runner to fail")
