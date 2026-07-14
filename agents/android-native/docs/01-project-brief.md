# SentinelX Android Project Brief

## Executive Summary

SentinelX Android should be treated as a new native Android project that extends the existing SentinelX platform to mobile. The strongest product shape is a hybrid app:

- A mobile monitoring agent that registers the Android device, collects low-risk telemetry, queues data offline, and syncs reliably.
- A mobile operations console that lets authenticated SentinelX users view infrastructure status, devices, alerts, incidents, and account settings.

The deep-research report and PRD agree on the core stack: Kotlin, Jetpack Compose, MVVM/Clean Architecture, Hilt, Retrofit, Room, DataStore, and WorkManager. They also agree that the first release should be an internally distributed signed APK before any Google Play workflow.

## Product Goal

Turn a Pixel 4 XL into a SentinelX-managed Android node and mobile console that can:

- Authenticate a SentinelX user.
- Register the Android device with SentinelX.
- Collect battery, RAM, storage, network, and device metadata.
- Send heartbeat and telemetry to the backend.
- Cache and retry telemetry when offline.
- Show dashboard, device, alert, and incident information in a professional Compose UI.

## Primary Users

| User | Needs |
|---|---|
| Admin | Full console access, device visibility, alert and incident review, future settings management. |
| Engineer | Investigate devices, alerts, telemetry, and incidents from mobile. |
| Viewer | Read-only mobile access to dashboard and operational state. |
| Developer/operator | Install, test, and demo the Android agent on a Pixel 4 XL. |

## v1 Product Principles

1. Start with low-permission telemetry.
2. Make sync reliable before making it richer.
3. Keep Live Mode explicit and visible.
4. Reuse existing SentinelX backend conventions where practical.
5. Build for internal APK delivery first.
6. Keep privacy-heavy features out of v1.

## MVP Scope

### In Scope

- Native Kotlin Android project.
- Compose + Material 3 UI.
- Login/logout and JWT session handling.
- Secure token/session persistence.
- Device registration.
- Heartbeat.
- Battery, memory, storage, network, and device metadata telemetry.
- Room-backed local telemetry queue.
- WorkManager periodic sync and retry.
- Optional foreground service Live Mode with persistent notification.
- Dashboard, devices, alerts, incidents, profile, and settings screens.
- Signed release APK.
- Pixel 4 XL real-device validation.

### Out of Scope for v1

- Push notifications.
- WebSocket live telemetry.
- Location telemetry.
- Raw sensor streams.
- Running app inventory or broad package visibility.
- Remote recovery actions.
- AI anomaly insights.
- Play Store public release.

## Success Criteria

- APK installs cleanly on Pixel 4 XL.
- User can authenticate against SentinelX.
- Device registers idempotently.
- Telemetry reaches backend and is visible in backend/dashboard flows.
- Offline telemetry is queued locally and uploaded after connectivity returns.
- Dashboard loads in under 2 seconds on typical local/staging conditions.
- Live Mode clearly shows a foreground notification when active.
- No hardcoded secrets or sensitive release logs.

## Main Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Backend contract mismatch | Android implementation stalls or duplicates existing APIs | Align endpoint paths and schemas before scaffolding. |
| Android background limits | Unreliable "always-on" behavior | Use WorkManager for durable sync and foreground service only for explicit Live Mode. |
| Permission overreach | Privacy concerns and Play readiness issues | Keep v1 telemetry permission-light. |
| Pixel 4 XL age | Security risk for sensitive deployments | Use staging/internal credentials and short-scoped tokens. |
| Scope creep | Project becomes too broad before a working vertical slice | Ship register -> collect -> queue -> upload -> display first. |

