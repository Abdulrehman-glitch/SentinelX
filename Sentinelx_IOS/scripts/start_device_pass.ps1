# Starts the dev server for the P5.5 iPhone device pass.
# Prints the exact URLs to enter in the app's Settings screen, warns if the
# firewall rule is missing, then runs uvicorn on 0.0.0.0:8100 (Ctrl+C to stop).

$serverDir = Join-Path $PSScriptRoot "..\server"
$python = Join-Path $serverDir ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "server\.venv not found - create it first (see server\README.md)" -ForegroundColor Red
    exit 1
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.InterfaceAlias -match 'Wi-Fi|Ethernet' -and $_.IPAddress -notmatch '^169\.' } |
    Select-Object -First 1).IPAddress

if (-not $ip) {
    Write-Host "No LAN IP found - connect to Wi-Fi (or the iPhone's hotspot) first." -ForegroundColor Red
    exit 1
}

$rule = netsh advfirewall firewall show rule name="SentinelX Dev Server" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Firewall rule missing - run once in an ADMIN PowerShell:" -ForegroundColor Yellow
    Write-Host '  netsh advfirewall firewall add rule name="SentinelX Dev Server" dir=in action=allow protocol=TCP localport=8100'
    Write-Host ""
}

Write-Host "Enter these in the app: Settings -> Server Overrides" -ForegroundColor Cyan
Write-Host "  API:       http://${ip}:8100/api/v1/mobile"
Write-Host "  WebSocket: ws://${ip}:8100/api/v1/mobile/ws"
Write-Host ""
Write-Host "Dashboard (laptop): http://127.0.0.1:8100/docs"
Write-Host "Starting server on 0.0.0.0:8100 - Ctrl+C to stop." -ForegroundColor Green

Set-Location $serverDir
& $python -m uvicorn app.main:app --host 0.0.0.0 --port 8100
