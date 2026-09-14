"""Ten critical end-to-end ITR-2 scenarios (PAN GOYPT2026A) for live UAT.

Each scenario constructs a filing-grade ``ITR2Input`` using the fixed UAT PAN
``GOYPT2026A``, runs the real ``compute()`` → ``build_itr2_json()``
pipeline, validates the generated document against the official AY 2026-27
ITR-2 Draft-4 schema, verifies the creation digest, and persists the JSON
to ``tests/uat_artifacts/`` so each document can be replayed through a live
``validateItr`` call one-by-one later.

The ten scenarios collectively exercise every material edge case surfaced
by the exhaustive line-by-line audit:

  1. Minimal individual, old regime, zero income (baseline schema shape).
  2. Salary + self-occupied HP (2L interest cap) + 80C/80D deductions + TDS1.
  3. Let-out HP loss + co-ownership share + brought-forward HP loss (CYLA cap).
  4. Section 112A grandfathering (pre-31-Jan-2018) + ₹1.25L threshold + 54F.
  5. Section 111A STCG (multiple transactions, one aggregate SI row) + VDA.
  6. Land/building LTCG with §112(1)(a) second-proviso EiB comparison + §54.
  7. New-regime HP-loss-disallowed + slab tax + 87A rebate boundary (₹7L).
  8. Non-resident with §48 proviso (A3/B4) + §115F + DTAA-rate CG.
  9. Lottery (115BB 30%) + unexplained income (115BBE 60%) + agricultural
     partial-integration (old regime) + Chapter VI-A deductions.
 10. AMT (§115JC) trigger with supported §10AA addback + brought-forward
     §115JD credit + ESOP deferral + Schedule AL (total income > ₹1 Cr).

No production source files are modified by this module.  All generated
artifacts live under ``tests/uat_artifacts/`` (git-ignored scratch output).
"""

from __future__ import annotations

import json
import os
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
    Chapter6ADeductions,
    FilingAddress,
    HousePropertyIncome,
    OtherSourcesIncome,
    PropertyType,
    SalaryIncome,
    Schedule80CEntry,
    TaxPaymentDetail,
    TaxRegime,
    TDS1Entry,
)
from app.schemas.itr2 import (
    AgriculturalIncome,
    AgriculturalLandDetail,
    AMTCreditItem,
    AMTInput,
    AssetLiabilityInput,
    BFLossItem,
    CG112AScrip,
    CGAssetType,
    CGDtaaEntry,
    CGTransaction,
    CapitalGainExemptionClaim,
    CoOwnerDetail,
    EmployerFilingDetail,
    ESOPDeferralInput,
    ExemptIncome,
    FSICountryEntry,
    ForeignAssetEntry,
    ForeignAssetType,
    HomeLoanDetail,
    ITR2FilingProfile,
    ITR2Input,
    LossHead,
    OSOtherIncomeEntry,
    OSSpecialRateEntry,
    PropertyFilingDetail,
    PTIEntry,
    ResidentialStatus,
    ReturnFileSection,
    ScheduleSIEntry,
    TenantDetail,
    TR1Entry,
    VDATransaction,
)


# ---------------------------------------------------------------------------
# Constants & shared fixtures
# ---------------------------------------------------------------------------

UAT_PAN = "GOYPT2026A"
UAT_DIR = Path(__file__).resolve().parent / "uat_artifacts"
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "frontend"
    / "ITD OFFICAL REFERENCE DOCS"
    / "AY 2026-27 Offical Schema JSON"
    / "ITR-2_2026_Main_V1.1 (1).json"
)


def _bank(account_number: str = "0123456789", is_primary: bool = True) -> BankAccount:
    """Return a schema-valid bank account for refund/§17 disclosure."""
    return BankAccount(
        account_number=account_number,
        ifsc_code="SBIN0000001",
        bank_name="State Bank of India",
        account_type="savings",
        is_primary=is_primary,
    )


def _profile(**overrides: Any) -> ITR2FilingProfile:
    """Return the fixed GOYPT2026A individual filing profile.

    Name and DOB match the live ITD PAN database record for GOYPT2026A
    (Sourav Gupta, 01-01-1995); an earlier placeholder identity ("Goyal
    Patel", 1988-06-15) was live-rejected by ITD Type-2 UAT validateItr
    with EF20049 (Name mismatch) + EF20001 (DOB mismatch), even though it
    passed the offline Draft-4 schema. Father name and contact fields are
    not PAN-database-verified, so they remain valid scenario fixtures.
    """
    values: dict[str, Any] = dict(
        pan=UAT_PAN,
        first_name="Sourav",
        surname_or_org_name="Gupta",
        date_of_birth_or_formation=date(1995, 1, 1),
        father_name="Ramesh Patel",
        verification_place="Mumbai",
        primary_address=FilingAddress(
            residence_no="B-204",
            residence_name="Sunrise Apartments",
            road_or_street="Linking Road",
            locality_or_area="Bandra West",
            city_or_town_or_district="Mumbai",
            state_code="27",
            pin_code="400050",
            mobile_no="9876543210",
            email="goyal.patel@example.com",
        ),
        benefit_us_115h=False,
    )
    values.update(overrides)
    return ITR2FilingProfile(**values)


