# Running the Agent on Your iPhone — No Mac Required

The Swift code is built and tested by GitHub Actions on a free cloud Mac
(`.github/workflows/ios.yml`). You never need macOS locally. This guide
covers getting the resulting app onto your iPhone from a Windows laptop.

## How the pipeline works

1. Push to `feature/ios-mobile-agent` (any change under `Sentinelx_IOS/ios/`)
   — or trigger manually: GitHub → **Actions** → *iOS Agent* → **Run
   workflow**.
2. The workflow generates the Xcode project, runs the full unit-test suite
   on an iOS Simulator, then builds an **unsigned** `SentinelXMobileAgent-
   unsigned.ipa` and attaches it as a build artifact (kept 14 days).
3. Download the artifact zip from the workflow run page onto your laptop.

## Installing the .ipa from Windows (sideloading)

Apple requires every app on a real iPhone to be signed. Sideloading tools
sign the .ipa with your own **free Apple ID** on your Windows machine:

**Sideloadly** (recommended, simplest):
1. Install iTunes (from Apple's site, not the Microsoft Store build if it
   gives trouble) — Sideloadly needs its device drivers.
2. Install Sideloadly from sideloadly.io.
3. Connect the iPhone by USB, unlock it, tap **Trust This Computer**.
4. Drag `SentinelXMobileAgent-unsigned.ipa` into Sideloadly, enter your
   Apple ID, click **Start**. (Use an app-specific password if your Apple
   ID has 2FA and the login is refused: appleid.apple.com → Sign-In and
   Security → App-Specific Passwords.)
5. On the iPhone: **Settings → General → VPN & Device Management** → trust
   your developer certificate.
6. iOS 16+: enable **Settings → Privacy & Security → Developer Mode**
   (appears after the first sideload; requires a reboot).

*AltStore (altstore.io) is an equivalent alternative — install AltServer
on Windows, then it can re-sign apps over Wi-Fi.*

## Free Apple ID limits (worth knowing)

- The signature expires after **7 days** — re-sideload to refresh
  (Sideloadly/AltStore make this a two-click job; AltStore can auto-refresh
  over Wi-Fi).
- Max **3 sideloaded apps** at a time, 10 App IDs per week.
- Some entitlements (push notifications, iCloud) are unavailable — the
  agent doesn't use them. Keychain, URLSession, WebSockets, CoreMotion,
  battery/thermal/storage/network APIs all work fine.
- A paid Apple Developer account ($99/yr) removes the 7-day limit (1 year)
  and enables TestFlight, but is **not needed** for this project.

## Pointing the iPhone at your dev server

The app defaults to `127.0.0.1:8100`, which is the *phone itself* — change
it in the app's **Settings** screen to your laptop's LAN address:

1. Start the dev server so it listens on the network:
   ```powershell
   cd C:\SentinelX\Sentinelx_IOS\server
   .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8100
   ```
2. Find the laptop's Wi-Fi IP: `ipconfig` → IPv4 Address (e.g. `192.168.1.20`).
3. Allow inbound port 8100 once, in an **admin** PowerShell:
   ```powershell
   netsh advfirewall firewall add rule name="SentinelX Dev Server" dir=in action=allow protocol=TCP localport=8100
   ```
4. Phone and laptop on the **same Wi-Fi**; in the app's Settings set:
   - API: `http://192.168.1.20:8100/api/v1/mobile`
   - WebSocket: `ws://192.168.1.20:8100/api/v1/mobile/ws`
5. Register/login in the app — telemetry should appear via the dashboard
   endpoints (`http://127.0.0.1:8100/docs` on the laptop).

Plain HTTP to a LAN address is allowed by the app's transport security
exception for local networking; production traffic would use HTTPS/WSS.
