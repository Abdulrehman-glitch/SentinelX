"""CLI simulator for an iPhone running the SentinelX mobile agent."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from dataclasses import dataclass
import json
from pathlib import Path
import random
import signal
from typing import Any
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import httpx
import websockets

try:
    from .simulator_payloads import CATEGORIES, PayloadGenerator, utc_timestamp
except ImportError:
    from simulator_payloads import CATEGORIES, PayloadGenerator, utc_timestamp


DEFAULT_API_BASE = "http://127.0.0.1:8100/api/v1/mobile"
DEFAULT_STATE_FILE = ".simulator_state.json"


@dataclass
class SendStats:
    events_sent: int = 0
    batches_sent: int = 0
    reconnects: int = 0
    alerts_received: int = 0
    errors_received: int = 0


@dataclass
class SimulatorState:
    device_id: str
    device_secret: str
    vendor_identifier: str

    @classmethod
    def load(cls, path: Path) -> "SimulatorState":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            device_id=data["device_id"],
            device_secret=data["device_secret"],
            vendor_identifier=data["vendor_identifier"],
        )

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "device_id": self.device_id,
                    "device_secret": self.device_secret,
                    "vendor_identifier": self.vendor_identifier,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def registration_payload(vendor_identifier: str) -> dict[str, str]:
    return {
        "platform": "ios",
        "device_name": "SentinelX Simulator iPhone",
        "device_model": "iPhone 15",
        "os_version": "iOS 17.5",
        "app_version": "1.0.0",
        "vendor_identifier": vendor_identifier,
        "timezone": "Europe/London",
        "locale": "en_GB",
    }


def event_for_batch(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key != "device_id"}


def make_batch(device_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "device_id": device_id,
        "batch_id": str(uuid4()),
        "sent_at": utc_timestamp(),
        "events": [event_for_batch(event) for event in events],
    }


def websocket_url(api_base: str, device_id: str) -> str:
    parsed = urlparse(api_base)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    path = parsed.path.rstrip("/") + f"/ws/{device_id}"
    return urlunparse((scheme, parsed.netloc, path, "", "", ""))


class DeviceSimulator:
    def __init__(
        self,
        api_base: str,
        state_file: Path,
        seed: int | None = None,
        start_time: datetime | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.state_file = state_file
        self.generator = PayloadGenerator(seed=seed, start_time=start_time)
        self.timeout = timeout
        self.rng = random.Random(seed)
        self._stop = asyncio.Event()

    async def register(self, vendor_identifier: str | None = None) -> SimulatorState:
        vendor = vendor_identifier or f"sentinelx-sim-{uuid4()}"
        async with httpx.AsyncClient(base_url=self.api_base, timeout=self.timeout) as client:
            response = await client.post("/register", json=registration_payload(vendor))
            response.raise_for_status()
            body = response.json()

        state = SimulatorState(
            device_id=body["device_id"],
            device_secret=body["device_secret"],
            vendor_identifier=vendor,
        )
        state.save(self.state_file)
        return state

    async def login(self, state: SimulatorState) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.api_base, timeout=self.timeout) as client:
            response = await client.post(
                "/login",
                json={"device_id": state.device_id, "device_secret": state.device_secret},
            )
            response.raise_for_status()
            return response.json()

    def load_state(self) -> SimulatorState:
        if not self.state_file.exists():
            raise SystemExit(
                f"missing simulator state file {self.state_file}; run with --register first"
            )
        return SimulatorState.load(self.state_file)

    def build_events(self, device_id: str, count: int, start_sequence: int = 0) -> list[dict[str, Any]]:
        return [
            self.generator.make_event(
                CATEGORIES[(start_sequence + index) % len(CATEGORIES)],
                device_id,
                start_sequence + index,
            )
            for index in range(count)
        ]

    async def run_rest(self, state: SimulatorState, burst: int, max_events: int, interval: float) -> SendStats:
        stats = SendStats()
        tokens = await self.login(state)
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        async with httpx.AsyncClient(base_url=self.api_base, timeout=self.timeout, headers=headers) as client:
            if burst > 0:
                events = self.build_events(state.device_id, burst)
                response = await client.post("/batch", json=make_batch(state.device_id, events))
                response.raise_for_status()
                print(json.dumps(response.json(), indent=2))
                stats.events_sent += burst
                stats.batches_sent += 1
                return stats

            for sequence in range(max_events):
                event = self.generator.make_event(CATEGORIES[sequence % len(CATEGORIES)], state.device_id, sequence)
                response = await client.post("/telemetry", json=event)
                response.raise_for_status()
                print(f"sent REST {event['category']} {event['event_id']}")
                stats.events_sent += 1
                await asyncio.sleep(interval)
        return stats

    async def _drain_ws_messages(self, ws: Any, timeout: float = 0.05) -> SendStats:
        stats = SendStats()
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except TimeoutError:
                break
            message = json.loads(raw)
            if message.get("type") == "alert.created":
                stats.alerts_received += 1
            elif message.get("type") == "error":
                stats.errors_received += 1
                print(f"websocket error: {message}")
            elif message.get("type") == "heartbeat.ack":
                continue
            else:
                print(f"websocket received {message.get('type')}")
        return stats

    async def run_websocket(
        self,
        state: SimulatorState,
        burst: int,
        max_events: int | None,
        interval: float,
        heartbeat_interval: float,
        chaos: bool,
    ) -> SendStats:
        sequence = 0
        stats = SendStats()
        while not self._stop.is_set():
            tokens = await self.login(state)
            try:
                async with websockets.connect(websocket_url(self.api_base, state.device_id), open_timeout=self.timeout) as ws:
                    await ws.send(json.dumps({
                        "type": "auth",
                        "access_token": tokens["access_token"],
                        "device_id": state.device_id,
                    }))
                    accepted = json.loads(await asyncio.wait_for(ws.recv(), timeout=self.timeout))
                    if accepted.get("type") != "auth.accepted":
                        raise RuntimeError(f"websocket auth failed: {accepted}")
                    print(f"websocket authenticated as {state.device_id}")

                    sent_since_heartbeat = 0
                    while not self._stop.is_set():
                        remaining = None if max_events is None else max_events - sequence
                        if remaining is not None and remaining <= 0:
                            return stats

                        if burst > 0:
                            count = min(burst, remaining) if remaining is not None else burst
                            events = self.build_events(state.device_id, count, sequence)
                            sequence += count
                            await ws.send(json.dumps({
                                "type": "telemetry.batch",
                                "batch_id": str(uuid4()),
                                "events": events,
                            }))
                            print(f"sent WS batch {count}")
                            stats.events_sent += count
                            stats.batches_sent += 1
                        else:
                            event = self.generator.make_event(
                                CATEGORIES[sequence % len(CATEGORIES)],
                                state.device_id,
                                sequence,
                            )
                            sequence += 1
                            await ws.send(json.dumps({"type": "telemetry.event", "event": event}))
                            print(f"sent WS {event['category']} {event['event_id']}")
                            stats.events_sent += 1

                        sent_since_heartbeat += 1
                        heartbeat_every = max(1, int(heartbeat_interval / max(interval, 0.1)))
                        if sent_since_heartbeat >= heartbeat_every:
                            await ws.send(json.dumps({
                                "type": "heartbeat",
                                "device_id": state.device_id,
                                "timestamp": utc_timestamp(),
                            }))
                            sent_since_heartbeat = 0

                        incoming = await self._drain_ws_messages(ws)
                        stats.alerts_received += incoming.alerts_received
                        stats.errors_received += incoming.errors_received

                        if chaos and self.rng.random() < 0.15:
                            print("chaos: dropping websocket connection")
                            await ws.close()
                            break

                        await asyncio.sleep(interval)
            except (OSError, TimeoutError, websockets.WebSocketException, RuntimeError) as exc:
                print(f"websocket disconnected: {exc}; retrying")
                stats.reconnects += 1
                await asyncio.sleep(2)

            if max_events is not None and sequence >= max_events:
                return stats
        return stats

    async def verify(self, state: SimulatorState) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.api_base, timeout=self.timeout) as client:
            response = await client.get(f"/devices/{state.device_id}")
            response.raise_for_status()
            return response.json()

    def stop(self) -> None:
        self._stop.set()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SentinelX mobile device simulator")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--state-file", type=Path, default=Path(DEFAULT_STATE_FILE))
    parser.add_argument("--register", action="store_true", help="register or re-register the simulator device")
    parser.add_argument("--rest-only", action="store_true", help="send telemetry over REST instead of WebSocket")
    parser.add_argument("--burst", type=int, default=0, help="send N events as one batch")
    parser.add_argument("--chaos", action="store_true", help="randomly drop WebSocket connections")
    parser.add_argument("--max-events", type=int, default=None, help="stop after N telemetry events")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between telemetry sends")
    parser.add_argument("--heartbeat-interval", type=float, default=30.0)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--vendor-identifier", default=None)
    parser.add_argument("--verify", action="store_true", help="fetch dashboard summary after sending")
    return parser


async def async_main(args: argparse.Namespace) -> None:
    simulator = DeviceSimulator(args.api_base, args.state_file, seed=args.seed)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, simulator.stop)
        except NotImplementedError:
            pass

    if args.register:
        state = await simulator.register(args.vendor_identifier)
        print(f"registered {state.device_id}; state saved to {args.state_file}")
        if args.max_events is None and not args.rest_only and args.burst <= 0:
            return
    else:
        state = simulator.load_state()

    max_events = args.max_events if args.max_events is not None else (args.burst if args.burst > 0 else 5)
    if args.rest_only:
        await simulator.run_rest(state, args.burst, max_events, args.interval)
    else:
        await simulator.run_websocket(
            state,
            args.burst,
            max_events,
            args.interval,
            args.heartbeat_interval,
            args.chaos,
        )

    if args.verify:
        print(json.dumps(await simulator.verify(state), indent=2))


def main() -> None:
    asyncio.run(async_main(build_parser().parse_args()))


if __name__ == "__main__":
    main()
