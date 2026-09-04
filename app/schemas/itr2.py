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


class JurisdictionResidenceEntry(StrictModel):
    """One jurisdiction-of-residence + TIN row (official ``JurisdictionResPrevYrDtls``)."""

    jurisdiction_code: str = Field(min_length=1)
    tin: str = Field(min_length=1, max_length=75)


class CompanyDirectorEntry(StrictModel):
    """One company-directorship disclosure row (official ``CompDirectorPrvYrDtls``)."""

    company_name: str = Field(min_length=1, max_length=125)
    company_type: Literal["D", "F"]
    pan: Optional[str] = Field(default=None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    shares_type: Literal["L", "U"]
    din: Optional[str] = Field(default=None, pattern=r"^[0-9]{8}$")


class UnlistedEquityEntry(StrictModel):
    """One unlisted-equity holding row (official ``HeldUnlistedEqShrPrYrDtls``)."""

    company_name: str = Field(min_length=1, max_length=125)
    company_type: Literal["D", "F"]
    pan: Optional[str] = Field(default=None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    opening_shares: int = Field(ge=0, le=99999999999999)
    opening_cost: Decimal = Field(ge=0)
    acquired_shares: int = Field(default=0, ge=0, le=99999999999999)
    date_of_acquisition: Optional[date] = None
    face_value_per_share: Decimal = Field(default=Decimal("0"), ge=0)
    issue_price_per_share: int = Field(default=0, ge=0, le=99999999999999)
    purchase_price_per_share: Decimal = Field(default=Decimal("0"), ge=0)
    transferred_shares: int = Field(default=0, ge=0, le=99999999999999)
    transfer_sale_consideration: Decimal = Field(default=Decimal("0"), ge=0)
    closing_shares: int = Field(ge=0, le=99999999999999)
    closing_cost: Decimal = Field(ge=0)


class SeventhProvisoClauseEntry(StrictModel):
    """One clause-(iv) seventh-proviso disclosure row (official
    ``clauseiv7provisio139iType``). ITR-2's own nature enum is ``1``/``2``
    only — narrower than ITR-4's four codes; the frontend already restricts
    the dropdown accordingly for ITR-2.
    """

    nature: Literal["1", "2"]
    amount: Decimal = Field(ge=0)


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
    deposit_exceeds_one_crore: bool = False
    foreign_travel_expenditure: Decimal = Field(default=Decimal("0"), ge=0)
    foreign_travel_flag: bool = False
    electricity_expenditure: Decimal = Field(default=Decimal("0"), ge=0)
    electricity_expenditure_flag: bool = False
    current_account_deposits: Decimal = Field(default=Decimal("0"), ge=0)
    other_clause_iv_flag: bool = False
    seventh_proviso_clause_iv_entries: List[SeventhProvisoClauseEntry] = Field(default_factory=list)
    is_company_director: bool = False
    company_director_entries: List[CompanyDirectorEntry] = Field(default_factory=list)
    held_unlisted_equity: bool = False
    unlisted_equity_entries: List[UnlistedEquityEntry] = Field(default_factory=list)
    is_fii_fpi: bool = False
    sebi_registration_number: Optional[str] = Field(
        default=None, pattern=r"^IN[A-Za-z]{2}FP[0-9]{6}$"
    )
    portuguese_civil_code_applies: bool = False
    lei_number: Optional[str] = Field(default=None, min_length=20, max_length=20)
    lei_valid_upto_date: Optional[date] = None
    conditions_res_status: Optional[Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]] = None
    jurisdiction_residence_entries: List[JurisdictionResidenceEntry] = Field(default_factory=list)
    total_stay_india_prev_yr: Optional[int] = Field(default=None, ge=0, le=365)
    total_stay_india_4_prec_yr: Optional[int] = Field(default=None, ge=0, le=1461)
    benefit_us_115h: bool = False
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
        if self.is_company_director and not self.company_director_entries:
            raise ValueError("Company-director filing requires at least one company_director_entries row")
        if self.held_unlisted_equity and not self.unlisted_equity_entries:
            raise ValueError("Unlisted-equity filing requires at least one unlisted_equity_entries row")
        # Statutory minimums the official schema hard-enforces for each
        # seventh-proviso amount (AmtSeventhProvisio139i/ii/iii) -- the
        # checkbox is only meaningful once the real amount crosses the
        # threshold it names, so a flag set without a qualifying amount is a
        # genuine data-entry inconsistency, not a value to silently pass
        # through or drop.
        if self.deposit_exceeds_one_crore and self.current_account_deposits < Decimal("10000000"):
            raise ValueError("Current-account deposits exceeding INR 1 crore requires an amount of at least INR 1,00,00,000")
        if self.foreign_travel_flag and self.foreign_travel_expenditure < Decimal("200000"):
            raise ValueError("Foreign-travel expenditure exceeding INR 2 lakh requires an amount of at least INR 2,00,000")
        if self.electricity_expenditure_flag and self.electricity_expenditure < Decimal("100000"):
            raise ValueError("Electricity expenditure exceeding INR 1 lakh requires an amount of at least INR 1,00,000")
        if self.other_clause_iv_flag and not self.seventh_proviso_clause_iv_entries:
            raise ValueError("Other seventh-proviso clause (iv) filing requires at least one seventh_proviso_clause_iv_entries row")
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


class OSUnexplainedIncome(StrictModel):
    """Section 68/69/69A/69B/69C/69D unexplained-income breakdown.

    Every category here is taxed under section 115BBE (flat rate, no
    deductions/set-off) -- the aggregate of all eight feeds a Schedule-SI
    115BBE entry alongside any ``UNEXPLAINED_115BBE``-type winnings.
    """

    cash_credits_us68: Decimal = Field(default=Decimal("0"), ge=0)
    unexplained_investments_us69: Decimal = Field(default=Decimal("0"), ge=0)
    unexplained_money_us69a: Decimal = Field(default=Decimal("0"), ge=0)
    undisclosed_investments_us69b: Decimal = Field(default=Decimal("0"), ge=0)
    unexplained_expenditure_us69c: Decimal = Field(default=Decimal("0"), ge=0)
    hundi_borrowing_us69d: Decimal = Field(default=Decimal("0"), ge=0)
    prior_year_business_trust_562xii: Decimal = Field(default=Decimal("0"), ge=0)
    prior_year_life_insurance_562xiii: Decimal = Field(default=Decimal("0"), ge=0)

    @property
    def total(self) -> Decimal:
        return (
            self.cash_credits_us68 + self.unexplained_investments_us69
            + self.unexplained_money_us69a + self.undisclosed_investments_us69b
            + self.unexplained_expenditure_us69c + self.hundi_borrowing_us69d
            + self.prior_year_business_trust_562xii + self.prior_year_life_insurance_562xiii
        )


class OSQuarterlyAmount(StrictModel):
    """A quarterly (Q1-Q5) amount breakdown for 234C advance-tax-interest
    purposes (official ``DateRangeType``)."""

    q1: Decimal = Field(default=Decimal("0"), ge=0)
    q2: Decimal = Field(default=Decimal("0"), ge=0)
    q3: Decimal = Field(default=Decimal("0"), ge=0)
    q4: Decimal = Field(default=Decimal("0"), ge=0)
    q5: Decimal = Field(default=Decimal("0"), ge=0)


class OS89ACountryEntry(StrictModel):
    """One Section 89A notified-income-by-country row (official ``NOT89AType``)."""

    country_code: Literal["US", "UK", "CA"]
    amount: Decimal = Field(default=Decimal("0"), ge=0)


class OSSection89A(StrictModel):
    """Section 89A (foreign-retirement-account income deferral) aggregates."""

    income_notified: Decimal = Field(default=Decimal("0"), ge=0)
    income_notified_other: Decimal = Field(default=Decimal("0"), ge=0)
    income_notified_prior_yr: Decimal = Field(default=Decimal("0"), ge=0)
    relief: Decimal = Field(default=Decimal("0"), ge=0)
    country_entries: List[OS89ACountryEntry] = Field(default_factory=list)


class OSOtherIncomeEntry(StrictModel):
    """One "any other income" detail row (official ``OthersIncDtlOS``)."""

    nature: str = Field(min_length=1, max_length=50)
    amount: Decimal = Field(default=Decimal("0"), ge=0)


class OSDividendEntry(StrictModel):
    """One dividend row carrying its official section classification and
    quarter breakdown (official ``DividendXxx`` date-range fields plus the
    ``Dividend22e``/``Dividend22f``/``DividendOthThan22e`` split)."""

    section: Literal[
        "194", "10(22e)", "10(22f)", "115BBDA", "115BBDAaiii",
        "115A1ai", "115A1aA", "115AC", "115ACA", "115AD1i", "DTAA",
    ]
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    q1: Decimal = Field(default=Decimal("0"), ge=0)
    q2: Decimal = Field(default=Decimal("0"), ge=0)
    q3: Decimal = Field(default=Decimal("0"), ge=0)
    q4: Decimal = Field(default=Decimal("0"), ge=0)
    q5: Decimal = Field(default=Decimal("0"), ge=0)


class OSDtaaEntry(StrictModel):
    """One DTAA-rate other-sources income row (official ``NRIDTAADtlsSchOS``)."""

    amount: Decimal
    nature_of_income: Literal["1ai", "1aiii", "1b", "1c", "1d", "2ai", "2aii", "2d", "2e"]
    country_name: str = Field(min_length=1, max_length=55)
    country_code: str = Field(min_length=1)
    dtaa_article: str = Field(min_length=1, max_length=16)
    rate_as_per_treaty: Decimal = Field(ge=0, le=100)
    rate_as_per_it_act: Decimal = Field(ge=0, le=100)
    tax_residency_certificate: Literal["Y", "N"] = "N"
    item_no_incl: str = Field(min_length=1)
    applicable_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class OSDeductions(StrictModel):
    """Other-sources deduction claims (official ``Deductions`` block, minus
    ``DeductionUs57iia`` which the calculator derives from family pension)."""

    expenses: Decimal = Field(default=Decimal("0"), ge=0)
    depreciation: Decimal = Field(default=Decimal("0"), ge=0)
    interest_expense_us57: Decimal = Field(default=Decimal("0"), ge=0)
    interest_expense_eligible_us57: Decimal = Field(default=Decimal("0"), ge=0)
    amount_not_deductible_us58: Decimal = Field(default=Decimal("0"), ge=0)
    profit_chargeable_us59: Decimal = Field(default=Decimal("0"), ge=0)


class OSRaceHorseActivity(StrictModel):
    """Income from owning and maintaining race horses (official
    ``IncFromOwnHorse``) -- a distinct business-like Schedule OS sub-head
    taxed at slab rate with its own specific deductions, separate from the
    ordinary "other sources" total."""

    receipts: Decimal = Field(default=Decimal("0"), ge=0)
    deduction_us57: Decimal = Field(default=Decimal("0"), ge=0)
    amount_not_deductible_us58: Decimal = Field(default=Decimal("0"))
    profit_chargeable_us59: Decimal = Field(default=Decimal("0"))
    balance: Decimal = Field(default=Decimal("0"))


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
    os_unexplained_income: Optional[OSUnexplainedIncome] = None
    os_section_89a: Optional[OSSection89A] = None
    os_other_income_entries: List[OSOtherIncomeEntry] = Field(default_factory=list)
    os_dividend_entries: List[OSDividendEntry] = Field(default_factory=list)
    os_dtaa_entries: List[OSDtaaEntry] = Field(default_factory=list)
    os_dtaa_aggregate: Decimal = Field(default=Decimal("0"), ge=0)
    os_deductions: Optional[OSDeductions] = None
    os_race_horse: Optional[OSRaceHorseActivity] = None
    os_pf_interest_10_11_first_proviso: Decimal = Field(default=Decimal("0"), ge=0)
    os_pf_interest_10_11_second_proviso: Decimal = Field(default=Decimal("0"), ge=0)
    os_pf_interest_10_12_first_proviso: Decimal = Field(default=Decimal("0"), ge=0)
    os_pf_interest_10_12_second_proviso: Decimal = Field(default=Decimal("0"), ge=0)
    os_interest_from_others: Decimal = Field(default=Decimal("0"), ge=0)
    os_lottery_quarters: Optional[OSQuarterlyAmount] = None
    os_gaming_quarters: Optional[OSQuarterlyAmount] = None
    os_machinery_plant_rent: Decimal = Field(default=Decimal("0"), ge=0)
    os_pass_through_income: Decimal = Field(default=Decimal("0"), ge=0)

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
