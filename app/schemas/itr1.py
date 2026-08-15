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
from typing import List, Literal, Optional
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.capital_gains import Section112ATransaction


OFFICIAL_COUNTRY_CODES = frozenset(
    "93 1001 355 213 684 376 244 1264 1010 1268 54 374 297 61 43 994 1242 "
    "973 880 1246 375 32 501 229 1441 975 591 1002 387 267 1003 55 1014 673 "
    "359 226 257 238 855 237 1 1345 236 235 56 86 9 672 57 270 242 243 682 "
    "506 225 385 53 1015 357 420 45 253 1767 1809 593 20 503 240 291 372 "
    "251 500 298 679 358 33 594 689 1004 241 220 995 49 233 350 30 299 1473 "
    "590 1671 502 1481 224 245 592 509 1005 6 504 852 36 354 91 62 98 964 "
    "353 1624 972 5 1876 81 1534 962 7 254 686 850 82 965 996 856 371 961 "
    "266 231 218 423 370 352 853 389 261 265 60 960 223 356 692 596 222 230 "
    "269 52 691 373 377 976 382 1664 212 258 95 264 674 977 31 687 64 505 "
    "227 234 683 15 1670 47 968 92 680 970 507 675 595 51 63 1011 48 14 "
    "1787 974 262 40 8 250 1006 290 1869 1758 1007 508 1784 685 378 239 966 "
    "221 381 248 232 65 1721 421 386 677 252 28 1008 211 35 94 249 597 1012 "
    "268 46 41 963 886 992 255 66 670 228 690 676 1868 216 90 993 1649 688 "
    "256 380 971 44 2 1009 598 998 678 58 84 1284 1340 681 1013 967 260 263 "
    "9999".split()
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DisabilitySeverity(str, Enum):
    """Statutory disability severity used by Sections 80DD and 80U."""

    NORMAL = "normal"
    SEVERE = "severe"

    @property
    def itd_code(self) -> str:
        """Return the official ITD nature-of-disability code."""
        return "2" if self is DisabilitySeverity.SEVERE else "1"


class DisabilityCategory(str, Enum):
    """Official category of disability for Sections 80DD and 80U."""

    AUTISM_CEREBRAL_PALSY_OR_MULTIPLE = "specified"
    OTHER = "other"

    @property
    def itd_code(self) -> str:
        """Return the official ITD type-of-disability code."""
        return (
            "1"
            if self is DisabilityCategory.AUTISM_CEREBRAL_PALSY_OR_MULTIPLE
            else "2"
        )


class DependentRelationship(str, Enum):
    """Eligible dependent relationships for Section 80DD."""

    SPOUSE = "spouse"
    SON = "son"
    DAUGHTER = "daughter"
    FATHER = "father"
    MOTHER = "mother"
    BROTHER = "brother"
    SISTER = "sister"
    MEMBER_OF_HUF = "member_of_huf"

    @property
    def itd_code(self) -> str:
        """Return the explicit official ITD dependent-type code."""
        return {
            "spouse": "1",
            "son": "2",
            "daughter": "3",
            "father": "4",
            "mother": "5",
            "brother": "6",
            "sister": "7",
            "member_of_huf": "8",
        }[self.value]


class AgeBracket(str, Enum):
    """
    Age bracket of the assessee as on the last day of the previous year.

    Determines the basic exemption limit under the old tax regime
    (IT Act Section 87A and the applicable slab structure).
    """

    BELOW_60 = "below_60"    # General individual: < 60 years
    SIXTY_TO_80 = "60_to_80"  # Senior citizen: 60 ≤ age < 80
    ABOVE_80 = "above_80"    # Super senior citizen: age ≥ 80


class AssesseeType(str, Enum):
    """Entity type of the assessee filing the return."""
    INDIVIDUAL = "individual"
    HUF = "huf"
    FIRM = "firm"
    LLP = "llp"


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
    gratuity_received: Decimal = Field(default=Decimal("0"), ge=0)
    commuted_pension_received: Decimal = Field(default=Decimal("0"), ge=0)
    leave_encashment_received: Decimal = Field(default=Decimal("0"), ge=0)
    vrs_compensation: Decimal = Field(default=Decimal("0"), ge=0)
    retrenchment_compensation: Decimal = Field(default=Decimal("0"), ge=0)
    transport_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    lta_amount_received: Decimal = Field(default=Decimal("0"), ge=0)
    sec10_6_embassy_exempt: Decimal = Field(default=Decimal("0"), ge=0)
    sec10_7_foreign_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    sec10_10cc_perquisite_tax: Decimal = Field(default=Decimal("0"), ge=0)
    sec10_14i_prescribed_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    sec10_14ii_personal_allowance: Decimal = Field(default=Decimal("0"), ge=0)



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
    interest_on_it_refund: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Interest received on an income-tax refund.",
    )
    income_56_2_x: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Income u/s 56(2)(x) — inadequacy of consideration for "
        "property/money received without consideration.",
    )
    income_56_2_vib: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Income u/s 56(2)(vib) — consideration for transfer of "
        "immovable property less than stamp duty value.",
    )
    other_income: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Any other income chargeable under other sources.",
    )


class DonationAddress(BaseModel):
    """Official Indian address for a donation recipient."""

    address_line: str = Field(min_length=1, max_length=200)
    city_or_district: str = Field(min_length=1, max_length=50)
    state_code: str = Field(pattern=r"^(0[1-9]|[12][0-9]|3[0-7])$")
    pin_code: int = Field(ge=100000, le=999999)


class Donation80GCategory(str, Enum):
    """Canonical Section 80G category and official frontend wire value."""

    HUNDRED_WITHOUT_LIMIT = "100_NO_APPROVAL"
    FIFTY_WITHOUT_LIMIT = "50_NO_APPROVAL"
    HUNDRED_WITH_LIMIT = "100_APPROVAL_REQD"
    FIFTY_WITH_LIMIT = "50_APPROVAL_REQD"

    @property
    def qualifying_percentage(self) -> str:
        """Return the statutory qualifying percentage label."""
        return "100%" if self in {
            Donation80GCategory.HUNDRED_WITHOUT_LIMIT,
            Donation80GCategory.HUNDRED_WITH_LIMIT,
        } else "50%"

    @property
    def has_qualifying_limit(self) -> bool:
        """Return whether the category uses the shared adjusted-GTI limit."""
        return self in {
            Donation80GCategory.HUNDRED_WITH_LIMIT,
            Donation80GCategory.FIFTY_WITH_LIMIT,
        }


