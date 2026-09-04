"""Canonical AY 2026-27 ITR-2 input schemas.

The models in this module represent taxpayer claims and filing facts. Tax and
schedule totals are computed by the engine; callers cannot override them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum, IntEnum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.itr1 import (
    AgeBracket,
    BankAccount,
    Chapter6ADeductions,
    FilingAddress,
    HousePropertyIncome,
    OtherSourcesIncome,
    PostalAddress,
    SalaryIncome,
    TDS1Entry,
    TDS2Entry,
    TDS3Entry,
    TCSEntry,
    TaxPaymentDetail,
    TaxRegime,
)


class StrictModel(BaseModel):
    """Base model that rejects unknown canonical fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ReturnFileSection(IntEnum):
    """Official AY 2026-27 return filing-section code."""

    ON_TIME_139_1 = 11
    BELATED_139_4 = 12
    NOTICE_142_1 = 13
    NOTICE_148 = 14
    NOTICE_153C = 16
    REVISED_139_5 = 17
    DEFECTIVE_139_9 = 18
    MODIFIED_92CD = 19
    CONDONATION_119_2B = 20

    # Backward-compatible names retained for stored drafts.
    S11 = 11
    S12 = 12
    S13 = 13
    S14 = 14
    S16 = 16
    S17 = 17
    S18 = 18
    S19 = 19
    S20 = 20


class ResidentialStatus(str, Enum):
    """Residential status used by ITR-2."""

    RESIDENT = "RES"
    NON_RESIDENT = "NRI"
    NOT_ORDINARILY_RESIDENT = "NOR"

    RES = "RES"
    NRI = "NRI"
    NOR = "NOR"


class AssesseeStatus(str, Enum):
    """Persons eligible to file ITR-2."""

    INDIVIDUAL = "I"
    HUF = "H"


class ITR2FilingProfile(StrictModel):
    """Identity, address, filing status, and verification facts."""

    pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    assessee_status: AssesseeStatus = AssesseeStatus.INDIVIDUAL
    first_name: str = Field(default="", max_length=25)
    middle_name: str = Field(default="", max_length=25)
    surname_or_org_name: str = Field(min_length=1, max_length=75)
    date_of_birth_or_formation: date
    aadhaar_number: Optional[str] = Field(default=None, pattern=r"^[0-9]{12}$")
    primary_address: FilingAddress
    alternate_address: Optional[PostalAddress] = None
    residential_status: ResidentialStatus = ResidentialStatus.RESIDENT
    return_file_section: ReturnFileSection = ReturnFileSection.ON_TIME_139_1
    filing_due_date: date = date(2026, 7, 31)
    receipt_number: Optional[str] = Field(default=None, pattern=r"^[0-9]{15}$")
    original_return_date: Optional[date] = None
    notice_number: Optional[str] = Field(default=None, max_length=100)
    notice_date: Optional[date] = None
    opted_out_new_tax_regime: bool = False
    seventh_proviso_139: bool = False
    foreign_travel_expenditure: Decimal = Field(default=Decimal("0"), ge=0)
    electricity_expenditure: Decimal = Field(default=Decimal("0"), ge=0)
    current_account_deposits: Decimal = Field(default=Decimal("0"), ge=0)
    is_company_director: bool = False
    held_unlisted_equity: bool = False
    is_fii_fpi: bool = False
    sebi_registration_number: Optional[str] = Field(
        default=None, pattern=r"^IN[A-Za-z]{2}FP[0-9]{6}$"
    )
    portuguese_civil_code_applies: bool = False
    father_name: str = Field(min_length=1, max_length=125)
    verification_place: str = Field(min_length=1, max_length=50)
    verification_capacity: Literal["S", "K"] = "S"

    @model_validator(mode="after")
    def validate_conditional_filing_facts(self) -> "ITR2FilingProfile":
        """Validate revised/notice/FPI and regime-election dependencies."""
        if self.return_file_section == ReturnFileSection.REVISED_139_5:
            if self.receipt_number is None or self.original_return_date is None:
                raise ValueError("Revised return requires receipt number and original return date")
        if self.return_file_section in {
            ReturnFileSection.NOTICE_142_1,
            ReturnFileSection.NOTICE_148,
            ReturnFileSection.NOTICE_153C,
            ReturnFileSection.DEFECTIVE_139_9,
        } and (self.notice_number is None or self.notice_date is None):
            raise ValueError("Notice return requires notice number and notice date")
        if self.is_fii_fpi and self.sebi_registration_number is None:
            raise ValueError("FII/FPI filing requires a SEBI registration number")
        return self


