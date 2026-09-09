"""Focused schema tests for the canonical ITR-2 ITD JSON builder."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft4Validator
from pydantic import ValidationError

from app.engine.calculators.itr2 import compute
from app.engine.itd.itr2 import build_itr2_json
from app.schemas.itr1 import (
    AgeBracket,
    BankAccount,
    Chapter6ADeductions,
    DependentRelationship,
    DisabilityCategory,
    DisabilitySeverity,
    Donation80G,
    Donation80GCategory,
    Donation80GGA,
    DonationAddress,
    FilingAddress,
    HousePropertyIncome,
    ITR1Schedule80EEALoanEntry,
    ITR1Schedule80EEBLoanEntry,
    ITR1Schedule80EELoanEntry,
    InsurancePolicy,
    OtherSourcesIncome,
    PoliticalContribution,
    PropertyType,
    Schedule80CEntry,
    Schedule80D,
    Schedule80DD,
    Schedule80EEntry,
    Schedule80GGA,
    Schedule80GGC,
    Schedule80U,
    Section80GGAClause,
    SalaryIncome,
    TaxPaymentDetail,
    TaxRegime,
    TCSEntry,
    TDS1Entry,
    TDS2Entry,
    TDS3Entry,
)
from app.schemas.itr2 import (
    AMTCreditItem,
    AMTInput,
    AgriculturalIncome,
    AssesseeStatus,
    BFLossItem,
    CG112AScrip,
    CGAssetType,
    CGTransaction,
    CapitalGainExemptionClaim,
    CoOwnerDetail,
    EmployerFilingDetail,
    ESOPDeferralInput,
    ExemptIncome,
    ForeignAssetEntry,
    ForeignAssetType,
    FSICountryEntry,
    HomeLoanDetail,
    ITR2FilingProfile,
    ITR2Input,
    LossHead,
    OS89ACountryEntry,
    OSAccumulatedPFEntry,
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


def _huf_profile(**overrides: Any) -> ITR2FilingProfile:
    """Return a complete HUF filing profile verified by its Karta."""
    values: dict[str, Any] = dict(
        pan="AAAHA1234A",  # HUF's own PAN -- 4th character "H"
        assessee_status=AssesseeStatus.HUF,
        first_name="",
        surname_or_org_name="Sharma HUF",
        date_of_birth_or_formation=date(2005, 4, 1),
        father_name="N/A",
        verification_place="Delhi",
        verification_capacity="K",
        karta_pan="AAAPK5678K",  # Karta's own individual PAN -- 4th character "P"
        primary_address=FilingAddress(
            residence_no="12", locality_or_area="Model Town", city_or_town_or_district="Delhi",
            state_code="07", pin_code="110009", mobile_no="9876543210", email="huf@example.com",
        ),
    )
    values.update(overrides)
    return ITR2FilingProfile(**values)


def test_itr2_filing_profile_requires_karta_pan_for_huf_assessee() -> None:
    """The official Verification.Declaration.AssesseeVerPAN pattern requires
    an individual's own PAN (4th character "P") -- an HUF's own PAN (4th
    character "H") cannot satisfy it, and there is no other field to
    supply a substitute. A bare HUF filing with no karta_pan is exactly the
    "flag with no detail" bug class already guarded against elsewhere in
    this schema (co_owned/co_owner_details, property_owner='OT'/
    property_owner_other) -- the schema itself now makes it impossible to
    construct."""
    with pytest.raises(ValueError, match="karta_pan"):
        _huf_profile(karta_pan=None)


def test_verification_uses_karta_pan_for_huf_assessee_not_the_hufs_own_pan() -> None:
    """Part B-71/Verification's AssesseeVerPAN previously always used
    profile.pan directly -- for an HUF return that is the HUF's own PAN
    (category "H"), which fails the schema's individual-only pattern.
    Every HUF ITR-2 return was therefore schema-invalid at the
    Verification block regardless of anything else being correct."""
    input_data = _input(filing_profile=_huf_profile())
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    declaration = document["ITR"]["ITR2"]["Verification"]["Declaration"]
    assert declaration["AssesseeVerPAN"] == "AAAPK5678K"
    assert declaration["AssesseeVerPAN"] != "AAAHA1234A"  # the HUF's own PAN must not appear here
    assert document["ITR"]["ITR2"]["Verification"]["Capacity"] == "K"
    # Part A-GEN's own PersonalInfo.PAN is unaffected -- it must still be
    # the HUF's own PAN, only the Verification declaration's PAN changes.
    assert document["ITR"]["ITR2"]["PartA_GEN1"]["PersonalInfo"]["PAN"] == "AAAHA1234A"


def test_verification_still_uses_the_assessees_own_pan_for_individual_filers() -> None:
    """Confirms the HUF-specific fix above does not change behavior for
    the ordinary (non-HUF) case -- Individual assessees continue to use
    their own profile.pan directly, exactly as before."""
    input_data = _input()  # default _profile() is an Individual assessee
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    declaration = document["ITR"]["ITR2"]["Verification"]["Declaration"]
    assert declaration["AssesseeVerPAN"] == "AAAPA1234A"


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


def test_equity_mf_on_stt_aggregates_transactions_instead_of_one_row_each() -> None:
    """``EquityMFonSTT`` (Schedule CG's 111A STCG detail) is a schema array
    capped at ``maxItems: 2``, one row per ``MFSectionCode``, and each row's
    own detail block (``EquityOrUnitSec94TypeMFonSTT``) is aggregate-only --
    no scrip identifier field exists at all. Previously appended one row PER
    TRANSACTION instead, so any taxpayer with 3+ STT-paid equity/MF STCG
    transactions in the year produced a schema-invalid array -- the common
    case for retail equity investors, not an edge case. Also confirms the
    incidental improvement_cost-omission bug is fixed: BalanceCG must
    reflect the full deduction (acquisition + improvement + transfer
    expenditure), matching DeductSec48.TotalDedn for the identical figure."""
    input_data = _input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 4, 1), date_of_transfer=date(2025, 1, 1),
                full_consideration=Decimal("100000"), cost_of_acquisition=Decimal("60000"),
                improvement_cost=Decimal("5000"),
            ),
            CGTransaction(
                asset_type=CGAssetType.EQUITY_ORIENTED_FUND_111A,
                date_of_acquisition=date(2024, 5, 1), date_of_transfer=date(2025, 2, 1),
                full_consideration=Decimal("200000"), cost_of_acquisition=Decimal("150000"),
                expenditure_on_transfer=Decimal("1000"),
            ),
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 3, 1),
                full_consideration=Decimal("50000"), cost_of_acquisition=Decimal("70000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    stcg = document["ITR"]["ITR2"]["ScheduleCGFor23"]["ShortTermCapGainFor23"]
    rows = stcg["EquityMFonSTT"]
    assert len(rows) == 1  # exactly one aggregate row, not one per transaction
    dtls = rows[0]["EquityMFonSTTDtls"]
    total_consideration = 100000 + 200000 + 50000
    total_acquisition = 60000 + 150000 + 70000
    total_improvement = 5000
    total_transfer_exp = 1000
    total_deduction = total_acquisition + total_improvement + total_transfer_exp
    assert dtls["FullConsideration"] == total_consideration
    assert dtls["DeductSec48"]["TotalDedn"] == total_deduction
    expected_balance = total_consideration - total_deduction
    assert dtls["BalanceCG"] == expected_balance
    assert dtls["CapgainonAssets"] == expected_balance


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


def test_schedule_112a_ltcg_before_lower_b1b2_sums_the_rows_not_the_bucket_totals() -> None:
    """``LTCGBeforelowerB1B2112A`` (Schedule 112A's own aggregate) was
    independently recomputed as ``max(0, total_sale - total_cost)`` from
    bucket-level totals, rather than summing the (already row-clamped)
    ``LTCGBeforelowerB1B2`` value each listed row discloses -- when scrips
    mix gains and losses these diverge: a +20,000 scrip and a -20,000 scrip
    each clamp to their own row minimum of 0/20,000, summing to 20,000, but
    the bucket formula gives max(0, 0) = 0. The aggregate must reconcile
    with its own listed rows."""
    input_data = _input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001", share_unit_name="GAIN SCRIP",
                date_of_acquisition=date(2023, 1, 1), date_of_transfer=date(2025, 5, 1),
                num_shares_units=Decimal("10"), sale_price_per_share=Decimal("52000"),
                total_sale_value=Decimal("520000"), cost_acq_without_index=Decimal("500000"),
            ),
            CG112AScrip(
                isin_code="INE000A00002", share_unit_name="LOSS SCRIP",
                date_of_acquisition=date(2023, 1, 1), date_of_transfer=date(2025, 5, 1),
                num_shares_units=Decimal("10"), sale_price_per_share=Decimal("48000"),
                total_sale_value=Decimal("480000"), cost_acq_without_index=Decimal("500000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    sch = document["ITR"]["ITR2"]["Schedule112A"]
    row_values = [r["LTCGBeforelowerB1B2"] for r in sch["Schedule112ADtls"]]
    assert row_values == [20000, 0]  # +20000 gain, -20000 loss clamped to 0
    assert sch["LTCGBeforelowerB1B2112A"] == sum(row_values) == 20000


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


def _stcg_111a_and_normal_rate_transactions() -> list[CGTransaction]:
    """One 111A-eligible STCG transaction (gain 200000) and one ordinary
    "other securities" STCG transaction (gain 50000, the SI engine's
    "normal_stcg"/30%-normal-rate basket) -- both genuinely short-term."""
    return [
        CGTransaction(
            asset_type=CGAssetType.LISTED_EQUITY_111A,
            date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 1, 1),
            full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
        ),
        CGTransaction(
            asset_type=CGAssetType.LISTED_SECURITY,
            date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 1, 1),
            full_consideration=Decimal("200000"), cost_of_acquisition=Decimal("150000"),
        ),
    ]


def test_partb_ti_short_term_buckets_are_not_swapped_for_ordinary_taxpayer() -> None:
    """Part B-TI's ``CapGain.ShortTerm`` previously swapped ``ShortTerm20Per``
    (should hold the true 111A/20%-flat bucket) with ``ShortTermAppRate``
    (should hold the ordinary slab-rate bucket) -- ``post_loss_cg_baskets()``'s
    own dict key "normal_stcg" is the 30%-normal-rate basket, not a 20%
    one, and was being read directly into ``ShortTerm20Per``. For a
    non-FII/FPI taxpayer this basket is taxed at slab/applicable rate, so
    it belongs in ``ShortTermAppRate``, and ``ShortTerm30Per`` (the FII-only
    115AD(1)(ii) flat-30% bucket) must stay zero."""
    input_data = _input(cg_transactions=_stcg_111a_and_normal_rate_transactions())
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    short_term = document["ITR"]["ITR2"]["PartB-TI"]["CapGain"]["ShortTerm"]
    assert short_term["ShortTerm20Per"] == 200000  # the real 111A bucket
    assert short_term["ShortTermAppRate"] == 50000  # the real slab-rate bucket
    assert short_term["ShortTerm30Per"] == 0  # FII-only bucket, no FII/FPI here
    assert short_term["TotalShortTerm"] == 250000


def test_partb_ti_short_term_30per_receives_fii_fpi_normal_rate_stcg() -> None:
    """For an FII/FPI assessee, the same "normal_stcg" basket is taxed at a
    flat 30% under section 115AD(1)(ii), not slab rate -- it must land in
    ``ShortTerm30Per``, not ``ShortTermAppRate``, which stays zero. The true
    111A bucket still belongs in ``ShortTerm20Per`` regardless of FII/FPI
    status (same 20% rate either way)."""
    profile = _profile().model_copy(update={
        "is_fii_fpi": True,
        "sebi_registration_number": "INABFP123456",
        "residential_status": ResidentialStatus.NON_RESIDENT,
    })
    input_data = _input(
        filing_profile=profile,
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_transactions=_stcg_111a_and_normal_rate_transactions(),
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    short_term = document["ITR"]["ITR2"]["PartB-TI"]["CapGain"]["ShortTerm"]
    assert short_term["ShortTerm20Per"] == 200000  # the real 111A bucket, unchanged
    assert short_term["ShortTerm30Per"] == 50000  # FII's flat-30% bucket
    assert short_term["ShortTermAppRate"] == 0  # not applicable-rate for an FII/FPI
    assert short_term["TotalShortTerm"] == 250000


def test_schedule_via_serializes_real_per_section_amounts_not_only_a_total() -> None:
    """Schedule VIA previously emitted only ``TotalChapVIADeductions`` on
    both ``UsrDeductUndChapVIA``/``DeductUndChapVIA`` (none of the ~20
    named per-section fields the schema actually requires -- three of them,
    Section80D/Section80G/Section80GGA, unconditionally required) plus a
    ``DeductUndChapVIAList`` key that does not exist anywhere in the
    official schema at all. Any return claiming a real Chapter VI-A
    deduction was schema-invalid on at least four independent grounds."""
    input_data = _input(
        other_sources_income=OtherSourcesIncome(income_56_2_x=Decimal("500000")),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80d_self_family=Decimal("25000"),
        ),
        # A claimed 80C deduction requires at least one backing detail row
        # with an identifier number (CBDT Category A validator) -- now that
        # Schedule80C is actually built (see §20.1's own fix), this must be
        # present for the return to stay schema-valid.
        schedule_80c_entries=[
            Schedule80CEntry(amount=Decimal("100000"), identifier_number="PPFXXXX1234"),
        ],
    )
    result = compute(input_data)
    assert result.deductions_total == Decimal("125000")
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    via = document["ITR"]["ITR2"]["ScheduleVIA"]

    for block_name in ("DeductUndChapVIA", "UsrDeductUndChapVIA"):
        block = via[block_name]
        assert block["Section80C"] == 100000
        assert block["Section80D"] == 25000
        # Required even when unclaimed.
        assert block["Section80G"] == 0
        assert block["Section80GGA"] == 0
        assert block["TotalChapVIADeductions"] == 125000
        # The old, non-existent key must not reappear.
        assert "DeductUndChapVIAList" not in via


def test_schedule_via_omits_unclaimed_sections_and_matches_zero_deduction() -> None:
    """No deduction claimed -- Schedule VIA is correctly omitted entirely
    (not emitted as an empty/zeroed placeholder)."""
    input_data = _input(other_sources_income=OtherSourcesIncome(income_56_2_x=Decimal("500000")))
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    assert "ScheduleVIA" not in document["ITR"]["ITR2"]


def test_chapter6a_detail_schedules_serialize_real_claimed_data_end_to_end() -> None:
    """None of the six dedicated Chapter VI-A detail schedules (80D, 80G,
    80GGA, 80GGC, 80DD, 80U) were ever built at all -- every one of them
    silently absent regardless of what the taxpayer claimed, even after
    Schedule VIA's own aggregate fix. A single return claiming all six
    sections must produce all six official detail schedules with real,
    schema-valid, cross-footing per-row/per-bucket data -- not just a
    correct aggregate total on Schedule VIA."""
    ded = Chapter6ADeductions(
        amount_80d_preventive_self=Decimal("3000"),
        amount_80d_preventive_parents=Decimal("2000"),
        amount_80gga=Decimal("10000"),
        amount_80ggc=Decimal("5000"),
        amount_80dd=Decimal("75000"),
        amount_80u=Decimal("125000"),
        amount_80g=Decimal("50000"),
        donations_80g=[
            Donation80G(
                cash_amount=Decimal("0"),
                non_cash_amount=Decimal("50000"),
                category=Donation80GCategory.HUNDRED_WITHOUT_LIMIT,
                donee_name="Charity Trust",
                donee_pan="AAAPD1234E",
                address=DonationAddress(
                    address_line="1 Charity Rd", city_or_district="Delhi",
                    state_code="07", pin_code=110001,
                ),
            ),
        ],
    )
    schedule_80d = Schedule80D(
        premium_1a_non_senior=Decimal("20000"),
        premium_2a_parents_non_senior=Decimal("15000"),
        policies=[
            InsurancePolicy(section="1a", premium_paid=Decimal("20000"), insurer_name="ABC Insurance", policy_number="POL123"),
            InsurancePolicy(section="2a", premium_paid=Decimal("15000"), insurer_name="XYZ Insurance", policy_number="POL456"),
        ],
    )
    schedule_80gga = Schedule80GGA(donations=[
        Donation80GGA(
            relevant_clause=Section80GGAClause.RURAL_DEVELOPMENT,
            donee_name="Rural Dev Trust",
            donee_pan="AAAPF1234G",
            address=DonationAddress(
                address_line="2 Village Rd", city_or_district="Pune",
                state_code="19", pin_code=411001,
            ),
            cash_amount=Decimal("0"),
            other_mode_amount=Decimal("10000"),
        ),
    ])
    schedule_80ggc = Schedule80GGC(contributions=[
        PoliticalContribution(
            cash_amount=Decimal("0"),
            other_mode_amount=Decimal("5000"),
            contribution_date=date(2025, 6, 1),
            transaction_ref="TXN123",
            ifsc_code="HDFC0001234",
            political_party_name="Party A",
            political_party_pan="AAAPZ9876Q",
        ),
    ])
    schedule_80dd = Schedule80DD(
        disability_type=DisabilitySeverity.NORMAL,
        disability_category=DisabilityCategory.OTHER,
        deduction_amount=Decimal("75000"),
        dependent_relationship=DependentRelationship.SON,
        dependent_pan="AAAPC1234D",
        form_10ia_ack_number="ACK123",
        udid_number="UDID123",
        form_10ia_filing_date=date(2025, 5, 1),
        form_ack_num_11a="11AACK1",
    )
    schedule_80u = Schedule80U(
        disability_type=DisabilitySeverity.SEVERE,
        disability_category=DisabilityCategory.AUTISM_CEREBRAL_PALSY_OR_MULTIPLE,
        deduction_amount=Decimal("125000"),
        form_10ia_ack_number="ACK456",
        udid_number="UDID456",
    )
    input_data = _input(
        other_sources_income=OtherSourcesIncome(income_56_2_x=Decimal("2000000")),
        deductions_chapter6a=ded,
        schedule_80d=schedule_80d,
        schedule_80gga=schedule_80gga,
        schedule_80ggc=schedule_80ggc,
        schedule_80dd=schedule_80dd,
        schedule_80u=schedule_80u,
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    payload = document["ITR"]["ITR2"]

    d80 = payload["Schedule80D"]["Sec80DSelfFamSrCtznHealth"]
    assert d80["SeniorCitizenFlag"] == "N"
    assert d80["SelfAndFamily"] == 23000  # 20000 premium + 3000 preventive
    assert d80["Sec80DSelfFamHIDtls"]["Sch80DInsDtls"][0]["InsurerName"] == "ABC Insurance"
    assert d80["ParentsSeniorCitizenFlag"] == "N"
    assert d80["Parents"] == 17000  # 15000 premium + 2000 preventive
    assert d80["EligibleAmountOfDedn"] == 40000

    g80 = payload["Schedule80G"]
    assert g80["Don100Percent"]["DoneeWithPan"][0]["DoneeWithPanName"] == "Charity Trust"
    assert g80["Don100Percent"]["TotEligibleDon100Percent"] == 50000
    assert g80["TotalEligibleDonationsUs80G"] == 50000

    gga = payload["Schedule80GGA"]
    assert gga["DonationDtlsSciRsrchRuralDev"][0]["RelevantClauseUndrDedClaimed"] == "80GGA2b"
    assert gga["DonationDtlsSciRsrchRuralDev"][0]["NameOfDonee"] == "Rural Dev Trust"
    assert gga["TotalEligibleDonationAmt80GGA"] == 10000

    ggc = payload["Schedule80GGC"]
    assert ggc["Schedule80GGCDetails"][0]["PoliticalPartyName"] == "Party A"
    assert ggc["Schedule80GGCDetails"][0]["DonationDate"] == "2025-06-01"
    assert ggc["TotalEligibleDonationAmt80GGC"] == 5000

    dd = payload["Schedule80DD"]
    assert dd["NatureOfDisability"] == "1"  # normal
    assert dd["TypeOfDisability"] == "2"  # other
    assert dd["DeductionAmount"] == 75000
    assert dd["DependentType"] == "2"  # son
    assert dd["DependentPan"] == "AAAPC1234D"
    assert dd["Form10IAFilingDate"] == "2025-05-01"
    assert dd["FormAckNum11A"] == "11AACK1"

    u80 = payload["Schedule80U"]
    assert u80["NatureOfDisability"] == "2"  # severe
    assert u80["TypeOfDisability"] == "1"  # autism/cerebral palsy/multiple
    assert u80["DeductionAmount"] == 125000
    assert "Form10IAFilingDate" not in u80  # not supplied for this schedule
    assert "DependentType" not in u80  # 80U has no dependent -- self only

    via = payload["ScheduleVIA"]["DeductUndChapVIA"]
    assert via["Section80D"] == 40000
    assert via["Section80G"] == 50000
    assert via["Section80GGA"] == 10000
    assert via["Section80GGC"] == 5000
    assert via["Section80DD"] == 75000
    assert via["Section80U"] == 125000


def test_chapter6a_detail_schedules_are_omitted_entirely_when_unclaimed() -> None:
    """No Chapter VI-A claim -- all eleven detail schedules are correctly
    omitted entirely (not emitted as empty/zeroed placeholders), matching
    Schedule VIA's own established omission behavior."""
    input_data = _input(other_sources_income=OtherSourcesIncome(income_56_2_x=Decimal("500000")))
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    payload = document["ITR"]["ITR2"]
    for name in (
        "Schedule80D", "Schedule80G", "Schedule80GGA", "Schedule80GGC", "Schedule80DD", "Schedule80U",
        "Schedule80C", "Schedule80E", "Schedule80EE", "Schedule80EEA", "Schedule80EEB",
    ):
        assert name not in payload


def test_five_more_chapter6a_detail_schedules_serialize_real_claimed_data() -> None:
    """`Schedule80C`, `Schedule80E`, `Schedule80EE`, `Schedule80EEA`, and
    `Schedule80EEB` were five more official Chapter VI-A detail schedules
    with zero implementation -- the exact same "aggregate right, detail
    schedule missing entirely" defect class §8.0a fixed six of, but never
    covered by that fix's own scope. A single return claiming all five
    must produce all five official detail schedules with real, schema-
    valid, cross-footing per-row data."""
    ded = Chapter6ADeductions(
        amount_80c=Decimal("100000"),
        amount_80e=Decimal("40000"),
        amount_80ee=Decimal("50000"),
        amount_80eea=Decimal("100000"),
        amount_80eeb=Decimal("100000"),
    )
    input_data = _input(
        other_sources_income=OtherSourcesIncome(income_56_2_x=Decimal("5000000")),
        deductions_chapter6a=ded,
        schedule_80c_entries=[
            Schedule80CEntry(amount=Decimal("100000"), identifier_number="PPFXXXX1234"),
        ],
        schedule_80e_entries=[
            Schedule80EEntry(
                loan_taken_from="B", lender_name="SBI", account_or_reference_number="EDULOAN123",
                loan_date=date(2020, 6, 1), total_loan_amount=Decimal("500000"),
                outstanding_loan_amount=Decimal("300000"), interest_paid=Decimal("40000"),
            ),
        ],
        loan_details_80ee_list=[
            ITR1Schedule80EELoanEntry(
                loan_taken_from="B", lender_name="HDFC Bank", account_or_reference_number="HOMELOAN80EE",
                loan_date=date(2016, 6, 1), total_loan_amount=Decimal("3000000"),
                outstanding_loan_amount=Decimal("2000000"), interest_paid=Decimal("50000"),
            ),
        ],
        loan_details_80eea_list=[
            ITR1Schedule80EEALoanEntry(
                loan_taken_from="B", lender_name="ICICI Bank", account_or_reference_number="HOMELOAN80EEA",
                loan_date=date(2020, 6, 1), total_loan_amount=Decimal("4000000"),
                outstanding_loan_amount=Decimal("3500000"), interest_paid=Decimal("100000"),
            ),
        ],
        loan_details_80eeb_list=[
            ITR1Schedule80EEBLoanEntry(
                loan_taken_from="B", lender_name="Axis Bank", account_or_reference_number="EVLOAN80EEB",
                loan_date=date(2021, 6, 1), total_loan_amount=Decimal("1000000"),
                outstanding_loan_amount=Decimal("800000"), interest_paid=Decimal("100000"),
                vehicle_registration_number="MH12AB1234",
            ),
        ],
        property_stamp_duty_value_80eea=Decimal("4000000"),
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    payload = document["ITR"]["ITR2"]

    c80 = payload["Schedule80C"]
    assert c80["Schedule80CDtls"][0]["IdentificationNo"] == "PPFXXXX1234"
    assert c80["TotalAmt"] == 100000

    e80 = payload["Schedule80E"]
    assert e80["Schedule80EDtls"][0]["BankOrInstnName"] == "SBI"
    assert e80["TotalInterest80E"] == 40000

    ee80 = payload["Schedule80EE"]
    assert ee80["Schedule80EEDtls"][0]["BankOrInstnName"] == "HDFC Bank"
    assert ee80["TotalInterest80EE"] == 50000

    eea80 = payload["Schedule80EEA"]
    assert eea80["Schedule80EEADtls"][0]["BankOrInstnName"] == "ICICI Bank"
    assert eea80["TotalInterest80EEA"] == 100000
    assert eea80["PropStmpDtyVal"] == 4000000

    eeb80 = payload["Schedule80EEB"]
    assert eeb80["Schedule80EEBDtls"][0]["VehicleRegNo"] == "MH12AB1234"
    assert eeb80["TotalInterest80EEB"] == 100000

    via = payload["ScheduleVIA"]["DeductUndChapVIA"]
    assert via["Section80C"] == 100000
    assert via["Section80E"] == 40000
    assert via["Section80EE"] == 50000
    assert via["Section80EEA"] == 100000
    assert via["Section80EEB"] == 100000


def test_schedule_115ad_receives_fii_fpi_scrips_instead_of_schedule_112a() -> None:
    """An FII/FPI assessee's 112A-eligible scrips must land in the
    official Schedule115AD table (the form's "115AD(1)(b)(iii) proviso"
    table), not Schedule112A (the resident taxpayer's table) -- previously
    Schedule115AD was never built at all, and every FII/FPI scrip was
    placed in Schedule112A regardless of status."""
    scrip_kwargs = dict(
        isin_code="INE000A00003", share_unit_name="FII SCRIP",
        date_of_acquisition=date(2023, 1, 1), date_of_transfer=date(2025, 5, 1),
        num_shares_units=Decimal("10"), sale_price_per_share=Decimal("500"),
        total_sale_value=Decimal("5000"), cost_acq_without_index=Decimal("2000"),
    )

    # Resident taxpayer: goes to Schedule112A, Schedule115AD absent.
    resident_input = _input(cg_112a_scrips=[CG112AScrip(**scrip_kwargs)])
    resident_doc = build_itr2_json(compute(resident_input), resident_input)
    _assert_schema_valid(resident_doc)
    resident_payload = resident_doc["ITR"]["ITR2"]
    assert resident_payload["Schedule112A"]["TotalBalance112A"] == 3000
    assert "Schedule115AD" not in resident_payload

    # FII/FPI taxpayer, same scrip data via the dedicated cg_115ad_scrips
    # field (the real v2-pipeline path once the draft mapper splits
    # schedule112A/schedule115AD rows): goes to Schedule115AD, Schedule112A
    # absent.
    fii_profile = _profile().model_copy(update={
        "is_fii_fpi": True,
        "sebi_registration_number": "INABFP123456",
        "residential_status": ResidentialStatus.NON_RESIDENT,
    })
    fii_input = _input(
        filing_profile=fii_profile,
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_115ad_scrips=[CG112AScrip(**scrip_kwargs)],
    )
    fii_doc = build_itr2_json(compute(fii_input), fii_input)
    _assert_schema_valid(fii_doc)
    fii_payload = fii_doc["ITR"]["ITR2"]
    assert fii_payload["Schedule115AD"]["TotalBalance115AD"] == 3000
    assert fii_payload["Schedule115AD"]["Schedule115ADDtls"][0]["ISINCode"] == "INE000A00003"
    assert "Schedule112A" not in fii_payload

    # Same tax amount either way -- only the disclosure schedule differs.
    assert compute(resident_input).capital_gains_income == compute(fii_input).capital_gains_income


def test_schedule_115ad_still_receives_scrips_supplied_via_cg_112a_scrips() -> None:
    """A caller that (like the pre-existing FII/FPI SI-rate test) supplies
    an FII/FPI assessee's scrips through ``cg_112a_scrips`` rather than the
    newer ``cg_115ad_scrips`` field must not have that data silently
    dropped from disclosure -- routing is determined by the assessee's
    FII/FPI status alone, not by which of the two explicit-scrip lists a
    row happens to sit in (the calculator already unions both for tax
    computation for the same reason)."""
    fii_profile = _profile().model_copy(update={
        "is_fii_fpi": True,
        "sebi_registration_number": "INABFP123456",
        "residential_status": ResidentialStatus.NON_RESIDENT,
    })
    fii_input = _input(
        filing_profile=fii_profile,
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_112a_scrips=[CG112AScrip(
            isin_code="INE000A00004", share_unit_name="FII SCRIP VIA OLD FIELD",
            date_of_acquisition=date(2023, 1, 1), date_of_transfer=date(2025, 5, 1),
            num_shares_units=Decimal("10"), sale_price_per_share=Decimal("500"),
            total_sale_value=Decimal("5000"), cost_acq_without_index=Decimal("2000"),
        )],
    )
    document = build_itr2_json(compute(fii_input), fii_input)
    _assert_schema_valid(document)
    payload = document["ITR"]["ITR2"]
    assert payload["Schedule115AD"]["TotalBalance115AD"] == 3000
    assert "Schedule112A" not in payload


def test_112a_scrip_total_deductions_is_not_double_counted() -> None:
    """`compute_112a()` previously subtracted `asset.total_deductions` (a
    redundant disclosure-only summary field, validated elsewhere to equal
    cost_acq_without_index + expenditure_on_transfer whenever a caller
    supplies it) ON TOP OF the cost and expenditure it already subtracts
    separately -- double-counting the same deduction and, for a real gain
    of this size, fabricating a loss instead. Schedule 112A's own
    `TotalDeductions`/`Balance` JSON fields are independently and correctly
    recomputed from cost+expense elsewhere in the builder and were never
    affected -- this bug was specifically in the taxed AMOUNT, not the
    disclosed one, making it invisible without checking the actual tax
    figures."""
    scrip = CG112AScrip(
        isin_code="INE000A00005", share_unit_name="REAL GAIN SCRIP",
        date_of_acquisition=date(2020, 1, 1), date_of_transfer=date(2025, 6, 1),
        num_shares_units=Decimal("100"), sale_price_per_share=Decimal("10000"),
        total_sale_value=Decimal("1000000"), cost_acq_without_index=Decimal("500000"),
        expenditure_on_transfer=Decimal("5000"),
        # Matches cost + expenditure -- exactly what the frontend's own
        # readout computes and app/engine/validators/itr2/input_rules.py's
        # ITR2-IN-112A-006 requires whenever this field is supplied.
        total_deductions=Decimal("505000"),
    )
    input_data = _input(cg_112a_scrips=[scrip])
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)

    # The real gain is 1,000,000 - 500,000 - 5,000 = 495,000 -- not the
    # fabricated -10,000 loss the double-counted formula produced
    # (1,000,000 - 500,000 - 505,000 - 5,000).
    assert result.capital_gains_income == Decimal("495000")

    row = document["ITR"]["ITR2"]["Schedule112A"]["Schedule112ADtls"][0]
    assert row["Balance"] == 495000
    assert row["TotalDeductions"] == 505000  # cost + expense, disclosure-only
    assert document["ITR"]["ITR2"]["Schedule112A"]["TotalBalance112A"] == 495000


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


def test_schedule_cyla_reports_real_capital_gains_income_not_zero() -> None:
    """Schedule CYLA's own six capital-gains sub-baskets (STCG20Per,
    STCG30Per, STCGAppRate, STCGDTAARate, LTCG12_5Per, LTCGDTAARate) were
    always hardcoded to zero regardless of real capital-gains income --
    `_schedule_cyla()` read `stcg20_income`/etc attributes that exist only
    on `CYLAInput` (what's passed INTO the CYLA engine), not on
    `CYLAResult` (what it returns), so the `getattr(..., default=0)` silently
    fell through to zero every time. This directly contradicted Schedule
    BFLA in the very same filed JSON, which correctly read the equivalent
    `stcg20_remaining`/etc attributes that do exist on `CYLAResult`."""
    input_data = _input(
        cg_transactions=[
            # 111A STCG gain -> the "stcg20" bucket.
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 1, 1),
                full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
            ),
            # Long-held "other securities" LTCG gain -> the "ltcg125" bucket.
            CGTransaction(
                asset_type=CGAssetType.LISTED_SECURITY,
                date_of_acquisition=date(2020, 1, 1), date_of_transfer=date(2025, 6, 1),
                full_consideration=Decimal("900000"), cost_of_acquisition=Decimal("500000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    payload = document["ITR"]["ITR2"]
    cyla = payload["ScheduleCYLA"]
    bfla = payload["ScheduleBFLA"]

    stcg20 = cyla["STCG20Per"]["IncCYLA"]
    assert stcg20["IncOfCurYrUnderThatHead"] == 200000  # 500000 - 300000
    assert stcg20["IncOfCurYrAfterSetOff"] == 200000  # no cross-head losses here

    ltcg125 = cyla["LTCG12_5Per"]["IncCYLA"]
    assert ltcg125["IncOfCurYrUnderThatHead"] == 400000  # 900000 - 500000
    assert ltcg125["IncOfCurYrAfterSetOff"] == 400000

    # No income in the untouched buckets, matching the "no fabricated data"
    # discipline used throughout this schedule.
    assert cyla["STCG30Per"]["IncCYLA"]["IncOfCurYrUnderThatHead"] == 0

    # Schedule CYLA and Schedule BFLA must agree with each other for the
    # identical basket in the identical return -- previously they always
    # disagreed (CYLA showed 0, BFLA showed the real figure) whenever any
    # capital-gains income existed.
    assert stcg20["IncOfCurYrAfterSetOff"] == bfla["STCG20Per"]["IncBFLA"]["IncOfCurYrUndHeadFromCYLA"]
    assert ltcg125["IncOfCurYrAfterSetOff"] == bfla["LTCG12_5Per"]["IncBFLA"]["IncOfCurYrUndHeadFromCYLA"]


def test_schedule_cg_table_e_reflects_real_intra_head_loss_setoff() -> None:
    """Schedule CG's own Table E (`CurrYrLosses`) was previously hardcoded
    to all-zero regardless of real current-year capital losses. A 111A
    STCG loss (50000) must set off against a same-year "other" STCG gain
    (80000, taxed at slab/applicable rate for this non-FII/FPI taxpayer),
    leaving a real remaining gain of 30000 -- and this must be visible in
    `InStcg30Per`'s own `StclSetoff20Per`/`CurrYrCapGain` fields, not just
    baked silently into Part B-TI's independently-sourced total."""
    input_data = _input(
        cg_transactions=[
            # 111A STCG LOSS: consideration 200000, cost 250000 -> -50000.
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 1, 1),
                full_consideration=Decimal("200000"), cost_of_acquisition=Decimal("250000"),
            ),
            # Ordinary "other securities" STCG GAIN: 280000 - 200000 = 80000.
            CGTransaction(
                asset_type=CGAssetType.LISTED_SECURITY,
                date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 1, 1),
                full_consideration=Decimal("280000"), cost_of_acquisition=Decimal("200000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    table_e = document["ITR"]["ITR2"]["ScheduleCGFor23"]["CurrYrLosses"]

    assert table_e["InLossSetOff"]["StclSetoff20Per"] == 50000
    assert table_e["InLossSetOff"]["StclSetoff30Per"] == 0

    stcg30_row = table_e["InStcg30Per"]
    assert stcg30_row["CurrYearIncome"] == 80000
    assert stcg30_row["StclSetoff20Per"] == 50000  # absorbed from the 111A loss
    assert stcg30_row["CurrYrCapGain"] == 30000

    stcg20_row = table_e["InStcg20Per"]
    assert stcg20_row["CurrYearIncome"] == 0  # this bucket has a loss, not a gain
    assert stcg20_row["CurrYrCapGain"] == 0

    assert table_e["TotLossSetOff"]["StclSetoff20Per"] == 50000
    assert table_e["LossRemainSetOff"]["StclSetoff20Per"] == 0  # fully absorbed

    # Part B-TI's own capital-gains figures are independently sourced from
    # post_loss_cg and correctly reflect the same net position either way.
    short_term = document["ITR"]["ITR2"]["PartB-TI"]["CapGain"]["ShortTerm"]
    assert short_term["TotalShortTerm"] == 30000


def test_schedule_cg_table_f_buckets_gains_by_real_transfer_date_quarter() -> None:
    """Schedule CG's own Table F (`AccruOrRecOfCG`) was previously always
    the zero default -- every quarterly bucket empty regardless of real
    transaction dates. Gains from a 111A transaction, a generic-other STCG
    transaction, a generic-other LTCG transaction, and a land/building LTCG
    transaction must each land in the correct rate-bucket AND quarter based
    on their own real transfer dates; a loss-making transaction in the same
    quarter as a real gain must not reduce that quarter's disclosed figure
    (Table F discloses accrual of GAIN, and its own schema fields reject
    negative values)."""
    input_data = _input(
        cg_transactions=[
            # 111A STCG gain, transferred 15-May-2025 -> Q1 (upto 15/6).
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 5, 15),
                full_consideration=Decimal("240000"), cost_of_acquisition=Decimal("200000"),
            ),
            # 111A STCG LOSS, also transferred in Q1 -- must not reduce Q1's
            # own disclosed 111A gain figure below.
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 6, 1),
                full_consideration=Decimal("100000"), cost_of_acquisition=Decimal("120000"),
            ),
            # Ordinary "other securities" STCG gain (held under the 12-month
            # threshold), transferred 10-Jul-2025 -> Q2.
            CGTransaction(
                asset_type=CGAssetType.LISTED_SECURITY,
                date_of_acquisition=date(2024, 8, 1), date_of_transfer=date(2025, 7, 10),
                full_consideration=Decimal("280000"), cost_of_acquisition=Decimal("200000"),
            ),
            # Ordinary "other securities" LTCG gain, transferred 20-Dec-2025 -> Q4.
            CGTransaction(
                asset_type=CGAssetType.LISTED_SECURITY,
                date_of_acquisition=date(2020, 1, 1), date_of_transfer=date(2025, 12, 20),
                full_consideration=Decimal("900000"), cost_of_acquisition=Decimal("500000"),
            ),
            # Land/building LTCG gain, transferred 15-Jan-2026 -> also Q4.
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                date_of_acquisition=date(2015, 4, 1), date_of_transfer=date(2026, 1, 15),
                full_consideration=Decimal("1000000"), cost_of_acquisition=Decimal("400000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    table_f = document["ITR"]["ITR2"]["ScheduleCGFor23"]["AccruOrRecOfCG"]

    stcg20 = table_f["ShortTermUnder20Per"]["DateRange"]
    assert stcg20["Upto15Of6"] == 40000  # only the gain; the loss contributes 0
    assert stcg20["Upto15Of9"] == 0

    stcg30 = table_f["ShortTermUnder30Per"]["DateRange"]
    assert stcg30["Upto15Of9"] == 80000
    assert stcg30["Upto15Of6"] == 0

    ltcg125 = table_f["LongTermUnder12_5Per"]["DateRange"]
    # Dec-2025 other-securities LTCG (400000) + Jan-2026 land/building LTCG
    # (1000000 - 400000 = 600000), both in the same Up16Of12To15Of3 period.
    assert ltcg125["Up16Of12To15Of3"] == 1000000
    assert ltcg125["Upto15Of6"] == 0

    # Buckets with no data source anywhere in this builder stay honestly zero.
    assert table_f["ShortTermUnderAppRate"]["DateRange"]["Upto15Of6"] == 0
    assert table_f["ShortTermUnderDTAARate"]["DateRange"]["Upto15Of6"] == 0
    assert table_f["LongTermUnderDTAARate"]["DateRange"]["Upto15Of6"] == 0


def test_schedule_cg_table_f_discloses_vda_accrual_timing() -> None:
    """Table F's own ``VDATrnsfGainsUnder30Per`` field (section 115BBH, 30%
    flat) was previously omitted entirely -- ``_accrued_cg()`` never read
    ``input_data.vda_transactions`` at all, despite each VDA transaction
    already carrying its own ``date_of_transfer`` and directly computable
    income, unlike the genuinely-data-source-less applicable-rate/DTAA
    buckets. A taxpayer with real VDA income previously got nothing
    disclosed in this table's own 234C-support breakdown for it."""
    input_data = _input(
        vda_transactions=[
            # Transferred 15-Jan-2026 -> Up16Of12To15Of3 (Q4).
            VDATransaction(
                date_of_acquisition=date(2024, 1, 1), date_of_transfer=date(2026, 1, 15),
                acquisition_cost=Decimal("50000"), consideration_received=Decimal("90000"),
            ),
            # Transferred 10-Jul-2025 -> Upto15Of9 (Q2).
            VDATransaction(
                date_of_acquisition=date(2024, 6, 1), date_of_transfer=date(2025, 7, 10),
                acquisition_cost=Decimal("20000"), consideration_received=Decimal("35000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    vda_accrual = document["ITR"]["ITR2"]["ScheduleCGFor23"]["AccruOrRecOfCG"]["VDATrnsfGainsUnder30Per"]["DateRange"]
    assert vda_accrual["Up16Of12To15Of3"] == 40000  # 90000 - 50000
    assert vda_accrual["Upto15Of9"] == 15000  # 35000 - 20000
    assert vda_accrual["Upto15Of6"] == 0


def test_schedule_cg_table_f_112a_scrip_gain_is_not_double_counted() -> None:
    """Table F's own per-scrip 112A/115AD gain approximation (`_accrued_cg()`)
    had the identical double-counted-deductions bug as `compute_112a()`
    itself -- subtracting `scrip.total_deductions` on top of
    `cost_acq_without_index`/`expenditure_on_transfer`, which already fully
    account for the same deduction."""
    scrip = CG112AScrip(
        isin_code="INE000A00006", share_unit_name="TABLE F GAIN SCRIP",
        date_of_acquisition=date(2020, 1, 1), date_of_transfer=date(2025, 6, 1),
        num_shares_units=Decimal("100"), sale_price_per_share=Decimal("10000"),
        total_sale_value=Decimal("1000000"), cost_acq_without_index=Decimal("500000"),
        expenditure_on_transfer=Decimal("5000"),
        total_deductions=Decimal("505000"),
    )
    input_data = _input(cg_112a_scrips=[scrip])
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    ltcg125 = document["ITR"]["ITR2"]["ScheduleCGFor23"]["AccruOrRecOfCG"]["LongTermUnder12_5Per"]["DateRange"]
    # 1,000,000 - 500,000 - 5,000 = 495,000 (2025-06-01 falls in Q1, upto 15/6).
    assert ltcg125["Upto15Of6"] == 495000


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


def test_schedule_tds3_serializes_the_buyer_tenants_aadhaar() -> None:
    """``TDS3Entry.tenant_aadhaar`` was correctly mapped from the draft but
    had no path to the JSON at all -- ``_schedule_tds3()`` built
    ``PANOfBuyerTenant`` from a *different* object (``TDS3FilingDetail``)
    that has no Aadhaar field, and never read ``entry.tenant_aadhaar`` from
    the paired ``TDS3Entry`` either. A taxpayer who supplied the buyer/
    tenant's Aadhaar never had it appear in the filed return."""
    input_data = _input(
        tds3_entries=[
            TDS3Entry(
                tenant_pan="CCCPC9012D",
                tenant_name="Tenant Pvt Ltd",
                tenant_aadhaar="987654321098",
                gross_receipt=Decimal("500000"),
                tds_deducted=Decimal("50000"),
                tds_claimed=Decimal("50000"),
                tds_section="195",
                deducted_yr="2024",
            )
        ],
        tds3_filing_details=[
            TDS3FilingDetail(buyer_tenant_pan="CCCPC9012D", head_of_income="OS"),
        ],
        bank_accounts=[
            BankAccount(
                account_number="1234567890", ifsc_code="SBIN0000001",
                bank_name="State Bank of India", account_type="savings", is_primary=True,
            )
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleTDS3"]["TDS3onOthThanSalDtls"][0]
    assert row["AadhaarOfBuyerTenant"] == "987654321098"


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
    assert os_block["TaxAccumulatedBalRecPF"] == {
        "TaxAccmltdBalRecPFDtls": [], "TotalIncomeBenefit": 30000, "TotalTaxBenefit": 3000,
    }


def test_inc_chargeable_special_rates_includes_accumulated_pf_income() -> None:
    """Schedule OS item "2" (``IncChargeableSpecialRates``, "Income
    chargeable at special rates (2ai+2aii+2b+2c+2d+2e...)") previously
    summed only 2ai/2aii/2b/2d (lottery/115BBJ/115BBE/OthersGross), omitting
    2c (``TaxAccumulatedBalRecPF.TotalIncomeBenefit``, accumulated PF income
    u/s 111) even though it is real, disclosed, and already correctly taxed
    via the calculator's own ``_OS_HEAD_SI_SECTIONS`` dispatch -- an
    under-reported item-2 total whenever a taxpayer has accumulated-PF
    income, with no tax effect (the tax itself was already correct)."""
    input_data = _input(
        si_entries=[
            ScheduleSIEntry(section="115BB", gross_income=Decimal("50000")),
            ScheduleSIEntry(section="111", gross_income=Decimal("30000")),
        ],
        os_pf_income_benefit=Decimal("30000"),
        os_pf_tax_benefit=Decimal("3000"),
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    os_block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]
    assert os_block["IncChargeableSpecialRates"] == 80000  # 50000 lottery + 30000 accumulated PF


def test_schedule_os_gross_inc_chrgbl_tax_at_app_rate_sums_its_own_components() -> None:
    """Schedule OS item "1" (``GrossIncChrgblTaxAtAppRate``, "Gross income
    chargeable to tax at normal applicable rates (1a+1b+1c+1d+1e)") was
    hardcoded to 0 regardless of its real components -- a visible
    self-contradiction against item "6" (``BalanceNoRaceHorse``), which
    already correctly derives from the real calculator total those same
    components are supposed to feed into.

    Uses only dividend/interest/rent/56(2)(x) (1a/1b/1c/1d) -- "any other
    income" (1e, ``os_other_income_entries``) is exercised separately by
    ``test_os_other_income_entries_are_taxed_not_just_disclosed()`` below,
    which covers the item-1e/undertaxation-gap fix specifically.
    """
    input_data = _input(
        other_sources_income=OtherSourcesIncome(
            dividend_income=Decimal("20000"),
            savings_bank_interest=Decimal("5000"),
            fixed_deposit_interest=Decimal("15000"),
            income_56_2_x=Decimal("30000"),
        ),
        os_machinery_plant_rent=Decimal("10000"),
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]
    assert block["DividendGross"] == 20000
    assert block["InterestGross"] == 20000
    assert block["RentFromMachPlantBldgs"] == 10000
    assert block["Tot562x"] == 30000
    assert block["AnyOtherIncome"] == 0
    assert block["GrossIncChrgblTaxAtAppRate"] == 20000 + 20000 + 10000 + 30000
    # No special-rate income and no "any other income" here, so item "1"
    # must equal item "6" (BalanceNoRaceHorse) -- the two figures this bug
    # made contradict each other whenever any of the four components was
    # non-zero.
    assert block["GrossIncChrgblTaxAtAppRate"] == block["BalanceNoRaceHorse"]


def test_os_other_income_entries_are_taxed_not_just_disclosed() -> None:
    """``os_other_income_entries`` ("any other income," Schedule OS item
    1e) was correctly disclosed in ``AnyOtherIncome``/``OthersIncDtls`` but
    was never summed into ``result.other_sources_income`` by the
    calculator at all -- a real undertaxation gap: the taxpayer's own
    disclosed "any other income" was shown on the filed return but not
    actually taxed. Proven here at the strongest level: taxable income
    itself must differ by exactly the disclosed amount between two
    otherwise-identical returns, not just a JSON disclosure field."""
    without_entry = _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("100000")),
    )
    with_entry = _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("100000")),
        os_other_income_entries=[
            OSOtherIncomeEntry(nature="Freelance consulting", amount=Decimal("30000")),
        ],
    )
    result_without = compute(without_entry)
    result_with = compute(with_entry)
    assert result_with.other_sources_income - result_without.other_sources_income == Decimal("30000")
    assert result_with.taxable_income - result_without.taxable_income == Decimal("30000")

    document = build_itr2_json(result_with, with_entry)
    _assert_schema_valid(document)
    block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]
    assert block["AnyOtherIncome"] == 30000
    assert block["OthersInc"]["OthersIncDtls"][0]["OthNatOfInc"] == "Freelance consulting"
    # Item 1e is now genuinely included in both item "1" (GrossIncChrgblTaxAtAppRate)
    # and item "6" (BalanceNoRaceHorse), so the two stay equal to each other
    # even with "any other income" present -- both now derive from the same
    # corrected result.other_sources_income.
    assert block["GrossIncChrgblTaxAtAppRate"] == 100000 + 30000
    assert block["GrossIncChrgblTaxAtAppRate"] == block["BalanceNoRaceHorse"]


def test_os_other_income_entries_are_not_double_counted_via_the_draft_pipeline() -> None:
    """The real v2 draft pipeline maps every ``otherIncome`` row into BOTH
    the generic ``other_income`` aggregate (via the shared
    ``_map_other_sources()``) and, for ITR-2, the structured
    ``os_other_income_entries`` list -- so once the calculator started
    taxing ``os_other_income_entries`` directly (this fix), the generic
    aggregate must have the same rows backed out of it, exactly like
    MACHINERY_RENT/PASS_THROUGH-natured rows already are, or a real
    taxpayer's "any other income" would be taxed twice."""
    from app.engine.draft_to_itr2_input import draft_to_itr2_input
    from tests.test_draft_to_itr2_input import OtherIncomeEntry, _filing_ready_itr2_draft

    baseline_draft = _filing_ready_itr2_draft()
    baseline_input, _ = draft_to_itr2_input(baseline_draft)
    baseline_result = compute(baseline_input)

    draft = _filing_ready_itr2_draft()
    draft.otherSources.otherIncome = [
        OtherIncomeEntry(id="o1", nature="OTHER", description="Freelance", amount=Decimal("5000")),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.other_sources_income.other_income == Decimal("0")
    assert len(itr2_input.os_other_income_entries) == 1
    assert itr2_input.os_other_income_entries[0].amount == Decimal("5000")
    result = compute(itr2_input)
    # The 5000 must appear in taxable other-sources income exactly once --
    # not zero (undertaxed) and not 10000 (double-counted via both the
    # generic aggregate and os_other_income_entries).
    assert result.other_sources_income - baseline_result.other_sources_income == Decimal("5000")


def test_os_pass_through_income_is_taxed_not_just_disclosed() -> None:
    """``os_pass_through_income`` (Schedule OS item 1b(iv), official
    ``NatofPassThrghIncome``) is a sibling of the ``os_other_income_entries``
    undertaxation gap and shares its root cause: ``draft_to_itr2_input.py``
    correctly backs this amount out of the generic ``other_income``
    aggregate (to avoid double-counting it there, alongside
    ``os_machinery_plant_rent``), but unlike that field it was never added
    back into taxable income anywhere -- disclosed in the filed JSON but
    never actually taxed. Proven at the strongest level: taxable income
    itself must differ by exactly the disclosed amount between two
    otherwise-identical returns."""
    without_pass_through = _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("100000")),
    )
    with_pass_through = _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("100000")),
        os_pass_through_income=Decimal("20000"),
    )
    result_without = compute(without_pass_through)
    result_with = compute(with_pass_through)
    assert result_with.other_sources_income - result_without.other_sources_income == Decimal("20000")
    assert result_with.taxable_income - result_without.taxable_income == Decimal("20000")

    document = build_itr2_json(result_with, with_pass_through)
    _assert_schema_valid(document)
    block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]
    assert block["NatofPassThrghIncome"] == 20000


def test_os_pass_through_income_is_not_double_counted_via_the_draft_pipeline() -> None:
    """The real v2 draft pipeline maps a PASS_THROUGH-natured ``otherIncome``
    row into BOTH the generic ``other_income`` aggregate (via the shared
    ``_map_other_sources()``) and, for ITR-2, ``os_pass_through_income`` --
    so now that the calculator taxes ``os_pass_through_income`` directly
    (this fix), the generic aggregate's own existing back-out of this same
    amount (already present, unlike ``os_other_income_entries``'s own
    back-out which needed adding) must still leave it taxed exactly once."""
    from app.engine.draft_to_itr2_input import draft_to_itr2_input
    from tests.test_draft_to_itr2_input import OtherIncomeEntry, _filing_ready_itr2_draft

    baseline_draft = _filing_ready_itr2_draft()
    baseline_input, _ = draft_to_itr2_input(baseline_draft)
    baseline_result = compute(baseline_input)

    draft = _filing_ready_itr2_draft()
    draft.otherSources.otherIncome = [
        OtherIncomeEntry(id="o1", nature="PASS_THROUGH", amount=Decimal("15000")),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.other_sources_income.other_income == Decimal("0")
    assert itr2_input.os_pass_through_income == Decimal("15000")
    result = compute(itr2_input)
    # The 15000 must appear in taxable other-sources income exactly once --
    # not zero (undertaxed) and not 30000 (double-counted).
    assert result.other_sources_income - baseline_result.other_sources_income == Decimal("15000")


def test_os_pf_proviso_and_other_interest_are_taxed_not_just_disclosed() -> None:
    """The four Section 10(11)/10(12) proviso PF-interest fields and
    ``os_interest_from_others`` (NSC/bonds/securities interest) were
    disclosed correctly in Schedule OS (``IntrstSec10XI*Proviso``/
    ``IntrstFrmOthers``) but previously reached GTI only through the
    generic, untraceable ``other_income`` aggregate the draft mapper backs
    them out of for exactly this reason -- there was no dedicated,
    verifiable GTI-inclusion path independent of that aggregate's own
    correctness. Proven the same way ``os_pass_through_income`` was: taxable
    income must differ by exactly the disclosed amount between two
    otherwise-identical returns."""
    without_pf_interest = _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("100000")),
    )
    with_pf_interest = _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("100000")),
        os_pf_interest_10_11_first_proviso=Decimal("5000"),
        os_pf_interest_10_11_second_proviso=Decimal("6000"),
        os_pf_interest_10_12_first_proviso=Decimal("7000"),
        os_pf_interest_10_12_second_proviso=Decimal("8000"),
        os_interest_from_others=Decimal("9000"),
    )
    result_without = compute(without_pf_interest)
    result_with = compute(with_pf_interest)
    assert result_with.other_sources_income - result_without.other_sources_income == Decimal("35000")
    assert result_with.taxable_income - result_without.taxable_income == Decimal("35000")


