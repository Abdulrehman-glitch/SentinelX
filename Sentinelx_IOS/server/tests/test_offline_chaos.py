"""C9 offline chaos validation: no loss, no duplicates across offline gaps.

Two layers: an integration test that drives the real server through three
connect/disconnect cycles with buffered and re-sent events (the server-side
mirror of the iOS airplane-mode acceptance), and unit tests for the
OfflineChaosRunner's invariant checking.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from server.tools import demo
from server.tools.demo import OfflineChaosRunner
from server.tools.device_simulator import SimulatorState
from tests.conftest import make_event


CATEGORY_PAYLOADS = {
    "battery": {"level": 61, "charging": False, "low_power_mode": False},
    "network": {"reachable": True, "interface": "wifi"},
    "thermal": {"state": "nominal"},
}


def _cycle_events(device_id: str, count: int) -> list[dict]:
    categories = list(CATEGORY_PAYLOADS)
    return [
        make_event(
            device_id,
            category=categories[index % len(categories)],
            payload=CATEGORY_PAYLOADS[categories[index % len(categories)]],
        )
        for index in range(count)
    ]


def _ws_drain(client, device_id: str, token: str, events: list[dict]) -> set[str]:
    """One connect/auth/send/ack/disconnect round; returns acked event ids."""
    acked: set[str] = set()
    with client.websocket_connect(f"/api/v1/mobile/ws/{device_id}") as ws:
        ws.send_json({"type": "auth", "access_token": token, "device_id": device_id})
        assert ws.receive_json()["type"] == "auth.accepted"
        for event in events:
            ws.send_json({"type": "telemetry.event", "event": event})
        # One ack per event, in order (alerts may interleave).
        while len(acked) < len(events):
            message = ws.receive_json()
            if message["type"] == "telemetry.ack":
                acked.update(str(event_id) for event_id in message["event_ids"])
    return acked


def test_no_loss_no_dupes_across_three_offline_cycles(client, device):
    device_id, secret, headers = device
    tokens = client.post(
        "/api/v1/mobile/login",
        json={"device_id": device_id, "device_secret": secret},
    ).json()
    token = tokens["access_token"]

    unique_ids: set[str] = set()
    previous_batch: list[dict] = []

    for _ in range(3):
        # Offline gap: events pile up locally...
        buffered = _cycle_events(device_id, 4)
        unique_ids.update(event["event_id"] for event in buffered)
        # ...reconnect re-sends the previous cycle's events too (the iOS
        # queue requeues in_flight on disconnect), then the new ones.
        acked = _ws_drain(client, device_id, token, previous_batch + buffered)
        assert {event["event_id"] for event in buffered} <= acked  # dupes acked too
        previous_batch = buffered

    stored = client.get(
        f"/api/v1/mobile/devices/{device_id}/telemetry", params={"limit": 1}
    ).json()["total"]
    assert stored == len(unique_ids), "stored events must equal unique sent events"


def test_rest_replay_after_chaos_does_not_change_totals(client, device):
    device_id, secret, headers = device
    tokens = client.post(
        "/api/v1/mobile/login",
        json={"device_id": device_id, "device_secret": secret},
    ).json()

    events = _cycle_events(device_id, 5)
    _ws_drain(client, device_id, tokens["access_token"], events)

    before = client.get(
        f"/api/v1/mobile/devices/{device_id}/telemetry", params={"limit": 1}
    ).json()["total"]

    # Replay the identical events as a REST batch — pure duplicates.
    import uuid

    from app.timeutil import now_iso

    response = client.post(
        "/api/v1/mobile/batch",
        headers=headers,
        json={
            "device_id": device_id,
            "batch_id": str(uuid.uuid4()),
            "sent_at": now_iso(),
            "events": [
                {key: value for key, value in event.items() if key != "device_id"}
                for event in events
            ],
        },
    )
    assert response.status_code == 200

    after = client.get(
        f"/api/v1/mobile/devices/{device_id}/telemetry", params={"limit": 1}
    ).json()["total"]
    assert after == before, "replayed duplicates must not be stored again"


# --- OfflineChaosRunner unit tests (no network; drains are faked) ---


def _make_runner(tmp_path: Path, **kwargs) -> OfflineChaosRunner:
    state_file = tmp_path / "state.json"
    SimulatorState("dev_chaos", "secret", "vendor").save(state_file)
    return OfflineChaosRunner(
        api_base="http://testserver/api/v1/mobile",
        state_file=state_file,
        interval=0.05,
        offline_window=0.01,
        cycles=3,
        **kwargs,
    )


def _patch_common(monkeypatch, runner: OfflineChaosRunner, totals: list[int]) -> None:
    totals_iter = iter(totals)

    async def fake_total(api_base: str, device_id: str) -> int:
        return next(totals_iter)

    async def fake_replay(simulator, state, delivered) -> int:
        return len(delivered[:50])

    monkeypatch.setattr(demo, "telemetry_total", fake_total)
    monkeypatch.setattr(runner, "_replay_duplicates", fake_replay)


def test_chaos_runner_passes_when_all_events_land(monkeypatch, tmp_path):
    runner = _make_runner(tmp_path)
    # 1 event buffered per cycle (offline_window/interval < 1) → 3 unique.
    _patch_common(monkeypatch, runner, totals=[10, 13])

    async def fake_drain(simulator, state, events):
        return len(events), {event["event_id"] for event in events}

    monkeypatch.setattr(runner, "_drain_over_websocket", fake_drain)

    result = asyncio.run(runner.run())
    assert result.unique_events == 3
    assert result.sends_attempted == 3
    assert result.stored_events == 3
    assert result.duplicates_replayed == 3


def test_chaos_runner_counts_resends_of_unacked_events(monkeypatch, tmp_path):
    runner = _make_runner(tmp_path)
    _patch_common(monkeypatch, runner, totals=[0, 3])
    drains = {"count": 0}

    async def flaky_drain(simulator, state, events):
        drains["count"] += 1
        if drains["count"] == 1:
            return len(events), set()  # sent but no acks — lost connection
        return len(events), {event["event_id"] for event in events}

    monkeypatch.setattr(runner, "_drain_over_websocket", flaky_drain)

    result = asyncio.run(runner.run())
    assert result.unique_events == 3
    assert result.sends_attempted > result.unique_events  # re-sends happened
    assert result.stored_events == 3


def test_chaos_runner_fails_on_event_loss(monkeypatch, tmp_path):
    runner = _make_runner(tmp_path)
    _patch_common(monkeypatch, runner, totals=[10, 12])  # only 2 of 3 landed

    async def fake_drain(simulator, state, events):
        return len(events), {event["event_id"] for event in events}

    monkeypatch.setattr(runner, "_drain_over_websocket", fake_drain)

    with pytest.raises(RuntimeError, match="chaos invariant violated"):
        asyncio.run(runner.run())


def test_chaos_runner_fails_when_events_cannot_be_delivered(monkeypatch, tmp_path):
    runner = _make_runner(tmp_path)
    _patch_common(monkeypatch, runner, totals=[0, 0])

    async def dead_drain(simulator, state, events):
        return len(events), set()  # nothing ever acked

    monkeypatch.setattr(runner, "_drain_over_websocket", dead_drain)

    with pytest.raises(RuntimeError, match="could not deliver"):
        asyncio.run(runner.run())
