# SentinelX Embedded Agent Guide

This folder contains the Arduino firmware for the SentinelX embedded telemetry path.

The live data flow is:

```text
Arduino Nano 33 BLE Sense Rev2
  -> USB Serial or Bluetooth LE
  -> Python bridge in agents/embedded-bridge
  -> FastAPI /api/v1/telemetry/embedded
  -> PostgreSQL
  -> React dashboard device and telemetry views
```

## File Map

| Path | Purpose |
|---|---|
| `arduino_nano33_ble_sense_rev2/SentinelXArduinoAgent/SentinelXArduinoAgent.ino` | Arduino sketch. Reads onboard sensors, builds JSON telemetry, writes it to USB Serial, and publishes it over BLE. |
| `arduino_nano33_ble_sense_rev2/SentinelXArduinoAgent/ble_config.h` | Arduino configuration. Controls BLE name/UUIDs, sample interval, serial baud rate, impact threshold, and sensor enable flags. Edit this copy — it sits in the sketch folder, which is what the Arduino IDE compiles (the copy one level up is a duplicate). |
| `arduino_nano33_ble_sense_rev2/README.md` | Board-specific setup, required Arduino libraries, flashing steps, and payload format. |
| `../agents/embedded-bridge/serial_bridge.py` | Reads one JSON line at a time from the Arduino USB Serial port and posts it to SentinelX. |
| `../agents/embedded-bridge/ble_bridge.py` | Connects to the Arduino BLE characteristic and posts notifications to SentinelX. |
| `../agents/embedded-bridge/config.py` | Loads bridge settings from `../agents/embedded-bridge/.env`. |
| `../agents/embedded-bridge/.env.example` | Template for API URL, device token, device ID, COM port, and BLE UUIDs. |
| `../agents/embedded-bridge/requirements.txt` | Python dependencies for the serial and BLE bridge scripts. |

## Start The Arduino Path

1. Start PostgreSQL and the SentinelX backend.
2. Seed clean demo data:

```powershell
cd C:\SentinelX\backend
.\.venv\Scripts\Activate.ps1
python -m app.db.init_db
python -m app.db.seed
```

3. Copy the raw `Apex Arduino Token` printed by the seed command.
4. Flash the Arduino sketch:

```text
Open embedded/arduino_nano33_ble_sense_rev2/SentinelXArduinoAgent/SentinelXArduinoAgent.ino
Board: Arduino Nano 33 BLE
Port: your Arduino COM/tty port
Upload
```

5. Configure the bridge:

```powershell
cd C:\SentinelX\agents\embedded-bridge
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Use:

```text
SENTINELX_API_BASE_URL=http://127.0.0.1:8000/api/v1
SENTINELX_DEVICE_TOKEN=<raw Apex Arduino Token>
SENTINELX_DEVICE_ID=d0307f8a-8e4c-48b7-b1bc-4024764103b0
SENTINELX_SERIAL_PORT=COM3
```

6. Start one bridge:

```powershell
python serial_bridge.py
```

or:

```powershell
python ble_bridge.py
```

7. Open the dashboard and log in as:

```text
Email:    ops@apexrobotics.io
Password: SentinelX2026!
```

Then open the `arduino-nano-33-ble-01` device. New readings should appear as embedded telemetry, and alert rules will fire for impact, high temperature, or pressure anomaly events.

## Expected Arduino JSON

The Arduino emits newline-delimited JSON like this:

```json
{"temperature_c":22.50,"humidity_percent":48.30,"pressure_hpa":1013.25,"accel_x":0.0100,"accel_y":-0.0200,"accel_z":0.9800,"gyro_x":0.100,"gyro_y":-0.100,"gyro_z":0.000,"impact_detected":false}
```

The bridge adds `device_id` before sending the payload to the backend.

## Notes

- Use USB Serial first. BLE adds Windows/Bluetooth pairing variables and is easier to debug after Serial works.
- Do not use Arduino Serial Monitor while `serial_bridge.py` is running; only one process can own the COM port.
- If you reseed the backend, device IDs and raw device tokens change. Update bridge `.env` after every reseed.
