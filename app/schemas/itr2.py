"""
ITR-2 input schemas.

ITR-2 is for Individuals and HUFs NOT having income from business or profession.

Eligibility:
  - Resident / Non-Resident / Not Ordinarily Resident (ITR-2 covers all)
  - Having capital gains (any type, any amount)
  - Having foreign assets / foreign income
  - Having agricultural income > Rs 5,000
  - Being a director in a company
  - Holding unlisted equity shares
  - Having brought-forward / carry-forward losses
  - Total income can exceed Rs 50 lakh

Disqualifiers (must use ITR-3 instead):
  - Income from business or profession (PGBP)

Schedules unique to ITR-2 (not in ITR-1):
  - Full CG schedule (STCG, LTCG, 112A, 115AD, VDA, exemptions)
  - CYLA (current year loss adjustment)
  - BFLA (brought forward loss adjustment)
  - CFL (carried forward losses)
  - SI (special rate incomes)
  - EI (exempt / agricultural income)
  - SPI (clubbing of income)
  - FSI + TR1 (foreign income + tax relief)
  - FA (foreign assets)
  - AL (assets and liabilities, if TI > 50L)
  - AMT / AMTC (alternate minimum tax)
  - ESOP (employee stock option deferral)
  - PTI (pass-through income from business trusts)
  - 5A (Portuguese Civil Code apportionment)
  - 80GGA, 80GGC (non-business donations)
  - TDS1, TDS2, TCS schedules
"""

from decimal import Decimal
from enum import Enum
from typing import List, Optional
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.itr1 import (
    AgeBracket, TaxRegime,
    SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions,
    TDS1Entry, TDS2Entry, TCSEntry,
)


# ---------------------------------------------------------------------------
# Filing Status
# ---------------------------------------------------------------------------

class ReturnFileSection(int, Enum):
    """Section under which return is filed."""
    S11 = 11    # Voluntary
    S12 = 12    # u/s 142(1)
    S14 = 14    # Having losses
    S15 = 15    # Foreign comparison
    S16 = 16    # Non-resident
    S17 = 17    # Revised return
    S18 = 18    # Modified return
    S19 = 19    # Updated return u/s 139(8A)
    S20 = 20    # Updated return (second)


class ResidentialStatus(str, Enum):
    RES = "RES"
    NRI = "NRI"
    NOR = "NOR"


class PartAGEN1(BaseModel):
    """Personal and filing information required for ITR-2."""
    pan: str = Field(..., pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    first_name: str = Field(..., max_length=75)
    middle_name: Optional[str] = Field(default=None, max_length=75)
    surname: str = Field(..., min_length=1, max_length=75)
    dob: date = Field(...)
    aadhaar_card_no: Optional[str] = Field(default=None, pattern=r"^[0-9]{12}$")
    mobile_no: str = Field(..., pattern=r"^[1-9][0-9]{9}$")
    email_address: Optional[str] = Field(default=None)
    residential_status: ResidentialStatus = Field(default=ResidentialStatus.RES)
    return_file_section: ReturnFileSection = Field(default=ReturnFileSection.S11)
    receipt_no: Optional[str] = Field(default=None, pattern=r"^[0-9]{15}$")
    orig_return_filed_date: Optional[date] = Field(default=None)
    itr_filing_due_date: Optional[date] = Field(default=None)
    seventh_provisio_139: str = Field(default="N")   # Y/N - if Y, triggers amount fields
    employer_category: Optional[str] = Field(default=None)  # GOVT/PSU/OTHER
    return_filed_by_representative: Optional[str] = Field(default="N")


# ---------------------------------------------------------------------------
# Capital Gains - Full (for ITR-2)
# ---------------------------------------------------------------------------

class CGAssetType(str, Enum):
    LAND_BUILDING = "land_building"
    LISTED_EQUITY_112A = "listed_equity_112a"
    LISTED_EQUITY_111A = "listed_equity_111a"
    UNLISTED_SHARES = "unlisted_shares"
    DEBT_MUTUAL_FUND = "debt_mutual_fund"
    BONDS_DEBENTURES = "bonds_debentures"
    JEWELLERY = "jewellery"
    OTHER = "other"


class CGTransaction(BaseModel):
    """Individual capital gains transaction."""
    asset_type: CGAssetType = Field(...)
    description: Optional[str] = Field(default=None)
    date_of_acquisition: Optional[date] = Field(default=None)
    date_of_transfer: Optional[date] = Field(default=None)
    full_consideration: Decimal = Field(default=Decimal("0"), ge=0)
    cost_of_acquisition: Decimal = Field(default=Decimal("0"), ge=0)
    indexed_cost: Decimal = Field(default=Decimal("0"), ge=0)
    improvement_cost: Decimal = Field(default=Decimal("0"), ge=0)
    indexed_improvement: Decimal = Field(default=Decimal("0"), ge=0)
    expenditure_on_transfer: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_us54: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_us54b: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_us54ec: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_us54f: Decimal = Field(default=Decimal("0"), ge=0)
    is_stt_paid: bool = Field(default=False)
    fair_market_value_jan2018: Optional[Decimal] = Field(default=None, ge=0)


class CG112AScrip(BaseModel):
    """Individual scrip detail for Schedule 112A."""
    isin_code: Optional[str] = Field(default=None, pattern=r"^IN[0-9A-Z]{10}$")
    share_unit_name: Optional[str] = Field(default=None, max_length=125)
    is_before_31jan2018: bool = Field(default=False)
    num_shares_units: Optional[Decimal] = Field(default=None, ge=0)
    sale_price_per_share: Optional[Decimal] = Field(default=None, ge=0)
    total_sale_value: Decimal = Field(default=Decimal("0"), ge=0)
    cost_acq_without_index: Decimal = Field(default=Decimal("0"), ge=0)
    fmv_per_share: Optional[Decimal] = Field(default=None, ge=0)
    total_fmv: Decimal = Field(default=Decimal("0"), ge=0)
    expenditure_on_transfer: Decimal = Field(default=Decimal("0"), ge=0)
    total_deductions: Decimal = Field(default=Decimal("0"), ge=0)
    balance: Decimal = Field(default=Decimal("0"))


class VDATransaction(BaseModel):
    """Virtual Digital Asset transaction u/s 115BBH."""
    date_of_acquisition: date = Field(...)
    date_of_transfer: date = Field(...)
    acquisition_cost: Decimal = Field(default=Decimal("0"), ge=0)
    consideration_received: Decimal = Field(default=Decimal("0"), ge=0)
    income_from_vda: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# CYLA / BFLA / CFL Inputs
# ---------------------------------------------------------------------------

class BFLossItem(BaseModel):
    """Brought forward loss from a prior year."""
    assessment_year: str = Field(...)
    head: str = Field(...)
    sub_category: str = Field(default="")
    original_loss: Decimal = Field(default=Decimal("0"), ge=0)
    brought_forward: Decimal = Field(default=Decimal("0"), ge=0)


class CFLLossItem(BaseModel):
    """Carry forward loss detail."""
    assessment_year_of_loss: str = Field(...)
    head: str = Field(...)
    original_loss: Decimal = Field(default=Decimal("0"), ge=0)
    loss_remaining: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# Special Rate Incomes (Schedule SI)
# ---------------------------------------------------------------------------

class ScheduleSIEntry(BaseModel):
    section: str = Field(...)
    description: Optional[str] = Field(default=None)
    gross_income: Decimal = Field(default=Decimal("0"), ge=0)
    deductions: Decimal = Field(default=Decimal("0"), ge=0)
    tax_rate_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)


