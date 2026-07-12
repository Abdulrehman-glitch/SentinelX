# Evidence Index — Android Production Session 2026-07-12

Captured live via `adb exec-out screencap` on AVD `sentinelx_api35` (Pixel 6, Android 15/API 35), running the **signed release APK** against the real FastAPI backend (`http://10.0.2.2:8000`, native Postgres). Backend-side proofs are JSON/text captured from the API at the same moments.

Round 1 (01–16) ran on v1.1.0; round 2 (17–29) on v1.1.0 pre-glass. Post-glass v1.2.0 visuals are 30+.

## Happy path
| File | Shows |
|---|---|
| 01-emulator-booted-api35.png | Clean Android 15 device before install |
| 02-login-screen-first-launch.png | First launch, empty login, password eye toggle |
| 03-login-filled.png | Valid credentials filled, Sign in enabled |
| 04-dashboard-enroll-card.png | Post-login: enroll card + live telemetry cards |
| 05-device-enrolled.png | Enrolled: hostname, green dot, queue 0 |
| 06-backend-device-record.json | Backend device row: android_mobile_agent v1.1.0 online |
| 07-manual-sync-result.png | "Uploaded 1 sample(s)" after Sync now |
| 08-notification-permission-dialog.png | Android 13+ POST_NOTIFICATIONS request |
| 09-live-mode-active.png | Live Mode on, toggle active |
| 10-live-mode-notification.png | Foreground notification with Stop action |

## Resilience (offline → recovery)
| File | Shows |
|---|---|
| 11-offline-queueing.png | Network cut: red dot, clear error, 2 samples queued |
| 12-recovery-after-reconnect.png | Reconnected: queue drained, green dot |
| 13-backend-metric-rows.txt | 10 metric rows incl. queued pair landing 1s apart (no loss) |

## Features & theming
| File | Shows |
|---|---|
| 14-settings-screen.png | Settings: account, device, interval, diagnostics, danger zone |
| 15-diagnostics-test-connection.png | "API online, database online · 729 ms · v2.0.0" |
| 16-dark-theme-dashboard.png | Dark theme; Live Mode survived relaunch |
| 17-settings-interval-15s.png | Interval chip change persisted |

## Error states & RBAC (deliberately induced)
| File | Shows |
|---|---|
| 18-signout-confirm-dialog.png | Sign-out confirmation copy |
| 19-signedout-agent-still-syncing.png | Signed out, agent keeps syncing on device token |
| 20-revoked-token-error.png | Backend-revoked credential → "Device token rejected… Re-enroll", samples queue |
| 21-revoked-token-notification.png | Same failure surfaced in Live Mode notification |
| 22-unlink-confirm-dialog.png | Unlink confirmation copy |
| 23-unlinked-back-to-login.png | Post-unlink: login screen, server URL persisted |
| 24-login-wrong-password-error.png | "Invalid email or password." (no stack trace) |
| 25-viewer-role-enroll-blocked.png | Viewer role: enroll disabled with amber explanation |
| 26-reenrolled-after-revocation.png | Recovery: fresh credential, green sync |

## Lifecycle & accessibility
| File | Shows |
|---|---|
| 27-state-survives-force-stop.png | Force-stop + relaunch: enrollment/state intact, Live Mode correctly off |
| 28-landscape-rotation.png | Landscape layout |
| 29-large-text-1_3x.png | 1.3× font scale, text wraps correctly |

## Glass redesign (v1.2.0)
| File | Shows |
|---|---|
| 30-glass-dashboard-upgrade-preserved.png | v1.1.0→v1.2.0 upgrade install: enrollment + sync history preserved; new glass light theme |
| 31-glass-settings.png | Glass settings (agent version 1.2.0) |
| 32-glass-dark-settings.png | Glass settings, dark |
| 33-glass-dark-dashboard.png | Glass dashboard, dark |
| 34-back-from-settings-fixed.png | Hardware back from Settings returns to dashboard (bug found in this session, fixed in 1.2.0) |
