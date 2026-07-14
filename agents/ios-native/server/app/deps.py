"""Request-scoped dependencies: settings, DB connection, authenticated
device."""

import sqlite3
from collections.abc import Iterator

from fastapi import Depends, Request

from . import database, store
from .config import Settings
from .errors import APIError
from .security import TokenError, decode_token


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = database.connect(request.app.state.settings.database_path)
    try:
        yield conn
    finally:
        conn.close()


def get_current_device(
    request: Request,
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_conn),
) -> sqlite3.Row:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise APIError(401, "AUTH_REQUIRED", "Missing bearer token")
    try:
        device_id = decode_token(settings, auth.removeprefix("Bearer ").strip(), "access")
    except TokenError as exc:
        raise APIError(401, exc.code, "Access token rejected")
    device = store.find_device(conn, device_id)
    if device is None:
        raise APIError(404, "DEVICE_NOT_FOUND", "Device not found")
    if device["status"] != "active":
        raise APIError(403, "DEVICE_DISABLED", "Device is not active")
    return device
