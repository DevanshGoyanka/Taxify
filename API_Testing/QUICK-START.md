# ERI Tax ERP - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Prerequisites
- ✅ Windows laptop with USB DSC token
- ✅ AWS EC2 instance (13.204.49.125)
- ✅ Java 17+ on both systems
- ✅ Maven 3.6+ on both systems
- ✅ MySQL database on AWS

### Step 1: Build Both Modules

#### Build Local DSC Signer
```bash
cd local-dsc-signer
mvn clean package
```

#### Build AWS Backend
```bash
cd "API TEST"
mvn clean package
```

### Step 2: Start Local DSC Signer (Windows Laptop)

```bash
cd local-dsc-signer

# Set environment variables
set DSC_TOKEN_PIN=123456789
set DSC_TOKEN_ALIAS=agencykey

# Start service
java -jar target/local-dsc-signer-1.0.0-SNAPSHOT.jar
```

**Or use the startup script**:
```bash
start-local-signer.bat
```

**Verify it's running**:
```bash
curl http://localhost:9090/health
```

Expected response:
```json
{
  "status": "UP",
  "service": "Local DSC Signer",
  "tokenAvailable": true
}
```

### Step 3: Start AWS Backend (AWS EC2)

```bash
cd "API TEST"

# Set environment variables
export ERI_PASSWORD=Oracle@123
export DB_PASSWORD=your_db_password
export LOCAL_SIGNER_URL=http://YOUR_LAPTOP_IP:9090

# Start service
java -jar -Dspring.profiles.active=aws target/eri-tax-erp-phase1-1.0.0-SNAPSHOT.jar
```

**Or use the startup script**:
```bash
chmod +x start-aws-backend.sh
./start-aws-backend.sh
```

**Verify it's running**:
```bash
curl http://13.204.49.125:8080/api/health
```

### Step 4: Test the Integration

#### Test Local Signer
```bash
curl -X POST http://localhost:9090/sign \
  -H "Content-Type: application/json" \
  -d '{"payload":"{\"test\":true}"}'
```

#### Test AWS Backend Health
```bash
curl http://13.204.49.125:8080/api/health
```

#### Test Complete ERI Login Flow
```bash
curl -X POST http://13.204.49.125:8080/api/integration/eri/login
```

## 📁 Project Structure

```
.
├── local-dsc-signer/              # Local USB DSC signing service
│   ├── src/main/java/com/taxerp/signer/
│   │   ├── LocalDscSignerApplication.java
│   │   ├── controller/SignerController.java
│   │   └── service/UsbDscSigningService.java
│   ├── pom.xml
│   └── README.md
│
└── API TEST/                      # AWS ERI backend service
    ├── src/main/java/com/taxerp/
    │   ├── TaxErpApplication.java
    │   ├── controller/
    │   │   ├── ERISignedLoginController.java
    │   │   └── HybridIntegrationController.java
    │   ├── service/
    │   │   ├── DSCSignatureService.java (interface)
    │   │   ├── DSCSignatureServiceHttpClient.java
    │   │   └── HybridERIIntegrationService.java
    │   └── integration/
    ├── pom.xml
    └── README-HYBRID-ARCHITECTURE.md
```

## 🔧 Configuration

### Local Signer (application.yml)
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

### AWS Backend (application-aws.yml)
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

## ✅ Success Criteria

Your system is ready when:

- [ ] Local signer health check returns UP
- [ ] Local signer token status shows available
- [ ] AWS backend health check returns UP
- [ ] AWS backend can reach local signer
- [ ] Test signing request succeeds
- [ ] ERI login flow completes successfully

## 🐛 Troubleshooting

### Local Signer Issues

**Problem**: Token not found
```bash
# Check USB token is inserted
# Verify PKCS#11 driver installed
# Check driver path in configuration
```

**Problem**: Service won't start
```bash
# Check port 9090 is not in use
netstat -ano | findstr :9090

# Check Java version
java -version
```

### AWS Backend Issues

**Problem**: Cannot reach local signer
```bash
# Check network connectivity
curl http://YOUR_LAPTOP_IP:9090/health

# Check firewall rules
# Verify LOCAL_SIGNER_URL is correct
```

**Problem**: Database connection failed
```bash
# Check MySQL is running
# Verify credentials
# Check database exists
mysql -u taxerp_user -p taxerp_uat
```

### Integration Issues

**Problem**: ERI login fails
```bash
# Check VPN connection to ITD
# Verify IP whitelisting (24-48hr delay)
# Check ERI credentials
# Review AWS backend logs
```

## 📚 Next Steps

1. **Read Full Documentation**:
   - `local-dsc-signer/README.md` - Local signer details
   - `API TEST/README-HYBRID-ARCHITECTURE.md` - Complete architecture guide

2. **Run Tests**:
   ```bash
   # Test local signer
   cd local-dsc-signer
   mvn test

   # Test AWS backend
   cd "API TEST"
   mvn test
   ```

3. **Monitor Logs**:
   - Local signer: Console output
   - AWS backend: `logs/aws-eri-backend.log`

4. **Production Deployment**:
   - Configure production database
   - Set up proper networking
   - Enable HTTPS
   - Configure monitoring

## 🎯 Key Endpoints

### Local Signer (Port 9090)
- `POST /sign` - Sign payload
- `GET /health` - Health check
- `GET /token/status` - Token status

### AWS Backend (Port 8080)
- `GET /api/health` - Health check
- `POST /api/eri/login-signed` - ERI login with pre-signed payload
- `POST /api/integration/eri/login` - Complete hybrid login flow
- `GET /api/integration/test` - Test integration components

## 💡 Tips

1. **Always start local signer first** - AWS backend needs it
2. **Check health endpoints** - Before running tests
3. **Monitor logs** - For debugging issues
4. **Use environment variables** - Never hardcode credentials
5. **Test components independently** - Before testing integration

## 🆘 Support

If you encounter issues:
1. Check component logs
2. Verify configuration
3. Test each component independently
4. Review troubleshooting guide
5. Check network connectivity

---

**Ready to start?** Follow the steps above and you'll be running in minutes! 🚀
