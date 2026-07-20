"""
ITR-3 input schemas.

ITR-3 is for Individuals and HUFs having income from business or profession.

Eligibility:
  - Resident / Non-Resident / Not Ordinarily Resident
  - Having income under the head "Profits and Gains of Business or Profession"
  - Can also have salary, house property, capital gains, other sources

Key schedules unique to ITR-3:
  - PARTA_BS (Balance Sheet)
  - PARTA_PL (Profit & Loss Account)
  - PARTA_OI (Other Information)
  - PARTA_QD (Quantitative Details - if 44AB audit)
  - Manufacturing Account / Trading Account
  - ITR3ScheduleBP (Business Income Computation)
  - ScheduleDPM (Depreciation on Plant & Machinery)
  - ScheduleDOA (Depreciation on Other Assets)
  - ScheduleDEP (Depreciation Summary)
  - ScheduleDCG (Deemed Capital Gains u/s 50 on depreciable assets)
  - ScheduleESR (Scientific Research Expenditure u/s 35)
  - ScheduleIF (Income from Firm/LLP/AOP)
  - ScheduleICDS (ICDS adjustments)
  - ScheduleUD (Unabsorbed Depreciation)
  - ScheduleGST (GSTIN-wise turnover)
  - Schedule10AA (SEZ deduction)
  - Schedule80-IA, 80-IB, 80-IC, 80RA (Business-specific deductions)
"""

from decimal import Decimal
from enum import Enum
from typing import List, Optional
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.itr1 import (
    AgeBracket, TaxRegime, SalaryIncome, HousePropertyIncome,
    OtherSourcesIncome, Chapter6ADeductions,
    TDS1Entry, TDS2Entry, TCSEntry,
)
from app.schemas.itr2 import (
    CGTransaction, CG112AScrip, VDATransaction, BFLossItem,
    CFLLossItem, ScheduleSIEntry, AgriculturalIncome, ExemptIncome,
    FSICountryEntry, TR1Entry, SPIEntry,
    ResidentialStatus, ReturnFileSection,
)


# ---------------------------------------------------------------------------
# Accounting Method
# ---------------------------------------------------------------------------

class MethodOfAccounting(str, Enum):
    MERCANTILE = "MERC"
    CASH = "CASH"


# ---------------------------------------------------------------------------
# Balance Sheet (PARTA_BS)
# ---------------------------------------------------------------------------

class BalanceSheet(BaseModel):
    capital: Decimal = Field(default=Decimal("0"), ge=0)
    reserves_and_surplus: Decimal = Field(default=Decimal("0"), ge=0)
    secured_loans: Decimal = Field(default=Decimal("0"), ge=0)
    unsecured_loans: Decimal = Field(default=Decimal("0"), ge=0)
    current_liabilities: Decimal = Field(default=Decimal("0"), ge=0)
    other_liabilities: Decimal = Field(default=Decimal("0"), ge=0)
    total_liabilities: Decimal = Field(default=Decimal("0"), ge=0)

    fixed_assets_gross: Decimal = Field(default=Decimal("0"), ge=0)
    accumulated_depreciation: Decimal = Field(default=Decimal("0"), ge=0)
    fixed_assets_net: Decimal = Field(default=Decimal("0"), ge=0)
    investments: Decimal = Field(default=Decimal("0"), ge=0)
    loans_and_advances: Decimal = Field(default=Decimal("0"), ge=0)
    sundry_debtors: Decimal = Field(default=Decimal("0"), ge=0)
    cash_and_bank: Decimal = Field(default=Decimal("0"), ge=0)
    inventories: Decimal = Field(default=Decimal("0"), ge=0)
    other_assets: Decimal = Field(default=Decimal("0"), ge=0)
    total_assets: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# Profit & Loss (PARTA_PL)
# ---------------------------------------------------------------------------

