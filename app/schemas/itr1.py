"""
ITR-1 input schemas.

ITR-1 is applicable to resident individuals whose total income does not exceed
₹50 lakh and who have income from:
  - Salary / Pension
  - One house property (self-occupied, let-out, or deemed let-out)
  - Other sources (interest, family pension, dividend, etc.)
  - Long-term capital gains under Section 112A ONLY, not exceeding ₹1.25 lakh
    (Finance Act 2024, effective AY 2025-26 onwards)

Disqualifiers (must use ITR-2 or ITR-3 instead):
  - LTCG u/s 112A exceeding ₹1.25 lakh
  - Any short-term capital gains
  - Any other capital gains (112, 111A, etc.)
  - Business or professional income
  - More than one house property
  - Brought-forward or carry-forward losses
"""

from decimal import Decimal
from enum import Enum
from typing import List, Optional
from datetime import date

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AgeBracket(str, Enum):
    """
    Age bracket of the assessee as on the last day of the previous year.

    Determines the basic exemption limit under the old tax regime
    (IT Act Section 87A and the applicable slab structure).
    """

    BELOW_60 = "below_60"    # General individual: < 60 years
    SIXTY_TO_80 = "60_to_80"  # Senior citizen: 60 ≤ age < 80
    ABOVE_80 = "above_80"    # Super senior citizen: age ≥ 80


class TaxRegime(str, Enum):
    """
    Tax regime elected by the assessee for the assessment year.

    - OLD: uses slab rates with deductions/exemptions (Chapter VI-A, HRA, etc.)
    - NEW: concessional flat slab rates; most deductions not available
      (IT Act Section 115BAC).
    """

    OLD = "old"
    NEW = "new"


# ---------------------------------------------------------------------------
# Component income / deduction models
# ---------------------------------------------------------------------------


class SalaryIncome(BaseModel):
    """
    Represents income chargeable under the head 'Salaries'.

    Covers gross salary received from employer(s), exempt allowances that
    reduce the taxable salary figure, professional tax paid (which is allowed
    as a deduction under Section 16(iii)), and the standard deduction under
    Section 16(ia) — ₹50,000 under the old regime, ₹75,000 under the new
    regime (Finance Act 2024, effective AY 2025-26 onwards).

    Relevant IT Act sections: Section 15, 16, 10(13A) [HRA], 10(5) [LTA].
    """

    gross_salary: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Salary received from employer(s) before any deduction, "
            "(Section 17(1))."
        ),
    )
    perquisites_value: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Value of perquisites under Section 17(2)",
    )
    profits_in_lieu_of_salary: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Profits in lieu of salary under Section 17(3)",
    )
    hra_exempt_amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Exempt portion of House Rent Allowance computed as the least of "
            "the three conditions under Section 10(13A). Zero if not in a "
            "rented accommodation or HRA not received."
        ),
    )
    lta_exempt_amount: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Exempt Leave Travel Allowance for journeys actually performed "
            "within India (Section 10(5)). Not available under the new regime "
            "(Section 115BAC); caller must pass 0 for new regime."
        ),
    )
    standard_deduction_claimed: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Standard deduction claimed under Section 16(ia). "
            "₹50,000 under the old regime; ₹75,000 under the new regime "
            "(Finance Act 2024, AY 2025-26 onwards). Pass 0 only if the "
            "assessee has no salary or pension income."
        ),
    )
    entertainment_allowance: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Entertainment allowance deduction under Section 16(ii). "
            "Applicable only for government employees under the old regime. "
            "Statutory cap is ₹5,000."
        ),
    )
    professional_tax_paid: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Professional / employment tax paid to the state government "
            "during the year, deductible under Section 16(iii). "
            "Not available under the new regime (Section 115BAC). "
            "Maximum ₹2,500 per year is typically levied by state acts."
        ),
    )
    is_government_employee: bool = Field(
        default=False,
        description="True if the employee is a Government employee (Central/State/PSU). Required for entertainment allowance deduction u/s 16(ii).",
    )



class PropertyType(str, Enum):
    """
    Type of house property as recognised by the ITR-1 schedule.

    Determines annual value computation and interest deduction ceiling
    (IT Act Sections 22, 23, 24).
    """

    SELF_OCCUPIED = "S"      # Annual value nil; interest cap ₹2,00,000 u/s 24(b)
    LET_OUT = "L"            # Gross rent taxable; 30% standard deduction u/s 24(a)
    DEEMED_LET_OUT = "D"     # Treated as let-out when owner has another self-occupied property


