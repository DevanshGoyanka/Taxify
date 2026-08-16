"""
ITR-4 (Sugam) input schemas.

ITR-4 applies to resident individuals, Hindu Undivided Families (HUFs), and
partnership firms (NOT LLPs) who opt for presumptive taxation under one of:
  - Section 44AD  — eligible businesses (traders, etc.)
  - Section 44ADA — specified professionals
  - Section 44AE  — goods carriage operators (≤ 10 vehicles)

Total income must not exceed ₹50 lakh. The assessee may also have salary,
house property, and other sources income — those are covered by the shared
models imported from itr1.py.

Only ONE presumptive scheme can be active per return. The active scheme is
indicated by the `presumptive_scheme` enum in ITR4Input; the corresponding
sub-model must be populated, the others must be None.

Capital gains under Section 112A (LTCG on listed equity/equity MF) are permitted
up to ₹1.25 lakh (CBDT notification effective AY 2025-26 onwards). No other capital
gains, brought-forward losses, foreign income, or speculative business income are
within ITR-4 scope.
"""

from decimal import Decimal
from enum import Enum
from typing import List, Optional, Literal
from datetime import date

from pydantic import BaseModel, Field, model_validator

# Shared tax-domain primitives (PAN/TAN patterns, donation, loan, TDS entry
# shapes — these represent tax concepts, not ITR-1 form logic). The ITR-4
# form-specific workflow lives entirely in app/engine/itd/itr4.py and
# app/engine/calculators/itr4.py.
from app.schemas.itr1 import (
    AgeBracket,
    AssesseeType,
    CapitalGainsIncome,
    Chapter6ADeductions,
    HousePropertyIncome,
    OtherSourcesIncome,
    SalaryIncome,
    TaxRegime,
    TDS1Entry, TDS2Entry, TDS3Entry, TCSEntry,
    Schedule80D, Schedule80G, Schedule80GGA, Schedule80GGC,
    Schedule80DD, Schedule80U,
    Schedule80CEntry, Schedule80CCCEntry, Schedule80EEntry,
    Schedule80EELoanEntry, Schedule80EEALoanEntry, Schedule80EEBLoanEntry,
    HRADetails, CoOwnershipDetails, RepresentativeDetails,
    LoanDetails, LoanDetail, SecondaryAddress,
    Donation80G, InsurancePolicy,
    TaxPaymentDetail,
)


# ---------------------------------------------------------------------------
# Enumeration — which presumptive scheme is active
# ---------------------------------------------------------------------------


class PresumptiveScheme(str, Enum):
    """
    Indicates which presumptive taxation scheme the assessee has opted for.

    Only one scheme can be active per ITR-4 return. NONE is used when the
    assessee has no presumptive business/professional income (not a typical
    ITR-4 scenario, but guarded for completeness).
    """

    NONE = "none"
    S44AD = "44AD"    # Eligible business — Section 44AD
    S44ADA = "44ADA"  # Specified profession — Section 44ADA
    S44AE = "44AE"    # Goods carriage — Section 44AE


# ---------------------------------------------------------------------------
# Section 44AD — Presumptive Business Income
# ---------------------------------------------------------------------------


class PresumptiveBusinessIncome44AD(BaseModel):
    """
    Input data for computing presumptive business income under Section 44AD.

    Eligible assessees: resident individuals, HUFs, and partnership firms
    (not LLPs) engaged in any eligible business (excluding commission/
    brokerage agents, professionals covered by 44ADA, and certain others).

    Turnover limits (AY 2025-26 onwards):
      - Up to ₹2 crore always eligible.
      - Up to ₹3 crore IF cash receipts ≤ 5% of total turnover
        (Finance Act 2023 amendment).

    Presumptive profit rates (enforced by the computation engine, not here):
      - 6% of turnover received via banking/digital modes (Section 44AD(1)).
      - 8% of turnover received via cash (Section 44AD(1)).

    The assessee may declare income higher than the presumptive rate.

    Relevant IT Act section: Section 44AD.
    """

    total_turnover: Decimal = Field(
        ge=0,
        description=(
            "Aggregate turnover or gross receipts from the eligible business "
            "during the previous year (Section 44AD(1)). Must not exceed "
            "₹2 crore (or ₹3 crore if digital_turnover / total_turnover ≥ 95%). "
            "Eligibility check is enforced by the computation engine."
        ),
    )
    digital_turnover: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Portion of total_turnover received via account-payee cheque, "
            "bank draft, NEFT, RTGS, ECS, or other prescribed electronic "
            "modes (Section 44AD(1) proviso). Attracts 6% presumptive rate. "
            "Must satisfy: digital_turnover + cash_turnover == total_turnover."
        ),
    )
    cash_turnover: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Portion of total_turnover received in cash or via non-account-"
            "payee instruments (Section 44AD(1)). Attracts 8% presumptive "
            "rate. Must satisfy: digital_turnover + cash_turnover == "
            "total_turnover."
        ),
    )
    income_declared: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description=(
            "Income declared by the assessee if higher than the presumptive "
            "amount (Section 44AD(1) allows declaration above the floor). "
            "If None, the computation engine will compute income at the "
            "statutory rates (6%/8%) of the respective turnover splits."
        ),
    )

    @model_validator(mode="after")
    def _check_44ad_cap(self) -> "PresumptiveBusinessIncome44AD":
        if self.total_turnover > Decimal("30000000"):
            raise ValueError("Total turnover exceeds ₹3 crore limit")
        return self


