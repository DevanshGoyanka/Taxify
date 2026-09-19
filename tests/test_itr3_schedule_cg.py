"""Tests for ITR-3 Schedule CG (tracker row #20 -- Schedule CGFor23),
covering the specific gaps closed across two rounds: Schedule CG items
A2/B2 (slump sale, section 50B), A4 (NRI STCG shares/debentures),
B3-proviso (NRI LTCG without indexation, s.48 first proviso), B8 (NRI
foreign exchange asset, s.115F), A9/B12 (DTAA-rate claims), A7/B10
(unutilized Capital Gains Accounts Scheme deposit deemed capital gains),
Schedule D's ``TotDeductClaim``, and a genuine ``NameError``-risk
dead-code fallback function reference.

**A2/B2 (slump sale) and A7/B10 (unutilized CGAS -- LTCG side only) are
genuinely ITR-3-only or ITR-3-first**: slump sale needs a business
(confirmed absent from ITR-2's own official form text); the unutilized-
CGAS LTCG item has NO existing ITR-2 precedent at all (confirmed by
reading `itd/itr2.py` directly -- ITR-2's own B10-equivalent is itself
still hardcoded, flagged as a cross-form issue in the tracker, not fixed).

**A4/B3-proviso/B8/A9-B12 (DTAA) already had a working ITR-2 mapper**
(``_map_cg_nri_proviso_48``/``_map_cg_dtaa_entries``) and working ITR-2
builder helpers/logic (``_nri_proviso_48``/``_nri_foreign_asset``/the
local ``_cg_dtaa_rows``) -- reused/ported directly rather than re-derived,
since both forms read the identical shared draft fields and disclose them
under the identical schema shape (confirmed by direct schema
introspection, not assumed).

**A7 (unutilized CGAS, STCG side) and A7/B10's own per-row enum
validation** are new this round: `AmtDeemedStcg`/`AmtDeemedLtcg` sum every
row's `amount_unutilized` regardless of whether the row's free-text
year/section label validates against the schema's own fixed enum (a real
deemed capital gain doesn't stop being real just because the label
doesn't parse), while the per-row disclosure array only includes rows
that DO validate -- and the valid section set genuinely DIFFERS between
the STCG (54B/54G/54GA only) and LTCG (54/54B/54D/54F/54G/54GA/54GB)
tables, confirmed by direct schema introspection of both
``UnutilizedCgPrvYrStcg``/``UnutilizedCgPrvYrLtcg`` definitions.

**Still not attempted, deliberately deferred with reason** (Schedule CG
is the largest, most complex ITR-3 schedule):
- The per-target current-year loss set-off matrix (``TotLossSetOff``,
  ``InStcgAppRate``/``InStcgDTAARate``'s own set-off sub-fields) remains
  disclosure-incomplete -- same class of gap Schedule BP's own Part E
  left deferred at its closure, for the identical reason (the calculator
  exposes loss magnitudes, not a per-target set-off breakdown; populating
  it without that breakdown risks a worse, half-right disclosure).
- ``TotDeductClaim`` is sourced from the calculator's own
  ``compute_exemptions()`` total (54/54B/54EC/54F), matching ITR-2's own
  established approach exactly -- but neither form's calculator currently
  folds the newer 115F/slump-sale-54EC-54F/other-assets-54D-54G-54GA
  claims into that same total, so this figure is a real improvement over
  the prior hardcoded 0 but not yet a fully comprehensive sum across
  every CG exemption sub-type. Flagged here, not silently claimed complete.
"""

from __future__ import annotations

from decimal import Decimal

from jsonschema import Draft4Validator

from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.engine.draft_to_itr3_input import draft_to_itr3_input, _map_slump_sale
from app.engine.calculators.itr3 import compute as compute_itr3
from app.engine.itd.itr3 import build_itr3_json, _schedule_cg_for23_typed, _slump_sale_block
from app.schemas.itr2 import CapitalGainExemptionClaim, CG112AScrip, CGTransaction, CGAssetType
from app.schemas.itr3 import ITR3SlumpSaleRow
from app.schemas.return_draft import PassThroughIncomeEntry


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


# ---------------------------------------------------------------------------
# A2/B2 -- slump sale
# ---------------------------------------------------------------------------

def test_slump_sale_block_stcg_no_exemption_subitem() -> None:
    """Form item A2's own formula is 2c = 2aiii - 2b, with no 2d/2e at
    all -- confirms the STCG block never emits an exemption key."""
    rows = [ITR3SlumpSaleRow(fmv_11uae_2=Decimal("5000000"), fmv_11uae_3=Decimal("4800000"), net_worth=Decimal("2000000"))]
    block = _slump_sale_block(rows, is_long_term=False)
    assert block["FullConsideration"] == 5000000  # higher of the two FMVs
    assert block["NetWorthOfDivision"] == 2000000
    assert block["CapgainonAssets"] == 3000000
    assert "ExemptionOrDednUs54" not in block


def test_slump_sale_block_ltcg_with_exemption() -> None:
    """Form item B2's own formula is 2c = 2aiii-2b, 2e = 2c-2d (54EC/54F
    deduction)."""
    rows = [ITR3SlumpSaleRow(fmv_11uae_2=Decimal("8000000"), fmv_11uae_3=Decimal("8200000"), net_worth=Decimal("3000000"), exemption_amount=Decimal("1000000"))]
    block = _slump_sale_block(rows, is_long_term=True)
    assert block["FullConsideration"] == 8200000
    assert block["SlumpBalance"] == 5200000
    assert block["ExemptionOrDednUs54"] == {"ExemptionGrandTotal": 1000000}
    assert block["CapgainonAssets"] == 4200000


