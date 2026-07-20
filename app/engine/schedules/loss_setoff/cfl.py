"""
Schedule CFL: Carry Forward Losses.

Losses that could not be set off in the current year are carried forward
to the next assessment year, subject to the carry-forward period limits:

  - House Property loss: carried forward 8 years (set off against HP only).
  - Non-speculative business loss: carried forward 8 years (set off against
    business income only).
  - Speculative business loss: carried forward 4 years (set off against
    speculative business only).
  - STCG loss: carried forward 8 years (set off against CG only).
  - LTCG loss: carried forward 8 years (set off against LTCG only).
  - Unabsorbed depreciation: carried forward indefinitely (set off against
    any income except salary).
  - Loss from owning race horses: carried forward 4 years.

This schedule computes the carry-forward amounts that will be available
in the next AY.

ITR forms: ITR-2, ITR-3 only.
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class CFLossEntry:
    head: str = ""
    sub_category: str = ""
    assessment_year_of_loss: str = ""
    original_loss: Decimal = Decimal("0")
    loss_remaining: Decimal = Decimal("0")
    years_remaining: int = 0
    expiry_ay: str = ""


@dataclass
class CFLResult:
    entries: list = field(default_factory=list)
    total_cf_loss: Decimal = Decimal("0")


def compute(
    cyla_remaining: Decimal = Decimal("0"),
    bfla_remaining: Decimal = Decimal("0"),
    head: str = "",
    assessment_year: str = "",
    original_loss: Decimal = Decimal("0"),
    years_carried: int = 0,
    max_carry_forward_years: int = 8,
) -> CFLResult:
    """Compute carried forward loss for a single head/loss category."""
    total_remaining = cyla_remaining + bfla_remaining
    remaining_years = max(0, max_carry_forward_years - years_carried)

    if total_remaining <= 0 or remaining_years <= 0:
        return CFLResult()

    entry = CFLossEntry(
        head=head,
        sub_category="",
        assessment_year_of_loss=assessment_year,
        original_loss=original_loss,
        loss_remaining=total_remaining,
        years_remaining=remaining_years,
        expiry_ay=assessment_year,
    )

    return CFLResult(entries=[entry], total_cf_loss=total_remaining)
