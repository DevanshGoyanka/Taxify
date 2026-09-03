"""Section 80CCD(2) — Employer NPS Contribution.

Employer's contribution to NPS (Central/State Govt or other employer).
Statutory ceiling, old regime: Government employees (Central/State) up to
14% of salary; other employees up to 10% of salary.

Finance (No. 2) Act 2024 raised the ceiling to 14% of salary for ALL
employers (not just Central/State Government) specifically for assessees
who have opted for the new regime u/s 115BAC — confirmed independently by
this codebase's own ITR-1/ITR-4 validators (``ITR1-R216``, ``ITR4-R263``),
which apply a flat 14% cap under the new regime with no employer-category
distinction at all. Allowed in BOTH old and new regimes; only the rate
differs by regime for non-government employers.

"Salary" for this purpose means basic salary + dearness allowance
(if forming part of retirement benefits per CBSDA). We approximate using
the Section 17(1) gross salary when a dedicated basic+DA figure is not
available.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.schemas.itr1 import Chapter6ADeductions, TaxRegime

_ZERO = Decimal("0")

# Statutory ceilings on employer NPS contribution as a fraction of salary.
_NPS_GOV_T_PCT = Decimal("0.14")   # 14% for Central/State Government employees (both regimes)
_NPS_GOV_T_PCT_OTHER_OLD = Decimal("0.10")  # 10% for other employers, old regime
_NPS_GOV_T_PCT_OTHER_NEW = Decimal("0.14")  # 14% for other employers, new regime (FA 2024)


@dataclass(frozen=True)
class Section80CCD2Result:
    """Complete Section 80CCD(2) statutory computation result."""

    user_claim: Decimal = _ZERO
    statutory_ceiling: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO


def compute_details(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
    *,
    salary: Decimal = _ZERO,
    is_government_employee: bool = False,
) -> Section80CCD2Result:
    """Compute Section 80CCD(2) employer NPS contribution deduction.

    Args:
        ded: Chapter VI-A deductions carrying amount_80ccd2.
        regime: Tax regime — 80CCD(2) is allowed in both old and new regimes,
            but the ceiling for non-government employers depends on which
            (14% new regime, 10% old regime; Central/State Government
            employers are 14% under both).
        salary: Section 17(1) salary used to apply the ceiling.
        is_government_employee: Whether the employer is specifically
            Central/State Government (narrower than ITR-1's
            SalaryIncome.is_government_employee, which also includes PSU
            for Section 16(ii) purposes -- this parameter must receive the
            CG/SG-only flag).

    Returns:
        A typed result with the statutory ceiling and the allowed
        deduction (the lesser of the user claim and the ceiling).
    """
    user_claim = ded.amount_80ccd2 if ded else _ZERO
    if ded is None or user_claim <= _ZERO:
        return Section80CCD2Result(user_claim=user_claim)

    if is_government_employee:
        pct = _NPS_GOV_T_PCT
    elif regime == TaxRegime.NEW:
        pct = _NPS_GOV_T_PCT_OTHER_NEW
    else:
        pct = _NPS_GOV_T_PCT_OTHER_OLD
    ceiling = (salary * pct) if salary > _ZERO else user_claim
    allowed = min(user_claim, ceiling)

    return Section80CCD2Result(
        user_claim=user_claim,
        statutory_ceiling=ceiling,
        allowed_deduction=allowed,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
    *,
    salary: Decimal = _ZERO,
    is_government_employee: bool = False,
) -> Decimal:
    """Return the allowed Section 80CCD(2) deduction for scalar callers."""
    return compute_details(
        ded, regime, salary=salary, is_government_employee=is_government_employee
    ).allowed_deduction