# Compatibility alias for early callers.
PartAGEN1 = ITR2FilingProfile


class CGAssetType(str, Enum):
    """Supported statutory capital-asset classifications."""

    LAND_BUILDING = "land_building"
    LISTED_EQUITY_112A = "listed_equity_112a"
    EQUITY_ORIENTED_FUND_112A = "equity_oriented_fund_112a"
    BUSINESS_TRUST_UNIT_112A = "business_trust_unit_112a"
    LISTED_EQUITY_111A = "listed_equity_111a"
    EQUITY_ORIENTED_FUND_111A = "equity_oriented_fund_111a"
    UNLISTED_SHARES = "unlisted_shares"
    LISTED_SECURITY = "listed_security"
    DEBT_MUTUAL_FUND = "debt_mutual_fund"
    SPECIFIED_MUTUAL_FUND_50AA = "specified_mutual_fund_50aa"
    MARKET_LINKED_DEBENTURE_50AA = "market_linked_debenture_50aa"
    BONDS_DEBENTURES = "bonds_debentures"
    DEPRECIABLE_ASSET = "depreciable_asset"
    JEWELLERY = "jewellery"
    FOREIGN_ASSET = "foreign_asset"
    OTHER = "other"


class CapitalGainExemptionClaim(StrictModel):
    """One evidence-backed capital-gain exemption claim."""

    section: Literal["54", "54B", "54EC", "54F", "115F"]
    transfer_date: date
    eligible_gain: Decimal = Field(ge=0)
    investment_amount: Decimal = Field(ge=0)
    investment_date: Optional[date] = None
    cgas_deposit_amount: Decimal = Field(default=Decimal("0"), ge=0)
    cgas_deposit_date: Optional[date] = None
    cgas_account_number: Optional[str] = Field(default=None, max_length=20)
    cgas_ifsc: Optional[str] = Field(default=None, pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$")

    @model_validator(mode="after")
    def validate_investment_or_deposit(self) -> "CapitalGainExemptionClaim":
        """Require dated investment or complete CGAS evidence."""
        if self.investment_amount > 0 and self.investment_date is None:
            raise ValueError("Exemption investment requires investment_date")
        if self.cgas_deposit_amount > 0 and (
            self.cgas_deposit_date is None
            or self.cgas_account_number is None
            or self.cgas_ifsc is None
        ):
            raise ValueError("CGAS deposit requires date, account number, and IFSC")
        return self


class CGTransaction(StrictModel):
    """One capital-asset disposal with classification and evidence facts."""

    asset_type: CGAssetType
    description: str = Field(default="", max_length=125)
    isin_code: Optional[str] = Field(default=None, pattern=r"^(IN[0-9A-Z]{10}|INNOTREQUIRD)$")
    date_of_acquisition: Optional[date] = None
    date_of_transfer: date
    full_consideration: Decimal = Field(default=Decimal("0"), ge=0)
    stamp_duty_value: Optional[Decimal] = Field(default=None, ge=0)
    fair_market_value_50ca: Optional[Decimal] = Field(default=None, ge=0)
    cost_of_acquisition: Decimal = Field(default=Decimal("0"), ge=0)
    indexed_cost: Decimal = Field(default=Decimal("0"), ge=0)
    improvement_cost: Decimal = Field(default=Decimal("0"), ge=0)
    indexed_improvement: Decimal = Field(default=Decimal("0"), ge=0)
    expenditure_on_transfer: Decimal = Field(default=Decimal("0"), ge=0)
    is_stt_paid_on_acquisition: Optional[bool] = None
    is_stt_paid_on_transfer: Optional[bool] = None
    is_recognized_stock_exchange: Optional[bool] = None
    fair_market_value_jan2018: Optional[Decimal] = Field(default=None, ge=0)
    quantity: Optional[Decimal] = Field(default=None, gt=0)
    sale_price_per_unit: Optional[Decimal] = Field(default=None, ge=0)
    explicit_long_term: Optional[bool] = None
    exemptions: List[CapitalGainExemptionClaim] = Field(default_factory=list)
    # Legacy aggregate claims are accepted but must reconcile to canonical claims.
    deduction_us54: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_us54b: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_us54ec: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_us54f: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="after")
    def validate_transaction(self) -> "CGTransaction":
        """Reject impossible dates, inconsistent quantity, and duplicate claims."""
        if self.date_of_acquisition is not None and self.date_of_transfer <= self.date_of_acquisition:
            raise ValueError("date_of_transfer must be after date_of_acquisition")
        if self.quantity is not None and self.sale_price_per_unit is not None:
            expected = self.quantity * self.sale_price_per_unit
            if abs(expected - self.full_consideration) > Decimal("1"):
                raise ValueError("quantity × sale_price_per_unit must reconcile to consideration")
        canonical = {
            section: sum((claim.investment_amount + claim.cgas_deposit_amount for claim in self.exemptions if claim.section == section), Decimal("0"))
            for section in ("54", "54B", "54EC", "54F")
        }
        legacy = {
            "54": self.deduction_us54,
            "54B": self.deduction_us54b,
            "54EC": self.deduction_us54ec,
            "54F": self.deduction_us54f,
        }
        for section, amount in legacy.items():
            if canonical[section] > 0 and amount not in (Decimal("0"), canonical[section]):
                raise ValueError(f"Conflicting Section {section} exemption amounts")
        return self


