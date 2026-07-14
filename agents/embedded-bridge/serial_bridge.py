"""
SentinelX Serial Bridge
=======================
Reads newline-delimited JSON from the Arduino Nano 33 BLE Sense Rev2 over USB
Serial and forwards each reading to the SentinelX embedded-telemetry endpoint.

Usage:
    python serial_bridge.py [--port COM3] [--baud 115200]

The bridge authenticates as the Arduino device using a device bearer token
(SENTINELX_DEVICE_TOKEN) set in .env or as an environment variable.
"""

import argparse
import json
import logging
import sys
import time
from typing import Any

import httpx
import serial

from config import get_settings

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("serial_bridge")

ENDPOINT = f"{settings.api_base_url.rstrip('/')}/telemetry/embedded"
HEADERS = {
    "Authorization": f"Bearer {settings.device_token}",
    "Content-Type": "application/json",
}


def post_telemetry(payload: dict[str, Any]) -> None:
    payload["device_id"] = settings.device_id
    try:
        with httpx.Client(timeout=settings.post_timeout) as client:
            r = client.post(ENDPOINT, json=payload, headers=HEADERS)
        if r.status_code in (200, 201):
            log.debug("POST ok — status %s", r.status_code)
        else:
            log.warning("POST %s → %s %s", ENDPOINT, r.status_code, r.text[:200])
    except httpx.RequestError as exc:
        log.error("Network error: %s", exc)


def run(port: str, baud: int) -> None:
    log.info("Opening serial port %s @ %d baud", port, baud)
    try:
        ser = serial.Serial(port, baud, timeout=settings.serial_timeout)
    except serial.SerialException as exc:
        log.critical("Cannot open serial port: %s", exc)
        sys.exit(1)

    log.info("Bridge running — device_id=%s  endpoint=%s", settings.device_id, ENDPOINT)
    consecutive_errors = 0

    while True:
        try:
            raw = ser.readline()
        except serial.SerialException as exc:
            log.error("Serial read error: %s", exc)
            time.sleep(2)
            continue

        if not raw:
            continue  # timeout with no data

        line = raw.decode("utf-8", errors="replace").strip()
        if not line or line.startswith("//"):
            continue

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            log.debug("Non-JSON line skipped: %r", line[:80])
            continue

        log.info("→ %s", line[:120])
        post_telemetry(payload)
        consecutive_errors = 0


def main() -> None:
    parser = argparse.ArgumentParser(description="SentinelX USB Serial bridge")
    parser.add_argument("--port", default=settings.serial_port)
    parser.add_argument("--baud", type=int, default=settings.serial_baud)
    args = parser.parse_args()
    run(args.port, args.baud)


if __name__ == "__main__":
    main()