class HousePropertyIncome(BaseModel):
    """
    Represents income (or loss) chargeable under 'Income from House Property'.

    ITR-1 allows exactly ONE house property. It can be self-occupied (S),
    let-out (L), or deemed let-out (D). For S: annual value is nil and home
    loan interest is capped at ₹2,00,000 under Section 24(b). For L/D: Net
    Annual Value = gross rent – municipal taxes; 30% standard deduction
    applies under Section 24(a); home loan interest has no ceiling.

    Under the new regime (Section 115BAC), interest deduction is allowed only
    for let-out/deemed-let-out property; self-occupied gets nil. The
    computation engine enforces this; the schema captures raw inputs.

    Relevant IT Act sections: Section 22, 23, 24.
    """

    property_type: PropertyType = Field(
        description=(
            "Type of house property: S (self-occupied), L (let-out), or "
            "D (deemed let-out). Determines annual value and interest cap "
            "under Sections 23 and 24."
        ),
    )
    annual_rent_received: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Gross annual rent received or receivable during the year "
            "(Section 23(1)(a)). Must be 0 if property_type is S."
        ),
    )
    municipal_taxes_paid: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Municipal / local body taxes actually paid by the owner during "
            "the year (Section 23(1)(b)). Deducted from gross rent to arrive "
            "at Net Annual Value. 0 for self-occupied property."
        ),
    )
    home_loan_interest_paid: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Interest on capital borrowed for acquisition, construction, "
            "repair, or reconstruction of the property (Section 24(b)). "
            "For self-occupied property the computation engine will cap this "
            "at ₹2,00,000 (or ₹30,000 for loans sanctioned before 01-04-1999)."
        ),
    )
    arrears_unrealised_rent_received: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Arrears of rent or unrealised rent received during the year "
            "that was not charged to tax in any earlier year (Section 25A(1)). "
            "The computation engine will reduce this by 30% and add the net "
            "amount back to house property income."
        ),
    )


class OtherSourcesIncome(BaseModel):
    """
    Represents income chargeable under 'Income from Other Sources'.

    For ITR-1 filers this head covers interest income, family pension, and
    dividend income (reportable in ITR-1 Schedule OS as of AY 2022-23 onwards).
    Winnings from lotteries/games (taxed at special rates) are outside ITR-1
    scope and are intentionally omitted.

    Relevant IT Act sections: Section 56, 57.
    """

    savings_bank_interest: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Interest credited to savings bank accounts during the year "
            "(Section 56(2)). Eligible for deduction under Section 80TTA "
            "(up to ₹10,000) or 80TTB (for senior citizens, up to ₹50,000)."
        ),
    )
    fixed_deposit_interest: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Interest earned on fixed deposits, recurring deposits, and "
            "other bank/post-office deposits (Section 56(2)). "
            "Fully taxable; no deduction under 80TTA applies to FD interest."
        ),
    )
    family_pension_received: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Family pension received by a nominee / legal heir of a deceased "
            "government or private-sector employee (Section 57(iia)). "
            "Reported at gross value."
        ),
    )
    dividend_income: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Dividend income taxable under other sources.",
    )


class Donation80G(BaseModel):
    """
    Represents an individual donation entry for Section 80G deduction.
    """
    cash_amount: Decimal = Field(default=Decimal("0"), ge=0, description="Amount donated in cash.")
    non_cash_amount: Decimal = Field(default=Decimal("0"), ge=0, description="Amount donated via bank/cheque/digital modes.")
    qualifying_percentage: str = Field(default="100%", description="Percentage of deduction allowed: '50%' or '100%'.")
    limit_on_deduction: str = Field(default="without limit", description="Whether subject to 10% adjusted GTI limit: 'with limit' or 'without limit'.")


