"""Tests for ITR-3 Schedule DPM/DOA/DEP/DCG (tracker rows #15-18).

These four schedules share one typed source (``ITR3DepreciationSchedules``)
and one root cause: the frontend's real, working editor
(``ITR3BusinessAuxiliaryManager.tsx``) writes into
``draft.itr3BusinessWorkspace.auxiliary["ScheduleDPM"/"ScheduleDOA"]``, but
the mapper used to read only the never-populated typed field
``draft.itr3BusinessWorkspace.depreciationSchedules`` -- a pure frontend
dead end. Schedule DEP/DCG's own summary figures are derived here from the
mapped DPM/DOA block totals, since the frontend never computes them either.

A second, independent bug was found while stress-testing this fix with
more realistic partial input (not every field of a block filled in): the
frontend only ever writes a block's DERIVED fields once the block already
exists, never the raw-input fields the taxpayer leaves genuinely blank
(no additions, no half-rate depreciation this year) -- constructing the
typed model directly from that subset raised a hard Pydantic
ValidationError. Every leaf field is now defaulted to 0 when absent,
matching the official schema's own per-field defaults.
"""

from __future__ import annotations

from decimal import Decimal

from jsonschema import Draft4Validator

from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.engine.draft_to_itr3_input import draft_to_itr3_input, _depreciation_schedules
from app.engine.calculators.itr3 import compute as compute_itr3
from app.engine.itd.itr3 import build_itr3_json


def _schedule_validator(name: str) -> Draft4Validator:
    full = get_itr3_schema_validator().schema
    definition = dict(full["definitions"][name])
    definition["definitions"] = full["definitions"]
    return Draft4Validator(definition)


def _minimal_draft():
    from app.schemas.return_draft import Presumptive44AD, create_empty_draft

    draft = create_empty_draft("2026-27", "ITR-3", "new")
    draft.personal.pan = "ABCDE1234F"
    draft.personal.firstName = "Ravi"
    draft.personal.surnameOrOrgName = "Kumar"
    draft.personal.dateOfBirth = "1980-01-01"
    draft.personal.flatNo = "1"
    draft.personal.localityOrArea = "Central"
    draft.personal.city = "Delhi"
    draft.personal.stateCode = "07"
    draft.personal.countryCode = "91"
    draft.personal.pinCode = "110001"
    draft.personal.mobile = "9876543210"
    draft.personal.email = "ravi@example.com"
    draft.verification.place = "Delhi"
    draft.verification.date = "2026-07-31"
    draft.verification.declarationAccepted = True
    draft.businesses = [
        Presumptive44AD(id="b1", natureCode="01001", digitalReceipts=Decimal("1000000"), declaredIncome=Decimal("60000")),
    ]
    return draft


def _dpm_rate_block(wdv_first_day: int, additions_gt180: int = 0, cap_gain: int = 0) -> dict:
    """A minimal-but-real Rate15/30/40 block, matching what the frontend's
    own recompute() derives from these raw facts."""
    full_rate_depr_amt = wdv_first_day + additions_gt180
    total_depreciation = int(full_rate_depr_amt * 0.15)
    net_agg = total_depreciation
    wdv_last_day = full_rate_depr_amt - total_depreciation
    return {
        "DepreciationDetail": {
            "WDVFirstDay": wdv_first_day, "Total": wdv_first_day,
            "AdditionsGrThan180Days": additions_gt180, "RealizationTotalPeriod": 0,
            "FullRateDeprAmt": full_rate_depr_amt,
            "AdditionsLessThan180Days": 0, "RealizationPeriodLessThan180days": 0, "HalfRateDeprAmt": 0,
            "DepreciationAtFullRate": total_depreciation, "DepreciationAtHalfRate": 0,
            "TotalDepreciation": total_depreciation, "DepDisAllowUs38_2": 0,
            "NetAggregateDepreciation": net_agg, "ProportionateAggDepreciation": 0,
            "ExpdrOnTrforSaleAsset": 0, "CapGainUs50": cap_gain, "WDVLastDay": wdv_last_day,
        }
    }


