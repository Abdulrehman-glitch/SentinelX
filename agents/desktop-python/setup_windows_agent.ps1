<#
.SYNOPSIS
    One-shot SentinelX Windows agent setup.

.DESCRIPTION
    Run the command shown on the SentinelX console (Devices -> Add Device ->
    Windows). It carries a short-lived one-time pairing code; this script:

      1. Creates the agent virtualenv and installs requirements (idempotent)
      2. Points the agent at the backend (.env holds the URL only - never a
         token; the pairing code is passed through the environment and is
         dead after one use)
      3. Enrols this machine: the device token is stored in Windows
         Credential Manager, and the first heartbeat + telemetry sample are
         delivered so the console confirms the pairing live
      4. Installs and starts the SentinelXAgent Windows service (elevated
         shells only; WinSW asks which account to run as - pick the account
         you are enrolling with, since it owns the stored credential)

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup_windows_agent.ps1 `
        -BackendUrl http://192.168.1.42:8000 -PairingCode sxe_...
#>
param(
    [Parameter(Mandatory = $true)][string]$BackendUrl,
    [Parameter(Mandatory = $true)][string]$PairingCode,
    [string]$DisplayName = "",
    [switch]$SkipService
)

$ErrorActionPreference = "Stop"
$agentDir = $PSScriptRoot

Write-Host ""
Write-Host "SentinelX Windows Agent setup" -ForegroundColor Cyan
Write-Host "Backend: $BackendUrl"
Write-Host ""

# --- 1. Python + virtualenv -------------------------------------------------
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python 3.11+ is required but was not found on PATH. Install it from python.org, then re-run this script."
}

$venvPython = Join-Path $agentDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[1/4] Creating virtualenv..."
    & python -m venv (Join-Path $agentDir ".venv")
} else {
    Write-Host "[1/4] Virtualenv already present."
}

Write-Host "      Installing agent requirements (quiet)..."
& $venvPython -m pip install --quiet --disable-pip-version-check -r (Join-Path $agentDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed - see output above." }

# --- 2. Point the agent at the backend --------------------------------------
# .env carries configuration only. The pairing code is single-use and passed
# via the process environment; the device token never touches a file.
$envFile = Join-Path $agentDir ".env"
$apiBase = $BackendUrl.TrimEnd("/") + "/api/v1"

$lines = @()
if (Test-Path $envFile) {
    $lines = Get-Content $envFile | Where-Object {
        $_ -notmatch "^\s*SENTINELX_API_BASE_URL=" -and
        $_ -notmatch "^\s*SENTINELX_ENROLLMENT_CODE=" -and
        (-not $DisplayName -or $_ -notmatch "^\s*SENTINELX_AGENT_DISPLAY_NAME=")
    }
}
$lines += "SENTINELX_API_BASE_URL=$apiBase"
if ($DisplayName) { $lines += "SENTINELX_AGENT_DISPLAY_NAME=$DisplayName" }
Set-Content -Path $envFile -Value $lines -Encoding utf8
Write-Host "[2/4] Backend address written to .env"

# --- 3. Enrol + first telemetry ---------------------------------------------
Write-Host "[3/4] Enrolling this machine with SentinelX..."
$env:SENTINELX_ENROLLMENT_CODE = $PairingCode
try {
    & $venvPython -m sentinelx_agent --enroll-only
    if ($LASTEXITCODE -ne 0) { throw "Enrolment failed - the pairing code may have expired. Open the console and start a new pairing session." }
} finally {
    Remove-Item Env:SENTINELX_ENROLLMENT_CODE -ErrorAction SilentlyContinue
}
Write-Host "      Device enrolled; token stored in Windows Credential Manager."

# --- 4. Windows service -----------------------------------------------------
$isElevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($SkipService) {
    Write-Host "[4/4] Service install skipped (-SkipService). Start the agent manually with:"
    Write-Host "      .\.venv\Scripts\python.exe -m sentinelx_agent"
} elseif (-not $isElevated) {
    Write-Host "[4/4] Not elevated - skipping service install." -ForegroundColor Yellow
    Write-Host "      To run SentinelX as a background service, open an elevated PowerShell and run:"
    Write-Host "      powershell -ExecutionPolicy Bypass -File `"$agentDir\service\install_service.ps1`""
    Write-Host "      Until then, start the agent with: .\.venv\Scripts\python.exe -m sentinelx_agent"
} else {
    Write-Host "[4/4] Installing the SentinelXAgent Windows service..."
    Write-Host "      When WinSW asks for an account, use THIS account - it holds the device credential."
    & (Join-Path $agentDir "service\install_service.ps1")
}

Write-Host ""
Write-Host "Setup complete. The console should now show this machine under SentinelX Live." -ForegroundColor Green
