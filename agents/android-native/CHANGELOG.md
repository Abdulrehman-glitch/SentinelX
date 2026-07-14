# SentinelX Android Agent — Changelog

## 2.1.0 (versionCode 7) — 2026-07-13

Brand release — the new SentinelX identity (steel spartan mark, graphite + signal red):

- New launcher icon: adaptive icon built from the brand mark on a graphite background (replaces the stock vector + indigo).
- Login screen shows the brand mark instead of the generic shield icon.
- Palette re-derived from the logo: primary accent moves from indigo (#6757E8) to signal red (#C8102E light / #FF4D5E dark); primary containers retuned to match. Severity colours (healthy/warning/critical/offline) unchanged.

## 2.0.1 (versionCode 6) — 2026-07-13

UI/UX audit pass (Material Design navigation + back-stack rules):

- Fixed: hardware/gesture back exited the app from any section — a regression of the v1.2.0 Settings back fix lost in the v2 restructure. Back now walks the hierarchy: Diagnostics/Activity → Settings, any other section → Home, Home → exit.
- Bottom navigation reduced from 7 to 5 destinations (Material limit): Home, Live, Health, Alerts, Settings. Diagnostics and Activity moved into a new Settings → Tools section (Diagnostics also stays one tap away via the Home quick action); Settings stays highlighted while either is open, and the cramped "Diag" label abbreviation is gone.
- Settings "Diagnostics & about" section renamed to "Connection & about".

## 2.0.0 (versionCode 5) — 2026-07-13

Full app restructure to the "Sentinel Glass" spec (light-first observability UI):

- Seven sections behind bottom navigation (nav rail on wide screens): Home, Live, Health, Alerts, Diagnostics, Activity, Settings. Edge-to-edge.
- Home: animated health orb (0–100 score, tap for breakdown), four metric tiles with sparklines, quick actions (collect/upload/live/diagnostics), agent status strip.
- Explainable health engine: battery/memory/storage/network/agent-reliability sub-scores, equally weighted, unit-tested; Health screen shows exactly how the score is built.
- Live Monitor: Balanced (60s) / Active (30s) / Diagnostic (10s, auto-stops after 10 min) modes, duration ticker, thermal state, live event feed.
- Alerts: device-scoped alerts fetched from the backend with the device token; engineer+ can resolve with their console session; viewers are read-only.
- Diagnostics centre: 12 one-tap checks (internet, DNS, TLS, backend, auth token, upload, Room, WorkManager, notifications, battery optimisation, storage, clock skew) with a redacted shareable report.
- Activity: local event timeline (Room) with category filters and expandable details.
- Settings: monitoring mode, Wi-Fi-only uploads, pause-on-low-battery, theme (light default/dark/system), reduced motion, privacy summary, delete-local-data.
- Sync: uploads now use `POST /metrics/batch` with per-sample capture timestamps (offline queues land as real history) plus battery/network fields; latency measured per flush.
- Notification channels split: monitoring status (low), alerts (high), recovery (default).
- Room v2 migration preserves queued samples across the upgrade.

Backend/web (same repo): `system_metrics` gains nullable battery/network/latency columns (additive SQL, no wipe), `/metrics/batch`, `/alerts/device/me`; device detail page shows mobile telemetry cards.

## 1.2.1 (versionCode 4) — 2026-07-12

- Live Mode: exponential backoff while the backend is unreachable (2×/4×/8× the configured interval, capped at 120s or the interval itself, whichever is larger) instead of hammering a dead link every 15s.
- Live Mode: a `ConnectivityManager` network callback wakes the sampling loop the moment connectivity returns, so the offline queue flushes immediately instead of waiting out the backed-off delay.

## 1.2.0 (versionCode 3) — 2026-07-12

- Apple-style glass redesign: soft tinted gradient backdrop, translucent frosted panels with hairline borders and indigo-tinted shadows, on all three screens (login, dashboard, settings); light and dark variants.
- Fixed: hardware back from Settings exited the app instead of returning to the dashboard (BackHandler added).

## 1.1.0 (versionCode 2) — 2026-07-12

Production hardening from the full checklist audit:

- Fixed: Live Mode service stacked duplicate sampling loops on repeated start commands (double uploads).
- Fixed: denying notification permission dead-ended Live Mode; it now starts with the notification suppressed.
- Added: Settings → Diagnostics → "Test server connection" (health round-trip with latency).
- Added: password visibility toggle and keyboard Next/Done flow on login.
- Added: first unit-test suite (9 tests: URL normalization, telemetry math, battery summary).
- Improved: three-state health dot (amber until first successful sync); manual sync status auto-clears; battery level falls back to BatteryManager instead of showing 0%; Live Mode row is screen-reader accessible.
- Build: fixed release R8 failure (Tink compile-only annotations); R8 + resource shrinking on.

## 1.0.0 (versionCode 1) — 2026-07-11

- Initial release: login, device enrollment (register + credential mint), battery/memory/storage/network/CPU-estimate telemetry, heartbeats, offline Room queue (cap 2000), 15-min WorkManager sync, foreground-service Live Mode, Compose dashboard + settings.
