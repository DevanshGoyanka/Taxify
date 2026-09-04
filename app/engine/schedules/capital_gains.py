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
    stamp_duty_value: Decimal = _ZERO
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
        land_gain += asset.balance
    other = land_gain + _decimal(stcg_other)
    section_111a = _decimal(stcg_111a)
    return STCGResult(
        income_111a=section_111a,
        income_30per=other,
        total_stcg=section_111a + other,
        land_building=list(stcg_land_building or []),
    )


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
    # NOTE: this still prefers indexed_acquisition_cost/indexed_improvement_cost
    # over the non-indexed figures when supplied, matching this function's
    # pre-existing behavior (and the existing regression test
    # test_compute_land_building_long_term_uses_indexed_cost). Per the
    # official ITR-2 form's own Schedule CG instructions (Part B item 1),
    # the PRIMARY declared LTCG ("1c"/B1e) should use the NON-indexed cost;
    # the indexed cost is used only for a separate section 112(1)(a) second
    # proviso tax comparison ("1ca", "for the purpose of computing eiB")
    # that can only ever REDUCE the payable tax below what the non-indexed
    # 12.5% computation would give, never serve as the primary basis. That
    # appears to be a real, separate defect in this function -- deliberately
    # NOT changed here since fixing it correctly requires implementing the
    # full section 112(1)(a) dual tax-comparison this function doesn't
    # attempt at all, not just swapping which cost figure is preferred; see
    # Docs/ITR2_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md for the
    # tracked finding.
    land_gain = _ZERO
    for asset in ltcg_land_building or []:
        deemed = deemed_consideration_50c(asset.full_consideration, getattr(asset, "stamp_duty_value", _ZERO))
        acquisition = _decimal(asset.indexed_acquisition_cost) or _decimal(asset.acquisition_cost)
        improvement = _decimal(asset.indexed_improvement_cost) or _decimal(asset.improvement_cost)
        total_ded = acquisition + improvement + _decimal(asset.expenditure_on_transfer)
        asset.total_deductions = total_ded
        asset.balance = deemed - total_ded
        asset.taxable_gain = asset.balance
        land_gain += asset.balance
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
                expenditure_on_transfer=expenditure,
            )
            if is_short:
                stcg_land.append(asset)
            else:
                ltcg_land.append(asset)
        else:
            gain = full_consideration - cost - expenditure
            if is_short:
                stcg_other_signed += gain
            else:
                ltcg_other_signed += gain

    return (
        ltcg_112a_assets, stcg_land, ltcg_land,
        stcg_111a_signed, stcg_other_signed, ltcg_other_signed,
    )


def compute(transactions) -> CGResult:
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
