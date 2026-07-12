# SentinelX Android Agent — Install & Run Guide

The signed, installable APK lives at `dist/SentinelX-Android-Agent-v1.0.0.apk`.

## What the app does

- Registers your Android phone as a managed SentinelX device (`/api/v1/devices/register`)
- Mints its own device token in-app (`/api/v1/device-credentials`) — no manual token copying
- Sends live telemetry to the main SentinelX backend: memory %, storage %, CPU estimate via `/api/v1/metrics`, plus heartbeats with battery/network context via `/api/v1/heartbeats`
- Queues samples in a local Room database while offline and uploads them when connectivity returns
- Reliable background sync every 15 minutes (WorkManager) + optional Live Mode foreground service (15/30/60 s interval, visible notification)
- The device, its metrics, alerts, and incidents all appear in the existing React dashboard — no backend changes were needed

## 1. Install the APK on your phone

1. Copy `dist/SentinelX-Android-Agent-v1.0.0.apk` to the phone (USB cable, Quick Share, or any file transfer).
2. On the phone, open the APK from the Files app.
3. Allow "Install unknown apps" for the Files app when prompted (the APK is internally signed, not Play-signed).
4. Install. Minimum Android version: 8.0 (API 26).

Alternative via ADB: `adb install dist/SentinelX-Android-Agent-v1.0.0.apk`

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

## 4. Live Mode (optional)

Toggle **Live Mode** on the dashboard to stream telemetry every 15–60 s behind a persistent notification (Android 13+ asks for notification permission first). Reliable 15-minute WorkManager sync runs regardless.

## Behaviour notes

- **Offline**: samples queue locally (cap 2000 rows, 50 upload attempts each) and flush when the network returns. The backend stamps `recorded_at` at ingest time, so late-uploaded samples carry upload time — a known v1 limitation, consistent with the desktop agent.
- **Sign out vs Unlink**: signing out ends the console session but the agent keeps syncing on its device token. "Unlink device" in Settings deletes the local token and queue.
- **Re-seeding the backend DB** wipes devices/credentials: the app will start getting `401` ("Device token rejected") — just Unlink and re-enroll.
- **CPU %** is an estimate from per-core frequency scaling (Android does not expose device-wide CPU load to apps since Android 8); memory/storage/battery/network are exact.
- Cleartext HTTP is enabled for LAN development use; use HTTPS for anything beyond that.

## Rebuilding from source

```powershell
$env:JAVA_HOME = "$env:LOCALAPPDATA\Android\jdk17"
cd C:\SentinelX\SentinelX_Andriod\android
& "$env:LOCALAPPDATA\Android\gradle-8.11.1\bin\gradle.bat" assembleRelease
# APK: app\build\outputs\apk\release\app-release.apk
```

Toolchain (installed under `%LOCALAPPDATA%\Android`): Temurin JDK 17, Android SDK (platform 35, build-tools 35.0.0), Gradle 8.11.1. `android/local.properties` points at the SDK. The release keystore is `android/keystore/sentinelx-release.keystore` (internal-distribution only; passwords in `app/build.gradle.kts`). Keep the same keystore to allow in-place upgrades on the phone.
