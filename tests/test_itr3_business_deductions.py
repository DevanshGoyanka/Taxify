"""Schema tests for typed ITR-3 business deduction schedules."""

from __future__ import annotations

from decimal import Decimal

from jsonschema import Draft4Validator

from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.engine.calculators.itr3 import ITR3Result
from app.engine.schedules.business import PGBPResult
from app.engine.itd.itr3 import _schedule_bp, _serialize_schedule_model, _partb_ti
from app.schemas.itr3 import BusinessIncome


def _schedule_bp_validator() -> Draft4Validator:
    """Create the official AY 2026-27 validator for Schedule BP."""
    full = get_itr3_schema_validator().schema
    definition = dict(full["definitions"]["ITR3ScheduleBP"])
    definition["definitions"] = full["definitions"]
    return Draft4Validator(definition)


def test_schedule_bp_maps_typed_rows_and_closes_official_arithmetic_bridge() -> None:
    """Every mapped BP adjustment contributes to the official bridge exactly once."""
    business = BusinessIncome(
        depreciation_books=Decimal("100"),
        depreciation_it_act=Decimal("60"),
        disallowance_us36=Decimal("11"),
        disallowance_us37=Decimal("12"),
        disallowance_us40=Decimal("13"),
        disallowance_us40a=Decimal("14"),
        disallowance_us43b=Decimal("15"),
        deemed_income_us41=Decimal("16"),
        deemed_income_us32ad=Decimal("17"),
        deemed_income_us33ab=Decimal("18"),
        deemed_income_us33aba=Decimal("19"),
        deemed_income_us35aba=Decimal("20"),
        deemed_income_us35abb=Decimal("21"),
        deemed_income_us40a3a=Decimal("22"),
        deemed_income_us72a=Decimal("23"),
        deemed_income_us80hhd=Decimal("24"),
        deemed_income_us80ia=Decimal("25"),
        deemed_income_us43ca=Decimal("26"),
        icds_increase=Decimal("27"),
        deduction_us32_1_iii=Decimal("28"),
        icds_decrease=Decimal("29"),
    )
    pgbp = PGBPResult(
        non_spec_profit_before_tax=Decimal("1000"),
        non_spec_signed=Decimal("1306"),
        non_spec_net_income=Decimal("1306"),
        total_business_income=Decimal("1306"),
        non_spec_depreciation_books=business.depreciation_books,
        non_spec_depreciation_it=business.depreciation_it_act,
    )
    result = ITR3Result(schedules={"pgbp": pgbp})

    payload = _schedule_bp(result, type("TypedInput", (), {"business_income": business})())
    errors = list(_schedule_bp_validator().iter_errors(payload))
    assert not errors, "\\n".join(error.message for error in errors)

    business_rows = payload["BusinessIncOthThanSpec"]
    additions = sum((Decimal(str(business_rows[key])) for key in (
        "AmtDebPLDisallowUs36", "AmtDebPLDisallowUs37", "AmtDebPLDisallowUs40",
        "AmtDebPLDisallowUs40A", "AmtDebPLDisallowUs43B", "DeemIncUs41",
        "DeemIncUs32AD", "DeemIncUs33AB", "DeemIncUs33ABA", "DeemIncUs35ABA",
        "DeemIncUs35ABB", "DeemIncUs40A3A", "DeemIncUs72A", "DeemIncUs80HHD",
        "DeemIncUs80IA", "DeemIncUs43CA", "IncProfDecLossAccICDSAdj",
    )), Decimal("0"))
    deductions = Decimal(str(business_rows["DeductUs32_1_iii"])) + Decimal(
        str(business_rows["DecProfIncLossAccICDSAdj"])
    )
    assert business_rows["DepreciationDebPLCosAct"] == 100
    assert business_rows["DepreciationAllowITAct32"]["TotDeprAllowITAct"] == 60
    # Item 10 (6+9) is BEFORE the depreciation adjustment -- item 13 (10+11-12iii)
    # is the separate, later step that applies it. Previously both were set
    # to the same (already depreciation-adjusted) value.
    assert business_rows["AdjustedPLOthThanSpecBus"] == 1000
    assert business_rows["AdjustPLAfterDeprOthSpecInc"] == 1040
    assert business_rows["TotAfterAddToPLDeprOthSpecInc"] == 1363
    assert business_rows["TotDeductionAmts"] == 57
    assert business_rows["PLAftAdjDedBusOthThanSpec"] == 1306
    assert additions == 323
    assert deductions == 57


