# Test Keystore Creation Instructions

This document provides instructions for creating a test keystore for integration testing.

## Creating Test Keystore

To create a test keystore for testing purposes, run the following commands:

```bash
# Generate a test private key and self-signed certificate
keytool -genkeypair -alias test-cert -keyalg RSA -keysize 2048 -validity 365 \
  -keystore src/test/resources/test-keystore.p12 -storetype PKCS12 \
  -storepass test123 -keypass test123 \
  -dname "CN=Test Certificate, OU=Test Unit, O=Test Organization, L=Test City, ST=Test State, C=IN"
```

## Alternative: Create with OpenSSL

```bash
# Create private key
openssl genrsa -out test-key.pem 2048

# Create self-signed certificate
openssl req -new -x509 -key test-key.pem -out test-cert.pem -days 365 \
  -subj "/C=IN/ST=Test State/L=Test City/O=Test Organization/OU=Test Unit/CN=Test Certificate"

# Create PKCS12 keystore
openssl pkcs12 -export -in test-cert.pem -inkey test-key.pem \
  -out src/test/resources/test-keystore.p12 -name test-cert -password pass:test123
```

## Test Keystore Properties

- **File**: `src/test/resources/test-keystore.p12`
- **Type**: PKCS12
- **Password**: `test123`
- **Alias**: `test-cert`
- **Key Algorithm**: RSA 2048-bit
- **Validity**: 365 days from creation

## Note

This keystore is for testing purposes only and should not be used in production environments.
The certificate is self-signed and not issued by a trusted Certificate Authority.

## Verification

To verify the keystore was created correctly:

```bash
keytool -list -keystore src/test/resources/test-keystore.p12 -storetype PKCS12 -storepass test123
```

This should show the test certificate with alias `test-cert`.