# ITR-1 and ITR-4 Constants for FY 2025-26 (AY 2026-27)
# All values use Decimal for precision - no float

from decimal import Decimal
from typing import Final

# =============================================================================
# OLD REGIME - TAX SLABS (Age-based) - Section 11, IT Act
# =============================================================================
# Taxable income up to basic exemption is nil

OLD_REGIME_SLABS_BELOW_60: Final[list] = [
    (Decimal("0"), Decimal("250000"), Decimal("0")),       # 0-2.5L @ 0%
    (Decimal("250000"), Decimal("500000"), Decimal("5")),   # 2.5L-5L @ 5%
    (Decimal("500000"), Decimal("1000000"), Decimal("20")), # 5L-10L @ 20%
    (Decimal("1000000"), None, Decimal("30")),               # Above 10L @ 30%
]

OLD_REGIME_SLABS_60_TO_80: Final[list] = [
    (Decimal("0"), Decimal("300000"), Decimal("0")),       # 0-3L @ 0%
    (Decimal("300000"), Decimal("500000"), Decimal("5")),   # 3L-5L @ 5%
    (Decimal("500000"), Decimal("1000000"), Decimal("20")), # 5L-10L @ 20%
    (Decimal("1000000"), None, Decimal("30")),               # Above 10L @ 30%
]

OLD_REGIME_SLABS_ABOVE_80: Final[list] = [
    (Decimal("0"), Decimal("500000"), Decimal("0")),       # 0-5L @ 0%
    (Decimal("500000"), Decimal("1000000"), Decimal("20")), # 5L-10L @ 20%
    (Decimal("1000000"), None, Decimal("30")),               # Above 10L @ 30%
]

# =============================================================================
# NEW REGIME (Section 115BAC) - Slabs for AY 2026-27 (FY 2025-26)
# =============================================================================

NEW_REGIME_SLABS_AY_2026_27: Final[list] = [
    (Decimal("0"), Decimal("400000"), Decimal("0")),        # 0-4L @ 0%
    (Decimal("400000"), Decimal("800000"), Decimal("5")),    # 4L-8L @ 5%
    (Decimal("800000"), Decimal("1200000"), Decimal("10")),  # 8L-12L @ 10%
    (Decimal("1200000"), Decimal("1600000"), Decimal("15")), # 12L-16L @ 15%
    (Decimal("1600000"), Decimal("2000000"), Decimal("20")), # 16L-20L @ 20%
    (Decimal("2000000"), Decimal("2400000"), Decimal("25")), # 20L-24L @ 25%
    (Decimal("2400000"), None, Decimal("30")),                # Above 24L @ 30%
]

# =============================================================================
# STANDARD DEDUCTION - Section 16(ia)
# =============================================================================

OLD_REGIME_STANDARD_DEDUCTION: Final[Decimal] = Decimal("50000")    # Sec 16(ia) - Salary income
NEW_REGIME_STANDARD_DEDUCTION: Final[Decimal] = Decimal("75000")    # Sec 16(ia) - Finance Act 2024

# =============================================================================
# SECTION 10 EXEMPTION CEILINGS (Salary)
# =============================================================================

# Sec 10(10) — Gratuity: non-govt capped at Rs 20 lakh (FA 2018).
GRATUITY_EXEMPTION_LIMIT: Final[Decimal] = Decimal("2000000")

# Sec 10(10AA) — Leave encashment on retirement: non-govt capped at Rs 25 lakh (FA 2023).
LEAVE_ENCASHMENT_EXEMPTION_LIMIT: Final[Decimal] = Decimal("2500000")

# Sec 10(10C) — VRS / retrenchment compensation: capped at Rs 5 lakh.
VRS_COMPENSATION_EXEMPTION_LIMIT: Final[Decimal] = Decimal("500000")