def test_schedule_bp_does_not_infer_untyped_adjustments_from_pgbp() -> None:
    """Omitted typed adjustments stay zero even when the calculator has a total."""
    pgbp = PGBPResult(
        non_spec_profit_before_tax=Decimal("500"),
        non_spec_signed=Decimal("500"),
        non_spec_net_income=Decimal("500"),
        total_business_income=Decimal("500"),
        non_spec_depreciation_books=Decimal("80"),
        non_spec_depreciation_it=Decimal("30"),
        non_spec_additions=Decimal("999"),
        non_spec_deductions=Decimal("888"),
    )
    result = ITR3Result(schedules={"pgbp": pgbp})
    typed = type("TypedInput", (), {"business_income": BusinessIncome()})()
    payload = _schedule_bp(result, typed)
    rows = payload["BusinessIncOthThanSpec"]
    assert rows["AdjustedPLOthThanSpecBus"] == 500
    assert rows["AdjustPLAfterDeprOthSpecInc"] == 550
    assert rows["AmtDebPLDisallowUs36"] == 0
    assert rows["AmtDebPLDisallowUs43B"] == 0
    assert rows["DeemIncUs41"] == 0
    assert rows["IncProfDecLossAccICDSAdj"] == 0
    assert rows["DecProfIncLossAccICDSAdj"] == 0


def _presumptive_draft():
    """A minimal end-to-end ITR-3 draft with 44AD + 44ADA + 44AE presumptive businesses."""
    from app.schemas.return_draft import Presumptive44AD, Presumptive44ADA, Presumptive44AE, create_empty_draft

    draft = create_empty_draft("2026-27", "ITR-3", "new")
    draft.personal.pan = "ABCDE1234F"
    draft.personal.firstName = "Asha"
    draft.personal.surnameOrOrgName = "Sharma"
    draft.personal.dateOfBirth = "1985-01-01"
    draft.personal.flatNo = "1"
    draft.personal.localityOrArea = "Central"
    draft.personal.city = "Delhi"
    draft.personal.stateCode = "07"
    draft.personal.countryCode = "91"
    draft.personal.pinCode = "110001"
    draft.personal.mobile = "9876543210"
    draft.personal.email = "asha@example.com"
    draft.verification.place = "Delhi"
    draft.verification.date = "2026-07-31"
    draft.verification.declarationAccepted = True
    draft.businesses = [
        Presumptive44AD(id="b1", natureCode="01001", digitalReceipts=Decimal("1000000"), declaredIncome=Decimal("60000")),
        Presumptive44ADA(id="b2", natureCode="16001", grossReceipts=Decimal("500000"), declaredIncome=Decimal("250000")),
        Presumptive44AE(id="b3", natureCode="60010", declaredIncome=Decimal("40000")),
    ]
    return draft


def test_schedule_bp_presumptive_income_breakdown_reaches_json() -> None:
    """Schedule 14 fix: items 4a/35 (the presumptive-income breakdown by
    section) were both entirely hardcoded to 0 despite draft.businesses
    already carrying exactly this data, grouped by scheme."""
    from app.engine.draft_to_itr3_input import draft_to_itr3_input
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _presumptive_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    bp = document["ITR"]["ITR3"]["ITR3ScheduleBP"]["BusinessIncOthThanSpec"]
    assert bp["ProfitLossInclRefrdSec"]["ProfitLossUs44AD"] == 60000
    assert bp["ProfitLossInclRefrdSec"]["ProfitLossUs44ADA"] == 250000
    assert bp["ProfitLossInclRefrdSec"]["ProfitLossUs44AE"] == 40000
    assert bp["DeemedProfitBusUs"]["Section44AD"] == 60000
    assert bp["DeemedProfitBusUs"]["Section44ADA"] == 250000
    assert bp["DeemedProfitBusUs"]["Section44AE"] == 40000
    assert bp["DeemedProfitBusUs"]["TotDeemedProfitBusUs"] == 350000
    errors = list(_schedule_bp_validator().iter_errors(document["ITR"]["ITR3"]["ITR3ScheduleBP"]))
    assert not errors, "\n".join(e.message for e in errors)


def test_schedule_bp_presumptive_breakdown_does_not_change_total_income() -> None:
    """The presumptive-income disclosure fix must be purely a re-allocation
    across items 6/34/35/36 -- it must never change the actual income
    figures (IncChrgUnHdProftGain / GTI), which the calculator already
    computed correctly before this fix. Item 36 must exactly equal the
    calculator's own unclamped total (pgbp.non_spec_signed)."""
    from app.engine.draft_to_itr3_input import draft_to_itr3_input
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _presumptive_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    result = compute_itr3(typed_input)
    pgbp = result.schedules["pgbp"]
    document = build_itr3_json(result, typed_input)
    bp_doc = document["ITR"]["ITR3"]["ITR3ScheduleBP"]
    bp = bp_doc["BusinessIncOthThanSpec"]
    # Item 36 = item 34 + item 35viii -- must reconcile internally...
    assert bp["NetPLAftAdjBusOthThanSpec"] == bp["PLAftAdjDedBusOthThanSpec"] + bp["DeemedProfitBusUs"]["TotDeemedProfitBusUs"]
    # ...and must equal the calculator's own unclamped total exactly, proving
    # the presumptive subtraction (item 6) and re-addition (item 35) are
    # perfectly neutral, not a double-count or a silent drop.
    from app.engine.itd.common import _to_rupees
    assert bp["NetPLAftAdjBusOthThanSpec"] == _to_rupees(pgbp.non_spec_signed)
    assert bp_doc["IncChrgUnHdProftGain"] == _to_rupees(result.schedules["pgbp"].total_business_income)


