# Guide01 — Running the SentinelX Agent on Your iPhone

This is the start-to-finish guide: what the files in this folder are, how the
app gets built without a Mac, and exactly what to do with your phone.

---

## 1. What's in this folder (30-second tour)

| Folder / file | What it is |
|---------------|------------|
| `SentinelXMobileAgent/` | The app's Swift source code |
| &nbsp;&nbsp;`App/` | App entry point + AppContainer (builds all services at launch) |
| &nbsp;&nbsp;`Collectors/` | The sensors: battery, thermal, storage, network, device info |
| &nbsp;&nbsp;`Services/` | TelemetryManager (validates events), SyncManager (uploads), auth |
| &nbsp;&nbsp;`Persistence/` | The SQLite offline queue — events survive airplane mode & app kills |
| &nbsp;&nbsp;`Networking/` | REST client + WebSocket client (live streaming to the server) |
| &nbsp;&nbsp;`Views/` | The screens you see: Status, Stream, Settings |
| `SentinelXMobileAgentTests/` | ~90 unit tests, run automatically in the cloud |
| `project.yml` | Project definition — GitHub's Mac turns this into an Xcode project |
| `Guide01.md` | This file |

You never build anything on this laptop. **GitHub Actions is your Mac**: every
push builds the app, runs all tests on an iPhone simulator, and produces an
installable `.ipa` file.

---

## 2. One-time setup (~15 minutes, do once)

### On the laptop
1. **Install iTunes** from apple.com (needed for iPhone USB drivers).
2. **Install Sideloadly** from https://sideloadly.io
3. **Open the firewall port** — right-click PowerShell → *Run as administrator*, then:
   ```powershell
   netsh advfirewall firewall add rule name="SentinelX Dev Server" dir=in action=allow protocol=TCP localport=8100
   ```

### Get the app file
The latest built app is already downloaded at:
```
C:\SentinelX\Sentinelx_IOS\dist\SentinelXMobileAgent-unsigned.ipa
```
(To fetch a newer one later: GitHub → **Actions** → *iOS Agent* → latest green
run → download the **SentinelXMobileAgent-unsigned-ipa** artifact.)

### Put it on the iPhone
1. Plug the iPhone in with USB, unlock it, tap **Trust This Computer**.
2. Open Sideloadly, drag the `.ipa` in, enter your Apple ID, press **Start**.
   - If sign-in fails with 2FA, create an app-specific password at
     appleid.apple.com → Sign-In and Security → App-Specific Passwords.
3. On the phone: **Settings → General → VPN & Device Management** → tap your
   Apple ID → **Trust**.
4. **Settings → Privacy & Security → Developer Mode** → turn on → restart the
   phone. (This option only appears after step 2.)

> ⏰ Free Apple ID apps expire after **7 days** — when the app stops opening,
> just repeat the Sideloadly step (2 clicks).

---

## 3. Every time you want to run it (~2 minutes)

1. **Start the server** on the laptop:
   ```powershell
   powershell -File C:\SentinelX\Sentinelx_IOS\scripts\start_device_pass.ps1
   ```
   It prints two URLs — leave this window open.

2. **Same network**: phone and laptop on the same Wi-Fi, or turn on the
   iPhone's **Personal Hotspot** and connect the laptop to it.

3. **In the app** (first run only): open the **Server** section on the login
   screen, paste the API URL the script printed (e.g.
   `http://172.20.10.11:8100/api/v1/mobile`), tap **Save**, then **close and
   reopen the app** — overrides apply at launch.

4. Tap **Register This Device** (first time) or **Connect** (after that).

5. You should see:
   - **Status tab** — live battery / thermal / storage / network cards
   - **Stream tab** — telemetry events scrolling in as they're collected
   - **Settings → Offline Queue** — "Uplink: Streaming" and Pending ≈ 0

6. **Watch it land on the server**: open http://127.0.0.1:8100/docs on the
   laptop → `GET /api/v1/mobile/dashboard/devices` → Execute → your iPhone
   appears with its latest telemetry.

---

## 4. The airplane-mode test (Phase 5 acceptance — the demo highlight)

This proves the offline queue: **no event is ever lost, none duplicated.**

1. With the app running and streaming, note the server's stored-event count
   (dashboard endpoint above).
2. Turn on **Airplane Mode** on the phone. In Settings → Offline Queue, watch
   **Pending** climb — events are being saved to the SQLite queue.
3. **Force-kill the app** (swipe up, flick it away). This simulates a crash.
4. Reopen the app, turn Airplane Mode **off**.
5. Within ~30 seconds the queue drains: Pending returns to 0, and the server's
   count includes every queued event **exactly once**.

If that works on your phone, Phase 5 is officially complete.

---

## 5. When something doesn't work

| Symptom | Fix |
|---------|-----|
| App won't open, "Untrusted Developer" | Trust the cert (one-time setup step 3) |
| App won't open after a week | 7-day signature expired — re-sideload |
| "Register" spins then errors | Phone can't reach the laptop: same network? server running? firewall rule added? URL saved **and app relaunched**? |
| Stream tab empty | Give it ~30 s; battery % only ticks on change — plug/unplug the charger to force events |
| Uplink says "REST fallback" | WebSocket URL override missing/wrong — check Settings → Server, relaunch |
| Wrong URL saved | Fix it in app Settings → Server overrides, relaunch the app |
| Want a clean slate | Login screen → **Forget this device** (re-registers fresh), or delete + reinstall the app |

Server-side logs appear live in the PowerShell window running the script.
