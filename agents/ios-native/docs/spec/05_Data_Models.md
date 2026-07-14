# 05_Data_Models.md

# SentinelX Mobile Agent

## Data Models and Schemas

Version: 1.0 Applies To: - iOS Swift Agent - FastAPI Backend -
PostgreSQL / TimescaleDB - SentinelX Dashboard - Future Android Agent

------------------------------------------------------------------------

# 1. Purpose

This document defines the canonical data models for the SentinelX Mobile
Agent.

It must be used as the source of truth for: - Swift Codable models -
FastAPI Pydantic schemas - PostgreSQL / TimescaleDB tables - WebSocket
messages - REST payloads - Dashboard DTOs - Future Android models

The goal is to keep the mobile agent, backend, and dashboard consistent.

------------------------------------------------------------------------

# 2. Modelling Principles

-   All timestamps use ISO 8601 UTC.
-   All IDs are strings.
-   Telemetry events are immutable after creation.
-   Telemetry event IDs must be idempotent.
-   Payloads must be JSON serializable.
-   Platform-specific details must stay inside payload or metadata.
-   Shared schemas must remain platform-neutral.
-   Do not expose secrets in API responses except at initial
    registration.
-   Avoid storing sensitive personal data unless explicitly required.

------------------------------------------------------------------------

# 3. Core Identifiers

## device_id

Format:

``` text
dev_<unique_id>
```

Example:

``` text
dev_01JZIOS001
```

Used for: - device profile - telemetry events - alerts - WebSocket
connection - dashboard lookups

## event_id

Format:

``` text
UUID
```

Example:

``` text
4F4F5F8D-8E9B-41C5-9A2A-7CC92B3A3C88
```

Used for telemetry idempotency.

## alert_id

Format:

``` text
alert_<unique_id>
```

Example:

``` text
alert_01JZLOWBATTERY
```

------------------------------------------------------------------------

# 4. Platform Enum

Valid platforms:

``` text
ios
android
macos
windows
linux
raspberry_pi
unknown
```

Swift:

``` swift
enum Platform: String, Codable {
    case ios
    case android
    case macos
    case windows
    case linux
    case raspberryPi = "raspberry_pi"
    case unknown
}
```

Backend:

``` python
class Platform(str, Enum):
    ios = "ios"
    android = "android"
    macos = "macos"
    windows = "windows"
    linux = "linux"
    raspberry_pi = "raspberry_pi"
    unknown = "unknown"
```

------------------------------------------------------------------------

# 5. Device Status Enum

Valid statuses:

``` text
active
disabled
online
offline
pending
revoked
```

Swift:

``` swift
enum DeviceStatus: String, Codable {
    case active
    case disabled
    case online
    case offline
    case pending
    case revoked
}
```

------------------------------------------------------------------------

# 6. Device Profile Model

Represents a registered mobile device.

## JSON

``` json
{
  "device_id": "dev_01JZIOS001",
  "platform": "ios",
  "device_name": "Abdulrehman's iPhone",
  "device_model": "iPhone 15",
  "os_version": "iOS 17.5",
  "app_version": "1.0.0",
  "timezone": "Europe/London",
  "locale": "en_GB",
  "status": "active",
  "registered_at": "2026-07-05T18:00:00Z",
  "last_seen": "2026-07-05T18:10:00Z"
}
```

## Swift

``` swift
struct DeviceProfile: Codable, Identifiable {
    var id: String { deviceId }

    let deviceId: String
    let platform: Platform
    let deviceName: String
    let deviceModel: String
    let osVersion: String
    let appVersion: String
    let timezone: String
    let locale: String
    let status: DeviceStatus
    let registeredAt: Date?
    let lastSeen: Date?
}
```

## Pydantic

``` python
class DeviceProfile(BaseModel):
    device_id: str
    platform: Platform
    device_name: str
    device_model: str
    os_version: str
    app_version: str
    timezone: str
    locale: str
    status: DeviceStatus
    registered_at: datetime | None = None
    last_seen: datetime | None = None
```

------------------------------------------------------------------------

# 7. Device Registration Request

## JSON

``` json
{
  "platform": "ios",
  "device_name": "Abdulrehman's iPhone",
  "device_model": "iPhone 15",
  "os_version": "iOS 17.5",
  "app_version": "1.0.0",
  "vendor_identifier": "ios-vendor-scoped-id",
  "timezone": "Europe/London",
  "locale": "en_GB"
}
```

