"""
Schedule S: Salary Income (u/s 15-17).

Sec 17(1): Salary
Sec 17(2): Perquisites
Sec 17(3): Profits in lieu of salary

Deductions u/s 16:
  - (ia) Standard deduction: Old=50K, New=75K
  - (ii) Entertainment allowance: 5K govt employees only (old regime)
  - (iii) Professional tax: actual, capped 5K (old regime)
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from app.engine.constants import OLD_REGIME_STANDARD_DEDUCTION, NEW_REGIME_STANDARD_DEDUCTION
from app.schemas.itr1 import SalaryIncome, TaxRegime


@dataclass
class SalaryResult:
    gross_salary: Decimal = Decimal("0")
    exempt_allowances: Decimal = Decimal("0")
    net_salary: Decimal = Decimal("0")
    standard_deduction: Decimal = Decimal("0")
    entertainment_allowance: Decimal = Decimal("0")
    professional_tax: Decimal = Decimal("0")
    deductions_u16: Decimal = Decimal("0")
    income_chargeable: Decimal = Decimal("0")


def compute(input_data: Optional[SalaryIncome], regime: TaxRegime) -> SalaryResult:
    if not input_data:
        return SalaryResult()

    gross = input_data.gross_salary + input_data.perquisites_value + input_data.profits_in_lieu_of_salary

    exempt_allowances = sum((
        input_data.hra_exempt_amount,
        input_data.lta_exempt_amount,
        input_data.gratuity_received,
        input_data.commuted_pension_received,
        input_data.leave_encashment_received,
        input_data.vrs_compensation,
        input_data.retrenchment_compensation,
        input_data.sec10_6_embassy_exempt,
        input_data.sec10_7_foreign_allowance,
        input_data.sec10_10cc_perquisite_tax,
        input_data.sec10_14i_prescribed_allowance,
        input_data.sec10_14ii_personal_allowance,
    ), Decimal("0"))

    if regime == TaxRegime.OLD:
        hra = input_data.hra_exempt_amount
        lta = input_data.lta_exempt_amount
        prof_tax = min(input_data.professional_tax_paid, Decimal("2500"))
        is_govt = getattr(input_data, "is_government_employee", False)
        if is_govt and input_data.entertainment_allowance > 0:
            # CBDT Rule 57 / Section 16(ii): the entertainment allowance
            # deduction is the least of:
            #   (a) Rs 5,000 (statutory ceiling)
            #   (b) 1/5th of salary (excluding the entertainment allowance)
            #   (c) 20% of basic salary
            # "Salary" for this test is Section 17(1) salary excluding the
            # entertainment allowance component itself.
            salary_excl_ent = max(
                Decimal("0"),
                input_data.gross_salary - input_data.entertainment_allowance,
            )
            one_fifth_salary = salary_excl_ent / Decimal("5")
            # 20% of basic: approximate basic as the 17(1) gross salary,
            # since a dedicated basic field is not exposed on the schema.
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
        std_ded = OLD_REGIME_STANDARD_DEDUCTION
        chargeable = net_before_std - std_ded - prof_tax - ent_allowance
    else:
        std_ded = NEW_REGIME_STANDARD_DEDUCTION
        chargeable = gross - exempt_allowances - std_ded
        hra = Decimal("0")
        lta = Decimal("0")
        prof_tax = Decimal("0")
        ent_allowance = Decimal("0")

    return SalaryResult(
        gross_salary=gross,
        exempt_allowances=exempt_allowances,
        net_salary=gross - exempt_allowances,
        standard_deduction=std_ded,
        entertainment_allowance=ent_allowance,
        professional_tax=prof_tax,
        deductions_u16=std_ded + ent_allowance + prof_tax,
        income_chargeable=max(Decimal("0"), chargeable),
    )
