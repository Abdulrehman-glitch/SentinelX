from tests.conftest import REGISTER_BODY


def test_register_creates_device(client):
    response = client.post("/api/v1/mobile/register", json=REGISTER_BODY)
    assert response.status_code == 201
    body = response.json()
    assert body["device_id"].startswith("dev_")
    assert body["device_secret"]
    assert body["status"] == "active"


def test_reregister_same_vendor_keeps_device_id_rotates_secret(client):
    first = client.post("/api/v1/mobile/register", json=REGISTER_BODY).json()
    second = client.post("/api/v1/mobile/register", json=REGISTER_BODY).json()
    assert second["device_id"] == first["device_id"]
    assert second["device_secret"] != first["device_secret"]

    # old secret is dead, new one logs in
    old = client.post("/api/v1/mobile/login", json={
        "device_id": first["device_id"], "device_secret": first["device_secret"]})
    assert old.status_code == 401
    new = client.post("/api/v1/mobile/login", json={
        "device_id": second["device_id"], "device_secret": second["device_secret"]})
    assert new.status_code == 200


def test_login_returns_token_pair(client):
    registered = client.post("/api/v1/mobile/register", json=REGISTER_BODY).json()
    response = client.post("/api/v1/mobile/login", json={
        "device_id": registered["device_id"], "device_secret": registered["device_secret"]})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert body["access_token"] and body["refresh_token"]


def test_login_bad_secret_uses_error_envelope(client):
    registered = client.post("/api/v1/mobile/register", json=REGISTER_BODY).json()
    response = client.post("/api/v1/mobile/login", json={
        "device_id": registered["device_id"], "device_secret": "wrong"})
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "INVALID_TOKEN"
    assert set(error) == {"code", "message", "details", "request_id"}


def test_refresh_rotates_and_invalidates_old_token(client, device):
    device_id, secret, _ = device
    tokens = client.post("/api/v1/mobile/login", json={
        "device_id": device_id, "device_secret": secret}).json()

    refreshed = client.post("/api/v1/mobile/token/refresh",
                            json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200

    replay = client.post("/api/v1/mobile/token/refresh",
                         json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/v1/mobile/profile").status_code == 401
    garbage = client.get("/api/v1/mobile/profile", headers={"Authorization": "Bearer nope"})
    assert garbage.status_code == 401
    assert garbage.json()["error"]["code"] == "INVALID_TOKEN"
