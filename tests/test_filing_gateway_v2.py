"""Tests for the Phase 2 canonical filing gateway."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

import app.engine.filing_gateway_v2 as gateway
from app.schemas.return_draft import (
    AlternateAddress,
    BankAccount,
    Category80D,
    CoOwner,
    Employer,
    HouseProperty,
    InterestIncome,
    OtherIncomeEntry,
    PensionContribution80CCC,
    Policy80D,
    ReconciliationDiscrepancy,
    ReconciliationEvidence,
    ReturnDraft,
    RepresentativeAssessee,
    Schedule80GGCEntry,
    SeventhProvisoClause,
    TenantDetail,
    create_empty_draft,
)


def _filing_ready_draft() -> ReturnDraft:
    """Create a minimally filing-ready canonical ITR-1 draft."""
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    draft.personal.name = "Rahul Sharma"
    draft.personal.firstName = "Rahul"
    draft.personal.surnameOrOrgName = "Sharma"
    draft.personal.fatherName = "Mohan Sharma"
    draft.personal.pan = "ABCDE1234F"
    draft.personal.email = "rahul@example.com"
    draft.personal.mobile = "9876543210"
    draft.personal.dateOfBirth = "1990-01-15"
    draft.personal.flatNo = "12A"
    draft.personal.localityOrArea = "Central Delhi"
    draft.personal.city = "Delhi"
    draft.personal.stateCode = "07"
    draft.personal.countryCode = "91"
    draft.personal.pinCode = "110001"
    draft.personal.employerCategory = "OTH"
    draft.verification.place = "Delhi"
    # A return filed under 139(1) declares a filing date on or before the due
    # date; without one the fixture is judged against the day the suite runs.
    draft.verification.date = "2026-07-31"
    draft.verification.declarationAccepted = True
    draft.employers = [Employer(id="e1", basic=Decimal("800000"))]
    draft.bankAccounts = [BankAccount(
        id="b1",
        bankName="State Bank of India",
        accountNumber="1234567890",
        ifscCode="SBIN0001234",
        accountType="SB",
        useForRefund=True,
    )]
    return draft


def test_itr1_rejects_itr4_only_verification_capacity() -> None:
    """ITR-1 must not silently map Karta or Partner verification to Self."""
    draft = _filing_ready_draft()
    draft.verification.capacity = "KARTA"

    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.generate_cbdt_json(draft)

    assert caught.value.message == "ITR-1 verification capacity is invalid."


def test_generate_reuses_one_computation_for_summary_and_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generation calls compute_itr1 exactly once and reuses its result."""
    draft = _filing_ready_draft()
    real_compute = gateway.compute_itr1
    calls = 0
    seen: dict[str, Any] = {}

    def spy_compute(typed_input: Any) -> Any:
        nonlocal calls
        calls += 1
        return real_compute(typed_input)

    def fake_build(result: Any, typed_input: Any) -> dict[str, Any]:
        seen["result"] = result
        seen["typed_input"] = typed_input
        return {"ITR": {"ITR1": {"ok": True}}}

    monkeypatch.setattr(gateway, "compute_itr1", spy_compute)
    monkeypatch.setattr(gateway, "build_itr1_json", fake_build)
    monkeypatch.setattr(gateway, "validate_itr1_json", lambda document: None)

    official, summary = gateway.generate_cbdt_json(draft)
    assert calls == 1
    assert official["ITR"]["ITR1"]["ok"] is True
    assert summary["grossTotalIncome"] == float(seen["result"].gross_total_income)
    assert seen["typed_input"].filing_profile.pan == "ABCDE1234F"
    assert seen["typed_input"].property_profile.address_detail == "12A"


def test_generation_produces_official_schema_valid_json() -> None:
    """A filing-ready canonical draft passes the real official validator."""
    official, summary = gateway.generate_cbdt_json(_filing_ready_draft())
    gateway.validate_itr1_json(official)
    assert "ITR" in official
    assert summary["computedByFormEngine"] == "ITR-1"


