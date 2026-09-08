"""Regression tests for statutory interest, filing dates, and SAT reconciliation."""

from datetime import date
from decimal import Decimal

from app.engine.common.due_dates import get_due_date
from app.engine.common.interest import compute_234a, compute_234b, compute_234c, compute_234f, compute_234i
from app.schemas.itr2 import ReturnFileSection


def test_ay_2026_27_default_due_dates() -> None:
    """Use the prescribed AY 2026-27 due dates for all supported ITR forms."""
    assert get_due_date("ITR-1") == date(2026, 7, 31)
    assert get_due_date("ITR-2") == date(2026, 7, 31)
    assert get_due_date("ITR-3") == date(2026, 8, 31)
    assert get_due_date("ITR-4") == date(2026, 8, 31)


def test_234b_uses_self_assessment_challan_date() -> None:
    """Stop 234B accrual when a dated self-assessment challan settles tax."""
    assessed_tax = Decimal("27400")
    ay_start = date(2026, 4, 1)
    filing_date = date(2026, 8, 10)

    result = compute_234b(
        assessed_tax=assessed_tax,
        advance_tax_paid=Decimal("0"),
        filing_date=filing_date,
        ay_start=ay_start,
        self_assessment_payments=[(date(2026, 8, 10), Decimal("27400"))],
    )

    assert result == Decimal("1370")


def test_234b_reduces_after_earlier_self_assessment_challan() -> None:
    """Reduce the 234B principal from each earlier self-assessment payment date."""
    result = compute_234b(
        assessed_tax=Decimal("27400"),
        advance_tax_paid=Decimal("0"),
        filing_date=date(2026, 8, 10),
        ay_start=date(2026, 4, 1),
        self_assessment_payments=[(date(2026, 6, 10), Decimal("27400"))],
    )

    assert result == Decimal("822")


def test_test7_advance_tax_interest_components() -> None:
    """Produce the Test 7 234B and 234C components for zero advance tax."""
    assessed_tax = Decimal("27400")
    ay_start = date(2026, 4, 1)

    assert compute_234b(
        assessed_tax,
        Decimal("0"),
        date(2026, 8, 10),
        ay_start,
        [(date(2026, 8, 10), assessed_tax)],
    ) == Decimal("1370")
    assert compute_234c([Decimal("0")], assessed_tax, ay_start) == Decimal("1384")


def test_234b_runs_until_self_assessment_payment_after_default_filing_date() -> None:
    """Continue 234B accrual when the SAT challan is dated after the default filing date."""
    assessed_tax = Decimal("27400")
    ay_start = date(2026, 4, 1)
    default_filing_date = date(2026, 7, 31)
    self_assessment_challan = (date(2026, 8, 10), Decimal("27400"))

    result = compute_234b(
        assessed_tax=assessed_tax,
        advance_tax_paid=Decimal("0"),
        filing_date=default_filing_date,
        ay_start=ay_start,
        self_assessment_payments=[self_assessment_challan],
    )

    assert result == Decimal("1370")



def test_late_filing_and_revised_return_fees() -> None:
    """Apply 234A, 234F, and 234-I only under their respective conditions.

    234F's pre-Finance-Act-2021 Rs 10,000 tier for filing after 31 December
    was removed; the maximum is Rs 5,000 regardless of how late within the
    belated-filing window the return is filed -- the official ITR-1 JSON
    schema enforces this directly (LateFilingFee234F max 5,000). See
    Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md.
    """
    due_date = date(2026, 7, 31)
    filing_date = date(2027, 1, 1)
    total_income = Decimal("600000")

    assert compute_234a(Decimal("27400"), filing_date, due_date) == Decimal("1644")
    assert compute_234f(filing_date, due_date, total_income) == Decimal("5000")
    assert compute_234i(filing_date, due_date, total_income, "139(5)") == Decimal("5000")
    assert compute_234i(
        filing_date,
        due_date,
        total_income,
        ReturnFileSection.REVISED_139_5,
    ) == Decimal("5000")
    assert compute_234i(filing_date, due_date, total_income, "139(4)") == Decimal("0")