class PLDebits(BaseModel):
    opening_stock: Decimal = Field(default=Decimal("0"), ge=0)
    purchases: Decimal = Field(default=Decimal("0"), ge=0)
    direct_expenses: Decimal = Field(default=Decimal("0"), ge=0)
    employee_benefit_expense: Decimal = Field(default=Decimal("0"), ge=0)
    finance_cost: Decimal = Field(default=Decimal("0"), ge=0)  # Interest
    depreciation_as_per_books: Decimal = Field(default=Decimal("0"), ge=0)
    administrative_expenses: Decimal = Field(default=Decimal("0"), ge=0)
    selling_expenses: Decimal = Field(default=Decimal("0"), ge=0)
    rent_rates_taxes: Decimal = Field(default=Decimal("0"), ge=0)
    repairs_and_maintenance: Decimal = Field(default=Decimal("0"), ge=0)
    legal_and_professional: Decimal = Field(default=Decimal("0"), ge=0)
    travel: Decimal = Field(default=Decimal("0"), ge=0)
    power_and_fuel: Decimal = Field(default=Decimal("0"), ge=0)
    communication: Decimal = Field(default=Decimal("0"), ge=0)
    other_expenses: Decimal = Field(default=Decimal("0"), ge=0)
    closing_stock: Decimal = Field(default=Decimal("0"), ge=0)


class PLCredits(BaseModel):
    sales_turnover: Decimal = Field(default=Decimal("0"), ge=0)
    other_business_income: Decimal = Field(default=Decimal("0"), ge=0)
    interest_income: Decimal = Field(default=Decimal("0"), ge=0)
    rent_income: Decimal = Field(default=Decimal("0"), ge=0)
    commission_income: Decimal = Field(default=Decimal("0"), ge=0)
    dividend_income: Decimal = Field(default=Decimal("0"), ge=0)
    capital_gains_business: Decimal = Field(default=Decimal("0"), ge=0)
    other_credits: Decimal = Field(default=Decimal("0"), ge=0)


class PLDisallowances(BaseModel):
    """Disallowances under the Income Tax Act from P&L."""
    us36_expenditure_on_family: Decimal = Field(default=Decimal("0"), ge=0)
    us36_interest_on_capital: Decimal = Field(default=Decimal("0"), ge=0)
    us36_salary_to_partners: Decimal = Field(default=Decimal("0"), ge=0)
    us36_bonus_commission_to_partners: Decimal = Field(default=Decimal("0"), ge=0)
    us36_employer_pf_esic_unpaid: Decimal = Field(default=Decimal("0"), ge=0)
    us40a_excessive_payments_to_related: Decimal = Field(default=Decimal("0"), ge=0)
    us40a2b_cash_payments: Decimal = Field(default=Decimal("0"), ge=0)
    us40ai_non_tds_payments: Decimal = Field(default=Decimal("0"), ge=0)
    us43b_taxes_duties_contributions_unpaid: Decimal = Field(default=Decimal("0"), ge=0)
    us43b_employer_contributions_unpaid: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_disallowance_us38_2: Decimal = Field(default=Decimal("0"), ge=0)
    personal_expenses: Decimal = Field(default=Decimal("0"), ge=0)
    other_disallowances: Decimal = Field(default=Decimal("0"), ge=0)


class PLAdjustment(BaseModel):
    """Net profit/loss as per P&L account."""
    net_profit_as_per_pl: Decimal = Field(default=Decimal("0"))
    method_of_accounting: MethodOfAccounting = Field(default=MethodOfAccounting.MERCANTILE)
    is_audited_under_44ab: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Depreciation (DPM / DOA / DEP)
# ---------------------------------------------------------------------------

class DepreciationBlock15(BaseModel):
    """15% block: Motors, Buses, Lorries, Tractors (non-commercial)."""
    wdv_opening: Decimal = Field(default=Decimal("0"), ge=0)
    additions: Decimal = Field(default=Decimal("0"), ge=0)
    additions_half_rate: Decimal = Field(default=Decimal("0"), ge=0)
    realizations: Decimal = Field(default=Decimal("0"), ge=0)
    wdv_closing: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_full: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_half: Decimal = Field(default=Decimal("0"), ge=0)
    total_depreciation: Decimal = Field(default=Decimal("0"), ge=0)


class DepreciationBlock30(BaseModel):
    """30% block: Commercial Vehicles, Computers."""
    wdv_opening: Decimal = Field(default=Decimal("0"), ge=0)
    additions: Decimal = Field(default=Decimal("0"), ge=0)
    additions_half_rate: Decimal = Field(default=Decimal("0"), ge=0)
    realizations: Decimal = Field(default=Decimal("0"), ge=0)
    wdv_closing: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_full: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_half: Decimal = Field(default=Decimal("0"), ge=0)
    total_depreciation: Decimal = Field(default=Decimal("0"), ge=0)