def test_slump_sale_block_multiple_rows_aggregated() -> None:
    """A taxpayer selling more than one division/undertaking in the year
    -- the schema has one aggregate object, not a per-row array."""
    rows = [
        ITR3SlumpSaleRow(fmv_11uae_2=Decimal("1000000"), fmv_11uae_3=Decimal("900000"), net_worth=Decimal("400000")),
        ITR3SlumpSaleRow(fmv_11uae_2=Decimal("500000"), fmv_11uae_3=Decimal("600000"), net_worth=Decimal("100000")),
    ]
    block = _slump_sale_block(rows, is_long_term=False)
    # 1000000 (higher for row 1) + 600000 (higher for row 2) = 1600000
    assert block["FullConsideration"] == 1600000
    assert block["NetWorthOfDivision"] == 500000
    assert block["CapgainonAssets"] == 1100000


def test_map_slump_sale_from_draft_rows() -> None:
    draft = _minimal_draft()
    draft.capitalGainsSchedule.stSlumpSale = [
        {"fmv11uae2": 1000000, "fmv11uae3": 900000, "netWorth": 400000},
    ]
    draft.capitalGainsSchedule.ltSlumpSale = [
        {"fmv11uae2": 8000000, "fmv11uae3": 8200000, "netWorth": 3000000, "exemptionAmount": 1000000},
    ]
    stcg_rows, ltcg_rows = _map_slump_sale(draft)
    assert len(stcg_rows) == 1 and stcg_rows[0].fmv_11uae_2 == Decimal("1000000")
    assert len(ltcg_rows) == 1 and ltcg_rows[0].exemption_amount == Decimal("1000000")


def test_slump_sale_reaches_json_and_validates_against_official_schema() -> None:
    draft = _minimal_draft()
    draft.capitalGainsSchedule.stSlumpSale = [
        {"fmv11uae2": 1000000, "fmv11uae3": 900000, "netWorth": 400000},
    ]
    draft.capitalGainsSchedule.ltSlumpSale = [
        {"fmv11uae2": 8000000, "fmv11uae3": 8200000, "netWorth": 3000000, "exemptionAmount": 1000000},
    ]
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    cg = itr3_doc["ScheduleCGFor23"]
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)
    assert cg["ShortTermCapGainFor23"]["SlumpSaleInStcg"]["CapgainonAssets"] == 600000
    assert cg["LongTermCapGain23"]["SlumpSaleInLtcgDtls"]["SlumpSaleInLtcg"]["CapgainonAssets"] == 4200000


# ---------------------------------------------------------------------------
# A4 / B3-proviso / B8 -- NRI bare-entry figures
# ---------------------------------------------------------------------------

def test_nri_section48_and_proviso48_and_115f_reach_json() -> None:
    draft = _minimal_draft()
    draft.capitalGainsSchedule.stSection48.nriSttPaid = Decimal("200000")
    draft.capitalGainsSchedule.stSection48.nriSttNotPaid = Decimal("50000")
    draft.capitalGainsSchedule.ltNriProviso48.ltcgWithoutBenefit = Decimal("900000")
    draft.capitalGainsSchedule.ltNriProviso48.deduction54F = Decimal("300000")
    draft.capitalGainsSchedule.ltForeignAssets = [
        {"saleValue": 500000, "deduction115F": 150000},
        {"saleValue": 200000, "deduction115F": 50000},
    ]
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.cg_nri_stcg_stt_paid == Decimal("200000")
    assert typed_input.cg_nri_ltcg_without_indexation == Decimal("900000")
    assert typed_input.cg_nri_115f_sale_value == Decimal("700000")  # summed across both rows
    assert typed_input.cg_nri_115f_deduction == Decimal("200000")

    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    cg = itr3_doc["ScheduleCGFor23"]
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)
    assert cg["ShortTermCapGainFor23"]["NRITransacSec48Dtl"] == {"NRItaxSTTPaid": 200000, "NRItaxSTTNotPaid": 50000}
    assert cg["LongTermCapGain23"]["NRIProvisoSec48"] == {"LTCGWithoutBenefit": 900000, "DeductionUs54F": 300000, "BalanceCG": 600000}
    assert cg["LongTermCapGain23"]["NRISaleofForeignAsset"] == {"SaleonSpecAsset": 700000, "DednSpecAssetus115": 200000, "BalonSpeciAsset": 500000}


def test_nri_fields_default_to_zero_when_absent() -> None:
    """A taxpayer with no NRI-specific CG data at all -- these blocks must
    still validate as all-zero, not be omitted (they are required
    sub-objects of an always-present schedule)."""
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    assert cg["ShortTermCapGainFor23"]["NRITransacSec48Dtl"] == {"NRItaxSTTPaid": 0, "NRItaxSTTNotPaid": 0}
    assert cg["LongTermCapGain23"]["NRIProvisoSec48"] == {"LTCGWithoutBenefit": 0, "DeductionUs54F": 0, "BalanceCG": 0}


# ---------------------------------------------------------------------------
# DeducClaimInfo.TotDeductClaim
# ---------------------------------------------------------------------------

