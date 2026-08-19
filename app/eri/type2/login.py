import os
import json
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any

from app.eri.envelope import (
    encrypt_password,
    build_request_envelope,
    parse_response_envelope,
    eri_headers
)
from app.eri.exceptions import ERIApiError

ERI_BASE_URL = os.getenv("ERI_BASE_URL", "https://uatocpservices.incometax.gov.in/v1")


def eri_login() -> Dict[str, Any]:
    """Authenticates the ERI user and establishes a session with ITD.
    
    Cites: Docs/API_Login_v1.1.pdf Section 4.3 (Login API Request) and Section 4.5 (Response)
    """
    eri_user_id = os.getenv("ERI_USER_ID")
    password = os.getenv("ERI_PASSWORD")
    symmetric_key = os.getenv("ERI_SYMMETRIC_KEY", "Xuslp8BPWDe0QCF+rLCGZA==")
    
    if not eri_user_id or not password:
        raise ValueError("ERI_USER_ID and ERI_PASSWORD must be configured in environment variables.")
        
    # ITD API might strictly validate timestamp against IST instead of UTC
    ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
    timestamp = ist_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    encrypted_pass = encrypt_password(password, symmetric_key)
    
    payload = {
        "serviceName": "EriLoginService",
        "entity": eri_user_id,
        "pass": encrypted_pass,
        "timeStamp": timestamp
    }
    
    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers()
    url = f"{ERI_BASE_URL.rstrip('/')}/login"
    
    import time
    print(f"DEBUG [LOGIN] URL: {url}")
    print(f"DEBUG [LOGIN] Envelope keys: {list(envelope.keys())}")
    print(f"DEBUG [LOGIN] Data b64 (first 80 chars): {envelope.get('data', '')[:80]}")
    print(f"DEBUG [LOGIN] Sign b64 (first 80 chars): {envelope.get('sign', '')[:80]}")
    print(f"DEBUG [LOGIN] Headers (without secrets): {{k: '***' if 'secret' in k.lower() else v for k, v in headers.items()}}")
    
    # Send actual HTTP call to the gateway
    t0 = time.time()
    with httpx.Client(timeout=120.0, verify=False) as client:
        response = client.post(url, json=envelope, headers=headers)
        elapsed = time.time() - t0
        
        print(f"DEBUG [LOGIN] HTTP {response.status_code} in {elapsed:.1f}s")
        print(f"DEBUG [LOGIN] Response headers: {dict(response.headers)}")
        print(f"DEBUG [LOGIN] Response body: {response.text[:500]}")

        if response.status_code not in (200, 201):
            raise ERIApiError(f"HTTP_{response.status_code}", f"Login failed with HTTP {response.status_code}: {response.text}")

        parsed_response = parse_response_envelope(response.json())
        return {
            "authToken": parsed_response.get("autkn"),
            "transactionId": parsed_response.get("transactionId")
        }


def eri_logout(auth_token: str) -> None:
    """Terminates the active ERI session with ITD.
    
    Cites: Docs/API_Login_v1.1.pdf Section 4.10.3 (Logout Request/Response)
    """
    eri_user_id = os.getenv("ERI_USER_ID")
    if not eri_user_id:
        raise ValueError("ERI_USER_ID is not configured in the environment.")
        
    payload = {
        "serviceName": "EriLogoutService",
        "entity": eri_user_id,
        "pan": ""
    }
    
    envelope = build_request_envelope(payload, eri_user_id)
    headers = eri_headers(auth_token)
    url = f"{ERI_BASE_URL.rstrip('/')}/auth/logout"
    
    with httpx.Client(timeout=120.0, verify=False) as client:
        response = client.post(url, json=envelope, headers=headers)
        
        if response.status_code not in (200, 201):
            raise ERIApiError(f"HTTP_{response.status_code}", f"Logout failed with HTTP {response.status_code}: {response.text}")
            
        if response.text.strip():
            parse_response_envelope(response.json())
