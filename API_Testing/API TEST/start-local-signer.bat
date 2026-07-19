@echo off
REM Start Local DSC Signing Service on Windows
REM This script starts the USB DSC token signing service

echo ========================================
echo Starting Local DSC Signing Service
echo Port: 9090
echo Profile: local
echo ========================================

REM Set environment variables
set DSC_PASSWORD=123456789
set DSC_ALIAS=agencykey

REM Check if USB token is inserted
echo Checking USB DSC token...
echo Please ensure USB DSC token is inserted before proceeding.
pause

REM Start the service
echo Starting local DSC signing service...
java -jar -Dspring.profiles.active=local target/eri-tax-erp-phase1-1.0.0-SNAPSHOT.jar

pause