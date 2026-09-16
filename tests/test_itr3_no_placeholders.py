"""Regression tests for fail-closed ITR-3 optional disclosures."""

from __future__ import annotations

from decimal import Decimal

from app.engine.calculators.itr3 import compute
from app.engine.itd.itr3 import _partb_tti, _schedule_if
from app.schemas.itr3 import ITR3Input


def _minimal_input() -> ITR3Input:
    """Build the minimum calculator input used by these builder unit tests."""
    return ITR3Input(age_bracket="below_60", tax_regime="new")


def test_schedule_if_is_omitted_without_partner_source() -> None:
    """The builder never invents a firm name or PAN."""
    result = compute(_minimal_input())
    assert _schedule_if(result, _minimal_input()) is None


def test_refund_bank_details_are_not_fabricated() -> None:
    """A non-refund result has no synthetic bank account disclosure."""
    typed = _minimal_input()
    result = compute(typed)
    payload = _partb_tti(result, typed)
    bank_details = payload["Refund"]["BankAccountDtls"]
    assert bank_details["AddtnlBankDetails"] == []
    assert bank_details["BankDtlsFlag"] == "N"


def test_refund_requires_explicit_selected_bank_account() -> None:
    """A refund cannot be serialized without a typed refund account."""
    typed = _minimal_input()
    result = compute(typed)
    result.refund_due = Decimal("100")
    try:
        _partb_tti(result, typed)
    except ValueError as exc:
        assert "refund bank account" in str(exc)
    else:
        raise AssertionError("refund serialization accepted missing bank source")
