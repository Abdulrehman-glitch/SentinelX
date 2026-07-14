# Testing and Release Guide

## Testing Strategy

Use a practical test pyramid:

| Layer | Tools | Coverage |
|---|---|---|
| Unit | JUnit, coroutine test | Collectors, DTO mappers, repository logic, retry policies. |
| Database | Room testing | Queue insert/update, pending selection, sent/failed transitions. |
| ViewModel | JUnit, coroutine test, Turbine if used | Auth state, dashboard state, sync status. |
| Worker | WorkManager test utilities | Periodic sync and one-time sync behavior. |
| UI | Compose UI test | Login, dashboard, empty/error states. |
| Instrumented | AndroidJUnitRunner | Permissions, service lifecycle, real Room integration. |
| Manual | Pixel 4 XL | Install, login, offline/online sync, Live Mode notification, battery sanity. |

## Minimum v1 Test Cases

P0:

- Login success stores session.
- Login failure shows error and stores no token.
- Logout clears session.
- Device registration is idempotent.
- Battery collector maps expected fields.
- Memory collector handles low-memory signal.
- Storage collector computes used percentage.
- Network collector handles offline and Wi-Fi/cellular states.
- Queue inserts pending telemetry before upload.
- Upload success marks batch sent.
- Upload failure leaves batch pending.
- Worker does not run without network.
- Dashboard shows last sync and queue depth.

P1:

- Foreground service starts only after Live Mode enable.
- Notification permission denial is handled.
- App survives process recreation.
- Alerts/incidents screens handle empty and error states.

## Device and Emulator Matrix

| Target | Purpose |
|---|---|
| Pixel 4 XL physical device | Source-of-truth demo and install validation. |
| API 29 or 30 emulator | Lower-bound modern compatibility depending min SDK. |
| API 33 emulator | Android 13 notification permission behavior. |
| API 34 emulator | Android 14 foreground service type enforcement. |
| API 35 emulator | Android 15 foreground service restrictions and target-era checks. |

## Manual Pixel 4 XL Validation

Checklist:

- Install APK with `adb install`.
- Launch app.
- Login.
- Register device.
- Confirm backend can see device.
- Turn Wi-Fi/mobile data off.
- Generate telemetry sample.
- Confirm pending queue increases.
- Turn network back on.
- Confirm queue flushes.
- Enable Live Mode.
- Confirm persistent notification appears.
- Leave app and confirm Live Mode continues for the expected interval.
- Disable Live Mode.
- Confirm service stops.
- Reboot phone.
- Confirm WorkManager eventually resumes periodic sync after login/session restore.

## Release Strategy

Initial distribution:

- Signed APK.
- ADB install over USB.
- Keep APKs internal.
- Track version code and version name.

Later distribution:

- Firebase App Distribution or Play Internal App Sharing.
- Play Internal Testing when app is closer to store-ready.
- AAB and Play App Signing for Play release.

## Signing Notes

Rules:

- Do not commit release keystore files.
- Do not commit signing passwords.
- Keep debug and release signing separate.
- Document local signing setup after the Android project is scaffolded.
- Generate checksums for release APKs used in demos or submissions.

## Useful Commands After Scaffolding

Exact commands will depend on the generated Gradle project, but likely commands are:

```powershell
.\gradlew assembleDebug
.\gradlew testDebugUnitTest
.\gradlew connectedDebugAndroidTest
.\gradlew assembleRelease
adb devices
adb install app\build\outputs\apk\release\app-release.apk
```

## Definition of Release Candidate

A v1 release candidate must satisfy:

- Builds in release mode.
- Installs on Pixel 4 XL.
- Auth, registration, telemetry, queue, upload, and dashboard work end to end.
- Offline retry is manually verified.
- Live Mode behavior is clear and user-visible.
- No sensitive logs in release.
- Known backend/API limitations are documented.

