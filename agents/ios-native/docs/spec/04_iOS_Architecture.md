# 04_iOS_Architecture.md

# SentinelX Mobile Agent

## iOS Architecture Guide

Version: 1.0 Platform: iOS 17+ Language: Swift 6+ UI Framework: SwiftUI
Architecture: MVVM + Repository + Service Layer + Collector Layer

------------------------------------------------------------------------

# 1. Purpose

This document defines the iOS application architecture for the SentinelX
Mobile Agent.

The app must be production-quality, modular, testable, secure, and built
only with Apple's public APIs.

This file is intended for Claude Code and should be used as the source
of truth for all iOS implementation decisions.

------------------------------------------------------------------------

# 2. Core Architecture

The iOS app uses a layered architecture:

``` text
SwiftUI Views
    ↓
ViewModels
    ↓
Repositories
    ↓
Services
    ↓
Collectors / Networking / Persistence
    ↓
Apple Frameworks
```

Core pattern:

``` text
Presentation Layer
Domain Layer
Data Layer
Infrastructure Layer
```

------------------------------------------------------------------------

# 3. Architecture Goals

-   Clear separation of concerns
-   Testable modules
-   Low coupling
-   High cohesion
-   Async/Await first
-   No private APIs
-   No business logic inside Views
-   No direct API calls from Views
-   No direct Apple framework access from Views
-   All telemetry passes through TelemetryManager

------------------------------------------------------------------------

# 4. Recommended Folder Structure

``` text
SentinelXMobileAgent/
│
├── App/
│   ├── SentinelXMobileAgentApp.swift
│   ├── AppContainer.swift
│   └── AppEnvironment.swift
│
├── Features/
│   ├── Authentication/
│   ├── Dashboard/
│   ├── DeviceStatus/
│   ├── Settings/
│   ├── Permissions/
│   └── Diagnostics/
│
├── Views/
│   ├── Components/
│   ├── Screens/
│   └── Shared/
│
├── ViewModels/
│   ├── AuthViewModel.swift
│   ├── DashboardViewModel.swift
│   ├── DeviceStatusViewModel.swift
│   └── SettingsViewModel.swift
│
├── Models/
│   ├── DeviceProfile.swift
│   ├── TelemetryEvent.swift
│   ├── TelemetryCategory.swift
│   ├── Alert.swift
│   ├── CollectorConfig.swift
│   └── APIModels.swift
│
├── Collectors/
│   ├── TelemetryCollector.swift
│   ├── DeviceCollector.swift
│   ├── BatteryCollector.swift
│   ├── ThermalCollector.swift
│   ├── StorageCollector.swift
│   ├── NetworkCollector.swift
│   ├── MotionCollector.swift
│   ├── ActivityCollector.swift
│   ├── LocationCollector.swift
│   ├── BluetoothCollector.swift
│   └── MetricKitCollector.swift
│
├── Services/
│   ├── TelemetryManager.swift
│   ├── SyncManager.swift
│   ├── AuthService.swift
│   ├── DeviceRegistrationService.swift
│   ├── ConfigurationService.swift
│   ├── AlertService.swift
│   └── PermissionService.swift
│
├── Networking/
│   ├── APIClient.swift
│   ├── APIEndpoint.swift
│   ├── WebSocketClient.swift
│   ├── RESTTelemetryClient.swift
│   ├── NetworkMonitor.swift
│   └── APIError.swift
│
├── Persistence/
│   ├── TelemetryQueue.swift
│   ├── SQLiteTelemetryStore.swift
│   ├── KeychainStore.swift
│   └── UserDefaultsStore.swift
│
├── Security/
│   ├── TokenStore.swift
│   ├── DeviceSecretStore.swift
│   └── CertificateValidator.swift
│
├── Utilities/
│   ├── Logger.swift
│   ├── DateProvider.swift
│   ├── UUIDProvider.swift
│   ├── RetryPolicy.swift
│   └── AppConstants.swift
│
└── Tests/
    ├── UnitTests/
    ├── IntegrationTests/
    └── MockServices/
```

