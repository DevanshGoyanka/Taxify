# 📝 Step-by-Step Guide (Beginner Friendly)

## 🎯 Goal
Generate a digital signature using your USB token

---

## ⚡ Quick 3-Step Process

### STEP 1: Insert USB Token
- Plug in your HYP2003 USB token
- Wait for Windows to recognize it (LED may blink)

### STEP 2: Open Command Prompt
- Press `Windows Key + R`
- Type: `cmd`
- Press Enter
- Type: `cd C:\Users\Devansh\Desktop\eri_testing`
- Press Enter

### STEP 3: Run This Command
Copy this entire command and paste it in Command Prompt:

```cmd
java --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner "test" "C:\Windows\System32\eps2003csp11v2.dll" "123456789"
```

**Important:** Replace `123456789` with your actual token PIN!

---

## 📺 What You'll See

### While Running:
```
======================================================================
CMS Token Signer - ITD Compliant
======================================================================
PKCS#11 Library: C:\Windows\System32\eps2003csp11v2.dll
Data length: 4 chars
Detected Java version: 25.0.1
✓ DLL file found
✓ Config file created
✓ Loading PKCS#11 provider for Java 9+...
✓ PKCS#11 Provider created successfully
✓ Provider registered: SunPKCS11-SmartCard
✓ KeyStore instance created
✓ Loading keystore from USB token...
✓ Keystore loaded successfully
✓ Searching for certificate with private key...
✓ Found key entry: 171965131758541427235
✓ Using certificate alias: 171965131758541427235
✓ Certificate chain length: 4
  - Subject: CN=SUNIT RAMASHANKAR GOYANKA...
✓ Private key accessible (stays in token)
✓ Creating CMS signature...
✓ CMS signature generated!
  Signature length: 8984 characters
```

### The Signature:
```
MIAGCSqGSIb3DQEHAqCAMIACAQExDTALBglghkgBZQMEAgEwCwYJKoZIhvcNAQcBoIAwggcCMIIF6qAD...
(continues for many lines)
```

### Success Message:
```
✓✓✓ SUCCESS ✓✓✓
```

---

## ✅ How to Know It Worked

Look for these signs:
1. ✅ You see green checkmarks (✓)
2. ✅ You see "Certificate chain length: 4"
3. ✅ You see a long string starting with "MIAGCSqGSIb3..."
4. ✅ You see "✓✓✓ SUCCESS ✓✓✓"

---

## ❌ Common Problems & Solutions

### Problem 1: "Java not found"
**What it means:** Java is not installed
**Solution:**
1. Download Java from: https://www.oracle.com/java/technologies/downloads/
2. Install it
3. Try again

### Problem 2: "Token not detected"
**What it means:** USB token not recognized
**Solution:**
1. Remove USB token
2. Wait 5 seconds
3. Insert it again
4. Try again

### Problem 3: "Wrong PIN"
**What it means:** PIN is incorrect
**Solution:**
1. Check your PIN
2. Update the command with correct PIN
3. Try again
**Warning:** Token locks after 3 wrong attempts!

### Problem 4: "Class not found"
**What it means:** Java file not compiled
**Solution:**
Run this first:
```cmd
javac --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner.java
```
Then try the main command again.

---

## 🎓 Understanding the Command

Don't worry about understanding everything, but here's what each part does:

| Part | What It Does |
|------|--------------|
| `java` | Runs Java program |
| `--add-opens ...` | Allows access to USB token |
| `-cp "..."` | Tells Java where libraries are |
| `CMSTokenSigner` | Your signing program |
| `"test"` | Data to sign (change this to your data) |
| `"C:\Windows\System32\eps2003csp11v2.dll"` | USB token driver |
| `"123456789"` | Your PIN (CHANGE THIS!) |

---

## 🔄 To Sign Different Data

Just change the `"test"` part:

**Example 1: Sign a message**
```cmd
java ... CMSTokenSigner "Hello World" ... "YOUR_PIN"
```

**Example 2: Sign a transaction**
```cmd
java ... CMSTokenSigner "Transaction-12345" ... "YOUR_PIN"
```

**Example 3: Sign JSON data**
```cmd
java ... CMSTokenSigner "{\"id\":123,\"amount\":1000}" ... "YOUR_PIN"
```

---

## 💾 Save Signature to File

Add `> signature.txt` at the end:

```cmd
java --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner "test" "C:\Windows\System32\eps2003csp11v2.dll" "YOUR_PIN" > signature.txt
```

The signature will be saved in `signature.txt` file.

---

## 🎯 What to Do with the Signature

The signature you get can be used for:
- ✅ ERI (e-Return Intermediary) submissions
- ✅ Income Tax filing
- ✅ GST portal
- ✅ Any system requiring digital signatures

**Copy the signature** (the long string starting with `MIAGCSqGSIb3...`) and use it in your API calls or forms.

---

## 📞 Still Need Help?

1. Check `HOW_TO_RUN.md` for detailed troubleshooting
2. Check `SUCCESS_SUMMARY.md` for complete guide
3. Make sure:
   - USB token is inserted
   - PIN is correct
   - All files are in the folder
   - Java is installed

---

## ✨ Pro Tip: Create a Shortcut

Create a file called `sign.bat` with this content:

```batch
@echo off
echo.
echo ========================================
echo Digital Signature Generator
echo ========================================
echo.
set /p DATA="Enter data to sign: "
echo.
echo Generating signature...
echo.
java --add-opens jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED -cp ".;bcprov-jdk18on-1.82.jar;bcpkix-jdk18on-1.82.jar;bcutil-jdk18on-1.82.jar" CMSTokenSigner "%DATA%" "C:\Windows\System32\eps2003csp11v2.dll" "YOUR_PIN"
echo.
pause
```

Then just double-click `sign.bat` to run!

---

**That's it! You're ready to generate digital signatures!** 🎉
