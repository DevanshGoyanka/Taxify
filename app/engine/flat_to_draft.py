"""One-way adapter from the legacy flat formData blob to ``ReturnDraft``.

This is the Python mirror of the frontend ``adaptLegacyReturn`` in
``frontend/src/domain/returns/legacyAdapter.ts``.  It exists so the legacy
flat-blob CBDT path can delegate to the single canonical mapper
``draft_to_itr1_input`` instead of maintaining a duplicate ~300-line
flat→typed mapper (the legacy ``_build_itr1_input_from_flat`` was deleted
in Phase 7; ``flat_to_draft`` is now the sole flat→canonical converter).

Authority: ``frontend/src/domain/returns/legacyAdapter.ts`` (the canonical
TypeScript adapter).  Field names and alias precedence match that file so a
flat blob that round-trips through the frontend also round-trips here.

Scope: the compute-relevant and ITR-1 filing-profile-relevant fields only.
Exotic ITR-2/3 schedules (DTAA, Section 89A, accumulated PF, special-rate
income, unexplained income) are preserved as best-effort typed lists when
the flat blob carries them, but are not required for ITR-1 compute or CBDT
generation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from pydantic import ValidationError

from app.schemas.return_draft import (
    BankAccount,
    BankAccountType,
    CapitalGainsSchedule,
    DeductionLoan,
    Deductions,
    DividendIncome,
    Employer,
    ExemptIncomeEntry,
    ExemptIncomeCategory,
    ExemptIncomeSubCategory,
    FilingStatus,
    GiftIncome,
    HomeLoan,
    HouseProperty,
    ImportProvenance,
    InterestIncome,
    Investment80C,
    OtherSources,
    PensionContribution80CCC,
    Policy80D,
    PresumptiveBusiness,
    PropertyType,
    ReturnDraft,
    Schedule80GGAEntry,
    Schedule80GGCEntry,
    TaxChallan,
    TaxChallanKind,
    TcsCredit,
    TdsCredit,
    Verification,
    WinningIncome,
    create_empty_draft,
)

JsonRecord = dict[str, Any]

_INTEREST_KINDS = (
    "SAVINGS_BANK", "TERM_DEPOSIT", "IT_REFUND", "POST_OFFICE", "NSC",
    "SCSS", "OTHER", "BONDS", "SECURITIES", "PF_10_11_FIRST",
    "PF_10_11_SECOND", "PF_10_12_FIRST", "PF_10_12_SECOND",
)
_DIVIDEND_SECTIONS = (
    "194", "10(22e)", "10(22f)", "115BBDA", "115BBDAaiii", "115A1ai",
    "115A1aA", "115AC", "115ACA", "115AD1i", "DTAA",
)
_WINNING_TYPES = (
    "LOTTERY", "BETTING", "CARD_GAME", "HORSE_RACE", "ONLINE_GAMING",
    "RACE_HORSE_ACTIVITY", "UNEXPLAINED_115BBE",
)
_PROPERTY_TYPES = ("SELF_OCCUPIED", "LET_OUT", "DEEMED_LET_OUT")
_LOAN_SECTIONS = ("80E", "80EE", "80EEA", "80EEB")
_FILING_SECTIONS = (
    "139(1)", "139(4)", "142(1)", "148", "153C", "139(5)", "139(9)",
    "119(2)(b)",
)


def _is_record(value: Any) -> bool:
    """Return True when value is a dict (not a list)."""
    return isinstance(value, dict)


def _records(value: Any) -> list[JsonRecord]:
    """Return a list of dict elements from a possibly-list value."""
    if isinstance(value, list):
        return [v for v in value if _is_record(v)]
    return []


def _array(source: JsonRecord, key: str) -> list[JsonRecord] | None:
    """Return the dict-elements of source[key] when it is a list."""
    raw = source.get(key)
    if isinstance(raw, list):
        return [v for v in raw if _is_record(v)]
    return None


def _text(value: Any, fallback: str = "") -> str:
    """Coerce a value to a stripped string with a fallback."""
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    return str(value)


def _bool(value: Any, fallback: bool = False) -> bool:
    """Coerce a value to bool, honoring explicit booleans only."""
    if isinstance(value, bool):
        return value
    return fallback


def _money(value: Any) -> Decimal:
    """Parse a non-negative monetary value; 0 for absent/invalid."""
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, (int, float, Decimal)):
        parsed = Decimal(str(value))
    else:
        try:
            parsed = Decimal(str(value).strip())
        except (ValueError, TypeError):
            return Decimal("0")
    if not parsed.is_finite() or parsed < 0:
        return Decimal("0")
    return parsed


def _signed(value: Any) -> Decimal:
    """Parse a signed monetary value; 0 for absent/invalid."""
    if value is None or value == "":
        return Decimal("0")
    try:
        parsed = Decimal(str(value)) if not isinstance(value, (int, float, Decimal)) else Decimal(str(value))
    except (ValueError, TypeError):
        return Decimal("0")
    return parsed if parsed.is_finite() else Decimal("0")


def _integer(value: Any, minimum: int = 0, maximum: int = 2_147_483_647) -> int:
    """Parse a non-negative integer clamped to [minimum, maximum]."""
    parsed = _money(value)
    return max(minimum, min(maximum, int(parsed)))


def _enum(value: Any, allowed: Iterable[str], fallback: str) -> str:
    """Return value when it is in allowed, else fallback."""
    text_value = _text(value)
    return text_value if text_value in tuple(allowed) else fallback


def _item_id(prefix: str, index: int, item: JsonRecord) -> str:
    """Return a deterministic id for a draft element.

    Mirrors the frontend FNV-1a hash so ids match across frontend and backend.
    """
    if isinstance(item.get("id"), str) and item["id"].strip():
        return item["id"]
    import json
    payload = f"{prefix}|{index}|{json.dumps(item, sort_keys=True, default=str)}"
    hash_value = 0x811C9DC5
    for char in payload:
        hash_value ^= ord(char)
        hash_value = (hash_value * 0x01000193) & 0xFFFFFFFF
    return f"{prefix}-{hash_value:08x}"


def _first_money(*keys: str, source: JsonRecord) -> Decimal:
    """Return the first positive monetary value among aliases."""
    for key in keys:
        value = source.get(key)
        if value is None or value == "":
            continue
        parsed = _money(value)
        if parsed > 0:
            return parsed
    return Decimal("0")


def _employer(item: JsonRecord, index: int) -> Employer:
    """Adapt one flat employer row to the typed Employer model."""
    def m(key: str, alias: str | None = None) -> Decimal:
        if alias and key in item:
            return _money(item[key])
        if alias and alias in item:
            return _money(item[alias])
        return _money(item.get(key))

    return Employer(
        id=_item_id("employer", index, item),
        customEmployerName=_text(item.get("customEmployerName")),
        employerName=_text(item.get("employerName"), _text(item.get("customEmployerName"))),
        employerTAN=_text(item.get("employerTAN")),
        natureOfEmployment=_text(item.get("natureOfEmployment")),
        employerAddress=_text(item.get("employerAddress")),
        employerCity=_text(item.get("employerCity")),
        employerStateCode=_text(item.get("employerStateCode")),
        employerPinCode=_text(item.get("employerPinCode")),
        employerZipCode=_text(item.get("employerZipCode")),
        basic=m("basic"), da=m("da"), commission=m("commission"),
        hra=m("hra", "hraReceived"), bonus=m("bonus"), allowances=m("allowances"),
        lta=m("lta"), otherAllowance=m("otherAllowance"), arrearSalary=m("arrearSalary"),
        perquisites=m("perquisites"), profitsInLieu=m("profitsInLieu"),
        rentPaid=m("rentPaid"), city=_text(item.get("city")),
        isMetroCity=_bool(item.get("isMetroCity")),
        isGovernmentEmployee=_bool(item.get("isGovernmentEmployee")),
        isDisabledEmployee=_bool(item.get("isDisabledEmployee")),
        commutedPension=m("commutedPension"), gratuity=m("gratuity"),
        leaveEncashment=m("leaveEncashment"), averageMonthlySalary=m("averageMonthlySalary"),
        yearsOfService=_integer(item.get("yearsOfService")),
        unavailedLeaveDays=_integer(item.get("unavailedLeaveDays")),
        actualLtaFare=m("actualLtaFare"), isDomesticTravel=_bool(item.get("isDomesticTravel")),
        journeysInBlock=_integer(item.get("journeysInBlock")), ltaExempt=m("ltaExempt"),
        numberOfChildren=_integer(item.get("numberOfChildren")),
        gratuityAlsoReceived=_bool(item.get("gratuityAlsoReceived")),
        transportAllowance=m("transportAllowance"),
        childrenEducationAllowance=m("childrenEducationAllowance"),
        hostelExpenditureAllowance=m("hostelExpenditureAllowance"),
        uniformAllowance=m("uniformAllowance"),
        entertainmentAllowance=m("entertainmentAllowance"),
        professionalTax=m("professionalTax", "profTax"),
        vrsCompensation=m("vrsCompensation"),
        retrenchmentCompensation=m("retrenchmentCompensation"),
        otherExempt=m("otherExempt"), tdsDeducted=m("tdsDeducted"),
        employerNPS=m("employerNPS"),
    )


def _home_loan(item: JsonRecord) -> HomeLoan:
    """Adapt one flat home-loan row to the typed HomeLoan model."""
    return HomeLoan(
        lenderType=_enum(item.get("lenderType"), ("B", "I"), "B"),
        lenderName=_text(item.get("lenderName")),
        lenderPAN=_text(item.get("lenderPAN")),
        loanAccountNo=_text(item.get("loanAccountNo")),
        dateOfLoan=_text(item.get("dateOfLoan")),
        totalLoanAmount=_money(item.get("totalLoanAmount")),
        loanOutstandingAmount=_money(item.get("loanOutstandingAmount")),
        interestUs24B=_money(item.get("interestUs24B")),
        constructionCompletionDate=_text(item.get("constructionCompletionDate")),
        completedWithin5Years=_bool(item.get("completedWithin5Years")),
        preConstructionInterest=_money(item.get("preConstructionInterest")),
    )


def _property(item: JsonRecord, index: int) -> HouseProperty:
    """Adapt one flat house-property row to the typed HouseProperty model."""
    raw = _text(item.get("propertyType"), _text(item.get("hpType"))).upper()
    if raw in ("LET_OUT", "LET"):
        property_type = "LET_OUT"
    elif raw == "DEEMED_LET_OUT":
        property_type = "DEEMED_LET_OUT"
    else:
        property_type = "SELF_OCCUPIED"

    tenant_rows = _records(item.get("tenantDetails"))
    legacy_tenant_name = _text(item.get("tenantName"))
    legacy_tenant_pan = _text(item.get("tenantPAN"))
    legacy_tenant_aadhaar = _text(item.get("tenantAadhaar"))
    legacy_tenant: list[JsonRecord] = (
        [{"name": legacy_tenant_name, "pan": legacy_tenant_pan, "aadhaar": legacy_tenant_aadhaar}]
        if legacy_tenant_name or legacy_tenant_pan or legacy_tenant_aadhaar else []
    )
    tenant_source = tenant_rows if tenant_rows else legacy_tenant
    tenant_details = [
        {
            "tenantSNo": _integer(t.get("tenantSNo")) or tenant_index + 1,
            "name": _text(t.get("name")),
            "pan": _text(t.get("pan")),
            "aadhaar": _text(t.get("aadhaar")),
            "panOrTan": _text(t.get("panOrTan"), _text(t.get("pan"))),
        }
        for tenant_index, t in enumerate(tenant_source)
    ]
    return HouseProperty(
        id=_item_id("property", index, item),
        name=_text(item.get("name"), f"Property {index + 1}"),
        propertySequenceNo=_integer(item.get("propertySequenceNo"), 1) or index + 1,
        propertyType=property_type,
        address=_text(item.get("address")),
        premisesName=_text(item.get("premisesName")),
        roadOrStreet=_text(item.get("roadOrStreet")),
        area=_text(item.get("area")),
        city=_text(item.get("city")),
        state=_text(item.get("state")),
        pinCode=_text(item.get("pinCode"), _text(item.get("pincode"))),
        zipCode=_text(item.get("zipCode")),
        countryCode=_text(item.get("countryCode"), "91"),
        propertyIdentificationNo=_text(item.get("propertyIdentificationNo")),
        propertyOwnerType=_enum(item.get("propertyOwnerType"), ("SE", "MI", "SP", "OT"), "SE"),
        propertyOwnerOther=_text(item.get("propertyOwnerOther")),
        ownershipType="JOINT" if _bool(item.get("isCoOwned")) else "SOLE",
        ownershipShare=_money(item.get("ownershipShare")),
        isCoOwned=_bool(item.get("isCoOwned")),
        isPropertyInJointOwnership=_bool(item.get("isCoOwned")),
        coOwners=[
            {
                "coOwnerSNo": co_index + 1,
                "name": _text(co.get("name")),
                "pan": _text(co.get("pan")),
                "aadhaar": _text(co.get("aadhaar")),
                "share": _money(co.get("share")),
            }
            for co_index, co in enumerate(_records(item.get("coOwners")))
        ],
        annualRent=_first_money("annualRent", "grossRent", source=item),
        municipalRateableValue=_money(item.get("municipalRateableValue")),
        fairRentValue=_money(item.get("fairRentValue")),
        standardRent=_money(item.get("standardRent")),
        annualLettingValue=_money(item.get("annualLettingValue")),
        unrealizedRent=_money(item.get("unrealizedRent")),
        arrearsOfRent=_money(item.get("arrearsOfRent")),
        vacancyPeriodMonths=_integer(item.get("vacancyPeriodMonths"), 0, 12),
        municipalTaxesPaid=_first_money("municipalTaxesPaid", "munTax", source=item),
        interestOnLoan=_first_money("interestOnLoan", "homeLoanInt", "sopLoanInt", source=item),
        preConstructionInterest=_money(item.get("preConstructionInterest")),
        lenderName=_text(item.get("lenderName")),
        lenderPAN=_text(item.get("lenderPAN")),
        lenderType=_enum(item.get("lenderType"), ("B", "I"), "B"),
        loanAccountNo=_text(item.get("loanAccountNo")),
        loanSanctionDate=_text(item.get("loanSanctionDate")),
        constructionCompletionDate=_text(item.get("constructionCompletionDate")),
        principalRepayment=_money(item.get("principalRepayment")),
        totalLoanAmount=_money(item.get("totalLoanAmount")),
        loanOutstandingAmount=_money(item.get("loanOutstandingAmount")),
        completedWithin5Years=_bool(item.get("completedWithin5Years")),
        homeLoans=[_home_loan(hl) for hl in _records(item.get("homeLoans"))],
        tenantDetails=tenant_details,
        tenantName=tenant_details[0]["name"] if tenant_details else legacy_tenant_name,
        tenantPAN=tenant_details[0]["pan"] if tenant_details else legacy_tenant_pan,
        tenantAadhaar=tenant_details[0]["aadhaar"] if tenant_details else legacy_tenant_aadhaar,
        passThroughIncome=_money(item.get("passThroughIncome")),
        grossAnnualValue=_money(item.get("grossAnnualValue")),
        netAnnualValue=_money(item.get("netAnnualValue")),
        standardDeduction30Pct=_money(item.get("standardDeduction30Pct")),
        incomeFromHP=_signed(item.get("incomeFromHP")),
        maxRent=_money(item.get("maxRent")),
        preConstructionInterestClaimed=_money(item.get("preConstructionInterestClaimed")),
    )


def _business(item: JsonRecord, index: int) -> PresumptiveBusiness:
    """Adapt one flat business row to the typed PresumptiveBusiness model."""
    scheme = _enum(item.get("scheme"), ("44AD", "44ADA", "44AE"), _text(item.get("bizPresumptive"), "44AD"))
    gst_rows = _array(item, "gstinTurnovers") or _array(item, "gstinTurnoverRows") or []
    common = {
        "id": _item_id("business", index, item),
        "businessName": _text(item.get("businessName")),
        "natureCode": _text(item.get("natureCode"), _text(item.get("nicCode"))),
        "description": _text(item.get("description"), _text(item.get("businessNature"))),
        "declaredIncome": _first_money("declaredIncome", "bizDeclared", source=item),
        "gstinTurnovers": [
            {"id": _item_id("gst", gi, gr), "gstin": _text(gr.get("gstin")), "turnover": _money(gr.get("turnover"))}
            for gi, gr in enumerate(gst_rows)
        ],
    }
    if scheme == "44ADA":
        return PresumptiveBusiness(
            scheme="44ADA", grossReceipts=_first_money("grossReceipts", "bizTurnover", source=item),
            digitalReceipts=_money(item.get("digitalReceipts")),
            nonDigitalReceipts=_money(item.get("nonDigitalReceipts")), **common,
        )
    if scheme == "44AE":
        return PresumptiveBusiness(
            scheme="44AE",
            vehicles=[
                {
                    "id": _item_id("vehicle", vi, v),
                    "vehicleNumber": _text(v.get("vehicleNumber")),
                    "vehicleType": _enum(v.get("vehicleType"), ("HEAVY", "OTHER"), "OTHER"),
                    "tonnage": _money(v.get("tonnage")),
                    "ownedMonths": _integer(v.get("ownedMonths"), 0, 12),
                    "leasedOrHired": _bool(v.get("leasedOrHired")),
                    "ownedLeasedHiredFlag": _enum(
                        v.get("ownedLeasedHiredFlag"),
                        ("OWN", "LEASE", "HIRED"),
                        "HIRED" if _bool(v.get("leasedOrHired")) else "OWN",
                    ),
                    "presumptiveIncome": _money(v.get("presumptiveIncome")),
                }
                for vi, v in enumerate(_records(item.get("vehicles")))
            ], **common,
        )
    digital = _first_money("digitalReceipts", "digitalTurnover", source=item)
    gross_turnover = item.get("grossTurnover")
    if gross_turnover is not None:
        non_digital = max(Decimal("0"), _money(gross_turnover) - digital)
    else:
        non_digital = _money(item.get("bizTurnover"))
    return PresumptiveBusiness(
        scheme="44AD", digitalReceipts=digital, nonDigitalReceipts=non_digital,
        otherModeReceipts=_money(item.get("otherModeReceipts")),
        digitalPresumptiveIncome=_money(item.get("digitalPresumptiveIncome")),
        nonDigitalPresumptiveIncome=_money(item.get("nonDigitalPresumptiveIncome")), **common,
    )


def _interest(item: JsonRecord, index: int) -> InterestIncome:
    """Adapt one flat interest row to the typed InterestIncome model."""
    return InterestIncome(
        id=_item_id("interest", index, item),
        kind=_enum(item.get("kind"), _INTEREST_KINDS, _enum(item.get("itdTag"), _INTEREST_KINDS, "OTHER")),
        grossAmount=_first_money("grossAmount", "amount", "interestEarned", source=item),
        tdsDeducted=_money(item.get("tdsDeducted")),
        bankName=_text(item.get("bankName"), _text(item.get("payerName"))),
        accountType=_enum(item.get("accountType"), ("SAVINGS", "CURRENT", "FD", ""), ""),
        accountNumber=_text(item.get("accountNumber")),
        ifscCode=_text(item.get("ifscCode")),
        postOfficeName=_text(item.get("postOfficeName")),
        accountNumberPO=_text(item.get("accountNumberPO")),
        nscCertificateNumber=_text(item.get("nscCertificateNumber")),
        yearOfPurchase=_integer(item.get("yearOfPurchase")),
        scssAccountNumber=_text(item.get("scssAccountNumber")),
        dateOfOpening=_text(item.get("dateOfOpening")),
        deductorName=_text(item.get("deductorName")),
        deductorTAN=_text(item.get("deductorTAN")),
        remarks=_text(item.get("remarks")),
    )


def _scalar_interest(source: JsonRecord) -> list[JsonRecord]:
    """Project legacy interest scalars into synthetic interest rows."""
    pairs = [
        ("SAVINGS_BANK", "interestSB"), ("TERM_DEPOSIT", "interestFD"),
        ("TERM_DEPOSIT", "interestRD"), ("NSC", "nscInterest"),
        ("SCSS", "scssInterest"), ("POST_OFFICE", "postOfficeInterest"),
        ("IT_REFUND", "incomeFromITRefund"),
        ("PF_10_11_FIRST", "pfInterest10_11_first"),
        ("PF_10_11_SECOND", "pfInterest10_11_second"),
        ("PF_10_12_FIRST", "pfInterest10_12_first"),
        ("PF_10_12_SECOND", "pfInterest10_12_second"),
        ("OTHER", "otherInterest"),
    ]
    return [
        {"kind": kind, "grossAmount": _money(source.get(key))}
        for kind, key in pairs
        if _money(source.get(key)) > 0
    ]


def _dividend(item: JsonRecord, index: int) -> DividendIncome:
    """Adapt one flat dividend row to the typed DividendIncome model."""
    return DividendIncome(
        id=_item_id("dividend", index, item),
        section=_enum(item.get("section"), _DIVIDEND_SECTIONS, "194"),
        grossAmount=_first_money("grossAmount", "dividendAmount", source=item),
        tdsDeducted=_money(item.get("tdsDeducted")),
        companyName=_text(item.get("companyName")),
        companyPAN=_text(item.get("companyPAN")),
        deductorTAN=_text(item.get("deductorTAN")),
        isin=_text(item.get("isin")),
        category=_enum(item.get("category"), ("EQUITY", "PREFERENCE", "MUTUAL_FUND", ""), ""),
        q1=_money(item.get("q1")), q2=_money(item.get("q2")),
        q3=_money(item.get("q3")), q4=_money(item.get("q4")),
        q5=_money(item.get("q5")),
    )


def _winning(item: JsonRecord, index: int) -> WinningIncome:
    """Adapt one flat winnings row to the typed WinningIncome model."""
    return WinningIncome(
        id=_item_id("winning", index, item),
        type=_enum(item.get("type"), _WINNING_TYPES, "LOTTERY"),
        grossAmount=_money(item.get("grossAmount")),
        tdsDeducted=_money(item.get("tdsDeducted")),
        payerName=_text(item.get("payerName")),
        payerTAN=_text(item.get("payerTAN")),
        dateOfWinning=_text(item.get("dateOfWinning")),
        q1=_money(item.get("q1")), q2=_money(item.get("q2")),
        q3=_money(item.get("q3")), q4=_money(item.get("q4")),
        q5=_money(item.get("q5")),
        receipts=_money(item.get("receipts")),
        deductionUs57=_money(item.get("deductionUs57")),
        amountNotDeductibleUs58=_money(item.get("amountNotDeductibleUs58")),
        profitChargeableUs59=_money(item.get("profitChargeableUs59")),
        balance=_money(item.get("balance")),
    )


def _gift(item: JsonRecord, index: int) -> GiftIncome:
    """Adapt one flat gift row to the typed GiftIncome model."""
    return GiftIncome(
        id=_item_id("gift", index, item),
        propertyType=_enum(item.get("propertyType"), ("IMMOVABLE", "CASH", "MOVABLE", "OTHER"), "OTHER"),
        value=_money(item.get("value")),
        donorName=_text(item.get("donorName")),
        donorRelation=_text(item.get("donorRelation")),
        dateOfReceipt=_text(item.get("dateOfReceipt")),
        description=_text(item.get("description")),
        fromRelative=_bool(item.get("fromRelative")),
        receivedOnMarriage=_bool(item.get("receivedOnMarriage")),
        considerationKind=_enum(item.get("considerationKind"), ("WITHOUT_CONSIDERATION", "INADEQUATE_CONSIDERATION"), "WITHOUT_CONSIDERATION"),
        stampDutyValue=_money(item.get("stampDutyValue")),
        considerationPaid=_money(item.get("considerationPaid")),
        fairMarketValue=_money(item.get("fairMarketValue")),
    )


def _investment_80c(item: JsonRecord, index: int) -> Investment80C:
    """Adapt one flat 80C investment row to the typed Investment80C model."""
    return Investment80C(
        id=_item_id("80c", index, item),
        investmentType=_text(item.get("investmentType"), "OTHER"),
        identificationNo=_text(item.get("identificationNo")),
        accountOrPolicyNo=_text(item.get("accountOrPolicyNo")),
        amount=_money(item.get("amount")),
        dateOfInvestment=_text(item.get("dateOfInvestment")),
        institutionName=_text(item.get("institutionName")),
        institutionPAN=_text(item.get("institutionPAN")),
    )


def _pension_80ccc(item: JsonRecord, index: int) -> PensionContribution80CCC:
    """Adapt one official/canonical 80CCC identifier row."""
    return PensionContribution80CCC(
        id=_item_id("80ccc", index, item),
        identifierType=_enum(
            item.get("identifierType", item.get("TypeofIdentifier")),
            ("PRAN", "OTHPRAN"),
            "OTHPRAN",
        ),
        identifierName=_text(
            item.get("identifierName", item.get("NameofIdentifier")),
            _text(item.get("policyNumber")),
        ),
        amount=_money(item.get("amount", item.get("Amount"))),
    )


def _policy_80d(item: JsonRecord, index: int) -> Policy80D:
    """Adapt one flat 80D policy row to the typed Policy80D model."""
    return Policy80D(
        id=_item_id("80d", index, item),
        insurerName=_text(item.get("insurerName")),
        policyNo=_text(item.get("policyNo")),
        premiumAmount=_money(item.get("premiumAmount")),
        policyType=_enum(item.get("policyType"), ("INDIVIDUAL", "FAMILY_FLOATER", "GROUP", "OTHER"), "INDIVIDUAL"),
        dateOfCommencement=_text(item.get("dateOfCommencement")),
    )


def _loan(item: JsonRecord, index: int) -> DeductionLoan:
    """Adapt one flat deduction-loan row to the typed DeductionLoan model."""
    return DeductionLoan(
        id=_item_id("loan", index, item),
        section=_enum(item.get("section"), _LOAN_SECTIONS, "80E"),
        loanTakenFrom=_enum(item.get("loanTakenFrom"), ("B", "I"), "B"),
        lenderName=_text(item.get("lenderName"), _text(item.get("bankOrInstnName"))),
        lenderPAN=_text(item.get("lenderPAN")),
        loanAccountNo=_text(item.get("loanAccountNo"), _text(item.get("loanAccNo"))),
        dateOfLoan=_text(item.get("dateOfLoan")),
        totalLoanAmount=_first_money("totalLoanAmount", "totalAmt", source=item),
        outstandingAmount=_first_money("outstandingAmount", "loanOutstandingAmt", source=item),
        interestAmount=_money(item.get("interestAmount")),
        firstTimeBuyerEligible=_bool(item.get("firstTimeBuyerEligible")),
        vehicleRegNo=_text(item.get("vehicleRegNo")),
    )


def _schedule_80gga(item: JsonRecord, index: int) -> Schedule80GGAEntry:
    return Schedule80GGAEntry(
        id=_item_id("80gga", index, item),
        relevantClause=_enum(item.get("relevantClause"), ("80GGA2a", "80GGA2b", "80GGA2c", "80GGA2d", "80GGA2e"), "80GGA2a"),
        doneeName=_text(item.get("doneeName")),
        doneePAN=_text(item.get("doneePAN")),
        addressLine=_text(item.get("addressLine")),
        city=_text(item.get("city")),
        stateCode=_text(item.get("stateCode")),
        pinCode=_text(item.get("pinCode")),
        cashAmount=_money(item.get("cashAmount")),
        otherModeAmount=_money(item.get("otherModeAmount")),
    )


def _schedule_80ggc(item: JsonRecord, index: int) -> Schedule80GGCEntry:
    return Schedule80GGCEntry(
        id=_item_id("80ggc", index, item),
        cashAmount=_money(item.get("cashAmount")),
        otherModeAmount=_money(item.get("otherModeAmount", item.get("amount"))),
        contributionDate=_text(item.get("contributionDate")),
        transactionRef=_text(item.get("transactionRef")),
        ifscCode=_text(item.get("ifscCode")),
        politicalPartyName=_text(item.get("politicalPartyName")),
        politicalPartyPAN=_text(item.get("politicalPartyPAN")),
    )


def _tds(item: JsonRecord, index: int) -> TdsCredit:
    """Adapt one flat TDS row to the typed TdsCredit model."""
    section = _text(item.get("section"))
    deducted = _money(item.get("taxDeducted", item.get("tdsDeducted")))
    claimed = _bool(item.get("claimedInReturn"), True)
    return TdsCredit(
        id=_item_id("tds", index, item),
        section=section,
        deductorName=_text(item.get("deductorName")),
        deductorTAN=_text(item.get("deductorTAN")),
        deductorPAN=_text(item.get("deductorPAN")),
        certificateNo=_text(item.get("certificateNo")),
        grossAmount=_first_money("grossAmount", "incomeAmount", source=item),
        taxDeducted=deducted,
        deductionDate=_text(item.get("deductionDate")),
        uniqueTransactionNo=_text(item.get("uniqueTransactionNo")),
        financialYear=_text(item.get("financialYear")),
        verified26AS=_bool(item.get("verified26AS")),
        claimedInReturn=claimed,
        schedule=_enum(item.get("schedule"), ("TDS1", "TDS2", "TDS3"), "TDS1" if section.upper() in {"192", "S192"} else "TDS2"),
        tdsSectionCode=_text(item.get("tdsSectionCode")),
        deductedYr=("" if item.get("deductedYr") in (None, "") else (int(item.get("deductedYr")) or "")) if item.get("deductedYr") not in (None, "") else "",
        nameOfTenant=_text(item.get("nameOfTenant")),
        grsRcptToTaxDeduct=_money(item.get("grsRcptToTaxDeduct")),
        tdsClaimed=_money(item.get("tdsClaimed")) or (deducted if claimed else Decimal("0")),
        panOfTenant=_text(item.get("panOfTenant")),
        aadhaarOfTenant=_text(item.get("aadhaarOfTenant")),
    )


def _tcs(item: JsonRecord, index: int) -> TcsCredit:
    """Adapt one flat TCS row to the typed TcsCredit model."""
    collected = _money(item.get("taxCollected", item.get("tcsCollected")))
    claimed = _bool(item.get("claimedInReturn"), True)
    return TcsCredit(
        id=_item_id("tcs", index, item),
        collectorName=_text(item.get("collectorName")),
        collectorTAN=_text(item.get("collectorTAN")),
        grossAmount=_money(item.get("grossAmount")),
        taxCollected=collected,
        claimedInReturn=claimed,
        tcsCreditOwner=_enum(item.get("tcsCreditOwner"), ("1", "2"), "1"),
        panOfSpouseOrOthrPrsn=_text(item.get("panOfSpouseOrOthrPrsn")),
        deductedYr=("" if item.get("deductedYr") in (None, "") else (int(item.get("deductedYr")) or "")) if item.get("deductedYr") not in (None, "") else "",
        broughtFwdTDSAmt=_money(item.get("broughtFwdTDSAmt")),
        tcsAmtCollOwnHand=_money(item.get("tcsAmtCollOwnHand")),
        tcsAmtCollSpouseOrOthrHand=_money(item.get("tcsAmtCollSpouseOrOthrHand")),
        tcsClaimedAmtCollOwnHand=_money(item.get("tcsClaimedAmtCollOwnHand")) or (collected if claimed else Decimal("0")),
        tcsClaimedAmtCollSpouseOrOthrHand=_money(item.get("tcsClaimedAmtCollSpouseOrOthrHand")),
        claimedPANOfSpouseOrOthrPrsn=_text(item.get("claimedPANOfSpouseOrOthrPrsn")),
    )


def _challan(item: JsonRecord, index: int) -> TaxChallan:
    """Adapt one flat tax-challan row to the typed TaxChallan model."""
    import re
    bsr = _text(item.get("bsrCode"))
    date = _text(item.get("depositDate"))
    serial = max(0, min(99999, int(_money(item.get("challanSerialNo", item.get("challanNo")))) or 0))
    amount = _money(item.get("amount"))
    cin = _text(item.get("cin")) or (
        f"{bsr}-{date.replace('-', '')}-{str(serial).zfill(5)}"
        if bsr and re.match(r"^[0-9]{3}[0-9A-Z]{4}$", bsr) and date and serial > 0 else ""
    )
    return TaxChallan(
        id=_item_id("challan", index, item),
        kind=_enum(item.get("kind"), ("ADVANCE_TAX", "SELF_ASSESSMENT"), "ADVANCE_TAX"),
        bsrCode=bsr, depositDate=date, challanSerialNo=serial, amount=amount, cin=cin,
    )


def _bank_account(item: JsonRecord, index: int) -> BankAccount:
    """Adapt one flat bank-account row to the typed BankAccount model."""
    raw_type = _text(item.get("accountType"))
    if raw_type == "SAVINGS":
        account_type = "SB"
    elif raw_type == "CURRENT":
        account_type = "CA"
    else:
        account_type = _enum(raw_type, ("SB", "CA", "CC", "OD", "NRO", "OTH"), "OTH")
    return BankAccount(
        id=_item_id("bank", index, item),
        bankName=_text(item.get("bankName")),
        accountNumber=_text(item.get("accountNumber")),
        ifscCode=_text(item.get("ifscCode")),
        accountType=account_type,
        useForRefund=_bool(item.get("useForRefund"), index == 0),
    )


def flat_to_draft(payload: Any) -> ReturnDraft:
    """Convert a legacy flat formData blob into a canonical ``ReturnDraft``.

    This is the Python mirror of ``frontend/src/domain/returns/legacyAdapter.ts::
    adaptLegacyReturn``.  It converts the legacy flat-blob payload to a
    canonical ``ReturnDraft`` so the v2 pipeline can compute + emit CBDT JSON
    without re-implementing the same alias parsing.

    Args:
        payload: The raw flat JSON blob persisted by the frontend.

    Returns:
        A typed ``ReturnDraft`` ready for ``draft_to_itr1_input`` or
        ``generate_cbdt_json``.
    """
    source: JsonRecord = payload if _is_record(payload) else {}
    raw_form = _text(source.get("form", source.get("itrForm", source.get("itrType")))).replace("ITR", "ITR-") if _text(source.get("form", source.get("itrForm"))) else "ITR-1"
    raw_form = _text(source.get("form", source.get("itrForm", source.get("itrType"))))
    if raw_form and not raw_form.startswith("ITR-") and raw_form.startswith("ITR"):
        raw_form = "ITR-" + raw_form[3:]
    normalized_form = _enum(raw_form, ("ITR-1", "ITR-2", "ITR-3", "ITR-4"), "ITR-1") if raw_form else "ITR-1"
    raw_regime = _text(source.get("regime", source.get("taxRegime"))).lower()
    regime = "old" if raw_regime == "old" else "new"

    draft = create_empty_draft(
        assessment_year=_text(source.get("assessmentYear", source.get("year", source.get("ay")))),
        form=normalized_form,  # type: ignore[arg-type]
        regime=regime,  # type: ignore[arg-type]
    )

    # ── Personal info + filing ────────────────────────────────────────────
    draft.personal = type(draft.personal)(
        name=_text(source.get("name")),
        firstName=_text(source.get("firstName")),
        middleName=_text(source.get("middleName")),
        surnameOrOrgName=_text(source.get("surnameOrOrgName")),
        fatherName=_text(source.get("fatherName")),
        employerCategory=_text(source.get("employerCategory")),
        pan=_text(source.get("pan")),
        aadhaar=_text(source.get("aadhaar")),
        email=_text(source.get("email")),
        mobile=_text(source.get("mobile")),
        mobileCountryCode=_text(source.get("mobileCountryCode"), "91") or "91",
        secondaryEmail=_text(source.get("secondaryEmail")),
        secondaryMobile=_text(source.get("secondaryMobile")),
        secondaryMobileCountryCode=_text(source.get("secondaryMobileCountryCode")),
        dateOfBirth=_text(source.get("dateOfBirth", source.get("dob"))) or None,
        flatNo=_text(source.get("flatNo", source.get("flatDoorNo"))),
        residenceName=_text(source.get("residenceName", source.get("premisesName", source.get("premises")))),
        roadOrStreet=_text(source.get("roadOrStreet", source.get("roadStreet", source.get("road")))),
        localityOrArea=_text(source.get("localityOrArea", source.get("area"))),
        city=_text(source.get("city", source.get("townCity"))),
        stateCode=_text(source.get("stateCode", source.get("state"))),
        countryCode=_text(source.get("countryCode", source.get("country")), "91") or "91",
        pinCode=_text(source.get("pinCode", source.get("pincode"))),
        zipCode=_text(source.get("zipCode")),
    )

    filing_source = source.get("filing") if _is_record(source.get("filing")) else source
    draft.filing = FilingStatus(
        filingSection=_enum(filing_source.get("filingSection"), _FILING_SECTIONS, "139(1)"),
        returnType=_enum(filing_source.get("returnType"), ("ORIGINAL", "REVISED"), "REVISED" if _text(filing_source.get("filingSection")) == "139(5)" else "ORIGINAL"),
        originalAcknowledgementNumber=_text(filing_source.get("originalAcknowledgementNumber")),
        originalFilingDate=_text(filing_source.get("originalFilingDate")) or None,
        noticeNumber=_text(filing_source.get("noticeNumber")),
    )

    # ── Employers ─────────────────────────────────────────────────────────
    employer_rows = _array(source, "employerEntries")
    if employer_rows is None:
        if any(_money(source.get(k)) > 0 for k in ("basic", "da", "hra", "bonus")):
            employer_rows = [source]
        else:
            employer_rows = []
    draft.employers = [_employer(row, i) for i, row in enumerate(employer_rows)]

    # ── House properties — do NOT cap here; the ITR1Input schema enforces
    # the 2-property limit (house_property_count le=2) and the golden suite
    # verifies that 3 properties raise a ValidationError.  Capping silently
    # would mask the violation.
    property_rows = _array(source, "housePropertyEntries")
    if property_rows is None:
        if any(_money(source.get(k)) > 0 for k in ("grossRent", "munTax", "homeLoanInt", "sopLoanInt")):
            property_rows = [source]
        else:
            property_rows = []
    draft.houseProperties = [_property(row, i) for i, row in enumerate(property_rows)]
    draft.housePropertyPassThroughIncome = _signed(
        source.get("housePropertyPassThroughIncome",
                   source.get("passThroughIncome",
                              draft.houseProperties[0].passThroughIncome if draft.houseProperties else Decimal("0")))
    )

    # ── Capital gains schedule ─────────────────────────────────────────────
    # Best-effort: an old flat blob's capitalGainsSchedule dict may predate
    # the typed shape entirely, or carry keys that no longer match. This is a
    # one-way legacy migration adapter, so a shape mismatch falls back to an
    # empty schedule rather than blocking the whole draft from loading.
    if _is_record(source.get("capitalGainsSchedule")):
        try:
            draft.capitalGainsSchedule = CapitalGainsSchedule.model_validate(
                source["capitalGainsSchedule"]
            )
        except ValidationError:
            draft.capitalGainsSchedule = CapitalGainsSchedule()
    else:
        draft.capitalGainsSchedule = CapitalGainsSchedule()

    # ── Businesses ─────────────────────────────────────────────────────────
    business_rows = _array(source, "businessEntries") or _array(source, "businesses")
    if business_rows is None:
        if any(_money(source.get(k)) > 0 for k in ("bizTurnover", "bizDeclared")):
            business_rows = [source]
        else:
            business_rows = []
    draft.businesses = [_business(row, i) for i, row in enumerate(business_rows)]

    # ── Other sources (interest, dividends, winnings, gifts) ──────────────
    interest_rows = _array(source, "interestEntries") or _array(source, "bankInterestEntries") or _scalar_interest(source)
    dividend_rows = _array(source, "dividendEntries")
    if dividend_rows is None:
        total_div = _money(source.get("dividends", source.get("dividendShares"))) + _money(source.get("dividendMF")) + _money(source.get("dividendUnits"))
        dividend_rows = [{"grossAmount": total_div}] if total_div > 0 else []
    winnings_rows = _array(source, "winningsEntries")
    if winnings_rows is None:
        winnings_rows = []
        for win_type, key in (("LOTTERY", "lotteryIncome"), ("CARD_GAME", "crosswordPuzzleIncome"),
                              ("HORSE_RACE", "horseRaceIncome"), ("CARD_GAME", "cardGameIncome"),
                              ("ONLINE_GAMING", "onlineGamingIncome"), ("RACE_HORSE_ACTIVITY", "raceHorseActivityIncome")):
            if _money(source.get(key)) > 0:
                winnings_rows.append({"type": win_type, "grossAmount": source.get(key)})
    gift_rows = _array(source, "giftEntries")
    if gift_rows is None:
        gift_rows = []
        for key, from_relative in (("giftsFromNonRelatives", False), ("giftsFromRelatives", True)):
            if _money(source.get(key)) > 0:
                gift_rows.append({"propertyType": "CASH", "value": source.get(key), "fromRelative": from_relative})

    draft.otherSources = OtherSources(
        interest=[_interest(row, i) for i, row in enumerate(interest_rows)],
        dividends=[_dividend(row, i) for i, row in enumerate(dividend_rows)],
        winnings=[_winning(row, i) for i, row in enumerate(winnings_rows)],
        gifts=[_gift(row, i) for i, row in enumerate(gift_rows)],
    )

    # ── Deductions (80C, 80D, 80G, loans, chapter VIA) ────────────────────
    s80c = source.get("section80C") if _is_record(source.get("section80C")) else {}
    investment_rows = _array(s80c, "investments") if isinstance(s80c, dict) else None
    if investment_rows is None:
        investment_rows = []
        for inv_type, key in (("EPF", "s80C_epf"), ("PPF", "s80C_ppf"), ("ELSS", "s80C_elss"), ("LIC", "s80C_lic"), ("HomeLoan", "s80C_home")):
            if _money(source.get(key)) > 0:
                investment_rows.append({"investmentType": inv_type, "amount": source.get(key)})

    s80d = source.get("section80D") if _is_record(source.get("section80D")) else {}
    loan_root = source.get("deductionLoans") if _is_record(source.get("deductionLoans")) else {}
    loan_items: list[JsonRecord] = []
    if isinstance(loan_root, dict):
        for section in ("80E", "80EE", "80EEA", "80EEB"):
            group = loan_root.get(f"section{section}") if _is_record(loan_root.get(f"section{section}")) else {}
            for loan_row in _records(group.get("loans")):
                loan_items.append({**loan_row, "section": section})

    via = source.get("chapterVIA") if _is_record(source.get("chapterVIA")) else {}
    donation_rows = _array(source, "donationEntries")
    if donation_rows is None:
        if _money(source.get("s80G")) > 0:
            donation_rows = [{"donationAmtOtherMode": source.get("s80G")}]
        else:
            donation_rows = []

    draft.deductions = type(draft.deductions)(
        section80C=[_investment_80c(row, i) for i, row in enumerate(investment_rows)],
        pensionContribution80CCC=[
            _pension_80ccc(row, i)
            for i, row in enumerate(
                _records(source.get("pensionContribution80CCC"))
                or _records(via.get("pensionContribution80CCC"))
            )
        ],
        section80D=type(draft.deductions.section80D)(
            selfSeniorCitizen=_enum(s80d.get("selfSeniorCitizen"), ("Y", "N", "S"), "N") if isinstance(s80d, dict) else "N",
            parentsSeniorCitizen=_enum(s80d.get("parentsSeniorCitizen"), ("Y", "N", "P"), "N") if isinstance(s80d, dict) else "N",
            selfFamily={"policies": [_policy_80d(p, i) for i, p in enumerate(_records(s80d.get("selfFamily", {}).get("policies")))]} if isinstance(s80d, dict) else {"policies": []},
            selfFamilySenior={"policies": [_policy_80d(p, i) for i, p in enumerate(_records(s80d.get("selfFamilySenior", {}).get("policies")))]} if isinstance(s80d, dict) else {"policies": []},
            parents={"policies": [_policy_80d(p, i) for i, p in enumerate(_records(s80d.get("parents", {}).get("policies")))]} if isinstance(s80d, dict) else {"policies": []},
            parentsSenior={"policies": [_policy_80d(p, i) for i, p in enumerate(_records(s80d.get("parentsSenior", {}).get("policies")))]} if isinstance(s80d, dict) else {"policies": []},
        ),
        section80G=[
            {
                "id": _item_id("80g", i, row),
                "category": _enum(row.get("category"), ("100_NO_APPROVAL", "50_NO_APPROVAL", "100_APPROVAL_REQD", "50_APPROVAL_REQD"), "50_APPROVAL_REQD"),
                "doneeName": _text(row.get("doneeName")),
                "doneePAN": _text(row.get("doneePAN")),
                "arnNumber": _text(row.get("arnNumber")),
                "addrDetail": _text(row.get("addrDetail")),
                "city": _text(row.get("city")),
                "stateCode": _text(row.get("stateCode")),
                "pinCode": _text(row.get("pinCode")),
                "donationAmtCash": _money(row.get("donationAmtCash")),
                "donationAmtOtherMode": _first_money("donationAmtOtherMode", "amount", source=row),
                "transactionRefNum": _text(row.get("transactionRefNum")),
                "ifscCode": _text(row.get("ifscCode")),
                "donationDate": _text(row.get("donationDate")),
                "receiptNumber": _text(row.get("receiptNumber")),
                "notes": _text(row.get("notes")),
            }
            for i, row in enumerate(donation_rows)
        ],
        loans={
            "section80EEAStampDutyValue": _money(loan_root.get("section80EEA", {}).get("stampDutyValue")) if _is_record(loan_root.get("section80EEA")) else Decimal("0"),
            "loans": [_loan(row, i) for i, row in enumerate(loan_items)],
        },
        schedule80GGA=[
            _schedule_80gga(row, i)
            for i, row in enumerate(_records(source.get("schedule80GGA")))
        ],
        schedule80GGC=[
            _schedule_80ggc(row, i)
            for i, row in enumerate(_records(source.get("schedule80GGC")))
        ],
        chapterVIA=type(draft.deductions.chapterVIA)(
            section80C=_first_money("section80C", "s80C_total", source=via) or _money(source.get("s80C_total")),
            section80CCC=_first_money("section80CCC", "s80CCC", source=via) or _money(source.get("s80CCC")),
            pensionContribution80CCC=sum(
                (
                    row.amount
                    for row in [
                        _pension_80ccc(item, i)
                        for i, item in enumerate(
                            _records(source.get("pensionContribution80CCC"))
                            or _records(via.get("pensionContribution80CCC"))
                        )
                    ]
                ),
                Decimal("0"),
            ),
            section80CCDEmployeeOrSE=_first_money("section80CCDEmployeeOrSE", "s80CCD1", source=via) or _money(source.get("s80CCD1")),
            section80CCD1B=_first_money("section80CCD1B", source=via) or _money(source.get("s80CCD1B")),
            section80CCDEmployer=_first_money("section80CCDEmployer", "s80CCD2", source=via) or _money(source.get("s80CCD2")),
            section80D=_money(via.get("section80D")) if isinstance(via, dict) else _money(source.get("s80D")),
            section80G=_money(via.get("section80G")) if isinstance(via, dict) else _money(source.get("s80G")),
            section80DD=_money(via.get("section80DD")) if isinstance(via, dict) else _money(source.get("s80DD")),
            section80DDB=_money(via.get("section80DDB")) if isinstance(via, dict) else _money(source.get("s80DDB")),
            section80TTA=_first_money("section80TTA", source=via) or _money(source.get("s80TTA")),
            section80TTB=_first_money("section80TTB", source=via) or _money(source.get("s80TTB")),
            section80E=_money(via.get("section80E")) if isinstance(via, dict) else Decimal("0"),
            section80EE=_money(via.get("section80EE")) if isinstance(via, dict) else Decimal("0"),
            section80EEA=_money(via.get("section80EEA")) if isinstance(via, dict) else Decimal("0"),
            section80EEB=_money(via.get("section80EEB")) if isinstance(via, dict) else Decimal("0"),
            section80GG=_money(via.get("section80GG")) if isinstance(via, dict) else Decimal("0"),
            section80GGA=_money(via.get("section80GGA")) if isinstance(via, dict) else Decimal("0"),
            section80GGC=_money(via.get("section80GGC")) if isinstance(via, dict) else Decimal("0"),
            section80U=_money(via.get("section80U")) if isinstance(via, dict) else _money(source.get("s80U")),
            pranNumber=(_text(via.get("pranNumber")) if isinstance(via, dict) and via.get("pranNumber") else "") or _text(source.get("s80CCD1B_PRAN")),
        ),
    )

    # ── Taxes (TDS, TCS, challans) ────────────────────────────────────────
    tds_rows = _array(source, "tdsEntries")
    if tds_rows is None:
        tds_rows = []
        for section, key in (("192", "tdsS192"), ("194A", "tds194A"), ("OTHER", "tdsOther")):
            if _money(source.get(key)) > 0:
                tds_rows.append({"section": section, "tdsDeducted": source.get(key)})
    draft.taxes = type(draft.taxes)(
        tds=[_tds(row, i) for i, row in enumerate(tds_rows)],
        tcs=[_tcs(row, i) for i, row in enumerate(_array(source, "tcsEntries") or [])],
        challans=[_challan(row, i) for i, row in enumerate(
            ([{**r, "kind": "ADVANCE_TAX"} for r in (_array(source, "advanceTaxEntries") or [])] +
             [{**r, "kind": "SELF_ASSESSMENT"} for r in (_array(source, "selfAssessmentTaxEntries") or
                ([{"amount": source.get("selfTax")}] if _money(source.get("selfTax")) > 0 else []))])
        )],
    )

    # ── Bank accounts ─────────────────────────────────────────────────────
    bank_root = source.get("bankAccountData") if _is_record(source.get("bankAccountData")) else {}
    accounts = _records(bank_root.get("accounts")) if isinstance(bank_root, dict) else (_array(source, "bankAccountDetails") or [])
    draft.bankAccounts = [_bank_account(row, i) for i, row in enumerate(accounts)]

    # ── Verification ──────────────────────────────────────────────────────
    verification = source.get("verification") if _is_record(source.get("verification")) else {}
    draft.verification = Verification(
        capacity=_enum(verification.get("capacity"), ("SELF", "REPRESENTATIVE"), "SELF"),
        place=_text(verification.get("place")),
        date=_text(verification.get("date")) or None,
        declarationAccepted=_bool(verification.get("declarationAccepted")),
    )

    # ── Provenance ─────────────────────────────────────────────────────────
    provenance_rows = _array(source, "provenance") or _array(source, "importProvenance") or []
    draft.provenance = [
        ImportProvenance(
            source=_enum(p.get("source"), ("MANUAL", "FORM16", "AIS", "TIS", "26AS", "ITD_PREFILL", "LEGACY"), "LEGACY"),
            importedAt=_text(p.get("importedAt")) or None,
            reference=_text(p.get("reference")),
        )
        for p in provenance_rows
    ]
    if not draft.provenance and source:
        draft.provenance = [ImportProvenance(source="LEGACY", importedAt=None, reference="")]

    return draft