# Sec 10(14)(ii) read with Rule 2BB(1)(f) -- transport allowance for a
# blind/deaf-and-dumb/orthopedically-handicapped employee to meet commuting
# expenses: Rs 3,200/month = Rs 38,400/year. (The general, non-disability
# transport allowance this constant's old Rs 1,600/month figure actually
# described was withdrawn by Finance Act 2018, folded into the standard
# deduction -- it is not a live exemption for AY 2026-27 at all. Confirmed
# against the primary source: CBDT ITR-4 Validation Rules rule 186, "10(14)
# (ii) transport allowance for physically handicapped should not exceed
# Rs 38,400" -- this codebase's own validator (ITR4-R105/ITR1 equivalent)
# already hardcoded the correct 38,400 figure directly, while this
# constant -- the one the calculator actually used -- was wrong, silently
# halving the exemption for every disabled employee claiming it.)
TRANSPORT_ALLOWANCE_DISABLED_LIMIT: Final[Decimal] = Decimal("38400")

# Sec 10(14) — Children Education Allowance: Rs 100/month per child (max 2) = Rs 1,200/year.
CHILDREN_EDUCATION_ALLOWANCE_LIMIT: Final[Decimal] = Decimal("1200")
CHILDREN_EDUCATION_ALLOWANCE_PER_CHILD: Final[Decimal] = Decimal("100")
CHILDREN_EDUCATION_MAX_CHILDREN: Final[int] = 2

# Sec 10(14) — Hostel Expenditure Allowance: Rs 300/month per child (max 2) = Rs 3,600/year.
HOSTEL_ALLOWANCE_LIMIT: Final[Decimal] = Decimal("3600")
HOSTEL_ALLOWANCE_PER_CHILD: Final[Decimal] = Decimal("300")

# Sec 10(10A) — Commuted pension, non-govt: 1/3rd if gratuity is also
# received, 1/2 if not (a higher, more generous fraction when there is no
# separate gratuity payout to rely on).
COMMUTED_PENSION_WITH_GRATUITY_PCT: Final[Decimal] = Decimal("1") / Decimal("3")
COMMUTED_PENSION_WITHOUT_GRATUITY_PCT: Final[Decimal] = Decimal("1") / Decimal("2")

# Sec 10(10) — Gratuity, non-govt, employees NOT covered under the Payment of
# Gratuity Act 1972: half a month's average salary (last 10 months) per
# completed year of service. (Employees covered under the Act instead use
# 15/26 x last-drawn salary x years — a more generous multiple — but that
# needs a "covered under the Act" fact this product does not capture; using
# the lower non-covered multiple is the conservative choice when that fact
# is unknown, matching this codebase's "never over-grant an exemption
# without evidence" convention.)
GRATUITY_NON_COVERED_SALARY_MULTIPLE: Final[Decimal] = Decimal("0.5")

# Sec 10(10AA) — Leave encashment, non-govt: cash equivalent of leave capped
# at 30 days earned per completed year of service, and separately capped at
# 10 months' average salary.
LEAVE_ENCASHMENT_MAX_DAYS_PER_YEAR: Final[int] = 30
LEAVE_ENCASHMENT_MAX_MONTHS_AVERAGE_SALARY: Final[Decimal] = Decimal("10")

# Sec 10(5) — LTA exemption: two journeys per block of four calendar years.
# No per-journey statutory cap; the exemption is the actual fare cost (economy air / AC rail).
# The cap is structural (block-year carry-forward), not a rupee ceiling.

# =============================================================================
# REBATE u/s 87A
# =============================================================================

# Old regime rebate (AY 2026-27)
OLD_REBATE_TAX_LIMIT: Final[Decimal] = Decimal("12500")           # Max rebate amount
OLD_REBATE_INCOME_LIMIT: Final[Decimal] = Decimal("500000")         # Income below which rebate applies

# New regime rebate (AY 2026-27) - Finance Act 2025
NEW_REBATE_TAX_LIMIT: Final[Decimal] = Decimal("60000")            # Max rebate amount
NEW_REBATE_INCOME_LIMIT: Final[Decimal] = Decimal("1200000")        # Full rebate income ceiling

# =============================================================================
# HEALTH & EDUCATION CESS - Section 272B
# =============================================================================

HEALTH_EDUCATION_CESS_RATE: Final[Decimal] = Decimal("0.04")       # 4% of tax + surcharge

