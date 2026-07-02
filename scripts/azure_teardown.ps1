# Deletes ALL SentinelX Azure resources and stops any credit usage. IRREVERSIBLE.
# Usage:  .\scripts\azure_teardown.ps1
$rg = "sentinelx-rg"
Write-Host "This will permanently delete resource group '$rg' and everything in it." -ForegroundColor Yellow
$confirm = Read-Host "Type the resource group name to confirm"
if ($confirm -eq $rg) {
    az group delete --name $rg --yes
    Write-Host "Deleted. No further credit will be consumed." -ForegroundColor Green
} else {
    Write-Host "Cancelled — nothing was deleted." -ForegroundColor Cyan
}