def test_tot_deduct_claim_reflects_calculator_exemption_total_not_hardcoded_zero() -> None:
    """The calculator's own exempt_54/etc accumulators (feeding
    `compute_exemptions()`) read each transaction's LEGACY scalar
    deduction_us54/etc fields, not the richer `exemptions` claim list --
    confirmed by reading `calculators/itr3.py` directly, matching exactly
    what the real mapper (`_map_immovable_gains`) itself populates."""
    from app.schemas.itr2 import CGTransaction, CGAssetType
    from datetime import date

    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    tx = CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_acquisition=date(2015, 4, 1), date_of_transfer=date(2025, 10, 1),
        full_consideration=Decimal("5000000"), cost_of_acquisition=Decimal("1000000"),
        deduction_us54=Decimal("2000000"),
    )
    typed_input = typed_input.model_copy(update={"cg_transactions": [tx]})
    result = compute_itr3(typed_input)
    cg_result = result.schedules.get("cg")
    block = _schedule_cg_for23_typed(cg_result, typed_input)
    assert block["DeducClaimInfo"]["TotDeductClaim"] == 2000000


# ---------------------------------------------------------------------------
# A9/B12 -- DTAA-rate capital-gains claims
# ---------------------------------------------------------------------------

def test_dtaa_entries_reach_json_and_split_chargeable_vs_not() -> None:
    from app.schemas.itr2 import CGDtaaEntry

    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input = typed_input.model_copy(update={
        "cg_stcg_dtaa_entries": [
            CGDtaaEntry(amount=Decimal("100000"), item_no_incl="A3ie", country_name="USA", country_code="2", dtaa_article="13", rate_as_per_treaty=Decimal("0"), sec_it_act="111A", rate_as_per_it_act=Decimal("15"), applicable_rate=Decimal("0")),
            CGDtaaEntry(amount=Decimal("50000"), item_no_incl="A3ie", country_name="UK", country_code="21", dtaa_article="14", rate_as_per_treaty=Decimal("10"), sec_it_act="111A", rate_as_per_it_act=Decimal("15"), applicable_rate=Decimal("10")),
        ],
    })
    result = compute_itr3(typed_input)
    block = _schedule_cg_for23_typed(result.schedules.get("cg"), typed_input)
    stcg = block["ShortTermCapGainFor23"]
    assert len(stcg["NRICgDTAA"]["NRIDTAADtls"]) == 2
    # First row: rate_as_per_treaty == 0 -> not chargeable in India.
    assert stcg["TotalAmtNotTaxUsDTAAStcg"] == 100000
    # Second row: rate_as_per_treaty > 0 -> chargeable at the DTAA rate.
    assert stcg["TotalAmtTaxUsDTAAStcg"] == 50000


def test_dtaa_entries_reach_json_validates_against_official_schema() -> None:
    """NOTE: ``item_no_incl`` must be one of the official schema's own
    enum of item labels (e.g. "B1g" for LTCG land/building) -- confirmed
    by direct schema validation, not assumed from ITR-2's own more
    permissive Pydantic field (`CGDtaaEntry.item_no_incl` has no enum
    constraint at the Python level, and the shared mapper's own default
    for a blank frontend field, "NA", is schema-invalid here). This is a
    pre-existing, shared-code limitation (affects ITR-2 too), flagged in
    the tracker's cross-form-issues log, not fixed as part of this pass."""
    from app.schemas.itr2 import CGDtaaEntry

    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input = typed_input.model_copy(update={
        "cg_ltcg_dtaa_entries": [
            CGDtaaEntry(amount=Decimal("300000"), item_no_incl="B1g", country_name="Singapore", country_code="65", dtaa_article="13", rate_as_per_treaty=Decimal("0"), sec_it_act="112A", rate_as_per_it_act=Decimal("12.5"), applicable_rate=Decimal("0")),
        ],
    })
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)
    assert cg["LongTermCapGain23"]["TotalAmtNotTaxUsDTAALtcg"] == 300000


def test_dtaa_omitted_when_no_entries() -> None:
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    result = compute_itr3(typed_input)
    block = _schedule_cg_for23_typed(result.schedules.get("cg"), typed_input)
    assert "NRICgDTAA" not in block["ShortTermCapGainFor23"]
    assert "NRICgDTAA" not in block["LongTermCapGain23"]


# ---------------------------------------------------------------------------
# A7/B10 -- unutilized Capital Gains Accounts Scheme deposit
# ---------------------------------------------------------------------------

def test_unutilized_stcg_deposit_reaches_json_with_valid_row() -> None:
    from app.schemas.itr3 import ITR3UnutilizedCGRow

    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input = typed_input.model_copy(update={
        "cg_stcg_unutilized_flag": "Y",
        "cg_stcg_unutilized_deposits": [
            ITR3UnutilizedCGRow(prev_year_transferred="2023-24", section_claimed="54G", year_asset_acquired="2024", amount_utilized=Decimal("100000"), amount_unutilized=Decimal("50000")),
        ],
    })
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)
    stcg = cg["ShortTermCapGainFor23"]
    assert stcg["UnutilizedStcgFlag"] == "Y"
    assert stcg["AmtDeemedStcg"] == 50000
    assert stcg["TotalAmtDeemedStcg"] == 50000
    assert stcg["UnutilizedCg"]["UnutilizedCgPrvYrDtls"][0]["SectionClmd"] == "54G"


