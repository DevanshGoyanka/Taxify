"""
Unit tests for app/engine/schedules/salary.py's Section 10(10)/10(10AA)
exemption formulas -- added while fixing
Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §11.1/§11.8.

Run: pytest tests/test_salary_schedule.py -v
"""

from __future__ import annotations

from decimal import Decimal

from app.engine.schedules.salary import (
    _exempt_commutted_pension,
    _exempt_gratuity,
    _exempt_leave_encashment,
    _exempt_uniform_allowance,
    compute,
)
from app.schemas.itr1 import SalaryIncome, TaxRegime


# ── Gratuity (Section 10(10)) ──────────────────────────────────────────────

def test_gratuity_govt_employee_fully_exempt_regardless_of_amount():
    assert _exempt_gratuity(Decimal("9999999"), True) == Decimal("9999999")


def test_gratuity_non_govt_capped_by_statutory_ceiling():
    """Received exceeds both the Rs 20L ceiling and the salary sub-limit;
    the salary sub-limit (0.5 x 200000 x 30 = 3,000,000) is looser than the
    Rs 20L ceiling here, so the ceiling binds."""
    result = _exempt_gratuity(
        Decimal("30000000"), False,
        average_monthly_salary=Decimal("200000"), years_of_service=30,
    )
    assert result == Decimal("2000000")


def test_gratuity_non_govt_capped_by_salary_sub_limit():
    """0.5 x average_monthly_salary x years_of_service is the tightest cap
    here (625,000), tighter than both the Rs 20L ceiling and the amount
    received."""
    result = _exempt_gratuity(
        Decimal("2500000"), False,
        average_monthly_salary=Decimal("50000"), years_of_service=25,
    )
    assert result == Decimal("625000")


def test_gratuity_non_govt_capped_by_amount_received():
    """Amount received is smaller than either statutory sub-limit."""
    result = _exempt_gratuity(
        Decimal("100000"), False,
        average_monthly_salary=Decimal("50000"), years_of_service=25,
    )
    assert result == Decimal("100000")


def test_gratuity_zero_without_average_salary_or_years_of_service():
    """No evidence of the salary sub-limit inputs -> exemption is zero,
    not an unbounded default. Mirrors this codebase's established
    recompute-from-evidence philosophy (HRA/LTA)."""
    result = _exempt_gratuity(Decimal("500000"), False)
    assert result == Decimal("0")


# ── Leave encashment (Section 10(10AA)) ────────────────────────────────────

def test_leave_encashment_govt_employee_fully_exempt():
    assert _exempt_leave_encashment(Decimal("9999999"), True) == Decimal("9999999")


def test_leave_encashment_non_govt_capped_by_cash_equivalent_of_leave():
    """unavailed_leave_days (200) is within the 30-days-per-year statutory
    cap (30*25=750), so cash equivalent = 200/30 * 40000 = 266,666.67,
    tighter than both the Rs 25L ceiling and the 10-months' average
    salary sub-limit (400,000)."""
    result = _exempt_leave_encashment(
        Decimal("2500000"), False,
        average_monthly_salary=Decimal("40000"), years_of_service=25,
        unavailed_leave_days=200,
    )
    assert result == (Decimal("200") / Decimal("30")) * Decimal("40000")


def test_leave_encashment_unavailed_days_capped_at_30_per_year_of_service():
    """unavailed_leave_days (750) exceeds the statutory 30-days-per-year
    cap for 10 years of service (300 days) -- the excess must not inflate
    the cash-equivalent sub-limit."""
    uncapped = _exempt_leave_encashment(
        Decimal("2500000"), False,
        average_monthly_salary=Decimal("40000"), years_of_service=10,
        unavailed_leave_days=750,
    )
    capped_at_statutory_max = _exempt_leave_encashment(
        Decimal("2500000"), False,
        average_monthly_salary=Decimal("40000"), years_of_service=10,
        unavailed_leave_days=300,
    )
    assert uncapped == capped_at_statutory_max


def test_leave_encashment_non_govt_capped_by_ten_months_average_salary():
    result = _exempt_leave_encashment(
        Decimal("2500000"), False,
        average_monthly_salary=Decimal("30000"), years_of_service=40,
        unavailed_leave_days=1200,
    )
    assert result == Decimal("300000")  # 10 * 30000