def test_itr1_emits_exact_refund_verification_and_creation_metadata() -> None:
    """Filing identity, bank data, and system metadata reach exact JSON paths."""
    draft = _filing_ready_draft()
    official, summary = gateway.generate_cbdt_json(draft)
    itr1 = official["ITR"]["ITR1"]

    assert itr1["Refund"] == {
        "RefundDue": round(summary["refundDue"] / 10) * 10,
        "BankAccountDtls": {
            "AddtnlBankDetails": [{
                "IFSCCode": "SBIN0001234",
                "BankName": "State Bank of India",
                "BankAccountNo": "1234567890",
                "AccountType": "SB",
                "UseForRefund": "true",
            }],
        },
    }
    assert itr1["Verification"] == {
        "Declaration": {
            "AssesseeVerName": "Rahul Sharma",
            "FatherName": "Mohan Sharma",
            "AssesseeVerPAN": "ABCDE1234F",
        },
        "Capacity": "S",
        "Place": "Delhi",
    }
    assert itr1["CreationInfo"]["SWVersionNo"] == "1.0"
    assert itr1["CreationInfo"]["SWCreatedBy"].startswith("SW")
    assert itr1["CreationInfo"]["JSONCreatedBy"] == itr1["CreationInfo"]["SWCreatedBy"]
    assert len(itr1["CreationInfo"]["JSONCreationDate"]) == 10
    assert itr1["CreationInfo"]["IntermediaryCity"] == "Akola"
    assert itr1["CreationInfo"]["Digest"] == "-" or len(itr1["CreationInfo"]["Digest"]) == 44


def test_generation_emits_canonical_property_ownership_and_tenants() -> None:
    """Canonical ITR-1 property identities survive into exact official rows."""
    draft = _filing_ready_draft()
    draft.houseProperties = [HouseProperty(
        id="hp-1",
        propertyType="LET_OUT",
        address="18 Market Road",
        city="Delhi",
        state="07",
        pinCode="110001",
        propertyOwnerType="OT",
        propertyOwnerOther="Estate",
        isCoOwned=True,
        ownershipType="JOINT",
        ownershipShare=Decimal("70"),
        coOwners=[CoOwner(
            coOwnerSNo=9,
            name="Priya Sharma",
            pan="PQRSX1234Y",
            aadhaar="123456789012",
            share=Decimal("30"),
        )],
        tenantDetails=[TenantDetail(
            tenantSNo=8,
            name="Tenant One",
            pan="LMNOP1234Q",
            aadhaar="234567890123",
            panOrTan="DELA12345B",
        )],
        annualRent=Decimal("300000"),
        unrealizedRent=Decimal("20000"),
        municipalTaxesPaid=Decimal("10000"),
    )]

    official, summary = gateway.generate_cbdt_json(draft)
    gateway.validate_itr1_json(official)
    prop = official["ITR"]["ITR1"]["ITR1_IncomeDeductions"]["PropertyDetails"][0]
    assert prop["PropertyOwnerOther"] == "Estate"
    assert prop["PropCoOwnedFlg"] == "YES"
    assert prop["AsseseeShareProperty"] == 70
    assert prop["CoOwners"][0] == {
        "CoOwnersSNo": 1,
        "NameCoOwner": "Priya Sharma",
        "PAN_CoOwner": "PQRSX1234Y",
        "Aadhaar_CoOwner": "123456789012",
        "PercentShareProperty": 30,
    }
    assert prop["TenantDetails"][0]["TenantSNo"] == 1
    assert prop["TenantDetails"][0]["PANTANofTenant"] == "DELA12345B"
    assert prop["Rentdetails"] == {
        "AnnualLetableValue": 300000,
        "RentNotRealized": 20000,
        "LocalTaxes": 10000,
        "TotalUnrealizedAndTax": 30000,
        "BalanceALV": 270000,
        "AnnualOfPropOwned": 189000,
        "ThirtyPercentOfBalance": 56700,
        "IntOnBorwCap": 0,
        "TotalDeduct": 56700,
        "IncomeOfHP": 132300,
    }
    assert summary["housePropertyDetails"] == [{
        "propertySequenceNo": 1,
        "annualLettableValue": 300000.0,
        "rentNotRealized": 20000.0,
        "localTaxes": 10000.0,
        "totalUnrealizedAndTax": 30000.0,
        "balanceALV": 270000.0,
        "annualOfPropOwned": 189000.0,
        "thirtyPercentOfBalance": 56700.0,
        "interestOnBorrowedCapital": 0.0,
        "totalDeduction": 56700.0,
        "arrearsUnrealizedRentReceived": 0.0,
        "incomeOfHP": 132300.0,
    }]


