"""Section 139(1) stops being available once the due date has gone.

After the due date an unfiled return is belated under 139(4) and one that was
already filed can only be corrected as revised under 139(5).  The ITD portal
enforces this by quietly dropping the affected forms from its ITR list rather
than reporting an error, so the rule has to be caught before a return reaches
the portal.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

import app.engine.filing_gateway_v2 as gateway
from app.engine.common.due_dates import (
    applicable_filing_section,
    filing_section_due_date_error,
    is_due_date_passed,
)
from app.filing_automation.uploader import (
    _assert_on_file_itr_route,
    _filing_section_from_json,
    _filing_section_pattern,
    _log_json_identity,
)

from tests.test_filing_gateway_v2 import _filing_ready_draft

ON_DUE_DATE = date(2026, 7, 31)
DAY_AFTER = date(2026, 8, 1)


def test_due_date_is_not_passed_on_the_due_date_itself() -> None:
    """Filing on 31 July is still on time — the rule is strictly "after"."""
    assert is_due_date_passed("ITR-1", "2026-27", ON_DUE_DATE) is False
    assert is_due_date_passed("ITR-1", "2026-27", DAY_AFTER) is True


def test_itr4_keeps_a_later_due_date() -> None:
    """ITR-3/ITR-4 run to 31 August, so 1 August is still on time for them."""
    assert is_due_date_passed("ITR-4", "2026-27", DAY_AFTER) is False
    assert is_due_date_passed("ITR-4", "2026-27", date(2026, 9, 1)) is True


def test_unknown_form_is_not_treated_as_overdue() -> None:
    """An unknown due date is not evidence that the due date passed."""
    assert is_due_date_passed("ITR-9", "2026-27", date(2030, 1, 1)) is False


@pytest.mark.parametrize("section", ["139(4)", "139(5)", "142(1)", "148", "153C", "139(9)", "119(2)(b)"])
def test_only_139_1_is_invalidated_by_the_due_date(section: str) -> None:
    """The notice-driven sections are triggered by the department, not the calendar."""
    assert filing_section_due_date_error(section, "ITR-1", "2026-27", DAY_AFTER) is None


def test_139_1_after_the_due_date_names_both_remedies() -> None:
    """The message must say which section to use instead, either way."""
    message = filing_section_due_date_error("139(1)", "ITR-1", "2026-27", DAY_AFTER)
    assert message is not None
    assert "2026-07-31" in message
    assert "139(4)" in message and "139(5)" in message


def test_139_1_on_or_before_the_due_date_is_accepted() -> None:
    assert filing_section_due_date_error("139(1)", "ITR-1", "2026-27", ON_DUE_DATE) is None


def test_applicable_section_follows_the_date_and_whether_it_was_filed() -> None:
    assert applicable_filing_section("ITR-1", "2026-27", on_date=ON_DUE_DATE) == "139(1)"
    assert applicable_filing_section("ITR-1", "2026-27", on_date=DAY_AFTER) == "139(4)"
    # A return already on record can only be corrected, never re-filed.
    assert applicable_filing_section(
        "ITR-1", "2026-27", original_return_filed=True, on_date=ON_DUE_DATE
    ) == "139(5)"
    assert applicable_filing_section(
        "ITR-1", "2026-27", original_return_filed=True, on_date=DAY_AFTER
    ) == "139(5)"


def test_gateway_blocks_139_1_declared_after_the_due_date() -> None:
    """The draft's own verification date is what the section is judged against."""
    draft = _filing_ready_draft()
    draft.filing.filingSection = "139(1)"
    draft.verification.date = "2026-08-01"

    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.generate_cbdt_json(draft)

    assert caught.value.message == (
        "The filing section is no longer available — the due date has passed."
    )
    assert "139(4)" in caught.value.errors[0]


def test_gateway_accepts_a_belated_return_after_the_due_date() -> None:
    draft = _filing_ready_draft()
    draft.filing.filingSection = "139(4)"
    draft.verification.date = "2026-08-01"

    official, _ = gateway.generate_cbdt_json(draft)

    assert official["ITR"]["ITR1"]["FilingStatus"]["ReturnFileSec"] == 12