def test_unutilized_stcg_invalid_section_still_counts_toward_total_but_not_disclosed() -> None:
    """54F is not a valid STCG-table section (LTCG-only) -- the row must
    be dropped from the disclosure array, but its amount must still count
    toward AmtDeemedStcg since it is a real deemed capital gain."""
    from app.schemas.itr3 import ITR3UnutilizedCGRow

    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input = typed_input.model_copy(update={
        "cg_stcg_unutilized_deposits": [
            ITR3UnutilizedCGRow(prev_year_transferred="2023-24", section_claimed="54F", amount_unutilized=Decimal("75000")),
        ],
    })
    result = compute_itr3(typed_input)
    block = _schedule_cg_for23_typed(result.schedules.get("cg"), typed_input)
    stcg = block["ShortTermCapGainFor23"]
    assert stcg["AmtDeemedStcg"] == 75000
    assert "UnutilizedCg" not in stcg


def test_unutilized_ltcg_wider_section_set_and_requires_amt_utilized() -> None:
    """54 is valid for the LTCG table but NOT the STCG table -- confirms
    the two tables' enums are genuinely different, not shared."""
    from app.schemas.itr3 import ITR3UnutilizedCGRow

    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input = typed_input.model_copy(update={
        "cg_ltcg_unutilized_flag": "Y",
        "cg_ltcg_unutilized_deposits": [
            ITR3UnutilizedCGRow(prev_year_transferred="2022-23", section_claimed="54", amount_utilized=Decimal("200000"), amount_unutilized=Decimal("100000")),
        ],
    })
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)
    ltcg = cg["LongTermCapGain23"]
    assert ltcg["AmtDeemedLtcg"] == 100000
    row = ltcg["UnutilizedCg"]["UnutilizedCgPrvYrDtls"][0]
    assert row["SectionClmd"] == "54"
    assert row["AmtUtilized"] == 200000


def test_unutilized_defaults_to_n_flag_and_zero_when_no_data() -> None:
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    assert cg["ShortTermCapGainFor23"]["UnutilizedStcgFlag"] == "N"
    assert cg["ShortTermCapGainFor23"]["AmtDeemedStcg"] == 0
    assert "UnutilizedCg" not in cg["ShortTermCapGainFor23"]
    assert cg["LongTermCapGain23"]["UnutilizedLtcgFlag"] == "N"


# ---------------------------------------------------------------------------
# Dead fallback-function NameError risk
# ---------------------------------------------------------------------------

def test_schedule_cg_typed_none_raises_clear_value_error_not_name_error() -> None:
    """Confirms the removed dead branch: a caller reaching this builder
    without `typed_input` gets a clear ValueError, not a NameError from a
    same-named-minus-'_typed' fallback function that was never defined."""
    import pytest

    with pytest.raises(ValueError, match="requires typed ITR3Input"):
        _schedule_cg_for23_typed(None, None)


# ---------------------------------------------------------------------------
# Land/building SaleofLandBuildDtls row shape (severe, pre-existing defect
# found during a "very very sure" re-verification of Schedule 20 -- unlike
# every other Schedule CG bug this schedule's history has fixed, this one
# is a hard SCHEMA-VALIDATION failure, not a tax-rate or disclosure gap.
# The codebase previously reused ITR-2's own land/building row builder
# unchanged for ITR-3 (`_cg_land_building_row_stcg`/`_ltcg` in
# `itd/itr2.py`), whose field names/shapes were verified correct for
# ITR-2's OWN schema but never independently checked against ITR-3's --
# confirmed by direct introspection that the two forms' schemas genuinely
# differ here (ITR-3's wider 54B/54G/54GA vs ITR-2's single 54B on the
# STCG side), meaning EVERY ITR-3 return with a land/building capital
# gain -- one of the most common real-world scenarios -- produced
# schema-invalid JSON (`Additional properties are not allowed`,
# missing required `ExemptionOrDednUs54`/`CapgainonAssets`/
# `CapgainonAssets_1ea`) regardless of anything else this schedule's
# history already fixed or tested.
# ---------------------------------------------------------------------------

from datetime import date as _date
from app.schemas.itr2 import CGTransaction, CGAssetType


def test_land_building_stcg_row_uses_itr3_field_names_and_validates() -> None:
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING, full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("500000"),
        date_of_acquisition=_date(2025, 6, 1), date_of_transfer=_date(2025, 12, 1), deduction_us54b=Decimal("100000"),
    )]
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    row = cg["ShortTermCapGainFor23"]["SaleofLandBuild"]["SaleofLandBuildDtls"][0]
    # ITR-3's own field names (not ITR-2's DeductionUs54B/STCGonImmvblPrprty).
    assert "ExemptionOrDednUs54" in row
    assert "CapgainonAssets" in row
    assert "DeductionUs54B" not in row
    assert "STCGonImmvblPrprty" not in row
    assert row["ExemptionOrDednUs54"]["ExemptionGrandTotal"] == 100000
    assert row["CapgainonAssets"] == 1400000  # 1500000 - 100000
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)


def test_land_building_ltcg_row_uses_itr3_field_names_and_validates() -> None:
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING, full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("500000"),
        date_of_acquisition=_date(2020, 1, 1), date_of_transfer=_date(2026, 1, 1), deduction_us54=Decimal("100000"),
    )]
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    row = cg["LongTermCapGain23"]["SaleofLandBuild"]["SaleofLandBuildDtls"][0]
    # ITR-3's own field names (not ITR-2's LTCGonImmvblPrprty/...BE).
    assert "CapgainonAssets" in row
    assert "LTCGonImmvblPrprty" not in row
    assert "LTCGonImmvblPrprtyBE" not in row
    assert row["ExemptionOrDednUs54"]["ExemptionGrandTotal"] == 100000
    assert row["CapgainonAssets"] == 1400000  # 1500000 - 100000
    # Acquired before the 23-Jul-2024 cutoff -> second-proviso EiB track present.
    assert "CapgainonAssets_1ea" in row
    assert "TaxSec1121a" in row
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)


