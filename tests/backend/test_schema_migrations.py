"""Tests for the deterministic migration apply script (Sprint 7 Phase 2).

Exercises three scenarios against dedicated scratch databases (never the
shared sentinelx_test database from conftest.py, since these tests mutate
schema mid-run): a fresh install, a reconstructed pre-Sprint-1 ("v2.0")
legacy schema being upgraded, and idempotent re-application. Also pins the
chronological-ordering bug (hyphen- vs underscore-dated filenames sort
wrong as raw strings) as a regression test.
"""

import os

import psycopg
import pytest
from sqlalchemy import create_engine, inspect, text

from app.db.apply_migrations import MIGRATIONS_DIR, apply_migrations, ordered_migration_files
from app.db.base import Base

_DEV_URL = os.environ["DATABASE_URL"]  # already rewritten to sentinelx_test by conftest.py
_ADMIN_DSN = _DEV_URL.replace("postgresql+psycopg", "postgresql").rsplit("/", 1)[0] + "/postgres"
_SCRATCH_BASE_URL = _DEV_URL.rsplit("/", 1)[0]

ALL_MIGRATION_FILENAMES = {path.name for path in MIGRATIONS_DIR.glob("*.sql")}

# Reverses every schema element the ten migrations under migrations/ add, in
# reverse-chronological (child-before-parent) order, so create_all's full
# latest schema can be stripped down to a pre-Sprint-1 ("v2.0") baseline and
# then upgraded back with apply_migrations() — the real gap Phase 0 found in
# production (code at the Sprint 1 boundary, schema still pre-Sprint-1).
_DOWNGRADE_TO_LEGACY_SQL = """
DROP TABLE IF EXISTS replay_runs;

DROP TABLE IF EXISTS model_evaluation_reports;
ALTER TABLE anomaly_models
    DROP COLUMN IF EXISTS lifecycle_status,
    DROP COLUMN IF EXISTS artifact_checksum,
    DROP COLUMN IF EXISTS promoted_by,
    DROP COLUMN IF EXISTS promoted_at;

DROP TABLE IF EXISTS hybrid_decisions;
ALTER TABLE devices DROP COLUMN IF EXISTS criticality;

DROP TABLE IF EXISTS recovery_command_events;
DROP TABLE IF EXISTS agent_capabilities;
DROP TABLE IF EXISTS recovery_commands;
DROP TABLE IF EXISTS recovery_policies;

DROP TABLE IF EXISTS anomaly_predictions;
DROP TABLE IF EXISTS telemetry_feature_windows;
DROP TABLE IF EXISTS anomaly_models;

DROP TABLE IF EXISTS enrollment_codes;
ALTER TABLE device_credentials
    DROP COLUMN IF EXISTS last_used_at,
    DROP COLUMN IF EXISTS replaces_credential_id;
ALTER TABLE system_metrics DROP CONSTRAINT IF EXISTS uq_metric_device_event;
ALTER TABLE system_metrics
    DROP COLUMN IF EXISTS event_id,
    DROP COLUMN IF EXISTS battery_temperature_c,
    DROP COLUMN IF EXISTS thermal_status,
    DROP COLUMN IF EXISTS network_validated,
    DROP COLUMN IF EXISTS network_metered;
ALTER TABLE system_metrics ALTER COLUMN cpu_percent SET NOT NULL;

ALTER TABLE system_metrics
    DROP COLUMN IF EXISTS battery_percent,
    DROP COLUMN IF EXISTS battery_charging,
    DROP COLUMN IF EXISTS network_transport,
    DROP COLUMN IF EXISTS latency_ms;
"""


def _terminate_and_drop(conn: psycopg.Connection, name: str) -> None:
    conn.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()",
        (name,),
    )
    conn.execute(f"DROP DATABASE IF EXISTS {name}")


def _scratch_database(name: str):
    with psycopg.connect(_ADMIN_DSN, autocommit=True) as conn:
        _terminate_and_drop(conn, name)
        conn.execute(f"CREATE DATABASE {name}")

    scratch_engine = create_engine(f"{_SCRATCH_BASE_URL}/{name}")
    try:
        yield scratch_engine
    finally:
        scratch_engine.dispose()
        with psycopg.connect(_ADMIN_DSN, autocommit=True) as conn:
            _terminate_and_drop(conn, name)


@pytest.fixture()
def fresh_engine():
    yield from _scratch_database("sentinelx_test_migrations_fresh")


