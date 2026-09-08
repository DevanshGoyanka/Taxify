"""Validate Taxify ITD JSON output against official CBDT schemas."""
import json
import os
import sys
from decimal import Decimal
from datetime import date

# Make ``import app...`` work when this is run directly from tests/.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import jsonschema
from jsonschema import validate, Draft4Validator, ValidationError

from app.engine.itd import build_itr2_json, build_itr3_json, build_itr4_json
from app.engine.calculators.itr2 import compute as c2
from app.engine.calculators.itr3 import compute as c3
from app.engine.calculators.itr4 import compute as c4
from app.schemas.itr1 import (SalaryIncome, HousePropertyIncome,
                               OtherSourcesIncome, Chapter6ADeductions,
                               PropertyType, AgeBracket, TaxRegime)
from app.schemas.itr2 import (ITR2Input, CGTransaction, CGAssetType,
                               CG112AScrip, VDATransaction, BFLossItem)
from app.schemas.itr4 import (ITR4Input, PresumptiveScheme,
                               PresumptiveBusinessIncome44AD)

# ITR-1 is validated through the real production pipeline (draft -> mapper ->
# calculator -> JSON builder, via filing_gateway_v2.generate_cbdt_json) below,
# against the schema shipped in this repo -- not a hand-built minimal
# ITR1Input against a hardcoded local Downloads path, which is what this file
# used to do for all four forms and why it previously could not run: the
# hardcoded Downloads paths for ITR-2/3/4 are this machine's, not portable,
# and the minimal ITR1Input never carried the filing_profile/bank_accounts
# now required to build the official JSON (see
# Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §17.1). ITR-2/3/4
# are left on their original hand-built-minimal-input approach and hardcoded
# paths -- out of scope for the current ITR-1 audit pass; each fixture would
# need its own update to current schema field names to run again (see the
# module docstring's "not part of this pass" note below).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS = {
    "ITR-1": os.path.join(
        _REPO_ROOT, "Reference Docs by CBDT & ITD", "Official JSON Schema",
        "ITR-1_2026_Main_V1.1 (2).json",
    ),
    "ITR-2": r"C:\Users\Devansh\Downloads\ITR-2_2026_Main_V1.1 (1).json",
    "ITR-3": r"C:\Users\Devansh\Downloads\ITR-3_2026_Main_V1.1 (1).json",
    "ITR-4": r"C:\Users\Devansh\Downloads\ITR-4_2026_Main_V1.1 (1).json",
}


def validate_json(itr_output, schema_path):
    with open(schema_path) as f:
        schema = json.load(f)
    errors = list(Draft4Validator(schema).iter_errors(itr_output))
    return errors


def error_summary(errors, label):
    if not errors:
        print(f"  {label}: PASS (0 errors)")
        return
    print(f"  {label}: FAIL ({len(errors)} errors)")
    for e in errors[:20]:
        path = " / ".join(str(p) for p in e.absolute_path)
        print(f"    {path}: {e.message}")


