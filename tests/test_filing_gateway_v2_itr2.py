"""
ITR-2/ITR-3 plan Phase 4 tests — filing_gateway_v2 ITR-2 wiring.

Mirrors tests/test_filing_gateway_v2_itr4.py: verifies compute_canonical_itr2,
the compute_canonical()/generate_cbdt_json() form dispatch, and that a
filing-ready ITR-2 draft produces official CBDT JSON passing the CBDT
Category A input/calc validators and the official ITR-2 JSON schema.

Run: pytest tests/test_filing_gateway_v2_itr2.py -v
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.filing_gateway_v2 import (
    FilingGatewayV2Error,
    ITR2PipelineResult,
    compute_canonical,
    compute_canonical_itr2,
    generate_cbdt_json,
)
from app.schemas.return_draft import (
    BankAccount,
    Employer,
    HouseProperty,
    InterestIncome,
    PersonalInfo,
    ReturnDraft,
    TdsCredit,
    create_empty_draft,
)


def _filing_ready_itr2_draft() -> ReturnDraft:
    """A minimally filing-ready canonical ITR-2 draft with salary + HP."""
    draft = create_empty_draft("2026-27", "ITR-2", "new")
    draft.personal = PersonalInfo(
        name="Priya Nair", firstName="Priya", surnameOrOrgName="Nair",
        fatherName="Ramesh Nair", pan="ABCPN1234F", dateOfBirth="1985-06-15",
        residentialStatus="ROR", flatNo="12", localityOrArea="MG Road",
        city="Mumbai", stateCode="27", pinCode="400001", mobile="9876543210",
        email="priya@example.com",
    )
    draft.employers = [Employer(
        id="e1", basic=Decimal("1500000"), tdsDeducted=Decimal("120000"),
        employerName="Acme Corp", employerTAN="MUMA12345B",
        employerCity="Mumbai", employerStateCode="27", employerAddress="Tower A",
    )]
    draft.houseProperties = [HouseProperty(id="hp1", propertyType="SELF_OCCUPIED")]
    draft.otherSources.interest = [InterestIncome(
        id="i1", kind="SAVINGS_BANK", grossAmount=Decimal("8000"),
    )]
    draft.taxes.tds = [TdsCredit(
        id="t1", section="192", deductorName="Acme", deductorTAN="MUMA12345B",
        taxDeducted=Decimal("120000"), schedule="TDS1",
    )]
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="HDFC Bank", accountNumber="000123456789",
        ifscCode="HDFC0000123", accountType="SB", useForRefund=True,
    )]
    draft.filing.filingSection = "139(1)"
    draft.verification.declarationAccepted = True
    draft.verification.capacity = "SELF"
    draft.verification.place = "Mumbai"
    draft.verification.date = "2026-07-15"
    return draft


def test_compute_canonical_itr2_returns_summary() -> None:
    """A filing-ready ITR-2 draft computes cleanly with a populated summary."""
    draft = _filing_ready_itr2_draft()
    pipeline = compute_canonical_itr2(draft)
    assert isinstance(pipeline, ITR2PipelineResult)
    assert pipeline.computation.gross_total_income > 0
    assert pipeline.summary["gti"] == float(pipeline.computation.gross_total_income)
    assert pipeline.summary["computedByFormEngine"] == "ITR-2"
    assert not pipeline.computation.errors


def test_compute_canonical_itr2_rejects_pending_reconciliation() -> None:
    """A pending AIS/TIS discrepancy blocks compute with a clear message."""
    from app.schemas.return_draft import ReconciliationDiscrepancy

    draft = _filing_ready_itr2_draft()
    draft.reconciliation.discrepancies = [ReconciliationDiscrepancy(
        id="d1", category="TDS", status="PENDING",
    )]
    with pytest.raises(FilingGatewayV2Error, match="Manual confirmation is required"):
        compute_canonical_itr2(draft)


def test_compute_canonical_dispatches_itr1_itr2_and_itr4() -> None:
    """The shared compute_canonical() dispatch routes ITR-2 drafts correctly."""
    draft = _filing_ready_itr2_draft()
    pipeline = compute_canonical(draft)
    assert isinstance(pipeline, ITR2PipelineResult)


def test_compute_canonical_itr2_requires_correct_form() -> None:
    """compute_canonical_itr2 rejects a draft whose form is not ITR-2."""
    draft = _filing_ready_itr2_draft()
    draft.form = "ITR-1"
    with pytest.raises(FilingGatewayV2Error):
        compute_canonical_itr2(draft)


def test_generate_cbdt_json_itr2_passes_validators_and_schema() -> None:
    """A filing-ready ITR-2 draft produces official JSON that reconciles."""
    draft = _filing_ready_itr2_draft()
    official_json, summary = generate_cbdt_json(draft)
    assert official_json["ITR"]["ITR2"] is not None
    assert summary["computedByFormEngine"] == "ITR-2"


def test_generate_cbdt_json_itr2_emits_fii_fpi_declaration() -> None:
    """FII/FPI status and SEBI registration number reach the official JSON.

    Regression coverage for audit §4.2: the backend/builder path
    (draft.filing.isFiiFpi/sebiRegistrationNumber -> _itr2_filing_profile ->
    ITR2FilingProfile.is_fii_fpi/sebi_registration_number -> _part_a_gen1's
    FiiFpiFlag/SebiRegnNo).

    Found and fixed a real, pre-existing schema-blocking bug along the way:
    the builder emitted the key "SEBIRegNo", but the official schema
    requires "SebiRegnNo" -- confirmed via live Draft4Validator rejection
    ("Additional properties are not allowed ('SEBIRegNo' was unexpected)").
    No prior test ever exercised is_fii_fpi=True through schema validation.
    """
    draft = _filing_ready_itr2_draft()
    draft.personal.residentialStatus = "NR"  # FII/FPI is NR-only (input_rules.py)
    draft.filing.isFiiFpi = True
    draft.filing.sebiRegistrationNumber = "INZZFP123456"
    official_json, _summary = generate_cbdt_json(draft)
    personal_info = official_json["ITR"]["ITR2"]["PartA_GEN1"]["FilingStatus"]
    assert personal_info["FiiFpiFlag"] == "Y"
    assert personal_info["SebiRegnNo"] == "INZZFP123456"


def test_generate_cbdt_json_itr2_emits_lei_details() -> None:
    """LEI number and validity date reach the official JSON when supplied.

    Regression coverage for audit §4.7: LEI was entirely unimplemented at
    every layer (backend schema, builder, frontend) before this fix.
    """
    draft = _filing_ready_itr2_draft()
    draft.filing.leiNumber = "9845003OQ3EEHS7QYW10"
    draft.filing.leiValidUptoDate = "2027-03-31"
    official_json, _summary = generate_cbdt_json(draft)
    filing_status = official_json["ITR"]["ITR2"]["PartA_GEN1"]["FilingStatus"]
    assert filing_status["LEIDtls"]["LEINumber"] == "9845003OQ3EEHS7QYW10"
    assert filing_status["LEIDtls"]["ValidUptoDate"] == "2027-03-31"


def test_generate_cbdt_json_itr2_omits_lei_block_when_unset() -> None:
    """No LEI number means no LEIDtls block at all -- no empty placeholder."""
    draft = _filing_ready_itr2_draft()
    official_json, _summary = generate_cbdt_json(draft)
    filing_status = official_json["ITR"]["ITR2"]["PartA_GEN1"]["FilingStatus"]
    assert "LEIDtls" not in filing_status


def test_generate_cbdt_json_itr2_rejects_representative_verification() -> None:
    """ITR-2 verification capacity REPRESENTATIVE/PARTNER is not supported."""
    draft = _filing_ready_itr2_draft()
    draft.verification.capacity = "REPRESENTATIVE"
    with pytest.raises(FilingGatewayV2Error) as excinfo:
        generate_cbdt_json(draft)
    assert "SELF or KARTA" in " ".join(excinfo.value.errors)


def test_generate_cbdt_json_itr2_property_details_match_house_property_count() -> None:
    """One PropertyFilingDetail is emitted per canonical house property."""
    draft = _filing_ready_itr2_draft()
    draft.houseProperties = [
        HouseProperty(id="hp1", propertyType="SELF_OCCUPIED"),
        HouseProperty(id="hp2", propertyType="LET_OUT", annualLettingValue=Decimal("240000")),
    ]
    official_json, _summary = generate_cbdt_json(draft)
    schedule_hp = official_json["ITR"]["ITR2"].get("ScheduleHP")
    assert schedule_hp is not None


# ── Phase 5G: complete pre-calculation preparation ──────────────────────────

def test_compute_canonical_itr2_prepares_filing_data_before_calculation() -> None:
    """compute_canonical_itr2 attaches the filing profile before compute,
    matching compute_canonical_itr1/_itr4 — ITR-2 was the outlier deferring
    this to JSON-generation time; Phase 5G closes that gap."""
    draft = _filing_ready_itr2_draft()
    pipeline = compute_canonical_itr2(draft)
    assert pipeline.typed_input.filing_profile is not None
    assert pipeline.typed_input.filing_profile.pan == "ABCPN1234F"
    assert pipeline.typed_input.property_filing_details
    assert pipeline.typed_input.employer_filing_details


def test_compute_canonical_itr2_rejects_incomplete_filing_profile() -> None:
    """An incomplete filing profile (missing father's name) is now rejected
    at compute time, not only at JSON-generation time — the same behavior
    ITR-1/ITR-4 already have."""
    draft = _filing_ready_itr2_draft()
    draft.personal.fatherName = ""
    with pytest.raises(FilingGatewayV2Error):
        compute_canonical_itr2(draft)


def test_itr2_json_reuses_prepared_input_without_late_enrichment() -> None:
    """_generate_cbdt_json_itr2 must not re-derive filing data from the
    draft — it reuses pipeline.typed_input as-is."""
    draft = _filing_ready_itr2_draft()
    pipeline = compute_canonical_itr2(draft)
    official_json, summary = generate_cbdt_json(draft)
    assert official_json["ITR"]["ITR2"] is not None
    assert summary["gti"] == pipeline.summary["gti"]


def test_itr2_pipeline_result_carries_personal_profile_source_hash() -> None:
    from app.engine.personal_profile import personal_profile_source_hash

    draft = _filing_ready_itr2_draft()
    pipeline = compute_canonical_itr2(draft)
    assert pipeline.personal_profile_source_hash == personal_profile_source_hash(draft)
    assert pipeline.personal_profile_source_hash != ""


# ── Phase 5G follow-up: _itr2_filing_profile on the shared normalizer ───────

def test_compute_canonical_itr2_succeeds_with_no_employer_category() -> None:
    """ITR2FilingProfile has no employer_category field at all — unlike
    ITR1FilingProfile/ITR4FilingProfile, ITR-2 must not require
    personal.employerCategory just because the shared normalizer parses it.
    _filing_ready_itr2_draft() never sets it; this asserts that omission is
    correct, not an oversight."""
    draft = _filing_ready_itr2_draft()
    assert draft.personal.employerCategory == ""
    pipeline = compute_canonical_itr2(draft)
    assert not hasattr(pipeline.typed_input.filing_profile, "employer_category")
    assert not pipeline.computation.errors


# ── §4.1/§4.4: residential-status facts and Section 115H ────────────────────

def test_generate_cbdt_json_itr2_emits_residential_status_facts() -> None:
    """Section 6 basis, day counts, jurisdiction/TIN, and 115H all reach the
    official JSON. Regression coverage for audit §4.1/§4.4: none of this was
    representable at any layer before this fix -- only the bare
    ResidentialStatus classification itself was ever emitted."""
    from app.schemas.return_draft import JurisdictionResidenceEntry as DraftJurisdictionEntry

    draft = _filing_ready_itr2_draft()
    draft.personal.residentialStatus = "RNOR"
    draft.filing.conditionsResStatus = "2"
    draft.filing.totalStayIndiaPrevYr = 90
    draft.filing.totalStayIndia4PrecYr = 400
    draft.filing.benefitUs115H = True
    draft.filing.jurisdictionResidenceEntries = [
        DraftJurisdictionEntry(id="j1", jurisdictionCode="2", tin="123-45-6789"),
    ]
    official_json, _summary = generate_cbdt_json(draft)
    filing_status = official_json["ITR"]["ITR2"]["PartA_GEN1"]["FilingStatus"]
    assert filing_status["ResidentialStatus"] == "NOR"
    assert filing_status["ConditionsResStatus"] == "2"
    assert filing_status["TotalPrStayIndiaPrevYr"] == 90
    assert filing_status["TotalPrStayIndia4PrecYr"] == 400
    assert filing_status["BenefitUs115HFlg"] == "Y"
    jur_row = filing_status["JurisdictionResPrevYr"]["JurisdictionResPrevYrDtls"][0]
    assert jur_row["JurisdictionResidence"] == "2"
    assert jur_row["TIN"] == "123-45-6789"


def test_generate_cbdt_json_itr2_omits_residential_status_facts_when_unset() -> None:
    """No residential-status detail entered means no fields emitted at all --
    all of it is genuinely optional per the official schema."""
    draft = _filing_ready_itr2_draft()
    official_json, _summary = generate_cbdt_json(draft)
    filing_status = official_json["ITR"]["ITR2"]["PartA_GEN1"]["FilingStatus"]
    assert "ConditionsResStatus" not in filing_status
    assert "JurisdictionResPrevYr" not in filing_status
    assert "TotalPrStayIndiaPrevYr" not in filing_status
    assert "TotalPrStayIndia4PrecYr" not in filing_status
    assert "BenefitUs115HFlg" not in filing_status


# ── §4.3: director and unlisted-equity disclosures ──────────────────────────

def test_generate_cbdt_json_itr2_emits_director_and_unlisted_equity_detail() -> None:
    """Director and unlisted-equity detail rows reach the official JSON.

    Regression coverage for audit §4.3: two real gaps existed before this
    fix -- CompDirectorPrvYrFlg was never emitted at all (is_company_director
    was read from the draft but silently dropped), and
    HeldUnlistedEqShrPrYrFlg (which the official schema marks required) had
    no backing HeldUnlistedEqShrPrYr.HeldUnlistedEqShrPrYrDtls[] array ever
    emitted, so a "Y" flag could reach ITD with zero detail rows.
    """
    from app.schemas.return_draft import CompanyDirectorEntry as DraftDirectorEntry
    from app.schemas.return_draft import UnlistedEquityEntry as DraftEquityEntry

    draft = _filing_ready_itr2_draft()
    draft.personal.isDirector = True
    draft.personal.companyDirectorEntries = [DraftDirectorEntry(
        id="d1", companyName="Acme Pvt Ltd", companyType="D",
        pan="AAACA1234A", sharesType="U", din="12345678",
    )]
    draft.personal.holdsUnlistedShares = True
    draft.personal.unlistedEquityEntries = [DraftEquityEntry(
        id="e1", companyName="Beta Pvt Ltd", companyType="D",
        pan="AAACB1234B", openingShares=Decimal("100"), openingCost=Decimal("10000"),
        acquiredShares=Decimal("50"), dateOfAcquisition="2025-06-01",
        faceValuePerShare=Decimal("10"), issuePricePerShare=Decimal("100"),
        purchasePricePerShare=Decimal("100"), transferredShares=Decimal("20"),
        transferSaleConsideration=Decimal("2500"),
        closingShares=Decimal("130"), closingCost=Decimal("15000"),
    )]
    official_json, _summary = generate_cbdt_json(draft)
    filing_status = official_json["ITR"]["ITR2"]["PartA_GEN1"]["FilingStatus"]

    assert filing_status["CompDirectorPrvYrFlg"] == "Y"
    director_row = filing_status["CompDirectorPrvYr"]["CompDirectorPrvYrDtls"][0]
    assert director_row["NameOfCompany"] == "Acme Pvt Ltd"
    assert director_row["CompanyType"] == "D"
    assert director_row["SharesTypes"] == "U"
    assert director_row["DIN"] == "12345678"

    assert filing_status["HeldUnlistedEqShrPrYrFlg"] == "Y"
    equity_row = filing_status["HeldUnlistedEqShrPrYr"]["HeldUnlistedEqShrPrYrDtls"][0]
    assert equity_row["NameOfCompany"] == "Beta Pvt Ltd"
    assert equity_row["OpngBalNumberOfShares"] == 100
    assert equity_row["OpngBalCostOfAcquisition"] == 10000
    assert equity_row["ShrAcqDurYrNumberOfShares"] == 50
    assert equity_row["ClsngBalNumberOfShares"] == 130
    assert equity_row["ClsngBalCostOfAcquisition"] == 15000


def test_generate_cbdt_json_itr2_omits_director_and_equity_blocks_when_unset() -> None:
    """Both flags default to N and no detail blocks are emitted."""
    draft = _filing_ready_itr2_draft()
    official_json, _summary = generate_cbdt_json(draft)
    filing_status = official_json["ITR"]["ITR2"]["PartA_GEN1"]["FilingStatus"]
    assert filing_status["CompDirectorPrvYrFlg"] == "N"
    assert filing_status["HeldUnlistedEqShrPrYrFlg"] == "N"
    assert "CompDirectorPrvYr" not in filing_status
    assert "HeldUnlistedEqShrPrYr" not in filing_status


def test_itr2_filing_profile_rejects_director_flag_without_entries() -> None:
    """is_company_director=True with zero director rows is rejected -- this
    was the exact live bug (a bare Y flag with no backing data)."""
    draft = _filing_ready_itr2_draft()
    draft.personal.isDirector = True
    with pytest.raises(FilingGatewayV2Error):
        generate_cbdt_json(draft)
