"""
Phase 1 tests — draft_to_itr1_input mapper parity + compute.

Verifies the single canonical mapper produces a valid ITR1Input and
that compute_itr1 runs cleanly on it. This is the mapper that replaces
both `_compute_tax_summary_impl`'s ITR-1 branch and
`_build_itr1_input_from_flat` (Phase 7 deletes the duplicates).

Run: pytest tests/test_draft_to_itr1_input.py -v
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.calculators.itr1 import compute as compute_itr1
from app.engine.draft_to_itr1_input import DraftMappingError, draft_to_itr1_input
from app.schemas.return_draft import (
    BankAccount,
    DividendIncome,
    Employer,
    InterestIncome,
    Investment80C,
    PersonalInfo,
    ReturnDraft,
    TaxChallan,
    TdsCredit,
    WinningIncome,
)


def _sample_draft() -> ReturnDraft:
    """Build a representative ITR-1 draft with all schedules populated."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="new")
    draft.personal = PersonalInfo(
        name="Rahul", pan="ABCDE1234F", email="r@example.com",
        mobile="9876543210", dateOfBirth="1990-01-15",
    )
    draft.employers = [Employer(
        id="e1", employerName="Acme", employerTAN="MUMA12345B",
        basic=Decimal("1200000"), da=Decimal("12000"), hra=Decimal("60000"),
        perquisites=Decimal("5000"), professionalTax=Decimal("2400"),
        tdsDeducted=Decimal("80000"),
    )]
    draft.otherSources.interest = [InterestIncome(
        id="i1", kind="SAVINGS_BANK", grossAmount=Decimal("15000"),
    )]
    draft.otherSources.dividends = [DividendIncome(
        id="d1", section="194", grossAmount=Decimal("10000"),
        tdsDeducted=Decimal("1000"), q1=Decimal("1000"),
        q2=Decimal("2000"), q3=Decimal("3000"),
        q4=Decimal("1500"), q5=Decimal("2500"),
    )]
    draft.deductions.section80C = [Investment80C(
        id="c1", investmentType="EPF", amount=Decimal("50000"),
    )]
    draft.taxes.tds = [TdsCredit(
        id="t1", section="192", deductorName="Acme",
        deductorTAN="MUMA12345B", taxDeducted=Decimal("80000"),
    )]
    draft.taxes.challans = [TaxChallan(
        id="ch1", kind="SELF_ASSESSMENT", bsrCode="1234567",
        depositDate="2026-04-10", challanSerialNo=1, amount=Decimal("5000"),
    )]
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="SBI", accountNumber="1234567890",
        ifscCode="SBIN0001234", accountType="SB", useForRefund=True,
    )]
    return draft


# ── Mapper produces valid ITR1Input ───────────────────────────────────────────

def test_mapper_produces_valid_itr1_input():
    draft = _sample_draft()
    itr1_input, breakdown = draft_to_itr1_input(draft)

    assert itr1_input.salary_income.gross_salary == Decimal("1277000")  # 1.2M+12k+60k+5k
    assert itr1_input.other_sources_income.savings_bank_interest == Decimal("15000")
    assert itr1_input.other_sources_income.dividend_income == Decimal("10000")
    assert itr1_input.dividend_quarterly_breakdown == {
        "Q1": Decimal("1000"),
        "Q2": Decimal("2000"),
        "Q3": Decimal("3000"),
        "Q4": Decimal("1500"),
        "Q5": Decimal("2500"),
    }
    assert itr1_input.deductions_chapter6a.amount_80c == Decimal("0")  # new regime excludes 80C
    assert len(itr1_input.tds1_entries) == 1
    assert itr1_input.tds1_entries[0].tds_deducted == Decimal("80000")
    assert len(itr1_input.bank_accounts) == 1
    assert str(itr1_input.bank_accounts[0].account_type) in ("savings", "BankAccountType.SAVINGS")

    # breakdown carries the intermediate totals
    assert breakdown["section_17_1_salary"] == Decimal("1272000")
    assert breakdown["gross_salary"] == Decimal("1277000")
    assert breakdown["total_interest"] == Decimal("15000")
    assert breakdown["total_dividend"] == Decimal("10000")
    assert breakdown["claimed_tds"] == Decimal("80000")


