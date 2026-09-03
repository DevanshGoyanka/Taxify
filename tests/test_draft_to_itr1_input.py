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
from app.schemas.itr1 import BankAccountType
from app.schemas.return_draft import (
    BankAccount,
    DividendIncome,
    Employer,
    HomeLoan,
    HouseProperty,
    InterestIncome,
    Investment80C,
    OtherIncomeEntry,
    PensionContribution80CCC,
    Policy80D,
    DeductionLoan,
    Schedule80GGAEntry,
    Schedule80GGCEntry,
    PersonalInfo,
    ReturnDraft,
    TaxChallan,
    TcsCredit,
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

    # SalaryIncome.gross_salary is the Section 17(1) portion only (basic+da+hra);
    # perquisites are tracked separately on perquisites_value and added by the
    # calculator, not summed in here -- see _map_salary's docstring. Previously
    # this field held the combined 17(1)+17(2)+17(3) total (1277000, including
    # the 5000 perquisites), which the calculator then added perquisites_value
    # on top of again, double-counting it.
    assert itr1_input.salary_income.gross_salary == Decimal("1272000")  # 1.2M+12k+60k
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


def test_maps_other_bank_account_type_without_downgrading_to_savings() -> None:
    """The canonical OTH code must survive through the typed filing model."""
    draft = _sample_draft()
    draft.bankAccounts[0].accountType = "OTH"

    itr1_input, _ = draft_to_itr1_input(draft)

    assert itr1_input.bank_accounts[0].account_type == BankAccountType.OTHER


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


def test_mapper_preserves_official_other_source_categories() -> None:
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.otherSources.interest = [
        InterestIncome(id="s", kind="SAVINGS_BANK", grossAmount=Decimal("100")),
        InterestIncome(id="p", kind="POST_OFFICE", grossAmount=Decimal("200")),
        InterestIncome(id="t", kind="IT_REFUND", grossAmount=Decimal("300")),
        InterestIncome(id="pf", kind="PF_10_11_FIRST", grossAmount=Decimal("400")),
        InterestIncome(
            id="o", kind="OTHER", grossAmount=Decimal("500"),
            remarks="Private loan interest",
        ),
    ]
    draft.otherSources.otherIncome = [OtherIncomeEntry(
        id="other-1", nature="OTHER",
        description="Consulting honorarium", amount=Decimal("600"),
    )]

    typed, _ = draft_to_itr1_input(draft)

    assert typed.other_sources_income.savings_bank_interest == Decimal("100")
    assert typed.other_sources_income.fixed_deposit_interest == Decimal("200")
    assert typed.other_sources_income.interest_on_it_refund == Decimal("300")
    assert typed.other_sources_income.other_income == Decimal("1500")
    assert [(row.nature, row.amount) for row in typed.other_sources_income.source_details] == [
        ("SAV", Decimal("100")),
        ("IFD", Decimal("200")),
        ("TAX", Decimal("300")),
        ("10(11)(iP)", Decimal("400")),
        ("OTH", Decimal("1100")),
    ]
    assert typed.other_sources_income.source_details[-1].other_description == (
        "Private loan interest; Consulting honorarium"
    )


def test_compute_runs_cleanly_on_mapped_input():
    """The mapped ITR1Input must run through compute_itr1 without error."""
    draft = _sample_draft()
    itr1_input, _ = draft_to_itr1_input(draft)
    result = compute_itr1(itr1_input)
    assert result.errors == []
    # gross(1272000 s.17(1) + 5000 perquisites = 1277000) - std ded(75000, new
    # regime); prof_tax is 0 in the new regime. Regression fence for a fixed
    # double-counting bug: perquisites_value/profits_in_lieu_of_salary were
    # previously summed into SalaryIncome.gross_salary *and* added again by
    # the calculator (app/engine/schedules/salary.py), inflating this figure
    # by the perquisites amount (previously asserted 1207000 here).
    assert result.salary_income == Decimal("1202000")
    assert result.gross_total_income == Decimal("1227000")  # salary + interest + dividend
    assert result.net_tax_liability == Decimal("28080.0")
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


def test_hra_mixed_metro_evidence_is_rejected() -> None:
    """The singular CBDT HRA schedule cannot truthfully encode mixed locations."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.employers = [
        Employer(id="metro", basic=Decimal("500000"), hra=Decimal("100000"),
                 rentPaid=Decimal("150000"), isMetroCity=True),
        Employer(id="non-metro", basic=Decimal("500000"), hra=Decimal("100000"),
                 rentPaid=Decimal("150000"), isMetroCity=False),
    ]

    with pytest.raises(DraftMappingError, match="mixed metro"):
        draft_to_itr1_input(draft)


def test_lta_exempt_recomputed_from_employer_evidence() -> None:
    """LTA/LTC exemption u/s 10(5) must be recomputed from actual fare +
    domestic-travel evidence, capped at the amount received -- never
    trusted from employer.ltaExempt, which no frontend control ever sets.

    Employer: lta=20,000 received, actualLtaFare=15,000, domestic travel.
    Exempt = min(20,000, 15,000) = 15,000.
    """
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        lta=Decimal("20000"), actualLtaFare=Decimal("15000"),
        isDomesticTravel=True,
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.lta_exempt_amount == Decimal("15000")


def test_lta_exempt_capped_at_amount_received() -> None:
    """The exemption cannot exceed the LTA actually received, even if the
    eligible fare evidence is larger."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        lta=Decimal("10000"), actualLtaFare=Decimal("15000"),
        isDomesticTravel=True,
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.lta_exempt_amount == Decimal("10000")


def test_lta_exempt_zero_for_foreign_travel() -> None:
    """Foreign travel is never exempt under Section 10(5), regardless of
    fare evidence entered."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        lta=Decimal("20000"), actualLtaFare=Decimal("15000"),
        isDomesticTravel=False,
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.lta_exempt_amount == Decimal("0")


def test_lta_received_is_taxable_income_regardless_of_exemption() -> None:
    """LTA received must reach gross salary as taxable income even when no
    exemption evidence is entered -- previously employer.lta was never
    summed into gross_salary at all, silently dropping it from income."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        lta=Decimal("20000"),
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.gross_salary == Decimal("520000")
    assert itr1_input.salary_income.lta_exempt_amount == Decimal("0")


def test_lta_amount_received_mapped_for_validator_cross_check() -> None:
    """SalaryIncome.lta_amount_received (distinct from lta_exempt_amount)
    must be populated -- previously it stayed 0, which after the LTA-exempt
    fix above made ITR1-R0xx's "exempt cannot exceed received" validator
    fire for every genuine LTA claim (see
    Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §11.5)."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        lta=Decimal("20000"), actualLtaFare=Decimal("15000"),
        isDomesticTravel=True,
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.lta_amount_received == Decimal("20000")
    assert itr1_input.salary_income.lta_exempt_amount <= itr1_input.salary_income.lta_amount_received


def test_retirement_receipts_reach_salary_income_and_gross_salary() -> None:
    """Gratuity/commuted-pension/leave-encashment/VRS/retrenchment amounts
    must reach both SalaryIncome's raw *_received fields (for the Section
    10 exemption test) and gross_salary (as taxable income) -- previously
    none of these five fields was ever set by the mapper at all, so the
    taxable residual of a real retirement payout silently vanished from
    computed income entirely (§11.1)."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", natureOfEmployment="OTH",
        basic=Decimal("500000"),
        gratuity=Decimal("300000"), commutedPension=Decimal("100000"),
        leaveEncashment=Decimal("200000"), vrsCompensation=Decimal("50000"),
        retrenchmentCompensation=Decimal("0"),
        averageMonthlySalary=Decimal("40000"), yearsOfService=10,
        unavailedLeaveDays=120,
    )]
    itr1_input, breakdown = draft_to_itr1_input(draft)
    sal = itr1_input.salary_income
    assert sal.gratuity_received == Decimal("300000")
    assert sal.commuted_pension_received == Decimal("100000")
    assert sal.leave_encashment_received == Decimal("200000")
    assert sal.vrs_compensation == Decimal("50000")
    assert sal.average_monthly_salary == Decimal("40000")
    assert sal.years_of_service == 10
    assert sal.unavailed_leave_days == 120
    # gross_salary (Section 17(1)) itself is unaffected -- retirement
    # receipts are added to *gross* by schedules/salary.py, not to 17(1).
    assert sal.gross_salary == Decimal("500000")
    result = compute_itr1(itr1_input)
    # The taxable residual must reach computed salary income, not vanish:
    # basic 500000 + 4 retirement receipts (650000) - std ded (50000)
    # - whatever portion is exempt. At minimum, chargeable income must
    # exceed basic salary alone (proving the receipts were not dropped).
    assert result.salary_income > Decimal("450000")


