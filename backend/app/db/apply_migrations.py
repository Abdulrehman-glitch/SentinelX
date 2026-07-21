"""Deterministic, idempotent application of migrations/*.sql.

No Alembic (see CLAUDE.md) — migrations/ holds hand-written SQL files meant
to bring an existing database (a legacy snapshot, or production) up to the
schema that Base.metadata.create_all already gives a fresh install. This
script tracks which files have run in a schema_migrations table so it is
safe to run repeatedly against any database: already-applied files are
skipped, and every file's own DDL is written to be a no-op when re-run
(CREATE ... IF NOT EXISTS, ADD COLUMN IF NOT EXISTS, guarded DO blocks for
constraints).
"""

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.session import engine

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"

# Filenames mix two date formats ("2026_06_26_..." and "2026-07-12_...").
# Sorting by the raw filename string is wrong: "-" (0x2D) sorts before "_"
# (0x5F) in ASCII, so "2026-07-12_mobile_metric_columns.sql" would sort
# *before* "2026_06_26_device_detail_indexes.sql" even though June precedes
# July. Parse the actual date instead of trusting filename order.
_DATE_PREFIX_RE = re.compile(r"^(\d{4})[-_](\d{2})[-_](\d{2})_")


def _chronological_sort_key(path: Path) -> tuple[int, int, int, str]:
    match = _DATE_PREFIX_RE.match(path.name)
    if not match:
        raise ValueError(f"Migration filename does not start with a YYYY-MM-DD/YYYY_MM_DD date: {path.name}")
    year, month, day = (int(part) for part in match.groups())
    return (year, month, day, path.name)


def ordered_migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"), key=_chronological_sort_key)


def _ensure_tracking_table(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename VARCHAR(255) PRIMARY KEY,
                checksum VARCHAR(64) NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )


def _already_applied(connection) -> set[str]:
    rows = connection.execute(text("SELECT filename FROM schema_migrations")).fetchall()
    return {row[0] for row in rows}


def apply_migrations(target_engine: Engine = engine) -> list[str]:
    """Apply every not-yet-applied migration file, in chronological order.

    Returns the filenames applied during this call (empty if the database
    was already up to date). Each file runs in its own transaction: either
    its full DDL commits and gets recorded, or it rolls back untouched.
    """
    with target_engine.begin() as connection:
        _ensure_tracking_table(connection)
        already = _already_applied(connection)

    applied_now: list[str] = []
    for path in ordered_migration_files():
        if path.name in already:
            continue

        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()

        with target_engine.begin() as connection:
            connection.execute(text(sql))
            connection.execute(
                text(
                    """
                    INSERT INTO schema_migrations (filename, checksum, applied_at)
                    VALUES (:filename, :checksum, :applied_at)
                    """
                ),
                {"filename": path.name, "checksum": checksum, "applied_at": datetime.now(timezone.utc)},
            )

        applied_now.append(path.name)

    return applied_now


if __name__ == "__main__":
    applied = apply_migrations()
    if applied:
        print(f"Applied {len(applied)} migration(s):")
        for name in applied:
            print(f"  - {name}")
    else:
        print("Database already up to date -- no migrations applied.")
