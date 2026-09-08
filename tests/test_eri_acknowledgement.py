"""Unit tests for app/eri/type2/acknowledgement.py's get_acknowledgement().

Cites: Docs/API_AcknowledgementFlow (1).txt Section 4 (getAcknowledgement API).
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ["ERI_MODE"] = "type2"
os.environ["ERI_ENV"] = "uat"
os.environ["ERI_SW_ID_TYPE2_UAT"] = "SW20014242"
os.environ["ERI_USER_ID_TYPE2_UAT"] = "ERIP013181"
os.environ["ERI_BASE_URL_TYPE2_UAT"] = "https://uatocpservices.incometax.gov.in/iec-uat/uat/eriapi"

import pytest

from app.eri.type2.acknowledgement import get_acknowledgement
from app.eri.exceptions import ERIApiError

# A minimal-but-valid PDF, used as the "real" payload embedded inside the
# Java-serialized wrapper ITD's live endpoint actually returns.
_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\nstartxref\n0\n%%EOF"


@patch("app.eri.type2.acknowledgement.requests.post")
@patch("app.eri.type2.acknowledgement.build_request_envelope")
def test_get_acknowledgement_extracts_pdf_from_malformed_java_serialized_response(
    mock_build_envelope, mock_post
):
    """ITD's live getAcknowledgement endpoint has a confirmed server-side
    bug (2026-09-04, PAN SRGPZ2026C, ARN 116997020040926): on success it
    returns a raw Java-serialized java.util.HashMap (magic bytes
    b"\\xac\\xed\\x00\\x05") wrapping the real PDF bytes, mislabeled with
    Content-Type: application/json -- not a real application/pdf binary
    body, and not valid JSON either. The same malformed shape was found
    independently in the ITR-V PDF ITD emailed the taxpayer directly, so
    this is a genuine upstream bug affecting the API response itself, not
    an artifact of email delivery. get_acknowledgement() must locate the
    embedded PDF by its own %PDF-/%%EOF markers rather than trusting the
    (here, actively wrong) Content-Type header.
    """
    mock_build_envelope.return_value = {"data": "x", "sign": "y", "eriUserId": "ERIP013181"}

    # Simulate the real malformed response: Java serialization header +
    # embedded metadata + the actual PDF bytes + trailing serialization
    # bytes after the PDF's own %%EOF.
    malformed_body = (
        b"\xac\xed\x00\x05ur\x00\x02[B\xac\xf3\x17\xf8\x06\x08T\xe0\x02\x00\x00xp"
        + _MINIMAL_PDF
        + b"\x00\x00trailing_java_bytes"
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.content = malformed_body
    mock_post.return_value = mock_response

    result = get_acknowledgement(pan="SRGPZ2026C", ack_number="116997020040926", auth_token="tok")

    assert result == _MINIMAL_PDF
    assert result.startswith(b"%PDF-")
    assert result.endswith(b"%%EOF")


@patch("app.eri.type2.acknowledgement.requests.post")
@patch("app.eri.type2.acknowledgement.build_request_envelope")
def test_get_acknowledgement_raises_on_real_json_error(mock_build_envelope, mock_post):
    """A genuine error response (no embedded PDF, real JSON body) must
    still raise ERIApiError with the server's code/desc -- the PDF-magic-
    bytes detection must not swallow real error responses."""
    mock_build_envelope.return_value = {"data": "x", "sign": "y", "eriUserId": "ERIP013181"}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    error_body = (
        b'{"messages":[{"code":"EF20038","type":"ERROR",'
        b'"desc":"Invalid Receipt number. Please retry and enter correct '
        b'acknowledgement number.","fieldName":null}],"errors":[],'
        b'"successFlag":false,"header":{"formName":null}}'
    )
    mock_response.content = error_body
    mock_response.json.return_value = {
        "messages": [
            {
                "code": "EF20038",
                "type": "ERROR",
                "desc": "Invalid Receipt number. Please retry and enter correct acknowledgement number.",
                "fieldName": None,
            }
        ],
        "errors": [],
        "successFlag": False,
        "header": {"formName": None},
    }
    mock_post.return_value = mock_response

    with pytest.raises(ERIApiError) as exc_info:
        get_acknowledgement(pan="SRGPZ2026C", ack_number="00000000000000", auth_token="tok")

    assert exc_info.value.code == "EF20038"
