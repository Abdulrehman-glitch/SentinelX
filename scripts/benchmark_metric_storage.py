#!/usr/bin/env python3
"""Measure the canonical metric store before making claims about it.

Bounded and reproducible on purpose. It builds a throwaway database, fills it
with a fixed number of synthetic points, runs EXPLAIN (ANALYZE, BUFFERS) on the
queries the product actually issues, and prints the numbers. Nothing here is
open-ended, nothing runs against a real database, and the whole thing finishes
in well under a minute on a laptop.

    python scripts/benchmark_metric_storage.py [--points 500000] [--series 200]

The output is what docs/adr/0010-postgresql-telemetry-storage.md cites. Re-run
it rather than trusting the numbers in that file if the hardware differs.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

BENCH_DB = "sentinelx_bench"


def _base_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    for line in (BACKEND / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("DATABASE_URL not set and not found in backend/.env")


def _recreate_database(base: str) -> str:
    import psycopg

    admin = base.replace("postgresql+psycopg", "postgresql").rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {BENCH_DB}")
        conn.execute(f"CREATE DATABASE {BENCH_DB}")
    return base.rsplit("/", 1)[0] + "/" + BENCH_DB


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points", type=int, default=500_000)
    parser.add_argument("--series", type=int, default=200)
    parser.add_argument("--batch", type=int, default=5_000)
    args = parser.parse_args()

    bench_url = _recreate_database(_base_url())
    os.environ["DATABASE_URL"] = bench_url

    from sqlalchemy import create_engine, text

    import app.models  # noqa: F401  (registers every table)
    from app.db.base import Base

    engine = create_engine(bench_url)
    Base.metadata.create_all(engine)

    print("=" * 74)
    print("SentinelX canonical metric store — local benchmark")
    print("=" * 74)
    print(f"host      : {platform.processor() or platform.machine()} / {platform.system()}")
    print(f"python    : {platform.python_version()}")
    with engine.connect() as conn:
        print(f"postgres  : {conn.execute(text('SHOW server_version')).scalar()}")
    print(f"points    : {args.points:,} across {args.series} series")
    print()

    org_id, resource_id = uuid.uuid4(), uuid.uuid4()
    series_ids = [uuid.uuid4() for _ in range(args.series)]

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO organizations (id, name, slug, plan, is_active) "
                "VALUES (:id, 'Bench', 'bench', 'professional', true)"
            ),
            {"id": org_id},
        )
        conn.execute(
            text(
                "INSERT INTO resources (id, organization_id, resource_type, identity_hash, "
                "collision_seq, identifying_attributes, attributes) "
                "VALUES (:id, :org, 'host', :h, 0, '{}'::jsonb, '{}'::jsonb)"
            ),
            {"id": resource_id, "org": org_id, "h": "b" * 64},
        )
        for i, sid in enumerate(series_ids):
            conn.execute(
                text(
                    "INSERT INTO metric_series (id, organization_id, resource_id, metric_name, "
                    "metric_unit, metric_kind, attributes, series_hash, collision_seq, source) "
                    "VALUES (:id, :org, :res, :name, '%', 'gauge', '{}'::jsonb, :h, 0, "
                    "'sentinelx_agent')"
                ),
                {
                    "id": sid,
                    "org": org_id,
                    "res": resource_id,
                    "name": f"bench.metric.{i % 20}",
                    "h": f"{i:064d}",
                },
            )

    # ── ingest ────────────────────────────────────────────────────────────
    print("-- insert throughput ------------------------------------------------")
    inserted, started = 0, time.perf_counter()
    batch_latencies: list[float] = []

    while inserted < args.points:
        size = min(args.batch, args.points - inserted)
        rows = []
        for n in range(size):
            idx = inserted + n
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "org": str(org_id),
                    "sid": str(series_ids[idx % args.series]),
                    "v": float(idx % 100),
                    # Spread over ~30 days so the timestamp distribution
                    # resembles real retained history rather than one instant.
                    "off": idx * 5,
                }
            )
        batch_started = time.perf_counter()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO metric_points "
                    "(id, recorded_at, organization_id, series_id, value, ingested_at) "
                    "VALUES (:id, now() - make_interval(secs => :off), :org, :sid, :v, now())"
                ),
                rows,
            )
        batch_latencies.append((time.perf_counter() - batch_started) * 1000)
        inserted += size

    elapsed = time.perf_counter() - started
    batch_latencies.sort()

    def pct(p: float) -> float:
        return batch_latencies[min(len(batch_latencies) - 1, int(len(batch_latencies) * p))]

    print(f"  inserted            : {inserted:,} points in {elapsed:.1f}s")
    print(f"  throughput          : {inserted / elapsed:,.0f} points/sec")
    print(f"  batch size          : {args.batch:,}")
    print(f"  batch latency p50   : {pct(0.50):.1f} ms")
    print(f"  batch latency p95   : {pct(0.95):.1f} ms")
    print(f"  batch latency p99   : {pct(0.99):.1f} ms")
    print()

    with engine.begin() as conn:
        conn.execute(text("ANALYZE metric_points"))

    # ── storage ───────────────────────────────────────────────────────────
    print("-- storage ----------------------------------------------------------")
    with engine.connect() as conn:
        table = conn.execute(text("SELECT pg_table_size('metric_points')")).scalar()
        indexes = conn.execute(text("SELECT pg_indexes_size('metric_points')")).scalar()
        brin = conn.execute(
            text("SELECT pg_relation_size('ix_metric_points_recorded_at_brin')")
        ).scalar()
        btree = conn.execute(
            text("SELECT pg_relation_size('ix_metric_points_series_time')")
        ).scalar()

    mib = 1024 * 1024
    print(f"  heap                : {table / mib:.1f} MiB ({table / inserted:.0f} bytes/point)")
    print(f"  all indexes         : {indexes / mib:.1f} MiB")
    print(f"  BRIN(recorded_at)   : {brin / 1024:.0f} KiB")
    print(f"  B-tree(series,time) : {btree / mib:.1f} MiB")
    print(f"  BRIN vs B-tree      : {btree / max(brin, 1):.0f}x smaller")
    print()

    # ── query plans ───────────────────────────────────────────────────────
    print("-- query plans (EXPLAIN ANALYZE, BUFFERS) ---------------------------")
    queries = {
        "one series, last hour (the dashboard query)": (
            "SELECT recorded_at, value FROM metric_points "
            "WHERE series_id = :sid AND recorded_at >= now() - interval '1 hour' "
            "ORDER BY recorded_at DESC LIMIT 500"
        ),
        "one series, 5-minute buckets over 24h (downsampled chart)": (
            "SELECT date_bin('5 minutes', recorded_at, now()) AS bucket, "
            "avg(value), min(value), max(value), count(*) "
            "FROM metric_points "
            "WHERE series_id = :sid AND recorded_at >= now() - interval '24 hours' "
            "GROUP BY bucket ORDER BY bucket"
        ),
        "whole tenant, 7-day scan (retention / export)": (
            "SELECT count(*), avg(value) FROM metric_points "
            "WHERE organization_id = :org AND recorded_at >= now() - interval '7 days'"
        ),
    }

    for label, sql in queries.items():
        with engine.connect() as conn:
            plan = conn.execute(
                text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}"),
                {"sid": series_ids[0], "org": org_id},
            ).fetchall()
        print(f"\n  {label}")
        for row in plan:
            print(f"    {row[0]}")

    print()
    print("=" * 74)
    print(f"Benchmark database `{BENCH_DB}` left in place for inspection.")
    print("Drop it with:  DROP DATABASE sentinelx_bench;")
    print("=" * 74)


if __name__ == "__main__":
    main()