def test_land_building_54d_54g_54ga_reach_table_d_detail_rows() -> None:
    """Direct completion of the item-10 fix (54D/54G/54GA schema fields):
    the amounts were wired into the actual tax computation, but the Table
    D per-claim disclosure detail rows for these three sections were
    missing from the builder entirely -- confirmed against the official
    schema, which genuinely has DeducClaimDtlsUs54D/54G/54GA fields."""
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [
        CGTransaction(
            asset_type=CGAssetType.LAND_BUILDING, full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("500000"),
            date_of_acquisition=_date(2020, 1, 1), date_of_transfer=_date(2026, 1, 1), deduction_us54d=Decimal("300000"),
        ),
        CGTransaction(
            asset_type=CGAssetType.LAND_BUILDING, full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("500000"),
            date_of_acquisition=_date(2025, 6, 1), date_of_transfer=_date(2025, 12, 1), deduction_us54g=Decimal("200000"), deduction_us54ga=Decimal("100000"),
        ),
    ]
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    info = cg["DeducClaimInfo"]
    assert info["DeducClaimDtlsUs54D"] == [{"DateofAcquisition": "2020-01-01", "AmtDeducted": 300000}]
    assert info["DeducClaimDtlsUs54G"] == [{"DateofTransfer": "2025-12-01", "AmtDeducted": 200000}]
    assert info["DeducClaimDtlsUs54GA"] == [{"DateofTransfer": "2025-12-01", "AmtDeducted": 100000}]
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)


# ---------------------------------------------------------------------------
# Cross-form issue #12 -- PTI capital gains: applicable-rate STCG and the
# combined (112A + other) LTCG@12.5% bucket in the CurrYrLosses disclosure
# ---------------------------------------------------------------------------

def test_pti_stcg_applicable_rate_disclosed_under_app_rate_not_flat_30() -> None:
    """Non-111A PTI STCG has no dedicated official SecCode for "applicable
    rate" (only PTI_STCG20P/PTI_STCG30P exist), so the calculator taxes it
    at slab rate, not a fabricated flat 30% -- the CurrYrLosses/
    PassThrIncNature disclosure must match, not still show it under the
    genuine-flat-30%-only "30Per" bucket."""
    draft = _minimal_draft()
    draft.passThroughIncomeEntries = [
        PassThroughIncomeEntry(entityName="Example InvIT", entityPAN="AAAAT1234E", incomeHead="STCG", section="111A", incomeAmount=Decimal("40000")),
        PassThroughIncomeEntry(entityName="Example InvIT", entityPAN="AAAAT1234E", incomeHead="STCG", section="OTH", incomeAmount=Decimal("60000")),
    ]
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    stcg = cg["ShortTermCapGainFor23"]
    assert cg["CurrYrLosses"]["InStcg20Per"]["CurrYearIncome"] == 40000
    assert cg["CurrYrLosses"]["InStcg30Per"]["CurrYearIncome"] == 0
    assert cg["CurrYrLosses"]["InStcgAppRate"]["CurrYearIncome"] == 60000
    assert stcg["PassThrIncNatureSTCG20Per"] == 40000
    assert stcg["PassThrIncNatureSTCG30Per"] == 0
    assert stcg["PassThrIncNatureSTCGAppRate"] == 60000
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)


def test_115f_canonical_claim_and_b7_scalar_both_reach_tot_deduct_claim() -> None:
    """Cross-form issue #13 (tracker), fixed 2026-09-19: TotDeductClaim
    previously omitted the section 115F deduction entirely, from both its
    possible sources -- a canonical per-transaction `CGTransaction.exemptions`
    claim, and item B7's own bare, off-form-computed aggregate figure
    (`cg_nri_115f_sale_value`/`_deduction`). Both are additive, not
    overlapping (different data sources), and disclosure-only -- the B7
    deduction already correctly reduces the actual taxed LTCG regardless.
    `DeducClaimDtlsUs115F` should now carry the canonical claim's own
    detail row (real transfer/investment dates exist for it), but NOT a
    row for the B7 aggregate (which has no per-transaction date data
    anywhere in this codebase to back one)."""
    from datetime import date as _dt
    tx = CGTransaction(
        asset_type=CGAssetType.LISTED_EQUITY_112A,
        full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("500000"),
        fair_market_value_jan2018=Decimal("500000"),
        date_of_acquisition=_dt(2015, 1, 1), date_of_transfer=_dt(2026, 1, 1),
        exemptions=[CapitalGainExemptionClaim(
            section="115F", transfer_date=_dt(2026, 1, 1), eligible_gain=Decimal("400000"),
            investment_amount=Decimal("400000"), investment_date=_dt(2026, 2, 1),
        )],
    )
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [tx]
    typed_input.cg_nri_115f_sale_value = Decimal("900000")
    typed_input.cg_nri_115f_deduction = Decimal("300000")
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    info = cg["DeducClaimInfo"]
    # 400000 (canonical claim) + 300000 (B7 scalar) = 700000.
    assert info["TotDeductClaim"] == 700000
    assert info["DeducClaimDtlsUs115F"] == [{
        "DateofTransfer": "2026-01-01", "AmtInvested": 400000,
        "DateofInvestment": "2026-02-01", "AmtDeducted": 400000,
    }]
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)


