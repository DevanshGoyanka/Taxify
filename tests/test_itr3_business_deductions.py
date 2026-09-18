"""Schema tests for typed ITR-3 business deduction schedules."""

from __future__ import annotations

from decimal import Decimal

from jsonschema import Draft4Validator

from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.engine.calculators.itr3 import ITR3Result
from app.engine.schedules.business import PGBPResult
from app.engine.itd.itr3 import _schedule_bp, _serialize_schedule_model
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