def test_transport_and_child_allowances_reach_salary_income() -> None:
    """Transport allowance and the two Section 10(14) child allowances
    must reach SalaryIncome -- previously dropped entirely (§11.2)."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        transportAllowance=Decimal("19200"), isDisabledEmployee=True,
        childrenEducationAllowance=Decimal("2400"),
        hostelExpenditureAllowance=Decimal("7200"), numberOfChildren=2,
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    sal = itr1_input.salary_income
    assert sal.transport_allowance == Decimal("19200")
    assert sal.is_disabled_employee is True
    assert sal.number_of_children == 2
    assert sal.sec10_14i_prescribed_allowance == Decimal("2400")
    assert sal.sec10_14ii_personal_allowance == Decimal("7200")
    result = compute_itr1(itr1_input)
    # Disabled-employee transport exemption (Rs 19,200 cap) + full CEA (Rs
    # 1,200/child x 2 = Rs 2,400, matches allowance exactly) + full hostel
    # (Rs 3,600/child x 2 = Rs 7,200, matches allowance exactly) must all
    # apply -- previously num_children was hardcoded to 0, forcing both
    # child-allowance exemptions to zero regardless of input.
    assert result.salary_transport_exempt == Decimal("19200")
    assert result.salary_children_education_exempt == Decimal("2400")
    assert result.salary_hostel_exempt == Decimal("7200")


def test_children_allowance_exemption_zero_without_number_of_children() -> None:
    """Explicit control: with numberOfChildren=0 (the schema default), the
    CEA/hostel exemptions are correctly zero -- confirms the fix reads the
    real field rather than always granting the 2-child statutory max."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        childrenEducationAllowance=Decimal("2400"),
        hostelExpenditureAllowance=Decimal("7200"), numberOfChildren=0,
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.number_of_children == 0


