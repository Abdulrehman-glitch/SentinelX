# SentinelX Embedded Bridge

Two lightweight Python scripts that forward Arduino Nano 33 BLE Sense Rev2
telemetry to the SentinelX backend.

| Script | Transport | When to use |
|--------|-----------|-------------|
| `serial_bridge.py` | USB Serial | Board is physically connected to the host machine |
| `ble_bridge.py` | Bluetooth LE | Board is wireless / cable-free |

## Prerequisites

**Python 3.11+** and the dependencies below:

```bash
pip install httpx pyserial pydantic-settings bleak
```

(`bleak` is only required for `ble_bridge.py`.)

## Setup

1. **Create a device token** in SentinelX (Fleet Setup → Device Credentials → New token).  
   Copy the raw token value — it is only shown once.

2. **Find the device UUID** on the Devices page in SentinelX (or from the admin seed data).

3. Copy `.env.example` to `.env` and fill in the values:

   ```bash
   cp .env.example .env
   # edit .env with your token, device ID, and port
   ```

## Running the Serial bridge

```bash
# Uses port from .env (SENTINELX_SERIAL_PORT)
python serial_bridge.py

# Or override:
python serial_bridge.py --port COM4
```

The bridge opens the USB serial port, reads one JSON line per sensor cycle, and
POSTs it to `/api/v1/telemetry/embedded`.

## Running the BLE bridge

```bash
python ble_bridge.py

# Override the BLE device name if needed:
python ble_bridge.py --name "SentinelX-Node"
```

The bridge continuously scans for a BLE peripheral advertising the configured
`BLE_DEVICE_NAME`, connects, subscribes to the telemetry GATT characteristic,
and forwards notifications to SentinelX. It reconnects automatically if the
connection drops.

## Viewing data in the console

Navigate to **Fleet → (select the Arduino device) → Embedded Telemetry** to see
the live sensor readings, impact events, and auto-generated alerts.
