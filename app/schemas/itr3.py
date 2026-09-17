"""
ITR-3 input schemas.

ITR-3 is applicable to individuals and HUFs having income from business or profession.

Eligibility:
  - Resident / Non-Resident / Not Ordinarily Resident
  - Having income under the head 'Profits and Gains of Business or Profession' (PGBP)
  - May also have: Salary, House Property, Capital Gains, Other Sources
  - Can carry forward / set off business losses
  - Total income can exceed Rs 50 lakh

Key schedules unique to ITR-3:
  - ITR3ScheduleBP: Core PGBP computation (BusinessIncOthThanSpec, SpecBusinessInc, etc.)
  - PARTA_BS: Balance Sheet
  - PARTA_PL: Profit & Loss Account
  - PartA_GEN2: Audit Info, Nature of Business
  - ScheduleDEP/DOA/DPM/DCG: Depreciation schedules
  - ScheduleUD: Unabsorbed Depreciation
  - ScheduleIF: Interest from Firms
  - ScheduleGST: GST details
  - 80-IA, 80-IB, 80-IC, 80RA, 10AA: Business-specific deductions
  - ManufacturingAccount, TradingAccount: P&L sub-schedules
  - PARTA_OI: Other Information (disallowances)
  - ScheduleICDS: Income Computation and Disclosure Standards
  - ScheduleESR: Expenditure on Scientific Research
  - ScheduleTPSA: Transfer Pricing Secondary Adjustment
"""

from decimal import Decimal
from enum import Enum
from typing import List, Optional, Any, Literal
from datetime import date

from pydantic import BaseModel, Field, ConfigDict

from app.schemas.itr1 import (
    AgeBracket, TaxRegime,
    SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions, CapitalGainsIncome,
    Schedule80D as ITR1Schedule80D,
    TDS1Entry, TDS2Entry, TDS3Entry, TCSEntry,
)
from app.schemas.itr2 import (
    CGTransaction, CG112AScrip, VDATransaction,
    BFLossItem, ScheduleSIEntry, AgriculturalIncome, ExemptIncome,
    FSICountryEntry, TR1Entry, SPIEntry, PTIEntry, AMTInput,
    ForeignAssetEntry, AssetLiabilityInput, Schedule5AInput, ESOPDeferralInput,
    TaxPaymentDetail, TDS3FilingDetail,
    ResidentialStatus, ReturnFileSection,
)


# ---------------------------------------------------------------------------
# PGBP — Business Income (ITR-3 core)
# ---------------------------------------------------------------------------

class PresumptiveScheme(str, Enum):
    """Presumptive taxation scheme, if opted."""
    NONE = "none"
    S44AD = "44AD"
    S44ADA = "44ADA"
    S44AE = "44AE"


class OIAmountGroup(BaseModel):
    """Typed monetary children used by ITR-3 PARTA_OI disclosures."""
    StkInsurPrem: Decimal = Decimal("0")
    EmpHealthInsurPrem: Decimal = Decimal("0")
    EmpBonusCommSum: Decimal = Decimal("0")
    IntOnBorrCap: Decimal = Decimal("0")
    ZeroCoupBondDisc: Decimal = Decimal("0")
    RecogPFContribAmt: Decimal = Decimal("0")
    AppSuperAnnFundAmt: Decimal = Decimal("0")
    PensionSchemeSec80CCD: Decimal = Decimal("0")
    AppGratFundAmt: Decimal = Decimal("0")
    OthFundAmt: Decimal = Decimal("0")
    EmpContributionCredits: Decimal = Decimal("0")
    BadDebtDoubtAmt: Decimal = Decimal("0")
    BadDebtDoubtProvn: Decimal = Decimal("0")
    SpecResrvTranfr: Decimal = Decimal("0")
    FamPlanPromoExp: Decimal = Decimal("0")
    SecuritiesPaidAmt: Decimal = Decimal("0")
    MrktLossOthExpLossICDS: Decimal = Decimal("0")
    OthDisallowances: Decimal = Decimal("0")
    TotAmtDisallUs36: Decimal = Decimal("0")
    CapitalNatureExp: Decimal = Decimal("0")
    PersonalExp: Decimal = Decimal("0")
    BusOrProfessnExp: Decimal = Decimal("0")
    PoliticPartyExp: Decimal = Decimal("0")
    LawVoilatPenalExp: Decimal = Decimal("0")
    OthPenalFineExp: Decimal = Decimal("0")
    OffenceExp: Decimal = Decimal("0")
    ContigentLiability: Decimal = Decimal("0")
    OthAmtNotAllowUs37: Decimal = Decimal("0")
    TotAmtDisallUs37: Decimal = Decimal("0")
    NonCompChapXVIIBAmt: Decimal = Decimal("0")
    NonComp40aiiChapXVIIBAmt: Decimal = Decimal("0")
    NonComp40aibChapXVIIBAmt: Decimal = Decimal("0")
    NonComp40aiiiChapXVIIBAmt: Decimal = Decimal("0")
    TaxAmtOnProfits: Decimal = Decimal("0")
    WTAmt: Decimal = Decimal("0")
    RolyatyOrServiceFee: Decimal = Decimal("0")
    IntSalBonPartner: Decimal = Decimal("0")
    OthDisallow: Decimal = Decimal("0")
    TotAmtDisallUs40: Decimal = Decimal("0")
    AmtDisallUs40PyNowAll: Decimal = Decimal("0")
    AmtPaidUs40A2b: Decimal = Decimal("0")
    AmtGT20kCash: Decimal = Decimal("0")
    ProvPmtGrat: Decimal = Decimal("0")
    ContToSetupTrust: Decimal = Decimal("0")
    TotAmtDisallUs40A: Decimal = Decimal("0")
    AmtUs43B: Decimal = Decimal("0")


class OIStockValuation(BaseModel):
    """Typed PARTA_OI closing-stock valuation method."""
    ValRawMaterial: str = "1"
    ValFinishedGoods: str = "1"
    ChngStockValMetFlg: str = "N"
    EffectOnPL: Decimal = Decimal("0")
    DecProOrIncLossUs145_A: Decimal = Decimal("0")


class OINoCredit(BaseModel):
    """Typed PARTA_OI credits not routed through profit and loss."""
    Section28Items: Decimal = Decimal("0")
    ProformaCreditsDue: Decimal = Decimal("0")
    PrevYrEscalClaim: Decimal = Decimal("0")
    OthItemInc: Decimal = Decimal("0")
    CapReceipt: Decimal = Decimal("0")
    TotNoCredToPLAmt: Decimal = Decimal("0")


class ITR3PartAOI(BaseModel):
    """Complete typed ITR-3 PARTA_OI schedule."""
    MethodOfAcct: str = "MERC"
    ChangeInAcctMethFlg: str = "N"
    ProfDeviatDueAcctMeth: Decimal = Decimal("0")
    DecProOrIncLossUs145_2: Decimal = Decimal("0")
    MethodOfValClgStk: OIStockValuation = Field(default_factory=OIStockValuation)
    NoCredToPLAmt: OINoCredit = Field(default_factory=OINoCredit)
    AmtDisallUs36: OIAmountGroup = Field(default_factory=OIAmountGroup)
    AmtDisallUs37: OIAmountGroup = Field(default_factory=OIAmountGroup)
    AmtDisallUs40: OIAmountGroup = Field(default_factory=OIAmountGroup)
    AmtDisallUs40A: OIAmountGroup = Field(default_factory=OIAmountGroup)
    AmtDisallUs43BPyNowAll: OIAmountGroup = Field(default_factory=OIAmountGroup)
    AmtDisall43B: OIAmountGroup = Field(default_factory=OIAmountGroup)
    AmtExciseCustomsVATOutstanding: OIAmountGroup = Field(default_factory=OIAmountGroup)
    DeemedProfUs33ABs: Decimal = Decimal("0")
    DeemedProfUs33AB: Decimal = Decimal("0")
    DeemedProfUs33ABA: Decimal = Decimal("0")
    ProfTaxAmtUs41: Decimal = Decimal("0")
    PriorAmtIncCrDrPL: Decimal = Decimal("0")
    AmountOfExpDisAllwUs14A: Decimal = Decimal("0")
    InterestDisAllowUs23SMEAct: Decimal = Decimal("0")
    ScheduleTPSAFlg: str = "N"


