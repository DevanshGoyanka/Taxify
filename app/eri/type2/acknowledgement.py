import os
import requests
from typing import Dict, Any, Union
from datetime import datetime, timedelta

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

def get_ist_timestamp() -> str:
    ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return ist_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def get_acknowledgement(pan: str, ack_number: str, auth_token: str) -> bytes:
    """
    Retrieves the acknowledgement PDF for a submitted ITR.
    Cites: Docs/API_AcknowledgementFlow.pdf Section 4
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID environment variable not set")
        
    payload = {
        "serviceName": "EriGetAckowledgement",
        "pan": pan,
        "arnNumber": ack_number,
        "timeStamp": get_ist_timestamp()
    }
    
    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)
    
    response = requests.post(
        f"{get_eri_base_url().rstrip('/')}/getAcknowledgement",
        json=envelope,
        headers=headers,
        verify=True,
        timeout=120.0
    )
    
    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")

    # ITD's live getAcknowledgement endpoint has a confirmed, INTERMITTENT
    # server-side bug (2026-09-04, PAN SRGPZ2026C, ARN 116997020040926):
    # that call returned a raw Java-serialized java.util.HashMap (magic
    # bytes b"\xac\xed\x00\x05") wrapping the original upstream HTTP
    # response object (headers like Transfer-Encoding/Date/Content-Type as
    # map entries, plus the actual PDF bytes as a nested byte-array
    # value), all mislabeled with Content-Type: application/json -- not a
    # real application/pdf binary body, and not valid JSON either. The
    # same malformed shape was independently found in the ITR-V PDF ITD
    # emailed that taxpayer directly, so it's a genuine upstream bug, not
    # an artifact of one delivery channel. It is NOT universal, though: an
    # earlier successful call for a different PAN/ARN (GOYPT2026B,
    # 111202010240326, from the original ITR-1 UAT round -- see
    # uat-login-test/acknowledgement_GOYPT2026B_111202010240326.pdf)
    # returned a clean, unwrapped PDF starting at byte 0. There is nothing
    # on our side to "fix" except tolerating both shapes: detect the real
    # payload by its own magic bytes (the %PDF- marker) wherever it
    # appears, rather than trusting the Content-Type header or assuming a
    # fixed offset.
    pdf_start = response.content.find(b"%PDF-")
    if pdf_start != -1:
        pdf_end = response.content.rfind(b"%%EOF")
        if pdf_end != -1:
            return response.content[pdf_start:pdf_end + 5]
        return response.content[pdf_start:]

    # No embedded PDF found -- this is a genuine error response. Some
    # endpoints might not wrap in 'messages' for generic errors, so a
    # plain-text/HTML body without a %PDF- marker also lands here.
    content_type = response.headers.get("Content-Type", "").lower()
    if "application/json" in content_type:
        try:
            resp_json = response.json()
        except Exception:
            resp_json = {}
        # Parse the error response envelope, which will raise the correct ERIApiError
        parse_response_envelope(resp_json)
        # If parse_response_envelope doesn't raise, we still didn't get a PDF, which is unexpected
        raise ERIApiError("UNEXPECTED", "Received JSON success response instead of PDF binary.")

    raise ERIApiError("UNEXPECTED", "Response contained neither a valid PDF nor a recognizable JSON error.")
