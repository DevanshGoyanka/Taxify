"""Shared rounding utilities matching ITD VBA engine behaviour."""

"""Statutory monetary rounding helpers for AY 2026-27."""

from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP


def round_to_nearest_rupee(val: Decimal) -> Decimal:
    """Round a monetary amount to the nearest rupee, with 50 paise rounded up.

    This is the standard Income-tax Act rounding convention for intermediate
    whole-rupee reporting where a provision does not prescribe a separate
    method. It is deliberately distinct from Section 288A/288B rounding.
    """
    return val.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def vba_round(val: Decimal) -> Decimal:
    """Round to nearest integer using legacy ITD VBA half-even behaviour.

    Retained only for legacy builder compatibility. New statutory calculation
    paths should use :func:`round_to_nearest_rupee` or Section 288A/288B.
    """
    return val.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)


def round_to_nearest_10(val: Decimal) -> Decimal:
    """Apply Sections 288A/288B: nearest ₹10, with ₹5 rounded upward."""
    return (val / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal("10")
