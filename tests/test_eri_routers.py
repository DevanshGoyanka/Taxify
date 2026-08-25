"""ERI Type-2 router tests aligned with the Dual-Mode ERI Integration Plan.

Phase 1 of the ERI plan moved the Type-2 modules to ``app/eri/type2/`` and
added a mode guard (``_require_type2_mode``) so the Type-2 routes return
HTTP 503 when ``ERI_MODE != "type2"``. These tests exercise the Type-2
route handlers in ``ERI_MODE=type2`` (guard passes → patched Type-2
functions are called) and assert the 503 mode-guard behaviour in
``ERI_MODE=type3``.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException, Request
from fastapi.datastructures import Headers
from unittest.mock import patch

from app.db.models import User
from app.routers.integration import (
    eri_add_client_route,
    eri_validate_client_otp_route,
    eri_validate_reg_otp_route,
    login_eri,
    logout_eri,
    eri_register_client_route,
)
from app.schemas.eri import (
    ERIAddClientRequest,
    ERIRegisterClientRequest,
    ERIValidateClientOtpRequest,
    ERIValidateRegOtpRequest,
)

# Suffix-qualified Type-2 UAT credentials so ``get_eri_credentials()``
# resolves cleanly and the ``_require_type2_mode`` guard passes. Per the
# ERI plan §3.1, all four credential sets live in .env under suffix-
# qualified names; the tests mirror that contract.
os.environ["ERI_MODE"] = "type2"
os.environ["ERI_ENV"] = "uat"
os.environ["ERI_SW_ID_TYPE2_UAT"] = "SW20014242"
os.environ["ERI_DIGEST_SECRET_KEY_TYPE2_UAT"] = "4448ffc0cec1a25d"
os.environ["ERI_DIGEST_ITERATIONS_TYPE2_UAT"] = "1344"
os.environ["ERI_CLIENT_ID_TYPE2_UAT"] = "test_client_id"
os.environ["ERI_CLIENT_SECRET_TYPE2_UAT"] = "test_client_secret"
os.environ["ERI_USER_ID_TYPE2_UAT"] = "TEST_ERI_USER_ID"
os.environ["ERI_PASSWORD_TYPE2_UAT"] = "test_password"
os.environ["ERI_BASE_URL_TYPE2_UAT"] = "https://uatocpservices.incometax.gov.in/iec-uat/uat/eriapi"
os.environ["ERI_DSC_SIGNING_MODE"] = "token"


@pytest.fixture
def mock_user() -> User:
    """Return a minimal authenticated user for route dependencies."""
    return User(id=1, email="test@example.com")


class MockRequest:
    """Simulates the FastAPI ``Request`` object for header extraction."""

    def __init__(self, headers_dict: dict) -> None:
        """Initialize with a headers mapping."""
        self.headers = Headers(headers_dict)


@patch("app.eri.type2.login.eri_login")
def test_eri_login_route(mock_eri_login, mock_user) -> None:
    """Login route returns the patched ERI login payload."""
    mock_eri_login.return_value = {
        "authToken": "mock_auth_token_ERIP013181",
        "transactionId": "mock_login_tx_12345",
    }

    res = login_eri(current_user=mock_user)

    assert res["success"] is True
    assert res["authToken"] == "mock_auth_token_ERIP013181"
    assert "transactionId" in res


@patch("app.eri.type2.login.eri_login")
def test_eri_login_route_defaults(mock_eri_login, mock_user) -> None:
    """Login route returns success with a default authToken."""
    mock_eri_login.return_value = {
        "authToken": "mock_auth_token_ERIP013181",
        "transactionId": "mock_login_tx_12345",
    }

    res = login_eri(current_user=mock_user)

    assert res["success"] is True
    assert res["authToken"] == "mock_auth_token_ERIP013181"


@patch("app.eri.type2.login.eri_logout")
def test_eri_logout_route(mock_eri_logout, mock_user) -> None:
    """Logout route returns success when an auth token is supplied."""
    mock_eri_logout.return_value = None
    mock_req = MockRequest({"Authorization": "Bearer mock_token_123"})

    res = logout_eri(req=mock_req, current_user=mock_user)
    assert res["success"] is True
    assert "message" in res


def test_eri_logout_route_missing_auth(mock_user) -> None:
    """Logout without an auth token raises 401 in Type-2 mode."""
    mock_req = MockRequest({})

    with pytest.raises(HTTPException) as exc_info:
        logout_eri(req=mock_req, current_user=mock_user)
    assert exc_info.value.status_code == 401


@patch("app.eri.type2.add_client.addClient")
def test_eri_add_client_route(mock_add_client, mock_user) -> None:
    """Add-client route forwards the patched payload."""
    mock_add_client.return_value = {
        "successFlag": True,
        "transactionId": "mock_add_client_tx_ABCDE1234F",
        "httpStatus": "SUBMITTED",
    }
    req = ERIAddClientRequest(pan="ABCDE1234F", dateOfBirth="1990-01-01", otpSourceFlag="E")
    mock_req = MockRequest({"authToken": "mock_token_123"})

    res = eri_add_client_route(req=mock_req, request=req, current_user=mock_user)
    assert res["successFlag"] is True
    assert "transactionId" in res
    assert res["httpStatus"] == "SUBMITTED"


@patch("app.eri.type2.add_client.validateClientOtp")
def test_eri_validate_client_otp_route(mock_validate_client, mock_user) -> None:
    """Validate-client-OTP route forwards the patched payload."""
    mock_validate_client.return_value = {
        "successFlag": True,
        "httpStatus": "ACCEPTED",
    }
    req = ERIValidateClientOtpRequest(
        pan="ABCDE1234F",
        transactionId="tx123",
        otpSourceFlag="E",
        otp="123456",
        validUpto="2027-01-01",
    )
    mock_req = MockRequest({"Authorization": "Bearer mock_token_123"})

    res = eri_validate_client_otp_route(req=mock_req, request=req, current_user=mock_user)
    assert res["successFlag"] is True
    assert res["httpStatus"] == "ACCEPTED"


@patch("app.eri.type2.add_client.addRegisterClient")
def test_eri_register_client_route(mock_add_register, mock_user) -> None:
    """Register-client route forwards the patched payload."""
    mock_add_register.return_value = {
        "successFlag": True,
        "smsTransactionId": "mock_sms_tx",
        "emailTransactionId": "mock_email_tx",
        "httpStatus": "SUBMITTED",
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
        addrLine2Txt="Building A",
    )
    mock_req = MockRequest({"authToken": "mock_token_123"})

    res = eri_register_client_route(req=mock_req, request=req, current_user=mock_user)
    assert res["successFlag"] is True
    assert "smsTransactionId" in res
    assert "emailTransactionId" in res


@patch("app.eri.type2.add_client.validateRegOtp")
def test_eri_validate_reg_otp_route(mock_validate_reg, mock_user) -> None:
    """Validate-registration-OTP route forwards the patched payload."""
    mock_validate_reg.return_value = {
        "successFlag": True,
        "httpStatus": "ACCEPTED",
    }
    req = ERIValidateRegOtpRequest(
        pan="ABCDE1234F",
        smsTransactionId="sms123",
        emailTransactionId="email123",
        mobileOtp="111111",
        emailOtp="222222",
        validUpto="2027-01-01",
    )
    mock_req = MockRequest({"Authorization": "Bearer mock_token_123"})

    res = eri_validate_reg_otp_route(req=mock_req, request=req, current_user=mock_user)
    assert res["successFlag"] is True
    assert res["httpStatus"] == "ACCEPTED"


# ── Mode-guard (Phase 1 B2): Type-2 routes return 503 in Type-3 mode ───────


def test_type2_routes_return_503_in_type3_mode(mock_user, monkeypatch: pytest.MonkeyPatch) -> None:
    """Per ERI plan §B2: Type-2 routes must 503 when ERI_MODE != type2."""
    monkeypatch.setenv("ERI_MODE", "type3")
    monkeypatch.setenv("ERI_ENV", "uat")
    monkeypatch.setenv("ERI_SW_ID_TYPE3_UAT", "SW20014122")
    monkeypatch.setenv("ERI_DIGEST_SECRET_KEY_TYPE3_UAT", "d96d4ce17e20a6ba")
    monkeypatch.setenv("ERI_DIGEST_ITERATIONS_TYPE3_UAT", "1038")

    with pytest.raises(HTTPException) as exc_info:
        login_eri(current_user=mock_user)
    assert exc_info.value.status_code == 503
    assert "Type-2" in exc_info.value.detail
