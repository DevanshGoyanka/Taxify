#!/usr/bin/env python
"""Quick schema compliance check for ITR-1 and ITR-4 builders."""
from __future__ import annotations
import json, os, sys
from dotenv import load_dotenv

PROJECT_ROOT = r"C:\Users\Devansh\Desktop\Taxify"
sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from decimal import Decimal
from datetime import date
from app.schemas.itr1 import (
    ITR1Input, SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions, AgeBracket, AssesseeType, TaxRegime, PropertyType,
)
from app.engine.calculators.itr1 import compute as compute_itr1
from app.engine.itd.itr1 import build_itr1_json

# ── ITR-1 ──
sal = SalaryIncome(gross_salary=Decimal("1180000"), standard_deduction_claimed=Decimal("75000"))
hp = HousePropertyIncome(
    property_type=PropertyType("S"), annual_rent_received=Decimal("0"),
    municipal_taxes_paid=Decimal("0"), home_loan_interest_paid=Decimal("0"),
)
inp = ITR1Input(
    age_bracket=AgeBracket("below_60"), assessee_type=AssesseeType("individual"),
    tax_regime=TaxRegime("new"), salary_income=sal, house_property_income=hp,
    other_sources_income=OtherSourcesIncome(),
    deductions_chapter6a=Chapter6ADeductions(),
    filing_date=date(2026, 7, 28), due_date=date(2026, 7, 31),
    house_property_count=1,
)
result = compute_itr1(inp)
print(f"ITR-1: taxable={result.taxable_income}, errors={result.errors}")

json_doc = build_itr1_json(
    result, pan="EPPPG3078Q", first_name="DEVANSH", last_name="GOYANKA",
    return_file_sec=11, opt_out_new_regime="Y",
)
itr1 = json_doc["ITR"]["ITR1"]

# Check all 9 required top-level sections
required = [
    "CreationInfo", "Form_ITR1", "PersonalInfo", "FilingStatus",
    "ITR1_IncomeDeductions", "ITR1_TaxComputation", "TaxPaid", "Refund", "Verification",
]
missing = [r for r in required if r not in itr1]
print(f"Required sections: {'OK' if not missing else 'MISSING: ' + str(missing)}")

# Check optional schedules (ITR-1 official schema list)
opt_schedules = [
    "Schedule80G", "Schedule80GGA", "Schedule80GGC", "Schedule80D",
    "Schedule80DD", "Schedule80U", "Schedule80E", "Schedule80EE",
    "Schedule80EEA", "Schedule80EEB", "Schedule80C", "ScheduleEA10_13A",
    "TDSonSalaries", "TDSonOthThanSals", "ScheduleTDS3Dtls",
    "ScheduleTCS", "TaxPayments", "LTCG112A", "TaxReturnPreparer",
]
present = [o for o in opt_schedules if o in itr1]
missing_opt = [o for o in opt_schedules if o not in itr1]
print(f"Optional schedules present: {len(present)}/19")

# Check for EXTRA sections NOT in official schema
official_all = set(required + opt_schedules)
actual = set(itr1.keys())
extra = actual - official_all
if extra:
    print(f"EXTRA SECTIONS (will be rejected!): {extra}")
else:
    print("No extra sections: OK")

# Check key required sub-fields
pi = itr1["PersonalInfo"]
assert "AssesseeName" in pi
assert "PAN" in pi
assert "Address" in pi
assert "SecondaryAdd" in pi
assert "DOB" in pi
assert "EmployerCategory" in pi
print("PersonalInfo: required fields OK")

fs = itr1["FilingStatus"]
assert "ReturnFileSec" in fs
assert "OptOutNewTaxRegime" in fs
assert "AsseseeRepFlg" in fs
assert "ItrFilingDueDate" in fs
assert fs["ItrFilingDueDate"] == "2026-07-31"
print("FilingStatus: required fields OK, due date correct")

ide = itr1["ITR1_IncomeDeductions"]
assert "GrossSalary" in ide
assert "NetSalary" in ide
assert "DeductionUs16" in ide
assert "IncomeFromSal" in ide
assert "IncomeOthSrc" in ide
assert "GrossTotIncome" in ide
assert "GrossTotIncomeIncLTCG112A" in ide
assert "UsrDeductUndChapVIA" in ide
assert "DeductUndChapVIA" in ide
assert "TotalIncome" in ide
# No IncomeFromBusinessProf
assert "IncomeFromBusinessProf" not in ide
print("IncomeDeductions: required fields OK, no business prof (correct for ITR-1)")

tc = itr1["ITR1_TaxComputation"]
for f in ["TotalTaxPayable", "Rebate87A", "TaxPayableOnRebate", "EducationCess",
          "GrossTaxLiability", "Section89", "NetTaxLiability", "TotalIntrstPay",
          "IntrstPay", "TotTaxPlusIntrstPay"]:
    assert f in tc, f"MISSING TaxComputation.{f}"
print("TaxComputation: all required fields OK")

# Refund
ref = itr1["Refund"]
assert "RefundDue" in ref
assert "BankAccountDtls" in ref
print("Refund: required fields OK")