def test_schedule_bp_loss_disclosed_as_negative_not_floored_to_zero() -> None:
    """Schedule 14 fix: NetPLAftAdjBusOthThanSpec/NetPLBusOthThanSpec7A7B7C
    have no official schema minimum (a regular business can genuinely make
    a loss) -- previously these were set directly from the GTI-floored
    non_spec_net_income (always >= 0), so a real business loss was silently
    disclosed as a false 0 instead of the true negative figure."""
    pgbp = PGBPResult(
        non_spec_profit_before_tax=Decimal("-20000"),
        non_spec_signed=Decimal("-20000"),
        non_spec_net_income=Decimal("0"),  # GTI-floored, as the calculator correctly does
        total_business_income=Decimal("0"),
    )
    result = ITR3Result(schedules={"pgbp": pgbp})
    typed = type("TypedInput", (), {"business_income": BusinessIncome()})()
    payload = _schedule_bp(result, typed)
    rows = payload["BusinessIncOthThanSpec"]
    assert rows["NetPLAftAdjBusOthThanSpec"] == -20000
    assert rows["NetPLBusOthThanSpec7A7B7C"] == -20000
    assert rows["PLAftAdjDedBusOthThanSpec"] == -20000
    # GTI-relevant total_business_income stays correctly floored at 0 --
    # this fix touches only the disclosure, never the actual tax computation.
    assert payload["IncChrgUnHdProftGain"] == 0
    errors = list(_schedule_bp_validator().iter_errors(payload))
    assert not errors, "\n".join(e.message for e in errors)


# ============================================================================
# Schedule 14 end-to-end closure: items 3a-3g/5a-5d/5A/7a-7g/8a/8b/19/23/
# 28/29/30/37a-38 and Part E, all previously deferred as "no data capture
# exists anywhere" -- the frontend's generic Schedule BP editor
# (ITR3ScheduleBPEditor.tsx, driven by the full 131-path official coverage
# manifest) already captures every one of these fields as a raw
# dedicated-input, matching the same pattern items 14-33 already used; this
# closure is therefore backend-only (schema + compute_pgbp + mapper +
# builder), no new frontend work.
# ============================================================================

from app.engine.schedules.business import compute as compute_pgbp


def test_pgbp_reallocation_income_and_expense_permanently_adjust_non_spec_signed() -> None:
    """Items 3a-3g (income reallocated to another head) must permanently
    REDUCE non_spec_signed -- this engine computes Salary/HP/CG/OS income
    independently from their own typed inputs, so failing to subtract this
    would double-tax it. Items 7a-7g (expenses relating to another head)
    must permanently INCREASE it back (they should never have reduced
    business income in the first place)."""
    baseline = compute_pgbp(net_profit_before_tax=Decimal("100000"))
    with_realloc = compute_pgbp(
        net_profit_before_tax=Decimal("100000"),
        reallocation_income_house_property=Decimal("30000"),
        reallocation_income_capital_gains=Decimal("5000"),
        reallocation_expense_salary=Decimal("2000"),
        reallocation_expense_other_sources=Decimal("1000"),
    )
    assert with_realloc.non_spec_signed == baseline.non_spec_signed - Decimal("30000") - Decimal("5000") + Decimal("2000") + Decimal("1000")
    assert with_realloc.non_spec_signed == Decimal("68000")


def test_pgbp_exempt_and_not_chargeable_income_reduce_non_spec_signed() -> None:
    """Items 5a/5b/5c (exempt income credited to P&L) and 5A (receipts not
    chargeable to tax at all) must reduce non_spec_signed -- neither is
    ever taxable as business income."""
    result = compute_pgbp(
        net_profit_before_tax=Decimal("100000"),
        exempt_income_firm_share=Decimal("10000"),
        exempt_income_aop_boi_share=Decimal("5000"),
        exempt_income_other=Decimal("2000"),
        income_not_chargeable=Decimal("3000"),
    )
    assert result.non_spec_signed == Decimal("100000") - Decimal("10000") - Decimal("5000") - Decimal("2000") - Decimal("3000")
    assert result.non_spec_signed == Decimal("80000")


def test_pgbp_expense_relating_to_exempt_income_added_back() -> None:
    """Items 8a/8b (expenses relating to exempt income, 8b disallowed u/s
    14A) are non-deductible and must be added back."""
    result = compute_pgbp(
        net_profit_before_tax=Decimal("50000"),
        expense_relating_to_exempt_income=Decimal("1000"),
        expense_exempt_income_disallowed_us14a=Decimal("500"),
    )
    assert result.non_spec_signed == Decimal("51500")


