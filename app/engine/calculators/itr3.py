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
from datetime import date

from app.schemas.itr1 import AgeBracket, HousePropertyIncome, PropertyType, TaxRegime
from app.schemas.itr2 import ResidentialStatus
from app.schemas.itr3 import ITR3Input
from app.engine.common.rounding import round_to_nearest_10
from app.engine.common.slab_tax import compute as compute_slab_tax
from app.engine.common.rebate import compute as compute_rebate
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.common.cess import compute as compute_cess
from app.engine.common.interest import compute_234a, compute_234b, compute_234c, compute_234i, compute_234f
from app.engine.common.due_dates import get_due_date, get_default_filing_date
from app.engine.schedules.salary import compute as compute_salary
from app.engine.schedules.house_property import compute as compute_hp
from app.engine.schedules.other_sources import compute as compute_os
from app.engine.schedules.business import compute as compute_pgbp
from app.engine.schedules.capital_gains import (
    compute_stcg, compute_ltcg, compute_vda,
    compute_exemptions, aggregate as aggregate_cg,
    post_loss_cg_baskets,
    STCGResult, LTCGResult, CG112AAsset, VDAEntry, CGAsset,
    _is_short_term, other_asset_gain, _normalized_land_exemptions,
    unquoted_shares_50ca_adjustment,
    ITR3_OTHER_ASSETS_ST_EXEMPTION_SECTIONS,
    ITR3_OTHER_ASSETS_LT_EXEMPTION_SECTIONS,
)
from app.engine.schedules.special_rates import (
    compute_112a_taxable as si_112a_taxable, compute_111a as si_111a,
    compute_112 as si_112, compute_dtaa_stcg, compute_dtaa_ltcg,
    compute_vda as si_vda, compute_lottery, compute_115bbe, compute_115bbf,
    aggregate as aggregate_si,
)
from app.engine.schedules.agricultural import (
    compute as compute_agri, compute_partial_integration_components,
)
from app.engine.schedules.deductions import compute_all as compute_deductions
from app.engine.schedules.tds_tcs import compute_all as compute_tds_tcs
from app.engine.schedules.loss_setoff.cyla import (
    compute as compute_cyla, CYLAInput,
)
from app.engine.schedules.loss_setoff.bfla import (
    compute as compute_bfla, BFLAInput,
)
from app.engine.schedules.loss_setoff.cfl import compute as compute_cfl
from app.engine.schedules.amt import compute as compute_amt, compute_amtc


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
    amtc_utilised: Decimal = Decimal("0")
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
    fees_234i: Decimal = Decimal("0")
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
    # Section 112(1)(a) second-proviso eligibility (land/building LTCG
    # comparison, capital_gains.py::compute_ltcg()) -- NOR is a species of
    # "resident" under section 6 (only a non-resident is excluded), same
    # gate ITR-2's own calculator uses (calculators/itr2.py).
    is_resident_or_nor = input_data.residential_status != ResidentialStatus.NON_RESIDENT

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
            reallocation_income_salary=bi.reallocation_income_salary,
            reallocation_income_house_property=bi.reallocation_income_house_property,
            reallocation_income_capital_gains=bi.reallocation_income_capital_gains,
            reallocation_income_other_sources=bi.reallocation_income_other_sources,
            reallocation_income_115bbf=bi.reallocation_income_115bbf,
            reallocation_income_115bbg=bi.reallocation_income_115bbg,
            reallocation_income_115bbh=bi.reallocation_income_115bbh,
            reallocation_expense_salary=bi.reallocation_expense_salary,
            reallocation_expense_house_property=bi.reallocation_expense_house_property,
            reallocation_expense_capital_gains=bi.reallocation_expense_capital_gains,
            reallocation_expense_other_sources=bi.reallocation_expense_other_sources,
            reallocation_expense_115bbf=bi.reallocation_expense_115bbf,
            reallocation_expense_115bbg=bi.reallocation_expense_115bbg,
            reallocation_expense_115bbh=bi.reallocation_expense_115bbh,
            exempt_income_firm_share=bi.exempt_income_firm_share,
            exempt_income_aop_boi_share=bi.exempt_income_aop_boi_share,
            exempt_income_other=bi.exempt_income_other,
            income_not_chargeable=bi.income_not_chargeable,
            expense_relating_to_exempt_income=bi.expense_relating_to_exempt_income,
            expense_exempt_income_disallowed_us14a=bi.expense_exempt_income_disallowed_us14a,
            msme_interest_disallowance=bi.msme_interest_disallowance,
            other_addition_28_to_44da=bi.other_addition_28_to_44da,
            section35_excess_deduction=bi.section35_excess_deduction,
            section40_now_allowable=bi.section40_now_allowable,
            section43b_now_allowable=bi.section43b_now_allowable,
            rule7_profit=bi.rule7_profit,
            rule7a_profit=bi.rule7a_profit,
            rule7b1_profit=bi.rule7b1_profit,
            rule7b1a_profit=bi.rule7b1a_profit,
            rule8_profit=bi.rule8_profit,
            rule7_taxable_income=bi.rule7_taxable_income,
            rule7a_deemed_income=bi.rule7a_deemed_income,
            rule7b1_deemed_income=bi.rule7b1_deemed_income,
            rule7b1a_deemed_income=bi.rule7b1a_deemed_income,
            rule8_deemed_income=bi.rule8_deemed_income,
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
    # relief_89 combines section 89(1) relief (Form 10E, salary arrears/
    # advance) with section 89A relief (Schedule S items 1d-1f, retirement
    # benefit account income) -- matching ITR-2's identical combination.
    r.relief_89 = input_data.relief_89 + sal.salary_89a_relief

    # ── 3. House Property ───────────────────────────────────────────────
    # ITR-3 allows any number of properties, each with its own type
    # (self-occupied/let-out/deemed-let-out), ownership share, and loan
    # sanction dates -- all of which change the Section 24 interest cap and
    # the 30% standard deduction. compute_hp() itself already handles all
    # of this correctly for ONE property; it must be called once per
    # property, not once with a single pre-aggregated input (which silently
    # collapsed every property's distinct self-occupied/let-out treatment
    # and ownership share into one figure).
    if input_data.schedule_hp_properties:
        hp_results: list = []
        for hp_source in input_data.schedule_hp_properties:
            try:
                property_type = PropertyType(hp_source.property_type)
            except ValueError:
                property_type = PropertyType.SELF_OCCUPIED
            loan_rows = hp_source.home_loan_details or []
            raw_interest = sum(
                (Decimal(str(loan.get("InterestUs24B", 0))) for loan in loan_rows), Decimal("0")
            )
            loan_sanction_dates: list[Optional[date]] = []
            for loan in loan_rows:
                raw_date = loan.get("DateofLoan")
                try:
                    loan_sanction_dates.append(date.fromisoformat(raw_date) if raw_date else None)
                except ValueError:
                    loan_sanction_dates.append(None)
            hp_input = HousePropertyIncome(
                property_type=property_type,
                annual_rent_received=hp_source.annual_lettable_value,
                rent_not_realized=hp_source.rent_not_realized,
                municipal_taxes_paid=hp_source.local_taxes,
                home_loan_interest_paid=raw_interest,
                arrears_unrealised_rent_received=hp_source.arrears_unrealised_rent,
            )
            hp_results.append(compute_hp(
                hp_input, regime,
                ownership_share_percentage=hp_source.assessee_share_percent or Decimal("100"),
                loan_sanction_dates=loan_sanction_dates or None,
            ))
        r.house_property_income = sum((row.income_chargeable for row in hp_results), Decimal("0"))
        r.hp_loss_disallowed = sum((row.loss_disallowed for row in hp_results), Decimal("0"))
        r.schedules["hp"] = hp_results
    else:
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
    vda_entries_list = []
    exempt_54 = z
    exempt_54b = z
    exempt_54ec = z
    exempt_54f = z
    # Cross-form issue #10 (tracker): ITR-3's own land/building exemption
    # items allow a WIDER section set than ITR-2's equivalent (STCG item
    # A1d = 54B/54G/54GA; LTCG item B1d additionally allows 54D) -- these
    # three have no legacy field/accumulation slot at all until now.
    exempt_54d = z
    exempt_54g = z
    exempt_54ga = z

    for tx in (input_data.cg_transactions or []):
        asset_type = tx.asset_type.value

        # Determine holding period by calendar anniversary, never day-count
        # approximations -- identical to ITR-2's own classification
        # (calculators/itr2.py's `_classify()`), since both forms share the
        # exact same statutory holding-period thresholds for this schedule.
        is_short = True
        if tx.date_of_acquisition is not None and tx.date_of_transfer is not None:
            is_short = _is_short_term(asset_type, tx.date_of_acquisition, tx.date_of_transfer)
        elif tx.explicit_long_term is not None:
            is_short = not tx.explicit_long_term

        if asset_type in ("listed_equity_111a", "equity_oriented_fund_111a"):
            if is_short:
                # Form A3c = 3a - 3biv (biv = cost + improvement + transfer
                # expenses); A3e = 3c + 3d (3d = 94(7)/94(8) disallowed
                # loss, entered positive and added back).
                stcg_111a_val += (tx.full_consideration - tx.cost_of_acquisition
                                  - tx.improvement_cost - tx.expenditure_on_transfer
                                  + tx.loss_disallowed_94_7_94_8)
            else:
                ltcg_112a_assets.append(CG112AAsset(
                    total_sale_value=tx.full_consideration,
                    cost_acq_without_index=tx.cost_of_acquisition,
                    total_fmv=tx.fair_market_value_jan2018 or tx.cost_of_acquisition,
                    total_deductions=tx.expenditure_on_transfer,
                ))
        elif asset_type == "land_building":
            # `date_of_acquisition`/`date_of_transfer`/`stamp_duty_value`/
            # `year_of_improvement` were never populated here at all -- a
            # real, separate defect: without a real acquisition date,
            # compute_ltcg()'s own section 112(1)(a) second-proviso relief
            # (`eib_applicable = is_resident and acquired_date is not None
            # and ...`) could NEVER trigger for ITR-3 regardless of the
            # `is_resident` fix above, since `_parse_date("")` always
            # returns None; `stamp_duty_value`'s absence also silently
            # disabled the section 50C deemed-consideration override.
            # Mirrors ITR-2's own already-correct construction exactly
            # (calculators/itr2.py).
            asset = CGAsset(
                description=tx.description or "",
                date_of_acquisition=tx.date_of_acquisition.isoformat() if tx.date_of_acquisition else "",
                date_of_transfer=tx.date_of_transfer.isoformat() if tx.date_of_transfer else "",
                full_consideration=tx.full_consideration,
                stamp_duty_value=tx.stamp_duty_value or Decimal("0"),
                acquisition_cost=tx.cost_of_acquisition,
                indexed_acquisition_cost=tx.indexed_cost,
                improvement_cost=tx.improvement_cost,
                indexed_improvement_cost=tx.indexed_improvement,
                year_of_improvement=tx.year_of_improvement or "",
                expenditure_on_transfer=tx.expenditure_on_transfer,
                # Populates `asset.exemption_total` (per-asset, section-
                # filtered) inside compute_stcg()/compute_ltcg() -- required
                # for `post_loss_cg_baskets()`'s own `stcg_land_54b`
                # STCG-bucket-targeting logic to see this claim at all (it
                # reads `asset.exemption_total`, never the scalar
                # accumulators below), and for the second-proviso's own
                # post-exemption EiB comparison. Falls back to the legacy
                # `deduction_us54*` scalars when no canonical claim exists,
                # exactly like ITR-2's own `_classify()` already does.
                exemptions=_normalized_land_exemptions(tx),
            )
            if is_short:
                stcg_land_cg.append(asset)
                # Section 54B (agricultural land) is the ONLY §54-series
                # exemption the official form allows against SHORT-term
                # land/building gain (Schedule CG item A1d) -- this branch
                # previously never accumulated ANY exemption at all, so a
                # 54B claim on short-term land/building had zero tax
                # effect on ITR-3 regardless of the per-asset fix above
                # (that fix only affects bucket TARGETING; the exemption
                # must also enter the aggregate `exemptions.total_exemption`
                # pool via this scalar accumulator, exactly like the
                # long-term branch below already does for its own four
                # sections).
                exempt_54b += tx.deduction_us54b
                # Item A1d also allows 54G/54GA (shifting an industrial
                # undertaking) against short-term land/building gain --
                # NOT 54D, which is long-term-only per item B1d.
                exempt_54g += tx.deduction_us54g
                exempt_54ga += tx.deduction_us54ga
            else:
                ltcg_land_cg.append(asset)
                exempt_54 += tx.deduction_us54
                exempt_54b += tx.deduction_us54b
                exempt_54ec += tx.deduction_us54ec
                exempt_54f += tx.deduction_us54f
                exempt_54d += tx.deduction_us54d
                exempt_54g += tx.deduction_us54g
                exempt_54ga += tx.deduction_us54ga

        elif asset_type == "listed_equity_112a":
            # 112A is always long-term (listed equity held >12 months)
            ltcg_112a_assets.append(CG112AAsset(
                total_sale_value=tx.full_consideration,
                cost_acq_without_index=tx.cost_of_acquisition,
                total_fmv=tx.fair_market_value_jan2018 or tx.cost_of_acquisition,
                total_deductions=tx.expenditure_on_transfer,
            ))

        else:
            # Unlisted shares, debt MFs, bonds, jewellery, other. Same
            # arithmetic STRUCTURE as ITR-2's own generic "other assets"
            # bucket (Sl. A5/B8 there vs A6/B9 here) -- shared via
            # `other_asset_gain`, but ITR-3's own valid exemption-section
            # set (54G/54GA for ST; 54D/54F/54G/54GA for LT) is WIDER than
            # ITR-2's (ITR-2's own A5 item has no exemption line at all;
            # its B8 item allows only 54F) -- passed explicitly per call,
            # never a shared default, so the two forms cannot silently
            # apply an exemption the other form's own item doesn't offer.
            valid_sections = (
                ITR3_OTHER_ASSETS_ST_EXEMPTION_SECTIONS if is_short
                else ITR3_OTHER_ASSETS_LT_EXEMPTION_SECTIONS
            )
            gain = other_asset_gain(tx, is_short, valid_sections)
            if is_short:
                stcg_other += gain
            else:
                ltcg_other_cg += gain

    # Cross-form issue #8 (Docs/ITR3_SCHEDULE_IMPLEMENTATION_TRACKER.md):
    # section 50CA's "higher of consideration or FMV" deemed value for
    # unquoted-share disposals was correctly disclosed (itd/cg_shared.py)
    # but never applied to the actual taxed gain -- other_asset_gain()
    # above uses tx.full_consideration directly. Added once, in aggregate,
    # matching the disclosure builder's own aggregation exactly (see
    # unquoted_shares_50ca_adjustment()'s own docstring for why a
    # per-transaction application would overstate the deemed
    # consideration whenever multiple unquoted-share sales exist).
    stcg_other += unquoted_shares_50ca_adjustment(input_data.cg_transactions, is_short=True)
    ltcg_other_cg += unquoted_shares_50ca_adjustment(input_data.cg_transactions, is_short=False)

    # Schedule CG item A6e -- "Deemed short-term capital gains on
    # depreciable assets (6 of schedule - DCG)". This is a SCHEDULE-level
    # total (Schedule DCG's own grand total across the block-of-assets
    # computation, item 6 = 1e+2d+3+4+5), not a per-transaction figure, so
    # it is added to the generic-other-assets STCG bucket once here rather
    # than inside the transaction loop above. ITR-2 has no business-income
    # concept and therefore no Schedule DCG at all -- this term exists ONLY
    # in ITR-3's A6 formula, never ITR-2's equivalent A5 formula (confirmed
    # against both forms' official PDFs: ITR-2's item 5 is "5c + 5d" only;
    # ITR-3's item 6 is "6c + 6d + 6e - 6f").
    dcg_schedule = (
        input_data.depreciation_schedules.schedule_dcg
        if input_data.depreciation_schedules else None
    )
    if dcg_schedule is not None:
        stcg_other += dcg_schedule.SummaryFromDeprSchCG.TotalDepreciation

    # Section 46A capital loss on buyback of shares (Schedule CG's
    # "CapitalLossBuyBackShares" block) is a genuine loss, not merely
    # disclosure -- it reduces the actual taxed STCG/LTCG total. Unlike
    # ITR-2, ITR-3 has no FII/FPI assessee concept and therefore no genuine
    # flat-30% STCG basket at all (section 115AD(1)(ii) is FII-only) -- both
    # `cg_buyback_loss_stcg30` and `cg_buyback_loss_stcg_applicable`
    # correctly net into the SAME `stcg_other` accumulator, which CYLA/BFLA
    # below route into the single "applicable rate" STCG sub-basket
    # (`stcg_app_income`), matching ITR-2's own non-FII path exactly.
    stcg_111a_val += input_data.cg_buyback_loss_stcg20
    stcg_other += input_data.cg_buyback_loss_stcg30 + input_data.cg_buyback_loss_stcg_applicable
    ltcg_other_cg += input_data.cg_buyback_loss_ltcg

    # Cross-form issue #11 (tracker): slump sale (A2/B2, section 50B) and
    # unutilized-CGAS deemed capital gains (A7/B10) were correctly
    # disclosed (itd/itr3.py::_slump_sale_block()/_unutilized_cg_block())
    # but never merged into the actual taxed STCG/LTCG total -- both are
    # taxed at ORDINARY rates (slab for short-term, section 112 for
    # long-term), exactly like the generic "other assets" bucket, so they
    # are merged into the same stcg_other/ltcg_other_cg accumulator
    # already used for that bucket -- correctly eligible for the same
    # intra-CG CYLA/BFLA loss set-off the Act allows, unlike PTI pass-
    # through income below. Formulas match the disclosure builder's own
    # exactly (item 2c/2e, item x "AmtDeemed").
    for row in (input_data.cg_slump_sale_stcg or []):
        stcg_other += max(row.fmv_11uae_2, row.fmv_11uae_3) - row.net_worth
    for row in (input_data.cg_slump_sale_ltcg or []):
        ltcg_other_cg += max(row.fmv_11uae_2, row.fmv_11uae_3) - row.net_worth - row.exemption_amount
    stcg_other += sum(
        (row.amount_unutilized for row in (input_data.cg_stcg_unutilized_deposits or [])), z,
    )
    ltcg_other_cg += sum(
        (row.amount_unutilized for row in (input_data.cg_ltcg_unutilized_deposits or [])), z,
    )

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
                                ltcg_other=ltcg_other_cg, is_resident=is_resident_or_nor)

    # NRI proviso-48 (Schedule CG A3/B4/B7 -- non-resident, not an FII,
    # sale under first proviso to section 48, and section 115F) and
    # DTAA-rate capital gains (A9/B12) -- ported verbatim from ITR-2's own
    # already-working calculator (calculators/itr2.py), since both forms
    # share the identical Schedule CG A3/B4/B7/A9/B12 arithmetic. These
    # ITR3Input fields were added earlier this session for Schedule CG
    # disclosure but were only ever read by the ITD builder for the raw
    # bare-figure rows -- never merged into stcg_result/ltcg_result here,
    # so they were correctly disclosed but had ZERO tax effect.
    stcg_dtaa_not_chargeable = sum(
        (e.amount for e in (input_data.cg_stcg_dtaa_entries or []) if not e.chargeable_in_india), z,
    )
    stcg_dtaa_special = sum(
        (e.amount for e in (input_data.cg_stcg_dtaa_entries or []) if e.chargeable_in_india), z,
    )
    ltcg_dtaa_not_chargeable = sum(
        (e.amount for e in (input_data.cg_ltcg_dtaa_entries or []) if not e.chargeable_in_india), z,
    )
    ltcg_dtaa_special = sum(
        (e.amount for e in (input_data.cg_ltcg_dtaa_entries or []) if e.chargeable_in_india), z,
    )
    nri_ltcg_proviso48 = max(z,
        input_data.cg_nri_ltcg_without_indexation - input_data.cg_nri_ltcg_deduction_54f)  # B4c
    # B7 (115F) is taxed at 12.5% under section 115E -- numerically the
    # same rate as ordinary non-112A LTCG post-Budget-2024, so folded into
    # income_125per_other for tax correctness (same scoping decision
    # ITR-2's calculator already makes, and the same documented deferral:
    # no distinct section-115E Schedule SI row, just correctly taxed).
    nri_ltcg_115f = max(z,
        input_data.cg_nri_115f_sale_value - input_data.cg_nri_115f_deduction)  # B7c

    stcg_result.income_111a += input_data.cg_nri_stcg_stt_paid  # A3a
    stcg_result.income_30per += (
        input_data.cg_nri_stcg_stt_not_paid  # A3b
        - stcg_dtaa_not_chargeable - stcg_dtaa_special
    )
    stcg_result.income_dtaa += stcg_dtaa_special
    stcg_result.total_stcg = (
        stcg_result.income_111a + stcg_result.income_30per
        + stcg_result.income_app_rate + stcg_result.income_dtaa
    )
    ltcg_result.income_125per_other += (
        nri_ltcg_proviso48 + nri_ltcg_115f - ltcg_dtaa_not_chargeable - ltcg_dtaa_special
    )
    ltcg_result.income_dtaa += ltcg_dtaa_special
    ltcg_result.total_ltcg = (
        ltcg_result.income_112a + ltcg_result.income_125per_other + ltcg_result.income_dtaa
    )

    vda_income = compute_vda(vda_entries=vda_entries_list)
    exemptions = compute_exemptions(exempt_54, exempt_54b, exempt_54ec, exempt_54f)
    # Cross-form issue #10 (tracker): 54D/54G/54GA have no dedicated
    # ExemptionResult field (compute_exemptions() is shared with ITR-1/2/4
    # and deliberately left untouched here) -- folded directly into the
    # aggregate total instead, which is all aggregate()/post_loss_cg_
    # baskets() actually consume for the LTCG-side exemption pool; the
    # STCG-side 54G/54GA netting already happens automatically via
    # asset.exemption_total (Table E's own per-asset mechanism), since
    # _normalized_land_exemptions() now recognizes these three sections.
    exemptions.total_exemption += exempt_54d + exempt_54g + exempt_54ga
    cg_result = aggregate_cg(stcg_result, ltcg_result, vda_income, exemptions)

    # Cross-form issue #11 (tracker): Schedule PTI capital gains
    # (income_head "STCG"/"LTCG") retain the SAME head AND rate the
    # business trust/investment fund itself earned them under (section
    # 115UA(2)/115UB(1) proviso) and get their OWN distinct Schedule-SI
    # SecCodes (PTI_STCG20P/PTI_STCG30P/PTI_LTCG12_5P112A/PTI_LTCG12_5P),
    # NOT the ordinary 111A/112/112A rows -- ported verbatim from ITR-2's
    # own already-working calculator (calculators/itr2.py), deliberately
    # NOT merged into stcg_result/ltcg_result (which would misclassify it
    # under the wrong SecCode) and NOT run through CYLA/BFLA, matching
    # how VDA income is already treated in this same function.
    pti_cg_gross = sum(
        (pti.income_amount for pti in (input_data.pti_entries or [])
         if pti.income_head in ("STCG", "LTCG") and pti.income_amount > 0),
        z,
    )
    r.capital_gains_income = cg_result.total_capital_gains + pti_cg_gross
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

    # ── 8. GTI before loss set-off (positive-only heads; losses handled by CYLA) ──
    gti_before = (r.business_income  # already floored at 0
                  + max(z, r.salary_income)
                  + max(z, r.house_property_income)
                  + r.capital_gains_income  # already floored by aggregate()
                  + max(z, r.other_sources_income))
    r.gti_before_loss_setoff = gti_before

    # ── 9. CYLA ─────────────────────────────────────────────────────────
    has_pgbp = pgbp is not None
    # Note: STCG/LTCG intra-head losses already netted by aggregate().
    # Business and HP losses are cross-head and handled here.
    # Non-speculative business loss/income and speculative business income
    # are fed post-Part-E (the Schedule BP Part E intra-head set-off of a
    # regular business loss against speculative/specified business income,
    # already computed inside compute_pgbp itself) -- NOT the raw signed
    # pgbp.non_spec_signed/pgbp.speculative_signed. Using the raw figures
    # here would let the same rupee of speculative/specified income be
    # used twice: once by Part E's own intra-head absorption, and again by
    # CYLA's cross-head absorption of an unrelated HP/CG loss. Speculative
    # business's OWN loss (spec_biz_loss, when speculative_signed itself is
    # negative) is a separate, pre-existing scenario Part E does not touch
    # (Part E only ever absorbs a NON-speculative loss), so it is left
    # sourced from the raw signed value exactly as before.
    non_spec_biz_loss_for_cyla = pgbp.part_e_loss_remaining if has_pgbp else z
    non_spec_biz_income_for_cyla = pgbp.non_spec_net_income if has_pgbp else z
    spec_biz_income_for_cyla = pgbp.part_e_speculative_income_after_setoff if has_pgbp else z

    # Map CG baskets into the statutory sub-baskets CYLA/BFLA/Schedule SI
    # need, mirroring ITR-2's own already-correct calculator exactly
    # (calculators/itr2.py) -- ITR-3 shares the identical Schedule CG/CYLA/
    # BFLA/SI architecture, just without a distinct FII/FPI assessee status
    # (FII is out of scope for ITR-3 filers entirely), so there is no
    # genuine flat-30% STCG basket here: `stcg_result.income_30per`
    # (land/building) and `income_app_rate` both always land in the
    # "applicable rate" (slab) STCG sub-basket. Previously EVERY CG rate
    # bucket -- 111A @20%, ordinary LTCG @12.5% under section 112, DTAA-rate
    # CG -- was lumped into a single generic bucket with no differentiation
    # at all, which meant: (1) section 112 LTCG-other was never taxed at
    # its own 12.5% special rate, only at slab rates; (2) the section
    # 112(1)(a) second-proviso relief could never apply (is_resident was
    # never even passed to compute_ltcg()); (3) a current-year/brought-
    # forward loss set off against the lumped bucket never correctly
    # reduced the special-rate 111A/112A tax, since Schedule SI entries
    # were built from RAW pre-loss values further down this function
    # (fixed below, ## 16).
    stcg_111a_signed = stcg_result.income_111a
    stcg_app_signed = stcg_result.income_30per + stcg_result.income_app_rate
    stcg_dtaa_signed = stcg_result.income_dtaa
    ltcg_125_signed = ltcg_result.income_125per_other
    ltcg_112a_gross = ltcg_result.income_112a
    ltcg_dtaa_signed = ltcg_result.income_dtaa

    cy_input = CYLAInput(
        hp_loss=r.house_property_income if r.house_property_income < 0 else z,
        hp_income=r.house_property_income if r.house_property_income > 0 else z,
        non_spec_biz_loss=non_spec_biz_loss_for_cyla,
        non_spec_biz_income=non_spec_biz_income_for_cyla,
        spec_biz_loss=pgbp.speculative_signed if has_pgbp and pgbp.speculative_signed < 0 else z,
        spec_biz_income=spec_biz_income_for_cyla,
        stcg20_income=stcg_111a_signed,
        stcg30_income=z,
        stcg_app_income=stcg_app_signed,
        stcg_dtaa_income=stcg_dtaa_signed,
        ltcg125_income=ltcg_125_signed + ltcg_112a_gross,
        ltcg_dtaa_income=ltcg_dtaa_signed,
        non_salary_income=max(z, r.salary_income) + max(z, r.other_sources_income - r.clubbing_income),
    )
    cyla = compute_cyla(cy_input)
    r.cyla_total_set_off = cyla.total_loss_set_off
    r.cyla_remaining = cyla.total_loss_remaining
    r.schedules["cyla"] = cyla

    # ── 10. BFLA ────────────────────────────────────────────────────────
    # Use each CYLA sub-basket's own post-CYLA residual directly (mirroring
    # ITR-2's own BFLAInput construction exactly) -- NOT a single
    # re-derived lumped figure, which previously discarded the
    # rate-basket split CYLA had just computed.
    bf_list = [
        {
            "assessment_year": str(item.assessment_year),
            # `BFLossItem.head` is a `LossHead(str, Enum)` -- `str(item.head)`
            # renders as the class-qualified "LossHead.LONG_TERM_CAPITAL",
            # not the plain "LTCG" value `loss_setoff/bfla.py`'s own head
            # dispatch (`elif head == "LTCG": ...`) and `_MAX_CARRY_FWD`
            # expiry lookup require -- so a brought-forward loss never
            # matched anything and had ZERO effect. Mirrors ITR-2's own
            # already-correct line exactly (calculators/itr2.py).
            "head": item.head.value if hasattr(item.head, "value") else str(item.head),
            "sub_category": str(item.sub_category),
            "original_loss": Decimal(str(item.original_loss)),
            "brought_forward": Decimal(str(item.brought_forward)),
        }
        for item in (input_data.bf_losses or [])
    ]
    bf_input = BFLAInput(
        hp_income=r.house_property_income if r.house_property_income > 0 else z,
        non_spec_biz_income=pgbp.non_spec_net_income if has_pgbp and pgbp.non_spec_net_income > 0 else z,
        spec_biz_income=pgbp.speculative_net_income if has_pgbp and pgbp.speculative_net_income > 0 else z,
        stcg20_income=cyla.stcg20_remaining,
        stcg30_income=cyla.stcg30_remaining,
        stcg_app_income=cyla.stcg_app_remaining,
        stcg_dtaa_income=cyla.stcg_dtaa_remaining,
        ltcg125_income=cyla.ltcg125_remaining,
        ltcg_dtaa_income=cyla.ltcg_dtaa_remaining,
        bf_losses=bf_list,
    )
    bfla = compute_bfla(bf_input)
    r.bfla_total_set_off = bfla.total_bf_loss_set_off
    r.bfla_remaining = bfla.total_bf_remaining
    r.schedules["bfla"] = bfla

    # ── 10a. CFL: Carry-Forward Loss Summary ────────────────────────────────
    cfl_entries = []
    # CYLA remaining losses (current-year that couldn't be set off)
    if cyla.hp_setoff > 0 or abs(r.house_property_income) > cyla.hp_setoff if r.house_property_income < 0 else False:
        pass  # hp_loss remaining handled via cyla.entries
    for entry in cyla.entries:
        if entry.remaining_loss > 0:
            cfl_entries.append({"head": entry.head, "sub_category": entry.sub_category,
                                "loss_cf": entry.remaining_loss})
    for entry in bfla.entries:
        if entry.remaining_carry_forward > 0:
            cfl_entries.append({"head": entry.head, "sub_category": entry.sub_category,
                                "loss_cf": entry.remaining_carry_forward})
    r.schedules["cfl"] = cfl_entries

    # ── 11. GTI after losses, and post-loss capital-gain rate baskets ───
    gti_after = max(z, gti_before - r.cyla_total_set_off - r.bfla_total_set_off)
    r.gti_after_loss_setoff = gti_after
    r.gross_total_income = gti_after

    # Allocate CYLA/BFLA's per-basket residuals into the post-loss
    # 111A/112/112A/DTAA rate baskets Schedule SI needs -- shared with
    # ITR-2 (app/engine/schedules/capital_gains.py::post_loss_cg_baskets()).
    post_loss_cg = post_loss_cg_baskets(stcg_result, ltcg_result, cyla, bfla, cg_result.exemptions)
    r.schedules["post_loss_cg"] = post_loss_cg

    # Correct GTI/Total Income and the disclosed capital-gains total for
    # §54/54B/54EC/54F/115F exemptions actually consumed against STCG/LTCG
    # above ("exemption_used") -- `gti_before`/`gti_after` were computed
    # from `stcg_result.total_stcg`/`ltcg_result.total_ltcg`, captured
    # BEFORE `post_loss_cg_baskets()` ever applies this same netting.
    # Mirrors ITR-2's identical correction (calculators/itr2.py).
    _cg_bucket_keys = ("normal_stcg", "111a", "112", "112a_gross", "stcg_dtaa", "ltcg_dtaa")
    r.capital_gains_income = sum((post_loss_cg[k] for k in _cg_bucket_keys), z) + vda_income + pti_cg_gross
    total_cg_exemption_relief = post_loss_cg.get("exemption_used", z)
    gti_after = max(z, gti_after - total_cg_exemption_relief)
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
    # Use post-CYLA/BFLA capital-gain amounts (post_loss_cg), not the raw
    # pre-loss stcg_result/ltcg_result figures -- mirrors ITR-2's identical
    # fix (calculators/itr2.py, "## 10. Chapter VI-A Deductions").
    cg_112a_taxable_for_ded = post_loss_cg["112a_taxable"]
    cg_111a_income_for_ded = post_loss_cg["111a"]
    ded = compute_deductions(
        input_data.deductions_chapter6a, gti_after, age, regime,
        input_data.other_sources_income,
        cg_112a_income=cg_112a_taxable_for_ded,
        cg_111a_income=cg_111a_income_for_ded,
    )
    r.schedules["deductions"] = ded
    r.deductions_partb_chapter6a = ded.total
    r.deductions_total = ded.total

    # Populate per-section business deductions from breakdown
    bd = ded.breakdown if ded.breakdown else {}
    r.deductions_80ia = bd.get("80-IA", z)
    r.deductions_80ib = bd.get("80-IB", z)
    r.deductions_80ic = bd.get("80-IC", z)
    r.deductions_10aa = bd.get("10AA", z)

    # ── 15. Taxable Income ──────────────────────────────────────────────
    income_before = max(z, gti_after - ded.total)
    ti = round_to_nearest_10(income_before)
    r.taxable_income = ti
    r.aggregate_income = ti + r.net_agricultural_income

    # ── 16. Special Rate Income Tax ─────────────────────────────────────
    # Every entry below is built from POST-loss-setoff `post_loss_cg`
    # values, not the raw pre-CYLA/BFLA stcg_result/ltcg_result figures --
    # otherwise a loss set off against the lumped CG bucket would never
    # actually reduce the special-rate 111A/112A/112 tax (it would still be
    # computed on the full, un-reduced amount) while `normal_income`'s own
    # `max(z, ...)` clip below silently "wastes" the loss's benefit instead.
    si_entries = []

    # Section 112A: taxable amount drives the tax; gross amount (BFLA-
    # sourced, "part of 3vii of Schedule BFLA" per the form's own Schedule
    # SI table) drives the disclosed "Income" column -- see
    # compute_112a_taxable()'s own docstring for the full citation.
    si_entries.append(si_112a_taxable(cg_112a_taxable_for_ded, gross_112a=post_loss_cg["112a_gross"]))

    # Section 111A: listed equity STCG (at 20% for AY 2026-27).
    si_entries.append(si_111a(cg_111a_income_for_ded))

    # Section 112: LTCG other than 112A, at 12.5% -- previously MISSING
    # entirely from ITR-3's calculator (the whole gain was taxed at slab
    # rates instead), the core bug this fix addresses.
    other_ltcg = post_loss_cg["112"]
    if other_ltcg > 0:
        si_112_entry = si_112(other_ltcg)
        # Section 112(1)(a) second-proviso relief (land/building,
        # residents, pre-23-Jul-2024 acquisition), computed per-row in
        # compute_ltcg() and summed onto ltcg_result.total_excess_tax_112_1a.
        # Capped at this bucket's own actual tax so the relief can never
        # exceed what was actually charged here -- mirrors ITR-2's
        # identical relief application exactly (calculators/itr2.py).
        relief = min(ltcg_result.total_excess_tax_112_1a, si_112_entry.tax_amount)
        if relief > z:
            si_112_entry.tax_amount -= relief
        si_entries.append(si_112_entry)

    # DTAA-rate STCG/LTCG (Schedule CG A9/B12) -- ratio-allocate the
    # post-loss taxable DTAA basket back across each declared entry's own
    # rate, mirroring ITR-2's identical allocation (calculators/itr2.py).
    stcg_dtaa_taxable = post_loss_cg["stcg_dtaa"]
    stcg_dtaa_gross = sum(
        (e.amount for e in (input_data.cg_stcg_dtaa_entries or []) if e.chargeable_in_india), z,
    )
    if stcg_dtaa_taxable > z and stcg_dtaa_gross > z:
        stcg_dtaa_ratio = min(Decimal("1"), stcg_dtaa_taxable / stcg_dtaa_gross)
        for dtaa in input_data.cg_stcg_dtaa_entries:
            if dtaa.chargeable_in_india:
                si_entries.append(compute_dtaa_stcg(dtaa.amount * stcg_dtaa_ratio, dtaa.applicable_rate))

    ltcg_dtaa_taxable = post_loss_cg["ltcg_dtaa"]
    ltcg_dtaa_gross = sum(
        (e.amount for e in (input_data.cg_ltcg_dtaa_entries or []) if e.chargeable_in_india), z,
    )
    if ltcg_dtaa_taxable > z and ltcg_dtaa_gross > z:
        ltcg_dtaa_ratio = min(Decimal("1"), ltcg_dtaa_taxable / ltcg_dtaa_gross)
        for dtaa in input_data.cg_ltcg_dtaa_entries:
            if dtaa.chargeable_in_india:
                si_entries.append(compute_dtaa_ltcg(dtaa.amount * ltcg_dtaa_ratio, dtaa.applicable_rate))

    if vda_income > 0:
        si_entries.append(si_vda(vda_income))

    # Cross-form issue #11 (tracker): Schedule PTI capital gains dispatch
    # to Schedule SI, ported verbatim from ITR-2's own already-working
    # calculator (calculators/itr2.py) -- both forms share the identical
    # PTIEntry.section-based rate routing.
    #
    # Cross-form issue #12 (tracker): item A8a/A8b/A8c on the official
    # form shows THREE PTI-STCG buckets -- 20% (111A), 30%, and
    # "chargeable at applicable rates" -- but the official schema's own
    # SecCode enum has only TWO PTI capital-gains codes for STCG at all
    # (`PTI_STCG20P`/`PTI_STCG30P`; confirmed by a full grep of every
    # PTI_* SecCode in the schema): no dedicated code exists for
    # "applicable rate" PTI STCG. That bucket is therefore ordinary
    # SLAB-rate income (matching how this codebase already treats every
    # other "applicable rate" CG bucket, e.g.
    # `cg_buyback_loss_stcg_applicable` merging into the plain slab-rate
    # `stcg_other` accumulator, never given a special SI entry) --
    # `PTIEntry.section`'s own real-world STCG values (111A vs the
    # business-trust/investment-fund codes 115UA/115UB/115U/115T)
    # identify WHICH TYPE of pass-through vehicle the income came from,
    # not a tax rate, so there is no reliable signal here for a genuine
    # flat-30% case. `compute_pti_stcg30()`/`PTI_STCG30P` therefore stay
    # unused pending a real, verified 30%-triggering scenario. Omitting
    # the SI entry for this bucket is sufficient and correct: this
    # session's own item-11 fix already adds `pti_cg_gross` directly to
    # `r.capital_gains_income`/`ti`, and `si_result.total_special_rate_
    # income` (## 12, below) only excludes amounts that actually got an
    # SI entry -- so this rupee automatically flows into
    # `normal_income`/`slab_tax` instead. Ported from the identical fix
    # in ITR-2's own calculator (which also documents this same
    # "no SI entry -> falls through to slab rate" mechanism for its
    # OS-head PTI dispatch).
    from app.engine.schedules.special_rates import (
        compute_pti_stcg20 as _compute_pti_stcg20,
        compute_pti_ltcg112a as _compute_pti_ltcg112a,
        compute_pti_ltcg125 as _compute_pti_ltcg125,
    )
    for pti in (input_data.pti_entries or []):
        if pti.income_amount > 0:
            if pti.income_head == "STCG" and pti.section == "111A":
                si_entries.append(_compute_pti_stcg20(pti.income_amount))
            elif pti.income_head == "LTCG" and "112A" in pti.section.upper():
                si_entries.append(_compute_pti_ltcg112a(pti.income_amount))
            elif pti.income_head == "LTCG":
                si_entries.append(_compute_pti_ltcg125(pti.income_amount))

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

    # Finance Act 3-step method: Step 1 (tax on aggregate income) REPLACES
    # slab_tax(normal_income) above; Step 2 (tax on agri+exemption) is the
    # separately-disclosed "rebate" -- see app/engine/calculators/itr2.py's
    # identical fix for the full derivation. `slab_tax += pit` previously
    # double-counted normal_income's own tax.
    r.partial_integration_tax = z
    if regime == TaxRegime.OLD and r.net_agricultural_income > Decimal("5000"):
        basic_exemption = _get_basic_exemption(age)
        tax_on_aggregate, tax_on_agri_plus_exemption = compute_partial_integration_components(
            normal_income, r.net_agricultural_income, basic_exemption,
            compute_slab_tax, age, regime,
        )
        r.partial_integration_tax = tax_on_agri_plus_exemption
        slab_tax = tax_on_aggregate

    r.slab_tax = slab_tax

    # ── 18. AMT ─────────────────────────────────────────────────────────
    r.amt_tax = z

    # ── 19. Total tax before relief ─────────────────────────────────────
    # CBDT rule #523 / official form Part B-TTI item 2d ("Tax Payable on
    # Total Income = 2a + 2b - 2c") applies here too -- when partial
    # integration applies, slab_tax is Step 1 and r.partial_integration_tax
    # is Step 2 (the rebate), so both must combine, not just slab_tax alone
    # (see app/engine/calculators/itr2.py's identical fix).
    r.total_tax_before_relief = max(
        z, slab_tax + r.special_rate_tax - r.partial_integration_tax + r.amt_tax
    )
    r.tax_before_rebate = r.total_tax_before_relief

    # ── 20. Rebate 87A ──────────────────────────────────────────────────
    # compute_rebate()'s `slab_tax` argument is "tax on normal-rate income
    # only" -- after partial integration that is Step 1 less the
    # agricultural rebate (Step 2), not Step 1 alone.
    normal_rate_tax_after_agri_rebate = max(z, slab_tax - r.partial_integration_tax)
    rebate = compute_rebate(ti, r.tax_before_rebate, normal_rate_tax_after_agri_rebate, regime)
    r.rebate_87a = rebate
    r.tax_after_rebate = max(z, r.tax_before_rebate - rebate)

    # ── 21. Surcharge ───────────────────────────────────────────────────
    surcharge = compute_surcharge(ti, r.tax_after_rebate, regime, age,
                                   sr_tax=si_result.surcharge_cap_tax,
                                   sr_surcharge_full_tax=si_result.surcharge_full_tax)
    r.surcharge = surcharge

    # ── 22. Cess ────────────────────────────────────────────────────────
    cess = compute_cess(r.tax_after_rebate + surcharge)
    r.health_education_cess = cess
    r.gross_tax_liability = r.tax_after_rebate + surcharge + cess

    # ── 23. AMT (override if applicable) ────────────────────────────────
    # AMT triggers: read from deduction breakdown
    amt_triggers = {}
    ded_sched = r.schedules.get("deductions")
    if ded_sched and hasattr(ded_sched, "breakdown") and ded_sched.breakdown:
        bd = ded_sched.breakdown
        for key, label in [("80-IA", "80-IA"), ("80-IB", "80-IB"),
                           ("80-IC", "80-IC"), ("10AA", "10AA")]:
            val = bd.get(key, z)
            if val > 0:
                amt_triggers[label] = val
    amt_result = compute_amt(ti, r.gross_tax_liability, amt_triggers, regime, age)
    if amt_result.chapter_xii_ba_applicable:
        r.schedules["amt"] = amt_result
        credits = input_data.amt_input.amt_credits if input_data.amt_input is not None else []
        capacity = max(z, r.gross_tax_liability - amt_result.amt_tax)
        r.schedules["amtc"] = compute_amtc(credits, capacity, "2026-27")
        r.amtc_utilised = r.schedules["amtc"].total_utilised
    if amt_result.amt_applicable:
        r.amt_tax = amt_result.amt_tax - r.gross_tax_liability
        r.gross_tax_liability = amt_result.final_tax
        r.total_tax_before_relief += r.amt_tax

    # ── 24. Foreign tax relief ──────────────────────────────────────────
    for tr1 in (input_data.tr1_entries or []):
        r.relief_90_91 += tr1.relief_claimed
    r.relief_90_91 = min(r.relief_90_91, r.gross_tax_liability)

    # ── 25. Tax Credits (compute BEFORE interest — 234A base uses net assessed tax) ──
    tds_tcs = compute_tds_tcs(
        tds1_entries=input_data.tds1_entries,
        tds2_entries=input_data.tds2_entries,
        tcs_entries=input_data.tcs_entries,
    )
    r.total_tds = tds_tcs.total_tds
    r.total_tcs = tds_tcs.total_tcs
    r.total_advance_tax = input_data.advance_tax_paid or z
    r.total_self_assessment_tax = input_data.self_assessment_tax_paid or z
    r.total_taxes_paid = (r.total_tds + r.total_tcs + r.total_advance_tax
                           + r.total_self_assessment_tax)

    # ── 26. Interest & Late Fee ─────────────────────────────────────────
    filing_date = input_data.filing_date
    due_date = input_data.due_date or (get_due_date("ITR-3") if filing_date else None)

    if filing_date and due_date:
        assessed_tax = max(z,
            r.gross_tax_liability - r.relief_90_91 - r.relief_89
            - r.amtc_utilised - r.total_tds - r.total_tcs)
        ay_start = date(due_date.year, 4, 1)
        r.interest_234a = compute_234a(assessed_tax, filing_date, due_date)
        r.interest_234b = compute_234b(assessed_tax,
            input_data.advance_tax_paid or z, filing_date, ay_start)
        if (input_data.advance_tax_q1 is not None or input_data.advance_tax_q2 is not None
                or input_data.advance_tax_q3 is not None or input_data.advance_tax_q4 is not None):
            quarterly = [
                input_data.advance_tax_q1 or z,
                input_data.advance_tax_q2 or z,
                input_data.advance_tax_q3 or z,
                input_data.advance_tax_q4 or z,
            ]
        else:
            quarterly = [input_data.advance_tax_paid or z]
        r.interest_234c = compute_234c(quarterly, assessed_tax, ay_start)
        r.late_fee_234f = compute_234f(filing_date, due_date, ti)
        r.fees_234i = compute_234i(filing_date, due_date, ti,
                                   filing_section=input_data.filing_section)
    r.total_interest = r.interest_234a + r.interest_234b + r.interest_234c

    # ── 27. Final payable / refund ──────────────────────────────────────
    net_liability = (r.gross_tax_liability - r.amtc_utilised - r.relief_89 - r.relief_90_91
                      + r.total_interest + r.late_fee_234f + r.fees_234i)
    r.net_tax_liability = max(z, net_liability)

    diff = r.net_tax_liability - r.total_taxes_paid
    if diff > 0:
        r.balance_payable = round_to_nearest_10(diff)
    else:
        r.refund_due = round_to_nearest_10(abs(diff))

    return r
