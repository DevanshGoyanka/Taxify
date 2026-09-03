import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import base64
import json
import pytest
from app.eri.envelope import build_request_envelope, parse_response_envelope, eri_headers
from app.eri.exceptions import ERIApiError


from unittest.mock import patch

@patch('app.eri.envelope.sign_data')
def test_build_request_envelope(mock_sign_data):
    payload = {"serviceName": "EriLoginService", "entity": "ERIP013181"}
    serialized = json.dumps(payload, separators=(",", ":"))
    base64_data = base64.b64encode(serialized.encode("utf-8")).decode("utf-8")
    mock_sign_data.return_value = (base64.b64encode(b"mock-signature-of-data").decode("utf-8"), base64_data)
    
    payload = {"serviceName": "EriLoginService", "entity": "ERIP013181"}
    eri_user_id = "ERIP013181"
    
    envelope = build_request_envelope(payload, eri_user_id)
    
    assert "data" in envelope
    assert "sign" in envelope
    assert "eriUserId" in envelope
    assert envelope["eriUserId"] == eri_user_id
    
    # Verify data base64 content
    decoded_bytes = base64.b64decode(envelope["data"])
    decoded_payload = json.loads(decoded_bytes.decode("utf-8"))
    assert decoded_payload == payload
    
    # Verify signature base64 content in mock mode
    sig_bytes = base64.b64decode(envelope["sign"])
    assert sig_bytes == b"mock-signature-of-data"


def test_parse_response_envelope_success():
    response = {
        "messages": [
            {
                "code": "EF00000",
                "type": "INFO",
                "desc": "OK",
                "fieldName": None
            }
        ],
        "errors": [],
        "entity": "ERIP013181",
        "autkn": "mock_auth_token"
    }
    
    parsed = parse_response_envelope(response)
    assert parsed == response
    assert parsed["autkn"] == "mock_auth_token"


def test_parse_response_envelope_error():
    response = {
        "messages": [
            {
                "code": "EF500060",
                "type": "ERROR",
                "desc": "Invalid UserId/Password",
                "fieldName": "pass"
            }
        ]
    }
    
    with pytest.raises(ERIApiError) as exc_info:
        parse_response_envelope(response)
        
    assert exc_info.value.code == "EF500060"
    assert exc_info.value.desc == "Invalid UserId/Password"
    assert exc_info.value.field_name == "pass"


def test_eri_headers(monkeypatch):
    """eri_headers() resolves client_id/client_secret via
    get_eri_credentials() (the suffix-aware (ERI_MODE, ERI_ENV) resolver),
    not the unsuffixed ERI_CLIENT_ID/ERI_CLIENT_SECRET this project never
    sets in .env -- found during the filing/submission pipeline audit:
    every Type-2 API call would have unconditionally raised ValueError
    before this fix, since only the suffixed variables ever exist."""
    monkeypatch.setenv("ERI_MODE", "type2")
    monkeypatch.setenv("ERI_ENV", "uat")
    monkeypatch.setenv("ERI_SW_ID_TYPE2_UAT", "SW_TEST")
    monkeypatch.setenv("ERI_CLIENT_ID_TYPE2_UAT", "test_client_id")
    monkeypatch.setenv("ERI_CLIENT_SECRET_TYPE2_UAT", "test_client_secret")

    headers = eri_headers(auth_token="test_token")
    assert headers["Content-Type"] == "application/json"
    assert headers["clientId"] == "test_client_id"
    assert headers["clientSecret"] == "test_client_secret"
    assert headers["accessMode"] == "API"
    assert headers["authToken"] == "test_token"


def test_eri_headers_missing(monkeypatch):
    """Missing suffix-qualified client credentials raise ValueError with a
    message naming the exact suffixed variable required, not the unsuffixed
    (never-set) name the old implementation checked."""
    monkeypatch.setenv("ERI_MODE", "type2")
    monkeypatch.setenv("ERI_ENV", "uat")
    monkeypatch.setenv("ERI_SW_ID_TYPE2_UAT", "SW_TEST")
    monkeypatch.delenv("ERI_CLIENT_ID_TYPE2_UAT", raising=False)
    monkeypatch.delenv("ERI_CLIENT_SECRET_TYPE2_UAT", raising=False)
    with pytest.raises(ValueError, match="ERI_CLIENT_ID_TYPE2_UAT"):
        eri_headers()


def test_encrypt_password():
    from app.eri.envelope import encrypt_password
    plain = "Oracle@123"
    key_b64 = "Xuslp8BPWDe0QCF+rLCGZA=="
    expected_cipher_b64 = "E9MVbDJgT9LK5xiEnNbA1A=="

    result = encrypt_password(plain, key_b64)
    assert result == expected_cipher_b64


# ---------------------------------------------------------------------------
# ERI_DSC_SIGNING_MODE=ngrok safety (found during the filing/submission
# pipeline audit): this mode transmits the full plain payload -- real
# taxpayer PII, and live OTP/EVC values via everify.py -- to an external
# URL for signing. It previously had a hardcoded fallback signer URL
# (one developer's personal ngrok tunnel) and was not forbidden in
# production, unlike the "mock" DSC mode.
# ---------------------------------------------------------------------------

