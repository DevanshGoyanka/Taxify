import os
import base64
import json
from typing import Any, Dict, Optional
from app.eri.exceptions import ERIApiError

# Import cryptography for file-based signing and encryption
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding
from cryptography.hazmat.backends import default_backend


def encrypt_password(password: str, symmetric_key_b64: str) -> str:
    """Encrypts the user's password using the symmetric key via AES-128-ECB.
    
    Cites: credentials.txt and ERI Specs for password symmetric key encryption.
    """
    key = base64.b64decode(symmetric_key_b64)
    # Pad password to 16-byte blocks (AES block size)
    padder = crypto_padding.PKCS7(128).padder()
    padded_data = padder.update(password.encode("utf-8")) + padder.finalize()
    
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    return base64.b64encode(ciphertext).decode("utf-8")


# Import win32crypt for Windows-based token signing
try:
    import win32crypt
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


def sign_data(plain_json: str) -> tuple[str, str]:
    """Signs the plain JSON data string using the ERI DSC private key.
    
    Cites: Docs/ERI API Specification_v1.1.pdf Section 4 (SIGNING API REQUEST)
    """
    mode = os.getenv("ERI_DSC_SIGNING_MODE", "token").lower()
    
    if mode == "file":
        pfx_path = os.getenv("ERI_DSC_PFX_PATH")
        pfx_password = os.getenv("ERI_DSC_PFX_PASSWORD", "")
        if not pfx_path or not os.path.exists(pfx_path):
            raise ValueError(f"PFX certificate path not found: {pfx_path}")
            
        with open(pfx_path, "rb") as f:
            pfx_data = f.read()
            
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            pfx_data,
            pfx_password.encode("utf-8") if pfx_password else None
        )
        if not private_key:
            raise ValueError("No private key found in PFX file.")
            
        signature = private_key.sign(
            plain_json.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        base64_data = base64.b64encode(plain_json.encode("utf-8")).decode("utf-8")
        return base64.b64encode(signature).decode("utf-8"), base64_data
        
    elif mode == "token":
        if not HAS_WIN32:
            raise RuntimeError("win32crypt is not available for token signing.")
            
        subject_filter = os.getenv("ERI_DSC_CERT_SUBJECT", "SUNIT RAMASHANKAR GOYANKA")
        
        # Open "My" System Store
        CERT_STORE_PROV_SYSTEM = 10
        CERT_SYSTEM_STORE_CURRENT_USER = 0x00010000
        
        store = win32crypt.CertOpenStore(
            CERT_STORE_PROV_SYSTEM,
            0,
            None,
            CERT_SYSTEM_STORE_CURRENT_USER,
            "My"
        )
        
        cert_context = None
        try:
            for cert in store.CertEnumCertificatesInStore():
                subject = win32crypt.CertNameToStr(cert.Subject)
                if subject_filter in subject:
                    try:
                        usage = cert.CertGetIntendedKeyUsage()
                        # 192 = Digital Signature (128) | Non-Repudiation (64)
                        # We just check if Digital Signature (128) is present
                        if usage & 128:
                            cert_context = cert
                            break
                    except Exception:
                        # Fallback if CertGetIntendedKeyUsage fails
                        cert_context = cert
                        break
        finally:
            pass
            
        if not cert_context:
            raise RuntimeError(f"DSC Certificate matching '{subject_filter}' not found in Windows User MY Store.")
            
        try:
            # Sign message using CryptoAPI
            sign_para = {
                "SigningCert": cert_context,
                "HashAlgorithm": {"ObjId": "2.16.840.1.101.3.4.2.1", "Parameters": None}, # SHA-256
            }
            # CryptSignMessage expects a sequence of bytes
            data_bytes = plain_json.encode("utf-8")
            # Set to False to generate an ATTACHED signature (which the Java app uses)
            signed_blob = win32crypt.CryptSignMessage(sign_para, (data_bytes,), False)
            base64_data = base64.b64encode(data_bytes).decode("utf-8")
            return base64.b64encode(signed_blob).decode("utf-8"), base64_data
        finally:
            pass
            
    elif mode == "ngrok":
        signer_url = os.getenv("SIGNER_URL", "https://unpondered-implacably-tamatha.ngrok-free.dev/api/sign")
        print(f"DEBUG: Sending payload to remote signer: {signer_url}")
        
        try:
            import httpx
            import json
            # The signing service expects the raw JSON object
            json_payload = json.loads(plain_json)
            
            with httpx.Client(timeout=30.0) as client:
                sign_resp = client.post(signer_url, json={"payload": json_payload})
                sign_resp.raise_for_status()
                sign_data_resp = sign_resp.json()
                
                if not sign_data_resp.get("success"):
                    raise Exception(f"Signing failed remotely: {sign_data_resp}")
                    
                # The signer returns both .data (base64) and .sign. We need both.
                return sign_data_resp.get("sign"), sign_data_resp.get("data")
        except Exception as e:
            raise RuntimeError(f"Failed to sign payload via ngrok: {e}")

    elif mode == "mock":
        base64_data = base64.b64encode(plain_json.encode("utf-8")).decode("utf-8")
        return base64.b64encode(b"mock_signature_for_testing_length_limits").decode("utf-8"), base64_data
    else:
        raise ValueError(f"Unknown ERI_DSC_SIGNING_MODE: {mode}")


def build_request_envelope(payload: dict, eri_user_id: str) -> dict:
    """Builds the request envelope containing serialized payload, DSC signature, and ERI User ID.
    
    Cites: Docs/API_Login_v1.1.pdf Section 4.4.2 (Request Body: Description)
    """
    # JSON-serialize payload using strict compact formatting
    serialized = json.dumps(payload, separators=(",", ":"))
    print(f"DEBUG [ENVELOPE] Plain payload: {serialized}")
    print(f"DEBUG [ENVELOPE] Plain payload length: {len(serialized)} chars")
    # Sign the plain JSON string
    signature_b64, final_data_b64 = sign_data(serialized)
    print(f"DEBUG [ENVELOPE] Signature (first 50 chars): {signature_b64[:50]}...")
    print(f"DEBUG [ENVELOPE] Data b64 (first 50 chars): {final_data_b64[:50]}...")
    
    return {
        "data": final_data_b64,
        "sign": signature_b64,
        "eriUserId": eri_user_id
    }


def parse_response_envelope(response_json: dict) -> dict:
    """Parses response envelope, raises ERIApiError on failure, and returns the response dictionary.
    
    Cites: Docs/API_Login_v1.1.pdf Section 4.5 (Response Parameters)
    """
    if "messages" not in response_json:
        # Some endpoints might not wrap in 'messages' for generic errors
        if "error" in response_json:
            raise ERIApiError(code="UNKNOWN", desc=response_json["error"])
            
    # Check for errors in the messages array
    for msg in response_json.get("messages", []):
        if msg.get("type") == "ERROR":
            code = msg.get("code", "UNKNOWN")
            desc = msg.get("desc", "Unknown Error")
            field_name = msg.get("fieldName")
            raise ERIApiError(code=code, desc=desc, field_name=field_name)
            
    # Also check the 'errors' array if present (seen in some Type-2 API responses)
    for err in response_json.get("errors", []):
        code = err.get("code", "UNKNOWN")
        desc = err.get("desc", "Unknown Error")
        field_name = err.get("fieldName")
        raise ERIApiError(code=code, desc=desc, field_name=field_name)
        
    return response_json


def eri_headers(auth_token: Optional[str] = None) -> dict:
    """Returns the HTTP request headers required for ERI API requests.
    
    Cites: Docs/API_Login_v1.1.pdf Section 4.4.1 (Request Header)
    """
    client_id = os.getenv("ERI_CLIENT_ID")
    client_secret = os.getenv("ERI_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise ValueError("ERI_CLIENT_ID and ERI_CLIENT_SECRET must be configured in environment variables.")
        
    headers = {
        "Content-Type": "application/json",
        "clientId": client_id,
        "clientSecret": client_secret,
        "accessMode": "API",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    if auth_token:
        headers["authToken"] = auth_token
        headers["Authorization"] = auth_token
        
    return headers
