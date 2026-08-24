"""Run one bounded load scenario and record what it actually cost.

Locust reports request rates and latency percentiles. On its own that is not
enough to say whether SentinelX coped: an API that accepts 500 samples a second
into a queue nothing is draining looks excellent right up until it falls over.
So this samples the server's own view at the same time - queue depth, oldest
pending job, rate-limit backend health - plus process CPU and memory and the
growth of the telemetry tables, and prints them next to the latency numbers.

    python scripts/run_load_profile.py --scenario fleet --users 25 --duration 60

Requires a backend already running (scripts/demo_up.ps1, or uvicorn by hand).
Scenario names are the Locust tags in tests/load/locustfile.py.

Everything here is local and bounded. It creates no cloud resources, writes its
report under docs/Evidence/load/ (gitignored), and refuses to run against a
non-loopback host so a load generator can never be aimed at somebody else's
service by accident.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

SCENARIOS = ("single-agent", "fleet", "batch", "burst", "query", "stream", "console")

# Sampling the health endpoint costs a request; once a second is plenty to see
# a backlog forming and cheap enough not to perturb what it is measuring.
SAMPLE_INTERVAL_SECONDS = 1.0


def _loopback_only(host: str) -> str:
    """Refuse to generate load against anything but this machine.

    Hosting is frozen and there is nothing remote to test, so a non-loopback
    host here is a mistake rather than an intention.
    """
    allowed = ("http://127.0.0.1", "http://localhost", "http://[::1]")
    if not host.startswith(allowed):
        raise SystemExit(
            f"Refusing to load-test {host!r}. This harness is local-only; use http://127.0.0.1:8000."
        )
    return host.rstrip("/")


class HealthSampler(threading.Thread):
    """Polls /health for the duration of the run."""

    def __init__(self, host: str) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.samples: list[dict] = []
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                with urllib.request.urlopen(f"{self.host}/api/v1/health", timeout=5) as response:
                    body = json.loads(response.read())
                queue = body.get("queue", {})
                self.samples.append(
                    {
                        "t": time.time(),
                        "queue_status": queue.get("status"),
                        "backlog": queue.get("backlog"),
                        "pending": queue.get("pending"),
                        "failed": queue.get("failed"),
                        "dead": queue.get("dead"),
                        "oldest_pending_age_seconds": queue.get("oldest_pending_age_seconds"),
                        "rate_limit_status": (body.get("rate_limiting") or {}).get("status"),
                        "degraded": body.get("degraded"),
                        "ready": body.get("ready"),
                    }
                )
            except (urllib.error.URLError, OSError, ValueError):
                self.samples.append({"t": time.time(), "queue_status": "unreachable"})
            self._stop_event.wait(SAMPLE_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._stop_event.set()


class ProcessSampler(threading.Thread):
    """CPU and RSS for the API and worker processes, if psutil can find them."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.samples: list[dict] = []
        self._stop_event = threading.Event()
        try:
            import psutil  # noqa: F401

            self.available = True
        except ImportError:
            self.available = False

    def _sentinelx_processes(self) -> list:
        import psutil

        found = []
        for process in psutil.process_iter(["name", "cmdline"]):
            try:
                cmdline = " ".join(process.info.get("cmdline") or [])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if "app.main:app" in cmdline or "app.worker" in cmdline:
                found.append(process)
        return found

    def run(self) -> None:
        if not self.available:
            return
        import psutil

        processes = self._sentinelx_processes()
        for process in processes:
            try:
                process.cpu_percent(None)  # prime the counter
            except psutil.Error:
                pass

        while not self._stop_event.is_set():
            total_cpu = 0.0
            total_rss = 0
            alive = 0
            for process in processes:
                try:
                    total_cpu += process.cpu_percent(None)
                    total_rss += process.memory_info().rss
                    alive += 1
                except psutil.Error:
                    continue
            if alive:
                self.samples.append(
                    {"t": time.time(), "cpu_percent": total_cpu, "rss_mb": total_rss / 1_048_576}
                )
            self._stop_event.wait(SAMPLE_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._stop_event.set()


def _table_sizes() -> dict:
    """Row counts and on-disk size of the tables a load run actually grows."""
    from sqlalchemy import text

    from app.db.session import engine

    tables = (
        "system_metrics",
        "metric_points",
        "metric_series",
        "resources",
        "outbox_jobs",
        "domain_events",
        "rate_limit_counters",
    )
    result: dict = {}
    with engine.connect() as conn:
        for table in tables:
            try:
                rows = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                size = conn.execute(
                    text("SELECT pg_total_relation_size(:t)"), {"t": table}
                ).scalar_one()
                result[table] = {"rows": int(rows), "bytes": int(size)}
            except Exception:
                result[table] = {"rows": None, "bytes": None}
    return result


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(int(round(fraction * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS, default="fleet")
    parser.add_argument("--host", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--spawn-rate", type=float, default=5)
    parser.add_argument("--duration", type=int, default=60, help="seconds")
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Compress the simulated agent reporting interval, in seconds. "
        "A 60s cadence over a 45s run produces about one sample per device and "
        "measures nothing; the value used is recorded in the report.",
    )
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    host = _loopback_only(args.host)

    # Guardrails for the owner's laptop. Not arbitrary: 200 concurrent users
    # and five minutes is already far beyond anything this project's fleet will
    # be, and past it a load run stops being a measurement and becomes a way to
    # fill a disk.
    if args.users > 200:
        raise SystemExit("Refusing more than 200 users on a development laptop.")
    if args.duration > 300:
        raise SystemExit("Refusing a run longer than 300 seconds.")

    print(f"scenario={args.scenario} users={args.users} duration={args.duration}s host={host}")

    before = _table_sizes()
    health = HealthSampler(host)
    processes = ProcessSampler()
    health.start()
    processes.start()

    csv_prefix = REPO / "docs" / "Evidence" / "load" / f"{args.scenario}-{int(time.time())}"
    csv_prefix.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(REPO / "tests" / "load" / "locustfile.py"),
        "--host",
        host,
        "--headless",
        "-u",
        str(args.users),
        "-r",
        str(args.spawn_rate),
        "-t",
        f"{args.duration}s",
        "--tags",
        args.scenario,
        "--csv",
        str(csv_prefix),
        "--only-summary",
    ]

    status_file = Path(f"{csv_prefix}_status.json")
    environment = dict(os.environ)
    environment["SENTINELX_LOAD_STATUS_FILE"] = str(status_file)
    if args.interval is not None:
        environment["SENTINELX_LOAD_INTERVAL"] = str(args.interval)

    began = time.time()
    completed = subprocess.run(
        command, cwd=str(REPO), capture_output=True, text=True, env=environment
    )
    elapsed = time.time() - began

    health.stop()
    processes.stop()
    health.join(timeout=5)
    processes.join(timeout=5)

    after = _table_sizes()

    backlogs = [s["backlog"] for s in health.samples if isinstance(s.get("backlog"), int)]
    ages = [
        s["oldest_pending_age_seconds"]
        for s in health.samples
        if isinstance(s.get("oldest_pending_age_seconds"), (int, float))
    ]
    cpus = [s["cpu_percent"] for s in processes.samples]
    rss = [s["rss_mb"] for s in processes.samples]

    status_counts: dict[str, int] = {}
    if status_file.exists():
        try:
            status_counts = json.loads(status_file.read_text(encoding="utf-8"))
        except ValueError:
            status_counts = {}
    total_responses = sum(status_counts.values())
    shed = sum(count for code, count in status_counts.items() if code in ("429", "503"))

    stats_csv = Path(f"{csv_prefix}_stats.csv")
    locust_summary = stats_csv.read_text(encoding="utf-8") if stats_csv.exists() else ""

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": args.scenario,
        "users": args.users,
        "duration_seconds": args.duration,
        "simulated_agent_interval_seconds": args.interval,
        "wall_clock_seconds": round(elapsed, 1),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "processor": platform.processor(),
        },
        "queue": {
            "max_backlog": max(backlogs) if backlogs else None,
            "final_backlog": backlogs[-1] if backlogs else None,
            "max_oldest_pending_age_seconds": max(ages) if ages else None,
            "ever_degraded": any(s.get("degraded") for s in health.samples),
            "ever_shedding": any(s.get("queue_status") == "shedding" for s in health.samples),
            "ever_unready": any(s.get("ready") is False for s in health.samples),
            "rate_limit_statuses": sorted(
                {s.get("rate_limit_status") for s in health.samples if s.get("rate_limit_status")}
            ),
        },
        "process": {
            "psutil_available": processes.available,
            "peak_cpu_percent": round(max(cpus), 1) if cpus else None,
            "median_cpu_percent": round(_percentile(cpus, 0.5) or 0, 1) if cpus else None,
            "peak_rss_mb": round(max(rss), 1) if rss else None,
        },
        "storage_growth": {
            table: {
                "rows_added": (after[table]["rows"] or 0) - (before[table]["rows"] or 0),
                "bytes_added": (after[table]["bytes"] or 0) - (before[table]["bytes"] or 0),
            }
            for table in before
        },
        "responses": {
            "by_status": status_counts,
            "total": total_responses,
            # Deliberate backpressure, not errors - but a run that shed most of
            # its traffic must not read as a clean one.
            "rejected_429_503": shed,
            "rejection_rate": round(shed / total_responses, 4) if total_responses else None,
        },
        "locust_stats_csv": locust_summary,
        "locust_returncode": completed.returncode,
    }

    out = Path(args.out) if args.out else Path(f"{csv_prefix}_report.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print("=" * 72)
    print(f"scenario: {args.scenario}   users: {args.users}   {args.duration}s")
    print("=" * 72)
    if locust_summary:
        print(locust_summary.strip())
    print()
    print(f"responses by status      : {status_counts or 'n/a'}")
    print(
        f"rejected (429/503)       : {shed}"
        + (f"  ({report['responses']['rejection_rate']:.1%})" if total_responses else "")
    )
    print(f"max queue backlog        : {report['queue']['max_backlog']}")
    print(f"max oldest pending age   : {report['queue']['max_oldest_pending_age_seconds']} s")
    print(
        f"ever degraded / shedding : {report['queue']['ever_degraded']} / "
        f"{report['queue']['ever_shedding']}"
    )
    print(f"rate limit backend       : {', '.join(report['queue']['rate_limit_statuses']) or 'n/a'}")
    print(f"peak CPU (api+worker)    : {report['process']['peak_cpu_percent']}%")
    print(f"peak RSS (api+worker)    : {report['process']['peak_rss_mb']} MB")
    for table, growth in report["storage_growth"].items():
        if growth["rows_added"]:
            per_row = growth["bytes_added"] / growth["rows_added"]
            print(
                f"  {table:<22} +{growth['rows_added']:>7} rows  "
                f"+{growth['bytes_added'] / 1024:>8.1f} KiB  ({per_row:.0f} B/row)"
            )
    print(f"\nreport: {out}")

    if completed.returncode != 0:
        print("\nlocust stderr:\n" + completed.stderr[-2000:], file=sys.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
