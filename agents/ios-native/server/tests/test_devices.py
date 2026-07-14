from datetime import timedelta

from app.timeutil import to_iso, utc_now
from tests.conftest import make_event


def test_profile_roundtrip(client, device):
    device_id, _, headers = device
    profile = client.get("/api/v1/mobile/profile", headers=headers).json()
    assert profile["device_id"] == device_id
    assert profile["platform"] == "ios"

    update = client.patch("/api/v1/mobile/profile",
                          json={"device_name": "Renamed"}, headers=headers)
    assert update.status_code == 200
    assert client.get("/api/v1/mobile/profile", headers=headers).json()["device_name"] == "Renamed"


def test_device_summary_reflects_latest_snapshots(client, device):
    device_id, _, headers = device
    for payload, category in [
        ({"level": 42, "charging": True}, "battery"),
        ({"state": "fair"}, "thermal"),
        ({"reachable": True, "interface": "wifi"}, "network"),
    ]:
        client.post("/api/v1/mobile/telemetry",
                    json=make_event(device_id, category=category, payload=payload),
                    headers=headers)

    summary = client.get(f"/api/v1/mobile/devices/{device_id}").json()
    assert summary["battery"] == 42
    assert summary["thermal"] == "fair"
    assert summary["network"] == "wifi"
    assert summary["status"] == "online"  # just sent telemetry

    listing = client.get("/api/v1/mobile/devices").json()
    assert any(item["device_id"] == device_id for item in listing["items"])


def test_device_summary_uses_latest_event_per_category(client, device):
    device_id, _, headers = device
    older = to_iso(utc_now() - timedelta(minutes=2))
    newer = to_iso(utc_now() - timedelta(minutes=1))

    client.post("/api/v1/mobile/telemetry",
                json=make_event(device_id, category="battery", timestamp=older,
                                payload={"level": 20, "charging": False, "low_power_mode": True}),
                headers=headers)
    client.post("/api/v1/mobile/telemetry",
                json=make_event(device_id, category="battery", timestamp=newer,
                                payload={"level": 88, "charging": True, "low_power_mode": False}),
                headers=headers)
    client.post("/api/v1/mobile/telemetry",
                json=make_event(device_id, category="thermal", timestamp=newer,
                                payload={"state": "fair"}),
                headers=headers)
    client.post("/api/v1/mobile/telemetry",
                json=make_event(device_id, category="network", timestamp=newer,
                                payload={"reachable": True, "interface": "cellular"}),
                headers=headers)

    summary = client.get(f"/api/v1/mobile/devices/{device_id}").json()

    assert summary["battery"] == 88
    assert summary["thermal"] == "fair"
    assert summary["network"] == "cellular"


def test_unknown_device_returns_standard_404(client):
    response = client.get("/api/v1/mobile/devices/dev_missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DEVICE_NOT_FOUND"

    telemetry = client.get("/api/v1/mobile/devices/dev_missing/telemetry")
    assert telemetry.status_code == 404
    assert telemetry.json()["error"]["code"] == "DEVICE_NOT_FOUND"

    alerts = client.get("/api/v1/mobile/devices/dev_missing/alerts")
    assert alerts.status_code == 404
    assert alerts.json()["error"]["code"] == "DEVICE_NOT_FOUND"


def test_telemetry_query_filters_and_paginates(client, device):
    device_id, _, headers = device
    for level in range(10):
        client.post("/api/v1/mobile/telemetry",
                    json=make_event(device_id, payload={"level": level}), headers=headers)
    client.post("/api/v1/mobile/telemetry",
                json=make_event(device_id, category="thermal", payload={"state": "nominal"}),
                headers=headers)

    page = client.get(f"/api/v1/mobile/devices/{device_id}/telemetry",
                      params={"category": "battery", "limit": 4, "page": 2}).json()
    assert page["total"] == 10
    assert len(page["items"]) == 4
    assert all(item["category"] == "battery" for item in page["items"])


def test_telemetry_query_filters_by_time_window(client, device):
    device_id, _, headers = device
    old = to_iso(utc_now() - timedelta(minutes=10))
    middle = to_iso(utc_now() - timedelta(minutes=5))
    recent = to_iso(utc_now() - timedelta(minutes=1))

    for timestamp, level in [(old, 10), (middle, 50), (recent, 90)]:
        client.post("/api/v1/mobile/telemetry",
                    json=make_event(device_id, timestamp=timestamp,
                                    payload={"level": level, "charging": False, "low_power_mode": False}),
                    headers=headers)

    page = client.get(
        f"/api/v1/mobile/devices/{device_id}/telemetry",
        params={"category": "battery", "from": middle, "to": recent, "limit": 10},
    ).json()

    levels = {item["payload"]["level"] for item in page["items"]}
    assert page["total"] == 2
    assert levels == {50, 90}


def test_config_returns_defaults(client, device):
    _, _, headers = device
    config = client.get("/api/v1/mobile/config", headers=headers).json()
    assert config["config_version"] == "1.0"
    assert config["collectors"]["battery"]["enabled"] is True
    assert config["upload"]["websocket_enabled"] is True