class DepreciationBlock40(BaseModel):
    """40% block: Intangible assets, Pollution control equipment."""
    wdv_opening: Decimal = Field(default=Decimal("0"), ge=0)
    additions: Decimal = Field(default=Decimal("0"), ge=0)
    additions_half_rate: Decimal = Field(default=Decimal("0"), ge=0)
    realizations: Decimal = Field(default=Decimal("0"), ge=0)
    wdv_closing: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_full: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_half: Decimal = Field(default=Decimal("0"), ge=0)
    total_depreciation: Decimal = Field(default=Decimal("0"), ge=0)


class DepreciationBlock45(BaseModel):
    """45% block: Energy saving devices, Solar plants."""
    wdv_opening: Decimal = Field(default=Decimal("0"), ge=0)
    additions: Decimal = Field(default=Decimal("0"), ge=0)
    additions_half_rate: Decimal = Field(default=Decimal("0"), ge=0)
    realizations: Decimal = Field(default=Decimal("0"), ge=0)
    wdv_closing: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_full: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_half: Decimal = Field(default=Decimal("0"), ge=0)
    total_depreciation: Decimal = Field(default=Decimal("0"), ge=0)


class DOABuildingResidential(BaseModel):
    """DOA - Building (Residential) 5%."""
    wdv_opening: Decimal = Field(default=Decimal("0"), ge=0)
    additions: Decimal = Field(default=Decimal("0"), ge=0)
    additions_half_rate: Decimal = Field(default=Decimal("0"), ge=0)
    realizations: Decimal = Field(default=Decimal("0"), ge=0)
    wdv_closing: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_full: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_half: Decimal = Field(default=Decimal("0"), ge=0)
    total_depreciation: Decimal = Field(default=Decimal("0"), ge=0)


class DOABuildingOther(BaseModel):
    """DOA - Building (Non-residential/Factory) 10%."""
    wdv_opening: Decimal = Field(default=Decimal("0"), ge=0)
    additions: Decimal = Field(default=Decimal("0"), ge=0)
    additions_half_rate: Decimal = Field(default=Decimal("0"), ge=0)
    realizations: Decimal = Field(default=Decimal("0"), ge=0)
    wdv_closing: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_full: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_half: Decimal = Field(default=Decimal("0"), ge=0)
    total_depreciation: Decimal = Field(default=Decimal("0"), ge=0)


class DOAFurniture(BaseModel):
    """DOA - Furniture & Fittings 10%."""
    wdv_opening: Decimal = Field(default=Decimal("0"), ge=0)
    additions: Decimal = Field(default=Decimal("0"), ge=0)
    additions_half_rate: Decimal = Field(default=Decimal("0"), ge=0)
    realizations: Decimal = Field(default=Decimal("0"), ge=0)
    wdv_closing: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_full: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_half: Decimal = Field(default=Decimal("0"), ge=0)
    total_depreciation: Decimal = Field(default=Decimal("0"), ge=0)


class DOAIntangible(BaseModel):
    """DOA - Intangible Assets (Know-how, Patents, Copyrights) 25%."""
    wdv_opening: Decimal = Field(default=Decimal("0"), ge=0)
    additions: Decimal = Field(default=Decimal("0"), ge=0)
    additions_half_rate: Decimal = Field(default=Decimal("0"), ge=0)
    realizations: Decimal = Field(default=Decimal("0"), ge=0)
    wdv_closing: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_full: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation_half: Decimal = Field(default=Decimal("0"), ge=0)
    total_depreciation: Decimal = Field(default=Decimal("0"), ge=0)


class DepreciationSchedule(BaseModel):
    """Aggregated depreciation schedule input."""
    block_15: Optional[DepreciationBlock15] = Field(default=None)
    block_30: Optional[DepreciationBlock30] = Field(default=None)
    block_40: Optional[DepreciationBlock40] = Field(default=None)
    block_45: Optional[DepreciationBlock45] = Field(default=None)
    building_residential_5: Optional[DOABuildingResidential] = Field(default=None)
    building_other_10: Optional[DOABuildingOther] = Field(default=None)
    furniture_10: Optional[DOAFurniture] = Field(default=None)
    intangible_25: Optional[DOAIntangible] = Field(default=None)


