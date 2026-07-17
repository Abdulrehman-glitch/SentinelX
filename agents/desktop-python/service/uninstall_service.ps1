# Stops and removes the SentinelX desktop agent Windows Service.
$ErrorActionPreference = "Stop"

$winswExe = Join-Path $PSScriptRoot "sentinelx-agent.exe"
if (-not (Test-Path $winswExe)) {
    throw "sentinelx-agent.exe not found — the service does not appear to be installed from this folder."
}

& $winswExe stop
& $winswExe uninstall

Write-Host "SentinelX Agent service removed. Local queue/logs in $env:LOCALAPPDATA\SentinelX were kept."
