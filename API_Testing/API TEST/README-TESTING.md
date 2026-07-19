# ERI UAT Hybrid Architecture - Setup and Testing Guide

## 🏗️ **ARCHITECTURE OVERVIEW**

This system implements a **hybrid architecture** for ERI (e-Return Intermediary) integration:

- **Local Windows Laptop**: USB DSC signing service (Port 9090)
- **AWS EC2 (13.204.49.125)**: ERI API backend (Port 8080)
- **ITD ERI API**: UAT environment (whitelisted IP only)

### Why Hybrid Architecture?
1. **USB DSC Token**: Physically on Windows laptop, cannot be on AWS
2. **IP Whitelisting**: Only AWS IP (13.204.49.125) is whitelisted by ITD
3. **Security**: Private key never leaves USB token

## 📋 **PREREQUISITES**

### Hardware & Software
- ✅ Windows laptop with USB DSC token
- ✅ AWS EC2 instance (13.204.49.125) running
- ✅ Java 17+ installed on both systems
- ✅ Maven 3.6+ for building
- ✅ MySQL database for audit logging

### Network & Access
- ✅ VPN access to ITD network
- ✅ AWS IP (13.204.49.125) whitelisted by ITD
- ✅ Network connectivity between laptop and AWS

### Credentials & Configuration
- ✅ ERI credentials (ERIP013181/Oracle@123)
- ✅ DSC token PIN (123456789)
- ✅ Database credentials configured

## 🚀 **SETUP INSTRUCTIONS**

### Step 1: Local DSC Signing Service Setup

1. **Insert USB DSC Token**
   ```bash
   # Verify token is recognized by Windows
   # Check Device Manager for smart card readers
   ```

2. **Set Environment Variables**
   ```bash
   # Windows Command Prompt
   set DSC_PASSWORD=123456789
   set DSC_ALIAS=agencykey
   
   # PowerShell
   $env:DSC_PASSWORD="123456789"
   $env:DSC_ALIAS="agencykey"
   
   # Linux/Mac (if testing)
   export DSC_PASSWORD=123456789
   export DSC_ALIAS=agencykey
   ```

3. **Build and Start Local Signer**
   ```bash
   cd "API TEST"
   
   # Build project
   mvn clean package -DskipTests
   
   # Start local DSC signing service
   java -jar -Dspring.profiles.active=local target/eri-tax-erp-phase1-1.0.0-SNAPSHOT.jar
   ```

4. **Verify Local Signer**
   ```bash
   # Health check
   curl http://localhost:9090/api/health
   
   # Token status
   curl http://localhost:9090/api/token/status
   ```

### Step 2: AWS Backend Setup

1. **Connect to AWS EC2**
   ```bash
   ssh -i your-key.pem ubuntu@13.204.49.125
   ```

2. **Set Environment Variables on AWS**
   ```bash
   # Create environment file
   sudo nano /etc/environment
   
   # Add these variables:
   ERI_CLIENT_ID=4fea04621c7b5660dbb12b959a29b0ee
   ERI_CLIENT_SECRET=e754ceb48732c4e197658f76bcc69037
   ERI_USERNAME=ERIP013181
   ERI_PASSWORD=Oracle@123
   ERI_USER_ID=ERIP011535
   DB_USERNAME=taxerp_user
   DB_PASSWORD=your_db_password
   ```

3. **Start AWS Backend**
   ```bash
   cd /home/ubuntu/tax-erp-complete/java-backend/
   
   # Start with AWS profile
   java -jar -Dspring.profiles.active=aws target/eri-tax-erp-phase1-1.0.0-SNAPSHOT.jar
   ```

4. **Verify AWS Backend**
   ```bash
   # Health check
   curl http://13.204.49.125:8080/api/health
   ```

### Step 3: Database Setup

1. **Create Database**
   ```sql
   CREATE DATABASE taxerp_uat;
   CREATE USER 'taxerp_user'@'%' IDENTIFIED BY 'your_db_password';
   GRANT ALL PRIVILEGES ON taxerp_uat.* TO 'taxerp_user'@'%';
   FLUSH PRIVILEGES;
   ```

2. **Verify Database Connection**
   ```bash
   # Check from AWS backend logs
   tail -f logs/aws-eri-backend.log
   ```

## 🧪 **TESTING PROCEDURES**

### Phase 1: Component Testing

#### Test Local DSC Signer
```bash
cd "API TEST"
chmod +x test-local-signer.sh
./test-local-signer.sh
```

**Expected Results:**
- ✅ Health check: HTTP 200
- ✅ Token status: available=true
- ✅ Simple signing: success=true
- ✅ ERI payload signing: success=true

#### Test AWS Backend
```bash
chmod +x test-aws-backend.sh
./test-aws-backend.sh
```

**Expected Results:**
- ✅ AWS health check: HTTP 200
- ✅ Signed payload acceptance: success=true
- ✅ ERI login: sessionId returned
- ✅ Session management: working

### Phase 2: End-to-End Testing

```bash
chmod +x test-end-to-end.sh
./test-end-to-end.sh
```

**Complete Flow Test:**
1. Generate canonical JSON payload
2. Sign with local DSC service
3. Send to AWS backend
4. AWS calls ITD ERI API
5. Return session ID
6. Session management
7. Logout

### Phase 3: Production Readiness

#### Performance Testing
```bash
# Run multiple iterations
for i in {1..10}; do
  echo "Test iteration $i"
  ./test-end-to-end.sh
  sleep 5
done
```

