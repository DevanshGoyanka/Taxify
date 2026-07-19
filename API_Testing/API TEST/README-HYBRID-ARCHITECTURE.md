# ERI Tax ERP - Hybrid Architecture Guide

## 🏗️ Architecture Overview

This system uses a **hybrid architecture** to handle ERI integration:

```
┌─────────────────────┐         ┌──────────────────────┐         ┌─────────────────┐
│  Windows Laptop     │         │  AWS EC2             │         │  ITD ERI API    │
│  (Local DSC Signer) │         │  (ERI Backend)       │         │  (UAT)          │
│                     │         │                      │         │                 │
│  Port: 9090         │◄───────►│  Port: 8080          │────────►│  HTTPS          │
│  USB DSC Token      │  HTTP   │  IP: 13.204.49.125   │  HTTPS  │  Whitelisted IP │
└─────────────────────┘         └──────────────────────┘         └─────────────────┘
```

## Why Hybrid?

1. **USB DSC Token**: Physically on Windows laptop, cannot be on AWS
2. **IP Whitelisting**: Only AWS IP (13.204.49.125) is whitelisted by ITD
3. **Security**: Private key never leaves USB token

## Components

### 1. Local DSC Signer (Windows Laptop)
**Location**: `local-dsc-signer/`
**Purpose**: USB DSC token signing ONLY
**Port**: 9090

**Responsibilities**:
- Sign payloads using USB DSC token
- PKCS#11 integration
- Return signed data and signature

**Does NOT**:
- Call ERI APIs
- Have database
- Have authentication
- Know about ERI business logic

### 2. AWS ERI Backend (AWS EC2)
**Location**: `API TEST/`
**Purpose**: ERI API execution ONLY
**Port**: 8080
**IP**: 13.204.49.125 (whitelisted)

**Responsibilities**:
- Generate ERI payloads
- Call local signer via HTTP
- Call ITD ERI APIs from whitelisted IP
- Audit logging
- Retry logic
- Session management

**Does NOT**:
- Access USB DSC token
- Perform PKCS#11 operations
- Have BouncyCastle signing logic

## Complete Flow

### ERI Login Flow
```
1. Client → AWS Backend: Login request
2. AWS Backend: Generate canonical JSON payload
3. AWS Backend → Local Signer: HTTP POST /sign with payload
4. Local Signer: Sign using USB DSC token
5. Local Signer → AWS Backend: Return signed data + signature
6. AWS Backend: Construct ITD ERI request
7. AWS Backend → ITD ERI: POST /auth/login (from whitelisted IP)
8. ITD ERI → AWS Backend: Return session ID
9. AWS Backend → Client: Return session ID
```

## Setup Instructions

### Step 1: Setup Local DSC Signer (Windows Laptop)

```bash
cd local-dsc-signer

# Set environment variables
set DSC_TOKEN_PIN=123456789
set DSC_TOKEN_ALIAS=agencykey

# Build
mvn clean package

# Run
java -jar target/local-dsc-signer-1.0.0-SNAPSHOT.jar
```

**Verify**:
```bash
curl http://localhost:9090/health
curl http://localhost:9090/token/status
```

### Step 2: Setup AWS ERI Backend (AWS EC2)

```bash
cd "API TEST"

# Set environment variables
export ERI_CLIENT_ID=4fea04621c7b5660dbb12b959a29b0ee
export ERI_CLIENT_SECRET=e754ceb48732c4e197658f76bcc69037
export ERI_USERNAME=ERIP013181
export ERI_PASSWORD=Oracle@123
export ERI_USER_ID=ERIP011535
export DB_PASSWORD=your_db_password
export LOCAL_SIGNER_URL=http://YOUR_LAPTOP_IP:9090

# Build
mvn clean package

# Run
java -jar -Dspring.profiles.active=aws target/eri-tax-erp-phase1-1.0.0-SNAPSHOT.jar
```

**Verify**:
```bash
curl http://13.204.49.125:8080/api/health
```

## Testing

### Test Local Signer
```bash
curl -X POST http://localhost:9090/sign \
  -H "Content-Type: application/json" \
  -d '{"payload":"{\"test\":true,\"timestamp\":\"2024-01-15T10:30:00\"}"}'
```