class Donation80G(BaseModel):
    """
    Represents an individual donation entry for Section 80G deduction.
    """
    cash_amount: Decimal = Field(default=Decimal("0"), ge=0, description="Amount donated in cash.")
    non_cash_amount: Decimal = Field(default=Decimal("0"), ge=0, description="Amount donated via bank/cheque/digital modes.")
    category: Optional[Donation80GCategory] = None
    qualifying_percentage: Literal["50%", "100%"] = Field(
        default="100%",
        description="Legacy percentage; use category.",
    )
    limit_on_deduction: Literal["with limit", "without limit"] = Field(
        default="without limit",
        description="Legacy limit label; use category.",
    )
    donee_name: Optional[str] = Field(default=None, min_length=1, max_length=125)
    donee_pan: Optional[str] = Field(default=None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    approval_reference_number: Optional[str] = Field(default=None, max_length=25)
    address: Optional[DonationAddress] = None
    donation_category: str = "A"
    ifsc_code: Optional[str] = Field(
        default=None,
        max_length=11,
        pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$",
    )
    transaction_ref: Optional[str] = Field(default=None, max_length=50)
    total_donation: Optional[Decimal] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_category_representations(self) -> "Donation80G":
        """Reject conflicting canonical and legacy category representations."""
        if self.category is None:
            return self
        expected_code = {
            Donation80GCategory.HUNDRED_WITHOUT_LIMIT: "A",
            Donation80GCategory.FIFTY_WITHOUT_LIMIT: "B",
            Donation80GCategory.HUNDRED_WITH_LIMIT: "C",
            Donation80GCategory.FIFTY_WITH_LIMIT: "D",
        }[self.category]
        legacy_is_default = (
            self.qualifying_percentage == "100%"
            and self.limit_on_deduction == "without limit"
            and self.donation_category == "A"
        )
        if not legacy_is_default and (
            self.qualifying_percentage != self.category.qualifying_percentage
            or (self.limit_on_deduction == "with limit")
            != self.category.has_qualifying_limit
            or self.donation_category != expected_code
        ):
            raise ValueError("Conflicting Section 80G category representations")
        self.qualifying_percentage = self.category.qualifying_percentage
        self.limit_on_deduction = (
            "with limit" if self.category.has_qualifying_limit else "without limit"
        )
        self.donation_category = expected_code
        return self


class Section80DDBUserType(str, Enum):
    """Official beneficiary category for Section 80DDB."""

    SELF_OR_DEPENDENT = "1"
    SELF_OR_DEPENDENT_SENIOR = "2"


class SpecifiedDisease80DDB(str, Enum):
    """Official Rule 11DD specified-disease codes for Section 80DDB."""

    DEMENTIA = "a"
    DYSTONIA_MUSCULORUM_DEFORMANS = "b"
    MOTOR_NEURON_DISEASE = "c"
    ATAXIA = "d"
    CHOREA = "e"
    HEMIBALLISMUS = "f"
    APHASIA = "g"
    PARKINSONS_DISEASE = "h"
    MALIGNANT_CANCERS = "i"
    AIDS = "j"
    CHRONIC_RENAL_FAILURE = "k"
    HEMATOLOGICAL_DISORDERS = "l"
    HEMOPHILIA = "m"
    THALASSAEMIA = "n"


class Section80DDBDetails(BaseModel):
    """Beneficiary, disease, and reimbursement details for Section 80DDB."""

    user_type: Section80DDBUserType
    disease: SpecifiedDisease80DDB
    reimbursement_amount: Decimal = Field(default=Decimal("0"), ge=0)


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
            "Capped at Rs 25,000 (Rs 50,000 if parents are senior citizens) "
            "by the computation engine."
        ),
    )
    amount_80d_preventive_self: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Preventive health check-up expenditure for self, spouse, and "
            "dependent children (Section 80D). Capped at Rs 5,000 and "
            "included within the self-family bucket limit."
        ),
    )
    amount_80d_preventive_parents: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description=(
            "Preventive health check-up expenditure for parents (Section 80D). "
            "Capped at Rs 5,000 and included within the parents bucket limit."
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
        description="Gross medical-treatment expenditure for a specified disease (Section 80DDB).",
    )
    details_80ddb: Optional[Section80DDBDetails] = Field(
        default=None,
        description="Official beneficiary category, disease code, and reimbursement details.",
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
    amount_80gga: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Donations for scientific research or rural development (Section 80GGA).",
    )
    amount_80ggc: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Contributions to political parties (Section 80GGC).",
    )
    amount_80ia: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Deduction for infrastructure development (Section 80-IA). ITR-3 only.",
    )
    amount_80ib: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Deduction for industrial undertakings (Section 80-IB). ITR-3 only.",
    )
    amount_80ic: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Deduction for undertakings in special category states (Section 80-IC). ITR-3 only.",
    )
    amount_10aa: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Deduction for SEZ units (Section 10AA). ITR-3 only.",
    )
    amount_80ra: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Deduction for research associations etc. (Section 80RA). ITR-3 only.",
    )

    has_parents_senior: bool = Field(
        default=False,
        description="Whether parents are senior citizens (affects 80D cap).",
    )
    schedule_80dd: Optional["Schedule80DD"] = Field(
        default=None,
        description="Structured schedule for 80DD deduction input.",
    )
    schedule_80u: Optional["Schedule80U"] = Field(
        default=None,
        description="Structured schedule for 80U deduction input.",
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
    full_value_of_consideration: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Aggregate sale consideration for Section 112A assets.",
    )
    transactions: Optional[List[Section112ATransaction]] = Field(
        default=None,
        description="Canonical transaction evidence for restricted Section 112A computation.",
    )

    @model_validator(mode="after")
    def derive_canonical_transaction_totals(self) -> "CapitalGainsIncome":
        """Validate canonical rows and project their aggregate into form fields."""
        if not self.transactions:
            return self
        from app.engine.schedules.restricted_112a import compute_restricted_112a

        raw_rows = [transaction.model_dump(mode="json") for transaction in self.transactions]
        portfolio = compute_restricted_112a(raw_rows)
        if portfolio.evidence_count:
            raise ValueError(
                "Imported capital-gains evidence must be matched and completed "
                "before generating an ITR-1/ITR-4 filing artifact"
            )
        if not portfolio.is_valid:
            codes = ", ".join(issue.code.value for issue in portfolio.issues)
            raise ValueError(f"Restricted Section 112A transactions are not eligible: {codes}")
        self.ltcg_112a = portfolio.gross_gain
        self.cost_of_acquisition = portfolio.cost_of_acquisition
        self.full_value_of_consideration = portfolio.full_value_of_consideration
        return self


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
        description="Primary house-property details retained for backward-compatible ITR-1 callers.",
    )
    house_properties: List[HousePropertyIncome] = Field(
        default_factory=list,
        max_length=2,
        description=(
            "Official AY 2026-27 ITR-1 PropertyDetails rows. The CBDT V1.1 "
            "schema permits at most two properties. When supplied, these rows "
            "replace the backward-compatible house_property_income field."
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
    cg_transactions: Optional[list] = Field(
        default=None,
        description=(
            "Canonical capital-gain transaction rows (the same typed "
            "CGTransaction shape used by ITR-2). When provided, the ITR-1 "
            "calculator runs the standalone CG schedule and projects the "
            "restricted-112A aggregate view, surfacing losses-forfeited and "
            "other-CG-disallowed for form-eligibility guidance. This does "
            "NOT widen ITR-1 eligibility — only restricted 112A LTCG within "
            "₹1.25 lakh is reportable; any other CG forces ITR-2/3."
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

    # --- ITR-1 eligibility gate fields ---
    assessee_type: AssesseeType = Field(default=AssesseeType.INDIVIDUAL, description="Entity type of the assessee. ITR-1 is only for individuals.")
    is_resident: bool = Field(default=True, description="True if assessee is a resident individual (ITR-1 is only for residents).")
    is_director: bool = Field(default=False, description="True if assessee is a director in any company (disqualifies ITR-1).")
    has_foreign_assets: bool = Field(default=False, description="True if assessee holds foreign assets or has foreign income (disqualifies ITR-1).")
    has_unlisted_equity: bool = Field(default=False, description="True if assessee holds unlisted equity shares (disqualifies ITR-1).")
    house_property_count: int = Field(default=1, ge=1, le=2, description="Number of house properties owned. Official AY 2026-27 ITR-1 permits at most 2.")

    # --- Quarterly advance tax ---
    advance_tax_q1: Optional[Decimal] = Field(default=None, ge=0, description="Advance tax paid by 15 June (Q1)")
    advance_tax_q2: Optional[Decimal] = Field(default=None, ge=0, description="Advance tax paid by 15 Sep (Q2)")
    advance_tax_q3: Optional[Decimal] = Field(default=None, ge=0, description="Advance tax paid by 15 Dec (Q3)")
    advance_tax_q4: Optional[Decimal] = Field(default=None, ge=0, description="Advance tax paid by 15 Mar (Q4)")

    # --- Relief and agricultural income ---
    relief_89: Decimal = Field(default=Decimal("0"), ge=0, description="Relief under section 89 (arrears of salary) as computed by Form 10E")
    agriculture_income: Decimal = Field(default=Decimal("0"), ge=0, description="Agricultural income shown as exempt")

    # --- Extended validation schedules and cross-foot totals ---
    nature_of_employment: Optional[str] = None
    filing_section: Optional[str] = None
    original_filing_section: Optional[str] = None
    form_10e_filed: bool = False
    form_10ia_filed: bool = False
    form_10ba_filed: bool = False
    pran_number: Optional[str] = Field(default=None, max_length=12)
    disease_category: Optional[str] = Field(
        default=None,
        max_length=125,
        deprecated=True,
        description="Deprecated: use deductions_chapter6a.details_80ddb.disease.",
    )
    agniveer_date_of_joining: Optional[date] = None
    date_of_incorporation: Optional[date] = None
    assessee_pan: Optional[str] = Field(default=None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    assessee_email_primary: Optional[str] = None
    assessee_phone_primary: Optional[str] = None
    representative_email: Optional[str] = None
    representative_phone: Optional[str] = None
    exempt_income_breakdown: dict[str, Decimal] = Field(default_factory=dict)
    exempt_income_dropdowns: list[str] = Field(default_factory=list)
    total_exempt_income: Optional[Decimal] = Field(default=None, ge=0)
    other_sources_dropdowns: list[str] = Field(default_factory=list)
    other_sources_total: Optional[Decimal] = Field(default=None, ge=0)
    dividend_quarterly_breakdown: dict[str, Decimal] = Field(default_factory=dict)
    full_value_of_consideration: Optional[Decimal] = Field(default=None, ge=0)
    schedule_80d: Optional["Schedule80D"] = None
    schedule_80g: Optional["Schedule80G"] = None
    schedule_80gga: Optional["Schedule80GGA"] = None
    schedule_80ggc: Optional["Schedule80GGC"] = None
    schedule_80dd: Optional["Schedule80DD"] = None
    schedule_80u: Optional["Schedule80U"] = None
    schedule_80c_entries: List["Schedule80CEntry"] = Field(default_factory=list)
    schedule_80ccc_entries: List["Schedule80CCCEntry"] = Field(default_factory=list)
    schedule_80e_entries: List["Schedule80EEntry"] = Field(default_factory=list)
    loan_details_80ee_list: List["ITR1Schedule80EELoanEntry"] = Field(default_factory=list)
    loan_details_80eea_list: List["ITR1Schedule80EEALoanEntry"] = Field(default_factory=list)
    loan_details_80eeb_list: List["ITR1Schedule80EEBLoanEntry"] = Field(default_factory=list)
    property_stamp_duty_value_80eea: Optional[Decimal] = Field(default=None, ge=0, le=4_500_000)
    loan_details_24b_list: List["LoanDetail"] = Field(default_factory=list)
    tax_payment_entries: List["TaxPaymentDetail"] = Field(default_factory=list)
    bank_accounts: List["BankAccount"] = Field(default_factory=list)
    hra_details: Optional["HRADetails"] = None
    schedule_10_13a: Optional["HRADetails"] = None
    loan_details_80ee: Optional["LoanDetails"] = None
    loan_details_80eea: Optional["LoanDetails"] = None
    loan_details_80eeb: Optional["LoanDetails"] = None
    is_property_co_owned: bool = False
    other_co_owner_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    co_ownership_details: Optional["CoOwnershipDetails"] = None
    representative_details: Optional["RepresentativeDetails"] = None
    secondary_address: Optional["SecondaryAddress"] = None
    tds3_entries: Optional[List["TDS3Entry"]] = None
    total_taxes_paid: Optional[Decimal] = Field(default=None, ge=0)
    total_tds_claimed: Optional[Decimal] = Field(default=None, ge=0)
    total_tcs_claimed: Optional[Decimal] = Field(default=None, ge=0)
    schedule_it_total_paid: Optional[Decimal] = Field(default=None, ge=0)
    schedule_tds1_total: Optional[Decimal] = Field(default=None, ge=0)
    schedule_tds2_total_claimed: Optional[Decimal] = Field(default=None, ge=0)
    schedule_tds3_total_claimed: Optional[Decimal] = Field(default=None, ge=0)
    schedule_tcs_total_claimed: Optional[Decimal] = Field(default=None, ge=0)
    filing_profile: Optional["ITR1FilingProfile"] = None
    property_profile: Optional["PropertyFilingProfile"] = None
    property_profiles: List["PropertyFilingProfile"] = Field(
        default_factory=list,
        max_length=2,
        description=(
            "Official AY 2026-27 ITR-1 PropertyDetails address/ownership "
            "profiles, one per row in ``house_properties``. When supplied, "
            "the i-th profile corresponds to the i-th house-property income "
            "row. A single ``property_profile`` remains supported for "
            "backward-compatible single-property callers."
        ),
    )
    tax_return_preparer: Optional["TaxReturnPreparer"] = None

    @model_validator(mode="after")
    def reconcile_house_property_rows(self) -> "ITR1Input":
        """Reconcile the single- and multi-property representations.

        The CBDT AY 2026-27 ITR-1 schema permits at most two
        ``PropertyDetails`` rows (V1.1 ``PropertyDetails.maxItems = 2``).
        Callers may supply either the legacy single-property fields
        (``house_property_income`` + ``property_profile``) or the typed
        list fields (``house_properties`` + ``property_profiles``). This
        validator normalises both directions so the computation engine
        and the official-JSON builder only need to read ``house_properties``
        and ``property_profiles``.
        """
        # 1. Ensure house_properties is populated for legacy callers.
        if not self.house_properties:
            self.house_properties = [self.house_property_income]
        # 2. Enforce the official two-row cap.
        if len(self.house_properties) > 2:
            raise ValueError(
                "ITR-1 supports at most two house properties; "
                f"{len(self.house_properties)} rows were supplied."
            )
        # 3. Mirror house_property_income to the first row for any legacy
        #    reader that still inspects the scalar field.
        if self.house_property_income is not self.house_properties[0]:
            self.house_property_income = self.house_properties[0]
        # 4. Mirror property_profiles ↔ property_profile (single row).
        if not self.property_profiles:
            if self.property_profile is not None:
                self.property_profiles = [self.property_profile]
        else:
            if len(self.property_profiles) > 2:
                raise ValueError(
                    "ITR-1 supports at most two property profiles; "
                    f"{len(self.property_profiles)} rows were supplied."
                )
            if self.property_profile is None:
                self.property_profile = self.property_profiles[0]
            else:
                # Keep the i-th profile authoritative for the i-th row.
                if self.property_profile is not self.property_profiles[0]:
                    self.property_profiles[0] = self.property_profile
        # 5. Keep house_property_count in sync with the row count.
        row_count = max(len(self.house_properties), len(self.property_profiles) or 1)
        if row_count > 2:
            raise ValueError(
                "ITR-1 supports at most two house properties."
            )
        self.house_property_count = max(self.house_property_count, row_count)
        return self

    def reconciled_house_properties(self) -> list["HousePropertyIncome"]:
        """Return the authoritative house-property input list.

        The schema's ``model_validator`` keeps ``house_properties`` and the
        legacy scalar ``house_property_income`` in sync at construction time.
        However, ``model_copy(update={"house_property_income": X})`` mutates
        the scalar without re-running the validator, leaving the list stale.
        This helper detects that staleness and returns the authoritative list
        so the calculator and ITD builder always read consistent inputs.
        """
        if self.house_properties and self.house_properties[0] is self.house_property_income:
            return list(self.house_properties)
        # Stale list (or single-property caller): the scalar is authoritative.
        if self.house_property_income is not None:
            return [self.house_property_income]
        return list(self.house_properties)

    def reconciled_property_profiles(self) -> list["PropertyFilingProfile"]:
        """Return the authoritative property-profile list (mirrors the above).

        If the scalar ``property_profile`` was explicitly cleared (e.g. via
        ``model_copy(update={"property_profile": None})``) the list is stale
        and we return an empty list so downstream builders raise the required
        "property_profile is required" error.
        """
        if self.property_profile is None:
            return []
        if self.property_profiles and self.property_profiles[0] is self.property_profile:
            return list(self.property_profiles)
        return [self.property_profile]

    def loan_schedule_rows(self, section: str) -> list["OfficialDeductionLoanEntry"]:
        """Return canonical official loan rows and reject incomplete legacy copies."""
        rows_by_section = {
            "80EE": self.loan_details_80ee_list,
            "80EEA": self.loan_details_80eea_list,
            "80EEB": self.loan_details_80eeb_list,
        }
        legacy_by_section = {
            "80EE": self.loan_details_80ee,
            "80EEA": self.loan_details_80eea,
            "80EEB": self.loan_details_80eeb,
        }
        if section not in rows_by_section:
            raise ValueError(f"Unsupported deduction loan section: {section}")
        if legacy_by_section[section] is not None:
            raise ValueError(
                f"Legacy {section} loan details are incomplete; provide official loan rows"
            )
        return list(rows_by_section[section])

    def disability_schedule_80dd(self) -> Optional["Schedule80DD"]:
        """Return the canonical 80DD schedule, rejecting conflicting copies."""
        nested = self.deductions_chapter6a.schedule_80dd
        if self.schedule_80dd is not None and nested is not None and self.schedule_80dd != nested:
            raise ValueError("Conflicting Schedule 80DD details were provided")
        return self.schedule_80dd or nested

    def disability_schedule_80u(self) -> Optional["Schedule80U"]:
        """Return the canonical 80U schedule, rejecting conflicting copies."""
        nested = self.deductions_chapter6a.schedule_80u
        if self.schedule_80u is not None and nested is not None and self.schedule_80u != nested:
            raise ValueError("Conflicting Schedule 80U details were provided")
        return self.schedule_80u or nested


# ---------------------------------------------------------------------------
# TDS / TCS entry models (shared across ITR forms)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Stub models referenced by ITR-4 / shared across ITR forms
# ---------------------------------------------------------------------------

class PostalAddress(BaseModel):
    """Postal address fields shared by primary and alternate addresses."""

    residence_no: str = Field(min_length=1, max_length=50)
    residence_name: str = Field(default="", max_length=50)
    road_or_street: str = Field(default="", max_length=50)
    locality_or_area: str = Field(min_length=1, max_length=50)
    city_or_town_or_district: str = Field(min_length=1, max_length=50)
    state_code: str = Field(pattern=r"^(0[1-9]|[12][0-9]|3[0-7]|99)$")
    country_code: str = Field(default="91", min_length=1, max_length=4)
    pin_code: Optional[str] = Field(default=None, pattern=r"^[1-9][0-9]{5}$")
    zip_code: str = Field(default="", max_length=8)


class PropertyFilingProfile(BaseModel):
    """Official address and ownership identity for the single ITR-1 property."""

    address_detail: str = Field(min_length=1, max_length=50)
    city_or_town_or_district: str = Field(min_length=1, max_length=50)
    state_code: str = Field(pattern=r"^(0[1-9]|[12][0-9]|3[0-7]|99)$")
    country_code: str = Field(default="91", min_length=1, max_length=4)
    pin_code: Optional[str] = Field(default=None, pattern=r"^[1-9][0-9]{5}$")
    zip_code: Optional[str] = Field(default=None, min_length=1, max_length=8)

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        """Require an official AY 2026-27 ITD country code."""
        if value not in OFFICIAL_COUNTRY_CODES:
            raise ValueError("country_code must be an official ITD country code")
        return value


class FilingAddress(PostalAddress):
    """Primary filing address with mandatory taxpayer contact details.

    The CBDT ITR-1 Address schema requires CountryCodeMobileNoSec and
    MobileNoSec (always emitted, 0 when absent) and optionally
    EmailAddressSec.  Every field emitted here is verified against the
    official AY 2026-27 schema.
    """

    mobile_country_code: int = Field(default=91, ge=1, le=99999)
    mobile_no: str = Field(pattern=r"^[1-9][0-9]{4,9}$")
    email: str = Field(
        min_length=3,
        max_length=125,
        pattern=r"^([\.a-zA-Z0-9_\-])+@([a-zA-Z0-9_\-])+(([a-zA-Z0-9_\-])*\.([a-zA-Z0-9_\-])+)+$",
    )
    # Secondary mobile — emitted as 0 when absent (CBDT Address schema
    # requires the keys CountryCodeMobileNoSec and MobileNoSec always).
    secondary_mobile_country_code: int = Field(default=0, ge=0, le=99999)
    secondary_mobile_no: Optional[str] = Field(
        default=None,
        pattern=r"^[1-9][0-9]{4,9}$",
    )
    # Secondary email — omitted from the JSON when blank (optional in the
    # CBDT Address schema).
    secondary_email: Optional[str] = Field(
        default=None,
        max_length=125,
        pattern=r"^([\.a-zA-Z0-9_\-])+@([a-zA-Z0-9_\-])+(([a-zA-Z0-9_\-])*\.([a-zA-Z0-9_\-])+)+$",
    )


class SeventhProvisoDetails(BaseModel):
    """Seventh-proviso to section 139(1) declaration details for ITR-1."""

    foreign_travel_flag: bool = False
    foreign_travel_amount: Decimal = Field(default=Decimal("0"), ge=0)
    electricity_expenditure_flag: bool = False
    electricity_expenditure_amount: Decimal = Field(default=Decimal("0"), ge=0)
    other_clause_iv_flag: bool = False
    other_clause_iv_detail: str = Field(default="", max_length=200)


class ITR1FilingProfile(BaseModel):
    """Taxpayer identity, filing status, and verification for official JSON.

    Every field here maps to a real CBDT ITR-1 PersonalInfo, FilingStatus,
    or Verification destination.  No entered statutory field is silently
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
    primary_address: FilingAddress
    alternate_address: Optional[PostalAddress] = None
    father_name: str = Field(min_length=1, max_length=125)
    verification_place: str = Field(min_length=1, max_length=50)
    verification_capacity: Literal["S"] = "S"
    return_file_section: Literal[11, 12] = 11
    # New-regime opt-out (FilingStatus.OptOutNewTaxRegime).  CBDT requires
    # this key always; ITR-1 filers in the new regime emit "N".
    opt_out_new_tax_regime: bool = False
    # Seventh-proviso declarations (FilingStatus.SeventhProvisio139).
    seventh_proviso: SeventhProvisoDetails = Field(default_factory=SeventhProvisoDetails)
    # Form 10-IEA acknowledgement when the assessee opts out of the new
    # regime via Form 10-IEA.  Empty string → emitted as "N" / omitted.
    form_10iea_acknowledgement: str = Field(default="", max_length=25)
    form_10iea_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_opt_out_requires_form_10iea(self) -> "ITR1FilingProfile":
        """Require Form 10-IEA acknowledgement when opting out of new regime.

        For AY 2026-27, a taxpayer with business/profession income who opts
        out of the new regime must have filed Form 10-IEA.  For ITR-1
        (salary-only) filers, the opt-out itself is the declaration, but
        if the acknowledgement number is provided it must be accompanied
        by a valid date and vice versa.
        """
        if self.opt_out_new_tax_regime:
            # Opt-out is allowed for ITR-1; Form 10-IEA is not strictly
            # required for salary-only filers, but if provided must be
            # consistent.
            pass
        if self.form_10iea_acknowledgement and not self.form_10iea_date:
            raise ValueError(
                "form_10iea_date is required when form_10iea_acknowledgement is provided"
            )
        return self


class TaxReturnPreparer(BaseModel):
    """Official tax return preparer details, when a TRP prepares the return."""

    identification_number: str = Field(pattern=r"^(T[0-9]{9}|[0-9]{6})$")
    name: str = Field(min_length=1, max_length=125)
    reimbursement_from_government: Decimal = Field(default=Decimal("0"), ge=0)


class TDS3Entry(BaseModel):
    """TDS on payment to non-residents - Schedule TDS3.

    Mirrors the official ``TDS3Details`` object: tenant/buyer PAN, name,
    gross receipt, deducted year, TDS deducted, TDS claimed, and section.
    """
    tenant_pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    tenant_name: str = Field(min_length=1, max_length=125)
    tenant_aadhaar: Optional[str] = Field(default=None, pattern=r"^[0-9]{12}$")
    gross_receipt: Decimal = Field(default=Decimal("0"), ge=0)
    tds_deducted: Decimal = Field(default=Decimal("0"), ge=0)
    tds_claimed: Decimal = Field(default=Decimal("0"), ge=0)
    tds_section: str = Field(...)
    deducted_yr: str = Field(default="2025", pattern=r"^20[0-9]{2}$")

    @model_validator(mode="after")
    def validate_claimed_does_not_exceed_deducted(self) -> "TDS3Entry":
        """Reject claimed credit that exceeds the deducted credit."""
        if self.tds_claimed > self.tds_deducted:
            raise ValueError("TDS3 claimed credit cannot exceed deducted credit")
        return self


class InsurancePolicy(BaseModel):
    """Health-insurance policy detail used by Schedule 80D."""
    section: str = "1a"
    premium_paid: Decimal = Field(default=Decimal("0"), ge=0)
    insurer_name: Optional[str] = Field(default=None, max_length=125)
    policy_number: Optional[str] = Field(default=None, max_length=50)
    payment_mode_cash: bool = False


class Schedule80D(BaseModel):
    """Schedule 80D health insurance details."""
    has_self_senior: bool = False
    has_parents_senior: bool = False
    not_claiming_self: bool = False
    not_claiming_parents: bool = False
    premium_1a_non_senior: Decimal = Field(default=Decimal("0"), ge=0)
    premium_1b_senior: Decimal = Field(default=Decimal("0"), ge=0)
    premium_2a_parents_non_senior: Decimal = Field(default=Decimal("0"), ge=0)
    premium_2b_parents_senior: Decimal = Field(default=Decimal("0"), ge=0)
    preventive_checkup_self: Decimal = Field(default=Decimal("0"), ge=0)
    preventive_checkup_parents: Decimal = Field(default=Decimal("0"), ge=0)
    policies: List[InsurancePolicy] = Field(default_factory=list)


class Schedule80G(BaseModel):
    """Schedule 80G donation details."""
    donations: List[Donation80G] = Field(default_factory=list)
    total_eligible_amount: Decimal = Field(default=Decimal("0"), ge=0)


class Section80GGAClause(str, Enum):
    """Official clauses under which a Section 80GGA deduction is claimed."""

    SCIENTIFIC_RESEARCH = "80GGA2a"
    SOCIAL_OR_STATISTICAL_RESEARCH = "80GGA2aa"
    RURAL_DEVELOPMENT = "80GGA2b"
    ELIGIBLE_PROJECT = "80GGA2bb"
    NATURAL_RESOURCES_OR_AFFORESTATION = "80GGA2c"
    NOTIFIED_AFFORESTATION_FUND = "80GGA2cc"
    NOTIFIED_RURAL_DEVELOPMENT_FUND = "80GGA2d"
    URBAN_POVERTY_ERADICATION_FUND = "80GGA2e"


class Donation80GGA(BaseModel):
    """Complete official donation row for Schedule 80GGA."""

    relevant_clause: Section80GGAClause
    donee_name: str = Field(min_length=1, max_length=125)
    address: DonationAddress
    donee_pan: str = Field(pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    cash_amount: Decimal = Field(default=Decimal("0"), ge=0)
    other_mode_amount: Decimal = Field(default=Decimal("0"), ge=0)


class Schedule80GGA(BaseModel):
    """Schedule 80GGA scientific research donations."""
    donations: List[Donation80GGA] = Field(default_factory=list)
    cash_donations: Decimal = Field(default=Decimal("0"), ge=0)
    non_cash_donations: Decimal = Field(default=Decimal("0"), ge=0)
    total_claimed: Decimal = Field(default=Decimal("0"), ge=0)
    eligible_amount: Decimal = Field(default=Decimal("0"), ge=0)
    donee_pan_list: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_canonical_rows(self) -> "Schedule80GGA":
        """Reject duplicate PANs and conflicting legacy aggregate copies."""
        if not self.donations:
            return self
        pans = [donation.donee_pan for donation in self.donations]
        if len(pans) != len(set(pans)):
            raise ValueError("Schedule 80GGA donee PANs must be unique")
        cash = sum((donation.cash_amount for donation in self.donations), Decimal("0"))
        other = sum((donation.other_mode_amount for donation in self.donations), Decimal("0"))
        legacy_present = (
            self.cash_donations > 0
            or self.non_cash_donations > 0
            or self.total_claimed > 0
            or self.eligible_amount > 0
            or bool(self.donee_pan_list)
        )
        if legacy_present and (
            self.cash_donations != cash
            or self.non_cash_donations != other
            or self.total_claimed != cash + other
            or (self.donee_pan_list and self.donee_pan_list != pans)
        ):
            raise ValueError("Conflicting legacy and canonical Schedule 80GGA details")
        self.cash_donations = cash
        self.non_cash_donations = other
        self.total_claimed = cash + other
        self.donee_pan_list = pans
        return self


class PoliticalContribution(BaseModel):
    """Complete official contribution row for Schedule 80GGC."""

    amount: Decimal = Field(default=Decimal("0"), ge=0)
    cash_amount: Decimal = Field(default=Decimal("0"), ge=0)
    other_mode_amount: Decimal = Field(default=Decimal("0"), ge=0)
    contribution_date: Optional[date] = None
    contribution_mode: str = "non_cash"
    transaction_ref: Optional[str] = Field(default=None, max_length=50)
    ifsc_code: Optional[str] = Field(
        default=None,
        max_length=11,
        pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$",
    )
    political_party_name: Optional[str] = Field(default=None, min_length=1, max_length=125)
    political_party_pan: Optional[str] = Field(
        default=None,
        pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
    )

    @model_validator(mode="after")
    def normalize_legacy_amount(self) -> "PoliticalContribution":
        """Normalize the legacy amount field into the official other-mode amount."""
        gross = self.cash_amount + self.other_mode_amount
        if self.amount > 0:
            if gross > 0 and self.amount != gross:
                raise ValueError("Conflicting legacy and official 80GGC amounts")
            if gross == 0:
                self.other_mode_amount = self.amount
                gross = self.amount
        self.amount = gross
        self.contribution_mode = "cash" if self.cash_amount > 0 and self.other_mode_amount == 0 else "non_cash"
        return self


class Schedule80GGC(BaseModel):
    """Schedule 80GGC political contributions."""
    total_claimed: Decimal = Field(default=Decimal("0"), ge=0)
    non_cash_contributions: Decimal = Field(default=Decimal("0"), ge=0)
    political_party_name: Optional[str] = Field(default=None, max_length=125)
    political_party_pan: Optional[str] = None
    contributions: List[PoliticalContribution] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_canonical_rows(self) -> "Schedule80GGC":
        """Reject conflicting aggregate and canonical contribution details."""
        if not self.contributions:
            return self
        other = sum(
            (contribution.other_mode_amount for contribution in self.contributions),
            Decimal("0"),
        )
        gross = sum(
            (
                contribution.cash_amount + contribution.other_mode_amount
                for contribution in self.contributions
            ),
            Decimal("0"),
        )
        numeric_legacy_present = (
            self.total_claimed > 0 or self.non_cash_contributions > 0
        )
        if numeric_legacy_present and (
            self.total_claimed != gross
            or self.non_cash_contributions != other
        ):
            raise ValueError("Conflicting legacy and canonical Schedule 80GGC details")
        if self.political_party_name is not None and any(
            contribution.political_party_name != self.political_party_name
            for contribution in self.contributions
        ):
            raise ValueError("Conflicting aggregate and row political party names")
        if self.political_party_pan is not None and any(
            contribution.political_party_pan != self.political_party_pan
            for contribution in self.contributions
        ):
            raise ValueError("Conflicting aggregate and row political party PANs")
        self.total_claimed = gross
        self.non_cash_contributions = other
        return self


class DisabilityScheduleBase(BaseModel):
    """Shared official disability certificate fields for Sections 80DD and 80U."""

    disability_type: DisabilitySeverity = DisabilitySeverity.NORMAL
    disability_category: DisabilityCategory = DisabilityCategory.OTHER
    deduction_amount: Decimal = Field(default=Decimal("0"), ge=0)
    form_10ia_ack_number: Optional[str] = Field(default=None, max_length=15)
    udid_number: Optional[str] = Field(default=None, max_length=18)

    @field_validator("disability_type", mode="before")
    @classmethod
    def normalize_legacy_severity(cls, value: object) -> object:
        """Normalize known legacy ITR-4 labels to the canonical severity enum."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            aliases = {
                "dependent with disability": DisabilitySeverity.NORMAL,
                "dependent with severe disability": DisabilitySeverity.SEVERE,
                "self with disability": DisabilitySeverity.NORMAL,
                "self with severe disability": DisabilitySeverity.SEVERE,
            }
            return aliases.get(normalized, value)
        return value


class Schedule80DD(DisabilityScheduleBase):
    """Official Section 80DD dependent-disability details."""

    dependent_relationship: Optional[DependentRelationship] = None
    dependent_pan: Optional[str] = Field(
        default=None,
        pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
    )
    dependent_aadhaar: Optional[str] = Field(default=None, pattern=r"^[0-9]{12}$")


class Schedule80U(DisabilityScheduleBase):
    """Official Section 80U self-disability details."""


class Schedule80CEntry(BaseModel):
    """Per-row entry for Schedule 80C."""
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    payment_type: Optional[str] = None
    identifier_number: Optional[str] = Field(default=None, max_length=50)


class Schedule80CCCEntry(BaseModel):
    """Per-row entry for Schedule 80CCC."""
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    insurer_name: Optional[str] = Field(default=None, max_length=125)
    policy_number: Optional[str] = Field(default=None, max_length=50)


class EducationLoanLenderType(str, Enum):
    """Official lender category shared by deduction loan schedules."""

    BANK = "B"
    INSTITUTION = "I"


class OfficialDeductionLoanEntry(BaseModel):
    """Common official lender and loan fields for interest deductions."""

    loan_taken_from: EducationLoanLenderType
    lender_name: str = Field(min_length=1, max_length=125)
    account_or_reference_number: str = Field(
        min_length=1,
        max_length=20,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9/-]*$",
    )
    loan_date: date
    total_loan_amount: Decimal = Field(ge=0)
    outstanding_loan_amount: Decimal = Field(ge=0)
    interest_paid: Decimal = Field(ge=0)


class Schedule80EEntry(OfficialDeductionLoanEntry):
    """Complete official loan row for Schedule 80E."""


class LoanDetails(BaseModel):
    """Common deduction-loan details."""
    lender_name: Optional[str] = Field(default=None, max_length=125)
    loan_amount: Decimal = Field(default=Decimal("0"), ge=0)
    sanction_date: Optional[date] = None
    stamp_duty_value: Optional[Decimal] = Field(default=None, ge=0)


class DeductionLoanEntry(LoanDetails):
    """Per-loan deduction entry with interest paid."""
    interest_paid: Decimal = Field(default=Decimal("0"), ge=0)


class Schedule80EELoanEntry(DeductionLoanEntry):
    """Legacy shared loan row retained for ITR-4 compatibility."""


class Schedule80EEALoanEntry(DeductionLoanEntry):
    """Legacy shared loan row retained for ITR-4 compatibility."""


class Schedule80EEBLoanEntry(DeductionLoanEntry):
    """Legacy shared loan row retained for ITR-4 compatibility."""


class ITR1Schedule80EELoanEntry(OfficialDeductionLoanEntry):
    """Complete official ITR-1 loan row for Schedule 80EE."""


class ITR1Schedule80EEALoanEntry(OfficialDeductionLoanEntry):
    """Complete official ITR-1 loan row for Schedule 80EEA."""


class ITR1Schedule80EEBLoanEntry(OfficialDeductionLoanEntry):
    """Complete official ITR-1 electric-vehicle loan row for Schedule 80EEB."""

    vehicle_registration_number: str = Field(min_length=1, max_length=11)


class HRADetails(BaseModel):
    """HRA computation breakdown."""
    actual_hra_received: Decimal = Field(default=Decimal("0"), ge=0)
    rent_paid: Decimal = Field(default=Decimal("0"), ge=0)
    salary_for_hra: Decimal = Field(default=Decimal("0"), ge=0)
    dearness_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    is_metro_city: bool = False


class CoOwnershipDetails(BaseModel):
    """Co-ownership details for house property."""
    ownership_percentage: Decimal = Field(default=Decimal("100"), ge=0, le=100)
    co_owner_pan: Optional[str] = None


class RepresentativeDetails(BaseModel):
    """Representative assessee details."""
    capacity: Optional[str] = None
    represented_person_name: Optional[str] = Field(default=None, max_length=125)
    represented_person_pan: Optional[str] = None


class LoanDetail(LoanDetails):
    """Per-property loan detail entry."""
    account_or_reference_number: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=20,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9/-]*$",
    )
    interest_paid_self_occupied: Decimal = Field(default=Decimal("0"), ge=0)
    interest_paid_let_out: Decimal = Field(default=Decimal("0"), ge=0)


class SecondaryAddress(BaseModel):
    """Secondary address for representative filing."""
    address_line: Optional[str] = Field(default=None, max_length=250)
    city: Optional[str] = Field(default=None, max_length=50)
    state_code: Optional[str] = Field(default=None, max_length=2)
    pin_code: Optional[str] = Field(default=None, max_length=10)


class BankAccountType(str, Enum):
    """Supported bank account types and their official ITD codes."""

    SAVINGS = "savings"
    CURRENT = "current"
    CASH_CREDIT = "cash_credit"
    OVERDRAFT = "overdraft"
    NRO = "nro"
    NRE = "nre"

    @property
    def itd_code(self) -> str:
        """Return the corresponding AY 2026-27 ITD account code."""
        return {
            BankAccountType.SAVINGS: "SB",
            BankAccountType.CURRENT: "CA",
            BankAccountType.CASH_CREDIT: "CC",
            BankAccountType.OVERDRAFT: "OD",
            BankAccountType.NRO: "NRO",
            BankAccountType.NRE: "OTH",
        }[self]


class BankAccount(BaseModel):
    """Bank account disclosed for refund credit."""
    account_number: str = Field(min_length=1, max_length=20)
    ifsc_code: str = Field(min_length=11, max_length=11)
    bank_name: Optional[str] = Field(default=None, min_length=1, max_length=125)
    account_type: str
    is_primary: bool = False


class TaxPaymentDetail(BaseModel):
    """Per-installment entry for Schedule IT."""
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    payment_type: str = "advance"
    payment_date: Optional[date] = None
    bsr_code: Optional[str] = Field(default=None, max_length=7)
    challan_serial_number: Optional[str] = Field(default=None, max_length=5)


class TDS1Entry(BaseModel):
    """Salary TDS credit reported in Schedule TDS1.

    Accepts the current canonical field names and maps legacy router/import
    names before validation so salary tax credits cannot be silently dropped.
    """

    employer_tan: Optional[str] = Field(default=None, pattern=r"^[A-Z]{4}[0-9]{5}[A-Z]$")
    employer_name: Optional[str] = Field(default=None, max_length=125)
    income_chargeable: Decimal = Field(default=Decimal("0"), ge=0)
    tds_deducted: Decimal = Field(default=Decimal("0"), ge=0)

    @model_validator(mode="before")
    @classmethod
    def map_legacy_salary_tds_fields(cls, value: object) -> object:
        """Map legacy salary-TDS payload keys to canonical Schedule TDS1 keys."""
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        aliases = {
            "deductor_tan": "employer_tan",
            "deductor_name": "employer_name",
            "total_amount_credited": "income_chargeable",
            "tax_deducted": "tds_deducted",
        }
        for legacy_key, canonical_key in aliases.items():
            if canonical_key not in payload and legacy_key in payload:
                payload[canonical_key] = payload[legacy_key]
        return payload


class TDS2Entry(BaseModel):
    deductor_tan: str = Field(..., pattern=r"^[A-Z]{4}[0-9]{5}[A-Z]$")
    deductor_name: Optional[str] = Field(default=None, max_length=125)
    tds_section: str = Field(...)
    gross_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tds_deducted: Decimal = Field(default=Decimal("0"), ge=0)
    tds_claimed_this_year: Decimal = Field(default=Decimal("0"), ge=0)
    financial_year: Optional[str] = Field(default=None, pattern=r"^20[0-9]{2}-[0-9]{2}$")


class TCSEntry(BaseModel):
    collector_tan: str = Field(..., pattern=r"^[A-Z]{4}[0-9]{5}[A-Z]$")
    collector_name: Optional[str] = Field(default=None)
    tcs_section: str = Field(...)
    gross_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tcs_collected: Decimal = Field(default=Decimal("0"), ge=0)
    tcs_credit_claimed: Decimal = Field(default=Decimal("0"), ge=0)
    financial_year: Optional[str] = Field(default=None, pattern=r"^20[0-9]{2}-[0-9]{2}$")


ITR1Input.model_rebuild()