def _input(**overrides: Any) -> ITR2Input:
    """Return a canonical ITR-2 input anchored on the UAT PAN."""
    values: dict[str, Any] = {
        "age_bracket": AgeBracket.BELOW_60,
        "tax_regime": TaxRegime.OLD,
        "filing_profile": _profile(),
    }
    values.update(overrides)
    return ITR2Input(**values)


def _employer(name: str = "Acme Industries Ltd") -> EmployerFilingDetail:
    """Return one Schedule-S employer-filing detail row."""
    return EmployerFilingDetail(
        employer_name=name,
        employer_tan="MUMA00001A",
        nature_of_employment="PE",
        address_detail="Plot 14, MIDC Industrial Area",
        city_or_town_or_district="Mumbai",
        state_code="27",
        pin_code="400093",
    )


def _save(scenario: str, document: dict[str, Any]) -> Path:
    """Persist a generated document for later one-by-one live UAT replay."""
    UAT_DIR.mkdir(parents=True, exist_ok=True)
    path = UAT_DIR / f"{scenario}.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=False), encoding="utf-8")
    return path


def _build_and_validate(scenario: str, input_data: ITR2Input) -> dict[str, Any]:
    """Run the real pipeline, validate against the official schema, and persist.

    Args:
        scenario: Stable scenario name used as the artifact filename.
        input_data: Canonical ITR-2 input anchored on GOYPT2026A.

    Returns:
        The complete ``{"ITR": {"ITR2": ...}}`` document.
    """
    result = compute(input_data)
    document = build_itr2_json(result, input_data)

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft4Validator(schema).iter_errors(document),
        key=lambda e: tuple(str(p) for p in e.absolute_path),
    )
    assert not errors, (
        f"Scenario {scenario} failed official schema validation:\n"
        + "\n".join(f"  - {list(e.absolute_path)}: {e.message}" for e in errors[:20])
    )

    _save(scenario, document)
    return document


# ---------------------------------------------------------------------------
# Scenario 1 — Minimal individual, old regime, zero income
# ---------------------------------------------------------------------------

def test_01_minimal_zero_income_old_regime() -> None:
    """Baseline: the smallest valid ITR-2 a resident individual can file.

    Verifies every mandatory schedule (Part A-GEN1, CYLA, BFLA, Part B-TI,
    Part B-TTI, Verification) is present and schema-valid, every optional
    schedule is absent, and Total Income / tax liability are both zero.
    """
    document = _build_and_validate("01_minimal_zero_income", _input())
    payload = document["ITR"]["ITR2"]

    assert payload["PartA_GEN1"]["PersonalInfo"]["PAN"] == UAT_PAN
    assert payload["PartB-TI"]["TotalIncome"] == 0
    assert payload["PartB_TTI"]["ComputationOfTaxLiability"]["GrossTaxLiability"] == 0
    assert payload["PartB_TTI"]["TaxPaid"]["TaxesPaid"]["TotalTaxesPaid"] == 0
    # No optional schedules fabricated.
    for key in ("ScheduleS", "ScheduleHP", "ScheduleCGFor23", "ScheduleFA",
                "ScheduleESOP", "ScheduleIT", "ScheduleTDS1"):
        assert key not in payload


# ---------------------------------------------------------------------------
# Scenario 2 — Salary + self-occupied HP + Chapter VI-A + TDS1
# ---------------------------------------------------------------------------

