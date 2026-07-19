import os
import base64
from fastapi import APIRouter, Depends, HTTPException, Response
from typing import Dict, Any

from app.auth.dependencies import get_current_user
from app.db.models import User

# ERI Pydantic schemas (we assume these will be added to app.schemas.eri)
from app.schemas.eri import (
    ERILoginRequest, ERILogoutRequest, 
    ERIAddClientRequest, ERIValidateClientOtpRequest,
    ERIRegisterClientRequest, ERIValidateRegOtpRequest,
    ERIPrefillOtpRequest, ERIPrefillDataRequest,
    ERIUpdateVerModeRequest, ERIGenerateEvcRequest, ERIVerifyEvcRequest,
    ERIAcknowledgementRequest
)

# ERI logic imports
from app.eri.login import eri_login, eri_logout
from app.eri.add_client import (
    addClient, validateClientOtp,
    addRegisterClient, validateRegOtp
)
from app.eri.prefill import request_prefill_otp, get_prefill_data
from app.eri.everify import update_ver_mode, generate_evc, verify_evc
from app.eri.acknowledgement import get_acknowledgement
from app.eri.exceptions import ERIApiError

router = APIRouter(prefix="/eri", tags=["eri"])

# Common auth token Dependency (since ERI requires an auth token after login)
# For now we'll just allow passing the token in the request headers or body.
# In a real app, this should be tracked per-user session.
def get_eri_auth_token(eri_auth_token: str = "") -> str:
    if not eri_auth_token:
        # We can fetch a dummy one or fail. Let's just fail loudly.
        raise HTTPException(status_code=401, detail="ERI auth token is required")
    return eri_auth_token

@router.post("/login")
async def login_eri(req: ERILoginRequest, current_user: User = Depends(get_current_user)):
    try:
        # In a real app, eri_user_id and password would be sourced carefully.
        # eri_login pulls from .env by default
        return await eri_login()
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout_eri(req: ERILogoutRequest, current_user: User = Depends(get_current_user)):
    try:
        # Token is usually passed in the header; this assumes eri_logout handles it
        return await eri_logout(req.pan)
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- ADD CLIENT -----------------

@router.post("/client/add")
def client_add(req: ERIAddClientRequest, token: str = Depends(get_eri_auth_token)):
    try:
        return addClient(req.pan, req.dateOfBirth, req.otpSourceFlag, token)
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
@router.post("/client/validate-otp")
def client_validate_otp(req: ERIValidateClientOtpRequest, token: str = Depends(get_eri_auth_token)):
    try:
        return validateClientOtp(req.pan, req.transactionId, req.otpSourceFlag, req.otp, req.validUpto, token)
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/client/register")
def client_register(req: ERIRegisterClientRequest, token: str = Depends(get_eri_auth_token)):
    try:
        return addRegisterClient(req.dict(), token)
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/client/register/validate-otp")
def client_register_validate(req: ERIValidateRegOtpRequest, token: str = Depends(get_eri_auth_token)):
    try:
        return validateRegOtp(req.pan, req.smsTransactionId, req.emailTransactionId, req.mobileOtp, req.emailOtp, req.validUpto, token)
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------- PREFILL -----------------

@router.post("/prefill/request-otp")
def prefill_request_otp(req: ERIPrefillOtpRequest, token: str = Depends(get_eri_auth_token)):
    try:
        return request_prefill_otp(req.pan, req.assessmentYear, req.otpSourceFlag, token)
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/prefill/data")
def prefill_data(req: ERIPrefillDataRequest, token: str = Depends(get_eri_auth_token)):
    try:
        return get_prefill_data(req.pan, req.assessmentYear, token, req.otpSourceFlag, req.transactionId, req.mobileOtp, req.emailOtp)
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------- E-VERIFY -----------------

@router.post("/everify/update-mode")
def everify_update_mode(req: ERIUpdateVerModeRequest, token: str = Depends(get_eri_auth_token)):
    try:
        return update_ver_mode(req.pan, req.ackNum, req.ay, req.formCode, req.verMode, token)
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/everify/generate-evc")
def everify_generate_evc(req: ERIGenerateEvcRequest, token: str = Depends(get_eri_auth_token)):
    try:
        return generate_evc(req.pan, req.ackNum, req.ay, req.formCode, req.verMode, token)
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/everify/verify-evc")
def everify_verify_evc(req: ERIVerifyEvcRequest, token: str = Depends(get_eri_auth_token)):
    try:
        return verify_evc(req.pan, req.ackNum, req.ay, req.formCode, req.verMode, req.transactionId, token, req.otpValue, req.evcValue)
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------- ACKNOWLEDGEMENT -----------------

@router.post("/acknowledgement")
def acknowledgement_download(req: ERIAcknowledgementRequest, token: str = Depends(get_eri_auth_token)):
    try:
        pdf_bytes = get_acknowledgement(req.pan, req.ackNumber, token)
        # Return PDF directly
        return Response(content=pdf_bytes, media_type="application/pdf")
    except ERIApiError as e:
        raise HTTPException(status_code=400, detail=str(e))
