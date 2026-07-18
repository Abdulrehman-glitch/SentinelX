# SentinelX Android

SentinelX Android is a native Kotlin application that extends SentinelX into a mobile edge agent.

**Status: v2.1.0 shipped**, rebuilt 2026-07-18 with the Trusted Agent Foundation changes (Sentinel Glass UI + the new brand identity, plus enrolment codes, HTTPS-only release traffic, split sync workers). The app source lives in `android/`, the signed installable APKs in `dist/` (latest: `SentinelX-Android-Agent-v2.1.0.apk`), the install + live-telemetry walkthrough in `INSTALL_GUIDE.md`, and the release history in `CHANGELOG.md`. The agent enrols the phone against the existing FastAPI backend (single-use code preferred, admin-JWT fallback), mints its own device token in-app, and streams batched metrics + heartbeats. **Release builds now require an HTTPS backend** — see `INSTALL_GUIDE.md` for the local/LAN debug-build path.

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

## Architecture decisions (original, still standing)

- Native Kotlin, internal signed-APK distribution (no Play workflow).
- Hybrid background model: WorkManager for durable 15-minute sync; foreground service only for explicit user-enabled Live Monitor.
- No privacy-heavy features: no running-app inventory, location, package visibility, or continuous raw sensor streaming.
- Deviation from the original plan: manual DI instead of Hilt, chosen to reduce build risk.
