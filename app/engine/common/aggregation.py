"""Final aggregation: round GTI/TI and compute payable/refund."""

from decimal import Decimal
from app.engine.common.rounding import round_to_nearest_10


def aggregate_tax(
    slab_tax: Decimal,
    special_rate_tax: Decimal,
    rebate: Decimal,
    surcharge: Decimal,
    cess: Decimal,
    relief_89: Decimal,
    relief_90_91: Decimal,
    total_interest: Decimal,
    late_fee_234f: Decimal,
    total_taxes_paid: Decimal,
) -> dict:
    """Aggregate all tax components into final payable/refund."""

    total_tax_before_relief = slab_tax + special_rate_tax
    tax_after_rebate = max(Decimal("0"), total_tax_before_relief - rebate)
    tax_after_relief = max(Decimal("0"), tax_after_rebate - relief_89 - relief_90_91)

    # Round to nearest 10 per section 288B
    gross_tax_liability = round_to_nearest_10(tax_after_relief + surcharge + cess)
    aggregate_liability = round_to_nearest_10(gross_tax_liability + total_interest + late_fee_234f)
    total_taxes_paid_rounded = round_to_nearest_10(total_taxes_paid)

    if aggregate_liability > total_taxes_paid_rounded:
        balance_payable = aggregate_liability - total_taxes_paid_rounded
        refund = Decimal("0")
    else:
        balance_payable = Decimal("0")
        refund = total_taxes_paid_rounded - aggregate_liability

    return {
        "slab_tax": slab_tax,
        "special_rate_tax": special_rate_tax,
        "total_tax_before_relief": total_tax_before_relief,
        "rebate_87a": rebate,
        "tax_after_rebate": tax_after_rebate,
        "relief_89": relief_89,
        "relief_90_91": relief_90_91,
        "surcharge": surcharge,
        "health_education_cess": cess,
        "gross_tax_liability": gross_tax_liability,
        "interest_234abc": total_interest,
        "late_fee_234f": late_fee_234f,
        "aggregate_liability": aggregate_liability,
        "total_taxes_paid": total_taxes_paid_rounded,
        "balance_payable": balance_payable,
        "refund": refund,
    }
