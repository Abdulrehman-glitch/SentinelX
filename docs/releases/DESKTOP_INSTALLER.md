# Desktop Agent Installer (Sprint 7 Phase 8)

A GUI Windows installer (`agents/desktop-python/installer/sentinelx_agent_installer.iss`,
compiled with Inno Setup 6) wrapping the existing WinSW service scripts
(`agents/desktop-python/service/`). Built artifact + checksum:
`agents/desktop-python/installer/dist/SentinelXAgentSetup-3.0.0.exe` (+ `.sha256`).

## What it does

1. Checks for Python 3.11+ (via the `py` launcher — see "Why `py`, not
   `python`" below). Aborts with a clear message if missing.
2. Prompts for the backend API base URL and a one-time enrolment code.
3. Copies the agent source, creates a venv, installs dependencies.
4. Writes `.env` from the prompted values.
5. Registers and starts the `SentinelXAgent` Windows service (WinSW),
   running as **LocalSystem** (WinSW's default — no `<serviceaccount>`
   override in `sentinelx-agent.xml`).
6. The service performs its own enrolment on first start.

Uninstall stops and removes the service, then removes installed files
(the venv, `.env`, and downloaded WinSW binary are runtime-created and not
tracked by the installer's file manifest, so they're intentionally left
behind — matching `uninstall_service.ps1`'s existing "local queue/logs were
kept" philosophy).

## Why no interactive pre-run before starting the service

The desktop agent's `README.md`/prerequisites historically said to run the
agent once interactively before installing the service, "so enrolment
stores the device token under the same account the service will use." That
instruction doesn't actually hold: the device token is stored via `keyring`
(Windows Credential Manager), which is **per-user** — an interactive run as
the installing user writes to *that* user's vault, while the service
(LocalSystem) has its own, separate vault. The two were never actually the
same account context.

This installer takes the simpler, correct path instead: it does **not**
run the agent interactively at all. The service performs its own
first-start enrolment as LocalSystem, so enrolment and every later run
happen under the exact same account, consistently. Verified live (Sprint 7
Phase 8 rehearsal): a freshly-installed test service self-enrolled
correctly against a real backend, stored its token, and reported telemetry
successfully from its very first start.

## Why `py`, not `python`

Detection and venv creation use the `py` launcher (`py -3 ...`), not a bare
`python` command. Found live during this sprint: when the installer's
elevated process looked for `python` on PATH, it failed even though Python
was genuinely installed — a user-scope Python install's PATH entry isn't
reliably visible to an elevated (admin) process, but the `py` launcher
(installed to `%WINDIR%` by every python.org installer) always is.

## Why uninstall calls WinSW directly, not through PowerShell

The original `[UninstallRun]` entry called
`powershell.exe -File uninstall_service.ps1`, mirroring how `[Run]` calls
`install_service.ps1` during install. Install worked fine; uninstall did
not — found live during this sprint's rehearsal. The script's own very
first line (a `Start-Transcript` call added specifically to debug this)
never even executed, meaning PowerShell itself wasn't running the script's
content at all inside the compiled uninstaller's (`unins000.exe`) process,
despite the syntactically identical invocation working fine from the
installer's (`Setup.exe`) process. Root cause not fully isolated (most
likely explanation: `unins000.exe` is a separate compiled binary from
`Setup.exe` with a different process-launch/token context) — rather than
keep chasing it, `[UninstallRun]` now calls the bundled
`sentinelx-agent.exe stop` / `sentinelx-agent.exe uninstall` directly, with
no scripting-host layer to go wrong. `uninstall_service.ps1` itself is
unchanged and still works for manual use (see the agent's `README.md`);
only the installer's own invocation path changed.

## Rehearsed live (2026-07-20)

Install → real enrolment against the live staging backend (device
registered, `status: "online"`, real telemetry every ~11s) → re-run the
same installer (upgrade path: non-destructive, service stayed healthy) →
uninstall (service confirmed fully removed via `sc.exe query`). All three
passes used a scratch-named variant (`SentinelXAgentTest` service ID,
distinct install directory and AppId) — the real installer was never run
against this machine's actual `SentinelXAgent` service.

## Rebuilding the installer

```powershell
cd agents\desktop-python\installer
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" sentinelx_agent_installer.iss
Get-FileHash dist\SentinelXAgentSetup-3.0.0.exe -Algorithm SHA256
```

## Known scope limits

- Requires Python 3.11+ pre-installed (checked, not bundled) — judged
  acceptable for a monitoring agent aimed at IT-managed machines rather
  than consumer software; bundling a full runtime (e.g. via PyInstaller)
  was out of scope for this sprint.
- No code-signing certificate — Windows SmartScreen will show an
  "unknown publisher" warning on first run. Expected for an unsigned
  student/coursework build; not a functional defect.
