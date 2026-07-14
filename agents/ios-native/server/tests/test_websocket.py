import uuid
from contextlib import contextmanager

from tests.conftest import make_event


@contextmanager
def _ws_session(client, device):
    """Authenticated WS connection; yields (ws, device_id) past auth.accepted."""
    device_id, secret, _ = device
    tokens = client.post("/api/v1/mobile/login", json={
        "device_id": device_id, "device_secret": secret}).json()
    with client.websocket_connect(f"/api/v1/mobile/ws/{device_id}") as ws:
        ws.send_json({"type": "auth", "access_token": tokens["access_token"],
                      "device_id": device_id})
        accepted = ws.receive_json()
        assert accepted["type"] == "auth.accepted"
        yield ws, device_id


def test_first_message_auth_accepted(client, device):
    device_id, secret, _ = device
    tokens = client.post("/api/v1/mobile/login", json={
        "device_id": device_id, "device_secret": secret}).json()
    with client.websocket_connect(f"/api/v1/mobile/ws/{device_id}") as ws:
        ws.send_json({"type": "auth", "access_token": tokens["access_token"],
                      "device_id": device_id})
        reply = ws.receive_json()
        assert reply["type"] == "auth.accepted"
        assert reply["device_id"] == device_id
        assert "server_time" in reply


def test_bad_token_rejected(client, device):
    device_id, _, _ = device
    with client.websocket_connect(f"/api/v1/mobile/ws/{device_id}") as ws:
        ws.send_json({"type": "auth", "access_token": "garbage", "device_id": device_id})
        reply = ws.receive_json()
        assert reply["type"] == "auth.rejected"
        assert reply["reason"] == "INVALID_TOKEN"


def test_heartbeat_ack(client, device):
    with _ws_session(client, device) as (ws, device_id):
        ws.send_json({"type": "heartbeat", "device_id": device_id,
                      "timestamp": "2026-07-06T00:00:00Z"})
        reply = ws.receive_json()
        assert reply["type"] == "heartbeat.ack"
        assert "server_time" in reply


def test_ws_telemetry_event_is_stored(client, device):
    with _ws_session(client, device) as (ws, device_id):
        event = make_event(device_id, category="network",
                           payload={"reachable": True, "interface": "wifi"})
        ws.send_json({"type": "telemetry.event", "event": event})
        assert ws.receive_json()["type"] == "telemetry.ack"
        # heartbeat round-trip guarantees the event was processed first
        ws.send_json({"type": "heartbeat", "device_id": device_id,
                      "timestamp": event["timestamp"]})
        assert ws.receive_json()["type"] == "heartbeat.ack"

    stored = client.get(f"/api/v1/mobile/devices/{device_id}/telemetry",
                        params={"category": "network"}).json()
    assert stored["total"] == 1


def test_ws_batch_and_invalid_event_error(client, device):
    with _ws_session(client, device) as (ws, device_id):
        good = make_event(device_id, category="storage",
                          payload={"total_bytes": 128_000_000_000, "free_bytes": 42_000_000_000})
        bad = make_event(device_id, payload={"level": 999})
        ws.send_json({"type": "telemetry.batch", "events": [good, bad],
                      "batch_id": str(uuid.uuid4())})
        error = ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "VALIDATION_ERROR"
        ack = ws.receive_json()
        assert ack["type"] == "telemetry.ack"
        assert ack["event_ids"] == [good["event_id"]]

    stored = client.get(f"/api/v1/mobile/devices/{device_id}/telemetry",
                        params={"category": "storage"}).json()
    assert stored["total"] == 1


def test_ws_telemetry_event_ack_lists_stored_event(client, device):
    with _ws_session(client, device) as (ws, device_id):
        event = make_event(device_id, category="battery",
                           payload={"level": 84, "charging": False, "low_power_mode": False})
        ws.send_json({"type": "telemetry.event", "event": event})
        ack = ws.receive_json()

    assert ack["type"] == "telemetry.ack"
    assert ack["event_ids"] == [event["event_id"]]
    assert "server_time" in ack


def test_ws_batch_ack_omits_rejected_events(client, device):
    with _ws_session(client, device) as (ws, device_id):
        good_one = make_event(device_id, category="network",
                              payload={"reachable": True, "interface": "wifi"})
        bad = make_event(device_id, category="storage",
                         payload={"total_bytes": 10, "free_bytes": 11})
        good_two = make_event(device_id, category="thermal", payload={"state": "nominal"})
        ws.send_json({"type": "telemetry.batch", "events": [good_one, bad, good_two],
                      "batch_id": str(uuid.uuid4())})
        error = ws.receive_json()
        ack = ws.receive_json()

    assert error["type"] == "error"
    assert error["event_id"] == bad["event_id"]
    assert ack["type"] == "telemetry.ack"
    assert ack["event_ids"] == [good_one["event_id"], good_two["event_id"]]


def test_ws_duplicate_resend_is_acked(client, device):
    with _ws_session(client, device) as (ws, device_id):
        event = make_event(device_id, category="battery",
                           payload={"level": 84, "charging": False, "low_power_mode": False})
        ws.send_json({"type": "telemetry.event", "event": event})
        first_ack = ws.receive_json()
        ws.send_json({"type": "telemetry.event", "event": event})
        duplicate_ack = ws.receive_json()

    assert first_ack["event_ids"] == [event["event_id"]]
    assert duplicate_ack["type"] == "telemetry.ack"
    assert duplicate_ack["event_ids"] == [event["event_id"]]
