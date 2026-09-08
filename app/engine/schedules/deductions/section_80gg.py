"""Section 80GG — Rent Paid (No HRA).

Deduction for rent paid by an individual who does NOT receive HRA as part
of salary (i.e., Section 10(13A) not applicable).

Minimum of three conditions:
  1. ₹60,000 per annum (₹5,000 x 12)
  2. 25% of adjusted total income (GTI minus LTCG 112A + STCG 111A +
     all other Chapter VI-A deductions except 80GG)
  3. Rent paid minus 10% of adjusted total income

Additional conditions:
  - Assessee, spouse, or minor child should NOT own a residential
    accommodation at the place of employment/business.
  - Assessee should not own self-occupied property elsewhere (claimed as
    self-occupied).
  - Form 10BA must be filed.

adjusted_gti = GTI minus all other Chapter VI-A deductions (except 80G/80GG).

Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.engine.constants import (
    SECTION_80GG_GTI_PERCENT,
    SECTION_80GG_RENT_LIMIT,
)
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80GGResult:
    """Complete Section 80GG statutory computation result."""

    user_claim: Decimal = _ZERO
    adjusted_gti: Decimal = _ZERO
    statutory_limit_rent: Decimal = _ZERO
    statutory_limit_gti: Decimal = _ZERO
    statutory_limit_net: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    hra_exempt: Decimal = _ZERO


def compute_details(
    ded: Optional[Chapter6ADeductions],
    adjusted_gti: Decimal,
    regime: TaxRegime,
    *,
    hra_exempt_amount: Decimal = _ZERO,
) -> Section80GGResult:
    """Compute Section 80GG rent deduction.

    Args:
        ded: Chapter VI-A deductions carrying amount_80gg (rent paid).
        adjusted_gti: GTI minus all other Chapter VI-A deductions and LTCG/STCG.
        regime: Tax regime — new regime disallows 80GG.
        hra_exempt_amount: HRA exemption under s.10(13A); 80GG is unavailable
            when this is positive.

    Returns:
        A typed result with the three statutory limits and the allowed
        deduction (their minimum).
    """
    user_claim = ded.amount_80gg if ded else _ZERO
    if ded is None or regime == TaxRegime.NEW or user_claim <= _ZERO:
        return Section80GGResult(
            user_claim=user_claim,
            adjusted_gti=adjusted_gti,
            hra_exempt=hra_exempt_amount,
        )
    if hra_exempt_amount > 0:
        return Section80GGResult(
            user_claim=user_claim,
            adjusted_gti=adjusted_gti,
            hra_exempt=hra_exempt_amount,
        )
    if adjusted_gti <= 0:
        return Section80GGResult(
            user_claim=user_claim,
            adjusted_gti=adjusted_gti,
            hra_exempt=hra_exempt_amount,
        )

    limit1 = SECTION_80GG_RENT_LIMIT
    limit2 = adjusted_gti * SECTION_80GG_GTI_PERCENT
    limit3 = max(_ZERO, user_claim - adjusted_gti * Decimal("0.10"))
    allowed = max(_ZERO, min(limit1, limit2, limit3))
    return Section80GGResult(
        user_claim=user_claim,
        adjusted_gti=adjusted_gti,
        statutory_limit_rent=limit1,
        statutory_limit_gti=limit2,
        statutory_limit_net=limit3,
        allowed_deduction=allowed,
        hra_exempt=hra_exempt_amount,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    adjusted_gti: Decimal,
    regime: TaxRegime,
    *,
    hra_exempt_amount: Decimal = _ZERO,
) -> Decimal:
    """Return the allowed Section 80GG deduction for scalar callers."""
    return compute_details(
        ded, adjusted_gti, regime, hra_exempt_amount=hra_exempt_amount,
    ).allowed_deduction