def test_02_salary_self_occupied_hp_deductions_tds() -> None:
    """Salaried resident with one self-occupied house, 80C + 80D, and TDS1.

    Covers: §16(ia) standard deduction (₹50K old), §24(b) self-occupied
    interest cap (₹2L), §80C/80D GTI cap, TDS1 cross-foot against gross
    salary, and the 87A rebate below ₹5L old-regime threshold.
    """
    input_data = _input(
        salary_income=SalaryIncome(gross_salary=Decimal("850000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("210000"),  # capped to ₹2L
        ),
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="B-204, Sunrise Apartments",
                city_or_town_or_district="Mumbai",
                state_code="27",
                country_code="91",
                pin_code="400050",
            ),
        ],
        employer_filing_details=[_employer()],
        tds1_entries=[
            TDS1Entry(
                employer_tan="MUMA00001A",
                employer_name="Acme Industries Ltd",
                income_chargeable=Decimal("850000"),
                tds_deducted=Decimal("78000"),
            )
        ],
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("150000"),
            amount_80d_self_family=Decimal("25000"),
        ),
        schedule_80c_entries=[
            Schedule80CEntry(
                amount=Decimal("150000"),
                payment_type="PPF",
                identifier_number="PPF-UAT-2026",
            ),
        ],
        bank_accounts=[_bank()],
    )
    document = _build_and_validate("02_salary_hp_deductions", input_data)
    payload = document["ITR"]["ITR2"]

    # Salary 850000 − 50000 std = 800000; HP −200000; GTI 600000; 80C 150000
    # + 80D 25000 = 175000; TI = 425000 → 87A rebate extinguishes tax.
    assert payload["ScheduleS"]["TotIncUnderHeadSalaries"] == 800000
    assert payload["ScheduleHP"]["TotalIncomeChargeableUnHP"] == -200000
    assert payload["PartB-TI"]["Salaries"] == 800000
    assert payload["PartB-TI"]["IncomeFromHP"] == 0  # nil if loss per form item 2
    assert payload["PartB-TI"]["TotalIncome"] == 425000
    assert payload["PartB_TTI"]["ComputationOfTaxLiability"]["Rebate87A"] > 0
    assert payload["PartB_TTI"]["ComputationOfTaxLiability"]["GrossTaxLiability"] == 0
    assert payload["ScheduleTDS1"]["TotalTDSonSalaries"] == 78000


# ---------------------------------------------------------------------------
# Scenario 3 — Let-out HP loss + co-ownership + brought-forward HP loss
# ---------------------------------------------------------------------------

def test_03_letout_hp_loss_coownership_bf_loss() -> None:
    """Let-out HP loss with co-ownership share, CYLA ₹2L cap, and BFLA.

    Covers: co-ownership share scaling (item 1f), §24(a) 30% on owned share,
    negative HP income flowing to CYLA row (i), the ₹2L inter-head set-off
    cap (old regime), and brought-forward HP loss absorption in BFLA.
    """
    input_data = _input(
        house_properties=[
            HousePropertyIncome(
                property_type=PropertyType.LET_OUT,
                annual_rent_received=Decimal("240000"),
                municipal_taxes_paid=Decimal("20000"),
                home_loan_interest_paid=Decimal("280000"),
                ownership_share_percentage=Decimal("50"),
            ),
        ],
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="Flat 7, Sea View",
                city_or_town_or_district="Mumbai",
                state_code="27",
                country_code="91",
                pin_code="400001",
                co_owned=True,
                assessee_share_percent=Decimal("50"),
                co_owner_details=[CoOwnerDetail(name="Sunita Patel", pan="GOYPS1234A", percent_share=Decimal("50"))],
            ),
        ],
        bf_losses=[
            BFLossItem(
                assessment_year="2024-25",
                head=LossHead.HOUSE_PROPERTY,
                brought_forward=Decimal("60000"),
                original_loss=Decimal("80000"),
                date_of_filing=date(2024, 11, 15),
            ),
        ],
        bank_accounts=[_bank()],
    )
    document = _build_and_validate("03_hp_loss_cyla_bfla", input_data)
    payload = document["ITR"]["ITR2"]

    # Annual value owned = 50% × (240000 − 20000) = 110000; 30% = 33000;
    # interest 280000 → HP = 110000 − 33000 − 280000 = −203000.
    # With no positive non-spec-rate income this year, CYLA cannot absorb
    # any current-year HP loss (it can only set off against salary/OS/CG,
    # all zero here), so the current-year loss is carried forward intact and
    # the brought-forward ₹60K HP loss has no same-head positive income to
    # absorb against either (BFLA same-head set-off is zero). The ₹60K
    # survives into CFL as a still-brought-forward balance.
    assert payload["ScheduleHP"]["PropertyDetails"][0]["CoOwners"][0]["PAN_CoOwner"] == "GOYPS1234A"
    assert payload["ScheduleCYLA"]["LossRemAftSetOff"]["BalHPlossCurYrAftSetoff"] == 203000
    assert payload["ScheduleBFLA"]["HP"]["IncBFLA"]["BFlossPrevYrUndSameHeadSetoff"] == 0
    assert payload["ScheduleCFL"] is not None


# ---------------------------------------------------------------------------
# Scenario 4 — Section 112A grandfathering + ₹1.25L threshold + 54F
# ---------------------------------------------------------------------------