## Swift

``` swift
struct DeviceRegistrationRequest: Codable {
    let platform: Platform
    let deviceName: String
    let deviceModel: String
    let osVersion: String
    let appVersion: String
    let vendorIdentifier: String
    let timezone: String
    let locale: String
}
```

## Response

``` json
{
  "device_id": "dev_01JZIOS001",
  "device_secret": "generated-secret",
  "registered_at": "2026-07-05T18:00:00Z",
  "status": "active"
}
```

Swift:

``` swift
struct DeviceRegistrationResponse: Codable {
    let deviceId: String
    let deviceSecret: String
    let registeredAt: Date
    let status: DeviceStatus
}
```

Security rule: - `device_secret` is returned only once during
registration. - Store it in iOS Keychain. - Store only its hash in the
backend database.

------------------------------------------------------------------------

# 8. Login Models

## Request

``` json
{
  "device_id": "dev_01JZIOS001",
  "device_secret": "generated-secret"
}
```

Swift:

``` swift
struct LoginRequest: Codable {
    let deviceId: String
    let deviceSecret: String
}
```

## Response

``` json
{
  "access_token": "jwt-access-token",
  "refresh_token": "jwt-refresh-token",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Swift:

``` swift
struct TokenResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let expiresIn: Int
}
```

------------------------------------------------------------------------

# 9. Telemetry Category Enum

Valid categories:

``` text
device
battery
thermal
storage
network
location
motion
activity
bluetooth
metrickit
diagnostic
alert
```

Swift:

``` swift
enum TelemetryCategory: String, Codable {
    case device
    case battery
    case thermal
    case storage
    case network
    case location
    case motion
    case activity
    case bluetooth
    case metrickit
    case diagnostic
    case alert
}
```

Backend:

``` python
class TelemetryCategory(str, Enum):
    device = "device"
    battery = "battery"
    thermal = "thermal"
    storage = "storage"
    network = "network"
    location = "location"
    motion = "motion"
    activity = "activity"
    bluetooth = "bluetooth"
    metrickit = "metrickit"
    diagnostic = "diagnostic"
    alert = "alert"
```

------------------------------------------------------------------------

# 10. Telemetry Event Envelope

All telemetry uses the same event envelope.

## JSON

``` json
{
  "event_id": "4F4F5F8D-8E9B-41C5-9A2A-7CC92B3A3C88",
  "device_id": "dev_01JZIOS001",
  "timestamp": "2026-07-05T18:15:00Z",
  "category": "battery",
  "type": "battery.snapshot",
  "source": "ios.uidevice",
  "sequence": 120,
  "payload": {
    "level": 84,
    "charging": false,
    "low_power_mode": false
  },
  "metadata": {
    "platform": "ios",
    "agent_version": "1.0.0",
    "collector_version": "1.0.0"
  }
}
```

## Swift

``` swift
struct TelemetryEvent: Codable, Identifiable {
    var id: UUID { eventId }

    let eventId: UUID
    let deviceId: String
    let timestamp: Date
    let category: TelemetryCategory
    let type: String
    let source: String
    let sequence: Int?
    let payload: JSONValue
    let metadata: TelemetryMetadata?
}
```

## Pydantic

``` python
class TelemetryEvent(BaseModel):
    event_id: UUID
    device_id: str
    timestamp: datetime
    category: TelemetryCategory
    type: str
    source: str
    sequence: int | None = None
    payload: dict[str, Any]
    metadata: dict[str, Any] | None = None