def test_gateway_accepts_a_revised_return_after_the_due_date() -> None:
    draft = _filing_ready_draft()
    draft.filing.filingSection = "139(5)"
    draft.filing.returnType = "REVISED"
    draft.filing.originalAcknowledgementNumber = "123456789012345"
    draft.filing.originalFilingDate = "2026-07-15"
    draft.verification.date = "2026-08-01"

    official, _ = gateway.generate_cbdt_json(draft)

    filing_status = official["ITR"]["ITR1"]["FilingStatus"]
    assert filing_status["ReturnFileSec"] == 17
    assert filing_status["ReceiptNo"] == "123456789012345"
    assert filing_status["OrigRetFiledDate"] == "2026-07-15"


def test_uploader_reads_the_filing_section_out_of_the_generated_json(tmp_path) -> None:
    """The portal's Filing Type comes from the artifact actually being uploaded."""
    path = tmp_path / "belated.json"
    path.write_text(
        json.dumps({"ITR": {"ITR1": {"FilingStatus": {"ReturnFileSec": 12}}}}),
        encoding="utf-8",
    )

    assert _filing_section_from_json(path) == "139(4)"


def test_uploader_reports_an_unreadable_filing_section_rather_than_guessing(tmp_path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"ITR": {}}), encoding="utf-8")

    assert _filing_section_from_json(path) is None


@pytest.mark.asyncio
async def test_leaving_the_file_itr_route_fails_at_the_step_that_left_it() -> None:
    """Clicking the portal's prefill control navigated off the wizard entirely.

    The run then reported an absent file input while sitting on
    ``#/dashboard/downloadPreFilledData`` — a page that has no upload step.
    """
    class _Page:
        url = "https://eportal.incometax.gov.in/iec/foservices/#/dashboard/downloadPreFilledData"

        async def evaluate(self, _script):
            raise RuntimeError("not needed for this assertion")

    logs: list[str] = []
    with pytest.raises(RuntimeError, match="navigated away from the File ITR page"):
        await _assert_on_file_itr_route(_Page(), "reaching the upload step", logs.append)

    assert any("downloadPreFilledData" in entry for entry in logs)


@pytest.mark.asyncio
async def test_staying_on_the_file_itr_route_is_not_flagged() -> None:
    class _Page:
        url = "https://eportal.incometax.gov.in/iec/foservices/#/dashboard/fileIncomeTaxReturn"

    await _assert_on_file_itr_route(_Page(), "reaching the upload step", None)


def test_uploaded_artifact_identity_is_logged(tmp_path) -> None:
    """The log has to name which file went to the portal, and whose return it is."""
    path = tmp_path / "ITR1_ABCDE1234F.json"
    path.write_text(
        json.dumps({
            "ITR": {"ITR1": {
                "Form_ITR1": {"AssessmentYear": "2026"},
                "PersonalInfo": {"PAN": "ABCDE1234F"},
                "FilingStatus": {"ReturnFileSec": 12},
            }},
        }),
        encoding="utf-8",
    )
    logs: list[str] = []

    _log_json_identity(path, logs.append)

    joined = " ".join(logs)
    assert "ITR1_ABCDE1234F.json" in joined
    assert "pan=ABCDE1234F" in joined
    assert "ReturnFileSec=12" in joined
    assert "assessmentYear=2026" in joined


@pytest.mark.parametrize(
    ("section", "label"),
    [
        ("139(1)", "139(1) - Original Return"),
        ("139(4)", "139 ( 4 ) - Belated Return"),
        ("139(5)", "139(5) — Revised Return"),
        ("119(2)(b)", "119(2)(b) - Condonation of delay"),
    ],
)
def test_filing_section_pattern_tolerates_portal_label_wording(section: str, label: str) -> None:
    """Portal labels carry extra wording and inconsistent bracket spacing."""
    import re

    assert re.search(_filing_section_pattern(section), label, re.I) is not None
