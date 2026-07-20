@echo off
REM Start Local DSC Signing Service
REM Runs on Windows laptop with USB DSC token

echo ========================================
echo Local DSC Signing Service
echo Port: 9090
echo ========================================

REM Set environment variables
set DSC_TOKEN_PIN=123456789
set DSC_TOKEN_ALIAS=agencykey
set DSC_PKCS11_LIBRARY=C:\Windows\System32\eps2003csp11v2.dll

echo.
echo Checking USB DSC token...
echo Please ensure USB token is inserted.
echo.
pause

echo Starting Local DSC Signing Service...
java -jar target/local-dsc-signer-1.0.0-SNAPSHOT.jar

pause