```

------------------------------------------------------------------------

# 11. JSONValue Swift Helper

Swift needs a safe generic JSON representation.

``` swift
enum JSONValue: Codable, Equatable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null
}
```

Rules: - Use concrete payload structs internally. - Convert to JSONValue
before storing or uploading. - Avoid `[String: Any]` in core models
unless isolated inside encoding utilities.

------------------------------------------------------------------------

# 12. Telemetry Metadata

``` json
{
  "platform": "ios",
  "agent_version": "1.0.0",
  "collector_version": "1.0.0",
  "app_build": "100",
  "environment": "development"
}
```

Swift:

``` swift
struct TelemetryMetadata: Codable {
    let platform: Platform
    let agentVersion: String
    let collectorVersion: String?
    let appBuild: String?
    let environment: String?
}
```

------------------------------------------------------------------------

# 13. Device Payload

Type:

``` text
device.snapshot
```

Source:

``` text
ios.uikit
```

Payload:

``` json
{
  "device_name": "Abdulrehman's iPhone",
  "device_model": "iPhone 15",
  "system_name": "iOS",
  "system_version": "17.5",
  "locale": "en_GB",
  "timezone": "Europe/London",
  "screen_width": 393,
  "screen_height": 852,
  "screen_scale": 3
}
```

Swift:

``` swift
struct DevicePayload: Codable {
    let deviceName: String
    let deviceModel: String
    let systemName: String
    let systemVersion: String
    let locale: String
    let timezone: String
    let screenWidth: Double
    let screenHeight: Double
    let screenScale: Double
}
```

------------------------------------------------------------------------

# 14. Battery Payload

Type:

``` text
battery.snapshot
```

Source:

``` text
ios.uidevice
```

Payload:

``` json
{
  "level": 84,
  "charging": false,
  "state": "unplugged",
  "low_power_mode": false
}
```

Swift:

``` swift
enum BatteryState: String, Codable {
    case unknown
    case unplugged
    case charging
    case full
}

struct BatteryPayload: Codable {
    let level: Int
    let charging: Bool
    let state: BatteryState
    let lowPowerMode: Bool
}
```

Validation: - level must be between 0 and 100. - If battery is
unavailable, level should be null or omitted depending on backend
implementation.

------------------------------------------------------------------------

# 15. Thermal Payload

Type:

``` text
thermal.state
```

Source:

``` text
ios.processinfo
```

Payload:

``` json
{
  "state": "nominal"
}
```

Swift:

``` swift
enum ThermalState: String, Codable {
    case nominal
    case fair
    case serious
    case critical
    case unknown
}

struct ThermalPayload: Codable {
    let state: ThermalState
}
```

------------------------------------------------------------------------

# 16. Storage Payload

Type:

``` text
storage.snapshot
```

Source:

``` text
ios.filemanager
```

Payload:

``` json
{
  "total_bytes": 128000000000,
  "free_bytes": 42000000000,
  "used_bytes": 86000000000,
  "free_percent": 32.8
}
```

Swift:

``` swift
struct StoragePayload: Codable {
    let totalBytes: Int64
    let freeBytes: Int64
    let usedBytes: Int64
    let freePercent: Double
}
```

Validation: - free_bytes cannot exceed total_bytes. - used_bytes =
total_bytes - free_bytes.

------------------------------------------------------------------------

# 17. Network Payload

Type:

``` text
network.status
```

Source:

``` text
ios.network
```

Payload:

``` json
{
  "reachable": true,
  "interface": "wifi",
  "expensive": false,
  "constrained": false
}
```

Swift:

``` swift
enum NetworkInterface: String, Codable {
    case wifi
    case cellular
    case wiredEthernet = "wired_ethernet"
    case loopback
    case other
    case unavailable
}

struct NetworkPayload: Codable {
    let reachable: Bool
    let interface: NetworkInterface
    let expensive: Bool
    let constrained: Bool
}
```

------------------------------------------------------------------------

# 18. Location Payload

Type:

``` text
location.update
```

Source:

``` text
ios.corelocation
```

Payload:

``` json
{
  "latitude": 51.5074,
  "longitude": -0.1278,
  "altitude": 35.2,
  "speed": 1.4,
  "heading": 270.0,
  "horizontal_accuracy": 8.0,
  "vertical_accuracy": 12.0
}
```

Swift:

``` swift
struct LocationPayload: Codable {
    let latitude: Double
    let longitude: Double
    let altitude: Double?
    let speed: Double?
    let heading: Double?
    let horizontalAccuracy: Double
    let verticalAccuracy: Double?
}
```

Validation: - latitude between -90 and 90. - longitude between -180 and
180. - accuracy must be non-negative.

Privacy: - Location collection must be permission-based. - Avoid logging
precise location in plaintext logs.

------------------------------------------------------------------------

# 19. Motion Payload

Type:

``` text
motion.sample
```

Source:

``` text
ios.coremotion
```

Payload:

``` json
{
  "accelerometer": {
    "x": 0.02,
    "y": 0.13,
    "z": 9.79
  },
  "gyroscope": {
    "x": 0.01,
    "y": 0.00,
    "z": 0.03
  },
  "gravity": {
    "x": 0.00,
    "y": 0.02,
    "z": 9.80
  },
  "user_acceleration": {
    "x": 0.02,
    "y": 0.11,
    "z": -0.01
  },
  "attitude": {
    "pitch": 0.1,
    "roll": 0.0,
    "yaw": 1.2
  }
}
```

Swift:

``` swift
struct Vector3D: Codable {
    let x: Double
    let y: Double
    let z: Double
}

