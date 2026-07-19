import os
import pytest
from unittest.mock import patch
from fastapi import Request, HTTPException
from fastapi.datastructures import Headers

from app.db.models import User
from app.routers.integration import (
    login_eri,
    logout_eri,
    eri_add_client_route,
    eri_validate_client_otp_route,
    eri_register_client_route,
    eri_validate_reg_otp_route
)
from app.schemas.eri import (
    ERILoginRequest,
    ERILogoutRequest,
    ERIAddClientRequest,
    ERIValidateClientOtpRequest,
    ERIRegisterClientRequest,
    ERIValidateRegOtpRequest
)

# Set env variables for test consistency
os.environ["ERI_USER_ID"] = "ERIP013181"
os.environ["ERI_PASSWORD"] = "Oracle@123"
os.environ["ERI_SYMMETRIC_KEY"] = "Xuslp8BPWDe0QCF+rLCGZA=="
os.environ["ERI_CLIENT_ID"] = "4fea04621c7b5660dbb12b959a29b0ee"
os.environ["ERI_CLIENT_SECRET"] = "e754ceb48732c4e197658f76bcc69037"
os.environ["ERI_DSC_SIGNING_MODE"] = "token"


@pytest.fixture
def mock_user():
    return User(id=1, email="test@example.com")


class MockRequest:
    """Simulates FastAPI Request object for extracting headers."""
    def __init__(self, headers_dict: dict):
        self.headers = Headers(headers_dict)


@patch('app.eri.login.eri_login')
def test_eri_login_route(mock_eri_login, mock_user):
    mock_eri_login.return_value = {
        "authToken": "mock_auth_token_ERIP013181",
        "transactionId": "mock_login_tx_12345"
    }
    
    res = login_eri(current_user=mock_user)
    
    assert res["success"] is True
    assert res["authToken"] == "mock_auth_token_ERIP013181"
    assert "transactionId" in res


@patch('app.eri.login.eri_login')
def test_eri_login_route_defaults(mock_eri_login, mock_user):
    mock_eri_login.return_value = {
        "authToken": "mock_auth_token_ERIP013181",
        "transactionId": "mock_login_tx_12345"
    }
    
    res = login_eri(current_user=mock_user)
    
    assert res["success"] is True
    assert res["authToken"] == "mock_auth_token_ERIP013181"


@patch('app.eri.login.eri_logout')
def test_eri_logout_route(mock_eri_logout, mock_user):
    mock_eri_logout.return_value = None
    mock_req = MockRequest({"Authorization": "Bearer mock_token_123"})
    
    res = logout_eri(req=mock_req, current_user=mock_user)
    assert res["success"] is True
    assert "message" in res


def test_eri_logout_route_missing_auth(mock_user):
    mock_req = MockRequest({})
    
    with pytest.raises(HTTPException) as exc_info:
        logout_eri(req=mock_req, current_user=mock_user)
    assert exc_info.value.status_code == 401


@patch('app.eri.add_client.addClient')
def test_eri_add_client_route(mock_add_client, mock_user):
    mock_add_client.return_value = {
        "successFlag": True,
        "transactionId": "mock_add_client_tx_ABCDE1234F",
        "httpStatus": "SUBMITTED"
    }
    req = ERIAddClientRequest(pan="ABCDE1234F", dateOfBirth="1990-01-01", otpSourceFlag="E")
    mock_req = MockRequest({"authToken": "mock_token_123"})
    
    res = eri_add_client_route(req=mock_req, request=req, current_user=mock_user)
    assert res["successFlag"] is True
    assert "transactionId" in res
    assert res["httpStatus"] == "SUBMITTED"


@patch('app.eri.add_client.validateClientOtp')
def test_eri_validate_client_otp_route(mock_validate_client, mock_user):
    mock_validate_client.return_value = {
        "successFlag": True,
        "httpStatus": "ACCEPTED"
    }
    req = ERIValidateClientOtpRequest(
        pan="ABCDE1234F",
        transactionId="tx123",
        otpSourceFlag="E",
        otp="123456",
        validUpto="2027-01-01"
    )
    mock_req = MockRequest({"Authorization": "Bearer mock_token_123"})
    
    res = eri_validate_client_otp_route(req=mock_req, request=req, current_user=mock_user)
    assert res["successFlag"] is True
    assert res["httpStatus"] == "ACCEPTED"


@patch('app.eri.add_client.addRegisterClient')
def test_eri_register_client_route(mock_add_register, mock_user):
    mock_add_register.return_value = {
        "successFlag": True,
        "smsTransactionId": "mock_sms_tx",
        "emailTransactionId": "mock_email_tx",
        "httpStatus": "SUBMITTED"
    }
    req = ERIRegisterClientRequest(
        pan="ABCDE1234F",
        residentialStatusCd="RES",
        firstName="John",
        lastName="Doe",
        dateOfBirth="1990-01-01",
        userGender="M",
        priMobileNum="9876543210",
        priEmailId="john@example.com",
        addrLine1Txt="Flat 101",
        addrLine2Txt="Building A"
    )
    mock_req = MockRequest({"authToken": "mock_token_123"})
    
    res = eri_register_client_route(req=mock_req, request=req, current_user=mock_user)
    assert res["successFlag"] is True
    assert "smsTransactionId" in res
    assert "emailTransactionId" in res


@patch('app.eri.add_client.validateRegOtp')
def test_eri_validate_reg_otp_route(mock_validate_reg, mock_user):
    mock_validate_reg.return_value = {
        "successFlag": True,
        "httpStatus": "ACCEPTED"
    }
    req = ERIValidateRegOtpRequest(
        pan="ABCDE1234F",
        smsTransactionId="sms123",
        emailTransactionId="email123",
        mobileOtp="111111",
        emailOtp="222222",
        validUpto="2027-01-01"
    )
    mock_req = MockRequest({"Authorization": "Bearer mock_token_123"})
    
    res = eri_validate_reg_otp_route(req=mock_req, request=req, current_user=mock_user)
    assert res["successFlag"] is True
    assert res["httpStatus"] == "ACCEPTED"