# ---------------------------------------------------------------------------
# Section 44ADA — Presumptive Professional Income
# ---------------------------------------------------------------------------


class PresumptiveProfessionalIncome44ADA(BaseModel):
    """
    Input data for computing presumptive professional income under Section 44ADA.

    Eligible assessees: resident individuals and partnership firms (not LLPs)
    engaged in specified professions — legal, medical, engineering,
    architectural, accountancy, technical consultancy, interior decoration,
    or any other profession notified by the CBDT (Section 44ADA(1)).

    Gross receipts limits (AY 2025-26 onwards, Finance Act 2023 amendment):
      - Up to ₹50 lakh always eligible.
      - Up to ₹75 lakh IF cash receipts ≤ 5% of total gross receipts.

    Presumptive income rate (enforced by the engine):
      - Minimum 50% of gross receipts must be declared as income
        (Section 44ADA(1)).

    Relevant IT Act section: Section 44ADA.
    """

    gross_receipts: Decimal = Field(
        ge=0,
        description=(
            "Total gross receipts from the specified profession during the "
            "previous year (Section 44ADA(1)). Must not exceed ₹50 lakh "
            "(or ₹75 lakh if cash receipts ≤ 5%). Eligibility enforced by "
            "the computation engine."
        ),
    )
    digital_receipts: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Portion of gross_receipts received via banking/digital modes "
            "(account-payee cheques, NEFT, RTGS, etc.). Used by the engine "
            "to verify the 5% cash threshold for the ₹75 lakh enhanced limit."
        ),
    )
    cash_receipts: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Portion of gross_receipts received in cash or via non-account-"
            "payee instruments. Must satisfy: "
            "digital_receipts + cash_receipts == gross_receipts."
        ),
    )
    income_declared: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description=(
            "Income declared if higher than 50% of gross receipts. "
            "If None, the computation engine defaults to 50% of gross_receipts "
            "(Section 44ADA(1))."
        ),
    )

    @model_validator(mode="after")
    def _check_44ada_cap(self) -> "PresumptiveProfessionalIncome44ADA":
        if self.gross_receipts > Decimal("7500000"):
            raise ValueError("Gross receipts exceed ₹75 lakh limit")
        return self


# ---------------------------------------------------------------------------
# Section 44AE — Presumptive Goods Carriage Income
# ---------------------------------------------------------------------------


