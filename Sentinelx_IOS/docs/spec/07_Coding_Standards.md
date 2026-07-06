
# 07_Coding_Standards.md

# SentinelX Mobile Agent
## Coding Standards and Engineering Guidelines

Version: 1.0  
Applies To:
- iOS Swift Agent
- FastAPI Backend
- Dashboard Integration
- Future Android Agent

---

# 1. Purpose

This document defines the coding standards for the SentinelX Mobile Agent project.

It exists to keep the codebase:
- consistent
- maintainable
- secure
- testable
- production-ready
- easy for Claude Code and future developers to extend

Claude Code must follow this document when generating, editing, or reviewing code.

---

# 2. Core Engineering Principles

The project must follow these principles:

- Production quality over quick hacks
- Simple solutions before complex abstractions
- Public APIs only
- Privacy-first design
- Security by default
- Strong typing
- Modular architecture
- Testable code
- Clear naming
- Explicit error handling
- No hidden side effects
- No hardcoded secrets
- No private Apple APIs

---

# 3. Swift Version and Platform

Target:
- Swift 6+
- iOS 17+
- SwiftUI
- Async/Await
- Structured Concurrency
- Swift Package Manager

Do not use:
- Private Apple frameworks
- Jailbreak APIs
- Deprecated APIs unless clearly justified
- Objective-C unless required by Apple framework integration

---

# 4. Architecture Rules

The iOS app follows:

```text
SwiftUI Views
    ↓
ViewModels
    ↓
Services / Repositories
    ↓
Collectors / Networking / Persistence
    ↓
Apple Frameworks
```

Rules:
- Views must not call APIs directly.
- Views must not access Apple telemetry frameworks directly.
- ViewModels must not contain low-level networking code.
- Collectors must not directly upload telemetry.
- All telemetry must pass through TelemetryManager.
- All remote communication must pass through APIClient or WebSocketClient.
- All secure storage must pass through TokenStore or DeviceSecretStore.

---

# 5. Naming Conventions

## Swift Types

Use UpperCamelCase.

Examples:

```swift
TelemetryManager
BatteryCollector
DeviceProfile
WebSocketClient
```

## Swift Variables and Functions

Use lowerCamelCase.

Examples:

```swift
deviceId
startCollection()
sendTelemetryEvent()
refreshAccessToken()
```

## Constants

Use lowerCamelCase unless globally significant.

```swift
let defaultBatchSize = 100
let heartbeatIntervalSeconds = 30
```

## Enum Cases

Use lowerCamelCase.

```swift
case connected
case reconnecting
case permissionDenied
```

## JSON Keys

Use snake_case.

```json
{
  "device_id": "dev_001",
  "access_token": "token"
}
```

Use `CodingKeys` to map between Swift camelCase and API snake_case.

---

# 6. File Naming

Each file should contain one main type.

Good:

```text
BatteryCollector.swift
TelemetryManager.swift
DeviceProfile.swift
AuthViewModel.swift
```

Avoid:

```text
Helpers.swift
Managers.swift
Models.swift
Everything.swift
```

Utility files are allowed only when focused:

```text
DateFormatterFactory.swift
RetryPolicy.swift
Logger.swift
```

---

# 7. SwiftUI Standards

Views must:
- Be small and composable
- Use ViewModels for logic
- Avoid direct service calls
- Avoid large computed bodies
- Use reusable components
- Handle loading, error, and empty states

Example:

```swift
struct BatteryStatusView: View {
    let level: Int
    let charging: Bool

    var body: some View {
        VStack(alignment: .leading) {
            Text("Battery")
            Text("\(level)%")
            Text(charging ? "Charging" : "Not Charging")
        }
    }
}
```

Avoid:
- Networking inside `.onAppear`
- Business logic inside View body
- Large nested UI blocks
- Force unwraps

---

# 8. ViewModel Standards

ViewModels should:
- Be marked `@MainActor` when updating UI state
- Expose immutable state where possible
- Use async methods for async work
- Contain no direct Apple framework telemetry access
- Convert service results into UI state

Example:

```swift
@MainActor
final class DashboardViewModel: ObservableObject {
    @Published private(set) var state: DashboardState = .idle

    private let telemetryManager: TelemetryManager

    init(telemetryManager: TelemetryManager) {
        self.telemetryManager = telemetryManager
    }

    func start() async {
        state = .loading
        await telemetryManager.start()
        state = .ready
    }
}
```

---

# 9. Service Standards

Services contain business logic.

Examples:
- AuthService
- SyncManager
- TelemetryManager
- ConfigurationService
- PermissionService

Rules:
- Services should be protocol-driven where useful.
- Services should be injectable.
- Services should avoid UI dependencies.
- Services should return typed results or throw typed errors.

---

# 10. Collector Standards

Each collector must:
- Conform to `TelemetryCollector`
- Have a single responsibility
- Report health
- Fail gracefully
- Respect permissions
- Respect low power mode where relevant
- Stop cleanly

