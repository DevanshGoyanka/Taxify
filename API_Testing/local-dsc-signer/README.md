# Local DSC Signing Service

## Purpose
USB DSC token signing service that runs on Windows laptop with physical USB token access.

## What This Service Does
- ✅ Signs payloads using USB DSC token via PKCS#11
- ✅ Returns Base64-encoded signed data and CMS signature
- ✅ Provides health check and token status endpoints

## What This Service Does NOT Do
- ❌ Call ERI APIs
- ❌ Have database
- ❌ Have authentication
- ❌ Know about AWS or ERI business logic

## Prerequisites
- Windows laptop
- USB DSC token inserted
- PKCS#11 driver installed (`eps2003csp11v2.dll` in System32)
- Java 17+
- Maven 3.6+

## Configuration
Set environment variables:
```bash
set DSC_TOKEN_PIN=123456789
set DSC_TOKEN_ALIAS=agencykey
set DSC_PKCS11_LIBRARY=C:\Windows\System32\eps2003csp11v2.dll
```

## Build
```bash
mvn clean package
```

## Run
```bash
java -jar target/local-dsc-signer-1.0.0-SNAPSHOT.jar
```

Service starts on port **9090**.

## API Endpoints

### POST /sign
Sign a payload using USB DSC token.

**Request:**
```json
{
  "payload": "CANONICAL_JSON_STRING"
}
```

**Response:**
```json
{
  "success": true,
  "data": "BASE64_SIGNED_DATA",
  "signature": "BASE64_CMS_SIGNATURE",
  "certificate": "BASE64_CERTIFICATE",
  "timestamp": "2024-01-15T10:30:00"
}
```

### GET /health
Check service health.

**Response:**
```json
{
  "status": "UP",
  "service": "Local DSC Signer",
  "tokenAvailable": true,
  "timestamp": "2024-01-15T10:30:00"
}
```

### GET /token/status
Check USB token availability.

**Response:**
```json
{
  "available": true,
  "message": "USB token accessible",
  "timestamp": "2024-01-15T10:30:00"
}
```

## Testing
```bash
# Health check
curl http://localhost:9090/health

# Token status
curl http://localhost:9090/token/status

# Sign test payload
curl -X POST http://localhost:9090/sign \
  -H "Content-Type: application/json" \
  -d '{"payload":"{\"test\":true}"}'
```

## Troubleshooting

### Token Not Found
- Check USB token is inserted
- Verify PKCS#11 driver is installed
- Check driver path in configuration

### PIN Error
- Verify DSC_TOKEN_PIN environment variable
- Check token is not locked

### PKCS#11 Error
- Ensure Java architecture matches DLL (32-bit vs 64-bit)
- Verify driver path is correct
- Check token drivers are installed

## Architecture
This service is part of a hybrid architecture:
- **Local Signer** (this service) → Signs payloads
- **AWS Backend** → Calls this service via HTTP, then calls ERI APIs

## Security
- Private key NEVER leaves USB token
- PIN stored as environment variable only
- No hardcoded credentials
- Minimal attack surface (no database, no auth)
