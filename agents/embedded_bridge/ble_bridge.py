"""
SentinelX BLE Bridge
====================
Connects to the Arduino Nano 33 BLE Sense Rev2 over Bluetooth LE, reads the
telemetry GATT characteristic, and forwards each reading to the SentinelX
embedded-telemetry endpoint.

Requires:
    pip install bleak httpx

Usage:
    python ble_bridge.py [--name SentinelX-Node]

The bridge authenticates as the Arduino device using a device bearer token
(SENTINELX_DEVICE_TOKEN) set in .env or as an environment variable.
"""

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

import httpx
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

from config import get_settings

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("ble_bridge")

ENDPOINT = f"{settings.api_base_url.rstrip('/')}/telemetry/embedded"
HEADERS = {
    "Authorization": f"Bearer {settings.device_token}",
    "Content-Type": "application/json",
}


async def post_telemetry(payload: dict[str, Any]) -> None:
    payload["device_id"] = settings.device_id
    try:
        async with httpx.AsyncClient(timeout=settings.post_timeout) as client:
            r = await client.post(ENDPOINT, json=payload, headers=HEADERS)
        if r.status_code in (200, 201):
            log.debug("POST ok — status %s", r.status_code)
        else:
            log.warning("POST %s → %s %s", ENDPOINT, r.status_code, r.text[:200])
    except httpx.RequestError as exc:
        log.error("Network error: %s", exc)


def notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray) -> None:
    line = data.decode("utf-8", errors="replace").strip()
    if not line:
        return
    log.info("BLE ← %s", line[:120])
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        log.debug("Non-JSON BLE packet skipped")
        return
    asyncio.ensure_future(post_telemetry(payload))


async def find_device(target_name: str) -> str | None:
    log.info("Scanning for BLE device '%s' (timeout %.1fs)…", target_name, settings.ble_scan_timeout)
    devices = await BleakScanner.discover(timeout=settings.ble_scan_timeout)
    for d in devices:
        if d.name and target_name.lower() in d.name.lower():
            log.info("Found: %s (%s)", d.name, d.address)
            return d.address
    return None


async def run_ble(target_name: str) -> None:
    log.info("BLE Bridge — device_id=%s  endpoint=%s", settings.device_id, ENDPOINT)

    while True:
        address = await find_device(target_name)
        if address is None:
            log.warning("Device not found, retrying in 10 s…")
            await asyncio.sleep(10)
            continue

        try:
            async with BleakClient(address) as client:
                log.info("Connected to %s", address)
                await client.start_notify(settings.ble_char_uuid, notification_handler)
                log.info("Subscribed to characteristic %s — listening…", settings.ble_char_uuid)
                # Keep the connection alive until it drops
                while client.is_connected:
                    await asyncio.sleep(1)
                log.warning("Disconnected from %s", address)
        except Exception as exc:
            log.error("BLE error: %s — reconnecting in 5 s", exc)
            await asyncio.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(description="SentinelX BLE bridge")
    parser.add_argument("--name", default=settings.ble_device_name)
    args = parser.parse_args()

    try:
        asyncio.run(run_ble(args.name))
    except KeyboardInterrupt:
        log.info("Stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
