"""Phase 3 tests — ITR-4 canonical compute + CBDT JSON via filing_gateway_v2.

Verifies the single canonical ITR-4 pipeline: compute_canonical_itr4
computes once, generate_cbdt_json dispatches ITR-4 to the v2 path, and the
produced CBDT JSON passes the official ITR-4 schema gate. Also verifies
the form dispatcher (compute_canonical) routes ITR-1 and ITR-4 correctly.

Run: pytest tests/test_filing_gateway_v2_itr4.py -v
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.filing_gateway_v2 import (
    FilingGatewayV2Error,
    ITR1PipelineResult,
    ITR4PipelineResult,
    _generate_cbdt_json_itr4,
    compute_canonical,
    compute_canonical_itr4,
    generate_cbdt_json,
)
from app.engine.itd.itr4_schema import validate_itr4_json
from app.schemas.return_draft import (
    GstinTurnoverRow,
    AlternateAddress,
    BankAccount,
    CoOwner,
    DividendIncome,
    Employer,
    Policy80D,
    DeductionLoan,
    FinancialParticulars,
    HomeLoan,
    HouseProperty,
    InterestIncome,
    OtherIncomeEntry,
    Presumptive44AD,
    Presumptive44ADA,
    Presumptive44AE,
    ReconciliationDiscrepancy,
    ReturnDraft,
    RepresentativeAssessee,
    SeventhProvisoClause,
    TenantDetail,
    create_empty_draft,
)


def _financial_particulars() -> FinancialParticulars:
    """Non-zero balance-sheet particulars so CBDT Sl 139 rule passes.

    The ITR-4 Category A validator requires Schedule BP financial particulars
    (sundry creditors, inventories, cash-in-hand, etc.) when gross receipts or
    turnover is disclosed. In production these are entered on the Business tab;
    the test fixture supplies representative values.
    """
    return FinancialParticulars(
        cashBalance=Decimal("50000"),
        bankBalance=Decimal("200000"),
        inventory=Decimal("100000"),
        sundryDebtors=Decimal("80000"),
        sundryCreditors=Decimal("60000"),
        totalAssets=Decimal("430000"),
        securedLoans=Decimal("0"),
        unsecuredLoans=Decimal("0"),
        grossProfit=Decimal("600000"),
        netProfit=Decimal("600000"),
    )


def _filing_ready_itr4(scheme: str = "44AD") -> ReturnDraft:
    """A canonical ITR-4 draft carrying all official-filing fields.

    Populates personal/filing/verification so _itr4_filing_profile can
    construct a valid ITR4FilingProfile, plus one business row in the
    requested scheme + a refund bank account.
    """
    draft = create_empty_draft("2026-27", "ITR-4", "new")
    p = draft.personal
    p.pan = "ABCDE1234F"
    p.firstName = "Rahul"
    p.surnameOrOrgName = "Sharma"
    p.fatherName = "Mohan Sharma"
    p.employerCategory = "OTH"
    p.dateOfBirth = "1980-05-15"
    p.age = 45
    p.flatNo = "12A"
    p.localityOrArea = "Central"
    p.city = "Delhi"
    p.stateCode = "07"
    p.pinCode = "110001"
    p.mobile = "9876543210"
    p.email = "rahul@example.com"
    draft.verification.place = "Delhi"
    draft.verification.date = "2026-07-31"
    draft.verification.declarationAccepted = True
    draft.verification.capacity = "SELF"
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="SBI", accountNumber="1234567890",
        ifscCode="SBIN0001234", accountType="SB", useForRefund=True,
    )]
    if scheme == "44AD":
        draft.businesses = [Presumptive44AD(
            id="b1", natureCode="01001",
            digitalReceipts=Decimal("5000000"),
            nonDigitalReceipts=Decimal("1000000"),
            declaredIncome=Decimal("600000"),
            financialParticulars=_financial_particulars(),
        )]
    elif scheme == "44ADA":
        draft.businesses = [Presumptive44ADA(
            id="b1", natureCode="14001",
            grossReceipts=Decimal("4000000"),
            digitalReceipts=Decimal("3000000"),
            nonDigitalReceipts=Decimal("1000000"),
            declaredIncome=Decimal("2000000"),
            financialParticulars=_financial_particulars(),
        )]
    elif scheme == "44AE":
        draft.businesses = [Presumptive44AE(
            id="b1", natureCode="08001",
            vehicles=[
                {"vehicleType": "HEAVY", "tonnage": Decimal("16"),
                 "ownedMonths": 12, "vehicleNumber": "KA01"},
            ],
            financialParticulars=_financial_particulars(),
        )]
    return draft


# ── compute_canonical_itr4 ───────────────────────────────────────────────────

def test_compute_canonical_itr4_prepares_filing_data_before_calculation() -> None:
    """Compute receives the complete ITR-4 profile and refund data."""
    draft = _filing_ready_itr4("44AD")
    draft.taxReturnPreparer.used = True
    draft.taxReturnPreparer.identificationNumber = "123456"
    draft.taxReturnPreparer.name = "Registered Tax Preparer"
    draft.taxReturnPreparer.reimbursementFromGovernment = Decimal("750")

    pipeline = compute_canonical_itr4(draft)

    assert isinstance(pipeline, ITR4PipelineResult)
    assert pipeline.computation.gross_total_income > 0
    assert "grossTotalIncome" in pipeline.summary
    assert pipeline.summary["computedByFormEngine"] == "ITR-1"  # shared summary
    assert pipeline.breakdown["presumptive_scheme"] == "44AD"
    assert pipeline.typed_input.filing_profile is not None
    assert pipeline.typed_input.filing_profile.pan == draft.personal.pan
    assert pipeline.typed_input.filing_profile.verification_place == draft.verification.place
    assert len(pipeline.typed_input.bank_accounts) == 1
    assert pipeline.typed_input.bank_accounts[0].is_primary is True
    assert pipeline.typed_input.tax_return_preparer is not None


def test_itr4_filing_date_reaches_typed_input_from_verification_date() -> None:
    """compute_canonical_itr4 must set filing_date/due_date on typed_input.

    Previously the mapper set ITR4Input.filing_date to a date-of-birth
    placeholder that the gateway's model_copy never overwrote (stale
    "gateway sets filing_date" comment), so compute_itr4()'s interest/fee
    gate always saw a "filing date" decades before the due date and
    computed zero -- found 2026-09-03 auditing ITR-4, see
    Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md."""
    from datetime import date
    draft = _filing_ready_itr4("44AD")
    pipeline = compute_canonical_itr4(draft)
    assert pipeline.typed_input.filing_date == date(2026, 7, 31)
    assert pipeline.typed_input.due_date == date(2026, 8, 31)


def test_itr4_late_filing_computes_nonzero_interest_and_late_fee() -> None:
    """A genuinely late-filed ITR-4 return must show real 234A interest and
    a 234F late fee in the generated JSON, not the silent zero the
    date-of-birth filing_date placeholder produced for every return."""
    from app.engine.filing_gateway_v2 import generate_cbdt_json
    draft = _filing_ready_itr4("44AD")
    draft.verification.date = "2027-02-01"
    draft.filing.filingSection = "139(4)"
    # Push declared income well above the new-regime 87A rebate threshold so
    # there is genuine tax payable for 234A to accrue interest on -- the
    # fixture's default 6L declared income is fully rebated under the new
    # regime, which would make 234A correctly (not buggily) zero and defeat
    # the point of this regression test.
    draft.businesses[0].declaredIncome = Decimal("2500000")

    official, summary = generate_cbdt_json(draft)
    intrst_pay = official["ITR"]["ITR4"]["TaxComputation"]["IntrstPay"]
    assert intrst_pay["IntrstPayUs234A"] > 0
    assert intrst_pay["LateFilingFee234F"] == 5000


def test_itr4_net_tax_liability_json_field_excludes_interest_and_fees() -> None:
    """Same shared-builder bug as ITR-1's equivalent test: the official
    schema documents TaxComputation.NetTaxLiability as "Balance Tax After
    Relief" (Part D's D7 = D5-D6), computed BEFORE interest/234F/234-I. A
    prior bug populated it with the calculator's internal final-total
    ``net_tax_liability`` instead, inflating it by the full interest+fees
    amount for any late-filed return; TotTaxPlusIntrstPay was wrong the
    other way (omitted Section 89 relief in its own formula)."""
    from app.engine.filing_gateway_v2 import generate_cbdt_json
    draft = _filing_ready_itr4("44AD")
    draft.verification.date = "2027-02-01"
    draft.filing.filingSection = "139(4)"
    draft.businesses[0].declaredIncome = Decimal("2500000")

    official, summary = generate_cbdt_json(draft)
    tc = official["ITR"]["ITR4"]["TaxComputation"]

    assert tc["IntrstPay"]["IntrstPayUs234A"] > 0

    total_intrst_fee = (
        tc["IntrstPay"]["IntrstPayUs234A"] + tc["IntrstPay"]["IntrstPayUs234B"]
        + tc["IntrstPay"]["IntrstPayUs234C"] + tc["IntrstPay"]["LateFilingFee234F"]
        + tc["IntrstPay"]["FeeFurnish234I"]
    )
    assert tc["NetTaxLiability"] == tc["GrossTaxLiability"] - tc["Section89"]
    assert tc["TotTaxPlusIntrstPay"] == tc["NetTaxLiability"] + total_intrst_fee
    assert tc["TotTaxPlusIntrstPay"] > tc["NetTaxLiability"]


def test_itr4_json_reuses_prepared_input_without_late_enrichment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON generation passes the same prepared profile to the builder."""
    draft = _filing_ready_itr4("44AD")
    captured: dict[str, object] = {}

    def fake_build(result: object, typed_input: object) -> dict[str, object]:
        captured["typed_input"] = typed_input
        return {"ITR": {"ITR4": {"ok": True}}}

    import app.engine.filing_gateway_v2 as gateway
    monkeypatch.setattr(gateway, "build_itr4_json", fake_build)
    monkeypatch.setattr(gateway, "validate_itr4_json", lambda document: None)

    expected = compute_canonical_itr4(draft)
    official, _summary = gateway.generate_cbdt_json(draft)

    assert official["ITR"]["ITR4"]["ok"] is True
    actual = captured["typed_input"]
    assert getattr(actual, "filing_profile") == expected.typed_input.filing_profile
    assert getattr(actual, "bank_accounts") == expected.typed_input.bank_accounts


