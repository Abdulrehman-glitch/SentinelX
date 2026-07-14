import uuid
from datetime import timedelta

from app.timeutil import to_iso, utc_now
from tests.conftest import make_event


def test_single_event_accepted(client, device):
    device_id, _, headers = device
    response = client.post("/api/v1/mobile/telemetry",
                           json=make_event(device_id), headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["duplicate"] is False


def test_duplicate_event_id_is_idempotent(client, device):
    device_id, _, headers = device
    event = make_event(device_id)
    first = client.post("/api/v1/mobile/telemetry", json=event, headers=headers).json()
    second = client.post("/api/v1/mobile/telemetry", json=event, headers=headers).json()
    assert first["duplicate"] is False
    assert second["accepted"] is True and second["duplicate"] is True

    stored = client.get(f"/api/v1/mobile/devices/{device_id}/telemetry").json()
    assert stored["total"] == 1


def test_device_id_mismatch_rejected(client, device):
    device_id, _, headers = device
    event = make_event("dev_someoneelse")
    response = client.post("/api/v1/mobile/telemetry", json=event, headers=headers)
    assert response.status_code == 403


def test_invalid_battery_level_rejected(client, device):
    device_id, _, headers = device
    event = make_event(device_id, payload={"level": 400})
    response = client.post("/api/v1/mobile/telemetry", json=event, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_category_rejected(client, device):
    device_id, _, headers = device
    event = make_event(device_id, category="teleportation")
    response = client.post("/api/v1/mobile/telemetry", json=event, headers=headers)
    assert response.status_code == 422


def test_stale_and_future_events_are_rejected(client, device):
    device_id, _, headers = device
    stale = make_event(device_id, timestamp=to_iso(utc_now() - timedelta(hours=25)))
    future = make_event(device_id, timestamp=to_iso(utc_now() + timedelta(minutes=6)))

    stale_response = client.post("/api/v1/mobile/telemetry", json=stale, headers=headers)
    future_response = client.post("/api/v1/mobile/telemetry", json=future, headers=headers)

    assert stale_response.status_code == 422
    assert "older than 24 hours" in stale_response.json()["error"]["message"]
    assert future_response.status_code == 422
    assert "more than 5 minutes in the future" in future_response.json()["error"]["message"]


def _batch(device_id, events):
    return {
        "device_id": device_id,
        "batch_id": str(uuid.uuid4()),
        "sent_at": events[0]["timestamp"],
        "events": [{k: v for k, v in event.items() if k != "device_id"} for event in events],
    }


def test_batch_rejects_per_event_not_whole_batch(client, device):
    device_id, _, headers = device
    good = make_event(device_id)
    bad = make_event(device_id, payload={"level": -5})
    response = client.post("/api/v1/mobile/batch",
                           json=_batch(device_id, [good, bad]), headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 1
    assert body["rejected_events"][0]["event_id"] == good["event_id"] or \
           body["rejected_events"][0]["event_id"] == bad["event_id"]
    assert "level" in body["rejected_events"][0]["reason"]


def test_batch_duplicates_stored_once(client, device):
    device_id, _, headers = device
    event = make_event(device_id, category="thermal", payload={"state": "nominal"})
    batch = _batch(device_id, [event, event])
    response = client.post("/api/v1/mobile/batch", json=batch, headers=headers)
    assert response.status_code == 200
    assert response.json()["accepted_count"] == 2  # duplicate counts as accepted

    stored = client.get(f"/api/v1/mobile/devices/{device_id}/telemetry",
                        params={"category": "thermal"}).json()
    assert stored["total"] == 1


def test_batch_rejects_stale_and_future_events_individually(client, device):
    device_id, _, headers = device
    fresh = make_event(device_id)
    stale = make_event(device_id, timestamp=to_iso(utc_now() - timedelta(hours=25)))
    future = make_event(device_id, timestamp=to_iso(utc_now() + timedelta(minutes=6)))

    response = client.post("/api/v1/mobile/batch",
                           json=_batch(device_id, [fresh, stale, future]), headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 2
    reasons = {item["event_id"]: item["reason"] for item in body["rejected_events"]}
    assert "older than 24 hours" in reasons[stale["event_id"]]
    assert "more than 5 minutes in the future" in reasons[future["event_id"]]

    stored = client.get(f"/api/v1/mobile/devices/{device_id}/telemetry").json()
    assert stored["total"] == 1
