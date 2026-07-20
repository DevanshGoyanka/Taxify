"""
CMS Bridge - Python wrapper for Java CMS signing
Outputs EXACT ERI JSON format
"""

import subprocess
import os
import sys
import json
import base64
import re

# ========================================
# CONFIGURATION
# ========================================
PKCS11_DLL_PATH = "C:\\Windows\\System32\\eps2003csp11v2.dll"
TOKEN_PIN = "123456789"   # <-- CHANGE THIS
ERI_USER_ID = "ERIP011535"   # <-- CHANGE THIS IF NEEDED

JAVA_CLASS = "CMSTokenSigner"
BC_PROV = "bcprov-jdk18on-1.82.jar"
BC_PKIX = "bcpkix-jdk18on-1.82.jar"
BC_UTIL = "bcutil-jdk18on-1.82.jar"


def clean_base64(value: str) -> str:
    """Remove newlines and spaces from Base64."""
    value = value.replace("\n", "").replace("\r", "").strip()
    value = re.sub(r"\s+", "", value)
    return value


def sign_with_token(data):
    """Calls Java CMS signer and returns Base64 CMS signature (one line)."""

    if isinstance(data, bytes):
        data = data.decode("utf-8")

    if sys.platform == "win32":
        cp = f".;{BC_PROV};{BC_PKIX};{BC_UTIL}"
    else:
        cp = f".:{BC_PROV}:{BC_PKIX}:{BC_UTIL}"

    cmd = [
        "java",
        "--add-opens", "jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED",
        "-cp", cp,
        JAVA_CLASS,
        data,
        PKCS11_DLL_PATH,
        TOKEN_PIN
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(f"Java error: {result.stderr}")

    signature = clean_base64(result.stdout)

    if len(signature) < 50:
        raise Exception("Invalid signature received.")

    return signature


def create_eri_json(data: str, cms_signature: str):
    """Creates perfect ERI JSON format."""

    # Base64 of original data
    data_b64 = base64.b64encode(data.encode()).decode()

    payload = {
        "sign": cms_signature,
        "data": data_b64,
        "eriUserId": ERI_USER_ID
    }

    return json.dumps(payload, indent=4)


def test():
    """Test mode"""
    test_data = "Hello, this is a CMS signature test!"

    try:
        cms_sig = sign_with_token(test_data)
        json_output = create_eri_json(test_data, cms_sig)

        # IMPORTANT: print only the JSON — ERI requires clean stdout
        print(json_output)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # If argument passed → sign that string
    if len(sys.argv) > 1:
        input_data = sys.argv[1]
        cms_sig = sign_with_token(input_data)
        print(create_eri_json(input_data, cms_sig))
    else:
        test()