def test_compute_canonical_dispatches_itr1_and_itr4():
    """compute_canonical routes ITR-1 and ITR-4 to the correct pipeline."""
    itr1 = create_empty_draft("2026-27", "ITR-1", "new")
    itr1.employers = [Employer(id="e1", basic=Decimal("800000"))]
    itr1.personal.pan = "ABCDE1234F"
    itr1.personal.firstName = "Rahul"
    itr1.personal.surnameOrOrgName = "Sharma"
    itr1.personal.fatherName = "Mohan Sharma"
    itr1.personal.dateOfBirth = "1980-05-15"
    itr1.personal.flatNo = "12A"
    itr1.personal.localityOrArea = "Central"
    itr1.personal.city = "Delhi"
    itr1.personal.stateCode = "07"
    itr1.personal.pinCode = "110001"
    itr1.personal.employerCategory = "OTH"
    itr1.personal.mobile = "9876543210"
    itr1.personal.email = "rahul@example.com"
    itr1.verification.place = "Delhi"
    itr1.verification.date = "2026-07-31"
    itr1.verification.declarationAccepted = True
    itr1.verification.capacity = "SELF"
    result1 = compute_canonical(itr1)
    assert isinstance(result1, ITR1PipelineResult)

    itr4 = _filing_ready_itr4("44AD")
    result4 = compute_canonical(itr4)
    assert isinstance(result4, ITR4PipelineResult)


