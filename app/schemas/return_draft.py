"""
Canonical ReturnDraft Pydantic model — backend mirror of the frontend
``frontend/src/domain/returns/types.ts`` ReturnDraft.

This is the SINGLE typed shape for an ITR return draft. It replaces the
flat legacy blob (``form_data`` with ~150+ alias keys) as the persisted
and computed contract for the /v2 endpoints.

Phase 1 of the ITR-1 Data-Flow Simplification (see
``ITR1_DATA_FLOW_SIMPLIFICATION_PLAN.md``).

Design rules:
  - Every field has exactly ONE name (no ``hra``/``hraReceived`` aliases).
  - Money is ``Decimal`` everywhere (no float precision loss).
  - Lists are typed; elements carry a stable ``id``.
  - ``model_config = ConfigDict(extra="forbid")`` so unknown keys are
    rejected on write — the compatibility envelope (``extras``) is gone.
  - Every type mirrors the official CBDT enum where one exists.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Common primitives
# ---------------------------------------------------------------------------

Money = Decimal  # All monetary values are Decimal (no float).

ItrForm = Literal["ITR-1", "ITR-2", "ITR-3", "ITR-4"]
TaxRegime = Literal["old", "new"]
PropertyType = Literal["SELF_OCCUPIED", "LET_OUT", "DEEMED_LET_OUT"]
PropertyOwnerType = Literal["SE", "MI", "SP", "OT"]
OwnershipType = Literal["SOLE", "JOINT"]
LenderType = Literal["B", "I"]
PresumptiveScheme = Literal["44AD", "44ADA", "44AE"]
InterestKind = Literal[
    "SAVINGS_BANK", "TERM_DEPOSIT", "IT_REFUND", "POST_OFFICE", "NSC", "SCSS",
    "OTHER", "BONDS", "SECURITIES",
    "PF_10_11_FIRST", "PF_10_11_SECOND", "PF_10_12_FIRST", "PF_10_12_SECOND",
]
DividendSection = Literal[
    "194", "10(22e)", "10(22f)", "115BBDA", "115BBDAaiii", "115A1ai",
    "115A1aA", "115AC", "115ACA", "115AD1i", "DTAA",
]
WinningIncomeType = Literal[
    "LOTTERY", "BETTING", "CARD_GAME", "HORSE_RACE", "ONLINE_GAMING",
    "RACE_HORSE_ACTIVITY", "UNEXPLAINED_115BBE",
]
GiftConsiderationKind = Literal["WITHOUT_CONSIDERATION", "INADEQUATE_CONSIDERATION"]
GiftPropertyType = Literal["IMMOVABLE", "CASH", "MOVABLE", "OTHER"]
DtaaNatureOfIncome = Literal["1ai", "1aiii", "1b", "1c", "1d", "2ai", "2aii", "2d", "2e"]
Section89ACountry = Literal["US", "UK", "CA"]
SpecialRateSourceDescription = Literal[
    "5A1ai", "5A1aA", "5A1aii", "5A1aiia", "5A1aiiaa", "5A1aiiab", "5A1aiiac",
    "5A1aiii", "5A1bA", "5AC1ab", "5AC1abD", "5ACA1a", "5AD1i", "5AD1iP",
    "5BBA", "5BBF", "5BBG", "5Ea", "5A1aiiaaP", "5A1aiiaa2P", "5AD1iDiv",
]
ExemptIncomeCategory = Literal["AGRI", "GOVC", "ISI", "SSRA", "SRSC", "SRST", "SRPC", "OTH", "OTHN"]
DtaaExemptHeadOfIncome = Literal["SA", "HP", "PG", "CG", "OS"]
TaxChallanKind = Literal["ADVANCE_TAX", "SELF_ASSESSMENT"]
BankAccountType = Literal["SB", "CA", "CC", "OD", "NRO", "OTH"]
FilingSection = Literal["139(1)", "139(4)", "139(5)", "119(2)(b)"]
ReturnType = Literal["ORIGINAL", "REVISED"]
VerificationCapacity = Literal["SELF", "REPRESENTATIVE"]
ImportSource = Literal["MANUAL", "FORM16", "AIS", "TIS", "26AS", "ITD_PREFILL", "LEGACY"]
DeductionLoanSection = Literal["80E", "80EE", "80EEA", "80EEB"]
SeniorCitizenFlag = Literal["Y", "N", "S", "P"]
DisabilitySeverityCode = Literal["1", "2", ""]
Form10IAFiled = Literal["Y", "N"]
Section80DDBUserType = Literal["1", "2", ""]
PolicyType80D = Literal["INDIVIDUAL", "FAMILY_FLOATER", "GROUP", "OTHER"]
AccountTypeInterest = Literal["SAVINGS", "CURRENT", "FD", ""]
DividendCategory = Literal["EQUITY", "PREFERENCE", "MUTUAL_FUND", ""]
Donation80GCategory = Literal["100_NO_APPROVAL", "50_NO_APPROVAL", "100_APPROVAL_REQD", "50_APPROVAL_REQD"]
Section80GGAClause = Literal["80GGA2a", "80GGA2b", "80GGA2c", "80GGA2d", "80GGA2e"]
TdsCreditName = Literal["S", "O"]
HeadOfIncome = Literal["HP", "CG", "OS", "BP", "EI", "NA"]
TdsSchedule = Literal["TDS1", "TDS2", "TDS3"]
TcsCreditOwner = Literal["1", "2"]
AgriculturalOwnedFlag = Literal["O", "H"]
AgriculturalIrrigatedFlag = Literal["IRG", "RF"]
PfAssessmentYear = Literal[
    "2005-06", "2006-07", "2007-08", "2008-09", "2009-10", "2010-11",
    "2011-12", "2012-13", "2013-14", "2014-15", "2015-16", "2016-17",
    "2017-18", "2018-19", "2019-20", "2020-21", "2021-22", "2022-23",
    "2023-24", "2024-25", "2025-26",
]
ExemptIncomeSubCategory = Literal[
    "10(1)", "10(2)", "10(2A)", "10(4)(i)", "10(4)(ii)", "10(4B)", "10(4C)",
    "10(4E)", "10(4F)", "10(4G)", "10(4H)", "10(6B)", "10(6BB)", "10(6D)",
    "10(8)", "10(8A)", "10(8B)", "10(9)", "10(10BB)", "10(10BC)", "10(10D)",
    "10(11)", "10(11A)", "10(12)", "10(12A)", "10(12AA)", "10(12AB)",
    "10(12B)", "10(12BA)", "10(12C)", "10(13)", "10(15)", "10(16)",
    "10(17A)", "10(18)", "10(19)", "10(19A)", "10(23AA)", "10(23FBB)",
    "10(23FBC)", "10(23FD)", "10(23FF)", "10(25)", "10(26)", "10(26AAA)",
    "10(30)", "10(31)", "10(32)", "10(33)", "10(35)", "10(35A)", "10(36)",
    "10(37)", "10(37A)", "10(43)", "10(44)", "DMD", "Incmexmptcircular",
    "Incmexmptnotification", "Receiptnotincme", "Anyother1",
    "Anyother2", "Anyother3", "Anyother4",
]


class _StrictModel(BaseModel):
    """Base model: rejects unknown keys, uses Decimal for money, nulls empty strings."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=False,
        str_strip_whitespace=False,
        populate_by_name=True,
    )


