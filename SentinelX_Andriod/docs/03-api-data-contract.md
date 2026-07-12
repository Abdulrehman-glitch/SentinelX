# API and Data Contract

## Contract Status

This is a proposed Android-side contract. It must be reconciled with the existing FastAPI backend before implementation.

Known backend context:

- API prefix is `/api/v1`.
- User login exists through `/api/v1/auth/login`.
- Swagger token endpoint exists through `/api/v1/auth/token`.
- Existing Python agent posts metrics to `/api/v1/metrics`.
- Device/agent endpoints use raw bearer-token auth.
- Roles include `platform_admin`, `owner`, `admin`, `engineer`, `operator`, and `viewer`.

The PRD proposes `/mobile/*` endpoints. The backend may need new routes or the Android app may need to reuse existing routes.

## Recommended v1 Endpoints

| Method | Path | Purpose | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/login` | User login | None |
| GET | `/api/v1/users/me` | Restore current user/session | User JWT |
| POST | `/api/v1/mobile/devices/register` | Register Android device | User JWT or bootstrap token |
| POST | `/api/v1/mobile/heartbeat` | Send device heartbeat | Device token |
| POST | `/api/v1/mobile/telemetry/batch` | Upload queued telemetry batch | Device token |
| GET | `/api/v1/dashboard` | Mobile dashboard summary | User JWT |
| GET | `/api/v1/devices` | Device list | User JWT |
| GET | `/api/v1/devices/{id}` | Device detail | User JWT |
| GET | `/api/v1/alerts` | Alert list | User JWT |
| POST | `/api/v1/alerts/{id}/acknowledge` | Acknowledge alert, v2 if needed | User JWT |
| GET | `/api/v1/incidents` | Incident list | User JWT |

## Auth Model

Two identities may exist in the app:

1. User identity:
   - Used for console screens.
   - JWT obtained through login.
   - RBAC controls dashboard, devices, alerts, incidents, settings.

2. Device identity:
   - Used for heartbeat and telemetry.
   - Issued during device registration.
   - Should be scoped to a single registered Android device.

If the backend cannot support separate user and device tokens in v1, use the existing auth path temporarily and document the limitation.

## Device Registration Request

```json
{
  "hostname": "pixel-4-xl-abdul",
  "platform": "android",
  "manufacturer": "Google",
  "model": "Pixel 4 XL",
  "os_version": "Android 13",
  "app_version": "1.0.0",
  "install_channel": "internal_apk",
  "organization_slug": "default"
}
```

## Device Registration Response

```json
{
  "device_id": "uuid",
  "device_token": "opaque-token-or-jwt",
  "registered_at": "2026-07-06T22:00:00Z",
  "sync_interval_minutes": 15
}
```

## Heartbeat Request

```json
{
  "device_id": "uuid",
  "observed_at": "2026-07-06T22:05:00Z",
  "status": "online",
  "app_version": "1.0.0",
  "battery_level_pct": 84,
  "network_type": "wifi"
}
```

## Telemetry Batch Request

```json
{
  "batch_id": "client-generated-uuid",
  "device_id": "uuid",
  "captured_at": "2026-07-06T22:05:00Z",
  "samples": [
    {
      "sample_id": "client-generated-uuid",
      "metric_type": "battery.status",
      "observed_at": "2026-07-06T22:05:00Z",
      "value": {
        "level_pct": 84,
        "is_charging": true,
        "plug_type": "usb",
        "temperature_c": 32.1
      }
    },
    {
      "sample_id": "client-generated-uuid",
      "metric_type": "memory.status",
      "observed_at": "2026-07-06T22:05:00Z",
      "value": {
        "total_bytes": 5798205849,
        "available_bytes": 2147483648,
        "low_memory": false
      }
    }
  ]
}
```

## Telemetry Batch Response

```json
{
  "batch_id": "client-generated-uuid",
  "accepted": true,
  "accepted_sample_count": 2,
  "server_received_at": "2026-07-06T22:05:02Z"
}
```

## v1 Metric Types

| Metric type | Fields |
|---|---|
| `device.identity` | `manufacturer`, `model`, `os_version`, `sdk_int`, `app_version`, `install_channel` |
| `battery.status` | `level_pct`, `is_charging`, `plug_type`, `health`, `temperature_c` |
| `memory.status` | `total_bytes`, `available_bytes`, `low_memory`, `threshold_bytes` |
| `storage.status` | `total_bytes`, `available_bytes`, `used_pct` |
| `network.status` | `is_connected`, `transport`, `is_metered`, `validated` |
| `sync.status` | `last_success_at`, `pending_batch_count`, `last_error_code` |

## Local Queue State Machine

```text
pending -> uploading -> sent
pending -> uploading -> failed -> pending
pending -> abandoned
```

Use `abandoned` only when a batch exceeds retention or retry limits. Do not silently delete unsent telemetry without recording why.

## Idempotency

- Android generates `batch_id` and `sample_id`.
- Backend should treat repeated `batch_id` uploads as safe retries.
- Android marks a batch as sent only after explicit backend acceptance.

