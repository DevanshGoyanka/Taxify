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


_CERT_STORE_PROV_SYSTEM = 10
_CERT_SYSTEM_STORE_CURRENT_USER = 0x00010000
_CERT_SYSTEM_STORE_LOCAL_MACHINE = 0x00020000


def _open_cert_store(name: str, location: int):
    return win32crypt.CertOpenStore(_CERT_STORE_PROV_SYSTEM, 0, None, location, name)


def _find_dsc_cert(subject_filter: str):
    """Finds the DSC signing certificate in the CurrentUser\\My store by
    subject substring match, preferring one with a Digital Signature key
    usage bit if that check is available."""
    store = _open_cert_store("My", _CERT_SYSTEM_STORE_CURRENT_USER)
    for cert in store.CertEnumCertificatesInStore():
        subject = win32crypt.CertNameToStr(cert.Subject)
        if subject_filter not in subject:
            continue
        try:
            usage = cert.CertGetIntendedKeyUsage()
            if usage & 128:  # Digital Signature
                return cert
        except Exception:
            return cert
    return None


def _build_cert_chain(leaf_cert, max_depth: int = 10) -> list:
    """Walks the issuer chain from ``leaf_cert`` up to its root by matching
    each certificate's Issuer DN against candidate Subject DNs in the
    Windows CA/Root/AuthRoot system stores (CurrentUser and LocalMachine).

    Cites: this token's intermediate/root certs are not present in the
    CurrentUser\\My store alongside the leaf -- only Windows's system-wide
    public CA stores carry them. A real ITD-whitelisted signature was
    confirmed (via direct ASN.1 inspection) to embed the full 4-certificate
    chain (leaf, issuing sub-CA, intermediate CA, root), not just the leaf;
    this reproduces that chain for the ``MsgCert`` parameter of
    ``CryptSignMessage``.
    """
    chain = [leaf_cert]
    current = leaf_cert
    for _ in range(max_depth):
        if current.Subject == current.Issuer:
            break  # self-signed root reached
        parent = None
        for store_name in ("CA", "Root", "AuthRoot"):
            for location in (_CERT_SYSTEM_STORE_CURRENT_USER, _CERT_SYSTEM_STORE_LOCAL_MACHINE):
                try:
                    store = _open_cert_store(store_name, location)
                except Exception:
                    continue
                for cert in store.CertEnumCertificatesInStore():
                    if cert.Subject == current.Issuer:
                        parent = cert
                        break
                if parent:
                    break
            if parent:
                break
        if parent is None:
            break
        chain.append(parent)
        current = parent
    return chain


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
        cert_context = _find_dsc_cert(subject_filter)
        if not cert_context:
            raise RuntimeError(f"DSC Certificate matching '{subject_filter}' not found in Windows User MY Store.")

        chain = _build_cert_chain(cert_context)

        # Sign message using CryptoAPI. Empirically verified against a real
        # ITD Type-2 UAT login call (2026-09-04): a DETACHED signature
        # (fDetachedSignature=True) with the FULL certificate chain embedded
        # via MsgCert is what ITD's verifier accepts -- confirmed by
        # comparing byte-for-byte against a prior successfully-whitelisted
        # capture (data length 172, sign length 8984) and by a live login
        # call returning EF00000/OK. An earlier version of this function
        # passed fDetachedSignature=False (attached, content embedded in the
        # CMS blob) with only the leaf cert and no chain -- that comment
        # ("False = ATTACHED ... which the Java app uses") was simply wrong;
        # the working Java local-dsc-signer reference (BouncyCastle,
        # generate(cmsData, false) where false=don't encapsulate) produces a
        # DETACHED signature with the full chain, not an attached one.
        #
        # Note: the real captured sample also carries a CMS authenticated-
        # attributes block (contentType/signingTime/messageDigest/
        # CMSAlgorithmProtection) that this implementation omits --
        # attempting to add it via CryptSignMessage's AuthAttr parameter
        # segfaulted against this specific hardware CSP (HyperPKI HYP2003).
        # The live login call above confirms ITD's verifier does not require
        # that block: a detached signature with the full chain and no signed
        # attributes is sufficient.
        sign_para = {
            "SigningCert": cert_context,
            "HashAlgorithm": {"ObjId": "2.16.840.1.101.3.4.2.1", "Parameters": None},  # SHA-256
            "MsgCert": chain,
        }
        data_bytes = plain_json.encode("utf-8")
        signed_blob = win32crypt.CryptSignMessage(sign_para, (data_bytes,), True)
        base64_data = base64.b64encode(data_bytes).decode("utf-8")
        return base64.b64encode(signed_blob).decode("utf-8"), base64_data
            
    elif mode == "ngrok":
        # No default: this mode transmits the FULL plain ITR/API payload
        # (real taxpayer PII, and live OTP/EVC values via everify.py) to an
        # arbitrary external URL for signing. A hardcoded fallback here
        # previously pointed at one developer's personal ngrok tunnel --
        # exactly the "a wrong destination must fail, not be guessed"
        # hazard app/eri/config.py's ERI_BASE_URL resolution already
        # guards against. SIGNER_URL must be explicitly configured.
        signer_url = os.getenv("SIGNER_URL")
        if not signer_url:
            raise ValueError(
                "SIGNER_URL is not set. ERI_DSC_SIGNING_MODE=ngrok requires an "
                "explicitly configured remote signer endpoint -- there is no "
                "default, because sending taxpayer PII/OTP payloads to a "
                "guessed or forgotten-default URL is not acceptable."
            )

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

    Never logs the payload, signature, or encoded data: ``payload`` routinely
    carries real taxpayer PII (PAN, name, address) and live authentication
    secrets (Aadhaar/mobile/bank OTP values, via ``everify.py``'s
    ``otpValue``/``evcValue`` fields) -- printing any of it, even a
    truncated prefix, would leak that into console output/server logs.
    ``login.py``'s own comment states the intended discipline explicitly:
    "Send the request without logging URLs, envelopes, headers, tokens, or
    response bodies." This function previously violated that on every call.
    """
    # JSON-serialize payload using strict compact formatting
    serialized = json.dumps(payload, separators=(",", ":"))
    # Sign the plain JSON string
    signature_b64, final_data_b64 = sign_data(serialized)

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
            
    # Also check the 'errors' array if present. Two distinct shapes exist
    # across Type-2 endpoints:
    #  - login/addClient/everify: {code, desc, fieldName}
    #  - validate/submit:         {errCd, errFld, errCtg, asPerItr,
    #                               asComputed, variance, schId}
    # Cites: API_SubmitFlow_v1.1.pdf Section 4.6 "Response 2: When error in
    # validation" -- without this branch, every validate/submit error
    # collapsed into a generic ERIApiError(code="UNKNOWN", desc="Unknown
    # Error"), discarding exactly the per-field arithmetic-mismatch detail
    # these endpoints exist to surface.
    for err in response_json.get("errors", []):
        if "errCd" in err or "errFld" in err:
            raise ERIApiError(
                code=err.get("errCd", "UNKNOWN"),
                desc=err.get("errCtg") or "Validation Error",
                field_name=err.get("errFld"),
                category=err.get("errCtg"),
                as_per_itr=err.get("asPerItr"),
                as_computed=err.get("asComputed"),
                variance=err.get("variance"),
                sch_id=err.get("schId"),
            )
        code = err.get("code", "UNKNOWN")
        desc = err.get("desc", "Unknown Error")
        field_name = err.get("fieldName")
        raise ERIApiError(code=code, desc=desc, field_name=field_name)

    return response_json


def eri_headers(auth_token: Optional[str] = None) -> dict:
    """Returns the HTTP request headers required for ERI API requests.

    Cites: Docs/API_Login_v1.1.pdf Section 4.4.1 (Request Header)

    Resolved per call from the active (ERI_MODE, ERI_ENV) pair via
    ``get_eri_credentials()``, matching every other Type-2 module in this
    package (see e.g. login.py's own header comment). This function used to
    read the unsuffixed ``ERI_CLIENT_ID``/``ERI_CLIENT_SECRET`` directly --
    the exact same "unsuffixed variable this project never sets" defect
    already fixed for ``ERI_BASE_URL``/``ERI_USER_ID`` elsewhere in this
    package, just not carried over to this one function. Since only the
    suffix-qualified ``ERI_CLIENT_ID_TYPE2_UAT``/``_PRODUCTION`` variables
    are ever set in .env, every Type-2 API call that reached this function
    would unconditionally raise ValueError.
    """
    from app.eri.config import ERIConfigurationError, get_eri_credentials

    try:
        creds = get_eri_credentials()
    except ERIConfigurationError:
        raise
    except Exception as exc:
        raise ERIConfigurationError(
            f"Could not resolve ERI credentials for API headers: {exc}"
        ) from exc
    client_id = creds.client_id
    client_secret = creds.client_secret

    if not client_id or not client_secret:
        raise ValueError(
            f"ERI_CLIENT_ID_{creds.mode.upper()}_{creds.environment.upper()} and "
            f"ERI_CLIENT_SECRET_{creds.mode.upper()}_{creds.environment.upper()} "
            "must be configured in .env for the active ERI mode/environment."
        )

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