Collector responsibilities:
- Collect telemetry
- Convert raw data into payload
- Emit TelemetryEvent
- Report CollectorHealth

Collectors must not:
- Upload data directly
- Store tokens
- Manage WebSocket connections
- Know dashboard logic

---

# 11. Async/Await Standards

Use async/await for:
- API calls
- WebSocket operations
- Database operations
- Collector start/stop
- Queue flushing

Avoid:
- Callback pyramids
- Unstructured background tasks
- Fire-and-forget tasks without cancellation

Use task cancellation where appropriate.

Example:

```swift
func start() async {
    guard !Task.isCancelled else { return }
    await collector.start()
}
```

---

# 12. Error Handling Standards

Use typed errors.

Examples:

```swift
enum AuthError: Error {
    case invalidCredentials
    case tokenExpired
    case missingDeviceSecret
}

enum CollectorError: Error {
    case permissionDenied
    case unsupported
    case unavailable
}
```

Rules:
- Do not swallow errors silently.
- Do not expose raw technical errors to users.
- Log technical details safely.
- Show friendly UI messages.
- Keep retryable and non-retryable errors separate.

---

# 13. Logging Standards

Use OSLog on iOS.

Log:
- Collector start/stop
- Collector health change
- Auth success/failure
- WebSocket connect/disconnect
- Queue flush result
- Upload failure
- Configuration update

Never log:
- access tokens
- refresh tokens
- device secrets
- passwords
- precise location payloads unless explicit debug mode is enabled
- health data payloads

Example:

```swift
logger.info("BatteryCollector started")
logger.error("WebSocket disconnected: \(error.localizedDescription)")
```

---

# 14. Security Standards

Required:
- HTTPS only
- TLS validation
- Keychain for tokens
- Keychain for device secret
- No secrets in UserDefaults
- No hardcoded credentials
- No private APIs
- No jailbreak detection bypass logic
- No spyware behaviour

Sensitive data:
- location
- Bluetooth scan results
- health data
- crash diagnostics
- persistent identifiers

Rules:
- Ask permission clearly.
- Explain why data is collected.
- Allow disabling collectors.
- Avoid unnecessary data collection.
- Minimise data retention.

---

# 15. Privacy Standards

The app must clearly communicate:
- what data is collected
- why it is collected
- how it is transmitted
- how it can be disabled
- whether location is enabled
- whether Bluetooth scanning is enabled
- whether HealthKit is enabled

Privacy-first defaults:
- Bluetooth disabled by default
- HealthKit disabled by default
- Location requires explicit permission
- Motion requires permission
- High-frequency motion sampling should be configurable

---

# 16. API Client Standards

APIClient must:
- Use URLSession
- Attach JWT automatically
- Refresh expired tokens
- Decode standard error responses
- Use typed request/response models
- Support request IDs
- Avoid hardcoded base URLs

API errors must map to typed APIError.

Example:

```swift
enum APIError: Error {
    case unauthorized
    case forbidden
    case validation(String)
    case rateLimited(retryAfter: Int?)
    case serverError
    case decodingFailed
    case networkUnavailable
}
```

---

# 17. WebSocket Standards

WebSocketClient must:
- Connect using configured backend URL
- Authenticate after connection
- Send heartbeat every 30 seconds
- Reconnect using exponential backoff
- Stop reconnecting after logout
- Support server commands
- Queue telemetry if disconnected

States:

```swift
enum WebSocketState {
    case disconnected
    case connecting
    case authenticating
    case connected
    case reconnecting
    case failed
}
```

---

# 18. Persistence Standards

Use SQLite for telemetry queue.

Rules:
- Store telemetry before upload.
- Delete only after acknowledgement.
- Use event_id for idempotency.
- Store retry_count.
- Store last_error.
- Keep FIFO ordering.
- Cleanup old uploaded events.

Do not store:
- JWT
- refresh token
- device secret
- raw passwords

Those belong in Keychain.

---

# 19. Configuration Standards

Do not hardcode collector intervals inside collectors.

Use configuration from:
- default local config
- backend remote config
- user settings override where appropriate

Configurable:
- enabled collectors
- battery interval
- storage interval
- motion sample rate
- location accuracy
- batch size
- flush interval
- WebSocket enabled
- REST fallback enabled

---

# 20. Performance Standards

Targets:
- App launch under 2 seconds
- Memory below 100 MB during normal usage
- Average CPU below 5%
- WebSocket latency under 500 ms where network allows
- Reconnect under 5 seconds where possible
- Battery impact below 2% per hour during normal monitoring

Performance rules:
- Batch uploads
- Avoid unnecessary GPS
- Reduce motion sampling in Low Power Mode
- Pause high-frequency collectors in background
- Avoid repeated expensive storage calculations
- Avoid excessive UI refreshes
- Use throttling/debouncing

---

# 21. Battery Optimisation Rules

When Low Power Mode is enabled:
- Reduce motion sample rate
- Increase upload batching interval
- Reduce location accuracy
- Disable optional BLE scan unless user forces it
- Avoid unnecessary background work

