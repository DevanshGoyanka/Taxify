# ============================================
# ERI LOGIN PAYLOAD GENERATOR
# ============================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ERI LOGIN PAYLOAD GENERATOR" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create canonical JSON
$eriUserId = "ERIP011535"
$timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
$canonicalJson = "{`"eriUserId`":`"$eriUserId`",`"timestamp`":`"$timestamp`"}"

Write-Host "1. Canonical JSON:" -ForegroundColor Yellow
Write-Host $canonicalJson
Write-Host ""

# Step 2: Sign with local DSC signer
Write-Host "2. Signing with USB DSC token..." -ForegroundColor Yellow
$signRequest = @{ payload = $canonicalJson } | ConvertTo-Json

try {
    $signResult = Invoke-RestMethod -Uri http://localhost:9090/api/sign -Method Post -Body $signRequest -ContentType "application/json"
    
    Write-Host "   ✅ Signature generated!" -ForegroundColor Green
    Write-Host "   Signature length: $($signResult.sign.Length) characters" -ForegroundColor Green
    Write-Host ""
    
    # Step 3: Construct ERI payload
    Write-Host "3. Final ERI Login Payload:" -ForegroundColor Yellow
    $eriPayload = @{
        sign = $signResult.sign
        data = $signResult.data
        eriUserId = $eriUserId
    }
    
    $eriPayloadJson = $eriPayload | ConvertTo-Json -Depth 10
    Write-Host $eriPayloadJson
    Write-Host ""
    
    # Step 4: Save to file for easy use
    $eriPayloadJson | Out-File -FilePath "eri_login_payload.json" -Encoding UTF8
    Write-Host "✅ Payload saved to: eri_login_payload.json" -ForegroundColor Green
    Write-Host ""
    
    # Step 5: Show curl command for testing from AWS
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "NEXT STEPS: TEST WITH ITD ERI API" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Option A: Test from AWS EC2 (recommended)" -ForegroundColor Yellow
    Write-Host "SSH into AWS and run:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "curl -X POST 'https://uatocpservices.incometax.gov.in/v1/auth/login' \"
    Write-Host "  -H 'Content-Type: application/json' \"
    Write-Host "  -H 'client-id: 4fea04621c7b5660dbb12b959a29b0ee' \"
    Write-Host "  -H 'client-secret: e754ceb48732c4e197658f76bcc69037' \"
    Write-Host "  -d @eri_login_payload.json"
    Write-Host ""
    Write-Host "Option B: Test from your laptop (if you have VPN)" -ForegroundColor Yellow
    Write-Host "Use the same curl command above" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    Write-Host "❌ Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Is local signer running on port 9090?"
    Write-Host "2. Is USB token inserted?"
    Write-Host "3. Try: Invoke-RestMethod -Uri http://localhost:9090/api/health"
}
