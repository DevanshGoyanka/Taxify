"""Focused regression tests for the canonical ITR-3 foundation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.draft_to_itr3_input import draft_to_itr3_input
from app.engine.filing_gateway_v2 import (
    FilingGatewayV2Error,
    ITR3PipelineResult,
    compute_canonical,
    compute_canonical_itr3,
    generate_cbdt_json,
)
from app.engine.itd.itr3_schema import ITR3SchemaValidationError, validate_itr3_json
from app.engine.validators.itr3 import run_calc_validation, run_input_validation
from app.schemas.return_draft import AlternateAddress, ITR3NatureOfBusiness, Presumptive44AD, ReturnDraft, create_empty_draft


def _draft_with_business() -> ReturnDraft:
    """Build the smallest explicit ITR-3 compute draft."""
    draft = create_empty_draft("2026-27", "ITR-3", "new")
    draft.personal.pan = "ABCDE1234F"
    draft.personal.firstName = "Asha"
    draft.personal.surnameOrOrgName = "Sharma"
    draft.personal.dateOfBirth = "1985-01-01"
    draft.personal.flatNo = "1"
    draft.personal.localityOrArea = "Central"
    draft.personal.city = "Delhi"
    draft.personal.stateCode = "07"
    draft.personal.countryCode = "91"
    draft.personal.pinCode = "110001"
    draft.personal.mobile = "9876543210"
    draft.personal.email = "asha@example.com"
    draft.verification.place = "Delhi"
    draft.verification.date = "2026-07-31"
    draft.verification.declarationAccepted = True
    draft.businesses = [Presumptive44AD(
        id="business-1",
        natureCode="01001",
        digitalReceipts=Decimal("1000000"),
        declaredIncome=Decimal("60000"),
    )]
    return draft


def test_itr3_mapper_requires_explicit_business_income() -> None:
    """The mapper must not silently turn an empty business profile into zero."""
    draft = create_empty_draft("2026-27", "ITR-3", "new")
    with pytest.raises(ValueError, match="business or professional income"):
        draft_to_itr3_input(draft)


def test_itr3_mapper_preserves_identity_and_business_amount() -> None:
    """Canonical identity and declared business income reach typed input."""
    typed_input, breakdown = draft_to_itr3_input(_draft_with_business())
    assert typed_input.assessee_pan == "ABCDE1234F"
    assert typed_input.assessee_first_name == "Asha"
    assert typed_input.assessee_last_name == "Sharma"
    assert typed_input.business_income is not None
    assert typed_input.business_income.net_profit_before_tax == Decimal("60000")
    assert breakdown["business_income"] == Decimal("60000")


def test_itr3_personal_info_optional_fields_reach_typed_input_and_json() -> None:
    """Schedule 1 (Personal Information, A1-A18): every optional field the
    PDF prints -- building/village name (A6a), road/street (A7a), Aadhaar
    (A16), office phone with STD code and secondary mobile (A17), secondary
    email (A18), and a genuinely distinct secondary address (A5b-A13b) --
    must reach the typed input and the emitted JSON as real, sourced data,
    not silently dropped or fabricated as a copy of the primary address."""
    draft = _draft_with_business()
    draft.personal.residenceName = "Shivam Apartments"
    draft.personal.roadOrStreet = "MG Road"
    draft.personal.aadhaar = "123456789012"
    draft.personal.landlineStdCode = "011"
    draft.personal.landlinePhoneNo = "23456789"
    draft.personal.secondaryMobileCountryCode = "91"
    draft.personal.secondaryMobile = "9123456780"
    draft.personal.secondaryEmail = "asha.alt@example.com"
    draft.personal.secondaryAddressDifferent = True
    draft.personal.alternateAddress = AlternateAddress(
        residenceNo="42", residenceName="Green Villa", roadOrStreet="Park Street",
        localityOrArea="Salt Lake", cityOrTownOrDistrict="Kolkata",
        stateCode="19", countryCode="91", pinCode="700091",
    )

    typed_input, _breakdown = draft_to_itr3_input(draft)
    assert typed_input.residence_name == "Shivam Apartments"
    assert typed_input.road_or_street == "MG Road"
    assert typed_input.assessee_aadhaar == "123456789012"
    assert typed_input.office_phone_std_code == "011"
    assert typed_input.office_phone_no == "23456789"
    assert typed_input.secondary_mobile_no == "9123456780"
    assert typed_input.secondary_email == "asha.alt@example.com"
    assert typed_input.secondary_address_different is True
    assert typed_input.alternate_city == "Kolkata"
    assert typed_input.alternate_pin_code == "700091"

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    personal = document["ITR"]["ITR3"]["PartA_GEN1"]["PersonalInfo"]

    # Scoped to Schedule 1 (Personal Information) only -- the full document
    # doesn't schema-validate yet since later schedules in this push (Part
    # A-BS/OI, CYLA/BFLA, Schedule OS, etc.) aren't closed out yet. Validate
    # PersonalInfo against its own official schema sub-definition directly.
    import json
    from jsonschema import Draft4Validator
    schema_path = (
        "Reference Docs by CBDT & ITD/Official JSON Schema/"
        "ITR-3_2026_Main_V1.1 (2).json"
    )
    with open(schema_path, encoding="utf-8") as f:
        full_schema = json.load(f)
    personal_info_schema = dict(full_schema["definitions"]["PersonalInfo"])
    personal_info_schema["definitions"] = full_schema["definitions"]
    errors = sorted(Draft4Validator(personal_info_schema).iter_errors(personal), key=lambda e: e.path)
    assert not errors, [e.message for e in errors]
    address = personal["Address"]
    assert address["ResidenceName"] == "Shivam Apartments"
    assert address["RoadOrStreet"] == "MG Road"
    assert personal["AadhaarCardNo"] == "123456789012"
    assert address["Phone"] == {"STDcode": 11, "PhoneNo": "23456789"}
    assert address["CountryCodeMobileNoSec"] == 91
    assert address["MobileNoSec"] == 9123456780
    assert address["EmailAddressSec"] == "asha.alt@example.com"
    assert personal["SecondaryAdd"] == "Y"
    alt = personal["AlternateAddress"]
    assert alt["ResidenceNo"] == "42"
    assert alt["ResidenceName"] == "Green Villa"
    assert alt["CityOrTownOrDistrict"] == "Kolkata"
    assert alt["StateCode"] == "19"
    assert alt["PinCode"] == 700091
    # Real, distinct alternate address -- not a copy of the primary one.
    assert alt["ResidenceNo"] != address["ResidenceNo"]
    assert alt["CityOrTownOrDistrict"] != address["CityOrTownOrDistrict"]


def test_itr3_secondary_address_flag_without_data_fails_closed() -> None:
    """A taxpayer who declares a secondary address (SecondaryAdd=Y) but
    never actually enters one must not silently file with a copied or
    fabricated AlternateAddress -- the builder must fail closed."""
    draft = _draft_with_business()
    draft.personal.secondaryAddressDifferent = True
    draft.personal.alternateAddress = None

    typed_input, _breakdown = draft_to_itr3_input(draft)
    assert typed_input.secondary_address_different is True
    assert typed_input.alternate_residence_no is None

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    with pytest.raises(ValueError, match="alternate-address"):
        build_itr3_json(result, typed_input)


def test_itr3_no_secondary_address_still_emits_alternate_address_as_primary_copy() -> None:
    """ITD's real Type-2 server rejects an entirely-absent AlternateAddress
    block regardless of SecondaryAdd (confirmed live for ITR-2, same
    PersonalInfo/AlternateAddress schema shape as ITR-3 -- see the matching
    comment in app/engine/itd/itr3.py::_parta_gen1). A taxpayer with no
    genuinely distinct secondary address must still get SecondaryAdd="Y"
    and a real AlternateAddress, copied from the primary address."""
    draft = _draft_with_business()
    assert draft.personal.secondaryAddressDifferent is False

    typed_input, _breakdown = draft_to_itr3_input(draft)
    assert typed_input.secondary_address_different is False

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    personal = document["ITR"]["ITR3"]["PartA_GEN1"]["PersonalInfo"]
    assert personal["SecondaryAdd"] == "Y"
    assert personal["AlternateAddress"]["ResidenceNo"] == personal["Address"]["ResidenceNo"]
    assert personal["AlternateAddress"]["CityOrTownOrDistrict"] == personal["Address"]["CityOrTownOrDistrict"]
    assert personal["AlternateAddress"]["PinCode"] == personal["Address"]["PinCode"]


def _validate_against_schema_definition(payload: dict, definition_name: str) -> None:
    """Scoped schema check against one official definitions/<name> block --
    used throughout this push since the full ITR-3 document doesn't
    schema-validate yet (other schedules aren't closed out)."""
    import json
    from jsonschema import Draft4Validator
    schema_path = (
        "Reference Docs by CBDT & ITD/Official JSON Schema/"
        "ITR-3_2026_Main_V1.1 (2).json"
    )
    with open(schema_path, encoding="utf-8") as f:
        full_schema = json.load(f)
    definition = dict(full_schema["definitions"][definition_name])
    definition["definitions"] = full_schema["definitions"]
    errors = sorted(Draft4Validator(definition).iter_errors(payload), key=lambda e: e.path)
    assert not errors, [e.message for e in errors]


def test_itr3_filing_status_old_regime_currently_filing_reaches_json() -> None:
    """Schedule 2 (Filing Status, A19): the A23(B) branch -- taxpayer never
    filed Form 10-IEA in an earlier AY for the old regime, and is filing
    Form 10-IEA for the OLD regime this year -- reaches the JSON, and the
    mutually-exclusive A23(A) "new regime" branch fields are NOT emitted
    alongside it (CBDT rule #353-364 / live-verified for ITR-4: emitting
    both branches at once is rejected outright)."""
    draft = _draft_with_business()
    draft.filing.form10IEAEarlierAYOldRegime = "N"
    draft.filing.form10IEACurrentAYOldRegime = True
    draft.filing.form10IEACurrentAYOldRegimeDate = "2026-07-15"
    draft.filing.form10IEACurrentAYOldRegimeAck = "123456789012345"

    typed_input, _breakdown = draft_to_itr3_input(draft)
    assert typed_input.form_10iea_earlier_ay_old_regime == "N"
    assert typed_input.f10iea_curr_ay_old_regime == "Y"

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    filing_status = document["ITR"]["ITR3"]["PartA_GEN1"]["FilingStatus"]
    assert filing_status["Form10IEAEarlierAYOldRegime"] == "N"
    assert filing_status["F10IEACurrAYOldRegime"] == "Y"
    assert filing_status["F10IEADateCurrAYOldTax"] == "2026-07-15"
    assert filing_status["F10IEAAckNoCurrAYOldTax"] == 123456789012345
    # The A23(A) branch must be completely absent -- not just "N".
    assert "F10IEAEarlierAYNewRegime" not in filing_status
    assert "F10IEACurrAYNewRegime" not in filing_status
    assert "Form10IEAAssYear" not in filing_status

    _validate_against_schema_definition(filing_status, "FilingStatus")


def test_itr3_filing_status_earlier_old_regime_then_reentered_new_reaches_json() -> None:
    """The A23(A) branch -- taxpayer filed Form 10-IEA for the old regime in
    an earlier AY, then re-entered the new regime -- reaches the JSON, and
    the A23(B) branch is absent."""
    draft = _draft_with_business()
    draft.filing.form10IEAEarlierAYOldRegime = "Y"
    draft.filing.form10IEAAssessmentYear = "2024-25"
    draft.filing.form10IEAEarlierAYAckOldRegime = "123456789012340"
    draft.filing.form10IEAEarlierAYNewRegime = "N"
    draft.filing.form10IEACurrentAYNewRegime = True
    draft.filing.form10IEACurrentAYNewRegimeDate = "2026-07-20"
    draft.filing.form10IEACurrentAYNewRegimeAck = "223456789012345"

    typed_input, _breakdown = draft_to_itr3_input(draft)

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    filing_status = document["ITR"]["ITR3"]["PartA_GEN1"]["FilingStatus"]
    assert filing_status["Form10IEAEarlierAYOldRegime"] == "Y"
    assert filing_status["Form10IEAAssYear"] == "2024-25"
    assert filing_status["Form10IEAEarlierAYAckOldRegime"] == 123456789012340
    assert filing_status["F10IEAEarlierAYNewRegime"] == "N"
    assert filing_status["F10IEACurrAYNewRegime"] == "Y"
    assert filing_status["F10IEADateCurrAYNewTax"] == "2026-07-20"
    assert "F10IEACurrAYOldRegime" not in filing_status

    _validate_against_schema_definition(filing_status, "FilingStatus")


def test_itr3_filing_status_seventh_proviso_representative_director_partner_reach_json() -> None:
    """Every other A19 sub-item -- seventh proviso, residential-status
    conditions/jurisdiction, 115H, representative, director, partner-in-
    firm, unlisted equity (with a genuine closing balance, not a copy of
    opening+acquired), PE/SEP, IFSC flag, FII/FPI+SEBI, LEI -- reaches the
    typed input and the emitted JSON."""
    draft = _draft_with_business()
    draft.personal.residentialStatus = "NR"
    draft.filing.seventhProvisoApplies = True
    draft.filing.seventhProviso.depositExceedsOneCrore = True
    draft.filing.seventhProviso.depositAmount = Decimal("15000000")
    draft.filing.seventhProviso.otherClauseIV = True
    from app.schemas.return_draft import SeventhProvisoClause
    draft.filing.seventhProviso.clauseIVDetails = [
        SeventhProvisoClause(nature="1", amount=Decimal("6500000")),
    ]
    draft.filing.conditionsResStatus = "5"
    from app.schemas.return_draft import JurisdictionResidenceEntry
    draft.filing.jurisdictionResidenceEntries = [
        JurisdictionResidenceEntry(jurisdictionCode="2", tin="US-TIN-123"),
    ]
    draft.filing.totalStayIndiaPrevYr = 45
    draft.filing.totalStayIndia4PrecYr = 400
    draft.filing.benefitUs115H = True
    draft.filing.benefitUs115HAnswered = True
    from app.schemas.return_draft import RepresentativeAssessee
    draft.filing.representative = RepresentativeAssessee(
        name="Rep Person", email="rep@example.com", mobileCountryCode="91", mobile="9988776655",
    )
    draft.personal.isDirector = True
    from app.schemas.return_draft import CompanyDirectorEntry
    draft.personal.companyDirectorEntries = [
        CompanyDirectorEntry(companyName="Acme Pvt Ltd", companyType="D", pan="ACMEP1234A", sharesType="U", din="12345678"),
    ]
    draft.filing.isPartnerInFirm = True
    from app.schemas.return_draft import PartnerInFirmEntry
    draft.filing.partnerInFirmEntries = [PartnerInFirmEntry(firmName="Sharma & Co", pan="SHRMP1234B")]
    draft.personal.holdsUnlistedShares = True
    from app.schemas.return_draft import UnlistedEquityEntry
    draft.personal.unlistedEquityEntries = [
        UnlistedEquityEntry(
            companyName="Beta Pvt Ltd", companyType="D", openingShares=Decimal("100"),
            openingCost=Decimal("10000"), acquiredShares=Decimal("50"), transferredShares=Decimal("30"),
            transferSaleConsideration=Decimal("6000"), closingShares=Decimal("120"), closingCost=Decimal("13000"),
        ),
    ]
    draft.filing.nriPEinIndia = "Y"
    draft.filing.nriSEPinIndia = "Y"
    draft.filing.aggrPaymentTransac = Decimal("500000")
    draft.filing.numberOfUsers = 200
    draft.filing.foreignExchangeFlag = "Y"
    draft.filing.isFiiFpi = True
    draft.filing.sebiRegistrationNumber = "INABFP123456"
    draft.filing.leiNumber = "1234567890ABCDEFGH12"
    draft.filing.leiValidUptoDate = "2027-03-31"

    typed_input, _breakdown = draft_to_itr3_input(draft)
    assert typed_input.seventh_proviso_139 is True
    assert typed_input.is_company_director is True
    assert typed_input.is_partner_in_firm is True
    assert typed_input.held_unlisted_equity is True
    assert typed_input.is_fii_fpi is True

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    fs = document["ITR"]["ITR3"]["PartA_GEN1"]["FilingStatus"]

    assert fs["SeventhProvisio139"] == "Y"
    assert fs["DepAmtAggAmtExcd1CrPrYrFlg"] == "Y"
    assert fs["AmtSeventhProvisio139i"] == 15000000
    assert fs["clauseiv7provisio139i"] == "Y"
    assert fs["clauseiv7provisio139iDtls"] == [{"clauseiv7provisio139iNature": "1", "clauseiv7provisio139iAmount": 6500000}]
    assert fs["ConditionsResStatus"] == "5"
    assert fs["JurisdictionResPrevYr"]["JurisdictionResPrevYrDtls"] == [{"JurisdictionResidence": "2", "TIN": "US-TIN-123"}]
    assert fs["TotalPrStayIndiaPrevYr"] == 45
    assert fs["TotalPrStayIndia4PrecYr"] == 400
    assert fs["BenefitUs115HFlg"] == "Y"
    assert fs["AsseseeRepFlg"] == "Y"
    assert fs["AssesseeRep"] == {
        "RepName": "Rep Person", "RepEmailID": "rep@example.com",
        "CountryCodeRepMobileNo": 91, "RepMobileNo": 9988776655,
    }
    assert fs["CompDirectorPrvYrFlg"] == "Y"
    assert fs["CompDirectorPrvYr"]["CompDirectorPrvYrDtls"] == [
        {"NameOfCompany": "Acme Pvt Ltd", "CompanyType": "D", "SharesTypes": "U", "PAN": "ACMEP1234A", "DIN": "12345678"},
    ]
    assert fs["PartnerInFirmFlg"] == "Y"
    assert fs["PartnerInFirm"]["PartnerInFirmDtls"] == [{"NameOfFirm": "Sharma & Co", "PAN": "SHRMP1234B"}]
    assert fs["HeldUnlistedEqShrPrYrFlg"] == "Y"
    unlisted = fs["HeldUnlistedEqShrPrYr"]["HeldUnlistedEqShrPrYrDtls"][0]
    assert unlisted["OpngBalNumberOfShares"] == 100
    assert unlisted["ClsngBalNumberOfShares"] == 120
    assert unlisted["ClsngBalCostOfAcquisition"] == 13000
    assert unlisted["ShrTrnfNumberOfShares"] == 30
    assert unlisted["ShrTrnfSaleConsideration"] == 6000
    assert fs["NriPEinIndia"] == "Y"
    assert fs["NriSEPinIndia"] == "Y"
    assert fs["AggrPaymentTransac"] == 500000
    assert fs["NumberOfUsers"] == 200
    assert fs["ForeignExchangeFlag"] == "Y"
    assert fs["FiiFpiFlag"] == "Y"
    assert fs["SebiRegnNo"] == "INABFP123456"
    assert fs["LEIDtls"] == {"LEINumber": "1234567890ABCDEFGH12", "ValidUptoDate": "2027-03-31"}

    _validate_against_schema_definition(fs, "FilingStatus")


def test_itr3_audit_info_full_44ab_disclosure_reaches_json() -> None:
    """Schedule 3 (Audit Information, A20): the full 44AB/92E/other-audit
    disclosure -- turnover band, cash-receipt/payment percentage bands,
    the 44AB liability reason, presumptive-section sub-flags, the actual
    audit-report detail (date/ack/auditor name/PAN/Aadhaar), the 92E audit
    detail, and both "other audit report" arrays -- reaches typed input and
    the emitted JSON. Previously AgrOFAllAmtsRcvd/AgrOFAllPayMade were
    hardcoded to "Upto5Per" regardless of the real return, and every other
    field here was silently dropped."""
    draft = _draft_with_business()
    draft.itr3AuditInfo.liableSec44AA = "Y"
    draft.itr3AuditInfo.incomeDeclaredUnderPresumptive = "Y"
    draft.itr3AuditInfo.totalSalesBand = "Upto10CR"
    draft.itr3AuditInfo.receiptsCashBand = "MoreThan5Per"
    draft.itr3AuditInfo.paymentsCashBand = "Upto5Per"
    draft.itr3AuditInfo.liableSec44AB = "Y"
    draft.itr3AuditInfo.condition44AB = "bii"
    draft.itr3AuditInfo.presumptive44AD = "Y"
    draft.itr3AuditInfo.presumptive44ADA = "N"
    draft.itr3AuditInfo.accountAudit = "Y"
    draft.itr3AuditInfo.auditAccountant = "Y"
    draft.itr3AuditInfo.auditReportFurnishDate = "2026-08-15"
    draft.itr3AuditInfo.acknowledgement44AB = "123456789012345"
    draft.itr3AuditInfo.auditorName = "Kapoor & Associates"
    draft.itr3AuditInfo.auditorPAN = "KAPOP1234A"
    draft.itr3AuditInfo.liableSec92E = "Y"
    draft.itr3AuditInfo.auditedUnder92E = "Y"
    draft.itr3AuditInfo.auditReport92EDate = "2026-08-20"
    draft.itr3AuditInfo.acknowledgement92E = "223456789012345"
    from app.schemas.return_draft import OtherAuditReportEntry, AuditUnderOtherActEntry
    draft.itr3AuditInfo.otherAuditReportEntries = [
        OtherAuditReportEntry(auditedSection="80-IA", auditFlag="Y", dateOfAudit="2026-08-10", ackNumOth="323456789012345"),
    ]
    draft.itr3AuditInfo.auditUnderOtherActEntries = [
        AuditUnderOtherActEntry(act="6", auditedSection="143", dateOfAudit="2026-08-05"),
    ]

    typed_input, _breakdown = draft_to_itr3_input(draft)
    audit = typed_input.audit_info
    assert audit.total_sales_band == "Upto10CR"
    assert audit.receipts_cash_band == "MoreThan5Per"
    assert audit.condition_44ab == "bii"
    assert audit.presumptive_44ad is True
    assert audit.auditor_firm_pan == "KAPOP1234A"
    assert len(audit.other_section_audit_entries) == 1
    assert len(audit.other_act_audit_entries) == 1

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    ai = document["ITR"]["ITR3"]["PartA_GEN2"]["AuditInfo"]

    assert ai["TotalSalesExcOneCr"] == "Upto10CR"
    assert ai["AgrOFAllAmtsRcvd"] == "MoreThan5Per"
    assert ai["AgrOFAllPayMade"] == "Upto5Per"
    assert ai["Cndnfor44AB"] == "bii"
    assert ai["BiiDetails"] == {"44AD": "Y", "44ADA": "N", "44AE": "N", "44BB": "N"}
    assert ai["AuditAccountantFlg"] == "Y"
    assert ai["AuditReportFurnishDate"] == "2026-08-15"
    assert ai["AckNum44AB"] == 123456789012345
    assert ai["AudFrmName"] == "Kapoor & Associates"
    assert ai["AudFrmPAN"] == "KAPOP1234A"
    assert ai["AuditDetails92E"] == {"DateOfAudit": "2026-08-20", "AckNum92E": 223456789012345}
    assert ai["AuditDetails"] == [
        {"AuditedSection": "80-IA", "AuditFlag": "Y", "OthAuditDtls": "Y", "DateOfAudit": "2026-08-10", "AckNumOth": 323456789012345},
    ]
    assert ai["AuditReportDetails"] == [
        {"AuditReportAct": "6", "AuditedSection": "143", "OtherITActFlag": "Y", "OthAuditDtlsOthThanITAct": "Y", "DateOfAudit": "2026-08-05"},
    ]

    _validate_against_schema_definition(ai, "AuditInfo")


def test_itr3_audit_info_not_audited_omits_report_detail_not_fabricates() -> None:
    """A taxpayer not liable for audit must not get a fabricated audit-report
    date/ack/auditor -- these fields should simply be absent, matching this
    codebase's fail-closed/no-placeholder discipline."""
    draft = _draft_with_business()
    draft.itr3AuditInfo.liableSec44AB = "N"
    draft.itr3AuditInfo.accountAudit = "N"
    draft.itr3AuditInfo.auditAccountant = "N"

    typed_input, _breakdown = draft_to_itr3_input(draft)

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    ai = document["ITR"]["ITR3"]["PartA_GEN2"]["AuditInfo"]
    assert ai["LiableSec44ABflg"] == "N"
    assert ai["AuditAccountantFlg"] == "N"
    assert "AuditReportFurnishDate" not in ai
    assert "AckNum44AB" not in ai
    assert "AudFrmName" not in ai
    assert "AuditDetails92E" not in ai

    _validate_against_schema_definition(ai, "AuditInfo")


def test_itr3_balance_sheet_minimal_draft_now_schema_valid() -> None:
    """Schedule 5 (Part A-BS): a minimal draft with no workspace/legacy
    balance-sheet data at all previously produced a PARTA_BS missing more
    than a dozen schema-required properties (confirmed live via direct
    Draft4Validator errors: FundApply.Investments, FundApply.MiscAdjust,
    FundApply.CurrAssetLoanAdv.{CurrAsset,LoanAdv,CurrLiabilitiesProv,
    NetCurrAsset}, FundApply.FixedAsset.{GrossBlock,Depreciation,NetBlock,
    CapWrkProg}, FundSrc.{LoanFunds,DeferredTax,Advances}, FundSrc.PropFund.
    {PropCap,ResrNSurp} were all absent). The same minimal draft must now
    produce a fully schema-valid PARTA_BS, every required block present
    and defaulting to 0."""
    draft = _draft_with_business()

    typed_input, _breakdown = draft_to_itr3_input(draft)
    assert typed_input.balance_sheet is not None
    assert typed_input.balance_sheet.official is not None

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    parta_bs = document["ITR"]["ITR3"]["PARTA_BS"]

    _validate_against_schema_definition(parta_bs, "PARTA_BS")


def test_itr3_balance_sheet_workspace_investments_and_misc_adjust_reach_json() -> None:
    """The rich workspace path: Investments (long-term + trade), loans and
    advances, miscellaneous adjustments, and net current assets -- all
    previously absent from the builder output entirely -- reach the JSON
    for real."""
    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {
        "PARTA_BS": {
            "FundSrc": {
                "PropFund": {"PropCap": 500000, "ResrNSurp": {"RevResr": 0, "CapResr": 0, "StatResr": 0, "OthResr": 0, "TotResrNSurp": 0}, "TotPropFund": 500000},
                "LoanFunds": {"SecrLoan": {"ForeignCurrLoan": 0, "RupeeLoan": {"FrmBank": 100000, "FrmOthrs": 0, "TotRupeeLoan": 100000}, "TotSecrLoan": 100000}, "UnsecrLoan": {"FrmBank": 0, "FrmOthrs": 0, "TotUnSecrLoan": 0}, "TotLoanFund": 100000},
                "DeferredTax": 0, "Advances": {"FromPrsn": 0, "FromOthers": 0, "TotalAdvances": 0},
                "TotFundSrc": 600000,
            },
            "FundApply": {
                "FixedAsset": {"GrossBlock": 200000, "Depreciation": 40000, "NetBlock": 160000, "CapWrkProg": 0, "TotFixedAsset": 160000},
                "Investments": {
                    "LongTermInv": {"GovtOthSecQuoted": 30000, "GovOthSecUnQoted": 0, "TotLongTermInv": 30000},
                    "TradeInv": {"EquityShares": 20000, "PreferShares": 0, "Debenture": 0, "TotTradeInv": 20000},
                    "TotInvestments": 50000,
                },
                "CurrAssetLoanAdv": {
                    "CurrAsset": {"Inventories": {"StoresConsumables": 0, "RawMatl": 0, "StkInProcess": 0, "FinOrTradGood": 0, "TotInventries": 0}, "SndryDebtors": 100000, "CashOrBankBal": {"CashinHand": 5000, "BankBal": 95000, "TotCashOrBankBal": 100000}, "OthCurrAsset": 0, "TotCurrAsset": 200000},
                    "LoanAdv": {"AdvRecoverable": 15000, "Deposits": 25000, "BalWithRevAuth": 0, "TotLoanAdv": 40000},
                    "CurrLiabilitiesProv": {"CurrLiabilities": {"SundryCred": 50000, "LiabForLeasedAsset": 0, "AccrIntonLeasedAsset": 0, "AccrIntNotDue": 0, "TotCurrLiabilities": 50000}, "Provisions": {"ITProvision": 0, "ELSuperAnnGratProvision": 0, "OthProvision": 0, "TotProvisions": 0}, "TotCurrLiabilitiesProvision": 50000},
                    "TotCurrAssetLoanAdv": 240000, "NetCurrAsset": 190000,
                },
                "MiscAdjust": {"MiscExpndr": 5000, "DefTaxAsset": 2000, "AccumaltedLosses": 0, "TotMiscAdjust": 7000},
                "TotFundApply": 407000,
            },
        }
    }

    typed_input, _breakdown = draft_to_itr3_input(draft)
    official = typed_input.balance_sheet.official
    assert official.investments.total == Decimal("50000")
    assert official.loan_advances.total == Decimal("40000")
    assert official.misc_adjust.total == Decimal("7000")
    assert official.net_current_asset == Decimal("190000")

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    fund_apply = document["ITR"]["ITR3"]["PARTA_BS"]["FundApply"]
    assert fund_apply["Investments"]["TotInvestments"] == 50000
    assert fund_apply["Investments"]["LongTermInv"]["GovtOthSecQuoted"] == 30000
    assert fund_apply["Investments"]["TradeInv"]["EquityShares"] == 20000
    assert fund_apply["CurrAssetLoanAdv"]["LoanAdv"]["AdvRecoverable"] == 15000
    assert fund_apply["CurrAssetLoanAdv"]["NetCurrAsset"] == 190000
    assert fund_apply["MiscAdjust"]["MiscExpndr"] == 5000
    assert document["ITR"]["ITR3"]["PARTA_BS"]["FundSrc"]["LoanFunds"]["TotLoanFund"] == 100000

    _validate_against_schema_definition(document["ITR"]["ITR3"]["PARTA_BS"], "PARTA_BS")


def test_itr3_balance_sheet_no_books_case_reaches_json() -> None:
    """Form item 6 (a)-(d), the "no account case" -- used when regular
    books of account are not maintained -- was never emitted at all,
    regardless of data source. A filer who marks noBooksOfAccounts must
    get a real NoBooksOfAccBS block."""
    draft = _draft_with_business()
    draft.itr3BalanceSheet.noBooksOfAccounts = True
    draft.itr3BalanceSheet.noBooksSundryDebtors = Decimal("40000")
    draft.itr3BalanceSheet.noBooksSundryCreditors = Decimal("25000")
    draft.itr3BalanceSheet.noBooksStockInTrade = Decimal("60000")
    draft.itr3BalanceSheet.noBooksCashBalance = Decimal("8000")

    typed_input, _breakdown = draft_to_itr3_input(draft)
    assert typed_input.balance_sheet.official.no_books is not None
    assert typed_input.balance_sheet.official.no_books.sundry_debtors == Decimal("40000")

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    parta_bs = document["ITR"]["ITR3"]["PARTA_BS"]
    assert parta_bs["NoBooksOfAccBS"] == {
        "TotSundryDbtAmt": 40000, "TotSundryCrdAmt": 25000,
        "TotStkInTradAmt": 60000, "CashBalAmt": 8000,
    }

    _validate_against_schema_definition(parta_bs, "PARTA_BS")


def test_itr3_nature_of_business_trade_name_reaches_json() -> None:
    """Schedule 4 (Nature of Business or Profession): the "Trade name of
    the proprietorship, if any" column was silently dropped end-to-end
    despite the draft already capturing it -- confirmed here directly."""
    draft = _draft_with_business()
    from app.schemas.return_draft import ITR3NatureOfBusiness
    draft.itr3NatureOfBusiness = [
        ITR3NatureOfBusiness(code="14001", tradeName="Acme Software Works", description="Custom software development"),
    ]

    typed_input, _breakdown = draft_to_itr3_input(draft)
    assert typed_input.nature_of_business[0].trade_name == "Acme Software Works"

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    rows = document["ITR"]["ITR3"]["PartA_GEN2"]["NatOfBus"]["NatureOfBusiness"]
    assert rows == [{
        "Code": "14001", "TradeName1": "Acme Software Works",
        "Description": "Custom software development",
    }]

    _validate_against_schema_definition({"NatureOfBusiness": rows}, "NatOfBus")


def test_itr3_nature_of_business_disambiguated_codes_not_silently_dropped() -> None:
    """The three official disambiguation codes (16019_1 Medical Profession,
    20023_1 Sports Management, 21008_1 Event Management) are real, valid
    CBDT enum values distinct from their un-suffixed base codes -- a filer
    who is a doctor/sports manager/event manager and correctly selects the
    disambiguated code must not have that row silently vanish."""
    draft = _draft_with_business()
    from app.schemas.return_draft import ITR3NatureOfBusiness
    draft.itr3NatureOfBusiness = [
        ITR3NatureOfBusiness(code="16019_1", description="Medical practice"),
        ITR3NatureOfBusiness(code="20023_1", description="Sports management"),
        ITR3NatureOfBusiness(code="21008_1", description="Event management"),
    ]

    typed_input, _breakdown = draft_to_itr3_input(draft)
    codes = {row.code for row in typed_input.nature_of_business}
    assert codes == {"16019_1", "20023_1", "21008_1"}

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    rows = document["ITR"]["ITR3"]["PartA_GEN2"]["NatOfBus"]["NatureOfBusiness"]
    assert {row["Code"] for row in rows} == {"16019_1", "20023_1", "21008_1"}

    _validate_against_schema_definition({"NatureOfBusiness": rows}, "NatOfBus")


def test_itr3_nri_112_115_securities_reach_cg_transactions_and_json() -> None:
    """Schedule CG item B6 (``ltNri112115``) had no mapper for ITR-3 at
    all, and the corresponding ``NRIOnSec112and115`` JSON block was
    entirely absent from the builder (unlike its STCG sibling
    ``NRISecur115AD``, which correctly stays empty for ITR-3 since section
    115AD is FII/FPI-specific and ITR-3 filers -- individuals/HUF -- can
    never be an FII/FPI entity). This is a genuine gap in ITR-3's own
    official schema coverage, not a by-design omission: confirmed the
    field exists identically in ITR-3's own JSON schema by direct
    introspection."""
    draft = _draft_with_business()
    draft.capitalGainsSchedule.ltNri112115 = [{
        "sectionCode": "5AC1c", "fullConsideration": Decimal("800000"),
        "acquisitionCost": Decimal("200000"), "transferExpenses": Decimal("3000"),
        "deduction54F": Decimal("50000"),
    }]
    typed_input, _breakdown = draft_to_itr3_input(draft)
    matching = [tx for tx in typed_input.cg_transactions if tx.is_nri_unquoted_shares_disposal]
    assert len(matching) == 1
    assert matching[0].section_code == "115AC"

    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    cg = document["ITR"]["ITR3"]["ScheduleCGFor23"]
    nri_dtls = cg["LongTermCapGain23"]["NRIOnSec112and115"]["NRIOnSec112and115Dtls"]
    assert len(nri_dtls) == 1
    assert nri_dtls[0]["SectionCode"] == "5AC1c"
    assert nri_dtls[0]["FullConsideration"] == 800000
    assert nri_dtls[0]["DeductSec48"]["AquisitCost"] == 200000


def test_itr3_mapper_uses_schedule_bp_workspace_values() -> None:
    """Persisted Schedule BP values override the presumptive fallback fields."""
    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {
        "ITR3ScheduleBP": {
            "BusinessIncOthThanSpec": {
                "ProfBfrTaxPL": 125000,
                "AmtDebPLDisallowUs36": 1500,
                "AmtDebPLDisallowUs40A": 2500,
                "DeemIncUs41": 700,
                "DeductUs32_1_iii": 300,
                "IncProfDecLossAccICDSAdj": 400,
                "DecProfIncLossAccICDSAdj": 100,
            }
        }
    }
    typed_input, breakdown = draft_to_itr3_input(draft)
    assert typed_input.business_income is not None
    assert typed_input.business_income.net_profit_before_tax == Decimal("125000")
    assert typed_input.business_income.disallowance_us36 == Decimal("1500")
    assert typed_input.business_income.disallowance_us40a == Decimal("2500")
    assert typed_input.business_income.deemed_income_us41 == Decimal("700")
    assert typed_input.business_income.deduction_us32_1_iii == Decimal("300")
    assert typed_input.business_income.icds_increase == Decimal("400")
    assert typed_input.business_income.icds_decrease == Decimal("100")
    assert breakdown["business_income"] == Decimal("125000")


def test_itr3_mapper_preserves_part_a_pl_workspace_values() -> None:
    """The typed input preserves required PARTA_PL workspace totals."""
    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {
        "PARTA_PL": {
            "GrossProfit": 240000,
            "Expenditure": 90000,
            "NetIncomeFrmSpecActivity": 12000,
            "TurnverFrmSpecActivity": 300000,
            "NoBooksOfAccPL": {"GrossReceipt": 400000, "GrossProfit": 150000, "Expenses": 50000, "NetProfit": 100000},
            "TaxProvAppr": {"ProvForCurrTax": 20000, "ProvDefTax": 5000, "ProfitAfterTax": 75000},
            "CreditsToPL": {"GrossProfitTrnsfFrmTrdAcc": 240000, "TotCreditsToPL": 252000, "OthIncome": {"TotOthIncome": 12000}},
            "DebitsToPL": {"OtherExpenses": 90000, "PBT": 162000},
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.profit_and_loss is not None
    assert typed_input.profit_and_loss.gross_profit == Decimal("240000")
    assert typed_input.profit_and_loss.no_books_net_profit == Decimal("100000")
    assert typed_input.profit_and_loss.profit_before_tax == Decimal("162000")
    assert typed_input.profit_and_loss.other_income_breakdown.dividends == Decimal("0")


def test_itr3_mapper_and_builder_preserve_part_a_pl_credit_debit_breakdown() -> None:
    """Mapped PARTA_PL credits and interest debits reach official integer paths."""
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {"PARTA_PL": {
        "CreditsToPL": {"OthIncome": {"RentInc": 1100, "Dividends": 2200, "InterestInc": 3300, "MiscOthIncome": 4400, "TotOthIncome": 11000}, "TotCreditsToPL": 15000},
        "DebitsToPL": {"InterestExpdrtDtls": {"InterestExpdr": 7700, "NonResOtherCompany": 1200, "Others": 6500}},
    }}
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.profit_and_loss is not None
    assert typed_input.profit_and_loss.other_income_breakdown.rent_income == Decimal("1100")
    assert typed_input.profit_and_loss.interest_expense.total == Decimal("7700")
    payload = build_itr3_json(compute_itr3(typed_input), typed_input)["ITR"]["ITR3"]["PARTA_PL"]
    assert payload["CreditsToPL"]["OthIncome"]["Dividends"] == 2200
    assert payload["CreditsToPL"]["OthIncome"]["MiscOthIncome"] == 4400
    assert payload["DebitsToPL"]["InterestExpdrtDtls"] == {"InterestExpdr": 7700, "NonResOtherCompany": 1200, "Others": 6500}


def test_itr3_builder_preserves_parta_pl_pbidta_and_depreciation() -> None:
    """PARTA_PL carries form rows 50 and 52 instead of hard-coded zeroes."""
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {
        "PARTA_PL": {
            "DebitsToPL": {
                "PBIDTA": 161000,
                "DepreciationAmort": 9000,
                "PBT": 152000,
            }
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    payload = build_itr3_json(compute_itr3(typed_input), typed_input)["ITR"]["ITR3"]["PARTA_PL"]
    assert payload["DebitsToPL"]["PBIDTA"] == 161000
    assert payload["DebitsToPL"]["DepreciationAmort"] == 9000
    assert payload["DebitsToPL"]["PBT"] == 152000


def test_itr3_builder_uses_part_a_pl_workspace_data() -> None:
    """PARTA_PL JSON carries typed workspace totals instead of hardcoded zeros."""
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {"PARTA_PL": {"GrossProfit": 240000, "Expenditure": 90000, "NetIncomeFrmSpecActivity": 12000, "TurnverFrmSpecActivity": 300000}}
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    pl = document["ITR"]["ITR3"]["PARTA_PL"]
    assert pl["GrossProfit"] == 240000
    assert pl["Expenditure"] == 90000
    assert pl["NetIncomeFrmSpecActivity"] == 12000
    assert pl["TurnverFrmSpecActivity"] == 300000


def test_itr3_builder_maps_parta_gen2_workspace() -> None:
    """Part A-GEN2 JSON carries mapped audit and nature-of-business data."""
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _draft_with_business()
    draft.itr3AuditInfo.accountAudit = "Y"
    draft.itr3AuditInfo.liableSec44AB = "Y"
    draft.itr3AuditInfo.incomeDeclaredUnderPresumptive = "Y"
    draft.itr3NatureOfBusiness = [ITR3NatureOfBusiness(code="14001", tradeName="Tech", description="Software")]
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    gen2 = document["ITR"]["ITR3"]["PartA_GEN2"]
    assert gen2["AuditInfo"]["AccountAuditFlag"] == "Y"
    assert gen2["AuditInfo"]["LiableSec44ABflg"] == "Y"
    assert gen2["AuditInfo"]["IncDclrdUs"] == "Y"
    # TradeName1 ("Tech") was previously silently dropped despite being set
    # on the draft -- see the dedicated Schedule 4 tests below for the
    # fail-pre-fix proof; this pre-existing test's own data already
    # exercised the bug without ever asserting on it.
    assert gen2["NatOfBus"]["NatureOfBusiness"] == [
        {"Code": "14001", "TradeName1": "Tech", "Description": "Software"}
    ]


def test_itr3_mapper_preserves_manufacturing_and_trading_accounts() -> None:
    """Official account schedules remain typed and lossless at field level."""
    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {
        "ManufacturingAccount": {
            "OpeningInventory": {"OpngStckRawMat": 10000, "Purchases": 50000, "TotalDebtsManfctrngAcc": 70000},
            "ClosingStock": {"ClsngStckRawMaterial": 5000, "ClsngStckTotal": 5000},
            "CostOfGoodsPrdcd": 65000,
        },
        "TradingAccount": {"OperatingRevenueTotal": 300000, "SalesGrossReceiptsTotal": 300000, "TotRevenueFrmOperations": 300000, "TardingAccTotCred": 305000, "DirectExpenses": 150000, "GrossProfitFrmBusProf": 155000},
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.business_accounts is not None
    assert typed_input.business_accounts.manufacturing_account is not None
    assert typed_input.business_accounts.manufacturing_account.cost_of_goods_produced == Decimal("65000")
    assert typed_input.business_accounts.trading_account is not None
    assert typed_input.business_accounts.trading_account.values["GrossProfitFrmBusProf"] == Decimal("155000")


def test_itr3_builder_emits_manufacturing_and_trading_schedules() -> None:
    """The builder emits exact official schedule names and nesting."""
    from app.engine.calculators.itr3 import compute as compute_itr3
    from app.engine.itd.itr3 import build_itr3_json

    draft = _draft_with_business()
    draft.itr3BusinessWorkspace.core = {"ManufacturingAccount": {"OpeningInventory": {"OpngStckRawMat": 10000}, "ClosingStock": {"ClsngStckTotal": 5000}, "CostOfGoodsPrdcd": 65000}, "TradingAccount": {"OperatingRevenueTotal": 300000, "SalesGrossReceiptsTotal": 300000, "TotRevenueFrmOperations": 300000, "TardingAccTotCred": 305000, "DirectExpenses": 150000}}
    typed_input, _ = draft_to_itr3_input(draft)
    payload = build_itr3_json(compute_itr3(typed_input), typed_input)["ITR"]["ITR3"]
    assert payload["ManufacturingAccount"]["OpeningInventory"]["OpngStckRawMat"] == 10000
    assert payload["ManufacturingAccount"]["CostOfGoodsPrdcd"] == 65000
    assert payload["TradingAccount"]["OperatingRevenueTotal"] == 300000
    assert payload["TradingAccount"]["DirectExpenses"] == 150000


    """Official workspace schedules are authoritative over duplicate legacy fields."""
    draft = _draft_with_business()
    draft.itr3AuditInfo.accountAudit = "N"
    draft.itr3NatureOfBusiness = [ITR3NatureOfBusiness(code="14001", tradeName="Legacy", description="Legacy")]
    draft.itr3BusinessWorkspace.core = {
        "PartA_GEN2": {
            "AuditInfo": {"AccountAuditFlag": "Y", "LiableSec44ABflg": "Y", "IncDclrdUs": "Y"},
            "NatOfBus": {"NatureOfBusiness": [{"Code": "16001", "Description": "Legal profession"}]},
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.audit_info is not None and typed_input.audit_info.account_audited is True
    assert typed_input.nature_of_business is not None
    assert typed_input.nature_of_business[0].code == "16001"


def test_itr3_mapper_prefers_workspace_balance_sheet_over_legacy_fields() -> None:
    """PARTA_BS workspace totals are authoritative over the duplicate summary."""
    draft = _draft_with_business()
    draft.itr3BalanceSheet.totalSources = Decimal("999")
    draft.itr3BusinessWorkspace.core = {
        "PARTA_BS": {
            "FundSrc": {
                "PropFund": {"TotPropFund": 700000},
                "LoanFunds": {"SecrLoan": {"TotSecrLoan": 100000}, "UnsecrLoan": {"TotUnSecrLoan": 50000}},
                "TotFundSrc": 850000,
            },
            "FundApply": {"FixedAsset": {"TotFixedAsset": 500000}, "CurrAssetLoanAdv": {"TotCurrAssetLoanAdv": 350000}, "TotFundApply": 850000},
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.balance_sheet is not None
    assert typed_input.balance_sheet.total_liabilities == Decimal("850000")
    assert typed_input.balance_sheet.total_assets == Decimal("850000")


    """The form dispatcher must route ITR-3 to the typed calculator path."""
    result = compute_canonical(_draft_with_business())
    assert isinstance(result, ITR3PipelineResult)
    assert result.summary["computedByFormEngine"] == "ITR-3"


def test_itr3_input_validator_reports_missing_business_income() -> None:
    """The baseline validator blocks an ITR-3 input without PGBP data."""
    typed_input, _ = draft_to_itr3_input(_draft_with_business())
    typed_input.business_income = None
    report = run_input_validation(typed_input)
    assert not report.can_upload
    assert any(item.rule_id == "ITR3-R001" for item in report.blocking_errors)


def test_itr3_input_validator_accepts_canonical_business_input() -> None:
    """A valid canonical foundation input passes the baseline validator."""
    typed_input, _ = draft_to_itr3_input(_draft_with_business())
    report = run_input_validation(typed_input)
    assert report.can_upload


def test_itr3_calculation_validator_accepts_computed_result() -> None:
    """The baseline calculation rules accept the current valid result."""
    pipeline = compute_canonical_itr3(_draft_with_business())
    report = run_calc_validation(pipeline.typed_input, pipeline.computation)
    assert report.can_upload
def test_itr3_schema_validator_reports_json_and_schema_paths() -> None:
    """Malformed documents expose actionable official-schema locations."""
    with pytest.raises(ITR3SchemaValidationError) as exc_info:
        validate_itr3_json({"ITR": {"ITR3": {}}})
    error = exc_info.value.errors[0]
    assert error["path"] == "ITR.ITR3"
    assert error["schema_path"]


def test_itr3_generation_fails_closed_until_builder_is_schema_exact() -> None:
    """The foundation must reject placeholder JSON, never return it as filing JSON."""
    with pytest.raises(FilingGatewayV2Error, match="official JSON generation failed"):
        generate_cbdt_json(_draft_with_business())


def test_itr3_compute_entrypoint_sets_filing_date() -> None:
    """The declared verification date reaches the computation input."""
    pipeline = compute_canonical_itr3(_draft_with_business())
    assert pipeline.typed_input.filing_date is not None
    assert pipeline.typed_input.filing_date.isoformat() == "2026-07-31"