------------------------------------------------------------------------

# 5. App Container

Use a central AppContainer for dependency injection.

Responsibilities: - Create shared services - Inject dependencies into
ViewModels - Hold environment configuration - Avoid singletons where
possible

Example dependencies: - APIClient - WebSocketClient - TelemetryManager -
SyncManager - TokenStore - TelemetryQueue - PermissionService -
Collector registry

------------------------------------------------------------------------

# 6. MVVM Rules

Views: - Render UI only - Trigger ViewModel actions - Contain no
networking - Contain no persistence logic - Contain no telemetry
collection logic

ViewModels: - Manage screen state - Call repositories/services - Expose
@Published or Observable state - Handle loading/error/success state

Services: - Contain business logic - Coordinate networking, collectors,
queue, and auth

Repositories: - Abstract remote/local data access where useful

------------------------------------------------------------------------

# 7. Telemetry Collector Protocol

All collectors must conform to a shared protocol.

``` swift
protocol TelemetryCollector {
    var id: String { get }
    var category: TelemetryCategory { get }
    var isEnabled: Bool { get }

    func start() async
    func stop() async
    func latestValue() async -> TelemetryEvent?
    func healthStatus() async -> CollectorHealth
}
```

Collector health states:

``` swift
enum CollectorHealth: String, Codable {
    case healthy
    case degraded
    case disabled
    case permissionDenied
    case unsupported
    case failed
}
```

------------------------------------------------------------------------

# 8. Telemetry Manager

TelemetryManager is the central coordinator.

Responsibilities: - Register collectors - Start collectors - Stop
collectors - Receive telemetry events - Validate event payloads - Add
events to local queue - Forward events to SyncManager - Apply collector
configuration - Throttle high-frequency data - Track collector health

No collector should directly communicate with the backend.

------------------------------------------------------------------------

# 9. Collector Registry

Use a CollectorRegistry to manage collectors.

``` text
CollectorRegistry
    ├── BatteryCollector
    ├── ThermalCollector
    ├── StorageCollector
    ├── NetworkCollector
    ├── MotionCollector
    ├── ActivityCollector
    ├── LocationCollector
    ├── BluetoothCollector
    └── MetricKitCollector
```

The registry should support: - enable collector - disable collector -
start all - stop all - get health status - apply remote config

------------------------------------------------------------------------

# 10. Telemetry Event Model

All telemetry events use a common envelope.

``` swift
struct TelemetryEvent: Codable, Identifiable {
    let id: UUID
    let deviceId: String
    let timestamp: Date
    let category: TelemetryCategory
    let type: String
    let source: String
    let sequence: Int?
    let payload: TelemetryPayload
    let metadata: TelemetryMetadata?
}
```

Payload should support flexible JSON encoding.

Recommended approach: - Use Codable concrete payload structs for known
event types. - Convert payloads to dictionary/JSON before
storage/upload. - Avoid untyped Any where possible.

------------------------------------------------------------------------

# 11. Telemetry Categories

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

------------------------------------------------------------------------

# 12. Device Collector

Framework: - UIKit - Foundation

Collect: - device name - model - system name - system version - locale -
timezone - screen scale - screen size

Frequency: - On startup - On app foreground

------------------------------------------------------------------------

# 13. Battery Collector

Framework: - UIDevice - ProcessInfo

Collect: - battery level - charging state - low power mode

Frequency: - Every 30 seconds - On battery state change - On power mode
change

Notes: - Enable battery monitoring before reading battery level. -
Battery health and cycle count are not available.

------------------------------------------------------------------------

# 14. Thermal Collector

Framework: - ProcessInfo

Collect: - thermal state

Frequency: - On thermal state change - On startup

Values: - nominal - fair - serious - critical

------------------------------------------------------------------------

# 15. Storage Collector

Framework: - FileManager

Collect: - total storage - free storage - used storage