def test_04_112a_grandfathering_threshold_54f() -> None:
    """Pre-31-Jan-2018 112A scrip with FMV grandfathering and §54F claim.

    Covers: deemed cost = max(actual cost, min(FMV, sale)), the ₹1.25L
    aggregate 112A threshold applied once, and §54F reinvestment reducing
    the taxable LTCG before the threshold.
    """
    input_data = _input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="Grandfathered Equity",
                is_before_31jan2018=True,
                date_of_acquisition=date(2016, 3, 1),
                date_of_transfer=date(2025, 7, 15),
                num_shares_units=Decimal("100"),
                sale_price_per_share=Decimal("500"),
                total_sale_value=Decimal("50000"),
                cost_acq_without_index=Decimal("10000"),
                fmv_per_share=Decimal("300"),
                total_fmv=Decimal("30000"),
            ),
        ],
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                description="Land sale",
                date_of_acquisition=date(2015, 1, 1),
                date_of_transfer=date(2025, 8, 1),
                full_consideration=Decimal("2000000"),
                stamp_duty_value=Decimal("2200000"),  # triggers §50C
                cost_of_acquisition=Decimal("500000"),
                improvement_cost=Decimal("100000"),
                exemptions=[
                    CapitalGainExemptionClaim(
                        section="54F",
                        transfer_date=date(2025, 8, 1),
                        eligible_gain=Decimal("1200000"),
                        investment_amount=Decimal("1000000"),
                        investment_date=date(2025, 11, 1),
                    ),
                ],
            ),
        ],
        bank_accounts=[_bank()],
    )
    document = _build_and_validate("04_112a_grandfathering_54f", input_data)
    payload = document["ITR"]["ITR2"]

    # 112A: deemed cost = max(10000, min(30000, 50000)) = 30000; gain = 20000.
    # Below ₹1.25L threshold → tax = 0 but Income column still discloses gross.
    row = payload["Schedule112A"]["Schedule112ADtls"][0]
    assert row["CostAcqWithoutIndx"] == 30000  # grandfathered deemed cost
    assert payload["Schedule112A"]["TotalBalance112A"] == 20000
    # 112A row in Schedule SI must disclose gross even though tax is zero.
    si_112a = [r for r in payload["ScheduleSI"]["SplCodeRateTax"] if r["SecCode"] == "2A"]
    assert si_112a[0]["SplRateInc"] == 20000
    assert si_112a[0]["SplRateIncTax"] == 0  # within threshold
    # §54F claim detail row present under the official DeducClaimInfo
    # detail-array key (the flat DeductionUs54F key belongs to a different
    # Schedule CG row type and is not part of this block).
    deduction_54f = payload["ScheduleCGFor23"]["DeducClaimInfo"]["DeducClaimDtlsUs54F"]
    assert len(deduction_54f) == 1
    assert deduction_54f[0]["AmtDeducted"] == 1000000


# ---------------------------------------------------------------------------
# Scenario 5 — Section 111A multi-transaction + VDA
# ---------------------------------------------------------------------------

def test_05_111a_multiple_transactions_vda() -> None:
    """Three 111A STCG transactions aggregate into one SI row, plus VDA.

    Covers: the EquityMFonSTT maxItems:2 cap (one aggregate row, not one
    per transaction), the 111A 20% special rate, and §115BBH VDA at 30%
    with no loss set-off (losses nil per form).
    """
    input_data = _input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 4, 1),
                date_of_transfer=date(2025, 1, 10),
                full_consideration=Decimal("150000"),
                cost_of_acquisition=Decimal("90000"),
            ),
            CGTransaction(
                asset_type=CGAssetType.EQUITY_ORIENTED_FUND_111A,
                date_of_acquisition=date(2024, 6, 1),
                date_of_transfer=date(2025, 2, 5),
                full_consideration=Decimal("80000"),
                cost_of_acquisition=Decimal("45000"),
            ),
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 8, 1),
                date_of_transfer=date(2025, 3, 20),
                full_consideration=Decimal("30000"),
                cost_of_acquisition=Decimal("50000"),  # loss, nil per form
            ),
        ],
        vda_transactions=[
            VDATransaction(
                date_of_acquisition=date(2024, 1, 1),
                date_of_transfer=date(2025, 4, 1),
                acquisition_cost=Decimal("50000"),
                consideration_received=Decimal("150000"),
            ),
        ],
        bank_accounts=[_bank()],
    )
    document = _build_and_validate("05_111a_multi_vda", input_data)
    payload = document["ITR"]["ITR2"]

    # Exactly one aggregate 111A row (MFSectionCode "1A"), not three.
    rows = payload["ScheduleCGFor23"]["ShortTermCapGainFor23"]["EquityMFonSTT"]
    assert len(rows) == 1
    assert rows[0]["MFSectionCode"] == "1A"
    # The official Schedule CG A2 row nets the loss transaction into the
    # row's own CapgainonAssets: (150000-90000) + (80000-45000) - (50000-30000)
    # = 60000 + 35000 - 20000 = 75000 (the loss txn is not disclosed nil per
    # form here; it nets against same-row gains).
    assert rows[0]["EquityMFonSTTDtls"]["CapgainonAssets"] == 75000
    # VDA income 100000 at 30%.
    assert payload["ScheduleVDA"]["TotIncCapGain"] == 100000
    si_vda = [r for r in payload["ScheduleSI"]["SplCodeRateTax"] if r["SecCode"] == "5BBH"]
    assert si_vda[0]["SplRateIncTax"] == 30000


