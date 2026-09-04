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
    OtherSourcesIncome,
    TaxPaymentDetail,
    TaxRegime,
    TCSEntry,
    TDS2Entry,
    TDS3Entry,
)
from app.schemas.itr2 import (
    CG112AScrip,
    CGAssetType,
    CGTransaction,
    ITR2FilingProfile,
    ITR2Input,
    OSGiftBreakdown,
    ScheduleSIEntry,
    TDS3FilingDetail,
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
    # Uses indexed cost (4500000), matching compute_ltcg()'s existing,
    # documented (not-yet-corrected) preference -- see its docstring note.
    assert ltcg_row["TotalDedn"] == 4550000
    assert ltcg_row["Balance"] == 3450000
    assert ltcg_row["LTCGonImmvblPrprty"] == 3450000
    assert cg["LongTermCapGain23"]["SaleofLandBuild"]["TotalLTCGImmblPrprty"] == 3450000


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