class Identified(_StrictModel):
    """Any list element that carries a stable client-generated id."""

    id: str = Field(default="")


# ---------------------------------------------------------------------------
# Salary (Schedule S)
# ---------------------------------------------------------------------------

class SalaryNatureRow(Identified):
    natureCode: str = Field(default="")
    otherDescription: str = Field(default="")
    amount: Money = Field(default=Decimal("0"))


class Employer(Identified):
    customEmployerName: str = Field(default="")
    employerName: str = Field(default="")
    employerTAN: str = Field(default="")
    natureOfEmployment: str = Field(default="")
    employerAddress: str = Field(default="")
    employerCity: str = Field(default="")
    employerStateCode: str = Field(default="")
    employerPinCode: str = Field(default="")
    employerZipCode: str = Field(default="")
    salaryNatureRows: list[SalaryNatureRow] = Field(default_factory=list)
    perquisiteNatureRows: list[SalaryNatureRow] = Field(default_factory=list)
    section10ExemptionRows: list[SalaryNatureRow] = Field(default_factory=list)
    basic: Money = Field(default=Decimal("0"))
    da: Money = Field(default=Decimal("0"))
    commission: Money = Field(default=Decimal("0"))
    hra: Money = Field(default=Decimal("0"))
    bonus: Money = Field(default=Decimal("0"))
    allowances: Money = Field(default=Decimal("0"))
    lta: Money = Field(default=Decimal("0"))
    otherAllowance: Money = Field(default=Decimal("0"))
    arrearSalary: Money = Field(default=Decimal("0"))
    perquisites: Money = Field(default=Decimal("0"))
    profitsInLieu: Money = Field(default=Decimal("0"))
    rentPaid: Money = Field(default=Decimal("0"))
    city: str = Field(default="")
    isMetroCity: bool = Field(default=False)
    isGovernmentEmployee: bool = Field(default=False)
    isDisabledEmployee: bool = Field(default=False)
    commutedPension: Money = Field(default=Decimal("0"))
    gratuity: Money = Field(default=Decimal("0"))
    leaveEncashment: Money = Field(default=Decimal("0"))
    averageMonthlySalary: Money = Field(default=Decimal("0"))
    yearsOfService: int = Field(default=0)
    unavailedLeaveDays: int = Field(default=0)
    actualLtaFare: Money = Field(default=Decimal("0"))
    isDomesticTravel: bool = Field(default=False)
    journeysInBlock: int = Field(default=0)
    ltaExempt: Money = Field(default=Decimal("0"))
    numberOfChildren: int = Field(default=0)
    gratuityAlsoReceived: bool = Field(default=False)
    transportAllowance: Money = Field(default=Decimal("0"))
    childrenEducationAllowance: Money = Field(default=Decimal("0"))
    hostelExpenditureAllowance: Money = Field(default=Decimal("0"))
    uniformAllowance: Money = Field(default=Decimal("0"))
    entertainmentAllowance: Money = Field(default=Decimal("0"))
    professionalTax: Money = Field(default=Decimal("0"))
    vrsCompensation: Money = Field(default=Decimal("0"))
    retrenchmentCompensation: Money = Field(default=Decimal("0"))
    otherExempt: Money = Field(default=Decimal("0"))
    tdsDeducted: Money = Field(default=Decimal("0"))
    employerNPS: Money = Field(default=Decimal("0"))


# ---------------------------------------------------------------------------
# House Property (Schedule HP)
# ---------------------------------------------------------------------------

class CoOwner(_StrictModel):
    coOwnerSNo: int = Field(default=0)
    name: str = Field(default="")
    pan: str = Field(default="")
    aadhaar: str = Field(default="")
    share: Money = Field(default=Decimal("0"))


class TenantDetail(_StrictModel):
    tenantSNo: int = Field(default=0)
    name: str = Field(default="")
    pan: str = Field(default="")
    aadhaar: str = Field(default="")
    panOrTan: str = Field(default="")


class HomeLoan(_StrictModel):
    lenderType: LenderType = Field(default="B")
    lenderName: str = Field(default="")
    lenderPAN: str = Field(default="")
    loanAccountNo: str = Field(default="")
    dateOfLoan: str = Field(default="")
    totalLoanAmount: Money = Field(default=Decimal("0"))
    loanOutstandingAmount: Money = Field(default=Decimal("0"))
    interestUs24B: Money = Field(default=Decimal("0"))
    constructionCompletionDate: str = Field(default="")
    completedWithin5Years: bool = Field(default=False)
    preConstructionInterest: Money = Field(default=Decimal("0"))