class ITR3ScheduleTPSATaxPayment(BaseModel):
    """Single tax-deposit row in official ITR-3 Schedule TPSA."""

    BSRCode: str
    BankBranchName: str
    DateDep: str
    SrlNoOfChaln: int
    Amount: Decimal = Decimal("0")


class ITR3ScheduleTPSA(BaseModel):
    """Typed ITR-3 Schedule TPSA (secondary adjustment tax under section 92CE)."""

    AmtPrimaryAdjUs92CE_2A: Decimal = Decimal("0")
    AdditionalIncTax18PercAbove: Decimal = Decimal("0")
    Surcharge12Perc: Decimal = Decimal("0")
    HealthEducationCess: Decimal = Decimal("0")
    TotalAdditionalTax: Decimal = Decimal("0")
    TaxesPaid: Decimal = Decimal("0")
    NetTaxPayable: Decimal = Decimal("0")
    DtlsTaxesPaid: Optional[List[ITR3ScheduleTPSATaxPayment]] = None
    TotalAmountDeposited: Decimal = Decimal("0")


class ITR3TradingQDRow(BaseModel):
    """Typed PARTA_QD trading-inventory row."""
    ItemName: str
    UnitOfMeasure: str
    OpeningStock: Decimal
    PurchaseQty: Decimal
    SaleQty: Decimal
    ClgStock: Decimal
    AnyShortExces: Decimal


class ITR3RawMaterialQDRow(BaseModel):
    """Typed PARTA_QD raw-material inventory row."""
    ItemName: str
    UnitOfMeasure: str
    OpeningStock: Decimal
    PurchaseQty: Decimal
    PrevYrConsum: Decimal
    SaleQty: Decimal
    ClgStock: Decimal
    yldFinisProd: Decimal
    PercentYld: Decimal
    AnyShortExces: Decimal


class ITR3FinishedProductQDRow(BaseModel):
    """Typed PARTA_QD finished-product inventory row."""
    ItemName: str
    UnitOfMeasure: str
    OpeningStock: Decimal
    PurchaseQty: Decimal
    PrevyrManfact: Decimal
    SaleQty: Decimal
    ClgStock: Decimal
    AnyShortExces: Decimal


class ITR3PartAQD(BaseModel):
    """Complete typed PARTA_QD schedule with official nested collections."""
    TradingConcern: Optional[List[ITR3TradingQDRow]] = None
    RawMaterial: Optional[List[ITR3RawMaterialQDRow]] = None
    FinishrByProd: Optional[List[ITR3FinishedProductQDRow]] = None


class BusinessIncome(BaseModel):
    """
    Core business income input for ITR-3.

    Captures the key financial figures needed to compute PGBP income.
    The full P&L and balance sheet can be provided via sub-schedules below.
    """

    net_profit_before_tax: Decimal = Field(
        default=Decimal("0"),
        description="Net profit as per Profit & Loss account before tax (PGBP).",
    )

    # Disallowances / Additions
    disallowance_us36: Decimal = Field(default=Decimal("0"), ge=0)
    disallowance_us37: Decimal = Field(default=Decimal("0"), ge=0)
    disallowance_us40: Decimal = Field(default=Decimal("0"), ge=0)
    disallowance_us40a: Decimal = Field(default=Decimal("0"), ge=0)
    disallowance_us43b: Decimal = Field(default=Decimal("0"), ge=0)

    # Deemed Incomes
    deemed_income_us41: Decimal = Field(default=Decimal("0"), ge=0)
    deemed_income_us33ab: Decimal = Field(default=Decimal("0"), ge=0)
    deemed_income_us33aba: Decimal = Field(default=Decimal("0"), ge=0)
    deemed_income_us35aba: Decimal = Field(default=Decimal("0"), ge=0)
    deemed_income_us35abb: Decimal = Field(default=Decimal("0"), ge=0)
    deemed_income_us32ad: Decimal = Field(default=Decimal("0"), ge=0)
    deemed_income_us40a3a: Decimal = Field(default=Decimal("0"), ge=0)
    deemed_income_us43ca: Decimal = Field(default=Decimal("0"), ge=0)
    deemed_income_us72a: Decimal = Field(default=Decimal("0"), ge=0)
    deemed_income_us80hhd: Decimal = Field(default=Decimal("0"), ge=0)
    deemed_income_us80ia: Decimal = Field(default=Decimal("0"), ge=0)

    # Deductions allowed
    deduction_us32_1_iii: Decimal = Field(default=Decimal("0"), ge=0)

    # Depreciation
    depreciation_books: Decimal = Field(default=Decimal("0"), ge=0,
                                         description="Depreciation as per Companies Act / books.")
    depreciation_it_act: Decimal = Field(default=Decimal("0"), ge=0,
                                          description="Depreciation as per Income Tax Act (Schedule DEP).")

    # ICDS Adjustments (net effect)
    icds_increase: Decimal = Field(default=Decimal("0"), ge=0)
    icds_decrease: Decimal = Field(default=Decimal("0"), ge=0)

    # Other
    other_additions: Decimal = Field(default=Decimal("0"), ge=0)
    other_deductions: Decimal = Field(default=Decimal("0"), ge=0)

    # Speculative business
    speculative_net_pl: Decimal = Field(default=Decimal("0"))
    speculative_additions: Decimal = Field(default=Decimal("0"), ge=0)
    speculative_deductions: Decimal = Field(default=Decimal("0"), ge=0)

    # Specified business (35AD)
    specified_business_net_pl: Decimal = Field(default=Decimal("0"))
    specified_business_additions: Decimal = Field(default=Decimal("0"), ge=0)
    specified_business_deductions: Decimal = Field(default=Decimal("0"), ge=0)


class ManufacturingAccount(BaseModel):
    """Typed official ManufacturingAccount schedule fields."""
    opening_inventory: dict[str, Decimal] = Field(default_factory=dict)
    closing_stock: dict[str, Decimal] = Field(default_factory=dict)
    cost_of_goods_produced: Decimal = Field(default=Decimal("0"), ge=0)


class TradingAccount(BaseModel):
    """Typed official TradingAccount schedule fields and totals."""
    values: dict[str, Decimal] = Field(default_factory=dict)


class ITR3BusinessAccounts(BaseModel):
    """Schema-shaped Manufacturing Account and Trading Account payloads.

    The keys intentionally mirror the official CBDT schedule names exactly;
    official JSON-schema validation remains the final authority while the
    remaining nested accounting fields are progressively typed.
    """

    manufacturing_account: Optional[ManufacturingAccount] = Field(default=None)
    trading_account: Optional[TradingAccount] = Field(default=None)