def test_mapper_aggregates_all_five_dividend_periods_across_rows():
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.otherSources.dividends = [
        DividendIncome(
            id="d1", grossAmount=Decimal("500"),
            q1=Decimal("100"), q2=Decimal("100"), q3=Decimal("100"),
            q4=Decimal("100"), q5=Decimal("100"),
        ),
        DividendIncome(
            id="d2", grossAmount=Decimal("1000"),
            q1=Decimal("50"), q2=Decimal("150"), q3=Decimal("200"),
            q4=Decimal("250"), q5=Decimal("350"),
        ),
    ]

    itr1_input, _ = draft_to_itr1_input(draft)

    assert itr1_input.dividend_quarterly_breakdown == {
        "Q1": Decimal("150"),
        "Q2": Decimal("250"),
        "Q3": Decimal("300"),
        "Q4": Decimal("350"),
        "Q5": Decimal("450"),
    }


def test_compute_runs_cleanly_on_mapped_input():
    """The mapped ITR1Input must run through compute_itr1 without error."""
    draft = _sample_draft()
    itr1_input, _ = draft_to_itr1_input(draft)
    result = compute_itr1(itr1_input)
    assert result.errors == []
    assert result.salary_income == Decimal("1207000")  # gross - profTax - std ded
    assert result.gross_total_income == Decimal("1232000")  # salary + interest + dividend
    assert result.net_tax_liability == Decimal("33280.0")
    assert result.total_tds == Decimal("80000")


def test_hra_exempt_recomputed_from_employer_evidence():
    """HRA exemption must be recomputed u/s 10(13A) from the per-employer
    rent + salary + metro facts — never trusted from a frontend-supplied
    exempt amount.

    Employer: basic=50,000, da=0, hra=4,000, rent=8,000, metro=False.
    Condition 1: 4,000 (actual HRA)
    Condition 2: 8,000 - (50,000 * 0.10) = 3,000
    Condition 3: 50,000 * 0.40 = 20,000
    Exempt = least = 3,000
    """
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("50000"),
        hra=Decimal("4000"), rentPaid=Decimal("8000"), isMetroCity=False,
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    # HRA exemption recomputed to 3,000 (condition 2 wins).
    assert itr1_input.salary_income.hra_exempt_amount == Decimal("3000")


def test_hra_exempt_zero_when_rent_missing():
    """When HRA is received but rent facts are missing, the exemption is
    zero for that row — not trusted from a stale frontend value."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("50000"),
        hra=Decimal("4000"), rentPaid=Decimal("0"), isMetroCity=False,
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.hra_exempt_amount == Decimal("0")


# ── ITR-1 scope guard ─────────────────────────────────────────────────────────

def test_lottery_rejected_on_itr1():
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.otherSources.winnings = [WinningIncome(
        id="w1", type="LOTTERY", grossAmount=Decimal("1000"),
    )]
    with pytest.raises(DraftMappingError):
        draft_to_itr1_input(draft)


# ── Age bracket derivation ────────────────────────────────────────────────────

def test_age_bracket_below_60():
    from app.schemas.itr1 import AgeBracket
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.personal.dateOfBirth = "1990-01-15"
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.age_bracket == AgeBracket.BELOW_60


def test_age_bracket_senior_citizen():
    from app.schemas.itr1 import AgeBracket
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.personal.dateOfBirth = "1955-01-15"  # ~71 as on 31-Mar-2026
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.age_bracket == AgeBracket.SIXTY_TO_80


def test_age_bracket_super_senior():
    from app.schemas.itr1 import AgeBracket
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.personal.dateOfBirth = "1940-01-15"  # ~86 as on 31-Mar-2026
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.age_bracket == AgeBracket.ABOVE_80


# ── TDS split (TDS1 salary vs TDS2 other) ─────────────────────────────────────

def test_tds_split_salary_vs_other():
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.tds = [
        TdsCredit(id="t1", section="192", deductorTAN="MUMA12345B",
                  taxDeducted=Decimal("80000")),
        TdsCredit(id="t2", section="194A", deductorTAN="DELB98765A",
                  taxDeducted=Decimal("5000")),
    ]
    itr1_input, breakdown = draft_to_itr1_input(draft)
    assert len(itr1_input.tds1_entries) == 1  # salary
    assert len(itr1_input.tds2_entries) == 1  # other
    assert breakdown["tds_salary"] == Decimal("80000")
    assert breakdown["tds_other"] == Decimal("5000")
    assert breakdown["tds_interest"] == Decimal("5000")  # 194A is interest


def test_unclaimed_tds_excluded():
    """TDS rows with claimedInReturn=False are preserved in the draft but
    excluded from entered/claimed totals."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.tds = [
        TdsCredit(id="t1", section="192", deductorTAN="MUMA12345B",
                  taxDeducted=Decimal("80000"), claimedInReturn=True),
        TdsCredit(id="t2", section="194A", deductorTAN="DELB98765A",
                  taxDeducted=Decimal("5000"), claimedInReturn=False),
    ]
    itr1_input, breakdown = draft_to_itr1_input(draft)
    assert len(itr1_input.tds1_entries) == 1
    assert itr1_input.tds2_entries is None or len(itr1_input.tds2_entries) == 0
    assert breakdown["claimed_tds"] == Decimal("80000")  # only the claimed row