# =============================================================================
# SURCHARGE RATES FOR INDIVIDUALS (AY 2026-27)
# =============================================================================
# Basic exemption limits by age bracket (AY 2026-27)
# Used for partial integration of agricultural income and other rate
# determination purposes under the old regime.
BASIC_EXEMPTION_LIMITS: Final[dict[str, Decimal]] = {
    "below_60": Decimal("250000"),
    "60_to_80": Decimal("300000"),
    "above_80": Decimal("500000"),
}


# Surcharge applies on tax after rebate
# Marginal relief ensures tax+surcharge does not exceed income over threshold

SURCHARGE_SLABS: Final[list] = [
    (Decimal("5000000"), Decimal("10000000"), Decimal("0.10")),  # 10% for 50L-1Cr
    (Decimal("10000000"), Decimal("20000000"), Decimal("0.15")), # 15% for 1Cr-2Cr
    (Decimal("20000000"), Decimal("50000000"), Decimal("0.25")), # 25% for 2Cr-5Cr
    (Decimal("50000000"), None, Decimal("0.37")),                  # 37% for above 5Cr (Old Regime)
]

# New regime surcharge above ₹5Cr is capped at 25% (Finance Act 2023)
SURCHARGE_SLABS_NEW_REGIME: Final[list] = [
    (Decimal("5000000"), Decimal("10000000"), Decimal("0.10")),  # 10% for 50L-1Cr
    (Decimal("10000000"), Decimal("20000000"), Decimal("0.15")), # 15% for 1Cr-2Cr
    (Decimal("20000000"), Decimal("50000000"), Decimal("0.25")), # 25% for 2Cr-5Cr
    (Decimal("50000000"), None, Decimal("0.25")),                  # 25% for above 5Cr (New Regime cap)
]

# =============================================================================
# PRESUMPTIVE INCOME RATES - Sections 44AD, 44ADA, 44AE
# =============================================================================

# Section 44AD - Business (turnover up to Rs 2 Crore)
# Presumptive rate depends on payment mode
PRESUMPTIVE_44AD_DIGITAL: Final[Decimal] = Decimal("0.06")        # 6% of gross receipts (digital)
PRESUMPTIVE_44AD_CASH: Final[Decimal] = Decimal("0.08")           # 8% of gross receipts (cash)
SEC_44AD_TURNOVER_LIMIT: Final[Decimal] = Decimal("30000000")     # Rs 3 crore (Section 44AD threshold, FA 2024)

# Section 44ADA - Professionals (gross receipts up to Rs 75 Lakh)
# Flat 50% of gross receipts as presumptive income
PRESUMPTIVE_44ADA_RATE: Final[Decimal] = Decimal("0.50")          # 50% of professional gross
SEC_44ADA_RECEIPTS_LIMIT: Final[Decimal] = Decimal("7500000")     # Rs 75 lakh (Section 44ADA threshold)

# Section 44AE - Goods carriage (per vehicle)
# Presumptive income per vehicle per year (monthly x 12)
PRESUMPTIVE_44AE_PER_VEHICLE_OWNER: Final[Decimal] = Decimal("7500")          # Rs 7,500 per month per vehicle
PRESUMPTIVE_44AE_PER_VEHICLE_LEASED: Final[Decimal] = Decimal("7500")         # Rs 7,500 per month per vehicle

# =============================================================================
# CHAPTER VI-A DEDUCTION LIMITS
# =============================================================================

# Section 80C - LIC, PPF, ELSS, etc. (combined with 80CCC, 80CCD(1))
SECTION_80C_LIMIT: Final[Decimal] = Decimal("150000")             # Rs 1.5 lakh

# Section 80CCC - Pension schemes (combined with 80C, 80CCD(1))
SECTION_80CCC_LIMIT: Final[Decimal] = Decimal("150000")           # Rs 1.5 lakh (combined)

# Section 80CCD(1) - Employee/self contribution to NPS (part of 80C limit)
SECTION_80CCD1_LIMIT: Final[Decimal] = Decimal("150000")          # Within 80C limit