struct AttitudePayload: Codable {
    let pitch: Double
    let roll: Double
    let yaw: Double
}

struct MotionPayload: Codable {
    let accelerometer: Vector3D?
    let gyroscope: Vector3D?
    let gravity: Vector3D?
    let userAcceleration: Vector3D?
    let attitude: AttitudePayload?
}
```

Notes: - Core Motion acceleration values are normally expressed in units
of g, not m/s², depending on the source. - Keep units documented in
metadata if required.

------------------------------------------------------------------------

# 20. Activity Payload

Type:

``` text
activity.state
```

Source:

``` text
ios.coremotion.activity
```

Payload:

``` json
{
  "stationary": false,
  "walking": true,
  "running": false,
  "cycling": false,
  "automotive": false,
  "unknown": false,
  "confidence": "high"
}
```

Swift:

``` swift
enum ActivityConfidence: String, Codable {
    case low
    case medium
    case high
    case unknown
}

struct ActivityPayload: Codable {
    let stationary: Bool
    let walking: Bool
    let running: Bool
    let cycling: Bool
    let automotive: Bool
    let unknown: Bool
    let confidence: ActivityConfidence
}
```

------------------------------------------------------------------------

# 21. Bluetooth Payload

Type:

``` text
bluetooth.scan_result
```

Source:

``` text
ios.corebluetooth
```

Payload:

``` json
{
  "peripheral_id": "uuid",
  "name": "BLE Sensor",
  "rssi": -62,
  "service_uuids": ["180D", "180F"],
  "connectable": true
}
```

Swift:

``` swift
struct BluetoothPayload: Codable {
    let peripheralId: String
    let name: String?
    let rssi: Int
    let serviceUUIDs: [String]
    let connectable: Bool?
}
```

Privacy: - Do not treat nearby BLE devices as user identity. - Do not
scan unless the user enables Bluetooth collection.

------------------------------------------------------------------------

# 22. MetricKit Payload

Types:

``` text
metrickit.metrics
metrickit.diagnostic
```

Source:

``` text
ios.metrickit
```

Recommended simplified payload:

``` json
{
  "report_type": "metrics",
  "cpu_time_seconds": 12.3,
  "memory_peak_bytes": 104857600,
  "cumulative_foreground_time_seconds": 900,
  "cumulative_background_time_seconds": 120,
  "crash_count": 0,
  "hang_count": 1,
  "diagnostic_summary": "Application hang detected"
}
```

Swift:

``` swift
struct MetricKitPayload: Codable {
    let reportType: String
    let cpuTimeSeconds: Double?
    let memoryPeakBytes: Int64?
    let cumulativeForegroundTimeSeconds: Double?
    let cumulativeBackgroundTimeSeconds: Double?
    let crashCount: Int?
    let hangCount: Int?
    let diagnosticSummary: String?
}
```

Important: - MetricKit is system-delivered and not real-time. - Store
full raw MetricKit payload only if needed and privacy-reviewed.

------------------------------------------------------------------------

# 23. Diagnostic Payload

Type:

``` text
diagnostic.log
diagnostic.collector_health
diagnostic.sync_status
```

Payload example:

``` json
{
  "component": "WebSocketClient",
  "status": "reconnecting",
  "message": "Connection lost, retrying",
  "retry_count": 3
}
```

Swift:

``` swift
struct DiagnosticPayload: Codable {
    let component: String
    let status: String
    let message: String?
    let retryCount: Int?
}
```

------------------------------------------------------------------------

# 24. Collector Health Model

JSON:

``` json
{
  "collector_id": "battery",
  "category": "battery",
  "enabled": true,
  "health": "healthy",
  "last_event_at": "2026-07-05T18:15:00Z",
  "error_message": null
}
```

Swift:

``` swift
enum CollectorHealthState: String, Codable {
    case healthy
    case degraded
    case disabled
    case permissionDenied = "permission_denied"
    case unsupported
    case failed
}