def test_pgbp_new_disallowances_and_deductions_flow_into_non_spec_signed() -> None:
    """Items 19 (MSME interest disallowance), 23 (other s.28-44DA addition),
    28 (s.35 excess deduction), 29/30 (s.40/s.43B now-allowable) all
    genuinely change taxable business income, exactly like their
    already-shipped siblings (disallowance_us36 etc)."""
    result = compute_pgbp(
        net_profit_before_tax=Decimal("100000"),
        msme_interest_disallowance=Decimal("4000"),
        other_addition_28_to_44da=Decimal("1000"),
        section35_excess_deduction=Decimal("2000"),
        section40_now_allowable=Decimal("1500"),
        section43b_now_allowable=Decimal("500"),
    )
    assert result.non_spec_signed == Decimal("100000") + Decimal("4000") + Decimal("1000") - Decimal("2000") - Decimal("1500") - Decimal("500")
    assert result.non_spec_signed == Decimal("101000")


def test_pgbp_rule_7_8_composite_income_reduces_taxable_by_agricultural_balance() -> None:
    """Item 4b's raw composite-activity profit is subtracted; the
    taxpayer's own Rule 7A-adjusted taxable figure (37b) is added back on
    top of item 36. The net effect on non_spec_signed is exactly
    -(item38), the agricultural balance -- proving the engine applies the
    statutory partial-agricultural-exemption, not the raw profit."""
    baseline = compute_pgbp(net_profit_before_tax=Decimal("500000"))
    composite = compute_pgbp(
        net_profit_before_tax=Decimal("500000"),
        rule7a_profit=Decimal("200000"),
        rule7a_deemed_income=Decimal("120000"),  # only 60% taxable under Rule 7A
    )
    assert composite.rule_7_8_agricultural_balance == Decimal("80000")
    assert composite.non_spec_signed == baseline.non_spec_signed - Decimal("80000")
    assert composite.non_spec_signed == Decimal("420000")
    # No composite activity at all -> zero agricultural balance, A37 == 36.
    assert baseline.rule_7_8_agricultural_balance == Decimal("0")
    assert baseline.non_spec_signed == baseline.non_spec_item36_signed


def test_pgbp_part_e_absorbs_non_spec_loss_into_speculative_then_specified_income() -> None:
    """Part E: a non-speculative business LOSS is set off first against
    speculative business income, then against whatever remains of
    specified business income -- matching the official form's own row
    ii-then-iii order."""
    result = compute_pgbp(
        net_profit_before_tax=Decimal("-100000"),
        speculative_net_pl=Decimal("40000"),
        specified_net_pl=Decimal("50000"),
    )
    assert result.non_spec_signed == Decimal("-100000")
    assert result.part_e_loss_to_set_off == Decimal("100000")
    assert result.part_e_speculative_setoff == Decimal("40000")
    assert result.part_e_speculative_income_after_setoff == Decimal("0")
    assert result.part_e_specified_setoff == Decimal("50000")  # remaining 60000 loss, capped at 50000 income
    assert result.part_e_specified_income_after_setoff == Decimal("0")
    assert result.part_e_total_setoff == Decimal("90000")
    assert result.part_e_loss_remaining == Decimal("10000")
    # Item D is a pure signed sum regardless of the intra-head bookkeeping.
    assert result.total_business_income == max(Decimal("0"), Decimal("-100000") + Decimal("40000") + Decimal("50000"))
    assert result.total_business_income == Decimal("0")


def test_pgbp_total_business_income_nets_loss_against_other_sub_heads_not_discarded() -> None:
    """Regression for the pre-fix bug: total_business_income used to floor
    EACH sub-head at 0 independently before summing, silently discarding a
    real non-speculative loss that speculative/specified income should
    have absorbed. Loss -30000, speculative income +50000 -> item D must
    be 20000, not 50000 (the old buggy behaviour)."""
    result = compute_pgbp(
        net_profit_before_tax=Decimal("-30000"),
        speculative_net_pl=Decimal("50000"),
    )
    assert result.total_business_income == Decimal("20000")
    assert result.part_e_loss_remaining == Decimal("0")


def test_pgbp_part_e_no_op_when_no_speculative_or_specified_income_available() -> None:
    """The common real-world case (a single regular business, no
    speculative/specified income) must be unaffected by Part E -- the full
    raw loss flows through as part_e_loss_remaining, exactly matching the
    pre-fix, pre-Part-E behaviour."""
    result = compute_pgbp(net_profit_before_tax=Decimal("-15000"))
    assert result.part_e_loss_remaining == Decimal("15000")
    assert result.part_e_total_setoff == Decimal("0")
    assert result.non_spec_signed == Decimal("-15000")


