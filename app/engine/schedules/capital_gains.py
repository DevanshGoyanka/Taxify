"""Capital-gains schedule foundations for ITR-2 (AY 2026-27)."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from app.engine.constants import LTCG_112A_EXEMPTION, LTCG_112A_RATE_POST_JUL24

_ZERO = Decimal("0")
_GRANDFATHERING_CUTOFF = date(2018, 2, 1)


def _decimal(value: Optional[Decimal]) -> Decimal:
    return value if value is not None else _ZERO


def _parse_date(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@dataclass
class CGAsset:
    """A capital asset other than a section 112A scrip or VDA."""

    description: str = ""
    date_of_acquisition: str = ""
    date_of_transfer: str = ""
    full_consideration: Decimal = _ZERO
    acquisition_cost: Decimal = _ZERO
    indexed_acquisition_cost: Decimal = _ZERO
    improvement_cost: Decimal = _ZERO
    indexed_improvement_cost: Decimal = _ZERO
    expenditure_on_transfer: Decimal = _ZERO
    total_deductions: Decimal = _ZERO
    balance: Decimal = _ZERO
    exemption_applied: Decimal = _ZERO
    exemption_section: str = ""
    taxable_gain: Decimal = _ZERO


@dataclass
class CG112AAsset:
    """Per-scrip details for equity covered by section 112A/115AD."""

    isin_code: str = ""
    share_name: str = ""
    num_shares: Decimal = _ZERO
    sale_price_per_share: Decimal = _ZERO
    total_sale_value: Decimal = _ZERO
    cost_acq_without_index: Decimal = _ZERO
    fmv_per_share: Decimal = _ZERO
    total_fmv: Decimal = _ZERO
    expenditure: Decimal = _ZERO
    total_deductions: Decimal = _ZERO
    balance: Decimal = _ZERO
    date_of_acquisition: str = ""
    date_of_transfer: str = ""
    grandfathering_eligible: Optional[bool] = None


@dataclass
class VDAEntry:
    """Per-transaction details for a virtual digital asset."""

    date_of_acquisition: str = ""
    date_of_transfer: str = ""
    acquisition_cost: Decimal = _ZERO
    consideration_received: Decimal = _ZERO
    income_from_vda: Decimal = _ZERO


@dataclass
class STCGResult:
    """Signed short-term capital-gain baskets."""

    income_111a: Decimal = _ZERO
    income_20per: Decimal = _ZERO
    income_30per: Decimal = _ZERO
    income_app_rate: Decimal = _ZERO
    income_dtaa: Decimal = _ZERO
    total_stcg: Decimal = _ZERO


@dataclass
class LTCGResult:
    """Signed long-term capital-gain baskets and section 112A threshold use."""

    income_112a: Decimal = _ZERO
    exemption_112a: Decimal = _ZERO
    taxable_112a: Decimal = _ZERO
    income_125per_other: Decimal = _ZERO
    income_dtaa: Decimal = _ZERO
    total_ltcg: Decimal = _ZERO


@dataclass
class ExemptionResult:
    """Eligible capital-gain exemptions claimed by section."""

    section_54: Decimal = _ZERO
    section_54b: Decimal = _ZERO
    section_54ec: Decimal = _ZERO
    section_54f: Decimal = _ZERO
    section_115f: Decimal = _ZERO
    total_exemption: Decimal = _ZERO


@dataclass
class CurrentYearLossCG:
    """Positive magnitudes of current-year capital-loss baskets."""

    stcg20_loss: Decimal = _ZERO
    stcg30_loss: Decimal = _ZERO
    stcg_app_loss: Decimal = _ZERO
    stcg_dtaa_loss: Decimal = _ZERO
    ltcg125_loss: Decimal = _ZERO
    ltcg_dtaa_loss: Decimal = _ZERO
    total_cg_loss: Decimal = _ZERO


@dataclass
class CGResult:
    """Aggregate capital-gains schedule result."""

    stcg: STCGResult = field(default_factory=STCGResult)
    ltcg: LTCGResult = field(default_factory=LTCGResult)
    vda: Decimal = _ZERO
    exemptions: ExemptionResult = field(default_factory=ExemptionResult)
    current_year_losses: CurrentYearLossCG = field(default_factory=CurrentYearLossCG)
    total_capital_gains: Decimal = _ZERO
    total_capital_gains_before_exemption: Decimal = _ZERO


def _acquire_fy(date_str: str) -> int:
    """Return the ending year of the financial year containing a date."""
    parsed = _parse_date(date_str)
    if parsed is None:
        return 2001
    return parsed.year if parsed.month <= 3 else parsed.year + 1


def _cii(fy: int) -> int:
    """Return the nearest available cost-inflation index."""
    from app.engine.constants import CII_TABLE

    if fy in CII_TABLE:
        return CII_TABLE[fy]
    years = sorted(CII_TABLE)
    eligible = [year for year in years if year <= fy]
    return CII_TABLE[eligible[-1] if eligible else years[0]]


def _indexed_cost(cost: Decimal, acquisition_date: str, transfer_date: str) -> Decimal:
    """Index cost for transfers in financial years where indexation applies."""
    if not acquisition_date or not transfer_date:
        return cost
    acq_fy = _acquire_fy(acquisition_date)
    xfer_fy = _acquire_fy(transfer_date)
    if xfer_fy <= 2022:
        cii_acq, cii_xfer = _cii(acq_fy), _cii(xfer_fy)
        if cii_acq > 0:
            return cost * Decimal(cii_xfer) / Decimal(cii_acq)
    return cost


def _is_grandfathering_eligible(asset: CG112AAsset) -> bool:
    if asset.grandfathering_eligible is not None:
        return asset.grandfathering_eligible
    acquired = _parse_date(asset.date_of_acquisition)
    return acquired is not None and acquired < _GRANDFATHERING_CUTOFF


def compute_112a(assets: Optional[list[CG112AAsset]]) -> tuple[Decimal, Decimal, Decimal]:
    """Compute signed section 112A gain and apply its annual threshold once.

    Grandfathering is used only when eligibility is explicit or the represented
    acquisition date precedes 1 February 2018. Its deemed cost can never be
    lower than actual cost. Loss-making scrips remain in the aggregate basket.

    Args:
        assets: Section 112A scrip transactions.

    Returns:
        A tuple of signed net gain, threshold consumed, and signed taxable gain.
    """
    total_gain = _ZERO
    for asset in assets or []:
        sale = _decimal(asset.total_sale_value)
        actual_cost = _decimal(asset.cost_acq_without_index)
        deductions = _decimal(asset.total_deductions) + _decimal(asset.expenditure)
        effective_cost = actual_cost
        if _is_grandfathering_eligible(asset):
            fmv = _decimal(asset.total_fmv)
            if fmv > _ZERO:
                effective_cost = max(actual_cost, min(fmv, sale))
        total_gain += sale - effective_cost - deductions

    exemption = min(total_gain, LTCG_112A_EXEMPTION) if total_gain > _ZERO else _ZERO
    taxable = total_gain - exemption
    return total_gain, exemption, taxable


def compute_112a_tax(taxable_112a: Decimal) -> Decimal:
    """Compute section 112A tax without taxing a loss.

    Args:
        taxable_112a: Taxable section 112A basket after the annual threshold.

    Returns:
        Tax at the AY 2026-27 section 112A rate.
    """
    return max(_ZERO, taxable_112a) * LTCG_112A_RATE_POST_JUL24 / Decimal("100")


def compute_stcg(
    stcg_111a: Decimal = _ZERO,
    stcg_land_building: Optional[list[CGAsset]] = None,
    stcg_other: Decimal = _ZERO,
    is_post_jul24: bool = True,
) -> STCGResult:
    """Compute signed short-term capital-gain baskets.

    Args:
        stcg_111a: Signed section 111A gain.
        stcg_land_building: Short-term immovable-property transactions.
        stcg_other: Other signed short-term gain.
        is_post_jul24: Retained compatibility flag for the applicable 111A rate.

    Returns:
        Signed STCG baskets.
    """
    del is_post_jul24
    land_gain = sum(
        (
            _decimal(asset.full_consideration)
            - _decimal(asset.acquisition_cost)
            - _decimal(asset.improvement_cost)
            - _decimal(asset.expenditure_on_transfer)
        )
        for asset in stcg_land_building or []
    )
    other = land_gain + _decimal(stcg_other)
    section_111a = _decimal(stcg_111a)
    return STCGResult(income_111a=section_111a, income_30per=other, total_stcg=section_111a + other)


def compute_ltcg(
    ltcg_112a_assets: Optional[list[CG112AAsset]] = None,
    ltcg_land_building: Optional[list[CGAsset]] = None,
    ltcg_other: Decimal = _ZERO,
    ltcg_dtaa: Decimal = _ZERO,
) -> LTCGResult:
    """Compute signed long-term capital-gain baskets.

    Args:
        ltcg_112a_assets: Section 112A transactions.
        ltcg_land_building: Long-term immovable-property transactions.
        ltcg_other: Other signed long-term gain.
        ltcg_dtaa: Signed DTAA long-term gain.

    Returns:
        Signed LTCG baskets with the 112A threshold applied once.
    """
    gain_112a, exemption_112a, taxable_112a = compute_112a(ltcg_112a_assets)
    land_gain = sum(
        (
            _decimal(asset.full_consideration)
            - (_decimal(asset.indexed_acquisition_cost) or _decimal(asset.acquisition_cost))
            - (_decimal(asset.indexed_improvement_cost) or _decimal(asset.improvement_cost))
            - _decimal(asset.expenditure_on_transfer)
        )
        for asset in ltcg_land_building or []
    )
    other = land_gain + _decimal(ltcg_other)
    dtaa = _decimal(ltcg_dtaa)
    return LTCGResult(
        income_112a=gain_112a,
        exemption_112a=exemption_112a,
        taxable_112a=taxable_112a,
        income_125per_other=other,
        income_dtaa=dtaa,
        total_ltcg=gain_112a + other + dtaa,
    )


def compute_vda(vda_entries: Optional[list[VDAEntry]] = None) -> Decimal:
    """Compute VDA income without permitting transaction-loss set-off.

    Args:
        vda_entries: VDA disposals.

    Returns:
        Sum of positive transaction gains; losses are ignored under 115BBH.
    """
    return sum(
        (max(_ZERO, _decimal(entry.consideration_received) - _decimal(entry.acquisition_cost)) for entry in vda_entries or []),
        _ZERO,
    )


def compute_vda_tax(vda_income: Decimal) -> Decimal:
    """Compute section 115BBH tax without taxing negative income.

    Args:
        vda_income: VDA income.

    Returns:
        Tax at the statutory VDA rate.
    """
    from app.engine.constants import VDA_RATE

    return max(_ZERO, vda_income) * VDA_RATE / Decimal("100")


def compute_exemptions(
    section_54: Decimal = _ZERO,
    section_54b: Decimal = _ZERO,
    section_54ec: Decimal = _ZERO,
    section_54f: Decimal = _ZERO,
    section_115f: Decimal = _ZERO,
) -> ExemptionResult:
    """Normalize eligible section 54-series and 115F exemption claims.

    Args:
        section_54: Section 54 claim.
        section_54b: Section 54B claim.
        section_54ec: Section 54EC claim, capped at fifty lakh rupees.
        section_54f: Section 54F claim.
        section_115f: Section 115F claim (NRI bonds/shares exemption).

    Returns:
        Nonnegative exemption claims and their total.
    """
    s54 = max(_ZERO, _decimal(section_54))
    s54b = max(_ZERO, _decimal(section_54b))
    s54ec = min(Decimal("5000000"), max(_ZERO, _decimal(section_54ec)))
    s54f = max(_ZERO, _decimal(section_54f))
    s115f = max(_ZERO, _decimal(section_115f))
    return ExemptionResult(s54, s54b, s54ec, s54f, s115f, s54 + s54b + s54ec + s54f + s115f)


def _derived_losses(stcg: STCGResult, ltcg: LTCGResult) -> CurrentYearLossCG:
    values = CurrentYearLossCG(
        stcg20_loss=max(_ZERO, -stcg.income_111a),
        stcg30_loss=max(_ZERO, -stcg.income_30per),
        stcg_app_loss=max(_ZERO, -stcg.income_app_rate),
        stcg_dtaa_loss=max(_ZERO, -stcg.income_dtaa),
        ltcg125_loss=max(_ZERO, -ltcg.taxable_112a) + max(_ZERO, -ltcg.income_125per_other),
        ltcg_dtaa_loss=max(_ZERO, -ltcg.income_dtaa),
    )
    values.total_cg_loss = sum((values.stcg20_loss, values.stcg30_loss, values.stcg_app_loss, values.stcg_dtaa_loss, values.ltcg125_loss, values.ltcg_dtaa_loss), _ZERO)
    return values


def aggregate(
    stcg: STCGResult,
    ltcg: LTCGResult,
    vda: Decimal = _ZERO,
    exemptions: Optional[ExemptionResult] = None,
    current_year_losses: Optional[CurrentYearLossCG] = None,
) -> CGResult:
    """Aggregate signed CG baskets while keeping VDA outside loss netting.

    Args:
        stcg: Signed STCG result.
        ltcg: Signed LTCG result.
        vda: Nonnegative VDA income.
        exemptions: Section 54-series exemptions.
        current_year_losses: Optional caller-provided loss breakout.

    Returns:
        Aggregate result with signed pre-floor income and retained losses.
    """
    exemptions = exemptions or ExemptionResult()
    losses = current_year_losses or _derived_losses(stcg, ltcg)
    signed_regular_cg = stcg.total_stcg + ltcg.total_ltcg

    # STCL may absorb both STCG and LTCG, but LTCL must never absorb STCG.
    remaining_stcg = stcg.total_stcg
    remaining_ltcg = ltcg.total_ltcg
    if remaining_stcg < _ZERO and remaining_ltcg > _ZERO:
        intra_head_setoff = min(-remaining_stcg, remaining_ltcg)
        remaining_stcg += intra_head_setoff
        remaining_ltcg -= intra_head_setoff

    positive_stcg = max(_ZERO, remaining_stcg)
    positive_ltcg = max(_ZERO, remaining_ltcg)
    eligible_exemption = min(positive_ltcg, max(_ZERO, exemptions.total_exemption))
    vda_income = max(_ZERO, _decimal(vda))
    total_before = signed_regular_cg + vda_income
    return CGResult(
        stcg=stcg,
        ltcg=ltcg,
        vda=vda_income,
        exemptions=exemptions,
        current_year_losses=losses,
        total_capital_gains=positive_stcg + positive_ltcg - eligible_exemption + vda_income,
        total_capital_gains_before_exemption=total_before,
    )