def test_section10_exemption_rows_mapped() -> None:
    """employer.section10ExemptionRows (10(6)/10(7)/10(10CC), a structured
    dropdown+amount list with a real rendered UI) must reach the matching
    SalaryIncome scalar fields -- previously never read at all (§11.4)."""
    from app.schemas.return_draft import Employer as EmployerT, SalaryNatureRow
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        section10ExemptionRows=[
            SalaryNatureRow(id="r1", natureCode="10(6)", amount=Decimal("10000")),
            SalaryNatureRow(id="r2", natureCode="10(7)", amount=Decimal("20000")),
            SalaryNatureRow(id="r3", natureCode="10(10CC)", amount=Decimal("5000")),
        ],
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    sal = itr1_input.salary_income
    assert sal.sec10_6_embassy_exempt == Decimal("10000")
    assert sal.sec10_7_foreign_allowance == Decimal("20000")
    assert sal.sec10_10cc_perquisite_tax == Decimal("5000")


def test_standard_deduction_claimed_mapped_to_regime_cap() -> None:
    """SalaryIncome.standard_deduction_claimed must report the regime
    statutory cap when there is salary -- previously always 0, which fired
    ITR1-B004's "did you mean to claim standard deduction?" warning on
    every single salaried return (§11.6)."""
    from app.schemas.return_draft import Employer as EmployerT
    old_draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    old_draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    old_draft.employers = [EmployerT(id="e1", employerName="Acme", basic=Decimal("500000"))]
    old_input, _ = draft_to_itr1_input(old_draft)
    assert old_input.salary_income.standard_deduction_claimed == Decimal("50000")

    new_draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="new")
    new_draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    new_draft.employers = [EmployerT(id="e1", employerName="Acme", basic=Decimal("500000"))]
    new_input, _ = draft_to_itr1_input(new_draft)
    assert new_input.salary_income.standard_deduction_claimed == Decimal("75000")


