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
    """44AD: 6% on banking/digital turnover, 8% on cash + any other mode.

    Section 44AD(1) prescribes 6% of turnover received through account
    payee cheque / bank draft / RTGS / NEFT / electronic modes, and 8% of
    the balance. "Any other mode" is a non-banking receipt, so it goes in
    the 8% bucket (NOT 6%).

    The 6%/8% values are entered manually by the operator in the Schedule
    BP editor (PersumptiveInc44AD6Per / PersumptiveInc44AD8Per); those
    entered values are respected as-typed -- no statutory-max() override --
    so the operator's computed figures flow straight through. When the
    operator has NOT entered a value (None / 0), the statutory minimum is
    computed from the turnover split so the tax is never understated.
    """
    statutory_six = ad.digital_turnover * PRESUMPTIVE_44AD_DIGITAL
    statutory_eight = (
        ad.cash_turnover + ad.other_mode_turnover
    ) * PRESUMPTIVE_44AD_CASH
    six_percent_income = (
        ad.income_at_six_percent
        if ad.income_at_six_percent is not None
        and ad.income_at_six_percent > 0
        else statutory_six
    )
    eight_percent_income = (
        ad.income_at_eight_percent
        if ad.income_at_eight_percent is not None
        and ad.income_at_eight_percent > 0
        else statutory_eight
    )
    statutory = six_percent_income + eight_percent_income
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
    """Compute presumptive income under 44AD / 44ADA / 44AE.

    Per CBDT Rule 140, ITR-4 must disclose income under at least one of
    Section 44AD, 44ADA, or 44AE. More than one section may apply.

    Args:
        input_data: The ITR-4 input model with a populated presumptive scheme.

    Returns:
        PresumptiveResult with 44AD/44ADA/44AE income breakdown.
    """
    active = [
        label for label, model in (
            ("44AD", input_data.business_income_44ad),
            ("44ADA", input_data.professional_income_44ada),
            ("44AE", input_data.goods_carriage_44ae),
        ) if model is not None
    ]
    if not active:
        return PresumptiveResult(scheme="INVALID")

    scheme = "+".join(active)
    inc_44ad = Decimal("0")
    inc_44ada = Decimal("0")
    inc_44ae = Decimal("0")
    declared_higher = False

    ad = input_data.business_income_44ad
    if ad:
        inc_44ad, dh = _compute_44ad(ad)
        declared_higher = declared_higher or dh

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
