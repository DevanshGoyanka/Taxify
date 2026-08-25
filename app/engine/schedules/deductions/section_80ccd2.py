"""Section 80CCD(2) — Employer NPS Contribution.

Employer's contribution to NPS (Central/State Govt or other employer).
Statutory ceiling:
  - Government employees (Central/State): up to 14% of salary.
  - Other employees: up to 10% of salary.
Allowed in BOTH old and new regimes (Section 115BAC).

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
_NPS_GOV_T_PCT = Decimal("0.14")   # 14% for Central/State Government employees
_NPS_GOV_T_PCT_OTHER = Decimal("0.10")  # 10% for other employees


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
        regime: Tax regime — 80CCD(2) is allowed in both old and new regimes.
        salary: Section 17(1) salary used to apply the 10%/14% ceiling.
        is_government_employee: Whether the employer is Central/State
            Government (14% ceiling applies); other employers use 10%.

    Returns:
        A typed result with the statutory ceiling and the allowed
        deduction (the lesser of the user claim and the ceiling).
    """
    user_claim = ded.amount_80ccd2 if ded else _ZERO
    if ded is None or user_claim <= _ZERO:
        return Section80CCD2Result(user_claim=user_claim)

    pct = _NPS_GOV_T_PCT if is_government_employee else _NPS_GOV_T_PCT_OTHER
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

