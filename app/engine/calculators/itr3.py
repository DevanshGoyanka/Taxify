"""
ITR-3 Calculator.

Composes schedule modules for ITR-3 (business/profession + all ITR-2 heads).

Unlike ITR-2, ITR-3 adds:
  - Business/Profession Income (PGBP)
  - Depreciation computation (WDV block method)
  - ICDS adjustments
  - Firm/LLP/AOP income (Schedule IF)
  - Business-specific deductions (80-IA, 80-IB, 10AA, etc.)
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from datetime import date

from app.schemas.itr1 import AgeBracket, TaxRegime
from app.schemas.itr3 import ITR3Input
from app.engine.common.rounding import vba_round, round_to_nearest_10
from app.engine.common.slab_tax import compute as compute_slab_tax
from app.engine.common.rebate import compute as compute_rebate
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.common.cess import compute as compute_cess
from app.engine.common.interest import compute_234a, compute_234b, compute_234c, compute_234f
from app.engine.schedules.salary import compute as compute_salary
from app.engine.schedules.house_property import compute as compute_hp
from app.engine.schedules.other_sources import compute as compute_os
from app.engine.schedules.capital_gains import (
    compute_stcg, compute_ltcg, compute_vda, compute_112a,
    compute_exemptions, aggregate as aggregate_cg,
    STCGResult, LTCGResult, ExemptionResult, CG112AAsset, VDAEntry, CGAsset,
)
from app.engine.schedules.special_rates import (
    compute_112a as si_112a, compute_111a as si_111a,
    compute_lottery, compute_vda as si_vda, compute_115bbe, compute_115bbf,
    aggregate as aggregate_si,
)
from app.engine.schedules.agricultural import (
    compute as compute_agri, compute_partial_integration_tax,
)
from app.engine.schedules.deductions import compute_all as compute_deductions
from app.engine.schedules.loss_setoff.cyla import (
    compute as compute_cyla, CYLAInput,
)
from app.engine.schedules.loss_setoff.bfla import (
    compute as compute_bfla, BFLAInput,
)
from app.engine.schedules.amt import compute as compute_amt
from app.engine.constants import (
    LTCG_112A_RATE_POST_JUL23,
    STCG_111A_RATE_POST_JUL23,
)


@dataclass
class DepreciationResult:
    total_depreciation: Decimal = Decimal("0")
    disallowance: Decimal = Decimal("0")
    net_depreciation: Decimal = Decimal("0")
    wdv_summary: dict = field(default_factory=dict)
    deemed_cg_us50: Decimal = Decimal("0")


def _compute_block(wdv_opening: Decimal, additions: Decimal, additions_half: Decimal,
                   realizations: Decimal, rate: Decimal) -> dict:
    """Compute WDV-based depreciation for one block."""
    wdv_before_dep = wdv_opening + additions + additions_half - realizations
    if wdv_before_dep <= 0:
        return {"wdv_closing": Decimal("0"), "depreciation_full": Decimal("0"),
                "depreciation_half": Decimal("0"), "total_depreciation": Decimal("0"),
                "deemed_cg": abs(wdv_before_dep)}

    dep_full = (wdv_opening + additions - realizations) * rate
    if dep_full < 0:
        dep_full = Decimal("0")
    dep_half = additions_half * rate / Decimal("2")
    total_dep = dep_full + dep_half
    wdv_closing = wdv_before_dep - total_dep
    if wdv_closing < 0:
        wdv_closing = Decimal("0")

    return {
        "wdv_closing": wdv_closing,
        "depreciation_full": dep_full,
        "depreciation_half": dep_half,
        "total_depreciation": total_dep,
        "deemed_cg": Decimal("0"),
    }


def compute_depreciation(dep_input) -> DepreciationResult:
    """Compute depreciation across all WDV blocks."""
    if not dep_input:
        return DepreciationResult()

    total_dep = Decimal("0")
    total_cg = Decimal("0")
    summary = {}

    blocks = {
        "15%": (dep_input.block_15, Decimal("0.15")),
        "30%": (dep_input.block_30, Decimal("0.30")),
        "40%": (dep_input.block_40, Decimal("0.40")),
        "45%": (dep_input.block_45, Decimal("0.45")),
        "Building_Res5%": (dep_input.building_residential_5, Decimal("0.05")),
        "Building_Other10%": (dep_input.building_other_10, Decimal("0.10")),
        "Furniture10%": (dep_input.furniture_10, Decimal("0.10")),
        "Intangible25%": (dep_input.intangible_25, Decimal("0.25")),
    }

    for name, (block, rate) in blocks.items():
        if block is None:
            continue
        res = _compute_block(
            block.wdv_opening, block.additions, block.additions_half_rate,
            block.realizations, rate,
        )
        summary[name] = res
        total_dep += res["total_depreciation"]
        total_cg += res["deemed_cg"]

    return DepreciationResult(
        total_depreciation=total_dep,
        net_depreciation=total_dep,
        wdv_summary=summary,
        deemed_cg_us50=total_cg,
    )


def compute_business_income(pl, disallowances, deemed_incomes, depreciation, icds,
                             firm_incomes) -> dict:
    """
    Compute PGBP income:
      PL profit + disallowances - depreciation + deemed incomes
      + ICDS effect + firm share income
    """
    pl_profit = Decimal("0")
    if pl:
        pl_profit = pl.net_profit_as_per_pl

    total_disallowances = Decimal("0")
    if disallowances:
        for fname in [
            "us36_expenditure_on_family", "us36_interest_on_capital",
            "us36_salary_to_partners", "us36_bonus_commission_to_partners",
            "us36_employer_pf_esic_unpaid", "us40a_excessive_payments_to_related",
            "us40a2b_cash_payments", "us40ai_non_tds_payments",
            "us43b_taxes_duties_contributions_unpaid",
            "us43b_employer_contributions_unpaid",
            "depreciation_disallowance_us38_2", "personal_expenses",
            "other_disallowances",
        ]:
            total_disallowances += getattr(disallowances, fname, Decimal("0"))

    total_deemed = Decimal("0")
    if deemed_incomes:
        total_deemed = (deemed_incomes.us41_recovery_of_deduction
                        + deemed_incomes.us33ab_recovery
                        + deemed_incomes.us35abb_recovery
                        + deemed_incomes.us50_capital_gains
                        + deemed_incomes.other_deemed_income)

    dep = compute_depreciation(depreciation) if depreciation else DepreciationResult()
    icds_effect = icds.net_icds_effect if icds else Decimal("0")

    business_income = pl_profit + total_disallowances - dep.net_depreciation + total_deemed + icds_effect

    firm_income = Decimal("0")
    firm_details = []
    for fi in (firm_incomes or []):
        share = fi.share_of_profit + fi.interest_on_capital + fi.salary_bonus_from_firm
        firm_income += share
        firm_details.append({"firm": fi.firm_name, "share": share})

    total_business_income = business_income + firm_income

    return {
        "pl_profit": pl_profit,
        "total_disallowances": total_disallowances,
        "depreciation": dep.total_depreciation,
        "disallowance_us38_2": dep.disallowance,
        "net_depreciation": dep.net_depreciation,
        "deemed_cg_us50": dep.deemed_cg_us50,
        "total_deemed_incomes": total_deemed,
        "icds_effect": icds_effect,
        "firm_income": firm_income,
        "firm_details": firm_details,
        "business_income": total_business_income,
    }


@dataclass
class ITR3Result:
    business_income: Decimal = Decimal("0")
    salary_income: Decimal = Decimal("0")
    house_property_income: Decimal = Decimal("0")
    capital_gains_income: Decimal = Decimal("0")
    other_sources_income: Decimal = Decimal("0")
    vda_income: Decimal = Decimal("0")
    clubbing_income: Decimal = Decimal("0")

    net_agricultural_income: Decimal = Decimal("0")
    partial_integration_tax: Decimal = Decimal("0")
    cyla_total_set_off: Decimal = Decimal("0")
    bfla_total_set_off: Decimal = Decimal("0")

    gross_total_income: Decimal = Decimal("0")
    deductions_total: Decimal = Decimal("0")
    taxable_income: Decimal = Decimal("0")

    slab_tax: Decimal = Decimal("0")
    special_rate_tax: Decimal = Decimal("0")
    amt_tax: Decimal = Decimal("0")
    tax_before_rebate: Decimal = Decimal("0")
    rebate_87a: Decimal = Decimal("0")
    tax_after_rebate: Decimal = Decimal("0")
    surcharge: Decimal = Decimal("0")
    health_education_cess: Decimal = Decimal("0")
    gross_tax_liability: Decimal = Decimal("0")

    relief_90_91: Decimal = Decimal("0")
    interest_234a: Decimal = Decimal("0")
    interest_234b: Decimal = Decimal("0")
    interest_234c: Decimal = Decimal("0")
    late_fee_234f: Decimal = Decimal("0")
    total_interest: Decimal = Decimal("0")

    net_tax_liability: Decimal = Decimal("0")
    total_tds: Decimal = Decimal("0")
    total_tcs: Decimal = Decimal("0")
    total_taxes_paid: Decimal = Decimal("0")
    balance_payable: Decimal = Decimal("0")
    refund_due: Decimal = Decimal("0")

    schedules: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


def _get_basic_exemption(age_bracket: AgeBracket) -> Decimal:
    if age_bracket == AgeBracket.ABOVE_80:
        return Decimal("500000")
    elif age_bracket == AgeBracket.SIXTY_TO_80:
        return Decimal("300000")
    return Decimal("250000")


def compute(input_data: ITR3Input) -> ITR3Result:
    r = ITR3Result()
    regime = input_data.tax_regime
    age = input_data.age_bracket

    # ── 1. Business Income ───────────────────────────────────────────────────
    biz = compute_business_income(
        input_data.pl_adjustment, input_data.pl_disallowances,
        input_data.deemed_incomes, input_data.depreciation,
        input_data.icds_adjustment, input_data.firm_incomes,
    )
    r.business_income = biz["business_income"]
    r.schedules["business"] = biz

    # ── 2. Salary, HP, OS ────────────────────────────────────────────────────
    sal = compute_salary(input_data.salary_income, regime)
    hp = compute_hp(input_data.house_property_income, regime)
    os = compute_os(input_data.other_sources_income, regime)
    r.salary_income = sal.income_chargeable
    r.house_property_income = hp.income_chargeable
    r.other_sources_income = os.income_chargeable
    r.schedules["salary"] = sal
    r.schedules["hp"] = hp
    r.schedules["os"] = os

    # ── 3. Capital Gains ────────────────────────────────────────────────────
    stcg_111a_val = Decimal("0")
    stcg_land_cg = []
    stcg_other = Decimal("0")
    ltcg_112a_assets = []
    ltcg_land_cg = []
    ltcg_other_cg = Decimal("0")
    ltcg_dtaa = Decimal("0")
    vda_entries_list = []
    exempt_54 = Decimal("0")
    exempt_54b = Decimal("0")
    exempt_54ec = Decimal("0")
    exempt_54f = Decimal("0")

    for tx in (input_data.cg_transactions or []):
        if tx.asset_type.value in ("listed_equity_111a",):
            is_short = True
            if tx.date_of_acquisition and tx.date_of_transfer:
                holding_days = (tx.date_of_transfer - tx.date_of_acquisition).days
                is_short = holding_days <= 365

            if is_short:
                stcg_111a_val += (tx.full_consideration - tx.cost_of_acquisition
                                  - tx.expenditure_on_transfer)
            else:
                ltcg_112a_assets.append(CG112AAsset(
                    total_sale_value=tx.full_consideration,
                    cost_acq_without_index=tx.cost_of_acquisition,
                    total_fmv=tx.fair_market_value_jan2018 or tx.cost_of_acquisition,
                    total_deductions=tx.expenditure_on_transfer,
                ))
        elif tx.asset_type.value == "land_building":
            asset = CGAsset(
                full_consideration=tx.full_consideration,
                acquisition_cost=tx.cost_of_acquisition,
                indexed_acquisition_cost=tx.indexed_cost,
                improvement_cost=tx.improvement_cost,
                indexed_improvement_cost=tx.indexed_improvement,
                expenditure_on_transfer=tx.expenditure_on_transfer,
            )
            is_short = True
            if tx.date_of_acquisition and tx.date_of_transfer:
                holding_days = (tx.date_of_transfer - tx.date_of_acquisition).days
                is_short = holding_days <= 730

            if is_short:
                stcg_land_cg.append(asset)
            else:
                ltcg_land_cg.append(asset)
                exempt_54 += tx.deduction_us54
                exempt_54b += tx.deduction_us54b
                exempt_54ec += tx.deduction_us54ec
                exempt_54f += tx.deduction_us54f
        else:
            stcg_other += (tx.full_consideration - tx.cost_of_acquisition
                           - tx.expenditure_on_transfer)

    for scrip in (input_data.cg_112a_scrips or []):
        ltcg_112a_assets.append(CG112AAsset(
            isin_code=scrip.isin_code or "",
            total_sale_value=scrip.total_sale_value,
            cost_acq_without_index=scrip.cost_acq_without_index,
            total_fmv=scrip.total_fmv,
            total_deductions=scrip.total_deductions,
        ))

    for vda in (input_data.vda_transactions or []):
        vda_entries_list.append(VDAEntry(
            date_of_acquisition=str(vda.date_of_acquisition),
            date_of_transfer=str(vda.date_of_transfer),
            acquisition_cost=vda.acquisition_cost,
            consideration_received=vda.consideration_received,
        ))

    stcg_r = compute_stcg(stcg_111a=stcg_111a_val, stcg_land_building=stcg_land_cg,
                          stcg_other=stcg_other)
    ltcg_r = compute_ltcg(ltcg_112a_assets=ltcg_112a_assets, ltcg_land_building=ltcg_land_cg,
                          ltcg_other=ltcg_other_cg, ltcg_dtaa=ltcg_dtaa)
    vda_inc = compute_vda(vda_entries=vda_entries_list)
    exemptions = compute_exemptions(exempt_54, exempt_54b, exempt_54ec, exempt_54f)
    cg_result = aggregate_cg(stcg_r, ltcg_r, vda_inc, exemptions)
    r.capital_gains_income = cg_result.total_capital_gains
    r.vda_income = vda_inc
    r.schedules["cg"] = cg_result

    # ── 4. Clubbing ──────────────────────────────────────────────────────────
    clubbing = Decimal("0")
    for spi in (input_data.spi_entries or []):
        clubbing += spi.amount_included
    r.clubbing_income = clubbing
    r.other_sources_income += clubbing

    # ── 5. GTI before loss set-off ───────────────────────────────────────────
    gti_before = (r.business_income + r.salary_income + r.house_property_income
                   + r.capital_gains_income + r.other_sources_income)

    # ── 5a. CYLA: Current Year Loss Set-off ─────────────────────────────────
    cy_input = CYLAInput(
        hp_loss=hp.income_chargeable if hp.income_chargeable < 0 else Decimal("0"),
        hp_income=hp.income_chargeable if hp.income_chargeable > 0 else Decimal("0"),
        stcg_loss=cg_result.stcg.total_stcg if cg_result.stcg.total_stcg < 0 else Decimal("0"),
        stcg_income=cg_result.stcg.total_stcg if cg_result.stcg.total_stcg > 0 else Decimal("0"),
        ltcg_loss=cg_result.ltcg.income_125per_other + cg_result.ltcg.income_dtaa,
        ltcg_income=max(Decimal("0"), cg_result.ltcg.income_125per_other + cg_result.ltcg.income_dtaa),
        non_spec_biz_loss=biz["business_income"] if biz["business_income"] < 0 else Decimal("0"),
        non_spec_biz_income=biz["business_income"] if biz["business_income"] > 0 else Decimal("0"),
        spec_biz_loss=Decimal("0"),
        spec_biz_income=Decimal("0"),
    )
    cyla = compute_cyla(cy_input)
    r.cyla_total_set_off = cyla.total_loss_set_off
    r.schedules["cyla"] = cyla

    # ── 5b. BFLA: Brought Forward Loss Set-off ──────────────────────────────
    bf_list = [
        {
            "assessment_year": str(item.assessment_year),
            "head": str(item.head),
            "sub_category": str(item.sub_category),
            "original_loss": Decimal(str(item.original_loss)),
            "brought_forward": Decimal(str(item.brought_forward)),
        }
        for item in (input_data.bf_losses or [])
    ]
    bf_input = BFLAInput(
        hp_income=hp.income_chargeable if hp.income_chargeable > 0 else Decimal("0"),
        non_spec_biz_income=biz["business_income"] if biz["business_income"] > 0 else Decimal("0"),
        spec_biz_income=Decimal("0"),
        stcg_income=cg_result.stcg.total_stcg if cg_result.stcg.total_stcg > 0 else Decimal("0"),
        ltcg_income=cg_result.ltcg.total_ltcg if cg_result.ltcg.total_ltcg > 0 else Decimal("0"),
        bf_losses=bf_list,
    )
    bfla = compute_bfla(bf_input)
    r.bfla_total_set_off = bfla.total_bf_loss_set_off
    r.schedules["bfla"] = bfla

    gti_after = gti_before - r.cyla_total_set_off - r.bfla_total_set_off
    r.gross_total_income = gti_after

    # ── 5c. Agricultural Income ─────────────────────────────────────────────
    agri = input_data.agricultural_income
    if agri:
        ag = compute_agri(agri.gross_agricultural_income, agri.agricultural_deductions,
                          agri.share_from_firm)
        r.net_agricultural_income = ag.total_net_agricultural_income
        r.schedules["agri"] = ag

    # ── 6. Business-specific Deductions (80-IA, 80-IB, 10AA, 80RA) ─────────
    biz_80ia = Decimal("0")
    biz_80ib = Decimal("0")
    biz_10aa = Decimal("0")
    biz_80ra = Decimal("0")

    if regime == TaxRegime.OLD:
        ded_input = input_data.deductions_chapter6a
        if ded_input:
            biz_80ia = getattr(ded_input, 'amount_80ia', Decimal("0")) or Decimal("0")
            biz_80ib = getattr(ded_input, 'amount_80ib', Decimal("0")) or Decimal("0")
            biz_10aa = getattr(ded_input, 'amount_10aa', Decimal("0")) or Decimal("0")
            biz_80ra = getattr(ded_input, 'amount_80ra', Decimal("0")) or Decimal("0")

    # ── 7. Chapter VI-A Deductions ───────────────────────────────────────────
    ded = compute_deductions(input_data.deductions_chapter6a, gti_after, age, regime,
                              input_data.other_sources_income,
                              cg_112a_income=cg_result.ltcg.taxable_112a,
                              cg_111a_income=stcg_r.income_111a,
                              business_80ia=biz_80ia,
                              business_80ib=biz_80ib,
                              business_10aa=biz_10aa,
                              business_80ra=biz_80ra)
    r.schedules["deductions"] = ded
    r.deductions_total = ded.total

    # ── 8. Taxable Income ────────────────────────────────────────────────��───
    ti = round_to_nearest_10(max(Decimal("0"), gti_after - ded.total))
    r.taxable_income = ti

    # ── 9. Special Rate Tax ──────────────────────────────────────────────────
    si_entries = [si_112a(cg_result.ltcg.income_112a)]
    si_entries.append(si_111a(stcg_r.income_111a))
    if vda_inc > 0:
        si_entries.append(si_vda(vda_inc))
    for sie in (input_data.si_entries or []):
        if sie.section == "115BB":
            si_entries.append(compute_lottery(sie.gross_income))
        elif sie.section == "115BBE":
            si_entries.append(compute_115bbe(sie.gross_income))
        elif sie.section == "115BBF":
            si_entries.append(compute_115bbf(sie.gross_income))
    si_r = aggregate_si(si_entries)
    r.special_rate_tax = si_r.total_special_rate_tax
    r.schedules["si"] = si_r

    # ── 10. Slab Tax ─────────────────────────────────────────────────────────
    normal_inc = max(Decimal("0"), ti - si_r.total_special_rate_income)
    slab = compute_slab_tax(normal_inc, age, regime)

    # Partial integration of agricultural income (old regime only)
    r.partial_integration_tax = Decimal("0")
    if regime == TaxRegime.OLD and r.net_agricultural_income > Decimal("5000"):
        basic_exemption = _get_basic_exemption(age)
        pit = compute_partial_integration_tax(
            normal_inc, r.net_agricultural_income, basic_exemption,
            compute_slab_tax, age, regime,
        )
        r.partial_integration_tax = pit
        slab += pit

    r.slab_tax = slab
    r.tax_before_rebate = r.slab_tax + r.special_rate_tax

    # ── 11. Rebate ──────────────────────────────────────────────────────────
    reb = compute_rebate(ti, r.tax_before_rebate, regime)
    r.rebate_87a = reb
    r.tax_after_rebate = max(Decimal("0"), r.tax_before_rebate - reb)

    # ── 12. Surcharge ────────────────────────────────────────────────────────
    sur = compute_surcharge(ti, r.tax_after_rebate, regime, age)
    r.surcharge = sur

    # ── 13. Cess ─────────────────────────────────────────────────────────────
    cess = compute_cess(r.tax_after_rebate + sur)
    r.health_education_cess = cess
    r.gross_tax_liability = r.tax_after_rebate + sur + cess

    # ── 13a. AMT (u/s 115JC): compare regular vs 18.5% of ATI ───────────────
    amt_triggers = {}
    if ded_input := input_data.deductions_chapter6a:
        for key, label in [("amount_80ia", "80-IA"), ("amount_80ib", "80-IB"),
                           ("amount_10aa", "10AA")]:
            val = getattr(ded_input, key, None) or Decimal("0")
            if val > 0:
                amt_triggers[label] = val
    amt_result = compute_amt(ti, r.gross_tax_liability, amt_triggers, regime, age)
    if amt_result.amt_applicable:
        r.amt_tax = amt_result.amt_tax - r.gross_tax_liability
        r.gross_tax_liability = amt_result.final_tax
        r.schedules["amt"] = amt_result

    # ── 14. Foreign Tax Relief ───────────────────────────────────────────────
    for tr1 in (input_data.tr1_entries or []):
        r.relief_90_91 += tr1.relief_claimed
    r.relief_90_91 = min(r.relief_90_91, r.gross_tax_liability)

    # ── 15. Interest ─────────────────────────────────────────────────────────
    filing_date = input_data.filing_date
    due_date = input_data.due_date
    if filing_date and due_date:
        tax_after_relief = r.gross_tax_liability - r.relief_90_91
        r.interest_234a = compute_234a(tax_after_relief, filing_date, due_date)
        r.late_fee_234f = compute_234f(filing_date, due_date, ti)
    r.total_interest = r.interest_234a + r.interest_234b + r.interest_234c

    # ── 16. Tax Credits ──────────────────────────────────────────────────────
    total_tds = sum((e.tds_deducted for e in (input_data.tds1_entries or [])), Decimal("0"))
    total_tds += sum((e.tds_deducted for e in (input_data.tds2_entries or [])), Decimal("0"))
    r.total_tds = total_tds

    total_tcs = sum((e.tcs_collected for e in (input_data.tcs_entries or [])), Decimal("0"))
    r.total_tcs = total_tcs
    r.total_taxes_paid = (r.total_tds + r.total_tcs + input_data.advance_tax_paid
                           + input_data.self_assessment_tax_paid)

    # ── 17. Final ────────────────────────────────────────────────────────────
    net_liability = (r.gross_tax_liability - r.relief_90_91 + r.total_interest
                      + r.late_fee_234f)
    r.net_tax_liability = round_to_nearest_10(net_liability)

    diff = r.net_tax_liability - r.total_taxes_paid
    if diff > 0:
        r.balance_payable = diff
    else:
        r.refund_due = abs(diff)

    return r