def test_generation_emits_exact_compact_other_source_rows() -> None:
    """Official categories and OTH descriptions survive canonical generation."""
    draft = _filing_ready_draft()
    draft.otherSources.interest = [
        InterestIncome(id="tax", kind="IT_REFUND", grossAmount=Decimal("300")),
        InterestIncome(id="pf", kind="PF_10_11_FIRST", grossAmount=Decimal("400")),
    ]
    draft.otherSources.otherIncome = [OtherIncomeEntry(
        id="other", nature="OTHER",
        description="Consulting honorarium", amount=Decimal("600"),
    )]

    official, _ = gateway.generate_cbdt_json(draft)
    gateway.validate_itr1_json(official)
    rows = official["ITR"]["ITR1"]["ITR1_IncomeDeductions"]["OthersInc"][
        "OthersIncDtlsOthSrc"
    ]
    assert rows == [
        {"OthSrcNatureDesc": "TAX", "OthSrcOthAmount": 300},
        {"OthSrcNatureDesc": "10(11)(iP)", "OthSrcOthAmount": 400},
        {
            "OthSrcNatureDesc": "OTH",
            "OthSrcOthAmount": 600,
            "OthSrcOthNatOfInc": "Consulting honorarium",
        },
    ]


def test_generation_emits_conditional_80ccc_and_80d_evidence() -> None:
    """Canonical detail rows survive through official JSON and schema validation."""
    draft = _filing_ready_draft()
    draft.regime = "old"
    draft.personal.dateOfBirth = "1955-01-15"
    draft.employers[0].natureOfEmployment = "OTH"
    draft.deductions.pensionContribution80CCC = [PensionContribution80CCC(
        id="ccc-1",
        identifierType="PRAN",
        identifierName="PRAN123456",
        amount=Decimal("10000"),
    )]
    draft.deductions.chapterVIA.section80CCC = Decimal("10000")
    draft.deductions.section80D.selfSeniorCitizen = "Y"
    draft.deductions.section80D.selfFamilySenior = Category80D(
        policies=[Policy80D(
            id="policy-1",
            insurerName="Health Insurer",
            policyNo="POLICY123",
            premiumAmount=Decimal("10000"),
        )],
        medicalExpense=Decimal("20000"),
    )
    draft.deductions.chapterVIA.section80D = Decimal("30000")

    official, _ = gateway.generate_cbdt_json(draft)
    gateway.validate_itr1_json(official)
    itr1 = official["ITR"]["ITR1"]
    assert itr1["ITR1_IncomeDeductions"]["UsrDeductUndChapVIA"][
        "PensionContribution80CCC"
    ][0]["NameofIdentifier"] == "PRAN123456"
    assert itr1["Schedule80D"]["Sec80DSelfFamSrCtznHealth"][
        "MedicalExpSlfFamSrCtzn"
    ] == 20000


def test_generation_requires_canonical_filing_fields() -> None:
    """Missing official profile data is rejected with actionable details."""
    draft = create_empty_draft("2026-27")
    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.generate_cbdt_json(draft)
    assert "required" in " ".join(caught.value.errors).lower()


def test_generation_requires_explicit_personal_employer_category() -> None:
    """Mandatory CBDT EmployerCategory must not silently fall back to OTH."""
    draft = _filing_ready_draft()
    draft.personal.employerCategory = ""
    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.generate_cbdt_json(draft)
    assert "personal.employerCategory" in " ".join(caught.value.errors)


def test_generation_emits_selected_personal_employer_category() -> None:
    """The personal category is independent of the number of employer rows."""
    draft = _filing_ready_draft()
    draft.personal.employerCategory = "CGOV"
    draft.employers = []
    official, _ = gateway.generate_cbdt_json(draft)
    assert official["ITR"]["ITR1"]["PersonalInfo"]["EmployerCategory"] == "CGOV"