class Chapter6ADeductions(BaseModel):
    """
    Represents deductions claimable under Chapter VI-A of the IT Act.

    Only deductions relevant to a salaried ITR-1 filer are included.
    Deductions under sections such as 80G (donations), 80GGA, 80RRB, etc.
    that are less commonly claimed by pure salaried filers are excluded from
    this schema to keep it minimal.

    80TTA vs 80TTB (mutually exclusive):
      - 80TTA: for assessees BELOW 60 years; only savings bank interest;
        capped at ₹10,000.
      - 80TTB: for SENIOR CITIZENS (age ≥ 60); covers savings bank + FD +
        recurring deposit interest; capped at ₹50,000.
    Caller must populate exactly one of the two fields (the other should be 0).
    The computation engine will enforce mutual exclusivity based on age_bracket.

    Note: Chapter VI-A deductions are NOT available under the new tax regime
    (Section 115BAC), except 80CCD(2) and 80CCH. The computation engine enforces this;
    the schema accepts the values regardless.

    Relevant IT Act sections: 80C, 80CCC, 80CCD(1), 80CCD(1B), 80D, 80TTA, 80TTB, 80E.
    """

    amount_80c: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Aggregate of investments/payments qualifying under Section 80C "
            "(e.g., PPF, ELSS, LIC premium, EPF, tuition fees, home loan "
            "principal). Share combined ₹1,50,000 limit u/s 80CCE with 80CCC/80CCD(1)."
        ),
    )
    amount_80ccc: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Premium paid for annuity plans of LIC or other insurers u/s 80CCC. Shares ₹1,50,000 u/s 80CCE.",
    )
    amount_80ccd1: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Employee contribution to NPS under Section 80CCD(1). Shares ₹1,50,000 u/s 80CCE.",
    )
    amount_80ccd1b: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Additional employee contribution to NPS (National Pension System) "
            "over and above 80C, deductible under Section 80CCD(1B). "
            "Capped at ₹50,000 by the computation engine."
        ),
    )
    amount_80d_self_family: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Medical insurance premium paid for self, spouse, and dependent "
            "children (Section 80D). Capped at ₹25,000 (₹50,000 if the "
            "insured is a senior citizen) by the computation engine."
        ),
    )
    amount_80d_parents: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Medical insurance premium paid for parents (Section 80D). "
            "Capped at ₹25,000 (₹50,000 if parents are senior citizens) "
            "by the computation engine."
        ),
    )
    amount_80tta: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Interest on savings bank accounts deductible under Section 80TTA. "
            "For assessees BELOW 60 years only. Statutory cap ₹10,000. "
            "Must be 0 for senior/super-senior citizens — use amount_80ttb."
        ),
    )
    amount_80ttb: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Interest on deposits (savings bank, FD, RD, post-office deposits) "
            "deductible under Section 80TTB. For SENIOR CITIZENS (age ≥ 60) "
            "only. Statutory cap ₹50,000 (Section 80TTB). Covers all deposit "
            "interest — unlike 80TTA which is limited to savings bank only. "
            "Must be 0 for assessees below 60 — use amount_80tta instead."
        ),
    )
    amount_80e: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Interest paid on education loan for higher studies for self, "
            "spouse, children, or a student for whom the assessee is legal "
            "guardian (Section 80E). No upper limit; allowed for up to "
            "8 assessment years from the year repayment begins."
        ),
    )
    amount_80ccd2: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Employer's contribution to NPS (Section 80CCD(2)). Allowed in both Old and New regimes.",
    )
    amount_80cch: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Contribution to Agniveer Corpus Fund (Section 80CCH). Allowed in both Old and New regimes.",
    )
    amount_80dd: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Medical treatment and maintenance of disabled dependent (Section 80DD).",
    )
    amount_80ddb: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Medical treatment of specified diseases (Section 80DDB).",
    )
    amount_80u: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Deduction in case of a person with disability (Section 80U).",
    )
    amount_80ee: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Interest on loan for residential house property for first-time home buyers (Section 80EE).",
    )
    amount_80eea: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Interest on loan for affordable housing (Section 80EEA).",
    )
    amount_80eeb: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Interest on loan for purchase of electric vehicle (Section 80EEB).",
    )
    amount_80g: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Donations to certain funds, charitable institutions, etc. (Section 80G). Simple fallback field.",
    )
    donations_80g: Optional[List[Donation80G]] = Field(
        default=None,
        description="List of individual Section 80G donation entries. Used for structured calculation u/s 80G.",
    )
    amount_80gg: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Rent paid when no HRA is received (Section 80GG).",
    )



# ---------------------------------------------------------------------------
# Capital gains (Section 112A only — Finance Act 2024 amendment)
# ---------------------------------------------------------------------------


class CapitalGainsIncome(BaseModel):
    """
    Represents the restricted capital-gains income permitted in ITR-1.

    Finance Act 2024 amended ITR-1 (Sahaj) to allow reporting of long-term
    capital gains (LTCG) under Section 112A — i.e., gains from the sale of
    listed equity shares, units of equity-oriented mutual funds, or units of
    business trusts — provided the total LTCG does NOT exceed ₹1.25 lakh
    for the assessment year (AY 2025-26 onwards).

    If LTCG exceeds ₹1.25 lakh, or if the assessee has any short-term capital
    gains or other capital gains, ITR-1 is not applicable and ITR-2 must be
    used instead. The computation engine must enforce this eligibility check.

    Short-term capital gains (Section 111A or otherwise) and all other capital
    gains categories remain outside ITR-1 scope and are intentionally absent.

    Relevant IT Act sections: Section 112A, Finance Act 2024 Schedule.
    """

    ltcg_112a: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Total long-term capital gains from listed equity shares, "
            "equity-oriented mutual funds, and units of business trusts "
            "(Section 112A). Taxed at 12.5% on the amount exceeding "
            "₹1.25 lakh (Finance Act 2024). If this value exceeds "
            "₹1,25,000 the assessee is ineligible for ITR-1 — the "
            "computation engine must raise an error in that case."
        ),
    )
    cost_of_acquisition: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Cost of acquisition (or deemed cost as per grandfathering "
            "rules for assets acquired before 31-01-2018) of the assets "
            "giving rise to LTCG u/s 112A. Required to compute the net "
            "gain reported in Schedule 112A of the ITR-1 form."
        ),
    )