# Section 80CCD(1B) - Additional NPS contribution (over 80C limit)
SECTION_80CCD1B_LIMIT: Final[Decimal] = Decimal("50000")          # Rs 50,000 extra

# Section 80CCD(2) - Employer NPS contribution (no cap)
SECTION_80CCD2_LIMIT: Final[Decimal] = None                         # No upper limit

# Section 80D - Health Insurance
SECTION_80D_SELF_FAMILY_LIMIT: Final[Decimal] = Decimal("25000")  # Self & family (non-senior)
SECTION_80D_SELF_FAMILY_SENIOR_LIMIT: Final[Decimal] = Decimal("50000")  # Self & family (senior)
SECTION_80D_PARENTS_LIMIT: Final[Decimal] = Decimal("25000")       # Parents (non-senior)
SECTION_80D_PARENTS_SENIOR_LIMIT: Final[Decimal] = Decimal("50000")  # Parents (senior)
SECTION_80D_PREVENTIVE_CHECKUP_LIMIT: Final[Decimal] = Decimal("5000")   # Per family/parent bucket

# Section 80DD - Medical treatment of dependent with disability
SECTION_80DD_LIMIT: Final[Decimal] = Decimal("75000")             # Disabled dependent
SECTION_80DD_SEVERE_LIMIT: Final[Decimal] = Decimal("125000")     # Severely disabled

# Section 80DDB - Medical treatment for specified diseases
SECTION_80DDB_LIMIT: Final[Decimal] = Decimal("40000")            # Below 60 years
SECTION_80DDB_SENIOR_LIMIT: Final[Decimal] = Decimal("100000")    # 60 years and above

# Section 80E - Interest on education loan
SECTION_80E_LIMIT: Final[Decimal] = None                           # No upper limit (8 years)

# Section 80EE - First-time home buyer interest
SECTION_80EE_LIMIT: Final[Decimal] = Decimal("50000")            # Rs 50,000

# Section 80EEA - Affordable housing interest (PMAY)
SECTION_80EEA_LIMIT: Final[Decimal] = Decimal("150000")          # Rs 1.5 lakh

# Section 80EEB - Electric vehicle loan interest
SECTION_80EEB_LIMIT: Final[Decimal] = Decimal("150000")          # Rs 1.5 lakh

# Section 80G - Donations (various percentages and limits)
SECTION_80G_100_PERCENT_LIMIT: Final[str] = "Without Limit"       # 100% without limit
SECTION_80G_50_PERCENT_LIMIT: Final[str] = "Subject to 10%"       # 50% with 10% of GTI cap
SECTION_80G_CASH_LIMIT: Final[Decimal] = Decimal("2000")         # Cash donation cap

# Section 80GGA - Donations to scientific research/rural development
SECTION_80GGA_LIMIT: Final[Decimal] = None                         # No upper limit

# Section 80GGC - Political party contributions
SECTION_80GGC_LIMIT: Final[Decimal] = None                         # No upper limit

# Section 80GG - House rent allowance (Section 80GG)
SECTION_80GG_RENT_LIMIT: Final[Decimal] = Decimal("60000")       # Rs 5,000 x 12 months
SECTION_80GG_GTI_PERCENT: Final[Decimal] = Decimal("0.25")      # 25% of GTI

# Section 80QQB - Royalty income (authors)
SECTION_80QQB_LIMIT: Final[Decimal] = Decimal("300000")          # Rs 3,00,000

# Section 80RRB - Royalty on patents
SECTION_80RRB_LIMIT: Final[Decimal] = Decimal("300000")          # Rs 3,00,000

# Section 80TTA - Interest on savings account
SECTION_80TTA_LIMIT: Final[Decimal] = Decimal("10000")          # Rs 10,000

# Section 80TTB - Interest for senior citizens
SECTION_80TTB_LIMIT: Final[Decimal] = Decimal("50000")           # Rs 50,000

# Section 80U - Person with disability
SECTION_80U_LIMIT: Final[Decimal] = Decimal("75000")             # Disabled
SECTION_80U_SEVERE_LIMIT: Final[Decimal] = Decimal("125000")     # Severely disabled

