import os
import httpx
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import HTTPException

from app.eri.envelope import (
    encrypt_password,
    build_request_envelope,
    parse_response_envelope,
    eri_headers
)
from app.eri.exceptions import ERIApiError

# ERI base URL defaulting to UAT gateway
# Resolved per call from the active (ERI_MODE, ERI_ENV) pair. It used to be
# a module constant captured at import time from an unsuffixed ERI_BASE_URL
# that this project never sets, so every request silently went to the
# hardcoded UAT default regardless of ERI_ENV.
from app.eri.config import get_eri_base_url


def get_eri_mode() -> str:
    """Returns the current ERI mode: 'real' if ERI_MODE is real, otherwise 'mock'."""
    return os.getenv("ERI_MODE", "mock").lower()


def eri_post(url_path: str, payload: dict, eri_user_id: str, auth_token: Optional[str] = None) -> dict:
    """Constructs the request envelope, signs it, and posts it to the ITD gateway.
    
    Cites: Docs/API_Login_v1.1.pdf Section 4 (Request/Response Envelope)
    """
    # 1. Build and sign envelope
    envelope = build_request_envelope(payload, eri_user_id)
            
    # 2. Make the actual HTTP call to the ITD UAT gateway
    url = f"{get_eri_base_url().rstrip('/')}/{url_path.lstrip('/')}"
    headers = eri_headers(auth_token)
    
    # Also support client-id/client-secret / Authorization headers just in case gateway expects them
    if "clientId" in headers:
        headers["client-id"] = headers["clientId"]
    if "clientSecret" in headers:
        headers["client-secret"] = headers["clientSecret"]
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
        headers["authToken"] = auth_token
        
    try:
        with httpx.Client(timeout=30.0, verify=True) as client:
            response = client.post(url, json=envelope, headers=headers)
            
            # Raise exception if status code is not 200/201
            if response.status_code not in (200, 201):
                try:
                    error_json = response.json()
                    desc = error_json.get("message") or error_json.get("desc") or response.text
                except Exception:
                    desc = response.text
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"ITD ERI gateway returned error: {desc}"
                )
                
            if not response.text.strip():
                return {}
                
            response_json = response.json()
            
            # Validate response envelope (e.g. check for errors in messages array)
            return parse_response_envelope(response_json)
            
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to communicate with ITD ERI gateway: {exc}"
        )
    except ERIApiError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"ITD ERI Error [{exc.code}]: {exc.desc}"
        )
