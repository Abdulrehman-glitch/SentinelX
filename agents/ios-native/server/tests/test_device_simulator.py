from __future__ import annotations

import json

from server.tools.device_simulator import (
    SimulatorState,
    event_for_batch,
    make_batch,
    registration_payload,
    websocket_url,
)
from server.tools.simulator_payloads import PayloadGenerator


def test_state_roundtrip(tmp_path) -> None:
    path = tmp_path / "state.json"
    state = SimulatorState(
        device_id="dev_01JZIOS001",
        device_secret="secret",
        vendor_identifier="vendor-1",
    )

    state.save(path)

    assert json.loads(path.read_text(encoding="utf-8"))["device_id"] == state.device_id
    assert SimulatorState.load(path) == state


def test_registration_payload_matches_contract() -> None:
    payload = registration_payload("vendor-123")

    assert payload["platform"] == "ios"
    assert payload["vendor_identifier"] == "vendor-123"
    assert payload["timezone"] == "Europe/London"
    assert payload["locale"] == "en_GB"


def test_batch_events_omit_device_id() -> None:
    event = PayloadGenerator(seed=1).make_event("battery", "dev_01JZIOS001", 1)
    batch = make_batch("dev_01JZIOS001", [event])

    assert batch["device_id"] == "dev_01JZIOS001"
    assert "batch_id" in batch
    assert "sent_at" in batch
    assert "device_id" not in batch["events"][0]
    assert event_for_batch(event)["event_id"] == event["event_id"]


def test_websocket_url_is_derived_from_api_base() -> None:
    assert websocket_url("http://127.0.0.1:8100/api/v1/mobile", "dev_1") == (
        "ws://127.0.0.1:8100/api/v1/mobile/ws/dev_1"
    )
    assert websocket_url("https://example.test/api/v1/mobile/", "dev_2") == (
        "wss://example.test/api/v1/mobile/ws/dev_2"
    )
