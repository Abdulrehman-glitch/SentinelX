# Stops and removes the SentinelX desktop agent Windows Service. For manual
# use (see README) — the installer's uninstaller calls sentinelx-agent.exe
# directly instead of this script (see the installer .iss for why).
$ErrorActionPreference = "Stop"

$winswExe = Join-Path $PSScriptRoot "sentinelx-agent.exe"
$winswXml = Join-Path $PSScriptRoot "sentinelx-agent.xml"
if (-not (Test-Path $winswExe)) {
    throw "sentinelx-agent.exe not found — the service does not appear to be installed from this folder."
}

& $winswExe stop

# WinSW's `stop` returns once it has issued the stop request; the Service
# Control Manager can take a few seconds to actually finish tearing the
# process down. Calling `uninstall` immediately can lose the race (SCM
# refuses to delete a service still in "stop pending"), so wait for a real
# Stopped/absent state before uninstalling, and retry if it still loses the
# race — found live during the Phase 8 install/upgrade/uninstall rehearsal
# (an installer-driven uninstall failed here on its first try). Service id
# is read from the XML rather than hardcoded so this also works unmodified
# against a differently-named service (e.g. a test rig).
$serviceName = ([xml](Get-Content $winswXml -Raw)).service.id
for ($i = 0; $i -lt 15; $i++) {
    $svc = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if ($null -eq $svc -or $svc.Status -eq "Stopped") { break }
    Start-Sleep -Seconds 1
}

$uninstallAttempts = 0
do {
    $uninstallAttempts++
    & $winswExe uninstall
    $stillPresent = $null -ne (Get-Service -Name $serviceName -ErrorAction SilentlyContinue)
    if ($stillPresent -and $uninstallAttempts -lt 3) {
        Start-Sleep -Seconds 2
    }
} while ($stillPresent -and $uninstallAttempts -lt 3)

if ($stillPresent) {
    throw "Service '$serviceName' could not be uninstalled after $uninstallAttempts attempt(s) — it may still be shutting down. Re-run this script."
}

Write-Host "SentinelX Agent service removed. Local queue/logs in $env:LOCALAPPDATA\SentinelX were kept."
