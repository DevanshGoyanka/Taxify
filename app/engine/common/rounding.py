"""Shared rounding utilities matching ITD VBA engine behaviour."""

"""Statutory monetary rounding helpers for AY 2026-27."""

from decimal import Decimal, ROUND_HALF_UP


def round_to_nearest_rupee(val: Decimal) -> Decimal:
    """Round a monetary amount to the nearest rupee, with 50 paise rounded up.

    This is the standard Income-tax Act rounding convention for intermediate
    whole-rupee reporting where a provision does not prescribe a separate
    method. It is deliberately distinct from Section 288A/288B rounding.
    """
    return val.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def vba_round(val: Decimal) -> Decimal:
    """Round to nearest rupee using statutory half-up rounding.

    Previously used ``ROUND_HALF_EVEN`` (banker's rounding) for legacy ITD
    VBA compatibility, but the Income-tax Act and CBDT utility both use
    half-up (50 paise rounds upward). Banker's rounding would round ₹100.50
    to ₹100 instead of ₹101, producing off-by-one discrepancies at every
    .50 boundary. Now aligned with :func:`round_to_nearest_rupee`.
    """
    return val.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def round_to_nearest_10(val: Decimal) -> Decimal:
    """Apply Sections 288A/288B: nearest ₹10, with ₹5 rounded upward."""
    return (val / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal("10")