def test_generation_emits_complete_conditional_filing_profile() -> None:
    """Alternate address, seventh proviso, representative and TRP survive."""
    draft = _filing_ready_draft()
    draft.personal.mobileCountryCode = "91"
    draft.personal.secondaryAddressDifferent = True
    draft.personal.alternateAddress = AlternateAddress(
        residenceNo="44",
        localityOrArea="South",
        cityOrTownOrDistrict="Delhi",
        stateCode="07",
        countryCode="91",
        pinCode="110002",
    )
    draft.filing.seventhProviso.foreignTravel = True
    draft.filing.seventhProviso.foreignTravelAmount = Decimal("250000")
    draft.filing.seventhProviso.electricityExpenditure = True
    draft.filing.seventhProviso.electricityExpenditureAmount = Decimal("150000")
    draft.filing.seventhProviso.otherClauseIV = True
    draft.filing.seventhProviso.clauseIVDetails = [
        SeventhProvisoClause(id="sp-1", nature="1", amount=Decimal("50000"))
    ]
    draft.verification.capacity = "REPRESENTATIVE"
    draft.filing.representative = RepresentativeAssessee(
        name="Priya Sharma",
        email="priya@example.com",
        mobileCountryCode="91",
        mobile="9876500000",
    )
    draft.taxReturnPreparer.used = True
    draft.taxReturnPreparer.identificationNumber = "T123456789"
    draft.taxReturnPreparer.name = "Tax Preparer"
    draft.taxReturnPreparer.reimbursementFromGovernment = Decimal("500")

    official, _ = gateway.generate_cbdt_json(draft)
    itr1 = official["ITR"]["ITR1"]
    assert itr1["PersonalInfo"]["SecondaryAdd"] == "Y"
    assert itr1["PersonalInfo"]["AlternateAddress"]["PinCode"] == 110002
    assert itr1["FilingStatus"]["SeventhProvisio139"] == "Y"
    assert itr1["FilingStatus"]["IncrExpAggAmt2LkTrvFrgnCntryFlg"] == "Y"
    assert itr1["FilingStatus"]["AmtSeventhProvisio139ii"] == 250000
    assert itr1["FilingStatus"]["IncrExpAggAmt1LkElctrctyPrYrFlg"] == "Y"
    assert itr1["FilingStatus"]["AmtSeventhProvisio139iii"] == 150000
    assert itr1["FilingStatus"]["clauseiv7provisio139i"] == "Y"
    assert itr1["FilingStatus"]["clauseiv7provisio139iDtls"][0] == {
        "clauseiv7provisio139iNature": "1",
        "clauseiv7provisio139iAmount": 50000,
    }
    assert itr1["FilingStatus"]["AsseseeRepFlg"] == "Y"
    assert itr1["FilingStatus"]["AssesseeRep"]["RepName"] == "Priya Sharma"
    assert itr1["FilingStatus"]["AssesseeRep"]["RepEmailID"] == "priya@example.com"
    assert itr1["FilingStatus"]["AssesseeRep"]["CountryCodeRepMobileNo"] == 91
    assert itr1["FilingStatus"]["AssesseeRep"]["RepMobileNo"] == 9876500000
    assert itr1["FilingStatus"]["ItrFilingDueDate"] == "2026-07-31"
    assert itr1["Verification"]["Capacity"] == "R"
    assert itr1["TaxReturnPreparer"] == {
        "IdentificationNoOfTRP": "T123456789",
        "NameOfTRP": "Tax Preparer",
        "ReImbFrmGov": 500,
    }
    gateway.validate_itr1_json(official)


def test_generation_rejects_unsupported_filing_section() -> None:
    """Official generation rejects filing sections outside the CBDT enum."""
    draft = _filing_ready_draft()
    draft.filing.filingSection = "NOT_A_REAL_SECTION"
    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.generate_cbdt_json(draft)
    assert "ReturnFileSec" in " ".join(caught.value.errors) or caught.value.message


def test_generation_accepts_revised_filing_section() -> None:
    """Filing section 139(5) (revised return) maps to CBDT code 17."""
    draft = _filing_ready_draft()
    draft.filing.filingSection = "139(5)"
    draft.filing.returnType = "REVISED"
    draft.filing.originalAcknowledgementNumber = "123456789012345"
    draft.filing.originalFilingDate = "2026-06-30"

    official, _ = gateway.generate_cbdt_json(draft)
    gateway.validate_itr1_json(official)
    status = official["ITR"]["ITR1"]["FilingStatus"]
    assert status["ReturnFileSec"] == 17
    assert status["ReceiptNo"] == "123456789012345"
    assert status["OrigRetFiledDate"] == "2026-06-30"


def test_generation_emits_notice_filing_fields() -> None:
    """Notice filings preserve their selected section, number, and date."""
    draft = _filing_ready_draft()
    draft.filing.filingSection = "148"
    draft.filing.noticeNumber = "NOTICE/148/2026/001"
    draft.filing.noticeDate = "2026-05-15"

    official, _ = gateway.generate_cbdt_json(draft)
    gateway.validate_itr1_json(official)
    status = official["ITR"]["ITR1"]["FilingStatus"]
    assert status["ReturnFileSec"] == 14
    assert status["NoticeNo"] == "NOTICE/148/2026/001"
    assert status["NoticeDateUnderSec"] == "2026-05-15"