class HouseProperty(Identified):
    name: str = Field(default="")
    propertySequenceNo: int = Field(default=0)
    propertyType: PropertyType = Field(default="SELF_OCCUPIED")
    address: str = Field(default="")
    premisesName: str = Field(default="")
    roadOrStreet: str = Field(default="")
    area: str = Field(default="")
    city: str = Field(default="")
    state: str = Field(default="")
    pinCode: str = Field(default="")
    zipCode: str = Field(default="")
    countryCode: str = Field(default="91")
    propertyIdentificationNo: str = Field(default="")
    propertyOwnerType: PropertyOwnerType = Field(default="SE")
    propertyOwnerOther: str = Field(default="")
    ownershipType: OwnershipType = Field(default="SOLE")
    ownershipShare: Money = Field(default=Decimal("0"))
    isCoOwned: bool = Field(default=False)
    isPropertyInJointOwnership: bool = Field(default=False)
    coOwners: list[CoOwner] = Field(default_factory=list)
    annualRent: Money = Field(default=Decimal("0"))
    municipalRateableValue: Money = Field(default=Decimal("0"))
    fairRentValue: Money = Field(default=Decimal("0"))
    standardRent: Money = Field(default=Decimal("0"))
    annualLettingValue: Money = Field(default=Decimal("0"))
    unrealizedRent: Money = Field(default=Decimal("0"))
    arrearsOfRent: Money = Field(default=Decimal("0"))
    vacancyPeriodMonths: int = Field(default=0)
    municipalTaxesPaid: Money = Field(default=Decimal("0"))
    interestOnLoan: Money = Field(default=Decimal("0"))
    preConstructionInterest: Money = Field(default=Decimal("0"))
    lenderName: str = Field(default="")
    lenderPAN: str = Field(default="")
    lenderType: LenderType = Field(default="B")
    loanAccountNo: str = Field(default="")
    loanSanctionDate: str = Field(default="")
    constructionCompletionDate: str = Field(default="")
    principalRepayment: Money = Field(default=Decimal("0"))
    totalLoanAmount: Money = Field(default=Decimal("0"))
    loanOutstandingAmount: Money = Field(default=Decimal("0"))
    completedWithin5Years: bool = Field(default=False)
    homeLoans: list[HomeLoan] = Field(default_factory=list)
    tenantDetails: list[TenantDetail] = Field(default_factory=list)
    tenantName: str = Field(default="")
    tenantPAN: str = Field(default="")
    tenantAadhaar: str = Field(default="")
    passThroughIncome: Money = Field(default=Decimal("0"))
    grossAnnualValue: Money = Field(default=Decimal("0"))
    netAnnualValue: Money = Field(default=Decimal("0"))
    standardDeduction30Pct: Money = Field(default=Decimal("0"))
    incomeFromHP: Money = Field(default=Decimal("0"))
    maxRent: Money = Field(default=Decimal("0"))
    preConstructionInterestClaimed: Money = Field(default=Decimal("0"))


# ---------------------------------------------------------------------------
# Business / Profession (Schedule BP / 44AD / 44ADA / 44AE)
# ---------------------------------------------------------------------------

class GstinTurnoverRow(Identified):
    gstin: str = Field(default="")
    turnover: Money = Field(default=Decimal("0"))


class FinancialParticulars(_StrictModel):
    cashBalance: Money = Field(default=Decimal("0"))
    bankBalance: Money = Field(default=Decimal("0"))
    inventory: Money = Field(default=Decimal("0"))
    sundryDebtors: Money = Field(default=Decimal("0"))
    sundryCreditors: Money = Field(default=Decimal("0"))
    otherAssets: Money = Field(default=Decimal("0"))
    totalAssets: Money = Field(default=Decimal("0"))
    securedLoans: Money = Field(default=Decimal("0"))
    unsecuredLoans: Money = Field(default=Decimal("0"))
    advances: Money = Field(default=Decimal("0"))
    otherLiabilities: Money = Field(default=Decimal("0"))
    totalLiabilities: Money = Field(default=Decimal("0"))
    grossProfit: Money = Field(default=Decimal("0"))
    expenses: Money = Field(default=Decimal("0"))
    netProfit: Money = Field(default=Decimal("0"))


class BusinessIdentity(_StrictModel):
    businessName: str = Field(default="")
    natureCode: str = Field(default="")
    description: str = Field(default="")


class VehicleRecord(Identified):
    vehicleNumber: str = Field(default="")
    vehicleType: Literal["HEAVY", "OTHER"] = Field(default="OTHER")
    tonnage: Money = Field(default=Decimal("0"))
    ownedMonths: int = Field(default=0)
    leasedOrHired: bool = Field(default=False)
    presumptiveIncome: Money = Field(default=Decimal("0"))


class Presumptive44AD(Identified, BusinessIdentity):
    scheme: Literal["44AD"] = Field(default="44AD")
    digitalReceipts: Money = Field(default=Decimal("0"))
    nonDigitalReceipts: Money = Field(default=Decimal("0"))
    digitalPresumptiveIncome: Money = Field(default=Decimal("0"))
    nonDigitalPresumptiveIncome: Money = Field(default=Decimal("0"))
    declaredIncome: Money = Field(default=Decimal("0"))
    gstinTurnovers: list[GstinTurnoverRow] = Field(default_factory=list)
    financialParticulars: FinancialParticulars = Field(default_factory=FinancialParticulars)


class Presumptive44ADA(Identified, BusinessIdentity):
    scheme: Literal["44ADA"] = Field(default="44ADA")
    grossReceipts: Money = Field(default=Decimal("0"))
    digitalReceipts: Money = Field(default=Decimal("0"))
    nonDigitalReceipts: Money = Field(default=Decimal("0"))
    declaredIncome: Money = Field(default=Decimal("0"))
    gstinTurnovers: list[GstinTurnoverRow] = Field(default_factory=list)
    financialParticulars: FinancialParticulars = Field(default_factory=FinancialParticulars)