def test_ngrok_signing_mode_requires_explicit_signer_url(monkeypatch):
    from app.eri.envelope import sign_data

    monkeypatch.setenv("ERI_DSC_SIGNING_MODE", "ngrok")
    monkeypatch.delenv("SIGNER_URL", raising=False)
    with pytest.raises(ValueError, match="SIGNER_URL"):
        sign_data('{"pan":"ABCDE1234F"}')


def test_ngrok_dsc_mode_is_forbidden_in_type2_production(monkeypatch):
    from app.eri.config import get_eri_credentials, assert_credentials_at_startup

    monkeypatch.setenv("ERI_MODE", "type2")
    monkeypatch.setenv("ERI_ENV", "production")
    monkeypatch.setenv("ERI_SW_ID_TYPE2_PRODUCTION", "SW_TEST")
    monkeypatch.setenv("ERI_DIGEST_SECRET_KEY_TYPE2_PRODUCTION", "abcdef0123456789")
    monkeypatch.setenv("ERI_DSC_SIGNING_MODE", "ngrok")
    creds = get_eri_credentials()
    assert creds.dsc_signing_mode == "ngrok"
    with pytest.raises(RuntimeError, match="ngrok"):
        assert_credentials_at_startup()


# ---------------------------------------------------------------------------
# validate/submit error shape (found while implementing app/eri/type2/
# validate.py and submit.py): these endpoints' errors[] entries use
# {errCd, errFld, errCtg, asPerItr, asComputed, variance, schId}, not the
# {code, desc, fieldName} shape login/addClient/everify use. Before this
# fix, every validate/submit error collapsed into a generic
# ERIApiError(code="UNKNOWN", desc="Unknown Error"), discarding the
# per-field detail these endpoints exist to surface.
# Cites: API_SubmitFlow_v1.1.pdf Section 4.6 "Response 2: When error in
# validation".
# ---------------------------------------------------------------------------

def test_parse_response_envelope_validate_submit_error_shape():
    response = {
        "serviceName": "EriValidateItr",
        "pan": "ACEPR7859X",
        "header": {"formName": None},
        "messages": [],
        "errors": [
            {
                "errCd": "AssesseeName_001",
                "errFld": "ITR.ITR1.PersonalInfo.AssesseeName",
                "errCtg": "OTH",
                "asPerItr": 0,
                "asComputed": 0,
                "variance": 0,
                "schId": None,
            }
        ],
        "arnNumber": None,
        "id": None,
        "successFlag": False,
        "transactionNo": None,
        "formPath": None,
        "httpStatus": None,
    }

    with pytest.raises(ERIApiError) as exc_info:
        parse_response_envelope(response)

    assert exc_info.value.code == "AssesseeName_001"
    assert exc_info.value.field_name == "ITR.ITR1.PersonalInfo.AssesseeName"
    assert exc_info.value.category == "OTH"
    assert exc_info.value.variance == 0


def test_parse_response_envelope_validate_success_with_false_success_flag():
    """The spec's own 'Validated Successfully' sample carries
    successFlag: false with empty messages/errors -- a documented anomaly,
    not something parse_response_envelope should treat as failure. Only
    non-empty errors[]/ERROR-typed messages[] entries should raise."""
    response = {
        "serviceName": "EriValidateItr",
        "pan": "ACEPR7859X",
        "header": {"formName": None},
        "messages": [],
        "errors": [],
        "arnNumber": None,
        "id": None,
        "successFlag": False,
        "transactionNo": "ITR000000004862",
        "httpStatus": None,
    }

    parsed = parse_response_envelope(response)
    assert parsed == response


def test_parse_response_envelope_legacy_error_shape_still_works():
    """Regression fence: the login/addClient/everify {code,desc,fieldName}
    errors[] shape must still be recognized after adding the errCd/errFld
    branch."""
    response = {
        "messages": [],
        "errors": [
            {"code": "EF500060", "desc": "Invalid UserId/Password", "fieldName": "pass"}
        ],
    }

    with pytest.raises(ERIApiError) as exc_info:
        parse_response_envelope(response)

    assert exc_info.value.code == "EF500060"
    assert exc_info.value.field_name == "pass"


def test_mock_dsc_mode_still_forbidden_in_type2_production(monkeypatch) -> None:
    """Regression fence: the new ngrok check must not have disturbed the
    existing mock-mode production guard."""
    from app.eri.config import assert_credentials_at_startup

    monkeypatch.setenv("ERI_MODE", "type2")
    monkeypatch.setenv("ERI_ENV", "production")
    monkeypatch.setenv("ERI_SW_ID_TYPE2_PRODUCTION", "SW_TEST")
    monkeypatch.setenv("ERI_DIGEST_SECRET_KEY_TYPE2_PRODUCTION", "abcdef0123456789")
    monkeypatch.setenv("ERI_DSC_SIGNING_MODE", "mock")
    with pytest.raises(RuntimeError, match="mock"):
        assert_credentials_at_startup()