# Verification
ver = itr1["Verification"]
assert "Declaration" in ver
assert "Capacity" in ver
assert "Place" in ver
print("Verification: required fields OK")

sw = itr1["CreationInfo"]["SWCreatedBy"]
digest = itr1["CreationInfo"]["Digest"]
print(f"SWCreatedBy: {sw}")
print(f"Digest: {digest[:20]}... ({len(digest)} chars)")

# ITR-4 specific checks NOT present
assert "ScheduleBP" not in itr1
assert "ScheduleIT" not in itr1
assert "TaxExmpIntIncDtls" not in itr1
print("No ITR-4 bleed-through: OK")

print("\n=== ITR-1 SCHEMA COMPLIANCE: ALL CHECKS PASSED ===")

# ── ITR-4 ──
from app.schemas.itr4 import (
    ITR4Input, PresumptiveScheme, PresumptiveBusinessIncome44AD,
)
from app.engine.calculators.itr4 import compute as compute_itr4
from app.engine.itd.itr4 import build_itr4_json

biz = PresumptiveBusinessIncome44AD(
    total_turnover=Decimal("2500000"), digital_turnover=Decimal("2000000"),
    cash_turnover=Decimal("500000"),
)
inp4 = ITR4Input(
    age_bracket=AgeBracket("below_60"), assessee_type=AssesseeType("individual"),
    tax_regime=TaxRegime("new"), presumptive_scheme=PresumptiveScheme("44AD"),
    business_income_44ad=biz, salary_income=sal, house_property_income=hp,
    other_sources_income=OtherSourcesIncome(),
    deductions_chapter6a=Chapter6ADeductions(),
    filing_date=date(2026, 7, 28), due_date=date(2026, 7, 31),
    house_property_count=1,
)
result4 = compute_itr4(inp4)
print(f"\nITR-4: presumptive={result4.presumptive_income}, taxable={result4.taxable_income}, errors={result4.errors}")

json_doc4 = build_itr4_json(
    result4, pan="EPPPG3078Q", first_name="DEVANSH", last_name="GOYANKA",
    dob="2006-06-01", itr4_return_file_sec=11, assesee_status="I",
    phone_std_code=0, phone_no="0",
    bp_gross_turnover=Decimal("2500000"), bp_digital_turnover=Decimal("2000000"),
    bp_cash_turnover=Decimal("500000"), bp_other_turnover=Decimal("0"),
    bp_scheme="44AD",
)
itr4 = json_doc4["ITR"]["ITR4"]

# Check all 9 required sections
req4 = [
    "CreationInfo", "Form_ITR4", "PersonalInfo", "FilingStatus",
    "IncomeDeductions", "TaxComputation", "TaxPaid", "Refund", "Verification",
]
missing4 = [r for r in req4 if r not in itr4]
print(f"Required sections: {'OK' if not missing4 else 'MISSING: ' + str(missing4)}")

# Check optional ITR-4 sections
opt4 = [
    "Schedule80G", "Schedule80GGC", "Schedule80DD", "Schedule80U",
    "Schedule80E", "Schedule80EE", "Schedule80EEA", "Schedule80EEB",
    "Schedule80C", "ScheduleEA10_13A", "Schedule80D", "TaxExmpIntIncDtls",
    "LTCG112A", "TaxReturnPreparer", "ScheduleBP", "ScheduleIT",
    "ScheduleTCS", "TDSonSalaries", "TDSonOthThanSals", "ScheduleTDS3Dtls",
]
present4 = [o for o in opt4 if o in itr4]
missing_opt4 = [o for o in opt4 if o not in itr4]
print(f"Optional present: {len(present4)}/20")

# CRITICAL: Schedule80GGA should NOT be present in ITR-4
assert "Schedule80GGA" not in itr4, "ITR-4 has Schedule80GGA but it should NOT!"
print("Schedule80GGA absent (correct for ITR-4): OK")

# PersonalInfo.Status
assert itr4["PersonalInfo"]["Status"] == "I"
print("PersonalInfo.Status: OK")

# IncomeDeductions has IncomeFromBusinessProf
assert "IncomeFromBusinessProf" in itr4["IncomeDeductions"]
print("IncomeDeductions.IncomeFromBusinessProf: OK")

# TaxExmpIntIncDtls present
assert "TaxExmpIntIncDtls" in itr4
assert "ScheduleBP" in itr4
assert "ScheduleIT" in itr4
print("TaxExmpIntIncDtls, ScheduleBP, ScheduleIT: all present OK")

# FilingStatus has Form10IEA, not OptOutNewTaxRegime
fs4 = itr4["FilingStatus"]
assert "Form10IEAEarlierAYOldRegime" in fs4
assert "OptOutNewTaxRegime" not in fs4
print("FilingStatus: Form10IEA (correct), no OptOutNewTaxRegime (correct)")

# Address.Phone
addr = itr4["PersonalInfo"]["Address"]
assert "Phone" in addr
print("Address.Phone: OK")

digest4 = itr4["CreationInfo"]["Digest"]
print(f"Digest: {digest4[:20]}... ({len(digest4)} chars)")

print("\n=== ITR-4 SCHEMA COMPLIANCE: ALL CHECKS PASSED ===")
