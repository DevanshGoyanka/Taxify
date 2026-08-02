"""
Cryptography utility for portal passwords.

Uses AES-256-GCM via the cryptography library's AESGCM class to encrypt
and decrypt client portal passwords.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Command to generate a key:
# python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"

def _get_key() -> bytes:
    """
    Retrieve and decode the PORTAL_ENCRYPTION_KEY environment variable.

    Returns the 32-byte key as bytes.
    Raises ValueError if key is missing or invalid.
    """
    key_b64 = os.environ.get("PORTAL_ENCRYPTION_KEY")
    if not key_b64:
        raise ValueError("PORTAL_ENCRYPTION_KEY environment variable is not set.")
    try:
        return base64.b64decode(key_b64)
    except Exception as e:
        raise ValueError(f"Invalid PORTAL_ENCRYPTION_KEY format: {e}")

def encrypt_portal_password(plain: str) -> str:
    """
    Encrypt a portal password string using AES-256-GCM.

    Generates a 96-bit random nonce, encrypts the plaintext,
    and returns base64(nonce + ciphertext).
    """
    if not plain:
        return ""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce
    ciphertext = aesgcm.encrypt(nonce, plain.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")

def decrypt_portal_password(encrypted: str) -> str:
    """
    Decrypt a base64-encoded encrypted portal password using AES-256-GCM.

    Splits the 12-byte nonce from the ciphertext and decrypts the data.
    """
    if not encrypted:
        return ""
    key = _get_key()
    aesgcm = AESGCM(key)
    try:
        data = base64.b64decode(encrypted.encode("utf-8"))
        if len(data) < 12:
            raise ValueError("Invalid encrypted data length.")
        nonce = data[:12]
        ciphertext = data[12:]
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Portal password decryption failed: {e}")