def test_os_pf_proviso_interest_is_not_double_counted_via_the_draft_pipeline() -> None:
    """The real v2 draft pipeline maps PF-proviso/NSC/bonds/securities
    interest rows (``draft.otherSources.interest``, kinds PF_10_11_FIRST/
    etc and NSC/BONDS/SECURITIES/OTHER) into BOTH the generic
    ``other_income`` aggregate (via the shared ``_map_other_sources()``) and
    the five dedicated ITR2Input fields -- so now that the calculator taxes
    those five fields directly (this fix), draft_to_itr2_input.py's own
    back-out of the identical amount from the generic aggregate must leave
    it taxed exactly once, matching the ``os_pass_through_income`` fix's own
    verification pattern."""
    from app.engine.draft_to_itr2_input import draft_to_itr2_input
    from tests.test_draft_to_itr2_input import _filing_ready_itr2_draft
    from app.schemas.return_draft import InterestIncome

    baseline_draft = _filing_ready_itr2_draft()
    baseline_input, _ = draft_to_itr2_input(baseline_draft)
    baseline_result = compute(baseline_input)

    draft = _filing_ready_itr2_draft()
    draft.otherSources.interest = list(draft.otherSources.interest) + [
        InterestIncome(id="pf1", kind="PF_10_11_FIRST", grossAmount=Decimal("12000")),
        InterestIncome(id="nsc1", kind="NSC", grossAmount=Decimal("8000")),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.other_sources_income.other_income == Decimal("0")
    assert itr2_input.os_pf_interest_10_11_first_proviso == Decimal("12000")
    assert itr2_input.os_interest_from_others == Decimal("8000")
    result = compute(itr2_input)
    # The 20000 must appear in taxable other-sources income exactly once --
    # not zero (undertaxed) and not 40000 (double-counted).
    assert result.other_sources_income - baseline_result.other_sources_income == Decimal("20000")


def test_interest_gross_sums_all_nine_of_its_own_declared_sub_items() -> None:
    """Schedule OS item "1b" (``InterestGross``, "Interest, Gross") is
    declared as bi+bii+biii+biv+bv+bvi+bvii+bviii+bix, but was previously
    computed from only the first three (savings/FD/refund interest) --
    the other six sibling sub-items (pass-through interest, the four PF-
    proviso buckets, and "interest from others") were all correctly
    populated as their own fields a few lines above but never folded into
    their own declared header total. Since item "1" (GrossIncChrgblTaxAtAppRate)
    reads InterestGross directly, this bug also silently understated item 1
    whenever any of those six categories was non-zero."""
    input_data = _input(
        other_sources_income=OtherSourcesIncome(
            savings_bank_interest=Decimal("1000"),
            fixed_deposit_interest=Decimal("2000"),
            interest_on_it_refund=Decimal("300"),
        ),
        os_pass_through_income=Decimal("4000"),
        os_pf_interest_10_11_first_proviso=Decimal("500"),
        os_pf_interest_10_11_second_proviso=Decimal("600"),
        os_pf_interest_10_12_first_proviso=Decimal("700"),
        os_pf_interest_10_12_second_proviso=Decimal("800"),
        os_interest_from_others=Decimal("900"),
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]
    expected_total = 1000 + 2000 + 300 + 4000 + 500 + 600 + 700 + 800 + 900
    assert block["InterestGross"] == expected_total
    # Item 1 (GrossIncChrgblTaxAtAppRate) picks up the fix automatically,
    # since it reads InterestGross directly rather than re-deriving it.
    assert block["GrossIncChrgblTaxAtAppRate"] == expected_total


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


def test_pti_os_head_entry_retaining_special_rate_character_is_taxed_via_schedule_si() -> None:
    """OS-head Schedule PTI income that retains a special-rate character in
    the unit holder's hands (section 115UA(2)/115UB(1) proviso: pass-through
    income keeps the same head AND rate the fund itself earned it under) was
    previously always taxed at slab rate regardless of `section` -- no
    dispatch path routed it to Schedule SI at all, and Schedule OS's own
    item "2e" (PassThrIncOSChrgblSplRate) stayed hardcoded 0. A second
    OS-head entry with a section outside the special-rate set (e.g. a plain
    "115UB" reference, not one of the specific special-rate codes) must
    still fall through to ordinary slab-rate treatment, unaffected."""
    input_data = _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("100000")),
        pti_entries=[
            # Fund's own underlying income was itself lottery-type (115BB)
            # -- retains that character and 30% flat rate in the unit
            # holder's hands.
            PTIEntry(
                entity_name="Lottery Fund", entity_pan="AAATL1234B",
                income_head="OS", section="115BB", income_amount=Decimal("40000"),
            ),
            # Ordinary pass-through OS income, no special-rate character --
            # must stay slab-rate.
            PTIEntry(
                entity_name="Ordinary InvIT", entity_pan="AAATO1234B",
                income_head="OS", section="115UB", income_amount=Decimal("15000"),
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)

    # GTI includes both entries regardless of rate treatment.
    assert result.other_sources_income == Decimal("100000") + Decimal("40000") + Decimal("15000")
    # Only the 115BB-classified entry is taxed at special rate via Schedule SI.
    si = result.schedules["si"]
    assert si.total_special_rate_income == Decimal("40000")

    os_block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]
    assert os_block["PassThrIncOSChrgblSplRate"] == 40000
    assert os_block["IncChargeableSpecialRates"] == 40000
    partb_ti = document["ITR"]["ITR2"]["PartB-TI"]
    assert partb_ti["IncChargeableTaxSplRates"] == 40000


