# SentinelX Android Agent — Install, Run & Live Telemetry Guide

The signed, installable APK lives at `dist/SentinelX-Android-Agent-v2.1.0.apk` (versionCode 7). This build includes the 2026-07-18 Trusted Agent Foundation changes (enrolment codes, HTTPS-only release traffic, split sync workers) on top of the 2026-07-13 brand release — see `CHANGELOG.md`. Older builds are kept alongside it; the keystore is unchanged, so it installs in-place over any earlier v2.x install.

## What the app does

- Enrols your Android phone as a managed SentinelX device via a single-use enrolment code (preferred, no admin login on the phone) or admin-JWT self-enrolment (fallback) — see step 3.
- Mints its own device token in-app, stored in Keystore-backed encrypted storage — no manual token copying
- Sends live telemetry to the main SentinelX backend: memory %, storage %, CPU estimate, plus battery/network/latency context via `POST /api/v1/metrics/batch`, and heartbeats via `/api/v1/heartbeats`
- Queues samples in a local Room database while offline; each sample keeps its capture timestamp, so late uploads land as real history
- Reliable background sync every 15 minutes (WorkManager, split into a collect worker and a sync worker) + optional Live Monitor foreground service (Balanced 60 s / Active 30 s / Diagnostic 10 s, visible notification)
- Seven sections in-app: Home (health orb + sparklines), Live, Health, Alerts, Diagnostics, Activity, Settings
- The device, its metrics, alerts, and incidents all appear in the existing React dashboard, with mobile telemetry cards on the device detail page

## ⚠️ Important: release builds are HTTPS-only

As of the 2026-07-18 rebuild, the signed release APK enforces `cleartextTrafficPermitted="false"` — **it can no longer reach a plain-HTTP backend**, including a local dev backend on your LAN. This closes the "cleartext Android traffic" finding from the technical audit. You have two options:

- **Point at the deployed backend** (`https://sentinelx-api.azurewebsites.net`, already HTTPS) — works out of the box with the release APK in `dist/`. Follow steps 1–3 below as written.
- **Local/LAN dev testing** (the workflow this guide previously described end-to-end) — install a **debug** build instead; only debug builds permit cleartext HTTP. See "Local/LAN testing (debug build)" below.

Debug and release share the same application ID (no suffix is configured) but different signing certificates, so Android will refuse to install one over the other — you'll need to uninstall whichever is currently installed before switching between them.

## 1. Install the release APK on your phone

1. Copy `dist/SentinelX-Android-Agent-v2.1.0.apk` to the phone (USB cable, Quick Share, or any file transfer).
2. On the phone, open the APK from the Files app.
3. Allow "Install unknown apps" for the Files app when prompted (the APK is internally signed, not Play-signed).
4. Install. Minimum Android version: 8.0 (API 26). Upgrading from v1.x keeps queued samples (Room v2 migration).

Alternative via ADB: `adb install dist/SentinelX-Android-Agent-v2.1.0.apk`

## 2. Point it at an HTTPS backend

If the deployed Azure backend is up, use `https://sentinelx-api.azurewebsites.net` as the server URL in step 3 and skip straight to enrolling — no local server setup needed.

To run against your own backend over HTTPS instead, you'd need a TLS-terminating reverse proxy in front of `uvicorn` (out of scope here) — for local development, use the debug-build path below instead.

## 3. Enrol the device

