from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import REGISTER_BODY, make_event


def _client(tmp_path, **settings_overrides):
    settings = Settings(database_path=str(tmp_path / "rate-limit.db"), **settings_overrides)
    return TestClient(create_app(settings))


def _error(response):
    return response.json()["error"]


def test_register_rate_limit_returns_standard_429(tmp_path) -> None:
    with _client(tmp_path, register_limit_per_minute=2) as client:
        for index in range(2):
            body = {**REGISTER_BODY, "vendor_identifier": f"vendor-register-{index}"}
            assert client.post("/api/v1/mobile/register", json=body).status_code == 201

        limited = client.post(
            "/api/v1/mobile/register",
            json={**REGISTER_BODY, "vendor_identifier": "vendor-register-limited"},
        )

    assert limited.status_code == 429
    error = _error(limited)
    assert error["code"] == "RATE_LIMITED"
    assert error["details"]["retry_after_seconds"] > 0


def test_login_rate_limit_is_per_device(tmp_path) -> None:
    with _client(tmp_path, login_limit_per_minute=2) as client:
        registered = client.post("/api/v1/mobile/register", json=REGISTER_BODY).json()
        login_body = {
            "device_id": registered["device_id"],
            "device_secret": registered["device_secret"],
        }
        assert client.post("/api/v1/mobile/login", json=login_body).status_code == 200
        assert client.post("/api/v1/mobile/login", json=login_body).status_code == 200
        limited = client.post("/api/v1/mobile/login", json=login_body)

    assert limited.status_code == 429
    assert _error(limited)["details"]["retry_after_seconds"] > 0


def test_telemetry_rate_limit_returns_standard_429(tmp_path) -> None:
    with _client(tmp_path, telemetry_limit_per_minute=2) as client:
        registered = client.post("/api/v1/mobile/register", json=REGISTER_BODY).json()
        tokens = client.post(
            "/api/v1/mobile/login",
            json={
                "device_id": registered["device_id"],
                "device_secret": registered["device_secret"],
            },
        ).json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        for index in range(2):
            response = client.post(
                "/api/v1/mobile/telemetry",
                json=make_event(registered["device_id"], sequence=index),
                headers=headers,
            )
            assert response.status_code == 200

        limited = client.post(
            "/api/v1/mobile/telemetry",
            json=make_event(registered["device_id"], sequence=99),
            headers=headers,
        )

    assert limited.status_code == 429
    error = _error(limited)
    assert error["code"] == "RATE_LIMITED"
    assert error["details"]["retry_after_seconds"] > 0


def test_ws_message_rate_limit_sends_error(tmp_path) -> None:
    with _client(tmp_path, ws_message_limit_per_minute=2) as client:
        registered = client.post("/api/v1/mobile/register", json=REGISTER_BODY).json()
        tokens = client.post(
            "/api/v1/mobile/login",
            json={
                "device_id": registered["device_id"],
                "device_secret": registered["device_secret"],
            },
        ).json()

        with client.websocket_connect(f"/api/v1/mobile/ws/{registered['device_id']}") as ws:
            ws.send_json({
                "type": "auth",
                "access_token": tokens["access_token"],
                "device_id": registered["device_id"],
            })
            assert ws.receive_json()["type"] == "auth.accepted"

            for _ in range(2):
                ws.send_json({"type": "heartbeat", "device_id": registered["device_id"]})
                assert ws.receive_json()["type"] == "heartbeat.ack"

            ws.send_json({"type": "heartbeat", "device_id": registered["device_id"]})
            limited = ws.receive_json()

    assert limited["type"] == "error"
    assert limited["code"] == "RATE_LIMITED"
    assert limited["details"]["retry_after_seconds"] > 0
