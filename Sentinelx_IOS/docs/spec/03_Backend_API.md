# 03_Backend_API.md

# SentinelX Mobile Agent

## Backend API Contract

Version: 1.0 Target Backend: FastAPI Database: PostgreSQL / TimescaleDB
Primary Client: iOS Swift Mobile Agent Future Clients: Android, macOS,
Windows, Linux, Raspberry Pi

------------------------------------------------------------------------

# 1. Purpose

This document defines the backend API contract for the SentinelX Mobile
Agent.

The backend must support: - Mobile device registration -
Authentication - Real-time telemetry ingestion - Batch telemetry
upload - WebSocket streaming - Device configuration sync - Alert
generation - Historical telemetry retrieval - Dashboard integration

This document is implementation-ready and should be treated as the
source of truth for Claude Code.

------------------------------------------------------------------------

# 2. API Design Principles

-   REST for standard operations
-   WebSocket for real-time telemetry
-   JSON payloads
-   ISO 8601 timestamps
-   JWT authentication
-   Platform-neutral schemas
-   Versioned API paths
-   Strong validation
-   Clear error responses
-   Backwards compatible changes where possible

Base path:

``` text
/api/v1/mobile
```

------------------------------------------------------------------------

# 3. Authentication

## Auth Method

Use JWT access tokens and refresh tokens.

Access token: - Short lived - Used for API and WebSocket authentication

Refresh token: - Longer lived - Used to renew access token

Device secret: - Generated during device registration - Stored securely
on iOS using Keychain

------------------------------------------------------------------------

# 4. Standard Headers

All authenticated HTTP requests must include:

``` text
Authorization: Bearer <access_token>
Content-Type: application/json
X-Client-Platform: ios
X-Agent-Version: 1.0.0
```

Optional:

``` text
X-Device-ID: <device_id>
X-Request-ID: <uuid>
```

------------------------------------------------------------------------

# 5. Standard Error Response

All errors must use the following structure:

``` json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid telemetry payload",
    "details": {},
    "request_id": "uuid"
  }
}
```

Common error codes:

``` text
AUTH_REQUIRED
INVALID_TOKEN
TOKEN_EXPIRED
DEVICE_NOT_FOUND
DEVICE_DISABLED
VALIDATION_ERROR
RATE_LIMITED
SERVER_ERROR
WEBSOCKET_AUTH_FAILED
```

------------------------------------------------------------------------

# 6. Device Registration

## POST /api/v1/mobile/register

Registers a new mobile device.

### Request

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

### Response

``` json
{
  "device_id": "dev_01JZIOS001",
  "device_secret": "generated-secret",
  "registered_at": "2026-07-05T18:00:00Z",
  "status": "active"
}
```

### Behaviour

-   Create a new device if not found.
-   Return existing device if vendor identifier already exists.
-   Never expose another user's device.

------------------------------------------------------------------------

# 7. Login

## POST /api/v1/mobile/login

Authenticates a registered device.

### Request

``` json
{
  "device_id": "dev_01JZIOS001",
  "device_secret": "generated-secret"
}
```

### Response

``` json
{
  "access_token": "jwt-access-token",
  "refresh_token": "jwt-refresh-token",
  "token_type": "bearer",
  "expires_in": 1800
}
```

------------------------------------------------------------------------

# 8. Refresh Token

## POST /api/v1/mobile/token/refresh

### Request

``` json
{
  "refresh_token": "jwt-refresh-token"
}
```

### Response

``` json
{
  "access_token": "new-jwt-access-token",
  "refresh_token": "new-jwt-refresh-token",
  "token_type": "bearer",
  "expires_in": 1800
}
```

------------------------------------------------------------------------

# 9. Device Profile

## GET /api/v1/mobile/profile

Returns the authenticated device profile.

### Response

``` json
{
  "device_id": "dev_01JZIOS001",
  "platform": "ios",
  "device_name": "Abdulrehman's iPhone",
  "device_model": "iPhone 15",
  "os_version": "iOS 17.5",
  "app_version": "1.0.0",
  "status": "active",
  "last_seen": "2026-07-05T18:10:00Z"
}
```

------------------------------------------------------------------------

# 10. Update Device Profile

## PATCH /api/v1/mobile/profile

### Request

``` json
{
  "device_name": "iPhone 15 Test Device",
  "app_version": "1.0.1",
  "os_version": "iOS 17.6"
}
```

### Response

``` json
{
  "success": true,
  "updated_at": "2026-07-05T18:12:00Z"
}
```

------------------------------------------------------------------------