def test_generation_emits_complete_schedule_80ggc() -> None:
    """Canonical 80GGC input must reach every official row and total field."""
    draft = _filing_ready_draft()
    draft.regime = "old"
    draft.employers[0].natureOfEmployment = "OTH"
    draft.deductions.schedule80GGC = [Schedule80GGCEntry(
        id="ggc-1",
        cashAmount=Decimal("500"),
        otherModeAmount=Decimal("10000"),
        contributionDate="2025-06-01",
        transactionRef="UTR-80GGC-001",
        ifscCode="SBIN0001234",
        politicalPartyName="National Reform Party",
        politicalPartyPAN="AAACP1234D",
    )]
    draft.deductions.chapterVIA.section80GGC = Decimal("10000")

    official, _ = gateway.generate_cbdt_json(draft)
    gateway.validate_itr1_json(official)
    assert official["ITR"]["ITR1"]["Schedule80GGC"] == {
        "Schedule80GGCDetails": [{
            "DonationDate": "2025-06-01",
            "DonationAmtCash": 500,
            "DonationAmtOtherMode": 10000,
            "TransactionRefNum": "UTR-80GGC-001",
            "IFSCCode": "SBIN0001234",
            "DonationAmt": 10500,
            "EligibleDonationAmt": 10000,
            "PoliticalPartyName": "National Reform Party",
            "PoliticalPartyPAN": "AAACP1234D",
        }],
        "TotalDonationAmtCash80GGC": 500,
        "TotalDonationAmtOtherMode80GGC": 10000,
        "TotalDonationsUs80GGC": 10500,
        "TotalEligibleDonationAmt80GGC": 10000,
    }


def test_compute_canonical_itr1_rejects_pending_reconciliation() -> None:
    """Pending reconciliation discrepancies block the canonical gateway."""
    draft = _filing_ready_draft()
    draft.reconciliation.discrepancies.append(ReconciliationDiscrepancy(
        id="reconciliation-1",
        category="interest from savings bank",
        description="AIS/TIS mismatch.",
        aisAmount=Decimal("157"),
        tisAcceptedAmount=Decimal("90"),
        as26Amount=Decimal("0"),
        difference=Decimal("67"),
        status="PENDING",
    ))
    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.compute_canonical_itr1(draft)
    assert "reconciliation" in " ".join(caught.value.errors).lower()


def test_compute_canonical_itr1_allows_confirmed_reconciliation() -> None:
    """A confirmed discrepancy no longer blocks the gateway."""
    draft = _filing_ready_draft()
    draft.reconciliation.discrepancies.append(ReconciliationDiscrepancy(
        id="reconciliation-1",
        category="interest from savings bank",
        description="AIS/TIS mismatch.",
        aisAmount=Decimal("157"),
        tisAcceptedAmount=Decimal("90"),
        as26Amount=Decimal("0"),
        difference=Decimal("67"),
        status="CONFIRMED_AIS",
    ))
    result = gateway.compute_canonical_itr1(draft)
    assert result.computation.gross_total_income >= Decimal("0")


def test_compute_canonical_itr1_rejects_out_of_scope_import_evidence() -> None:
    """Imported taxable evidence outside ITR-1 forces form escalation."""
    draft = _filing_ready_draft()
    draft.reconciliation.evidence.append(ReconciliationEvidence(
        id="ais-sft-012-1",
        source="AIS",
        sourceCode="SFT-012",
        sourceSection="B2",
        incomeHead="Capital gains",
        category="Sale of immovable property",
        description="Property sale evidence.",
        sourceName="Sub-registrar",
        sourceIdentifier="",
        role="OUT_OF_SCOPE_TAXABLE",
        relatedTab="CAPITAL_GAINS",
        canonicalDestination="none",
        evidenceKind="SOURCE_DETAIL",
        reportedAmount=Decimal("5000000"),
        processedAmount=Decimal("5000000"),
        acceptedAmount=Decimal("0"),
        taxAmount=Decimal("0"),
        status="SFT-012",
        requiresReview=True,
        raw={"information_code": "SFT-012"},
    ))
    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.compute_canonical_itr1(draft)
    message = f"{caught.value} {' '.join(caught.value.errors)}".lower()
    assert "outside itr-1" in message
    assert "sft-012" in message


def test_compute_canonical_itr1_purchase_only_does_not_fabricate_112a_gain() -> None:
    """A purchase-only MF entry (no sale) must never be treated as a 112A gain.

    Reproduces the bug where a client with a ₹4,99,975 MF purchase and no sale
    was blocked with "LTCG u/s 112A of Rs 499975 exceeds Rs 125000 limit".
    A purchase is an acquisition, not a disposal — there is no gain event.
    """
    draft = _filing_ready_draft()
    # Simulate the simplified 112A block with only a cost (purchase) and no sale.
    draft.capitalGainsSchedule = {
        "simplified112A": {
            "totalSaleConsideration": 0,
            "totalCostAcquisition": Decimal("499975"),
        },
    }
    result = gateway.compute_canonical_itr1(draft)
    # The gain must be 0 (sale - cost floored at 0), so ITR-1 stays eligible.
    assert result.computation.capital_gains_112a == Decimal("0")
    assert not result.computation.errors

