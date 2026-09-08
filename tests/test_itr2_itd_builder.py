"""Focused schema tests for the canonical ITR-2 ITD JSON builder."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft4Validator

from app.engine.calculators.itr2 import compute
from app.engine.itd.itr2 import build_itr2_json
from app.schemas.itr1 import (
    AgeBracket,
    BankAccount,
    FilingAddress,
    HousePropertyIncome,
    OtherSourcesIncome,
    PropertyType,
    SalaryIncome,
    TaxPaymentDetail,
    TaxRegime,
    TCSEntry,
    TDS1Entry,
    TDS2Entry,
    TDS3Entry,
)
from app.schemas.itr2 import (
    BFLossItem,
    CG112AScrip,
    CGAssetType,
    CGTransaction,
    CapitalGainExemptionClaim,
    CoOwnerDetail,
    EmployerFilingDetail,
    ESOPDeferralInput,
    ForeignAssetEntry,
    ForeignAssetType,
    FSICountryEntry,
    HomeLoanDetail,
    ITR2FilingProfile,
    ITR2Input,
    LossHead,
    OS89ACountryEntry,
    OSDeductions,
    OSDividendEntry,
    OSDtaaEntry,
    OSGiftBreakdown,
    OSOtherIncomeEntry,
    OSQuarterlyAmount,
    OSRaceHorseActivity,
    OSSection89A,
    OSSpecialRateEntry,
    OSUnexplainedIncome,
    PropertyFilingDetail,
    PTIEntry,
    ResidentialStatus,
    ScheduleSIEntry,
    TDS3FilingDetail,
    TenantDetail,
    TR1Entry,
    VDATransaction,
)

_SCHEMA = Path(__file__).resolve().parents[1] / "frontend" / "ITD OFFICAL REFERENCE DOCS" / "AY 2026-27 Offical Schema JSON" / "ITR-2_2026_Main_V1.1 (1).json"


def _profile() -> ITR2FilingProfile:
    """Return a complete real filing profile suitable for tests."""
    return ITR2FilingProfile(
        pan="AAAPA1234A",
        first_name="Asha",
        surname_or_org_name="Sharma",
        date_of_birth_or_formation=date(1990, 1, 1),
        father_name="Arun Sharma",
        verification_place="Delhi",
        primary_address=FilingAddress(
            residence_no="12",
            locality_or_area="Model Town",
            city_or_town_or_district="Delhi",
            state_code="07",
            pin_code="110009",
            mobile_no="9876543210",
            email="asha@example.com",
        ),
    )


def _input(**overrides: Any) -> ITR2Input:
    """Return a canonical ITR-2 input with mandatory filing facts."""
    values: dict[str, Any] = {
        "age_bracket": AgeBracket.BELOW_60,
        "tax_regime": TaxRegime.OLD,
        "filing_profile": _profile(),
    }
    values.update(overrides)
    return ITR2Input(**values)


def _assert_schema_valid(document: dict[str, Any]) -> None:
    """Assert that a generated document satisfies the official Draft-4 schema."""
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    Draft4Validator(schema).validate(document)


def test_minimal_builder_requires_identity_and_omits_optional_schedules() -> None:
    """Minimal output is valid and contains no fabricated optional schedules."""
    input_data = _input()
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    payload = document["ITR"]["ITR2"]
    assert payload["PartA_GEN1"]["PersonalInfo"]["PAN"] == "AAAPA1234A"
    assert "ScheduleS" not in payload
    assert "ScheduleHP" not in payload
    assert "ScheduleFA" not in payload
    assert "ScheduleESOP" not in payload
    assert "ScheduleIT" not in payload


def test_missing_filing_profile_is_rejected() -> None:
    """The builder never fabricates taxpayer identity."""
    input_data = ITR2Input(age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD)
    with pytest.raises(ValueError, match="filing_profile"):
        build_itr2_json(compute(input_data), input_data)


def test_refund_requires_real_primary_bank_account() -> None:
    """A refund cannot be emitted with fabricated or undesignated bank data."""
    input_data = _input()
    result = compute(input_data)
    result.refund_due = Decimal("100")
    with pytest.raises(ValueError, match="bank account"):
        build_itr2_json(result, input_data)

    input_data = _input(
        bank_accounts=[
            BankAccount(
                account_number="1234567890",
                ifsc_code="SBIN0000001",
                bank_name="State Bank of India",
                account_type="savings",
                is_primary=True,
            )
        ]
    )
    result = compute(input_data)
    result.refund_due = Decimal("100")
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    bank = document["ITR"]["ITR2"]["PartB_TTI"]["Refund"]["BankAccountDtls"]["AddtnlBankDetails"][0]
    assert bank["BankAccountNo"] == "1234567890"
    assert bank["IFSCCode"] == "SBIN0000001"


def test_112a_and_vda_rows_are_complete_signed_and_schema_valid() -> None:
    """Actual 112A and VDA rows serialize with row totals and signed CG balance."""
    input_data = _input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="LOSS SCRIP",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 5, 1),
                num_shares_units=Decimal("10"),
                sale_price_per_share=Decimal("100"),
                total_sale_value=Decimal("1000"),
                cost_acq_without_index=Decimal("1500"),
            )
        ],
        vda_transactions=[
            VDATransaction(
                date_of_acquisition=date(2024, 1, 1),
                date_of_transfer=date(2025, 1, 1),
                acquisition_cost=Decimal("100"),
                consideration_received=Decimal("250"),
            )
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    payload = document["ITR"]["ITR2"]
    assert payload["Schedule112A"]["Schedule112ADtls"][0]["Balance"] == -500
    assert payload["Schedule112A"]["TotalBalance112A"] == -500
    assert payload["ScheduleVDA"]["ScheduleVDADtls"][0]["IncomeFromVDA"] == 150
    assert payload["ScheduleVDA"]["TotIncCapGain"] == 150


def test_sale_of_equity_share_us112a_reflects_real_gain_not_hardcoded_zero() -> None:
    """Schedule CG's LongTermCapGain23.SaleOfEquityShareUs112A (item 3a/3c,
    "LTCG u/s 112A (column 14 of Schedule 112A)") was previously always a
    hardcoded zero placeholder regardless of actual 112A gain -- a real bug
    independent of FII/FPI status: even a resident with genuine 112A gains
    saw this summary field as zero, though the dedicated Schedule112A
    per-scrip block and the actual tax were both already correct."""
    input_data = _input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001", share_unit_name="GAIN SCRIP",
                date_of_acquisition=date(2023, 1, 1), date_of_transfer=date(2025, 5, 1),
                num_shares_units=Decimal("10"), sale_price_per_share=Decimal("500"),
                total_sale_value=Decimal("5000"), cost_acq_without_index=Decimal("2000"),
            )
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    ltcg = document["ITR"]["ITR2"]["ScheduleCGFor23"]["LongTermCapGain23"]
    assert ltcg["SaleOfEquityShareUs112A"]["BalanceCG"] == 3000
    assert ltcg["SaleOfEquityShareUs112A"]["CapgainonAssets"] == 3000
    # Not FII/FPI -- the parallel NRI-specific field stays at its zero
    # placeholder, not populated a second time.
    assert ltcg["NRISaleOfEquityShareUs112A"]["BalanceCG"] == 0


def test_fii_fpi_capital_gains_route_to_section_115ad_fields_and_si_codes() -> None:
    """An FII/FPI's OWN capital gains on securities route to the parallel
    Section 115AD Schedule-CG fields (NRISecur115AD, NRISaleOfEquityShareUs112A,
    NRIOnSec112and115Dtls[SectionCode=5ADiii], EquityMFonSTT's
    "5AD1biip" code) and Schedule-SI codes (5AD1biip/5ADii/5ADiii/5ADiiiP)
    instead of the ordinary ones -- same statutory rates (20%/30%/12.5%/
    12.5%), previously always zero-placeholder regardless of real FII
    activity. A non-security asset type (jewellery) held in the same
    return stays in the ordinary generic-other bucket, not swept into the
    FII-specific one."""
    profile = _profile().model_copy(update={
        "is_fii_fpi": True,
        "sebi_registration_number": "INABFP123456",
        "residential_status": ResidentialStatus.NON_RESIDENT,
    })
    input_data = _input(
        filing_profile=profile,
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_transactions=[
            # 111A-equivalent (STT paid): 20%, same rate as ordinary 111A.
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 1, 1),
                full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
            ),
            # "Other securities" STCG (STT not paid): 30% flat under 115AD,
            # unlike an ordinary taxpayer where this same basket is slab-rate.
            CGTransaction(
                asset_type=CGAssetType.LISTED_SECURITY,
                date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 1, 1),
                full_consideration=Decimal("200000"), cost_of_acquisition=Decimal("150000"),
            ),
            # "Other securities" LTCG: 12.5%, same rate as ordinary section 112.
            CGTransaction(
                asset_type=CGAssetType.LISTED_SECURITY,
                date_of_acquisition=date(2020, 6, 1), date_of_transfer=date(2025, 6, 1),
                full_consideration=Decimal("900000"), cost_of_acquisition=Decimal("400000"),
            ),
        ],
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00002", share_unit_name="FII GAIN SCRIP",
                date_of_acquisition=date(2023, 1, 1), date_of_transfer=date(2025, 5, 1),
                num_shares_units=Decimal("10"), sale_price_per_share=Decimal("50000"),
                total_sale_value=Decimal("500000"), cost_acq_without_index=Decimal("200000"),
            )
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)

    stcg = document["ITR"]["ITR2"]["ScheduleCGFor23"]["ShortTermCapGainFor23"]
    assert stcg["EquityMFonSTT"][0]["MFSectionCode"] == "5AD1biip"
    assert stcg["EquityMFonSTT"][0]["EquityMFonSTTDtls"]["BalanceCG"] == 200000
    assert stcg["NRISecur115AD"]["CapgainonAssets"] == 50000
    # No non-FII-security STCG in this return, so the ordinary bucket is zero.
    assert stcg["SaleOnOtherAssets"]["CapgainonAssets"] == 0

    ltcg = document["ITR"]["ITR2"]["ScheduleCGFor23"]["LongTermCapGain23"]
    assert ltcg["NRISaleOfEquityShareUs112A"]["BalanceCG"] == 300000
    # Not FII-specific -- stays at zero since the 112A gain routed to the FII field.
    assert ltcg["SaleOfEquityShareUs112A"]["BalanceCG"] == 0
    nri_sec = ltcg["NRIOnSec112and115"]["NRIOnSec112and115Dtls"]
    assert len(nri_sec) == 1
    assert nri_sec[0]["SectionCode"] == "5ADiii"
    assert nri_sec[0]["CapgainonAssets"] == 500000

    si_by_code = {row["SecCode"]: row for row in document["ITR"]["ITR2"]["ScheduleSI"]["SplCodeRateTax"]}
    assert si_by_code["5AD1biip"]["SplRatePercent"] == 20
    assert si_by_code["5AD1biip"]["SplRateIncTax"] == 40000
    assert si_by_code["5ADii"]["SplRatePercent"] == 30
    assert si_by_code["5ADii"]["SplRateIncTax"] == 15000
    assert si_by_code["5ADiii"]["SplRatePercent"] == 12.5
    assert si_by_code["5ADiii"]["SplRateIncTax"] == 62500
    assert si_by_code["5ADiiiP"]["SplRatePercent"] == 12.5
    assert si_by_code["5ADiiiP"]["SplRateIncTax"] == 21875  # 12.5% * (300000 - 125000 threshold)
    # None of the ordinary (non-FII) SecCodes should appear at all.
    assert "1A" not in si_by_code
    assert "21" not in si_by_code
    assert "2A" not in si_by_code


def test_land_building_stcg_and_ltcg_rows_are_schema_valid_with_correct_fields() -> None:
    """Schedule CG land/building rows use the official field names and values.

    Regression test for a builder defect where ``_cg_land_building_row``
    emitted an entirely different (and wrong) key set --
    ``FullValueConsdRecvUnqshr``/nested ``DeductSec48``/``BalanceCG`` (the
    shape for the unquoted-shares/other-assets block) instead of the real
    ``SaleofLandBuildDtls`` schema (``FullConsideration``/``AquisitCost``/
    flat ``TotalDedn``/``Balance``/``STCGonImmvblPrprty``/
    ``LTCGonImmvblPrprty``). No prior test exercised a land/building
    transaction at all, so this was never caught by schema validation.
    """
    input_data = _input(
        cg_transactions=[
            # Short-term: held well under a year, no indexation applies.
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                description="Plot A",
                date_of_acquisition=date(2024, 6, 1),
                date_of_transfer=date(2025, 1, 1),
                full_consideration=Decimal("2000000"),
                cost_of_acquisition=Decimal("1500000"),
                expenditure_on_transfer=Decimal("20000"),
            ),
            # Long-term: held over 2 years, indexed cost supplied.
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                description="Plot B",
                date_of_acquisition=date(2015, 4, 1),
                date_of_transfer=date(2025, 6, 1),
                full_consideration=Decimal("8000000"),
                cost_of_acquisition=Decimal("3000000"),
                indexed_cost=Decimal("4500000"),
                expenditure_on_transfer=Decimal("50000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    cg = document["ITR"]["ITR2"]["ScheduleCGFor23"]

    stcg_rows = cg["ShortTermCapGainFor23"]["SaleofLandBuild"]["SaleofLandBuildDtls"]
    assert len(stcg_rows) == 1
    stcg_row = stcg_rows[0]
    assert stcg_row["FullConsideration"] == 2000000
    assert stcg_row["AquisitCost"] == 1500000
    assert stcg_row["TotalDedn"] == 1520000
    assert stcg_row["Balance"] == 480000
    assert stcg_row["STCGonImmvblPrprty"] == 480000

    ltcg_rows = cg["LongTermCapGain23"]["SaleofLandBuild"]["SaleofLandBuildDtls"]
    assert len(ltcg_rows) == 1
    ltcg_row = ltcg_rows[0]
    assert ltcg_row["FullConsideration"] == 8000000
    assert ltcg_row["AquisitCost"] == 3000000
    assert ltcg_row["AquisitCostIndex"] == 4500000
    # The PRIMARY declared gain always uses the non-indexed cost (3000000),
    # per the official form's Schedule CG item 1c -- the indexed cost only
    # feeds the separate section 112(1)(a) second-proviso comparison below.
    assert ltcg_row["TotalDedn"] == 3050000
    assert ltcg_row["Balance"] == 4950000
    assert ltcg_row["LTCGonImmvblPrprty"] == 4950000
    assert cg["LongTermCapGain23"]["SaleofLandBuild"]["TotalLTCGImmblPrprty"] == 4950000
    # Plot B was acquired 2015-04-01 (pre-23-Jul-2024) and `_input()`
    # defaults to RESIDENT, so the second-proviso EiB comparison applies:
    # 12.5% * 4950000 = 618750 vs 20% * (8000000-4550000=3450000) = 690000
    # -- the new-regime tax is already lower, so no relief is triggered.
    assert ltcg_row["BalanceForEiB"] == 3450000
    assert ltcg_row["TaxSec1121a"] == 618750
    assert ltcg_row["TaxSec1121aiiB"] == 690000
    assert ltcg_row["ExcessAmtSec1121a"] == 0
    assert cg["LongTermCapGain23"]["SaleofLandBuild"]["TotalExcessTax"] == 0


def test_land_building_applies_section_50c_stamp_duty_deeming() -> None:
    """A stamp duty value exceeding 110% of consideration raises the deemed
    full value of consideration (section 50C), increasing the reported gain.
    """
    input_data = _input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                description="Undervalued plot",
                date_of_acquisition=date(2024, 6, 1),
                date_of_transfer=date(2025, 1, 1),
                full_consideration=Decimal("1000000"),
                stamp_duty_value=Decimal("1500000"),  # well over 110% of consideration
                cost_of_acquisition=Decimal("600000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleCGFor23"]["ShortTermCapGainFor23"]["SaleofLandBuild"]["SaleofLandBuildDtls"][0]
    assert row["PropertyValuation"] == 1500000
    assert row["FullConsideration50C"] == 1500000  # deemed value, not the lower actual consideration
    assert row["Balance"] == 900000  # 1500000 - 600000, not 1000000 - 600000


def test_land_building_section_112_1a_relief_reduces_actual_si_tax() -> None:
    """The section 112(1)(a) second-proviso relief isn't just disclosed in
    Schedule CG -- it actually reduces the Schedule SI section-112 tax
    figure, since a self-assessed return declares tax liability inclusive
    of every relief the law allows, not just an FYI memo alongside an
    unreduced tax total."""
    input_data = _input(
        residential_status=ResidentialStatus.RESIDENT,
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                description="Ancestral plot",
                date_of_acquisition=date(2005, 4, 1),
                date_of_transfer=date(2024, 1, 1),
                full_consideration=Decimal("5000000"),
                cost_of_acquisition=Decimal("1000000"),
                indexed_cost=Decimal("3000000"),
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)

    cg = document["ITR"]["ITR2"]["ScheduleCGFor23"]
    ltcg_row = cg["LongTermCapGain23"]["SaleofLandBuild"]["SaleofLandBuildDtls"][0]
    assert ltcg_row["TaxSec1121a"] == 500000  # 12.5% * (50L - 10L)
    assert ltcg_row["TaxSec1121aiiB"] == 400000  # 20% * (50L - 30L)
    assert ltcg_row["ExcessAmtSec1121a"] == 100000
    assert cg["LongTermCapGain23"]["SaleofLandBuild"]["TotalExcessTax"] == 100000

    si = document["ITR"]["ITR2"]["ScheduleSI"]
    si_112_row = next(row for row in si["SplCodeRateTax"] if row["SecCode"] == "21")
    # Without relief this would be 500000 (12.5% * 4000000 declared gain);
    # the 100000 second-proviso relief reduces it to 400000.
    assert si_112_row["SplRateIncTax"] == 400000


def test_per_transaction_exemption_claims_reduce_own_row_and_populate_detail_arrays() -> None:
    """Section 54/54B/54EC/54F/115F exemption claims, already captured
    per-transaction on CGTransaction.exemptions, previously only reduced
    the AGGREGATE DeducClaimInfo.TotDeductClaim -- individual Schedule CG
    rows (land/building's ExemptionOrDednUs54, the generic-other bucket's
    DeductionUs54F) always showed the pre-exemption gain as if no
    exemption existed, and the DeducClaimDtlsUs54/etc detail arrays were
    always empty regardless of real claims. This does not change the
    actual tax computed (the pre-existing aggregate-level
    compute_exemptions()/eligible_exemption mechanism already applies the
    exemption correctly exactly once) -- only the disclosure granularity."""
    input_data = _input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                date_of_acquisition=date(2020, 1, 1), date_of_transfer=date(2025, 6, 1),
                full_consideration=Decimal("5000000"), cost_of_acquisition=Decimal("2000000"),
                exemptions=[
                    CapitalGainExemptionClaim(
                        section="54", transfer_date=date(2025, 6, 1),
                        eligible_gain=Decimal("3000000"), investment_amount=Decimal("1000000"),
                        investment_date=date(2025, 7, 1),
                    ),
                ],
            ),
            CGTransaction(
                asset_type=CGAssetType.LISTED_SECURITY,
                date_of_acquisition=date(2020, 1, 1), date_of_transfer=date(2025, 6, 1),
                full_consideration=Decimal("1000000"), cost_of_acquisition=Decimal("400000"),
                exemptions=[
                    CapitalGainExemptionClaim(
                        section="54F", transfer_date=date(2025, 6, 1),
                        eligible_gain=Decimal("600000"), investment_amount=Decimal("300000"),
                        investment_date=date(2025, 7, 1),
                    ),
                ],
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    cg = document["ITR"]["ITR2"]["ScheduleCGFor23"]

    land_row = cg["LongTermCapGain23"]["SaleofLandBuild"]["SaleofLandBuildDtls"][0]
    assert land_row["Balance"] == 3000000  # pre-exemption "1c"
    assert land_row["ExemptionOrDednUs54"]["ExemptionGrandTotal"] == 1000000
    assert land_row["ExemptionOrDednUs54"]["ExemptionOrDednUs54Dtls"] == [
        {"ExemptionSecCode": "54", "ExemptionAmount": 1000000}
    ]
    assert land_row["LTCGonImmvblPrprty"] == 2000000  # post-exemption "1e" = 3000000 - 1000000

    other_assets = cg["LongTermCapGain23"]["SaleofAssetNADtls"]["SaleofAssetNA"]
    assert other_assets["BalanceCG"] == 600000  # pre-exemption
    assert other_assets["DeductionUs54F"] == 300000
    assert other_assets["CapgainonAssets"] == 300000  # post-exemption

    claims = cg["DeducClaimInfo"]
    assert claims["DeducClaimDtlsUs54"] == [
        {"DateofTransfer": "2025-06-01", "AmtDeducted": 1000000, "CostofNewResHouse": 1000000, "DateofPurchase": "2025-07-01"}
    ]
    assert claims["DeducClaimDtlsUs54F"] == [
        {"DateofTransfer": "2025-06-01", "AmtDeducted": 300000, "CostofNewResHouse": 300000, "DateofPurchase": "2025-07-01"}
    ]
    assert claims["TotDeductClaim"] == 1300000

    # The actual taxable total is unaffected by per-row disclosure -- the
    # pre-existing aggregate mechanism still applies eligible_exemption
    # exactly once to the real GTI/tax computation: total LTCG
    # (3000000 + 600000 = 3600000) minus the aggregate exemption
    # (1000000 + 300000 = 1300000) = 2300000.
    result = compute(input_data)
    assert result.schedules["cg"].total_capital_gains == Decimal("2300000")


def test_generic_other_assets_bucket_maps_jewellery_and_bonds() -> None:
    """Jewellery/bonds/depreciable-asset/etc. transactions -- previously
    always emitted as a zero placeholder regardless of real data -- now
    populate the official Schedule CG item 5/8 "assets other than unquoted
    shares" generic bucket, and reconcile with the calculator's own signed
    STCG/LTCG totals.
    """
    input_data = _input(
        cg_transactions=[
            # Short-term jewellery.
            CGTransaction(
                asset_type=CGAssetType.JEWELLERY,
                description="Gold jewellery",
                date_of_acquisition=date(2024, 8, 1),
                date_of_transfer=date(2025, 2, 1),
                full_consideration=Decimal("500000"),
                cost_of_acquisition=Decimal("350000"),
            ),
            # Long-term bonds/debentures.
            CGTransaction(
                asset_type=CGAssetType.BONDS_DEBENTURES,
                description="NCDs",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 6, 1),
                full_consideration=Decimal("1000000"),
                cost_of_acquisition=Decimal("800000"),
                expenditure_on_transfer=Decimal("5000"),
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    cg = document["ITR"]["ITR2"]["ScheduleCGFor23"]

    stcg_other = cg["ShortTermCapGainFor23"]["SaleOnOtherAssets"]
    assert stcg_other["FullValueConsdOthUnqshr"] == 500000
    assert stcg_other["FullValueConsdRecvUnqshr"] == 0  # no unquoted-shares transaction here
    assert stcg_other["FullConsideration"] == 500000
    assert stcg_other["DeductSec48"]["AquisitCost"] == 350000
    assert stcg_other["BalanceCG"] == 150000
    assert stcg_other["CapgainonAssets"] == 150000
    assert stcg_other["LossSec94of7Or94of8"] == 0

    ltcg_other = cg["LongTermCapGain23"]["SaleofAssetNADtls"]["SaleofAssetNA"]
    assert ltcg_other["FullValueConsdOthUnqshr"] == 1000000
    assert ltcg_other["DeductSec48"]["AquisitCost"] == 800000
    assert ltcg_other["DeductSec48"]["ExpOnTrans"] == 5000
    assert ltcg_other["BalanceCG"] == 195000
    assert ltcg_other["DeductionUs54F"] == 0

    # Reconciles with the calculator's own signed totals -- confirms the
    # new detail rows aren't just schema-valid but actually agree with the
    # aggregate tax computation.
    assert result.schedules["cg"].stcg.income_30per == Decimal("150000")
    assert result.schedules["cg"].ltcg.income_125per_other == Decimal("195000")


def test_generic_other_assets_bucket_applies_section_50ca_for_unquoted_shares() -> None:
    """Unquoted-share transactions route into the unquoted-shares sub-fields
    with section 50CA deeming -- a straight higher-of-consideration-or-FMV
    comparison, unlike section 50C's 110% tolerance band for land/building.
    """
    input_data = _input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.UNLISTED_SHARES,
                description="Pvt Ltd shares",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 6, 1),
                full_consideration=Decimal("200000"),
                fair_market_value_50ca=Decimal("350000"),  # FMV exceeds consideration
                cost_of_acquisition=Decimal("100000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleCGFor23"]["LongTermCapGain23"]["SaleofAssetNADtls"]["SaleofAssetNA"]
    assert row["FullValueConsdRecvUnqshr"] == 200000
    assert row["FairMrktValueUnqshr"] == 350000
    assert row["FullValueConsdSec50CA"] == 350000  # deemed value: higher of the two, no tolerance band
    assert row["FullConsideration"] == 350000
    assert row["BalanceCG"] == 250000  # 350000 - 100000


def test_tds2_tds3_tcs_carry_ownership_and_brought_forward_data() -> None:
    """TDS2/TDS3/TCS credits report real ownership, brought-forward, and
    carry-forward data instead of always hardcoding "Self"/zero.

    Regression test for a defect where the ITR-2 builder hardcoded
    ``TDSCreditName``/``TCSCreditOwner`` to "Self" and ``BroughtFwdTDSAmt``
    to 0 regardless of the taxpayer's actual entry -- even though the
    frontend's ``ReturnDraft.taxes.tds``/``taxes.tcs`` rows (``TdsCredit``/
    ``TcsCredit``) already captured this data; it was dropped when mapped
    into the (until this fix) narrower canonical ``TDS2Entry``/
    ``TDS3Entry``/``TCSEntry`` types.
    """
    input_data = _input(
        tds2_entries=[
            TDS2Entry(
                deductor_tan="DELA00001A",
                tds_section="94A",
                gross_amount=Decimal("10000"),
                tds_deducted=Decimal("1000"),
                tds_claimed_this_year=Decimal("1000"),
                financial_year="2024-25",
                brought_forward_tds=Decimal("200"),
                tds_credit_carried_forward=Decimal("0"),
                ownership="O",
                pan_of_other_person="BBBPB5678C",
                aadhaar_of_other_person="123456789012",
            )
        ],
        tds3_entries=[
            TDS3Entry(
                tenant_pan="CCCPC9012D",
                tenant_name="Tenant Pvt Ltd",
                gross_receipt=Decimal("500000"),
                tds_deducted=Decimal("50000"),
                tds_claimed=Decimal("50000"),
                tds_section="195",
                deducted_yr="2024",
                brought_forward_tds=Decimal("5000"),
                tds_credit_carried_forward=Decimal("1000"),
                ownership="O",
                pan_of_other_person="BBBPB5678C",
            )
        ],
        tds3_filing_details=[
            TDS3FilingDetail(buyer_tenant_pan="CCCPC9012D", head_of_income="OS"),
        ],
        tcs_entries=[
            TCSEntry(
                collector_tan="DELA00002B",
                tcs_section="206C",
                gross_amount=Decimal("100000"),
                tcs_collected=Decimal("10000"),
                tcs_credit_claimed=Decimal("6000"),
                financial_year="2024-25",
                ownership="2",
                pan_of_spouse_or_other_person="DDDPD3456E",
                tcs_collected_spouse_or_other=Decimal("4000"),
                tcs_credit_claimed_spouse_or_other=Decimal("2500"),
                brought_forward_tds=Decimal("100"),
            )
        ],
        bank_accounts=[
            BankAccount(
                account_number="1234567890",
                ifsc_code="SBIN0000001",
                bank_name="State Bank of India",
                account_type="savings",
                is_primary=True,
            )
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    payload = document["ITR"]["ITR2"]

    tds2_row = payload["ScheduleTDS2"]["TDSOthThanSalaryDtls"][0]
    assert tds2_row["TDSCreditName"] == "O"
    assert tds2_row["PANofOtherPerson"] == "BBBPB5678C"
    assert tds2_row["AadhaarOfOtherPerson"] == "123456789012"
    assert tds2_row["BroughtFwdTDSAmt"] == 200

    tds3_row = payload["ScheduleTDS3"]["TDS3onOthThanSalDtls"][0]
    assert tds3_row["TDSCreditName"] == "O"
    assert tds3_row["PANofOtherPerson"] == "BBBPB5678C"
    assert tds3_row["BroughtFwdTDSAmt"] == 5000
    assert tds3_row["AmtCarriedFwd"] == 1000

    tcs_row = payload["ScheduleTCS"]["TCS"][0]
    assert tcs_row["TCSCreditOwner"] == "2"
    assert tcs_row["PANOfSpouseOrOthrPrsn"] == "DDDPD3456E"
    assert tcs_row["TCSCurrFYDtls"]["TCSAmtCollSpouseOrOthrHand"] == 4000
    assert tcs_row["TCSClaimedThisYearDtls"]["TCSAmtCollSpouseOrOthrHand"] == 2500
    assert tcs_row["BroughtFwdTDSAmt"] == 100
    assert payload["ScheduleTCS"]["TotalSchTCS"] == 8500  # 6000 own + 2500 spouse


def test_schedule_os_serializes_lottery_pf_and_gift_income() -> None:
    """Schedule OS emits real lottery/PF/gift data, not zero placeholders.

    Regression test for the §3.4 finding: ``_schedule_os()`` initialized
    ``LtryPzzlChrgblUs115BB``/``TaxAccumulatedBalRecPF``/``Tot562x`` and the
    section-56(2)(x) category breakdown to zero unconditionally -- none of
    winnings, accumulated PF, or gifts had any path into ``ITR2Input`` at
    all for ITR-2 before this fix.
    """
    input_data = _input(
        other_sources_income=OtherSourcesIncome(income_56_2_x=Decimal("75000")),
        si_entries=[
            ScheduleSIEntry(section="115BB", gross_income=Decimal("50000")),
            ScheduleSIEntry(section="111", gross_income=Decimal("30000")),
        ],
        os_gift_breakdown=OSGiftBreakdown(aggregate_without_consideration=Decimal("75000")),
        os_pf_income_benefit=Decimal("30000"),
        os_pf_tax_benefit=Decimal("3000"),
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    os_block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]

    assert os_block["LtryPzzlChrgblUs115BB"] == 50000
    assert os_block["Tot562x"] == 75000
    assert os_block["Aggrtvaluewithoutcons562x"] == 75000
    assert os_block["TaxAccumulatedBalRecPF"] == {"TotalIncomeBenefit": 30000, "TotalTaxBenefit": 3000}


def test_schedule_it_serializes_complete_challan_rows() -> None:
    """A complete tax-payment challan row reaches Schedule IT correctly."""
    input_data = _input(
        tax_payment_entries=[
            TaxPaymentDetail(
                amount=Decimal("50000"), payment_type="advance",
                payment_date=date(2025, 12, 15), bsr_code="1234567",
                challan_serial_number="12345",
            ),
        ],
        bank_accounts=[
            BankAccount(
                account_number="1234567890",
                ifsc_code="SBIN0000001",
                bank_name="State Bank of India",
                account_type="savings",
                is_primary=True,
            )
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    schedule_it = document["ITR"]["ITR2"]["ScheduleIT"]
    row = schedule_it["TaxPayment"][0]
    assert row["BSRCode"] == "1234567"
    assert row["DateDep"] == "2025-12-15"
    assert row["SrlNoOfChaln"] == 12345
    assert row["Amt"] == 50000
    assert schedule_it["TotalTaxPayments"] == 50000


def test_schedule_it_incomplete_challan_error_names_row_and_missing_fields() -> None:
    """An incomplete challan row's error identifies the row and the exact
    missing field(s), not just a generic "requires BSR code..." message.

    Regression test for audit §3.8: the old message
    ("Schedule IT payment requires BSR code, date, and challan serial
    number") gave no indication of which row was wrong or which of the
    three fields it was actually missing, forcing a taxpayer/support agent
    to guess across every entered challan.
    """
    input_data = _input(
        tax_payment_entries=[
            TaxPaymentDetail(
                amount=Decimal("50000"), payment_type="advance",
                payment_date=date(2025, 12, 15), bsr_code="1234567",
                challan_serial_number="12345",
            ),
            TaxPaymentDetail(
                amount=Decimal("20000"), payment_type="self_assessment",
                bsr_code="7654321",
            ),
        ],
        bank_accounts=[
            BankAccount(
                account_number="1234567890",
                ifsc_code="SBIN0000001",
                bank_name="State Bank of India",
                account_type="savings",
                is_primary=True,
            )
        ],
    )
    with pytest.raises(ValueError, match=r"entry #2 is missing: payment date, challan serial number"):
        build_itr2_json(compute(input_data), input_data)


def test_schedule_os_serializes_unexplained_income_89a_deductions_and_dtaa() -> None:
    """Optional Schedule OS fields (unexplained income, §89A, other-income
    detail, deductions, DTAA) all reach the official JSON, not just the
    mandatory dividend/interest/family-pension aggregates.

    Per explicit user instruction: the system must input and process every
    schema field, mandatory or optional, not just the fields required for a
    schema-valid minimal return.
    """
    input_data = _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("5000")),
        # The mapper (draft_to_itr2_input.py) is what actually routes
        # os_unexplained_income's total into a "115BBE" Schedule-SI entry --
        # this builder-level test supplies the matching entry directly,
        # exactly like test_schedule_os_serializes_lottery_pf_and_gift_income
        # already does for winnings/PF, since _schedule_os() itself only
        # reads si_entries for the 115BBE tax figure.
        si_entries=[ScheduleSIEntry(section="115BBE", gross_income=Decimal("150000"))],
        os_unexplained_income=OSUnexplainedIncome(
            cash_credits_us68=Decimal("100000"),
            unexplained_money_us69a=Decimal("50000"),
        ),
        os_section_89a=OSSection89A(
            income_notified=Decimal("200000"),
            relief=Decimal("15000"),
            country_entries=[OS89ACountryEntry(country_code="US", amount=Decimal("200000"))],
        ),
        os_other_income_entries=[
            OSOtherIncomeEntry(nature="Freelance consulting", amount=Decimal("30000")),
        ],
        os_dtaa_entries=[
            OSDtaaEntry(
                amount=Decimal("40000"), nature_of_income="1ai",
                country_name="Singapore", country_code="65", dtaa_article="11",
                rate_as_per_treaty=Decimal("10"), rate_as_per_it_act=Decimal("20"),
                tax_residency_certificate="Y", item_no_incl="5A1ai",
                applicable_rate=Decimal("10"),
            ),
        ],
        os_dtaa_aggregate=Decimal("4000"),
        os_deductions=OSDeductions(expenses=Decimal("2000"), depreciation=Decimal("1000")),
        bank_accounts=[
            BankAccount(
                account_number="1234567890", ifsc_code="SBIN0000001",
                bank_name="State Bank of India", account_type="savings", is_primary=True,
            )
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    os_block = document["ITR"]["ITR2"]["ScheduleOS"]
    block = os_block["IncOthThanOwnRaceHorse"]

    assert block["CashCreditsUs68"] == 100000
    assert block["UnExplndMoneyUs69A"] == 50000
    # 115BBE special-rate tax on the unexplained-income total.
    assert block["IncChrgblUs115BBE"] == 150000

    assert block["IncomeNotified89AOS"] == 200000
    assert block["Increliefus89AOS"] == 15000
    assert block["IncomeNotified89ATypeOS"] == [{"NOT89ACountrycode": "US", "NOT89AAmount": 200000}]

    assert block["AnyOtherIncome"] == 30000
    assert block["OthersInc"]["OthersIncDtls"] == [{"OthNatOfInc": "Freelance consulting", "OthAmount": 30000}]

    assert block["Deductions"]["Expenses"] == 2000
    assert block["Deductions"]["Depreciation"] == 1000

    assert block["IncChargblSplRateOS"]["TotalAmtTaxUsDTAASchOs"] == 4000
    dtaa_row = block["IncChargblSplRateOS"]["NRIOsDTAA"]["NRIDTAADtlsSchOS"][0]
    assert dtaa_row["DTAAamt"] == 40000
    assert dtaa_row["CountryName"] == "Singapore"
    assert dtaa_row["NatureOfIncome"] == "1ai"


def test_schedule_os_serializes_dividend_section_breakdown() -> None:
    """Dividend rows preserve their official section classification
    (Dividend22e/Dividend22f split, DTAA/115A-series date-range fields),
    not just the undifferentiated aggregate."""
    input_data = _input(
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("100000")),
        os_dividend_entries=[
            OSDividendEntry(section="10(22e)", amount=Decimal("30000")),
            OSDividendEntry(section="DTAA", amount=Decimal("20000"), q2=Decimal("20000")),
            OSDividendEntry(section="194", amount=Decimal("50000")),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    os_block = document["ITR"]["ITR2"]["ScheduleOS"]
    block = os_block["IncOthThanOwnRaceHorse"]

    assert block["Dividend22e"] == 30000
    assert block["Dividend22f"] == 0
    assert block["DividendOthThan22e"] == 70000  # 100000 - 30000
    assert os_block["DividendDTAA"]["DateRange"]["Upto15Of9"] == 20000


def test_schedule_os_serializes_race_horse_activity_and_includes_net_profit_in_gti() -> None:
    """Race-horse-activity net profit reaches IncFromOwnHorse AND is
    included in GTI (as slab-rate Other Sources income) -- previously this
    entire sub-schedule had no data path into ITR2Input at all."""
    input_data = _input(
        os_race_horse=OSRaceHorseActivity(
            receipts=Decimal("500000"), deduction_us57=Decimal("300000"),
            balance=Decimal("200000"),
        ),
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    os_block = document["ITR"]["ITR2"]["ScheduleOS"]

    assert os_block["IncFromOwnHorse"]["Receipts"] == 500000
    assert os_block["IncFromOwnHorse"]["BalanceOwnRaceHorse"] == 200000
    # The race-horse profit is included in GTI (IncChargeable) but excluded
    # from BalanceNoRaceHorse/TotOthSrcNoRaceHorse, matching the official
    # form's own "no race horse" naming.
    assert os_block["IncChargeable"] == 200000
    assert os_block["IncOthThanOwnRaceHorse"]["BalanceNoRaceHorse"] == 0
    assert os_block["TotOthSrcNoRaceHorse"] == 0
    assert result.other_sources_income == Decimal("200000")


def test_schedule_os_serializes_machinery_rent_and_pass_through_income() -> None:
    """RentFromMachPlantBldgs and NatofPassThrghIncome reach the JSON --
    previously always hardcoded to zero even though the frontend
    (ScheduleOSWorkspace.tsx) already captures both via specially-tagged
    "other income" rows."""
    input_data = _input(
        os_machinery_plant_rent=Decimal("50000"),
        os_pass_through_income=Decimal("15000"),
        bank_accounts=[
            BankAccount(
                account_number="1234567890", ifsc_code="SBIN0000001",
                bank_name="State Bank of India", account_type="savings", is_primary=True,
            )
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]
    assert block["RentFromMachPlantBldgs"] == 50000
    assert block["NatofPassThrghIncome"] == 15000


def test_schedule_os_dtaa_entries_are_taxed_via_si_at_applicable_rate_and_reach_gti() -> None:
    """DTAA-rate Other Sources income (NRIDTAADtlsSchOS rows) was previously
    disclosure-only -- never taxed, never added to GTI. Each entry's own
    per-treaty `applicable_rate` (section 90(2) beneficial-treatment rate)
    now drives a dedicated Schedule SI "DTAAOS" entry, and the amount
    reaches Gross Total Income."""
    input_data = _input(
        os_dtaa_entries=[
            OSDtaaEntry(
                amount=Decimal("100000"), nature_of_income="1b",
                country_name="Singapore", country_code="65", dtaa_article="12",
                rate_as_per_treaty=Decimal("10"), rate_as_per_it_act=Decimal("20"),
                tax_residency_certificate="Y", item_no_incl="5A1bA",
                applicable_rate=Decimal("10"),
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)

    si = document["ITR"]["ITR2"]["ScheduleSI"]
    dtaa_row = next(row for row in si["SplCodeRateTax"] if row["SecCode"] == "DTAAOS")
    assert dtaa_row["SplRatePercent"] == 10
    assert dtaa_row["SplRateInc"] == 100000
    assert dtaa_row["SplRateIncTax"] == 10000

    assert result.other_sources_income == Decimal("100000")


def test_schedule_os_serializes_nri_special_rate_entries_and_taxes_them_via_si() -> None:
    """Section 115A/115AC/115ACA/115AD/115E "any other income chargeable at
    special rate" rows (Schedule OS's OthersGrossDtls dropdown) previously
    had no data path at all -- this now wires disclosure (OthersGross/
    OthersGrossDtls, IncChargeableSpecialRates), Schedule SI taxation at the
    correct statutory rate per code, and GTI inclusion, all from one input
    field."""
    input_data = _input(
        os_special_rate_entries=[
            OSSpecialRateEntry(source_description="5A1bA", source_amount=Decimal("100000")),  # royalty/FTS @20%
            OSSpecialRateEntry(source_description="5AD1i", source_amount=Decimal("50000")),  # FII income @20%
            OSSpecialRateEntry(source_description="5Ea", source_amount=Decimal("20000")),  # 115E investment income
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)

    os_block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]
    assert os_block["OthersGross"] == 170000
    assert {
        (row["SourceDescription"], row["SourceAmount"]) for row in os_block["OthersGrossDtls"]
    } == {("5A1bA", 100000), ("5AD1i", 50000), ("5Ea", 20000)}
    assert os_block["IncChargeableSpecialRates"] == 170000

    si = document["ITR"]["ITR2"]["ScheduleSI"]
    si_by_code = {row["SecCode"]: row for row in si["SplCodeRateTax"]}
    assert si_by_code["5A1bA"]["SplRatePercent"] == 20
    assert si_by_code["5A1bA"]["SplRateIncTax"] == 20000
    assert si_by_code["5AD1i"]["SplRatePercent"] == 20
    assert si_by_code["5Ea"]["SplRateIncTax"] == 4000  # 115E(a) @20%
    assert si["TotSplRateInc"] == 170000

    # All three amounts are gross OS income and must reach GTI, the same
    # way 111A/112A/VDA capital-gains special-rate income does.
    assert result.other_sources_income == Decimal("170000")


def test_pti_hp_and_os_head_entries_reach_gti_and_schedule_pti() -> None:
    """HP-head and OS-head Schedule PTI entries reach both the JSON
    disclosure (SchedulePTIDtls) AND actual GTI -- previously only the
    disclosure existed; STCG/LTCG-head entries already dispatched to
    Schedule SI, but HP/OS heads had no GTI-inclusion path at all."""
    input_data = _input(
        pti_entries=[
            PTIEntry(
                entity_name="ABC REIT", entity_pan="AAATA1234B",
                income_head="HP", section="115UA", income_amount=Decimal("50000"),
            ),
            PTIEntry(
                entity_name="XYZ InvIT", entity_pan="AAATX1234B",
                income_head="OS", section="115UB", income_amount=Decimal("30000"),
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)

    pti_rows = document["ITR"]["ITR2"]["SchedulePTI"]["SchedulePTIDtls"]
    assert len(pti_rows) == 2
    hp_row = next(r for r in pti_rows if r["BusinessName"] == "ABC REIT")
    assert hp_row["IncFromHP"]["NetIncomeLoss"] == 50000
    os_row = next(r for r in pti_rows if r["BusinessName"] == "XYZ InvIT")
    assert os_row["IncOthSrc"]["NetIncomeLoss"] == 30000

    assert result.house_property_income == Decimal("50000")
    assert result.other_sources_income == Decimal("30000")


def test_schedule_hp_self_occupied_interest_is_capped_not_raw() -> None:
    """Self-occupied home-loan interest above the Sec 24(b) old-regime cap
    (Rs 2,00,000) must be reported CAPPED in Schedule HP, matching what the
    calculator actually allows -- not the raw, uncapped amount. The builder
    previously recomputed IntOnBorwCap/IncomeOfHP from raw input fields
    instead of the real per-property HPResult, via a dead
    ``hasattr(hp_res, "interest_deduction")`` check (HPResult's real field is
    named ``interest_on_loan``, so the hasattr always failed silently and
    fell through to the uncapped raw value)."""
    input_data = _input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("350000"),
        ),
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="12 MG Road",
                city_or_town_or_district="Pune",
                state_code="27",
                pin_code="411001",
            ),
        ],
    )
    result = compute(input_data)
    assert result.house_property_income == Decimal("-200000")

    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    rent_details = document["ITR"]["ITR2"]["ScheduleHP"]["PropertyDetails"][0]["Rentdetails"]
    assert rent_details["IntOnBorwCap"] == 200000
    assert rent_details["Section24B"]["TotalInterestUs24B"] == 200000
    assert rent_details["IncomeOfHP"] == -200000


def test_schedule_hp_reflects_rent_not_realized_and_arrears() -> None:
    """RentNotRealized and ArrearsUnrealizedRentRcvd must reflect the real
    values the calculator already applies (rent_not_realized reduces ALV;
    arrears are 70%-taxable u/s 25A and added to income_chargeable) --
    previously RentNotRealized was hardcoded to 0 and arrears were never
    emitted at all, while IncomeOfHP was independently recomputed without
    either adjustment, so it could disagree with the calculator's real
    per-property HPResult and with result.house_property_income."""
    input_data = _input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("300000"),
            rent_not_realized=Decimal("20000"),
            municipal_taxes_paid=Decimal("10000"),
            arrears_unrealised_rent_received=Decimal("50000"),
        ),
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="45 Park Street",
                city_or_town_or_district="Kolkata",
                state_code="19",
                pin_code="700016",
            ),
        ],
    )
    result = compute(input_data)
    # NAV = 300000 - 20000 - 10000 = 270000; std ded = 30% = 81000
    # income = 270000 - 81000 + 0.7*50000 = 224000
    assert result.house_property_income == Decimal("224000")

    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    rent_details = document["ITR"]["ITR2"]["ScheduleHP"]["PropertyDetails"][0]["Rentdetails"]
    assert rent_details["RentNotRealized"] == 20000
    assert rent_details["ArrearsUnrealizedRentRcvd"] == 50000
    assert rent_details["BalanceALV"] == 270000
    assert rent_details["ThirtyPercentOfBalance"] == 81000
    assert rent_details["IncomeOfHP"] == 224000


def test_schedule_hp_serializes_loan_co_owner_and_tenant_detail_rows() -> None:
    """Section24BDtls/CoOwners/TenantDetails were previously always emitted
    empty regardless of real input -- PropertyFilingDetail now carries
    home_loan_details/co_owner_details/tenant_details, and the builder
    must serialize real rows and cross-foot the loan rows' interest against
    the property's actual computed Section 24(b) interest."""
    input_data = _input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("600000"),
            home_loan_interest_paid=Decimal("150000"),
        ),
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="7 MG Road",
                city_or_town_or_district="Bengaluru",
                state_code="29",
                pin_code="560001",
                co_owned=True,
                home_loan_details=[
                    HomeLoanDetail(
                        loan_taken_from="B",
                        bank_or_institution_name="HDFC Bank",
                        loan_account_or_ref_no="HL123456",
                        date_of_loan=date(2018, 4, 1),
                        total_loan_amount=Decimal("5000000"),
                        loan_outstanding_amount=Decimal("3000000"),
                        interest_this_year=Decimal("150000"),
                    ),
                ],
                co_owner_details=[
                    CoOwnerDetail(name="Spouse Name", pan="BBBPB5678C", percent_share=Decimal("50")),
                ],
                tenant_details=[
                    TenantDetail(name="Tenant Pvt Ltd", pan="CCCPC9012D"),
                ],
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleHP"]["PropertyDetails"][0]

    loan_row = row["Rentdetails"]["Section24B"]["Section24BDtls"][0]
    assert loan_row["BankOrInstnName"] == "HDFC Bank"
    assert loan_row["LoanAccNoOfBankOrInstnRefNo"] == "HL123456"
    assert loan_row["InterestUs24B"] == 150000
    assert row["Rentdetails"]["Section24B"]["TotalInterestUs24B"] == 150000

    co_owner_row = row["CoOwners"][0]
    assert co_owner_row["NameCoOwner"] == "Spouse Name"
    assert co_owner_row["PAN_CoOwner"] == "BBBPB5678C"
    assert co_owner_row["PercentShareProperty"] == 50.0

    tenant_row = row["TenantDetails"][0]
    assert tenant_row["NameofTenant"] == "Tenant Pvt Ltd"
    assert tenant_row["PANofTenant"] == "CCCPC9012D"