def test_schedule_bp_reallocation_and_exempt_income_reach_json_and_reduce_disclosed_total() -> None:
    """Items 3a-3g/5a-5c/5A/7a-7g/8a/8b all reach their exact official JSON
    fields and correctly move item 6/9/10/13/34/36."""
    business = BusinessIncome(
        net_profit_before_tax=Decimal("200000"),
        reallocation_income_house_property=Decimal("20000"),
        reallocation_income_dividend=Decimal("3000"),
        reallocation_income_other_than_dividend=Decimal("1000"),
        reallocation_income_other_sources=Decimal("4000"),
        reallocation_expense_capital_gains=Decimal("6000"),
        exempt_income_firm_share=Decimal("8000"),
        exempt_income_other=Decimal("2000"),
        income_not_chargeable=Decimal("1000"),
        expense_relating_to_exempt_income=Decimal("500"),
        expense_exempt_income_disallowed_us14a=Decimal("300"),
    )
    pgbp = compute_pgbp(
        net_profit_before_tax=business.net_profit_before_tax,
        reallocation_income_house_property=business.reallocation_income_house_property,
        reallocation_income_other_sources=business.reallocation_income_other_sources,
        reallocation_expense_capital_gains=business.reallocation_expense_capital_gains,
        exempt_income_firm_share=business.exempt_income_firm_share,
        exempt_income_other=business.exempt_income_other,
        income_not_chargeable=business.income_not_chargeable,
        expense_relating_to_exempt_income=business.expense_relating_to_exempt_income,
        expense_exempt_income_disallowed_us14a=business.expense_exempt_income_disallowed_us14a,
    )
    result = ITR3Result(schedules={"pgbp": pgbp})
    typed = type("TypedInput", (), {"business_income": business})()
    payload = _schedule_bp(result, typed)
    rows = payload["BusinessIncOthThanSpec"]
    assert rows["IncRecCredPLOthHeadDtls"]["HouseProperty"] == 20000
    assert rows["IncRecCredPLOthHeadDtls"]["Dividend"] == 3000
    assert rows["IncRecCredPLOthHeadDtls"]["OtherThanDividend"] == 1000
    assert rows["IncRecCredPLOthHeadDtls"]["OtherSources"] == 4000
    assert rows["ExpDebToPLOthHeadDtls"]["CapitalGains"] == 6000
    assert rows["IncCredPL"]["FirmShareInc"] == 8000
    assert rows["IncCredPL"]["OthExempInc"] == 2000
    assert rows["IncCredPL"]["TotExempIncPL"] == 10000
    assert rows["IncCredPLNotChargable"] == 1000
    assert rows["ExpDebToPLExemptInc"] == 500
    assert rows["ExpDebToPLExemptIncDisAllwUs14A"] == 300
    # Item 6 = 200000 - 20000(3b) - 4000(3d) - 8000(5a) - 2000(5c) - 1000(5A)
    #        (3di/3dii are informational only, not separately subtracted)
    assert rows["BalancePLOthThanSpecBus"] == Decimal("165000")
    # Item 9 = 6000(7c) + 500(8a) + 300(8b)
    assert rows["TotExpDebPL"] == Decimal("6800")
    assert rows["AdjustedPLOthThanSpecBus"] == Decimal("171800")
    assert rows["NetPLAftAdjBusOthThanSpec"] == pgbp.non_spec_item36_signed
    from app.engine.itd.common import _to_rupees
    assert rows["NetPLAftAdjBusOthThanSpec"] == _to_rupees(pgbp.non_spec_item36_signed)
    assert rows["NetPLBusOthThanSpec7A7B7C"] == _to_rupees(pgbp.non_spec_signed)
    errors = list(_schedule_bp_validator().iter_errors(payload))
    assert not errors, "\n".join(e.message for e in errors)


def test_schedule_bp_new_disallowance_and_deduction_items_reach_json() -> None:
    """Items 19/23/28/29/30 reach their exact official JSON fields."""
    business = BusinessIncome(
        net_profit_before_tax=Decimal("100000"),
        msme_interest_disallowance=Decimal("4000"),
        other_addition_28_to_44da=Decimal("1000"),
        section35_excess_deduction=Decimal("2000"),
        section40_now_allowable=Decimal("1500"),
        section43b_now_allowable=Decimal("500"),
    )
    pgbp = compute_pgbp(
        net_profit_before_tax=business.net_profit_before_tax,
        msme_interest_disallowance=business.msme_interest_disallowance,
        other_addition_28_to_44da=business.other_addition_28_to_44da,
        section35_excess_deduction=business.section35_excess_deduction,
        section40_now_allowable=business.section40_now_allowable,
        section43b_now_allowable=business.section43b_now_allowable,
    )
    result = ITR3Result(schedules={"pgbp": pgbp})
    typed = type("TypedInput", (), {"business_income": business})()
    payload = _schedule_bp(result, typed)
    rows = payload["BusinessIncOthThanSpec"]
    assert rows["InterestDisAllowUs23SMEAct"] == 4000
    assert rows["OthItemDisallowUs28To44DA"] == 1000
    assert rows["DebPLUs35ExcessAmt"] == 2000
    assert rows["AmtDisallUs40NowAllow"] == 1500
    assert rows["AmtDisallUs43BNowAllow"] == 500
    assert rows["NetPLAftAdjBusOthThanSpec"] == _to_rupees_local(pgbp.non_spec_signed)
    errors = list(_schedule_bp_validator().iter_errors(payload))
    assert not errors, "\n".join(e.message for e in errors)