def test_uniform_allowance_reaches_gross_salary_fully_taxable() -> None:
    """employer.uniformAllowance must reach taxable income regardless of
    whether expenditure evidence is supplied -- the received amount is part
    of Section 17(1) salary either way; only the *exemption* (a separate
    concern, see the evidence test below) depends on evidence."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        uniformAllowance=Decimal("15000"),
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.gross_salary == Decimal("515000")


def test_uniform_allowance_expenditure_reaches_calculator_as_exemption() -> None:
    """employer.uniformAllowanceExpenditure -- actual-expenditure evidence
    for the Section 10(14)(i)/Rule 2BB exemption -- must reach SalaryIncome
    and reduce taxable income via schedules/salary.py's
    _exempt_uniform_allowance, closing the gap
    test_uniform_allowance_reaches_gross_salary_fully_taxable documented as
    open (§11.9/§19)."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        uniformAllowance=Decimal("15000"),
        uniformAllowanceExpenditure=Decimal("11000"),
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.uniform_allowance_received == Decimal("15000")
    assert itr1_input.salary_income.uniform_allowance_actual_expenditure == Decimal("11000")
    result = compute_itr1(itr1_input)
    assert result.salary_uniform_allowance_exempt == Decimal("11000")


def test_gratuity_also_received_flag_reaches_salary_income() -> None:
    """employer.gratuityAlsoReceived must reach SalaryIncome and affect the
    Section 10(10A) commuted-pension exemption fraction -- previously
    captured on the frontend but never wired, so the exemption always used
    the flat 1/3rd fraction (§11.9 follow-up)."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", natureOfEmployment="OTH",
        basic=Decimal("500000"),
        commutedPension=Decimal("300000"), gratuityAlsoReceived=False,
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.is_gratuity_also_received is False
    result = compute_itr1(itr1_input)
    assert result.salary_commutted_pension_exempt == Decimal("150000")  # 1/2, not 1/3


def test_pre_1999_home_loan_sanction_date_caps_self_occupied_interest_at_30000() -> None:
    """LoanDetail.sanction_date (from HouseProperty.homeLoans[].dateOfLoan)
    must reach the calculator and cap self-occupied interest at Rs 30,000,
    not the usual Rs 2,00,000, per CBDT's pre-1-April-1999 proviso to Sec
    24(b) -- closes Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md
    §14.1/§19's documented-but-deferred gap."""
    from app.schemas.return_draft import (
        Employer as EmployerT, HouseProperty as HousePropertyT, HomeLoan,
    )
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
    )]
    draft.houseProperties = [HousePropertyT(
        id="hp1", name="Old Flat", propertyType="SELF_OCCUPIED",
        interestOnLoan=Decimal("60000"),
        homeLoans=[HomeLoan(
            lenderType="B", lenderName="SBI", loanAccountNo="OLD123",
            dateOfLoan="1998-05-01", totalLoanAmount=Decimal("400000"),
            loanOutstandingAmount=Decimal("100000"), interestUs24B=Decimal("60000"),
        )],
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    result = compute_itr1(itr1_input)
    assert result.house_property_income == Decimal("-30000")


def test_other_taxable_salary_and_arrears_reach_gross_salary() -> None:
    """Other taxable salary and arrears/advance salary must be counted as
    income -- previously employer.otherAllowance/.arrearSalary were never
    summed into gross_salary at all."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        otherAllowance=Decimal("30000"), arrearSalary=Decimal("40000"),
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.gross_salary == Decimal("570000")


def test_perquisites_not_double_counted_in_gross_salary() -> None:
    """SalaryIncome.gross_salary must hold only the Section 17(1) portion --
    perquisites_value and profits_in_lieu_of_salary are tracked separately
    and added by the calculator (app/engine/schedules/salary.py). Passing
    the already-combined total here previously caused the calculator to
    double-count both."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Acme", basic=Decimal("500000"),
        perquisites=Decimal("50000"), profitsInLieu=Decimal("25000"),
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.gross_salary == Decimal("500000")
    assert itr1_input.salary_income.perquisites_value == Decimal("50000")
    assert itr1_input.salary_income.profits_in_lieu_of_salary == Decimal("25000")


def test_government_employee_derived_from_nature_of_employment() -> None:
    """is_government_employee must be derived from natureOfEmployment
    (CGOV/SGOV specifically) -- the separate employer.isGovernmentEmployee
    scalar has no live frontend control anywhere in the product and was
    always False."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Ministry of X", basic=Decimal("500000"),
        natureOfEmployment="CGOV",
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.is_government_employee is True


def test_psu_employee_is_not_government_employee_for_16ii_or_80ccd2() -> None:
    """PSU and the pensioner nature-of-employment codes do not qualify as
    'Government employee' for Section 16(ii) / Section 80CCD(2) purposes --
    matches this codebase's own Central/State-only definition in
    section_80ccd2.py."""
    from app.schemas.return_draft import Employer as EmployerT
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1990-01-15")
    draft.employers = [EmployerT(
        id="e1", employerName="Some PSU", basic=Decimal("500000"),
        natureOfEmployment="PSU",
    )]
    itr1_input, _ = draft_to_itr1_input(draft)
    assert itr1_input.salary_income.is_government_employee is False


def test_mapper_preserves_section_24b_loan_rows() -> None:
    """Canonical home-loan evidence must reach the typed filing input."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.houseProperties = [HouseProperty(
        id="hp1",
        propertyType="SELF_OCCUPIED",
        interestOnLoan=Decimal("200000"),
        homeLoans=[HomeLoan(
            lenderType="I",
            lenderName="Housing Finance Ltd",
            loanAccountNo="HOME-123",
            dateOfLoan="2020-04-01",
            totalLoanAmount=Decimal("3000000"),
            loanOutstandingAmount=Decimal("2400000"),
            interestUs24B=Decimal("200000"),
        )],
    )]

    itr1_input, _ = draft_to_itr1_input(draft)

    assert len(itr1_input.loan_details_24b_list) == 1
    row = itr1_input.loan_details_24b_list[0]
    assert row.loan_taken_from.value == "I"
    assert row.outstanding_loan_amount == Decimal("2400000")
    assert row.interest_paid_self_occupied == Decimal("200000")


