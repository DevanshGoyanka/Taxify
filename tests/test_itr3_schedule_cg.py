"""Tests for ITR-3 Schedule CG (tracker row #20 -- Schedule CGFor23),
covering the specific gaps closed this turn: Schedule CG items A2/B2
(slump sale, section 50B), A4 (NRI STCG shares/debentures), B3-proviso
(NRI LTCG without indexation, s.48 first proviso), B8 (NRI foreign
exchange asset, s.115F), Schedule D's ``TotDeductClaim``, and a genuine
``NameError``-risk dead-code fallback function reference.

**A2/B2 (slump sale) is genuinely ITR-3-only** (section 50B requires a
business; confirmed absent from ITR-2's own official form text) -- new
schema/mapper/builder, no ITR-2 precedent to port.

**A4/B3-proviso/B8 already had a working ITR-2 mapper**
(``app/engine/draft_to_itr2_input.py::_map_cg_nri_proviso_48``) and
working ITR-2 builder helpers (``app/engine/itd/itr2.py::_nri_proviso_48``/
``_nri_foreign_asset``) -- both reused directly for ITR-3 rather than
re-derived, since both forms read the identical
``ReturnDraft.capitalGainsSchedule.stSection48``/``ltNriProviso48``/
``ltForeignAssets`` fields and disclose them under the identical schema
shape (confirmed by direct schema introspection, not assumed).

**Not attempted this turn, deliberately deferred with reason** (Schedule
CG is the largest, most complex ITR-3 schedule; this pass closed the
clearest remaining gaps rather than force the entire schedule into one
sitting):
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
from app.schemas.itr3 import ITR3SlumpSaleRow


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
# Dead fallback-function NameError risk
# ---------------------------------------------------------------------------

def test_schedule_cg_typed_none_raises_clear_value_error_not_name_error() -> None:
    """Confirms the removed dead branch: a caller reaching this builder
    without `typed_input` gets a clear ValueError, not a NameError from a
    same-named-minus-'_typed' fallback function that was never defined."""
    import pytest

    with pytest.raises(ValueError, match="requires typed ITR3Input"):
        _schedule_cg_for23_typed(None, None)