class CG112AScrip(StrictModel):
    """Per-scrip Schedule 112A disposal detail."""

    isin_code: str = Field(pattern=r"^(IN[0-9A-Z]{10}|INNOTREQUIRD)$")
    share_unit_name: str = Field(min_length=1, max_length=125)
    is_before_31jan2018: bool = False
    date_of_acquisition: Optional[date] = None
    date_of_transfer: date
    num_shares_units: Decimal = Field(gt=0)
    sale_price_per_share: Decimal = Field(ge=0)
    total_sale_value: Decimal = Field(ge=0)
    cost_acq_without_index: Decimal = Field(ge=0)
    fmv_per_share: Decimal = Field(default=Decimal("0"), ge=0)
    total_fmv: Decimal = Field(default=Decimal("0"), ge=0)
    expenditure_on_transfer: Decimal = Field(default=Decimal("0"), ge=0)
    total_deductions: Decimal = Field(default=Decimal("0"), ge=0)
    balance: Optional[Decimal] = None
    stt_paid_on_acquisition: Optional[bool] = None
    stt_paid_on_transfer: bool = True

    @model_validator(mode="after")
    def validate_scrip_totals(self) -> "CG112AScrip":
        """Validate dates, sale totals, and grandfathering evidence."""
        if self.date_of_acquisition is not None and self.date_of_transfer <= self.date_of_acquisition:
            raise ValueError("112A transfer date must be after acquisition date")
        if abs(self.num_shares_units * self.sale_price_per_share - self.total_sale_value) > Decimal("1"):
            raise ValueError("112A quantity × price must reconcile to sale value")
        if self.is_before_31jan2018 and self.total_fmv <= 0:
            raise ValueError("Pre-31 January 2018 112A scrip requires FMV")
        return self


class VDATransaction(StrictModel):
    """Virtual digital asset transaction under Section 115BBH."""

    date_of_acquisition: date
    date_of_transfer: date
    acquisition_cost: Decimal = Field(default=Decimal("0"), ge=0)
    consideration_received: Decimal = Field(default=Decimal("0"), ge=0)
    income_from_vda: Optional[Decimal] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_dates_and_income(self) -> "VDATransaction":
        """Require valid chronology and reconcile any supplied income."""
        if self.date_of_transfer <= self.date_of_acquisition:
            raise ValueError("VDA transfer date must be after acquisition date")
        computed = max(Decimal("0"), self.consideration_received - self.acquisition_cost)
        if self.income_from_vda is not None and self.income_from_vda != computed:
            raise ValueError("income_from_vda must equal nonnegative consideration less cost")
        return self


