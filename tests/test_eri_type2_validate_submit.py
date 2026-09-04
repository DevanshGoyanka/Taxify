"""Unit tests for app/eri/type2/validate.py and submit.py's payload
construction and URL/serviceName routing.

Cites: Docs/API_SubmitFlow_v1.1.pdf Section 4 (validateItr/submitItr APIs)
-- both endpoints share an identical request/response shape and only
differ in serviceName ("EriValidateItr"/"EriItrSubmit") and the URL suffix
("/validate"/"/submit").
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ["ERI_MODE"] = "type2"
os.environ["ERI_ENV"] = "uat"
os.environ["ERI_SW_ID_TYPE2_UAT"] = "SW20014242"
os.environ["ERI_USER_ID_TYPE2_UAT"] = "ERIP013181"
os.environ["ERI_BASE_URL_TYPE2_UAT"] = "https://uatocpservices.incometax.gov.in/iec-uat/uat/eriapi"

from app.eri.type2.validate import build_itr_payload, validate_itr
from app.eri.type2.submit import submit_itr
from app.eri.exceptions import ERIApiError


def test_build_itr_payload_shape():
    payload = build_itr_payload(
        pan="ABCDE1234F",
        form_name="ITR-1",
        form_code="1",
        ay="2026",
        filing_type_cd="O",
        filing_mode="OF",
        income_tax_sec_cd="11",
        submitted_by="ERI",
        form_data_json='{"ITR":{"ITR1":{}}}',
        service_name="EriValidateItr",
    )

    assert payload["serviceName"] == "EriValidateItr"
    assert payload["pan"] == "ABCDE1234F"
    # formData is base64-encoded JSON, not a plain JSON string -- confirmed
    # live (2026-09-04): a plain-string formData was rejected with
    # errCd=EF500140; see build_itr_payload()'s own docstring.
    import base64
    assert base64.b64decode(payload["formData"]).decode("utf-8") == '{"ITR":{"ITR1":{}}}'
    header = payload["header"]
    assert header["formName"] == "ITR-1"
    assert header["formCode"] == "1"
    assert header["mimeType"] == "json"
    assert header["entityNum"] == "ABCDE1234F"
    assert header["entityType"] == "p"
    assert header["ay"] == "2026"
    assert header["filingTypeCd"] == "O"
    assert header["filingMode"] == "OF"
    assert header["incomeTaxSecCd"] == "11"
    assert header["submittedBy"] == "ERI"
    # createdBy defaults to the configured ERI user ID when not supplied
    assert header["createdBy"] == "ERIP013181"
    # Mandatory per ITD's onboarding email (not shown in the spec PDF's own
    # sample tables) -- every API call must carry timeStamp in the signed
    # payload, matching login.py/add_client.py/everify.py's existing pattern.
    assert "timeStamp" in payload
    assert payload["timeStamp"].endswith("Z")


def test_build_itr_payload_created_by_override():
    payload = build_itr_payload(
        pan="ABCDE1234F",
        form_name="ITR-4",
        form_code="4",
        ay="2026",
        filing_type_cd="R",
        filing_mode="OF",
        income_tax_sec_cd="17",
        submitted_by="ERI",
        form_data_json="{}",
        created_by="SW28450842",
        service_name="EriItrSubmit",
    )
    assert payload["header"]["createdBy"] == "SW28450842"
    assert payload["header"]["filingTypeCd"] == "R"
    assert payload["header"]["incomeTaxSecCd"] == "17"


@patch("app.eri.type2.validate.requests.post")
@patch("app.eri.type2.validate.build_request_envelope")
def test_validate_itr_hits_validate_endpoint(mock_build_envelope, mock_post):
    mock_build_envelope.return_value = {"data": "x", "sign": "y", "eriUserId": "ERIP013181"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "messages": [],
        "errors": [],
        "successFlag": False,
        "transactionNo": "ITR000000004862",
    }
    mock_post.return_value = mock_response

    res = validate_itr(
        pan="ABCDE1234F",
        form_name="ITR-1",
        form_code="1",
        ay="2026",
        filing_type_cd="O",
        filing_mode="OF",
        income_tax_sec_cd="11",
        submitted_by="ERI",
        form_data_json="{}",
        auth_token="tok",
    )

    assert res["transactionNo"] == "ITR000000004862"
    called_url = mock_post.call_args[0][0]
    assert called_url.endswith("/validate")
    # The payload signed/enveloped must carry the Validate serviceName.
    payload_sent = mock_build_envelope.call_args[0][0]
    assert payload_sent["serviceName"] == "EriValidateItr"


@patch("app.eri.type2.submit.requests.post")
@patch("app.eri.type2.submit.build_request_envelope")
def test_submit_itr_hits_submit_endpoint(mock_build_envelope, mock_post):
    mock_build_envelope.return_value = {"data": "x", "sign": "y", "eriUserId": "ERIP013181"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "messages": [],
        "errors": [],
        "successFlag": True,
        "arnNumber": "111202010240326",
    }
    mock_post.return_value = mock_response

    res = submit_itr(
        pan="ABCDE1234F",
        form_name="ITR-1",
        form_code="1",
        ay="2026",
        filing_type_cd="O",
        filing_mode="OF",
        income_tax_sec_cd="11",
        submitted_by="ERI",
        form_data_json="{}",
        auth_token="tok",
    )

    assert res["arnNumber"] == "111202010240326"
    called_url = mock_post.call_args[0][0]
    assert called_url.endswith("/submit")
    payload_sent = mock_build_envelope.call_args[0][0]
    assert payload_sent["serviceName"] == "EriItrSubmit"


@patch("app.eri.type2.validate.requests.post")
@patch("app.eri.type2.validate.build_request_envelope")
def test_validate_itr_raises_on_field_error(mock_build_envelope, mock_post):
    """A validate response carrying an errCd/errFld entry raises ERIApiError
    with the field detail intact (exercises the parse_response_envelope fix
    end-to-end through validate_itr)."""
    mock_build_envelope.return_value = {"data": "x", "sign": "y", "eriUserId": "ERIP013181"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "messages": [],
        "errors": [
            {
                "errCd": "DOB_001",
                "errFld": "ITR.ITR1.PersonalInfo.DOB",
                "errCtg": "OTH",
                "asPerItr": 0,
                "asComputed": 0,
                "variance": 0,
                "schId": None,
            }
        ],
        "successFlag": False,
    }
    mock_post.return_value = mock_response

    try:
        validate_itr(
            pan="ABCDE1234F",
            form_name="ITR-1",
            form_code="1",
            ay="2026",
            filing_type_cd="O",
            filing_mode="OF",
            income_tax_sec_cd="11",
            submitted_by="ERI",
            form_data_json="{}",
            auth_token="tok",
        )
        assert False, "expected ERIApiError"
    except ERIApiError as exc:
        assert exc.code == "DOB_001"
        assert exc.field_name == "ITR.ITR1.PersonalInfo.DOB"
