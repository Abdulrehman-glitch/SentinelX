"""Collector configuration sync (docs/spec/03 §15). Serves a stored
per-device config if one exists, otherwise the spec default."""

import json
import sqlite3

from fastapi import APIRouter, Depends

from ..deps import get_conn, get_current_device

router = APIRouter()

DEFAULT_CONFIG = {
    "config_version": "1.0",
    "collectors": {
        "device": {"enabled": True, "interval_seconds": 300},
        "battery": {"enabled": True, "interval_seconds": 30},
        "thermal": {"enabled": True, "interval_seconds": 60},
        "storage": {"enabled": True, "interval_seconds": 60},
        "network": {"enabled": True, "interval_seconds": 30},
        "motion": {"enabled": False, "sample_hz": 20},
        "location": {"enabled": False, "interval_seconds": 5, "accuracy": "balanced"},
        "bluetooth": {"enabled": False},
    },
    "upload": {
        "websocket_enabled": True,
        "batch_size": 100,
        "flush_interval_seconds": 30,
    },
}


@router.get("/config")
def get_config(
    device: sqlite3.Row = Depends(get_current_device),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    row = conn.execute(
        """SELECT config_version, config_json FROM mobile_config
           WHERE device_id = ? ORDER BY updated_at DESC LIMIT 1""",
        (device["device_id"],),
    ).fetchone()
    if row:
        config = json.loads(row["config_json"])
        config_version = row["config_version"]
    else:
        config = {k: v for k, v in DEFAULT_CONFIG.items() if k != "config_version"}
        config_version = DEFAULT_CONFIG["config_version"]
    return {"device_id": device["device_id"], "config_version": config_version, **config}