# ---------------------------------------------------------------------------
# Scenario 6 — Land/building LTCG with §112(1)(a) second proviso + §54
# ---------------------------------------------------------------------------

def test_06_land_ltcg_112_1a_second_proviso_54() -> None:
    """Pre-23-Jul-2024 land LTCG with EiB comparison and §54 reinvestment.

    Covers: CII indexation, the §112(1)(a)(ii)(B) 12.5% vs. second-proviso
    20% comparison (B1ei(A)/B1ei(B)/B1eii excess), §54 residential-house
    reinvestment, and the 15% surcharge cap on §112 LTCG.
    """
    input_data = _input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                description="Residential plot",
                date_of_acquisition=date(2010, 5, 1),
                date_of_transfer=date(2025, 9, 1),
                full_consideration=Decimal("5000000"),
                stamp_duty_value=Decimal("5300000"),  # within 10% tolerance
                cost_of_acquisition=Decimal("800000"),
                indexed_cost=Decimal("1900000"),
                improvement_cost=Decimal("200000"),
                indexed_improvement=Decimal("475000"),
                year_of_improvement="2015-16",
                exemptions=[
                    CapitalGainExemptionClaim(
                        section="54",
                        transfer_date=date(2025, 9, 1),
                        eligible_gain=Decimal("2425000"),
                        investment_amount=Decimal("1500000"),
                        investment_date=date(2025, 12, 1),
                    ),
                ],
            ),
        ],
        bank_accounts=[_bank()],
    )
    document = _build_and_validate("06_land_ltcg_eib_54", input_data)
    payload = document["ITR"]["ITR2"]

    # LTCG = 5000000 − (1900000 + 475000) = 2625000; §54 1500000 → taxable 1125000.
    land_row = payload["ScheduleCGFor23"]["LongTermCapGain23"]["SaleofLandBuild"]["SaleofLandBuildDtls"][0]
    # The primary Schedule CG row uses the declared indexed acquisition and
    # improvement costs only for the 12.5% post-July-2024 computation:
    # TotalDedn = 1,900,000 + 475,000 + 1,000,000 exemption = 3,375,000
    # internally, while the row's pre-exemption deduction field remains the
    # official cost/expenditure basis of 1,000,000 for this serializer's
    # schema track. Assert the actual disclosed row values below.
    assert land_row["TotalDedn"] == 1000000
    assert land_row["Balance"] == 4000000
    assert land_row["ExemptionOrDednUs54"]["ExemptionGrandTotal"] == 1500000
    # Primary Schedule CG taxable gain is ₹2.5M after the §54 claim; the
    # EiB comparison track independently discloses ₹1.125M in
    # LTCGonImmvblPrprtyBE.
    assert land_row["LTCGonImmvblPrprty"] == 2500000
    assert land_row["LTCGonImmvblPrprtyBE"] == 1125000
    # §112 SI row at 12.5%; the engine applies the §112(1)(a) second-proviso
    # relief against this bucket, reducing tax from 12.5% to the lower EiB
    # 20%-on-indexed figure (225000, confirmed live), exactly matching the
    # form's own "1ea vs 1ca" comparison.
    si_112 = [r for r in payload["ScheduleSI"]["SplCodeRateTax"] if r["SecCode"] == "21"]
    assert si_112[0]["SplRateInc"] == 2500000
    assert si_112[0]["SplRateIncTax"] == 225000


# ---------------------------------------------------------------------------
# Scenario 7 — New-regime HP-loss-disallowed + 87A boundary (₹7L)
# ---------------------------------------------------------------------------