class Presumptive44AE(Identified, BusinessIdentity):
    scheme: Literal["44AE"] = Field(default="44AE")
    vehicles: list[VehicleRecord] = Field(default_factory=list)
    declaredIncome: Money = Field(default=Decimal("0"))
    gstinTurnovers: list[GstinTurnoverRow] = Field(default_factory=list)
    financialParticulars: FinancialParticulars = Field(default_factory=FinancialParticulars)


PresumptiveBusiness = Union[Presumptive44AD, Presumptive44ADA, Presumptive44AE]


# ---------------------------------------------------------------------------
# Other Sources (Schedule OS)
# ---------------------------------------------------------------------------

class InterestIncome(Identified):
    kind: InterestKind = Field(default="OTHER")
    grossAmount: Money = Field(default=Decimal("0"))
    tdsDeducted: Money = Field(default=Decimal("0"))
    bankName: str = Field(default="")
    accountType: AccountTypeInterest = Field(default="")
    accountNumber: str = Field(default="")
    ifscCode: str = Field(default="")
    postOfficeName: str = Field(default="")
    accountNumberPO: str = Field(default="")
    nscCertificateNumber: str = Field(default="")
    yearOfPurchase: int = Field(default=0)
    scssAccountNumber: str = Field(default="")
    dateOfOpening: str = Field(default="")
    deductorName: str = Field(default="")
    deductorTAN: str = Field(default="")
    remarks: str = Field(default="")


class DividendIncome(Identified):
    section: DividendSection = Field(default="194")
    grossAmount: Money = Field(default=Decimal("0"))
    tdsDeducted: Money = Field(default=Decimal("0"))
    companyName: str = Field(default="")
    companyPAN: str = Field(default="")
    deductorTAN: str = Field(default="")
    isin: str = Field(default="")
    category: DividendCategory = Field(default="")
    q1: Money = Field(default=Decimal("0"))
    q2: Money = Field(default=Decimal("0"))
    q3: Money = Field(default=Decimal("0"))
    q4: Money = Field(default=Decimal("0"))
    q5: Money = Field(default=Decimal("0"))


class FamilyPension(_StrictModel):
    grossAmount: Money = Field(default=Decimal("0"))
    payerName: str = Field(default="")
    relationToPensioner: str = Field(default="")


class WinningIncome(Identified):
    type: WinningIncomeType = Field(default="LOTTERY")
    grossAmount: Money = Field(default=Decimal("0"))
    tdsDeducted: Money = Field(default=Decimal("0"))
    payerName: str = Field(default="")
    payerTAN: str = Field(default="")
    dateOfWinning: str = Field(default="")
    q1: Optional[Money] = Field(default=None)
    q2: Optional[Money] = Field(default=None)
    q3: Optional[Money] = Field(default=None)
    q4: Optional[Money] = Field(default=None)
    q5: Optional[Money] = Field(default=None)
    receipts: Optional[Money] = Field(default=None)
    deductionUs57: Optional[Money] = Field(default=None)
    amountNotDeductibleUs58: Optional[Money] = Field(default=None)
    profitChargeableUs59: Optional[Money] = Field(default=None)
    balance: Optional[Money] = Field(default=None)


class GiftIncome(Identified):
    propertyType: GiftPropertyType = Field(default="OTHER")
    value: Money = Field(default=Decimal("0"))
    donorName: str = Field(default="")
    donorRelation: str = Field(default="")
    dateOfReceipt: str = Field(default="")
    description: str = Field(default="")
    fromRelative: bool = Field(default=False)
    receivedOnMarriage: bool = Field(default=False)
    considerationKind: GiftConsiderationKind = Field(default="WITHOUT_CONSIDERATION")
    stampDutyValue: Optional[Money] = Field(default=None)
    considerationPaid: Optional[Money] = Field(default=None)
    fairMarketValue: Optional[Money] = Field(default=None)


class OtherIncomeEntry(Identified):
    nature: str = Field(default="")
    description: str = Field(default="")
    amount: Money = Field(default=Decimal("0"))


class DtaaIncomeEntry(Identified):
    amount: Money = Field(default=Decimal("0"))
    natureOfIncome: DtaaNatureOfIncome = Field(default="1ai")
    countryName: str = Field(default="")
    countryCode: str = Field(default="")
    dtaaArticle: str = Field(default="")
    rateAsPerTreaty: Money = Field(default=Decimal("0"))
    rateAsPerITAct: Money = Field(default=Decimal("0"))
    taxResidencyCertificate: Literal["Y", "N"] = Field(default="N")
    itemNoIncl: str = Field(default="")
    applicableRate: Money = Field(default=Decimal("0"))
    q1: Money = Field(default=Decimal("0"))
    q2: Money = Field(default=Decimal("0"))
    q3: Money = Field(default=Decimal("0"))
    q4: Money = Field(default=Decimal("0"))
    q5: Money = Field(default=Decimal("0"))


class DtaaAggregates(_StrictModel):
    totalAmountTaxUsDtaa: Money = Field(default=Decimal("0"))


class Section89AEntry(Identified):
    countryCode: Section89ACountry = Field(default="US")
    amount: Money = Field(default=Decimal("0"))


class Section89AAggregates(_StrictModel):
    incomeNotified89AOS: Money = Field(default=Decimal("0"))
    incomeNotifiedOther89AOS: Money = Field(default=Decimal("0"))
    incomeNotifiedPriorYear89AOS: Money = Field(default=Decimal("0"))
    incomeReliefUs89AOS: Money = Field(default=Decimal("0"))


class AccumulatedPfEntry(Identified):
    assessmentYear: PfAssessmentYear = Field(default="2025-26")
    incomeBenefit: Money = Field(default=Decimal("0"))
    taxBenefit: Money = Field(default=Decimal("0"))


