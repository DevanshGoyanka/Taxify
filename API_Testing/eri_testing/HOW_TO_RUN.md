# 🚀 How to Run the Application

## Prerequisites Check

Before running, ensure you have:
- ✅ USB token (HYP2003) inserted
- ✅ Java installed (check: `java -version`)
- ✅ All files in `C:\Users\Devansh\Desktop\eri_testing\`
- ✅ Your token PIN ready

---

## Method 1: Using Java Directly (Recommended)

### Step 1: Open Command Prompt
1. Press `Win + R`
2. Type `cmd` and press Enter
3. Navigate to project folder:
   ```cmd
   cd C:\Users\Devansh\Desktop\eri_testing
   ```

### Step 2: Run the Signer
Copy and paste this command (replace `YOUR_PIN` with your actual PIN):

```cmd
java --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner "test" "C:\Windows\System32\eps2003csp11v2.dll" "YOUR_PIN"
```

### Step 3: Check Output
You should see:
```
✓ PKCS#11 Provider created successfully
✓ Keystore loaded successfully
✓ Certificate chain length: 4
✓ CMS signature generated!
```

Followed by a long Base64 signature starting with `MIAGCSqGSIb3...`

---

## Method 2: Using Python (Easier)

### Step 1: Update PIN in Python File
1. Open `cms_bridge.py` in a text editor
2. Find line 11: `TOKEN_PIN = "123456789"`
3. Change to your actual PIN
4. Save the file

### Step 2: Run Python Script
```cmd
cd C:\Users\Devansh\Desktop\eri_testing
python cms_bridge.py
```

### Step 3: Check Output
You should see:
```
✓✓✓ SUCCESS! CMS SIGNATURE GENERATED ✓✓✓
Signature format: CMS/PKCS#7 (ITD compliant)
Signature length: 8984 characters
```

Followed by the Base64 signature.

---

## Method 3: Sign Your Own Data

### Using Java
Replace `"test"` with your data:

```cmd
java --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner "Your data here" "C:\Windows\System32\eps2003csp11v2.dll" "YOUR_PIN"
```

### Using Python
```python
from cms_bridge import sign_with_cms_token

# Sign your data
data = "Transaction ID: 12345"
signature = sign_with_cms_token(data)

print(f"Signature: {signature}")
```

---

## 📝 Complete Example

### Example 1: Sign a Simple Message

**Command:**
```cmd
cd C:\Users\Devansh\Desktop\eri_testing

java --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner "Hello World" "C:\Windows\System32\eps2003csp11v2.dll" "123456789"
```

**Expected Output:**
```
======================================================================
CMS Token Signer - ITD Compliant
======================================================================
PKCS#11 Library: C:\Windows\System32\eps2003csp11v2.dll
Data length: 11 chars
...
✓ CMS signature generated!
  Signature length: 8984 characters

MIAGCSqGSIb3DQEHAqCAMIACAQExDTALBglghkgBZQMEAgEwCwYJKoZIhvcNAQcBoIAwggcC...
```

### Example 2: Sign JSON Data

**Command:**
```cmd
java --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner "{\"name\":\"John\",\"amount\":1000}" "C:\Windows\System32\eps2003csp11v2.dll" "123456789"
```

---

## 🔧 Troubleshooting

### Error: "Java not found"
**Solution:**
1. Install Java JDK from https://www.oracle.com/java/technologies/downloads/
2. Or check if Java is in PATH: `java -version`

### Error: "Token not detected"
**Solution:**
1. Check USB token is inserted
2. Try removing and reinserting token
3. Check Device Manager for smart card reader

### Error: "Wrong PIN"
**Solution:**
1. Verify your PIN is correct
2. Token locks after 3 wrong attempts
3. Contact token issuer if locked

### Error: "Class not found"
**Solution:**
Recompile the Java file:
```cmd
javac --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner.java
```

---

## 💡 Quick Tips

### Tip 1: Create a Batch File
Create `sign.bat` with:
```batch
@echo off
java --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner %1 "C:\Windows\System32\eps2003csp11v2.dll" "YOUR_PIN"
```

Then run: `sign.bat "your data"`

### Tip 2: Save Output to File
```cmd
java ... CMSTokenSigner "test" ... > signature.txt
```

### Tip 3: Use in Scripts
```python
import subprocess

def sign_data(data):
    cmd = [
        'java',
        '--add-opens', 'jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED',
        '-cp', '.;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar',
        'CMSTokenSigner',
        data,
        'C:\\Windows\\System32\\eps2003csp11v2.dll',
        'YOUR_PIN'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()
```

---

## 📋 Command Breakdown

Let's understand the command:

```cmd
java                                                    # Run Java
--add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED  # Allow PKCS11 access
-cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar"  # Classpath
CMSTokenSigner                                          # Main class
"test"                                                  # Data to sign
"C:\Windows\System32\eps2003csp11v2.dll"               # Token driver
"YOUR_PIN"                                              # Token PIN
```

---

## ✅ Success Indicators

You know it's working when you see:
- ✅ `✓ PKCS#11 Provider created successfully`
- ✅ `✓ Keystore loaded successfully`
- ✅ `✓ Found key entry`
- ✅ `✓ Certificate chain length: 4`
- ✅ `✓ CMS signature generated!`
- ✅ Long Base64 string output

---

## 🎯 Next Steps

After successful run:
1. Copy the signature output
2. Use it in your ERI API calls
3. Integrate into your application
4. See `SUCCESS_SUMMARY.md` for integration examples

---

**Need more help? Check:**
- `QUICK_START.md` - Quick reference
- `SUCCESS_SUMMARY.md` - Detailed guide
- `README.md` - Complete documentation