def test_schedule_hp_rejects_loan_rows_that_dont_cross_foot_to_real_interest() -> None:
    """A home_loan_details total that disagrees with the property's real
    computed Section 24(b) interest must be rejected, not silently
    accepted -- matching this project's established cross-foot discipline."""
    input_data = _input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("600000"),
            home_loan_interest_paid=Decimal("150000"),
        ),
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="7 MG Road",
                city_or_town_or_district="Bengaluru",
                state_code="29",
                pin_code="560001",
                home_loan_details=[
                    HomeLoanDetail(
                        loan_taken_from="B",
                        bank_or_institution_name="HDFC Bank",
                        loan_account_or_ref_no="HL123456",
                        date_of_loan=date(2018, 4, 1),
                        total_loan_amount=Decimal("5000000"),
                        loan_outstanding_amount=Decimal("3000000"),
                        interest_this_year=Decimal("100000"),  # real interest is 150000
                    ),
                ],
            ),
        ],
    )
    result = compute(input_data)
    with pytest.raises(ValueError, match="cross-foot"):
        build_itr2_json(result, input_data)


def test_property_filing_detail_requires_co_owner_rows_when_co_owned_flag_set() -> None:
    """A bare co_owned=True with no backing co_owner_details is exactly the
    "flag with no detail" bug class already found and fixed once in
    Schedule HP -- the schema itself now makes it impossible to construct."""
    with pytest.raises(ValueError, match="co_owner_details"):
        PropertyFilingDetail(
            address_detail="7 MG Road",
            city_or_town_or_district="Bengaluru",
            state_code="29",
            pin_code="560001",
            co_owned=True,
        )


