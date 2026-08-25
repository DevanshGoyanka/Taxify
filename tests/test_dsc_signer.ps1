# DSC Signer Test Script
# Run this after the signer service is started

param(
    [string]$BaseUrl = "http://localhost:9090"
)

Write-Host "🧪 Testing DSC Signer Service" -ForegroundColor Green
Write-Host "=============================" -ForegroundColor Green
Write-Host "Base URL: $BaseUrl" -ForegroundColor White
Write-Host ""

# Test 1: Check if service is running
Write-Host "1. Testing service availability..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$BaseUrl/actuator/health" -Method GET -TimeoutSec 5 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✓ Service is running (HTTP $($response.StatusCode))" -ForegroundColor Green
    } else {
        Write-Host "   ⚠ Service responded with HTTP $($response.StatusCode)" -ForegroundColor Yellow
    }
}
catch {
    # Try basic connection test
    try {
        $tcpTest = New-Object System.Net.Sockets.TcpClient
        $tcpTest.Connect("localhost", 9090)
        $tcpTest.Close()
        Write-Host "   ✓ Service is running on port 9090" -ForegroundColor Green
    }
    catch {
        Write-Host "   ✗ Service is not running on port 9090" -ForegroundColor Red
        Write-Host "   Make sure to start the service first:" -ForegroundColor White
        Write-Host "   java -jar target\local-dsc-signer-1.0.0-SNAPSHOT.jar" -ForegroundColor Cyan
        exit 1
    }
}

# Test 2: Test sign endpoint
Write-Host ""
Write-Host "2. Testing /api/sign endpoint..." -ForegroundColor Yellow

$testPayload = @{
    data = "test data for signing"
    format = "pdf"
} | ConvertTo-Json

try {
    $headers = @{
        'Content-Type' = 'application/json'
        'Accept' = 'application/json'
    }
    
    $response = Invoke-WebRequest -Uri "$BaseUrl/api/sign" -Method POST -Body $testPayload -Headers $headers -TimeoutSec 30 -ErrorAction Stop
    
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✓ Sign endpoint responding (HTTP $($response.StatusCode))" -ForegroundColor Green
        
        # Try to parse response
        try {
            $jsonResponse = $response.Content | ConvertFrom-Json
            Write-Host "   ✓ Valid JSON response received" -ForegroundColor Green
            
            if ($jsonResponse.PSObject.Properties['signature']) {
                Write-Host "   ✓ Signature field present in response" -ForegroundColor Green
            } else {
                Write-Host "   ⚠ No signature field in response" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "   ⚠ Response is not valid JSON" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   ⚠ Sign endpoint responded with HTTP $($response.StatusCode)" -ForegroundColor Yellow
    }
}
catch {
    $errorStatus = $_.Exception.Response.StatusCode.value__
    if ($errorStatus) {
        Write-Host "   ✗ Sign endpoint failed with HTTP $errorStatus" -ForegroundColor Red
        if ($errorStatus -eq 500) {
            Write-Host "   💡 HTTP 500 suggests internal server error - check DSC token connection" -ForegroundColor Cyan
        }
    } else {
        Write-Host "   ✗ Could not connect to sign endpoint: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Test 3: Check logs/status
Write-Host ""
Write-Host "3. Service status summary..." -ForegroundColor Yellow
try {
    $processes = Get-Process | Where-Object { $_.ProcessName -eq "java" -and $_.MainWindowTitle -eq "" }
    if ($processes) {
        Write-Host "   ✓ Found $($processes.Count) Java process(es) running" -ForegroundColor Green
        $processes | ForEach-Object {
            Write-Host "     - PID: $($_.Id), Memory: $([math]::Round($_.WorkingSet64/1MB, 2)) MB" -ForegroundColor White
        }
    } else {
        Write-Host "   ⚠ No Java processes found" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "   ⚠ Could not check Java processes" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎯 Test Results Summary:" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green
Write-Host "- If all tests pass: ✅ DSC Signer is working correctly" -ForegroundColor White
Write-Host "- If HTTP 500 errors: 🔌 Check DSC token connection and PIN" -ForegroundColor White
Write-Host "- If connection fails: 🚀 Start the service first" -ForegroundColor White
Write-Host ""
Write-Host "📋 Common troubleshooting:" -ForegroundColor Yellow
Write-Host "- Ensure USB DSC token is connected" -ForegroundColor White
Write-Host "- Verify DSC PIN is configured correctly" -ForegroundColor White
Write-Host "- Check Windows certificate store has DSC certificate" -ForegroundColor White
Write-Host "- Review service logs for detailed error messages" -ForegroundColor White