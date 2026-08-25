"""
Schedule S: Salary Income (u/s 15-17).

Sec 17(1): Salary
Sec 17(2): Perquisites
Sec 17(3): Profits in lieu of salary

Deductions u/s 16:
  - (ia) Standard deduction: Old=50K, New=75K
  - (ii) Entertainment allowance: least of {5K; 1/5th salary excl. ent; 20% basic} (govt, old only)
  - (iii) Professional tax: actual, capped 2,500 (old only)

Section 10 exemption ceilings applied to gross-received amounts:
  - 10(10)  Gratuity:      non-govt capped at Rs 20L; govt fully exempt
  - 10(10A) Commuted pension: non-govt — 1/3rd of commuted value; govt fully exempt
  - 10(10AA) Leave encashment: non-govt capped at Rs 25L; govt fully exempt
  - 10(10C) VRS compensation: capped at Rs 5L (lifetime)
  - 10(14)  Transport / CEA / Hostel: per-child / per-month statutory limits
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from app.engine.constants import (
    OLD_REGIME_STANDARD_DEDUCTION,
    NEW_REGIME_STANDARD_DEDUCTION,
    GRATUITY_EXEMPTION_LIMIT,
    LEAVE_ENCASHMENT_EXEMPTION_LIMIT,
    VRS_COMPENSATION_EXEMPTION_LIMIT,
    TRANSPORT_ALLOWANCE_DISABLED_LIMIT,
    CHILDREN_EDUCATION_ALLOWANCE_LIMIT,
    CHILDREN_EDUCATION_ALLOWANCE_PER_CHILD,
    CHILDREN_EDUCATION_MAX_CHILDREN,
    HOSTEL_ALLOWANCE_LIMIT,
    HOSTEL_ALLOWANCE_PER_CHILD,
    COMMUTED_PENSION_NON_GOV_T_PCT,
)
from app.schemas.itr1 import SalaryIncome, TaxRegime

_ZERO = Decimal("0")


@dataclass
class SalaryResult:
    """Complete salary schedule computation result."""

    gross_salary: Decimal = Decimal("0")
    exempt_allowances: Decimal = Decimal("0")
    net_salary: Decimal = Decimal("0")
    standard_deduction: Decimal = Decimal("0")
    entertainment_allowance: Decimal = Decimal("0")
    professional_tax: Decimal = Decimal("0")
    deductions_u16: Decimal = Decimal("0")
    income_chargeable: Decimal = Decimal("0")
    # Per-exemption breakdown for ITD JSON / display.
    gratuity_exempt: Decimal = Decimal("0")
    leave_encashment_exempt: Decimal = Decimal("0")
    vrs_exempt: Decimal = Decimal("0")
    commuted_pension_exempt: Decimal = Decimal("0")
    transport_exempt: Decimal = Decimal("0")
    children_education_exempt: Decimal = Decimal("0")
    hostel_exempt: Decimal = Decimal("0")
    hra_exempt: Decimal = Decimal("0")
    lta_exempt: Decimal = Decimal("0")


def _exempt_gratuity(received: Decimal, is_govt: bool) -> Decimal:
    """Exempt gratuity u/s 10(10): govt fully exempt; others capped at Rs 20L."""
    if is_govt:
        return max(_ZERO, received)
    return min(max(_ZERO, received), GRATUITY_EXEMPTION_LIMIT)


def _exempt_leave_encashment(received: Decimal, is_govt: bool) -> Decimal:
    """Exempt leave encashment u/s 10(10AA): govt fully; others capped at Rs 25L."""
    if is_govt:
        return max(_ZERO, received)
    return min(max(_ZERO, received), LEAVE_ENCASHMENT_EXEMPTION_LIMIT)


def _exempt_vrs(received: Decimal) -> Decimal:
    """Exempt VRS/retrenchment compensation u/s 10(10C): capped at Rs 5L."""
    return min(max(_ZERO, received), VRS_COMPENSATION_EXEMPTION_LIMIT)


def _exempt_commutted_pension(received: Decimal, is_govt: bool) -> Decimal:
    """Exempt commuted pension u/s 10(10A): govt fully; others — 1/3rd of value."""
    if is_govt:
        return max(_ZERO, received)
    return max(_ZERO, received) * COMMUTED_PENSION_NON_GOV_T_PCT


def _exempt_transport(allowance: Decimal, is_disabled: bool) -> Decimal:
    """Exempt transport allowance u/s 10(14): Rs 19,200/yr for disabled employees."""
    if not is_disabled:
        return _ZERO
    return min(max(_ZERO, allowance), TRANSPORT_ALLOWANCE_DISABLED_LIMIT)


def _exempt_children_education(allowance: Decimal, num_children: int) -> Decimal:
    """Exempt children education allowance u/s 10(14): Rs 100/mo per child (max 2)."""
    capped_children = min(max(0, num_children), CHILDREN_EDUCATION_MAX_CHILDREN)
    statutory = CHILDREN_EDUCATION_ALLOWANCE_PER_CHILD * Decimal(12) * Decimal(capped_children)
    return min(max(_ZERO, allowance), statutory)


def _exempt_hostel(allowance: Decimal, num_children: int) -> Decimal:
    """Exempt hostel expenditure allowance u/s 10(14): Rs 300/mo per child (max 2)."""
    capped_children = min(max(0, num_children), CHILDREN_EDUCATION_MAX_CHILDREN)
    statutory = HOSTEL_ALLOWANCE_PER_CHILD * Decimal(12) * Decimal(capped_children)
    return min(max(_ZERO, allowance), statutory)


def compute(input_data: Optional[SalaryIncome], regime: TaxRegime) -> SalaryResult:
    """Compute salary income chargeable u/s 15-17 with Section 10 exemptions and Section 16 deductions.

    Args:
        input_data: The salary income schema with gross components, exempt
            allowance amounts, and deduction inputs.
        regime: Tax regime — old regime allows HRA/LTA/entertainment/prof-tax
            exemptions; new regime allows only standard deduction.

    Returns:
        A typed result with per-exemption breakdown and the final
        chargeable salary income.
    """
    if not input_data:
        return SalaryResult()

    is_govt = getattr(input_data, "is_government_employee", False)
    gross = input_data.gross_salary + input_data.perquisites_value + input_data.profits_in_lieu_of_salary

    # Apply statutory exemption ceilings to each Section 10 component.
    # The schema captures *gross received* amounts; the engine computes the
    # *exempt portion* subject to CBDT ceilings.
    hra_exempt = input_data.hra_exempt_amount
    lta_exempt = input_data.lta_exempt_amount
    gratuity_exempt = _exempt_gratuity(input_data.gratuity_received, is_govt)
    leave_encashment_exempt = _exempt_leave_encashment(
        input_data.leave_encashment_received, is_govt,
    )
    commuted_pension_exempt = _exempt_commutted_pension(
        input_data.commuted_pension_received, is_govt,
    )
    vrs_exempt = _exempt_vrs(input_data.vrs_compensation)
    # Retrenchment compensation uses the same Rs 5L ceiling as VRS (10(10C)).
    retrenchment_exempt = _exempt_vrs(input_data.retrenchment_compensation)
    transport_exempt = _exempt_transport(
        input_data.transport_allowance,
        getattr(input_data, "is_disabled_employee", False),
    )
    # Children education and hostel allowances require number of children;
    # the schema does not yet have a dedicated field, so default to 0 children
    # (i.e., exemption = 0) unless the caller populates sec10_14i/14ii directly.
    children_education_exempt = _exempt_children_education(
        input_data.sec10_14i_prescribed_allowance, 0,
    )
    hostel_exempt = _exempt_hostel(input_data.sec10_14ii_personal_allowance, 0)

    exempt_allowances = sum((
        hra_exempt,
        lta_exempt,
        gratuity_exempt,
        commuted_pension_exempt,
        leave_encashment_exempt,
        vrs_exempt,
        retrenchment_exempt,
        input_data.sec10_6_embassy_exempt,
        input_data.sec10_7_foreign_allowance,
        input_data.sec10_10cc_perquisite_tax,
        transport_exempt,
        children_education_exempt,
        hostel_exempt,
    ), Decimal("0"))

    if regime == TaxRegime.OLD:
        prof_tax = min(input_data.professional_tax_paid, Decimal("2500"))
        if is_govt and input_data.entertainment_allowance > 0:
            # CBDT Rule 57 / Section 16(ii): the entertainment allowance
            # deduction is the least of:
            #   (a) Rs 5,000 (statutory ceiling)
            #   (b) 1/5th of salary (excluding the entertainment allowance)
            #   (c) 20% of basic salary
            salary_excl_ent = max(
                Decimal("0"),
                input_data.gross_salary - input_data.entertainment_allowance,
            )
            one_fifth_salary = salary_excl_ent / Decimal("5")
            twenty_pct_basic = input_data.gross_salary * Decimal("0.20")
            ent_allowance = min(
                Decimal("5000"),
                one_fifth_salary,
                twenty_pct_basic,
                input_data.entertainment_allowance,
            )
        else:
            ent_allowance = Decimal("0")
        net_before_std = max(Decimal("0"), gross - exempt_allowances)
        # Section 16 deductions cannot create a loss under the salary head.
        prof_tax = min(prof_tax, net_before_std)
        ent_allowance = min(ent_allowance, max(Decimal("0"), net_before_std - prof_tax))
        std_ded = min(
            OLD_REGIME_STANDARD_DEDUCTION,
            max(Decimal("0"), net_before_std - prof_tax - ent_allowance),
        )
        chargeable = net_before_std - std_ded - prof_tax - ent_allowance
    else:
        # New-regime HRA and LTA exemptions are disallowed before calculating
        # the available salary against which Section 16(ia) can be claimed.
        disallowed_hra_lta = hra_exempt + lta_exempt
        hra_exempt = Decimal("0")
        lta_exempt = Decimal("0")
        exempt_allowances = max(Decimal("0"), exempt_allowances - disallowed_hra_lta)
        net_before_std = max(Decimal("0"), gross - exempt_allowances)
        std_ded = min(NEW_REGIME_STANDARD_DEDUCTION, net_before_std)
        chargeable = net_before_std - std_ded
        prof_tax = Decimal("0")
        ent_allowance = Decimal("0")

    return SalaryResult(
        gross_salary=gross,
        exempt_allowances=exempt_allowances,
        net_salary=max(Decimal("0"), gross - exempt_allowances),
        standard_deduction=std_ded,
        entertainment_allowance=ent_allowance,
        professional_tax=prof_tax,
        deductions_u16=std_ded + ent_allowance + prof_tax,
        income_chargeable=max(Decimal("0"), chargeable),
        gratuity_exempt=gratuity_exempt,
        leave_encashment_exempt=leave_encashment_exempt,
        vrs_exempt=vrs_exempt,
        commuted_pension_exempt=commuted_pension_exempt,
        transport_exempt=transport_exempt,
        children_education_exempt=children_education_exempt,
        hostel_exempt=hostel_exempt,
        hra_exempt=hra_exempt,
        lta_exempt=lta_exempt,
    )
