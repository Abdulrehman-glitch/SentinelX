# SentinelX Android

SentinelX Android is a native Kotlin application that extends SentinelX into a mobile edge agent.

**Status: v1 implemented.** The app source lives in `android/`, the signed installable APK in `dist/`, and the install/run walkthrough in `INSTALL_GUIDE.md`. The agent registers the phone against the existing FastAPI backend, mints its own device token in-app, and streams metrics + heartbeats — zero backend changes were required.

## Source Inputs

- `deep-research-report.md` - platform research and recommended Android implementation strategy.
- `SentinelX_Mobile_PRD.md` - draft product requirements for SentinelX Mobile.

## Documentation Index

- `docs/00-source-analysis.md` - synthesis of the research report and PRD, including conflicts and implementation implications.
- `docs/01-project-brief.md` - refined product brief and v1 definition.
- `docs/02-architecture.md` - Android architecture, modules, background execution, and local persistence.
- `docs/03-api-data-contract.md` - proposed SentinelX mobile API contract and telemetry schema.
- `docs/04-roadmap.md` - detailed phased roadmap with deliverables and definitions of done.
- `docs/05-security-privacy.md` - permissions, auth, storage, transport, and threat model.
- `docs/06-testing-release.md` - testing strategy, release signing, and Pixel 4 XL validation.
- `PROJECT_MEMORY.md` - durable working memory for future Android sessions.

## Implemented v1 (2026-07-11)

- `android/` — single-module Kotlin app `com.sentinelx.mobile` (Compose + Material 3, MVVM, manual DI, Retrofit + kotlinx.serialization, Room queue, DataStore, WorkManager, foreground-service Live Mode).
- Endpoint mapping (final): reuses existing `/api/v1` routes — `auth/login`, `organizations/me`, `devices/register`, `device-credentials`, `heartbeats`, `metrics`. No `/mobile/*` routes were added.
- Auth model: user JWT for login/enrollment; Keystore-encrypted device token for telemetry (same mechanics as the desktop agent).
- Deviations from the original plan, chosen to reduce build risk and match the real backend: manual DI instead of Hilt; per-sample `POST /metrics` upload instead of a batch endpoint (backend has no batch route); CPU % is a frequency-scaling estimate.

## Original Decision Summary

- Build as a native Android app in Kotlin.
- Use Jetpack Compose, Material 3, MVVM/Clean Architecture, Hilt, Retrofit, Room, DataStore, and WorkManager.
- Treat the app as two products in one:
  - Mobile Monitoring Agent: registers the Android device, collects device telemetry, queues offline data, and syncs to SentinelX.
  - Mobile Operations Console: lets authenticated SentinelX users view dashboards, devices, alerts, incidents, and account state.
- Start with internal signed APK distribution, primarily installed through ADB on the Pixel 4 XL.
- Use a hybrid background model:
  - WorkManager for durable periodic sync and retries.
  - Foreground service only for explicit user-enabled Live Mode.
- Avoid privacy-heavy features in v1, including running-app inventory, location, broad package visibility, and continuous raw sensor streaming.

## Before Implementation

1. Confirm backend endpoint paths and payloads against the existing FastAPI backend.
2. Decide whether mobile auth reuses existing `/api/v1/auth/login` and device auth reuses current device-token mechanics, or whether dedicated `/mobile/*` endpoints will be added.
3. Freeze the v1 telemetry schema.
4. Scaffold the Android Studio project only after those contracts are clear.
