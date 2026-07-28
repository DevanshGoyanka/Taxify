"""
Schedule CG: Capital Gains (u/s 45-55A) + Schedule 112A + Schedule VDA.

Capital gains are classified by holding period and asset type:

Short-Term (held <= 12/24/36 months):
  - 111A STCG on listed equity/equity MF (STT paid): 15% pre-Jul23 / 20% post-Jul23
  - Other STCG: taxed at normal slab rates (reported under 30%, AppRate, or DTAA)

Long-Term (held > 12/24/36 months depending on asset):
  - 112A LTCG on equity shares/equity MF/business trust (STT paid): 12.5% post-Jul23
    with ₹1,25,000 annual exemption.
  - Other LTCG: 20% with indexation (pre-Jul23) / 12.5% without indexation (post-Jul23)
  - DTAA: Taxed as per DTAA rates for NRIs

VDA (Virtual Digital Assets / Crypto) u/s 115BBH: Flat 30%, no deductions except cost.

Exemptions:
  - 54: LTCG on residential property reinvested in residential property
  - 54B: CG on agricultural land reinvested in agricultural land
  - 54EC: LTCG invested in specified bonds (REC/NHAI), max ₹50 lakh
  - 54F: LTCG on any asset other than residential property, reinvested in
    residential property (subject to conditions)

ITR forms:
  - ITR-1: Only 112A LTCG, capped at ₹1,25,000
  - ITR-2/3: Full CG schedule
  - ITR-4: Only 112A LTCG, capped at Rs 1,25,000 (CBDT notification AY 2025-26 onwards)
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from app.engine.constants import (
    STCG_111A_RATE_PRE_JUL24,
    STCG_111A_RATE_POST_JUL24,
    LTCG_112A_RATE,
    LTCG_112A_RATE_POST_JUL24,
    LTCG_112A_EXEMPTION,
    LTCG_OTHER_RATE,
    LTCG_OTHER_RATE_POST_JUL24,
)


@dataclass
class CGAsset:
    description: str = ""
    date_of_acquisition: str = ""
    date_of_transfer: str = ""
    full_consideration: Decimal = Decimal("0")
    acquisition_cost: Decimal = Decimal("0")
    indexed_acquisition_cost: Decimal = Decimal("0")
    improvement_cost: Decimal = Decimal("0")
    indexed_improvement_cost: Decimal = Decimal("0")
    expenditure_on_transfer: Decimal = Decimal("0")
    total_deductions: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    exemption_applied: Decimal = Decimal("0")
    exemption_section: str = ""
    taxable_gain: Decimal = Decimal("0")


@dataclass
class CG112AAsset:
    """Per-scrip detail for 112A/115AD equity shares."""
    isin_code: str = ""
    share_name: str = ""
    num_shares: Decimal = Decimal("0")
    sale_price_per_share: Decimal = Decimal("0")
    total_sale_value: Decimal = Decimal("0")
    cost_acq_without_index: Decimal = Decimal("0")
    fmv_per_share: Decimal = Decimal("0")
    total_fmv: Decimal = Decimal("0")
    expenditure: Decimal = Decimal("0")
    total_deductions: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")


@dataclass
class VDAEntry:
    """Per-transaction detail for Virtual Digital Assets u/s 115BBH."""
    date_of_acquisition: str = ""
    date_of_transfer: str = ""
    acquisition_cost: Decimal = Decimal("0")
    consideration_received: Decimal = Decimal("0")
    income_from_vda: Decimal = Decimal("0")


@dataclass
class STCGResult:
    income_111a: Decimal = Decimal("0")
    income_20per: Decimal = Decimal("0")
    income_30per: Decimal = Decimal("0")
    income_app_rate: Decimal = Decimal("0")
    income_dtaa: Decimal = Decimal("0")
    total_stcg: Decimal = Decimal("0")


@dataclass
class LTCGResult:
    income_112a: Decimal = Decimal("0")
    exemption_112a: Decimal = Decimal("0")
    taxable_112a: Decimal = Decimal("0")
    income_125per_other: Decimal = Decimal("0")
    income_dtaa: Decimal = Decimal("0")
    total_ltcg: Decimal = Decimal("0")


@dataclass
class ExemptionResult:
    section_54: Decimal = Decimal("0")
    section_54b: Decimal = Decimal("0")
    section_54ec: Decimal = Decimal("0")
    section_54f: Decimal = Decimal("0")
    total_exemption: Decimal = Decimal("0")


@dataclass
class CurrentYearLossCG:
    stcg20_loss: Decimal = Decimal("0")
    stcg30_loss: Decimal = Decimal("0")
    stcg_app_loss: Decimal = Decimal("0")
    stcg_dtaa_loss: Decimal = Decimal("0")
    ltcg125_loss: Decimal = Decimal("0")
    ltcg_dtaa_loss: Decimal = Decimal("0")
    total_cg_loss: Decimal = Decimal("0")


@dataclass
class CGResult:
    stcg: STCGResult = field(default_factory=STCGResult)
    ltcg: LTCGResult = field(default_factory=LTCGResult)
    vda: Decimal = Decimal("0")
    exemptions: ExemptionResult = field(default_factory=ExemptionResult)
    current_year_losses: CurrentYearLossCG = field(default_factory=CurrentYearLossCG)
    total_capital_gains: Decimal = Decimal("0")
    total_capital_gains_before_exemption: Decimal = Decimal("0")


def _acquire_fy(date_str: str) -> int:
    """Extract financial year from a 'YYYY-MM-DD' date string."""
    if not date_str:
        return 2001
    parts = date_str.split("-")
    y = int(parts[0])
    m = int(parts[1])
    return y if m <= 3 else y + 1


def _cii(fy: int) -> int:
    """Look up CII for a financial year."""
    from app.engine.constants import CII_TABLE
    return CII_TABLE.get(fy, CII_TABLE[max(CII_TABLE)])


def _indexed_cost(cost: Decimal, acquisition_date: str, transfer_date: str) -> Decimal:
    """
    Apply Cost Inflation Index to acquisition cost per Section 48.

    Post-Jul-2023 (FY 2023-24 onwards): For LTCG on assets other than 112A,
    the Finance Act 2023 removed indexation. However, for acquisitions prior
    to 23-Jul-2024, the full cost without indexation is used for LTCG computation.
    For assets acquired in FY 2023-24 and later, indexation is N/A.

    For pre-2001-04-01 acquisitions: FMV as on 01-04-2001 may be substituted.
    """
    if not acquisition_date or not transfer_date:
        return cost

    acq_fy = _acquire_fy(acquisition_date)
    xfer_fy = _acquire_fy(transfer_date)

    if xfer_fy <= 2022:
        # Pre-Jul-2023: use indexation
        cii_acq = _cii(acq_fy)
        cii_xfer = _cii(xfer_fy)
        if cii_acq > 0 and cii_xfer > 0:
            return cost * Decimal(cii_xfer) / Decimal(cii_acq)

    return cost


def compute_112a(assets: list[CG112AAsset]) -> tuple[Decimal, Decimal, Decimal]:
    """
    Compute LTCG u/s 112A with grandfathering provision.

    Per Section 112A Explanation (a), for shares acquired before 31-01-2018:
      Step 1: FMV as on 31-01-2018 (use ``total_fmv`` from input).
      Step 2: Cost basis = max(actual cost, min(FMV on 31-01-2018, sale value)).
      Step 3: Gain = sale value - cost basis - deductions.

    For shares acquired on or after 01-02-2018:
      Gain = sale value - actual cost - deductions.
    """
    if not assets:
        return Decimal("0"), Decimal("0"), Decimal("0")

    total_gain = Decimal("0")
    for a in assets:
        sale_value = a.total_sale_value or Decimal("0")
        actual_cost = a.cost_acq_without_index or Decimal("0")
        fmv = a.total_fmv or Decimal("0")
        total_ded = a.total_deductions or Decimal("0")

        effective_cost = actual_cost
        if fmv > 0 and actual_cost < fmv:
            effective_cost = max(actual_cost, min(fmv, sale_value))
        elif fmv > 0:
            effective_cost = min(fmv, sale_value)

        gain = max(Decimal("0"), sale_value - effective_cost - total_ded)
        total_gain += gain

    exemption = min(total_gain, LTCG_112A_EXEMPTION) if total_gain > 0 else Decimal("0")
    taxable = max(Decimal("0"), total_gain - exemption)

    return total_gain, exemption, taxable


def compute_112a_tax(taxable_112a: Decimal) -> Decimal:
    """Tax u/s 112A at 12.5% on the taxable portion (post to ₹1.25L exemption)."""
    return taxable_112a * LTCG_112A_RATE_POST_JUL24 / Decimal("100")


def compute_stcg(
    stcg_111a: Decimal = Decimal("0"),
    stcg_land_building: list[CGAsset] = None,
    stcg_other: Decimal = Decimal("0"),
    is_post_jul24: bool = True,
) -> STCGResult:
    """
    Compute Short Term Capital Gains.

    Categories:
      - 111A: Listed equity/equity MF (STT paid). Taxed at 15%/20%.
      - Land/Building: Sale of immovable property held <= 24 months.
        Taxed at slab rates but reported separately.
      - Other: STCG on assets not covered by 111A or land/building.
    """
    land_gain = Decimal("0")
    if stcg_land_building:
        for lb in stcg_land_building:
            sale = lb.full_consideration or Decimal("0")
            cost = lb.acquisition_cost or Decimal("0")
            impr = lb.improvement_cost or Decimal("0")
            exp = lb.expenditure_on_transfer or Decimal("0")
            gain = sale - cost - impr - exp  # signed — losses net naturally within sub-category
            land_gain += gain

    return STCGResult(
        income_111a=stcg_111a,
        income_20per=Decimal("0"),
        income_30per=land_gain + stcg_other,
        income_app_rate=Decimal("0"),
        income_dtaa=Decimal("0"),
        total_stcg=stcg_111a + land_gain + stcg_other,
    )


def compute_ltcg(
    ltcg_112a_assets: list[CG112AAsset] = None,
    ltcg_land_building: list[CGAsset] = None,
    ltcg_other: Decimal = Decimal("0"),
    ltcg_dtaa: Decimal = Decimal("0"),
) -> LTCGResult:
    """Compute Long Term Capital Gains across all categories."""
    gain_112a, exemption_112a, taxable_112a = compute_112a(ltcg_112a_assets or [])

    land_gain = Decimal("0")
    if ltcg_land_building:
        for lb in ltcg_land_building:
            sale = lb.full_consideration or Decimal("0")
            icost = lb.indexed_acquisition_cost or lb.acquisition_cost or Decimal("0")
            iimpr = lb.indexed_improvement_cost or lb.improvement_cost or Decimal("0")
            exp = lb.expenditure_on_transfer or Decimal("0")
            gain = sale - icost - iimpr - exp  # signed — losses net within sub-category
            land_gain += gain

    return LTCGResult(
        income_112a=gain_112a,
        exemption_112a=exemption_112a,
        taxable_112a=taxable_112a,
        income_125per_other=land_gain + ltcg_other,
        income_dtaa=ltcg_dtaa,
        total_ltcg=taxable_112a + land_gain + ltcg_other + ltcg_dtaa,
    )


def compute_vda(vda_entries: list[VDAEntry] = None) -> Decimal:
    """
    Compute income from Virtual Digital Assets u/s 115BBH.

    VDA income = Consideration received - Cost of acquisition.
    No other deductions allowed (Section 115BBH(2)).
    Taxed at flat 30%.
    """
    if not vda_entries:
        return Decimal("0")
    total = Decimal("0")
    for v in vda_entries:
        gain = (v.consideration_received or Decimal("0")) - (v.acquisition_cost or Decimal("0"))
        total += max(Decimal("0"), gain)
    return total


def compute_vda_tax(vda_income: Decimal) -> Decimal:
    """Tax u/s 115BBH at 30% on VDA income."""
    from app.engine.constants import VDA_RATE
    return vda_income * VDA_RATE / Decimal("100")


def compute_exemptions(
    section_54: Decimal = Decimal("0"),
    section_54b: Decimal = Decimal("0"),
    section_54ec: Decimal = Decimal("0"),
    section_54f: Decimal = Decimal("0"),
) -> ExemptionResult:
    """
    Compute CG exemptions under Sections 54/54B/54EC/54F.

    Section 54: LTCG from residential property reinvested in residential
    property (max 2 properties if CG <= ₹2Cr).
    Section 54B: CG from agricultural land reinvested in agricultural land.
    Section 54EC: LTCG invested in REC/NHAI bonds within 6 months (max ₹50L).
    Section 54F: LTCG from any asset (not residential property) reinvested
    in residential property. Conditions: net consideration must be reinvested;
    if only part, exemption is proportional.
    """
    return ExemptionResult(
        section_54=section_54,
        section_54b=section_54b,
        section_54ec=section_54ec,
        section_54f=section_54f,
        total_exemption=section_54 + section_54b + section_54ec + section_54f,
    )


def aggregate(
    stcg: STCGResult,
    ltcg: LTCGResult,
    vda: Decimal = Decimal("0"),
    exemptions: ExemptionResult = None,
    current_year_losses: CurrentYearLossCG = None,
) -> CGResult:
    """Aggregate all CG components into a single result."""
    if exemptions is None:
        exemptions = ExemptionResult()
    if current_year_losses is None:
        current_year_losses = CurrentYearLossCG()

    # total_before_exemption uses taxable_112a (net of ₹1.25L 112A exemption)
    # because the 112A exemption is per-section, not a 54-series exemption.
    # 54/54B/54EC/54F exemptions apply to land/building only and are subtracted next.
    total_before_exemption = stcg.total_stcg + ltcg.taxable_112a + ltcg.income_125per_other + ltcg.income_dtaa + vda
    total = total_before_exemption - exemptions.total_exemption

    return CGResult(
        stcg=stcg,
        ltcg=ltcg,
        vda=vda,
        exemptions=exemptions,
        current_year_losses=current_year_losses,
        total_capital_gains=max(Decimal("0"), total),
        total_capital_gains_before_exemption=total_before_exemption,
    )