class LossHead(str, Enum):
    """Statutory brought-forward loss category supported by ITR-2."""

    HOUSE_PROPERTY = "HP"
    SHORT_TERM_CAPITAL = "STCG"
    LONG_TERM_CAPITAL = "LTCG"
    RACE_HORSE = "RaceHorse"


class BFLossItem(StrictModel):
    """Opening brought-forward loss balance for one origin AY."""

    assessment_year: str = Field(pattern=r"^20[0-9]{2}-[0-9]{2}$")
    head: LossHead
    sub_category: str = Field(default="", max_length=50)
    original_loss: Decimal = Field(default=Decimal("0"), ge=0)
    brought_forward: Decimal = Field(default=Decimal("0"), ge=0)
    date_of_filing: Optional[date] = None

    @model_validator(mode="after")
    def validate_balance(self) -> "BFLossItem":
        """Ensure brought-forward balance does not exceed original loss."""
        if self.original_loss > 0 and self.brought_forward > self.original_loss:
            raise ValueError("brought_forward cannot exceed original_loss")
        return self


class CFLLossItem(StrictModel):
    """Caller-provided legacy CFL control total used only for reconciliation."""

    assessment_year_of_loss: str = Field(pattern=r"^20[0-9]{2}-[0-9]{2}$")
    head: LossHead
    original_loss: Decimal = Field(default=Decimal("0"), ge=0)
    loss_remaining: Decimal = Field(default=Decimal("0"), ge=0)


class ScheduleSIEntry(StrictModel):
    """Additional special-rate income not generated by another schedule."""

    section: Literal["115BB", "115BBE", "115BBF", "115BBG", "115BBJ", "115BBA", "111"]
    description: Optional[str] = Field(default=None, max_length=125)
    gross_income: Decimal = Field(default=Decimal("0"), ge=0)
    deductions: Decimal = Field(default=Decimal("0"), ge=0)
    tax_rate_pct: Optional[Decimal] = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def reject_disallowed_deductions(self) -> "ScheduleSIEntry":
        """Reject deductions for sections that statutorily prohibit them."""
        if self.section in {"115BB", "115BBE"} and self.deductions > 0:
            raise ValueError(f"Deductions are not allowed against Section {self.section} income")
        return self


class AgriculturalIncome(StrictModel):
    """Agricultural income and related expenditure."""

    gross_agricultural_income: Decimal = Field(default=Decimal("0"), ge=0)
    agricultural_deductions: Decimal = Field(default=Decimal("0"), ge=0)
    share_from_firm: Decimal = Field(default=Decimal("0"), ge=0)


class ExemptIncome(StrictModel):
    """Exempt income disclosed in Schedule EI."""

    ppf_interest: Decimal = Field(default=Decimal("0"), ge=0)
    sukanya_samriddhi_interest: Decimal = Field(default=Decimal("0"), ge=0)
    tax_free_bond_interest: Decimal = Field(default=Decimal("0"), ge=0)
    nre_interest: Decimal = Field(default=Decimal("0"), ge=0)
    share_of_profit_from_firm: Decimal = Field(default=Decimal("0"), ge=0)
    other_exempt: Decimal = Field(default=Decimal("0"), ge=0)
    other_description: Optional[str] = Field(default=None, max_length=125)


