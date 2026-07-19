"""Local SQLite persistence for the SentinelX desktop agent.

Two responsibilities:
- a persist-first metric queue so samples survive backend/network outages
  and process restarts (flushed in idempotent batches via event_id);
- a small key/value state table so recovery cooldowns and device identity
  survive restarts instead of living in process memory.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def default_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "SentinelX"
    return Path.home() / ".sentinelx"


@dataclass(frozen=True)
class QueuedMetric:
    event_id: str
    captured_at: str
    cpu_percent: float | None
    memory_percent: float
    disk_percent: float
    attempts: int

    def to_sample(self) -> dict:
        return {
            "event_id": self.event_id,
            "recorded_at": self.captured_at,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_percent": self.disk_percent,
        }


class AgentStore:
    def __init__(self, db_path: Path | None = None, *, max_queue_rows: int = 10_000) -> None:
        path = db_path or (default_data_dir() / "agent.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._max_queue_rows = max_queue_rows
        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metric_queue (
                event_id TEXT PRIMARY KEY,
                captured_at TEXT NOT NULL,
                cpu_percent REAL,
                memory_percent REAL NOT NULL,
                disk_percent REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                next_retry_at REAL NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS agent_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS command_log (
                command_id TEXT PRIMARY KEY,
                nonce TEXT,
                action_type TEXT NOT NULL,
                status TEXT NOT NULL,
                received_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- metric queue -------------------------------------------------------

    def enqueue_metric(
        self,
        *,
        cpu_percent: float | None,
        memory_percent: float,
        disk_percent: float,
        captured_at: datetime | None = None,
    ) -> str:
        """Persist a sample before any upload attempt. Returns its event_id."""
        event_id = str(uuid.uuid4())
        when = (captured_at or datetime.now(timezone.utc)).isoformat()
        self._conn.execute(
            "INSERT INTO metric_queue (event_id, captured_at, cpu_percent, memory_percent, disk_percent) VALUES (?, ?, ?, ?, ?)",
            (event_id, when, cpu_percent, memory_percent, disk_percent),
        )
        # Bound disk usage: drop the oldest rows beyond the cap.
        self._conn.execute(
            """
            DELETE FROM metric_queue WHERE event_id IN (
                SELECT event_id FROM metric_queue
                ORDER BY captured_at DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (self._max_queue_rows,),
        )
        self._conn.commit()
        return event_id

    def next_batch(self, limit: int = 100) -> list[QueuedMetric]:
        """Oldest-first rows that are due for (re)delivery."""
        rows = self._conn.execute(
            """
            SELECT event_id, captured_at, cpu_percent, memory_percent, disk_percent, attempts
            FROM metric_queue
            WHERE next_retry_at <= ?
            ORDER BY captured_at ASC
            LIMIT ?
            """,
            (time.time(), limit),
        ).fetchall()
        return [QueuedMetric(*row) for row in rows]

    def mark_delivered(self, event_ids: list[str]) -> None:
        """Remove rows only after an idempotent backend acknowledgement."""
        self._conn.executemany("DELETE FROM metric_queue WHERE event_id = ?", [(e,) for e in event_ids])
        self._conn.commit()

    def mark_failed(self, event_ids: list[str], *, base_delay: float = 30.0, max_delay: float = 900.0) -> None:
        """Push failed rows into the future with per-row exponential backoff."""
        now = time.time()
        for event_id in event_ids:
            row = self._conn.execute(
                "SELECT attempts FROM metric_queue WHERE event_id = ?", (event_id,)
            ).fetchone()
            if row is None:
                continue
            attempts = row[0] + 1
            delay = min(base_delay * (2 ** min(attempts - 1, 6)), max_delay)
            self._conn.execute(
                "UPDATE metric_queue SET attempts = ?, next_retry_at = ? WHERE event_id = ?",
                (attempts, now + delay, event_id),
            )
        self._conn.commit()

    def queue_depth(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM metric_queue").fetchone()[0]

    def drop_exhausted(self, *, max_attempts: int = 20) -> int:
        """Drop rows that have failed at least ``max_attempts`` times.

        Used by the ``repair_agent_queue`` recovery action to clear rows that
        will never successfully deliver (e.g. permanently malformed samples).
        """
        cursor = self._conn.execute("DELETE FROM metric_queue WHERE attempts >= ?", (max_attempts,))
        self._conn.commit()
        return cursor.rowcount

    # -- signed recovery commands --------------------------------------------

    def get_command_status(self, command_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT status FROM command_log WHERE command_id = ?", (command_id,)
        ).fetchone()
        return row[0] if row else None

    def nonce_seen(self, nonce: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM command_log WHERE nonce = ?", (nonce,)).fetchone()
        return row is not None

    def record_command_received(self, command_id: str, nonce: str | None, action_type: str) -> None:
        """Persist receipt before any execution — idempotent (first receipt wins)."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR IGNORE INTO command_log (command_id, nonce, action_type, status, received_at) "
            "VALUES (?, ?, ?, 'received', ?)",
            (command_id, nonce, action_type, now),
        )
        self._conn.commit()

    def update_command_status(self, command_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE command_log SET status = ? WHERE command_id = ?", (status, command_id)
        )
        self._conn.commit()

    def mark_command_completed(self, command_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE command_log SET status = 'completed', completed_at = ? WHERE command_id = ?",
            (now, command_id),
        )
        self._conn.commit()

    # -- persistent state ---------------------------------------------------

    def get_state(self, key: str, default=None):
        row = self._conn.execute("SELECT value FROM agent_state WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return json.loads(row[0])

    def set_state(self, key: str, value) -> None:
        self._conn.execute(
            "INSERT INTO agent_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )
        self._conn.commit()