# Section 80CCH - Agniveer Corpus Fund (no statutory rupee ceiling per s.80CCH)

# =============================================================================
# HOUSE PROPERTY - Section 24
# =============================================================================

HOUSE_PROPERTY_STANDARD_DEDUCTION: Final[Decimal] = Decimal("0.30") # 30% of NAV (Sec 24(a))
HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED: Final[Decimal] = Decimal("200000")  # Sec 24(b) - Self-occupied
# Sec 24(b) proviso: the Rs 2,00,000 self-occupied cap applies only to loans
# sanctioned on/after 1 April 1999 for purchase or construction; a loan
# sanctioned before that date is capped at Rs 30,000 instead.
HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED_PRE_1999: Final[Decimal] = Decimal("30000")

# =============================================================================
# CAPITAL GAINS - Special Rates (AY 2026-27)
# =============================================================================

# Section 111A - STCG on listed equity (STT paid)
STCG_111A_RATE_PRE_JUL24: Final[Decimal] = Decimal("15")         # Before 23 July 2024
STCG_111A_RATE_POST_JUL24: Final[Decimal] = Decimal("20")        # On/after 23 July 2024

# Section 112A - LTCG on listed equity (STT paid)
LTCG_112A_RATE: Final[Decimal] = Decimal("10")                   # Pre-23 July 2024
LTCG_112A_RATE_POST_JUL24: Final[Decimal] = Decimal("12.5")      # On/after 23 July 2024
LTCG_112A_EXEMPTION: Final[Decimal] = Decimal("125000")         # Rs 1.25 lakh exemption

# Section 112 - Other LTCG (without indexation)
LTCG_OTHER_RATE: Final[Decimal] = Decimal("20")                  # With indexation pre-23 Jul 2024
LTCG_OTHER_RATE_POST_JUL24: Final[Decimal] = Decimal("12.5")     # Without indexation post-23 Jul 2024

# Section 115BB - Lottery/Gambling
LOTTERY_RATE: Final[Decimal] = Decimal("30")                     # Flat 30%

# Section 115BBH - Virtual Digital Assets
VDA_RATE: Final[Decimal] = Decimal("30")                         # Flat 30%

# Section 115BBE - Unexplained income
UNEXPLAINED_INCOME_RATE: Final[Decimal] = Decimal("60")          # Flat 60%

# =============================================================================
# COST INFLATION INDEX (CII) — Notified u/s 48, Explanation (v)
# Base year: FY 2001-02 = 100
# Source: CBDT Notification No. 70/2025 dated 1-Jul-2025 (as amended by FA 2025)
# =============================================================================

CII_TABLE: Final[dict[int, int]] = {
    # Pre base-year: actual FMV as on 01-04-2001 used
    2001: 100, 2002: 105, 2003: 109, 2004: 113, 2005: 117,
    2006: 122, 2007: 129, 2008: 137, 2009: 148, 2010: 167,
    2011: 184, 2012: 200, 2013: 220, 2014: 240, 2015: 254,
    2016: 264, 2017: 272, 2018: 280, 2019: 289, 2020: 301,
    2021: 317, 2022: 331, 2023: 348, 2024: 363, 2025: 376,
    2026: 384,
}

# FMV date for "grandfathering" rule u/s 112A
LTCG_112A_GRANDFATHER_DATE: Final[str] = "2018-01-31"

# ---------------------------------------------------------------------------
# Business-specific deduction limits (ITR-3 only)
# ---------------------------------------------------------------------------

# 80-IA: 100% of profits for 10 consecutive AYs (infrastructure). No per-AY cap.
# 80-IB: 100%/30%/25% of profits depending on category. No per-AY cap.
# 80-IC: 100% of profits first 5 years, 25%/30% next 5 years. No per-AY cap.
# 10AA: 100% of export profits first 5 years, 50% next 5 years. No per-AY cap.
# 80RA: 100% deduction on patent/royalty income received. No per-AY cap.
# All business deductions have no fixed rupee cap � claim = qualifying profit.