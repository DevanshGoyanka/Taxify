"""Schedule Presumptive: 44AD / 44ADA / 44AE (ITR-4)."""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from app.schemas.itr4 import (
    ITR4Input, PresumptiveScheme, PresumptiveBusinessIncome44AD,
    PresumptiveProfessionalIncome44ADA, GoodsCarriageVehicle, PresumptiveGoodsCarriage44AE,
)
from app.engine.constants import (
    PRESUMPTIVE_44AD_DIGITAL, PRESUMPTIVE_44AD_CASH,
    PRESUMPTIVE_44ADA_RATE,
)


@dataclass
class PresumptiveResult:
    scheme: str = ""
    income_44ad: Decimal = Decimal("0")
    income_44ada: Decimal = Decimal("0")
    income_44ae: Decimal = Decimal("0")
    total_presumptive_income: Decimal = Decimal("0")
    declared_higher: bool = False


def _compute_44ad(ad: PresumptiveBusinessIncome44AD) -> tuple[Decimal, bool]:
    """44AD: 6% digital, 8% cash, or higher if declared."""
    statutory = (
        ad.digital_turnover * PRESUMPTIVE_44AD_DIGITAL
        + ad.cash_turnover * PRESUMPTIVE_44AD_CASH
    )
    declared = ad.income_declared
    if declared is not None and declared > statutory:
        return declared, True
    return statutory, False


def _compute_44ada(ada: PresumptiveProfessionalIncome44ADA) -> tuple[Decimal, bool]:
    """44ADA: 50% of gross receipts, or higher if declared."""
    statutory = ada.gross_receipts * PRESUMPTIVE_44ADA_RATE
    declared = ada.income_declared
    if declared is not None and declared > statutory:
        return declared, True
    return statutory, False


def _compute_44ae(ae: PresumptiveGoodsCarriage44AE) -> tuple[Decimal, bool]:
    """44AE: 7,500/ton/month for heavy, 7,500/month for light, or higher."""
    total = Decimal("0")
    higher = False
    for v in ae.vehicles:
        if v.is_heavy_goods_vehicle:
            wt = v.gross_vehicle_weight_tons or Decimal("0")
            statutory = Decimal("1000") * wt * Decimal(v.months_owned)
        else:
            statutory = Decimal("7500") * Decimal(v.months_owned)
        declared = v.income_declared
        if declared is not None and declared > statutory:
            total += declared
            higher = True
        else:
            total += statutory
    return total, higher


def compute(input_data: ITR4Input) -> PresumptiveResult:
    if input_data.presumptive_scheme == PresumptiveScheme.NONE:
        return PresumptiveResult()

    scheme = input_data.presumptive_scheme.value
    inc_44ad = Decimal("0")
    inc_44ada = Decimal("0")
    inc_44ae = Decimal("0")
    declared_higher = False

    if input_data.presumptive_scheme in (PresumptiveScheme.S44AD,):
        ad = input_data.business_income_44ad
        if ad:
            inc_44ad, dh = _compute_44ad(ad)
            declared_higher = declared_higher or dh

    if input_data.presumptive_scheme in (PresumptiveScheme.S44ADA,):
        ada = input_data.professional_income_44ada
        if ada:
            inc_44ada, dh = _compute_44ada(ada)
            declared_higher = declared_higher or dh

    if input_data.goods_carriage_44ae:
        ae = input_data.goods_carriage_44ae
        if ae and ae.vehicles:
            inc_44ae, dh = _compute_44ae(ae)
            declared_higher = declared_higher or dh

    return PresumptiveResult(
        scheme=scheme,
        income_44ad=inc_44ad,
        income_44ada=inc_44ada,
        income_44ae=inc_44ae,
        total_presumptive_income=inc_44ad + inc_44ada + inc_44ae,
        declared_higher=declared_higher,
    )
