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
from app.schemas.itr1 import (
    AgeBracket,
    Chapter6ADeductions,
    Section80DDBUserType,
    TaxRegime,
)
from app.engine.constants import SECTION_80DDB_LIMIT, SECTION_80DDB_SENIOR_LIMIT


def compute(
    ded: Optional[Chapter6ADeductions],
    age_bracket: AgeBracket,
    regime: TaxRegime,
    *,
    use_structured_details: bool = False,
) -> Decimal:
    """Return the net eligible deduction after reimbursement and category cap."""
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    details = ded.details_80ddb if use_structured_details else None
    if details is not None:
        is_senior = details.user_type is Section80DDBUserType.SELF_OR_DEPENDENT_SENIOR
        net_expenditure = max(
            Decimal("0"),
            ded.amount_80ddb - details.reimbursement_amount,
        )
    else:
        is_senior = age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)
        net_expenditure = ded.amount_80ddb
    cap = SECTION_80DDB_SENIOR_LIMIT if is_senior else SECTION_80DDB_LIMIT
    return min(net_expenditure, cap)
