# SentinelX Android Agent — Changelog

## 1.2.0 (versionCode 3) — 2026-07-12

- Apple-style glass redesign: soft tinted gradient backdrop, translucent frosted panels with hairline borders and indigo-tinted shadows, on all three screens (login, dashboard, settings); light and dark variants.
- Fixed: hardware back from Settings exited the app instead of returning to the dashboard (BackHandler added).

## 1.1.0 (versionCode 2) — 2026-07-12

Production hardening from the full checklist audit (`AUDIT_REPORT.md`):

- Fixed: Live Mode service stacked duplicate sampling loops on repeated start commands (double uploads).
- Fixed: denying notification permission dead-ended Live Mode; it now starts with the notification suppressed.
- Added: Settings → Diagnostics → "Test server connection" (health round-trip with latency).
- Added: password visibility toggle and keyboard Next/Done flow on login.
- Added: first unit-test suite (9 tests: URL normalization, telemetry math, battery summary).
- Improved: three-state health dot (amber until first successful sync); manual sync status auto-clears; battery level falls back to BatteryManager instead of showing 0%; Live Mode row is screen-reader accessible.
- Build: fixed release R8 failure (Tink compile-only annotations); R8 + resource shrinking on.

## 1.0.0 (versionCode 1) — 2026-07-11

- Initial release: login, device enrollment (register + credential mint), battery/memory/storage/network/CPU-estimate telemetry, heartbeats, offline Room queue (cap 2000), 15-min WorkManager sync, foreground-service Live Mode, Compose dashboard + settings.