def test_schedule_s_standard_deduction_does_not_silently_zero_on_mismatch() -> None:
    """_schedule_s() back-derives DeductionUnderSection16ia as
    ``max(0, net_salary - result.salary_income - ...)`` where net_salary
    comes from tds1_entries (a separate, independently-editable model from
    the SalaryIncome the calculator actually taxes). Nothing keeps the two
    in sync -- ITR2-IN-TDS-004 only bounds tds_deducted, never
    income_chargeable -- so if an employer's reported TDS1
    income_chargeable is smaller than what SalaryIncome yields once taxed,
    the subtraction goes negative and the previous code silently clamped
    it to 0, hiding a real standard deduction the calculator actually
    applied (and producing a Schedule S row whose own Gross/Net/Deduction
    arithmetic no longer cross-foots to TotIncUnderHeadSalaries)."""
    input_data = _input(
        salary_income=SalaryIncome(gross_salary=Decimal("1000000")),
        tds1_entries=[
            TDS1Entry(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                income_chargeable=Decimal("900000"),
                tds_deducted=Decimal("50000"),
            ),
        ],
        employer_filing_details=[
            EmployerFilingDetail(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                address_detail="1 Corporate Park",
                city_or_town_or_district="Mumbai",
                state_code="27",
            ),
        ],
    )
    result = compute(input_data)
    # Old-regime standard deduction: min(50000, gross) = 50000.
    assert result.salary_income == Decimal("950000")

    with pytest.raises(ValueError, match="Schedule S"):
        build_itr2_json(result, input_data)


