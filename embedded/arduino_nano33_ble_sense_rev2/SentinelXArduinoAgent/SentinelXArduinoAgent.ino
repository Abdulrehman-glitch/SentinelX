/*
 * SentinelX Arduino Agent — Nano 33 BLE Sense Rev2
 *
 * Sensors used:
 *   Arduino_BMI270_BMM150  — IMU (accelerometer + gyroscope)
 *   Arduino_HS300x         — temperature (°C) + humidity (%)
 *   Arduino_LPS22HB        — barometric pressure (hPa)
 *   ArduinoBLE             — BLE advertisement + GATT characteristic
 *
 * Output:
 *   USB Serial → newline-delimited JSON  (consumed by serial_bridge.py)
 *   BLE GATT characteristic              (consumed by ble_bridge.py)
 *
 * JSON schema (matches SentinelX EmbeddedTelemetryCreate):
 *   {
 *     "temperature_c":   float,
 *     "humidity_percent": float,
 *     "pressure_hpa":    float,
 *     "accel_x":         float,  // g
 *     "accel_y":         float,
 *     "accel_z":         float,
 *     "gyro_x":          float,  // dps
 *     "gyro_y":          float,
 *     "gyro_z":          float,
 *     "impact_detected": bool,
 *     "raw_payload":     string  // optional free-form
 *   }
 */

#include "ble_config.h"
#include <Arduino_BMI270_BMM150.h>
#include <Arduino_HS300x.h>
#include <Arduino_LPS22HB.h>
#include <ArduinoBLE.h>
#include <math.h>

// ── BLE objects ──────────────────────────────────────────────
BLEService           telemetryService(BLE_SERVICE_UUID);
BLEStringCharacteristic telemetryChar(BLE_CHAR_TELEMETRY, BLERead | BLENotify, 256);

// ── State ─────────────────────────────────────────────────────
unsigned long lastSampleMs = 0;

// ── Helpers ───────────────────────────────────────────────────

static float imuMagnitude(float x, float y, float z) {
  return sqrtf(x * x + y * y + z * z);
}

// Serialise one telemetry frame to a JSON string.
static String buildJson(float temp, float hum, float pres,
                        float ax, float ay, float az,
                        float gx, float gy, float gz,
                        bool impact) {
  String j = "{";
  j += "\"temperature_c\":"   + String(temp,  2) + ",";
  j += "\"humidity_percent\":" + String(hum,  2) + ",";
  j += "\"pressure_hpa\":"    + String(pres,  2) + ",";
  j += "\"accel_x\":"         + String(ax,    4) + ",";
  j += "\"accel_y\":"         + String(ay,    4) + ",";
  j += "\"accel_z\":"         + String(az,    4) + ",";
  j += "\"gyro_x\":"          + String(gx,    3) + ",";
  j += "\"gyro_y\":"          + String(gy,    3) + ",";
  j += "\"gyro_z\":"          + String(gz,    3) + ",";
  j += "\"impact_detected\":"; j += impact ? "true" : "false";
  j += "}";
  return j;
}

// ── setup ─────────────────────────────────────────────────────

void setup() {
  Serial.begin(SERIAL_BAUD);
  while (!Serial && millis() < 3000) {}   // wait for host up to 3 s

  // IMU
#if ENABLE_IMU
  if (!IMU.begin()) {
    Serial.println("{\"error\":\"IMU init failed\"}");
  }
#endif

  // Temperature + Humidity
#if ENABLE_HTS
  if (!HS300x.begin()) {
    Serial.println("{\"error\":\"HTS init failed\"}");
  }
#endif

  // Barometer
#if ENABLE_BARO
  if (!BARO.begin()) {
    Serial.println("{\"error\":\"BARO init failed\"}");
  }
#endif

  // BLE
#if ENABLE_BLE
  if (!BLE.begin()) {
    Serial.println("{\"error\":\"BLE init failed\"}");
  } else {
    BLE.setLocalName(BLE_DEVICE_NAME);
    BLE.setAdvertisedService(telemetryService);
    telemetryService.addCharacteristic(telemetryChar);
    BLE.addService(telemetryService);
    BLE.advertise();
  }
#endif
}

// ── loop ──────────────────────────────────────────────────────

void loop() {
  unsigned long now = millis();
  if (now - lastSampleMs < SAMPLE_INTERVAL_MS) {
#if ENABLE_BLE
    BLE.poll();
#endif
    return;
  }
  lastSampleMs = now;

  // ── Read sensors ─────────────────────────────────────────
  float ax = 0, ay = 0, az = 0;
  float gx = 0, gy = 0, gz = 0;
  float temp = 0, hum = 0, pres = 0;
  bool impact = false;

#if ENABLE_IMU
  if (IMU.accelerationAvailable()) {
    IMU.readAcceleration(ax, ay, az);
    impact = (imuMagnitude(ax, ay, az) > IMPACT_G_THRESHOLD);
  }
  if (IMU.gyroscopeAvailable()) {
    IMU.readGyroscope(gx, gy, gz);
  }
#endif

#if ENABLE_HTS
  temp = HS300x.readTemperature();
  hum  = HS300x.readHumidity();
#endif

#if ENABLE_BARO
  pres = BARO.readPressure() * 10.0f;   // kPa → hPa
#endif

  // ── Emit JSON ────────────────────────────────────────────
  String json = buildJson(temp, hum, pres, ax, ay, az, gx, gy, gz, impact);

  Serial.println(json);

#if ENABLE_BLE
  telemetryChar.writeValue(json);
  BLE.poll();
#endif
}