class GoodsCarriageVehicle(BaseModel):
    """
    Details of a single goods carriage vehicle owned during the year.

    Under Section 44AE, income is computed per vehicle per month (or part
    of a month) the vehicle is owned. A part-month counts as a full month.

    Rate (AY 2025-26, Section 44AE(2)):
      - Heavy goods vehicle (GVW > 12,000 kg): ₹1,000 per ton of GVW
        (or unladen weight) per month or part of a month.
      - Other / light goods vehicle (GVW ≤ 12,000 kg): ₹7,500 per vehicle
        per month or part of a month.

    The assessee may declare actual income if higher.

    Relevant IT Act section: Section 44AE(2).
    """

    is_heavy_goods_vehicle: bool = Field(
        description=(
            "True if the vehicle is a 'heavy goods vehicle' — i.e., gross "
            "vehicle weight (GVW) exceeds 12,000 kg (Section 44AE(2) "
            "Explanation). False for light or medium goods vehicles "
            "(GVW ≤ 12,000 kg), which attract a flat ₹7,500/month rate."
        ),
    )
    gross_vehicle_weight_tons: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description=(
            "Gross vehicle weight in metric tons. Required when "
            "is_heavy_goods_vehicle is True; used to compute "
            "₹1,000 × GVW (tons) × months_owned. "
            "Ignored (and may be None) for light goods vehicles."
        ),
    )
    months_owned: int = Field(
        ge=1,
        le=12,
        description=(
            "Number of months (or part-months, each counted as a full month) "
            "during which the vehicle was owned in the previous year "
            "(Section 44AE(2)). Must be between 1 and 12."
        ),
    )
    income_declared: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description=(
            "Actual income declared for this vehicle if higher than the "
            "statutory presumptive amount (Section 44AE(1) proviso). "
            "If None, the engine computes income at the statutory rate."
        ),
    )


class PresumptiveGoodsCarriage44AE(BaseModel):
    """
    Input data for computing presumptive income from goods carriage under
    Section 44AE.

    Eligible assessees: resident individuals, HUFs, and firms (not LLPs)
    engaged in the business of plying, hiring, or leasing goods carriages,
    provided they did NOT own more than 10 goods carriages at any time
    during the previous year (Section 44AE(1) proviso).

    Total presumptive income = sum of per-vehicle income across all vehicles.
    The 10-vehicle limit is enforced by the computation engine (not the schema).

    Relevant IT Act section: Section 44AE.
    """

    vehicles: List[GoodsCarriageVehicle] = Field(
        min_length=1,
        description=(
            "List of goods carriage vehicles owned during the previous year. "
            "Each entry represents one vehicle with its type, GVW (if heavy), "
            "months owned, and any higher-declared income. Maximum 10 vehicles "
            "is a statutory limit enforced by the computation engine."
        ),
    )


# ---------------------------------------------------------------------------
# Schedule BP — Balance Sheet Financial Particulars
# ---------------------------------------------------------------------------

class ScheduleBPFinancial(BaseModel):
    """Financial particulars from Schedule BP for cross-consistency checks (CBDT Sl 3-4, 139)."""
    # Capital & Liabilities
    partners_capital: Decimal = Field(default=Decimal("0"), ge=0)
    secured_loans: Decimal = Field(default=Decimal("0"), ge=0)
    unsecured_loans: Decimal = Field(default=Decimal("0"), ge=0)
    advances_received: Decimal = Field(default=Decimal("0"), ge=0)
    sundry_creditors: Decimal = Field(default=Decimal("0"), ge=0)
    other_liabilities: Decimal = Field(default=Decimal("0"), ge=0)
    total_capital_liabilities: Decimal = Field(default=Decimal("0"), ge=0)

    # Assets
    fixed_assets: Decimal = Field(default=Decimal("0"), ge=0)
    investments_bp: Decimal = Field(default=Decimal("0"), ge=0)
    inventories: Decimal = Field(default=Decimal("0"), ge=0)
    sundry_debtors: Decimal = Field(default=Decimal("0"), ge=0)
    bank_balance: Decimal = Field(default=Decimal("0"), ge=0)
    cash_in_hand: Decimal = Field(default=Decimal("0"), ge=0)
    loans_and_advances_given: Decimal = Field(default=Decimal("0"), ge=0)
    other_assets: Decimal = Field(default=Decimal("0"), ge=0)
    total_assets: Decimal = Field(default=Decimal("0"), ge=0)

    # Partnership details for 44AE
    salary_to_partners: Decimal = Field(default=Decimal("0"), ge=0, description="Salary paid to partners (44AE firms)")
    interest_to_partners: Decimal = Field(default=Decimal("0"), ge=0, description="Interest paid to partners (44AE firms)")


# ---------------------------------------------------------------------------
# ITR-4-specific filing profile, address, bank, property, TRP types
# ---------------------------------------------------------------------------

class ITR4AssesseeStatus(str, Enum):
    """ITR-4 PersonalInfo.Status — assessee entity type.

    I : Individual; H : HUF; F : Firm (other than LLP).
    """
    INDIVIDUAL = "I"
    HUF = "H"
    FIRM = "F"


