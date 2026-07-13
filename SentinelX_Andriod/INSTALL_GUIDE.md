# SentinelX Android Agent — Install, Run & Live Telemetry Guide

The signed, installable APK lives at `dist/SentinelX-Android-Agent-v2.0.1.apk` (versionCode 6, "Sentinel Glass"). Older builds are kept alongside it; the keystore is unchanged, so it installs in-place over any earlier version.

## What the app does

- Registers your Android phone as a managed SentinelX device (`/api/v1/devices/register`)
- Mints its own device token in-app (`/api/v1/device-credentials`) — no manual token copying
- Sends live telemetry to the main SentinelX backend: memory %, storage %, CPU estimate, plus battery/network/latency context via `POST /api/v1/metrics/batch`, and heartbeats via `/api/v1/heartbeats`
- Queues samples in a local Room database while offline; each sample keeps its capture timestamp, so late uploads land as real history
- Reliable background sync every 15 minutes (WorkManager) + optional Live Monitor foreground service (Balanced 60 s / Active 30 s / Diagnostic 10 s, visible notification)
- Seven sections in-app: Home (health orb + sparklines), Live, Health, Alerts, Diagnostics, Activity, Settings
- The device, its metrics, alerts, and incidents all appear in the existing React dashboard, with mobile telemetry cards on the device detail page

## 1. Install the APK on your phone

1. Copy `dist/SentinelX-Android-Agent-v2.0.1.apk` to the phone (USB cable, Quick Share, or any file transfer).
2. On the phone, open the APK from the Files app.
3. Allow "Install unknown apps" for the Files app when prompted (the APK is internally signed, not Play-signed).
4. Install. Minimum Android version: 8.0 (API 26). Upgrading from v1.x keeps queued samples (Room v2 migration).

Alternative via ADB: `adb install dist/SentinelX-Android-Agent-v2.0.1.apk`

## 2. Start the backend on your LAN

The phone must reach the FastAPI backend over Wi-Fi:

```powershell
cd C:\SentinelX\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Find your PC's LAN IP with `ipconfig` (e.g. `192.168.1.50`) and make sure Windows Firewall allows inbound TCP 8000 (the iOS phase's `scripts/start_device_pass.ps1` already does this setup, if present on your branch).

## 3. Sign in and enroll

1. Open **SentinelX Agent** on the phone.
2. Server URL: `http://<your-pc-lan-ip>:8000`
3. Sign in with an **admin or owner** account — enrollment mints a device credential, which is role-gated. E.g. `ops@technova.io` / `SentinelX2026!` (see `DEMO_USERS.md`).
4. Tap **Enroll device**. The app registers the phone, creates its device token, stores it in Keystore-backed encrypted storage, and immediately syncs.

The phone now appears in the web dashboard as `android-<model>-<id>` (agent type `android_mobile_agent`).

## 4. Live Monitor (optional)

Open the **Live** section and start monitoring in one of three modes — Balanced (60 s), Active (30 s), or Diagnostic (10 s, auto-stops after 10 min) — behind a persistent notification (Android 13+ asks for notification permission first). Reliable 15-minute WorkManager sync runs regardless. The "Live telemetry end-to-end" section below covers the web dashboard side.

## Behaviour notes

- **Offline**: samples queue locally (cap 2000 rows, 50 upload attempts each) and flush when the network returns. Since v2.0.0, uploads go through `/metrics/batch` with per-sample capture timestamps, so queued samples appear at their real recording time in dashboard history.
- **Sign out vs Unlink**: signing out ends the console session but the agent keeps syncing on its device token. "Unlink device" in Settings deletes the local token and queue.
- **Re-seeding the backend DB** wipes devices/credentials: the app will start getting `401` ("Device token rejected") — just Unlink and re-enroll.
- **CPU %** is an estimate from per-core frequency scaling (Android does not expose device-wide CPU load to apps since Android 8); memory/storage/battery/network are exact.
- Cleartext HTTP is enabled for LAN development use; use HTTPS for anything beyond that.

## Live telemetry end-to-end

The full pipeline, with all devices in an organization streaming to the same dashboard at once:

```
Android app (Live Monitor 10/30/60 s) ──┐
Laptop agent (python_desktop_agent)  ───┼──► FastAPI backend :8000 ──► PostgreSQL
Arduino bridge (embedded)            ───┘             │
                                                      ▼
                                    React dashboard :5173 (auto-refresh 15–20 s)
```

With the backend running (step 2 above), start the web dashboard:

```powershell
cd C:\SentinelX\frontend
npm run dev
```

Open `http://localhost:5173` and sign in (accounts in `DEMO_USERS.md`). The Fleet Monitor panel re-polls every 15 s, overview/health every 20 s, and the device detail page every 10–15 s — no manual refresh needed.

### Adding more fleet devices

Each device streams independently and they all appear together in the Fleet Monitor.

Laptop agent (needs `SENTINELX_DEVICE_TOKEN` in `agent\.env` — printed by the seed script; see `agent/README.md`):

```powershell
cd C:\SentinelX\agent
.\.venv\Scripts\Activate.ps1
python -m sentinelx_agent
```

Arduino bridge: see `embedded/README.md` (`agents/embedded_bridge/.env` holds its seeded token).

### Watching more than one fleet (organization) at once

A fleet is an organization — each login is scoped to one org (the multi-tenant isolation boundary). To watch two fleets side by side, open a second browser window (incognito/other profile so sessions don't collide) with the other org's account, e.g. `ops@technova.io` and `ops@novamobile.io`. Both dashboards poll independently.

### Verifying it's actually live

1. Start Diagnostic mode (10 s) on the phone.
2. Open the phone's device detail page on the dashboard — `recorded_at` should advance roughly every 10 s.
3. Toggle airplane mode for a minute, then back: queued samples flush and appear in history at their real capture times.

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Phone can't reach server | Wrong LAN IP, different Wi-Fi network, or firewall — run the in-app **Diagnostics** (12 checks incl. backend + upload) |
| `401 Device token rejected` | Backend DB was re-seeded — Settings → Unlink device, then re-enroll |
| Device shows offline on dashboard | No samples in the staleness window — start Live Monitor or wait for the 15-min WorkManager sync |
| Dashboard feels static | It auto-refreshes every 15–20 s; check the backend is up |
| Nova Mobile org missing | Created via API, not seed — re-seeding wipes it (recreate via `POST /organizations`, see `DEMO_USERS.md`) |

## Rebuilding from source

```powershell
$env:JAVA_HOME = "$env:LOCALAPPDATA\Android\jdk17"
cd C:\SentinelX\SentinelX_Andriod\android
& "$env:LOCALAPPDATA\Android\gradle-8.11.1\bin\gradle.bat" assembleRelease
# APK: app\build\outputs\apk\release\app-release.apk
```

Toolchain (installed under `%LOCALAPPDATA%\Android`): Temurin JDK 17, Android SDK (platform 35, build-tools 35.0.0), Gradle 8.11.1. `android/local.properties` points at the SDK. The release keystore is `android/keystore/sentinelx-release.keystore` (internal-distribution only; passwords in `app/build.gradle.kts`). Keep the same keystore to allow in-place upgrades on the phone.
