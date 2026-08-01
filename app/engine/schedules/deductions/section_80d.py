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

    preventive_self = min(
        ded.amount_80d_preventive_self,
        SECTION_80D_PREVENTIVE_CHECKUP_LIMIT,
    )
    preventive_parents = min(
        ded.amount_80d_preventive_parents,
        max(Decimal("0"), SECTION_80D_PREVENTIVE_CHECKUP_LIMIT - preventive_self),
    )

    # Self + family bucket: insurance premium plus its share of the aggregate
    # preventive-checkup sub-limit.
    cap_self = SECTION_80D_SELF_FAMILY_SENIOR_LIMIT if is_senior else SECTION_80D_SELF_FAMILY_LIMIT
    total_self = ded.amount_80d_self_family + preventive_self
    ded_self = min(total_self, cap_self)

    # Parents bucket uses only the unconsumed part of the aggregate preventive
    # check-up limit and remains subject to its own overall bucket cap.
    parents_cap = SECTION_80D_PARENTS_SENIOR_LIMIT if is_parents_senior else SECTION_80D_PARENTS_LIMIT
    total_parents = ded.amount_80d_parents + preventive_parents
    ded_parents = min(total_parents, parents_cap)

    return ded_self + ded_parents