# 11. Telemetry Event Schema

All telemetry events must use a shared envelope.

``` json
{
  "event_id": "uuid",
  "device_id": "dev_01JZIOS001",
  "timestamp": "2026-07-05T18:15:00Z",
  "category": "battery",
  "type": "battery.snapshot",
  "source": "ios.uidevice",
  "sequence": 120,
  "payload": {},
  "metadata": {
    "agent_version": "1.0.0",
    "platform": "ios"
  }
}
```

Required fields: - event_id - device_id - timestamp - category - type -
source - payload

------------------------------------------------------------------------

# 12. Telemetry Categories

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
alert
diagnostic
```

------------------------------------------------------------------------

# 13. Single Telemetry Upload

## POST /api/v1/mobile/telemetry

Uploads one telemetry event.

### Request

``` json
{
  "event_id": "uuid",
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
  }
}
```

### Response

``` json
{
  "accepted": true,
  "event_id": "uuid",
  "stored_at": "2026-07-05T18:15:01Z"
}
```

------------------------------------------------------------------------

# 14. Batch Telemetry Upload

## POST /api/v1/mobile/batch

Uploads multiple telemetry events.

### Request

``` json
{
  "device_id": "dev_01JZIOS001",
  "batch_id": "batch_uuid",
  "sent_at": "2026-07-05T18:16:00Z",
  "events": [
    {
      "event_id": "uuid-1",
      "timestamp": "2026-07-05T18:15:00Z",
      "category": "battery",
      "type": "battery.snapshot",
      "source": "ios.uidevice",
      "payload": {
        "level": 84,
        "charging": false
      }
    }
  ]
}
```

### Response

``` json
{
  "accepted": true,
  "batch_id": "batch_uuid",
  "accepted_count": 1,
  "rejected_count": 0,
  "rejected_events": []
}
```

### Behaviour

-   Accept valid events.
-   Reject invalid events individually.
-   Return rejected event IDs with reasons.
-   Must be idempotent based on event_id.

------------------------------------------------------------------------

# 15. Device Configuration

## GET /api/v1/mobile/config

Returns collector configuration for the device.

### Response

``` json
{
  "device_id": "dev_01JZIOS001",
  "config_version": "1.0",
  "collectors": {
    "battery": {
      "enabled": true,
      "interval_seconds": 30
    },
    "storage": {
      "enabled": true,
      "interval_seconds": 60
    },
    "motion": {
      "enabled": true,
      "sample_hz": 20
    },
    "location": {
      "enabled": true,
      "interval_seconds": 5,
      "accuracy": "balanced"
    },
    "bluetooth": {
      "enabled": false
    }
  },
  "upload": {
    "websocket_enabled": true,
    "batch_size": 100,
    "flush_interval_seconds": 30
  }
}
```

------------------------------------------------------------------------

# 16. WebSocket Endpoint

## WS /api/v1/mobile/ws/{device_id}

Used for live telemetry streaming.

Authentication options: 1. Bearer token in query string for development
2. Bearer token in WebSocket protocol/header where supported 3. First
message authentication payload

Preferred first-message auth:

``` json
{
  "type": "auth",
  "access_token": "jwt-access-token",
  "device_id": "dev_01JZIOS001"
}
```

### Successful Auth Response

``` json
{
  "type": "auth.accepted",
  "device_id": "dev_01JZIOS001",
  "server_time": "2026-07-05T18:20:00Z"
}
```

### Failed Auth Response

``` json
{
  "type": "auth.rejected",
  "reason": "INVALID_TOKEN"
}
```

------------------------------------------------------------------------

# 17. WebSocket Message Types

Client to server:

``` text
auth
heartbeat
telemetry.event
telemetry.batch
agent.status
```

Server to client:

``` text
auth.accepted
auth.rejected
heartbeat.ack
config.update
alert.created
command.pause_collector
command.resume_collector
error
```

------------------------------------------------------------------------

# 18. WebSocket Telemetry Event

``` json
{
  "type": "telemetry.event",
  "event": {
    "event_id": "uuid",
    "device_id": "dev_01JZIOS001",
    "timestamp": "2026-07-05T18:21:00Z",
    "category": "network",
    "type": "network.status",
    "source": "ios.network",
    "payload": {
      "reachable": true,
      "interface": "wifi",
      "expensive": false,
      "constrained": false
    }
  }
}
```

------------------------------------------------------------------------

# 19. Heartbeat

Client sends heartbeat every 30 seconds.

``` json
{
  "type": "heartbeat",
  "device_id": "dev_01JZIOS001",
  "timestamp": "2026-07-05T18:22:00Z"
}
```

Server response:

``` json
{
  "type": "heartbeat.ack",
  "server_time": "2026-07-05T18:22:00Z"
}
```

------------------------------------------------------------------------

# 20. Alert Schema

``` json
{
  "alert_id": "alert_uuid",
  "device_id": "dev_01JZIOS001",
  "severity": "critical",
  "category": "thermal",
  "rule": "THERMAL_CRITICAL",
  "message": "Device thermal state is critical",
  "created_at": "2026-07-05T18:25:00Z",
  "resolved": false
}
```

Severity values:

``` text
info
warning
critical
```

------------------------------------------------------------------------

# 21. Dashboard APIs

## GET /api/v1/mobile/devices

Returns all registered mobile devices.

### Response

``` json
{
  "items": [
    {
      "device_id": "dev_01JZIOS001",
      "device_name": "iPhone 15",
      "platform": "ios",
      "status": "online",
      "last_seen": "2026-07-05T18:30:00Z",
      "battery": 84,
      "thermal": "normal"
    }
  ]
}
```

------------------------------------------------------------------------

## GET /api/v1/mobile/devices/{device_id}

Returns one device.

------------------------------------------------------------------------

## GET /api/v1/mobile/devices/{device_id}/telemetry

Query parameters:

``` text
category
from
to
limit
page
```

------------------------------------------------------------------------

## GET /api/v1/mobile/devices/{device_id}/alerts

Returns alert history.

------------------------------------------------------------------------

# 22. Rate Limiting

Recommended limits:

-   Register: 10/minute/IP
-   Login: 20/minute/device
-   Telemetry single: 120/minute/device
-   Batch upload: 30/minute/device
-   WebSocket messages: 1200/minute/device

On limit exceed:

``` json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many telemetry events",
    "details": {
      "retry_after_seconds": 30
    }
  }
}
```

------------------------------------------------------------------------

# 23. Validation Rules

Telemetry: - event_id must be UUID - timestamp must be ISO 8601 -
category must be valid - payload must be JSON object - device_id must
match authenticated device - duplicate event_id must not create
duplicate rows

Location: - latitude between -90 and 90 - longitude between -180 and
180 - speed must be numeric

Battery: - level between 0 and 100

Thermal: - normal, fair, serious, critical

------------------------------------------------------------------------

# 24. Database Tables

## mobile_devices

``` text
id
device_id
platform
device_name
device_model
os_version
app_version
vendor_identifier_hash
status
registered_at
last_seen
created_at
updated_at
```

## mobile_device_credentials

``` text
id
device_id
device_secret_hash
refresh_token_hash
created_at
updated_at
revoked_at
```

## mobile_telemetry_events

``` text
id
event_id
device_id
timestamp
category
type
source
payload_json
created_at
```

## mobile_alerts

``` text
id
alert_id
device_id
severity
category
rule
message
resolved
created_at
resolved_at
```

## mobile_config

``` text
id
device_id
config_version
config_json
created_at
updated_at
```

------------------------------------------------------------------------

# 25. Idempotency

All telemetry events must be idempotent by event_id.

If duplicate event_id is received: - Do not insert duplicate. - Return
accepted true. - Mark as duplicate if useful for diagnostics.

------------------------------------------------------------------------

# 26. Logging

Log: - device registration - login success/failure - telemetry ingestion
failures - WebSocket connect/disconnect - validation failures - alert
creation - rate limit events

Never log: - raw tokens - device secrets - sensitive location payloads
in plaintext logs

------------------------------------------------------------------------

# 27. Backend Implementation Notes

Use: - FastAPI routers - Pydantic models - SQLAlchemy or SQLModel -
Alembic migrations - JWT utilities - WebSocket manager - Background task
queue if needed - Structured logging

Recommended router structure:

``` text
app/api/v1/mobile/auth.py
app/api/v1/mobile/devices.py
app/api/v1/mobile/telemetry.py
app/api/v1/mobile/websocket.py
app/api/v1/mobile/config.py
app/api/v1/mobile/alerts.py
```

------------------------------------------------------------------------

# 28. Acceptance Criteria

Backend is complete when:

-   Device can register.
-   Device can authenticate.
-   JWT works for REST.
-   WebSocket authenticates device.
-   Telemetry stores in database.
-   Batch upload handles duplicates.
-   Dashboard endpoints return live state.
-   Alerts are generated from rules.
-   Invalid payloads return clear errors.
-   API docs appear in Swagger.

End of document.
