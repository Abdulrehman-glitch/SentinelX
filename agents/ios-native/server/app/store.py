"""Data access over SQLite. One connection per request (see deps.get_conn);
all functions take an open connection and commit their own writes."""

import hashlib
import json
import sqlite3
import uuid
from typing import Any

from .timeutil import now_iso


def hash_vendor_identifier(vendor_identifier: str) -> str:
    return hashlib.sha256(vendor_identifier.encode()).hexdigest()


# --- devices -----------------------------------------------------------

def find_device_by_vendor_hash(conn: sqlite3.Connection, vendor_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM mobile_devices WHERE vendor_identifier_hash = ?", (vendor_hash,)
    ).fetchone()


def find_device(conn: sqlite3.Connection, device_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM mobile_devices WHERE device_id = ?", (device_id,)
    ).fetchone()


def create_device(conn: sqlite3.Connection, device_id: str, fields: dict[str, Any], secret_hash: str) -> str:
    now = now_iso()
    conn.execute(
        """INSERT INTO mobile_devices
           (device_id, platform, device_name, device_model, os_version, app_version,
            vendor_identifier_hash, timezone, locale, status, registered_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
        (
            device_id,
            fields["platform"],
            fields["device_name"],
            fields["device_model"],
            fields["os_version"],
            fields["app_version"],
            fields["vendor_identifier_hash"],
            fields["timezone"],
            fields["locale"],
            now,
            now,
            now,
        ),
    )
    conn.execute(
        """INSERT INTO mobile_device_credentials (device_id, device_secret_hash, created_at, updated_at)
           VALUES (?, ?, ?, ?)""",
        (device_id, secret_hash, now, now),
    )
    conn.commit()
    return now


def rotate_device_secret(conn: sqlite3.Connection, device_id: str, secret_hash: str) -> str:
    now = now_iso()
    conn.execute(
        """UPDATE mobile_device_credentials
           SET device_secret_hash = ?, refresh_token_hash = NULL, updated_at = ?, revoked_at = NULL
           WHERE device_id = ?""",
        (secret_hash, now, device_id),
    )
    conn.execute("UPDATE mobile_devices SET updated_at = ? WHERE device_id = ?", (now, device_id))
    conn.commit()
    return now


def get_credentials(conn: sqlite3.Connection, device_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM mobile_device_credentials WHERE device_id = ? AND revoked_at IS NULL",
        (device_id,),
    ).fetchone()


def set_refresh_token_hash(conn: sqlite3.Connection, device_id: str, token_hash: str) -> None:
    conn.execute(
        "UPDATE mobile_device_credentials SET refresh_token_hash = ?, updated_at = ? WHERE device_id = ?",
        (token_hash, now_iso(), device_id),
    )
    conn.commit()


def touch_last_seen(conn: sqlite3.Connection, device_id: str) -> None:
    now = now_iso()
    conn.execute(
        "UPDATE mobile_devices SET last_seen = ?, updated_at = ? WHERE device_id = ?",
        (now, now, device_id),
    )
    conn.commit()


def update_profile(conn: sqlite3.Connection, device_id: str, updates: dict[str, str]) -> str:
    now = now_iso()
    sets = ", ".join(f"{column} = ?" for column in updates)
    conn.execute(
        f"UPDATE mobile_devices SET {sets}, updated_at = ? WHERE device_id = ?",
        (*updates.values(), now, device_id),
    )
    conn.commit()
    return now


# --- telemetry ---------------------------------------------------------

def insert_event(conn: sqlite3.Connection, device_id: str, event: dict[str, Any]) -> bool:
    """Insert one envelope; returns False when event_id already exists."""
    cursor = conn.execute(
        """INSERT OR IGNORE INTO mobile_telemetry_events
           (event_id, device_id, timestamp, category, type, source, sequence,
            payload_json, metadata_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(event["event_id"]),
            device_id,
            event["timestamp"],
            event["category"],
            event["type"],
            event["source"],
            event.get("sequence"),
            json.dumps(event["payload"]),
            json.dumps(event["metadata"]) if event.get("metadata") else None,
            now_iso(),
        ),
    )
    conn.commit()
    return cursor.rowcount == 1


def query_events(
    conn: sqlite3.Connection,
    device_id: str,
    category: str | None,
    time_from: str | None,
    time_to: str | None,
    limit: int,
    page: int,
) -> tuple[list[dict[str, Any]], int]:
    where = ["device_id = ?"]
    params: list[Any] = [device_id]
    if category:
        where.append("category = ?")
        params.append(category)
    if time_from:
        where.append("timestamp >= ?")
        params.append(time_from)
    if time_to:
        where.append("timestamp <= ?")
        params.append(time_to)
    clause = " AND ".join(where)

    total = conn.execute(
        f"SELECT COUNT(*) FROM mobile_telemetry_events WHERE {clause}", params
    ).fetchone()[0]
    rows = conn.execute(
        f"""SELECT event_id, device_id, timestamp, category, type, source, sequence,
                   payload_json, metadata_json
            FROM mobile_telemetry_events WHERE {clause}
            ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
        (*params, limit, (page - 1) * limit),
    ).fetchall()

    items = []
    for row in rows:
        items.append(
            {
                "event_id": row["event_id"],
                "device_id": row["device_id"],
                "timestamp": row["timestamp"],
                "category": row["category"],
                "type": row["type"],
                "source": row["source"],
                "sequence": row["sequence"],
                "payload": json.loads(row["payload_json"]),
                "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else None,
            }
        )
    return items, total


def latest_payload(conn: sqlite3.Connection, device_id: str, category: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT payload_json FROM mobile_telemetry_events
           WHERE device_id = ? AND category = ?
           ORDER BY timestamp DESC LIMIT 1""",
        (device_id, category),
    ).fetchone()
    return json.loads(row["payload_json"]) if row else None


# --- alerts ------------------------------------------------------------

def list_alerts(conn: sqlite3.Connection, device_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM mobile_alerts WHERE device_id = ? ORDER BY created_at DESC",
        (device_id,),
    ).fetchall()


def count_active_alerts(conn: sqlite3.Connection, device_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM mobile_alerts WHERE device_id = ? AND resolved = 0",
        (device_id,),
    ).fetchone()[0]


def find_active_alert(conn: sqlite3.Connection, device_id: str, rule: str) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM mobile_alerts
           WHERE device_id = ? AND rule = ? AND resolved = 0
           ORDER BY created_at DESC LIMIT 1""",
        (device_id, rule),
    ).fetchone()


def create_alert(
    conn: sqlite3.Connection,
    device_id: str,
    severity: str,
    category: str,
    rule: str,
    message: str,
) -> dict[str, Any]:
    alert_id = "alert_" + uuid.uuid4().hex[:20]
    now = now_iso()
    conn.execute(
        """INSERT INTO mobile_alerts (alert_id, device_id, severity, category, rule, message, resolved, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
        (alert_id, device_id, severity, category, rule, message, now),
    )
    conn.commit()
    return {
        "alert_id": alert_id,
        "device_id": device_id,
        "severity": severity,
        "category": category,
        "rule": rule,
        "message": message,
        "created_at": now,
        "resolved": False,
        "resolved_at": None,
    }


def resolve_alert(conn: sqlite3.Connection, device_id: str, rule: str) -> bool:
    now = now_iso()
    cursor = conn.execute(
        """UPDATE mobile_alerts
           SET resolved = 1, resolved_at = ?
           WHERE device_id = ? AND rule = ? AND resolved = 0""",
        (now, device_id, rule),
    )
    conn.commit()
    return cursor.rowcount > 0
