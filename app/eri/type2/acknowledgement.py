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
        verify=False,
        timeout=120.0
    )
    
    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")
        
    # Check if the response is JSON (meaning an error occurred, as success returns raw binary PDF)
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
        
    # Success case: returning the PDF binary data
    return response.content