Frequency: - Every 60 seconds - On startup

------------------------------------------------------------------------

# 16. Network Collector

Framework: - Network

Use: - NWPathMonitor

Collect: - reachable - interface type - expensive network - constrained
network

Frequency: - On network path change

Do not attempt: - general Wi-Fi scanning - Wi-Fi passwords - packet
capture

------------------------------------------------------------------------

# 17. Motion Collector

Framework: - CoreMotion

Use: - CMMotionManager

Collect: - accelerometer - gyroscope - gravity - user acceleration -
rotation rate - attitude - pitch - roll - yaw

Default sampling: - 20 Hz

Rules: - Downsample before upload if needed. - Stop collection when
disabled. - Reduce frequency in Low Power Mode. - Never stream extremely
high frequency data without throttling.

------------------------------------------------------------------------

# 18. Activity Collector

Framework: - CoreMotion

Use: - CMMotionActivityManager

Collect: - stationary - walking - running - cycling - automotive -
unknown - confidence

Frequency: - On change

------------------------------------------------------------------------

# 19. Location Collector

Framework: - CoreLocation

Collect: - latitude - longitude - altitude - speed - heading -
horizontal accuracy - vertical accuracy - timestamp

Default: - Balanced accuracy - 5 second interval where possible

Rules: - Ask permission in context. - Support When In Use first. -
Support Always only if background mode is implemented clearly. - Use
significant location updates for low-power background operation. -
Respect reduced accuracy.

------------------------------------------------------------------------

# 20. Bluetooth Collector

Framework: - CoreBluetooth

Collect: - nearby BLE device name - identifier - RSSI - advertisement
metadata - service UUIDs if available

Rules: - Bluetooth permission required. - No classic Bluetooth
monitoring. - No system Bluetooth traffic capture.

Default: - Disabled until user enables it.

------------------------------------------------------------------------

# 21. MetricKit Collector

Framework: - MetricKit

Collect: - crash diagnostics - hang diagnostics - launch metrics -
memory metrics - energy metrics - app CPU metrics

Important: - MetricKit is not real-time. - Reports are delivered by the
system. - Use it for diagnostics and historical performance.

------------------------------------------------------------------------

# 22. Sync Manager

Responsibilities: - Maintain WebSocket connection - Send telemetry
events - Send heartbeat - Detect disconnect - Reconnect with exponential
backoff - Use REST fallback - Flush offline queue - Respect network
constraints

WebSocket is primary for live telemetry. REST is fallback for
durability.

------------------------------------------------------------------------

# 23. WebSocket Client

Responsibilities: - Connect - Authenticate - Send heartbeat every 30
seconds - Send telemetry.event messages - Receive config updates -
Receive server commands - Reconnect on failure

States:

``` swift
enum WebSocketState {
    case disconnected
    case connecting
    case authenticating
    case connected
    case reconnecting
    case failed
}
```

------------------------------------------------------------------------

# 24. REST Client

Responsibilities: - Device registration - Login - Token refresh - Single
telemetry upload - Batch upload - Config fetch - Profile update

Must: - attach JWT - refresh expired token - handle 401 - retry safe
requests - decode standard errors

------------------------------------------------------------------------

# 25. Offline Queue

Use SQLite.

Responsibilities: - Persist telemetry events before upload - FIFO
ordering - Retry failed uploads - Delete only after acknowledgement -
Support batch upload - Support duplicate protection - Cleanup old events

Queue states: - pending - inFlight - uploaded - failed

------------------------------------------------------------------------

# 26. Background Execution

Use: - BackgroundTasks - URLSession background transfers where
appropriate

Background tasks: - Flush queue - Refresh config - Send heartbeat-like
status update if allowed

Important: - iOS does not guarantee continuous background execution. -
Do not design as an always-on daemon. - Foreground streaming is
real-time. - Background mode is opportunistic.

------------------------------------------------------------------------

# 27. Permissions