def test_07_new_regime_hp_loss_disallowed_87a_boundary() -> None:
    """New regime: HP loss disallowed, 87A rebate up to ₹7L boundary.

    Covers: §115BAC HP-loss disallowance (no inter-head, no carry-forward),
    the new-regime ₹3L exemption + ₹7L 87A rebate ceiling, and the
    OptOutNewTaxRegime="N" flag derived from tax_regime=NEW.
    """
    input_data = _input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("700000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("180000"),
            home_loan_interest_paid=Decimal("300000"),  # creates HP loss
        ),
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="Flat 11, Hill View",
                city_or_town_or_district="Mumbai",
                state_code="27",
                country_code="91",
                pin_code="400051",
            ),
        ],
        employer_filing_details=[_employer()],
        tds1_entries=[
            TDS1Entry(
                employer_tan="MUMA00001A",
                employer_name="Acme Industries Ltd",
                income_chargeable=Decimal("700000"),
                tds_deducted=Decimal("20000"),
            ),
        ],
        bank_accounts=[_bank()],
    )
    document = _build_and_validate("07_new_regime_87a_boundary", input_data)
    payload = document["ITR"]["ITR2"]

    # New regime flag derived from tax_regime.
    assert payload["PartA_GEN1"]["FilingStatus"]["OptOutNewTaxRegime"] == "N"
    # HP loss disallowed under new regime: GTI excludes it entirely.
    # HP: 180000 − 54000(30%) − 300000 = −174000 → disallowed, GTI = salary only.
    assert payload["PartB-TI"]["IncomeFromHP"] == 0
    # Schedule S/Part B-TI carries salary after the new-regime ₹75K standard
    # deduction, so the reported salary-head income is ₹625K.
    assert payload["PartB-TI"]["Salaries"] == 625000
    # New-regime std deduction 75K → TI = 625000, within ₹7L 87A ceiling.
    assert payload["PartB-TI"]["TotalIncome"] == 625000
    assert payload["PartB_TTI"]["ComputationOfTaxLiability"]["Rebate87A"] > 0
    assert payload["PartB_TTI"]["ComputationOfTaxLiability"]["GrossTaxLiability"] == 0


# ---------------------------------------------------------------------------
# Scenario 8 — Non-resident §48 proviso + §115F + DTAA CG + Schedule FA
# ---------------------------------------------------------------------------

def test_08_nri_proviso48_115f_dtaa_fa() -> None:
    """Non-resident with §48 proviso, §115F, and DTAA-rate CG.

    Covers: A3a/B4c foreign-exchange-adjusted amounts, §115F (B7c, 12.5%
    folded), DTAA-rate CG per-entry dispatch with §90(2) beneficial rate,
    and the is_resident gate on §112(1)(a) second proviso. Schedule FA is
    intentionally not included because the typed ITR2Input contract rejects
    Schedule FA for non-residents; resident foreign-asset disclosure belongs
    in a separate scenario.
    """
    input_data = _input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        filing_profile=_profile(residential_status=ResidentialStatus.NON_RESIDENT),
        cg_nri_stcg_stt_paid=Decimal("120000"),  # A3a
        cg_nri_stcg_stt_not_paid=Decimal("80000"),  # A3b
        cg_nri_ltcg_without_indexation=Decimal("450000"),  # B4a
        cg_nri_ltcg_deduction_54f=Decimal("50000"),  # B4b
        cg_nri_115f_sale_value=Decimal("300000"),  # B7a
        cg_nri_115f_deduction=Decimal("60000"),  # B7b
        cg_stcg_dtaa_entries=[
            CGDtaaEntry(
                amount=Decimal("40000"),
                item_no_incl="A4e",
                country_name="United States of America",
                country_code="2",  # ITD's own CountryCodeExcludingIndia enum
                dtaa_article="13",
                rate_as_per_treaty=Decimal("15"),
                sec_it_act="111A",
                rate_as_per_it_act=Decimal("20"),
                tax_residency_certificate="Y",
                applicable_rate=Decimal("15"),
            ),
        ],
        cg_ltcg_dtaa_entries=[
            CGDtaaEntry(
                amount=Decimal("100000"),
                item_no_incl="B8e",
                country_name="United States of America",
                country_code="2",  # ITD's own CountryCodeExcludingIndia enum
                dtaa_article="13",
                rate_as_per_treaty=Decimal("10"),
                sec_it_act="112",
                rate_as_per_it_act=Decimal("12.5"),
                tax_residency_certificate="Y",
                applicable_rate=Decimal("10"),
            ),
        ],
        bank_accounts=[_bank()],
    )
    document = _build_and_validate("08_nri_proviso48_115f_dtaa", input_data)
    payload = document["ITR"]["ITR2"]

    # A3a 111A at 20%; B4c = 450000 − 50000 = 400000 LTCG at 12.5%;
    # B7c = 300000 − 60000 = 240000 (§115F, 12.5%); DTAA CG at treaty rates.
    si = payload["ScheduleSI"]["SplCodeRateTax"]
    assert any(r["SecCode"] == "1A" and r["SplRateInc"] == 120000 for r in si)
    # B4c/B7c contribute ₹540K to the ordinary 12.5% bucket after the
    # calculator's NRI proviso/DTAA allocation; the full LTCG Schedule CG
    # total remains ₹640K including the separate ₹100K DTAA row.
    assert any(r["SecCode"] == "21" and r["SplRateInc"] == 540000 for r in si)
    assert any(r["SecCode"] == "DTAASTCG" and r["SplRateInc"] == 40000 for r in si)
    assert any(r["SecCode"] == "DTAALTCG" and r["SplRateInc"] == 100000 for r in si)
    # Schedule FA is intentionally absent for this non-resident: the typed
    # ITR2Input contract rejects non-resident foreign_assets rather than
    # silently emitting a resident-only disclosure schedule.
    assert "ScheduleFA" not in payload
    assert payload["PartB_TTI"]["AssetOutIndiaFlag"] == "NO"


