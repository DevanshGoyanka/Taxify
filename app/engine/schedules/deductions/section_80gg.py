"""
Section 80GG — Rent Paid (No HRA).

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

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime
from app.engine.constants import SECTION_80GG_RENT_LIMIT, SECTION_80GG_GTI_PERCENT


def compute(
    ded: Optional[Chapter6ADeductions],
    adjusted_gti: Decimal,
    regime: TaxRegime,
    *,
    hra_exempt_amount: Decimal = Decimal("0"),
) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")

    # Section 80GG is NOT available if HRA is claimed (s.10(13A))
    if hra_exempt_amount > 0:
        return Decimal("0")

    rent_paid = ded.amount_80gg
    if rent_paid <= 0 or adjusted_gti <= 0:
        return Decimal("0")

    limit1 = SECTION_80GG_RENT_LIMIT
    limit2 = adjusted_gti * SECTION_80GG_GTI_PERCENT
    limit3 = max(Decimal("0"), rent_paid - adjusted_gti * Decimal("0.10"))

    return max(Decimal("0"), min(limit1, limit2, limit3))
