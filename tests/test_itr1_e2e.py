#!/usr/bin/env python
"""
ITR-1 (Sahaj) -- Interactive End-to-End Test Script
====================================================
Covers every mandatory field per ITR-1_2026_Main_V1.1 schema.
Generates a CBDT ITD-compliant JSON you can validate on the UAT portal.

Usage:
    python test_itr1_e2e.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Any

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))  # Load UAT credentials before app imports

# ── Terminal formatting ─────────────────────────────────────────────────────
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def header(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}")

def subheader(text: str) -> None:
    print(f"\n{BOLD}{YELLOW}  ▸ {text}{RESET}")

def ask(label: str, default: str = "", validate: str = "any") -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"    {label}{suffix}: ").strip()
        if not val and default:
            val = default
        if validate == "any":
            return val
        if validate == "nonempty" and not val:
            print(f"      {RED}Required.{RESET}"); continue
        if validate == "pan":
            import re
            if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", val): return val
            print(f"      {RED}Invalid PAN (e.g. AAAAA0000A).{RESET}"); continue
        if validate == "ifsc":
            import re
            if re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", val): return val
            print(f"      {RED}Invalid IFSC (e.g. SBIN0000001).{RESET}"); continue
        if validate == "date":
            try: datetime.strptime(val, "%Y-%m-%d"); return val
            except ValueError: print(f"      {RED}Use YYYY-MM-DD.{RESET}"); continue
        if validate == "decimal":
            try: Decimal(val); return val
            except InvalidOperation: print(f"      {RED}Invalid number.{RESET}"); continue
        if validate == "int":
            try: int(val); return val
            except ValueError: print(f"      {RED}Invalid integer.{RESET}"); continue
        return val

def ask_opt(label: str, default: str, options: list[str]) -> str:
    print(f"    {label}:")
    for i, opt in enumerate(options, 1):
        mark = " ←" if opt.startswith(default) else ""
        print(f"      {i}. {opt}{mark}")
    while True:
        val = input(f"    Choose [1-{len(options)}] (default={default}): ").strip()
        if not val: return default
        try:
            idx = int(val) - 1
            if 0 <= idx < len(options): return options[idx]
        except ValueError: pass
        print(f"      {RED}Please choose 1-{len(options)}.{RESET}")

def fmt(amt: Decimal) -> str:
    return f"₹{int(amt):,}"


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    header("ITR-1 (Sahaj)  End-to-End Test •• AY 2026-27")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1. PERSONAL & FILING
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("1. PERSONAL & FILING INFO")

    pan            = ask("PAN (10-char)",        "AAAAA0000A", "pan")
    first_name     = ask("First Name",           "Rahul")
    middle_name    = ask("Middle Name (optional)","")
    last_name      = ask("Last Name",            "Sharma")
    dob            = ask("Date of Birth (YYYY-MM-DD)", "1990-08-15", "date")
    aadhaar        = ask("Aadhaar (12 digits, optional)", "123456789012")

    age_opts = ["below_60  (< 60)", "60_to_80  (Senior)", "above_80  (Super Senior)"]
    age_bracket = ask_opt("Age Bracket", "below_60", age_opts)
    age_bracket = age_bracket.split()[0]  # extract enum value

    regime_opts = ["old (with deductions)", "new (115BAC, concessional rates)"]
    tax_regime = ask_opt("Tax Regime", "new", regime_opts)
    tax_regime = "old" if "old" in tax_regime else "new"

    emp_opts = ["CGOV", "SGOV", "PSU", "PE", "OTH", "NA"]
    employer_category = ask_opt("Employer Category", "OTH", emp_opts)

    filing_opts = ["11-139(1) Original","12-139(4) Belated","17-139(5) Revised",
                   "13-142(1)","14-148","16-153C","20-119(2)(b)"]
    return_file_sec = int(ask_opt("Filing Section", "11-139(1) Original", filing_opts).split("-")[0])

    subheader("Address")
    residence_no   = ask("House/Flat No",       "42")
    locality       = ask("Locality/Area",       "MG Road")
    city           = ask("City/Town",           "Bengaluru")
    pin_code       = ask("PIN Code (6-digit, opt)","560001")
    state_code     = ask("State Code (01-37)",  "29")
    country_code   = ask("Country Code",        "91")
    mobile_no      = ask("Mobile (10-digit)",   "9876543210")
    email          = ask("Email",               "rahul@email.com")

    subheader("Eligibility Gates")
    is_resident     = ask("Is resident? (y/n)",           "y") == "y"
    is_director     = ask("Director in any company? (y/n)","n") == "y"
    has_foreign     = ask("Has foreign assets/income? (y/n)", "n") == "y"
    has_unlisted    = ask("Holds unlisted equity? (y/n)", "n") == "y"
    hp_count        = max(1, int(ask("Number of house properties", "1", "int")))

    if not is_resident:
        print(f"\n{RED}  ✗ ITR-1 requires resident status. Cannot proceed.{RESET}")
        sys.exit(1)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2. SALARY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("2. SALARY INCOME")
    has_sal = ask("Has salary income? (y/n)", "y") == "y"
    if has_sal:
        gross_salary       = Decimal(ask("Gross Salary                   (₹)", "1800000", "decimal"))
        perquisites        = Decimal(ask("Perquisites value             (₹)", "0", "decimal"))
        profits_lieu       = Decimal(ask("Profits in lieu of salary     (₹)", "0", "decimal"))
        standard_ded_claimed=Decimal(ask("Standard deduction claimed    (₹, old=50000, new=75000)", "75000" if tax_regime=="new" else "50000", "decimal"))
        entertainment_allow= Decimal(ask("Entertainment allowance u/s 16(ii) (₹)", "0", "decimal"))
        professional_tax   = Decimal(ask("Professional tax paid u/s 16(iii) (₹)", "2500", "decimal"))
        is_govt_emp        = ask("Govt employee? (y/n)", "n") == "y"
        hra_received       = Decimal(ask("HRA received                  (₹)", "120000", "decimal"))
        rent_paid          = Decimal(ask("Actual rent paid              (₹)", "180000", "decimal"))
        hra_metro          = ask("Place of work is metro city? (y/n)", "y") == "y"
    else:
        gross_salary = perquisites = profits_lieu = standard_ded_claimed = Decimal("0")
        entertainment_allow = professional_tax = hra_received = rent_paid = Decimal("0")
        is_govt_emp = False; hra_metro = False

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3. HOUSE PROPERTY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("3. HOUSE PROPERTY")
    has_hp = ask("Has house property? (y/n)", "n") == "y"
    if has_hp:
        hp_opts = ["S-Self Occupied","L-Let Out","D-Deemed Let Out"]
        hp_type = ask_opt("Property Type", "S-Self Occupied", hp_opts).split("-")[0]
        municipal_value = Decimal(ask("Municipal Value / ALV       (₹)", "0", "decimal"))
        annual_rent     = Decimal("0")
        municipal_tax   = Decimal("0")
        if hp_type != "S":
            annual_rent  = Decimal(ask("Annual Rent Received        (₹)", "240000", "decimal"))
            municipal_tax= Decimal(ask("Municipal Taxes Paid        (₹)", "12000", "decimal"))
        home_loan_int   = Decimal(ask("Home loan interest u/s 24(b) (₹)", "200000", "decimal"))
    else:
        hp_type = "S"; municipal_value = annual_rent = municipal_tax = home_loan_int = Decimal("0")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. OTHER SOURCES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("4. OTHER SOURCES INCOME")
    has_os = ask("Has other sources income? (y/n)", "y") == "y"
    if has_os:
        savings_int  = Decimal(ask("Savings bank interest    (₹)", "15000", "decimal"))
        fd_int       = Decimal(ask("Fixed deposit interest   (₹)", "45000", "decimal"))
        dividend     = Decimal(ask("Dividend income          (₹)", "0", "decimal"))
        fam_pension  = Decimal(ask("Family pension           (₹)", "0", "decimal"))
    else:
        savings_int = fd_int = dividend = fam_pension = Decimal("0")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 5. CAPITAL GAINS 112A
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("5. CAPITAL GAINS (Section 112A)")
    has_cg = ask("Has LTCG u/s 112A? (y/n)", "n") == "y"
    if has_cg:
        ltcg_112a  = Decimal(ask("Total LTCG u/s 112A     (₹)", "200000", "decimal"))
        cg_sale    = Decimal(ask("Sale consideration      (₹)", "500000", "decimal"))
        cg_cost    = Decimal(ask("Cost of acquisition     (₹)", "300000", "decimal"))
        if ltcg_112a > 125000:
            print(f"\n{RED}  ✗ LTCG exceeds ₹1,25,000 — ITR-1 not allowed. Use ITR-2.{RESET}")
            sys.exit(1)
    else:
        ltcg_112a = Decimal("0"); cg_sale = None; cg_cost = None

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 6. CHAPTER VI-A DEDUCTIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("6. CHAPTER VI-A DEDUCTIONS")

    ded = {}  # keys are schema field names
    sen_self = sen_parents = False; dd_severe = u_severe = False

    if tax_regime == "old":
        ded["amount_80c"]   = Decimal(ask("80C  - LIC/PPF/ELSS/EPF etc                    (₹)", "150000", "decimal"))
        ded["amount_80ccc"] = Decimal(ask("80CCC- Annuity plan premium                     (₹)", "0", "decimal"))
        ded["amount_80ccd1"]= Decimal(ask("80CCD(1)-Employee NPS contribution               (₹)", "50000", "decimal"))
        raw_80cce = ded["amount_80c"] + ded["amount_80ccc"] + ded["amount_80ccd1"]
        if raw_80cce > 150000:
            print(f"      {YELLOW}⚠ 80C+80CCC+80CCD(1) = ₹{raw_80cce:,} exceeds ₹1,50,000 80CCE cap.{RESET}")
        ded["amount_80ccd1b"]=Decimal(ask("80CCD(1B)-Additional NPS                  (₹, max 50000)", "50000", "decimal"))
        ded["amount_80ccd2"]= Decimal(ask("80CCD(2)-Employer NPS (allowed in both regimes)  (₹)", "0", "decimal"))
        ded["amount_80d_self_family"]=Decimal(ask("80D - Med. insurance prem. (self+family)       (₹)", "25000", "decimal"))
        ded["amount_80d_preventive_self"]=Decimal(ask("80D - Preventive check-up (self+family) (₹, max 5000)", "0", "decimal"))
        if ded["amount_80d_preventive_self"] > 5000:
            print(f"      {YELLOW}⚠ Preventive check-up capped at ₹5,000. Engine will cap.{RESET}")
        ded["amount_80d_parents"]=Decimal(ask("80D - Med. insurance prem. (parents)           (₹)", "25000", "decimal"))
        ded["amount_80d_preventive_parents"]=Decimal(ask("80D - Preventive check-up (parents)   (₹, max 5000)", "0", "decimal"))
        if ded["amount_80d_preventive_parents"] > 5000:
            print(f"      {YELLOW}⚠ Preventive check-up capped at ₹5,000. Engine will cap.{RESET}")
        sen_self     = ask("80D: Self/family includes senior citizen? (y/n)", "n") == "y"
        sen_parents  = ask("80D: Parents include senior citizen? (y/n)", "y") == "y"
        ded["amount_80dd"]  = Decimal(ask("80DD - Disabled dependent maintenance           (₹)", "0", "decimal"))
        dd_severe    = ask("80DD: Disability is severe (>=80%)? (y/n)", "n") == "y"
        dd_cap = 125000 if dd_severe else 75000
        if ded["amount_80dd"] > dd_cap:
            print(f"      {YELLOW}⚠ 80DD cap is ₹{dd_cap:,}. Engine will cap.{RESET}")
        ded["amount_80ddb"] = Decimal(ask("80DDB- Specified disease treatment                (₹)", "0", "decimal"))
        ddb_cap = 100000 if age_bracket in ("60_to_80", "above_80") else 40000
        if ded["amount_80ddb"] > ddb_cap:
            print(f"      {YELLOW}⚠ 80DDB cap is ₹{ddb_cap:,} (age-based). Engine will cap.{RESET}")
        ded["amount_80u"]   = Decimal(ask("80U  - Self disability                            (₹)", "0", "decimal"))
        u_severe     = ask("80U: Disability is severe (>=80%)? (y/n)", "n") == "y"
        u_cap = 125000 if u_severe else 75000
        if ded["amount_80u"] > u_cap:
            print(f"      {YELLOW}⚠ 80U cap is ₹{u_cap:,}. Engine will cap.{RESET}")
        ded["amount_80e"]   = Decimal(ask("80E  - Education loan interest                    (₹)", "0", "decimal"))
        ded["amount_80ee"]  = Decimal(ask("80EE - First-time home loan interest              (₹)", "0", "decimal"))
        if ded["amount_80ee"] > 50000:
            print(f"      {YELLOW}⚠ 80EE cap is ₹50,000. Engine will cap.{RESET}")
        ded["amount_80eea"] = Decimal(ask("80EEA- Affordable housing loan interest           (₹)", "0", "decimal"))
        if ded["amount_80eea"] > 150000:
            print(f"      {YELLOW}⚠ 80EEA cap is ₹1,50,000. Engine will cap.{RESET}")
        ded["amount_80eeb"] = Decimal(ask("80EEB- Electric vehicle loan interest             (₹)", "0", "decimal"))
        if ded["amount_80eeb"] > 150000:
            print(f"      {YELLOW}⚠ 80EEB cap is ₹1,50,000. Engine will cap.{RESET}")
        ded["amount_80g"]   = Decimal(ask("80G  - Donations                                  (₹)", "0", "decimal"))
        ded["amount_80gg"]  = Decimal(ask("80GG - Rent paid (no HRA)                         (₹)", "0", "decimal"))
        if ded["amount_80gg"] > 0 and has_sal and hra_received > 0:
            print(f"      {RED}⚠ 80GG not available when HRA is received. Engine will disallow.{RESET}")
        ded["amount_80tta"] = Decimal(ask("80TTA- Savings interest (age<60, max 10000)       (₹)", "10000", "decimal"))
        if ded["amount_80tta"] > 10000:
            print(f"      {YELLOW}⚠ 80TTA cap is ₹10,000. Engine will cap.{RESET}")
        if age_bracket == "below_60":
            has_ttb = Decimal(ask("80TTB- Sr citizen deposit interest (age>=60, max 50000)(₹)", "0", "decimal"))
            if has_ttb > 0:
                print(f"      {RED}⚠ 80TTB is only for senior citizens (age ≥ 60). Engine will set to ₹0.{RESET}")
            ded["amount_80ttb"] = Decimal("0")
        else:
            ded["amount_80ttb"] = Decimal(ask("80TTB- Sr citizen deposit interest (age>=60, max 50000)(₹)", "0", "decimal"))
        ded["amount_80cch"] = Decimal(ask("80CCH-Agniveer Corpus Fund                        (₹)", "0", "decimal"))
    else:
        # New regime: only 80CCD(2) + 80CCH
        ded["amount_80ccd2"]= Decimal(ask("80CCD(2)-Employer NPS (only deduction available)  (₹)", "0", "decimal"))
        ded["amount_80cch"] = Decimal(ask("80CCH - Agniveer Corpus Fund                      (₹)", "0", "decimal"))
        # Set all others to 0
        for k in ["amount_80c","amount_80ccc","amount_80ccd1","amount_80ccd1b",
                  "amount_80d_self_family","amount_80d_parents","amount_80d_preventive_self",
                  "amount_80d_preventive_parents","amount_80dd","amount_80ddb","amount_80u",
                  "amount_80e","amount_80ee","amount_80eea","amount_80eeb",
                  "amount_80g","amount_80gg","amount_80tta","amount_80ttb"]:
            ded.setdefault(k, Decimal("0"))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 7. AGRICULTURAL INCOME
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("7. AGRICULTURAL INCOME")
    has_agri = ask("Has net agricultural income > ₹5,000? (y/n)", "n") == "y"
    if has_agri:
        agri_income = Decimal(ask("Net Agricultural Income (₹, must be > ₹5,000)", "6000", "decimal"))
        if agri_income <= Decimal("5000"):
            print(f"      {RED}⚠ Agri income ≤ ₹5,000 contradicts 'Yes' above.{RESET}")
            print(f"      {RED}  ITR-1 allows agri income up to ₹5,000. Set to 0 for ITR-1.{RESET}")
            agri_income = Decimal("0")
    else:
        agri_income = Decimal("0")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 8. TAX PAYMENTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("8. TDS / TCS / ADVANCE TAX / SELF-ASSESSMENT")

    has_tds_sal = ask("Has TDS on salary (Form 16)? (y/n)", "y") == "y"
    tds_salary = Decimal(ask("Total TDS on salary (₹)", "120000", "decimal")) if has_tds_sal else Decimal("0")

    has_tds_oth = ask("Has TDS on other income? (y/n)", "n") == "y"
    if has_tds_oth:
        tds_other = Decimal(ask("Total TDS deducted on other income (₹)", "0", "decimal"))
        tds_other_gross = Decimal(ask("Gross amount on which TDS was deducted (₹)", "0", "decimal"))
    else:
        tds_other = Decimal("0")
        tds_other_gross = Decimal("0")

    tcs_total = Decimal(ask("Total TCS collected (₹)", "0", "decimal"))

    advance_tax = Decimal(ask("Total Advance Tax Paid (₹)", "0", "decimal"))
    has_qwise = ask("Provide quarter-wise advance tax breakup? (y/n)", "n") == "y"
    advance_q1 = advance_q2 = advance_q3 = advance_q4 = None
    if has_qwise:
        advance_q1 = Decimal(ask("  Q1 (by 15-Jun) (₹)", "0", "decimal"))
        advance_q2 = Decimal(ask("  Q2 (by 15-Sep) (₹)", "0", "decimal"))
        advance_q3 = Decimal(ask("  Q3 (by 15-Dec) (₹)", "0", "decimal"))
        advance_q4 = Decimal(ask("  Q4 (by 15-Mar) (₹)", str(advance_tax), "decimal"))

    self_assmt = Decimal(ask("Self-Assessment Tax Paid (₹)", "0", "decimal"))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 9. DATES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("9. FILING DATES")
    filing_date = datetime.strptime(ask("Date of Filing (YYYY-MM-DD)", "2025-07-31", "date"), "%Y-%m-%d").date()
    due_date    = datetime.strptime(ask("Due Date       (YYYY-MM-DD)", "2025-07-31", "date"), "%Y-%m-%d").date()
    relief_89   = Decimal(ask("Relief u/s 89 - Form 10E (₹)", "0", "decimal"))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 10. BANK
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("10. BANK DETAILS")
    bank_name  = ask("Bank Name", "State Bank of India")
    account_no = ask("Account Number", "12345678901")
    ifsc       = ask("IFSC Code", "SBIN0000001", "ifsc")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 11. VERIFICATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    header("11. VERIFICATION")
    father_name = ask("Father's Name", "Ramesh Sharma")
    ver_place   = ask("Place of Verification", "Bengaluru")

    # ═══════════════════════════════════════════════════════════════════════
    # BUILD & COMPUTE
    # ═══════════════════════════════════════════════════════════════════════
    header("COMPUTING...")

    from app.schemas.itr1 import (
        ITR1Input, SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
        Chapter6ADeductions, CapitalGainsIncome, AgeBracket, AssesseeType,
        TaxRegime, PropertyType, Schedule80DD, Schedule80U,
        TDS1Entry, TDS2Entry, TCSEntry,
    )
    from app.engine.calculators.itr1 import compute as compute_itr1
    from app.engine.itd.itr1 import build_itr1_json

    # Build salary
    sal = SalaryIncome(
        gross_salary=gross_salary,
        perquisites_value=perquisites,
        profits_in_lieu_of_salary=profits_lieu,
        standard_deduction_claimed=standard_ded_claimed,
        entertainment_allowance=entertainment_allow,
        professional_tax_paid=professional_tax,
        is_government_employee=is_govt_emp,
    ) if has_sal else None

    # Build HP (required — always create, default to self-occupied with zeros)
    hp = HousePropertyIncome(
        property_type=PropertyType(hp_type),
        annual_rent_received=annual_rent,
        municipal_taxes_paid=municipal_tax,
        home_loan_interest_paid=home_loan_int,
    )

    # Build OS
    os_total = savings_int + fd_int + dividend + fam_pension
    os_inp = OtherSourcesIncome(
        savings_bank_interest=savings_int,
        fixed_deposit_interest=fd_int,
        dividend_income=dividend,
        family_pension_received=fam_pension,
    ) if os_total > 0 else None

    # Build CG
    cg_inp = CapitalGainsIncome(
        ltcg_112a=ltcg_112a,
        cost_of_acquisition=cg_cost or Decimal("0"),
    ) if has_cg else None

    # Build deductions
    ded_kwargs = {
        "has_parents_senior": sen_parents,
        "schedule_80dd": Schedule80DD(disability_type="severe" if dd_severe else "normal"),
        "schedule_80u": Schedule80U(disability_type="severe" if u_severe else "normal"),
    }
    ded_kwargs.update(ded)
    ded_inp = Chapter6ADeductions(**ded_kwargs)

    # Build TDS entries
    tds1 = [TDS1Entry(
        employer_name="ABC Corp",
        income_chargeable=gross_salary if has_sal else Decimal("0"),
        tds_deducted=tds_salary,
    )] if has_tds_sal and tds_salary > 0 else None

    tds2 = [TDS2Entry(
        deductor_tan="DELA00001B",
        tds_section="194A",
        gross_amount=tds_other_gross,
        tds_deducted=tds_other,
    )] if has_tds_oth and tds_other > 0 else None

    tcs_e = [TCSEntry(
        collector_tan="DELA00001C",
        tcs_section="206C",
        gross_amount=tcs_total,
        tcs_collected=tcs_total,
    )] if tcs_total > 0 else None

    # Assemble ITR1Input
    inp = ITR1Input(
        age_bracket=AgeBracket(age_bracket),
        assessee_type=AssesseeType.INDIVIDUAL,
        tax_regime=TaxRegime(tax_regime),
        salary_income=sal,
        house_property_income=hp,
        other_sources_income=os_inp,
        deductions_chapter6a=ded_inp,
        capital_gains=cg_inp,
        tds1_entries=tds1,
        tds2_entries=tds2,
        tcs_entries=tcs_e,
        advance_tax_paid=advance_tax,
        advance_tax_q1=advance_q1,
        advance_tax_q2=advance_q2,
        advance_tax_q3=advance_q3,
        advance_tax_q4=advance_q4,
        self_assessment_tax_paid=self_assmt,
        filing_date=filing_date,
        due_date=due_date,
        relief_89=relief_89,
        agriculture_income=agri_income,
        is_resident=is_resident,
        is_director=is_director,
        has_foreign_assets=has_foreign,
        has_unlisted_equity=has_unlisted,
        house_property_count=hp_count,
    )

    result = compute_itr1(inp)

    # ── Errors / Warnings ─────────────────────────────────────────────────
    if result.errors:
        print(f"\n{RED}  ERRORS:{RESET}")
        for e in result.errors:
            print(f"    {RED}✗ {e}{RESET}")
        print(f"\n{RED}Cannot proceed — fix errors above.{RESET}")
        sys.exit(1)
    if result.warnings:
        print(f"\n{YELLOW}  WARNINGS:{RESET}")
        for w in result.warnings:
            print(f"    {YELLOW}⚠ {w}{RESET}")

    # ═══════════════════════════════════════════════════════════════════════
    # BREAKDOWN
    # ═══════════════════════════════════════════════════════════════════════
    header("TAX BREAKDOWN")

    def row(label, val, extra=""):
        print(f"  {label:<35s} {fmt(val):>14s}  {extra}")

    print(f"\n  {BOLD}INCOME HEADS{RESET}")
    row("Salary Income", result.salary_income)
    row("House Property Income", result.house_property_income)
    row("Other Sources Income", result.other_sources_income)
    row("Capital Gains (112A)", result.capital_gains_112a)
    row(f"{BOLD}GROSS TOTAL INCOME{RESET}", result.gross_total_income, f"{BOLD}⟸{RESET}")
    agri = getattr(result, "net_agricultural_income", Decimal("0"))
    if agri > 0:
        row("Net Agricultural Income", agri, "(for rate purposes)")

    print(f"\n  {BOLD}DEDUCTIONS{RESET}")
    ded_sched = result.schedules.get("deductions") if result.schedules else None
    breakdown = getattr(ded_sched, "breakdown", {}) if ded_sched else {}

    section_info = [
        ("80C+80CCC+80CCD(1)", "80C+80CCC+80CCD(1) pool (max ₹1,50,000 u/s 80CCE)", "amount_80c,amount_80ccc,amount_80ccd1"),
        ("80CCC",   "  ↳ 80CCC portion",      "amount_80ccc"),
        ("80CCD(1)","  ↳ 80CCD(1) portion",   "amount_80ccd1"),
        ("80CCD(1B)","80CCD(1B) — Additional NPS (max ₹50,000)", "amount_80ccd1b"),
        ("80CCD(2)", "80CCD(2) — Employer NPS", "amount_80ccd2"),
        ("80D",      "80D — Health Insurance (max ₹1,00,000)", "amount_80d_self_family,amount_80d_preventive_self,amount_80d_parents,amount_80d_preventive_parents"),
        ("80DD",     "80DD — Disabled Dependent", "amount_80dd"),
        ("80DDB",    "80DDB — Specified Disease",  "amount_80ddb"),
        ("80U",      "80U — Self Disability",     "amount_80u"),
        ("80TTA",    "80TTA — Savings Interest (max ₹10,000)", "amount_80tta"),
        ("80TTB",    "80TTB — Sr Citizen Deposit Interest",    "amount_80ttb"),
        ("80E",      "80E — Education Loan Interest",         "amount_80e"),
        ("80EE",     "80EE — First-time Home Loan (max ₹50,000)", "amount_80ee"),
        ("80EEA",    "80EEA — Affordable Housing Loan (max ₹1,50,000)", "amount_80eea"),
        ("80EEB",    "80EEB — Electric Vehicle Loan (max ₹1,50,000)", "amount_80eeb"),
        ("80G",      "80G — Donations",           "amount_80g"),
        ("80GG",     "80GG — Rent Paid (no HRA, max ₹60,000)", "amount_80gg"),
        ("80GGA",    "80GGA — Scientific Research/Rural Dev", "amount_80gga"),
        ("80GGC",    "80GGC — Political Contributions", "amount_80ggc"),
        ("80CCH",    "80CCH — Agniveer Corpus Fund",     "amount_80cch"),
    ]

    def _raw_sum(raw_keys: str) -> Decimal:
        return sum(ded.get(k, Decimal("0")) for k in raw_keys.split(","))

    for key, label, raw_keys in section_info:
        allowed = breakdown.get(key, Decimal("0"))
        if allowed > 0 or key in ("80C+80CCC+80CCD(1)", "80GGA"):
            if key == "80C+80CCC+80CCD(1)":
                raw_total = _raw_sum(raw_keys)
                if raw_total > allowed:
                    row(f"  ✓ {label}", allowed, f"{YELLOW}(claimed ₹{raw_total:,.0f}{RESET})")
                else:
                    row(f"  ✓ {label}", allowed)
            elif key in ("80CCC", "80CCD(1)"):
                row(f"  ✓ {label}", allowed)
            else:
                raw_val = _raw_sum(raw_keys)
                if raw_val > allowed and allowed > 0:
                    row(f"  ✓ {label}", allowed, f"{YELLOW}(claimed ₹{raw_val:,.0f}{RESET})")
                elif allowed > 0:
                    row(f"  ✓ {label}", allowed)
                else:
                    row(f"  — {label}", Decimal("0"))
    row(f"{BOLD}Chapter VI-A Total{RESET}", result.deductions_total)
    row(f"{BOLD}TAXABLE INCOME (r/o 10){RESET}", result.taxable_income, f"{BOLD}⟸ s.288A{RESET}")

    print(f"\n  {BOLD}TAX COMPUTATION{RESET}")
    row("Slab Tax", result.slab_tax)
    row("Special Rate Tax (112A @12.5%)", result.special_rate_tax)
    row(f"{BOLD}TAX BEFORE REBATE{RESET}", result.tax_before_rebate)
    row(f"  Less: Rebate u/s 87A", result.rebate_87a)
    row(f"{BOLD}TAX AFTER REBATE{RESET}", result.tax_after_rebate)
    row(f"  Add: Surcharge", result.surcharge)
    row(f"  Add: HEC @ 4%", result.health_education_cess)
    if result.relief_89 > 0:
        row(f"  Less: Relief u/s 89", result.relief_89)
    row(f"{BOLD}{GREEN}GROSS TAX LIABILITY{RESET}", result.gross_tax_liability, f"{BOLD}⟸{RESET}")

    print(f"\n  {BOLD}INTEREST & LATE FEE{RESET}")
    row("234A Interest", result.interest_234a)
    row("234B Interest", result.interest_234b)
    row("234C Interest", result.interest_234c)
    row("234F Late Filing Fee", result.late_fee_234f)
    row(f"{BOLD}Total Interest + Fee{RESET}", result.total_interest + result.late_fee_234f)

    print(f"\n  {BOLD}TAX PAYMENTS{RESET}")
    row("TDS", result.total_tds)
    row("TCS", result.total_tcs)
    row("Advance Tax", result.advance_tax_paid)
    row("Self-Assessment Tax", result.self_assessment_tax_paid)
    row(f"{BOLD}Total Taxes Paid{RESET}", result.total_taxes_paid)

    print(f"\n  {BOLD}{'─'*50}{RESET}")
    final_liab = result.net_tax_liability
    if result.balance_payable > 0:
        row(f"{BOLD}{RED}BALANCE PAYABLE{RESET}", result.balance_payable, f"{RED}⟸{RESET}")
    else:
        row(f"{BOLD}{GREEN}REFUND DUE{RESET}", result.refund_due, f"{GREEN}⟸{RESET}")
    row(f"Net Tax Liability", final_liab)

    # ═══════════════════════════════════════════════════════════════════════
    # ITD JSON
    # ═══════════════════════════════════════════════════════════════════════
    header("GENERATING ITD-COMPLIANT JSON")

    # Build form-16-style TDS salary entry dicts for JSON builder
    tds_sal_js = [{
        "TAN": "DELA00001A",
        "EmployerName": "ABC Corp",
        "IncChrgSal": int(gross_salary) if has_sal else 0,
        "TotalTDSSal": int(tds_salary),
    }] if has_tds_sal and tds_salary > 0 else None

    tds_oth_js = [{
        "TAN": "DELA00001B",
        "TDSSection": "194A",
        "AmtForTaxDeduct": int(tds_other_gross),
        "DeductedYr": "2025",
        "TotTDSOnAmtPaid": int(tds_other),
        "ClaimOutOfTotTDSOnAmtPaid": int(tds_other),
    }] if has_tds_oth and tds_other > 0 else None

    json_doc = build_itr1_json(
        result,
        pan=pan,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        dob=dob,
        employer_category=employer_category,
        residence_no=residence_no,
        locality=locality,
        city=city,
        state_code=state_code,
        country_code=country_code,
        mobile_no=mobile_no,
        email=email,
        aadhaar=aadhaar,
        secondary_add="N",
        pin_code=pin_code,
        opt_out_new_regime="N" if tax_regime == "old" else "Y",
        return_file_sec=return_file_sec,
        father_name=father_name,
        ver_place=ver_place,
        bank_name=bank_name,
        account_no=account_no,
        ifsc=ifsc,
        tds_salary_entries=tds_sal_js,
        tds_other_entries=tds_oth_js,
        hra_received=hra_received if has_sal else None,
        rent_paid=rent_paid if has_sal else None,
        hra_metro=hra_metro,
        schedule_80d_senior_self="Y" if sen_self else "N",
        schedule_80d_senior_parents="Y" if sen_parents else "N",
        schedule_80d_self_amt=ded.get("amount_80d_self_family", Decimal("0")),
        schedule_80d_parents_amt=ded.get("amount_80d_parents", Decimal("0")),
        cg_sale_consideration=cg_sale,
        cg_cost_acquisition=cg_cost,
    )

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(PROJECT_ROOT, f"ITR-1_{pan}_{timestamp}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(json_doc, f, indent=2, default=str)

    # Quick schema check
    itr1_body = json_doc.get("ITR", {}).get("ITR1", {})
    required = [
        "CreationInfo","Form_ITR1","PersonalInfo","FilingStatus",
        "ITR1_IncomeDeductions","ITR1_TaxComputation","TaxPaid","Refund","Verification",
    ]
    missing = [k for k in required if k not in itr1_body]

    print(f"\n  {GREEN}✓ JSON saved → {out_file}{RESET}")
    print(f"  Size: {len(json.dumps(json_doc)):,} bytes")
    print(f"  Digest: {itr1_body.get('CreationInfo',{}).get('Digest','MISSING')}")

    if missing:
        print(f"\n  {RED}✗ MISSING required sections: {missing}{RESET}")
    else:
        print(f"  {GREEN}✓ All 9 required top-level sections present{RESET}")

    # Spot-check critical fields
    checks = [
        ("PersonalInfo.PAN","PersonalInfo"),
        ("PersonalInfo.DOB","PersonalInfo"),
        ("FilingStatus.ReturnFileSec","FilingStatus"),
        ("FilingStatus.ItrFilingDueDate","FilingStatus"),
        ("ITR1_IncomeDeductions.GrossSalary","ITR1_IncomeDeductions"),
        ("ITR1_IncomeDeductions.TotalIncome","ITR1_IncomeDeductions"),
        ("ITR1_IncomeDeductions.DeductUndChapVIA","ITR1_IncomeDeductions"),
        ("ITR1_IncomeDeductions.UsrDeductUndChapVIA","ITR1_IncomeDeductions"),
        ("ITR1_TaxComputation.TotalTaxPayable","ITR1_TaxComputation"),
        ("ITR1_TaxComputation.TotTaxPlusIntrstPay","ITR1_TaxComputation"),
        ("TaxPaid.TaxesPaid","TaxPaid"),
        ("Refund.BankAccountDtls","Refund"),
        ("Verification.Declaration","Verification"),
    ]
    all_ok = True
    for field, section in checks:
        val = itr1_body.get(section, {}).get(field.split(".")[1], "MISSING")
        status = "✓" if val != "MISSING" else "✗"
        if val == "MISSING": all_ok = False
        print(f"    [{status}] {field}")

    # Check 80GGA (ITR-1 specific)
    deduct = itr1_body.get("ITR1_IncomeDeductions",{}).get("DeductUndChapVIA",{})
    print(f"    {'✓' if 'Section80GGA' in deduct else '✗'} DeductUndChapVIA.Section80GGA")

    header(f"{'ALL CHECKS PASSED' if all_ok else 'ISSUES FOUND — REVIEW ABOVE'}")
    print(f"\n  You can now validate {os.path.basename(out_file)} on the ITD UAT portal.\n")


if __name__ == "__main__":
    main()