#### Load Testing
```bash
# Concurrent requests (use Apache Bench or similar)
ab -n 100 -c 10 -H "Content-Type: application/json" \
   -p test-payload.json \
   http://localhost:9090/api/sign
```

## 🔧 **TROUBLESHOOTING GUIDE**

### Local DSC Signer Issues

#### Token Not Detected
```
Error: "USB token not detected"
```
**Solutions:**
1. Check USB token insertion
2. Verify drivers installed: `eps2003csp11v2.dll` in System32
3. Check Device Manager for smart card readers
4. Try different USB port
5. Restart token service

#### PIN Errors
```
Error: "Incorrect PIN" or "Token locked"
```
**Solutions:**
1. Verify PIN: `DSC_PASSWORD=123456789`
2. Check if token is locked (too many wrong attempts)
3. Contact token provider for unlock
4. Try token on different system

#### PKCS#11 Errors
```
Error: "PKCS#11 provider failed"
```
**Solutions:**
1. Check Java architecture (32-bit vs 64-bit)
2. Verify DLL path: `C:\Windows\System32\eps2003csp11v2.dll`
3. Check BouncyCastle JARs in classpath
4. Review PKCS#11 configuration

#### Certificate Issues
```
Error: "Certificate not found" or "No private key"
```
**Solutions:**
1. Check certificate alias: `DSC_ALIAS=agencykey`
2. List token contents: Use token management software
3. Verify certificate validity
4. Check certificate chain

### AWS Backend Issues

#### Connection Refused
```
Error: "Connection refused" to AWS backend
```
**Solutions:**
1. Check AWS EC2 service status
2. Verify security groups (port 8080 open)
3. Check VPN connection
4. Verify AWS backend is running

#### ERI API Errors

#### Unauthorized (401)
```
Error: "Unauthorized" from ERI API
```
**Solutions:**
1. Check ERI credentials configuration
2. Verify client-id and client-secret
3. Check username/password
4. Confirm credentials are for UAT environment

#### IP Not Whitelisted (403)
```
Error: "Forbidden" or "IP not whitelisted"
```
**Solutions:**
1. Confirm AWS IP: 13.204.49.125
2. Wait 24-48 hours after whitelisting request
3. Contact ITD support for whitelisting status
4. Verify VPN connection

#### Connection Timeout
```
Error: "Connection timeout" to ERI API
```
**Solutions:**
1. Check VPN connection to ITD network
2. Verify ERI API URL: `https://uatocpservices.incometax.gov.in/v1`
3. Check network firewall rules
4. Try from different network

### Database Issues

#### Connection Failed
```
Error: "Database connection failed"
```
**Solutions:**
1. Check MySQL service status
2. Verify database credentials
3. Check network connectivity
4. Review database logs

#### Schema Issues
```
Error: "Table doesn't exist"
```
**Solutions:**
1. Check Hibernate DDL setting: `ddl-auto: update`
2. Verify database permissions
3. Run schema creation manually
4. Check entity mappings

### Integration Issues

#### Local Signer Unavailable
```
Error: "Local signer unavailable"
```
**Solutions:**
1. Check if local service is running on port 9090
2. Verify network connectivity
3. Check firewall rules
4. Review local signer logs

#### AWS Backend Unavailable
```
Error: "AWS backend unavailable"
```
**Solutions:**
1. Check AWS EC2 instance status
2. Verify service is running on port 8080
3. Check security groups
4. Review AWS backend logs

## 📊 **MONITORING AND LOGGING**

### Log Files
- **Local Signer**: `logs/local-dsc-signer.log`
- **AWS Backend**: `logs/aws-eri-backend.log`
- **Integration**: Application logs with correlation IDs

### Key Metrics to Monitor
1. **Signing Performance**: < 5 seconds per operation
2. **ERI API Response Time**: < 30 seconds
3. **Success Rate**: > 95%
4. **Error Patterns**: Monitor for recurring issues

### Audit Trail
All operations are logged to database with:
- Correlation ID for tracing
- Request/response payloads (masked)
- Timestamps and response times
- Success/failure status

## 🔒 **SECURITY CONSIDERATIONS**

### Data Protection
- Private keys never leave USB token
- PINs stored as environment variables only
- Sensitive data masked in logs
- HTTPS for production (HTTP for UAT)

### Access Control
- USB token physical security
- AWS EC2 security groups
- Database access restrictions
- VPN-only access to ITD network

### Compliance
- ITD ERI specification compliance
- Audit logging for all operations
- Data retention policies
- Error handling and reporting

## 🎯 **SUCCESS CRITERIA**

### System Ready When:
- ✅ Local DSC signer: Health check green
- ✅ AWS backend: Health check green
- ✅ DSC signing: Works without errors
- ✅ ERI login: Returns session ID
- ✅ Session management: Working
- ✅ Audit logs: Complete and accurate
- ✅ Error handling: Graceful
- ✅ Performance: Acceptable response times

### Production Deployment Checklist:
- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] Security review completed
- [ ] Monitoring configured
- [ ] Backup procedures tested
- [ ] Documentation updated
- [ ] Team training completed

## 📞 **SUPPORT CONTACTS**

### Technical Issues
- **DSC Token**: Token provider support
- **ERI API**: ITD helpdesk
- **AWS Infrastructure**: AWS support
- **Application**: Development team

### Emergency Procedures
1. Check system status dashboard
2. Review recent logs for errors
3. Verify network connectivity
4. Contact appropriate support team
5. Document issue for post-mortem

---

**Last Updated**: January 2024  
**Version**: 1.0.0  
**Environment**: UAT