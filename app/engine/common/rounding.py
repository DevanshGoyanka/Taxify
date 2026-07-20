"""Shared rounding utilities matching ITD VBA engine behaviour."""

from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN


def vba_round(val: Decimal) -> Decimal:
    """Banker's rounding to nearest integer (ITD VBA engine)."""
    return val.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)


def round_to_nearest_10(val: Decimal) -> Decimal:
    """Section 288A/288B: round to nearest 10."""
    return (val / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal("10")