class AccumulatedPfAggregates(_StrictModel):
    totalIncomeBenefit: Money = Field(default=Decimal("0"))
    totalTaxBenefit: Money = Field(default=Decimal("0"))


class SpecialRateIncomeEntry(Identified):
    sourceDescription: SpecialRateSourceDescription = Field(default="5A1ai")
    sourceAmount: Money = Field(default=Decimal("0"))


class UnexplainedIncomeDetails(_StrictModel):
    cashCreditsUs68: Money = Field(default=Decimal("0"))
    unexplainedInvestmentsUs69: Money = Field(default=Decimal("0"))
    unexplainedMoneyUs69A: Money = Field(default=Decimal("0"))
    undisclosedInvestmentsUs69B: Money = Field(default=Decimal("0"))
    unexplainedExpenditureUs69C: Money = Field(default=Decimal("0"))
    hundiBorrowingUs69D: Money = Field(default=Decimal("0"))
    priorYearBusinessTrust562xii: Money = Field(default=Decimal("0"))
    priorYearLifeInsurance562xiii: Money = Field(default=Decimal("0"))


class OtherSourcesDeductions(_StrictModel):
    expenses: Money = Field(default=Decimal("0"))
    interestExpenseUs57: Money = Field(default=Decimal("0"))
    interestExpenseEligibleUs57: Money = Field(default=Decimal("0"))
    familyPensionDeductionUs57iia: Money = Field(default=Decimal("0"))
    depreciation: Money = Field(default=Decimal("0"))
    totalDeductions: Money = Field(default=Decimal("0"))
    amountNotDeductibleUs58: Money = Field(default=Decimal("0"))
    profitChargeableUs59: Money = Field(default=Decimal("0"))


class OtherSources(_StrictModel):
    interest: list[InterestIncome] = Field(default_factory=list)
    dividends: list[DividendIncome] = Field(default_factory=list)
    familyPension: FamilyPension = Field(default_factory=FamilyPension)
    winnings: list[WinningIncome] = Field(default_factory=list)
    gifts: list[GiftIncome] = Field(default_factory=list)
    otherIncome: list[OtherIncomeEntry] = Field(default_factory=list)
    dtaaIncome: list[DtaaIncomeEntry] = Field(default_factory=list)
    dtaaAggregates: DtaaAggregates = Field(default_factory=DtaaAggregates)
    section89A: list[Section89AEntry] = Field(default_factory=list)
    section89AAggregates: Section89AAggregates = Field(default_factory=Section89AAggregates)
    accumulatedPf: list[AccumulatedPfEntry] = Field(default_factory=list)
    accumulatedPfAggregates: AccumulatedPfAggregates = Field(default_factory=AccumulatedPfAggregates)
    specialRateIncome: list[SpecialRateIncomeEntry] = Field(default_factory=list)
    unexplainedIncome: UnexplainedIncomeDetails = Field(default_factory=UnexplainedIncomeDetails)
    deductions: OtherSourcesDeductions = Field(default_factory=OtherSourcesDeductions)


# ---------------------------------------------------------------------------
# Exempt Income (Schedule EI)
# ---------------------------------------------------------------------------

class ExemptIncomeEntry(Identified):
    category: ExemptIncomeCategory = Field(default="OTH")
    subCategory: ExemptIncomeSubCategory = Field(default="Incmexmptnotification")
    description: str = Field(default="")
    grossAmount: Money = Field(default=Decimal("0"))


class AgriculturalLandParcel(Identified):
    nameOfDistrict: str = Field(default="")
    pinCode: str = Field(default="")
    measurementOfLand: Money = Field(default=Decimal("0"))
    ownedFlag: AgriculturalOwnedFlag = Field(default="O")
    irrigatedFlag: AgriculturalIrrigatedFlag = Field(default="IRG")


class DtaaExemptIncomeEntry(Identified):
    amountOfIncome: Money = Field(default=Decimal("0"))
    natureOfIncome: str = Field(default="")
    countryName: str = Field(default="")
    countryCode: str = Field(default="")
    articleOfDtaa: str = Field(default="")
    headOfIncome: DtaaExemptHeadOfIncome = Field(default="OS")
    trcFlag: Literal["Y", "N"] = Field(default="N")


class ExemptIncomeSchedule(_StrictModel):
    interestIncome: Money = Field(default=Decimal("0"))
    grossAgriculturalReceipts: Money = Field(default=Decimal("0"))
    agriculturalExpenses: Money = Field(default=Decimal("0"))
    unabsorbedAgriculturalLossPreviousEightYears: Money = Field(default=Decimal("0"))
    agriculturalIncomeRule7And8: Money = Field(default=Decimal("0"))
    netAgriculturalIncomeOrOtherIncomeRule7: Money = Field(default=Decimal("0"))
    agriculturalLandParcels: list[AgriculturalLandParcel] = Field(default_factory=list)
    otherExemptIncome: list[ExemptIncomeEntry] = Field(default_factory=list)
    othersTotal: Money = Field(default=Decimal("0"))
    dtaaExemptIncome: list[DtaaExemptIncomeEntry] = Field(default_factory=list)
    incomeNotChargeableToTax: Money = Field(default=Decimal("0"))
    incomeChargeableAsPerDtaa: Money = Field(default=Decimal("0"))
    passThroughIncomeNotChargeableToTax: Money = Field(default=Decimal("0"))
    totalExemptIncome: Money = Field(default=Decimal("0"))


# ---------------------------------------------------------------------------
# Deductions (Chapter VI-A)
# ---------------------------------------------------------------------------

class Investment80C(Identified):
    investmentType: str = Field(default="OTHER")
    identificationNo: str = Field(default="")
    accountOrPolicyNo: str = Field(default="")
    amount: Money = Field(default=Decimal("0"))
    dateOfInvestment: str = Field(default="")
    institutionName: str = Field(default="")
    institutionPAN: str = Field(default="")