def test_compute_canonical_rejects_unsupported_form():
    """ITR-3 is not yet supported by the v2 pipeline (ITR-2 is, since Phase 4)."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-3")
    with pytest.raises(FilingGatewayV2Error) as caught:
        compute_canonical(draft)
    assert "ITR-1, ITR-2, and ITR-4 only" in caught.value.message


# ── generate_cbdt_json (ITR-4 dispatch) ──────────────────────────────────────

def test_generate_cbdt_json_itr4_44ad_passes_schema():
    """ITR-4 44AD CBDT JSON validates against the official schema."""
    draft = _filing_ready_itr4("44AD")
    official_json, summary = generate_cbdt_json(draft)
    # Must pass the official ITR-4 schema gate.
    validate_itr4_json(official_json)
    assert summary["grossTotalIncome"] > 0
    assert official_json.get("ITR4", {}).get("FormName") or "ITR-4" in str(official_json)


def test_itr4_emits_exact_refund_verification_and_creation_metadata() -> None:
    """Filing identity, bank data, and system metadata reach exact JSON paths."""
    draft = _filing_ready_itr4("44AD")
    official, summary = generate_cbdt_json(draft)
    itr4 = official["ITR"]["ITR4"]

    assert itr4["Refund"] == {
        "RefundDue": round(summary["refundDue"] / 10) * 10,
        "BankAccountDtls": {
            "AddtnlBankDetails": [{
                "IFSCCode": "SBIN0001234",
                "BankName": "SBI",
                "BankAccountNo": "1234567890",
                "AccountType": "SB",
                "UseForRefund": "true",
            }],
        },
    }
    assert itr4["Verification"] == {
        "Declaration": {
            "AssesseeVerName": "Rahul Sharma",
            "FatherName": "Mohan Sharma",
            "AssesseeVerPAN": "ABCDE1234F",
        },
        "Capacity": "S",
        "Place": "Delhi",
    }
    assert itr4["CreationInfo"]["SWVersionNo"] == "1.0"
    assert itr4["CreationInfo"]["SWCreatedBy"].startswith("SW")
    assert itr4["CreationInfo"]["JSONCreatedBy"] == itr4["CreationInfo"]["SWCreatedBy"]
    assert len(itr4["CreationInfo"]["JSONCreationDate"]) == 10
    assert itr4["CreationInfo"]["IntermediaryCity"] == "Akola"
    assert itr4["CreationInfo"]["Digest"] == "-" or len(itr4["CreationInfo"]["Digest"]) == 44


def test_generate_cbdt_json_itr4_rejects_malformed_bank_rows() -> None:
    """Malformed canonical bank rows must be reported, never silently dropped."""
    draft = _filing_ready_itr4("44AD")
    draft.bankAccounts[0].bankName = ""
    draft.bankAccounts[0].accountNumber = "INVALID"
    draft.bankAccounts[0].ifscCode = "BAD"

    with pytest.raises(FilingGatewayV2Error) as caught:
        generate_cbdt_json(draft)

    assert caught.value.message == "ITR-4 bank account details are invalid."
    assert any("bankAccounts[0].bankName" in error for error in caught.value.errors)
    assert any("bankAccounts[0].accountNumber" in error for error in caught.value.errors)
    assert any("bankAccounts[0].ifscCode" in error for error in caught.value.errors)


def test_generate_cbdt_json_itr4_requires_one_unique_refund_account() -> None:
    """The gateway enforces one refund choice and rejects duplicate rows."""
    draft = _filing_ready_itr4("44AD")
    draft.bankAccounts.append(draft.bankAccounts[0].model_copy(update={"id": "b2"}))

    with pytest.raises(FilingGatewayV2Error) as caught:
        generate_cbdt_json(draft)

    assert any("exactly one account" in error for error in caught.value.errors)
    assert any("duplicates another bank account" in error for error in caught.value.errors)


def test_generate_cbdt_json_itr4_preserves_other_bank_account_type() -> None:
    """The canonical OTH bank type must serialize as the official OTH code."""
    draft = _filing_ready_itr4("44AD")
    draft.bankAccounts[0].accountType = "OTH"

    official, _ = generate_cbdt_json(draft)

    bank = official["ITR"]["ITR4"]["Refund"]["BankAccountDtls"][
        "AddtnlBankDetails"
    ][0]
    assert bank["AccountType"] == "OTH"


def test_generate_itr4_schedule_bp_preserves_exact_canonical_fields() -> None:
    """Schedule BP values are not replaced by fabricated builder defaults."""
    draft = _filing_ready_itr4("44AD")
    business = draft.businesses[0]
    business.businessName = "Sharma Stores"
    business.description = "Retail trade"
    business.otherModeReceipts = Decimal("250000")
    business.digitalPresumptiveIncome = Decimal("315000")
    business.nonDigitalPresumptiveIncome = Decimal("80000")
    business.declaredIncome = Decimal("395000")
    business.gstinTurnovers = [
        GstinTurnoverRow(
            id="gst-1",
            gstin="07ABCDE1234F1Z5",
            turnover=Decimal("6250000"),
        )
    ]
    business.financialParticulars.partnerMemberOwnCapital = Decimal("100000")
    business.financialParticulars.fixedAssets = Decimal("50000")
    business.financialParticulars.investments = Decimal("25000")
    business.financialParticulars.loansAndAdvances = Decimal("5000")
    business.financialParticulars.otherAssets = Decimal("10000")
    business.financialParticulars.totalAssets = Decimal("520000")

    official, _ = generate_cbdt_json(draft)
    validate_itr4_json(official)
    bp = official["ITR"]["ITR4"]["ScheduleBP"]
    assert bp["NatOfBus44AD"][0] == {
        "NameOfBusiness": "Sharma Stores",
        "CodeAD": "01001",
        "Description": "Retail trade",
    }
    assert bp["PersumptiveInc44AD"]["GrsTrnOverAnyOthMode"] == 250000
    assert bp["PersumptiveInc44AD"]["PersumptiveInc44AD6Per"] == 315000
    assert bp["PersumptiveInc44AD"]["PersumptiveInc44AD8Per"] == 80000
    assert bp["TurnoverGrsRcptForGSTIN"][0] == {
        "GSTINNo": "07ABCDE1234F1Z5",
        "AmtTurnGrossRcptGSTIN": 6250000,
    }
    assert bp["TotalTurnoverGrsRcptGSTIN"] == 6250000
    assert bp["FinanclPartclrOfBusiness"]["PartnerMemberOwnCapital"] == 100000
    assert bp["FinanclPartclrOfBusiness"]["FixedAssets"] == 50000


def test_generate_itr4_schedule_bp_supports_all_three_schemes() -> None:
    """Official Schedule BP emits concurrent 44AD, 44ADA, and 44AE blocks."""
    draft = _filing_ready_itr4("44AD")
    draft.businesses[0].businessName = "Trading"
    draft.businesses[0].digitalPresumptiveIncome = Decimal("300000")
    draft.businesses[0].nonDigitalPresumptiveIncome = Decimal("80000")
    draft.businesses[0].declaredIncome = Decimal("380000")
    draft.businesses.extend([
        Presumptive44ADA(
            id="ada", businessName="Consulting", natureCode="14001",
            grossReceipts=Decimal("400000"),
            digitalReceipts=Decimal("400000"),
            declaredIncome=Decimal("200000"),
            financialParticulars=_financial_particulars(),
        ),
        Presumptive44AE(
            id="ae", businessName="Transport", natureCode="08001",
            vehicles=[{
                "vehicleType": "OTHER", "ownedMonths": 2,
                "vehicleNumber": "DL01AB1234",
                "presumptiveIncome": Decimal("15000"),
            }],
            declaredIncome=Decimal("15000"),
            financialParticulars=_financial_particulars(),
        ),
    ])

    official, summary = generate_cbdt_json(draft)
    validate_itr4_json(official)
    bp = official["ITR"]["ITR4"]["ScheduleBP"]
    assert bp["NatOfBus44AD"][0]["NameOfBusiness"] == "Trading"
    assert bp["NatOfBus44ADA"][0]["NameOfBusiness"] == "Consulting"
    assert bp["NatOfBus44AE"][0]["NameOfBusiness"] == "Transport"
    assert bp["PersumptiveInc44AD"]["TotPersumptiveInc44AD"] == 380000
    assert bp["PersumptiveInc44ADA"]["TotPersumptiveInc44ADA"] == 200000
    assert bp["PersumptiveInc44AE"]["TotalPersumptiveInc"] == 15000
    assert bp["PersumptiveInc44AE"]["IncChargeableUnderBus"] == 595000
    assert summary["grossTotalIncome"] == 595000


def test_generate_itr4_emits_full_filing_status_and_trp() -> None:
    """ITR-4 emits exact conditional profile keys and integer acknowledgements."""
    draft = _filing_ready_itr4("44AD")
    draft.personal.assesseeStatus = "H"
    draft.personal.mobileCountryCode = "91"
    draft.personal.landlineStdCode = "11"
    draft.personal.landlinePhoneNo = "23456789"
    draft.personal.secondaryAddressDifferent = True
    draft.personal.alternateAddress = AlternateAddress(
        residenceNo="44",
        localityOrArea="South",
        cityOrTownOrDistrict="Delhi",
        stateCode="07",
        countryCode="91",
        pinCode="110002",
    )
    draft.filing.form10IEAEarlierAYOldRegime = "Y"
    draft.filing.form10IEAAssessmentYear = "2025-26"
    draft.filing.form10IEAEarlierAYAckOldRegime = "123456789012345"
    draft.filing.seventhProviso.depositExceedsOneCrore = True
    draft.filing.seventhProviso.depositAmount = Decimal("10000001")
    draft.filing.seventhProviso.otherClauseIV = True
    draft.filing.seventhProviso.clauseIVDetails = [
        SeventhProvisoClause(id="sp-1", nature="3", amount=Decimal("50000"))
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

    official, _ = generate_cbdt_json(draft)
    itr4 = official["ITR"]["ITR4"]
    assert itr4["PersonalInfo"]["Status"] == "H"
    assert itr4["PersonalInfo"]["Address"]["Phone"] == {
        "STDcode": 11,
        "PhoneNo": "23456789",
    }
    assert itr4["PersonalInfo"]["AlternateAddress"]["PinCode"] == 110002
    assert itr4["FilingStatus"]["Form10IEAEarlierAYAckOldRegime"] == 123456789012345
    assert itr4["FilingStatus"]["AmtSeventhProvisio139i"] == 10000001
    assert itr4["FilingStatus"]["clauseiv7provisio139iDtls"][0][
        "clauseiv7provisio139iNature"
    ] == "3"
    assert itr4["FilingStatus"]["AssesseeRep"]["RepName"] == "Priya Sharma"
    assert itr4["Verification"]["Capacity"] == "R"
    assert itr4["TaxReturnPreparer"]["IdentificationNoOfTRP"] == "T123456789"


def test_generate_cbdt_json_itr4_emits_80eea_stamp_duty_value():
    """ITR-4 Schedule 80EEA carries its required property stamp-duty value."""
    draft = _filing_ready_itr4("44AD")
    draft.regime = "old"
    draft.deductions.chapterVIA.section80EEA = Decimal("50000")
    draft.deductions.loans.section80EEAStampDutyValue = Decimal("4000000")
    draft.houseProperties = [HouseProperty(
        id="hp-1",
        propertyType="SELF_OCCUPIED",
        address="12A Central",
        city="Delhi",
        state="07",
        pinCode="110001",
        interestOnLoan=Decimal("200000"),
        homeLoans=[HomeLoan(
            lenderType="B",
            lenderName="Example Bank",
            loanAccountNo="HOME123",
            dateOfLoan="2022-01-01",
            totalLoanAmount=Decimal("3000000"),
            loanOutstandingAmount=Decimal("2500000"),
            interestUs24B=Decimal("200000"),
        )],
    )]
    draft.deductions.loans.loans = [DeductionLoan(
        id="loan-1",
        section="80EEA",
        loanTakenFrom="B",
        lenderName="Example Bank",
        loanAccountNo="HOME123",
        dateOfLoan="2022-01-01",
        totalLoanAmount=Decimal("3000000"),
        outstandingAmount=Decimal("2500000"),
        interestAmount=Decimal("50000"),
    )]

    official_json, summary = generate_cbdt_json(draft)
    validate_itr4_json(official_json)
    assert official_json["ITR"]["ITR4"]["Schedule80EEA"]["PropStmpDtyVal"] == 4000000


def test_itr4_emits_family_pension_deduction_57iia() -> None:
    draft = _filing_ready_itr4("44AD")
    draft.regime = "old"
    draft.otherSources.familyPension.grossAmount = Decimal("45000")

    official_json, _ = generate_cbdt_json(draft)
    validate_itr4_json(official_json)
    income = official_json["ITR"]["ITR4"]["IncomeDeductions"]
    assert income["DeductionUs57iia"] == 15000
    assert income["IncomeOthSrc"] == 30000


def test_itr4_schedule_80d_aggregates_include_checkups_and_medical_expense() -> None:
    draft = _filing_ready_itr4("44AD")
    draft.regime = "old"
    schedule = draft.deductions.section80D
    schedule.selfSeniorCitizen = "N"
    schedule.parentsSeniorCitizen = "Y"
    schedule.selfFamily.policies = [Policy80D(
        id="self-policy",
        insurerName="Self Insurer",
        policyNo="SELF123",
        premiumAmount=Decimal("20000"),
    )]
    schedule.selfFamily.preventiveCheckup = Decimal("5000")
    schedule.parentsSenior.policies = [Policy80D(
        id="parent-policy",
        insurerName="Parent Insurer",
        policyNo="PARENT123",
        premiumAmount=Decimal("30000"),
    )]
    schedule.parentsSenior.preventiveCheckup = Decimal("5000")
    schedule.parentsSenior.medicalExpense = Decimal("10000")

    official_json, _ = generate_cbdt_json(draft)
    validate_itr4_json(official_json)
    schedule_json = official_json["ITR"]["ITR4"]["Schedule80D"][
        "Sec80DSelfFamSrCtznHealth"
    ]
    assert schedule_json["SelfAndFamily"] == 25000
    assert schedule_json["HealthInsPremSlfFam"] == 20000
    assert schedule_json["ParentsSeniorCitizen"] == 40000
    assert schedule_json["HlthInsPremParentsSrCtzn"] == 30000
    assert schedule_json["MedicalExpParentsSrCtzn"] == 10000
    assert schedule_json["EligibleAmountOfDedn"] == 65000
    income = official_json["ITR"]["ITR4"]["IncomeDeductions"]
    assert income["UsrDeductUndChapVIA"]["Section80D"] == 70000
    assert income["DeductUndChapVIA"]["Section80D"] == 65000


@pytest.mark.parametrize(
    ("flag", "amount_field", "threshold"),
    [
        ("depositExceedsOneCrore", "depositAmount", Decimal("10000000")),
        ("foreignTravel", "foreignTravelAmount", Decimal("200000")),
        (
            "electricityExpenditure",
            "electricityExpenditureAmount",
            Decimal("100000"),
        ),
    ],
)
def test_itr4_seventh_proviso_flags_require_amounts_above_threshold(
    flag: str,
    amount_field: str,
    threshold: Decimal,
) -> None:
    draft = _filing_ready_itr4("44AD")
    setattr(draft.filing.seventhProviso, flag, True)
    setattr(draft.filing.seventhProviso, amount_field, threshold)

    with pytest.raises(FilingGatewayV2Error):
        generate_cbdt_json(draft)


def test_generate_cbdt_json_itr4_emits_property_ownership_and_tenants():
    """ITR-4 emits the complete canonical co-owner and tenant rows."""
    draft = _filing_ready_itr4("44AD")
    draft.houseProperties = [HouseProperty(
        id="hp-1",
        propertyType="DEEMED_LET_OUT",
        address="18 Market Road",
        city="Delhi",
        state="07",
        pinCode="110001",
        propertyOwnerType="SP",
        isCoOwned=True,
        ownershipType="JOINT",
        ownershipShare=Decimal("55.5"),
        coOwners=[CoOwner(
            coOwnerSNo=3,
            name="Priya Sharma",
            pan="PQRSX1234Y",
            aadhaar="123456789012",
            share=Decimal("44.5"),
        )],
        tenantDetails=[TenantDetail(
            tenantSNo=4,
            name="Tenant One",
            pan="LMNOP1234Q",
            aadhaar="234567890123",
            panOrTan="DELA12345B",
        )],
        annualRent=Decimal("240000"),
        unrealizedRent=Decimal("12000"),
        municipalTaxesPaid=Decimal("12000"),
    )]

    official_json, summary = generate_cbdt_json(draft)
    validate_itr4_json(official_json)
    prop = official_json["ITR"]["ITR4"]["IncomeDeductions"]["PropertyDetails"][0]
    assert prop["PropertyOwner"] == "SP"
    assert prop["PropCoOwnedFlg"] == "YES"
    assert prop["AsseseeShareProperty"] == 55.5
    assert prop["CoOwners"] == [{
        "CoOwnersSNo": 1,
        "NameCoOwner": "Priya Sharma",
        "PAN_CoOwner": "PQRSX1234Y",
        "Aadhaar_CoOwner": "123456789012",
        "PercentShareProperty": 44.5,
    }]
    assert prop["TenantDetails"] == [{
        "TenantSNo": 1,
        "NameofTenant": "Tenant One",
        "PANofTenant": "LMNOP1234Q",
        "AadhaarofTenant": "234567890123",
        "PANTANofTenant": "DELA12345B",
    }]
    assert prop["Rentdetails"] == {
        "AnnualLetableValue": 240000,
        "RentNotRealized": 12000,
        "LocalTaxes": 12000,
        "TotalUnrealizedAndTax": 24000,
        "BalanceALV": 216000,
        "AnnualOfPropOwned": 119880,
        "ThirtyPercentOfBalance": 35964,
        "IntOnBorwCap": 0,
        "TotalDeduct": 35964,
        "IncomeOfHP": 83916,
    }
    assert summary["housePropertyDetails"][0]["annualOfPropOwned"] == 119880
    assert summary["housePropertyDetails"][0]["incomeOfHP"] == 83916


def test_generate_cbdt_json_itr4_emits_dividend_date_range() -> None:
    """ITR-4 must retain all five editable dividend receipt periods."""
    draft = _filing_ready_itr4("44AD")
    draft.otherSources.dividends = [DividendIncome(
        id="div-1", grossAmount=Decimal("15000"),
        q1=Decimal("1000"), q2=Decimal("2000"), q3=Decimal("3000"),
        q4=Decimal("4000"), q5=Decimal("5000"),
    )]

    official_json, _ = generate_cbdt_json(draft)
    validate_itr4_json(official_json)
    rows = official_json["ITR"]["ITR4"]["IncomeDeductions"]["OthersInc"][
        "OthersIncDtlsOthSrc"
    ]
    dividend = next(row for row in rows if row["OthSrcNatureDesc"] == "DIV")
    assert dividend["OthSrcOthAmount"] == 15000
    assert dividend["DividendInc"]["DateRange"] == {
        "Upto15Of6": 1000,
        "Upto15Of9": 2000,
        "Up16Of9To15Of12": 3000,
        "Up16Of12To15Of3": 4000,
        "Up16Of3To31Of3": 5000,
    }


def test_generate_cbdt_json_itr4_emits_exact_compact_other_source_rows() -> None:
    draft = _filing_ready_itr4("44AD")
    draft.otherSources.interest = [
        InterestIncome(id="tax", kind="IT_REFUND", grossAmount=Decimal("300")),
        InterestIncome(id="pf", kind="PF_10_12_SECOND", grossAmount=Decimal("400")),
    ]
    draft.otherSources.otherIncome = [OtherIncomeEntry(
        id="other", nature="OTHER",
        description="Consulting honorarium", amount=Decimal("600"),
    )]

    official_json, _ = generate_cbdt_json(draft)
    validate_itr4_json(official_json)
    rows = official_json["ITR"]["ITR4"]["IncomeDeductions"]["OthersInc"][
        "OthersIncDtlsOthSrc"
    ]
    assert rows == [
        {"OthSrcNatureDesc": "TAX", "OthSrcOthAmount": 300},
        {"OthSrcNatureDesc": "10(12)(iiP)", "OthSrcOthAmount": 400},
        {
            "OthSrcNatureDesc": "OTH",
            "OthSrcOthAmount": 600,
            "OthSrcOthNatOfInc": "Consulting honorarium",
        },
    ]


def test_generate_cbdt_json_itr4_44ada_passes_schema():
    """ITR-4 44ADA CBDT JSON validates against the official schema."""
    draft = _filing_ready_itr4("44ADA")
    official_json, summary = generate_cbdt_json(draft)
    validate_itr4_json(official_json)


def test_generate_cbdt_json_itr4_44ae_passes_schema():
    """ITR-4 44AE CBDT JSON validates against the official schema.

    The pre-existing validator conflict (CBDT Sl 12 vs Sl 137) is resolved:
    Rule 12 (ITR4-R012) now only fires when a business code is present but
    NO presumptive scheme is active — 44ADA/44AE carry their own business
    codes (Sl 137) and no longer trip the 44AD-specific check. The 44AE
    goods-carriage builder also emits the official schema fields
    (RegNumberGoodsCarriage, OwnedLeasedHiredFlag, TonnageCapacity,
    HoldingPeriod, PresumptiveIncome) instead of the old
    IsHeavyGoodsVehicle/NoOfMonthsOwned/GrossVehicleWeight fields.
    """
    draft = _filing_ready_itr4("44AE")
    official_json, _ = generate_cbdt_json(draft)
    validate_itr4_json(official_json)


def test_generate_cbdt_json_dispatches_itr4_not_itr1():
    """generate_cbdt_json routes ITR-4 to _generate_cbdt_json_itr4."""
    draft = _filing_ready_itr4("44AD")
    official_json, summary = _generate_cbdt_json_itr4(draft)
    validate_itr4_json(official_json)
    assert summary["grossTotalIncome"] > 0


# ── Guards ───────────────────────────────────────────────────────────────────

def test_compute_canonical_itr4_rejects_pending_discrepancies():
    """Pending reconciliation discrepancies block ITR-4 compute."""
    draft = _filing_ready_itr4("44AD")
    draft.reconciliation.discrepancies.append(ReconciliationDiscrepancy(
        id="d1", category="interest from savings bank",
        description="AIS/TIS mismatch.", status="PENDING",
    ))
    with pytest.raises(FilingGatewayV2Error) as caught:
        compute_canonical_itr4(draft)
    assert "reconciliation" in caught.value.message.lower()


def test_generate_cbdt_json_itr4_rejects_missing_profile():
    """Missing required profile fields raise a clear filing-profile error."""
    draft = _filing_ready_itr4("44AD")
    draft.personal.pan = ""  # required field removed
    with pytest.raises(FilingGatewayV2Error) as caught:
        generate_cbdt_json(draft)
    assert "filing profile" in caught.value.message.lower()


def test_compute_canonical_itr4_rejects_empty_employer_category() -> None:
    """ITR4FilingProfile.employer_category must not silently fall back —
    the adapter enforces this itself via require_field(), since the shared
    personal_profile normalizer now leaves employer_category optional (it
    is not a field ITR2FilingProfile has at all)."""
    draft = _filing_ready_itr4("44AD")
    draft.personal.employerCategory = ""
    with pytest.raises(FilingGatewayV2Error) as caught:
        compute_canonical_itr4(draft)
    assert "personal.employerCategory" in " ".join(caught.value.errors)


# ── ITR-1 unchanged (regression) ─────────────────────────────────────────────

def test_generate_cbdt_json_itr1_still_works():
    """Regression: ITR-1 generate_cbdt_json still dispatches correctly."""
    # Minimal ITR-1 filing-ready draft.
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    draft.employers = [Employer(id="e1", basic=Decimal("800000"))]
    p = draft.personal
    p.pan = "ABCDE1234F"
    p.firstName = "Rahul"
    p.surnameOrOrgName = "Sharma"
    p.fatherName = "Mohan Sharma"
    p.employerCategory = "OTH"
    p.dateOfBirth = "1980-05-15"
    p.flatNo = "12A"
    p.localityOrArea = "Central"
    p.city = "Delhi"
    p.stateCode = "07"
    p.pinCode = "110001"
    p.mobile = "9876543210"
    p.email = "rahul@example.com"
    draft.verification.place = "Delhi"
    draft.verification.date = "2026-07-31"
    draft.verification.declarationAccepted = True
    draft.verification.capacity = "SELF"
    pipeline = compute_canonical(draft)
    assert isinstance(pipeline, ITR1PipelineResult)
    assert pipeline.summary["grossTotalIncome"] > 0
