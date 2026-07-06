"""One-command demo and soak runner for the mobile API dev server."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse, urlunparse

import httpx

from .device_simulator import DEFAULT_API_BASE, DeviceSimulator, SendStats, SimulatorState


DEFAULT_PORT = 8100
DEFAULT_STATE_FILE = Path(__file__).resolve().parents[1] / ".simulator_state.json"


@dataclass
class DemoResult:
    device_id: str
    events_sent: int
    stored_events: int
    alerts_fired: int
    reconnects: int


def health_url(api_base: str) -> str:
    parsed = urlparse(api_base)
    return urlunparse((parsed.scheme, parsed.netloc, "/healthz", "", "", ""))


def server_dir() -> Path:
    return Path(__file__).resolve().parents[1]


async def is_server_healthy(api_base: str, timeout: float = 1.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(health_url(api_base))
            return response.status_code == 200 and response.json().get("status") == "ok"
    except (httpx.HTTPError, ValueError):
        return False


async def wait_for_server(api_base: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await is_server_healthy(api_base):
            return
        await asyncio.sleep(0.25)
    raise RuntimeError(f"dev server did not become healthy at {health_url(api_base)}")


def start_dev_server(api_base: str) -> subprocess.Popen:
    parsed = urlparse(api_base)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or DEFAULT_PORT
    db_path = server_dir() / "sentinelx_mobile_dev.db"
    env = os.environ.copy()
    env.setdefault("SENTINELX_MOBILE_DB", str(db_path))
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=server_dir(),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def telemetry_total(api_base: str, device_id: str) -> int:
    async with httpx.AsyncClient(base_url=api_base, timeout=10.0) as client:
        response = await client.get(f"/devices/{device_id}/telemetry", params={"limit": 1})
        response.raise_for_status()
        return int(response.json()["total"])


async def alert_count(api_base: str, device_id: str) -> int:
    async with httpx.AsyncClient(base_url=api_base, timeout=10.0) as client:
        response = await client.get(f"/devices/{device_id}/alerts")
        response.raise_for_status()
        return len(response.json()["items"])


class DemoRunner:
    def __init__(
        self,
        api_base: str = DEFAULT_API_BASE,
        state_file: Path = DEFAULT_STATE_FILE,
        seed: int | None = 42,
        interval: float = 1.0,
        simulator_cls: type[DeviceSimulator] = DeviceSimulator,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.state_file = state_file
        self.seed = seed
        self.interval = interval
        self.simulator_cls = simulator_cls

    async def state(self, simulator: DeviceSimulator) -> SimulatorState:
        if self.state_file.exists():
            return simulator.load_state()
        return await simulator.register("sentinelx-demo-device")

    async def run(self, duration_seconds: float, chaos: bool = False) -> DemoResult:
        simulator = self.simulator_cls(
            self.api_base,
            self.state_file,
            seed=self.seed,
            start_time=datetime.now(UTC),
        )
        state = await self.state(simulator)
        before_events = await telemetry_total(self.api_base, state.device_id)
        before_alerts = await alert_count(self.api_base, state.device_id)
        max_events = max(1, int(duration_seconds / max(self.interval, 0.1)))

        stats: SendStats = await simulator.run_websocket(
            state=state,
            burst=0,
            max_events=max_events,
            interval=self.interval,
            heartbeat_interval=30.0,
            chaos=chaos,
        )

        after_events = await telemetry_total(self.api_base, state.device_id)
        after_alerts = await alert_count(self.api_base, state.device_id)
        stored_delta = after_events - before_events
        alert_delta = after_alerts - before_alerts
        print(
            f"\rdevice={state.device_id} events_sent={stats.events_sent} "
            f"stored={stored_delta} alerts={alert_delta} reconnects={stats.reconnects}"
        )
        if stored_delta < stats.events_sent:
            raise RuntimeError(
                f"demo stored {stored_delta} events but sent {stats.events_sent}"
            )
        return DemoResult(
            device_id=state.device_id,
            events_sent=stats.events_sent,
            stored_events=stored_delta,
            alerts_fired=alert_delta,
            reconnects=stats.reconnects,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the SentinelX mobile API demo")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--duration", type=float, default=120.0, help="demo duration in seconds")
    parser.add_argument("--soak", type=float, default=None, help="run for N minutes instead of --duration")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between generated events")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--chaos", action="store_true", help="randomly reconnect while streaming")
    return parser


async def async_main(args: argparse.Namespace) -> None:
    process: subprocess.Popen | None = None
    if await is_server_healthy(args.api_base):
        print(f"dev server already healthy at {health_url(args.api_base)}")
    else:
        process = start_dev_server(args.api_base)
        await wait_for_server(args.api_base)
        print(f"started dev server at {health_url(args.api_base)}")

    try:
        duration = (args.soak * 60.0) if args.soak is not None else args.duration
        result = await DemoRunner(
            api_base=args.api_base,
            state_file=args.state_file,
            seed=args.seed,
            interval=args.interval,
        ).run(duration_seconds=duration, chaos=args.chaos)
        print(
            f"demo ok: device={result.device_id} events={result.events_sent} "
            f"stored={result.stored_events} alerts={result.alerts_fired} "
            f"reconnects={result.reconnects}"
        )
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main() -> None:
    asyncio.run(async_main(build_parser().parse_args()))


if __name__ == "__main__":
    main()