@pytest.fixture()
def legacy_engine():
    yield from _scratch_database("sentinelx_test_migrations_legacy")


def test_migration_files_sort_chronologically_not_lexicographically():
    """Regression test for the ordering bug: '-' (0x2D) sorts before '_'
    (0x5F), so a naive filename sort puts "2026-07-12_..." before
    "2026_06_26_..." even though June precedes July."""
    ordered_names = [path.name for path in ordered_migration_files()]

    assert ordered_names.index("2026_06_26_device_detail_indexes.sql") < ordered_names.index(
        "2026-07-12_mobile_metric_columns.sql"
    )
    assert ordered_names.index("2026_06_27_auth_rbac_indexes.sql") < ordered_names.index(
        "2026-07-17_trusted_agent_foundation.sql"
    )
    assert sorted(ordered_names) != ordered_names, "fixture is meaningless if lexicographic order already matches"


def test_fresh_install_apply_records_every_migration(fresh_engine):
    """A brand-new database already has the latest schema via create_all —
    most migration DDL is then a no-op, except the three index-only files,
    whose composite indexes are never modeled in SQLAlchemy and so are
    created for real. Either way every file must be recorded as applied,
    and a second run must apply nothing."""
    Base.metadata.create_all(bind=fresh_engine)

    first_run = apply_migrations(target_engine=fresh_engine)
    assert set(first_run) == ALL_MIGRATION_FILENAMES

    second_run = apply_migrations(target_engine=fresh_engine)
    assert second_run == []


def test_legacy_v2_schema_upgrades_to_full_schema(legacy_engine):
    """Reconstruct a pre-Sprint-1 ("v2.0") schema by stripping every table/
    column the migrations added from a full create_all schema, then prove
    apply_migrations() brings it back to parity."""
    Base.metadata.create_all(bind=legacy_engine)
    with legacy_engine.begin() as connection:
        connection.execute(text(_DOWNGRADE_TO_LEGACY_SQL))

    pre_upgrade_tables = set(inspect(legacy_engine).get_table_names())
    assert "enrollment_codes" not in pre_upgrade_tables
    assert "hybrid_decisions" not in pre_upgrade_tables

    applied = apply_migrations(target_engine=legacy_engine)
    assert set(applied) == ALL_MIGRATION_FILENAMES

    inspector = inspect(legacy_engine)
    table_names = set(inspector.get_table_names())
    for expected_table in (
        "enrollment_codes",
        "telemetry_feature_windows",
        "anomaly_models",
        "anomaly_predictions",
        "recovery_policies",
        "recovery_commands",
        "recovery_command_events",
        "agent_capabilities",
        "hybrid_decisions",
        "model_evaluation_reports",
        "replay_runs",
    ):
        assert expected_table in table_names, f"{expected_table} missing after migration upgrade"

    system_metrics_columns = {col["name"] for col in inspector.get_columns("system_metrics")}
    for expected_column in (
        "event_id",
        "battery_temperature_c",
        "thermal_status",
        "network_validated",
        "network_metered",
        "battery_percent",
        "battery_charging",
        "network_transport",
        "latency_ms",
    ):
        assert expected_column in system_metrics_columns

    assert "criticality" in {col["name"] for col in inspector.get_columns("devices")}
    assert "lifecycle_status" in {col["name"] for col in inspector.get_columns("anomaly_models")}

    # Idempotent re-run: nothing left to apply.
    assert apply_migrations(target_engine=legacy_engine) == []


def test_fk_and_index_integrity_after_upgrade(legacy_engine):
    Base.metadata.create_all(bind=legacy_engine)
    with legacy_engine.begin() as connection:
        connection.execute(text(_DOWNGRADE_TO_LEGACY_SQL))
    apply_migrations(target_engine=legacy_engine)

    inspector = inspect(legacy_engine)

    enrollment_fk_targets = {fk["referred_table"] for fk in inspector.get_foreign_keys("enrollment_codes")}
    assert "organizations" in enrollment_fk_targets

    hybrid_fk_targets = {fk["referred_table"] for fk in inspector.get_foreign_keys("hybrid_decisions")}
    assert {"organizations", "devices", "telemetry_feature_windows"} <= hybrid_fk_targets

    system_metrics_indexes = {idx["name"] for idx in inspector.get_indexes("system_metrics")}
    assert "ix_system_metrics_device_recorded_at" in system_metrics_indexes

    user_indexes = {idx["name"] for idx in inspector.get_indexes("users")}
    assert "ix_users_role_created_at" in user_indexes
