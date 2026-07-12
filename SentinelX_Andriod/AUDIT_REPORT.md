# SentinelX Android Agent — Production Audit & Debug Report

Date: 2026-07-12 · Version audited: 1.0.0 → shipped 1.1.0 (versionCode 2)
Evidence: `Evidence/2026-07-12-android-production/` (screenshots captured live on AVD `sentinelx_api35`, Pixel 6 / Android 15 / API 35, release APK, real backend)

## Scope

Full audit of `android/` against `SentinelX_Android_Agent_Complete_Checklist.md`, followed by fixes, a rebuilt signed release APK, and a live end-to-end pass on an emulator against the real FastAPI backend (native Postgres).

## Findings and resolutions

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| F1 | HIGH | `LiveMonitorService.onStartCommand` launched a new sampling coroutine on every start command without cancelling the previous one — toggle spam or a sticky restart stacked duplicate loops and double-uploaded | Fixed: `monitorJob` tracked and cancelled before relaunch (`LiveMonitorService.kt`) |
| F2 | MED | Denying POST_NOTIFICATIONS on Android 13+ silently dead-ended Live Mode | Fixed: Live Mode now starts regardless (FGS is legal without the permission; notification is suppressed) (`MainActivity.kt`) |
| F3 | MED | No diagnostics — checklist requires a backend test | Fixed: Settings → Diagnostics → "Test server connection" round-trips `/api/v1/health`, reports API/DB status + latency + version (evidence 15: "API online, database online · 729 ms · v2.0.0") |
| F4 | LOW | Health dot showed green before the first sync ever succeeded | Fixed: 3-state dot — amber never-synced / green ok / red error |
| F5 | LOW | Manual sync result message lingered forever | Fixed: auto-clears after 8 s (visible working in evidence 07→08) |
| F6 | LOW | Login lacked password visibility toggle and IME Next/Done flow | Fixed: eye toggle + keyboard navigation (evidence 02, 03) |
| F7 | MED | Live Mode switch not associated with its label for screen readers | Fixed: whole row is `toggleable` with `Role.Switch` |
| F8 | MED | `usesCleartextTraffic="true"` global | KEPT deliberately: the agent must reach a LAN backend over HTTP for the coursework device pass. Documented as a known limitation; production would pin HTTPS + network security config |
| F9 | MED | Zero unit tests | Fixed: 9 JUnit tests (URL normalization, memory/storage math, battery summary) — 9/9 pass |
| F10 | LOW | Unknown battery level rendered as 0% | Fixed: falls back to `BatteryManager.BATTERY_PROPERTY_CAPACITY` |
| F11 | INFO | No boot receiver | Intentional: WorkManager self-reschedules after boot; Android 15 forbids starting a dataSync FGS from BOOT_COMPLETED, so Live Mode does not auto-resume — documented |
| F12 | INFO | CPU metric sends 0.0 when the cpufreq estimate is unavailable | Documented: backend metric schema requires the field |
| F13 | MED (build) | Release build failed at R8: Tink (via security-crypto) references compile-only errorprone annotations | Fixed: `-dontwarn` rules in `proguard-rules.pro` |

## Live pass results (all on release APK v1.1.0)

| Check | Result | Evidence |
|---|---|---|
| Install signed release APK on clean device | PASS | 02 |
| Login against live backend (`ops@technova.io`) | PASS | 03, 04 |
| Live telemetry cards (battery/memory/storage/CPU/network) | PASS | 04 |
| Device enrollment (register + credential mint) | PASS | 05 |
| Device visible on backend, `agent_type=android_mobile_agent`, v1.1.0, online | PASS | 06-backend-device-record.json |
| Manual sync uploads a sample | PASS | 07 |
| Notification permission flow (Android 13+) | PASS | 08 |
| Live Mode foreground service + persistent notification + Stop action | PASS | 09, 10 |
| Offline: red dot, clear error, samples queue locally, app keeps working | PASS | 11 (2 queued, "Failed to connect") |
| Recovery: queue flushes on reconnect, no loss (rows 1 s apart on backend) | PASS | 12, 13-backend-metric-rows.txt (10 rows) |
| Settings: account/device info, interval chips, danger zone | PASS | 14 |
| Diagnostics connection test | PASS | 15 |
| Dark theme | PASS | 16 |
| Live Mode survives app relaunch + theme change | PASS | 16 (toggle still on) |
| Unit tests | 9/9 PASS | Gradle test report |
| APK signature verified (apksigner) | PASS | CN=SentinelX Android Agent |

Release artifact: `dist/SentinelX-Android-Agent-v1.1.0.apk`
SHA-256: `66dc4936f3e314ecbdbda45f8ed5c7a6e4f3e2199efe491d9e4e0d09b16f8a0e`

## Round 2 — error states, lifecycle, RBAC (2026-07-12, evidence 17–29)

| Check | Result | Evidence |
|---|---|---|
| Live interval change (15s chip) persists and relabels dashboard | PASS | 17, 19 |
| Sign-out confirm dialog + enrolled agent keeps syncing after sign-out | PASS | 18, 19 |
| Backend credential revocation → 401 surfaced as actionable error; samples queue, not lost | PASS | 20, 21 |
| Unlink device: confirm dialog, local token+queue cleared, back to login with server URL kept | PASS | 22, 23 |
| Wrong password → "Invalid email or password.", no stack trace | PASS | 24 |
| Viewer role blocked from enrollment with explanation (RBAC) | PASS | 25 |
| Re-enrollment after revocation mints fresh credential, green sync | PASS | 26 |
| Force-stop + relaunch: state intact, Live Mode correctly off | PASS | 27 |
| Landscape rotation | PASS | 28 |
| 1.3× font scale | PASS | 29 |

Round-2 finding: **F14 (MED, UX)** — hardware back from Settings exited the app (no BackHandler). Fixed in v1.2.0; verified in evidence 34.

## v1.2.0 — glass UI redesign (evidence 30–34)

Apple-style glass design (gradient backdrop + frosted translucent panels) across login, dashboard, settings, light and dark. Upgrade install v1.1.0→v1.2.0 preserved enrollment and sync history (evidence 30) — checklist "upgrade preserves enrollment/queued data" PASS.

Release artifact: `dist/SentinelX-Android-Agent-v1.2.0.apk`
SHA-256: `8f2fa30735d01f92ba95adbe34dd279842217787bd68cb6595cf1966ad106f02`

## Known limitations (accepted for v1.1)

- Cleartext HTTP allowed (LAN demo requirement). Production: HTTPS only + network security config.
- Late uploads carry ingest time, not capture time (backend stamps `recorded_at`; no batch endpoint).
- Live Mode does not auto-resume after reboot (Android 15 FGS-from-boot restriction); the 15-minute WorkManager sync does.
- CPU % is a frequency-scaling estimate, marked "(estimate)" in the UI.
- Keystore passwords live in `build.gradle.kts` — internal distribution only, not a production trust anchor.
- Emulator pass covers Android 15 only; physical multi-manufacturer matrix (checklist §26/§30) remains open — Pixel 4 XL physical pass recommended next.

## Checklist coverage summary

Standard Agent Mode requirements: enrollment ✔, telemetry collectors with graceful fallback ✔, offline queue with caps ✔, WorkManager + FGS split ✔, permission UX ✔, security storage (Keystore-backed EncryptedSharedPreferences) ✔, R8+shrink release ✔, tests started ✔. Managed Device Mode, remote commands, Play release: out of scope for v1 (per checklist's own "build Standard Mode first" guidance).
