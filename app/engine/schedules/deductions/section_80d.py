"""
Section 80D — Health Insurance Premium.

Sub-limits:
  - Self, spouse, dependent children:
      - Non-senior: ₹25,000
      - Senior citizen (60+): ₹50,000
  - Parents:
      - Non-senior: ₹25,000
      - Senior citizen (60+): ₹50,000
  - Preventive health check-up: ₹5,000 (included within above limits)

Aggregate limit (self + parents): ₹1,00,000.
Not available under the new regime (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, AgeBracket, TaxRegime
from app.engine.constants import (
    SECTION_80D_SELF_FAMILY_LIMIT,
    SECTION_80D_SELF_FAMILY_SENIOR_LIMIT,
    SECTION_80D_PARENTS_LIMIT,
    SECTION_80D_PARENTS_SENIOR_LIMIT,
    SECTION_80D_PREVENTIVE_CHECKUP_LIMIT,
)


def compute(ded: Optional[Chapter6ADeductions], age_bracket: AgeBracket, regime: TaxRegime,
            is_parents_senior: bool = False) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")

    is_senior = age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)

    # Self + family bucket: insurance premium + preventive check-up
    # Preventive check-up is capped at Rs 5,000 within the bucket
    cap_self = SECTION_80D_SELF_FAMILY_SENIOR_LIMIT if is_senior else SECTION_80D_SELF_FAMILY_LIMIT
    preventive_self_capped = min(
        ded.amount_80d_preventive_self,
        SECTION_80D_PREVENTIVE_CHECKUP_LIMIT,
    )
    total_self = ded.amount_80d_self_family + preventive_self_capped
    ded_self = min(total_self, cap_self)

    # Parents bucket: insurance premium + preventive check-up
    parents_cap = SECTION_80D_PARENTS_SENIOR_LIMIT if is_parents_senior else SECTION_80D_PARENTS_LIMIT
    preventive_parents_capped = min(
        ded.amount_80d_preventive_parents,
        SECTION_80D_PREVENTIVE_CHECKUP_LIMIT,
    )
    total_parents = ded.amount_80d_parents + preventive_parents_capped
    ded_parents = min(total_parents, parents_cap)

    return ded_self + ded_parents