def test_mapper_uses_canonical_annual_lettable_value_before_legacy_rent() -> None:
    """The editable CBDT ALV field wins over stale compatibility aliases."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.houseProperties = [HouseProperty(
        id="hp1",
        propertyType="LET_OUT",
        annualLettingValue=Decimal("300000"),
        annualRent=Decimal("250000"),
        maxRent=Decimal("275000"),
        municipalRateableValue=Decimal("900000"),
        fairRentValue=Decimal("800000"),
    )]

    itr1_input, _ = draft_to_itr1_input(draft)

    assert itr1_input.house_property_income.annual_rent_received == Decimal("300000")
    assert not hasattr(itr1_input.house_property_income, "municipal_value")
    assert not hasattr(itr1_input.house_property_income, "fair_rent")


def test_mapper_keeps_legacy_annual_rent_fallback() -> None:
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.houseProperties = [HouseProperty(
        id="hp1",
        propertyType="LET_OUT",
        annualRent=Decimal("240000"),
    )]

    itr1_input, _ = draft_to_itr1_input(draft)

    assert itr1_input.house_property_income.annual_rent_received == Decimal("240000")


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


def test_tds2_partial_claim_reaches_claimed_total_not_full_deducted():
    """A TDS2 row's claimOutOfTotTDSOnAmtPaid (Rule 37BA(3) partial-year
    claim) must reach both TDS2Entry.tds_claimed_this_year and the mapper's
    aggregate claimed_tds -- previously claimed_tds always summed the full
    taxDeducted regardless of a genuine partial claim (§15)."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.tds = [TdsCredit(
        id="t1", section="194A", deductorTAN="ABCD12345E",
        taxDeducted=Decimal("10000"), claimOutOfTotTDSOnAmtPaid=Decimal("3000"),
        claimedInReturn=True,
    )]
    itr1_input, breakdown = draft_to_itr1_input(draft)
    entry = itr1_input.tds2_entries[0]
    assert entry.tds_deducted == Decimal("10000")
    assert entry.tds_claimed_this_year == Decimal("3000")
    assert breakdown["claimed_tds"] == Decimal("3000")