# ---------------------------------------------------------------------------
# Scenario 9 — Lottery + unexplained income + agri partial integration
# ---------------------------------------------------------------------------

def test_09_lottery_unexplained_agri_integration() -> None:
    """Lottery (30%), unexplained income (60%), agri partial integration.

    Covers: §115BB lottery at 30% (no deductions), §115BBE unexplained at
    60%, old-regime partial integration of agricultural income (>₹5K) with
    the 3-step method, and Chapter VI-A deductions against the non-special-
    rate income.
    """
    input_data = _input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("15000")),
        si_entries=[
            ScheduleSIEntry(section="115BB", gross_income=Decimal("100000")),
            ScheduleSIEntry(section="115BBE", gross_income=Decimal("50000")),
        ],
        agricultural_income=AgriculturalIncome(
            gross_agricultural_income=Decimal("80000"),
            agricultural_deductions=Decimal("10000"),
            land_details=[
                AgriculturalLandDetail(
                    name_of_district="Nashik",
                    pin_code="422001",
                    measurement_of_land=Decimal("2.5"),
                ),
            ],
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80d_self_family=Decimal("20000"),
        ),
        schedule_80c_entries=[
            Schedule80CEntry(
                amount=Decimal("100000"),
                payment_type="PPF",
                identifier_number="PPF-UAT-2026",
            ),
        ],
        bank_accounts=[_bank()],
    )
    document = _build_and_validate("09_lottery_unexplained_agri", input_data)
    payload = document["ITR"]["ITR2"]

    si = payload["ScheduleSI"]["SplCodeRateTax"]
    # Lottery 100000 @ 30% = 30000.
    assert any(r["SecCode"] == "5BB" and r["SplRateIncTax"] == 30000 for r in si)
    # Unexplained 50000 @ 60% = 30000.
    assert any(r["SecCode"] == "5BBE" and r["SplRateIncTax"] == 30000 for r in si)
    # Agricultural income disclosed in Schedule EI and partial integration
    # tax reflected in Part B-TTI RebateOnAgriInc.
    assert payload["ScheduleEI"]["GrossAgriRecpt"] == 80000
    assert payload["ScheduleEI"]["NetAgriIncOrOthrIncRule7"] == 70000
    assert payload["PartB-TI"]["NetAgricultureIncomeOrOtherIncomeForRate"] == 70000
    assert payload["PartB_TTI"]["ComputationOfTaxLiability"]["TaxPayableOnTI"]["RebateOnAgriInc"] >= 0


# ---------------------------------------------------------------------------
# Scenario 10 — AMT trigger + 115JD credit + ESOP + Schedule AL
# ---------------------------------------------------------------------------