class PLOtherIncome(BaseModel):
    """Typed PARTA_PL other-income credit breakdown."""

    rent_income: Decimal = Field(default=Decimal("0"), alias="RentInc", ge=0)
    commissions: Decimal = Field(default=Decimal("0"), alias="Comissions", ge=0)
    dividends: Decimal = Field(default=Decimal("0"), alias="Dividends", ge=0)
    interest_income: Decimal = Field(default=Decimal("0"), alias="InterestInc", ge=0)
    profit_on_sale_fixed_asset: Decimal = Field(default=Decimal("0"), alias="ProfitOnSaleFixedAsset", ge=0)
    profit_on_investment_stt: Decimal = Field(default=Decimal("0"), alias="ProfitOnInvChrSTT", ge=0)
    profit_on_other_investment: Decimal = Field(default=Decimal("0"), alias="ProfitOnOthInv", ge=0)
    profit_on_currency_fluctuation: Decimal = Field(default=Decimal("0"), alias="ProfitOnCurrFluct", ge=0)
    profit_on_inventory_conversion: Decimal = Field(default=Decimal("0"), alias="ProfitOnCnvInvntryToCapAsst", ge=0)
    profit_on_agricultural_income: Decimal = Field(default=Decimal("0"), alias="ProfitOnAgriIncome", ge=0)
    miscellaneous_income: Decimal = Field(default=Decimal("0"), alias="MiscOthIncome", ge=0)
    total: Decimal = Field(default=Decimal("0"), alias="TotOthIncome", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class PLInterestExpense(BaseModel):
    """Typed PARTA_PL interest-expense credit-party breakdown."""

    non_resident_or_other_company: Decimal = Field(default=Decimal("0"), alias="NonResOtherCompany", ge=0)
    others: Decimal = Field(default=Decimal("0"), alias="Others", ge=0)
    total: Decimal = Field(default=Decimal("0"), alias="InterestExpdr", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class ProfitAndLoss(BaseModel):
    """Typed required PARTA_PL totals and bounded credit/debit disclosures."""

    gross_profit: Decimal = Field(default=Decimal("0"), ge=0)
    expenditure: Decimal = Field(default=Decimal("0"), ge=0)
    net_income_from_special_activity: Decimal = Field(default=Decimal("0"), ge=0)
    turnover_from_special_activity: Decimal = Field(default=Decimal("0"), ge=0)
    no_books_gross_receipt: Decimal = Field(default=Decimal("0"), ge=0)
    no_books_gross_profit: Decimal = Field(default=Decimal("0"), ge=0)
    no_books_expenses: Decimal = Field(default=Decimal("0"), ge=0)
    no_books_net_profit: Decimal = Field(default=Decimal("0"), ge=0)
    provision_current_tax: Decimal = Field(default=Decimal("0"), ge=0)
    provision_deferred_tax: Decimal = Field(default=Decimal("0"), ge=0)
    profit_after_tax: Decimal = Field(default=Decimal("0"), ge=0)
    gross_profit_from_trading: Decimal = Field(default=Decimal("0"), ge=0)
    other_income: Decimal = Field(default=Decimal("0"), ge=0)
    other_income_breakdown: PLOtherIncome = Field(default_factory=PLOtherIncome)
    total_credits: Decimal = Field(default=Decimal("0"), ge=0)
    total_expenses: Decimal = Field(default=Decimal("0"), ge=0)
    pbidta: Decimal = Field(default=Decimal("0"), ge=0)
    interest_expense: PLInterestExpense = Field(default_factory=PLInterestExpense)
    depreciation_amortization: Decimal = Field(default=Decimal("0"), ge=0)
    profit_before_tax: Decimal = Field(default=Decimal("0"))


class BSReserves(BaseModel):
    """Typed PARTA_BS reserves and surplus breakdown."""
    rev_reserve: Decimal = Field(Decimal("0"), alias="RevResr", ge=0)
    capital_reserve: Decimal = Field(Decimal("0"), alias="CapResr", ge=0)
    statutory_reserve: Decimal = Field(Decimal("0"), alias="StatResr", ge=0)
    other_reserve: Decimal = Field(Decimal("0"), alias="OthResr", ge=0)
    total: Decimal = Field(Decimal("0"), alias="TotResrNSurp", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSProprietorsFund(BaseModel):
    """Typed PARTA_BS proprietors-fund group."""
    capital: Decimal = Field(Decimal("0"), alias="PropCap", ge=0)
    reserves: BSReserves = Field(default_factory=BSReserves, alias="ResrNSurp")
    total: Decimal = Field(Decimal("0"), alias="TotPropFund", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSLoanGroup(BaseModel):
    """Typed secured or unsecured loan group in PARTA_BS."""
    foreign_currency: Decimal = Field(Decimal("0"), alias="ForeignCurrLoan", ge=0)
    from_bank: Decimal = Field(Decimal("0"), alias="FrmBank", ge=0)
    from_others: Decimal = Field(Decimal("0"), alias="FrmOthrs", ge=0)
    total_rupee: Decimal = Field(Decimal("0"), alias="TotRupeeLoan", ge=0)
    total: Decimal = Field(Decimal("0"), alias="TotSecrLoan", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSUnsecuredLoanGroup(BaseModel):
    """Typed unsecured loan group in PARTA_BS."""
    from_bank: Decimal = Field(Decimal("0"), alias="FrmBank", ge=0)
    from_others: Decimal = Field(Decimal("0"), alias="FrmOthrs", ge=0)
    total: Decimal = Field(Decimal("0"), alias="TotUnSecrLoan", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSAdvances(BaseModel):
    """Typed advances group in PARTA_BS."""
    from_persons: Decimal = Field(Decimal("0"), alias="FromPrsn", ge=0)
    from_others: Decimal = Field(Decimal("0"), alias="FromOthers", ge=0)
    total: Decimal = Field(Decimal("0"), alias="TotalAdvances", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSFixedAsset(BaseModel):
    """Typed fixed-asset group in PARTA_BS."""
    gross_block: Decimal = Field(Decimal("0"), alias="GrossBlock", ge=0)
    depreciation: Decimal = Field(Decimal("0"), alias="Depreciation", ge=0)
    net_block: Decimal = Field(Decimal("0"), alias="NetBlock", ge=0)
    capital_work_progress: Decimal = Field(Decimal("0"), alias="CapWrkProg", ge=0)
    total: Decimal = Field(Decimal("0"), alias="TotFixedAsset", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSInventory(BaseModel):
    """Typed inventory group in PARTA_BS."""
    stores: Decimal = Field(Decimal("0"), alias="StoresConsumables", ge=0)
    raw_material: Decimal = Field(Decimal("0"), alias="RawMatl", ge=0)
    work_in_process: Decimal = Field(Decimal("0"), alias="StkInProcess", ge=0)
    finished_goods: Decimal = Field(Decimal("0"), alias="FinOrTradGood", ge=0)
    total: Decimal = Field(Decimal("0"), alias="TotInventries", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSCashBank(BaseModel):
    """Typed cash and bank group in PARTA_BS."""
    cash: Decimal = Field(Decimal("0"), alias="CashinHand", ge=0)
    bank: Decimal = Field(Decimal("0"), alias="BankBal", ge=0)
    total: Decimal = Field(Decimal("0"), alias="TotCashOrBankBal", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSCurrentAssets(BaseModel):
    """Typed current-assets group in PARTA_BS."""
    inventories: BSInventory = Field(default_factory=BSInventory, alias="Inventories")
    receivables: Decimal = Field(Decimal("0"), alias="SndryDebtors", ge=0)
    cash_bank: BSCashBank = Field(default_factory=BSCashBank, alias="CashOrBankBal")
    other: Decimal = Field(Decimal("0"), alias="OthCurrAsset", ge=0)
    total: Decimal = Field(Decimal("0"), alias="TotCurrAsset", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSCurrentLiabilities(BaseModel):
    """Typed current-liabilities group in PARTA_BS."""
    creditors: Decimal = Field(Decimal("0"), alias="SundryCred", ge=0)
    leased_asset: Decimal = Field(Decimal("0"), alias="LiabForLeasedAsset", ge=0)
    accrued_lease_interest: Decimal = Field(Decimal("0"), alias="AccrIntonLeasedAsset", ge=0)
    accrued_interest: Decimal = Field(Decimal("0"), alias="AccrIntNotDue", ge=0)
    total: Decimal = Field(Decimal("0"), alias="TotCurrLiabilities", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSProvisions(BaseModel):
    """Typed provisions group in PARTA_BS."""
    income_tax: Decimal = Field(Decimal("0"), alias="ITProvision", ge=0)
    employee_benefits: Decimal = Field(Decimal("0"), alias="ELSuperAnnGratProvision", ge=0)
    other: Decimal = Field(Decimal("0"), alias="OthProvision", ge=0)
    total: Decimal = Field(Decimal("0"), alias="TotProvisions", ge=0)
    model_config = ConfigDict(populate_by_name=True)


class BSOfficial(BaseModel):
    """Explicitly typed, bounded PARTA_BS source tree."""
    proprietors_fund: BSProprietorsFund = Field(default_factory=BSProprietorsFund, alias="PropFund")
    secured_loans: BSLoanGroup = Field(default_factory=BSLoanGroup, alias="SecrLoan")
    unsecured_loans: BSUnsecuredLoanGroup = Field(default_factory=BSUnsecuredLoanGroup, alias="UnsecrLoan")
    advances: BSAdvances = Field(default_factory=BSAdvances, alias="Advances")
    deferred_tax: Decimal = Field(Decimal("0"), alias="DeferredTax", ge=0)
    total_sources: Decimal = Field(Decimal("0"), alias="TotFundSrc", ge=0)
    fixed_assets: BSFixedAsset = Field(default_factory=BSFixedAsset, alias="FixedAsset")
    current_assets: BSCurrentAssets = Field(default_factory=BSCurrentAssets, alias="CurrAsset")
    current_liabilities: BSCurrentLiabilities = Field(default_factory=BSCurrentLiabilities, alias="CurrLiabilities")
    provisions: BSProvisions = Field(default_factory=BSProvisions, alias="Provisions")
    model_config = ConfigDict(populate_by_name=True)


class BalanceSheet(BaseModel):
    """Balance sheet summary and explicit PARTA_BS source for ITR-3."""
    proprietors_fund: Decimal = Field(default=Decimal("0"), ge=0)
    secured_loans: Decimal = Field(default=Decimal("0"), ge=0)
    unsecured_loans: Decimal = Field(default=Decimal("0"), ge=0)
    current_liabilities: Decimal = Field(default=Decimal("0"), ge=0)
    total_liabilities: Decimal = Field(default=Decimal("0"), ge=0)
    fixed_assets: Decimal = Field(default=Decimal("0"), ge=0)
    current_assets: Decimal = Field(default=Decimal("0"), ge=0)
    total_assets: Decimal = Field(default=Decimal("0"), ge=0)
    official: Optional[BSOfficial] = None


class NatureOfBusiness(BaseModel):
    """Nature of business codes for ITR-3 PartA_GEN2."""
    # A handful of official codes carry a disambiguating "_N" suffix (e.g.
    # 16019_1 "Medical Profession", 20023_1 "Sports Management", 21008_1
    # "Event Management" -- confirmed present in the real enum, distinct
    # from their un-suffixed base codes). A plain ^[0-9]{5}$ pattern makes
    # these three legitimate codes impossible to construct at all.
    code: str = Field(default="00001", pattern=r"^[0-9]{5}(_[0-9]+)?$")
    trade_name: Optional[str] = Field(default=None, max_length=125)
    description: Optional[str] = Field(default=None, max_length=125)


class AuditInfo(BaseModel):
    """Audit information for PartA_GEN2 (form A20)."""
    liable_sec_44ab: bool = Field(default=False)
    liable_sec_44aa: bool = Field(default=False)
    liable_sec_92e: bool = Field(default=False)
    # Schema AccountAuditFlag -- A20(b) "Are you liable for audit u/s 44AB?"
    account_audited: bool = Field(default=False)
    # Schema AuditAccountantFlg -- A20(c) "have the accounts been audited by
    # an accountant?" -- a genuinely distinct question from AccountAuditFlag
    # per the schema's own two separate properties.
    audited_by_accountant: bool = Field(default=False)
    income_declared_under_presumptive: bool = Field(default=False)
    # A20(a2i) turnover band -- schema TotalSalesExcOneCr enum.
    total_sales_band: Optional[str] = Field(default=None)
    # A20(a2ii)/(a2iii) cash-receipts/payments percentage bands.
    receipts_cash_band: Optional[str] = Field(default=None)
    payments_cash_band: Optional[str] = Field(default=None)
    # A20(b)(i)/(ii)/(iii) reason for 44AB liability.
    condition_44ab: Optional[str] = Field(default=None)
    presumptive_44ad: bool = Field(default=False)
    presumptive_44ada: bool = Field(default=False)
    presumptive_44ae: bool = Field(default=False)
    presumptive_44bb: bool = Field(default=False)
    # A20(c)(1)-(4) audit-report detail.
    audit_report_furnish_date: Optional[str] = Field(default=None)
    ack_num_44ab: Optional[str] = Field(default=None)
    auditor_firm_name: Optional[str] = Field(default=None)
    auditor_firm_pan: Optional[str] = Field(default=None)
    auditor_firm_aadhaar: Optional[str] = Field(default=None)
    # A20(d)(ii) 92E audit detail -- "audited" is distinct from "liable"
    # (liable_sec_92e above only asks whether section 92E applies at all).
    audited_under_92e: bool = Field(default=False)
    audit_92e_date: Optional[str] = Field(default=None)
    ack_num_92e: Optional[str] = Field(default=None)
    # A20(d)(iii) other-section audit reports (schema AuditDetails[]).
    other_section_audit_entries: List[dict[str, Any]] = Field(default_factory=list)
    # A20(e) audit report(s) under Acts other than the Income-tax Act
    # (schema AuditReportDetails[]).
    other_act_audit_entries: List[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Partner in Firm details (Schedule IF)
# ---------------------------------------------------------------------------

class PartnerInFirm(BaseModel):
    """Typed Schedule IF partnership-firm disclosure row."""

    firm_name: str = Field(default="", max_length=125)
    firm_pan: str = Field(default="AAAAA0000A", pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    is_liable_to_audit: bool = False
    sec92e_firm: bool = False
    profit_share_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    profit_share_amount: Decimal = Field(default=Decimal("0"))
    interest_amount: Decimal = Field(default=Decimal("0"), ge=0)
    remuneration_amount: Decimal = Field(default=Decimal("0"), ge=0)
    capital_balance: Decimal = Field(default=Decimal("0"))


# ---------------------------------------------------------------------------
# Depreciation schedules (official ITR-3 2026 schema)
# ---------------------------------------------------------------------------

class _DepreciationDetail(BaseModel):
    """Typed common depreciation-block arithmetic disclosed by the CBDT schema."""
    WDVFirstDay: Decimal
    AdjustmentSec115BAC: Optional[Decimal] = None
    Total: Optional[Decimal] = None
    AdditionsGrThan180Days: Decimal
    RealizationTotalPeriod: Decimal
    FullRateDeprAmt: Decimal
    AdditionsLessThan180Days: Decimal
    RealizationPeriodLessThan180days: Decimal
    HalfRateDeprAmt: Decimal
    DepreciationAtFullRate: Decimal
    DepreciationAtHalfRate: Decimal
    AddlnDeprOnGT180DayAdditions: Optional[Decimal] = None
    AddlnDeprOnLessThan180DayAdditions: Optional[Decimal] = None
    AddlnDeprOnAssetLessThan180Days: Optional[Decimal] = None
    TotalDepreciation: Decimal
    DepDisAllowUs38_2: Decimal
    NetAggregateDepreciation: Decimal
    ProportionateAggDepreciation: Decimal
    ExpdrOnTrforSaleAsset: Decimal
    CapGainUs50: Decimal
    WDVLastDay: Decimal


class _DepreciationDetailRate45(BaseModel):
    """Typed 45-percent plant-and-machinery depreciation block."""
    WDVFirstDay: Decimal
    AdjustmentSec115BAC: Optional[Decimal] = None
    Total: Optional[Decimal] = None
    RealizationTotalPeriod: Decimal
    FullRateDeprAmt: Decimal
    DepreciationAtFullRate: Decimal
    TotalDepreciation: Decimal
    DepDisAllowUs38_2: Decimal
    NetAggregateDepreciation: Decimal
    ProportionateAggDepreciation: Decimal
    ExpdrOnTrforSaleAsset: Decimal
    CapGainUs50: Decimal
    WDVLastDay: Decimal


class _DepreciationDetailDOA(BaseModel):
    """Typed depreciation block used by Schedule DOA."""
    WDVFirstDay: Decimal
    AdditionsGrThan180Days: Decimal
    RealizationTotalPeriod: Decimal
    FullRateDeprAmt: Decimal
    AdditionsLessThan180Days: Decimal
    RealizationPeriodLessThan180days: Decimal
    HalfRateDeprAmt: Decimal
    DepreciationAtFullRate: Decimal
    DepreciationAtHalfRate: Decimal
    TotalDepreciation: Decimal
    DepDisAllowUs38_2: Decimal
    NetAggregateDepreciation: Decimal
    ProportionateAggDepreciation: Decimal
    ExpdrOnTrforSaleAsset: Decimal
    CapGainUs50: Decimal
    WDVLastDay: Decimal


class _Rate(BaseModel):
    """Typed rate wrapper for a Schedule DPM depreciation block."""
    DepreciationDetail: _DepreciationDetail


class _Rate45(BaseModel):
    """Typed 45-percent rate wrapper."""
    DepreciationDetail: _DepreciationDetailRate45


class _RateDOA(BaseModel):
    """Typed rate wrapper for a Schedule DOA depreciation block."""
    DepreciationDetail: _DepreciationDetailDOA


class DepreciationDetailForLand(BaseModel):
    """Typed land opening and closing written-down values."""
    WDVFirstDay: Decimal
    WDVLastDay: Decimal


class _Land(BaseModel):
    """Typed land block in Schedule DOA."""
    DepreciationDetail: DepreciationDetailForLand


class _BuildingSummary(BaseModel):
    """Typed building depreciation summary."""
    DeprBlockTot5Percent: Decimal
    DeprBlockTot10Percent: Decimal
    DeprBlockTot40Percent: Decimal
    TotBuildng: Decimal


class _PlantMachinerySummary(BaseModel):
    """Typed plant and machinery depreciation summary."""
    DeprBlockTot15Percent: Decimal
    DeprBlockTot30Percent: Decimal
    DeprBlockTot40Percent: Decimal
    DeprBlockTot45Percent: Decimal
    TotPlntMach: Decimal


class _Summary(BaseModel):
    """Typed Schedule DEP summary."""
    PlantMachinerySummary: Optional[_PlantMachinerySummary] = None
    BuildingSummary: Optional[_BuildingSummary] = None
    FurnitureSummary: Optional[Decimal] = None
    IntangibleAssetSummary: Optional[Decimal] = None
    ShipsSummary: Optional[Decimal] = None
    TotalDepreciation: Decimal


class _SummaryCG(BaseModel):
    """Typed Schedule DCG summary."""
    PlantMachinerySummaryCG: Optional[_PlantMachinerySummary] = None
    BuildingSummaryCG: Optional[_BuildingSummary] = None
    FurnitureSummary: Optional[Decimal] = None
    IntangibleAssetSummary: Optional[Decimal] = None
    ShipsSummary: Optional[Decimal] = None
    TotalDepreciation: Decimal


class _PlantMachinery(BaseModel):
    """Typed official plant-and-machinery rate groups."""
    Rate15: Optional[_Rate] = None
    Rate30: Optional[_Rate] = None
    Rate40: Optional[_Rate] = None
    Rate45: Optional[_Rate45] = None


class _Building(BaseModel):
    """Typed official building rate groups."""
    Rate5: Optional[_RateDOA] = None
    Rate10: Optional[_RateDOA] = None
    Rate40: Optional[_RateDOA] = None


class _FurnitureFittings(BaseModel):
    """Typed official furniture and fittings rate group."""
    Rate10: Optional[_RateDOA] = None


class _IntangibleAssets(BaseModel):
    """Typed official intangible-asset rate group."""
    Rate25: Optional[_RateDOA] = None


class _Ships(BaseModel):
    """Typed official ships rate group."""
    Rate20: Optional[_RateDOA] = None


class ScheduleDPM(BaseModel):
    """Schedule DPM: plant and machinery depreciation by statutory rate."""
    PlantMachinery: _PlantMachinery


class ScheduleDOA(BaseModel):
    """Schedule DOA: depreciation on assets other than plant and machinery."""
    Land: Optional[_Land] = None
    Building: Optional[_Building] = None
    FurnitureFittings: Optional[_FurnitureFittings] = None
    IntangibleAssets: Optional[_IntangibleAssets] = None
    Ships: Optional[_Ships] = None


class ScheduleDEP(BaseModel):
    """Schedule DEP: summary of depreciation under the Income-tax Act."""
    SummaryFromDeprSch: _Summary


class ScheduleDCG(BaseModel):
    """Schedule DCG: deemed capital gains summary for depreciable assets."""
    SummaryFromDeprSchCG: _SummaryCG


class ITR3DepreciationSchedules(BaseModel):
    """Canonical typed source for all four ITR-3 depreciation schedules."""
    schedule_dpm: Optional[ScheduleDPM] = None
    schedule_doa: Optional[ScheduleDOA] = None
    schedule_dep: Optional[ScheduleDEP] = None
    schedule_dcg: Optional[ScheduleDCG] = None


class ScheduleGSTTurnover(BaseModel):
    """GSTIN-wise gross receipts disclosed in Schedule GST."""
    GSTINNo: str
    AmtTurnGrossRcptGSTIN: Decimal


class ScheduleGST(BaseModel):
    """Schedule GST: gross receipts reported against each GSTIN."""
    TurnoverGrsRcptForGSTIN: List[ScheduleGSTTurnover]


class ICDSInfo(BaseModel):
    """One ICDS disclosure containing increase, decrease, and net effect."""
    IncreaseInProfit: Decimal
    DecreaseInProfit: Decimal
    NetEffect: Decimal


class ICDSTotalNetAmount(BaseModel):
    """Aggregate ICDS increase and decrease totals."""
    IncreaseInProfit: Decimal
    DecreaseInProfit: Decimal


class ScheduleICDS(BaseModel):
    """Schedule ICDS with all ten official standard-wise disclosures."""
    AccPolicyAmtDetl: ICDSInfo
    InventoriesValueDetl: ICDSInfo
    ConstContractsAmtDetl: ICDSInfo
    RevenueRcgAmtDetl: ICDSInfo
    TangibleFixedAssetDetl: ICDSInfo
    ForeignExgRatesDetl: ICDSInfo
    GovtGrantsDetl: ICDSInfo
    SecuritiesDetl: ICDSInfo
    BorrowingCostsDetl: ICDSInfo
    ProvAssetsDetl: ICDSInfo
    TotalNetAmtDetl: ICDSTotalNetAmount


class ESRDeductionDetail(BaseModel):
    """Scientific-research expenditure and allowable deduction amounts."""
    AmtDebPL: Decimal
    AmtUs35Allowable: Decimal
    ExcessAmtOverDebPL: Decimal


class ESRDeduction(BaseModel):
    """Nested scientific-research deduction disclosure."""
    DeductUs35: ESRDeductionDetail


class ESRDeductionUs35(BaseModel):
    """All section 35 categories required by Schedule ESR."""
    Section35_1_i: ESRDeduction
    Section35_1_ii: ESRDeduction
    Section35_1_iia: ESRDeduction
    Section35_1_iii: ESRDeduction
    Section35_1_iv: ESRDeduction
    Section35_2AA: ESRDeduction
    Section35_2AB: ESRDeduction
    Section35_CCC: ESRDeduction
    Section35_CCD: ESRDeduction
    TotUs35: ESRDeduction


class ScheduleESR(BaseModel):
    """Schedule ESR: expenditure on scientific research."""
    DeductionUs35: ESRDeductionUs35



class UDEntry(BaseModel):
    assessment_year: str = Field(default="2026-27")
    bf_unabsorbed_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    bf_unabsorbed_depreciation: Decimal = Field(default=Decimal("0"), ge=0)
    allowance_setoff_cy: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_setoff_cy: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# Top-level ITR-3 input model
class ITR3DeductionDonation(BaseModel):
    """Typed Section 80G/80GGA/80GGC disclosure row."""
    category: str = "50_APPROVAL_REQD"
    donee_name: str = ""
    donee_pan: str = ""
    address_line: str = ""
    city: str = ""
    state_code: str = ""
    pin_code: str = ""
    cash_amount: Decimal = Decimal("0")
    other_mode_amount: Decimal = Decimal("0")
    contribution_date: str = ""
    transaction_ref: str = ""
    ifsc_code: str = ""
    political_party_name: str = ""
    political_party_pan: str = ""


class ITR3DeductionLoan(BaseModel):
    """Typed Section 80E-series loan disclosure row."""
    section: str = "80E"
    loan_taken_from: str = "B"
    lender_name: str = ""
    loan_account_no: str = ""
    date_of_loan: str = ""
    total_loan_amount: Decimal = Decimal("0")
    outstanding_amount: Decimal = Decimal("0")
    interest_amount: Decimal = Decimal("0")
    vehicle_reg_no: str = ""


class ITR3DeductionDetails(BaseModel):
    """Typed Chapter VI-A detail sources used by the ITR-3 serializer."""
    investments_80c: List[ITR3DeductionDonation] = Field(default_factory=list)
    donations_80g: List[ITR3DeductionDonation] = Field(default_factory=list)
    donations_80gga: List[ITR3DeductionDonation] = Field(default_factory=list)
    contributions_80ggc: List[ITR3DeductionDonation] = Field(default_factory=list)
    loans: List[ITR3DeductionLoan] = Field(default_factory=list)
    stamp_duty_80eea: Decimal = Decimal("0")


class ITR3Schedule80DInsurance(BaseModel):
    """Official Schedule 80D insurer payment row."""
    InsurerName: str = ""
    PolicyNo: str = ""
    HealthInsAmt: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule80DHealth(BaseModel):
    """Official Schedule 80D health-payment category."""
    Sch80DInsDtls: List[ITR3Schedule80DInsurance] = Field(default_factory=list)
    TotalPayments: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule80DCategory(BaseModel):
    """Typed official Schedule 80D category and its statutory components."""
    insurance: ITR3Schedule80DHealth | None = None
    SeniorCitizenFlag: str | None = None
    SelfAndFamily: Decimal | None = Field(default=None, ge=0)
    HealthInsPremSlfFam: Decimal | None = Field(default=None, ge=0)
    Sec80DSelfFamHIDtls: ITR3Schedule80DHealth | None = None
    PrevHlthChckUpSlfFam: Decimal | None = Field(default=None, ge=0)
    SelfAndFamilySeniorCitizen: Decimal | None = Field(default=None, ge=0)
    HlthInsPremSlfFamSrCtzn: Decimal | None = Field(default=None, ge=0)
    Sec80DSelfFamSrCtznHIDtls: ITR3Schedule80DHealth | None = None
    PrevHlthChckUpSlfFamSrCtzn: Decimal | None = Field(default=None, ge=0)
    MedicalExpSlfFamSrCtzn: Decimal | None = Field(default=None, ge=0)
    ParentsSeniorCitizenFlag: str | None = None
    Parents: Decimal | None = Field(default=None, ge=0)
    HlthInsPremParents: Decimal | None = Field(default=None, ge=0)
    Sec80DParentsHIDtls: ITR3Schedule80DHealth | None = None
    PrevHlthChckUpParents: Decimal | None = Field(default=None, ge=0)
    ParentsSeniorCitizen: Decimal | None = Field(default=None, ge=0)
    HlthInsPremParentsSrCtzn: Decimal | None = Field(default=None, ge=0)
    Sec80DParentsSrCtznHIDtls: ITR3Schedule80DHealth | None = None
    PrevHlthChckUpParentsSrCtzn: Decimal | None = Field(default=None, ge=0)
    MedicalExpParentsSrCtzn: Decimal | None = Field(default=None, ge=0)
    EligibleAmountOfDedn: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule80D(BaseModel):
    """Typed CBDT Schedule 80D."""
    Sec80DSelfFamSrCtznHealth: ITR3Schedule80DCategory


class ITR3Schedule80DD(BaseModel):
    """Typed CBDT Schedule 80DD dependent disability claim."""
    NatureOfDisability: str
    TypeOfDisability: str
    DeductionAmount: Decimal = Field(ge=0)
    DependentType: str
    DependentPan: str | None = None
    DependentAadhaar: str | None = None
    Form10IAFilingDate: str | None = None
    Form10IAAckNum: str | None = None
    FormAckNum11A: str | None = None
    UDIDNum: str | None = None


class ITR3Schedule80U(BaseModel):
    """Typed CBDT Schedule 80U self disability claim."""
    NatureOfDisability: str
    TypeOfDisability: str
    DeductionAmount: Decimal = Field(ge=0)
    Form10IAFilingDate: str | None = None
    Form10IAAckNum: str | None = None
    FormAckNum11A: str | None = None
    UDIDNum: str | None = None
class ITR3Section80DeductionAmount(BaseModel):
    """One official section 80 deduction amount row."""
    DeductAmountSec80: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Section80Activity(BaseModel):
    """Official activity code and deduction rows for sections 80-IA/IB."""
    Sch80LocOrDescCode: str
    Sch80DeductAmtDtls: List[ITR3Section80DeductionAmount] = Field(default_factory=list)


class ITR3Schedule80IA(BaseModel):
    """Typed CBDT Schedule 80-IA."""
    Sch80SectionCode: str = "80-IA"
    DeductUs80_IA_4_iv: ITR3Section80Activity
    TotSchedule80_IA: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule80IB(BaseModel):
    """Typed CBDT Schedule 80-IB."""
    Sch80SectionCode: str = "80-IB"
    DeductMinOilUs80_IB_9_Und: ITR3Section80Activity
    DeductHousUs80_IB_10_Und: ITR3Section80Activity
    DeductFruitVegUs80_IB_11A_Und: ITR3Section80Activity
    DeductFoodGrainUs80_IB_11A_Und: ITR3Section80Activity
    TotSchedule80_IB: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule80ICNorthEast(BaseModel):
    """Typed state-wise section 80-IC deduction details."""
    Assam_Und: ITR3Section80Activity
    ArunachalPradesh_Und: ITR3Section80Activity
    Manipur_Und: ITR3Section80Activity
    Mizoram_Und: ITR3Section80Activity
    Meghalaya_Und: ITR3Section80Activity
    Nagaland_Und: ITR3Section80Activity
    Tripura_Und: ITR3Section80Activity
    Sikkim_Und: ITR3Section80Activity
    TotDeductInNorthEast: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule80IC(BaseModel):
    """Typed CBDT Schedule 80-IC."""
    Sch80SectionCode: str = "80-IC_IE"
    DeductInNorthEast: ITR3Schedule80ICNorthEast
    TotSchedule80_IC: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule80RAAddress(BaseModel):
    """Official Schedule 80RA donee address."""
    AddrDetail: str
    CityOrTownOrDistrict: str
    StateCode: str
    PinCode: int


class ITR3Schedule80RADonation(BaseModel):
    """Typed research-association donation row in Schedule 80RA."""
    NameOfDonee: str
    AddressDetail: ITR3Schedule80RAAddress
    DoneePAN: str
    DonationAmtCash: Decimal = Field(default=Decimal("0"), ge=0)
    DonationAmtOtherMode: Decimal = Field(default=Decimal("0"), ge=0)
    DonationAmt: Decimal = Field(default=Decimal("0"), ge=0)
    EligibleDonationAmt: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule80RA(BaseModel):
    """Typed CBDT Schedule 80RA."""
    DonationDtlsRsrchAssctn: List[ITR3Schedule80RADonation] = Field(default_factory=list)
    TotalDonationAmtCash80RA: Decimal = Field(default=Decimal("0"), ge=0)
    TotalDonationAmtOtherMode80RA: Decimal = Field(default=Decimal("0"), ge=0)
    TotalDonationsUs80RA: Decimal = Field(default=Decimal("0"), ge=0)
    TotalEligibleDonationAmt80RA: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule10AAUnit(BaseModel):
    """Typed Schedule 10AA undertaking assessment-year row."""
    AssmtYrUnit: str
    DedUs10Sub: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule10AAUndertaking(BaseModel):
    """Schedule 10AA undertaking collection."""
    DedFromUndertakingWithAy: List[ITR3Schedule10AAUnit] = Field(default_factory=list)


class ITR3Schedule10AADetail(BaseModel):
    """Schedule 10AA deduction details."""
    Undertaking: ITR3Schedule10AAUndertaking
    TotalDedUs10Sub: Decimal = Field(default=Decimal("0"), ge=0)


class ITR3Schedule10AAContainer(BaseModel):
    """Schedule 10AA SEZ container."""
    DedUs10Detail: ITR3Schedule10AADetail


class ITR3Schedule10AA(BaseModel):
    """Typed CBDT Schedule 10AA."""
    DeductSEZ: ITR3Schedule10AAContainer


class ITR3ScheduleSEmployer(BaseModel):
    """Complete source row for one official ITR-3 Schedule S employer."""

    employer_name: str = Field(min_length=1, max_length=125)
    nature_of_employment: str = "OTH"
    employer_tan: str | None = None
    address_detail: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state_code: str = Field(min_length=1)
    pin_code: str | None = None
    zip_code: str | None = None
    basic: Decimal = Decimal("0")
    da: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    hra: Decimal = Decimal("0")
    bonus: Decimal = Decimal("0")
    allowances: Decimal = Decimal("0")
    lta: Decimal = Decimal("0")
    other_allowance: Decimal = Decimal("0")
    arrear_salary: Decimal = Decimal("0")
    perquisites: Decimal = Decimal("0")
    profits_in_lieu: Decimal = Decimal("0")
    income_notified_89a: Decimal = Decimal("0")
    income_notified_other_89a: Decimal = Decimal("0")
    income_notified_prior_year_89a: Decimal = Decimal("0")
    salary_nature_rows: list[dict[str, Any]] = Field(default_factory=list)
    perquisite_nature_rows: list[dict[str, Any]] = Field(default_factory=list)
    profit_in_lieu_nature_rows: list[dict[str, Any]] = Field(default_factory=list)
    notified_89a_country_rows: list[dict[str, Any]] = Field(default_factory=list)


class ITR3ScheduleHPProperty(BaseModel):
    """Complete source row for one official ITR-3 Schedule HP property."""

    sequence_no: int = Field(ge=1)
    address_detail: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state_code: str = Field(min_length=1)
    country_code: str = "91"
    pin_code: str | None = None
    zip_code: str | None = None
    property_owner: str = "SE"
    property_owner_other: str | None = None
    co_owned: bool = False
    assessee_share_percent: Decimal = Decimal("100")
    property_type: str = "S"
    annual_lettable_value: Decimal = Decimal("0")
    rent_not_realized: Decimal = Decimal("0")
    local_taxes: Decimal = Decimal("0")
    annual_value_owned: Decimal = Decimal("0")
    standard_deduction: Decimal = Decimal("0")
    interest_on_loan: Decimal = Decimal("0")
    income_of_hp: Decimal = Decimal("0")
    # Form item 1j -- arrears/unrealised rent received during the year, RAW
    # amount (the 30% Section 25A reduction is applied by the calculator,
    # not pre-applied here).
    arrears_unrealised_rent: Decimal = Decimal("0")
    home_loan_details: list[dict[str, Any]] = Field(default_factory=list)
    co_owner_details: list[dict[str, Any]] = Field(default_factory=list)
    tenant_details: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------

class ITR3Input(BaseModel):
    """
    Top-level input model for computing an ITR-3 return.

    Required schedules per ITD JSON spec:
      CreationInfo, Form_ITR3, ITR3ScheduleBP, PARTA_BS, PARTA_PL,
      PartA_GEN1, PartA_GEN2, ScheduleCYLA, ScheduleBFLA, PartB-TI, PartB-TTI,
      Verification
    """

    # --- Assessee meta ---
    age_bracket: AgeBracket = Field(...)
    tax_regime: TaxRegime = Field(...)
    residential_status: ResidentialStatus = Field(default=ResidentialStatus.RES)
    filing_section: ReturnFileSection = Field(default=ReturnFileSection.S11)

    # Canonical filing identity/profile used by the ITD builder. These remain
    # optional for legacy calculator callers, but canonical generation never
    # fabricates them.
    assessee_pan: Optional[str] = Field(default=None)
    assessee_first_name: str = Field(default="")
    assessee_middle_name: str = Field(default="")
    assessee_last_name: str = Field(default="")
    assessee_dob: Optional[str] = Field(default=None)
    assessee_father_name: str = Field(default="")
    # PDF item A14 -- ITR-3 permits only Individual/HUF (schema `Status`
    # enum is `["I","H"]`, no Firm).
    assessee_status: Literal["I", "H"] = Field(default="I")
    verification_place: Optional[str] = Field(default=None)
    verification_date: Optional[str] = Field(default=None)
    residence_no: Optional[str] = Field(default=None)
    residence_name: Optional[str] = Field(default=None)
    road_or_street: Optional[str] = Field(default=None)
    locality: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    state_code: Optional[str] = Field(default=None)
    country_code: Optional[str] = Field(default=None)
    pin_code: Optional[str] = Field(default=None)
    zip_code: Optional[str] = Field(default=None)
    mobile_country_code: str = Field(default="91")
    mobile_no: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    assessee_aadhaar: Optional[str] = Field(default=None)
    # PDF item A17 -- office/residence phone with STD code (schema
    # `Address.Phone`), distinct from the primary mobile number above.
    office_phone_std_code: Optional[str] = Field(default=None)
    office_phone_no: Optional[str] = Field(default=None)
    # PDF items A17/A18's own secondary mobile/email columns.
    secondary_mobile_country_code: Optional[str] = Field(default=None)
    secondary_mobile_no: Optional[str] = Field(default=None)
    secondary_email: Optional[str] = Field(default=None)
    # PDF item A5b-A13b "Secondary Address" -- `SecondaryAdd`/`AlternateAddress`
    # in the schema. `secondary_address_different` is the Y/N flag itself;
    # the alternate_* fields are only meaningful (and only emitted) when it
    # is True -- mirrors `app.engine.personal_profile.NormalizedAlternateAddress`.
    secondary_address_different: bool = Field(default=False)
    alternate_residence_no: Optional[str] = Field(default=None)
    alternate_residence_name: Optional[str] = Field(default=None)
    alternate_road_or_street: Optional[str] = Field(default=None)
    alternate_locality: Optional[str] = Field(default=None)
    alternate_city: Optional[str] = Field(default=None)
    alternate_state_code: Optional[str] = Field(default=None)
    alternate_country_code: Optional[str] = Field(default=None)
    alternate_pin_code: Optional[str] = Field(default=None)
    alternate_zip_code: Optional[str] = Field(default=None)
    bank_accounts: List[dict[str, Any]] = Field(default_factory=list)

    # --- Explicit employer/property disclosure sources ---
    schedule_s_employers: Optional[List[ITR3ScheduleSEmployer]] = None
    schedule_hp_properties: Optional[List[ITR3ScheduleHPProperty]] = None

    # --- Business Income (core PGBP) ---
    business_income: Optional[BusinessIncome] = Field(default=None)

    # --- Business accounts ---
    business_accounts: Optional[ITR3BusinessAccounts] = Field(default=None)
    parta_oi: Optional[ITR3PartAOI] = Field(default=None)
    parta_qd: Optional[ITR3PartAQD] = Field(default=None)

    # --- Profit and Loss ---
    profit_and_loss: Optional[ProfitAndLoss] = Field(default=None)

    # --- Depreciation schedules ---
    depreciation_schedules: Optional[ITR3DepreciationSchedules] = Field(default=None)

    # --- Heads of Income ---
    salary_income: Optional[SalaryIncome] = Field(default=None)
    house_property_income: Optional[HousePropertyIncome] = Field(default=None)
    other_sources_income: Optional[OtherSourcesIncome] = Field(default=None)

    # --- Capital Gains (full CG) ---
    cg_transactions: Optional[List[CGTransaction]] = Field(default=None)
    cg_112a_scrips: Optional[List[CG112AScrip]] = Field(default=None)
    cg_115ad_scrips: Optional[List[CG112AScrip]] = Field(default=None)
    vda_transactions: Optional[List[VDATransaction]] = Field(default=None)
    # Schedule CG's "CapitalLossBuyBackShares" block (Section 46A capital
    # loss on buyback of shares) -- same shared, form-agnostic mapper as
    # ITR-2 (see `app/engine/draft_to_itr2_input.py::_map_buyback_losses`'s
    # own docstring for the full schema-shape reasoning).
    cg_buyback_loss_stcg20: Decimal = Field(default=Decimal("0"), le=0)
    cg_buyback_loss_stcg30: Decimal = Field(default=Decimal("0"), le=0)
    cg_buyback_loss_stcg_applicable: Decimal = Field(default=Decimal("0"), le=0)
    cg_buyback_loss_ltcg: Decimal = Field(default=Decimal("0"), le=0)

    # --- Loss Set-Off ---
    bf_losses: Optional[List[BFLossItem]] = Field(default=None)

    # --- Partner in Firm ---
    partner_firm_details: Optional[List[PartnerInFirm]] = Field(default=None)

    # --- ICDS, scientific research, and GST schedules ---
    schedule_icds: Optional[ScheduleICDS] = Field(default=None)
    schedule_esr: Optional[ScheduleESR] = Field(default=None)
    schedule_tpsa: Optional[ITR3ScheduleTPSA] = Field(default=None)
    schedule_gst: Optional[ScheduleGST] = Field(default=None)
    schedule_80ia: Optional[ITR3Schedule80IA] = Field(default=None)
    schedule_80ib: Optional[ITR3Schedule80IB] = Field(default=None)
    schedule_80d: Optional[ITR3Schedule80D] = Field(default=None)
    schedule_80dd: Optional[ITR3Schedule80DD] = Field(default=None)
    schedule_80u: Optional[ITR3Schedule80U] = Field(default=None)
    schedule_80ic: Optional[ITR3Schedule80IC] = Field(default=None)
    schedule_80ra: Optional[ITR3Schedule80RA] = Field(default=None)
    schedule_10aa: Optional[ITR3Schedule10AA] = Field(default=None)

    # --- Unabsorbed Depreciation ---
    ud_entries: Optional[List[UDEntry]] = Field(default=None)

    # --- Special Rate Income ---
    si_entries: Optional[List[ScheduleSIEntry]] = Field(default=None)

    # --- Agricultural / Exempt ---
    agricultural_income: Optional[AgriculturalIncome] = Field(default=None)
    exempt_income: Optional[ExemptIncome] = Field(default=None)

    # --- Foreign ---
    fsi_entries: Optional[List[FSICountryEntry]] = Field(default=None)
    tr1_entries: Optional[List[TR1Entry]] = Field(default=None)
    foreign_assets: List[ForeignAssetEntry] = Field(default_factory=list)
    foreign_tax_relief_refunded: bool = False
    foreign_tax_relief_refunded_amount: Decimal = Field(default=Decimal("0"), ge=0)
    asset_liability: Optional[AssetLiabilityInput] = Field(default=None)
    schedule_5a: Optional[Schedule5AInput] = Field(default=None)
    esop_deferrals: List[ESOPDeferralInput] = Field(default_factory=list)
    tax_payment_entries: List[TaxPaymentDetail] = Field(default_factory=list)
    tds3_entries: Optional[List[TDS3Entry]] = Field(default=None)
    tds3_filing_details: List[TDS3FilingDetail] = Field(default_factory=list)

    # --- Clubbing ---
    spi_entries: Optional[List[SPIEntry]] = Field(default=None)
    pti_entries: Optional[List[PTIEntry]] = Field(default=None)

    # --- AMT ---
    amt_input: Optional[AMTInput] = Field(default=None)

    # --- Filing Status (A19) ---
    # Form10IEA cascade (A19(b)(I)) -- see app/engine/itd/itr3.py's own
    # comment on the mutually-exclusive A23 branch (ported from ITR-4's
    # live-UAT-verified fix) for why these two sub-branches must never both
    # be emitted at once.
    form_10iea_earlier_ay_old_regime: Literal["Y", "N"] = Field(default="N")
    form_10iea_ass_year: Optional[str] = Field(default=None)
    form_10iea_earlier_ay_ack_old_regime: Optional[str] = Field(default=None)
    f10iea_earlier_ay_new_regime: Literal["Y", "N"] = Field(default="N")
    ass_yr_f10iea_new_tax_reg: Optional[str] = Field(default=None)
    form_10iea_earlier_ay_ack_new_regime: Optional[str] = Field(default=None)
    f10iea_curr_ay_new_regime: Literal["Y", "N"] = Field(default="N")
    f10iea_date_curr_ay_new_tax: Optional[str] = Field(default=None)
    f10iea_ack_no_curr_ay_new_tax: Optional[str] = Field(default=None)
    f10iea_curr_ay_old_regime: Literal["Y", "N"] = Field(default="N")
    f10iea_date_curr_ay_old_tax: Optional[str] = Field(default=None)
    f10iea_ack_no_curr_ay_old_tax: Optional[str] = Field(default=None)
    # A19(c) seventh proviso to section 139(1).
    seventh_proviso_139: bool = Field(default=False)
    deposit_exceeds_one_crore: bool = Field(default=False)
    current_account_deposits: Decimal = Field(default=Decimal("0"), ge=0)
    foreign_travel_flag: bool = Field(default=False)
    foreign_travel_expenditure: Decimal = Field(default=Decimal("0"), ge=0)
    electricity_expenditure_flag: bool = Field(default=False)
    electricity_expenditure: Decimal = Field(default=Decimal("0"), ge=0)
    other_clause_iv_flag: bool = Field(default=False)
    seventh_proviso_clause_iv_entries: List[tuple[str, Decimal]] = Field(default_factory=list)
    # A19(d)/(e) revised/defective/notice metadata.
    receipt_number: Optional[str] = Field(default=None)
    original_return_date: Optional[str] = Field(default=None)
    notice_number: Optional[str] = Field(default=None)
    notice_date: Optional[str] = Field(default=None)
    # A19(f) residential-status conditions/jurisdictions/stay-days (NRI/RNOR).
    conditions_res_status: Optional[str] = Field(default=None)
    jurisdiction_residence_entries: List[tuple[str, str]] = Field(default_factory=list)
    total_stay_india_prev_yr: Optional[int] = Field(default=None, ge=0, le=365)
    total_stay_india_4_prec_yr: Optional[int] = Field(default=None, ge=0, le=1461)
    # A19(g)/(h) 115H benefit, Portuguese Civil Code.
    benefit_us_115h: Optional[bool] = Field(default=None)
    portuguese_civil_code_applies: bool = Field(default=False)
    # A19(i) representative assessee.
    assessee_representative_name: Optional[str] = Field(default=None)
    assessee_representative_email: Optional[str] = Field(default=None)
    assessee_representative_mobile_country_code: Optional[str] = Field(default=None)
    assessee_representative_mobile_no: Optional[str] = Field(default=None)
    # A19(j) company directorships, A19(k) partner-in-firm, A19(l) unlisted equity.
    is_company_director: bool = Field(default=False)
    company_director_entries: List[dict[str, Any]] = Field(default_factory=list)
    is_partner_in_firm: bool = Field(default=False)
    partner_in_firm_entries: List[dict[str, Any]] = Field(default_factory=list)
    held_unlisted_equity: bool = Field(default=False)
    unlisted_equity_entries: List[dict[str, Any]] = Field(default_factory=list)
    # A19(m)/(n) NRI permanent establishment / significant economic presence.
    nri_pe_in_india: Optional[str] = Field(default=None)
    nri_sep_in_india: Optional[str] = Field(default=None)
    sep_aggregate_payment: Decimal = Field(default=Decimal("0"), ge=0)
    sep_number_of_users: int = Field(default=0, ge=0)
    # A19(o)/(p)/(q) IFSC unit, FII/FPI, LEI.
    ifsc_unit_foreign_exchange_flag: Optional[str] = Field(default=None)
    is_fii_fpi: bool = Field(default=False)
    sebi_registration_number: Optional[str] = Field(default=None)
    lei_number: Optional[str] = Field(default=None)
    lei_valid_upto_date: Optional[str] = Field(default=None)

    # --- Audit Info ---
    audit_info: Optional[AuditInfo] = Field(default=None)

    # --- Nature of Business ---
    nature_of_business: Optional[List[NatureOfBusiness]] = Field(default=None)

    # --- Balance Sheet ---
    balance_sheet: Optional[BalanceSheet] = Field(default=None)

    # --- Deductions ---
    deductions_chapter6a: Optional[Chapter6ADeductions] = Field(default=None)
    deduction_details: Optional[ITR3DeductionDetails] = Field(default=None)

    # --- TDS/TCS ---
    tds1_entries: Optional[List[TDS1Entry]] = Field(default=None)
    tds2_entries: Optional[List[TDS2Entry]] = Field(default=None)
    tcs_entries: Optional[List[TCSEntry]] = Field(default=None)

    # --- Tax payments ---
    advance_tax_paid: Decimal = Field(default=Decimal("0"), ge=0)
    advance_tax_q1: Optional[Decimal] = Field(default=None, ge=0, description="Advance tax paid by 15 June (Q1)")
    advance_tax_q2: Optional[Decimal] = Field(default=None, ge=0, description="Advance tax paid by 15 Sep (Q2)")
    advance_tax_q3: Optional[Decimal] = Field(default=None, ge=0, description="Advance tax paid by 15 Dec (Q3)")
    advance_tax_q4: Optional[Decimal] = Field(default=None, ge=0, description="Advance tax paid by 15 Mar (Q4)")
    self_assessment_tax_paid: Decimal = Field(default=Decimal("0"), ge=0)

    # --- Filing dates ---
    filing_date: Optional[date] = Field(default=None)
    due_date: Optional[date] = Field(default=None)
    relief_89: Decimal = Field(default=Decimal("0"), ge=0, description="Relief under section 89 (arrears of salary) as computed by Form 10E")