**Preferred: enrolment code (no login needed on the phone).** An org admin mints a single-use code from a machine that can already reach the backend (Swagger UI is the only interface for this today — there's no dashboard button yet):

1. Open `<backend-url>/docs`, click **Authorize**, sign in as an admin/owner account (e.g. `ops@technova.io` / `SentinelX2026!` — see `docs/DEMO_USERS.md`).
2. Call `POST /api/v1/devices/enrollment-codes` with a `name` and `expires_in_minutes` (default 15). Copy the `code` field from the response — it's shown once.
3. On the phone, open **SentinelX Agent** → Home → paste the code into the **enrolment code** field → tap **Enrol**.

The app registers itself, creates its device token, stores it securely, and immediately syncs. The phone appears in the web dashboard as `android-<model>-<id>` (agent type `android_mobile_agent`).

**Fallback: admin-JWT self-enrolment.** On the phone's Home screen, sign in directly with an admin/owner account instead of pasting a code, then tap the secondary **Enrol** button. This calls the same role-gated `/devices/register` + `/device-credentials` flow the app has always used — no code needed, but it does require typing admin credentials on the phone.

## Local/LAN testing (debug build)

For the local-backend LAN workflow this guide previously described (phone + `uvicorn --host 0.0.0.0` on the same Wi-Fi), install a **debug** build instead of the release APK — only debug builds permit cleartext HTTP (`app/src/debug/res/xml/network_security_config.xml`):

```powershell
cd C:\SentinelX\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Find your PC's LAN IP with `ipconfig` (e.g. `192.168.1.50`) and make sure Windows Firewall allows inbound TCP 8000. Then, with the phone connected via USB:

```powershell
$env:JAVA_HOME = "$env:LOCALAPPDATA\Android\jdk17"
cd C:\SentinelX\agents\android-native\android
& "$env:LOCALAPPDATA\Android\gradle-8.11.1\bin\gradle.bat" installDebug
```

(If the release APK is already installed, uninstall it first — same application ID, different signing cert, per the note above.) In the app, use server URL `http://<your-pc-lan-ip>:8000` and enrol as in step 3 above (either flow works against a debug build too).

## 4. Live Monitor (optional)

Open the **Live** section and start monitoring in one of three modes — Balanced (60 s), Active (30 s), or Diagnostic (10 s, auto-stops after 10 min) — behind a persistent notification (Android 13+ asks for notification permission first). Reliable 15-minute WorkManager sync runs regardless. The "Live telemetry end-to-end" section below covers the web dashboard side.

## Behaviour notes

- **Offline**: samples queue locally (cap 2000 rows, 50 upload attempts each) and flush when the network returns. Since v2.0.0, uploads go through `/metrics/batch` with per-sample capture timestamps, so queued samples appear at their real recording time in dashboard history.
- **Sign out vs Unlink**: signing out ends the console session but the agent keeps syncing on its device token. "Unlink device" in Settings deletes the local token and queue.
- **Re-seeding the backend DB** wipes devices/credentials: the app will start getting `401` ("Device token rejected") — just Unlink and re-enroll.
- **CPU %** is an estimate from per-core frequency scaling (Android does not expose device-wide CPU load to apps since Android 8); memory/storage/battery/network are exact.
- Cleartext HTTP is only permitted in **debug** builds (local/LAN dev). The release APK in `dist/` enforces HTTPS for every destination — see "⚠️ Important" above.

## Live telemetry end-to-end

The full pipeline, with all devices in an organization streaming to the same dashboard at once (this section assumes the local/LAN debug-build setup — swap in the Azure URL if you're using the release APK against the deployed backend):

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

Open `http://localhost:5173` and sign in (accounts in `docs/DEMO_USERS.md`). The Fleet Monitor panel re-polls every 15 s, overview/health every 20 s, and the device detail page every 10–15 s — no manual refresh needed.

### Adding more fleet devices

Each device streams independently and they all appear together in the Fleet Monitor.

Laptop agent (needs `SENTINELX_DEVICE_TOKEN` in `agents\desktop-python\.env` — printed by the seed script; see `agents/desktop-python/README.md`):

```powershell
cd C:\SentinelX\agents\desktop-python
.\.venv\Scripts\Activate.ps1
python -m sentinelx_agent
```

Arduino bridge: see `embedded/README.md` (`agents/embedded-bridge/.env` holds its seeded token).

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
| Nova Mobile org missing | Created via API, not seed — re-seeding wipes it (recreate via `POST /organizations`, see `docs/DEMO_USERS.md`) |

## Rebuilding from source

Release builds need signing credentials that are **not** committed to source control. Copy `keystore.properties.example` to `keystore.properties` (gitignored) in `android/` and fill in the real values, or set `KEYSTORE_STORE_PASSWORD` / `KEYSTORE_KEY_ALIAS` / `KEYSTORE_KEY_PASSWORD` / `KEYSTORE_FILE` environment variables (used by CI). Without either, `assembleRelease` still succeeds but produces an **unsigned** APK that won't install.

```powershell
$env:JAVA_HOME = "$env:LOCALAPPDATA\Android\jdk17"
cd C:\SentinelX\agents\android-native\android
& "$env:LOCALAPPDATA\Android\gradle-8.11.1\bin\gradle.bat" assembleRelease
# APK: app\build\outputs\apk\release\app-release.apk
# verify signing: & "$env:LOCALAPPDATA\Android\Sdk\build-tools\35.0.0\apksigner.bat" verify --verbose app\build\outputs\apk\release\app-release.apk
```

Toolchain (installed under `%LOCALAPPDATA%\Android`): Temurin JDK 17, Android SDK (platform 35, build-tools 35.0.0), Gradle 8.11.1. `android/local.properties` points at the SDK. The release keystore file is `android/keystore/sentinelx-release.keystore` (internal-distribution only, unchanged since v1.0). Keep the same keystore to allow in-place upgrades on the phone.
