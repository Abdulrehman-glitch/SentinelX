# SentinelX Arduino Nano 33 BLE Sense Rev2 Agent

Collects temperature, humidity, pressure, acceleration, gyroscope, and impact-detection data. Outputs newline-delimited JSON over USB Serial and exposes the same payload as a BLE GATT characteristic.

## Hardware
- **Board:** Arduino Nano 33 BLE Sense Rev2
- **Sensors (on-board):**
  - HTS221 / HS300x — temperature + humidity
  - LPS22HB — barometric pressure
  - BMI270 / BMM150 — 6-axis IMU (accelerometer + gyroscope)

## Required libraries (install via Arduino IDE Library Manager)
| Library | Version |
|---------|---------|
| `Arduino_BMI270_BMM150` | ≥ 1.0 |
| `Arduino_HS300x` | ≥ 1.0 |
| `Arduino_LPS22HB` | ≥ 1.0 |
| `ArduinoBLE` | ≥ 1.3 |

## Configuration
Edit `ble_config.h` before flashing:
- `SAMPLE_INTERVAL_MS` — how often to read and transmit (default: 2 000 ms)
- `IMPACT_G_THRESHOLD` — acceleration magnitude (g) that triggers `impact_detected` (default: 2.5)
- `ENABLE_BLE` — set to `0` to disable BLE and use Serial only

## Wiring
No external wiring required. All sensors are on-board.

## Flashing
1. Open `SentinelXArduinoAgent.ino` in Arduino IDE 2.x.
2. Select board: **Arduino Nano 33 BLE** (via Boards Manager → "Arduino Mbed OS Nano Boards").
3. Select the correct COM/tty port.
4. Click **Upload**.

## Serial output format
Each line is a self-contained JSON object:
```json
{"temperature_c":22.5,"humidity_percent":48.3,"pressure_hpa":1013.25,"accel_x":0.01,"accel_y":-0.02,"accel_z":0.98,"gyro_x":0.1,"gyro_y":-0.1,"gyro_z":0.0,"impact_detected":false}
```

## Bridge scripts
Two bridge scripts in `agents/embedded_bridge/` forward the data to SentinelX:

| Script | Transport |
|--------|-----------|
| `serial_bridge.py` | USB Serial (plug-and-play) |
| `ble_bridge.py` | Bluetooth LE (wireless) |

See `agents/embedded_bridge/README.md` for setup instructions.