def test_invalid_tan_row_skipped_and_surfaced():
    """A TDS row with an invalid TAN is excluded from the typed engine input
    (which enforces the TAN pattern) but surfaced as a structured issue in
    the breakdown. The row remains in the editable draft."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.tds = [
        TdsCredit(id="t1", section="192", deductorTAN="INVALID",
                  taxDeducted=Decimal("80000"), claimedInReturn=True),
    ]
    itr1_input, breakdown = draft_to_itr1_input(draft)
    # The invalid row is not added to the typed engine input.
    assert not itr1_input.tds1_entries  # None or empty
    # But it is surfaced as a structured issue.
    issues = breakdown["credit_validation_issues"]
    assert len(issues) == 1
    assert issues[0]["code"] == "INVALID_TAN_FORMAT"
    assert issues[0]["amount"] == 80000.0


def test_empty_tan_tds2_row_with_zero_tax_skipped_not_crashed():
    """A TDS-2 (non-salary) row with an empty TAN and tax==0 but gross>0
    must be skipped and surfaced as an issue — not passed to the
    ``TDS2Entry`` constructor, whose ``deductor_tan`` field enforces the
    TAN pattern and would otherwise raise a Pydantic validation error.

    Regression for the compute-time crash:
    "TDS2Entry deductor_tan String should match pattern '^[A-Z]{4}[0-9]{5}[A-Z]$'".
    """
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.tds = [
        TdsCredit(id="t1", section="194A", deductorTAN="",
                  grossAmount=Decimal("100000"), taxDeducted=Decimal("0"),
                  claimedInReturn=True),
    ]
    # Must not raise.
    itr1_input, breakdown = draft_to_itr1_input(draft)
    assert itr1_input.tds2_entries is None or len(itr1_input.tds2_entries) == 0
    issues = breakdown["credit_validation_issues"]
    assert len(issues) == 1
    assert issues[0]["code"] == "INVALID_TAN_FORMAT"
    assert issues[0]["enteredValue"] == ""


# ── Tax-payment reclassification ─────────────────────────────────────────────

def test_sat_before_fy_end_reclassified_as_advance():
    """A self-assessment payment dated on/before 31-Mar-2026 is advance tax."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.challans = [TaxChallan(
        id="ch1", kind="SELF_ASSESSMENT", bsrCode="1234567",
        depositDate="2026-03-20", challanSerialNo=1, amount=Decimal("5000"),
    )]
    itr1_input, breakdown = draft_to_itr1_input(draft)
    assert itr1_input.advance_tax_paid == Decimal("5000")  # reclassified
    assert len(itr1_input.tax_payment_entries) == 0  # none left as SAT


def test_sat_after_fy_end_stays_self_assessment():
    """A self-assessment payment dated after 31-Mar-2026 stays as SAT."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.challans = [TaxChallan(
        id="ch1", kind="SELF_ASSESSMENT", bsrCode="1234567",
        depositDate="2026-04-10", challanSerialNo=1, amount=Decimal("5000"),
    )]
    itr1_input, breakdown = draft_to_itr1_input(draft)
    assert itr1_input.advance_tax_paid == Decimal("0")
    assert len(itr1_input.tax_payment_entries) == 1
    assert itr1_input.self_assessment_tax_paid == Decimal("5000")


def test_advance_tax_quarterly_bucketing():
    """Advance-tax installments land in the correct quarterly bucket."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.challans = [
        TaxChallan(id="ch1", kind="ADVANCE_TAX", bsrCode="1234567",
                   depositDate="2025-06-10", challanSerialNo=1, amount=Decimal("1000")),
        TaxChallan(id="ch2", kind="ADVANCE_TAX", bsrCode="1234567",
                   depositDate="2025-09-10", challanSerialNo=2, amount=Decimal("2000")),
        TaxChallan(id="ch3", kind="ADVANCE_TAX", bsrCode="1234567",
                   depositDate="2025-12-10", challanSerialNo=3, amount=Decimal("3000")),
        TaxChallan(id="ch4", kind="ADVANCE_TAX", bsrCode="1234567",
                   depositDate="2026-03-10", challanSerialNo=4, amount=Decimal("4000")),
    ]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.advance_tax_paid == Decimal("10000")
    assert itr1_input.advance_tax_q1 == Decimal("1000")
    assert itr1_input.advance_tax_q2 == Decimal("2000")
    assert itr1_input.advance_tax_q3 == Decimal("3000")
    assert itr1_input.advance_tax_q4 == Decimal("4000")