def test_schedule_ei_inc_not_chrgbl_to_tax_and_total_exempt_inc_formulas_are_correct() -> None:
    """Form item 4 ("Income claimed as not chargeable to tax as per DTAA")
    is "Total Income from DTAA claimed as not chargeable to tax" -- the sum
    of the paired ``IncNotChrgblAsPerDTAADtls`` detail rows, not a duplicate
    of item 1 (``InterestInc``). No mapper populates that detail array for
    ITR-2 yet, so item 4 must correctly be 0 even when real exempt interest
    is disclosed. Item 6 (``TotalExemptInc``) is the form's own declared
    "Total (1+2+3+4+5)", and must include items 4/5, not just 1+2+3."""
    input_data = _input(
        exempt_income=ExemptIncome(
            ppf_interest=Decimal("40000"),
            nre_interest=Decimal("10000"),
            share_of_profit_from_firm=Decimal("5000"),
        ),
        agricultural_income=AgriculturalIncome(gross_agricultural_income=Decimal("20000")),
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    ei = document["ITR"]["ITR2"]["ScheduleEI"]

    assert ei["InterestInc"] == 50000  # 40000 ppf + 10000 nre
    assert ei["Others"] == 5000
    assert ei["NetAgriIncOrOthrIncRule7"] == int(result.net_agricultural_income)
    # Item 4 must NOT duplicate item 1 -- no DTAA detail rows exist, so it
    # is correctly 0, matching the always-empty detail array.
    assert ei["IncNotChrgblAsPerDTAA"]["IncNotChrgblAsPerDTAADtls"] == []
    assert ei["IncNotChrgblToTax"] == 0
    assert ei["PassThrIncNotChrgblTax"] == 0
    # Item 6 = 1+2+3+4+5.
    expected_total = 50000 + int(result.net_agricultural_income) + 5000 + 0 + 0
    assert ei["TotalExemptInc"] == expected_total


def test_schedule_ei_others_inc_dtls_reports_real_description_not_empty_array() -> None:
    """``ExemptIncome.other_description`` (free-text nature of "other
    exempt income") was never read by ``_schedule_ei()`` -- ``OthersInc.
    OthersIncDtls`` was hardcoded ``[]`` even though the scalar total
    (``other_exempt``, folded into item 3's own ``Others`` figure) was
    already correctly populated. A missing description falls back to a
    sensible default rather than omitting the row or fabricating a specific
    statutory sub-category this schema field was never captured to hold."""
    input_data = _input(
        exempt_income=ExemptIncome(
            other_exempt=Decimal("12000"), other_description="Scholarship for education",
        ),
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    others_inc = document["ITR"]["ITR2"]["ScheduleEI"]["OthersInc"]["OthersIncDtls"]
    assert others_inc == [{"Description": "Scholarship for education", "OthAmount": 12000}]

    # No description supplied -- falls back to a sensible default, not an
    # empty/missing row (the schema requires a non-empty Description when
    # present at all).
    no_desc_input = _input(exempt_income=ExemptIncome(other_exempt=Decimal("5000")))
    no_desc_document = build_itr2_json(compute(no_desc_input), no_desc_input)
    _assert_schema_valid(no_desc_document)
    no_desc_others = no_desc_document["ITR"]["ITR2"]["ScheduleEI"]["OthersInc"]["OthersIncDtls"]
    assert no_desc_others == [{"Description": "Other exempt income", "OthAmount": 5000}]


def test_schedule_os_tax_accumulated_bal_rec_pf_reports_real_per_year_breakdown() -> None:
    """``TaxAccmltdBalRecPFDtls`` (the form's own per-assessment-year
    accumulated-PF sub-table) was always ``[]``, even when the aggregate
    totals it should sum to were real and disclosed -- the per-year detail
    was collapsed to scalar totals before ever reaching ``ITR2Input``."""
    input_data = _input(
        os_pf_income_benefit=Decimal("18000"),
        os_pf_tax_benefit=Decimal("1800"),
        os_pf_accumulated_entries=[
            OSAccumulatedPFEntry(
                assessment_year="2022-23", income_benefit=Decimal("10000"), tax_benefit=Decimal("1000"),
            ),
            OSAccumulatedPFEntry(
                assessment_year="2023-24", income_benefit=Decimal("8000"), tax_benefit=Decimal("800"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    pf_block = document["ITR"]["ITR2"]["ScheduleOS"]["IncOthThanOwnRaceHorse"]["TaxAccumulatedBalRecPF"]

    assert pf_block["TaxAccmltdBalRecPFDtls"] == [
        {"AssessmentYear": "2022-23", "IncomeBenefit": 10000, "TaxBenefit": 1000},
        {"AssessmentYear": "2023-24", "IncomeBenefit": 8000, "TaxBenefit": 800},
    ]
    assert pf_block["TotalIncomeBenefit"] == 18000
    assert pf_block["TotalTaxBenefit"] == 1800


def test_accumulated_pf_per_year_breakdown_reaches_json_via_the_draft_pipeline() -> None:
    """The real v2 draft pipeline (``draft_to_itr2_input.py``'s
    ``_map_os_accumulated_pf()``) must carry the per-year rows through to
    ``ITR2Input``, not just the aggregate totals it always computed."""
    from app.engine.draft_to_itr2_input import draft_to_itr2_input
    from tests.test_draft_to_itr2_input import _filing_ready_itr2_draft
    from app.schemas.return_draft import AccumulatedPfEntry

    draft = _filing_ready_itr2_draft()
    draft.otherSources.accumulatedPf = [
        AccumulatedPfEntry(id="pf1", assessmentYear="2022-23", incomeBenefit=Decimal("10000"), taxBenefit=Decimal("1000")),
        AccumulatedPfEntry(id="pf2", assessmentYear="2023-24", incomeBenefit=Decimal("8000"), taxBenefit=Decimal("800")),
    ]
    itr2_input, _breakdown = draft_to_itr2_input(draft)
    assert itr2_input.os_pf_income_benefit == Decimal("18000")
    assert {(e.assessment_year, e.income_benefit, e.tax_benefit) for e in itr2_input.os_pf_accumulated_entries} == {
        ("2022-23", Decimal("10000"), Decimal("1000")),
        ("2023-24", Decimal("8000"), Decimal("800")),
    }
    # JSON-level serialization of these entries is independently proven by
    # test_schedule_os_tax_accumulated_bal_rec_pf_reports_real_per_year_breakdown
    # above; this test's own scope is the mapper wiring specifically.


def test_schedule_pti_routes_111a_112a_pass_through_gains_to_their_own_sub_bucket() -> None:
    """Schedule PTI's ``STCG_Sec111A``/``LTCG_Sec112A`` were always zeroed,
    with the full amount routed into ``STCG_Others``/``LTCG_Others``
    regardless of ``item.section`` -- misrepresenting a 111A/112A
    pass-through gain as "Others", inconsistent with Schedule SI's own
    111A/112A line items for the identical income (the calculator's own PTI
    dispatch loop already taxes these two cases differently: `pti.section
    == "111A"` for STCG, `"112A" in pti.section.upper()` for LTCG). This
    fix mirrors that exact same classification, not a new one."""
    input_data = _input(
        pti_entries=[
            PTIEntry(
                entity_name="STT Fund", entity_pan="AAATS1234B",
                income_head="STCG", section="111A", income_amount=Decimal("40000"),
            ),
            PTIEntry(
                entity_name="Other Fund", entity_pan="AAATO1234B",
                income_head="STCG", section="OTHER", income_amount=Decimal("25000"),
            ),
            PTIEntry(
                entity_name="Equity 112A Fund", entity_pan="AAATE1234B",
                income_head="LTCG", section="112A", income_amount=Decimal("60000"),
            ),
            PTIEntry(
                entity_name="Debt Fund", entity_pan="AAATD1234B",
                income_head="LTCG", section="OTHER", income_amount=Decimal("15000"),
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    pti_rows = document["ITR"]["ITR2"]["SchedulePTI"]["SchedulePTIDtls"]

    stt_row = next(r for r in pti_rows if r["BusinessName"] == "STT Fund")["CapitalGainsPTI"]
    assert stt_row["STCG_Sec111A"]["NetIncomeLoss"] == 40000
    assert stt_row["STCG_Others"]["NetIncomeLoss"] == 0

    other_row = next(r for r in pti_rows if r["BusinessName"] == "Other Fund")["CapitalGainsPTI"]
    assert other_row["STCG_Sec111A"]["NetIncomeLoss"] == 0
    assert other_row["STCG_Others"]["NetIncomeLoss"] == 25000

    eq112a_row = next(r for r in pti_rows if r["BusinessName"] == "Equity 112A Fund")["CapitalGainsPTI"]
    assert eq112a_row["LTCG_Sec112A"]["NetIncomeLoss"] == 60000
    assert eq112a_row["LTCG_Others"]["NetIncomeLoss"] == 0

    debt_row = next(r for r in pti_rows if r["BusinessName"] == "Debt Fund")["CapitalGainsPTI"]
    assert debt_row["LTCG_Sec112A"]["NetIncomeLoss"] == 0
    assert debt_row["LTCG_Others"]["NetIncomeLoss"] == 15000


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


def test_property_filing_detail_requires_property_owner_other_when_owner_is_others() -> None:
    """A bare property_owner="OT" with no property_owner_other description
    is the same "flag with no detail" bug class as co_owned/co_owner_details
    immediately above -- the schema itself now makes it impossible to
    construct, matching that established precedent."""
    with pytest.raises(ValueError, match="property_owner_other"):
        PropertyFilingDetail(
            address_detail="7 MG Road",
            city_or_town_or_district="Bengaluru",
            state_code="29",
            pin_code="560001",
            property_owner="OT",
        )


def test_schedule_hp_serializes_property_owner_other_only_when_owner_is_others() -> None:
    """"PropertyOwnerOther" (who "Others" refers to when PropertyOwner is
    "OT") was captured on the frontend (HousePropertyEntryManager.tsx) and
    on HouseProperty.propertyOwnerOther (return_draft.py), but
    PropertyFilingDetail had no field to receive it at all -- the value was
    silently dropped before ever reaching the ITD JSON. Also confirms the
    key is correctly OMITTED (not emitted as an empty string) for every
    other PropertyOwner value, matching this codebase's established
    no-empty-placeholder convention."""
    input_data = _input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("300000"),
        ),
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="7 MG Road",
                city_or_town_or_district="Bengaluru",
                state_code="29",
                pin_code="560001",
                property_owner="OT",
                property_owner_other="HUF of taxpayer's late father",
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleHP"]["PropertyDetails"][0]
    assert row["PropertyOwner"] == "OT"
    assert row["PropertyOwnerOther"] == "HUF of taxpayer's late father"


def test_schedule_hp_deemed_let_out_property_discloses_d_code_not_collapsed_to_l() -> None:
    """The official schema's ``ifLetOut`` enum is exactly {"L", "D", "S"}
    ("D" = deemed let out, section 23(4), for a taxpayer owning more
    properties than the self-occupied-exempt limit) -- previously collapsed
    to "S"/"L" only, so a deemed-let-out property was always misrepresented
    as ordinary "Let Out". ITR-1's own builder already passes
    ``property_type.value`` straight through unchanged; ITR-2's alone
    diverged."""
    input_data = _input(
        house_properties=[
            HousePropertyIncome(
                property_type=PropertyType.DEEMED_LET_OUT,
                annual_rent_received=Decimal("240000"),
            ),
        ],
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="19 Residency Road",
                city_or_town_or_district="Bengaluru",
                state_code="29",
                pin_code="560025",
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleHP"]["PropertyDetails"][0]
    assert row["ifLetOut"] == "D"

    # Self-occupied (the default PropertyFilingDetail.property_owner="SE")
    # must NOT carry the key at all.
    self_input = _input(
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="9 Park Street", city_or_town_or_district="Kolkata",
                state_code="19", pin_code="700016",
            ),
        ],
    )
    self_document = build_itr2_json(compute(self_input), self_input)
    _assert_schema_valid(self_document)
    self_row = self_document["ITR"]["ITR2"]["ScheduleHP"]["PropertyDetails"][0]
    assert self_row["PropertyOwner"] == "SE"
    assert "PropertyOwnerOther" not in self_row


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


def test_schedule_s_income_notified_89a_country_rows_use_official_key_names() -> None:
    """``IncomeNotified89AType`` (Schedule S's own per-employer Section 89A
    country breakdown) was previously passed through with the frontend's
    own field names (``id``/``countryCode``/``amount``) instead of the
    official schema's ``NOT89ACountrycode``/``NOT89AAmount`` -- unlike its
    three sibling detail-row types in the same block
    (``NatureOfSalary``/``NatureOfPerquisites``/``NatureOfProfitInLieuOfSalary``),
    which are correctly transformed by the mapper before reaching this
    builder. Dormant until now (no frontend UI ever populated this array),
    but would have produced schema-invalid JSON the instant it did."""
    input_data = _input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        employer_filing_details=[
            EmployerFilingDetail(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                address_detail="1 Corporate Park",
                city_or_town_or_district="Mumbai",
                state_code="27",
                income_notified_89a=Decimal("50000"),
                income_notified_89a_country_rows=[
                    OS89ACountryEntry(country_code="US", amount=Decimal("50000")),
                ],
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    rows = document["ITR"]["ITR2"]["ScheduleS"]["Salaries"][0]["Salarys"]["IncomeNotified89AType"]
    assert rows == [{"NOT89ACountrycode": "US", "NOT89AAmount": 50000}]


def test_schedule_s_uniform_allowance_disclosed_under_10_14_i_not_10_14_ii() -> None:
    """Uniform allowance (`_exempt_uniform_allowance()`) is exempt only to
    the extent of actual expenditure incurred, unlike transport/CEA/hostel
    (fixed statutory-rate allowances, correctly "10(14)(ii)": "granted to
    meet personal expenses... or to compensate for increased cost of
    living"). Per the official schema's own "10(14)(i)" description
    ("...to the extent actually incurred...") and the calculator's own
    docstring ("u/s 10(14)(i) / Rule 2BB(1)(f)"), uniform allowance belongs
    under "10(14)(i)" -- it was previously tagged "10(14)(ii)" alongside the
    fixed-rate allowances it has nothing statutorily in common with."""
    input_data = _input(
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            uniform_allowance_received=Decimal("20000"),
            uniform_allowance_actual_expenditure=Decimal("15000"),
        ),
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
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    rows = document["ITR"]["ITR2"]["ScheduleS"]["AllwncExemptUs10"]["AllwncExemptUs10Dtls"]
    by_code = {r["SalNatureDesc"]: r["SalOthNatOfInc"] for r in rows}
    assert by_code.get("10(14)(i)") == "Uniform allowance"
    assert "10(14)(ii)" not in by_code


def test_schedule_s_reports_real_per_employer_section_10_exemption_rows_not_discarded() -> None:
    """``detail.section10_exemption_rows`` (EmployerEntryManager.tsx's own
    "Section 10 Exemption" row editor -- 10(6)/10(7)/10(10CC)/EIC/10(17)/
    etc., real frontend-captured data) was computed into a local
    ``exemption_rows`` variable that was then shadowed and discarded --
    ``AllwncExemptUs10Dtls`` was built purely from the calculator's own 10
    fixed exemption codes, which don't cover any of these. Also confirms
    rows from EVERY employer are collected, not just the last one iterated
    (the discarded local was loop-scoped and never accumulated across
    employers even before being dropped)."""
    input_data = _input(
        salary_income=SalaryIncome(gross_salary=Decimal("1500000")),
        tds1_entries=[
            TDS1Entry(
                employer_tan="DELA00003C", employer_name="Acme Corp",
                income_chargeable=Decimal("900000"), tds_deducted=Decimal("40000"),
            ),
            TDS1Entry(
                employer_tan="BLRA00004D", employer_name="Beta Corp",
                income_chargeable=Decimal("600000"), tds_deducted=Decimal("20000"),
            ),
        ],
        employer_filing_details=[
            EmployerFilingDetail(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                address_detail="1 Corporate Park",
                city_or_town_or_district="Mumbai",
                state_code="27",
                section10_exemption_rows=[
                    {"SalNatureDesc": "10(17)", "SalOthNatOfInc": "MLA allowance", "SalOthAmount": 12000},
                ],
            ),
            EmployerFilingDetail(
                employer_tan="BLRA00004D",
                employer_name="Beta Corp",
                address_detail="2 Residency Road",
                city_or_town_or_district="Bengaluru",
                state_code="29",
                section10_exemption_rows=[
                    {"SalNatureDesc": "10(6)", "SalOthNatOfInc": "Embassy remuneration", "SalOthAmount": 8000},
                    {"SalNatureDesc": "EIC", "SalOthNatOfInc": "Judge's exempt income", "SalOthAmount": 0},  # zero -- excluded
                ],
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    rows = document["ITR"]["ITR2"]["ScheduleS"]["AllwncExemptUs10"]["AllwncExemptUs10Dtls"]
    by_code = {r["SalNatureDesc"]: r for r in rows}

    assert by_code["10(17)"]["SalOthAmount"] == 12000
    assert by_code["10(6)"]["SalOthAmount"] == 8000
    assert "EIC" not in by_code  # zero amount -- correctly excluded, not fabricated


def test_schedule_s_rejects_section_10_exemption_row_with_no_valid_schema_code() -> None:
    """The frontend's "Section10Rows" editor offers an "OTH" catch-all
    option with no matching official ``SalNatureDesc`` enum value -- passing
    it through unfiltered would produce schema-invalid JSON; silently
    dropping it would just reintroduce the exact "real data vanishes"
    defect this fix addresses for every other code. Fails loudly instead,
    naming the employer and the bad code, matching this builder's
    established fail-closed convention (e.g. Schedule 80C's own
    identifier_number guard)."""
    input_data = _input(
        salary_income=SalaryIncome(gross_salary=Decimal("800000")),
        employer_filing_details=[
            EmployerFilingDetail(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                address_detail="1 Corporate Park",
                city_or_town_or_district="Mumbai",
                state_code="27",
                section10_exemption_rows=[
                    {"SalNatureDesc": "OTH", "SalOthNatOfInc": "Some other exemption", "SalOthAmount": 5000},
                ],
            ),
        ],
    )
    result = compute(input_data)
    with pytest.raises(ValueError, match="OTH"):
        build_itr2_json(result, input_data)


def _amt_triggering_input(*, deduction_10aa: Decimal, amt_credits: list) -> ITR2Input:
    """Return an ITR-2 input that genuinely triggers AMT via
    ``AMTInput.deduction_10aa`` alone (old regime, pushing adjusted total
    income past the ₹20L threshold until AMT-computed tax exceeds regular
    tax) -- confirmed empirically, not hand-derived, since the exact AMT
    trigger threshold depends on slab/surcharge/cess interaction.
    Deliberately does NOT also set ``Chapter6ADeductions.amount_10aa``:
    that field is a genuine Chapter VI-A deduction claim with no official
    ITR-2 Schedule VIA field (business-income-linked, correctly rejected
    by §8.0's fix), a different concept from this AMT-only add-back
    trigger."""
    return _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("10000")),
        amt_input=AMTInput(deduction_10aa=deduction_10aa, amt_credits=amt_credits),
    )


def test_schedule_amt_deduction_claim_reflects_the_real_addback_not_zero() -> None:
    """``ScheduleAMT.DeductionClaimUndrAnySec`` (form item, the section-10AA/
    80-IA-to-80RRB/35AD addback that adjusted total income is built from)
    read a ``total_deductions`` attribute that doesn't exist anywhere on
    ``AMTResult`` -- the ``getattr(..., default=0)`` fallback made it
    unconditionally zero on every return this schedule is even built for,
    since Schedule AMT is only emitted when a real, nonzero addback exists
    (``amt_applicable`` requires it). Directly self-contradicted the
    correctly-computed sibling field ``AdjustedUnderSec115JC`` two lines
    below on the same object."""
    input_data = _amt_triggering_input(deduction_10aa=Decimal("2500000"), amt_credits=[])
    result = compute(input_data)
    assert result.amt_tax > 0
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    schedule = document["ITR"]["ITR2"]["ScheduleAMT"]
    assert schedule["DeductionClaimUndrAnySec"] == 2500000
    # The form's own D1-style chain: item + addback = adjusted total income.
    assert (
        schedule["TotalIncItemPartBTI"] + schedule["DeductionClaimUndrAnySec"]
        == schedule["AdjustedUnderSec115JC"]
    )


def test_schedule_amtc_uses_correct_official_field_names_and_schema_validates() -> None:
    """``ScheduleAMTCDtls`` rows previously used entirely invented field
    names (``AssessmentYear``/``AmtTaxCreditBF``/``TaxSection115JD``/
    ``AmtTaxCreditUtilisedCY``/``AmtCreditCF``) matching none of the six
    real, all-required schema field names -- every row was unconditionally
    schema-invalid whenever any AMT credit was brought forward."""
    input_data = _amt_triggering_input(
        deduction_10aa=Decimal("2500000"),
        amt_credits=[AMTCreditItem(assessment_year="2023-24", credit_brought_forward=Decimal("50000"))],
    )
    result = compute(input_data)
    assert result.amt_tax > 0
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    row = document["ITR"]["ITR2"]["ScheduleAMTC"]["ScheduleAMTCDtls"][0]
    assert row["AssYr"] == "2023-24"
    assert row["Gross"] == 50000
    assert row["AmtCreditSetOfEy"] == 0
    assert row["AmtCreditBalBroughtFwd"] == 50000
    assert row["AmtCreditUtilized"] == 50000  # fully absorbed -- amt_tax comfortably exceeds 50000
    assert row["BalAmtCreditCarryFwd"] == 0
    assert "AssessmentYear" not in row and "AmtTaxCreditBF" not in row and "AmtCreditCF" not in row


def test_schedule_amtc_applies_fifo_across_multiple_years_not_double_counting() -> None:
    """Multiple years of brought-forward AMT credit are utilized oldest-
    year-first against this year's available AMT-tax offset capacity, not
    each row independently claiming the full capacity -- the previous code
    applied ``result.amt_tax`` in full to every row regardless of how much
    earlier (older) rows had already consumed, over-crediting utilization
    for any return with more than one year of brought-forward credit."""
    input_data = _amt_triggering_input(
        deduction_10aa=Decimal("5000000"),
        amt_credits=[
            # Deliberately out of chronological order in the input -- the
            # builder must still process oldest first.
            AMTCreditItem(assessment_year="2023-24", credit_brought_forward=Decimal("500000")),
            AMTCreditItem(assessment_year="2022-23", credit_brought_forward=Decimal("900000")),
        ],
    )
    result = compute(input_data)
    assert result.amt_tax == Decimal("1060316")  # confirmed empirically for this fixture
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    amtc = document["ITR"]["ITR2"]["ScheduleAMTC"]
    rows_by_year = {r["AssYr"]: r for r in amtc["ScheduleAMTCDtls"]}

    # Older year (2022-23) absorbs its full 900000 first.
    assert rows_by_year["2022-23"]["AmtCreditUtilized"] == 900000
    assert rows_by_year["2022-23"]["BalAmtCreditCarryFwd"] == 0
    # Remaining capacity (1060316 - 900000 = 160316) is all that's left for
    # the newer year -- NOT the full 500000 a per-row-independent
    # (pre-fix) computation would have given it.
    assert rows_by_year["2023-24"]["AmtCreditUtilized"] == 160316
    assert rows_by_year["2023-24"]["BalAmtCreditCarryFwd"] == 339684

    assert amtc["TotAMTGross"] == 1400000
    assert amtc["TotBalBF"] == 1400000
    assert amtc["TotAmtCreditUtilisedCY"] == 1060316
    assert amtc["TotBalAMTCreditCF"] == 339684
    assert amtc["CurrYrCreditCarryFwd"] == 339684
    # A real monetary total (was previously len(rows) == 2, a row count).
    assert amtc["TotSetOffEys"] == 0


def test_schedule_amtc_rejects_out_of_range_assessment_year() -> None:
    """The schema's AssYr enum on ScheduleAMTCDtls only covers 2013-14
    through 2025-26; AMTCreditItem.assessment_year is Pydantic-typed more
    loosely, so an out-of-range year (e.g. the current AY, which belongs
    in ScheduleAMT/the top-level TaxSection115JC block instead) must be
    caught here with a clear error, not silently emitted as schema-invalid
    JSON."""
    input_data = _amt_triggering_input(
        deduction_10aa=Decimal("2500000"),
        amt_credits=[AMTCreditItem(assessment_year="2026-27", credit_brought_forward=Decimal("50000"))],
    )
    result = compute(input_data)
    with pytest.raises(ValueError, match="2026-27"):
        build_itr2_json(result, input_data)


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


def test_schedule_cfl_separates_current_year_fresh_losses_from_earlier_years_brought_forward() -> None:
    """Form row ix "Total of earlier year losses" (``TotalOfBFLossesEarlierYrs``)
    covers only the genuine AY2018-19..2025-26 brought-forward entries; row
    xi "2026-27 (Current year losses)" (``CurrentAYloss``) discloses this
    year's own fresh unabsorbed loss separately; row xii "Total loss carried
    forward to future years" (``TotalLossCFSummary``) is ix+xi combined.
    Previously ``TotalOfBFLossesEarlierYrs`` and ``TotalLossCFSummary`` both
    read the same unfiltered total (built from ``cyla.entries`` tagged
    "2026-27" AND ``bfla.entries``, unfiltered by year) -- mislabeling this
    year's own fresh LTCG loss as an "earlier year" loss, and ``CurrentAYloss``
    (the schema's own dedicated slot for it) was never emitted at all."""
    input_data = _input(
        cg_transactions=[
            # A fresh AY2026-27 LTCG loss of 50000 (450000 - 500000).
            CGTransaction(
                asset_type=CGAssetType.LISTED_SECURITY,
                date_of_acquisition=date(2020, 1, 1), date_of_transfer=date(2025, 6, 1),
                full_consideration=Decimal("450000"), cost_of_acquisition=Decimal("500000"),
            ),
        ],
        bf_losses=[
            # A genuine AY2023-24 brought-forward STCG loss of 30000.
            BFLossItem(
                assessment_year="2023-24",
                head=LossHead.SHORT_TERM_CAPITAL,
                original_loss=Decimal("30000"),
                brought_forward=Decimal("30000"),
                date_of_filing=date(2023, 7, 31),
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    cfl = document["ITR"]["ITR2"]["ScheduleCFL"]

    earlier = cfl["TotalOfBFLossesEarlierYrs"]["LossSummaryDetail"]
    assert earlier["TotalSTCGPTILossCF"] == 30000
    assert earlier["TotalLTCGPTILossCF"] == 0  # the fresh LTCG loss must NOT land here

    assert "CurrentAYloss" in cfl
    current = cfl["CurrentAYloss"]["LossSummaryDetail"]
    assert current["TotalLTCGPTILossCF"] == 50000
    assert current["TotalSTCGPTILossCF"] == 0

    total = cfl["TotalLossCFSummary"]["LossSummaryDetail"]
    assert total["TotalSTCGPTILossCF"] == 30000
    assert total["TotalLTCGPTILossCF"] == 50000

    # The per-year AY2023-24 slot must still show only the real BF loss.
    assert cfl["LossCFFromPrev3rdYearFromAY"]["CarryFwdLossDetail"]["TotalSTCGPTILossCF"] == 30000


def test_schedule_cfl_omits_current_ay_loss_when_no_fresh_loss_exists() -> None:
    """Confirms the fix above does not fabricate an empty ``CurrentAYloss``
    placeholder when every carry-forward entry is a genuine brought-forward
    loss -- matching this codebase's own "no empty placeholder objects"
    convention elsewhere in this builder."""
    input_data = _input(
        bf_losses=[
            BFLossItem(
                assessment_year="2023-24",
                head=LossHead.SHORT_TERM_CAPITAL,
                original_loss=Decimal("30000"),
                brought_forward=Decimal("30000"),
                date_of_filing=date(2023, 7, 31),
            ),
        ],
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    cfl = document["ITR"]["ITR2"]["ScheduleCFL"]
    assert "CurrentAYloss" not in cfl
    assert (
        cfl["TotalOfBFLossesEarlierYrs"]["LossSummaryDetail"]
        == cfl["TotalLossCFSummary"]["LossSummaryDetail"]
    )


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


def test_esop_deferral_rejects_dpiit_registration_number_with_wrong_format() -> None:
    """``ESOPDeferralInput.dpiit_registration_number`` previously had no
    pattern constraint at all (just ``min_length=1, max_length=50``), even
    though the official schema's ``DPIITRegNo`` requires ``DIPP[0-9]{3,5}``
    -- any other format passed Pydantic and would have failed only at ITD
    submission, a late and opaque rejection."""
    with pytest.raises(ValidationError, match="dpiit_registration_number"):
        ESOPDeferralInput(
            employer_pan="AAACS1234A",
            dpiit_registration_number="NOT-A-REAL-DPIIT-NUMBER",
            assessment_year="2025-26",
        )
    # A real, correctly-formatted number still constructs cleanly.
    ESOPDeferralInput(
        employer_pan="AAACS1234A", dpiit_registration_number="DIPP12345",
        assessment_year="2025-26",
    )


def test_tds2_entry_rejects_head_of_income_outside_the_official_enum() -> None:
    """``TDS2Entry.head_of_income`` was a bare ``Optional[str]`` (unlike its
    correctly ``Literal``-typed sibling on ``TDS3FilingDetail``), so a value
    outside the official ``TDSOthThanSalaryDtls.HeadOfIncome`` enum
    (``HP``/``CG``/``OS``/``EI``/``NA``) reached the builder validly per
    Pydantic but would have failed the official schema only at ITD
    submission."""
    with pytest.raises(ValidationError, match="head_of_income"):
        TDS2Entry(deductor_tan="MUMA12345B", tds_section="194A", head_of_income="BP")
    # Every real enum value still constructs cleanly, including "NA"
    # (present in TDS2's own enum, unlike TDS3's).
    for value in ("HP", "CG", "OS", "EI", "NA"):
        TDS2Entry(deductor_tan="MUMA12345B", tds_section="194A", head_of_income=value)


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


def test_schedule_tr1_dtaa_split_is_not_double_counted_across_mixed_relief_sections() -> None:
    """``ScheduleTR1``'s own ``TaxReliefOutsideIndiaDTAA``/``NotDTAA`` split
    previously matched each row against the ENTIRE ``tr1_entries`` list by
    country code -- a per-COUNTRY test, not a per-ROW one. Two rows for the
    same country under different relief sections (one DTAA-relieved u/s
    90, one unilaterally-relieved u/s 91 -- a real scenario for a taxpayer
    with two income sources in one country under different TINs) each
    matched BOTH tests, so both rows' relief was summed into BOTH buckets,
    overstating the schedule's own total."""
    input_data = _input(
        fsi_entries=[
            FSICountryEntry(country_code="44", tax_identification_no="UK-TIN-1", salary_income=Decimal("100000")),
            FSICountryEntry(country_code="44", tax_identification_no="UK-TIN-2", salary_income=Decimal("50000")),
        ],
        tr1_entries=[
            TR1Entry(
                country_code="44", tax_identification_no="UK-TIN-1",
                tax_paid_outside_india=Decimal("10000"), indian_tax_payable=Decimal("8000"),
                relief_claimed=Decimal("8000"), relief_section="90",
            ),
            TR1Entry(
                country_code="44", tax_identification_no="UK-TIN-2",
                tax_paid_outside_india=Decimal("5000"), indian_tax_payable=Decimal("4000"),
                relief_claimed=Decimal("4000"), relief_section="91",
            ),
        ],
    )
    document = build_itr2_json(compute(input_data), input_data)
    _assert_schema_valid(document)
    tr1 = document["ITR"]["ITR2"]["ScheduleTR1"]
    assert tr1["TaxReliefOutsideIndiaDTAA"] == 8000
    assert tr1["TaxReliefOutsideIndiaNotDTAA"] == 4000
    assert tr1["TotalTaxReliefOutsideIndia"] == 12000  # not 24000 (double-counted)


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


def test_asset_out_india_flag_reflects_real_schedule_fa_presence() -> None:
    """Part B-TTI's ``AssetOutIndiaFlag`` (form item 19: "Do you ... hold
    ... any asset ... located outside India? [Ensure Schedule FA is filled
    up if the answer is Yes]") was previously hardcoded "NO" regardless of
    Schedule FA content -- a taxpayer with real, correctly-serialized
    Schedule FA entries would file a return where Schedule FA is populated
    but Part B-TTI's own flag says no foreign assets exist, a direct
    self-contradiction in the same JSON."""
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
    assert document["ITR"]["ITR2"]["PartB_TTI"]["AssetOutIndiaFlag"] == "YES"

    # No foreign assets at all -- flag correctly stays "NO".
    no_fa_input = _input()
    no_fa_document = build_itr2_json(compute(no_fa_input), no_fa_input)
    _assert_schema_valid(no_fa_document)
    assert no_fa_document["ITR"]["ITR2"]["PartB_TTI"]["AssetOutIndiaFlag"] == "NO"


def test_net_tax_liability_is_balance_before_interest_not_the_final_aggregate() -> None:
    """Form item 12 "Net tax liability (10 - 11d)" is computed BEFORE
    interest/fees are added -- distinct from item 14 "Aggregate liability
    (12 + 13e)", which comes after. Previously both fields read the
    calculator's own ``net_tax_liability`` (the FINAL, item-14-equivalent
    total, interest/fees already baked in), making ``NetTaxLiability`` ==
    ``AggregateTaxInterestLiability`` -- a direct self-contradiction on any
    return with 234A/B/C interest, a 234F late fee, or Section 89/90/91
    relief (item 12 must be strictly less than item 14 whenever any
    interest/fee applies)."""
    input_data = _input(
        salary_income=SalaryIncome(gross_salary=Decimal("2000000")),
        employer_filing_details=[
            EmployerFilingDetail(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                address_detail="1 Corporate Park",
                city_or_town_or_district="Mumbai",
                state_code="27",
            ),
        ],
        relief_89=Decimal("10000"),
        filing_date=date(2026, 8, 10),  # after the 2026-07-31 ITR-2 due date
        due_date=date(2026, 7, 31),
    )
    result = compute(input_data)
    assert result.total_interest > 0
    assert result.late_fee_234f > 0
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    computation = document["ITR"]["ITR2"]["PartB_TTI"]["ComputationOfTaxLiability"]

    expected_net_tax_liability = int(result.gross_tax_liability - result.relief_89 - result.relief_90_91)
    assert computation["NetTaxLiability"] == expected_net_tax_liability
    assert computation["AggregateTaxInterestLiability"] == int(result.net_tax_liability)
    # The two must genuinely differ once interest/fees are nonzero -- this
    # is the exact self-contradiction the bug produced.
    assert computation["NetTaxLiability"] < computation["AggregateTaxInterestLiability"]


def test_total_intrst_pay_includes_the_234f_late_fee_and_234i_fee() -> None:
    """Form item 13e "Total Interest and Fee Payable" = 13a+13b+13c+13d+13da
    (234A+234B+234C+234F+234-I) -- previously summed only 234A/B/C, silently
    excluding the 234F late fee disclosed one field above it (and
    ``FeeFurnish234I`` was separately hardcoded 0 even though the
    calculator already computes ``result.fees_234i``)."""
    input_data = _input(
        salary_income=SalaryIncome(gross_salary=Decimal("2000000")),
        employer_filing_details=[
            EmployerFilingDetail(
                employer_tan="DELA00003C",
                employer_name="Acme Corp",
                address_detail="1 Corporate Park",
                city_or_town_or_district="Mumbai",
                state_code="27",
            ),
        ],
        filing_date=date(2026, 8, 10),
        due_date=date(2026, 7, 31),
    )
    result = compute(input_data)
    assert result.late_fee_234f > 0
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    intrst_pay = document["ITR"]["ITR2"]["PartB_TTI"]["ComputationOfTaxLiability"]["IntrstPay"]

    assert intrst_pay["FeeFurnish234I"] == int(result.fees_234i)
    expected_total = int(
        result.interest_234a + result.interest_234b + result.interest_234c
        + result.late_fee_234f + result.fees_234i
    )
    assert expected_total > int(
        result.interest_234a + result.interest_234b + result.interest_234c
    )
    assert intrst_pay["TotalIntrstPay"] == expected_total


def test_partb_ti_inc_from_os_splits_special_rate_and_race_horse_income_consistent_with_schedule_os() -> None:
    """Part B-TI's ``IncFromOS.IncChargblSplRate``/``FromOwnRaceHorse`` were
    hardcoded 0 while the whole blended Other-Sources total (normal-rate +
    special-rate + race-horse) was dumped into ``OtherSrcThanOwnRaceHorse``
    alone -- violating CBDT Validation Rules 500-502, which require these
    figures be "consistent with income offered in Schedule OS"."""
    input_data = _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("50000")),
        os_special_rate_entries=[
            OSSpecialRateEntry(source_description="5A1bA", source_amount=Decimal("100000")),
        ],
        os_race_horse=OSRaceHorseActivity(
            receipts=Decimal("500000"), deduction_us57=Decimal("300000"),
            balance=Decimal("200000"),
        ),
    )
    result = compute(input_data)
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    os_block = document["ITR"]["ITR2"]["ScheduleOS"]
    inc_from_os = document["ITR"]["ITR2"]["PartB-TI"]["IncFromOS"]

    assert inc_from_os["IncChargblSplRate"] == 100000 == os_block["IncOthThanOwnRaceHorse"]["IncChargeableSpecialRates"]
    assert inc_from_os["FromOwnRaceHorse"] == 200000 == os_block["IncFromOwnHorse"]["BalanceOwnRaceHorse"]
    assert inc_from_os["OtherSrcThanOwnRaceHorse"] == 50000
    assert inc_from_os["TotIncFromOS"] == 350000  # 50000 + 100000 + 200000
    assert (
        inc_from_os["OtherSrcThanOwnRaceHorse"] + inc_from_os["IncChargblSplRate"] + inc_from_os["FromOwnRaceHorse"]
        == inc_from_os["TotIncFromOS"]
    )


def test_inc_charge_tax_spl_rate_111a_112_and_spl_rates_cover_full_schedule_si_total() -> None:
    """Form items 10/13 (``IncChargeTaxSplRate111A112``/
    ``IncChargeableTaxSplRates``) are both, per the official form text,
    "total of column (i) of schedule SI" -- CBDT rule 374 requires item 10
    "consistent with all the special incomes of Schedule SI", not just
    111A/112/112A. Previously both summed only the CG-only
    111A+112+112A(+VDA) subset from ``post_loss_cg``, silently excluding
    lottery/unexplained-income/NRI-special-rate-OS/DTAA-OS income that
    Schedule SI itself discloses and taxes."""
    input_data = _input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2025, 1, 1), date_of_transfer=date(2025, 6, 1),
                full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
            ),
        ],
        os_special_rate_entries=[
            OSSpecialRateEntry(source_description="5A1bA", source_amount=Decimal("100000")),
        ],
    )
    result = compute(input_data)
    si = result.schedules["si"]
    assert si.total_special_rate_income > 0
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    partb_ti = document["ITR"]["ITR2"]["PartB-TI"]

    expected = int(si.total_special_rate_income)
    # The 111A STCG alone (200000 gain) is strictly less than the full
    # Schedule SI total once the 5A1bA special-rate OS income is included --
    # proving the fix actually widened the figure, not just relabeled it.
    assert expected > 200000
    assert partb_ti["IncChargeTaxSplRate111A112"] == expected
    assert partb_ti["IncChargeableTaxSplRates"] == expected
    assert partb_ti["IncChargeTaxSplRate111A112"] == document["ITR"]["ITR2"]["ScheduleSI"]["TotSplRateInc"]


def test_gross_tax_payable_reflects_real_gross_tax_liability() -> None:
    """"GrossTaxPayable" (form item 8, "higher of 1d and 7") is a required
    ``PartB_TTI.ComputationOfTaxLiability`` field and was previously
    hardcoded to ``0`` regardless of the return's real tax liability --
    contradicting its own sibling field ``GrossTaxLiability`` one line
    above on every return with any tax due at all. The distinct,
    correctly-named "GrossTaxPay" field (an unrelated ESOP-deferred-tax
    structure) must still be present and unaffected."""
    input_data = _input(other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("600000")))
    result = compute(input_data)
    assert result.gross_tax_liability > 0
    document = build_itr2_json(result, input_data)
    _assert_schema_valid(document)
    computation = document["ITR"]["ITR2"]["PartB_TTI"]["ComputationOfTaxLiability"]
    assert computation["GrossTaxPayable"] == computation["GrossTaxLiability"] > 0
    assert computation["GrossTaxPay"] == {"TaxInc17": 0, "TaxDeferred17": 0, "TaxDeferredPayableCY": 0}