struct CollectorHealth: Codable {
    let collectorId: String
    let category: TelemetryCategory
    let enabled: Bool
    let health: CollectorHealthState
    let lastEventAt: Date?
    let errorMessage: String?
}
```

------------------------------------------------------------------------

# 25. Alert Model

JSON:

``` json
{
  "alert_id": "alert_01JZLOWBATTERY",
  "device_id": "dev_01JZIOS001",
  "severity": "warning",
  "category": "battery",
  "rule": "BATTERY_LOW",
  "message": "Battery level is below 20%",
  "created_at": "2026-07-05T18:20:00Z",
  "resolved": false,
  "resolved_at": null
}
```

Swift:

``` swift
enum AlertSeverity: String, Codable {
    case info
    case warning
    case critical
}

struct Alert: Codable, Identifiable {
    var id: String { alertId }

    let alertId: String
    let deviceId: String
    let severity: AlertSeverity
    let category: TelemetryCategory
    let rule: String
    let message: String
    let createdAt: Date
    let resolved: Bool
    let resolvedAt: Date?
}
```

------------------------------------------------------------------------

# 26. Configuration Model

JSON:

``` json
{
  "device_id": "dev_01JZIOS001",
  "config_version": "1.0",
  "collectors": {
    "battery": {
      "enabled": true,
      "interval_seconds": 30
    },
    "motion": {
      "enabled": true,
      "sample_hz": 20
    },
    "location": {
      "enabled": true,
      "interval_seconds": 5,
      "accuracy": "balanced"
    }
  },
  "upload": {
    "websocket_enabled": true,
    "rest_fallback_enabled": true,
    "batch_size": 100,
    "flush_interval_seconds": 30
  }
}
```

Swift:

``` swift
struct AgentConfig: Codable {
    let deviceId: String
    let configVersion: String
    let collectors: [String: CollectorConfig]
    let upload: UploadConfig
}

struct CollectorConfig: Codable {
    let enabled: Bool
    let intervalSeconds: Int?
    let sampleHz: Int?
    let accuracy: String?
}

struct UploadConfig: Codable {
    let websocketEnabled: Bool
    let restFallbackEnabled: Bool
    let batchSize: Int
    let flushIntervalSeconds: Int
}
```

------------------------------------------------------------------------

# 27. WebSocket Message Models

## Base Message

``` json
{
  "type": "telemetry.event",
  "message_id": "uuid",
  "timestamp": "2026-07-05T18:21:00Z"
}
```

Swift:

``` swift
struct WebSocketEnvelope<T: Codable>: Codable {
    let type: String
    let messageId: UUID
    let timestamp: Date
    let payload: T?
}
```

## Auth Message

``` json
{
  "type": "auth",
  "access_token": "jwt-access-token",
  "device_id": "dev_01JZIOS001"
}
```

Swift:

``` swift
struct WebSocketAuthMessage: Codable {
    let type: String
    let accessToken: String
    let deviceId: String
}
```

## Telemetry Message

``` json
{
  "type": "telemetry.event",
  "event": {
    "event_id": "uuid",
    "device_id": "dev_01JZIOS001",
    "timestamp": "2026-07-05T18:21:00Z",
    "category": "battery",
    "type": "battery.snapshot",
    "source": "ios.uidevice",
    "payload": {
      "level": 84
    }
  }
}
```

Swift:

``` swift
struct WebSocketTelemetryMessage: Codable {
    let type: String
    let event: TelemetryEvent
}
```

------------------------------------------------------------------------

# 28. Batch Upload Model

JSON:

``` json
{
  "device_id": "dev_01JZIOS001",
  "batch_id": "batch_uuid",
  "sent_at": "2026-07-05T18:16:00Z",
  "events": []
}
```

Swift:

``` swift
struct TelemetryBatchUploadRequest: Codable {
    let deviceId: String
    let batchId: UUID
    let sentAt: Date
    let events: [TelemetryEvent]
}
```

Response:

``` json
{
  "accepted": true,
  "batch_id": "batch_uuid",
  "accepted_count": 100,
  "rejected_count": 0,
  "rejected_events": []
}
```

Swift:

``` swift
struct TelemetryBatchUploadResponse: Codable {
    let accepted: Bool
    let batchId: UUID
    let acceptedCount: Int
    let rejectedCount: Int
    let rejectedEvents: [RejectedTelemetryEvent]
}

struct RejectedTelemetryEvent: Codable {
    let eventId: UUID
    let reason: String
}
```

------------------------------------------------------------------------

# 29. Standard Error Model

JSON:

``` json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid telemetry payload",
    "details": {},
    "request_id": "request_uuid"
  }
}
```

Swift:

``` swift
struct APIErrorResponse: Codable {
    let error: APIErrorDetail
}

