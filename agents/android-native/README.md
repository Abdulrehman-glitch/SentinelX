# SentinelX Android

SentinelX Android is a native Kotlin application that extends SentinelX into a mobile edge agent.

**Status: v4.0.0** — QR pairing onboarding, target SDK 36 (Android 16), foreground-service timeout compliance, and a dedicated **local** build type for self-hosted LAN backends. The app source lives in `android/`, the signed installable APKs in `dist/` (latest: `SentinelX-Android-Agent-v4.0.0.apk`), the install + live-telemetry walkthrough in `INSTALL_GUIDE.md`, and the release history in `CHANGELOG.md`.

**Onboarding is now pairing-first**: the first-run screen is "Connect to SentinelX" → scan the QR shown by the console (**Devices → Add Device → Android**) → the app verifies the server, redeems the one-time code for its own device credential (Keystore-encrypted), delivers first telemetry and schedules background monitoring — with each step shown as it completes. A fallback pairing-code field covers devices without a camera or Play services; console sign-in survives only as an "Advanced" path. Build types: `release` stays HTTPS-only for the internet; `local` (version suffix `-local`) permits cleartext **only to private-network addresses** (RFC1918/loopback/`.local`, enforced in both the network security config and `HostSelectionInterceptor`) for self-hosted LAN backends; `debug` is for development.

## Documentation Index

- `INSTALL_GUIDE.md` - install, enroll, live telemetry end-to-end (multi-device + multi-org), rebuild from source.
- `CHANGELOG.md` - per-release history from v1.0.0 to current.
- `docs/00-source-analysis.md` - synthesis of the original platform research and PRD (raw source documents since removed).
- `docs/01-project-brief.md` - refined product brief and v1 definition.
- `docs/02-architecture.md` - Android architecture, modules, background execution, and local persistence.
- `docs/03-api-data-contract.md` - proposed SentinelX mobile API contract and telemetry schema.
- `docs/04-roadmap.md` - detailed phased roadmap with deliverables and definitions of done.
- `docs/05-security-privacy.md` - permissions, auth, storage, transport, and threat model.
- `docs/06-testing-release.md` - testing strategy, release signing, and Pixel 4 XL validation.
- `Evidence/` - dated evidence packs per session (gitignored; commit with `git add -f`).

## What's implemented

- `android/` — single-module Kotlin app `com.sentinelx.mobile` (Compose + Material 3, MVVM, manual DI, Retrofit + kotlinx.serialization, Room queue, DataStore, WorkManager, foreground-service Live Monitor).
- Five-section shell (Home, Live, Health, Alerts, Settings; Diagnostics and Activity under Settings → Tools), animated health orb with an explainable score engine, 12-check diagnostics centre, local activity timeline.
- Auth model: user JWT for login/enrollment; Keystore-encrypted device token for telemetry (same mechanics as the desktop agent).
- Sync: `POST /api/v1/metrics/batch` with per-sample capture timestamps (offline queues land as real history), plus heartbeats; exponential backoff + connectivity-callback wakeups while offline.
- CPU % is a frequency-scaling estimate (Android exposes no device-wide CPU load to apps); memory/storage/battery/network are exact.
- **Safe Recovery Orchestration (Sprint 3)**: executes 8 typed, individually allowlisted, Ed25519-signed recovery actions dispatched by the backend (`collect_diagnostics`, `restart_monitoring_service`, `reschedule_sync_workers`, `retry_telemetry_sync`, `reset_api_connection`, `repair_local_database`, `enter_safe_monitoring_mode`, `restore_normal_monitoring_mode`) — every command is verified locally (signature, expiry, nonce replay) before execution. Never touches other apps, root, device-wide settings, or reboot. See `command/{CommandSigningVerifier,CommandExecutor,CommandRepository,CommandPollWorker}.kt`.

## Architecture decisions (original, still standing)

- Native Kotlin, internal signed-APK distribution (no Play workflow).
- Hybrid background model: WorkManager for durable 15-minute sync; foreground service only for explicit user-enabled Live Monitor.
- No privacy-heavy features: no running-app inventory, location, package visibility, or continuous raw sensor streaming.
- Deviation from the original plan: manual DI instead of Hilt, chosen to reduce build risk.