def test_pti_ltcg_112a_and_other_combined_into_single_12_5_bucket() -> None:
    """Schedule CYLA does not split section-112A LTCG from other 12.5%-rate
    LTCG the way Schedule CG's own Table A/B do -- both must share the
    single InLtcg12_5Per row, not have the non-112A portion misclassified
    as DTAA-rate income under InLtcgDTAARate."""
    draft = _minimal_draft()
    draft.passThroughIncomeEntries = [
        PassThroughIncomeEntry(entityName="Example REIT", entityPAN="AAAAT1234E", incomeHead="LTCG", section="112A", incomeAmount=Decimal("70000")),
        PassThroughIncomeEntry(entityName="Example REIT", entityPAN="AAAAT1234E", incomeHead="LTCG", section="OTHER", incomeAmount=Decimal("30000")),
    ]
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    assert cg["CurrYrLosses"]["InLtcg12_5Per"]["CurrYearIncome"] == 100000
    assert cg["CurrYrLosses"]["InLtcgDTAARate"]["CurrYearIncome"] == 0
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)


# ---------------------------------------------------------------------------
# Tracker row #21 -- Schedule 112A: ordinary cg_transactions previously
# never reached the schedule at all, only explicit cg_112a_scrips rows
# ---------------------------------------------------------------------------

def _112a_scrip(**overrides) -> CG112AScrip:
    from datetime import date as _dt
    values = dict(
        isin_code="INNOTREQUIRD", share_unit_name="Example Fund", is_before_31jan2018=True,
        date_of_acquisition=_dt(2015, 1, 1), date_of_transfer=_dt(2026, 1, 1),
        num_shares_units=Decimal("100"), sale_price_per_share=Decimal("2000"),
        total_sale_value=Decimal("200000"), cost_acq_without_index=Decimal("50000"),
        fmv_per_share=Decimal("500"), total_fmv=Decimal("50000"),
    )
    values.update(overrides)
    return CG112AScrip(**values)


def test_112a_ordinary_transaction_reaches_schedule_previously_omitted() -> None:
    """A 112A-classified gain entered through the generic capital-gains
    transaction editor (the most common real-world entry path) previously
    never reached Schedule112A's own disclosure at all -- only the
    dedicated `cg_112a_scrips` per-scrip editor did, even though the
    calculator's own tax computation already correctly included ordinary
    transactions via `ltcg_112a_assets`. Ported from ITR-2's own
    `_112a_source_rows()`, confirmed live there (2026-09-13, Type-2 UAT
    validateItr, PAN GOYPT2026A) for the identical defect."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.LISTED_EQUITY_112A,
        full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("500000"),
        fair_market_value_jan2018=Decimal("500000"),
        date_of_acquisition=_dt(2015, 1, 1), date_of_transfer=_dt(2026, 1, 1),
    )]
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    sched = itr3_doc.get("Schedule112A")
    assert sched is not None
    assert len(sched["Schedule112ADtls"]) == 1
    assert sched["Balance112A"] == 1500000
    errors = list(_schedule_validator("Schedule112A").iter_errors(sched))
    assert not errors, "\n".join(e.message for e in errors)


def test_112a_explicit_scrip_still_reaches_schedule() -> None:
    """No regression on the pre-existing, already-working explicit-scrip
    path (`cg_112a_scrips`)."""
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_112a_scrips = [_112a_scrip()]
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    sched = document["ITR"]["ITR3"]["Schedule112A"]
    assert len(sched["Schedule112ADtls"]) == 1
    assert sched["Balance112A"] == 150000  # 200000 sale - 50000 cost (BE, no grandfathering delta)
    errors = list(_schedule_validator("Schedule112A").iter_errors(sched))
    assert not errors, "\n".join(e.message for e in errors)


def test_112a_explicit_scrip_and_ordinary_transaction_both_counted_no_double_count() -> None:
    """The union of `cg_112a_scrips` and 112A-eligible `cg_transactions`
    must produce exactly one row each, summed correctly -- neither source
    silently drops the other, and no double-counting occurs."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_112a_scrips = [_112a_scrip()]
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.LISTED_EQUITY_112A,
        full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("500000"),
        fair_market_value_jan2018=Decimal("500000"),
        date_of_acquisition=_dt(2015, 1, 1), date_of_transfer=_dt(2026, 1, 1),
    )]
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    sched = document["ITR"]["ITR3"]["Schedule112A"]
    assert len(sched["Schedule112ADtls"]) == 2
    assert sched["Balance112A"] == 150000 + 1500000
    errors = list(_schedule_validator("Schedule112A").iter_errors(sched))
    assert not errors, "\n".join(e.message for e in errors)


