"""
ITR-2 Calculator — AY 2026-27 (FY 2025-26).

Orchestrates all schedule modules to produce a complete, signed computation
with capital gains, loss set-off, special-rate income, deductions, AMT,
foreign tax relief, interest, and tax credits.

Computation order:
  1.  Income heads: Salary, HP, OS, Capital Gains, VDA
  2.  Clubbing (SPI) added to respective heads
  3.  Intra-head CG loss set-off (STCL before LTCL)
  4.  CYLA: Current-year inter-head loss set-off
  5.  BFLA: Brought-forward loss set-off
  6.  CFL: Carry-forward loss summary
  7.  GTI = all heads after CYLA + BFLA
  8.  Agricultural income for partial integration
  9.  Chapter VI-A deductions (adjusted GTI base excludes special-rate income)
  10. TI = GTI - deductions (rounded u/s 288A)
  11. SI: Special-rate income tax (111A at 20%, 112 at 12.5%, 112A at 12.5%
      after one-time ₹1.25L threshold, VDA at 30%, etc.)
  12. Normal slab tax on (TI - special-rate income)
  13. AMT if triggered (old regime, AMT additions)
  14. Rebate u/s 87A (resident individuals only, slab tax only)
  15. Surcharge with 15% cap on 111A/112/112A/dividend; marginal relief
  16. 4% Health & Education Cess
  17. Foreign tax relief (TR1, u/s 90/91)
  18. Interest 234A/B/C + late fee 234F
  19. TDS/TCS and tax payments (claimed amounts)
  20. Net tax payable / refund
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.engine.common.cess import compute as compute_cess
from app.engine.common.interest import compute_234a, compute_234b, compute_234c, compute_234i, compute_234f
from app.engine.common.due_dates import get_due_date, get_default_filing_date
from app.engine.common.rebate import compute as compute_rebate
from app.engine.common.rounding import round_to_nearest_10
from app.engine.common.slab_tax import compute as compute_slab_tax
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.constants import (
    HEALTH_EDUCATION_CESS_RATE,
    LTCG_112A_EXEMPTION,
    LTCG_112A_RATE_POST_JUL24,
    LTCG_OTHER_RATE_POST_JUL24,
    STCG_111A_RATE_POST_JUL24,
    VDA_RATE,
)
from app.engine.schedules.agricultural import compute as compute_agri
from app.engine.schedules.agricultural import compute_partial_integration_tax
from app.engine.schedules.amt import AMTAddition, AMTAdditionSection, compute as compute_amt
from app.engine.schedules.capital_gains import (
    CG112AAsset,
    CGAsset,
    CGResult,
    CurrentYearLossCG,
    ExemptionResult,
    LTCGResult,
    STCGResult,
    VDAEntry,
    aggregate as aggregate_cg,
    compute_112a as compute_112a_gain,
    compute_exemptions,
    compute_ltcg,
    compute_stcg,
    compute_vda,
)
from app.engine.schedules.deductions import compute_all as compute_deductions
from app.engine.schedules.house_property import apply_inter_head_loss_limit, compute as compute_hp
from app.engine.schedules.house_property import HPResult
from app.engine.schedules.loss_setoff.bfla import BFLAInput, BFLAResult, compute as compute_bfla
from app.engine.schedules.loss_setoff.cfl import CFLResult, compute as compute_cfl
from app.engine.schedules.loss_setoff.cyla import CYLAInput, CYLAResult, compute as compute_cyla
from app.engine.schedules.other_sources import compute as compute_os
from app.engine.schedules.salary import compute as compute_salary
from app.engine.schedules.special_rates import (
    SpecialRateEntry,
    SpecialRatesResult,
    aggregate as aggregate_si,
    compute_111a,
    compute_112,
    compute_112a_taxable,
    compute_115bbf,
    compute_115bbg,
    compute_115bbe,
    compute_115bbi,
    compute_lottery,
    compute_vda as si_vda,
)
from app.engine.schedules.tds_tcs import compute_all as compute_tds_tcs
from app.schemas.itr1 import AgeBracket, TaxRegime
from app.schemas.itr2 import ITR2Input, ITR2FilingProfile, ResidentialStatus

_ZERO = Decimal("0")
_OS_HEAD_SI_SECTIONS = frozenset({
    "115BB", "115BBE", "115BBF", "115BBG", "115BBJ", "115BBA", "111", "115E",
    # Section 115A/115AC/115ACA/115AD "any other income chargeable at
    # special rate" dropdown family -- confirmed part of the Other Sources
    # head by the official form's own Part B-TI arithmetic (item 4:
    # "4d Total (4a + 4b + 4c)" where 4b is literally "Income chargeable to
    # tax at special rates (2 of Schedule OS)").
    "5A1ai", "5A1aA", "5A1aii", "5A1aiia", "5A1aiiaa", "5A1aiiab",
    "5A1aiiac", "5A1aiii", "5A1bA", "5AC1ab", "5AC1abD", "5ACA1a",
    "5AD1i", "5AD1iP", "5AD1iDiv", "5A1aiiaaP", "5A1aiiaa2P",
})


@dataclass
class ITR2Result:
    """Complete ITR-2 computation result with all schedules."""

    # Income heads
    salary_income: Decimal = _ZERO
    house_property_income: Decimal = _ZERO
    capital_gains_income: Decimal = _ZERO
    other_sources_income: Decimal = _ZERO
    vda_income: Decimal = _ZERO
    clubbing_income: Decimal = _ZERO

    # GTI and loss set-off
    gti_before_loss_setoff: Decimal = _ZERO
    cyla_total_set_off: Decimal = _ZERO
    bfla_total_set_off: Decimal = _ZERO
    gti_after_loss_setoff: Decimal = _ZERO
    gross_total_income: Decimal = _ZERO

    # Agricultural income
    net_agricultural_income: Decimal = _ZERO
    partial_integration_tax: Decimal = _ZERO

    # Deductions and taxable income
    deductions_total: Decimal = _ZERO
    taxable_income: Decimal = _ZERO
    aggregate_income: Decimal = _ZERO

    # Tax
    slab_tax: Decimal = _ZERO
    special_rate_tax: Decimal = _ZERO
    amt_tax: Decimal = _ZERO
    total_tax_before_relief: Decimal = _ZERO
    tax_before_rebate: Decimal = _ZERO
    rebate_87a: Decimal = _ZERO
    tax_after_rebate: Decimal = _ZERO
    surcharge: Decimal = _ZERO
    health_education_cess: Decimal = _ZERO
    gross_tax_liability: Decimal = _ZERO

    # Relief and interest
    relief_89: Decimal = _ZERO
    relief_90_91: Decimal = _ZERO
    interest_234a: Decimal = _ZERO
    interest_234b: Decimal = _ZERO
    interest_234c: Decimal = _ZERO
    late_fee_234f: Decimal = _ZERO
    fees_234i: Decimal = _ZERO
    total_interest: Decimal = _ZERO

    # Final
    net_tax_liability: Decimal = _ZERO
    total_tds: Decimal = _ZERO
    total_tcs: Decimal = _ZERO
    total_advance_tax: Decimal = _ZERO
    total_self_assessment_tax: Decimal = _ZERO
    total_taxes_paid: Decimal = _ZERO
    balance_payable: Decimal = _ZERO
    refund_due: Decimal = _ZERO

    # Remaining losses
    hp_loss_disallowed: Decimal = _ZERO
    cyla_remaining: Decimal = _ZERO
    bfla_remaining: Decimal = _ZERO

    # Schedule objects for builder/validators
    schedules: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _get_basic_exemption(age_bracket: AgeBracket) -> Decimal:
    """Return the old-regime basic exemption for the age bracket."""
    if age_bracket == AgeBracket.ABOVE_80:
        return Decimal("500000")
    if age_bracket == AgeBracket.SIXTY_TO_80:
        return Decimal("300000")
    return Decimal("250000")


def _calendar_anniversary(acquired: date, years: int) -> date:
    """Return a calendar anniversary, normalizing 29 February to 28 February."""
    try:
        return acquired.replace(year=acquired.year + years)
    except ValueError:
        return acquired.replace(year=acquired.year + years, day=28)


def _is_short_term(asset_type: str, acquired: date, transferred: date) -> bool:
    """Classify holding period under AY 2026-27 asset-specific rules."""
    if asset_type in {"specified_mutual_fund_50aa", "market_linked_debenture_50aa", "depreciable_asset"}:
        return True
    years = 1 if asset_type in {
        "listed_equity_112a", "equity_oriented_fund_112a", "business_trust_unit_112a",
        "listed_equity_111a", "equity_oriented_fund_111a", "listed_security",
    } else 2
    return transferred < _calendar_anniversary(acquired, years)


def _classify_cg_transactions(
    input_data: ITR2Input,
) -> tuple[list[CG112AAsset], list[CGAsset], list[CGAsset], Decimal, Decimal, Decimal]:
    """Classify ITR-2 CG transactions into 112A, land/building, 111A, and other baskets.

    Returns:
        (112A_assets, stcg_land, ltcg_land, stcg_111a_signed,
         stcg_other_signed, ltcg_other_signed)
    """
    ltcg_112a_assets: list[CG112AAsset] = []
    stcg_land: list[CGAsset] = []
    ltcg_land: list[CGAsset] = []
    stcg_111a_signed = _ZERO
    stcg_other_signed = _ZERO
    ltcg_other_signed = _ZERO

    for tx in input_data.cg_transactions:
        asset_type = tx.asset_type.value

        # Determine holding period by calendar anniversary, never day-count approximations.
        is_short = True
        if tx.date_of_acquisition is not None:
            is_short = _is_short_term(asset_type, tx.date_of_acquisition, tx.date_of_transfer)
        elif tx.explicit_long_term is not None:
            is_short = not tx.explicit_long_term

        if asset_type in ("listed_equity_112a", "equity_oriented_fund_112a", "business_trust_unit_112a"):
            ltcg_112a_assets.append(CG112AAsset(
                isin_code=tx.isin_code or "INNOTREQUIRD",
                share_name=tx.description or "",
                total_sale_value=tx.full_consideration,
                cost_acq_without_index=tx.cost_of_acquisition,
                total_fmv=tx.fair_market_value_jan2018 or _ZERO,
                date_of_acquisition=tx.date_of_acquisition.isoformat() if tx.date_of_acquisition else "",
                date_of_transfer=tx.date_of_transfer.isoformat(),
                grandfathering_eligible=tx.date_of_acquisition is not None and tx.date_of_acquisition < date(2018, 2, 1),
            ))
        elif asset_type == "listed_equity_111a" or asset_type == "equity_oriented_fund_111a":
            gain = tx.full_consideration - tx.cost_of_acquisition - tx.expenditure_on_transfer
            if is_short:
                stcg_111a_signed += gain
            else:
                ltcg_112a_assets.append(CG112AAsset(
                    isin_code=tx.isin_code or "INNOTREQUIRD",
                    share_name=tx.description or "",
                    total_sale_value=tx.full_consideration,
                    cost_acq_without_index=tx.cost_of_acquisition,
                    total_fmv=tx.fair_market_value_jan2018 or _ZERO,
                    date_of_acquisition=tx.date_of_acquisition.isoformat() if tx.date_of_acquisition else "",
                    date_of_transfer=tx.date_of_transfer.isoformat(),
                    grandfathering_eligible=tx.date_of_acquisition is not None and tx.date_of_acquisition < date(2018, 2, 1),
                ))
        elif asset_type == "land_building":
            asset = CGAsset(
                description=tx.description or "",
                date_of_acquisition=tx.date_of_acquisition.isoformat() if tx.date_of_acquisition else "",
                date_of_transfer=tx.date_of_transfer.isoformat(),
                full_consideration=tx.full_consideration,
                stamp_duty_value=tx.stamp_duty_value or Decimal("0"),
                acquisition_cost=tx.cost_of_acquisition,
                indexed_acquisition_cost=tx.indexed_cost,
                improvement_cost=tx.improvement_cost,
                indexed_improvement_cost=tx.indexed_improvement,
                expenditure_on_transfer=tx.expenditure_on_transfer,
            )
            if is_short:
                stcg_land.append(asset)
            else:
                ltcg_land.append(asset)
        else:
            gain = tx.full_consideration - tx.cost_of_acquisition - tx.expenditure_on_transfer
            if is_short:
                stcg_other_signed += gain
            else:
                ltcg_other_signed += gain

    return ltcg_112a_assets, stcg_land, ltcg_land, stcg_111a_signed, stcg_other_signed, ltcg_other_signed


def _consume(amount: Decimal, pools: list[Decimal]) -> tuple[Decimal, list[Decimal]]:
    """Consume a nonnegative amount from ordered nonnegative income pools."""
    remaining = max(_ZERO, amount)
    updated = list(pools)
    for index, pool in enumerate(updated):
        used = min(remaining, max(_ZERO, pool))
        updated[index] = max(_ZERO, pool - used)
        remaining -= used
    return remaining, updated


def _post_loss_cg_baskets(
    stcg: STCGResult,
    ltcg: LTCGResult,
    cyla: CYLAResult,
    bfla: BFLAResult,
    non_cg_income_available_for_hp: Decimal,
    exemptions: ExemptionResult,
) -> dict[str, Decimal]:
    """Allocate statutory loss set-offs into capital-gain rate baskets.

    Uses the per-basket residual incomes from the 6-sub-basket CYLA and BFLA
    engines to populate the official ITR-2 Schedule CG/Part B-TI sub-baskets.
    """
    # Map CYLA/BFLA 6-sub-basket residuals into the 4 post-loss baskets
    # used by the SI engine.
    normal_stcg = cyla.stcg30_remaining  # 30% normal-rate STCG
    section_111a = cyla.stcg20_remaining  # 20% 111A STCG
    # 112A gross and 112 other LTCG are both in the ltcg125 pool;
    # split 112A out for threshold application.
    other_ltcg = bfla.ltcg125_remaining  # post-BFLA LTCG (includes 112A)
    section_112a = max(_ZERO, ltcg.income_112a)  # gross 112A before losses

    # Allocate CYLA/BFLA losses against 112A vs other LTCG proportionally
    total_ltcg_before = max(_ZERO, ltcg.income_112a) + max(_ZERO, ltcg.income_125per_other) + max(_ZERO, ltcg.income_dtaa)
    if total_ltcg_before > _ZERO:
        ltcg_loss_absorbed = max(_ZERO, total_ltcg_before) - other_ltcg
        # Absorb losses proportionally from 112A and other LTCG
        ratio_112a = max(_ZERO, ltcg.income_112a) / total_ltcg_before
        section_112a = max(_ZERO, ltcg.income_112a) - ltcg_loss_absorbed * ratio_112a
        other_ltcg = max(_ZERO, ltcg.income_125per_other + ltcg.income_dtaa) - ltcg_loss_absorbed * (1 - ratio_112a)

    # HP loss absorbed from CG (after non-CG income) — already handled in CYLA
    # per-basket residuals, so no additional allocation needed here.

    # BFLA CG losses are already consumed in the per-basket residuals.
    # No additional allocation needed.

    # Section 54-series claims can only reduce positive LTCG.
    _, pools = _consume(exemptions.total_exemption, [other_ltcg, section_112a])
    other_ltcg, section_112a = pools
    return {
        "normal_stcg": normal_stcg,
        "111a": section_111a,
        "112": other_ltcg,
        "112a_gross": section_112a,
        "112a_taxable": max(_ZERO, section_112a - LTCG_112A_EXEMPTION),
    }


def compute(input_data: ITR2Input) -> ITR2Result:
    """Compute ITR-2 tax liability end-to-end.

    Args:
        input_data: Canonical ITR-2 input model.

    Returns:
        Complete computation result with signed baskets, typed schedules,
        and no placeholder data.
    """
    r = ITR2Result()
    regime = input_data.tax_regime
    age = input_data.age_bracket
    is_resident = input_data.residential_status == ResidentialStatus.RESIDENT
    is_individual = (
        input_data.filing_profile is None
        or input_data.filing_profile.assessee_status.value == "I"
    )
    # Section 112(1)(a) second-proviso eligibility (land/building LTCG
    # comparison, capital_gains.py::compute_ltcg()) counts BOTH ordinary
    # residents and not-ordinarily-residents (NOR is a species of "resident"
    # under section 6 -- only a non-resident is excluded), distinct from
    # `is_resident` above (used for the narrower section 87A rebate
    # eligibility, deliberately left unchanged here).
    is_resident_or_nor = input_data.residential_status != ResidentialStatus.NON_RESIDENT

    # ── 1. Income Heads ──────────────────────────────────────────────────────
    sal = compute_salary(input_data.salary_income, regime)
    r.salary_income = sal.income_chargeable
    r.schedules["salary"] = sal

    # Support both single house_property_income and multiple house_properties
    hp_results: list[HPResult] = []
    if input_data.house_property_income:
        hp_results.append(compute_hp(input_data.house_property_income, regime))
    for prop in input_data.house_properties:
        hp_results.append(compute_hp(prop, regime))

    # Aggregate HP income (intra-head netting)
    hp_total = sum((hp.income_chargeable for hp in hp_results), _ZERO)
    hp_loss_disallowed_total = sum((hp.loss_disallowed for hp in hp_results), _ZERO)
    r.hp_loss_disallowed = hp_loss_disallowed_total
    r.house_property_income = hp_total
    # HP-head pass-through income (Schedule PTI, e.g. a REIT/InvIT's own
    # house-property income passed through under section 115UA) retains its
    # head in the unit holder's hands -- added here, before CYLA/BFLA, so a
    # passed-through HP loss is subject to the same inter-head set-off cap
    # as the assessee's own HP loss. Previously this income was disclosed in
    # Schedule PTI's own JSON block but never reached GTI at all -- the same
    # "computed but not included in GTI" bug pattern as several other
    # Schedule OS/PTI categories fixed this session.
    r.house_property_income += sum(
        (p.income_amount for p in input_data.pti_entries if p.income_head == "HP"), _ZERO
    )
    r.schedules["hp"] = hp_results

    os = compute_os(input_data.other_sources_income, regime)
    r.other_sources_income = os.income_chargeable
    # Schedule-SI sections that are genuinely part of the Other Sources head
    # for Total Income purposes -- lottery/gaming (115BB/115BBJ), unexplained
    # income (115BBE), accumulated PF (111), patent royalty (115BBF), carbon
    # credits (115BBG), non-resident sportsmen (115BBA). These must be
    # included in GTI here, the same way 111A/112/112A/VDA capital-gains
    # special-rate income is included via positive_regular_cg/vda_income
    # below -- otherwise Total Income is understated and the later
    # `ti - special_rate_income_for_slab` step (which already subtracts this
    # same total via si_result.surcharge_full_income) removes income that
    # was never added, incorrectly shrinking slab tax on unrelated income.
    # Uses gross_income (not gross_income - deductions) to match exactly
    # what compute_lottery()/compute_115bbe()/etc. below actually tax.
    r.other_sources_income += sum(
        (sie.gross_income for sie in input_data.si_entries if sie.section in _OS_HEAD_SI_SECTIONS),
        _ZERO,
    )
    # Income from owning/maintaining race horses (Schedule OS's own
    # "IncFromOwnHorse" sub-head) is slab-rate Other Sources income like any
    # other OS category, just disclosed separately in the official form.
    # Only a net profit is added to GTI here -- a race-horse activity loss
    # cannot be set off against other income at all (section 74A(3)), so a
    # negative balance is disclosed but not netted against other OS income;
    # its carry-forward is a further, separately-scoped limitation.
    if input_data.os_race_horse is not None:
        r.other_sources_income += max(_ZERO, input_data.os_race_horse.balance)
    # Income from letting machinery/plant/furniture (Section 56(2)(ii)/(iii),
    # Schedule OS's "RentFromMachPlantBldgs") is ordinary slab-rate Other
    # Sources income computed net of its own specific deductions --
    # Expenses/Depreciation/interest u/s 57 reduce it, while amounts
    # disallowed u/s 58 and deemed profits u/s 59 (a balancing charge on
    # sale of assets used in the letting activity) add back to it. Floored
    # at zero: a resulting loss would need its own carry-forward tracking,
    # a further scoped-out limitation matching the race-horse treatment
    # above.
    if input_data.os_machinery_plant_rent:
        ded = input_data.os_deductions
        deductible = (ded.expenses + ded.depreciation + ded.interest_expense_us57) if ded else _ZERO
        addbacks = (ded.amount_not_deductible_us58 + ded.profit_chargeable_us59) if ded else _ZERO
        r.other_sources_income += max(
            _ZERO, input_data.os_machinery_plant_rent - deductible + addbacks
        )
    # NRI/FII special-rate Other Sources income (Section 115A/115AC/115ACA/
    # 115AD/115E family, Schedule OS's "OthersGrossDtls" dropdown) lives in
    # its own `os_special_rate_entries` field, entirely separate from
    # `input_data.si_entries` -- so it is NOT covered by the
    # `_OS_HEAD_SI_SECTIONS` inclusion above and must be added to GTI here,
    # using the same gross-amount-taxed convention.
    r.other_sources_income += sum(
        (spr.source_amount for spr in input_data.os_special_rate_entries), _ZERO
    )
    # DTAA-rate Other Sources income (Schedule OS's NRIDTAADtlsSchOS rows) --
    # likewise a field entirely separate from `input_data.si_entries`/
    # `_OS_HEAD_SI_SECTIONS`, so it needs the same independent GTI-inclusion
    # step as the block above. Previously this income was disclosed but
    # never reached GTI or Schedule SI at all.
    r.other_sources_income += sum(
        (dtaa.amount for dtaa in input_data.os_dtaa_entries), _ZERO
    )
    # OS-head pass-through income (Schedule PTI) -- STCG/LTCG-head PTI
    # entries are already dispatched to Schedule SI above; HP-head is added
    # to house_property_income above; OS-head retains its head as ordinary
    # slab-rate Other Sources income in the unit holder's hands. Same
    # previously-missing GTI-inclusion bug as the HP-head fix above.
    r.other_sources_income += sum(
        (p.income_amount for p in input_data.pti_entries if p.income_head == "OS"), _ZERO
    )
    r.schedules["os"] = os

    # ── 2. Capital Gains ─────────────────────────────────────────────────────
    # The standalone CG schedule classifies every canonical transaction into
    # the 112A / 111A / section-112 / land-building / other baskets, applies
    # 31-Jan-2018 grandfathering, the ₹1.25L aggregate 112A threshold, and
    # §54/54B/54EC/54F/115F exemptions, and runs the intra-head STCL↔LTCG
    # set-off. The ITR-2 calculator consumes that signed result and then
    # performs the form-specific CYLA/BFLA/special-rate tax work on top.
    from app.engine.schedules.capital_gains import (
        CG112AAsset as _CG112AAsset,
        _classify as _cg_classify,
        aggregate as _aggregate_cg,
        compute as _compute_cg_schedule,
        compute_ltcg as _compute_ltcg_merged,
        compute_stcg as _compute_stcg_merged,
        compute_vda as _compute_vda_income,
    )
    cg_result = _compute_cg_schedule(input_data.cg_transactions, is_resident=is_resident_or_nor)

    # Merge explicit 112A scrips (Schedule 112A Part-A3) into the 112A basket
    # so the ₹1.25L threshold is applied once over the union of classified
    # scrips and explicit scrips.  VDA (§115BBH) is kept outside the regular
    # loss-netting and folded in after aggregation.
    if input_data.cg_112a_scrips:
        (
            ltcg_112a_assets, stcg_land, ltcg_land,
            stcg_111a_signed, stcg_other_signed, ltcg_other_signed,
        ) = _cg_classify(input_data.cg_transactions)
        for scrip in input_data.cg_112a_scrips:
            ltcg_112a_assets.append(_CG112AAsset(
                isin_code=scrip.isin_code,
                share_name=scrip.share_unit_name,
                num_shares=scrip.num_shares_units,
                sale_price_per_share=scrip.sale_price_per_share,
                total_sale_value=scrip.total_sale_value,
                cost_acq_without_index=scrip.cost_acq_without_index,
                fmv_per_share=scrip.fmv_per_share,
                total_fmv=scrip.total_fmv,
                expenditure=scrip.expenditure_on_transfer,
                total_deductions=scrip.total_deductions,
                date_of_acquisition=scrip.date_of_acquisition.isoformat() if scrip.date_of_acquisition else "",
                date_of_transfer=scrip.date_of_transfer.isoformat(),
                grandfathering_eligible=scrip.is_before_31jan2018,
            ))
        stcg_result = _compute_stcg_merged(
            stcg_111a=stcg_111a_signed,
            stcg_land_building=stcg_land,
            stcg_other=stcg_other_signed,
        )
        ltcg_result = _compute_ltcg_merged(
            ltcg_112a_assets=ltcg_112a_assets,
            ltcg_land_building=ltcg_land,
            ltcg_other=ltcg_other_signed,
            is_resident=is_resident_or_nor,
        )
        cg_result = _aggregate_cg(stcg_result, ltcg_result, _ZERO, cg_result.exemptions)
    else:
        stcg_result = cg_result.stcg
        ltcg_result = cg_result.ltcg

    # VDA (§115BBH) — outside the regular loss-netting.
    vda_entries: list[VDAEntry] = []
    for vda in input_data.vda_transactions:
        vda_entries.append(VDAEntry(
            date_of_acquisition=vda.date_of_acquisition.isoformat(),
            date_of_transfer=vda.date_of_transfer.isoformat(),
            acquisition_cost=vda.acquisition_cost,
            consideration_received=vda.consideration_received,
        ))
    vda_income = _compute_vda_income(vda_entries)
    r.vda_income = vda_income
    cg_result = type(cg_result)(
        stcg=cg_result.stcg,
        ltcg=cg_result.ltcg,
        vda=vda_income,
        exemptions=cg_result.exemptions,
        current_year_losses=cg_result.current_year_losses,
        total_capital_gains=cg_result.total_capital_gains + vda_income,
        total_capital_gains_before_exemption=cg_result.total_capital_gains_before_exemption + vda_income,
    )
    r.schedules["cg"] = cg_result

    # ── 3. Clubbing (SPI) ────────────────────────────────────────────────────
    clubbing = sum((spi.amount_included for spi in input_data.spi_entries), _ZERO)
    r.clubbing_income = clubbing
    # Add to the head specified by each SPI entry
    for spi in input_data.spi_entries:
        if spi.head_of_income == "SAL":
            r.salary_income += spi.amount_included
        elif spi.head_of_income == "HP":
            r.house_property_income += spi.amount_included
        elif spi.head_of_income == "CG":
            r.capital_gains_income += spi.amount_included
        else:
            r.other_sources_income += spi.amount_included

    # ── 4. GTI before loss set-off ───────────────────────────────────────────
    # Gross positive heads before current-year and brought-forward loss adjustments.
    # VDA remains a separate positive special-rate basket and cannot absorb losses.
    positive_regular_cg = max(_ZERO, stcg_result.total_stcg) + max(_ZERO, ltcg_result.total_ltcg)
    gti_before = (
        max(_ZERO, r.salary_income)
        + max(_ZERO, r.house_property_income)
        + positive_regular_cg
        + vda_income
        + max(_ZERO, r.other_sources_income)
    )
    r.gti_before_loss_setoff = gti_before

    # ── 5. CYLA: Current Year Loss Set-off ───────────────────────────────────
    # Map CG baskets into 6 statutory sub-baskets for CYLA/BFLA/CG schedule.
    # STCG: 111A (20%) goes to stcg20; other STCG (30% normal rate) to stcg30;
    # applicable-rate and DTAA baskets are zero unless explicitly classified.
    stcg_111a_signed = stcg_result.income_111a
    stcg_30_signed = stcg_result.income_30per + stcg_result.income_app_rate + stcg_result.income_dtaa
    stcg_app_signed = _ZERO  # applicable-rate STCG (e.g. 15% pre-Jul 2024 111A)
    stcg_dtaa_signed = _ZERO  # DTAA-rate STCG
    ltcg_125_signed = ltcg_result.income_125per_other  # section 112 at 12.5%
    ltcg_112a_gross = ltcg_result.income_112a  # 112A before threshold
    ltcg_dtaa_signed = ltcg_result.income_dtaa  # DTAA-rate LTCG

    # HP loss for CYLA (capped at 2L for old regime; blocked for new regime)
    hp_loss_for_cyla = _ZERO
    if r.house_property_income < _ZERO and regime == TaxRegime.OLD:
        hp_loss_for_cyla = abs(min(_ZERO, r.house_property_income))
    elif r.house_property_income < _ZERO and regime == TaxRegime.NEW:
        pass

    cy_input = CYLAInput(
        hp_loss=-hp_loss_for_cyla if hp_loss_for_cyla > 0 else _ZERO,
        hp_income=max(_ZERO, r.house_property_income),
        stcg20_income=stcg_111a_signed,
        stcg30_income=stcg_30_signed,
        stcg_app_income=stcg_app_signed,
        stcg_dtaa_income=stcg_dtaa_signed,
        ltcg125_income=ltcg_125_signed + ltcg_112a_gross,
        ltcg_dtaa_income=ltcg_dtaa_signed,
        non_salary_income=max(_ZERO, r.salary_income) + max(_ZERO, r.other_sources_income),
        non_spec_biz_loss=_ZERO,
        non_spec_biz_income=_ZERO,
        spec_biz_loss=_ZERO,
        spec_biz_income=_ZERO,
    )
    cyla = compute_cyla(cy_input)
    r.cyla_total_set_off = cyla.total_loss_set_off
    r.cyla_remaining = cyla.total_loss_remaining
    r.schedules["cyla"] = cyla

    # ── 6. BFLA: Brought Forward Loss Set-off ────────────────────────────────
    bf_loss_items = [
        {
            "assessment_year": item.assessment_year,
            "head": item.head.value if hasattr(item.head, "value") else str(item.head),
            "sub_category": item.sub_category,
            "original_loss": item.original_loss,
            "brought_forward": item.brought_forward,
        }
        for item in input_data.bf_losses
    ]

    bf_input = BFLAInput(
        hp_income=max(_ZERO, r.house_property_income),
        non_spec_biz_income=_ZERO,
        spec_biz_income=_ZERO,
        stcg20_income=cyla.stcg20_remaining,
        stcg30_income=cyla.stcg30_remaining,
        stcg_app_income=cyla.stcg_app_remaining,
        stcg_dtaa_income=cyla.stcg_dtaa_remaining,
        ltcg125_income=cyla.ltcg125_remaining,
        ltcg_dtaa_income=cyla.ltcg_dtaa_remaining,
        bf_losses=bf_loss_items,
        current_ay="2026-27",
    )
    bfla = compute_bfla(bf_input)
    r.bfla_total_set_off = bfla.total_bf_loss_set_off
    r.bfla_remaining = bfla.total_bf_remaining
    r.schedules["bfla"] = bfla

    # ── 7. CFL: Carry-Forward Loss Summary ───────────────────────────────────
    cfl_entries: list[CFLResult] = []
    for entry in cyla.entries:
        if entry.remaining_loss <= 0:
            continue
        head = entry.head
        if head not in {"HP", "STCG", "LTCG"}:
            continue
        cfl_result = compute_cfl(
            cyla_remaining=entry.remaining_loss,
            head=head,
            sub_category=entry.sub_category,
            assessment_year="2026-27",
            original_loss=entry.loss_amount,
            years_carried=0,
            max_carry_forward_years=8,
        )
        if cfl_result.entries:
            cfl_entries.append(cfl_result)
    if bfla.total_bf_remaining > 0:
        for entry in bfla.entries:
            if entry.remaining_carry_forward > 0 and entry.sub_category != "EXPIRED":
                cfl_result = compute_cfl(
                    bfla_remaining=entry.remaining_carry_forward,
                    head=entry.head,
                    assessment_year=entry.assessment_year,
                    original_loss=entry.original_loss,
                    years_carried=0,
                    max_carry_forward_years=8,
                )
                if cfl_result.entries:
                    cfl_entries.append(cfl_result)
    r.schedules["cfl"] = cfl_entries

    # ── 8. GTI and post-loss capital-gain rate baskets ────────────────────────
    gti_after = max(_ZERO, gti_before - r.cyla_total_set_off - r.bfla_total_set_off)
    r.gti_after_loss_setoff = gti_after
    r.gross_total_income = gti_after
    non_cg_for_hp = max(_ZERO, r.salary_income) + max(_ZERO, r.other_sources_income)
    post_loss_cg = _post_loss_cg_baskets(
        stcg_result,
        ltcg_result,
        cyla,
        bfla,
        non_cg_for_hp,
        cg_result.exemptions,
    )
    r.schedules["post_loss_cg"] = post_loss_cg
    r.capital_gains_income = sum(post_loss_cg.values(), _ZERO) - post_loss_cg["112a_taxable"] + vda_income

    # ── 9. Agricultural Income ───────────────────────────────────────────────
    agri = input_data.agricultural_income
    if agri:
        ag_result = compute_agri(
            agri.gross_agricultural_income,
            agri.agricultural_deductions,
            agri.share_from_firm,
        )
        r.net_agricultural_income = ag_result.total_net_agricultural_income
        r.schedules["agri"] = ag_result

    # ── 10. Chapter VI-A Deductions ──────────────────────────────────────────
    # Use capital-gain amounts after CYLA/BFLA and Section 54-series claims.
    cg_112a_gross = post_loss_cg["112a_gross"]
    cg_112a_taxable = post_loss_cg["112a_taxable"]
    cg_111a_income = post_loss_cg["111a"]

    # Determine senior flags
    is_parents_senior = False
    is_80dd_severe = False
    is_80u_severe = False
    if ded_input := input_data.deductions_chapter6a:
        is_parents_senior = getattr(ded_input, "has_parents_senior", False)
        if schedule_80dd := getattr(ded_input, "schedule_80dd", None):
            is_80dd_severe = "severe" in str(getattr(schedule_80dd, "disability_type", "")).lower()
        if schedule_80u := getattr(ded_input, "schedule_80u", None):
            is_80u_severe = "severe" in str(getattr(schedule_80u, "disability_type", "")).lower()

    ded = compute_deductions(
        input_data.deductions_chapter6a,
        gti_after,
        age,
        regime,
        input_data.other_sources_income,
        cg_112a_income=cg_112a_taxable,
        cg_111a_income=cg_111a_income,
        is_parents_senior=is_parents_senior,
        is_80dd_severe=is_80dd_severe,
        is_80u_severe=is_80u_severe,
    )
    r.schedules["deductions"] = ded
    r.deductions_total = ded.total

    # ── 11. Taxable Income (u/s 288A) ────────────────────────────────────────
    income_before = max(_ZERO, gti_after - ded.total)
    ti = round_to_nearest_10(income_before)
    r.taxable_income = ti
    r.aggregate_income = ti + r.net_agricultural_income

    # ── 12. Special Rate Income Tax (Schedule SI) ────────────────────────────
    si_entries: list[SpecialRateEntry] = []

    # Section 112A: use the taxable amount from the CG engine (threshold applied once)
    si_112a_entry = compute_112a_taxable(cg_112a_taxable)
    si_entries.append(si_112a_entry)

    # Section 111A: listed equity STCG (at 20% for AY 2026-27)
    si_111a_entry = compute_111a(cg_111a_income)
    si_entries.append(si_111a_entry)

    # Section 112: other post-loss LTCG at 12.5%
    other_ltcg = post_loss_cg["112"]
    if other_ltcg > 0:
        si_112_entry = compute_112(other_ltcg)
        # Section 112(1)(a) second-proviso relief (land/building, residents,
        # pre-23-Jul-2024 acquisition) computed per-row in compute_ltcg().
        # Capped at this bucket's own actual tax so the relief can never
        # exceed what was actually charged here -- loss set-off/exemption
        # consumption upstream (post_loss_cg, exemptions) may already have
        # reduced this blended bucket below the raw land/building gain the
        # relief figure was computed from; capping avoids over-relieving in
        # that case rather than attempting an exact proportional allocation
        # across land/building vs. other section-112 income, which
        # post_loss_cg's blended-basket design does not track separately.
        relief = min(ltcg_result.total_excess_tax_112_1a, si_112_entry.tax_amount)
        if relief > _ZERO:
            si_112_entry.tax_amount -= relief
        si_entries.append(si_112_entry)

    # VDA at 30%
    if vda_income > 0:
        si_entries.append(si_vda(vda_income))

    # Additional SI entries from input
    for sie in input_data.si_entries:
        if sie.section == "115BB":
            si_entries.append(compute_lottery(sie.gross_income))
        elif sie.section == "115BBE":
            si_entries.append(compute_115bbe(sie.gross_income))
        elif sie.section == "115BBF":
            si_entries.append(compute_115bbf(sie.gross_income))
        elif sie.section == "115BBG":
            si_entries.append(compute_115bbg(sie.gross_income))
        elif sie.section == "115BBJ":
            from app.engine.schedules.special_rates import compute_115bbj
            si_entries.append(compute_115bbj(sie.gross_income))
        elif sie.section == "115BBA":
            from app.engine.schedules.special_rates import compute_115bba
            si_entries.append(compute_115bba(sie.gross_income))
        elif sie.section == "111":
            from app.engine.schedules.special_rates import compute_111
            si_entries.append(compute_111(sie.gross_income))

    # Schedule OS "any other income chargeable at special rate" dropdown --
    # the Section 115A/115AC/115ACA/115AD/115E/115BBF/115BBG family of
    # NRI/FII-specific special-rate categories. 115BBF/115BBG/115E already
    # have dedicated handlers (reused here for consistency with every other
    # caller of those functions); every other code dispatches through the
    # shared compute_other_special_rate_income() lookup table.
    from app.engine.schedules.special_rates import compute_other_special_rate_income
    for spr in input_data.os_special_rate_entries:
        if spr.source_description == "5BBF":
            si_entries.append(compute_115bbf(spr.source_amount))
        elif spr.source_description == "5BBG":
            si_entries.append(compute_115bbg(spr.source_amount))
        elif spr.source_description == "5Ea":
            from app.engine.schedules.special_rates import compute_115e_a
            si_entries.append(compute_115e_a(spr.source_amount))
        elif spr.source_description == "5BBA":
            from app.engine.schedules.special_rates import compute_115bba
            si_entries.append(compute_115bba(spr.source_amount))
        else:
            si_entries.append(compute_other_special_rate_income(spr.source_description, spr.source_amount))

    # DTAA-rate Other Sources income (Schedule OS's NRIDTAADtlsSchOS detail
    # rows, disclosure-only until now) → taxed via Schedule SI's dedicated
    # "DTAAOS" code at each entry's own treaty-vs-Act beneficial rate
    # (`applicable_rate`, per section 90(2)) -- unlike every other special
    # rate in this module, this one is not a fixed statutory percentage but
    # varies per DTAA article/country, hence the per-entry rate argument.
    from app.engine.schedules.special_rates import compute_dtaa_os
    for dtaa in input_data.os_dtaa_entries:
        si_entries.append(compute_dtaa_os(dtaa.amount, dtaa.applicable_rate))

    # Pass-through income (Schedule PTI) → SI entries
    from app.engine.schedules.special_rates import (
        compute_115bbj as _compute_115bbj,
        compute_115bba as _compute_115bba,
        compute_111 as _compute_111,
        compute_pti_stcg20 as _compute_pti_stcg20,
        compute_pti_stcg30 as _compute_pti_stcg30,
        compute_pti_ltcg112a as _compute_pti_ltcg112a,
        compute_pti_ltcg125 as _compute_pti_ltcg125,
    )
    for pti in input_data.pti_entries:
        if pti.income_amount > 0:
            if pti.income_head == "STCG" and pti.section == "111A":
                si_entries.append(_compute_pti_stcg20(pti.income_amount))
            elif pti.income_head == "STCG":
                si_entries.append(_compute_pti_stcg30(pti.income_amount))
            elif pti.income_head == "LTCG" and "112A" in pti.section.upper():
                si_entries.append(_compute_pti_ltcg112a(pti.income_amount))
            elif pti.income_head == "LTCG":
                si_entries.append(_compute_pti_ltcg125(pti.income_amount))

    si_result: SpecialRatesResult = aggregate_si(si_entries)
    r.special_rate_tax = si_result.total_special_rate_tax
    r.schedules["si"] = si_result

    # ── 13. Normal Slab Tax ──────────────────────────────────────────────────
    # Full post-loss 111A/112/112A/VDA income is excluded from slab tax.
    # For 112A, the ₹1.25 lakh threshold is tax-free but remains special-rate
    # income and must not leak into the normal slab basket.
    special_rate_income_for_slab = (
        post_loss_cg["111a"]
        + post_loss_cg["112"]
        + post_loss_cg["112a_gross"]
        + si_result.surcharge_full_income
    )
    normal_income = max(_ZERO, ti - special_rate_income_for_slab)
    slab_tax = compute_slab_tax(normal_income, age, regime)

    # Partial integration of agricultural income (old regime only)
    r.partial_integration_tax = _ZERO
    if regime == TaxRegime.OLD and r.net_agricultural_income > Decimal("5000"):
        basic_exemption = _get_basic_exemption(age)
        pit = compute_partial_integration_tax(
            normal_income,
            r.net_agricultural_income,
            basic_exemption,
            compute_slab_tax,
            age,
            regime,
        )
        r.partial_integration_tax = pit
        slab_tax += pit

    r.slab_tax = slab_tax

    # ── 14. AMT ──────────────────────────────────────────────────────────────
    # Build AMT additions from typed inputs
    amt_additions: list[AMTAddition] = []
    amt_in = input_data.amt_input
    if amt_in:
        if amt_in.deduction_10aa > 0:
            amt_additions.append(AMTAddition(AMTAdditionSection.SECTION_10AA, amt_in.deduction_10aa))
        if amt_in.deduction_80ia_to_80rrb_except_80p > 0:
            # 80-IA is the primary trigger
            amt_additions.append(AMTAddition(AMTAdditionSection.SECTION_80IA, amt_in.deduction_80ia_to_80rrb_except_80p))
        if amt_in.deduction_35ad_net_depreciation > 0:
            amt_additions.append(AMTAddition(AMTAdditionSection.SECTION_35AD, amt_in.deduction_35ad_net_depreciation))

    # Also derive from Chapter VI-A deductions if present
    if ded_input := input_data.deductions_chapter6a:
        for field_name, section in [
            ("amount_80ia", AMTAdditionSection.SECTION_80IA),
            ("amount_80ib", AMTAdditionSection.SECTION_80IB),
            ("amount_80ic", AMTAdditionSection.SECTION_80IC),
            ("amount_10aa", AMTAdditionSection.SECTION_10AA),
        ]:
            val = getattr(ded_input, field_name, None) or _ZERO
            if val > 0:
                amt_additions.append(AMTAddition(section, val))

    # AMT comparison uses tax before cess
    tax_before_cess = slab_tax + r.special_rate_tax
    amt_result = compute_amt(
        ti,
        tax_before_cess,
        amt_additions or None,
        regime,
        age,
        regular_tax_includes_cess=False,
    )
    r.amt_tax = _ZERO
    if amt_result.amt_applicable:
        r.amt_tax = amt_result.amt_tax - tax_before_cess
        r.schedules["amt"] = amt_result

    # ── 15. Total tax before relief/rebate ───────────────────────────────────
    r.total_tax_before_relief = slab_tax + r.special_rate_tax + r.amt_tax
    r.tax_before_rebate = r.total_tax_before_relief

    # ── 16. Rebate u/s 87A ───────────────────────────────────────────────────
    rebate = compute_rebate(
        ti,
        r.tax_before_rebate,
        slab_tax,
        regime,
        is_resident_individual=is_resident and is_individual,
    )
    r.rebate_87a = rebate
    r.tax_after_rebate = max(_ZERO, r.tax_before_rebate - rebate)

    # ── 17. Surcharge ───────────────────────────────────────────────────────
    surcharge = compute_surcharge(
        ti,
        r.tax_after_rebate,
        regime,
        age,
        sr_tax=si_result.surcharge_cap_tax,
        sr_surcharge_full_tax=si_result.surcharge_full_tax,
        sr_income=si_result.surcharge_cap_income,
        sr_surcharge_full_income=si_result.surcharge_full_income,
    )
    r.surcharge = surcharge

    # ── 18. Cess ─────────────────────────────────────────────────────────────
    cess = compute_cess(r.tax_after_rebate + surcharge)
    r.health_education_cess = cess
    r.gross_tax_liability = r.tax_after_rebate + surcharge + cess

    # Apply AMT final tax if applicable (AMT includes its own surcharge + cess)
    if amt_result.amt_applicable:
        r.gross_tax_liability = amt_result.final_tax

    # ── 19. Foreign Tax Relief ───────────────────────────────────────────────
    r.relief_90_91 = _ZERO
    for tr1 in input_data.tr1_entries:
        r.relief_90_91 += tr1.relief_claimed
    r.relief_90_91 = min(r.relief_90_91, r.gross_tax_liability)
    r.relief_89 = input_data.relief_89

    # ── 20. Tax Credits ──────────────────────────────────────────────────────
    # Filing tax credits use the amount claimed in this return, not merely the
    # amount appearing as deducted/collected in an information statement.
    r.total_tds = sum((entry.tds_deducted for entry in input_data.tds1_entries), _ZERO)
    r.total_tds += sum((entry.tds_claimed_this_year for entry in input_data.tds2_entries), _ZERO)
    # TDS3Entry's field is `tds_claimed`, not `tds_claimed_this_year` (that
    # name belongs to TDS2Entry) -- the old line here referenced a
    # nonexistent attribute, an AttributeError that crashed compute()
    # outright on any return with real tds3_entries data, before ever
    # reaching the JSON builder. No prior test exercised this path.
    r.total_tds += sum((entry.tds_claimed for entry in input_data.tds3_entries), _ZERO)
    r.total_tcs = sum((entry.tcs_credit_claimed for entry in input_data.tcs_entries), _ZERO)

    detailed_advance = sum(
        (entry.amount for entry in input_data.tax_payment_entries if entry.payment_type == "advance"),
        _ZERO,
    )
    detailed_self_assessment = sum(
        (entry.amount for entry in input_data.tax_payment_entries if entry.payment_type == "self_assessment"),
        _ZERO,
    )
    r.total_advance_tax = detailed_advance or input_data.advance_tax_paid
    r.total_self_assessment_tax = detailed_self_assessment or input_data.self_assessment_tax_paid
    r.total_taxes_paid = r.total_tds + r.total_tcs + r.total_advance_tax + r.total_self_assessment_tax

    # ── 21. Interest and Late Fee ─────────────────────────────────────────────
    filing_date = input_data.filing_date
    due_date = input_data.due_date or (get_due_date("ITR-2") if filing_date else None)

    if filing_date and due_date:
        assessed_tax = max(
            _ZERO,
            r.gross_tax_liability - r.relief_90_91 - r.relief_89 - r.total_tds - r.total_tcs,
        )
        ay_start = date(due_date.year, 4, 1)
        r.interest_234a = compute_234a(assessed_tax, filing_date, due_date)
        r.interest_234b = compute_234b(
            assessed_tax,
            input_data.advance_tax_paid or _ZERO,
            filing_date,
            ay_start,
        )
        quarterly = (
            [
                input_data.advance_tax_q1 or _ZERO,
                input_data.advance_tax_q2 or _ZERO,
                input_data.advance_tax_q3 or _ZERO,
                input_data.advance_tax_q4 or _ZERO,
            ]
            if any(v is not None for v in (
                input_data.advance_tax_q1,
                input_data.advance_tax_q2,
                input_data.advance_tax_q3,
                input_data.advance_tax_q4,
            ))
            else [input_data.advance_tax_paid or _ZERO]
        )
        r.interest_234c = compute_234c(quarterly, assessed_tax, ay_start)
        r.late_fee_234f = compute_234f(filing_date, due_date, ti)
        r.fees_234i = compute_234i(filing_date, due_date, ti,
                                   filing_section=input_data.filing_section)

    r.total_interest = r.interest_234a + r.interest_234b + r.interest_234c

    # ── 22. Final Payable/Refund ─────────────────────────────────────────────
    net_liability = (
        r.gross_tax_liability
        - r.relief_89
        - r.relief_90_91
        + r.total_interest
        + r.late_fee_234f
        + r.fees_234i
    )
    r.net_tax_liability = max(_ZERO, net_liability)

    diff = r.net_tax_liability - r.total_taxes_paid
    if diff > 0:
        r.balance_payable = round_to_nearest_10(diff)
        r.refund_due = _ZERO
    else:
        r.balance_payable = _ZERO
        r.refund_due = round_to_nearest_10(abs(diff))

    return r