class ITR4PostalAddress(BaseModel):
    """Postal address used by the ITR-4 AlternateAddress block."""
    residence_no: str = Field(default="", max_length=50)
    residence_name: str = Field(default="", max_length=50)
    road_or_street: str = Field(default="", max_length=50)
    locality_or_area: str = Field(default="", max_length=50)
    city_or_town_or_district: str = Field(default="", max_length=50)
    state_code: str = Field(default="", max_length=2)
    country_code: str = Field(default="91", max_length=5)
    pin_code: Optional[str] = Field(default=None, max_length=6)
    zip_code: str = Field(default="", max_length=10)


class ITR4FilingAddress(ITR4PostalAddress):
    """Primary filing address with mandatory contact details (Phone + Mobile)."""
    mobile_country_code: int = Field(ge=1, le=99999)
    mobile_no: str = Field(min_length=1, max_length=10)
    email: str = Field(min_length=1, max_length=125)
    secondary_mobile_country_code: int = Field(default=0, ge=0, le=99999)
    secondary_mobile_no: Optional[str] = Field(default=None, max_length=10)
    secondary_email: Optional[str] = Field(default=None, max_length=125)
    # Landline (Address.Phone in the CBDT schema) — optional, defaults to "0".
    landline_std_code: int = Field(default=0, ge=0, le=99999)
    landline_phone_no: str = Field(default="0", max_length=12)


class ITR4PropertyProfile(BaseModel):
    """Address profile for the single ITR-4 house property."""
    address_detail: str = Field(min_length=1, max_length=50)
    city_or_town_or_district: str = Field(min_length=1, max_length=50)
    state_code: str = Field(min_length=1, max_length=2)
    country_code: str = Field(default="91", max_length=5)
    pin_code: Optional[str] = Field(default=None, max_length=6)
    zip_code: Optional[str] = Field(default=None, max_length=10)


class ITR4BankAccount(BaseModel):
    """Bank account disclosed for ITR-4 refund credit."""
    account_number: str = Field(min_length=1, max_length=20)
    ifsc_code: str = Field(min_length=11, max_length=11)
    bank_name: str = Field(min_length=1, max_length=125)
    account_type: str = Field(min_length=1, max_length=20)
    is_primary: bool = False


class ITR4TaxReturnPreparer(BaseModel):
    """ITR-4 Tax Return Preparer details, when a TRP prepares the return."""
    identification_number: str = Field(pattern=r"^(T[0-9]{9}|[0-9]{6})$")
    name: str = Field(min_length=1, max_length=125)
    reimbursement_from_government: Decimal = Field(default=Decimal("0"), ge=0)


class ITR4SeventhProvisoDetails(BaseModel):
    """Seventh-proviso to Section 139(1) declarations for ITR-4 FilingStatus."""
    foreign_travel_flag: bool = False
    foreign_travel_amount: Decimal = Field(default=Decimal("0"), ge=0)
    electricity_expenditure_flag: bool = False
    electricity_expenditure_amount: Decimal = Field(default=Decimal("0"), ge=0)
    other_clause_iv_flag: bool = False
    other_clause_iv_detail: str = Field(default="", max_length=125)


