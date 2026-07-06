"""Register / login / token refresh (docs/spec/03 §6–8)."""

import sqlite3

from fastapi import APIRouter, Depends

from .. import store
from ..config import Settings
from ..deps import get_conn, get_settings
from ..errors import APIError
from ..models import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenRefreshRequest,
    TokenResponse,
)
from ..security import (
    TokenError,
    decode_token,
    hash_secret,
    hash_token,
    issue_tokens,
    new_device_id,
    new_device_secret,
    verify_secret,
)

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(
    body: RegisterRequest,
    conn: sqlite3.Connection = Depends(get_conn),
) -> RegisterResponse:
    vendor_hash = store.hash_vendor_identifier(body.vendor_identifier)
    secret = new_device_secret()
    secret_hash = hash_secret(secret)

    existing = store.find_device_by_vendor_hash(conn, vendor_hash)
    if existing is not None:
        # Same physical device re-registering: keep the device_id, rotate
        # the secret (we only store hashes, so the old one can't be returned).
        store.rotate_device_secret(conn, existing["device_id"], secret_hash)
        return RegisterResponse(
            device_id=existing["device_id"],
            device_secret=secret,
            registered_at=existing["registered_at"],
            status=existing["status"],
        )

    device_id = new_device_id()
    registered_at = store.create_device(
        conn,
        device_id,
        {
            "platform": body.platform.value,
            "device_name": body.device_name,
            "device_model": body.device_model,
            "os_version": body.os_version,
            "app_version": body.app_version,
            "vendor_identifier_hash": vendor_hash,
            "timezone": body.timezone,
            "locale": body.locale,
        },
        secret_hash,
    )
    return RegisterResponse(
        device_id=device_id,
        device_secret=secret,
        registered_at=registered_at,
        status="active",
    )


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_conn),
) -> TokenResponse:
    device = store.find_device(conn, body.device_id)
    credentials = store.get_credentials(conn, body.device_id) if device else None
    # Single error path for unknown device / bad secret — no oracle.
    if device is None or credentials is None or not verify_secret(body.device_secret, credentials["device_secret_hash"]):
        raise APIError(401, "INVALID_TOKEN", "Invalid device credentials")
    if device["status"] != "active":
        raise APIError(403, "DEVICE_DISABLED", "Device is not active")

    access, refresh = issue_tokens(settings, body.device_id)
    store.set_refresh_token_hash(conn, body.device_id, hash_token(refresh))
    store.touch_last_seen(conn, body.device_id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/token/refresh", response_model=TokenResponse)
def refresh_token(
    body: TokenRefreshRequest,
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_conn),
) -> TokenResponse:
    try:
        device_id = decode_token(settings, body.refresh_token, "refresh")
    except TokenError as exc:
        raise APIError(401, exc.code, "Refresh token rejected")

    credentials = store.get_credentials(conn, device_id)
    # Rotation: only the most recently issued refresh token is accepted.
    if credentials is None or credentials["refresh_token_hash"] != hash_token(body.refresh_token):
        raise APIError(401, "INVALID_TOKEN", "Refresh token superseded or revoked")

    access, refresh = issue_tokens(settings, device_id)
    store.set_refresh_token_hash(conn, device_id, hash_token(refresh))
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_seconds,
    )
