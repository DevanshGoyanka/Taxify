import os
import requests
from typing import Dict, Any, Optional
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

def update_ver_mode(pan: str, ack_num: str, ay: str, form_code: str, ver_mode: str, auth_token: str) -> Dict[str, Any]:
    """
    Updates the verification mode of the ITR to "LATER" or "ITRV".
    Cites: Docs/API_Everify_Return_v1.1.pdf Section 4
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID environment variable not set")
        
    payload = {
        "serviceName": "EriUpdateVerMode",
        "pan": pan,
        "verMode": ver_mode,
        "ackNum": ack_num,
        "ay": ay,
        "formCode": form_code,
        "timeStamp": get_ist_timestamp()
    }
    
    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)
    
    response = requests.post(
        f"{get_eri_base_url().rstrip('/')}/updateVerMode",
        json=envelope,
        headers=headers,
        verify=False
    )
    
    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")
        
    return parse_response_envelope(response.json())


def generate_evc(pan: str, ack_num: str, ay: str, form_code: str, ver_mode: str, auth_token: str) -> Dict[str, Any]:
    """
    Generates EVC online using one of the verification modes.
    Cites: Docs/API_Everify_Return_v1.1.pdf Section 5
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID environment variable not set")
        
    payload = {
        "serviceName": "EriGenerateEvcService",
        "eriUserId": eri_user_id,
        "pan": pan,
        "verMode": ver_mode,
        "ackNum": ack_num,
        "ay": ay,
        "formCode": form_code,
        "timeStamp": get_ist_timestamp()
    }
    
    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)
    
    response = requests.post(
        f"{get_eri_base_url().rstrip('/')}/generateEvc",
        json=envelope,
        headers=headers,
        verify=False,
        timeout=120.0
    )
    
    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")
        
    return parse_response_envelope(response.json())


def verify_evc(pan: str, ack_num: str, ay: str, form_code: str, ver_mode: str, transaction_id: str, auth_token: str, otp_value: Optional[str] = None, evc_value: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies the ITR using Aadhaar OTP or EVC.
    Cites: Docs/API_Everify_Return_v1.1.pdf Section 6
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID environment variable not set")
        
    payload = {
        "serviceName": "EriVerifyEvcService",
        "eriUserId": eri_user_id,
        "pan": pan,
        "verMode": ver_mode,
        "ay": ay,
        "formCode": form_code,
        "ackNum": ack_num,
        "transactionId": transaction_id,
        "timeStamp": get_ist_timestamp()
    }
    
    if ver_mode == "AADHAAR":
        if not otp_value:
            raise ValueError("otp_value is mandatory when ver_mode is AADHAAR")
        payload["otpValue"] = otp_value
    elif ver_mode in ["BANKEVC", "DEMATEVC"]:
        if not evc_value:
            raise ValueError("evc_value is mandatory when ver_mode is BANKEVC or DEMATEVC")
        payload["evcValue"] = evc_value
    else:
        raise ValueError(f"Unknown verMode: {ver_mode}")
        
    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)
    
    response = requests.post(
        f"{get_eri_base_url().rstrip('/')}/verifyEvc",
        json=envelope,
        headers=headers,
        verify=False,
        timeout=120.0
    )
    
    if response.status_code != 200:
        raise ERIApiError("HTTP_ERROR", f"HTTP {response.status_code}: {response.text}")
        
    return parse_response_envelope(response.json())