def _zero_dpm_rate_block() -> dict:
    """A block whose every field is explicitly 0 -- distinct from a
    genuinely untouched block (which the frontend leaves absent
    entirely, see the realistic-partial-input tests below)."""
    return _dpm_rate_block(0)


def test_dpm_rate_detail_omits_all_zero_untouched_blocks() -> None:
    """An explicitly all-zero rate block (every field present, every value
    0 -- e.g. a stale block a taxpayer cleared out) must not be mistaken
    for a real, in-use one."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDPM"] = {
        "PlantMachinery": {
            "Rate15": _dpm_rate_block(100000, additions_gt180=20000, cap_gain=0),
            "Rate30": _zero_dpm_rate_block(),
            "Rate40": _zero_dpm_rate_block(),
            "Rate45": _zero_dpm_rate_block(),
        }
    }
    schedules = _depreciation_schedules(draft)
    assert schedules is not None
    assert schedules.schedule_dpm is not None
    pm = schedules.schedule_dpm.PlantMachinery
    assert pm.Rate15 is not None
    assert pm.Rate30 is None
    assert pm.Rate40 is None
    assert pm.Rate45 is None
    assert pm.Rate15.DepreciationDetail.WDVFirstDay == Decimal("100000")


def test_depreciation_schedules_none_when_nothing_entered() -> None:
    draft = _minimal_draft()
    assert _depreciation_schedules(draft) is None


def test_schedule_dep_summary_derived_from_dpm_doa_net_aggregate_depreciation() -> None:
    """Schedule DEP item 1a = Schedule DPM item 17(i), the 15% block's own
    NetAggregateDepreciation -- not computed anywhere on the frontend, so
    the mapper itself must derive it."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDPM"] = {
        "PlantMachinery": {
            "Rate15": _dpm_rate_block(100000, additions_gt180=0, cap_gain=0),
            "Rate30": _dpm_rate_block(50000, additions_gt180=0, cap_gain=0),
        }
    }
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDOA"] = {
        "Building": {"Rate10": _dpm_rate_block(200000, additions_gt180=0, cap_gain=0)},
    }
    schedules = _depreciation_schedules(draft)
    dep = schedules.schedule_dep.SummaryFromDeprSch
    assert dep.PlantMachinerySummary.DeprBlockTot15Percent == Decimal("15000")  # 100000 * 15%
    assert dep.PlantMachinerySummary.DeprBlockTot30Percent == Decimal("7500")   # 50000 * 15% (helper always uses 15%, see below)
    assert dep.PlantMachinerySummary.TotPlntMach == Decimal("22500")
    assert dep.BuildingSummary.DeprBlockTot10Percent == Decimal("30000")        # 200000 * 15%
    assert dep.BuildingSummary.TotBuildng == Decimal("30000")
    assert dep.TotalDepreciation == Decimal("52500")


