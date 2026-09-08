"""Section 80CCH — Agniveer Corpus Fund.

Deduction for contributions to the Agniveer Corpus Fund (Agneepath Scheme).
Section 80CCH has NO statutory rupee ceiling — the full contribution amount
is deductible.

Allowed in BOTH old and new regimes (Section 115BAC).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.schemas.itr1 import Chapter6ADeductions, TaxRegime

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80CCHResult:
    """Complete Section 80CCH statutory computation result."""

    user_claim: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO


def compute_details(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Section80CCHResult:
    """Compute Section 80CCH Agniveer Corpus Fund contribution deduction.

    Args:
        ded: Chapter VI-A deductions carrying amount_80cch.
        regime: Tax regime — 80CCH is allowed in both old and new regimes.

    Returns:
        A typed result with the allowed deduction (full contribution,
        no statutory cap).
    """
    user_claim = ded.amount_80cch if ded else _ZERO
    if ded is None or user_claim <= _ZERO:
        return Section80CCHResult(user_claim=user_claim)
    return Section80CCHResult(
        user_claim=user_claim,
        allowed_deduction=user_claim,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return the allowed Section 80CCH deduction for scalar callers."""
    return compute_details(ded, regime).allowed_deduction