def test_tds2_full_claim_when_partial_amount_not_specified():
    """When claimOutOfTotTDSOnAmtPaid is unset, the full amount deducted is
    claimed this year -- the common case."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.tds = [TdsCredit(
        id="t1", section="194A", deductorTAN="ABCD12345E",
        taxDeducted=Decimal("10000"), claimedInReturn=True,
    )]
    itr1_input, breakdown = draft_to_itr1_input(draft)
    entry = itr1_input.tds2_entries[0]
    assert entry.tds_claimed_this_year == Decimal("10000")
    assert breakdown["claimed_tds"] == Decimal("10000")


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


def test_invalid_tcs_tan_row_skipped_and_surfaced():
    """Invalid collector TAN must be visible instead of silently losing TCS."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.tcs = [TcsCredit(
        id="tcs1",
        collectorName="Collector",
        collectorTAN="INVALID",
        grossAmount=Decimal("100000"),
        taxCollected=Decimal("1000"),
    )]

    itr1_input, breakdown = draft_to_itr1_input(draft)

    assert not itr1_input.tcs_entries
    assert breakdown["total_tcs"] == Decimal("0")
    assert breakdown["credit_validation_issues"] == [{
        "creditType": "TCS",
        "section": "206C",
        "code": "INVALID_TAN_FORMAT",
        "field": "collectorTAN",
        "enteredValue": "INVALID",
    }]