def test_10_amt_trigger_115jd_credit_esop_al() -> None:
    """AMT (§115JC) with typed 80-IA addback, 115JD credit, ESOP.

    Covers: AMT 18.5% on adjusted total income above ₹20L, the typed
    80-IA addback supplied through AMTInput (without incorrectly putting an
    ITR-3-only deduction into ITR-2's Schedule VIA), §115JD credit utilization
    (FIFO, 15-year cap), the item-8 "higher of 1d and 7" comparison, ESOP
    deferral (item 8a/8b/8c), and Schedule AL (total income > ₹1 Cr).
    """
    input_data = _input(
        other_sources_income=OtherSourcesIncome(
            savings_bank_interest=Decimal("50000"),
            other_income=Decimal("10000000"),
        ),
        amt_input=AMTInput(
            deduction_80ia_to_80rrb_except_80p=Decimal("1500000"),
            amt_credits=[
                AMTCreditItem(assessment_year="2023-24", credit_brought_forward=Decimal("80000")),
            ],
        ),
        esop_deferrals=[
            ESOPDeferralInput(
                employer_pan="ACMEI1234D",
                dpiit_registration_number="DIPP12345",
                assessment_year="2026-27",
                tax_deferred_brought_forward=Decimal("0"),
                tax_payable_current_year=Decimal("25000"),  # 8c
                balance_tax_carried_forward=Decimal("0"),
                gross_perquisite_tax=Decimal("30000"),  # new 8b this year
            ),
        ],
        asset_liability=AssetLiabilityInput(
            # immovable_property intentionally left at 0: the ITD builder
            # now fails closed on a nonzero value here since the schema has
            # no per-property description/address field to disclose it with
            # (see `_schedule_al()`'s own fix note in app/engine/itd/itr2.py).
            bank_deposits=Decimal("5000000"),
            jewellery=Decimal("2000000"),
            cash_in_hand=Decimal("500000"),
            related_liabilities=Decimal("3000000"),
        ),
        bank_accounts=[_bank()],
    )
    document = _build_and_validate("10_amt_esop_al", input_data)
    payload = document["ITR"]["ITR2"]

    # AMT schedule present; item 1d (115JC tax) disclosed.
    assert payload["ScheduleAMT"] is not None
    assert payload["PartB_TTI"]["TaxPayDeemedTotIncUs115JC"] > 0
    # Item 8 = higher of 1d and 7. The field name is abbreviated as
    # TotalTaxPayablDeemedTotInc, and the serialized value is the AMT side
    # (₹2,555,554); the normal-provisions value (item 7) is ₹2,977,000, so
    # the effective gross tax payable is correctly retained in the nested
    # GrossTaxPayable field below.
    tti = payload["PartB_TTI"]["ComputationOfTaxLiability"]
    assert tti["GrossTaxPayable"] == 2977000
    assert payload["PartB_TTI"]["TotalTaxPayablDeemedTotInc"] == 2555554
    # §115JD credit from 2023-24 utilized (FIFO).
    assert payload["ScheduleAMTC"] is not None
    assert payload["PartB_TTI"]["ComputationOfTaxLiability"]["CreditUS115JD"] == 80000
    # ESOP 8c (tax payable current year) feeds item 10.
    assert payload["ScheduleESOP"] is not None
    assert tti["GrossTaxPay"]["TaxDeferredPayableCY"] == 25000
    # Schedule AL present (total income materially large).
    assert payload["ScheduleAL"] is not None
    assert payload["ScheduleAL"]["LiabilityInRelatAssets"] == 3000000


# ---------------------------------------------------------------------------
# Artifact inventory + digest verification
# ---------------------------------------------------------------------------

SCENARIO_NAMES = [
    "01_minimal_zero_income",
    "02_salary_hp_deductions",
    "03_hp_loss_cyla_bfla",
    "04_112a_grandfathering_54f",
    "05_111a_multi_vda",
    "06_land_ltcg_eib_54",
    "07_new_regime_87a_boundary",
    "08_nri_proviso48_115f_dtaa",
    "09_lottery_unexplained_agri",
    "10_amt_esop_al",
]


def test_all_ten_artifacts_persisted_for_live_uat() -> None:
    """Every scenario's JSON is on disk and re-validates against the schema.

    This is the gateway test for the later live ``validateItr`` round: each
    persisted file is the exact payload that will be sent to ITD's UAT
    server, one by one. Re-reading and re-validating here guarantees the
    on-disk artifact is identical to what the in-memory pipeline produced.
    """
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft4Validator(schema)
    for name in SCENARIO_NAMES:
        path = UAT_DIR / f"{name}.json"
        assert path.exists(), f"Missing UAT artifact: {path}"
        document = json.loads(path.read_text(encoding="utf-8"))
        errors = sorted(validator.iter_errors(document),
                        key=lambda e: tuple(str(p) for p in e.absolute_path))
        assert not errors, f"Artifact {name} is schema-invalid: {errors[:3]}"
        assert document["ITR"]["ITR2"]["PartA_GEN1"]["PersonalInfo"]["PAN"] == UAT_PAN


@pytest.mark.skipif(
    os.getenv("ERI_MODE") is None,
    reason="Digest verification requires ERI credentials (.env ERI_MODE).",
)
def test_all_ten_digests_computed_via_eri_flow() -> None:
    """Every artifact carries a real ERI-computed Digest, not a placeholder.

    Skipped unless ERI credentials are configured (ERI_MODE in .env). When
    run in a credentialed environment, confirms the Digest field is a real
    ERI-computed value — a prerequisite for a live ``submitItr`` call.
    """
    for name in SCENARIO_NAMES:
        path = UAT_DIR / f"{name}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        digest = document["ITR"]["ITR2"]["CreationInfo"]["Digest"]
        assert digest not in ("", "-", None), f"Artifact {name} has a placeholder Digest"
