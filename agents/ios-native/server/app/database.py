"""SQLite storage for the dev server. The production backend uses
PostgreSQL; the schema here mirrors docs/spec/05 §31 with SQLite types so
the contract behaviour (idempotency, lookups) is faithful."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS mobile_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT UNIQUE NOT NULL,
    platform TEXT NOT NULL,
    device_name TEXT NOT NULL,
    device_model TEXT,
    os_version TEXT,
    app_version TEXT,
    vendor_identifier_hash TEXT,
    timezone TEXT,
    locale TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    registered_at TEXT NOT NULL,
    last_seen TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mobile_device_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL REFERENCES mobile_devices(device_id),
    device_secret_hash TEXT NOT NULL,
    refresh_token_hash TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS mobile_telemetry_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    device_id TEXT NOT NULL REFERENCES mobile_devices(device_id),
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,
    type TEXT NOT NULL,
    source TEXT NOT NULL,
    sequence INTEGER,
    payload_json TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mobile_telemetry_device_timestamp
    ON mobile_telemetry_events (device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_mobile_telemetry_category_timestamp
    ON mobile_telemetry_events (category, timestamp DESC);

CREATE TABLE IF NOT EXISTS mobile_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT UNIQUE NOT NULL,
    device_id TEXT NOT NULL REFERENCES mobile_devices(device_id),
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    rule TEXT NOT NULL,
    message TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS mobile_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT REFERENCES mobile_devices(device_id),
    config_version TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def connect(database_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(database_path: str) -> None:
    conn = connect(database_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
