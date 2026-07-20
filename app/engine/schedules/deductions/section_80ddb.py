"""
Section 80DDB — Medical Treatment for Specified Diseases.

Deduction for expenditure on medical treatment of specified diseases
(e.g., cancer, AIDS, neurological diseases, etc.).

  - Below 60 years: ₹40,000
  - Senior citizen (60+): ₹1,00,000

Reduced by any amount received from insurer or reimbursed by employer.
Not available under the new regime (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, AgeBracket, TaxRegime
from app.engine.constants import SECTION_80DDB_LIMIT, SECTION_80DDB_SENIOR_LIMIT


def compute(ded: Optional[Chapter6ADeductions], age_bracket: AgeBracket, regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    is_senior = age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)
    cap = SECTION_80DDB_SENIOR_LIMIT if is_senior else SECTION_80DDB_LIMIT
    return min(ded.amount_80ddb, cap)
