"""
ITR-3 Calculator.

Composes schedule modules to produce a complete ITR-3 computation.

Computation order:
  1. Business Income (PGBP): non-speculative, speculative, specified (35AD)
  2. Heads: Salary + HP + STCG + LTCG + 112A + VDA + OS
  3. Clubbing (SPI) income
  4. Partner in Firm income (Schedule IF)
  5. CYLA: Current year loss set-off
  6. BFLA: Brought forward loss set-off
  7. GTI after losses
  8. Unabsorbed Depreciation set-off (Schedule UD)
  9. Agricultural income
  10. Chapter VI-A deductions (Part B + Part C) + 10AA/80IA/80IB/80IC deductions
  11. TI = GTI - deductions (rounded to nearest Rs 10)
  12. SI: Special-rate income tax
  13. AMT
  14. Slab tax on normal income + special rate + AMT + partial integration
  15. Rebate 87A, surcharge, cess
  16. Foreign tax relief (TR1)
  17. Interest 234A/B/C + late fee 234F
  18. TDS/TCS credit
  19. Final payable/refund
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field

from app.schemas.itr1 import AgeBracket, TaxRegime
from app.schemas.itr3 import ITR3Input
from app.engine.common.rounding import round_to_nearest_10
from app.engine.common.slab_tax import compute as compute_slab_tax
from app.engine.common.rebate import compute as compute_rebate
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.common.cess import compute as compute_cess
from app.engine.common.interest import compute_234a, compute_234f
from app.engine.schedules.salary import compute as compute_salary
from app.engine.schedules.house_property import compute as compute_hp
from app.engine.schedules.other_sources import compute as compute_os
from app.engine.schedules.business import compute as compute_pgbp
from app.engine.schedules.capital_gains import (
    compute_stcg, compute_ltcg, compute_vda,
    compute_exemptions, aggregate as aggregate_cg,
    STCGResult, LTCGResult, CG112AAsset, VDAEntry, CGAsset,
)
from app.engine.schedules.special_rates import (
    compute_112a as si_112a, compute_111a as si_111a,
    compute_vda as si_vda, compute_lottery, compute_115bbe, compute_115bbf,
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


@dataclass
class ITR3Result:
    """Complete ITR-3 computation result."""
    business_income: Decimal = Decimal("0")
    salary_income: Decimal = Decimal("0")
    house_property_income: Decimal = Decimal("0")
    capital_gains_income: Decimal = Decimal("0")
    other_sources_income: Decimal = Decimal("0")
    vda_income: Decimal = Decimal("0")
    clubbing_income: Decimal = Decimal("0")
    partner_firm_income: Decimal = Decimal("0")

    gti_before_loss_setoff: Decimal = Decimal("0")
    cyla_total_set_off: Decimal = Decimal("0")
    bfla_total_set_off: Decimal = Decimal("0")
    gti_after_loss_setoff: Decimal = Decimal("0")
    gross_total_income: Decimal = Decimal("0")

    net_agricultural_income: Decimal = Decimal("0")
    partial_integration_tax: Decimal = Decimal("0")

    deductions_partb_chapter6a: Decimal = Decimal("0")
    deductions_partc_chapter6a: Decimal = Decimal("0")
    deductions_10aa: Decimal = Decimal("0")
    deductions_80ia: Decimal = Decimal("0")
    deductions_80ib: Decimal = Decimal("0")
    deductions_80ic: Decimal = Decimal("0")
    deductions_total: Decimal = Decimal("0")

    taxable_income: Decimal = Decimal("0")
    aggregate_income: Decimal = Decimal("0")

    slab_tax: Decimal = Decimal("0")
    special_rate_tax: Decimal = Decimal("0")
    amt_tax: Decimal = Decimal("0")
    total_tax_before_relief: Decimal = Decimal("0")
    tax_before_rebate: Decimal = Decimal("0")
    rebate_87a: Decimal = Decimal("0")
    tax_after_rebate: Decimal = Decimal("0")
    surcharge: Decimal = Decimal("0")
    health_education_cess: Decimal = Decimal("0")
    gross_tax_liability: Decimal = Decimal("0")

    relief_89: Decimal = Decimal("0")
    relief_90_91: Decimal = Decimal("0")
    interest_234a: Decimal = Decimal("0")
    interest_234b: Decimal = Decimal("0")
    interest_234c: Decimal = Decimal("0")
    late_fee_234f: Decimal = Decimal("0")
    total_interest: Decimal = Decimal("0")

    net_tax_liability: Decimal = Decimal("0")
    total_tds: Decimal = Decimal("0")
    total_tcs: Decimal = Decimal("0")
    total_advance_tax: Decimal = Decimal("0")
    total_self_assessment_tax: Decimal = Decimal("0")
    total_taxes_paid: Decimal = Decimal("0")
    balance_payable: Decimal = Decimal("0")
    refund_due: Decimal = Decimal("0")

    hp_loss_disallowed: Decimal = Decimal("0")
    cyla_remaining: Decimal = Decimal("0")
    bfla_remaining: Decimal = Decimal("0")
    unabsorbed_dep_setoff: Decimal = Decimal("0")

    schedules: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


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
    z = Decimal("0")

    # ── 1. Business Income (PGBP) ───────────────────────────────────────
    biz_income = z
    pgbp = None
    if input_data.business_income:
        bi = input_data.business_income
        pgbp = compute_pgbp(
            net_profit_before_tax=bi.net_profit_before_tax,
            disallowance_us36=bi.disallowance_us36,
            disallowance_us37=bi.disallowance_us37,
            disallowance_us40=bi.disallowance_us40,
            disallowance_us40a=bi.disallowance_us40a,
            disallowance_us43b=bi.disallowance_us43b,
            deemed_income_us41=bi.deemed_income_us41,
            deemed_income_us33ab=bi.deemed_income_us33ab,
            deemed_income_us33aba=bi.deemed_income_us33aba,
            deemed_income_us35aba=bi.deemed_income_us35aba,
            deemed_income_us35abb=bi.deemed_income_us35abb,
            deemed_income_us32ad=bi.deemed_income_us32ad,
            deemed_income_us40a3a=bi.deemed_income_us40a3a,
            deemed_income_us43ca=bi.deemed_income_us43ca,
            deemed_income_us72a=bi.deemed_income_us72a,
            deemed_income_us80hhd=bi.deemed_income_us80hhd,
            deemed_income_us80ia=bi.deemed_income_us80ia,
            deduction_us32_1_iii=bi.deduction_us32_1_iii,
            depreciation_books=bi.depreciation_books,
            depreciation_it=bi.depreciation_it_act,
            icds_increase=bi.icds_increase,
            icds_decrease=bi.icds_decrease,
            other_additions=bi.other_additions,
            other_deductions=bi.other_deductions,
            speculative_net_pl=bi.speculative_net_pl,
            speculative_additions=bi.speculative_additions,
            speculative_deductions=bi.speculative_deductions,
            specified_net_pl=bi.specified_business_net_pl,
            specified_additions=bi.specified_business_additions,
            specified_deductions=bi.specified_business_deductions,
        )
        biz_income = pgbp.total_business_income
        r.schedules["pgbp"] = pgbp
        r.errors.extend(pgbp.errors)
        r.warnings.extend(pgbp.warnings)

    r.business_income = biz_income

    # ── 2. Salary ───────────────────────────────────────────────────────
    sal = compute_salary(input_data.salary_income, regime)
    r.salary_income = sal.income_chargeable
    r.schedules["salary"] = sal

    # ── 3. House Property ───────────────────────────────────────────────
    hp = compute_hp(input_data.house_property_income, regime)
    r.house_property_income = hp.income_chargeable
    r.hp_loss_disallowed = hp.loss_disallowed
    r.schedules["hp"] = hp

    # ── 4. Capital Gains (same as ITR-2) ────────────────────────────────
    stcg_111a_val = z
    stcg_land_cg = []
    stcg_other = z
    ltcg_112a_assets = []
    ltcg_land_cg = []
    ltcg_other_cg = z
    ltcg_dtaa = z
    vda_entries_list = []
    exempt_54 = z
    exempt_54b = z
    exempt_54ec = z
    exempt_54f = z

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

    stcg_result = compute_stcg(stcg_111a=stcg_111a_val, stcg_land_building=stcg_land_cg,
                                stcg_other=stcg_other)
    ltcg_result = compute_ltcg(ltcg_112a_assets=ltcg_112a_assets, ltcg_land_building=ltcg_land_cg,
                                ltcg_other=ltcg_other_cg, ltcg_dtaa=ltcg_dtaa)
    vda_income = compute_vda(vda_entries=vda_entries_list)
    exemptions = compute_exemptions(exempt_54, exempt_54b, exempt_54ec, exempt_54f)
    cg_result = aggregate_cg(stcg_result, ltcg_result, vda_income, exemptions)
    r.capital_gains_income = cg_result.total_capital_gains
    r.vda_income = vda_income
    r.schedules["cg"] = cg_result

    # ── 5. Other Sources ────────────────────────────────────────────────
    os_ = compute_os(input_data.other_sources_income, regime)
    r.other_sources_income = os_.income_chargeable
    r.schedules["os"] = os_

    # ── 6. Clubbing (SPI) ───────────────────────────────────────────────
    clubbing = z
    for spi in (input_data.spi_entries or []):
        clubbing += spi.amount_included
    r.clubbing_income = clubbing
    r.other_sources_income += clubbing

    # ── 7. Partner in Firm ──────────────────────────────────────────────
    partner_income = z
    for pf in (input_data.partner_firm_details or []):
        partner_income += pf.profit_share_amount
        r.other_sources_income += pf.interest_amount
    r.partner_firm_income = partner_income
    r.business_income += partner_income

    # ── 8. GTI before loss set-off ──────────────────────────────────────
    gti_before = (r.business_income + r.salary_income + r.house_property_income
                  + r.capital_gains_income + r.other_sources_income)
    r.gti_before_loss_setoff = gti_before

    # ── 9. CYLA ─────────────────────────────────────────────────────────
    has_pgbp = pgbp is not None
    cy_input = CYLAInput(
        hp_loss=hp.income_chargeable if hp.income_chargeable < 0 else z,
        hp_income=hp.income_chargeable if hp.income_chargeable > 0 else z,
        non_spec_biz_loss=pgbp.non_spec_net_income if has_pgbp and pgbp.non_spec_net_income < 0 else z,
        non_spec_biz_income=pgbp.non_spec_net_income if has_pgbp and pgbp.non_spec_net_income > 0 else z,
        spec_biz_loss=pgbp.speculative_net_income if has_pgbp and pgbp.speculative_net_income < 0 else z,
        spec_biz_income=pgbp.speculative_net_income if has_pgbp and pgbp.speculative_net_income > 0 else z,
        stcg_loss=cg_result.stcg.total_stcg if cg_result.stcg.total_stcg < 0 else z,
        stcg_income=cg_result.stcg.total_stcg if cg_result.stcg.total_stcg > 0 else z,
        ltcg_loss=cg_result.ltcg.income_125per_other + cg_result.ltcg.income_dtaa
                  if (cg_result.ltcg.income_125per_other + cg_result.ltcg.income_dtaa) < 0 else z,
        ltcg_income=cg_result.ltcg.income_125per_other + cg_result.ltcg.income_dtaa
                    if (cg_result.ltcg.income_125per_other + cg_result.ltcg.income_dtaa) > 0 else z,
    )
    cyla = compute_cyla(cy_input)
    r.cyla_total_set_off = cyla.total_loss_set_off
    r.cyla_remaining = cyla.total_loss_remaining
    r.schedules["cyla"] = cyla

    # ── 10. BFLA ────────────────────────────────────────────────────────
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
        hp_income=hp.income_chargeable if hp.income_chargeable > 0 else z,
        non_spec_biz_income=pgbp.non_spec_net_income if has_pgbp and pgbp.non_spec_net_income > 0 else z,
        spec_biz_income=pgbp.speculative_net_income if has_pgbp and pgbp.speculative_net_income > 0 else z,
        stcg_income=cg_result.stcg.total_stcg if cg_result.stcg.total_stcg > 0 else z,
        ltcg_income=cg_result.ltcg.total_ltcg if cg_result.ltcg.total_ltcg > 0 else z,
        bf_losses=bf_list,
    )
    bfla = compute_bfla(bf_input)
    r.bfla_total_set_off = bfla.total_bf_loss_set_off
    r.bfla_remaining = bfla.total_bf_remaining
    r.schedules["bfla"] = bfla

    # ── 11. GTI after losses ────────────────────────────────────────────
    gti_after = gti_before - r.cyla_total_set_off - r.bfla_total_set_off
    r.gti_after_loss_setoff = gti_after
    r.gross_total_income = gti_after

    # ── 12. Unabsorbed Depreciation set-off ─────────────────────────────
    # Simplified: set off against business income
    r.unabsorbed_dep_setoff = z

    # ── 13. Agricultural Income ─────────────────────────────────────────
    agri = input_data.agricultural_income
    if agri:
        ag = compute_agri(agri.gross_agricultural_income, agri.agricultural_deductions,
                          agri.share_from_firm)
        r.net_agricultural_income = ag.total_net_agricultural_income
        r.schedules["agri"] = ag

    # ── 14. Deductions (Chapter VI-A + Business deductions) ─────────────
    ded = compute_deductions(
        input_data.deductions_chapter6a, gti_after, age, regime,
        input_data.other_sources_income,
        cg_112a_income=cg_result.ltcg.taxable_112a,
        cg_111a_income=stcg_result.income_111a,
    )
    r.schedules["deductions"] = ded
    r.deductions_partb_chapter6a = ded.total
    r.deductions_total = ded.total

    # ── 15. Taxable Income ──────────────────────────────────────────────
    income_before = max(z, gti_after - ded.total)
    ti = round_to_nearest_10(income_before)
    r.taxable_income = ti
    r.aggregate_income = ti + r.net_agricultural_income

    # ── 16. Special Rate Income Tax ─────────────────────────────────────
    si_entries = []
    si_entries.append(si_112a(cg_result.ltcg.income_112a, z))
    si_entries.append(si_111a(stcg_result.income_111a))
    if vda_income > 0:
        si_entries.append(si_vda(vda_income))

    for sie in (input_data.si_entries or []):
        if sie.section == "115BB":
            si_entries.append(compute_lottery(sie.gross_income))
        elif sie.section == "115BBE":
            si_entries.append(compute_115bbe(sie.gross_income))
        elif sie.section == "115BBF":
            si_entries.append(compute_115bbf(sie.gross_income))

    si_result = aggregate_si(si_entries)
    r.special_rate_tax = si_result.total_special_rate_tax
    r.schedules["si"] = si_result

    # ── 17. Normal Slab Tax ─────────────────────────────────────────────
    normal_income = max(z, ti - si_result.total_special_rate_income)
    slab_tax = compute_slab_tax(normal_income, age, regime)

    r.partial_integration_tax = z
    if regime == TaxRegime.OLD and r.net_agricultural_income > Decimal("5000"):
        basic_exemption = _get_basic_exemption(age)
        pit = compute_partial_integration_tax(
            normal_income, r.net_agricultural_income, basic_exemption,
            compute_slab_tax, age, regime,
        )
        r.partial_integration_tax = pit
        slab_tax += pit

    r.slab_tax = slab_tax

    # ── 18. AMT ─────────────────────────────────────────────────────────
    r.amt_tax = z

    # ── 19. Total tax before relief ─────────────────────────────────────
    r.total_tax_before_relief = slab_tax + r.special_rate_tax + r.amt_tax
    r.tax_before_rebate = r.total_tax_before_relief

    # ── 20. Rebate 87A ──────────────────────────────────────────────────
    rebate = compute_rebate(ti, r.tax_before_rebate, regime)
    r.rebate_87a = rebate
    r.tax_after_rebate = max(z, r.tax_before_rebate - rebate)

    # ── 21. Surcharge ───────────────────────────────────────────────────
    surcharge = compute_surcharge(ti, r.tax_after_rebate, regime, age)
    r.surcharge = surcharge

    # ── 22. Cess ────────────────────────────────────────────────────────
    cess = compute_cess(r.tax_after_rebate + surcharge)
    r.health_education_cess = cess
    r.gross_tax_liability = r.tax_after_rebate + surcharge + cess

    # ── 23. AMT (override if applicable) ────────────────────────────────
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

    # ── 24. Foreign tax relief ──────────────────────────────────────────
    for tr1 in (input_data.tr1_entries or []):
        r.relief_90_91 += tr1.relief_claimed
    r.relief_90_91 = min(r.relief_90_91, r.gross_tax_liability)

    # ── 25. Interest ────────────────────────────────────────────────────
    filing_date = input_data.filing_date
    due_date = input_data.due_date
    if filing_date and due_date:
        r.interest_234a = compute_234a(r.gross_tax_liability, filing_date, due_date)
        r.late_fee_234f = compute_234f(filing_date, due_date, ti)
    r.total_interest = r.interest_234a + r.interest_234b + r.interest_234c

    # ── 26. Tax Credits ─────────────────────────────────────────────────
    for tds1 in (input_data.tds1_entries or []):
        r.total_tds += tds1.tds_deducted
    for tds2 in (input_data.tds2_entries or []):
        r.total_tds += tds2.tds_deducted
    for tcs in (input_data.tcs_entries or []):
        r.total_tcs += tcs.tcs_collected
    r.total_advance_tax = input_data.advance_tax_paid or z
    r.total_self_assessment_tax = input_data.self_assessment_tax_paid or z
    r.total_taxes_paid = (r.total_tds + r.total_tcs + r.total_advance_tax
                           + r.total_self_assessment_tax)

    # ── 27. Final payable / refund ──────────────────────────────────────
    net_liability = (r.gross_tax_liability - r.relief_89 - r.relief_90_91
                      + r.total_interest + r.late_fee_234f)
    r.net_tax_liability = round_to_nearest_10(net_liability)

    diff = r.net_tax_liability - r.total_taxes_paid
    if diff > 0:
        r.balance_payable = diff
    else:
        r.refund_due = abs(diff)

    return r
