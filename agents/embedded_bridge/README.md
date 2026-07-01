# SentinelX Embedded Bridge

The embedded bridge runs on your laptop/PC and forwards Arduino Nano 33 BLE Sense Rev2 telemetry to the SentinelX backend.

Use one bridge mode:

| File | Transport | Use when |
|---|---|---|
| `serial_bridge.py` | USB Serial | The Arduino is plugged into the host machine. This is the easiest and most reliable mode. |
| `ble_bridge.py` | Bluetooth LE | The Arduino is powered wirelessly and advertising as `SentinelX-Node`. |
| `config.py` | Shared settings | Loads `SENTINELX_*` values from `.env`. |
| `.env.example` | Config template | Copy to `.env` and fill in API URL, device token, device ID, and port/BLE settings. |
| `requirements.txt` | Python dependencies | Install into a bridge virtual environment. |

## Backend Endpoint

Both bridges post JSON readings to:

```text
POST http://127.0.0.1:8000/api/v1/telemetry/embedded
Authorization: Bearer <SENTINELX_DEVICE_TOKEN>
```

The backend derives the organization from the device token. Do not put `organization_id` in Arduino payloads.

## Seeded Demo Values

After `python -m app.db.seed`, the Arduino device is:

```text
Organization: Apex Robotics
Hostname:     arduino-nano-33-ble-01
Device ID:    d0307f8a-8e4c-48b7-b1bc-4024764103b0
```

The raw Apex Arduino device token is printed once by the seed command. Copy that value into `.env` as `SENTINELX_DEVICE_TOKEN`.

## Setup

```powershell
cd C:\SentinelX\agents\embedded_bridge
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Set at least:

```text
SENTINELX_API_BASE_URL=http://127.0.0.1:8000/api/v1
SENTINELX_DEVICE_TOKEN=<raw Apex Arduino token from seed>
SENTINELX_DEVICE_ID=d0307f8a-8e4c-48b7-b1bc-4024764103b0
SENTINELX_SERIAL_PORT=COM3
```

Change `COM3` to the port shown by Arduino IDE.

## Run With USB Serial

Start the backend first:

```powershell
cd C:\SentinelX\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Then start the bridge:

```powershell
cd C:\SentinelX\agents\embedded_bridge
.\.venv\Scripts\Activate.ps1
python serial_bridge.py
```

Override the port if needed:

```powershell
python serial_bridge.py --port COM4
```

## Run With BLE

Flash the Arduino with BLE enabled in `embedded/arduino_nano33_ble_sense_rev2/ble_config.h`, then run:

```powershell
cd C:\SentinelX\agents\embedded_bridge
.\.venv\Scripts\Activate.ps1
python ble_bridge.py
```

Override the advertised device name:

```powershell
python ble_bridge.py --name SentinelX-Node
```

## View Live Data

1. Log in to the dashboard as `ops@apexrobotics.io` or `admin@sentinelx.io`.
2. Open the Arduino device: `arduino-nano-33-ble-01`.
3. Check the embedded telemetry view or device detail panels.
4. Impact, high temperature, and pressure anomaly readings create alerts automatically.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `401 Invalid or revoked device token` | The token in `.env` is missing, old, or not the raw Apex Arduino token from the latest seed. |
| `403 Device token does not match payload device_id` | `SENTINELX_DEVICE_ID` does not match the device linked to the token. |
| Serial port cannot open | Close Arduino Serial Monitor and verify the COM port in Arduino IDE. |
| BLE device not found | Confirm `ENABLE_BLE 1`, board is powered, and `BLE_DEVICE_NAME` matches `.env`. |
| No dashboard data | Confirm backend is running and bridge logs show HTTP `201` responses. |
