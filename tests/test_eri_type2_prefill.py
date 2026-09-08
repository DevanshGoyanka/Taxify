"""Unit tests for app/eri/type2/prefill.py, covering bugs found and fixed
during live ITD Type-2 UAT testing against PAN GOYPT2026A / AY 2025
(2026-09-04). See Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md for the full
trace of how each of these was diagnosed against the real gateway.
"""
from __future__ import annotations

import base64
import json
import os
from unittest.mock import MagicMock, patch

os.environ["ERI_MODE"] = "type2"
os.environ["ERI_ENV"] = "uat"
os.environ["ERI_SW_ID_TYPE2_UAT"] = "SW20014242"
os.environ["ERI_USER_ID_TYPE2_UAT"] = "ERIP013181"
os.environ["ERI_BASE_URL_TYPE2_UAT"] = "https://uatocpservices.incometax.gov.in/iec-uat/uat/eriapi"

# Arbitrary, not the real ERI symmetric key -- these tests only need a
# self-consistent local encrypt(fixture)/decrypt(code under test) round
# trip, never a live call, so any 16-byte AES-128 key works.
_FAKE_TEST_SYMMETRIC_KEY = "2fkYangyhElzB/IrFCif4w=="

from app.eri.type2.prefill import request_prefill_otp, get_prefill_data, validate_prefill_schema
from app.eri.exceptions import ERIApiError


@patch("app.eri.type2.prefill.requests.post")
@patch("app.eri.type2.prefill.build_request_envelope")
def test_request_prefill_otp_uses_eriprefill_service_name(mock_build_envelope, mock_post):
    """The spec's own table claims serviceName 'EriGetPrefill' for this
    endpoint, but the real gateway rejects that with
    errCd=EF40000/fieldName=serviceName -- 'EriPrefill' is what it actually
    requires (confirmed via a live call)."""
    mock_build_envelope.return_value = {"data": "x", "sign": "y", "eriUserId": "ERIP013181"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "messages": [{"code": "EF40010", "type": "REMARK", "desc": "OTP has been sent successfully.", "fieldName": None}],
        "errors": [],
        "successFlag": True,
        "smsTransactionId": "FOS1",
        "emailTransactionId": "FOS2",
    }
    mock_post.return_value = mock_response

    request_prefill_otp("GOYPT2026A", "2025", "E", "tok")

    payload_sent = mock_build_envelope.call_args[0][0]
    assert payload_sent["serviceName"] == "EriPrefill"


@patch("app.eri.type2.prefill.requests.post")
@patch("app.eri.type2.prefill.build_request_envelope")
def test_get_prefill_data_sends_separate_sms_and_email_transaction_ids(mock_build_envelope, mock_post):
    """The spec documents a single 'transactionId' field, but the real
    gateway wants the two IDs requestPrefillOTP actually returns
    (smsTransactionId/emailTransactionId) as separate fields -- a single
    'transactionId' reproducibly failed with errCd=EF40000 'JSON data
    invalid' against a live call, regardless of which ID was used."""
    mock_build_envelope.return_value = {"data": "x", "sign": "y", "eriUserId": "ERIP013181"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "messages": [],
        "errors": [],
        "successFlag": True,
        "prefill": _encrypted_prefill_fixture(),
    }
    mock_post.return_value = mock_response

    with patch.dict(os.environ, {"ERI_SYMMETRIC_KEY": _FAKE_TEST_SYMMETRIC_KEY}):
        get_prefill_data(
            pan="GOYPT2026A",
            assessment_year="2025",
            auth_token="tok",
            otp_source_flag="E",
            sms_transaction_id="FOS_SMS",
            mobile_otp="111111",
            email_transaction_id="FOS_EMAIL",
            email_otp="222222",
        )

    payload_sent = mock_build_envelope.call_args[0][0]
    assert payload_sent["smsTransactionId"] == "FOS_SMS"
    assert payload_sent["emailTransactionId"] == "FOS_EMAIL"
    assert "transactionId" not in payload_sent


