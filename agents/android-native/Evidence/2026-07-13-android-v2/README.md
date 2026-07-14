# Evidence Index — SentinelX Android Agent v2.0.0 — 2026-07-13

Live captures via `adb exec-out screencap` on AVD `sentinelx_api35` (Pixel 6, Android 15/API 35),
running the **signed release APK v2.0.0** against the real FastAPI backend
(`http://10.0.2.2:8000`, native Postgres) and the real Vite web console.
Console captures are rendered terminal output from the actual runs.

## App tour (Sentinel Glass, light-first)
| File | Shows |
|---|---|
| 01-home-orb-upgrade-preserved.png | v1.2.1→v2.0.0 upgrade install: enrollment + Room queue preserved; health orb 92 (agent sub-score penalised for 14h-stale sync — engine working); 2×2 metric tiles, quick actions, 7-tab nav |
| 02-live-monitor-stopped.png | Live Monitor idle: mode chips, current readings incl. backend latency (789 ms via /metrics/batch) + thermal state |
| 03-live-monitor-running.png | Foreground service running: duration ticker, red stop button, live event feed ("Live monitoring started · Mode: balanced") |
| 04-health-breakdown-top.png | Health 100 — battery/memory/storage cards with real values and per-category scores |
| 05-health-breakdown-bottom.png | Network + agent-reliability categories (latency, failures, token state) |
| 06-alerts-list.png | Real backend alerts (CPU critical/warning from org alert rules), severity chips, badge count 30, role-gated "Mark resolved" |
| 07-diagnostics-running.png | Diagnostic suite mid-run (progress counter) |
| 08-diagnostics-results-top.png | 12 tests: 10 passed, 2 warnings, 0 failed — summary card + per-test detail and duration |
| 09-diagnostics-results-bottom.png | Full list incl. clock skew (1 s vs server) and the two honest warnings (cleartext dev transport, battery optimisation); "Share redacted report" |
| 10-activity-timeline-all.png | Local event timeline: diagnostics, backend alert events, live-mode start — severities + filters |
| 11-activity-filter-monitoring.png | Category filter applied (Monitoring) |
| 12-settings-top.png | Account/enrollment (org, agent ID, server), monitoring mode chips, upload policy toggles |
| 13-settings-bottom.png | Appearance (theme, reduced motion), privacy summary, delete-local-data, about block (v2.0.0) |
| 14-settings-dark-theme.png | Dark Sentinel Glass variant (spec palette #080A10 / #8B7CFF) |
| 15-home-dark-theme.png | Home after theme switch — light restored afterwards (light is the default identity) |

## Resilience & batch-timestamp proof (/metrics/batch)
| File | Shows |
|---|---|
| 16-offline-queueing.png | Airplane mode: orb goes grey "76 OFFLINE", "Backend unreachable" text (not colour alone), Network tile None with sparkline drop |
| 17-regain-flushed.png | 15 s after regain: orb back to 100, "last sync just now", Network sparkline shows the dip-and-recover |
| 18-backend-batch-timestamps-preserved.png | Backend rows: offline samples (net=none) landed with their ORIGINAL capture timestamps (13:27:13, 13:29:13) after the 13:30 flush; battery/charging/network columns populated |

## Alerts round-trip & fixes found during the pass
| File | Shows |
|---|---|
| 19-alerts-titled.png | Fix verified: rule-based alerts now titled from the rule name ("CPU Critical") instead of raw `alert_rule:<uuid>` |
| 20-alert-resolved.png | "Mark resolved" from the phone (admin JWT → PATCH /alerts/…/resolve): green Resolved, badge 36→35 |
| 23-web-cors-failed-to-fetch.png | Error found live: web login from the emulator browser failed ("Failed to fetch") — Origin http://10.0.2.2:5173 missing from CORS allowlist; fixed in backend/.env |

## Web console wiring (same telemetry, browser view)
| File | Shows |
|---|---|
| 21-web-dashboard-fleet.png | Ops console in emulator Chrome: fleet incl. this device; event stream shows the phone-initiated "Alert Resolved" |
| 22-web-device-detail-mobile-cards.png | Device detail renders the new mobile cards: Battery 100% · charging, Network Transport wifi — live from POST /metrics/batch |