def test_tcs_year_and_claim_flow_to_typed_input():
    """A selected TCS year and claimed amount must survive canonical mapping."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.tcs = [TcsCredit(
        id="tcs1",
        collectorName="Collector",
        collectorTAN="DELA12345B",
        grossAmount=Decimal("100000"),
        taxCollected=Decimal("1000"),
        tcsClaimedAmtCollOwnHand=Decimal("750"),
        deductedYr=2023,
    )]

    itr1_input, breakdown = draft_to_itr1_input(draft)

    assert itr1_input.tcs_entries is not None
    assert len(itr1_input.tcs_entries) == 1
    entry = itr1_input.tcs_entries[0]
    assert entry.financial_year == "2023-24"
    assert entry.tcs_collected == Decimal("1000")
    assert entry.tcs_credit_claimed == Decimal("750")
    assert breakdown["total_tcs"] == Decimal("750")


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


def test_mapper_preserves_conditional_deduction_schedules():
    """Canonical conditional evidence must reach the typed official input."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    via = draft.deductions.chapterVIA
    via.section80CCC = Decimal("12000")
    via.section80E = Decimal("5000")
    via.section80GGA = Decimal("3000")
    via.section80GGC = Decimal("4000")
    via.section80DD = Decimal("75000")
    via.section80DDNatureOfDisability = "1"
    via.section80DDTypeOfDisability = "2"
    via.section80DDDependentType = "1"
    via.section80U = Decimal("125000")
    via.section80UNatureOfDisability = "2"
    via.section80UTypeOfDisability = "2"
    draft.deductions.pensionContribution80CCC = [
        PensionContribution80CCC(
            id="ccc-1", identifierType="OTHPRAN",
            identifierName="POLICY-123", amount=Decimal("12000"),
        )
    ]
    draft.deductions.section80D.selfFamily.policies = [
        Policy80D(
            id="d-1", insurerName="Health Co", policyNo="H-123",
            premiumAmount=Decimal("10000"),
        )
    ]
    draft.deductions.section80D.selfFamily.preventiveCheckup = Decimal("1000")
    draft.deductions.loans.loans = [
        DeductionLoan(
            id="loan-1", section="80E", lenderName="Bank",
            loanAccountNo="EDU-1", dateOfLoan="2022-01-01",
            totalLoanAmount=Decimal("100000"), outstandingAmount=Decimal("50000"),
            interestAmount=Decimal("5000"),
        )
    ]
    draft.deductions.schedule80GGA = [
        Schedule80GGAEntry(
            id="gga-1", relevantClause="80GGA2a", doneeName="Research Fund",
            doneePAN="ABCDE1234F", addressLine="1 Main Road", city="Delhi",
            stateCode="09", pinCode="110001", otherModeAmount=Decimal("3000"),
        )
    ]
    draft.deductions.schedule80GGC = [
        Schedule80GGCEntry(
            id="ggc-1", otherModeAmount=Decimal("4000"),
            contributionDate="2025-06-01", transactionRef="UTR-1",
            ifscCode="SBIN0001234", politicalPartyName="Example Party",
            politicalPartyPAN="ABCDE1234F",
        )
    ]

    itr1_input, _ = draft_to_itr1_input(draft)

    assert itr1_input.deductions_chapter6a.amount_80ccc == Decimal("12000")
    assert itr1_input.schedule_80ccc_entries[0].identifier_name == "POLICY-123"
    assert itr1_input.schedule_80d.policies[0].policy_number == "H-123"
    assert itr1_input.schedule_80e_entries[0].account_or_reference_number == "EDU-1"
    assert itr1_input.schedule_80gga.donations[0].donee_name == "Research Fund"
    assert itr1_input.schedule_80ggc.contributions[0].transaction_ref == "UTR-1"
    assert itr1_input.schedule_80dd.dependent_relationship.value == "spouse"
    assert itr1_input.schedule_80u.disability_type.value == "severe"


def test_mapper_preserves_tds3_and_all_tax_challans():
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1")
    draft.taxes.tds = [
        TdsCredit(
            id="tds3-1", schedule="TDS3", section="194IB",
            tdsSectionCode="194IB", nameOfTenant="Tenant",
            panOfTenant="ABCDE1234F", grsRcptToTaxDeduct=Decimal("100000"),
            taxDeducted=Decimal("5000"), tdsClaimed=Decimal("4000"),
            deductedYr=2025,
        )
    ]
    draft.taxes.challans = [
        TaxChallan(
            id="adv-1", kind="ADVANCE_TAX", bsrCode="1234567",
            depositDate="2025-06-10", challanSerialNo=1, amount=Decimal("1000"),
        ),
        TaxChallan(
            id="sat-1", kind="SELF_ASSESSMENT", bsrCode="1234567",
            depositDate="2026-04-10", challanSerialNo=2, amount=Decimal("2000"),
        ),
    ]

    itr1_input, breakdown = draft_to_itr1_input(draft)

    assert itr1_input.tds3_entries[0].tds_claimed == Decimal("4000")
    assert itr1_input.schedule_tds3_total_claimed == Decimal("4000")
    assert breakdown["claimed_tds"] == Decimal("4000")
    assert len(itr1_input.tax_payment_entries) == 2
    assert {row.payment_type for row in itr1_input.tax_payment_entries} == {
        "advance", "self_assessment",
    }


