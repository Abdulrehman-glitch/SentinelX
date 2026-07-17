# Installs the SentinelX desktop agent as a Windows Service via WinSW.
#
# Prerequisites (run once, from agents\desktop-python):
#   1. python -m venv .venv; .\.venv\Scripts\Activate.ps1
#   2. pip install -r requirements.txt
#   3. Copy .env.example to .env, set SENTINELX_ENROLLMENT_CODE (or dev token)
#   4. Run the agent once interactively so enrolment stores the device token
#      under the SAME account the service will use.
#
# Then run this script from an elevated PowerShell.

$ErrorActionPreference = "Stop"

$serviceDir = $PSScriptRoot
$agentDir = Split-Path $serviceDir -Parent
$pythonExe = Join-Path $agentDir ".venv\Scripts\python.exe"
$winswExe = Join-Path $serviceDir "sentinelx-agent.exe"
$winswXmlSrc = Join-Path $serviceDir "sentinelx-agent.xml"

if (-not (Test-Path $pythonExe)) {
    throw "Agent virtualenv not found at $pythonExe. Create it and install requirements first."
}

if (-not (Test-Path $winswExe)) {
    Write-Host "WinSW executable not found. Downloading WinSW-x64.exe (v2.12.0)..."
    $url = "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe"
    Invoke-WebRequest -Uri $url -OutFile $winswExe
}

# Materialise the service definition with absolute paths.
$xml = Get-Content $winswXmlSrc -Raw
$xml = $xml.Replace("PYTHON_EXE_PLACEHOLDER", $pythonExe).Replace("AGENT_DIR_PLACEHOLDER", $agentDir)
Set-Content -Path (Join-Path $serviceDir "sentinelx-agent.xml") -Value $xml -Encoding utf8

& $winswExe install
& $winswExe start

Write-Host ""
Write-Host "SentinelX Agent service installed and started."
Write-Host "Status:    .\sentinelx-agent.exe status"
Write-Host "Logs:      $env:LOCALAPPDATA\SentinelX\logs\agent.log"
Write-Host "Uninstall: .\uninstall_service.ps1"
