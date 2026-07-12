# Android Architecture

## Recommended Stack

| Concern | Choice |
|---|---|
| Language | Kotlin |
| UI | Jetpack Compose + Material 3 |
| Architecture | MVVM + Clean Architecture |
| Dependency injection | Hilt |
| Networking | Retrofit + OkHttp |
| Local database | Room |
| Preferences | DataStore |
| Background work | WorkManager |
| Live foreground work | Foreground service with explicit user toggle |
| Async | Kotlin coroutines + Flow |
| Navigation | Navigation Compose |

## Layering

```text
Presentation
  Compose screens
  ViewModels
  immutable UI state

Domain
  use cases
  business rules
  sync policies

Data
  repositories
  Retrofit services
  Room DAOs
  DataStore preferences
  telemetry collectors
```

Rules:

- Composables render state and emit events only.
- ViewModels coordinate UI state and call use cases.
- Repositories own local/remote data orchestration.
- Telemetry collectors expose typed values, not UI models.
- Sync logic must be testable outside Android UI.

## Suggested Module Layout

Start with this if the project is scaffolded as a multi-module app:

```text
:app
:core:model
:core:network
:core:database
:core:datastore
:core:ui
:feature:auth
:feature:dashboard
:feature:devices
:feature:alerts
:feature:incidents
:feature:settings
:sync
```

If this is too much for the first implementation pass, use one app module with equivalent package boundaries:

```text
com.sentinelx.mobile
  core.model
  core.network
  core.database
  core.datastore
  core.ui
  feature.auth
  feature.dashboard
  feature.devices
  feature.alerts
  feature.incidents
  feature.settings
  sync
  telemetry
```

## Data Flow

```text
Compose Screen
  -> ViewModel
  -> UseCase
  -> Repository
  -> Local Room/DataStore and Remote API
  -> Repository emits Flow
  -> ViewModel exposes UI state
  -> Compose re-renders
```

## Background Execution Model

Android does not support a hidden always-on agent model in a production-friendly way. Use a hybrid design:

### Reliable Sync Mode

- Implemented with WorkManager.
- Always available after login and registration.
- Runs periodic sync with minimum interval of 15 minutes.
- Uses network constraints.
- Flushes pending Room queue.
- Schedules unique work to avoid duplicate workers.

### Live Mode

- Implemented with a foreground service.
- Disabled by default.
- Enabled only by explicit user action.
- Shows a persistent notification.
- Samples at a sensible interval such as 15-60 seconds.
- Still writes through the same queue/upload path.

## Local Persistence

### Room

Use Room for:

- Pending telemetry batches.
- Sent/failed sync records.
- Cached dashboard summaries.
- Cached device, alert, and incident lists.

Core entities:

- `TelemetryBatchEntity`
- `TelemetrySampleEntity`
- `DeviceEntity`
- `AlertEntity`
- `IncidentEntity`
- `SyncAttemptEntity`

### DataStore

Use DataStore for:

- Backend base URL if configurable.
- User preferences.
- Live Mode setting.
- Theme setting when added.
- Last selected organization if needed.

Token storage should use encrypted storage or Keystore-backed protection, not plain preferences.

## Telemetry Collector Boundaries

Collectors should be small, synchronous or suspendable classes:

- `BatteryTelemetryCollector`
- `MemoryTelemetryCollector`
- `StorageTelemetryCollector`
- `NetworkTelemetryCollector`
- `DeviceInfoCollector`

Each collector returns a domain model that is mapped to the API DTO and Room entity.

## Sync Engine

Responsibilities:

- Create idempotent batch IDs.
- Insert collected telemetry into Room.
- Upload pending batches.
- Mark acknowledged batches as sent.
- Increment attempt count on failure.
- Apply backoff.
- Cap queue size to avoid unlimited local growth.
- Expose sync status to the dashboard.

## UI Screens

P0 screens:

- Splash/session restore.
- Login.
- Dashboard.
- Devices list.
- Device detail.
- Alerts list.
- Incidents list.
- Profile.
- Settings.

The dashboard should show:

- Backend connection state.
- Last successful sync.
- Queue depth.
- Local device health.
- Fleet summary from backend.
- Active alerts/incidents summary.

