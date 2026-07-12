# Security and Privacy

## Security Posture

SentinelX Android handles operational telemetry and authenticated console access. Treat it as a sensitive internal tool even while it is distributed as a sideloaded APK.

v1 security goals:

- No hardcoded credentials.
- HTTPS-only transport.
- Secure token storage.
- Least-privilege permissions.
- Minimal telemetry collection.
- No sensitive logging.
- Release signing for APK builds.

## Permissions Plan

| Feature | Permission | v1? | Notes |
|---|---|---|---|
| API calls | `INTERNET` | Yes | Required for backend communication. |
| Connectivity state | `ACCESS_NETWORK_STATE` | Yes | Required for network status and sync constraints. |
| Foreground service | `FOREGROUND_SERVICE` | Yes, when Live Mode exists | Required for foreground service behavior. |
| Data sync foreground service | `FOREGROUND_SERVICE_DATA_SYNC` | Yes for API 34+ Live Mode | Declare matching service type. |
| Notifications | `POST_NOTIFICATIONS` | Yes for Android 13+ Live Mode | Runtime permission for foreground notification visibility. |
| Location | `ACCESS_COARSE_LOCATION` / `ACCESS_FINE_LOCATION` | No | Defer to v2 only with explicit product need. |
| Background location | `ACCESS_BACKGROUND_LOCATION` | No | Avoid unless absolutely necessary. |
| Package usage stats | `PACKAGE_USAGE_STATS` | No | Avoid in v1 due privacy and special access friction. |
| Nearby Wi-Fi devices | `NEARBY_WIFI_DEVICES` | No | Only if richer Wi-Fi detail becomes a justified v2 feature. |

## Token and Secret Handling

Rules:

- Do not commit API tokens, JWTs, signing passwords, keystores, or backend secrets.
- Keep access tokens short-lived where backend support exists.
- Store refresh/bootstrap secrets only if necessary.
- Use Android Keystore-backed encryption for sensitive persisted values.
- Redact tokens and auth headers from logs.
- Clear local session state on logout.

## Network Security

Requirements:

- Use HTTPS for all backend environments.
- Reject cleartext traffic in release builds.
- Define Network Security Configuration explicitly.
- Do not disable certificate validation.
- Consider certificate pinning or mTLS only after the basic flow is stable.

## Privacy Boundaries

v1 should collect:

- Device identity metadata.
- Battery state.
- Memory state.
- Storage state.
- Network connectivity state.
- Sync status.

v1 should not collect:

- Precise location.
- Contacts, SMS, call logs, photos, microphone, or camera data.
- Installed app inventory.
- Foreground app usage.
- Raw continuous sensor streams.

## Threat Model

| Threat | Risk | Mitigation |
|---|---|---|
| Token leakage | Rogue client can impersonate user/device | Secure storage, short-lived tokens, redacted logs, scoped device token. |
| Replay or duplicate telemetry | Incorrect metrics or duplicate alerts | Client-generated batch IDs and backend idempotency. |
| Cleartext traffic | Telemetry/session interception | HTTPS only and release cleartext disabled. |
| Overbroad permissions | Privacy and Play readiness risk | Minimal v1 permission set. |
| Lost offline data | Monitoring gaps | Room queue and retry worker. |
| Infinite queue growth | Storage pressure on device | Retention and max queue policy. |
| Tampered APK | Malicious internal redistribution | Release signing, checksums, controlled distribution. |
| Outdated Pixel security | Sensitive credentials at higher risk | Use internal/staging scope and avoid high-value secrets. |

## Release Logging Policy

Release logs may include:

- Endpoint category without full sensitive query parameters.
- HTTP status code.
- Batch ID.
- Device ID only if needed and not considered secret.
- Error class.

Release logs must not include:

- JWTs.
- Device tokens.
- Passwords.
- Authorization headers.
- Full telemetry payloads unless sanitized and explicitly enabled for debug builds.

