import logging
import os
import json
import base64
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

_log = logging.getLogger("taxify.eri.type2.prefill")

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding
from cryptography.hazmat.backends import default_backend

import jsonschema

from app.eri.envelope import build_request_envelope, parse_response_envelope, eri_headers
from app.eri.exceptions import ERIApiError

# Resolved per call from the active (ERI_MODE, ERI_ENV) pair. It used to be
# a module constant captured at import time from an unsuffixed ERI_BASE_URL
# that this project never sets, so every request silently went to the
# hardcoded UAT default regardless of ERI_ENV.
from app.eri.config import (
    get_eri_base_url,
    get_eri_password,
    get_eri_symmetric_key,
    get_eri_user_id,
)

def decrypt_prefill(encrypted_b64: str) -> str:
    """Decrypts the AES encrypted prefill payload using the Symmetric Key.
    ITD generally uses AES-128 ECB mode with PKCS7 padding for prefill decryption.
    """
    key_b64 = get_eri_symmetric_key()
    if not key_b64:
        raise ValueError("ERI_SYMMETRIC_KEY is not set.")
    
    key = base64.b64decode(key_b64)
    ciphertext = base64.b64decode(encrypted_b64)
    
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    
    unpadder = crypto_padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    
    return data.decode("utf-8")

def validate_prefill_schema(prefill_data: Dict[str, Any]):
    """Validates the decrypted prefill JSON against the official schema."""
    # app/eri/type2/prefill.py -> repo root needs THREE ".." levels
    # (type2 -> eri -> app -> root), not two -- the previous two-level path
    # resolved to app/Docs/... (never existed) instead of the real
    # Docs/... at repo root, so this raised FileNotFoundError on every
    # call, including the very first genuinely successful getPrefill
    # response (2026-09-04, live UAT call, PAN GOYPT2026A).
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "Docs", "PreFillSchemaJSON_V6.5", "PreFillSchemaJSON_V6.5.json")
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Prefill schema not found at {schema_path}")
        
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
        
    jsonschema.validate(instance=prefill_data, schema=schema)

def get_ist_timestamp() -> str:
    ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return ist_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def request_prefill_otp(pan: str, assessment_year: str, otp_source_flag: str, auth_token: str) -> Dict[str, Any]:
    """
    Requests the OTP to get consent for Prefill data.
    Cites: Docs/API_Prefill_v1.1.pdf Section 4
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID environment variable not set")
        
    payload = {
        # Empirically confirmed (2026-09-04, live UAT calls): despite
        # API_Prefill_v1.1.pdf Section 4.4.3's table claiming "mandatory and
        # valid value is 'EriGetPrefill'" for this endpoint, the real
        # requestPrefillOTP gateway rejects that value with
        # errCd=EF40000/fieldName=serviceName ("JSON data invalid") --
        # "EriPrefill" is what the live endpoint actually requires. The
        # spec's table text for this section appears to be a copy-paste of
        # getPrefill's own (correct) requirement; do not "fix" this to
        # "EriGetPrefill" again without re-verifying against a live call.
        "serviceName": "EriPrefill",
        "pan": pan,
        "assessmentYear": assessment_year,
        "otpSourceFlag": otp_source_flag,
        "timeStamp": get_ist_timestamp()
    }

    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)

    response = requests.post(
        f"{get_eri_base_url().rstrip('/')}/requestPrefillOTP",
        json=envelope,
        headers=headers,
        verify=True,
        timeout=120.0
    )
    
    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")
        
    response_json = response.json()
    return parse_response_envelope(response_json)

def get_prefill_data(
    pan: str,
    assessment_year: str,
    auth_token: str,
    otp_source_flag: str,
    sms_transaction_id: str,
    mobile_otp: str,
    email_transaction_id: Optional[str] = None,
    email_otp: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetches and validates the prefill data after getting OTP consent from the taxpayer.
    Cites: Docs/API_Prefill_v1.1.pdf Section 5

    Empirically confirmed (2026-09-04, live UAT call against PAN GOYPT2026A,
    AY 2025) against the spec's own documented request shape (a single
    "transactionId" field): the real gateway wants the two transaction IDs
    requestPrefillOTP actually returns -- "smsTransactionId" and
    "emailTransactionId" -- as SEPARATE fields, not one generic
    "transactionId". Sending a single "transactionId" (matching the spec
    literally) reproducibly failed with errCd=EF40000 "JSON data invalid"
    regardless of which of the two IDs was used. See
    ``Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md`` for the full trace.
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID environment variable not set")

    payload = {
        "serviceName": "EriGetPrefill",
        "pan": pan,
        "assessmentYear": assessment_year,
        "otpSourceFlag": otp_source_flag,
        "mobileOtp": mobile_otp,
        "smsTransactionId": sms_transaction_id,
        "timeStamp": get_ist_timestamp()
    }
    if otp_source_flag == "E" and email_otp:
        payload["emailOtp"] = email_otp
    if email_transaction_id:
        payload["emailTransactionId"] = email_transaction_id

    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)

    response = requests.post(
        f"{get_eri_base_url().rstrip('/')}/getPrefill",
        json=envelope,
        headers=headers,
        verify=True,
        timeout=120.0
    )

    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")

    response_json = response.json()
    validated_envelope = parse_response_envelope(response_json)

    # Empirically confirmed (same live call): the real response key is
    # lowercase "prefill", not "Prefill" as this previously read -- that
    # mismatch alone would have silently treated even a genuinely
    # successful response as an error.
    encrypted_prefill = validated_envelope.get("prefill")
    if not encrypted_prefill:
        raise ERIApiError("ERROR", "prefill attribute is missing from the success response.")
        
    decrypted_str = decrypt_prefill(encrypted_prefill)
    
    try:
        prefill_json = json.loads(decrypted_str)
    except json.JSONDecodeError as e:
        raise ERIApiError("DECRYPT_ERROR", f"Failed to parse decrypted prefill as JSON: {e}")
        
    try:
        validate_prefill_schema(prefill_json)
    except jsonschema.exceptions.ValidationError as e:
        # Non-fatal. Empirically confirmed (2026-09-04, live UAT call, PAN
        # GOYPT2026A/AY2025): a real, successfully-decrypted response from
        # ITD's own live server routinely sets optional/inapplicable form
        # sections to `null` (e.g. scheduleCFL when there are no carried-
        # forward losses) where the PUBLISHED schema declares
        # "type": "object" with no null allowed -- the schema itself is out
        # of sync with the live server's actual behavior, not a defect in
        # this response. Since a real taxpayer will almost always have many
        # such inapplicable null sections (this response had 53 of 55
        # top-level sections null, with only personalInfo/verification
        # populated), treating this as fatal would make get_prefill_data()
        # unusable for its actual purpose. The decrypted, successfully-
        # parsed JSON is still the authoritative data from ITD; only log.
        _log.warning(
            "Prefill data for PAN %s (AY %s) failed schema validation at %s: %s "
            "-- returning the data anyway (see prefill.py's get_prefill_data "
            "docstring/comment for why this is non-fatal).",
            pan, assessment_year, list(e.path), e.message,
        )

    return prefill_json