def test_itr1():
    """Exercise the real production pipeline (draft -> mapper -> calculator ->
    JSON builder via filing_gateway_v2.generate_cbdt_json), not a hand-built
    minimal ITR1Input -- see the SCHEMAS comment above for why."""
    from decimal import Decimal as _D
    from app.schemas.return_draft import (
        ReturnDraft, create_empty_draft, Employer, HouseProperty, BankAccount,
        InterestIncome, Investment80C, HomeLoan,
    )
    from app.engine import filing_gateway_v2 as gateway

    draft = create_empty_draft("2026-27", "ITR-1", "old")
    p = draft.personal
    p.name = "Rahul Kumar Sharma"
    p.firstName = "Rahul"
    p.surnameOrOrgName = "Sharma"
    p.fatherName = "Mohan Sharma"
    p.pan = "ABCDE1234F"
    p.email = "rahul@example.com"
    p.mobile = "9876543210"
    p.dateOfBirth = "1980-01-15"
    p.flatNo = "12A"
    p.localityOrArea = "Central Delhi"
    p.city = "Delhi"
    p.stateCode = "07"
    p.countryCode = "91"
    p.pinCode = "110001"
    p.employerCategory = "OTH"

    draft.verification.place = "Delhi"
    draft.verification.date = "2026-07-25"
    draft.verification.declarationAccepted = True
    draft.verification.capacity = "SELF"

    draft.employers = [Employer(
        id="e1", employerName="Acme Corp", employerTAN="MUMA12345B",
        natureOfEmployment="OTH", employerAddress="123 Business Park",
        employerCity="Mumbai", employerStateCode="27", employerPinCode="400001",
        basic=_D("900000"), da=_D("50000"),
        tdsDeducted=_D("80000"), professionalTax=_D("2500"),
    )]
    draft.houseProperties = [HouseProperty(
        id="hp1", name="Flat 401", propertyType="SELF_OCCUPIED",
        address="401, Sunrise Apartments", city="Mumbai", state="27",
        pinCode="400001", interestOnLoan=_D("150000"),
        homeLoans=[HomeLoan(
            lenderType="B", lenderName="HDFC Bank", loanAccountNo="HL123456",
            dateOfLoan="2019-06-01", totalLoanAmount=_D("2000000"),
            loanOutstandingAmount=_D("1500000"), interestUs24B=_D("150000"),
        )],
    )]
    draft.otherSources.interest = [
        InterestIncome(id="i1", kind="SAVINGS_BANK", grossAmount=_D("15000")),
        InterestIncome(id="i2", kind="TERM_DEPOSIT", grossAmount=_D("35000")),
    ]
    draft.deductions.section80C = [Investment80C(
        id="c1", investmentType="EPF", amount=_D("150000"),
        identificationNo="PF1234567",
    )]
    draft.deductions.chapterVIA.section80D = _D("25000")
    draft.deductions.chapterVIA.section80TTA = _D("10000")
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="State Bank of India", accountNumber="1234567890123",
        ifscCode="SBIN0001234", accountType="SB", useForRefund=True,
    )]

    official, _summary = gateway.generate_cbdt_json(draft)
    return validate_json(official, SCHEMAS["ITR-1"])


def test_itr4():
    si = SalaryIncome(gross_salary=Decimal("500000"), perquisites_value=Decimal("20000"),
                       profits_in_lieu_of_salary=Decimal("5000"), professional_tax_paid=Decimal("2500"))
    hpi = HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED,
                               home_loan_interest_paid=Decimal("100000"))
    osi = OtherSourcesIncome(savings_bank_interest=Decimal("5000"))
    ded = Chapter6ADeductions(amount_80c=Decimal("100000"))
    biz = PresumptiveBusinessIncome44AD(total_turnover=Decimal("3000000"),
                                         digital_turnover=Decimal("2800000"),
                                         cash_turnover=Decimal("200000"))
    inp = ITR4Input(age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
                    presumptive_scheme=PresumptiveScheme.S44AD,
                    business_income_44ad=biz, salary_income=si,
                    house_property_income=hpi, other_sources_income=osi,
                    deductions_chapter6a=ded,
                    advance_tax_paid=Decimal("30000"),
                    self_assessment_tax_paid=Decimal("5000"))
    r = c4(inp)
    j = build_itr4_json(r)
    return validate_json(j, SCHEMAS["ITR-4"])