def test_schedule_dcg_summary_derived_from_dpm_doa_cap_gain_us50() -> None:
    """Schedule DCG item 1a = Schedule DPM item 20(i), the 15% block's own
    CapGainUs50 -- a distinct figure from NetAggregateDepreciation."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDPM"] = {
        "PlantMachinery": {
            "Rate15": _dpm_rate_block(100000, additions_gt180=0, cap_gain=12000),
        }
    }
    schedules = _depreciation_schedules(draft)
    dcg = schedules.schedule_dcg.SummaryFromDeprSchCG
    assert dcg.PlantMachinerySummaryCG.DeprBlockTot15Percent == Decimal("12000")
    assert dcg.PlantMachinerySummaryCG.TotPlntMach == Decimal("12000")
    assert dcg.TotalDepreciation == Decimal("12000")
    # NetAggregateDepreciation and CapGainUs50 must not be confused with
    # each other even though DEP and DCG reuse the same field names.
    dep = schedules.schedule_dep.SummaryFromDeprSch
    assert dep.PlantMachinerySummary.DeprBlockTot15Percent == Decimal("15000")


def test_doa_land_furniture_intangible_ships_all_reach_typed_model() -> None:
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDOA"] = {
        "Land": {"DepreciationDetail": {"WDVFirstDay": 500000, "WDVLastDay": 500000}},
        "FurnitureFittings": {"Rate10": _dpm_rate_block(40000, cap_gain=0)},
        "IntangibleAssets": {"Rate25": _dpm_rate_block(80000, cap_gain=0)},
        "Ships": {"Rate20": _dpm_rate_block(1000000, cap_gain=5000)},
    }
    schedules = _depreciation_schedules(draft)
    doa = schedules.schedule_doa
    assert doa.Land.DepreciationDetail.WDVFirstDay == Decimal("500000")
    assert doa.FurnitureFittings.Rate10.DepreciationDetail.WDVFirstDay == Decimal("40000")
    assert doa.IntangibleAssets.Rate25.DepreciationDetail.WDVFirstDay == Decimal("80000")
    assert doa.Ships.Rate20.DepreciationDetail.CapGainUs50 == Decimal("5000")
    dep = schedules.schedule_dep.SummaryFromDeprSch
    assert dep.FurnitureSummary == Decimal("6000")   # 40000 * 15%
    assert dep.IntangibleAssetSummary == Decimal("12000")  # 80000 * 15%
    dcg = schedules.schedule_dcg.SummaryFromDeprSchCG
    assert dcg.ShipsSummary == Decimal("5000")


def test_schedule_dpm_doa_dep_dcg_reach_json_and_validate_against_official_schema() -> None:
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDPM"] = {
        "PlantMachinery": {"Rate15": _dpm_rate_block(100000, additions_gt180=20000, cap_gain=0)},
    }
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDOA"] = {
        "Building": {"Rate10": _dpm_rate_block(200000, cap_gain=0)},
    }
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    for name in ("ScheduleDPM", "ScheduleDOA", "ScheduleDEP", "ScheduleDCG"):
        assert name in itr3_doc, f"{name} missing from the generated document"
        errors = list(_schedule_validator(name).iter_errors(itr3_doc[name]))
        assert not errors, f"{name}: " + "\n".join(e.message for e in errors)
    assert itr3_doc["ScheduleDPM"]["PlantMachinery"]["Rate15"]["DepreciationDetail"]["WDVFirstDay"] == 100000
    assert "Rate30" not in itr3_doc["ScheduleDPM"]["PlantMachinery"]
    assert itr3_doc["ScheduleDEP"]["SummaryFromDeprSch"]["TotalDepreciation"] == 48000  # (120000+200000)*15%


def test_depreciation_schedules_absent_when_no_real_data_entered() -> None:
    """A taxpayer with no depreciable assets at all must not see any of
    these four schedules in the generated JSON (no zero-filled stubs)."""
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    for name in ("ScheduleDPM", "ScheduleDOA", "ScheduleDEP", "ScheduleDCG"):
        assert name not in itr3_doc


def test_schedule_dcg_total_depreciation_reaches_capital_gains_computation() -> None:
    """Schedule 18's own tracker note ("Only TotalDepreciation read, for
    deemed-STCG figure") pointed at a real consuming call
    (calculators/itr3.py adds dcg_schedule.SummaryFromDeprSchCG.
    TotalDepreciation into stcg_other) that was silently always-zero
    because depreciation_schedules was never populated. This proves the
    fix reaches the actual capital-gains computation, not just disclosure."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDPM"] = {
        "PlantMachinery": {"Rate15": _dpm_rate_block(100000, cap_gain=25000)},
    }
    typed_input, _ = draft_to_itr3_input(draft)
    result = compute_itr3(typed_input)
    assert result.capital_gains_income >= Decimal("25000")


def _realistic_partial_block(wdv_first_day: int) -> dict:
    """What a REAL taxpayer interaction actually produces: only
    WDVFirstDay plus the frontend's own derived/readonly fields
    (Total/FullRateDeprAmt/TotalDepreciation/NetAggregateDepreciation/
    WDVLastDay), with every other raw-input field (additions,
    realizations, half-rate figures, DepreciationAtFullRate/HalfRate,
    section-38(2) disallowance, capital gain) genuinely left untouched --
    absent from the dict entirely, not typed as an explicit 0. The
    frontend's recompute() only ever assigns the handful of fields it
    itself derives; it never back-fills the rest."""
    return {"DepreciationDetail": {
        "WDVFirstDay": wdv_first_day, "Total": wdv_first_day,
        "FullRateDeprAmt": wdv_first_day, "TotalDepreciation": 0,
        "NetAggregateDepreciation": 0, "WDVLastDay": wdv_first_day,
    }}