def test_leave_encashment_zero_without_evidence():
    result = _exempt_leave_encashment(Decimal("500000"), False)
    assert result == Decimal("0")


# ── End-to-end compute() wiring ────────────────────────────────────────────

def test_retrenchment_compensation_capped_and_exposed_on_result():
    """retrenchment_exempt must be exposed on SalaryResult (it was
    previously computed and folded into exempt_allowances but never
    exposed -- app/engine/itd/itr1.py's JSON row fell back to the raw,
    uncapped received amount as a result; §11.7)."""
    salary_input = SalaryIncome(
        gross_salary=Decimal("500000"),
        retrenchment_compensation=Decimal("800000"),
    )
    result = compute(salary_input, TaxRegime.OLD)
    assert result.retrenchment_exempt == Decimal("500000")  # Rs 5L ceiling


def test_disabled_employee_transport_exemption_reads_real_field():
    """is_disabled_employee is a real, declared SalaryIncome field now --
    previously getattr(..., False) always returned False since the field
    did not exist (§11.3)."""
    salary_input = SalaryIncome(
        gross_salary=Decimal("500000"),
        transport_allowance=Decimal("25000"),
        is_disabled_employee=True,
    )
    result = compute(salary_input, TaxRegime.OLD)
    assert result.transport_exempt == Decimal("25000")


def test_disabled_employee_transport_exemption_capped_at_38400():
    """Sec 10(14)(ii) read with Rule 2BB(1)(f): transport allowance for a
    blind/deaf-and-dumb/orthopedically-handicapped employee is exempt up
    to Rs 3,200/month = Rs 38,400/year -- confirmed against the primary
    source (CBDT ITR-4 Validation Rules rule 186). A prior bug capped this
    at Rs 19,200 (half the correct figure, the withdrawn general
    non-disability allowance's old rate) for every disabled employee."""
    salary_input = SalaryIncome(
        gross_salary=Decimal("500000"),
        transport_allowance=Decimal("50000"),
        is_disabled_employee=True,
    )
    result = compute(salary_input, TaxRegime.OLD)
    assert result.transport_exempt == Decimal("38400")


def test_children_allowances_use_real_number_of_children():
    """number_of_children is read from the schema, not hardcoded to 0
    (§11.2)."""
    salary_input = SalaryIncome(
        gross_salary=Decimal("500000"),
        sec10_14i_prescribed_allowance=Decimal("5000"),
        sec10_14ii_personal_allowance=Decimal("10000"),
        number_of_children=2,
    )
    result = compute(salary_input, TaxRegime.OLD)
    assert result.children_education_exempt == Decimal("2400")  # 100*12*2
    assert result.hostel_exempt == Decimal("7200")  # 300*12*2


# ── Commuted pension (Section 10(10A)) — gratuity-also-received fraction ──

def test_commuted_pension_govt_fully_exempt():
    assert _exempt_commutted_pension(Decimal("500000"), True) == Decimal("500000")


def test_commuted_pension_non_govt_one_third_when_gratuity_also_received():
    result = _exempt_commutted_pension(Decimal("300000"), False, True)
    assert round(result, 2) == Decimal("100000.00")  # 300000 / 3 (1/3 is a repeating decimal)


def test_commuted_pension_non_govt_one_half_when_no_gratuity():
    """The more generous 1/2 fraction applies when no separate gratuity was
    received -- previously always used the 1/3rd fraction unconditionally,
    since employer.gratuityAlsoReceived (captured on the frontend) was
    never wired to the calculator (§11.9 follow-up)."""
    result = _exempt_commutted_pension(Decimal("300000"), False, False)
    assert result == Decimal("150000")  # 300000 / 2


def test_commuted_pension_defaults_to_conservative_one_third():
    """Caller omitting the flag gets the lower (1/3rd), not the more
    generous (1/2), fraction -- never over-grant without evidence."""
    result = _exempt_commutted_pension(Decimal("300000"), False)
    assert round(result, 2) == Decimal("100000.00")


