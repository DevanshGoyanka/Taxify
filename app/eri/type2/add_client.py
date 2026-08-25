import os
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.eri.envelope import (
    build_request_envelope,
    eri_headers,
    parse_response_envelope
)
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


def addClient(pan: str, dateOfBirth: str, otpSourceFlag: str, auth_token: str) -> Dict[str, Any]:
    """Implements the addClient API to request adding a registered taxpayer as a client.
    
    Cites: Docs/API_AddClientFlow_v1.1.pdf Section 4 (addClient API Details).
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID is not configured in the environment.")
        
    payload = {
        "serviceName": "EriAddClientService",
        "pan": pan,
        "dateOfBirth": dateOfBirth,
        "otpSourceFlag": otpSourceFlag,
        "timeStamp": get_ist_timestamp()
    }
    
    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)
    url = f"{get_eri_base_url().rstrip('/')}/addClient"
    
    with httpx.Client(timeout=30.0, verify=False) as client:
        response = client.post(url, json=envelope, headers=headers)
        if response.status_code not in (200, 201):
            raise ERIApiError(f"HTTP_{response.status_code}", f"addClient failed with HTTP {response.status_code}: {response.text}")
        return parse_response_envelope(response.json())


def validateClientOtp(pan: str, transactionId: str, otpSourceFlag: str, otp: str, validUpto: str, auth_token: str) -> Dict[str, Any]:
    """Implements the validateClientOtp API to confirm client addition via OTP.
    
    Cites: Docs/API_AddClientFlow_v1.1.pdf Section 5 (validateClientOtp API Details).
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID is not configured in the environment.")
        
    payload = {
        "serviceName": "EriValidateClientService",
        "pan": pan,
        "transactionId": transactionId,
        "otpSourceFlag": otpSourceFlag,
        "Otp": otp,
        "validUpto": validUpto,
        "timeStamp": get_ist_timestamp()
    }
    
    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)
    url = f"{get_eri_base_url().rstrip('/')}/validateClientOtp"
    
    with httpx.Client(timeout=30.0, verify=False) as client:
        response = client.post(url, json=envelope, headers=headers)
        if response.status_code not in (200, 201):
            raise ERIApiError(f"HTTP_{response.status_code}", f"validateClientOtp failed with HTTP {response.status_code}: {response.text}")
        return parse_response_envelope(response.json())


def addRegisterClient(
    pan: str, residentialStatusCd: str, lastName: str, dateOfBirth: str, 
    userGender: str, priMobileNum: str, isdCd: str, priMobBelongsTo: str, 
    priEmailRelationId: str, priEmailId: str, addrLine1Txt: str, addrLine2Txt: str, 
    countryCd: str, auth_token: str,
    firstName: str = "", midName: str = "", addrLine3Txt: str = "", addrLine4Txt: str = "", 
    addrLine5Txt: str = "", pinCd: str = "", zipCd: str = "", stdCd: str = "", 
    landlineNo: str = "", stateCd: str = "", foreignStateDesc: str = ""
) -> Dict[str, Any]:
    """Implements the AddRegisterClient API to register an unregistered taxpayer.
    
    Cites: Docs/API_AddClientFlow_v1.1.pdf Section 6 (AddRegisterClient API Details).
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID is not configured in the environment.")
        
    # Map string relation types to the UAT coded values (1=Self, 2=Spouse, etc.)
    mob_rel = "1" if str(priMobBelongsTo).upper() == "SELF" else priMobBelongsTo
    email_rel = "1" if str(priEmailRelationId).upper() == "SELF" else priEmailRelationId

    payload = {
        "serviceName": "EriRegisterClient",
        "pan": pan,
        "residentialStatusCd": residentialStatusCd,
        "firstName": firstName,
        "lastName": lastName,
        "midName": midName,
        "dateOfBirth": dateOfBirth,
        "userGender": userGender,
        "priMobileNum": priMobileNum,
        "isdCd": isdCd,
        "priMobBelongsTo": mob_rel,
        "priEmailRelationId": email_rel,
        "priEmailId": priEmailId,
        "addrLine1Txt": addrLine1Txt,
        "addrLine2Txt": addrLine2Txt,
        "addrLine3Txt": addrLine3Txt,
        "addrLine4Txt": addrLine4Txt,
        "addrLine5Txt": addrLine5Txt,
        "pinCd": pinCd,
        "zipCd": zipCd,
        "stdCd": stdCd,
        "countryCd": countryCd,
        "landlineNo": landlineNo,
        "stateCd": stateCd,
        "foreignStateDesc": foreignStateDesc,
        "timeStamp": get_ist_timestamp()
    }
    
    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)
    url = f"{get_eri_base_url().rstrip('/')}/registerClient"
    
    with httpx.Client(timeout=30.0, verify=False) as client:
        response = client.post(url, json=envelope, headers=headers)
        if response.status_code not in (200, 201):
            raise ERIApiError(f"HTTP_{response.status_code}", f"addRegisterClient failed with HTTP {response.status_code}: {response.text}")
        return parse_response_envelope(response.json())


def validateRegOtp(pan: str, smsTransactionId: str, emailTransactionId: str, mobileOtp: str, emailOtp: str, validUpto: str, auth_token: str) -> Dict[str, Any]:
    """Implements the ValidateRegOtp API to confirm registration and add client.
    
    Cites: Docs/API_AddClientFlow_v1.1.pdf Section 7 (ValidateRegOtp API Details).
    """
    eri_user_id = get_eri_user_id()
    if not eri_user_id:
        raise ValueError("ERI_USER_ID is not configured in the environment.")
        
    payload = {
        "serviceName": "EriValidateRegOtp",
        "pan": pan,
        "smsTransactionId": smsTransactionId,
        "emailTransactionId": emailTransactionId,
        "mobileOtp": mobileOtp,
        "emailOtp": emailOtp,
        "validUpto": validUpto,
        "timeStamp": get_ist_timestamp()
    }
    
    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)
    url = f"{get_eri_base_url().rstrip('/')}/validateRegOtp"
    
    with httpx.Client(timeout=30.0, verify=False) as client:
        response = client.post(url, json=envelope, headers=headers)
        if response.status_code not in (200, 201):
            raise ERIApiError(f"HTTP_{response.status_code}", f"validateRegOtp failed with HTTP {response.status_code}: {response.text}")
        return parse_response_envelope(response.json())
