"""Tests for app/routers/filing.py's Type-2 API submission path
(_submit_via_type2_api), added when /submit was wired to actually call
validateItr/submitItr for ERI_MODE=type2 instead of returning
501 "deferred until the next implementation phase".
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.eri.exceptions import ERIApiError
from app.routers.filing import SubmitFilingRequest, submit_via_portal


def _fake_official_json(form_key: str, pan: str, return_file_sec: int) -> dict:
    return {
        "ITR": {
            form_key: {
                "PersonalInfo": {"PAN": pan},
                "FilingStatus": {"ReturnFileSec": return_file_sec},
            }
        }
    }


def _run_submit(itr_type: str = "ITR-4"):
    return submit_via_portal(
        client_id="1",
        ay="2026-27",
        itr_type=itr_type,
        request=SubmitFilingRequest(verification_mode="LATER"),
        current_user=SimpleNamespace(id=1),
        db=MagicMock(),
    )


@patch("app.eri.type2.submit.submit_itr")
@patch("app.eri.type2.validate.validate_itr")
@patch("app.eri.type2.login.eri_login")
@patch("app.routers.filing.upsert_filing_record")
@patch("app.routers.filing.log_filing_action")
@patch("app.routers.filing.produce_itd_json")
@patch("app.routers.filing._draft")
@patch("app.routers.filing.resolve_owned_client")
@patch("app.routers.filing.get_eri_credentials")
def test_type2_submit_validates_then_submits_with_correct_fields(
    mock_creds, mock_resolve_client, mock_draft, mock_produce_json,
    mock_log, mock_upsert, mock_login, mock_validate, mock_submit,
):
    mock_creds.return_value = SimpleNamespace(mode="type2", environment="uat")
    mock_resolve_client.return_value = SimpleNamespace(id=42, pan="GOYPT2026A")
    mock_draft.return_value = {"form": "ITR-4"}
    mock_produce_json.return_value = _fake_official_json("ITR4", "GOYPT2026A", 11)
    mock_login.return_value = {"authToken": "tok123"}
    mock_validate.return_value = {"successFlag": False, "errors": [], "transactionNo": "T1"}
    mock_submit.return_value = {"successFlag": True, "arnNumber": "111202010240326", "transactionNo": "T2"}
    mock_upsert.return_value = SimpleNamespace(id=7)

    res = _run_submit("ITR-4")

    assert res["success"] is True
    assert res["arnNumber"] == "111202010240326"
    assert res["filing_id"] == 7

    # validateItr must be called before submitItr, with matching fields.
    validate_kwargs = mock_validate.call_args.kwargs
    submit_kwargs = mock_submit.call_args.kwargs
    assert validate_kwargs["pan"] == "GOYPT2026A"
    assert validate_kwargs["form_code"] == "4"
    assert validate_kwargs["ay"] == "2026"  # bare YYYY, not Taxify's YYYY-YY
    assert validate_kwargs["filing_type_cd"] == "O"  # ReturnFileSec 11 -> Original
    assert validate_kwargs["income_tax_sec_cd"] == "11"
    assert validate_kwargs["auth_token"] == "tok123"
    assert submit_kwargs["pan"] == "GOYPT2026A"

    mock_upsert.assert_called_once()
    assert mock_upsert.call_args.kwargs["acknowledgement_number"] == "111202010240326"
    assert mock_upsert.call_args.kwargs["status"] == "submitted"


@patch("app.eri.type2.submit.submit_itr")
@patch("app.eri.type2.validate.validate_itr")
@patch("app.eri.type2.login.eri_login")
@patch("app.routers.filing.produce_itd_json")
@patch("app.routers.filing._draft")
@patch("app.routers.filing.resolve_owned_client")
@patch("app.routers.filing.get_eri_credentials")
def test_type2_submit_revised_return_file_sec_maps_to_R(
    mock_creds, mock_resolve_client, mock_draft, mock_produce_json,
    mock_login, mock_validate, mock_submit,
):
    """ReturnFileSec 17 (139(5) revised) must map to filingTypeCd 'R', not
    the default 'O' every other supported section uses."""
    mock_creds.return_value = SimpleNamespace(mode="type2", environment="uat")
    mock_resolve_client.return_value = SimpleNamespace(id=42, pan="GOYPT2026A")
    mock_draft.return_value = {"form": "ITR-1"}
    mock_produce_json.return_value = _fake_official_json("ITR1", "GOYPT2026A", 17)
    mock_login.return_value = {"authToken": "tok123"}
    mock_validate.return_value = {"successFlag": False, "errors": []}
    mock_submit.return_value = {"successFlag": True, "arnNumber": "ARN1"}

    with patch("app.routers.filing.upsert_filing_record") as mock_upsert, \
         patch("app.routers.filing.log_filing_action"):
        mock_upsert.return_value = SimpleNamespace(id=1)
        _run_submit("ITR-1")

    assert mock_validate.call_args.kwargs["filing_type_cd"] == "R"
    assert mock_validate.call_args.kwargs["income_tax_sec_cd"] == "17"
    assert mock_validate.call_args.kwargs["form_code"] == "1"


@patch("app.routers.filing.resolve_owned_client")
@patch("app.routers.filing.get_eri_credentials")
def test_type2_submit_rejects_itr2(mock_creds, mock_resolve_client):
    mock_creds.return_value = SimpleNamespace(mode="type2", environment="uat")
    with pytest.raises(HTTPException) as caught:
        _run_submit("ITR-2")
    assert caught.value.status_code == 501
    mock_resolve_client.assert_not_called()


@patch("app.eri.type2.validate.validate_itr")
@patch("app.eri.type2.login.eri_login")
@patch("app.routers.filing.produce_itd_json")
@patch("app.routers.filing._draft")
@patch("app.routers.filing.resolve_owned_client")
@patch("app.routers.filing.get_eri_credentials")
def test_type2_submit_stops_at_validate_error_without_calling_submit(
    mock_creds, mock_resolve_client, mock_draft, mock_produce_json,
    mock_login, mock_validate,
):
    """A validateItr rejection must surface as a 422 and must NOT proceed
    to submitItr -- an invalid return must never actually be filed."""
    mock_creds.return_value = SimpleNamespace(mode="type2", environment="uat")
    mock_resolve_client.return_value = SimpleNamespace(id=42, pan="GOYPT2026A")
    mock_draft.return_value = {"form": "ITR-4"}
    mock_produce_json.return_value = _fake_official_json("ITR4", "GOYPT2026A", 11)
    mock_login.return_value = {"authToken": "tok123"}
    mock_validate.side_effect = ERIApiError(code="DOB_001", desc="OTH", field_name="ITR.ITR1.PersonalInfo.DOB")

    with patch("app.eri.type2.submit.submit_itr") as mock_submit, \
         patch("app.routers.filing.log_filing_action"):
        with pytest.raises(HTTPException) as caught:
            _run_submit("ITR-4")
        mock_submit.assert_not_called()

    assert caught.value.status_code == 422
    assert "DOB_001" in str(caught.value.detail)
