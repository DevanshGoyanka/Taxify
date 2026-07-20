"""Health & Education Cess (4%)."""

from decimal import Decimal
from app.engine.common.rounding import vba_round
from app.engine.constants import HEALTH_EDUCATION_CESS_RATE


def compute(tax_after_rebate_surcharge: Decimal) -> Decimal:
    return vba_round(tax_after_rebate_surcharge * HEALTH_EDUCATION_CESS_RATE)