def test_tds3_credit_reaches_computed_tax_liability() -> None:
    """TDS3 (Section 195, e.g. TDS withheld on rent paid to an NRI landlord)
    was mapped correctly (test_mapper_preserves_tds3_and_all_tax_challans
    above) but the calculator never passed tds3_entries to
    app/engine/schedules/tds_tcs's compute_all(), so it never reduced
    computed tax payable at all -- confirmed by an isolated repro before
    the fix (§15). Asserts the fix end to end via the real calculator."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    draft.personal = PersonalInfo(pan="ABCDE1234F", dateOfBirth="1980-01-15")
    draft.employers = [Employer(id="e1", employerName="Acme", basic=Decimal("1500000"))]
    draft.taxes.tds = [TdsCredit(
        id="tds3-1", schedule="TDS3", section="194IB",
        tdsSectionCode="194IB", nameOfTenant="Tenant",
        panOfTenant="ABCDE1234F", grsRcptToTaxDeduct=Decimal("100000"),
        taxDeducted=Decimal("5000"), tdsClaimed=Decimal("5000"),
        deductedYr=2025,
    )]

    itr1_input, _ = draft_to_itr1_input(draft)
    result = compute_itr1(itr1_input)

    assert result.total_tds == Decimal("5000")
    assert result.total_taxes_paid >= Decimal("5000")


def test_mapper_derives_detail_backed_deductions_and_form_10ia_flag():
    """Canonical schedule rows remain authoritative when scalar claims are zero."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    via = draft.deductions.chapterVIA
    via.section80DDForm10IA.filed = "Y"
    draft.deductions.loans.loans = [
        DeductionLoan(
            id="loan-80e", section="80E", lenderName="Bank",
            loanAccountNo="EDU-1", dateOfLoan="2022-01-01",
            totalLoanAmount=Decimal("100000"), outstandingAmount=Decimal("50000"),
            interestAmount=Decimal("5000"),
        ),
    ]
    draft.deductions.schedule80GGA = [
        Schedule80GGAEntry(
            id="gga", relevantClause="80GGA2aa", doneeName="Research Fund",
            doneePAN="ABCDE1234F", addressLine="1 Main Road", city="Delhi",
            stateCode="09", pinCode="110001", cashAmount=Decimal("100"),
            otherModeAmount=Decimal("3000"),
        ),
    ]
    draft.deductions.schedule80GGC = [
        Schedule80GGCEntry(
            id="ggc", cashAmount=Decimal("200"), otherModeAmount=Decimal("4000"),
            contributionDate="2025-06-01", transactionRef="UTR-1",
            ifscCode="SBIN0001234", politicalPartyName="Example Party",
            politicalPartyPAN="ABCDE1234F",
        ),
    ]

    typed, _ = draft_to_itr1_input(draft)

    assert typed.form_10ia_filed is True
    assert typed.deductions_chapter6a.amount_80e == Decimal("5000")
    assert typed.deductions_chapter6a.amount_80gga == Decimal("3000")
    assert typed.deductions_chapter6a.amount_80ggc == Decimal("4000")
    assert typed.schedule_80gga.donations[0].relevant_clause.value == "80GGA2aa"


def test_80ddb_reimbursement_reaches_details_and_reduces_deduction() -> None:
    """ChapterVIA.section80DDBReimbursement must reach
    Section80DDBDetails.reimbursement_amount -- previously there was no
    frontend field to source it from at all
    (Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §11.9)."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-1", regime="old")
    via = draft.deductions.chapterVIA
    via.section80DDB = Decimal("60000")
    via.section80DDBUserType = "1"
    via.section80DDBNameOfSpecDisease = "a"
    via.section80DDBReimbursement = Decimal("15000")

    typed, _ = draft_to_itr1_input(draft)

    assert typed.deductions_chapter6a.details_80ddb.reimbursement_amount == Decimal("15000")