def test_schedule_s_serializes_real_perquisites_profits_in_lieu_and_relief_89() -> None:
    """ValueOfPerquisites and ProfitsinLieuOfSalary were hardcoded to 0
    regardless of source.perquisites_value/profits_in_lieu_of_salary (real,
    user-suppliable schema fields the calculator already taxes as part of
    gross salary); Increliefus89A was hardcoded to 0 regardless of
    result.relief_89. All three are single-employer-attributable here."""
    input_data = _input(
        salary_income=SalaryIncome(
            gross_salary=Decimal("900000"),
            perquisites_value=Decimal("50000"),
            profits_in_lieu_of_salary=Decimal("20000"),
        ),
        relief_89=Decimal("15000"),
        tds1_entries=[
            TDS1Entry(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                income_chargeable=Decimal("970000"),  # 900000 + 50000 + 20000
                tds_deducted=Decimal("50000"),
            ),
        ],
        employer_filing_details=[
            EmployerFilingDetail(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                address_detail="1 Corporate Park",
                city_or_town_or_district="Mumbai",
                state_code="27",
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    schedule_s = document["ITR"]["ITR2"]["ScheduleS"]
    salarys = schedule_s["Salaries"][0]["Salarys"]
    assert salarys["GrossSalary"] == 970000
    assert salarys["ValueOfPerquisites"] == 50000
    assert salarys["ProfitsinLieuOfSalary"] == 20000
    assert salarys["Salary"] == 900000  # 970000 - 50000 - 20000
    assert schedule_s["Increliefus89A"] == 15000


def test_schedule_s_reports_real_section_10_exemption_breakdown() -> None:
    """AllwncExemptUs10Dtls was always hardcoded to an empty array, even
    though the calculator already computes a full per-category exemption
    breakdown (gratuity/leave-encashment/VRS/etc. -- SalaryResult) that was
    simply never read. AllwncExtentExemptUs10/NetSalary/
    DeductionUnderSection16ia now come from the real SalaryResult too,
    instead of being re-derived locally from only hra+lta."""
    input_data = _input(
        salary_income=SalaryIncome(
            gross_salary=Decimal("800000"),
            gratuity_received=Decimal("300000"),
            is_cg_sg_employee=True,
            lta_exempt_amount=Decimal("10000"),
        ),
        tds1_entries=[
            TDS1Entry(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                income_chargeable=Decimal("1100000"),  # 800000 + 300000 gratuity received
                tds_deducted=Decimal("50000"),
            ),
        ],
        employer_filing_details=[
            EmployerFilingDetail(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                address_detail="1 Corporate Park",
                city_or_town_or_district="Mumbai",
                state_code="27",
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    schedule_s = document["ITR"]["ITR2"]["ScheduleS"]
    rows = schedule_s["AllwncExemptUs10"]["AllwncExemptUs10Dtls"]
    codes = {r["SalNatureDesc"] for r in rows}
    assert "10(10)" in codes  # gratuity -- govt employee, fully exempt
    assert "10(5)" in codes  # LTA
    assert "10(13A)" not in codes  # HRA has its own dedicated block, not this array
    gratuity_row = next(r for r in rows if r["SalNatureDesc"] == "10(10)")
    assert gratuity_row["SalOthAmount"] == 300000
    assert schedule_s["AllwncExtentExemptUs10"] == 310000  # 300000 gratuity + 10000 LTA


def test_schedule_cfl_reports_race_horse_loss_instead_of_dropping_it() -> None:
    """A brought-forward race-horse activity loss (LossHead.RACE_HORSE,
    Section 74A) is tracked correctly through BFLA (unset-off, carried
    forward as its own entry -- confirmed at
    app/engine/schedules/loss_setoff/bfla.py:120-174, where no head branch
    matches "RaceHorse" so the full brought-forward amount passes through
    as remaining) but _schedule_cfl()'s summary() helper only recognizes
    HP/STCG/CG/LTCG heads -- a RaceHorse-head entry matched none of them,
    so its loss_remaining was dropped from every total, INCLUDING the one
    field literally named for it (OthSrcLossRaceHorseCF), which stayed
    hardcoded at 0 regardless of the real disclosed loss."""
    input_data = _input(
        bf_losses=[
            BFLossItem(
                assessment_year="2024-25",
                head=LossHead.RACE_HORSE,
                original_loss=Decimal("40000"),
                brought_forward=Decimal("40000"),
                date_of_filing=date(2024, 7, 31),
            ),
        ],
    )
    result = compute(input_data)
    cfl_entries = [e for coll in result.schedules.get("cfl", []) for e in coll.entries]
    race_horse_entry = next(e for e in cfl_entries if e.head == "RaceHorse")
    assert race_horse_entry.loss_remaining == Decimal("40000")

    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    cfl = document["ITR"]["ITR2"]["ScheduleCFL"]
    year_detail = cfl["LossCFFromPrev2ndYearFromAY"]["CarryFwdLossDetail"]
    assert year_detail["OthSrcLossRaceHorseCF"] == 40000
    assert cfl["TotalLossCFSummary"]["LossSummaryDetail"]["OthSrcLossRaceHorseCF"] == 40000


def test_schedule_cfl_requires_date_of_filing_instead_of_silently_omitting_it() -> None:
    """DateOfFiling is unconditionally required by the official schema for
    every Schedule CFL year-slot (both CarryFwdLossDetail and
    CarryFwdWithoutLossDetail) -- BFLossItem.date_of_filing is Optional in
    the Pydantic schema, and the previous code silently left the field out
    whenever it was unset, producing schema-invalid JSON instead of a clear
    error naming the missing input."""
    input_data = _input(
        bf_losses=[
            BFLossItem(
                assessment_year="2024-25",
                head=LossHead.SHORT_TERM_CAPITAL,
                original_loss=Decimal("30000"),
                brought_forward=Decimal("30000"),
            ),
        ],
    )
    result = compute(input_data)
    with pytest.raises(ValueError, match="date_of_filing"):
        build_itr2_json(result, input_data)


def test_schedule_cfl_omits_race_horse_field_for_older_year_slots() -> None:
    """The official schema's 5th-8th-year-back CFL slots (AY2018-19 through
    AY2021-22) use a different type, CarryFwdWithoutLossDetail, which has
    no OthSrcLossRaceHorseCF property at all -- additionalProperties is
    false, so emitting it there (as the previous unconditional summary()
    helper did) is itself a schema violation, independent of whether a
    real race-horse loss exists at that age."""
    input_data = _input(
        bf_losses=[
            BFLossItem(
                assessment_year="2018-19",
                head=LossHead.SHORT_TERM_CAPITAL,
                original_loss=Decimal("20000"),
                brought_forward=Decimal("20000"),
                date_of_filing=date(2018, 7, 31),
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    year_detail = document["ITR"]["ITR2"]["ScheduleCFL"]["LossCFFromPrev8thYearFromAY"]["CarryFwdLossDetail"]
    assert "OthSrcLossRaceHorseCF" not in year_detail


def test_schedule_esop_aggregates_same_year_entries_instead_of_dropping_them() -> None:
    """_schedule_esop() previously built entry_by_ay as
    ``{e.assessment_year: e for e in ...}`` -- a plain dict comprehension
    that keeps only the LAST entry for a given year, silently discarding
    every earlier same-year entry's deferred/payable/carried-forward
    amounts (a real scenario: more than one qualifying ESOP grant vesting
    in the same assessment year). It also used ``first.balance_tax_carried_
    forward`` alone for the running AY2026-27 balance, dropping every other
    entry's outstanding balance. Two entries for AY2024-25 plus one for
    AY2025-26 exercise both bugs at once."""
    input_data = _input(
        esop_deferrals=[
            ESOPDeferralInput(
                employer_pan="AAACS1234A",
                dpiit_registration_number="DIPP12345",
                assessment_year="2024-25",
                tax_deferred_brought_forward=Decimal("2000"),
                tax_payable_current_year=Decimal("10000"),
                balance_tax_carried_forward=Decimal("8000"),
            ),
            ESOPDeferralInput(
                employer_pan="AAACS1234A",
                dpiit_registration_number="DIPP12345",
                assessment_year="2024-25",
                tax_deferred_brought_forward=Decimal("1000"),
                tax_payable_current_year=Decimal("5000"),
                balance_tax_carried_forward=Decimal("3000"),
            ),
            ESOPDeferralInput(
                employer_pan="AAACS1234A",
                dpiit_registration_number="DIPP12345",
                assessment_year="2025-26",
                tax_deferred_brought_forward=Decimal("0"),
                tax_payable_current_year=Decimal("7000"),
                balance_tax_carried_forward=Decimal("6000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    esop = document["ITR"]["ITR2"]["ScheduleESOP"]

    block_2425 = esop["ScheduleESOP2425_Type"]
    assert block_2425["TaxDeferredBFEarlierAY"] == 3000  # 2000 + 1000
    assert block_2425["TaxPayableCurrentAY"] == 15000  # 10000 + 5000
    assert block_2425["BalanceTaxCF"] == 11000  # 8000 + 3000

    block_2526 = esop["ScheduleESOP2526_Type"]
    assert block_2526["TaxPayableCurrentAY"] == 7000
    assert block_2526["BalanceTaxCF"] == 6000

    assert esop["ScheduleESOP2627_Type"]["BalanceTaxCF"] == 17000  # 8000 + 3000 + 6000
    assert esop["TotalTaxAttributedAmt"] == 22000  # 10000 + 5000 + 7000


def test_schedule_fa_bank_account_uses_real_zip_not_truncated_account_number() -> None:
    """The bank-account branch previously set "ZipCode" to
    ``item.account_or_asset_identifier[:8]`` -- the first 8 characters of
    the ACCOUNT NUMBER, not any real postal code -- because the model had
    no dedicated zip_code field at all. Schema-valid (ZipCode's pattern
    accepts any short string) but semantically fabricated data."""
    input_data = _input(
        foreign_assets=[
            ForeignAssetEntry(
                asset_type=ForeignAssetType.BANK_ACCOUNT,
                country_code="44",
                institution_or_entity_name="Chase Bank",
                address="270 Park Avenue, New York",
                zip_code="10017",
                account_or_asset_identifier="123456789012",
                ownership_status="OWNER",
                opening_or_acquisition_date=date(2020, 1, 1),
                peak_value=Decimal("500000"),
                closing_value=Decimal("400000"),
                gross_income=Decimal("2000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleFA"]["DetailsForiegnBank"][0]
    assert row["ZipCode"] == "10017"
    assert row["ForeignAccountNumber"] == "123456789012"


def test_schedule_fa_bank_account_rejects_invalid_owner_status() -> None:
    """OwnerStatus is an official enum (OWNER/BENEFICIAL_OWNER/BENIFICIARY)
    -- an unrecognized value must be rejected, not passed through to
    produce schema-invalid JSON."""
    input_data = _input(
        foreign_assets=[
            ForeignAssetEntry(
                asset_type=ForeignAssetType.BANK_ACCOUNT,
                country_code="US",
                institution_or_entity_name="Chase Bank",
                address="270 Park Avenue, New York",
                zip_code="10017",
                account_or_asset_identifier="123456789012",
                ownership_status="SELF",
                opening_or_acquisition_date=date(2020, 1, 1),
            ),
        ],
    )
    with pytest.raises(ValueError, match="OwnerStatus"):
        build_itr2_json(compute(input_data), input_data)


def test_schedule_fa_immovable_property_uses_correct_official_field_names() -> None:
    """The immovable-property branch previously emitted AddressOfProp,
    DateOfImp, PeakValueOfProp, and IncFromProp -- none of which are valid
    property names for the official DetailsImmovableProperty type
    (the real names are AddressOfProperty, TotalInvestment, IncDrvProperty,
    with no DateOfImp at all) -- and omitted several required fields
    (Ownership, NatureOfInc, IncTaxAmt, IncTaxSch, IncTaxSchNo) entirely.
    With additionalProperties: false, every prior immovable-property
    disclosure was schema-invalid."""
    input_data = _input(
        foreign_assets=[
            ForeignAssetEntry(
                asset_type=ForeignAssetType.IMMOVABLE_PROPERTY,
                country_code="44",
                institution_or_entity_name="N/A",
                address="10 Downing Street area flat, London",
                zip_code="SW1A2AA",
                account_or_asset_identifier="PROP-001",
                ownership_status="DIRECT",
                opening_or_acquisition_date=date(2019, 6, 15),
                peak_value=Decimal("15000000"),
                gross_income=Decimal("300000"),
                income_offered=Decimal("300000"),
                income_head="OS",
                nature_of_income="Rental income",
                income_tax_schedule_item_no="OS-1",
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleFA"]["DetailsImmovableProperty"][0]
    assert row["AddressOfProperty"] == "10 Downing Street area flat, London"
    assert row["Ownership"] == "DIRECT"
    assert row["TotalInvestment"] == 15000000
    assert row["IncDrvProperty"] == 300000
    assert row["NatureOfInc"] == "Rental income"
    assert row["IncTaxSch"] == "OS"
    assert row["IncTaxSchNo"] == "OS-1"
    assert "DateOfImp" not in row
    assert "AddressOfProp" not in row


def test_schedule_fa_other_asset_uses_correct_official_field_names() -> None:
    """The generic "other asset" branch previously emitted NameOfInst,
    AddressOfInst, AcctNumOrIdtyNum, OwnerStatus, PeakBalanceDuringYear,
    ClosingBalance, IncFromOthSrc -- NONE of which are valid property names
    for the official DetailsOthAssets type (whose real fields are
    NatureOfAsset, Ownership, TotalInvestment, IncDrvAsset, NatureOfInc,
    IncTaxAmt, IncTaxSch, IncTaxSchNo). Every prior "other asset"
    disclosure was schema-invalid on both counts: wrong properties present,
    required properties absent."""
    input_data = _input(
        foreign_assets=[
            ForeignAssetEntry(
                asset_type=ForeignAssetType.OTHER_ASSET,
                country_code="971",
                institution_or_entity_name="N/A",
                address="N/A",
                zip_code="00000",
                account_or_asset_identifier="GOLD-001",
                ownership_status="DIRECT",
                opening_or_acquisition_date=date(2021, 3, 1),
                peak_value=Decimal("800000"),
                nature_of_asset="Gold bullion held in a Dubai vault",
                nature_of_income="No income",
                income_tax_schedule_item_no="NA",
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleFA"]["DetailsOthAssets"][0]
    assert row["NatureOfAsset"] == "Gold bullion held in a Dubai vault"
    assert row["Ownership"] == "DIRECT"
    assert row["TotalInvestment"] == 800000
    assert row["IncTaxSch"] == "NI"
    assert "NameOfInst" not in row
    assert "AcctNumOrIdtyNum" not in row


def test_schedule_fa_unsupported_category_fails_closed() -> None:
    """Custodial accounts, equity/debt interests, insurance, financial
    interests, signing authority, trusts, and other foreign-sourced income
    each require official fields ForeignAssetEntry doesn't capture --
    the previous code silently folded all of them into DetailsOthAssets,
    misclassifying them into the wrong official category entirely. Confirm
    this now fails closed instead."""
    input_data = _input(
        foreign_assets=[
            ForeignAssetEntry(
                asset_type=ForeignAssetType.CUSTODIAL_ACCOUNT,
                country_code="SG",
                institution_or_entity_name="DBS Bank",
                address="12 Marina Blvd, Singapore",
                zip_code="018982",
                account_or_asset_identifier="CUST-001",
                ownership_status="DIRECT",
                opening_or_acquisition_date=date(2022, 1, 1),
            ),
        ],
    )
    with pytest.raises(ValueError, match="custodial_account"):
        build_itr2_json(compute(input_data), input_data)


def test_schedule_fa_fsi_tr_derive_real_country_name_from_the_code() -> None:
    """CountryName was fed the exact same raw country_code value as
    CountryCodeExcludingIndia everywhere a foreign country is disclosed
    (Schedule FA, FSI, TR) -- correct only for the latter (a specific
    ~200-entry ITD-bespoke numeric enum, not ISO alpha/numeric), never for
    the former, which needs a real name. Confirm all three now derive a
    real name via the official lookup table, and that TR's own DTAA/non-DTAA
    aggregation (previously matched rows via the fabricated CountryName)
    still cross-foots by country code."""
    input_data = _input(
        fsi_entries=[
            FSICountryEntry(country_code="44", tax_identification_no="UK-TIN-1", salary_income=Decimal("100000")),
        ],
        tr1_entries=[
            TR1Entry(
                country_code="44", tax_identification_no="UK-TIN-1",
                tax_paid_outside_india=Decimal("10000"), indian_tax_payable=Decimal("8000"),
                relief_claimed=Decimal("8000"), relief_section="90",
            ),
        ],
        foreign_assets=[
            ForeignAssetEntry(
                asset_type=ForeignAssetType.BANK_ACCOUNT,
                country_code="44",
                institution_or_entity_name="Barclays",
                address="1 Churchill Place, London",
                zip_code="E145HP",
                account_or_asset_identifier="12345678",
                ownership_status="OWNER",
                opening_or_acquisition_date=date(2020, 1, 1),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    payload = document["ITR"]["ITR2"]

    fsi_row = payload["ScheduleFSI"]["ScheduleFSIDtls"][0]
    assert fsi_row["CountryName"] == "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND"
    assert fsi_row["CountryCodeExcludingIndia"] == "44"

    tr_row = payload["ScheduleTR1"]["ScheduleTR"][0]
    assert tr_row["CountryName"] == "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND"
    assert payload["ScheduleTR1"]["TaxReliefOutsideIndiaDTAA"] == 8000

    fa_row = payload["ScheduleFA"]["DetailsForiegnBank"][0]
    assert fa_row["CountryName"] == "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND"


def test_schedule_fsi_income_fields_are_nested_tax_objects_not_plain_integers() -> None:
    """IncFromSal/IncFromHP/IncCapGain/IncOthSrc/TotalCountryWise are all
    nested objects in the official schema (ScheduleFSIIncType /
    TotalScheduleFSIIncType: IncFrmOutsideInd/TaxPaidOutsideInd/
    TaxPayableinInd/TaxReliefinInd each) -- the previous code emitted plain
    integers for all five, plus three fabricated top-level fields
    (TaxPaidOutsideIndia/TaxPayableInIndia/TaxReliefAvailable) that do not
    exist in the real schema at all. Every Schedule FSI disclosure this
    builder ever produced was schema-invalid on both counts, discovered
    only because a country-code test happened to call schema validation on
    Schedule FSI for the first time."""
    input_data = _input(
        fsi_entries=[
            FSICountryEntry(
                country_code="65", tax_identification_no="SG-TIN-1",
                salary_income=Decimal("500000"),
                tax_paid_outside_india=Decimal("50000"), tax_payable_in_india=Decimal("40000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleFSI"]["ScheduleFSIDtls"][0]

    # Sole nonzero head (salary) gets the jurisdiction's real tax figures.
    assert row["IncFromSal"] == {
        "IncFrmOutsideInd": 500000, "TaxPaidOutsideInd": 50000,
        "TaxPayableinInd": 40000, "TaxReliefinInd": 40000,
    }
    # Every other head is genuinely zero income here -- zero tax, not a guess.
    assert row["IncFromHP"] == {
        "IncFrmOutsideInd": 0, "TaxPaidOutsideInd": 0,
        "TaxPayableinInd": 0, "TaxReliefinInd": 0,
    }
    assert row["TotalCountryWise"] == {
        "IncFrmOutsideInd": 500000, "TaxPaidOutsideInd": 50000,
        "TaxPayableinInd": 40000, "TaxReliefinInd": 40000,
    }
    assert "TaxPaidOutsideIndia" not in row
    assert "TaxReliefAvailable" not in row


def test_schedule_fa_rejects_unrecognized_country_code() -> None:
    """country_code is a closed ~200-entry ITD enum, not free text -- an
    unrecognized value (e.g. a raw ISO alpha code from a plain text input,
    since the currently-shipped generic FSI/TR/FA workspace has no country
    dropdown, unlike the House Property and Personal Info tabs) must be
    rejected with a clear message, not silently accepted as if it were a
    real code."""
    input_data = _input(
        foreign_assets=[
            ForeignAssetEntry(
                asset_type=ForeignAssetType.BANK_ACCOUNT,
                country_code="US",
                institution_or_entity_name="Chase Bank",
                address="270 Park Avenue, New York",
                zip_code="10017",
                account_or_asset_identifier="123456789012",
                ownership_status="OWNER",
                opening_or_acquisition_date=date(2020, 1, 1),
            ),
        ],
    )
    with pytest.raises(ValueError, match="not a valid ITD"):
        build_itr2_json(compute(input_data), input_data)


def test_schedule_os_omits_optional_blocks_when_unset() -> None:
    """No optional Schedule OS data means no placeholder detail blocks --
    matches the project's no-fabricated-data convention."""
    input_data = _input(other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("1000")))
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]
    assert block["OthersInc"]["OthersIncDtls"] == []
    assert "NRIOsDTAA" not in block["IncChargblSplRateOS"]
    assert block["IncomeNotified89ATypeOS"] == []
