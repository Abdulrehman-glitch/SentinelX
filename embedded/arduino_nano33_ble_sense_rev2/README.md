# SentinelX Arduino Nano 33 BLE Sense Rev2 Agent

This sketch collects onboard sensor data and emits SentinelX-compatible telemetry over USB Serial and Bluetooth LE.

## Hardware

- Board: Arduino Nano 33 BLE Sense Rev2
- Sensors:
  - `Arduino_HS300x`: temperature and humidity
  - `Arduino_LPS22HB`: barometric pressure
  - `Arduino_BMI270_BMM150`: accelerometer and gyroscope
  - `ArduinoBLE`: BLE advertisement and GATT notifications

No external wiring is required.

## Files

| File | Purpose |
|---|---|
| `SentinelXArduinoAgent/SentinelXArduinoAgent.ino` | Main firmware sketch. Reads sensors, serializes JSON, writes Serial and BLE telemetry. |
| `SentinelXArduinoAgent/ble_config.h` | Local configuration for BLE name/UUIDs, sampling rate, serial baud, impact threshold, and feature flags. This is the copy the IDE compiles; `ble_config.h` at this folder's root is a duplicate. |

## Install Arduino Libraries

Install these through Arduino IDE Library Manager:

| Library | Minimum version |
|---|---|
| `Arduino_BMI270_BMM150` | 1.0 |
| `Arduino_HS300x` | 1.0 |
| `Arduino_LPS22HB` | 1.0 |
| `ArduinoBLE` | 1.3 |

Also install the board package:

```text
Arduino Mbed OS Nano Boards
```

## Configure

Edit `SentinelXArduinoAgent/ble_config.h` if needed:

| Setting | Default | Meaning |
|---|---:|---|
| `BLE_DEVICE_NAME` | `SentinelX-Node` | Name scanned by `ble_bridge.py`. |
| `BLE_SERVICE_UUID` | `12345678-1234-1234-1234-123456789abc` | BLE telemetry service UUID. |
| `BLE_CHAR_TELEMETRY` | `12345678-1234-1234-1234-123456789ab0` | BLE telemetry characteristic UUID. |
| `SAMPLE_INTERVAL_MS` | `2000` | Sensor read interval in milliseconds. |
| `SERIAL_BAUD` | `115200` | USB Serial baud rate. |
| `IMPACT_G_THRESHOLD` | `2.5f` | Acceleration magnitude that flags `impact_detected`. |
| `ENABLE_BLE` | `1` | Set to `0` for USB Serial only. |

## Flash

1. Open `SentinelXArduinoAgent/SentinelXArduinoAgent.ino` in Arduino IDE 2.x.
2. Select **Arduino Nano 33 BLE** as the board.
3. Select the board port, for example `COM3`.
4. Click **Upload**.

## Verify Serial Output

Open Arduino Serial Monitor at `115200` baud. You should see one JSON object every two seconds:

```json
{"temperature_c":22.50,"humidity_percent":48.30,"pressure_hpa":1013.25,"accel_x":0.0100,"accel_y":-0.0200,"accel_z":0.9800,"gyro_x":0.100,"gyro_y":-0.100,"gyro_z":0.000,"impact_detected":false}
```

Close Serial Monitor before running `agents/embedded_bridge/serial_bridge.py`.

## Connect To SentinelX

Use the bridge scripts in `agents/embedded_bridge`:

```powershell
cd C:\SentinelX\agents\embedded_bridge
.\.venv\Scripts\Activate.ps1
python serial_bridge.py
```

or:

```powershell
python ble_bridge.py
```

See `embedded/README.md` and `agents/embedded_bridge/README.md` for the full backend/dashboard setup.