High-frequency telemetry must always be configurable.

---

# 22. Testing Standards

Test priority:
1. Authentication
2. Token storage
3. API client
4. Telemetry event encoding
5. SQLite queue
6. Retry policy
7. Sync manager
8. Collectors
9. Configuration parsing
10. Alert logic

Unit tests should:
- Use mocks
- Avoid real network calls
- Avoid real Keychain where possible
- Be deterministic
- Test success and failure paths

Integration tests should:
- Use test backend or mocked server
- Validate REST payloads
- Validate WebSocket message format
- Validate offline queue flush

---

# 23. Dependency Injection Standards

Use AppContainer.

Rules:
- Avoid global singletons.
- Inject services into ViewModels.
- Inject APIClient into services.
- Inject TokenStore into AuthService.
- Inject TelemetryQueue into SyncManager.
- Inject collectors into TelemetryManager.

Benefits:
- easier testing
- cleaner architecture
- fewer hidden dependencies

---

# 24. Dependency Management

Use Swift Package Manager.

Before adding a dependency, ask:
- Is it necessary?
- Can Apple framework do this?
- Is it maintained?
- Does it increase security risk?
- Does it affect App Store approval?
- Does it complicate Claude Code implementation?

Prefer Apple-native frameworks when possible.

---

# 25. Backend Coding Standards

FastAPI backend should use:
- routers
- Pydantic models
- SQLAlchemy or SQLModel
- Alembic migrations
- dependency injection
- JWT utilities
- structured logging
- clear error responses

Backend rules:
- Validate all payloads.
- Never trust device_id from body alone.
- Match device_id with authenticated token.
- Hash device secrets.
- Store telemetry payloads as JSONB.
- Use idempotency on event_id.
- Rate limit ingestion endpoints.
- Do not log sensitive payloads.

---

# 26. Database Standards

Use:
- PostgreSQL
- TimescaleDB for time-series telemetry if available
- JSONB for flexible telemetry payloads
- indexes on device_id and timestamp
- unique index on event_id

Required:
- migrations
- seed/test data
- retention strategy
- cleanup strategy

Avoid:
- storing raw secrets
- unindexed telemetry queries
- duplicate telemetry events

---

# 27. API Design Standards

REST:
- Use nouns for resources
- Use versioned paths
- Use JSON
- Use standard status codes
- Use standard error response

WebSocket:
- Use typed message envelopes
- Include message type
- Include timestamp
- Include message_id where useful
- Authenticate before accepting telemetry

---

# 28. Git Commit Standards

Use conventional commits.

Examples:

```text
feat: add battery telemetry collector
fix: handle websocket reconnect failure
refactor: split telemetry queue storage
test: add auth service unit tests
docs: update backend API contract
perf: reduce motion sampling in low power mode
security: move device secret to keychain
```

Commit frequently:
- after each working feature
- after tests pass
- before major refactors
- after bug fixes

---

# 29. Code Review Checklist

Before accepting code, verify:

- Does it compile?
- Does it follow architecture?
- Are secrets protected?
- Are errors handled?
- Is logging safe?
- Is telemetry schema correct?
- Are permissions respected?
- Are tests added where needed?
- Does it avoid private APIs?
- Does it avoid hardcoded URLs/secrets?
- Does it preserve battery life?
- Does it remain App Store compliant?

---

# 30. Documentation Standards

Every major feature must have:
- purpose
- behaviour
- configuration
- error handling
- testing notes

Public methods should be self-explanatory.
Comments should explain why, not obvious what.

Good comment:

```swift
// Reduce motion sampling in Low Power Mode to avoid unnecessary battery drain.
```

Bad comment:

```swift
// Set sample rate to 10.
```

---

# 31. Do and Don't Examples

## Do

```swift
let token = try await tokenStore.getAccessToken()
```

## Don't

```swift
let token = UserDefaults.standard.string(forKey: "token")
```

## Do

```swift
try await telemetryQueue.enqueue(event)
```

## Don't

```swift
try await apiClient.postTelemetry(event)
```

from inside a collector.

## Do

```swift
logger.info("Telemetry upload completed")
```

## Don't

```swift
print("Token is \(accessToken)")
```

---

# 32. Claude Code Rules

Claude Code must:
- Follow all previous context documents.
- Generate complete files when requested.
- Avoid partial patches unless explicitly requested.
- Keep code modular.
- Avoid private APIs.
- Avoid overengineering.
- Ask before adding dependencies.
- Preserve existing architecture.
- Use clear commit messages.
- Add tests for critical logic.
- Never store secrets in plain text.
- Never invent unsupported iOS telemetry access.
- Be honest about Apple API limitations.

---

# 33. Definition of Quality

Code is considered acceptable only when:
- It builds successfully.
- It follows this coding standard.
- It respects the data model document.
- It respects the backend API contract.
- It has clear error handling.
- It does not introduce security issues.
- It avoids unnecessary complexity.
- It can be tested.
- It can be maintained by another developer.

End of document.