# ── Uniform allowance (Section 10(14)(i) / Rule 2BB(1)(f)) ─────────────────
# Added closing Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md
# §11.9/§19's documented-but-deferred gap: unlike CEA/hostel (a fixed
# per-child/month statutory rate), this allowance is exempt only to the
# extent of actual expenditure incurred, so it needed its own
# received/expenditure evidence pair rather than reusing
# sec10_14i_prescribed_allowance's fixed-rate formula.

def test_uniform_allowance_exempt_is_lesser_of_received_and_actual_expenditure():
    assert _exempt_uniform_allowance(Decimal("12000"), Decimal("8000")) == Decimal("8000")


def test_uniform_allowance_exempt_capped_at_amount_received():
    """Substantiated expenditure exceeding the received allowance cannot make
    the exemption bigger than what was actually received."""
    assert _exempt_uniform_allowance(Decimal("5000"), Decimal("9000")) == Decimal("5000")


def test_uniform_allowance_no_exemption_without_expenditure_evidence():
    """No expenditure evidence -> no exemption, matching the conservative
    default already used elsewhere: the received amount still reaches
    taxable income (via the mapper), it just isn't exempted."""
    assert _exempt_uniform_allowance(Decimal("12000"), Decimal("0")) == Decimal("0")


def test_uniform_allowance_exempt_reduces_old_regime_chargeable_income():
    si = SalaryIncome(
        gross_salary=Decimal("600000"),
        uniform_allowance_received=Decimal("10000"),
        uniform_allowance_actual_expenditure=Decimal("7000"),
    )
    result = compute(si, TaxRegime.OLD)
    assert result.uniform_allowance_exempt == Decimal("7000")
    # gross_salary includes the received amount (already taxed as income
    # elsewhere in the mapper); the exemption reduces net_salary by the
    # substantiated 7,000, not the full 10,000 received.
    assert result.exempt_allowances >= Decimal("7000")


def test_uniform_allowance_exempt_disallowed_under_new_regime():
    """Section 10(14)(i)/Rule 2BB(1) general allowances (uniform allowance
    included) are disallowed under the new regime, same category as HRA/LTA
    per CBDT Rule 149."""
    si = SalaryIncome(
        gross_salary=Decimal("600000"),
        uniform_allowance_received=Decimal("10000"),
        uniform_allowance_actual_expenditure=Decimal("7000"),
    )
    result = compute(si, TaxRegime.NEW)
    assert result.uniform_allowance_exempt == Decimal("0")


# ── Children education / hostel allowance (Section 10(14)(i)/(ii)) ─────────
# Added closing Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §20.6's
# flagged-but-unfixed gap: unlike HRA/LTA/uniform allowance, CEA and hostel
# exemptions were never zeroed under the new regime here, even though both
# ITR1-R166/R167 and ITR4-R200/R201 already hard-block a positive claim at
# the input-validation layer -- the calculator must independently agree.

def test_cea_and_hostel_exempt_apply_under_old_regime():
    si = SalaryIncome(
        gross_salary=Decimal("600000"),
        sec10_14i_prescribed_allowance=Decimal("2400"),
        sec10_14ii_personal_allowance=Decimal("7200"),
        number_of_children=2,
    )
    result = compute(si, TaxRegime.OLD)
    assert result.children_education_exempt == Decimal("2400")
    assert result.hostel_exempt == Decimal("7200")


def test_cea_and_hostel_exempt_disallowed_under_new_regime():
    """Rule 2BB(1)(f) personal allowances (children education, hostel
    expenditure) are disallowed under the new regime, same category as
    HRA/LTA/uniform allowance per CBDT Rule 149 -- confirmed by both forms'
    validators (ITR1-R166/R167, ITR4-R200/R201) already hard-blocking a
    positive sec10_14i/sec10_14ii claim under the new regime."""
    si = SalaryIncome(
        gross_salary=Decimal("600000"),
        sec10_14i_prescribed_allowance=Decimal("2400"),
        sec10_14ii_personal_allowance=Decimal("7200"),
        number_of_children=2,
    )
    result = compute(si, TaxRegime.NEW)
    assert result.children_education_exempt == Decimal("0")
    assert result.hostel_exempt == Decimal("0")
    assert result.exempt_allowances == Decimal("0")
