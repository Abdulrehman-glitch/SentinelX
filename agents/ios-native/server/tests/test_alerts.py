from __future__ import annotations

import sqlite3
from datetime import timedelta

from app.timeutil import to_iso, utc_now
from tests.conftest import make_event


def _alerts(client, device_id):
    return client.get(f"/api/v1/mobile/devices/{device_id}/alerts").json()["items"]


def test_battery_low_alert_fires_dedupes_and_resolves(client, device):
    device_id, _, headers = device

    first = client.post(
        "/api/v1/mobile/telemetry",
        json=make_event(device_id, payload={"level": 15, "charging": False, "low_power_mode": True}),
        headers=headers,
    )
    second = client.post(
        "/api/v1/mobile/telemetry",
        json=make_event(device_id, payload={"level": 12, "charging": False, "low_power_mode": True}),
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200

    active = [alert for alert in _alerts(client, device_id) if not alert["resolved"]]
    assert len(active) == 1
    assert active[0]["rule"] == "BATTERY_LOW"
    assert active[0]["severity"] == "warning"

    client.post(
        "/api/v1/mobile/telemetry",
        json=make_event(device_id, payload={"level": 50, "charging": True, "low_power_mode": False}),
        headers=headers,
    )
    alerts = _alerts(client, device_id)
    low_alert = next(alert for alert in alerts if alert["rule"] == "BATTERY_LOW")
    assert low_alert["resolved"] is True
    assert low_alert["resolved_at"] is not None
    assert client.get(f"/api/v1/mobile/devices/{device_id}").json()["active_alerts"] == 0


def test_network_loss_alert_resolves_when_reachable(client, device):
    device_id, _, headers = device

    client.post(
        "/api/v1/mobile/telemetry",
        json=make_event(device_id, category="network",
                        payload={"reachable": False, "interface": "unavailable"}),
        headers=headers,
    )
    assert any(alert["rule"] == "NETWORK_LOSS" and not alert["resolved"] for alert in _alerts(client, device_id))

    client.post(
        "/api/v1/mobile/telemetry",
        json=make_event(device_id, category="network",
                        payload={"reachable": True, "interface": "wifi"}),
        headers=headers,
    )
    network_alert = next(alert for alert in _alerts(client, device_id) if alert["rule"] == "NETWORK_LOSS")
    assert network_alert["resolved"] is True


def test_ws_telemetry_pushes_alert_created(client, device):
    device_id, secret, _ = device
    tokens = client.post("/api/v1/mobile/login", json={
        "device_id": device_id, "device_secret": secret}).json()

    with client.websocket_connect(f"/api/v1/mobile/ws/{device_id}") as ws:
        ws.send_json({"type": "auth", "access_token": tokens["access_token"], "device_id": device_id})
        assert ws.receive_json()["type"] == "auth.accepted"

        ws.send_json({
            "type": "telemetry.event",
            "event": make_event(device_id, category="thermal", payload={"state": "critical"}),
        })
        pushed = ws.receive_json()

    assert pushed["type"] == "alert.created"
    assert pushed["alert"]["rule"] == "THERMAL_CRITICAL"
    assert pushed["alert"]["severity"] == "critical"


def test_offline_alert_created_from_dashboard_read(client, device):
    device_id, _, _ = device
    conn = sqlite3.connect(client.app.state.settings.database_path)
    try:
        conn.execute(
            "UPDATE mobile_devices SET last_seen = ? WHERE device_id = ?",
            (to_iso(utc_now() - timedelta(minutes=6)), device_id),
        )
        conn.commit()
    finally:
        conn.close()

    alerts = _alerts(client, device_id)

    assert any(alert["rule"] == "DEVICE_OFFLINE" and not alert["resolved"] for alert in alerts)