class Policy80D(Identified):
    insurerName: str = Field(default="")
    policyNo: str = Field(default="")
    premiumAmount: Money = Field(default=Decimal("0"))
    policyType: PolicyType80D = Field(default="INDIVIDUAL")
    dateOfCommencement: str = Field(default="")


class Category80D(_StrictModel):
    policies: list[Policy80D] = Field(default_factory=list)
    preventiveCheckup: Money = Field(default=Decimal("0"))
    medicalExpense: Money = Field(default=Decimal("0"))


class Section80D(_StrictModel):
    selfSeniorCitizen: SeniorCitizenFlag = Field(default="N")
    parentsSeniorCitizen: SeniorCitizenFlag = Field(default="N")
    selfFamily: Category80D = Field(default_factory=Category80D)
    selfFamilySenior: Category80D = Field(default_factory=Category80D)
    parents: Category80D = Field(default_factory=Category80D)
    parentsSenior: Category80D = Field(default_factory=Category80D)


class Donation80G(Identified):
    category: Donation80GCategory = Field(default="50_APPROVAL_REQD")
    doneeName: str = Field(default="")
    doneePAN: str = Field(default="")
    arnNumber: str = Field(default="")
    addrDetail: str = Field(default="")
    city: str = Field(default="")
    stateCode: str = Field(default="")
    pinCode: str = Field(default="")
    donationAmtCash: Money = Field(default=Decimal("0"))
    donationAmtOtherMode: Money = Field(default=Decimal("0"))
    transactionRefNum: str = Field(default="")
    ifscCode: str = Field(default="")
    donationDate: str = Field(default="")
    receiptNumber: str = Field(default="")
    notes: str = Field(default="")


class DeductionLoan(Identified):
    section: DeductionLoanSection = Field(default="80E")
    loanTakenFrom: LenderType = Field(default="B")
    lenderName: str = Field(default="")
    lenderPAN: str = Field(default="")
    loanAccountNo: str = Field(default="")
    dateOfLoan: str = Field(default="")
    totalLoanAmount: Money = Field(default=Decimal("0"))
    outstandingAmount: Money = Field(default=Decimal("0"))
    interestAmount: Money = Field(default=Decimal("0"))
    firstTimeBuyerEligible: bool = Field(default=False)
    vehicleRegNo: str = Field(default="")


class LoanDeductions(_StrictModel):
    loans: list[DeductionLoan] = Field(default_factory=list)
    section80EEAStampDutyValue: Money = Field(default=Decimal("0"))


class Form10IAFiling(_StrictModel):
    filed: Form10IAFiled = Field(default="N")
    acknowledgementNumber: str = Field(default="")
    filingDate: Optional[str] = Field(default=None)
    formAckNum11A: str = Field(default="")


class BusinessDeductions(_StrictModel):
    totalPartBChapterVIA: Money = Field(default=Decimal("0"))
    section80IA: Money = Field(default=Decimal("0"))
    section80IAB: Money = Field(default=Decimal("0"))
    section80IB: Money = Field(default=Decimal("0"))
    section80IBA: Money = Field(default=Decimal("0"))
    section80IC: Money = Field(default=Decimal("0"))
    section80JJA: Money = Field(default=Decimal("0"))
    section80JJAA: Money = Field(default=Decimal("0"))
    totalPartCChapterVIA: Money = Field(default=Decimal("0"))
    totalPartCAAndDChapterVIA: Money = Field(default=Decimal("0"))


class ChapterVIA(_StrictModel):
    section80C: Money = Field(default=Decimal("0"))
    section80CCC: Money = Field(default=Decimal("0"))
    pensionContribution80CCC: Money = Field(default=Decimal("0"))
    section80CCDEmployeeOrSE: Money = Field(default=Decimal("0"))
    section80CCD1B: Money = Field(default=Decimal("0"))
    section80CCDEmployer: Money = Field(default=Decimal("0"))
    pranNumber: str = Field(default="")
    section80D: Money = Field(default=Decimal("0"))
    section80DD: Money = Field(default=Decimal("0"))
    section80DDNatureOfDisability: DisabilitySeverityCode = Field(default="")
    section80DDTypeOfDisability: DisabilitySeverityCode = Field(default="")
    section80DDDependentType: str = Field(default="")
    section80DDDependentPAN: str = Field(default="")
    section80DDDependentAadhaar: str = Field(default="")
    section80DDForm10IA: Form10IAFiling = Field(default_factory=Form10IAFiling)
    section80DDUDIDNumber: str = Field(default="")
    section80DDB: Money = Field(default=Decimal("0"))
    section80DDBUserType: Section80DDBUserType = Field(default="")
    section80DDBNameOfSpecDisease: str = Field(default="")
    section80E: Money = Field(default=Decimal("0"))
    section80EE: Money = Field(default=Decimal("0"))
    section80EEA: Money = Field(default=Decimal("0"))
    section80EEAStampDutyValue: Money = Field(default=Decimal("0"))
    section80EEB: Money = Field(default=Decimal("0"))
    section80G: Money = Field(default=Decimal("0"))
    section80GG: Money = Field(default=Decimal("0"))
    section80GGRentPaid: Money = Field(default=Decimal("0"))
    section80GGA: Money = Field(default=Decimal("0"))
    section80GGC: Money = Field(default=Decimal("0"))
    section80U: Money = Field(default=Decimal("0"))
    section80UNatureOfDisability: DisabilitySeverityCode = Field(default="")
    section80UTypeOfDisability: DisabilitySeverityCode = Field(default="")
    section80UForm10IA: Form10IAFiling = Field(default_factory=Form10IAFiling)
    section80UUDIDNumber: str = Field(default="")
    section80QQB: Money = Field(default=Decimal("0"))
    section80QQBRoyaltyIncome: Money = Field(default=Decimal("0"))
    section80QQBForm10CCDAckNum: str = Field(default="")
    section80RRB: Money = Field(default=Decimal("0"))
    section80RRBForm10CCEAckNum: str = Field(default="")
    section80TTA: Money = Field(default=Decimal("0"))
    section80TTB: Money = Field(default=Decimal("0"))
    form10BAAckNum: str = Field(default="")
    anyOtherSection80CCH: Money = Field(default=Decimal("0"))
    anyOtherSection80CCHDescription: str = Field(default="")
    totalChapterVIADeductions: Money = Field(default=Decimal("0"))
    businessDeductions: BusinessDeductions = Field(default_factory=BusinessDeductions)


