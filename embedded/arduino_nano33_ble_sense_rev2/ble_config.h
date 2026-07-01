/*
 * SentinelX — BLE configuration for Arduino Nano 33 BLE Sense Rev2
 * Adjust these constants to match your deployment.
 */

#pragma once

// ── BLE identity ──────────────────────────────────────────────
#define BLE_DEVICE_NAME     "SentinelX-Node"
#define BLE_SERVICE_UUID    "12345678-1234-1234-1234-123456789abc"
#define BLE_CHAR_TELEMETRY  "12345678-1234-1234-1234-123456789ab0"

// Manufacturer ID embedded in advertisement packets (arbitrary; must match bridge)
#define MANUFACTURER_ID     0x05AB

// ── Sampling & transmission ───────────────────────────────────
#define SAMPLE_INTERVAL_MS  2000    // time between sensor reads
#define SERIAL_BAUD         115200  // USB serial baud rate

// ── Impact detection ─────────────────────────────────────────
// Magnitude threshold (g) above which an impact event is flagged
#define IMPACT_G_THRESHOLD  2.5f

// ── Sensor enable flags ───────────────────────────────────────
#define ENABLE_IMU          1
#define ENABLE_HTS          1   // temperature + humidity (HTS221 / HS300x)
#define ENABLE_BARO         1   // barometric pressure (LPS22HB)
#define ENABLE_BLE          1   // broadcast via BLE in addition to Serial