### Test AWS Backend
```bash
curl http://13.204.49.125:8080/api/health
```

### Test End-to-End ERI Login
```bash
curl -X POST http://13.204.49.125:8080/api/eri/login-signed \
  -H "Content-Type: application/json" \
  -d '{
    "data": "BASE64_DATA",
    "signature": "BASE64_SIGNATURE",
    "eriUserId": "ERIP011535"
  }'
```

## Configuration

### Local Signer Configuration
File: `local-dsc-signer/src/main/resources/application.yml`

```yaml
server:
  port: 9090

dsc:
  pkcs11:
    library: C:\\Windows\\System32\\eps2003csp11v2.dll
  token:
    pin: ${DSC_TOKEN_PIN}
    alias: ${DSC_TOKEN_ALIAS}
```

### AWS Backend Configuration
File: `API TEST/src/main/resources/application-aws.yml`

```yaml
server:
  port: 8080

dsc:
  local-signer:
    url: ${LOCAL_SIGNER_URL:http://localhost:9090}

eri:
  base-url: https://uatocpservices.incometax.gov.in/v1
  auth:
    client-id: ${ERI_CLIENT_ID}
    client-secret: ${ERI_CLIENT_SECRET}
```

## Network Requirements

### Local Signer
- Must be accessible from AWS EC2 on port 9090
- Firewall rules must allow incoming HTTP on 9090
- Can use VPN or SSH tunnel if needed

### AWS Backend
- Must be accessible on port 8080
- Must have outbound HTTPS access to ITD ERI
- IP 13.204.49.125 must be whitelisted by ITD

## Security Considerations

### Local Signer
- Private key NEVER leaves USB token
- PIN stored as environment variable only
- No database = no data breach risk
- Minimal attack surface

### AWS Backend
- No USB token access = no key exposure
- All ERI calls from whitelisted IP only
- Comprehensive audit logging
- Encrypted communication

## Troubleshooting

### Local Signer Issues
**Problem**: Token not found
**Solution**: Check USB token insertion and PKCS#11 drivers

**Problem**: PIN error
**Solution**: Verify DSC_TOKEN_PIN environment variable

**Problem**: PKCS#11 error
**Solution**: Check Java architecture matches DLL (32-bit vs 64-bit)

### AWS Backend Issues
**Problem**: Cannot reach local signer
**Solution**: Check network connectivity and firewall rules

**Problem**: ERI API unauthorized
**Solution**: Verify ERI credentials and IP whitelisting

**Problem**: Connection timeout
**Solution**: Check VPN connection to ITD network

### Integration Issues
**Problem**: Signing works but ERI fails
**Solution**: Check AWS IP whitelisting status (24-48hr delay)

**Problem**: ERI works but signing fails
**Solution**: Check local signer service and USB token

## Deployment Checklist

### Local Signer
- [ ] USB DSC token inserted
- [ ] PKCS#11 drivers installed
- [ ] Environment variables set
- [ ] Service running on port 9090
- [ ] Health check returns UP
- [ ] Token status returns available

### AWS Backend
- [ ] Database configured and accessible
- [ ] Environment variables set
- [ ] Service running on port 8080
- [ ] Health check returns UP
- [ ] Can reach local signer
- [ ] VPN connected to ITD network
- [ ] IP whitelisting confirmed

## Success Criteria

✅ Local signer compiles independently
✅ AWS backend compiles independently
✅ Local signer can sign payloads
✅ AWS backend can call local signer
✅ AWS backend can call ERI APIs
✅ Complete login flow succeeds
✅ Session ID returned from ITD
✅ Audit logs complete
✅ No circular dependencies
✅ Clear separation of concerns

## Architecture Benefits

1. **Security**: Private key never leaves USB token
2. **Compliance**: All ERI calls from whitelisted IP
3. **Flexibility**: Can run local signer anywhere
4. **Scalability**: AWS backend can scale independently
5. **Maintainability**: Clear separation of concerns
6. **Testability**: Each component testable independently

## Support

For issues:
1. Check component logs
2. Verify network connectivity
3. Test each component independently
4. Check configuration
5. Review troubleshooting guide

---

**Last Updated**: January 2024
**Version**: 1.0.0
**Environment**: UAT
