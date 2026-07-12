# SentinelX Android Project Memory

Last updated: 2026-07-12

## v1.2.0 (same session, round 2)

- Round-2 test sweep (evidence 17–29): revoked-token error path, RBAC viewer block, unlink/sign-out dialogs, wrong-password, force-stop persistence, rotation, 1.3× font scale — all pass. Found+fixed F14: Settings lacked BackHandler (hardware back exited app).
- Glass UI: `ui/theme/Glass.kt` (GlassBackground gradient + GlassPanel frosted card) applied to all screens, light+dark. v1.2.0 / versionCode 3.
- Upgrade install v1.1.0→v1.2.0 on emulator preserved enrollment (checklist upgrade test PASS).
- Version control live: work committed on `feature/android-mobile-agent` (3 commits), tagged `android-v1.2.0`; CHANGELOG.md tracks app versions; keystore + local.properties + build/ gitignored, dist/ APKs tracked (negation rule in root .gitignore).
- `dist/SentinelX-Android-Agent-v1.2.0.apk` (sha256 8f2fa307…) handed to user for physical Pixel sideload; phone must use laptop LAN IP (e.g. http://172.20.10.11:8000), backend bound to 0.0.0.0, Windows Firewall may need port 8000 inbound rule.

## v1.1.0 production session (2026-07-12)

- Audit + hardening pass done; see `AUDIT_REPORT.md` (13 findings F1–F13) and `SESSION_LOG.md`.
- Key fixes: Live Mode duplicate-loop bug, notification-denial dead-end, Settings diagnostics (health round-trip), 3-state health dot, login password toggle + IME flow, battery fallback, first 9 unit tests, R8 Tink `-dontwarn` fix.
- Release: `dist/SentinelX-Android-Agent-v1.1.0.apk` (versionCode 2, sha256 66dc4936…). Keystore unchanged — in-place upgrade from 1.0.0 works.
- Live evidence (16 screenshots + backend JSON, emulator Pixel 6 / Android 15): `Evidence/2026-07-12-android-production/` — includes offline-queue → reconnect-flush proof.
- Emulator toolchain now installed: `emulator` + `system-images;android-35;google_apis;x86_64`, AVD `sentinelx_api35`. Set `JAVA_HOME=%LOCALAPPDATA%\Android\jdk17` for sdkmanager/avdmanager/gradle.
- Backend for emulator runs: uvicorn on 0.0.0.0:8000 + native Windows Postgres service (postgresql-x64-16, no Docker on this machine); emulator reaches host via `http://10.0.2.2:8000`.
- Open follow-ups: physical Pixel 4 XL pass, HTTPS/NSC for production, Compose UI tests, backend telemetry batch endpoint.

## Purpose

This file is the durable memory for future SentinelX Android work. Read it at the start of every Android session, then read the relevant docs in `docs/`.

## Project State

- **v1 implemented (2026-07-11)** on branch `feature/android-mobile-agent` (branched from `feature/ios-mobile-agent` because `main` was 40 commits behind).
- App source: `android/` (single-module, `com.sentinelx.mobile`); signed APK: `dist/SentinelX-Android-Agent-v1.0.0.apk`; usage: `INSTALL_GUIDE.md`.
- Final contract decision: reuse existing `/api/v1` routes only — `auth/login`, `organizations/me`, `devices/register`, `device-credentials` (mints device token in-app; requires admin/owner/platform_admin), `heartbeats`, `metrics`. No backend changes, no `/mobile/*` routes.
- Implementation deviations from the plan docs (deliberate): manual DI instead of Hilt (fewer codegen failure modes); per-sample uploads instead of telemetry batches (backend has no batch endpoint); CPU % estimated from per-core cpufreq scaling (`/proc/stat` is restricted since Android O).
- Offline queue: Room `queued_metrics`, cap 2000 rows, 50 attempts per row, flush serialized by a mutex shared between the WorkManager worker and Live Mode service. Backend stamps `recorded_at` at ingest, so late uploads carry upload time (known v1 limitation).
- Build toolchain lives in `%LOCALAPPDATA%\Android` (Temurin JDK 17, SDK platform 35 + build-tools 35.0.0, Gradle 8.11.1) — no Android Studio on this machine. Release keystore: `android/keystore/sentinelx-release.keystore` (passwords in `app/build.gradle.kts`, internal distribution only; keep the keystore stable for in-place upgrades).
- Original inputs (`deep-research-report.md`, `SentinelX_Mobile_PRD.md`) and planning docs in `docs/` remain as historical planning record.
- The folder name is currently `SentinelX_Andriod`; keep using it unless the user explicitly asks to rename it.

## Product Definition

SentinelX Android is a native Kotlin app that combines:

1. Monitoring agent:
   - Registers the phone as a SentinelX-managed device.
   - Collects battery, memory, storage, network, and device metadata.
   - Sends heartbeats and telemetry to the SentinelX backend.
   - Queues telemetry locally while offline.

2. Operations console:
   - Authenticates SentinelX users.
   - Shows dashboard health, devices, alerts, incidents, and profile/settings.
   - Honors backend RBAC roles where applicable.

## Accepted Direction

- Native Android, not React Native or Flutter.
- Kotlin first.
- Jetpack Compose + Material 3 UI.
- MVVM/Clean Architecture.
- Hilt dependency injection.
- Retrofit + OkHttp for HTTP.
- Room for structured local queue/cache.
- DataStore for preferences and lightweight settings.
- WorkManager for periodic durable sync.
- Foreground service only for explicit Live Mode.
- Internal signed APK first; Google Play later.

## v1 Scope

P0:

- Login/logout with JWT session.
- Device registration.
- Heartbeat.
- Battery telemetry.
- Memory telemetry.
- Storage telemetry.
- Network connectivity telemetry.
- Local Room queue for unsent telemetry.
- WorkManager sync worker.
- Compose dashboard.
- Devices, alerts, incidents read-only console views.
- Settings/profile basics.
- Release APK installable on Pixel 4 XL.

Defer:

- Push notifications.
- WebSocket live stream.
- Location.
- Sensor streaming.
- Running app/package inventory.
- Remote recovery commands.
- AI anomaly insights.
- Play Store release.

## Key Architecture Decisions

- Use a feature-first package/module layout, but avoid premature over-modularization.
- Recommended initial module split:
  - `:app`
  - `:core:model`
  - `:core:network`
  - `:core:database`
  - `:core:datastore`
  - `:core:ui`
  - `:feature:auth`
  - `:feature:dashboard`
  - `:feature:devices`
  - `:feature:alerts`
  - `:feature:incidents`
  - `:feature:settings`
  - `:sync`
- If this feels too heavy at scaffold time, start single-module with the same package boundaries and split modules later.
- Business logic belongs in repositories/use cases, not composables.
- UI state should be immutable.
- Sync should be idempotent with client-generated batch IDs.

## Backend Alignment Notes

Existing SentinelX backend conventions from repository guidance:

- Base API prefix is `/api/v1`.
- User auth already exists via:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/token` for Swagger OAuth2 flow
- Device/agent auth uses raw Bearer-token auth for device endpoints.
- Existing agent pipeline posts metrics to `POST /api/v1/metrics`.
- Existing roles include `platform_admin`, `owner`, `admin`, `engineer`, `operator`, and `viewer`.

Important: the PRD proposes `/mobile/*` endpoints, but the existing backend may not have them. Before Android coding, reconcile whether Android should:

- reuse existing auth/device/metrics endpoints, or
- add dedicated mobile endpoints under `/api/v1/mobile`.

## Proposed Android API Shape

Preferred v1 after backend confirmation:

- `POST /api/v1/auth/login`
- `GET /api/v1/users/me`
- `POST /api/v1/mobile/devices/register`
- `POST /api/v1/mobile/heartbeat`
- `POST /api/v1/mobile/telemetry/batch`
- `GET /api/v1/dashboard`
- `GET /api/v1/devices`
- `GET /api/v1/alerts`
- `GET /api/v1/incidents`

If backend changes must be minimal, adapt Android to current available endpoints and document any mismatches.

## Pixel 4 XL Notes

- Good development/demo target.
- Out of official security update support, so do not treat it as a high-trust production device.
- Keep tokens scoped and avoid storing high-value secrets.
- Validate on real hardware before calling v1 complete.

## Implementation Start Checklist

1. Read `docs/01-project-brief.md`.
2. Read `docs/03-api-data-contract.md`.
3. Inspect backend route files before finalizing endpoint names.
4. Create Android project only after API contract is accepted.
5. Build the first vertical slice:
   - login
   - register device
   - collect one telemetry sample
   - queue in Room
   - upload to backend
   - display latest state in dashboard
6. Add WorkManager after the upload path works.
7. Add foreground service Live Mode after dashboard and sync are stable.

## Quality Bar

- No hardcoded secrets.
- HTTPS only.
- No sensitive logging.
- Offline queue must not grow forever.
- UI must clearly show last sync, queue depth, and backend error state.
- Tests should cover collectors, mappers, repositories, Room queue transitions, worker behavior, and key ViewModels.

