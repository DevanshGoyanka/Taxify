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
    monkeypatch.setenv("ERI_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("ERI_CLIENT_SECRET", "test_client_secret")
    
    headers = eri_headers(auth_token="test_token")
    assert headers["Content-Type"] == "application/json"
    assert headers["clientId"] == "test_client_id"
    assert headers["clientSecret"] == "test_client_secret"
    assert headers["accessMode"] == "API"
    assert headers["authToken"] == "test_token"


def test_eri_headers_missing():
    # Temporarily clean variables
    orig_id = os.environ.pop("ERI_CLIENT_ID", None)
    orig_secret = os.environ.pop("ERI_CLIENT_SECRET", None)
    try:
        with pytest.raises(ValueError):
            eri_headers()
    finally:
        # Restore variables
        if orig_id:
            os.environ["ERI_CLIENT_ID"] = orig_id
        if orig_secret:
            os.environ["ERI_CLIENT_SECRET"] = orig_secret


def test_encrypt_password():
    from app.eri.envelope import encrypt_password
    plain = "Oracle@123"
    key_b64 = "Xuslp8BPWDe0QCF+rLCGZA=="
    expected_cipher_b64 = "E9MVbDJgT9LK5xiEnNbA1A=="
    
    result = encrypt_password(plain, key_b64)
    assert result == expected_cipher_b64

