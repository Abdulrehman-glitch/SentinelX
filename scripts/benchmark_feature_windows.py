"""Before/after benchmark for the feature-window hot path.

Runs `build_pending_windows` over a synthetic but realistically shaped backlog
and reports the three numbers that decide whether a change was worth making:
SQL round trips, wall clock, and rows examined.

Query counting uses a SQLAlchemy `before_cursor_execute` listener rather than a
wrapper, so it counts what the database actually received - including anything
a helper issues behind the service's back.

    python scripts/benchmark_feature_windows.py --devices 5 --days 4

The benchmark database is created, used and dropped inside one run; it never
touches sentinelx_dev. Nothing in the application imports this file.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
import tracemalloc
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import psycopg  # noqa: E402


def _dev_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    for line in (BACKEND / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("DATABASE_URL not found")


BENCH_DB = "sentinelx_fwbench"
_DEV = _dev_url()
os.environ["DATABASE_URL"] = _DEV.rsplit("/", 1)[0] + f"/{BENCH_DB}"


def _admin_dsn() -> str:
    return _DEV.replace("postgresql+psycopg", "postgresql").rsplit("/", 1)[0] + "/postgres"


def _recreate_database() -> None:
    with psycopg.connect(_admin_dsn(), autocommit=True) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
            (BENCH_DB,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{BENCH_DB}"')
        conn.execute(f'CREATE DATABASE "{BENCH_DB}"')


def _drop_database() -> None:
    with psycopg.connect(_admin_dsn(), autocommit=True) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
            (BENCH_DB,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{BENCH_DB}"')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--devices", type=int, default=5)
    parser.add_argument("--days", type=int, default=4)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--keep", action="store_true", help="keep the benchmark database")
    parser.add_argument("--label", default="", help="tag printed with the results")
    args = parser.parse_args()

    _recreate_database()

    from sqlalchemy import event

    from app.db.base import Base
    from app.db.session import SessionLocal, engine
    from app.models.device import Device
    from app.models.organization import Organization
    from app.models.system_metric import SystemMetric
    from app.models.telemetry_feature_window import TelemetryFeatureWindow
    from app.services.feature_window_service import build_pending_windows

    Base.metadata.create_all(bind=engine)

    query_count = 0

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        nonlocal query_count
        query_count += 1

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = now - timedelta(days=args.days)
    samples_per_device = int(args.days * 86400 / args.interval_seconds)

    session = SessionLocal()
    org = Organization(name="Bench", slug=f"bench-{uuid.uuid4().hex[:8]}")
    session.add(org)
    session.flush()

    devices = []
    for index in range(args.devices):
        device = Device(
            organization_id=org.id,
            hostname=f"bench-host-{index}",
            display_name=f"bench-{index}",
            device_type="desktop",
            status="online",
        )
        session.add(device)
        session.flush()
        devices.append(device)

    print(
        f"seeding {args.devices} devices x {samples_per_device} samples "
        f"({args.devices * samples_per_device} rows)...",
        flush=True,
    )
    rows = []
    for device in devices:
        for i in range(samples_per_device):
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "organization_id": org.id,
                    "device_id": device.id,
                    "cpu_percent": 30 + (i % 40),
                    "memory_percent": 50 + (i % 20),
                    "disk_percent": 60 + (i % 10),
                    "recorded_at": start + timedelta(seconds=i * args.interval_seconds),
                }
            )
    session.bulk_insert_mappings(SystemMetric, rows)
    session.commit()

    durations: list[float] = []
    queries: list[int] = []
    cpu_times: list[float] = []
    peak_kib = 0

    for repeat in range(args.repeats):
        session.execute(TelemetryFeatureWindow.__table__.delete())
        session.commit()

        query_count = 0
        tracemalloc.start()
        began = time.perf_counter()
        cpu_began = time.process_time()
        for device in devices:
            build_pending_windows(session, device, "laptop_windows_v1")
        session.commit()
        elapsed = time.perf_counter() - began
        cpu_elapsed = time.process_time() - cpu_began
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        durations.append(elapsed)
        queries.append(query_count)
        cpu_times.append(cpu_elapsed)
        peak_kib = max(peak_kib, peak // 1024)
        print(f"  run {repeat + 1}: {elapsed * 1000:8.1f} ms  {query_count:6d} queries", flush=True)

    window_rows = session.query(TelemetryFeatureWindow).count()

    print()
    print("=" * 68)
    print(f"feature-window hot path {args.label}".rstrip())
    print("=" * 68)
    print(f"devices              : {args.devices}")
    print(f"samples per device   : {samples_per_device} ({args.interval_seconds}s interval)")
    print(f"rows examined        : {args.devices * samples_per_device}")
    print(f"windows produced     : {window_rows}")
    print(f"median wall clock    : {statistics.median(durations) * 1000:.1f} ms")
    print(f"best wall clock      : {min(durations) * 1000:.1f} ms")
    print(f"median process CPU   : {statistics.median(cpu_times) * 1000:.1f} ms")
    print(f"SQL round trips      : {statistics.median(queries):.0f}")
    print(f"peak python heap     : {peak_kib} KiB")
    print("=" * 68)

    session.close()
    engine.dispose()
    if not args.keep:
        _drop_database()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
