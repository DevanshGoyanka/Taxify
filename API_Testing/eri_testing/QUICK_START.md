# Quick Start Guide - ERI CMS Signature

## ✅ Your System is Ready!

Everything is configured and working. Here's how to use it:

## 🚀 Quick Test

Run this command to test:
```cmd
java --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner "test" "C:\Windows\System32\eps2003csp11v2.dll" "123456789"
```

Replace `"123456789"` with your actual PIN.

## 📝 Sign Your Data

### Method 1: Command Line
```cmd
java --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner "YOUR_DATA_HERE" "C:\Windows\System32\eps2003csp11v2.dll" "YOUR_PIN"
```

### Method 2: Python
```python
python cms_bridge.py
```

Or in your code:
```python
from cms_bridge import sign_with_cms_token

signature = sign_with_cms_token("your data to sign")
print(signature)
```

## 📋 What You Get

A Base64-encoded CMS/PKCS#7 signature like:
```
MIAGCSqGSIb3DQEHAqCAMIACAQExDTALBglghkgBZQMEAgEwCwYJKoZIhvcNAQcBoIAwggcCMIIF6qAD...
```

This signature:
- ✅ Is ITD compliant
- ✅ Works with ERI APIs
- ✅ Includes your certificate chain
- ✅ Can be verified by anyone

## 🔧 Configuration

Your working setup:
- **DLL**: `C:\Windows\System32\eps2003csp11v2.dll`
- **Certificate**: SUNIT RAMASHANKAR GOYANKA
- **Chain**: 4 certificates (to CCA India 2022)
- **Algorithm**: SHA256withRSA

## 📖 For ERI Integration

Use the signature in your ERI API calls:
```json
{
  "data": "your data",
  "signature": "MIAGCSqGSIb3DQEHAqCAMIACAQExDTAL...",
  "certificate": "base64_encoded_cert"
}
```

## 🆘 Need Help?

See `SUCCESS_SUMMARY.md` for complete details and troubleshooting.

## 🎉 You're All Set!

Your digital signature system is production-ready!
