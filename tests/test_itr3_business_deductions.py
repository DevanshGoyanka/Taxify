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
        non_spec_net_income=Decimal("1000"),
        total_business_income=Decimal("1000"),
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
    assert business_rows["AdjustedPLOthThanSpecBus"] == 1040
    assert business_rows["TotAfterAddToPLDeprOthSpecInc"] == 1363
    assert business_rows["TotDeductionAmts"] == 57
    assert business_rows["PLAftAdjDedBusOthThanSpec"] == 1306
    assert additions == 323
    assert deductions == 57


def test_schedule_bp_does_not_infer_untyped_adjustments_from_pgbp() -> None:
    """Omitted typed adjustments stay zero even when the calculator has a total."""
    pgbp = PGBPResult(
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
    assert rows["AdjustedPLOthThanSpecBus"] == 550
    assert rows["AmtDebPLDisallowUs36"] == 0
    assert rows["AmtDebPLDisallowUs43B"] == 0
    assert rows["DeemIncUs41"] == 0
    assert rows["IncProfDecLossAccICDSAdj"] == 0
    assert rows["DecProfIncLossAccICDSAdj"] == 0
    assert rows["PLAftAdjDedBusOthThanSpec"] == 550


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