@patch("app.eri.type2.prefill.requests.post")
@patch("app.eri.type2.prefill.build_request_envelope")
def test_get_prefill_data_reads_lowercase_prefill_key(mock_build_envelope, mock_post):
    """The real response key is lowercase 'prefill', not 'Prefill' -- that
    mismatch alone previously treated even a genuinely successful response
    as an error ('prefill attribute is missing')."""
    mock_build_envelope.return_value = {"data": "x", "sign": "y", "eriUserId": "ERIP013181"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "messages": [],
        "errors": [],
        "successFlag": True,
        "Prefill": "wrong-cased-key-should-be-ignored",
        "prefill": _encrypted_prefill_fixture(),
    }
    mock_post.return_value = mock_response

    with patch.dict(os.environ, {"ERI_SYMMETRIC_KEY": _FAKE_TEST_SYMMETRIC_KEY}):
        result = get_prefill_data(
            pan="GOYPT2026A",
            assessment_year="2025",
            auth_token="tok",
            otp_source_flag="E",
            sms_transaction_id="FOS_SMS",
            mobile_otp="111111",
            email_transaction_id="FOS_EMAIL",
            email_otp="222222",
        )
    assert result == {"personalInfo": {"name": "Test"}}


def test_validate_prefill_schema_finds_the_schema_file():
    """app/eri/type2/prefill.py -> repo root needs THREE '..' levels
    (type2 -> eri -> app -> root); the previous two-level path resolved to
    app/Docs/... (never existed), raising FileNotFoundError on every call,
    including a genuinely successful getPrefill response.

    An empty dict validates cleanly against this schema (no top-level
    properties are required) -- the point of this test is only that the
    schema file itself is found and loaded without FileNotFoundError, not
    that {} is a meaningful prefill payload.
    """
    validate_prefill_schema({})  # must not raise FileNotFoundError


@patch("app.eri.type2.prefill.requests.post")
@patch("app.eri.type2.prefill.build_request_envelope")
def test_get_prefill_data_schema_mismatch_is_non_fatal(mock_build_envelope, mock_post):
    """A real ITD response routinely sets optional/inapplicable form
    sections (e.g. scheduleCFL when there are no carried-forward losses) to
    null where the published schema declares type object -- the schema is
    out of sync with the live server, not a defect in the response. Since a
    real taxpayer will almost always have many such null sections, this
    must not raise and lose the already-successfully-decrypted data."""
    mock_build_envelope.return_value = {"data": "x", "sign": "y", "eriUserId": "ERIP013181"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    # A minimal dict that will legitimately fail schema validation (missing
    # nearly everything the schema expects) but must still be RETURNED, not
    # raised as ERIApiError.
    mock_response.json.return_value = {
        "messages": [],
        "errors": [],
        "successFlag": True,
        "prefill": _encrypt(json.dumps({"personalInfo": {"name": "Test"}})),
    }
    mock_post.return_value = mock_response

    with patch.dict(os.environ, {"ERI_SYMMETRIC_KEY": _FAKE_TEST_SYMMETRIC_KEY}):
        result = get_prefill_data(
            pan="GOYPT2026A",
            assessment_year="2025",
            auth_token="tok",
            otp_source_flag="E",
            sms_transaction_id="FOS_SMS",
            mobile_otp="111111",
            email_transaction_id="FOS_EMAIL",
            email_otp="222222",
        )
    # Must not raise ERIApiError("SCHEMA_ERROR", ...) -- the data is
    # returned regardless of the schema mismatch.
    assert result == {"personalInfo": {"name": "Test"}}


def _encrypt(plaintext: str) -> str:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as crypto_padding

    key = base64.b64decode(_FAKE_TEST_SYMMETRIC_KEY)
    padder = crypto_padding.PKCS7(128).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ct).decode("utf-8")


def _encrypted_prefill_fixture() -> str:
    return _encrypt(json.dumps({"personalInfo": {"name": "Test"}}))