Required permissions: - Location - Motion & Fitness - Bluetooth

Optional: - Notifications - HealthKit

Permission UX: - Explain why permission is needed before asking. - Ask
only when feature is enabled. - Allow user to disable collectors.

------------------------------------------------------------------------

# 28. Security Architecture

Use: - Keychain for tokens - Keychain for device secret - HTTPS only -
TLS validation - No sensitive data in logs - User-controlled data
collection - Clear privacy screen

Never store: - raw passwords - raw device secret in UserDefaults - JWT
in plain UserDefaults

------------------------------------------------------------------------

# 29. Logging

Use OSLog.

Log: - collector start/stop - collector health changes - WebSocket
connection events - upload failures - auth failures - queue flush
results

Do not log: - access tokens - refresh tokens - device secret - precise
location payloads in debug logs unless explicitly enabled

------------------------------------------------------------------------

# 30. Configuration

The backend can control: - enabled collectors - sampling intervals -
batch size - WebSocket enabled/disabled - REST fallback
enabled/disabled - location accuracy - motion sampling rate

Configuration must be cached locally.

------------------------------------------------------------------------

# 31. App Screens

Minimum screens: - Login / Register Device - Permissions Setup - Live
Device Status - Collector Health - Telemetry Stream Debug View -
Settings - Privacy / Consent

Optional: - Local alerts - Diagnostics - Upload queue status

------------------------------------------------------------------------

# 32. State Management

Recommended: - ObservableObject / @Observable - @State for local view
state - @StateObject for ViewModel ownership - @Environment for app-wide
dependencies where appropriate

Avoid: - Global mutable state - Networking inside Views - Large
monolithic ViewModels

------------------------------------------------------------------------

# 33. Testing Strategy

Unit test: - collectors - payload encoding - API client - retry policy -
queue logic - auth token refresh - config parsing

Integration test: - WebSocket connection - REST batch upload - SQLite
persistence

Mock: - APIClient - WebSocketClient - TelemetryQueue - TokenStore -
collectors

------------------------------------------------------------------------

# 34. Error Handling

Use typed errors.

Examples: - AuthError - APIError - WebSocketError - CollectorError -
PersistenceError - PermissionError

All user-facing errors should be clear and non-technical.

------------------------------------------------------------------------

# 35. Battery Optimisation

Rules: - Reduce motion sampling in Low Power Mode. - Pause
high-frequency collectors when app is backgrounded. - Batch uploads. -
Avoid constant GPS unless explicitly enabled. - Respect
constrained/expensive networks. - Stop unused collectors.

------------------------------------------------------------------------

# 36. App Lifecycle Handling

On launch: - Load tokens - Load cached config - Register collectors -
Start safe collectors - Connect WebSocket if authenticated

On foreground: - Resume live streaming - Refresh config - Flush queue

On background: - Persist pending events - Stop high-frequency
collectors - Schedule background sync

On logout: - Stop collectors - Disconnect WebSocket - Clear secure
tokens - Preserve or delete local telemetry based on user choice

------------------------------------------------------------------------

# 37. Implementation Order

1.  App shell
2.  AppContainer
3.  Models
4.  APIClient
5.  TokenStore
6.  Device registration
7.  Auth flow
8.  TelemetryEvent model
9.  Battery / thermal / device collectors
10. TelemetryManager
11. SQLite queue
12. WebSocket client
13. REST fallback
14. Network collector
15. Storage collector
16. Motion collector
17. Location collector
18. Bluetooth collector
19. MetricKit collector
20. Settings and permissions UI
21. Tests

------------------------------------------------------------------------

# 38. Claude Code Rules

Claude Code must: - Use native Swift and SwiftUI. - Avoid private
APIs. - Avoid overengineering. - Generate full files when requested. -
Keep architecture modular. - Use comments for non-obvious logic. - Not
hardcode backend URLs. - Use configuration files or environment
constants. - Keep future Android compatibility in mind through
platform-neutral schemas.

End of document.