class ITR4FilingProfile(BaseModel):
    """ITR-4 taxpayer identity, filing status, and verification.

    Every field here maps to a real CBDT ITR-4 PersonalInfo, FilingStatus,
    or Verification destination. No entered statutory field is silently
    replaced with a default during JSON generation.
    """
    pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    first_name: str = Field(default="", max_length=25)
    middle_name: str = Field(default="", max_length=25)
    surname: str = Field(min_length=1, max_length=75)
    date_of_birth: date
    employer_category: str = Field(
        default="OTH",
        pattern=r"^(CGOV|SGOV|PSU|PE|PESG|PEPS|PEO|OTH|NA)$",
    )
    aadhaar_number: Optional[str] = Field(default=None, pattern=r"^[0-9]{12}$")
    assessee_status: ITR4AssesseeStatus = Field(default=ITR4AssesseeStatus.INDIVIDUAL)
    primary_address: ITR4FilingAddress
    alternate_address: Optional[ITR4PostalAddress] = None
    father_name: str = Field(min_length=1, max_length=125)
    verification_place: str = Field(min_length=1, max_length=50)
    verification_capacity: Literal["S"] = "S"
    return_file_section: Literal[11, 12, 13, 14, 16, 17, 18, 20] = 11
    seventh_proviso: ITR4SeventhProvisoDetails = Field(default_factory=ITR4SeventhProvisoDetails)
    # Form 10-IEA cascade (ITR-4 uses this, not OptOutNewTaxRegime).
    form_10iea_earlier_ay_old_regime: str = Field(default="NA", pattern=r"^(NA|Y|N)$")
    form_10iea_ass_year: str = Field(default="", pattern=r"^(2024-25|2025-26)?$")
    form_10iea_earlier_ay_ack_old_regime: int = Field(default=0, ge=0)
    f10iea_earlier_ay_new_regime: str = Field(default="N", pattern=r"^(Y|N)$")
    ass_yr_f10iea_new_tax_reg: str = Field(default="", pattern=r"^(2024-25|2025-26)?$")
    form_10iea_earlier_ay_ack_new_regime: int = Field(default=0, ge=0)
    f10iea_curr_ay_new_regime: str = Field(default="N", pattern=r"^(Y|N)$")
    f10iea_date_curr_ay_new_tax: str = Field(default="", max_length=10)
    f10iea_ack_no_curr_ay_new_tax: int = Field(default=0, ge=0)
    f10iea_curr_ay_old_regime: str = Field(default="N", pattern=r"^(Y|N)$")
    f10iea_date_curr_ay_old_tax: str = Field(default="", max_length=10)
    f10iea_ack_no_curr_ay_old_tax: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Top-level ITR-4 input model
# ---------------------------------------------------------------------------


