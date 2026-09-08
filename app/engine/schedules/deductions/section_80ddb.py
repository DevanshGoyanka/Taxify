"""Section 80DDB — Medical Treatment for Specified Diseases.

Deduction for expenditure on medical treatment of specified diseases.

  - Non-senior beneficiary: ₹40,000
  - Senior-citizen beneficiary: ₹1,00,000

The eligible expenditure is reduced by insurance or employer reimbursement.
Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.engine.constants import SECTION_80DDB_LIMIT, SECTION_80DDB_SENIOR_LIMIT
from app.schemas.itr1 import (
    AgeBracket,
    Chapter6ADeductions,
    Section80DDBDetails,
    Section80DDBUserType,
    TaxRegime,
)

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80DDBResult:
    """Complete Section 80DDB statutory computation result."""

    gross_expenditure: Decimal = _ZERO
    reimbursement_amount: Decimal = _ZERO
    user_claim: Decimal = _ZERO
    statutory_eligible: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    source: Optional[Section80DDBDetails] = None


def compute_details(
    ded: Optional[Chapter6ADeductions],
    age_bracket: AgeBracket,
    regime: TaxRegime,
    *,
    use_structured_details: bool = False,
) -> Section80DDBResult:
    """Compute Section 80DDB from beneficiary and reimbursement details.

    Args:
        ded: Chapter VI-A deductions carrying gross expenditure and details.
        age_bracket: Assessee age used only by legacy scalar callers.
        regime: Tax regime — new regime disallows Section 80DDB.
        use_structured_details: Whether canonical beneficiary details are
            mandatory and authoritative.

    Returns:
        Typed gross, reimbursement, net user claim, statutory eligibility,
        allowed deduction, and source details.

    Raises:
        ValueError: If a positive structured claim lacks details, details are
            stale, or reimbursement exceeds gross expenditure.
    """
    gross = ded.amount_80ddb if ded else _ZERO
    details = ded.details_80ddb if ded else None

    if gross <= _ZERO:
        if use_structured_details and details is not None:
            raise ValueError("Section 80DDB details require positive expenditure")
        return Section80DDBResult(source=details)

    if use_structured_details and details is None:
        raise ValueError(
            "A positive Section 80DDB claim requires official beneficiary and disease details"
        )

    reimbursement = details.reimbursement_amount if details else _ZERO
    if reimbursement > gross:
        raise ValueError("Section 80DDB reimbursement cannot exceed expenditure")

    net_claim = gross - reimbursement
    if regime == TaxRegime.NEW:
        return Section80DDBResult(
            gross_expenditure=gross,
            reimbursement_amount=reimbursement,
            user_claim=net_claim,
            source=details,
        )

    if details is not None:
        is_senior = (
            details.user_type
            is Section80DDBUserType.SELF_OR_DEPENDENT_SENIOR
        )
    else:
        is_senior = age_bracket in (
            AgeBracket.SIXTY_TO_80,
            AgeBracket.ABOVE_80,
        )
    cap = SECTION_80DDB_SENIOR_LIMIT if is_senior else SECTION_80DDB_LIMIT
    statutory = min(net_claim, cap)
    return Section80DDBResult(
        gross_expenditure=gross,
        reimbursement_amount=reimbursement,
        user_claim=net_claim,
        statutory_eligible=statutory,
        allowed_deduction=statutory,
        source=details,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    age_bracket: AgeBracket,
    regime: TaxRegime,
    *,
    use_structured_details: bool = False,
) -> Decimal:
    """Return the allowed Section 80DDB deduction for scalar callers."""
    return compute_details(
        ded,
        age_bracket,
        regime,
        use_structured_details=use_structured_details,
    ).allowed_deduction