class FSICountryEntry(StrictModel):
    """Foreign-source income and foreign tax for one jurisdiction."""

    country_code: str = Field(min_length=2, max_length=4)
    tax_identification_no: str = Field(min_length=1, max_length=75)
    salary_income: Decimal = Field(default=Decimal("0"), ge=0)
    hp_income: Decimal = Field(default=Decimal("0"))
    cg_income: Decimal = Field(default=Decimal("0"))
    os_income: Decimal = Field(default=Decimal("0"))
    total_income: Optional[Decimal] = Field(default=None)
    tax_paid_outside_india: Decimal = Field(default=Decimal("0"), ge=0)
    tax_payable_in_india: Decimal = Field(default=Decimal("0"), ge=0)
    relief_section: Literal["90", "90A", "91"] = "90"

    @model_validator(mode="after")
    def derive_and_validate_total(self) -> "FSICountryEntry":
        """Derive total foreign income and reject conflicting totals.

        Guarded with ``!= computed`` before assigning: ``StrictModel`` sets
        ``validate_assignment=True``, so an unconditional
        ``self.total_income = computed`` here re-triggers this same "after"
        validator on every assignment, recursing infinitely (Python's
        recursion limit) the moment any caller constructs an entry without
        pre-supplying a matching ``total_income`` — the previously untested
        common case. Only assigning when the value actually changes lets the
        second (post-assignment) validator pass see them already equal and
        return without reassigning, terminating the recursion.
        """
        computed = self.salary_income + self.hp_income + self.cg_income + self.os_income
        if self.total_income is not None and self.total_income != computed:
            raise ValueError("FSI total_income does not reconcile to income heads")
        if self.total_income != computed:
            self.total_income = computed
        return self


class TR1Entry(StrictModel):
    """Foreign tax relief claim for one jurisdiction."""

    country_code: str = Field(min_length=2, max_length=4)
    tax_identification_no: str = Field(min_length=1, max_length=75)
    income_included_in_this_return: Decimal = Field(default=Decimal("0"), ge=0)
    tax_paid_outside_india: Decimal = Field(default=Decimal("0"), ge=0)
    indian_tax_payable: Decimal = Field(default=Decimal("0"), ge=0)
    relief_claimed: Decimal = Field(default=Decimal("0"), ge=0)
    relief_section: Literal["90", "90A", "91"] = "90"
    form67_filed: bool = False

    @model_validator(mode="after")
    def validate_relief_limit(self) -> "TR1Entry":
        """Limit relief to foreign tax and Indian tax attributable to income."""
        if self.relief_claimed > min(self.tax_paid_outside_india, self.indian_tax_payable):
            raise ValueError("Foreign tax relief exceeds foreign or Indian tax")
        return self


class ForeignAssetType(str, Enum):
    """Schedule FA disclosure category."""

    BANK_ACCOUNT = "bank_account"
    CUSTODIAL_ACCOUNT = "custodial_account"
    EQUITY_DEBT_INTEREST = "equity_debt_interest"
    CASH_VALUE_INSURANCE = "cash_value_insurance"
    FINANCIAL_INTEREST = "financial_interest"
    IMMOVABLE_PROPERTY = "immovable_property"
    SIGNING_AUTHORITY = "signing_authority"
    TRUST = "trust"
    OTHER_FOREIGN_INCOME = "other_foreign_income"
    OTHER_ASSET = "other_asset"


class ForeignAssetEntry(StrictModel):
    """One Schedule FA asset or account disclosure."""

    asset_type: ForeignAssetType
    country_code: str = Field(min_length=2, max_length=4)
    institution_or_entity_name: str = Field(min_length=1, max_length=125)
    address: str = Field(min_length=1, max_length=250)
    account_or_asset_identifier: str = Field(min_length=1, max_length=100)
    ownership_status: str = Field(min_length=1, max_length=50)
    opening_or_acquisition_date: date
    peak_value: Decimal = Field(default=Decimal("0"), ge=0)
    closing_value: Decimal = Field(default=Decimal("0"), ge=0)
    gross_income: Decimal = Field(default=Decimal("0"))
    income_offered: Decimal = Field(default=Decimal("0"))
    income_head: Optional[Literal["SAL", "HP", "CG", "OS"]] = None