def test_112a_111a_long_held_transaction_reclassified_into_schedule() -> None:
    """A `listed_equity_111a`-typed transaction actually held past the
    12-month threshold is reclassified into the 112A LTCG basket for real
    tax computation (matching ITR-2's own already-established rule) -- it
    must reach Schedule112A's own disclosure too, not just the aggregate
    tax figure."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.LISTED_EQUITY_111A,
        full_consideration=Decimal("1000000"), cost_of_acquisition=Decimal("400000"),
        date_of_acquisition=_dt(2020, 1, 1), date_of_transfer=_dt(2026, 1, 1),
    )]
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    sched = document["ITR"]["ITR3"].get("Schedule112A")
    assert sched is not None
    assert len(sched["Schedule112ADtls"]) == 1
    assert sched["Balance112A"] == 600000
    errors = list(_schedule_validator("Schedule112A").iter_errors(sched))
    assert not errors, "\n".join(e.message for e in errors)


def test_112a_b4_and_b7_dispatch_on_is_fii_fpi_consistently_with_schedule() -> None:
    """Schedule CG's own B4 ("SaleOfEquityShareUs112A", resident) vs B7
    ("NRISaleOfEquityShareUs112A", FII/FPI) must dispatch on `is_fii_fpi`
    identically to `_schedule_112a_115ad()`'s own Schedule112A/Schedule115AD
    dispatch (tracker #21-22) -- otherwise a taxpayer could have real
    numbers in Schedule115AD's own detail table while B7 (which the form's
    own text cites as sourced "Column 14 of Schedule 115AD(1)(b)(iii)
    proviso") silently stayed at zero, and B4 kept showing the gain as if
    it were an ordinary resident 112A gain."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.LISTED_EQUITY_112A,
        full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("500000"),
        fair_market_value_jan2018=Decimal("500000"),
        date_of_acquisition=_dt(2015, 1, 1), date_of_transfer=_dt(2026, 1, 1),
    )]
    typed_input.is_fii_fpi = True
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    ltcg = itr3_doc["ScheduleCGFor23"]["LongTermCapGain23"]
    assert ltcg["SaleOfEquityShareUs112A"] == {"BalanceCG": 0, "DeductionUs54F": 0, "CapgainonAssets": 0}
    assert ltcg["NRISaleOfEquityShareUs112A"]["CapgainonAssets"] == 1500000
    assert "Schedule112A" not in itr3_doc
    assert itr3_doc["Schedule115AD"]["Balance115AD"] == 1500000
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(itr3_doc["ScheduleCGFor23"]))
    assert not errors, "\n".join(e.message for e in errors)


def test_a3_equity_mf_on_stt_mf_section_code_dispatches_on_is_fii_fpi() -> None:
    """Schedule CG item A3 ("EquityMFonSTT") is explicitly a combined item
    per the official form's own text (page 99): "on which STT is paid
    under section 111A OR 115AD(1)(ii) proviso (for FII)" -- confirmed a
    genuine gap, distinct from item A5's own rate-changing FII item
    (deliberately left unfixed, see this file's own comment): A3's
    underlying tax rate is unaffected by FII status either way
    (`compute_111a()` always taxes it flat 20% regardless), so only the
    disclosure `MFSectionCode` tag needed to change, not any tax
    computation."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.LISTED_EQUITY_111A,
        full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
        date_of_acquisition=_dt(2025, 6, 1), date_of_transfer=_dt(2026, 1, 1),
        explicit_long_term=False,
    )]
    typed_input.is_fii_fpi = True
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    stcg = document["ITR"]["ITR3"]["ScheduleCGFor23"]["ShortTermCapGainFor23"]
    assert stcg["EquityMFonSTT"][0]["MFSectionCode"] == "5AD1biip"
    assert stcg["EquityMFonSTT"][0]["EquityMFonSTTDtls"]["CapgainonAssets"] == 200000
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(document["ITR"]["ITR3"]["ScheduleCGFor23"]))
    assert not errors, "\n".join(e.message for e in errors)


def test_a3_equity_mf_on_stt_default_mf_section_code_when_not_fii_fpi() -> None:
    """No regression on the default (`is_fii_fpi=False`) path."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.LISTED_EQUITY_111A,
        full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
        date_of_acquisition=_dt(2025, 6, 1), date_of_transfer=_dt(2026, 1, 1),
        explicit_long_term=False,
    )]
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    stcg = document["ITR"]["ITR3"]["ScheduleCGFor23"]["ShortTermCapGainFor23"]
    assert stcg["EquityMFonSTT"][0]["MFSectionCode"] == "1A"


# ---------------------------------------------------------------------------
# Item 5 ("NRISecur115AD") -- full FII/FPI flat-30% tax machinery, ported
# from ITR-2's own already-correct, live-UAT-tested calculator, plus the
# matching disclosure (deferred, then completed, after the tax side landed)
# ---------------------------------------------------------------------------

def test_115ad_fii_securities_taxed_flat_30_not_slab() -> None:
    """Section 115AD(1)(ii): an FII/FPI's own "other" STCG on securities
    (unlisted shares/listed securities/debt MFs/bonds -- STT not paid) is a
    flat 30% special rate via Schedule SI, unlike an ordinary taxpayer's
    identical basket (slab-rate). `calculators/itr3.py` previously had
    zero `is_fii_fpi` awareness at all, always taxing this bucket at slab
    rate regardless."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.UNLISTED_SHARES,
        full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("1000000"),
        date_of_acquisition=_dt(2025, 6, 1), date_of_transfer=_dt(2026, 1, 1),
        explicit_long_term=False,
    )]
    typed_input.is_fii_fpi = True
    result = compute_itr3(typed_input)
    si_by_section = {e.section: e for e in result.schedules["si"].entries}
    assert si_by_section["5ADii"].gross_income == Decimal("1000000")
    assert si_by_section["5ADii"].tax_rate_pct == Decimal("30")
    assert si_by_section["5ADii"].tax_amount == Decimal("300000")
    assert result.special_rate_tax == Decimal("300000")


def test_115ad_ordinary_taxpayer_same_transaction_stays_slab_rate() -> None:
    """No regression: the identical transaction for a non-FII/FPI taxpayer
    must still fall through to ordinary slab rate, with no 5ADii SI
    entry."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.UNLISTED_SHARES,
        full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("1000000"),
        date_of_acquisition=_dt(2025, 6, 1), date_of_transfer=_dt(2026, 1, 1),
        explicit_long_term=False,
    )]
    result = compute_itr3(typed_input)
    assert "5ADii" not in {e.section for e in result.schedules["si"].entries}
    assert result.special_rate_tax == Decimal("0")
    assert result.slab_tax > Decimal("0")