# ---------------------------------------------------------------------------
# Top-level ITR-1 input model
# ---------------------------------------------------------------------------


class ITR1Input(BaseModel):
    """
    Top-level input model for computing an ITR-1 return.

    Combines assessee meta-information (age bracket, regime choice) with the
    four income/deduction component models. This is the single object the
    computation engine receives; it contains everything needed to produce
    gross total income, total income, and tax liability for an ITR-1 filer.

    Relevant IT Act parts: Part B of Schedule ITR-1 (Computation of income
    and tax), Finance Act applicable to the assessment year.
    """

    age_bracket: AgeBracket = Field(
        description=(
            "Age of the assessee as on the last day of the previous year "
            "(31 March). Determines the basic exemption limit and slab "
            "structure under the old regime."
        ),
    )
    tax_regime: TaxRegime = Field(
        description=(
            "Tax regime elected by the assessee. 'old' allows exemptions and "
            "Chapter VI-A deductions; 'new' uses Section 115BAC concessional "
            "rates and disallows most deductions."
        ),
    )
    salary_income: SalaryIncome = Field(
        description="Details of salary and allowances received during the year.",
    )
    house_property_income: HousePropertyIncome = Field(
        description=(
            "Details of the single house property owned by the assessee. "
            "ITR-1 does not permit more than one property."
        ),
    )
    other_sources_income: OtherSourcesIncome = Field(
        description=(
            "Interest income and family pension receivable under the head "
            "'Income from Other Sources'."
        ),
    )
    deductions_chapter6a: Chapter6ADeductions = Field(
        description=(
            "Deductions claimed under Chapter VI-A. The computation engine "
            "will ignore these fields (except 80CCD(2)) when tax_regime "
            "is 'new'."
        ),
    )
    capital_gains: Optional[CapitalGainsIncome] = Field(
        default=None,
        description=(
            "Long-term capital gains under Section 112A only (Finance Act "
            "2024). Omit or set to None if the assessee has no capital gains. "
            "The computation engine must reject this input if ltcg_112a "
            "exceeds ₹1,25,000, as such assessees must file ITR-2."
        ),
    )
    # --- TDS/TCS ---
    tds1_entries: Optional[List["TDS1Entry"]] = Field(
        default=None,
        description="TDS on salary (Form 16 entries).",
    )
    tds2_entries: Optional[List["TDS2Entry"]] = Field(
        default=None,
        description="TDS on income other than salary.",
    )
    tcs_entries: Optional[List["TCSEntry"]] = Field(
        default=None,
        description="Tax collected at source.",
    )
    # --- Tax payments ---
    advance_tax_paid: Decimal = Field(default=Decimal("0"), ge=0)
    self_assessment_tax_paid: Decimal = Field(default=Decimal("0"), ge=0)
    # --- Filing dates ---
    filing_date: Optional[date] = Field(default=None)
    due_date: Optional[date] = Field(default=None)


# ---------------------------------------------------------------------------
# TDS / TCS entry models (shared across ITR forms)
# ---------------------------------------------------------------------------


class TDS1Entry(BaseModel):
    employer_tan: Optional[str] = Field(default=None, pattern=r"^[A-Z]{4}[0-9]{5}[A-Z]$")
    employer_name: Optional[str] = Field(default=None, max_length=125)
    income_chargeable: Decimal = Field(default=Decimal("0"), ge=0)
    tds_deducted: Decimal = Field(default=Decimal("0"), ge=0)


class TDS2Entry(BaseModel):
    deductor_tan: str = Field(..., pattern=r"^[A-Z]{4}[0-9]{5}[A-Z]$")
    deductor_name: Optional[str] = Field(default=None, max_length=125)
    tds_section: str = Field(...)
    gross_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tds_deducted: Decimal = Field(default=Decimal("0"), ge=0)


class TCSEntry(BaseModel):
    collector_tan: str = Field(..., pattern=r"^[A-Z]{4}[0-9]{5}[A-Z]$")
    collector_name: Optional[str] = Field(default=None)
    tcs_section: str = Field(...)
    gross_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tcs_collected: Decimal = Field(default=Decimal("0"), ge=0)
