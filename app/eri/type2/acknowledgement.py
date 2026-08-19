import os
import requests
from typing import Dict, Any, Union
from datetime import datetime, timedelta

from app.eri.envelope import build_request_envelope, parse_response_envelope, eri_headers
from app.eri.exceptions import ERIApiError

ERI_BASE_URL = os.getenv("ERI_BASE_URL", "https://uatocpservices.incometax.gov.in/v1")

def get_ist_timestamp() -> str:
    ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return ist_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def get_acknowledgement(pan: str, ack_number: str, auth_token: str) -> bytes:
    """
    Retrieves the acknowledgement PDF for a submitted ITR.
    Cites: Docs/API_AcknowledgementFlow.pdf Section 4
    """
    eri_user_id = os.getenv("ERI_USER_ID")
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
        f"{ERI_BASE_URL.rstrip('/')}/getAcknowledgement",
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