def test_115ad_disclosure_and_tax_agree_a5_vs_a6_split() -> None:
    """Schedule CG item A5 ("NRISecur115AD") now carries the real FII
    securities figure (previously hardcoded zero), correctly EXCLUDED from
    item A6 ("SaleOnOtherAssets") to avoid double-counting the same
    transaction in both -- and the disclosed amount matches exactly what
    Schedule SI actually taxes at 30%."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.UNLISTED_SHARES,
        full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("1000000"),
        date_of_acquisition=_dt(2025, 6, 1), date_of_transfer=_dt(2026, 1, 1),
        explicit_long_term=False,
    )]
    typed_input.is_fii_fpi = True
    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    stcg = document["ITR"]["ITR3"]["ScheduleCGFor23"]["ShortTermCapGainFor23"]
    assert stcg["NRISecur115AD"]["CapgainonAssets"] == 1000000
    assert stcg["SaleOnOtherAssets"]["CapgainonAssets"] == 0
    si_by_section = {e.section: e for e in result.schedules["si"].entries}
    assert si_by_section["5ADii"].gross_income == Decimal("1000000")
    errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(document["ITR"]["ITR3"]["ScheduleCGFor23"]))
    assert not errors, "\n".join(e.message for e in errors)


def test_115ad_no_disclosure_when_not_fii_fpi() -> None:
    """No regression: item A5 stays the honest zero placeholder, and A6
    carries the real (slab-rate) gain, when `is_fii_fpi=False`."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.UNLISTED_SHARES,
        full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("1000000"),
        date_of_acquisition=_dt(2025, 6, 1), date_of_transfer=_dt(2026, 1, 1),
        explicit_long_term=False,
    )]
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    stcg = document["ITR"]["ITR3"]["ScheduleCGFor23"]["ShortTermCapGainFor23"]
    assert stcg["NRISecur115AD"]["CapgainonAssets"] == 0
    assert stcg["SaleOnOtherAssets"]["CapgainonAssets"] == 1000000


# ---------------------------------------------------------------------------
# CORRECTION (2026-09-19): item 5's own scope was itself initially wrong.
# "Securities" under section 115AD(1)(ii) is a defined, narrow statutory
# term (shares/debentures/units/bonds) -- NOT land/building or the other
# generic-other-asset types. The first version of the item-5 machinery
# above (correctly) taxed genuine FII securities at flat 30%, but a
# `post_loss_cg_baskets()` bug meant ANY FII/FPI "other" STCG -- including
# land/building, which has no section-115AD flat-rate treatment at all --
# was swept into the same flat-30% bucket. These two tests certify the
# fix: land-only stays slab-rate, and a mixed land+securities return
# splits correctly (only the securities portion gets 5ADii).
# ---------------------------------------------------------------------------

def test_115ad_fii_land_only_stcg_stays_slab_not_flat_30() -> None:
    """An FII/FPI's STCG on land/building has no section 115AD flat-rate
    treatment -- `CGAssetType.LAND_BUILDING` is not a member of
    `_FII_SECURITIES_ASSET_TYPES`, so it must fall through to ordinary
    slab rate exactly like a non-FII taxpayer's identical gain, with no
    5ADii Schedule SI entry at all."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("1000000"),
        date_of_acquisition=_dt(2025, 6, 1), date_of_transfer=_dt(2026, 1, 1),
        explicit_long_term=False,
    )]
    typed_input.is_fii_fpi = True
    result = compute_itr3(typed_input)
    assert "5ADii" not in {e.section for e in result.schedules["si"].entries}
    assert result.special_rate_tax == Decimal("0")
    assert result.slab_tax > Decimal("0")


def test_115ad_fii_mixed_land_and_securities_splits_correctly() -> None:
    """A single FII/FPI return with BOTH a land/building STCG (slab-rate)
    AND a securities STCG (flat-30% u/s 115AD(1)(ii)) must tax only the
    securities portion at 30% via Schedule SI -- the land portion must
    still contribute to ordinary slab tax, not be swept into the flat-30%
    bucket alongside it."""
    from datetime import date as _dt
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    typed_input.cg_transactions = [
        CGTransaction(
            asset_type=CGAssetType.LAND_BUILDING,
            full_consideration=Decimal("2000000"), cost_of_acquisition=Decimal("1000000"),
            date_of_acquisition=_dt(2025, 6, 1), date_of_transfer=_dt(2026, 1, 1),
            explicit_long_term=False,
        ),
        CGTransaction(
            asset_type=CGAssetType.UNLISTED_SHARES,
            full_consideration=Decimal("700000"), cost_of_acquisition=Decimal("500000"),
            date_of_acquisition=_dt(2025, 6, 1), date_of_transfer=_dt(2026, 1, 1),
            explicit_long_term=False,
        ),
    ]
    typed_input.is_fii_fpi = True
    result = compute_itr3(typed_input)
    si_by_section = {e.section: e for e in result.schedules["si"].entries}
    assert si_by_section["5ADii"].gross_income == Decimal("200000")
    assert si_by_section["5ADii"].tax_amount == Decimal("60000")
    assert result.special_rate_tax == Decimal("60000")
    assert result.slab_tax > Decimal("0")