def test_itr3():
    from app.schemas.itr3 import ITR3Input, BusinessIncome
    bi = BusinessIncome(net_profit_before_tax=Decimal("500000"))
    si = SalaryIncome(gross_salary=Decimal("800000"), professional_tax_paid=Decimal("2500"))
    hpi = HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED,
                               home_loan_interest_paid=Decimal("200000"))
    osi = OtherSourcesIncome(savings_bank_interest=Decimal("20000"),
                              fixed_deposit_interest=Decimal("50000"))
    ded = Chapter6ADeductions(amount_80c=Decimal("150000"),
                               amount_80d_self_family=Decimal("25000"))
    cg_tx = [CGTransaction(asset_type=CGAssetType.LISTED_EQUITY_111A,
              full_consideration=Decimal("500000"),
              cost_of_acquisition=Decimal("300000"),
              date_of_acquisition=date(2024, 1, 15),
              date_of_transfer=date(2025, 10, 20))]
    bfl = [BFLossItem(assessment_year="2024", head="HouseProperty",
            original_loss=Decimal("150000"), brought_forward=Decimal("150000"))]
    inp = ITR3Input(age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
                    business_income=bi, salary_income=si,
                    house_property_income=hpi, other_sources_income=osi,
                    cg_transactions=cg_tx, bf_losses=bfl,
                    deductions_chapter6a=ded,
                    advance_tax_paid=Decimal("100000"),
                    filing_date=date(2026, 7, 15), due_date=date(2026, 7, 31))
    r = c3(inp)
    j = build_itr3_json(r)
    return validate_json(j, SCHEMAS["ITR-3"])


def test_itr2():
    si = SalaryIncome(gross_salary=Decimal("1500000"), professional_tax_paid=Decimal("2500"))
    hpi = HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED,
                               home_loan_interest_paid=Decimal("200000"))
    osi = OtherSourcesIncome(savings_bank_interest=Decimal("20000"),
                              fixed_deposit_interest=Decimal("50000"))
    ded = Chapter6ADeductions(amount_80c=Decimal("150000"),
                               amount_80d_self_family=Decimal("25000"),
                               amount_80tta=Decimal("10000"))
    cg_tx = [CGTransaction(asset_type=CGAssetType.LISTED_EQUITY_111A,
              full_consideration=Decimal("500000"),
              cost_of_acquisition=Decimal("300000"),
              date_of_acquisition=date(2024, 1, 15),
              date_of_transfer=date(2025, 10, 20))]
    scrip = [CG112AScrip(total_sale_value=Decimal("200000"),
              cost_acq_without_index=Decimal("100000"),
              total_fmv=Decimal("110000"))]
    vda = [VDATransaction(date_of_acquisition=date(2024, 6, 1),
            date_of_transfer=date(2025, 3, 15),
            acquisition_cost=Decimal("500000"),
            consideration_received=Decimal("800000"))]
    bfl = [BFLossItem(assessment_year="2024", head="HouseProperty",
            original_loss=Decimal("150000"), brought_forward=Decimal("150000"))]
    inp = ITR2Input(age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
                    salary_income=si, house_property_income=hpi,
                    other_sources_income=osi, cg_transactions=cg_tx,
                    cg_112a_scrips=scrip, vda_transactions=vda,
                    bf_losses=bfl, deductions_chapter6a=ded,
                    advance_tax_paid=Decimal("100000"),
                    filing_date=date(2026, 7, 15), due_date=date(2026, 7, 31))
    r = c2(inp)
    j = build_itr2_json(r)
    return validate_json(j, SCHEMAS["ITR-2"])


if __name__ == "__main__":
    print("Validating against CBDT schemas...\n")

    print("ITR-1:")
    errs1 = test_itr1()
    error_summary(errs1, "ITR-1")

    print("\nITR-4:")
    errs4 = test_itr4()
    error_summary(errs4, "ITR-4")

    print("\nITR-2:")
    errs2 = test_itr2()
    error_summary(errs2, "ITR-2")

    print("\nITR-3:")
    errs3 = test_itr3()
    error_summary(errs3, "ITR-3")

    total = len(errs1) + len(errs2) + len(errs3) + len(errs4)
    print(f"\nTotal schema violations: {total}")
    sys.exit(0 if total == 0 else 1)
