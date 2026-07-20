# ============================================
# START LOCAL DSC SIGNER SERVICE
# ============================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STARTING LOCAL DSC SIGNER SERVICE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get the script directory (workspace root)
$workspaceRoot = $PSScriptRoot
Write-Host "Workspace: $workspaceRoot" -ForegroundColor Yellow

# Navigate to local-dsc-signer
$signerPath = Join-Path $workspaceRoot "local-dsc-signer"

if (Test-Path $signerPath) {
    Write-Host "Found local-dsc-signer at: $signerPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "Starting Spring Boot application..." -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to stop the service" -ForegroundColor Yellow
    Write-Host ""
    
    Set-Location $signerPath
    mvn spring-boot:run
} else {
    Write-Host "❌ Error: local-dsc-signer folder not found!" -ForegroundColor Red
    Write-Host "Expected path: $signerPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please ensure you're running this script from the workspace root." -ForegroundColor Yellow
}