class ITR4Input(BaseModel):
    """
    Top-level input model for computing an ITR-4 (Sugam) return.

    Combines assessee meta-information (age bracket, regime), the active
    presumptive scheme with its specific income data, and the shared income /
    deduction models from ITR-1 (salary, house property, other sources,
    Chapter VI-A deductions).

    Exactly one of {business_income_44ad, professional_income_44ada,
    goods_carriage_44ae} must be non-None when presumptive_scheme is not NONE.
    The computation engine must enforce this constraint; the schema does not,
    to keep validation simple and error messages explicit.

    Relevant IT Act parts: Sections 44AD, 44ADA, 44AE, and the parts shared
    with ITR-1 (Sections 15–24, Chapter VI-A).
    """

    age_bracket: AgeBracket = Field(
        description=(
            "Age of the assessee as on the last day of the previous year "
            "(31 March). Determines the basic exemption limit and tax slabs."
        ),
    )
    assessee_type: AssesseeType = Field(
        default=AssesseeType.INDIVIDUAL,
        description="Entity type of the assessee. ITR-4 is for individuals, HUFs, and firms (other than LLPs).",
    )
    # --- ITR-4 eligibility gate fields ---
    is_resident: bool = Field(default=True, description="True if assessee is a resident. ITR-4 requires resident status.")
    is_director: bool = Field(default=False, description="True if assessee is a director in any company (disqualifies ITR-4).")
    has_foreign_assets: bool = Field(default=False, description="True if assessee holds foreign assets/income (disqualifies ITR-4).")
    has_unlisted_equity: bool = Field(default=False, description="True if assessee holds unlisted equity shares (disqualifies ITR-4).")
    house_property_count: int = Field(default=1, ge=1, description="Number of house properties. ITR-4 allows at most 1.")

    tax_regime: TaxRegime = Field(
        description=(
            "Tax regime elected. 'old' allows Chapter VI-A deductions; "
            "'new' uses Section 115BAC concessional rates. Note: ITR-4 filers "
            "under the new regime cannot opt out of 115BAC mid-year."
        ),
    )
    presumptive_scheme: PresumptiveScheme = Field(
        description=(
            "Which presumptive scheme the assessee has opted for. "
            "Determines which of the three presumptive sub-models is active "
            "and which statutory rates apply."
        ),
    )

    # --- Presumptive income sub-models (at most one must be non-None) ---

    business_income_44ad: Optional[PresumptiveBusinessIncome44AD] = Field(
        default=None,
        description=(
            "Populate when presumptive_scheme == '44AD'. "
            "Must be None for all other schemes."
        ),
    )
    professional_income_44ada: Optional[PresumptiveProfessionalIncome44ADA] = Field(
        default=None,
        description=(
            "Populate when presumptive_scheme == '44ADA'. "
            "Must be None for all other schemes."
        ),
    )
    goods_carriage_44ae: Optional[PresumptiveGoodsCarriage44AE] = Field(
        default=None,
        description=(
            "Populate when presumptive_scheme == '44AE'. "
            "Must be None for all other schemes."
        ),
    )

    # --- Shared income / deduction models (same as ITR-1) ---

    salary_income: Optional[SalaryIncome] = Field(
        default=None,
        description=(
            "Salary or pension income, if any. ITR-4 permits salary income "
            "alongside presumptive business income (Section 44AD/ADA/AE)."
        ),
    )
    house_property_income: Optional[HousePropertyIncome] = Field(
        default=None,
        description=(
            "Single house property income or loss. ITR-4 allows one house "
            "property, same as ITR-1."
        ),
    )
    other_sources_income: Optional[OtherSourcesIncome] = Field(
        default=None,
        description=(
            "Interest, family pension, and other sources income, if any."
        ),
    )
    deductions_chapter6a: Optional[Chapter6ADeductions] = Field(
        default=None,
        description=(
            "Chapter VI-A deductions (80C, 80D, 80E, etc.). Ignored by the "
            "computation engine when tax_regime is 'new', except 80CCD(2)."
        ),
    )
    capital_gains: Optional[CapitalGainsIncome] = Field(
        default=None,
        description=(
            "Long-term capital gains under Section 112A only. As per CBDT "
            "notification, ITR-4 allows LTCG u/s 112A up to ₹1,25,000. "
            "The computation engine will reject inputs exceeding this limit. "
            "No other capital gains (STCG, VDA, LTCG other than 112A) are "
            "permitted in ITR-4."
        ),
    )
    cg_transactions: Optional[list] = Field(
        default=None,
        description=(
            "Canonical capital-gain transaction rows (the same typed "
            "CGTransaction shape used by ITR-2). When provided, the ITR-4 "
            "calculator runs the standalone CG schedule and projects the "
            "restricted-112A aggregate view, surfacing losses-forfeited and "
            "other-CG-disallowed for form-eligibility guidance. This does "
            "NOT widen ITR-4 eligibility — only restricted 112A LTCG within "
            "₹1.25 lakh is reportable; any other CG forces ITR-3."
        ),
    )
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

    # --- Extended schema fields for detailed validations ---
    agriculture_income: Decimal = Field(default=Decimal("0"), ge=0, description="Agricultural income shown as exempt")
    exempt_income_breakdown: dict[str, Decimal] = Field(default_factory=dict, description="Breakdown of exempt income by category")
    exempt_income_dropdowns: list[str] = Field(default_factory=list, description="Selected exempt income dropdown categories for uniqueness check")
    schedule_80d: Optional[Schedule80D] = Field(default=None, description="Schedule 80D health insurance details")
    schedule_80g: Optional[Schedule80G] = Field(default=None, description="Schedule 80G donation details")
    schedule_80gga: Optional[Schedule80GGA] = Field(default=None, description="Schedule 80GGA scientific research donations")
    schedule_80ggc: Optional[Schedule80GGC] = Field(default=None, description="Schedule 80GGC political contributions")
    schedule_80dd: Optional[Schedule80DD] = Field(default=None, description="Schedule 80DD: dependent disability deduction details (CBDT Sl 248-252)")
    schedule_80u: Optional[Schedule80U] = Field(default=None, description="Schedule 80U: self disability deduction details (CBDT Sl 249-253)")
    schedule_80c_entries: List[Schedule80CEntry] = Field(default_factory=list, description="Per-row entries for Schedule 80C (CBDT Sl 273, 290)")
    schedule_80ccc_entries: List[Schedule80CCCEntry] = Field(default_factory=list, description="Per-row entries for Schedule 80CCC (CBDT Sl 366, 409)")
    schedule_80e_entries: List[Schedule80EEntry] = Field(default_factory=list, description="Per-row entries for Schedule 80E (CBDT Sl 274, 291)")
    loan_details_80ee_list: List[Schedule80EELoanEntry] = Field(default_factory=list, description="Per-loan entries for Schedule 80EE (CBDT Sl 292, 298)")
    loan_details_80eea_list: List[Schedule80EEALoanEntry] = Field(default_factory=list, description="Per-loan entries for Schedule 80EEA (CBDT Sl 293, 299)")
    loan_details_80eeb_list: List[Schedule80EEBLoanEntry] = Field(default_factory=list, description="Per-loan entries for Schedule 80EEB (CBDT Sl 294, 300)")
    loan_details_24b_list: List[LoanDetail] = Field(default_factory=list, description="Per-loan entries for Schedule 24(b) (CBDT Sl 269, 295)")
    tax_payment_entries: List[TaxPaymentDetail] = Field(default_factory=list, description="Per-installment entries for Schedule IT")
    hra_details: Optional[HRADetails] = Field(default=None, description="HRA computation breakdown")
    schedule_10_13a: Optional[HRADetails] = Field(default=None, description="Schedule 10(13A) HRA detailed breakdown (CBDT Sl 315, 320)")
    co_ownership_details: Optional[CoOwnershipDetails] = Field(default=None, description="Co-ownership details for house property")
    representative_details: Optional[RepresentativeDetails] = Field(default=None, description="Representative assessee details")
    secondary_address: Optional[SecondaryAddress] = Field(default=None, description="Secondary address for representative filing")
    form_10e_filed: bool = Field(default=False, description="Whether Form 10E (relief u/s 89) has been filed")
    form_10ia_filed: bool = Field(default=False, description="Whether Form 10-IA (80DD/80U certificate) has been filed")
    form_10ia_filed_80dd: bool = Field(default=False, description="Whether separate Form 10-IA filed for 80DD (CBDT Sl 287)")
    form_10ia_filed_80u: bool = Field(default=False, description="Whether separate Form 10-IA filed for 80U (CBDT Sl 287)")
    form_10ba_filed: bool = Field(default=False, description="Whether Form 10BA (80GG declaration) has been filed")
    pran_number: Optional[str] = Field(default=None, max_length=12, description="PRAN number for NPS contributions")
    nature_of_employment: Optional[str] = Field(default=None, description="Nature of employment: Central/State Govt, PSU, Private, Pensioner, etc.")
    # --- Loan details (single records, backward compat) ---
    loan_details_24b: Optional[LoanDetails] = Field(default=None, description="Loan details for 24(b) interest")
    loan_details_80ee: Optional[LoanDetails] = Field(default=None, description="Loan details for 80EE deduction")
    loan_details_80eea: Optional[LoanDetails] = Field(default=None, description="Loan details for 80EEA deduction")
    loan_details_80eeb: Optional[LoanDetails] = Field(default=None, description="Loan details for 80EEB deduction")
    # --- Filing ---
    filing_section: Optional[str] = Field(default=None, description="Filing section: 139(1), 139(4), 139(5), 142(1)")
    original_filing_section: Optional[str] = Field(default=None, description="Original filing section for revised returns")
    filing_date: Optional[date] = Field(default=None)
    due_date: Optional[date] = Field(default=None)
    relief_89: Decimal = Field(default=Decimal("0"), ge=0, description="Relief under section 89 (arrears of salary) as computed by Form 10E")
    form_10iea_filed: bool = Field(default=False, description="Whether Form 10-IEA (new regime exercise) has been filed")
    form_10iea_filing_date: Optional[date] = Field(default=None, description="Date Form 10-IEA was filed")
    form_10iea_ack_no: Optional[str] = Field(default=None, max_length=15, description="Acknowledgement number of Form 10-IEA")
    # --- Assessee identity ---
    assessee_pan: Optional[str] = Field(default=None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$", description="PAN of the assessee")
    assessee_name: Optional[str] = Field(default=None, max_length=125, description="Name of assessee as per PAN")
    aadhaar_number: Optional[str] = Field(default=None, min_length=12, max_length=12, description="Aadhaar number")
    assessee_email_primary: Optional[str] = Field(default=None, description="Primary email of assessee (CBDT Sl 403)")
    assessee_phone_primary: Optional[str] = Field(default=None, description="Primary phone of assessee (CBDT Sl 403)")
    representative_email: Optional[str] = Field(default=None, description="Email of representative (CBDT Sl 344)")
    representative_phone: Optional[str] = Field(default=None, description="Phone of representative (CBDT Sl 344)")
    # --- Other sources dropdowns ---
    other_sources_dropdowns: list[str] = Field(default_factory=list, description="Selected Other Sources income dropdown categories")
    other_sources_total: Optional[Decimal] = Field(default=None, ge=0, description="Total OS income for cross-foot")
    dividend_quarterly_breakdown: dict[str, Decimal] = Field(default_factory=dict, description="Quarterly breakup of dividend income")
    # --- Capital gains extended ---
    full_value_of_consideration: Optional[Decimal] = Field(default=None, ge=0, description="Full value of consideration for LTCG 112A")
    disease_category: Optional[str] = Field(default=None, max_length=125, description="Specified disease for 80DDB")
    date_of_incorporation: Optional[date] = Field(default=None, description="Date of incorporation/formation")
    agniveer_date_of_joining: Optional[date] = Field(default=None, description="Date of joining armed forces")
    is_property_co_owned: bool = Field(default=False, description="True if house property is co-owned")
    other_co_owner_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100, description="Other co-owner share %")
    total_taxes_paid: Optional[Decimal] = Field(default=None, ge=0, description="Total taxes paid")
    total_tds_claimed: Optional[Decimal] = Field(default=None, ge=0, description="Total TDS claimed")
    total_tcs_claimed: Optional[Decimal] = Field(default=None, ge=0, description="Total TCS claimed")
    schedule_it_total_paid: Optional[Decimal] = Field(default=None, ge=0, description="Schedule IT col 4 total")
    schedule_tds1_total: Optional[Decimal] = Field(default=None, ge=0, description="Schedule TDS1 col 5 total")
    schedule_tds2_total_claimed: Optional[Decimal] = Field(default=None, ge=0, description="Schedule TDS2 col 6 total")
    schedule_tds3_total_claimed: Optional[Decimal] = Field(default=None, ge=0, description="Schedule TDS3 col 7 total")
    schedule_tcs_total_claimed: Optional[Decimal] = Field(default=None, ge=0, description="Schedule TCS col 6 total")
    tds3_entries: Optional[List[TDS3Entry]] = Field(default=None, description="TDS3 entries")
    # --- A23 Form 10-IEA complex fields ---
    has_filed_10iea_earlier: Optional[bool] = Field(default=None, description="A23: Filed Form 10-IEA in earlier AY")
    has_reentered_new_regime: Optional[bool] = Field(default=None, description="A23(A)(ii): Re-entered new regime via 10-IEA")
    has_filed_10iea_current: Optional[bool] = Field(default=None, description="A23(B): Filed 10-IEA current AY")
    a23_earlier_ay: Optional[int] = Field(default=None, ge=2020, le=2026, description="A23(A)(i): AY when first 10-IEA filed")
    a23_reenter_ay: Optional[int] = Field(default=None, ge=2020, le=2026, description="A23(A)(ii)(a): AY when re-entered new regime")
    is_148_proceeding: bool = Field(default=False, description="True if proceeding u/s 148 initiated")
    original_acknowledgement_no: Optional[str] = Field(default=None, max_length=15, description="Acknowledgement no of original return")
    total_exempt_income: Optional[Decimal] = Field(default=None, ge=0, description="Total exempt income for cross-foot")
    has_salary_income: bool = Field(default=True, description="Whether taxpayer has salary income")
    # --- Schedule BP Financial ---
    schedule_bp_financial: Optional[ScheduleBPFinancial] = Field(default=None, description="Schedule BP financial particulars for cross-consistency")
    # --- Business/Professional code dropdowns ---
    business_code: Optional[str] = Field(default=None, description="Business code for 44AD/44AE")
    profession_code: Optional[str] = Field(default=None, description="Profession code for 44ADA")
    # --- Vehicle registration (44AE) ---
    vehicle_registration_numbers: list[str] = Field(default_factory=list, description="Vehicle registration numbers for 44AE duplicate check")
    # --- ITR-4-specific filing profile, bank accounts, TRP ---
    filing_profile: Optional[ITR4FilingProfile] = Field(
        default=None,
        description=(
            "Taxpayer identity, filing status, and verification details. "
            "Required for official ITR-4 JSON generation — maps to "
            "PersonalInfo, FilingStatus, and Verification nodes."
        ),
    )
    property_profile: Optional[ITR4PropertyProfile] = Field(
        default=None,
        description=(
            "Address profile for the single house property allowed in ITR-4. "
            "Maps to PropertyDetails[].AddressDetailWithZipCode in the ITD JSON."
        ),
    )
    bank_accounts: List[ITR4BankAccount] = Field(
        default_factory=list,
        description="Bank accounts for refund credit. Exactly one must be marked is_primary.",
    )
    tax_return_preparer: Optional[ITR4TaxReturnPreparer] = Field(
        default=None,
        description="Tax Return Preparer details, when a TRP prepares the return.",
    )
