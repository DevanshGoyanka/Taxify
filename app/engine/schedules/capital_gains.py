"""Capital-gains schedule foundations for ITR-2 (AY 2026-27)."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from app.engine.constants import (
    LTCG_112A_EXEMPTION,
    LTCG_112A_RATE_POST_JUL24,
    LTCG_OTHER_RATE,
    LTCG_OTHER_RATE_POST_JUL24,
)
from app.engine.schedules.loss_setoff.bfla import BFLAResult
from app.engine.schedules.loss_setoff.cyla import CYLAResult

_ZERO = Decimal("0")
_GRANDFATHERING_CUTOFF = date(2018, 2, 1)
# Finance Act 2024's indexation-removal cutoff. The second proviso to
# section 112(1)(a) protects a resident individual/HUF who acquired
# land/building before this date from paying MORE tax under the new
# 12.5%-without-indexation regime than the old 20%-with-indexation regime
# would have required.
_SECOND_PROVISO_112_1A_CUTOFF = date(2024, 7, 23)


def _decimal(value: Optional[Decimal]) -> Decimal:
    return value if value is not None else _ZERO


# Widest valid set across both forms' own LTCG land/building item text --
# ITR-2's own item allows only 54/54B/54EC/54F; ITR-3's item B1d
# additionally allows 54D/54G/54GA (cross-form issue #10, tracker).
# compute_stcg()/compute_ltcg() are called only by ITR-2/ITR-3 (confirmed:
# ITR-1/4 have no capital-gains schedule at all), so widening this shared
# constant is safe for ITR-1/4 (unreachable) and harmless for ITR-2
# (nothing populates deduction_us54d/g/ga there) while fixing the real
# ITR-3 gap.
_LAND_BUILDING_EXEMPTION_SECTIONS = frozenset({"54", "54B", "54EC", "54F", "54D", "54G", "54GA"})


def _exemption_claim_total(claims: list, sections: frozenset) -> Decimal:
    """Sum `investment_amount + cgas_deposit_amount` across matching claims."""
    total = _ZERO
    for claim in claims or []:
        if getattr(claim, "section", None) in sections:
            total += _decimal(getattr(claim, "investment_amount", None))
            total += _decimal(getattr(claim, "cgas_deposit_amount", None))
    return total


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
    stamp_duty_value: Decimal = _ZERO
    acquisition_cost: Decimal = _ZERO
    indexed_acquisition_cost: Decimal = _ZERO
    improvement_cost: Decimal = _ZERO
    indexed_improvement_cost: Decimal = _ZERO
    # CBDT rule #186: the official LTCG land/building schema's
    # CostOfImprovements.CostOfImprovementsDtls detail array requires an AY
    # "ImproveDate" per improvement event whenever any improvement cost is
    # declared -- carried through from CGTransaction.year_of_improvement.
    year_of_improvement: str = ""
    expenditure_on_transfer: Decimal = _ZERO
    total_deductions: Decimal = _ZERO
    balance: Decimal = _ZERO
    exemption_applied: Decimal = _ZERO
    exemption_section: str = ""
    taxable_gain: Decimal = _ZERO
    # This transaction's own section 54/54B/54EC/54F/115F exemption claims
    # (the canonical `CapitalGainExemptionClaim` list, carried through from
    # `CGTransaction.exemptions` by `_classify()`) -- used by the ITD
    # builder to reduce THIS row's own disclosed post-exemption gain
    # (e.g. LTCGonImmvblPrprty) and populate the per-claim DeducClaimDtls
    # detail arrays. Does NOT affect the actual taxable total, which
    # continues to use the pre-existing aggregate-level
    # compute_exemptions()/eligible_exemption mechanism -- this is a
    # disclosure-granularity addition only, not a tax recomputation.
    exemptions: list = field(default_factory=list)
    # This asset's own §54/54B/54EC/54F claim total (populated by
    # compute_ltcg()/compute_stcg() from `exemptions` above) -- used for
    # the section 112(1)(a) second-proviso relief comparison (which the
    # official form bases on the POST-exemption "1e"/"1ea" figures, not
    # the pre-exemption "1c"/"1ca") and exposed for the ITD builder's own
    # disclosure so both stay consistent with each other.
    exemption_total: Decimal = _ZERO
    # Section 112(1)(a) second-proviso comparison track (LTCG land/building
    # only, residents who acquired before 23-Jul-2024) -- populated by
    # compute_ltcg() only when eib_applicable is True; zero/False otherwise,
    # not a placeholder (genuinely not applicable for this transaction).
    eib_applicable: bool = False
    balance_for_eib: Decimal = _ZERO
    tax_sec_112_1a: Decimal = _ZERO
    tax_sec_112_1a_iib: Decimal = _ZERO
    excess_amt_sec_112_1a: Decimal = _ZERO


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
    # Per-transaction land/building detail, preserved for Schedule CG's
    # SaleofLandBuildDtls rows -- previously discarded after computing
    # land_gain, leaving the official schedule's required detail array
    # always empty even when land/building STCG was nonzero.
    land_building: list = field(default_factory=list)


@dataclass
class LTCGResult:
    """Signed long-term capital-gain baskets and section 112A threshold use."""

    income_112a: Decimal = _ZERO
    exemption_112a: Decimal = _ZERO
    taxable_112a: Decimal = _ZERO
    income_125per_other: Decimal = _ZERO
    income_dtaa: Decimal = _ZERO
    total_ltcg: Decimal = _ZERO
    # Same as STCGResult.land_building -- preserved for Schedule CG's
    # LTCG SaleofLandBuildDtls rows.
    land_building: list = field(default_factory=list)
    # Aggregate section 112(1)(a) second-proviso relief across every
    # eligible land/building row (sum of each asset's
    # excess_amt_sec_112_1a) -- the amount of tax "required to be ignored"
    # per the official form's item B1eii, applied against the actual
    # section-112 Schedule SI tax by the form calculator.
    total_excess_tax_112_1a: Decimal = _ZERO


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
    """Index cost using the CII table for the acquisition/transfer years.

    Indexation was withdrawn from the PRIMARY long-term capital gain
    computation (section 48's proviso) for transfers on/after 23-Jul-2024,
    but it is still required for the section 112(1)(a) second-proviso
    comparison (``compute_ltcg()``'s ``eib_applicable`` track), which
    exists specifically to compute what the OLD, indexed-cost-based 20%
    computation would have produced. A prior ``xfer_fy <= 2022`` gate here
    made this function silently return the raw, un-indexed cost for any
    transfer in FY2023 onward -- i.e. for every AY 2026-27 transfer, the
    exact returns this function exists to support -- even though
    ``CII_TABLE`` (app/engine/constants.py) has real CBDT-notified values
    through FY2025-26. That made the second-proviso relief compute against
    an indexed cost equal to the un-indexed cost (an implicit, always-wrong
    CII ratio of 1), silently zeroing or understating a resident's
    statutory relief. Index using whatever years CII_TABLE actually covers;
    ``_cii()`` already falls back to the nearest earlier notified year.
    """
    if not acquisition_date or not transfer_date:
        return cost
    acq_fy = _acquire_fy(acquisition_date)
    xfer_fy = _acquire_fy(transfer_date)
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
        effective_cost = actual_cost
        if _is_grandfathering_eligible(asset):
            fmv = _decimal(asset.total_fmv)
            if fmv > _ZERO:
                effective_cost = max(actual_cost, min(fmv, sale))
        expenditure = _decimal(asset.expenditure)
        # `asset.total_deductions` is NOT read here -- it is a redundant,
        # disclosure-only summary field (validated elsewhere,
        # app/engine/validators/itr2/input_rules.py's ITR2-IN-112A-006, to
        # equal cost_acq_without_index + expenditure whenever a caller
        # supplies it) rather than a third independent cost component.
        # Subtracting it here on top of effective_cost/expenditure -- which
        # already fully account for the same cost and expenditure -- was
        # double- (for a plain scrip) or effectively triple-counting (for a
        # grandfathered one) the deduction, turning real gains into
        # fabricated losses. Schedule 112A/115AD's own JSON `TotalDeductions`
        # field is independently and correctly built from
        # `deemed_cost + expense` in `_112a_style_schedule()`
        # (`app/engine/itd/itr2.py`), which never reads this field either --
        # confirming it has no legitimate role as a compute input.
        total_gain += sale - effective_cost - expenditure

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


def deemed_consideration_50c(consideration: Decimal, stamp_duty_value: Decimal) -> Decimal:
    """Apply section 50C's deemed full value of consideration for land/building.

    Per the ITR-2 form's own instruction (Schedule CG, item 1(a)(iii)): "in
    case (stamp value) does not exceed 1.10 times (consideration), take this
    figure as (consideration), or else take (stamp value)." When no stamp
    duty value is supplied, section 50C simply does not apply and the actual
    consideration is used -- this is the common case and leaves every
    existing computation unchanged.
    """
    stamp_duty_value = _decimal(stamp_duty_value)
    consideration = _decimal(consideration)
    if stamp_duty_value > _ZERO and stamp_duty_value > consideration * Decimal("1.10"):
        return stamp_duty_value
    return consideration


def deemed_consideration_50ca(consideration: Decimal, fair_market_value: Decimal) -> Decimal:
    """Apply section 50CA's deemed full value of consideration for unquoted shares.

    Per the ITR-2 form's own instruction (Schedule CG, items 5(a)(i)(c) and
    8(a)(i)(c)): "Full value of consideration in respect of unquoted shares
    adopted as per section 50CA... (higher of a or b)" -- a straight
    higher-of comparison with NO tolerance threshold, unlike section 50C's
    "does not exceed 1.10 times" carve-out for land/building
    (``deemed_consideration_50c``). When no FMV is supplied, section 50CA
    simply does not apply and the actual consideration is used.
    """
    fair_market_value = _decimal(fair_market_value)
    consideration = _decimal(consideration)
    return max(consideration, fair_market_value)


def compute_stcg(
    stcg_111a: Decimal = _ZERO,
    stcg_land_building: Optional[list[CGAsset]] = None,
    stcg_other: Decimal = _ZERO,
    is_post_jul24: bool = True,
    stcg_dtaa: Decimal = _ZERO,
) -> STCGResult:
    """Compute signed short-term capital-gain baskets.

    Args:
        stcg_111a: Signed section 111A gain.
        stcg_land_building: Short-term immovable-property transactions.
        stcg_other: Other signed short-term gain.
        is_post_jul24: Retained compatibility flag for the applicable 111A rate.
        stcg_dtaa: Signed DTAA-rate STCG (official Schedule CG item A8b) --
            mirrors ``compute_ltcg()``'s own already-shipped ``ltcg_dtaa``
            parameter; defaults to zero so every existing caller (ITR-1/3/4)
            is unaffected.

    Returns:
        Signed STCG baskets.
    """
    del is_post_jul24
    # Set each asset's own .total_deductions/.balance in place so the ITD
    # builder's per-row Schedule CG detail can read the exact same figures
    # this land_gain sum uses, instead of independently recomputing gain
    # with a formula that could drift out of sync.
    land_gain = _ZERO
    for asset in stcg_land_building or []:
        deemed = deemed_consideration_50c(asset.full_consideration, getattr(asset, "stamp_duty_value", _ZERO))
        total_ded = _decimal(asset.acquisition_cost) + _decimal(asset.improvement_cost) + _decimal(asset.expenditure_on_transfer)
        asset.total_deductions = total_ded
        asset.balance = deemed - total_ded
        asset.taxable_gain = asset.balance
        # STCG land/building's valid exemption-section set differs by
        # form: ITR-2's own item 1d allows only 54B (agricultural land);
        # ITR-3's item A1d additionally allows 54G/54GA (cross-form issue
        # #10, tracker). 54/54EC/54D/54F are LTCG-only exemptions on both
        # forms. Widened here (not split per-form) since ITR-2 never
        # populates deduction_us54g/ga -- harmless for ITR-2, fixes ITR-3.
        asset.exemption_total = _exemption_claim_total(asset.exemptions, frozenset({"54B", "54G", "54GA"}))
        land_gain += asset.balance
    other = land_gain + _decimal(stcg_other)
    section_111a = _decimal(stcg_111a)
    dtaa = _decimal(stcg_dtaa)
    return STCGResult(
        income_111a=section_111a,
        income_30per=other,
        income_dtaa=dtaa,
        total_stcg=section_111a + other + dtaa,
        land_building=list(stcg_land_building or []),
    )


def compute_ltcg(
    ltcg_112a_assets: Optional[list[CG112AAsset]] = None,
    ltcg_land_building: Optional[list[CGAsset]] = None,
    ltcg_other: Decimal = _ZERO,
    ltcg_dtaa: Decimal = _ZERO,
    is_resident: bool = False,
) -> LTCGResult:
    """Compute signed long-term capital-gain baskets.

    Args:
        ltcg_112a_assets: Section 112A transactions.
        ltcg_land_building: Long-term immovable-property transactions.
        ltcg_other: Other signed long-term gain.
        ltcg_dtaa: Signed DTAA long-term gain.
        is_resident: Whether the assessee is a resident (RES or NOR, i.e.
            not NRI) for the section 112(1)(a) second-proviso comparison
            below. Defaults to False so callers that don't track residency
            (ITR-1/4's restricted-112A-only projection, which never surfaces
            land/building LTCG at all) get no behavior change.

    Returns:
        Signed LTCG baskets with the 112A threshold applied once.
    """
    gain_112a, exemption_112a, taxable_112a = compute_112a(ltcg_112a_assets)
    # Per the official ITR-2 form's own Schedule CG instructions (Part B
    # item 1), the PRIMARY declared LTCG ("1c"/B1e) uses the NON-indexed
    # cost only. The indexed cost feeds a separate section 112(1)(a) second
    # proviso comparison ("1ca"/B1ea, "for the purpose of computing eiB")
    # below -- it must never replace the primary basis, since doing so
    # (this function's prior behavior) understates the declared gain
    # whenever indexed cost exceeds actual cost, the normal case.
    land_gain = _ZERO
    total_excess_tax_112_1a = _ZERO
    for asset in ltcg_land_building or []:
        deemed = deemed_consideration_50c(asset.full_consideration, getattr(asset, "stamp_duty_value", _ZERO))
        acquisition = _decimal(asset.acquisition_cost)
        improvement = _decimal(asset.improvement_cost)
        total_ded = acquisition + improvement + _decimal(asset.expenditure_on_transfer)
        asset.total_deductions = total_ded
        asset.balance = deemed - total_ded
        asset.taxable_gain = asset.balance
        # This asset's own §54/54B/54EC/54F claims -- used below for the
        # EiB relief comparison (the form bases "ei(A)" on "1e", the
        # POST-exemption figure) and by the ITD builder's own disclosure.
        # Does NOT reduce `asset.balance`/`land_gain` themselves: the
        # actual taxable total continues to use the pre-existing
        # aggregate-level compute_exemptions()/eligible_exemption
        # mechanism exactly once, so subtracting here too would double the
        # exemption's effect on the real tax computation.
        asset.exemption_total = _exemption_claim_total(asset.exemptions, _LAND_BUILDING_EXEMPTION_SECTIONS)
        land_gain += asset.balance

        # Section 112(1)(a) second proviso: a resident who acquired before
        # the Finance Act 2024 indexation-removal cutoff is protected from
        # paying MORE tax under the new 12.5%-non-indexed regime than the
        # old 20%-with-indexation regime would have required. This is a
        # per-row comparison of two TAX figures, not a substitute for the
        # primary gain above -- "1ca"/BalanceForEiB exists "only for the
        # purpose of computing eiB" per the form's own text.
        acquired_date = _parse_date(asset.date_of_acquisition)
        asset.eib_applicable = bool(
            is_resident and acquired_date is not None and acquired_date < _SECOND_PROVISO_112_1A_CUTOFF
        )
        if asset.eib_applicable:
            # Fall back to a real CII-computed indexed cost (not the raw
            # un-indexed cost -- see `_indexed_cost()`'s own docstring for
            # why that fallback silently zeroed this relief) whenever the
            # preparer hasn't supplied an explicit indexed figure.
            indexed_acquisition = _decimal(asset.indexed_acquisition_cost) or _indexed_cost(
                acquisition, asset.date_of_acquisition, asset.date_of_transfer
            )
            indexed_improvement = _decimal(asset.indexed_improvement_cost) or (
                _indexed_cost(improvement, asset.year_of_improvement or asset.date_of_acquisition, asset.date_of_transfer)
                if improvement > _ZERO else _ZERO
            )
            indexed_total_ded = indexed_acquisition + indexed_improvement + _decimal(asset.expenditure_on_transfer)
            # "In case of negative, to be considered as nil" (form item 1ca).
            asset.balance_for_eib = max(_ZERO, deemed - indexed_total_ded)
            # Per the form's own text, "ei(A)" is "1e*12.5%" and "ei(B)" is
            # "1ea*20%" -- both POST-exemption ("1e"/"1ea" = "1c"/"1ca"
            # minus "1d"), not the pre-exemption "1c"/"1ca" this comparison
            # previously used before per-row exemption attribution existed.
            primary_taxable = max(_ZERO, asset.balance - asset.exemption_total)
            eib_taxable = max(_ZERO, asset.balance_for_eib - asset.exemption_total)
            asset.tax_sec_112_1a = primary_taxable * LTCG_OTHER_RATE_POST_JUL24 / Decimal("100")
            asset.tax_sec_112_1a_iib = eib_taxable * LTCG_OTHER_RATE / Decimal("100")
            asset.excess_amt_sec_112_1a = max(_ZERO, asset.tax_sec_112_1a - asset.tax_sec_112_1a_iib)
            total_excess_tax_112_1a += asset.excess_amt_sec_112_1a
    other = land_gain + _decimal(ltcg_other)
    dtaa = _decimal(ltcg_dtaa)
    return LTCGResult(
        income_112a=gain_112a,
        exemption_112a=exemption_112a,
        taxable_112a=taxable_112a,
        income_125per_other=other,
        income_dtaa=dtaa,
        total_ltcg=gain_112a + other + dtaa,
        land_building=list(ltcg_land_building or []),
        total_excess_tax_112_1a=total_excess_tax_112_1a,
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

    # Section 54B (agricultural land) is the ONLY §54-series exemption the
    # official form allows against short-term capital gain (Schedule CG
    # item A1d restricts the STCG-land-building deduction row to 54B only;
    # 54/54EC/54F are long-term-only per their own statutory text). Net the
    # STCG-land-building 54B claims against the STCG bucket FIRST, then net
    # whatever remains of the total exemption pool against LTCG as before.
    # Previously the entire exemption pool -- including any 54B claimed on
    # an STCG land/building disposal -- was only ever netted against LTCG,
    # so a 54B claim was correctly disclosed per-row but silently never
    # reduced the taxable total whenever LTCG couldn't fully absorb it
    # (e.g. no LTCG at all in the return).
    stcg_land_54b = sum((asset.exemption_total for asset in stcg.land_building), _ZERO)
    stcg_eligible_exemption = min(positive_stcg, max(_ZERO, stcg_land_54b), max(_ZERO, exemptions.total_exemption))
    remaining_exemption_pool = max(_ZERO, exemptions.total_exemption - stcg_eligible_exemption)
    ltcg_eligible_exemption = min(positive_ltcg, remaining_exemption_pool)

    vda_income = max(_ZERO, _decimal(vda))
    total_before = signed_regular_cg + vda_income
    return CGResult(
        stcg=stcg,
        ltcg=ltcg,
        vda=vda_income,
        exemptions=exemptions,
        current_year_losses=losses,
        total_capital_gains=(
            positive_stcg - stcg_eligible_exemption
            + positive_ltcg - ltcg_eligible_exemption
            + vda_income
        ),
        total_capital_gains_before_exemption=total_before,
    )


def _consume(amount: Decimal, pools: list[Decimal]) -> tuple[Decimal, list[Decimal]]:
    """Consume a nonnegative amount from ordered nonnegative income pools."""
    remaining = max(_ZERO, amount)
    updated = list(pools)
    for index, pool in enumerate(updated):
        used = min(remaining, max(_ZERO, pool))
        updated[index] = max(_ZERO, pool - used)
        remaining -= used
    return remaining, updated


def post_loss_cg_baskets(
    stcg: STCGResult,
    ltcg: LTCGResult,
    cyla: CYLAResult,
    bfla: BFLAResult,
    exemptions: ExemptionResult,
) -> dict[str, Decimal]:
    """Allocate statutory loss set-offs into capital-gain rate baskets.

    Uses the per-basket residual incomes from the 6-sub-basket CYLA and BFLA
    engines to populate the post-loss capital-gain rate baskets that both
    ITR-2 and ITR-3 Schedule CG/Part B-TI/Schedule SI computations need.
    Form-agnostic: takes only the shared CG/CYLA/BFLA result types, no
    ITR-2/ITR-3-specific concept (e.g. FII/FPI's own STCG@30% basket is
    still exposed via `cyla.stcg30_remaining`/`bfla.stcg30...` inputs
    upstream -- the caller decides which of its own signed CYLAInput/
    BFLAInput sub-baskets each result lands in before this function ever
    runs; this function only re-derives the post-loss basket allocation
    from whatever residuals the caller's own CYLA/BFLA run produced).

    Note: `non_cg_income_available_for_hp` from the original ITR-2-only
    version of this function was an unused parameter (HP loss absorption
    against CG is already fully resolved inside the CYLA/BFLA engines
    themselves) and has been dropped in this shared version.
    """
    # Map CYLA/BFLA 6-sub-basket residuals into the 4 post-loss baskets
    # used by the SI engine. `normal_stcg` is the "ordinary slab-rate STCG"
    # basket (land/building + generic other-assets, form items A1/A5) --
    # sourced from `stcg30_remaining` for an FII/FPI (whose OWN section
    # 115AD(1)(ii) securities gain genuinely IS a flat 30%) or from
    # `stcg_app_remaining` for every other taxpayer -- exactly one of the
    # two is ever nonzero for a single return, so summing both is safe and
    # keeps this basket's own total unchanged regardless of which CYLA
    # sub-bucket it came from.
    #
    # All six sub-baskets read the POST-BFLA (not CYLA-level) residual --
    # BFLA runs after CYLA and is the true final remaining income once
    # BOTH current-year (CYLA) and brought-forward (BFLA) losses are
    # applied. The STCG-side buckets previously read `cyla.*_remaining`
    # (pre-BFLA) while the LTCG-side buckets already correctly read
    # `bfla.*_remaining` -- a pre-existing asymmetry (present since this
    # function's introduction, confirmed via `git log -S`, with no comment
    # ever justifying it) that made a brought-forward loss absorbed into
    # an STCG-rate bucket correctly reduce GTI (via the separate
    # `bfla_total_set_off` subtraction) but silently NEVER reduce that
    # bucket's own Schedule SI special-rate tax -- the disclosed loss
    # set-off and the actual tax charged diverged. Found via
    # `tests/test_schedule_cg_comprehensive.py` (2026-09-18).
    normal_stcg = bfla.stcg30_remaining + bfla.stcg_app_remaining
    section_111a = bfla.stcg20_remaining  # 20% 111A STCG
    # 112A gross and 112 other LTCG are both in the ltcg125 pool;
    # split 112A out for threshold application.
    other_ltcg = bfla.ltcg125_remaining  # post-BFLA LTCG (includes 112A)
    section_112a = max(_ZERO, ltcg.income_112a)  # gross 112A before losses

    # Allocate CYLA/BFLA losses against 112A vs other LTCG proportionally.
    # DTAA-rate LTCG is deliberately excluded from this split -- it is its
    # own separate CYLA/BFLA sub-basket (ltcg_dtaa_income/
    # bfla.ltcg_dtaa_remaining), never blended into the ltcg125 CYLA pool
    # (CYLAInput.ltcg125_income = ltcg_125_signed + ltcg_112a_gross only), so
    # including it here would misattribute DTAA income as "loss absorbed"
    # against 112A/other-LTCG whenever both DTAA and 112A income exist in
    # the same return, understating 112A and overstating other-LTCG with no
    # real loss involved.
    total_ltcg_before = max(_ZERO, ltcg.income_112a) + max(_ZERO, ltcg.income_125per_other)
    if total_ltcg_before > _ZERO:
        ltcg_loss_absorbed = max(_ZERO, total_ltcg_before) - other_ltcg
        # Absorb losses proportionally from 112A and other LTCG
        ratio_112a = max(_ZERO, ltcg.income_112a) / total_ltcg_before
        section_112a = max(_ZERO, ltcg.income_112a) - ltcg_loss_absorbed * ratio_112a
        other_ltcg = max(_ZERO, ltcg.income_125per_other) - ltcg_loss_absorbed * (1 - ratio_112a)

    # Section 54B (agricultural land) is the ONLY §54-series exemption the
    # official form allows against short-term capital gain (Schedule CG
    # item A1d restricts the STCG-land-building deduction to 54B only) --
    # consume it from the 30%/normal-rate STCG bucket first, which is where
    # land/building STCG lands (`compute_stcg()` blends land gain into
    # `income_30per`). Only the REMAINING exemption pool -- after whatever
    # 54B actually reduced STCG -- can then reduce LTCG.
    stcg_land_54b = sum((asset.exemption_total for asset in stcg.land_building), _ZERO)
    stcg_exemption_pool = min(max(_ZERO, stcg_land_54b), max(_ZERO, exemptions.total_exemption))
    remaining_after_stcg, stcg_pools = _consume(stcg_exemption_pool, [normal_stcg])
    normal_stcg = stcg_pools[0]
    stcg_exemption_used = stcg_exemption_pool - remaining_after_stcg

    # Section 54/54EC/54F/115F (LTCG-only) plus any 54B not already
    # consumed by STCG above can reduce positive LTCG.
    ltcg_exemption_pool = max(_ZERO, exemptions.total_exemption - stcg_exemption_used)
    ltcg_exemption_remaining, pools = _consume(ltcg_exemption_pool, [other_ltcg, section_112a])
    other_ltcg, section_112a = pools
    ltcg_exemption_used = ltcg_exemption_pool - ltcg_exemption_remaining
    return {
        "normal_stcg": normal_stcg,
        "111a": section_111a,
        "112": other_ltcg,
        "112a_gross": section_112a,
        "112a_taxable": max(_ZERO, section_112a - LTCG_112A_EXEMPTION),
        # DTAA-rate STCG/LTCG -- each its own independent CYLA/BFLA
        # sub-basket, post-brought-forward remaining amount (matching
        # "111a"'s and "112"'s own post-BFLA sourcing above).
        "stcg_dtaa": bfla.stcg_dtaa_remaining,
        "ltcg_dtaa": bfla.ltcg_dtaa_remaining,
        # Total §54-series exemption actually consumed against STCG+LTCG
        # this year (NOT including the separate section 112A ₹1.25L
        # threshold, tracked implicitly via "112a_gross" - "112a_taxable"
        # above) -- used by the caller to correct GTI/Total Income, which
        # was computed further up from the PRE-exemption gross CG totals
        # (loss set-off must run before exemption is applied, so GTI
        # necessarily starts from the gross figure; this is the retroactive
        # correction for the exemption on top of it).
        "exemption_used": stcg_exemption_used + ltcg_exemption_used,
    }


# ============================================================
# Standalone form-agnostic CG schedule entry point (AY 2026-27)
# ============================================================
#
# The CBDT treats Schedule CG as one schedule reported (in varying detail)
# by every applicable ITR form.  Rather than have each form calculator own
# a copy of the classification + holding-period + basket logic, this single
# `compute()` function classifies the canonical `CGTransaction` rows into
# the 112A / 111A / section-112 / land-building / VDA / other baskets,
# applies grandfathering and the aggregate ₹1.25 lakh section-112A
# threshold, claims §54/54B/54EC/54F/115F exemptions, runs the intra-head
# STCL↔LTCG set-off, and returns signed baskets plus current-year losses.
#
# Form calculators then PROJECT this single result:
#   - ITR-1 / ITR-4: aggregate the 112A basket only (losses forfeited, no
#     exemptions), and enforce the ₹1.25L restricted-112A eligibility cap.
#   - ITR-2 / ITR-3: consume the full signed result, feed CYLA/BFLA, and
#     report per-scrip Schedule CG with losses and exemptions.
#
# `transactions` are passed structurally (duck-typed) so the schedule does
# not import the ITR-2 schema, keeping the dependency arrow one-way
# (calculators → schedule, never schedule → calculators).

# Asset types that are always short-term under AY 2026-27 rules
# (specified mutual funds u/s 50AA, market-linked debentures, depreciable
# assets) — indexation is never available and holding period is irrelevant.
_ALWAYS_ST_ASSET_TYPES = frozenset({
    "specified_mutual_fund_50aa",
    "market_linked_debenture_50aa",
    "depreciable_asset",
    "SPECIFIED_MUTUAL_FUND",
    "MARKET_LINKED_DEBENTURE",
    "DEPRECIABLE_ASSET",
})

# Asset types with a 12-month long-term threshold (equity, equity-oriented
# MFs, business-trust units, listed securities).
_12_MONTH_ASSET_TYPES = frozenset({
    "listed_equity_112a", "equity_oriented_fund_112a", "business_trust_unit_112a",
    "listed_equity_111a", "equity_oriented_fund_111a", "listed_security",
    "listed_equity", "equity_oriented_mutual_fund", "business_trust_unit",
    "LISTED_EQUITY", "EQUITY_ORIENTED_MUTUAL_FUND", "BUSINESS_TRUST_UNIT",
    "LISTED_SECURITY",
})

# Asset types routed into the section-112A scrip basket (long-term equity).
_112A_ASSET_TYPES = frozenset({
    "listed_equity_112a", "equity_oriented_fund_112a", "business_trust_unit_112a",
    "EQUITY_ORIENTED_MUTUAL_FUND", "LISTED_EQUITY", "BUSINESS_TRUST_UNIT",
})

# Asset types routed into the section-111A STCG basket (short-term equity).
_111A_ASSET_TYPES = frozenset({
    "listed_equity_111a", "equity_oriented_fund_111a",
    "listed_equity", "equity_oriented_mutual_fund", "business_trust_unit",
    "LISTED_EQUITY", "EQUITY_ORIENTED_MUTUAL_FUND", "BUSINESS_TRUST_UNIT",
})

# Virtual-digital-asset disposal code, routed to the 115BBH basket which is
# outside the regular loss-netting (losses on VDA cannot be set off).


def _calendar_anniversary(acquired: date, years: int) -> date:
    """Return a calendar anniversary, normalizing 29 February to 28 February."""
    try:
        return acquired.replace(year=acquired.year + years)
    except ValueError:
        return acquired.replace(year=acquired.year + years, day=28)


def _is_short_term(asset_type: str, acquired: date, transferred: date) -> bool:
    """Classify holding period under AY 2026-27 asset-specific rules.

    Args:
        asset_type: The canonical asset-type string (value of CGAssetType).
        acquired: Date of acquisition.
        transferred: Date of transfer.

    Returns:
        True when the transaction is short-term; False when long-term.

    Holding-period thresholds (CBDT AY 2026-27):
        - 12 months: listed equity, equity-oriented MF, business-trust units,
          listed securities.
        - 24 months: immovable property (land/building), unlisted shares,
          jewellery, bonds/debentures, other assets.
        - Always short-term: specified MFs (§50AA), market-linked debentures,
          depreciable assets (post-23-Jul-2024 regime).
    The long-term test uses the calendar anniversary, never a day-count
    approximation, so a 365-day leap-year span is correctly short-term.
    """
    if asset_type in _ALWAYS_ST_ASSET_TYPES:
        return True
    years = 1 if asset_type in _12_MONTH_ASSET_TYPES else 2
    return transferred < _calendar_anniversary(acquired, years)


# Schedule CG's generic "other assets" bucket (Sl. A6/B9 in ITR-3; Sl. A5/B8
# in ITR-2) -- valid exemption sections differ by BOTH form AND ST/LT, per
# each form's own printed item text, confirmed by direct introspection of
# both forms' official JSON schemas (not assumed from a shared type name --
# see `app/engine/itd/cg_shared.py`'s own builder docstrings for the exact
# citations): ITR-3 STCG-other-assets (item 6) allows 54G/54GA; ITR-2
# STCG-other-assets (item 5) has NO exemption line at all -- an EMPTY set,
# not a subset of ITR-3's; ITR-3 LTCG-other-assets (item 9) allows
# 54D/54F/54G/54GA; ITR-2 LTCG-other-assets (item 8) allows ONLY 54F. Each
# caller must pass its own form-correct set explicitly -- there is no safe
# shared default, since a wrongly-broad set would let an ITR-2 return
# silently apply an exemption (54D/54G/54GA) its own form never offers.
ITR2_OTHER_ASSETS_ST_EXEMPTION_SECTIONS: frozenset[str] = frozenset()
ITR2_OTHER_ASSETS_LT_EXEMPTION_SECTIONS = frozenset({"54F"})
ITR3_OTHER_ASSETS_ST_EXEMPTION_SECTIONS = frozenset({"54G", "54GA"})
ITR3_OTHER_ASSETS_LT_EXEMPTION_SECTIONS = frozenset({"54D", "54F", "54G", "54GA"})


def other_asset_gain(tx: object, is_short: bool, valid_exemption_sections: frozenset[str]) -> Decimal:
    """
    Compute the taxable gain for one Schedule CG generic "other assets"
    transaction (Sl. A6/B9 ITR-3; Sl. A5/B8 ITR-2) -- unlisted shares, debt
    mutual funds, bonds/debentures, jewellery, foreign assets, and any
    other capital asset not covered by an earlier, more specific Schedule
    CG item.

    Official form formula (identical arithmetic STRUCTURE in both forms,
    for a given ST/LT side -- only which exemption sections are legal
    differs, hence the required, form-specific ``valid_exemption_sections``
    parameter rather than a shared default; pass one of the
    ``ITR{2,3}_OTHER_ASSETS_{ST,LT}_EXEMPTION_SECTIONS`` constants above):
        Balance = FullConsideration - (CostOfAcquisition + ImprovementCost
                                        + TransferExpenses)
        Gain    = Balance + LossDisallowedUs94_7Or94_8 [STCG only]
                          - OtherAssetsExemptionAmount  [only when the
                            claimed section is in valid_exemption_sections]

    The 94(7)/94(8) add-back is STCG-only per the form (no such sub-item
    exists on the LTCG side of this bucket in either form). The exemption
    subtraction happens here, at the actual tax-computation source, not
    only in the disclosure JSON (`cg_shared.py`'s aggregators) -- the two
    must agree, or the disclosed "CapgainonAssets" figure and the amount
    actually taxed would silently diverge whenever an exemption is claimed
    on a generic-other-asset sale.
    """
    exemption = (
        _decimal(getattr(tx, "other_assets_exemption_amount", None))
        if getattr(tx, "other_assets_exemption_section", None) in valid_exemption_sections
        else _ZERO
    )
    gain = (
        tx.full_consideration - tx.cost_of_acquisition
        - tx.improvement_cost - tx.expenditure_on_transfer
        - exemption
    )
    if is_short:
        gain += _decimal(getattr(tx, "loss_disallowed_94_7_94_8", None))
    return gain


# Field aliases — the schedule accepts both the canonical snake_case names
# (used by the typed CGTransaction schema) and the camelCase names used by
# the flat frontend payload rows, so it can be fed directly from the router
# payload without a mapping layer.
_FIELD_ALIASES = {
    "full_consideration": ("full_consideration", "saleValue", "saleCost", "fullValueOfConsideration"),
    "cost_of_acquisition": ("cost_of_acquisition", "actualCost", "purchaseCost", "costOfAcquisition"),
    "expenditure_on_transfer": ("expenditure_on_transfer", "transferExpenses", "expenses"),
    "fair_market_value_jan2018": ("fair_market_value_jan2018", "fmv31Jan2018", "fmvJan2018", "fairMarketValueJan2018"),
    "date_of_acquisition": ("date_of_acquisition", "acquisitionDate", "purchaseDate", "dateOfAcquisition"),
    "date_of_transfer": ("date_of_transfer", "transferDate", "saleDate", "dateOfTransfer"),
    "isin_code": ("isin_code", "isin", "isinCode"),
    "description": ("description", "assetDescription"),
    "indexed_cost": ("indexed_cost", "indexedCost"),
    "improvement_cost": ("improvement_cost", "improvementCost"),
    "indexed_improvement": ("indexed_improvement", "indexedImprovement"),
    "explicit_long_term": ("explicit_long_term", "explicitLongTerm", "aisHoldingPeriod"),
    "asset_type": ("asset_type", "assetType"),
}


def _attr(obj: object, name: str, default: object = None) -> object:
    """Read an attribute from a structurally-typed transaction row.

    Tolerates both typed objects (CGTransaction) and plain dicts (the flat
    frontend payload rows), trying each alias in ``_FIELD_ALIASES`` so the
    schedule can be fed directly from the router payload without a mapping
    layer.
    """
    aliases = _FIELD_ALIASES.get(name, (name,))
    if isinstance(obj, dict):
        for alias in aliases:
            if alias in obj and obj[alias] is not None and obj[alias] != "":
                return obj[alias]
        return default
    for alias in aliases:
        value = getattr(obj, alias, None)
        if value is not None and value != "":
            return value
    return default


def _decimal_attr(obj: object, name: str) -> Decimal:
    """Read a Decimal attribute, tolerating None / dict rows / returning ZERO."""
    raw = _attr(obj, name, None)
    if raw is None:
        return _ZERO
    if isinstance(raw, Decimal):
        return raw
    try:
        return Decimal(str(raw))
    except (TypeError, ValueError):
        return _ZERO


def _bool_attr(obj: object, name: str) -> Optional[bool]:
    """Read an optional boolean attribute from a typed object or dict row."""
    raw = _attr(obj, name, None)
    if raw is None:
        return None
    return bool(raw)


def _date_attr(obj: object, name: str) -> Optional[date]:
    """Read an optional date attribute from a typed object or dict row."""
    raw = _attr(obj, name, None)
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    parsed = _parse_date(str(raw))
    return parsed


def _asset_type_value(tx: object) -> str:
    """Return the canonical asset-type string for a transaction row.

    Accepts the typed ``CGAssetType`` enum (via ``.value``), a raw string
    (from a flat dict payload), or ``None`` (defaults to ``"other"``).
    """
    at = _attr(tx, "asset_type", None)
    if at is None:
        return "other"
    value = getattr(at, "value", None)
    if value is not None:
        return str(value)
    return str(at)


def unquoted_shares_50ca_adjustment(transactions, is_short: bool) -> Decimal:
    """Aggregate section 50CA deemed-consideration adjustment for the
    generic "other assets" bucket's unlisted-shares subset (Sl. A5(a)(i)/
    B8(a)(i) ITR-2; A6(a)(i)/B9(a)(i) ITR-3).

    Section 50CA applies "higher of consideration or FMV" to ALL unquoted-
    share disposals TOGETHER as one aggregate row on the official form --
    not per transaction. Applying ``deemed_consideration_50ca()`` to each
    transaction individually would silently OVERSTATE the deemed
    consideration whenever multiple unquoted-share sales exist with some
    above and some below their own FMV (max(a,b) + max(c,d) >= max(a+c,
    b+d) in general), and would also disagree with the disclosure builder
    (``itd/cg_shared.py``'s own ``unq_deemed = deemed_consideration_50ca(
    unq_consideration, unq_fmv)``), which already aggregates correctly.

    Returns the DELTA (deemed - actual consideration) to be added once to
    the bucket's own signed gain total -- neither ``other_asset_gain()``
    nor ITR-2's ``_classify()`` substitute a per-transaction deemed value,
    both still compute the "actual consideration" gain in their own loop;
    this adjustment is added on top, matching how the disclosure side
    itself only ever adjusts the aggregate.
    """
    consideration = _ZERO
    fmv = _ZERO
    for tx in transactions or []:
        if _asset_type_value(tx) != "unlisted_shares":
            continue
        acquired = _date_attr(tx, "date_of_acquisition")
        transferred = _date_attr(tx, "date_of_transfer")
        explicit_long = _bool_attr(tx, "explicit_long_term")
        tx_is_short = True
        if acquired is not None and transferred is not None:
            tx_is_short = _is_short_term("unlisted_shares", acquired, transferred)
        elif explicit_long is not None:
            tx_is_short = not explicit_long
        if tx_is_short != is_short:
            continue
        consideration += _decimal_attr(tx, "full_consideration")
        fmv += _decimal_attr(tx, "fair_market_value_50ca")
    return deemed_consideration_50ca(consideration, fmv) - consideration


def _claim_total(transactions, section: str) -> Decimal:
    """Sum canonical §54-series / 115F exemption claims for one section.

    Each transaction may carry a list of `CapitalGainExemptionClaim` objects
    under `exemptions`; the claim amount is `investment_amount +
    cgas_deposit_amount`.  Legacy scalar fields (`deduction_us54` etc.) are
    used only when no canonical claim for that section exists on that row.
    """
    canonical = _ZERO
    legacy_map = {
        "54": ("deduction_us54",),
        "54B": ("deduction_us54b",),
        "54EC": ("deduction_us54ec",),
        "54F": ("deduction_us54f",),
        "115F": tuple(),
    }
    for tx in transactions or []:
        claims = getattr(tx, "exemptions", None) or []
        section_total = _ZERO
        for claim in claims:
            if getattr(claim, "section", None) == section:
                section_total += _decimal_attr(claim, "investment_amount")
                section_total += _decimal_attr(claim, "cgas_deposit_amount")
        if section_total > _ZERO:
            canonical += section_total
        else:
            for legacy_field in legacy_map.get(section, ()):
                legacy_val = _decimal_attr(tx, legacy_field)
                if legacy_val > _ZERO:
                    canonical += legacy_val
                    break
    return canonical


@dataclass
class _LegacyClaim:
    """Duck-typed stand-in for a canonical `CapitalGainExemptionClaim`.

    Lets `_normalized_land_exemptions()` feed a legacy-scalar-only claim
    through the same `_exemption_claim_total()`/`asset.exemptions` path a
    canonical claim uses, without this schedule module importing the real
    Pydantic model (keeping the calculators -> schedule dependency arrow
    one-way, per this module's own header comment).
    """

    section: str
    investment_amount: Decimal = _ZERO
    cgas_deposit_amount: Decimal = _ZERO


_LEGACY_EXEMPTION_FIELDS = {
    "54": "deduction_us54",
    "54B": "deduction_us54b",
    "54EC": "deduction_us54ec",
    "54F": "deduction_us54f",
    "54D": "deduction_us54d",
    "54G": "deduction_us54g",
    "54GA": "deduction_us54ga",
}


def _normalized_land_exemptions(tx) -> list:
    """Canonical §54-series claims plus any legacy-scalar-only claims.

    `CGTransaction.deduction_us54*` legacy scalar fields are accepted by
    the schema as a standalone claim (only rejected if they DISAGREE with a
    canonical claim for the same section, not required to duplicate one --
    see `CGTransaction.validate_transaction()`). Without this
    normalization, a claim entered ONLY via a legacy scalar field on a
    land/building transaction was invisible to `compute_stcg()`/
    `compute_ltcg()`'s per-asset `exemption_total` (sourced exclusively
    from `asset.exemptions`, itself built only from the canonical
    `exemptions` list at classification time) -- so a 54B claim entered
    this way would silently never reduce the assessee's actual STCG tax,
    the same bug class `aggregate()`/`_post_loss_cg_baskets()` are fixed
    for below, just via a different, legacy-field-only entry path.
    """
    claims = list(getattr(tx, "exemptions", None) or [])
    covered = {getattr(c, "section", None) for c in claims}
    for section, field_name in _LEGACY_EXEMPTION_FIELDS.items():
        if section in covered:
            continue
        legacy_amount = _decimal_attr(tx, field_name)
        if legacy_amount > _ZERO:
            claims.append(_LegacyClaim(section=section, investment_amount=legacy_amount))
    return claims


def _classify(transactions) -> tuple:
    """Classify canonical CG transactions into the schedule's baskets.

    Returns:
        (ltcg_112a_assets, stcg_land, ltcg_land, stcg_111a_signed,
         stcg_other_signed, ltcg_other_signed)
    """
    ltcg_112a_assets: list[CG112AAsset] = []
    stcg_land: list[CGAsset] = []
    ltcg_land: list[CGAsset] = []
    stcg_111a_signed = _ZERO
    stcg_other_signed = _ZERO
    ltcg_other_signed = _ZERO

    for tx in transactions or []:
        asset_type = _asset_type_value(tx)
        full_consideration = _decimal_attr(tx, "full_consideration")
        cost = _decimal_attr(tx, "cost_of_acquisition")
        expenditure = _decimal_attr(tx, "expenditure_on_transfer")
        acquired = _date_attr(tx, "date_of_acquisition")
        transferred = _date_attr(tx, "date_of_transfer")
        explicit_long = _bool_attr(tx, "explicit_long_term")

        # Determine holding period by calendar anniversary.
        is_short = True
        if acquired is not None and transferred is not None:
            is_short = _is_short_term(asset_type, acquired, transferred)
        elif explicit_long is not None:
            is_short = not explicit_long

        acquired_str = acquired.isoformat() if acquired is not None else ""
        transferred_str = transferred.isoformat() if transferred is not None else ""
        grandfathering_eligible = acquired is not None and acquired < _GRANDFATHERING_CUTOFF

        if asset_type in _112A_ASSET_TYPES:
            ltcg_112a_assets.append(CG112AAsset(
                isin_code=str(_attr(tx, "isin_code", "") or "INNOTREQUIRD"),
                share_name=str(_attr(tx, "description", "") or ""),
                total_sale_value=full_consideration,
                cost_acq_without_index=cost,
                total_fmv=_decimal_attr(tx, "fair_market_value_jan2018"),
                expenditure=expenditure,
                date_of_acquisition=acquired_str,
                date_of_transfer=transferred_str,
                grandfathering_eligible=grandfathering_eligible,
            ))
        elif asset_type in _111A_ASSET_TYPES:
            gain = full_consideration - cost - expenditure
            if is_short:
                stcg_111a_signed += gain
            else:
                ltcg_112a_assets.append(CG112AAsset(
                    isin_code=str(_attr(tx, "isin_code", "") or "INNOTREQUIRD"),
                    share_name=str(_attr(tx, "description", "") or ""),
                    total_sale_value=full_consideration,
                    cost_acq_without_index=cost,
                    total_fmv=_decimal_attr(tx, "fair_market_value_jan2018"),
                    date_of_acquisition=acquired_str,
                    date_of_transfer=transferred_str,
                    grandfathering_eligible=grandfathering_eligible,
                ))
        elif asset_type in ("land_building", "LAND_BUILDING"):
            asset = CGAsset(
                description=str(_attr(tx, "description", "") or ""),
                date_of_acquisition=acquired_str,
                date_of_transfer=transferred_str,
                full_consideration=full_consideration,
                stamp_duty_value=_decimal_attr(tx, "stamp_duty_value"),
                acquisition_cost=cost,
                indexed_acquisition_cost=_decimal_attr(tx, "indexed_cost"),
                improvement_cost=_decimal_attr(tx, "improvement_cost"),
                indexed_improvement_cost=_decimal_attr(tx, "indexed_improvement"),
                year_of_improvement=str(_attr(tx, "year_of_improvement", "") or ""),
                expenditure_on_transfer=expenditure,
                exemptions=_normalized_land_exemptions(tx),
            )
            if is_short:
                stcg_land.append(asset)
            else:
                ltcg_land.append(asset)
        else:
            gain = full_consideration - cost - expenditure
            # Item 9 (cross-form issues log): the 94(7)/94(8) disallowed-
            # loss add-back (Sl. A5d ITR-2) was present on ITR-3's own
            # equivalent formula (other_asset_gain()) but missing here --
            # entered as a positive value that must be ADDED to reverse a
            # loss the taxpayer already booked but the Act disallows.
            if is_short:
                gain += _decimal_attr(tx, "loss_disallowed_94_7_94_8")
                stcg_other_signed += gain
            else:
                ltcg_other_signed += gain

    # Item 8 (cross-form issues log): section 50CA's "higher of
    # consideration or FMV" deemed value for unquoted-share disposals was
    # correctly disclosed (itd/cg_shared.py) but never applied to the
    # actual taxed gain. Added once, in aggregate, matching the disclosure
    # builder's own aggregation exactly -- see unquoted_shares_50ca_
    # adjustment()'s own docstring for why per-transaction application
    # would overstate the deemed consideration.
    stcg_other_signed += unquoted_shares_50ca_adjustment(transactions, is_short=True)
    ltcg_other_signed += unquoted_shares_50ca_adjustment(transactions, is_short=False)

    return (
        ltcg_112a_assets, stcg_land, ltcg_land,
        stcg_111a_signed, stcg_other_signed, ltcg_other_signed,
    )


def compute(transactions, is_resident: bool = False) -> CGResult:
    """Compute the complete capital-gains suite for AY 2026-27.

    This is the ONE form-agnostic entry point called by every form calculator
    (ITR-1, ITR-2, ITR-3, ITR-4). It classifies the canonical `CGTransaction`
    rows into every CG basket — 112A, 111A, section 112, land/building, other
    — applies 31-Jan-2018 grandfathering, the aggregate ₹1.25 lakh
    section-112A threshold, §54/54B/54EC/54F/115F exemptions, and the
    intra-head STCL↔LTCG set-off, and returns signed baskets plus
    current-year losses.

    Form calculators PROJECT this single result:
      - ITR-1 / ITR-4: aggregate the 112A basket (losses forfeited, no
        exemptions) and enforce the restricted-112A ₹1.25L eligibility cap.
      - ITR-2 / ITR-3: consume the full signed result, feed CYLA/BFLA, and
        report per-scrip Schedule CG with losses and exemptions.

    Virtual-digital-asset (VDA) disposals are NOT classified here; they are
    a separate input (`vda_transactions`) on the ITR-2/3 schema and are
    computed via ``compute_vda()`` by the form calculator, because VDA
    income is outside the regular loss-netting (§115BBH).

    Args:
        transactions: Canonical CGTransaction rows (structurally typed — any
            object exposing the standard CG field names works, so the schedule
            does not import the ITR-2 schema).
        is_resident: Whether the assessee is a resident, for the section
            112(1)(a) second-proviso land/building comparison in
            ``compute_ltcg()``. Defaults to False -- ITR-1/4's restricted
            projection never surfaces land/building LTCG at all, so this is
            a no-op for those callers.

    Returns:
        CGResult with signed LTCG/STCG baskets, exemptions claimed, and the
        current-year CG loss breakout.
    """
    (
        ltcg_112a_assets, stcg_land, ltcg_land,
        stcg_111a_signed, stcg_other_signed, ltcg_other_signed,
    ) = _classify(transactions)

    stcg_result = compute_stcg(
        stcg_111a=stcg_111a_signed,
        stcg_land_building=stcg_land,
        stcg_other=stcg_other_signed,
    )
    ltcg_result = compute_ltcg(
        ltcg_112a_assets=ltcg_112a_assets,
        ltcg_land_building=ltcg_land,
        ltcg_other=ltcg_other_signed,
        is_resident=is_resident,
    )
    exemptions = compute_exemptions(
        section_54=_claim_total(transactions, "54"),
        section_54b=_claim_total(transactions, "54B"),
        section_54ec=_claim_total(transactions, "54EC"),
        section_54f=_claim_total(transactions, "54F"),
        section_115f=_claim_total(transactions, "115F"),
    )
    return aggregate(stcg_result, ltcg_result, _ZERO, exemptions)


def project_restricted_112a(cg_result: CGResult) -> dict:
    """Project the unified CG result as the restricted-112A aggregate view.

    ITR-1 / ITR-4 may report ONLY restricted section-112A LTCG as a single
    aggregate (no per-scrip detail, no losses, no exemptions, no other CG).
    This projection derives that aggregate from the unified computation:

      - The 112A basket is clamped at zero (a loss is forfeited — ITR-1/4
        cannot declare or carry forward capital losses).
      - §54-series exemptions and other CG baskets are reported as
        ``disallowed`` so the form classifier can surface "file ITR-2 to use
        these" guidance to the taxpayer.
      - The official ITR-1/4 112A fields map:
            TotSaleCnsdrn → full_value_of_consideration (112A basket)
            TotCstAcqisn  → cost_of_acquisition (112A basket)
            LongCap112A   → max(0, income_112a)  (≤ ₹1.25 lakh to be eligible)

    Args:
        cg_result: The unified CG schedule result.

    Returns:
        A dict with the restricted-112A aggregate projection fields.
    """
    gain_112a_signed = cg_result.ltcg.income_112a
    gain_112a_clamped = max(_ZERO, gain_112a_signed)
    losses_forfeited = max(_ZERO, -gain_112a_signed) + max(
        _ZERO, cg_result.ltcg.income_125per_other + cg_result.ltcg.income_dtaa
    ) + max(_ZERO, cg_result.stcg.total_stcg)
    exemptions_disallowed = cg_result.exemptions.total_exemption
    other_cg_disallowed = (
        max(_ZERO, cg_result.ltcg.income_125per_other)
        + max(_ZERO, cg_result.ltcg.income_dtaa)
        + max(_ZERO, cg_result.stcg.total_stcg)
        + cg_result.vda
    )
    return {
        "gain_112a": gain_112a_clamped,
        "losses_forfeited": losses_forfeited,
        "exemptions_disallowed": exemptions_disallowed,
        "other_cg_disallowed": other_cg_disallowed,
        "full_value_of_consideration": cg_result.ltcg.income_112a,  # signed pre-clamp
        "schema_fields": {
            "TotSaleCnsdrn": gain_112a_clamped,
            "TotCstAcqisn": cg_result.ltcg.income_112a,  # cost aggregated at schedule level
            "LongCap112A": min(gain_112a_clamped, LTCG_112A_EXEMPTION),
        },
    }