def test_realistic_partial_block_with_untouched_fields_still_validates() -> None:
    """Regression: constructing the typed model directly from whatever
    subset of fields the frontend happened to send raised a hard Pydantic
    ValidationError for this entirely ordinary case (a block with no
    additions/realizations/half-rate depreciation this year, correctly
    left blank rather than typed as "0") -- every required leaf field
    must default to 0 when genuinely absent, matching the official
    schema's own per-field default."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDPM"] = {
        "PlantMachinery": {"Rate15": _realistic_partial_block(100000)},
    }
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDOA"] = {
        "Land": {"DepreciationDetail": {"WDVFirstDay": 1000000}},  # WDVLastDay never typed
        "FurnitureFittings": {"Rate10": _realistic_partial_block(40000)},
    }
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    for name in ("ScheduleDPM", "ScheduleDOA", "ScheduleDEP", "ScheduleDCG"):
        errors = list(_schedule_validator(name).iter_errors(itr3_doc[name]))
        assert not errors, f"{name}: " + "\n".join(e.message for e in errors)
    assert itr3_doc["ScheduleDOA"]["Land"]["DepreciationDetail"]["WDVLastDay"] == 0


def test_rate45_special_block_validates_against_official_schema() -> None:
    """Rate45 (the special 45% block) has a genuinely smaller required-
    field set than Rate15/30/40 (no half-rate/additional-depreciation
    provisions at all) -- exercised end-to-end through the real builder,
    not just the typed-model layer, to prove the smaller shape doesn't
    silently break schema validation."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDPM"] = {
        "PlantMachinery": {"Rate45": _dpm_rate_block(500000, cap_gain=3000)},
    }
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    errors = list(_schedule_validator("ScheduleDPM").iter_errors(itr3_doc["ScheduleDPM"]))
    assert not errors, "\n".join(e.message for e in errors)
    assert itr3_doc["ScheduleDPM"]["PlantMachinery"]["Rate45"]["DepreciationDetail"]["CapGainUs50"] == 3000
    assert itr3_doc["ScheduleDCG"]["SummaryFromDeprSchCG"]["PlantMachinerySummaryCG"]["DeprBlockTot45Percent"] == 3000


def test_all_doa_asset_categories_together_validate_against_official_schema() -> None:
    """Land + Building + FurnitureFittings + IntangibleAssets + Ships all
    populated at once, exercised end-to-end through the real builder."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleDOA"] = {
        "Land": {"DepreciationDetail": {"WDVFirstDay": 500000, "WDVLastDay": 500000}},
        "Building": {"Rate10": _dpm_rate_block(200000)},
        "FurnitureFittings": {"Rate10": _dpm_rate_block(40000)},
        "IntangibleAssets": {"Rate25": _dpm_rate_block(80000)},
        "Ships": {"Rate20": _dpm_rate_block(1000000, cap_gain=5000)},
    }
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    for name in ("ScheduleDOA", "ScheduleDEP", "ScheduleDCG"):
        errors = list(_schedule_validator(name).iter_errors(itr3_doc[name]))
        assert not errors, f"{name}: " + "\n".join(e.message for e in errors)
    doa = itr3_doc["ScheduleDOA"]
    assert doa["Land"]["DepreciationDetail"]["WDVFirstDay"] == 500000
    assert doa["FurnitureFittings"]["Rate10"]["DepreciationDetail"]["WDVFirstDay"] == 40000
    assert doa["IntangibleAssets"]["Rate25"]["DepreciationDetail"]["WDVFirstDay"] == 80000
    assert doa["Ships"]["Rate20"]["DepreciationDetail"]["CapGainUs50"] == 5000
    assert itr3_doc["ScheduleDCG"]["SummaryFromDeprSchCG"]["ShipsSummary"] == 5000