def _to_rupees_local(value: Decimal) -> int:
    from app.engine.itd.common import _to_rupees as _f
    return _f(value)


def test_schedule_bp_rule_7_8_composite_income_reaches_json_and_a37_differs_from_36() -> None:
    """Items 4b/37a-37e/38 reach their exact official JSON fields, and
    NetPLBusOthThanSpec7A7B7C (A37) genuinely differs from
    NetPLAftAdjBusOthThanSpec (36) when a composite activity is declared,
    unlike the pre-fix code where they were always forced equal."""
    business = BusinessIncome(
        net_profit_before_tax=Decimal("500000"),
        rule7a_profit=Decimal("200000"),
        rule7a_deemed_income=Decimal("120000"),
    )
    pgbp = compute_pgbp(
        net_profit_before_tax=business.net_profit_before_tax,
        rule7a_profit=business.rule7a_profit,
        rule7a_deemed_income=business.rule7a_deemed_income,
    )
    result = ITR3Result(schedules={"pgbp": pgbp})
    typed = type("TypedInput", (), {"business_income": business})()
    payload = _schedule_bp(result, typed)
    rows = payload["BusinessIncOthThanSpec"]
    assert rows["TotalProfitFrmActCvrd"] == 200000
    assert rows["ProfitFrmActCvrd"]["ProfitFrmActCvrdUndrRule7A"] == 200000
    assert rows["DeemedChrgblIncUndrRule7A"] == 120000
    assert rows["IncomeOtherThanRule"] == rows["NetPLAftAdjBusOthThanSpec"]
    assert rows["NetPLBusOthThanSpec7A7B7C"] == rows["NetPLAftAdjBusOthThanSpec"] + 120000
    assert rows["BalIncDeemedFrmAgri"] == 80000
    assert rows["NetPLBusOthThanSpec7A7B7C"] != rows["NetPLAftAdjBusOthThanSpec"]
    errors = list(_schedule_bp_validator().iter_errors(payload))
    assert not errors, "\n".join(e.message for e in errors)


def test_schedule_bp_part_e_populates_intra_head_setoff_table() -> None:
    """Part E (BusSetoffCurrYr) was hardcoded all-zero; it must now show
    the real intra-head set-off of a regular business loss against
    speculative/specified business income."""
    business = BusinessIncome(
        net_profit_before_tax=Decimal("-100000"),
        speculative_net_pl=Decimal("40000"),
        specified_business_net_pl=Decimal("50000"),
    )
    pgbp = compute_pgbp(
        net_profit_before_tax=business.net_profit_before_tax,
        speculative_net_pl=business.speculative_net_pl,
        specified_net_pl=business.specified_business_net_pl,
    )
    result = ITR3Result(schedules={"pgbp": pgbp})
    typed = type("TypedInput", (), {"business_income": business})()
    payload = _schedule_bp(result, typed)
    setoff = payload["BusSetoffCurrYr"]
    assert setoff["LossSetOffOnBusLoss"] == -100000
    assert setoff["SpeculativeInc"]["BusLossSetoff"] == 40000
    assert setoff["SpeculativeInc"]["IncOfCurYrUnderThatHead"] == 40000
    assert setoff["SpeculativeInc"]["IncOfCurYrAfterSetOff"] == 0
    assert setoff["SpecifiedInc"]["BusLossSetoff"] == 50000
    assert setoff["SpecifiedInc"]["IncOfCurYrUnderThatHead"] == 50000
    assert setoff["SpecifiedInc"]["IncOfCurYrAfterSetOff"] == 0
    assert setoff["TotLossSetOffOnBus"] == 90000
    assert setoff["LossRemainSetOffOnBus"] == 10000
    errors = list(_schedule_bp_validator().iter_errors(payload))
    assert not errors, "\n".join(e.message for e in errors)