struct APIErrorDetail: Codable {
    let code: String
    let message: String
    let details: JSONValue?
    let requestId: String?
}
```

------------------------------------------------------------------------

# 30. Local SQLite Models

## telemetry_queue

Fields:

``` text
id INTEGER PRIMARY KEY AUTOINCREMENT
event_id TEXT UNIQUE NOT NULL
device_id TEXT NOT NULL
category TEXT NOT NULL
type TEXT NOT NULL
payload_json TEXT NOT NULL
metadata_json TEXT
timestamp TEXT NOT NULL
status TEXT NOT NULL
retry_count INTEGER DEFAULT 0
created_at TEXT NOT NULL
updated_at TEXT NOT NULL
last_error TEXT
```

Statuses:

``` text
pending
in_flight
uploaded
failed
```

Swift:

``` swift
enum QueueStatus: String, Codable {
    case pending
    case inFlight = "in_flight"
    case uploaded
    case failed
}

struct QueuedTelemetryEvent: Codable, Identifiable {
    let id: Int64?
    let eventId: UUID
    let deviceId: String
    let category: TelemetryCategory
    let type: String
    let payloadJson: String
    let metadataJson: String?
    let timestamp: Date
    let status: QueueStatus
    let retryCount: Int
    let createdAt: Date
    let updatedAt: Date
    let lastError: String?
}
```

------------------------------------------------------------------------

# 31. Backend Database Tables

## mobile_devices

``` sql
CREATE TABLE mobile_devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) UNIQUE NOT NULL,
    platform VARCHAR(50) NOT NULL,
    device_name VARCHAR(255) NOT NULL,
    device_model VARCHAR(255),
    os_version VARCHAR(100),
    app_version VARCHAR(100),
    vendor_identifier_hash VARCHAR(255),
    timezone VARCHAR(100),
    locale VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## mobile_device_credentials

``` sql
CREATE TABLE mobile_device_credentials (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) NOT NULL REFERENCES mobile_devices(device_id),
    device_secret_hash VARCHAR(255) NOT NULL,
    refresh_token_hash VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);
```

## mobile_telemetry_events

``` sql
CREATE TABLE mobile_telemetry_events (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID UNIQUE NOT NULL,
    device_id VARCHAR(100) NOT NULL REFERENCES mobile_devices(device_id),
    timestamp TIMESTAMPTZ NOT NULL,
    category VARCHAR(50) NOT NULL,
    type VARCHAR(100) NOT NULL,
    source VARCHAR(100) NOT NULL,
    sequence INTEGER,
    payload_json JSONB NOT NULL,
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Recommended indexes:

``` sql
CREATE INDEX idx_mobile_telemetry_device_timestamp
ON mobile_telemetry_events (device_id, timestamp DESC);

CREATE INDEX idx_mobile_telemetry_category_timestamp
ON mobile_telemetry_events (category, timestamp DESC);

