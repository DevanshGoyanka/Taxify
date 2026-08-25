"""Typed carry-forward-loss schedule output."""

from dataclasses import dataclass, field
from decimal import Decimal

_ZERO = Decimal("0")


def _ay_label(start_year: int) -> str:
    return f"{start_year:04d}-{(start_year + 1) % 100:02d}"


def _ay_start(value: str) -> int:
    cleaned = value.upper().replace("AY", "").replace(" ", "")
    try:
        return int(cleaned.split("-")[0]) if cleaned else 0
    except (TypeError, ValueError):
        return 0


@dataclass
class CFLossEntry:
    """A typed loss available for carry-forward to a future AY."""

    head: str = ""
    sub_category: str = ""
    assessment_year_of_loss: str = ""
    original_loss: Decimal = _ZERO
    loss_remaining: Decimal = _ZERO
    years_remaining: int = 0
    expiry_ay: str = ""


@dataclass
class CFLResult:
    """Typed collection of carry-forward losses."""

    entries: list[CFLossEntry] = field(default_factory=list)
    total_cf_loss: Decimal = _ZERO


def compute(
    cyla_remaining: Decimal = _ZERO,
    bfla_remaining: Decimal = _ZERO,
    head: str = "",
    assessment_year: str = "",
    original_loss: Decimal = _ZERO,
    years_carried: int = 0,
    max_carry_forward_years: int = 8,
    sub_category: str = "",
) -> CFLResult:
    """Create a typed carry-forward result for one loss category.

    Args:
        cyla_remaining: Unabsorbed current-year loss.
        bfla_remaining: Unabsorbed valid brought-forward loss.
        head: Statutory income head.
        assessment_year: Assessment year in which the loss arose.
        original_loss: Original positive loss magnitude.
        years_carried: Completed carry-forward years.
        max_carry_forward_years: Statutory lifetime; negative means indefinite.
        sub_category: Optional loss sub-category.

    Returns:
        An empty result for exhausted/expired losses, otherwise one typed entry.
    """
    total = max(_ZERO, cyla_remaining) + max(_ZERO, bfla_remaining)
    carried = max(0, years_carried)
    indefinite = max_carry_forward_years < 0
    years_remaining = -1 if indefinite else max(0, max_carry_forward_years - carried)
    if total <= _ZERO or (not indefinite and years_remaining <= 0):
        return CFLResult()

    start = _ay_start(assessment_year)
    expiry = "" if indefinite or start == 0 else _ay_label(start + max_carry_forward_years)
    entry = CFLossEntry(
        head=head,
        sub_category=sub_category,
        assessment_year_of_loss=assessment_year,
        original_loss=max(_ZERO, original_loss) or total,
        loss_remaining=total,
        years_remaining=years_remaining,
        expiry_ay=expiry,
    )
    return CFLResult(entries=[entry], total_cf_loss=total)