def test_schedule_bp_speculative_and_specified_disclose_signed_value_and_additions() -> None:
    """SpecBusinessInc/SpecifiedBusinessInc disclose the genuinely signed
    B42/C48 figures (the official schema places no minimum on either),
    and their own s.28-44DA additions/deductions -- both were previously
    hardcoded to a floored/zeroed value despite the calculator already
    computing them correctly."""
    business = BusinessIncome(
        speculative_net_pl=Decimal("-5000"),
        speculative_additions=Decimal("1000"),
        specified_business_net_pl=Decimal("8000"),
        specified_business_deductions=Decimal("2000"),
    )
    pgbp = compute_pgbp(
        speculative_net_pl=business.speculative_net_pl,
        speculative_additions=business.speculative_additions,
        specified_net_pl=business.specified_business_net_pl,
        specified_deductions=business.specified_business_deductions,
    )
    result = ITR3Result(schedules={"pgbp": pgbp})
    typed = type("TypedInput", (), {"business_income": business})()
    payload = _schedule_bp(result, typed)
    assert payload["SpecBusinessInc"]["NetPLFrmSpecBus"] == -4000
    assert payload["SpecBusinessInc"]["AdditionUs28to44DA"] == 1000
    assert payload["SpecBusinessInc"]["AdjustedPLFrmSpecuBus"] == -4000
    assert payload["SpecifiedBusinessInc"]["NetPLFrmSpecifiedBus"] == 6000
    assert payload["SpecifiedBusinessInc"]["DedSec28to44DAOTDedSec35AD"] == 2000
    assert payload["SpecifiedBusinessInc"]["PLFrmSpecifiedBus"] == 6000
    errors = list(_schedule_bp_validator().iter_errors(payload))
    assert not errors, "\n".join(e.message for e in errors)


