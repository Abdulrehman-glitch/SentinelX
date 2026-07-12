# Source Analysis: Research Report and PRD

## Inputs Reviewed

- `deep-research-report.md`
- `SentinelX_Mobile_PRD.md`

## Shared Conclusions

Both documents support the same broad direction:

- Build a native Android app in Kotlin.
- Use Jetpack Compose for the UI.
- Use MVVM/Clean Architecture.
- Use Hilt for dependency injection.
- Use Retrofit for backend communication.
- Use Room for local structured storage.
- Use DataStore for settings/preferences.
- Use WorkManager for durable background sync.
- Ship as an internal signed APK first.
- Prepare for Google Play later, not as the initial distribution route.

## Product Shape

The PRD describes SentinelX Mobile as both:

- a mobile monitoring agent; and
- a mobile operations console.

The research report strengthens this by framing the app as a "managed telemetry endpoint" rather than a simple phone dashboard. That framing is important because it means reliability, local persistence, explicit background behavior, secure distribution, and observability are core product requirements, not polish.

## Android Platform Reality

The research report adds platform constraints that the PRD only hints at:

- Android background execution is limited.
- Always-on hidden monitoring is not a production-friendly goal.
- Periodic WorkManager jobs have a minimum interval of 15 minutes.
- Continuous monitoring requires a foreground service with a visible notification.
- Android 13+ notification permission affects foreground service user experience.
- Android 14+ foreground service types and permissions must be declared correctly.
- Android 15+ adds stricter foreground service limits for some service types.

Planning implication:

- v1 should have Reliable Sync Mode through WorkManager.
- Live Mode should be explicit, user-enabled, and visible.
- Do not design the Android agent as an invisible daemon.

## PRD Strengths

The PRD provides a clear v1 product structure:

- Login/logout.
- JWT authentication.
- Device registration.
- Heartbeat.
- Battery, RAM, storage, network, and device information.
- Dashboard, devices, alerts, incidents, profile, and settings.
- Offline support.
- Professional UI.
- Test coverage and release deliverables.

These are appropriate for a portfolio-quality MVP if implementation starts with a narrow vertical slice.

## PRD Gaps

The PRD is intentionally high-level and needs clarification before implementation:

- Endpoint paths are proposed, not verified against the existing FastAPI backend.
- It says "real-time telemetry", but Android constraints mean v1 should define "real-time" carefully.
- It lists optional foreground service permissions, but Live Mode requires a deliberate service and notification design.
- It does not distinguish user auth from device/agent auth.
- It does not define local queue retention, idempotency, or retry behavior.
- It does not specify telemetry payload shape.
- It does not define how RBAC maps to mobile screens.

The generated docs address these gaps as implementation requirements.

## Backend Contract Conflict

The PRD proposes:

```text
POST /auth/login
POST /mobile/register
POST /mobile/heartbeat
POST /mobile/telemetry

GET /dashboard
GET /devices
GET /alerts
GET /incidents
```

The existing repository guidance says:

- API routes are under `/api/v1`.
- Login currently exists under `/api/v1/auth/login`.
- The existing Python agent posts metrics to `/api/v1/metrics`.
- Device/agent endpoints use raw bearer-token auth.

Planning implication:

- Do not scaffold hardcoded `/mobile/*` routes until backend alignment is done.
- Prefer `/api/v1/mobile/*` if new mobile-specific routes are added.
- If backend changes must be minimal, adapt Android to existing `/api/v1/*` routes.

## Scope Recommendation

v1 should focus on:

- Auth.
- Device registration.
- Heartbeat.
- Battery/memory/storage/network telemetry.
- Local Room queue.
- WorkManager sync.
- Compose dashboard.
- Console read-only views.
- Signed APK on Pixel 4 XL.

v1 should avoid:

- Location.
- Running-app inventory.
- Continuous raw sensor streaming.
- Remote recovery commands.
- Push notifications.
- WebSocket live streams.
- Google Play public release.

## Key Product Decision

The correct v1 promise is not "hidden always-on mobile monitoring."

The correct v1 promise is:

> SentinelX Android reliably collects and syncs Android device health telemetry, supports an explicit Live Mode when continuous monitoring is needed, and provides authenticated mobile visibility into SentinelX operations.

## Implementation Readiness

The project is ready for backend contract alignment and Android scaffolding after these decisions are confirmed:

1. Final endpoint list.
2. Final auth model: user token only, device token only, or both.
3. Final telemetry schema.
4. Minimum supported Android version.
5. Whether Live Mode is included in the first APK or added immediately after the first sync slice.