# ---------------------------------------------------------------------------
# ICDS Adjustments
# ---------------------------------------------------------------------------

class ICDSAdjustment(BaseModel):
    """Net effect of ICDS adjustments on business income."""
    net_icds_effect: Decimal = Field(default=Decimal("0"))


# ---------------------------------------------------------------------------
# Firm/LLP/AOP Income
# ---------------------------------------------------------------------------

class FirmIncome(BaseModel):
    firm_name: str = Field(..., max_length=125)
    firm_pan: Optional[str] = Field(default=None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    share_of_profit: Decimal = Field(default=Decimal("0"), ge=0)
    share_of_capital_gains: Decimal = Field(default=Decimal("0"), ge=0)
    interest_on_capital: Decimal = Field(default=Decimal("0"), ge=0)
    salary_bonus_from_firm: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# Deemed Incomes
# ---------------------------------------------------------------------------

class DeemedIncomes(BaseModel):
    us41_recovery_of_deduction: Decimal = Field(default=Decimal("0"), ge=0)
    us33ab_recovery: Decimal = Field(default=Decimal("0"), ge=0)
    us35abb_recovery: Decimal = Field(default=Decimal("0"), ge=0)
    us50_capital_gains: Decimal = Field(default=Decimal("0"), ge=0)
    other_deemed_income: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# GST Schedule
# ---------------------------------------------------------------------------

class GSTINEntry(BaseModel):
    gstin: str = Field(..., pattern=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
    turnover: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# Top-level ITR-3 input model
# ---------------------------------------------------------------------------

class ITR3Input(BaseModel):
    """
    Top-level input model for computing an ITR-3 return.
    """

    # --- Assessee meta ---
    age_bracket: AgeBracket = Field(...)
    tax_regime: TaxRegime = Field(...)
    residential_status: ResidentialStatus = Field(default=ResidentialStatus.RES)
    filing_section: ReturnFileSection = Field(default=ReturnFileSection.S11)

    # --- Business / Profession ---
    pl_adjustment: Optional[PLAdjustment] = Field(default=None)
    pl_debits: Optional[PLDebits] = Field(default=None)
    pl_credits: Optional[PLCredits] = Field(default=None)
    pl_disallowances: Optional[PLDisallowances] = Field(default=None)
    balance_sheet: Optional[BalanceSheet] = Field(default=None)
    depreciation: Optional[DepreciationSchedule] = Field(default=None)
    icds_adjustment: Optional[ICDSAdjustment] = Field(default=None)
    deemed_incomes: Optional[DeemedIncomes] = Field(default=None)
    firm_incomes: Optional[List[FirmIncome]] = Field(default=None)

    # --- Heads of Income (non-business) ---
    salary_income: Optional[SalaryIncome] = Field(default=None)
    house_property_income: Optional[HousePropertyIncome] = Field(default=None)
    other_sources_income: Optional[OtherSourcesIncome] = Field(default=None)

    # --- Capital Gains (shared with ITR-2) ---
    cg_transactions: Optional[List[CGTransaction]] = Field(default=None)
    cg_112a_scrips: Optional[List[CG112AScrip]] = Field(default=None)
    vda_transactions: Optional[List[VDATransaction]] = Field(default=None)

    # --- Loss Set-Off (shared with ITR-2) ---
    bf_losses: Optional[List[BFLossItem]] = Field(default=None)
    cf_losses: Optional[List[CFLLossItem]] = Field(default=None)

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

    # --- Deductions ---
    deductions_chapter6a: Optional[Chapter6ADeductions] = Field(default=None)

    # --- TDS/TCS ---
    tds1_entries: Optional[List[TDS1Entry]] = Field(default=None)
    tds2_entries: Optional[List[TDS2Entry]] = Field(default=None)
    tcs_entries: Optional[List[TCSEntry]] = Field(default=None)

    # --- Tax payments ---
    advance_tax_paid: Decimal = Field(default=Decimal("0"), ge=0)
    self_assessment_tax_paid: Decimal = Field(default=Decimal("0"), ge=0)
    # --- Filing dates ---
    filing_date: Optional[date] = Field(default=None)
    due_date: Optional[date] = Field(default=None)