class SPIEntry(StrictModel):
    """Income clubbed under Section 64."""

    specified_person_name: str = Field(min_length=1, max_length=125)
    pan: Optional[str] = Field(default=None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    relationship: str = Field(min_length=1, max_length=50)
    amount_included: Decimal = Field(default=Decimal("0"), ge=0)
    head_of_income: Literal["SAL", "HP", "CG", "OS"] = "OS"


class PTIEntry(StrictModel):
    """Pass-through income from a business trust or investment fund."""

    entity_name: str = Field(min_length=1, max_length=125)
    entity_pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    income_head: Literal["HP", "STCG", "LTCG", "OS"]
    section: str = Field(min_length=1, max_length=20)
    income_amount: Decimal = Field(default=Decimal("0"))
    tds_credit: Decimal = Field(default=Decimal("0"), ge=0)


class AMTCreditItem(StrictModel):
    """AMT credit brought forward from one assessment year."""

    assessment_year: str = Field(pattern=r"^20[0-9]{2}-[0-9]{2}$")
    credit_brought_forward: Decimal = Field(ge=0)


class AMTInput(StrictModel):
    """AMT additions and opening credit ledger."""

    deduction_10aa: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_80ia_to_80rrb_except_80p: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_35ad_net_depreciation: Decimal = Field(default=Decimal("0"), ge=0)
    amt_credits: List[AMTCreditItem] = Field(default_factory=list)
    # Legacy controls retained for migration; calculator validates rather than trusts them.
    adjusted_total_income: Decimal = Field(default=Decimal("0"), ge=0)
    amt_rate_pct: Decimal = Field(default=Decimal("18.5"), ge=0, le=100)
    amt_tax: Decimal = Field(default=Decimal("0"), ge=0)
    amt_credit_brought_forward: Decimal = Field(default=Decimal("0"), ge=0)
    amt_credit_utilised: Decimal = Field(default=Decimal("0"), ge=0)


class AssetLiabilityInput(StrictModel):
    """Schedule AL assets and related liabilities."""

    immovable_property: Decimal = Field(default=Decimal("0"), ge=0)
    cash_in_hand: Decimal = Field(default=Decimal("0"), ge=0)
    bank_deposits: Decimal = Field(default=Decimal("0"), ge=0)
    shares_and_securities: Decimal = Field(default=Decimal("0"), ge=0)
    insurance_policies: Decimal = Field(default=Decimal("0"), ge=0)
    loans_and_advances: Decimal = Field(default=Decimal("0"), ge=0)
    jewellery: Decimal = Field(default=Decimal("0"), ge=0)
    art: Decimal = Field(default=Decimal("0"), ge=0)
    vehicles_boats_aircraft: Decimal = Field(default=Decimal("0"), ge=0)
    related_liabilities: Decimal = Field(default=Decimal("0"), ge=0)


class Schedule5AInput(StrictModel):
    """Portuguese Civil Code income apportionment facts."""

    spouse_name: str = Field(min_length=1, max_length=125)
    spouse_pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    spouse_aadhaar: Optional[str] = Field(default=None, pattern=r"^[0-9]{12}$")
    hp_amount_apportioned: Decimal = Field(default=Decimal("0"))
    cg_amount_apportioned: Decimal = Field(default=Decimal("0"))
    os_amount_apportioned: Decimal = Field(default=Decimal("0"))
    tds_apportioned: Decimal = Field(default=Decimal("0"), ge=0)


class ESOPDeferralInput(StrictModel):
    """Eligible-startup ESOP tax deferral ledger entry."""

    employer_pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    dpiit_registration_number: str = Field(min_length=1, max_length=50)
    assessment_year: str = Field(pattern=r"^20(2[1-6])-[0-9]{2}$")
    tax_deferred_brought_forward: Decimal = Field(default=Decimal("0"), ge=0)
    tax_payable_current_year: Decimal = Field(default=Decimal("0"), ge=0)
    balance_tax_carried_forward: Decimal = Field(default=Decimal("0"), ge=0)


class EmployerFilingDetail(StrictModel):
    """Official employer identity and address for one Schedule S row."""

    employer_tan: str = Field(pattern=r"^[A-Z]{4}[0-9]{5}[A-Z]$")
    employer_name: str = Field(min_length=1, max_length=125)
    nature_of_employment: Literal["CGOV", "SGOV", "PSU", "PE", "PESG", "PEPS", "PEO", "OTH"] = "OTH"
    address_detail: str = Field(min_length=1, max_length=200)
    city_or_town_or_district: str = Field(min_length=1, max_length=50)
    state_code: str = Field(pattern=r"^(0[1-9]|[12][0-9]|3[0-7]|99)$")


class PropertyFilingDetail(StrictModel):
    """Official address and ownership facts for one Schedule HP row."""

    address_detail: str = Field(min_length=1, max_length=200)
    city_or_town_or_district: str = Field(min_length=1, max_length=50)
    state_code: str = Field(pattern=r"^(0[1-9]|[12][0-9]|3[0-7]|99)$")
    country_code: str = Field(default="91", min_length=1, max_length=4)
    pin_code: Optional[str] = Field(default=None, pattern=r"^[1-9][0-9]{5}$")
    zip_code: Optional[str] = Field(default=None, min_length=1, max_length=8)
    property_owner: Literal["SE", "MI", "SP", "OT"] = "SE"
    co_owned: bool = False
    assessee_share_percent: Decimal = Field(default=Decimal("100"), ge=0, le=100)

    @model_validator(mode="after")
    def validate_postal_code(self) -> "PropertyFilingDetail":
        """Require Indian PIN or foreign ZIP according to country code."""
        if self.country_code == "91" and self.pin_code is None:
            raise ValueError("Indian property requires pin_code")
        if self.country_code != "91" and self.zip_code is None:
            raise ValueError("Foreign property requires zip_code")
        return self


class TDS3FilingDetail(StrictModel):
    """Buyer/tenant identity and income head for one Schedule TDS3 row."""

    buyer_tenant_pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    head_of_income: Literal["HP", "CG", "OS", "EI"] = "OS"


class OSGiftBreakdown(StrictModel):
    """Section 56(2)(x) taxable-gift category breakdown for Schedule OS.

    Mirrors the official ``IncOthThanOwnRaceHorse`` block's own gift-category
    fields exactly (``Tot562x``'s components): money and "any other property"
    without consideration are tested against the aggregate INR 50,000
    threshold (the whole amount becomes taxable once crossed, not just the
    excess); immovable property is tested per-property against its own
    stamp-duty value/inadequate-consideration threshold. Gifts from a
    relative or received on the occasion of marriage are excluded entirely
    upstream, before this breakdown is built.
    """

    aggregate_without_consideration: Decimal = Field(default=Decimal("0"), ge=0)
    immovable_property_without_consideration: Decimal = Field(default=Decimal("0"), ge=0)
    immovable_property_inadequate_consideration: Decimal = Field(default=Decimal("0"), ge=0)
    other_property_without_consideration: Decimal = Field(default=Decimal("0"), ge=0)
    other_property_inadequate_consideration: Decimal = Field(default=Decimal("0"), ge=0)


class ITR2Input(StrictModel):
    """Complete canonical input for an AY 2026-27 ITR-2 computation."""

    age_bracket: AgeBracket
    tax_regime: TaxRegime
    residential_status: ResidentialStatus = ResidentialStatus.RESIDENT
    filing_section: ReturnFileSection = ReturnFileSection.ON_TIME_139_1
    filing_profile: Optional[ITR2FilingProfile] = None
    employer_filing_details: List[EmployerFilingDetail] = Field(default_factory=list)
    property_filing_details: List[PropertyFilingDetail] = Field(default_factory=list)
    tds3_filing_details: List[TDS3FilingDetail] = Field(default_factory=list)

    salary_income: Optional[SalaryIncome] = None
    house_property_income: Optional[HousePropertyIncome] = None
    house_properties: List[HousePropertyIncome] = Field(default_factory=list)
    other_sources_income: Optional[OtherSourcesIncome] = None
    os_gift_breakdown: Optional[OSGiftBreakdown] = None
    os_pf_income_benefit: Decimal = Field(default=Decimal("0"), ge=0)
    os_pf_tax_benefit: Decimal = Field(default=Decimal("0"), ge=0)

    cg_transactions: List[CGTransaction] = Field(default_factory=list)
    cg_112a_scrips: List[CG112AScrip] = Field(default_factory=list)
    vda_transactions: List[VDATransaction] = Field(default_factory=list)
    bf_losses: List[BFLossItem] = Field(default_factory=list)
    cf_losses: List[CFLLossItem] = Field(default_factory=list)
    si_entries: List[ScheduleSIEntry] = Field(default_factory=list)
    agricultural_income: Optional[AgriculturalIncome] = None
    exempt_income: Optional[ExemptIncome] = None
    fsi_entries: List[FSICountryEntry] = Field(default_factory=list)
    tr1_entries: List[TR1Entry] = Field(default_factory=list)
    foreign_assets: List[ForeignAssetEntry] = Field(default_factory=list)
    spi_entries: List[SPIEntry] = Field(default_factory=list)
    pti_entries: List[PTIEntry] = Field(default_factory=list)
    amt_input: Optional[AMTInput] = None
    asset_liability: Optional[AssetLiabilityInput] = None
    schedule_5a: Optional[Schedule5AInput] = None
    esop_deferrals: List[ESOPDeferralInput] = Field(default_factory=list)

    deductions_chapter6a: Optional[Chapter6ADeductions] = None
    tds1_entries: List[TDS1Entry] = Field(default_factory=list)
    tds2_entries: List[TDS2Entry] = Field(default_factory=list)
    tds3_entries: List[TDS3Entry] = Field(default_factory=list)
    tcs_entries: List[TCSEntry] = Field(default_factory=list)
    tax_payment_entries: List[TaxPaymentDetail] = Field(default_factory=list)
    bank_accounts: List[BankAccount] = Field(default_factory=list)

    advance_tax_paid: Decimal = Field(default=Decimal("0"), ge=0)
    advance_tax_q1: Optional[Decimal] = Field(default=None, ge=0)
    advance_tax_q2: Optional[Decimal] = Field(default=None, ge=0)
    advance_tax_q3: Optional[Decimal] = Field(default=None, ge=0)
    advance_tax_q4: Optional[Decimal] = Field(default=None, ge=0)
    self_assessment_tax_paid: Decimal = Field(default=Decimal("0"), ge=0)
    filing_date: Optional[date] = None
    due_date: Optional[date] = None
    relief_89: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("bank_accounts")
    @classmethod
    def validate_primary_bank(cls, value: List[BankAccount]) -> List[BankAccount]:
        """Allow at most one refund-designated bank account."""
        if sum(1 for account in value if account.is_primary) > 1:
            raise ValueError("Only one bank account may be designated for refund")
        return value

    @model_validator(mode="after")
    def validate_cross_schedule_contract(self) -> "ITR2Input":
        """Reject conflicting compatibility fields and schedule dependencies."""
        if self.house_property_income is not None and self.house_properties:
            raise ValueError("Use either house_property_income or house_properties, not both")
        property_count = int(self.house_property_income is not None) + len(self.house_properties)
        if self.property_filing_details and len(self.property_filing_details) != property_count:
            raise ValueError("property_filing_details must contain one row per house property")
        if self.employer_filing_details and len(self.employer_filing_details) != len(self.tds1_entries):
            raise ValueError("employer_filing_details must contain one row per TDS1 employer")
        if self.tds3_filing_details and len(self.tds3_filing_details) != len(self.tds3_entries):
            raise ValueError("tds3_filing_details must contain one row per TDS3 entry")
        if self.filing_profile is not None:
            if self.filing_profile.residential_status != self.residential_status:
                raise ValueError("Filing-profile residential status conflicts with return input")
            if self.filing_profile.return_file_section != self.filing_section:
                raise ValueError("Filing-profile section conflicts with return input")
            if self.filing_profile.portuguese_civil_code_applies != (self.schedule_5a is not None):
                raise ValueError("Schedule 5A presence must match filing profile")
        if self.foreign_assets and self.residential_status == ResidentialStatus.NON_RESIDENT:
            raise ValueError("Schedule FA is not applicable to a non-resident")
        fsi_keys = {(entry.country_code, entry.tax_identification_no) for entry in self.fsi_entries}
        for relief in self.tr1_entries:
            if (relief.country_code, relief.tax_identification_no) not in fsi_keys:
                raise ValueError("Every TR1 claim must match a Schedule FSI jurisdiction/TIN")
        if self.filing_date is not None and self.due_date is None:
            raise ValueError("due_date is required when filing_date is supplied")
        return self