# ---------------------------------------------------------------------------
# Agricultural & Exempt Income (Schedule EI)
# ---------------------------------------------------------------------------

class AgriculturalIncome(BaseModel):
    gross_agricultural_income: Decimal = Field(default=Decimal("0"), ge=0)
    agricultural_deductions: Decimal = Field(default=Decimal("0"), ge=0)
    share_from_firm: Decimal = Field(default=Decimal("0"), ge=0)


class ExemptIncome(BaseModel):
    """Other exempt incomes that must be reported in Schedule EI."""
    ppf_interest: Decimal = Field(default=Decimal("0"), ge=0)
    sukanya_samriddhi_interest: Decimal = Field(default=Decimal("0"), ge=0)
    tax_free_bond_interest: Decimal = Field(default=Decimal("0"), ge=0)
    nre_interest: Decimal = Field(default=Decimal("0"), ge=0)
    other_exempt: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# Foreign Schedules (FSI, TR1, FA)
# ---------------------------------------------------------------------------

class FSICountryEntry(BaseModel):
    country_code: str = Field(..., length=2)
    tax_identification_no: Optional[str] = Field(default=None)
    salary_income: Decimal = Field(default=Decimal("0"), ge=0)
    hp_income: Decimal = Field(default=Decimal("0"), ge=0)
    cg_income: Decimal = Field(default=Decimal("0"), ge=0)
    os_income: Decimal = Field(default=Decimal("0"), ge=0)
    total_income: Decimal = Field(default=Decimal("0"), ge=0)
    tax_paid_outside_india: Decimal = Field(default=Decimal("0"), ge=0)


class TR1Entry(BaseModel):
    country_code: str = Field(..., length=2)
    income_included_in_this_return: Decimal = Field(default=Decimal("0"), ge=0)
    tax_paid_outside_india: Decimal = Field(default=Decimal("0"), ge=0)
    indian_tax_payable: Decimal = Field(default=Decimal("0"), ge=0)
    relief_claimed: Decimal = Field(default=Decimal("0"), ge=0)
    is_dtaa_claim: bool = Field(default=True)


# ---------------------------------------------------------------------------
# Schedule SPI (Clubbing)
# ---------------------------------------------------------------------------

class SPIEntry(BaseModel):
    specified_person_name: str = Field(..., max_length=125)
    relationship: str = Field(...)
    amount_included: Decimal = Field(default=Decimal("0"), ge=0)
    head_of_income: str = Field(default="OS")


# ---------------------------------------------------------------------------
# Schedule AMT (Alternate Minimum Tax)
# ---------------------------------------------------------------------------

class AMTInput(BaseModel):
    adjusted_total_income: Decimal = Field(default=Decimal("0"), ge=0)
    amt_rate_pct: Decimal = Field(default=Decimal("18.5"), ge=0, le=100)
    amt_tax: Decimal = Field(default=Decimal("0"), ge=0)
    amt_credit_brought_forward: Decimal = Field(default=Decimal("0"), ge=0)
    amt_credit_utilised: Decimal = Field(default=Decimal("0"), ge=0)


# ---------------------------------------------------------------------------
# TDS/TCS for ITR-2 (Schedule TDS1, TDS2, TCS)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Top-level ITR-2 input model
# ---------------------------------------------------------------------------

class ITR2Input(BaseModel):
    """
    Top-level input model for computing an ITR-2 return.

    Required schedules per ITD JSON spec:
      - PartA-GEN1, ScheduleCYLA, ScheduleBFLA, PartB-TI, PartB-TTI, Verification
    """

    # --- Assessee meta ---
    age_bracket: AgeBracket = Field(...)
    tax_regime: TaxRegime = Field(...)
    residential_status: ResidentialStatus = Field(default=ResidentialStatus.RES)
    filing_section: ReturnFileSection = Field(default=ReturnFileSection.S11)

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

    # --- AMT ---
    amt_input: Optional[AMTInput] = Field(default=None)

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
