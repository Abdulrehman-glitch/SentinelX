# SentinelX Android Roadmap

## Roadmap Strategy

The first Android milestone should be a narrow vertical slice, not a broad UI shell. The priority is to prove the agent pipeline end to end:

```text
login -> register device -> collect telemetry -> queue locally -> upload -> display status
```

After that slice works, add broader console screens, Live Mode, tests, release signing, and distribution hardening.

## Phase 0: Contract and Project Setup

Estimated effort: 2-3 working days

Deliverables:

- Confirm backend endpoints and auth flow.
- Freeze v1 telemetry schema.
- Decide whether to add `/api/v1/mobile/*` backend routes or reuse existing routes.
- Choose package name, app name, min SDK, and target SDK.
- Create Android Studio project.
- Add Gradle version catalog and core dependencies.
- Configure debug/release build variants.

Definition of done:

- API contract is documented and accepted.
- Empty app builds.
- CI or local Gradle command can run `assembleDebug`.

## Phase 1: Auth and Session

Estimated effort: 3-4 working days

Deliverables:

- Login screen.
- JWT login request.
- Session restore.
- Logout.
- Secure token/session persistence.
- Basic authenticated navigation shell.

Definition of done:

- User can log in against SentinelX.
- App restores session after process restart.
- Logout clears session and returns to login.

## Phase 2: Device Registration and Telemetry Collectors

Estimated effort: 4-5 working days

Deliverables:

- Device registration flow.
- Device identity collector.
- Battery collector.
- Memory collector.
- Storage collector.
- Network collector.
- Initial local domain models and mappers.

Definition of done:

- Pixel 4 XL registers idempotently.
- App can collect one full telemetry snapshot.
- Collector unit tests exist for mapper logic and edge cases where practical.

## Phase 3: Local Queue and Upload Path

Estimated effort: 4-5 working days

Deliverables:

- Room schema for batches and samples.
- Queue DAO and repository.
- Retrofit telemetry upload endpoint.
- Retry/error mapping.
- Queue retention/backpressure policy.

Definition of done:

- Telemetry is inserted locally before upload.
- Successful upload marks batches as sent.
- Failed upload leaves data pending with attempt count.
- Duplicate batch upload is safe if backend supports idempotency.

## Phase 4: Dashboard and Console MVP

Estimated effort: 5-6 working days

Deliverables:

- Dashboard screen.
- Devices list and detail screen.
- Alerts list.
- Incidents list.
- Profile screen.
- Settings screen.
- Shared UI components and theme.

Definition of done:

- Dashboard shows backend state, local device state, last sync, queue depth, alerts, incidents, and health summary.
- Console screens handle loading, empty, error, and success states.
- UI follows a professional SentinelX visual style without copying the web app blindly.

## Phase 5: WorkManager Reliable Sync

Estimated effort: 3-4 working days

Deliverables:

- Unique periodic sync worker.
- Network constraints.
- One-time sync trigger after login/register.
- Sync status exposed to dashboard.
- Worker tests where feasible.

Definition of done:

- Pending batches sync after connectivity returns.
- No duplicate periodic workers are scheduled.
- Work survives app process death.

## Phase 6: Live Mode Foreground Service

Estimated effort: 3-4 working days

Deliverables:

- Live Mode setting/toggle.
- Foreground service.
- Notification channel.
- Runtime notification permission handling for Android 13+.
- Service samples through same queue/upload path.

Definition of done:

- Live Mode is off by default.
- When enabled, a persistent notification is visible.
- Disabling Live Mode stops the service.
- Sampling interval is configurable or conservatively fixed.

## Phase 7: Testing, Release, and Pixel Validation

Estimated effort: 4-6 working days

Deliverables:

- Unit tests for core collectors/mappers/repositories.
- Room tests for queue state transitions.
- ViewModel tests for dashboard/auth flows.
- Compose UI smoke tests.
- Release signing documentation.
- Signed APK.
- Pixel 4 XL validation notes.

Definition of done:

- `testDebugUnitTest` passes.
- `assembleRelease` creates a signed APK.
- APK installs through ADB on Pixel 4 XL.
- Offline/online retry is manually verified.
- Battery behavior is sanity-checked during Live Mode.

## Phase 8: v2 Enhancements

Candidate features:

- Push notifications.
- Alert acknowledgement.
- Remote config.
- WebSocket live telemetry.
- Optional location.
- Optional sensors.
- QR enrollment.
- Remote recovery actions.
- Firebase App Distribution or Play Internal Testing.
- Baseline Profiles and Macrobenchmark.

## Detailed Task Backlog

| Priority | Task |
|---|---|
| P0 | Inspect current FastAPI routes and choose final endpoint mapping. |
| P0 | Scaffold Android project with Kotlin, Compose, Hilt, Retrofit, Room, DataStore, WorkManager. |
| P0 | Implement login and session restore. |
| P0 | Implement device registration. |
| P0 | Implement battery, memory, storage, network collectors. |
| P0 | Implement Room queue. |
| P0 | Implement telemetry batch upload. |
| P0 | Implement dashboard status cards. |
| P0 | Implement WorkManager sync. |
| P0 | Build signed APK and install on Pixel 4 XL. |
| P1 | Add devices, alerts, incidents read-only screens. |
| P1 | Add foreground service Live Mode. |
| P1 | Add testing foundation. |
| P1 | Add CI build workflow. |
| P2 | Add push notifications or alert acknowledgement. |
| P2 | Add optional sensors/location after privacy review. |
| P2 | Add Play distribution readiness. |

