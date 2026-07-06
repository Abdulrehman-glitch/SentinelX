import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.timeutil import now_iso


@pytest.fixture()
def client(tmp_path):
    settings = Settings(database_path=str(tmp_path / "test.db"))
    with TestClient(create_app(settings)) as test_client:
        yield test_client


REGISTER_BODY = {
    "platform": "ios",
    "device_name": "Test iPhone",
    "device_model": "iPhone 15",
    "os_version": "iOS 17.5",
    "app_version": "1.0.0",
    "vendor_identifier": "vendor-test-0001",
    "timezone": "Europe/London",
    "locale": "en_GB",
}


@pytest.fixture()
def device(client):
    """Registered + logged-in device: (device_id, secret, auth headers)."""
    registered = client.post("/api/v1/mobile/register", json=REGISTER_BODY).json()
    tokens = client.post(
        "/api/v1/mobile/login",
        json={"device_id": registered["device_id"], "device_secret": registered["device_secret"]},
    ).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return registered["device_id"], registered["device_secret"], headers


def make_event(device_id: str, category: str = "battery", payload: dict | None = None, **overrides):
    event = {
        "event_id": str(uuid.uuid4()),
        "device_id": device_id,
        "timestamp": now_iso(),
        "category": category,
        "type": f"{category}.snapshot",
        "source": "test.fixture",
        "sequence": 1,
        "payload": payload if payload is not None else {"level": 84, "charging": False, "low_power_mode": False},
    }
    event.update(overrides)
    return event