class Schedule80GGAEntry(Identified):
    relevantClause: Section80GGAClause = Field(default="80GGA2a")
    doneeName: str = Field(default="")
    doneePAN: str = Field(default="")
    addressLine: str = Field(default="")
    city: str = Field(default="")
    stateCode: str = Field(default="")
    pinCode: str = Field(default="")
    cashAmount: Money = Field(default=Decimal("0"))
    otherModeAmount: Money = Field(default=Decimal("0"))


class Schedule80GGCEntry(Identified):
    cashAmount: Money = Field(default=Decimal("0"))
    otherModeAmount: Money = Field(default=Decimal("0"))
    contributionDate: str = Field(default="")
    transactionRef: str = Field(default="")
    ifscCode: str = Field(default="")
    politicalPartyName: str = Field(default="")
    politicalPartyPAN: str = Field(default="")


class Deductions(_StrictModel):
    section80C: list[Investment80C] = Field(default_factory=list)
    section80D: Section80D = Field(default_factory=Section80D)
    section80G: list[Donation80G] = Field(default_factory=list)
    loans: LoanDeductions = Field(default_factory=LoanDeductions)
    chapterVIA: ChapterVIA = Field(default_factory=ChapterVIA)
    schedule80GGA: list[Schedule80GGAEntry] = Field(default_factory=list)
    schedule80GGC: list[Schedule80GGCEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Taxes (TDS / TCS / Tax Payments)
# ---------------------------------------------------------------------------

class TaxDeductCreditDtls(_StrictModel):
    taxDeductedOwnHands: Money = Field(default=Decimal("0"))
    taxDeductedIncome: Money = Field(default=Decimal("0"))
    taxDeductedTDS: Money = Field(default=Decimal("0"))
    taxClaimedOwnHands: Money = Field(default=Decimal("0"))
    taxClaimedIncome: Money = Field(default=Decimal("0"))
    taxClaimedTDS: Money = Field(default=Decimal("0"))
    taxClaimedSpouseOthPrsnPAN: str = Field(default="")
    spouseOthPrsnAadhaar: str = Field(default="")


class TdsCredit(Identified):
    section: str = Field(default="192")
    deductorName: str = Field(default="")
    deductorTAN: str = Field(default="")
    deductorPAN: str = Field(default="")
    certificateNo: str = Field(default="")
    grossAmount: Money = Field(default=Decimal("0"))
    taxDeducted: Money = Field(default=Decimal("0"))
    deductionDate: str = Field(default="")
    uniqueTransactionNo: str = Field(default="")
    financialYear: str = Field(default="2025-26")
    verified26AS: bool = Field(default=False)
    claimedInReturn: bool = Field(default=True)
    schedule: TdsSchedule = Field(default="TDS1")
    tdsSectionCode: str = Field(default="")
    deductedYr: Union[int, Literal[""]] = Field(default="")
    headOfIncome: HeadOfIncome = Field(default="NA")
    tdsCreditName: TdsCreditName = Field(default="S")
    panOfOtherPerson: str = Field(default="")
    aadhaarOfOtherPerson: str = Field(default="")
    broughtFwdTDSAmt: Money = Field(default=Decimal("0"))
    amtCarriedFwd: Money = Field(default=Decimal("0"))
    claimOutOfTotTDSOnAmtPaid: Money = Field(default=Decimal("0"))
    taxDeductCreditDtls: TaxDeductCreditDtls = Field(default_factory=TaxDeductCreditDtls)
    nameOfTenant: str = Field(default="")
    grsRcptToTaxDeduct: Money = Field(default=Decimal("0"))
    tdsClaimed: Money = Field(default=Decimal("0"))
    panOfTenant: str = Field(default="")
    aadhaarOfTenant: str = Field(default="")
    tcsCreditOwner: TcsCreditOwner = Field(default="1")
    panOfSpouseOrOthrPrsn: str = Field(default="")
    tcsAmtCollOwnHand: Money = Field(default=Decimal("0"))
    tcsAmtCollSpouseOrOthrHand: Money = Field(default=Decimal("0"))
    tcsClaimedAmtCollOwnHand: Money = Field(default=Decimal("0"))
    tcsClaimedAmtCollSpouseOrOthrHand: Money = Field(default=Decimal("0"))


class TcsCredit(Identified):
    collectorName: str = Field(default="")
    collectorTAN: str = Field(default="")
    grossAmount: Money = Field(default=Decimal("0"))
    taxCollected: Money = Field(default=Decimal("0"))
    claimedInReturn: bool = Field(default=True)
    tcsCreditOwner: TcsCreditOwner = Field(default="1")
    panOfSpouseOrOthrPrsn: str = Field(default="")
    deductedYr: Union[int, Literal[""]] = Field(default="")
    broughtFwdTDSAmt: Money = Field(default=Decimal("0"))
    tcsAmtCollOwnHand: Money = Field(default=Decimal("0"))
    tcsAmtCollSpouseOrOthrHand: Money = Field(default=Decimal("0"))
    tcsClaimedAmtCollOwnHand: Money = Field(default=Decimal("0"))
    tcsClaimedAmtCollSpouseOrOthrHand: Money = Field(default=Decimal("0"))
    claimedPANOfSpouseOrOthrPrsn: str = Field(default="")


class TaxChallan(Identified):
    kind: TaxChallanKind = Field(default="ADVANCE_TAX")
    bsrCode: str = Field(default="")
    depositDate: str = Field(default="")
    challanSerialNo: int = Field(default=0)
    amount: Money = Field(default=Decimal("0"))
    cin: str = Field(default="")


class Taxes(_StrictModel):
    tds: list[TdsCredit] = Field(default_factory=list)
    tcs: list[TcsCredit] = Field(default_factory=list)
    challans: list[TaxChallan] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Bank accounts + Filing + Meta
# ---------------------------------------------------------------------------

class BankAccount(Identified):
    bankName: str = Field(default="")
    accountNumber: str = Field(default="")
    ifscCode: str = Field(default="")
    accountType: BankAccountType = Field(default="SB")
    useForRefund: bool = Field(default=False)


class FilingStatus(_StrictModel):
    filingSection: FilingSection = Field(default="139(1)")
    returnType: ReturnType = Field(default="ORIGINAL")
    originalAcknowledgementNumber: str = Field(default="")
    originalFilingDate: Optional[str] = Field(default=None)
    noticeNumber: str = Field(default="")


class PersonalInfo(_StrictModel):
    """Canonical taxpayer identity, contact, and official filing address."""

    name: str = Field(default="")
    firstName: str = Field(default="")
    middleName: str = Field(default="")
    surnameOrOrgName: str = Field(default="")
    fatherName: str = Field(default="")
    pan: str = Field(default="")
    aadhaar: str = Field(default="")
    email: str = Field(default="")
    mobile: str = Field(default="")
    secondaryEmail: str = Field(default="")
    secondaryMobile: str = Field(default="")
    secondaryMobileCountryCode: str = Field(default="")
    dateOfBirth: Optional[str] = Field(default=None)
    flatNo: str = Field(default="")
    residenceName: str = Field(default="")
    roadOrStreet: str = Field(default="")
    localityOrArea: str = Field(default="")
    city: str = Field(default="")
    stateCode: str = Field(default="")
    countryCode: str = Field(default="91")
    pinCode: str = Field(default="")
    zipCode: str = Field(default="")


class Verification(_StrictModel):
    capacity: VerificationCapacity = Field(default="SELF")
    place: str = Field(default="")
    date: Optional[str] = Field(default=None)
    declarationAccepted: bool = Field(default=False)


class TaxReturnPreparer(_StrictModel):
    used: bool = Field(default=False)
    identificationNumber: str = Field(default="")
    name: str = Field(default="")
    reimbursementFromGovernment: Money = Field(default=Decimal("0"))


class ImportProvenance(_StrictModel):
    source: ImportSource = Field(default="LEGACY")
    importedAt: Optional[str] = Field(default=None)
    reference: str = Field(default="")


class ReturnDraft(_StrictModel):
    """Canonical ITR return draft — the single typed persisted shape.

    Mirrors ``frontend/src/domain/returns/types.ts::ReturnDraft``.
    No legacy scalar aliases; every concept has one field.
    ``extra="forbid"`` rejects unknown keys on write.
    """

    schemaVersion: int = Field(default=1)
    assessmentYear: str = Field(default="")
    form: ItrForm = Field(default="ITR-1")
    regime: TaxRegime = Field(default="new")
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    filing: FilingStatus = Field(default_factory=FilingStatus)
    employers: list[Employer] = Field(default_factory=list)
    houseProperties: list[HouseProperty] = Field(default_factory=list)
    housePropertyPassThroughIncome: Money = Field(default=Decimal("0"))
    businesses: list[PresumptiveBusiness] = Field(default_factory=list)
    capitalGainsSchedule: dict = Field(default_factory=dict)
    otherSources: OtherSources = Field(default_factory=OtherSources)
    exemptIncome: ExemptIncomeSchedule = Field(default_factory=ExemptIncomeSchedule)
    deductions: Deductions = Field(default_factory=Deductions)
    taxes: Taxes = Field(default_factory=Taxes)
    bankAccounts: list[BankAccount] = Field(default_factory=list)
    verification: Verification = Field(default_factory=Verification)
    taxReturnPreparer: TaxReturnPreparer = Field(default_factory=TaxReturnPreparer)
    provenance: list[ImportProvenance] = Field(default_factory=list)


def create_empty_draft(assessment_year: str = "", form: ItrForm = "ITR-1", regime: TaxRegime = "new") -> ReturnDraft:
    """Return a fresh empty ReturnDraft with no shared mutable state."""
    return ReturnDraft(assessmentYear=assessment_year, form=form, regime=regime)


def draft_from_client_seed(client: object, assessment_year: str) -> ReturnDraft:
    """Seed a draft from a Client master row (personal info only).

    Mirrors the legacy ``GET /clients/{id}/itr/{year}`` fallback that
    returns client master fields when no draft exists yet. The additive
    official filing fields (firstName/surnameOrOrgName/fatherName/aadhaar/
    address components) are seeded from the Client master when present so
    the Phase 2 ``ITR1FilingProfile`` can be constructed without a
    separate ``PersonalInfoTab`` import.
    """
    draft = create_empty_draft(assessment_year=assessment_year)
    name = getattr(client, "name", "") or ""
    first_name = getattr(client, "first_name", "") or ""
    middle_name = getattr(client, "middle_name", "") or ""
    surname = getattr(client, "surname", "") or ""
    if not first_name and not surname and name:
        # Client master only stored the full name — keep it on `name`
        # so the mapper can surface it without losing the empty split.
        pass
    draft.personal = PersonalInfo(
        name=name,
        firstName=first_name,
        middleName=middle_name,
        surnameOrOrgName=surname,
        fatherName=getattr(client, "father_name", "") or "",
        pan=getattr(client, "pan", "") or "",
        aadhaar=getattr(client, "aadhaar", "") or "",
        email=getattr(client, "email", "") or "",
        mobile=getattr(client, "mobile", "") or "",
        dateOfBirth=getattr(client, "dob", None),
    )
    return draft