def test_draft_to_itr3_input_maps_reallocation_and_new_disallowance_fields() -> None:
    """Mapper-level proof: the raw Schedule BP workspace JSON (exactly what
    the frontend's generic ITR3ScheduleBPEditor writes, keyed by official
    field names) reaches BusinessIncome's new typed fields, including the
    nested IncRecCredPLOthHeadDtls/IncCredPL/ProfitFrmActCvrd objects."""
    from app.engine.draft_to_itr3_input import draft_to_itr3_input

    draft = _presumptive_draft()
    draft.itr3BusinessWorkspace.core["ITR3ScheduleBP"] = {
        "BusinessIncOthThanSpec": {
            "IncRecCredPLOthHeadDtls": {"HouseProperty": 15000, "OtherSources": 2500},
            "ExpDebToPLOthHeadDtls": {"CapitalGains": 7000},
            "IncCredPL": {"FirmShareInc": 9000, "AOPBOISharInc": 0, "OthExempInc": 1000, "TotExempIncPL": 10000},
            "IncCredPLNotChargable": 500,
            "ExpDebToPLExemptInc": 200,
            "ExpDebToPLExemptIncDisAllwUs14A": 100,
            "InterestDisAllowUs23SMEAct": 3000,
            "OthItemDisallowUs28To44DA": 1200,
            "DebPLUs35ExcessAmt": 800,
            "AmtDisallUs40NowAllow": 600,
            "AmtDisallUs43BNowAllow": 400,
            "ProfitFrmActCvrd": {"ProfitFrmActCvrdUndrRule7A": 50000},
            "ChrgblIncUndrRule7": 0,
            "DeemedChrgblIncUndrRule7A": 30000,
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    bi = typed_input.business_income
    assert bi.reallocation_income_house_property == Decimal("15000")
    assert bi.reallocation_income_other_sources == Decimal("2500")
    assert bi.reallocation_expense_capital_gains == Decimal("7000")
    assert bi.exempt_income_firm_share == Decimal("9000")
    assert bi.exempt_income_other == Decimal("1000")
    assert bi.income_not_chargeable == Decimal("500")
    assert bi.expense_relating_to_exempt_income == Decimal("200")
    assert bi.expense_exempt_income_disallowed_us14a == Decimal("100")
    assert bi.msme_interest_disallowance == Decimal("3000")
    assert bi.other_addition_28_to_44da == Decimal("1200")
    assert bi.section35_excess_deduction == Decimal("800")
    assert bi.section40_now_allowable == Decimal("600")
    assert bi.section43b_now_allowable == Decimal("400")
    assert bi.rule7a_profit == Decimal("50000")
    assert bi.rule7a_deemed_income == Decimal("30000")


from app.schemas.itr3 import (
    ITR3Schedule10AA,
    ITR3Schedule10AAContainer,
    ITR3Schedule10AADetail,
    ITR3Schedule10AAUndertaking,
    ITR3Schedule10AAUnit,
    ITR3Schedule80IA,
    ITR3Schedule80IB,
    ITR3Schedule80IC,
    ITR3Schedule80ICNorthEast,
    ITR3Schedule80RA,
    ITR3Schedule80RADonation,
    ITR3Schedule80RAAddress,
    ITR3Section80Activity,
    ITR3Section80DeductionAmount,
)


def _definition_validator(name: str) -> Draft4Validator:
    """Create a validator retaining the official definitions registry."""
    full = get_itr3_schema_validator().schema
    definition = dict(full["definitions"][name])
    definition["definitions"] = full["definitions"]
    return Draft4Validator(definition)


def _activity(code: str = "POWER") -> ITR3Section80Activity:
    """Create one explicit section-80 activity row."""
    return ITR3Section80Activity(
        Sch80LocOrDescCode=code,
        Sch80DeductAmtDtls=[ITR3Section80DeductionAmount(DeductAmountSec80=Decimal("100"))],
    )


def test_business_deduction_schedules_serialize_with_official_names() -> None:
    """Typed business deductions retain exact official keys and validate."""
    ia = ITR3Schedule80IA(DeductUs80_IA_4_iv=_activity(), TotSchedule80_IA=100)
    ib = ITR3Schedule80IB(
        DeductMinOilUs80_IB_9_Und=_activity("COMM_PROD"),
        DeductHousUs80_IB_10_Und=_activity("HOUSING_PROJECT"),
        DeductFruitVegUs80_IB_11A_Und=_activity("FRIUTS_VEGTBLE"),
        DeductFoodGrainUs80_IB_11A_Und=_activity("STOR_TRANS"),
        TotSchedule80_IB=400,
    )
    ic = ITR3Schedule80IC(
        DeductInNorthEast=ITR3Schedule80ICNorthEast(
            Assam_Und=_activity("INDSRTL_ASSAM"),
            ArunachalPradesh_Und=_activity("INDSRTL_ARUNPRADESH"),
            Manipur_Und=_activity("INDSRTL_MANIPUR"),
            Mizoram_Und=_activity("INDSRTL_MIZORAM"),
            Meghalaya_Und=_activity("INDSRTL_MEGHALAYA"),
            Nagaland_Und=_activity("INDSRTL_NAGALND"),
            Tripura_Und=_activity("INDSRTL_TRIPURA"),
            Sikkim_Und=_activity("INDSRTL_SIKKIM"),
            TotDeductInNorthEast=800,
        ),
        TotSchedule80_IC=800,
    )
    for name, model in (("Schedule80_IA", ia), ("Schedule80_IB", ib), ("Schedule80_IC", ic)):
        payload = _serialize_schedule_model(model)
        assert not list(_definition_validator(name).iter_errors(payload))


def test_schedule_80ra_and_10aa_validate() -> None:
    """Typed 80RA donation and 10AA undertaking sources validate."""
    ra = ITR3Schedule80RA(
        DonationDtlsRsrchAssctn=[ITR3Schedule80RADonation(
            NameOfDonee="Research Association",
            AddressDetail=ITR3Schedule80RAAddress(AddrDetail="1 Road", CityOrTownOrDistrict="City", StateCode="07", PinCode=444001),
            DoneePAN="AAAAA1234A", DonationAmtCash=100, DonationAmt=100, EligibleDonationAmt=100,
        )],
        TotalDonationAmtCash80RA=100,
        TotalDonationsUs80RA=100,
        TotalEligibleDonationAmt80RA=100,
    )
    aa = ITR3Schedule10AA(DeductSEZ=ITR3Schedule10AAContainer(
        DedUs10Detail=ITR3Schedule10AADetail(
            Undertaking=ITR3Schedule10AAUndertaking(DedFromUndertakingWithAy=[
                ITR3Schedule10AAUnit(AssmtYrUnit="2022-23", DedUs10Sub=100)
            ]),
            TotalDedUs10Sub=100,
        )
    ))
    assert not list(_definition_validator("Schedule80RA").iter_errors(_serialize_schedule_model(ra)))
    assert not list(_definition_validator("Schedule10AA").iter_errors(_serialize_schedule_model(aa)))


def test_partb_ti_prof_gain_specified_bus_reflects_real_section_35ad_income() -> None:
    """CORRECTION (2026-09-19): `_partb_ti()` read a non-existent PGBPResult
    attribute (`specified_business_net_income`) instead of the real field
    (`specified_net_income`) -- the `getattr` fallback silently discarded
    any real section 35AD specified-business income, always disclosing
    `ProfGainSpecifiedBus`/its contribution to `TotProfBusGain` as zero.
    Found incidentally while re-verifying Schedule VDA's Part B-TI wiring,
    unrelated to VDA/115BBH itself."""
    pgbp = compute_pgbp(net_profit_before_tax=Decimal("0"), specified_net_pl=Decimal("250000"))
    assert pgbp.specified_net_income == Decimal("250000")
    result = ITR3Result(schedules={"pgbp": pgbp}, business_income=Decimal("250000"))
    payload = _partb_ti(result)
    assert payload["ProfBusGain"]["ProfGainSpecifiedBus"] == 250000
    assert payload["ProfBusGain"]["TotProfBusGain"] == 250000
