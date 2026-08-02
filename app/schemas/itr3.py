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
from typing import List, Optional
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.itr1 import (
    AgeBracket, TaxRegime,
    SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions, CapitalGainsIncome,
    TDS1Entry, TDS2Entry, TCSEntry,
)
from app.schemas.itr2 import (
    CGTransaction, CG112AScrip, VDATransaction,
    BFLossItem, ScheduleSIEntry, AgriculturalIncome, ExemptIncome,
    FSICountryEntry, TR1Entry, SPIEntry, AMTInput,
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


class BalanceSheet(BaseModel):
    """Balance sheet summary for ITR-3."""
    proprietors_fund: Decimal = Field(default=Decimal("0"), ge=0)
    secured_loans: Decimal = Field(default=Decimal("0"), ge=0)
    unsecured_loans: Decimal = Field(default=Decimal("0"), ge=0)
    current_liabilities: Decimal = Field(default=Decimal("0"), ge=0)
    total_liabilities: Decimal = Field(default=Decimal("0"), ge=0)

    fixed_assets: Decimal = Field(default=Decimal("0"), ge=0)
    current_assets: Decimal = Field(default=Decimal("0"), ge=0)
    total_assets: Decimal = Field(default=Decimal("0"), ge=0)


class NatureOfBusiness(BaseModel):
    """Nature of business codes for ITR-3 PartA_GEN2."""
    code: int = Field(default=1, ge=1, le=99)
    description: Optional[str] = Field(default=None, max_length=125)


class AuditInfo(BaseModel):
    """Audit information for PartA_GEN2."""
    liable_sec_44ab: bool = Field(default=False)
    liable_sec_44aa: bool = Field(default=False)
    liable_sec_92e: bool = Field(default=False)
    account_audited: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Partner in Firm details (Schedule IF)
# ---------------------------------------------------------------------------

class PartnerInFirm(BaseModel):
    firm_name: str = Field(default="", max_length=125)
    firm_pan: str = Field(default="AAAAA0000A", pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    profit_share_amount: Decimal = Field(default=Decimal("0"), ge=0)
    interest_amount: Decimal = Field(default=Decimal("0"), ge=0)
    remuneration_amount: Decimal = Field(default=Decimal("0"), ge=0)
    capital_balance: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# Unabsorbed Depreciation (Schedule UD)
# ---------------------------------------------------------------------------

class UDEntry(BaseModel):
    assessment_year: str = Field(default="2026-27")
    bf_unabsorbed_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    bf_unabsorbed_depreciation: Decimal = Field(default=Decimal("0"), ge=0)
    allowance_setoff_cy: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_setoff_cy: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# Top-level ITR-3 input model
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

    # --- Business Income (core PGBP) ---
    business_income: Optional[BusinessIncome] = Field(default=None)

    # --- Heads of Income ---
    salary_income: Optional[SalaryIncome] = Field(default=None)
    house_property_income: Optional[HousePropertyIncome] = Field(default=None)
    other_sources_income: Optional[OtherSourcesIncome] = Field(default=None)

    # --- Capital Gains (full CG) ---
    cg_transactions: Optional[List[CGTransaction]] = Field(default=None)
    cg_112a_scrips: Optional[List[CG112AScrip]] = Field(default=None)
    vda_transactions: Optional[List[VDATransaction]] = Field(default=None)

    # --- Loss Set-Off ---
    bf_losses: Optional[List[BFLossItem]] = Field(default=None)

    # --- Partner in Firm ---
    partner_firm_details: Optional[List[PartnerInFirm]] = Field(default=None)

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

    # --- Clubbing ---
    spi_entries: Optional[List[SPIEntry]] = Field(default=None)

    # --- AMT ---
    amt_input: Optional[AMTInput] = Field(default=None)

    # --- Audit Info ---
    audit_info: Optional[AuditInfo] = Field(default=None)

    # --- Nature of Business ---
    nature_of_business: Optional[List[NatureOfBusiness]] = Field(default=None)

    # --- Balance Sheet ---
    balance_sheet: Optional[BalanceSheet] = Field(default=None)

    # --- Deductions ---
    deductions_chapter6a: Optional[Chapter6ADeductions] = Field(default=None)

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