CREATE INDEX idx_mobile_telemetry_payload_gin
ON mobile_telemetry_events USING GIN (payload_json);
```

## mobile_alerts

``` sql
CREATE TABLE mobile_alerts (
    id BIGSERIAL PRIMARY KEY,
    alert_id VARCHAR(100) UNIQUE NOT NULL,
    device_id VARCHAR(100) NOT NULL REFERENCES mobile_devices(device_id),
    severity VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    rule VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
```

## mobile_config

``` sql
CREATE TABLE mobile_config (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) REFERENCES mobile_devices(device_id),
    config_version VARCHAR(50) NOT NULL,
    config_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

------------------------------------------------------------------------

# 32. TimescaleDB Recommendation

If TimescaleDB is enabled, convert telemetry table into a hypertable:

``` sql
SELECT create_hypertable('mobile_telemetry_events', 'timestamp');
```

Recommended retention: - Raw high-frequency motion data: 7 to 30 days -
Standard telemetry: 90 days - Aggregated telemetry: 1 year

------------------------------------------------------------------------

# 33. Dashboard DTOs

## Mobile Device Summary

``` json
{
  "device_id": "dev_01JZIOS001",
  "device_name": "iPhone 15",
  "platform": "ios",
  "status": "online",
  "last_seen": "2026-07-05T18:30:00Z",
  "battery": 84,
  "thermal": "nominal",
  "network": "wifi",
  "active_alerts": 0
}
```

## Telemetry Chart Point

``` json
{
  "timestamp": "2026-07-05T18:30:00Z",
  "value": 84,
  "category": "battery",
  "metric": "level"
}
```

## Location Map Point

``` json
{
  "timestamp": "2026-07-05T18:30:00Z",
  "latitude": 51.5074,
  "longitude": -0.1278,
  "speed": 1.4
}
```

------------------------------------------------------------------------

# 34. Validation Rules

## Global

-   device_id must exist.
-   device_id in payload must match authenticated device.
-   timestamp must be valid ISO 8601.
-   event_id must be UUID.
-   category must be allowed enum.
-   payload must be valid JSON object.

## Battery

-   level must be 0 to 100.
-   charging must be boolean.
-   low_power_mode must be boolean.

## Thermal

-   state must be one of:
    -   nominal
    -   fair
    -   serious
    -   critical
    -   unknown

## Location

-   latitude must be between -90 and 90.
-   longitude must be between -180 and 180.
-   speed may be negative only if iOS reports invalid speed; backend
    should normalize invalid speed to null.
-   accuracy must be non-negative.

## Storage

-   total_bytes must be positive.
-   free_bytes must not exceed total_bytes.
-   used_bytes must not be negative.

## Motion

-   vectors must contain numeric x, y, z.
-   high-frequency payloads must be rate limited.

------------------------------------------------------------------------

# 35. Data Privacy Classification

## Low Sensitivity

-   device model
-   OS version
-   app version
-   battery level
-   thermal state
-   storage statistics
-   network interface type

## Medium Sensitivity

-   device name
-   BLE scan results
-   motion data
-   diagnostics

## High Sensitivity

-   precise GPS location
-   health data
-   persistent identifiers
-   crash diagnostics containing user context

Rules: - High sensitivity data requires explicit permission. - Avoid
logging high sensitivity payloads. - Allow user to disable location and
Bluetooth collection.

------------------------------------------------------------------------

# 36. Naming Conventions

## JSON

Use snake_case.

Example:

``` json
{
  "device_id": "dev_01",
  "battery_level": 84
}
```

## Swift

Use camelCase.

Example:

``` swift
let deviceId: String
let batteryLevel: Int
```

## Database

Use snake_case.

Example:

``` sql
device_id VARCHAR(100)
```

------------------------------------------------------------------------

# 37. Versioning

Each telemetry event may include:

``` json
{
  "metadata": {
    "schema_version": "1.0",
    "agent_version": "1.0.0",
    "collector_version": "1.0.0"
  }
}
```

Rules: - Additive changes are allowed. - Removing fields requires major
schema version. - Unknown fields should be ignored by clients where
possible.

------------------------------------------------------------------------

# 38. Example Complete Event Set

``` json
[
  {
    "event_id": "11111111-1111-1111-1111-111111111111",
    "device_id": "dev_01JZIOS001",
    "timestamp": "2026-07-05T18:15:00Z",
    "category": "battery",
    "type": "battery.snapshot",
    "source": "ios.uidevice",
    "payload": {
      "level": 84,
      "charging": false,
      "state": "unplugged",
      "low_power_mode": false
    }
  },
  {
    "event_id": "22222222-2222-2222-2222-222222222222",
    "device_id": "dev_01JZIOS001",
    "timestamp": "2026-07-05T18:15:01Z",
    "category": "network",
    "type": "network.status",
    "source": "ios.network",
    "payload": {
      "reachable": true,
      "interface": "wifi",
      "expensive": false,
      "constrained": false
    }
  },
  {
    "event_id": "33333333-3333-3333-3333-333333333333",
    "device_id": "dev_01JZIOS001",
    "timestamp": "2026-07-05T18:15:02Z",
    "category": "thermal",
    "type": "thermal.state",
    "source": "ios.processinfo",
    "payload": {
      "state": "nominal"
    }
  }
]
```

------------------------------------------------------------------------

# 39. Claude Code Implementation Rules

Claude Code must: - Keep Swift models Codable. - Keep JSON keys
snake_case. - Use CodingKeys where needed. - Keep backend Pydantic
schemas aligned with this file. - Do not invent new telemetry categories
without updating this document. - Do not store tokens or secrets in
plain storage. - Use event_id for idempotency. - Treat location and
Bluetooth data as sensitive. - Keep schema changes backward compatible.

End of document.
