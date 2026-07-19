"""
CMS Bridge - Python wrapper for Java CMS signing
Calls Java to generate ITD-compliant CMS signatures
"""

import subprocess
import os
import sys

# ========================================
# CONFIGURATION - UPDATE THESE VALUES
# ========================================
PKCS11_DLL_PATH = "C:\\Windows\\System32\\eps2003csp11v2.dll"
TOKEN_PIN = "123456789"  # CHANGE THIS TO YOUR ACTUAL PIN!!!

# Java files
JAVA_CLASS = "CMSTokenSigner"
BC_PROV = "bcprov-jdk18on-1.82.jar"
BC_PKIX = "bcpkix-jdk18on-1.82.jar"
BC_UTIL = "bcutil-jdk18on-1.82.jar"


def check_setup():
    """Check if all required files exist"""
    print("\n" + "=" * 70)
    print("Checking setup...")
    print("=" * 70)
    
    errors = []
    
    # Check Java
    try:
        result = subprocess.run(['java', '-version'], 
                              capture_output=True, 
                              text=True,
                              timeout=5)
        version = result.stderr.split('\n')[0]
        print(f"✓ Java: {version}")
    except:
        errors.append("Java not found. Install Java JDK.")
        print("✗ Java not found")
    
    # Check BouncyCastle JARs
    if os.path.exists(BC_PROV):
        print(f"✓ Found: {BC_PROV}")
    else:
        errors.append(f"Missing: {BC_PROV}")
        print(f"✗ Missing: {BC_PROV}")
    
    if os.path.exists(BC_PKIX):
        print(f"✓ Found: {BC_PKIX}")
    else:
        errors.append(f"Missing: {BC_PKIX}")
        print(f"✗ Missing: {BC_PKIX}")
    
    if os.path.exists(BC_UTIL):
        print(f"✓ Found: {BC_UTIL}")
    else:
        errors.append(f"Missing: {BC_UTIL}")
        print(f"✗ Missing: {BC_UTIL}")
    
    # Check Java class
    if os.path.exists(f"{JAVA_CLASS}.class"):
        print(f"✓ Found: {JAVA_CLASS}.class")
    else:
        errors.append(f"Not compiled: {JAVA_CLASS}.java")
        print(f"✗ Not compiled: {JAVA_CLASS}.class")
        print(f"   Run: javac -cp \"{BC_PROV};{BC_PKIX}\" {JAVA_CLASS}.java")
    
    # Check token driver
    if os.path.exists(PKCS11_DLL_PATH):
        print(f"✓ Found: {PKCS11_DLL_PATH}")
    else:
        errors.append(f"Token driver not found: {PKCS11_DLL_PATH}")
        print(f"✗ Not found: {PKCS11_DLL_PATH}")
    
    print("=" * 70)
    
    if errors:
        print("\n❌ Setup incomplete. Fix these issues:")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}")
        return False
    else:
        print("\n✓ All checks passed! Ready to sign.")
        return True


def sign_with_cms_token(data):
    """
    Generate CMS signature using USB token via Java
    
    Args:
        data (str or bytes): Data to sign
        
    Returns:
        str: Base64-encoded CMS signature
    """
    
    # Convert bytes to string
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    
    # Build classpath
    if sys.platform == 'win32':
        classpath = f".;{BC_PROV};{BC_PKIX};{BC_UTIL}"
    else:
        classpath = f".:{BC_PROV}:{BC_PKIX}:{BC_UTIL}"
    
    # Build command
    cmd = [
        'java',
        '--add-opens', 'jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED',
        '-cp', classpath,
        JAVA_CLASS,
        data,
        PKCS11_DLL_PATH,
        TOKEN_PIN
    ]
    
    print(f"\n🔐 Generating CMS signature...")
    print(f"Data length: {len(data)} characters")
    
    try:
        # Run Java process
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Show debug output from Java
        if result.stderr:
            print("\nJava output:")
            print(result.stderr)
        
        # Check for errors
        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else "Unknown error"
            raise Exception(f"Java signing failed:\n{error_msg}")
        
        # Get signature from stdout
        signature = result.stdout.strip()
        
        if not signature:
            raise Exception("No signature generated (empty output)")
        
        print(f"\n✓ CMS signature generated!")
        print(f"  Length: {len(signature)} characters")
        print(f"  First 80 chars: {signature[:80]}...")
        
        return signature
        
    except subprocess.TimeoutExpired:
        raise Exception("Signing timeout (>60s). Check if token is inserted.")
    except FileNotFoundError:
        raise Exception("Java not found in PATH")
    except Exception as e:
        raise Exception(f"CMS signing failed: {e}")


def test_signature():
    """Test CMS signature generation"""
    print("\n" + "=" * 70)
    print("CMS SIGNATURE TEST")
    print("=" * 70)
    
    # Check setup
    if not check_setup():
        print("\n❌ Cannot proceed. Fix setup issues above.")
        return False
    
    # Test data
    test_data = "Hello, this is a CMS signature test!"
    
    print(f"\n📝 Test data: {test_data}")
    
    try:
        signature = sign_with_cms_token(test_data)
        
        print("\n" + "=" * 70)
        print("✓✓✓ SUCCESS! CMS SIGNATURE GENERATED ✓✓✓")
        print("=" * 70)
        print(f"\nSignature format: CMS/PKCS#7 (ITD compliant)")
        print(f"Signature length: {len(signature)} characters")
        print(f"\nFull signature:")
        print(signature[:200] + "...")
        print("\n✓ Ready to use with ERI Login API!")
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 70)
        print("✗✗✗ SIGNATURE GENERATION FAILED ✗✗✗")
        print("=" * 70)
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("  1. Check USB token is inserted")
        print("  2. Verify TOKEN_PIN is correct")
        print("  3. Check token driver path")
        print("  4. Try token management software to verify it works")
        
        return False


if __name__ == "__main__":
    # If called with argument, sign that data
    if len(sys.argv) > 1:
        data = sys.argv[1]
        try:
            signature = sign_with_cms_token(data)
            print(signature)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Run test mode
        test_signature()