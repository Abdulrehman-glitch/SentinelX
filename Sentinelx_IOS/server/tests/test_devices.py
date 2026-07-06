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


def test_unknown_device_returns_standard_404(client):
    response = client.get("/api/v1/mobile/devices/dev_missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DEVICE_NOT_FOUND"


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


def test_config_returns_defaults(client, device):
    _, _, headers = device
    config = client.get("/api/v1/mobile/config", headers=headers).json()
    assert config["config_version"] == "1.0"
    assert config["collectors"]["battery"]["enabled"] is True
    assert config["upload"]["websocket_enabled"] is True
