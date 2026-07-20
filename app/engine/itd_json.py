"""
ITD JSON Output Builder.

Converts internal Taxify computation results into ITD-compliant JSON for
each ITR form.  Every field in the output is present — even when its value
is zero or an empty array — so the JSON passes the ITD schema validator
(`additionalProperties: false`).

Key conversions
---------------
* Decimal (rupees) → integer (paise) via ``_to_paise()``
* snake_case → CamelCase (hard-coded per field to avoid ambiguity)
* Missing optional schemas are populated with their required defaults

Not Yet Implemented
-------------------
* ITR-2  ``build_itr2_json()``
* ITR-3  ``build_itr3_json()``
These will be added in a follow-up when the ITR-2 / ITR-3 calculators produce
full results that include the additional schedules those forms require.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from app.engine.calculators.itr1 import ITR1Result
from app.engine.calculators.itr4 import ITR4Result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_paise(val: Decimal) -> int:
    """Convert a rupee Decimal to integer paise: Rs 1,500.50 → 150050."""
    return int(round(val * 100))


def _zero_if_none(val: Optional[Decimal]) -> Decimal:
    return val if val is not None else Decimal("0")


def _str_or(val: Any, default: str = "") -> str:
    return str(val) if val is not None else default


def _today() -> str:
    return date.today().isoformat()


def _compute_digest(data: dict) -> str:
    """Compute a 44-character digest for the CreationInfo.Digest field."""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Shared sections (identical across all ITR forms)
# ---------------------------------------------------------------------------

_SW_VERSION = "1.0"
_SW_CODE = "SW00000001"


def _creation_info() -> dict:
    return {
        "SWVersionNo": _SW_VERSION,
        "SWCreatedBy": _SW_CODE,
        "JSONCreatedBy": _SW_CODE,
        "JSONCreationDate": _today(),
        "IntermediaryCity": "Delhi",
        "Digest": "-" * 44,
    }


def _verification(assessee_name: str, father_name: str, pan: str, place: str) -> dict:
    return {
        "Declaration": {
            "AssesseeVerName": _str_or(assessee_name, "ASSESSEE"),
            "FatherName": _str_or(father_name, "FATHER"),
            "AssesseeVerPAN": _str_or(pan, "AAAAA0000A"),
        },
        "Capacity": "S",
        "Place": _str_or(place, "Delhi"),
    }


# ---------------------------------------------------------------------------
# PersonalInfo builder
# ---------------------------------------------------------------------------

def _personal_info(
    pan: str,
    first_name: str,
    middle_name: str,
    last_name: str,
    dob: str,
    employer_category: str,
    residence_no: str,
    locality: str,
    city: str,
    state_code: str,
    country_code: str,
    mobile_no: Optional[str] = None,
    email: Optional[str] = None,
    aadhaar: Optional[str] = None,
    secondary_add: str = "N",
    pin_code: Optional[str] = None,
) -> dict:
    result: dict[str, Any] = {
        "AssesseeName": {
            "FirstName": first_name or "",
            "MiddleName": middle_name or "",
            "SurNameOrOrgName": last_name or "ASSESSEE",
        },
        "PAN": pan.upper(),
        "Address": {
            "ResidenceNo": _str_or(residence_no, "1"),
            "ResidenceName": "",
            "RoadOrStreet": "",
            "LocalityOrArea": _str_or(locality, "Locality"),
            "CityOrTownOrDistrict": _str_or(city, "City"),
            "StateCode": _str_or(state_code, "07"),
            "CountryCode": _str_or(country_code, "91"),
            "PinCode": int(pin_code) if pin_code and pin_code.isdigit() else 110001,
            "ZipCode": "",
            "CountryCodeMobile": 91,
            "MobileNo": int(mobile_no) if mobile_no and mobile_no.isdigit() else 9999999999,
            "CountryCodeMobileNoSec": 0,
            "MobileNoSec": 0,
            "EmailAddress": _str_or(email, "assessee@example.com"),
            "EmailAddressSec": "",
        },
        "SecondaryAdd": secondary_add,
        "DOB": _str_or(dob, "1990-01-01"),
        "EmployerCategory": _str_or(employer_category, "OTH"),
    }
    if aadhaar:
        result["AadhaarCardNo"] = aadhaar
    if secondary_add == "Y":
        result["AlternateAddress"] = {
            "ResidenceNo": _str_or(residence_no, "1"),
            "ResidenceName": "",
            "RoadOrStreet": "",
            "LocalityOrArea": _str_or(locality, "Locality"),
            "CityOrTownOrDistrict": _str_or(city, "City"),
            "StateCode": _str_or(state_code, "07"),
            "CountryCode": _str_or(country_code, "91"),
            "PinCode": int(pin_code) if pin_code and pin_code.isdigit() else 110001,
            "ZipCode": "",
        }
    return result


# ---------------------------------------------------------------------------
# FilingStatus builder
# ---------------------------------------------------------------------------

def _filing_status(opt_out_new_regime: str, return_file_sec: int = 11) -> dict:
    return {
        "ReturnFileSec": return_file_sec,
        "OptOutNewTaxRegime": opt_out_new_regime,
        "SeventhProvisio139": "N",
        "AsseseeRepFlg": "N",
        "ItrFilingDueDate": "2026-07-31",
    }


# ---------------------------------------------------------------------------
# Form_ITRx builder
# ---------------------------------------------------------------------------

def _form_itr(form_name: str) -> dict:
    return {
        "FormName": form_name,
        "Description": f"For AY 2026-27",
        "AssessmentYear": "2026",
        "SchemaVer": "Ver1.0",
        "FormVer": "Ver1.0",
    }


# ---------------------------------------------------------------------------
# DeductUndChapVIA / UsrDeductUndChapVIA (both share the same structure)
# ---------------------------------------------------------------------------

def _chapter_via(
    deductions_total: Decimal,
    ded_80c: Decimal = Decimal("0"),
    ded_80ccc: Decimal = Decimal("0"),
    ded_80ccd1: Decimal = Decimal("0"),
    ded_80ccd1b: Decimal = Decimal("0"),
    ded_80ccd2: Decimal = Decimal("0"),
    ded_80d: Decimal = Decimal("0"),
    ded_80dd: Decimal = Decimal("0"),
    ded_80ddb: Decimal = Decimal("0"),
    ded_80e: Decimal = Decimal("0"),
    ded_80ee: Decimal = Decimal("0"),
    ded_80eea: Decimal = Decimal("0"),
    ded_80eeb: Decimal = Decimal("0"),
    ded_80g: Decimal = Decimal("0"),
    ded_80gg: Decimal = Decimal("0"),
    ded_80gga: Decimal = Decimal("0"),
    ded_80ggc: Decimal = Decimal("0"),
    ded_80u: Decimal = Decimal("0"),
    ded_80tta: Decimal = Decimal("0"),
    ded_80ttb: Decimal = Decimal("0"),
    ded_80cch: Decimal = Decimal("0"),
) -> dict:
    return {
        "Section80C": _to_paise(ded_80c),
        "Section80CCC": _to_paise(ded_80ccc),
        "Section80CCDEmployeeOrSE": _to_paise(ded_80ccd1),
        "Section80CCD1B": _to_paise(ded_80ccd1b),
        "Section80CCDEmployer": _to_paise(ded_80ccd2),
        "Section80D": _to_paise(ded_80d),
        "Section80DD": _to_paise(ded_80dd),
        "Section80DDB": _to_paise(ded_80ddb),
        "Section80E": _to_paise(ded_80e),
        "Section80EE": _to_paise(ded_80ee),
        "Section80EEA": _to_paise(ded_80eea),
        "Section80EEB": _to_paise(ded_80eeb),
        "Section80G": _to_paise(ded_80g),
        "Section80GG": _to_paise(ded_80gg),
        "Section80GGA": _to_paise(ded_80gga),
        "Section80GGC": _to_paise(ded_80ggc),
        "Section80U": _to_paise(ded_80u),
        "Section80TTA": _to_paise(ded_80tta),
        "Section80TTB": _to_paise(ded_80ttb),
        "AnyOthSec80CCH": _to_paise(ded_80cch),
        "TotalChapVIADeductions": _to_paise(deductions_total),
    }


def _income_deductions(
    gross_salary: Decimal,
    net_salary: Decimal,
    ded_us16: Decimal,
    ded_us16ia: Decimal,
    ded_us16ii: Decimal,
    ded_us16iii: Decimal,
    income_from_sal: Decimal,
    income_hp: Decimal,
    income_os: Decimal,
    gti: Decimal,
    gti_cg: Decimal,
    total_income: Decimal,
    deductions_total: Decimal,
    hp_schedules: Optional[list[dict]] = None,
) -> dict:
    result: dict[str, Any] = {
        "GrossSalary": _to_paise(gross_salary),
        "Salary": _to_paise(net_salary + ded_us16),
        "PerquisitesValue": 0,
        "ProfitsInSalary": 0,
        "AllwncExemptUs10": {
            "AllwncExemptUs10Dtls": [],
            "TotalAllwncExemptUs10": 0,
        },
        "NetSalary": _to_paise(net_salary),
        "DeductionUs16": _to_paise(ded_us16),
        "DeductionUs16ia": _to_paise(ded_us16ia),
        "EntertainmentAlw16ii": _to_paise(ded_us16ii),
        "ProfessionalTaxUs16iii": _to_paise(ded_us16iii),
        "IncomeFromSal": _to_paise(income_from_sal),
        "PropertyDetails": hp_schedules or [],
        "TotalIncomeChargeableUnHP": _to_paise(income_hp),
        "IncomeOthSrc": _to_paise(income_os),
        "OthersInc": {
            "OthersIncDtlsOthSrc": [],
        },
        "DeductionUs57iia": 0,
        "GrossTotIncome": _to_paise(gti),
        "GrossTotIncomeIncLTCG112A": _to_paise(gti_cg),
        "UsrDeductUndChapVIA": _chapter_via(deductions_total),
        "DeductUndChapVIA": _chapter_via(deductions_total),
        "TotalIncome": _to_paise(total_income),
        "ExemptIncAgriOthUs10": {
            "ExemptIncAgriOthUs10Dtls": [],
            "ExemptIncAgriOthUs10Total": 0,
        },
    }
    return result


def _tax_computation(
    slab_tax: Decimal,
    rebate_87a: Decimal,
    tax_after_rebate: Decimal,
    surcharge: Decimal,
    cess: Decimal,
    gross_tax_liability: Decimal,
    net_tax_liability: Decimal,
    relief_89: Decimal,
    total_interest: Decimal,
    interest_234a: Decimal,
    interest_234b: Decimal,
    interest_234c: Decimal,
    late_fee_234f: Decimal,
) -> dict:
    total_tax_payable = slab_tax  # slab + special rate combined
    return {
        "TotalTaxPayable": _to_paise(total_tax_payable),
        "Rebate87A": _to_paise(rebate_87a),
        "TaxPayableOnRebate": _to_paise(tax_after_rebate),
        "EducationCess": _to_paise(cess),
        "GrossTaxLiability": _to_paise(gross_tax_liability),
        "Section89": _to_paise(relief_89),
        "NetTaxLiability": _to_paise(net_tax_liability),
        "TotalIntrstPay": _to_paise(total_interest + late_fee_234f),
        "IntrstPay": {
            "IntrstPayUs234A": _to_paise(interest_234a),
            "IntrstPayUs234B": _to_paise(interest_234b),
            "IntrstPayUs234C": _to_paise(interest_234c),
            "LateFilingFee234F": _to_paise(late_fee_234f),
            "FeeFurnish234I": 0,
        },
        "TotTaxPlusIntrstPay": _to_paise(
            gross_tax_liability + total_interest + late_fee_234f
        ),
    }


def _tax_paid_section(
    total_tds: Decimal,
    total_tcs: Decimal,
    advance_tax: Decimal,
    self_assessment_tax: Decimal,
    balance_payable: Decimal,
) -> dict:
    total_paid = total_tds + total_tcs + advance_tax + self_assessment_tax
    return {
        "TaxesPaid": {
            "AdvanceTax": _to_paise(advance_tax),
            "TDS": _to_paise(total_tds),
            "TCS": _to_paise(total_tcs),
            "SelfAssessmentTax": _to_paise(self_assessment_tax),
            "TotalTaxesPaid": _to_paise(total_paid),
        },
        "BalTaxPayable": _to_paise(balance_payable),
    }


def _refund_section(
    refund_due: Decimal,
    bank_name: str = "BankName",
    account_no: str = "0000000000",
    ifsc: str = "SBIN0000001",
) -> dict:
    return {
        "RefundDue": _to_paise(refund_due),
        "BankAccountDtls": {
            "AddtnlBankDetails": [
                {
                    "IFSCCode": _str_or(ifsc, "SBIN0000001"),
                    "BankName": _str_or(bank_name, "BankName"),
                    "BankAccountNo": _str_or(account_no, "0000000000"),
                    "AccountType": "SB",
                    "UseForRefund": "true",
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Optional schedule builders
# ---------------------------------------------------------------------------

def _schedule_80d(
    senior_flag_self: str,
    senior_flag_parents: str,
    self_amt: Decimal,
    parents_amt: Decimal,
    eligible_deduction: Decimal,
) -> dict:
    return {
        "Sec80DSelfFamSrCtznHealth": {
            "SeniorCitizenFlag": senior_flag_self,
            "SelfAndFamily": _to_paise(self_amt) if senior_flag_self == "N" else 0,
            "HealthInsPremSlfFam": _to_paise(self_amt) if senior_flag_self == "N" else 0,
            "Sec80DSelfFamHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_paise(self_amt) if senior_flag_self == "N" else 0,
            },
            "PrevHlthChckUpSlfFam": 0,
            "SelfAndFamilySeniorCitizen": _to_paise(self_amt) if senior_flag_self in ("Y", "S") else 0,
            "HlthInsPremSlfFamSrCtzn": _to_paise(self_amt) if senior_flag_self in ("Y", "S") else 0,
            "Sec80DSelfFamSrCtznHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_paise(self_amt) if senior_flag_self in ("Y", "S") else 0,
            },
            "PrevHlthChckUpSlfFamSrCtzn": 0,
            "MedicalExpSlfFamSrCtzn": 0,
            "ParentsSeniorCitizenFlag": senior_flag_parents,
            "Parents": _to_paise(parents_amt) if senior_flag_parents == "N" else 0,
            "HlthInsPremParents": _to_paise(parents_amt) if senior_flag_parents == "N" else 0,
            "Sec80DParentsHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_paise(parents_amt) if senior_flag_parents == "N" else 0,
            },
            "PrevHlthChckUpParents": 0,
            "ParentsSeniorCitizen": _to_paise(parents_amt) if senior_flag_parents in ("Y", "P") else 0,
            "HlthInsPremParentsSrCtzn": _to_paise(parents_amt) if senior_flag_parents in ("Y", "P") else 0,
            "Sec80DParentsSrCtznHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_paise(parents_amt) if senior_flag_parents in ("Y", "P") else 0,
            },
            "PrevHlthChckUpParentsSrCtzn": 0,
            "MedicalExpParentsSrCtzn": 0,
            "EligibleAmountOfDedn": _to_paise(eligible_deduction),
        }
    }


def _schedule_80c(total_amt: Decimal) -> dict:
    return {
        "Schedule80CDtls": [],
        "TotalAmt": _to_paise(total_amt),
    }


def _schedule_80g(total_donations_cash: Decimal, total_donations_other: Decimal) -> dict:
    return {
        "Don100Percent": {
            "DoneeWithPan": [],
            "TotDon100PercentCash": 0,
            "TotDon100PercentOtherMode": 0,
            "TotDon100Percent": 0,
            "TotEligibleDon100Percent": 0,
        },
        "Don50PercentNoApprReqd": {
            "DoneeWithPan": [],
            "TotDon50PercentNoAppReqCash": 0,
            "TotDon50PercentNoAppReqOtherMode": 0,
            "TotDon50PercentNoAppReq": 0,
            "TotEligibleDon50PercentNoAppReq": 0,
        },
        "Don100PercentApprReqd": {
            "DoneeWithPan": [],
            "TotDon100PercentAppReqCash": 0,
            "TotDon100PercentAppReqOtherMode": 0,
            "TotDon100PercentAppReq": 0,
            "TotEligibleDon100PercentAppReq": 0,
        },
        "Don50PercentApprReqd": {
            "DoneeWithPan": [],
            "TotDon50PercentAppReqCash": 0,
            "TotDon50PercentAppReqOtherMode": 0,
            "TotDon50PercentAppReq": 0,
            "TotEligibleDon50PercentAppReq": 0,
        },
        "TotalDonationsUs80GCash": _to_paise(total_donations_cash),
        "TotalDonationsUs80GOtherMode": _to_paise(total_donations_other),
        "TotalDonationsUs80G": _to_paise(total_donations_cash + total_donations_other),
        "TotalEligibleDonationsUs80G": 0,
    }


def _tds_salary_schedule(tds_salary_entries: Optional[list[dict]] = None) -> dict:
    entries = tds_salary_entries or []
    total = sum(
        (e.get("TotalTDSSal", 0) if isinstance(e, dict) else 0) for e in entries
    )
    return {
        "TDSonSalary": [
            {
                "EmployerOrDeductorOrCollectDetl": {
                    "TAN": e.get("TAN", "DELA00001A"),
                    "EmployerOrDeductorOrCollecterName": e.get("EmployerName", "Employer"),
                },
                "IncChrgSal": e.get("IncChrgSal", 0),
                "TotalTDSSal": e.get("TotalTDSSal", 0),
            }
            for e in entries
        ],
        "TotalTDSonSalaries": total,
    }


def _tds_other_schedule(tds_other_entries: Optional[list[dict]] = None) -> dict:
    entries = tds_other_entries or []
    total = sum(
        (e.get("ClaimOutOfTotTDSOnAmtPaid", 0) if isinstance(e, dict) else 0) for e in entries
    )
    return {
        "TDSonOthThanSal": [
            {
                "EmployerOrDeductorOrCollectDetl": {
                    "TAN": e.get("TAN", "DELA00001A"),
                    "EmployerOrDeductorOrCollecterName": e.get("EmployerName", "Deductor"),
                },
                "TDSSection": e.get("TDSSection", "194A"),
                "AmtForTaxDeduct": e.get("AmtForTaxDeduct", 0),
                "DeductedYr": e.get("DeductedYr", "2025"),
                "TotTDSOnAmtPaid": e.get("TotTDSOnAmtPaid", 0),
                "ClaimOutOfTotTDSOnAmtPaid": e.get("ClaimOutOfTotTDSOnAmtPaid", 0),
            }
            for e in entries
        ],
        "TotalTDSonOthThanSals": total,
    }


def _schedule_ea10_13a(
    place_of_work: str = "1",
    hra_received: Decimal = Decimal("0"),
    rent_paid: Decimal = Decimal("0"),
    basic_salary: Decimal = Decimal("0"),
    dearness_allowance: Decimal = Decimal("0"),
) -> dict:
    dtls_sal = basic_salary + dearness_allowance
    rent_minus_10pct = max(Decimal("0"), rent_paid - dtls_sal * Decimal("0.1"))
    sal_40_or_50 = dtls_sal * (Decimal("0.5") if place_of_work == "1" else Decimal("0.4"))
    eligible = min(hra_received, rent_minus_10pct, sal_40_or_50)
    return {
        "Placeofwork": place_of_work,
        "ActlHRARecv": _to_paise(hra_received),
        "ActlRentPaid": _to_paise(rent_paid),
        "DtlsSalUsSec171": _to_paise(dtls_sal),
        "BasicSalary": _to_paise(basic_salary),
        "DearnessAllwnc": _to_paise(dearness_allowance),
        "ActlRentPaid10Per": _to_paise(rent_minus_10pct),
        "Sal40Or50Per": _to_paise(sal_40_or_50),
        "EligbleExmpAllwncUs13A": _to_paise(eligible),
    }


def _ltcg_112a_schedule(
    sale_consideration: Decimal,
    cost_acquisition: Decimal,
    long_cap_112a: Decimal,
) -> dict:
    return {
        "TotSaleCnsdrn": _to_paise(sale_consideration),
        "TotCstAcqisn": _to_paise(cost_acquisition),
        "LongCap112A": _to_paise(long_cap_112a),
    }


# ---------------------------------------------------------------------------
# Schedule BP (ITR-4 only)
# ---------------------------------------------------------------------------

def _schedule_bp(
    gross_turnover: Decimal,
    digital_turnover: Decimal,
    cash_turnover: Decimal,
    other_turnover: Decimal,
    presumptive_income: Decimal,
    scheme: str,
) -> dict:
    bp: dict[str, Any] = {
        "NatOfBus44AD": [],
        "PersumptiveInc44AD": {
            "GrsTotalTrnOver": _to_paise(gross_turnover),
            "GrsTrnOverBank": _to_paise(digital_turnover),
            "GrsTotalTrnOverInCash": _to_paise(cash_turnover),
            "GrsTrnOverAnyOthMode": _to_paise(other_turnover),
            "PersumptiveInc44AD6Per": 0,
            "PersumptiveInc44AD8Per": 0,
            "TotPersumptiveInc44AD": _to_paise(presumptive_income),
        },
        "NatOfBus44ADA": [],
        "PersumptiveInc44ADA": {
            "GrsReceipt": 0,
            "GrsTrnOverBank44ADA": 0,
            "GrsTotalTrnOverInCash44ADA": 0,
            "GrsTrnOverAnyOthMode44ADA": 0,
            "TotPersumptiveInc44ADA": 0,
        },
        "NatOfBus44AE": [],
        "GoodsDtlsUs44AE": [],
        "PersumptiveInc44AE": {
            "TotPersumInc44AE": 0,
            "SalInterestByFirm": 0,
            "TotalPersumptiveInc": 0,
            "IncChargeableUnderBus": 0,
        },
        "TurnoverGrsRcptForGSTIN": [],
        "TotalTurnoverGrsRcptGSTIN": 0,
        "FinanclPartclrOfBusiness": {
            "PartnerMemberOwnCapital": 0,
            "SecuredLoans": 0,
            "UnSecuredLoans": 0,
            "Advances": 0,
            "SundryCreditors": 0,
            "OthrCurrLiab": 0,
            "TotCapLiabilities": 0,
            "FixedAssets": 0,
            "Investments": 0,
            "Inventories": 0,
            "SundryDebtors": 0,
            "BalWithBanks": 0,
            "CashInHand": 0,
            "LoansAndAdvances": 0,
            "OtherAssets": 0,
            "TotalAssets": 0,
        },
    }
    if scheme == "44ADA":
        bp["PersumptiveInc44ADA"] = {
            "GrsReceipt": _to_paise(gross_turnover),
            "GrsTrnOverBank44ADA": _to_paise(digital_turnover),
            "GrsTotalTrnOverInCash44ADA": _to_paise(cash_turnover),
            "GrsTrnOverAnyOthMode44ADA": _to_paise(other_turnover),
            "TotPersumptiveInc44ADA": _to_paise(presumptive_income),
        }
        bp["NatOfBus44ADA"] = [{
            "NameOfBusiness": "Profession",
            "CodeADA": "14001",
            "Description": "",
        }]
    elif scheme == "44AE":
        bp["PersumptiveInc44AE"] = {
            "TotPersumInc44AE": _to_paise(presumptive_income),
            "SalInterestByFirm": 0,
            "TotalPersumptiveInc": _to_paise(presumptive_income),
            "IncChargeableUnderBus": _to_paise(presumptive_income),
        }
    else:
        bp["NatOfBus44AD"] = [{
            "NameOfBusiness": "Business",
            "CodeAD": "01001",
            "Description": "",
        }]
        cash_limit = gross_turnover * Decimal("0.05")
        if cash_turnover > cash_limit:
            bp["PersumptiveInc44AD"]["PersumptiveInc44AD8Per"] = _to_paise(presumptive_income)
        else:
            bp["PersumptiveInc44AD"]["PersumptiveInc44AD6Per"] = _to_paise(presumptive_income)

    return bp


# ============================================================================
# Public API: ITR-1
# ============================================================================

ITR1_PERSONAL_INFO_FIELDS = [
    "pan", "first_name", "middle_name", "last_name",
    "dob", "employer_category", "residence_no", "locality",
    "city", "state_code", "country_code", "mobile_no", "email",
    "aadhaar", "secondary_add", "pin_code",
]

ITR1_FILING_FIELDS = [
    "opt_out_new_regime", "return_file_sec",
]

ITR1_BANK_FIELDS = [
    "bank_name", "account_no", "ifsc",
]

ITR1_OPTIONAL_FIELDS = [
    "tds_salary_entries", "tds_other_entries",
    "hra_received", "rent_paid", "hra_metro",
    "schedule_80d_senior_self", "schedule_80d_senior_parents",
    "schedule_80d_self_amt", "schedule_80d_parents_amt",
    "schedule_80g_cash", "schedule_80g_other",
    "cg_sale_consideration", "cg_cost_acquisition",
]


def build_itr1_json(
    result: ITR1Result,
    *,
    pan: str = "AAAAA0000A",
    first_name: str = "",
    middle_name: str = "",
    last_name: str = "",
    dob: str = "1990-01-01",
    employer_category: str = "OTH",
    residence_no: str = "1",
    locality: str = "Locality",
    city: str = "City",
    state_code: str = "07",
    country_code: str = "91",
    mobile_no: Optional[str] = None,
    email: Optional[str] = None,
    aadhaar: Optional[str] = None,
    secondary_add: str = "N",
    pin_code: Optional[str] = None,
    opt_out_new_regime: str = "N",
    return_file_sec: int = 11,
    assessee_ver_name: str = "",
    father_name: str = "",
    ver_place: str = "Delhi",
    bank_name: str = "BankName",
    account_no: str = "0000000000",
    ifsc: str = "SBIN0000001",
    tds_salary_entries: Optional[list[dict]] = None,
    tds_other_entries: Optional[list[dict]] = None,
    hra_received: Optional[Decimal] = None,
    rent_paid: Optional[Decimal] = None,
    hra_metro: bool = False,
    schedule_80d_senior_self: str = "N",
    schedule_80d_senior_parents: str = "N",
    schedule_80d_self_amt: Optional[Decimal] = None,
    schedule_80d_parents_amt: Optional[Decimal] = None,
    cg_sale_consideration: Optional[Decimal] = None,
    cg_cost_acquisition: Optional[Decimal] = None,
) -> dict:
    """
    Build an ITD-compliant ITR-1 JSON document.

    Parameters
    ----------
    result : ITR1Result
        The output of ``app.engine.calculators.itr1.compute()``.
    All other parameters map to PersonalInfo, FilingStatus, Verification,
    and optional schedule fields from the ITD schema.  See ``ITR1_PERSONAL_INFO_FIELDS``,
    ``ITR1_FILING_FIELDS``, ``ITR1_BANK_FIELDS``, and ``ITR1_OPTIONAL_FIELDS``.
    """
    # ── Mandatory sections ──────────────────────────────────────────────

    form = _form_itr("ITR-1")
    personal = _personal_info(
        pan=pan, first_name=first_name, middle_name=middle_name, last_name=last_name,
        dob=dob, employer_category=employer_category,
        residence_no=residence_no, locality=locality, city=city,
        state_code=state_code, country_code=country_code,
        mobile_no=mobile_no, email=email, aadhaar=aadhaar,
        secondary_add=secondary_add, pin_code=pin_code,
    )
    filing = _filing_status(
        opt_out_new_regime=opt_out_new_regime,
        return_file_sec=return_file_sec,
    )
    ver = _verification(
        assessee_name=first_name + " " + last_name,
        father_name=father_name,
        pan=pan,
        place=ver_place,
    )

    # ── Income & Tax computation ────────────────────────────────────────

    gti_cg = result.gross_total_income + result.capital_gains_112a
    income = _income_deductions(
        gross_salary=result.salary_income,
        net_salary=max(Decimal("0"), result.salary_income),
        ded_us16=Decimal("0"),
        ded_us16ia=Decimal("0"),
        ded_us16ii=Decimal("0"),
        ded_us16iii=Decimal("0"),
        income_from_sal=result.salary_income,
        income_hp=result.house_property_income,
        income_os=result.other_sources_income,
        gti=result.gross_total_income - result.capital_gains_112a,
        gti_cg=gti_cg,
        total_income=result.taxable_income,
        deductions_total=result.deductions_total,
    )

    tax = _tax_computation(
        slab_tax=result.tax_before_rebate,
        rebate_87a=result.rebate_87a,
        tax_after_rebate=result.tax_after_rebate,
        surcharge=result.surcharge,
        cess=result.health_education_cess,
        gross_tax_liability=result.gross_tax_liability,
        net_tax_liability=result.net_tax_liability,
        relief_89=result.relief_89,
        total_interest=result.total_interest,
        interest_234a=result.interest_234a,
        interest_234b=result.interest_234b,
        interest_234c=result.interest_234c,
        late_fee_234f=result.late_fee_234f,
    )

    tax_paid = _tax_paid_section(
        total_tds=result.total_tds,
        total_tcs=result.total_tcs,
        advance_tax=Decimal("0"),
        self_assessment_tax=Decimal("0"),
        balance_payable=result.balance_payable,
    )

    refund = _refund_section(
        refund_due=result.refund_due,
        bank_name=bank_name,
        account_no=account_no,
        ifsc=ifsc,
    )

    # ── Assemble the ITR-1 object ───────────────────────────────────────

    itr1: dict[str, Any] = {
        "CreationInfo": _creation_info(),
        "Form_ITR1": form,
        "PersonalInfo": personal,
        "FilingStatus": filing,
        "ITR1_IncomeDeductions": income,
        "ITR1_TaxComputation": tax,
        "TaxPaid": tax_paid,
        "Refund": refund,
        "Verification": ver,
        # Optional schedules — all present with defaults
        "Schedule80G": _schedule_80g(Decimal("0"), Decimal("0")),
        "Schedule80GGA": {
            "DonationDtlsSciRsrchRuralDev": [],
            "TotalDonationAmtCash80GGA": 0,
            "TotalDonationAmtOtherMode80GGA": 0,
            "TotalDonationsUs80GGA": 0,
            "TotalEligibleDonationAmt80GGA": 0,
        },
        "Schedule80GGC": {
            "Schedule80GGCDetails": [],
            "TotalDonationAmtCash80GGC": 0,
            "TotalDonationAmtOtherMode80GGC": 0,
            "TotalDonationsUs80GGC": 0,
            "TotalEligibleDonationAmt80GGC": 0,
        },
        "Schedule80D": _schedule_80d(
            senior_flag_self=schedule_80d_senior_self,
            senior_flag_parents=schedule_80d_senior_parents,
            self_amt=_zero_if_none(schedule_80d_self_amt),
            parents_amt=_zero_if_none(schedule_80d_parents_amt),
            eligible_deduction=_zero_if_none(schedule_80d_self_amt) + _zero_if_none(schedule_80d_parents_amt),
        ),
        "Schedule80DD": {
            "NatureOfDisability": "1",
            "TypeOfDisability": "2",
            "DeductionAmount": 0,
            "DependentType": "1",
            "Form10IAAckNum": "",
            "UDIDNum": "",
        },
        "Schedule80U": {
            "NatureOfDisability": "1",
            "TypeOfDisability": "2",
            "DeductionAmount": 0,
        },
        "Schedule80E": {
            "Schedule80EDtls": [],
            "TotalInterest80E": 0,
        },
        "Schedule80EE": {
            "Schedule80EEDtls": [],
            "TotalInterest80EE": 0,
        },
        "Schedule80EEA": {
            "PropStmpDtyVal": 0,
            "Schedule80EEADtls": [],
            "TotalInterest80EEA": 0,
        },
        "Schedule80EEB": {
            "Schedule80EEBDtls": [],
            "TotalInterest80EEB": 0,
        },
        "Schedule80C": _schedule_80c(Decimal("0")),
        "ScheduleEA10_13A": _schedule_ea10_13a(
            place_of_work=("1" if hra_metro else "2"),
            hra_received=_zero_if_none(hra_received),
            rent_paid=_zero_if_none(rent_paid),
        ),
        "TDSonSalaries": _tds_salary_schedule(tds_salary_entries),
        "TDSonOthThanSals": _tds_other_schedule(tds_other_entries),
        "ScheduleTDS3Dtls": {
            "TDS3Details": [],
            "TotalTDS3Details": 0,
        },
        "ScheduleTCS": {
            "TCS": [],
            "TotalSchTCS": _to_paise(result.total_tcs),
        },
        "TaxPayments": {
            "TaxPayment": [],
            "TotalTaxPayments": 0,
        },
        "TaxReturnPreparer": {
            "IdentificationNoOfTRP": "T000000000",
            "NameOfTRP": "Tax Preparer",
            "ReImbFrmGov": 0,
        },
    }

    # LTCG 112A schedule (if applicable)
    if cg_sale_consideration is not None and cg_cost_acquisition is not None:
        itr1["LTCG112A"] = _ltcg_112a_schedule(
            sale_consideration=cg_sale_consideration,
            cost_acquisition=cg_cost_acquisition,
            long_cap_112a=result.capital_gains_112a,
        )

    # Compute the digest AFTER the full ITR1 object is built
    itr1["CreationInfo"]["Digest"] = _compute_digest(itr1)

    return {"ITR": {"ITR1": itr1}}


# ============================================================================
# Public API: ITR-4
# ============================================================================

ITR4_PERSONAL_INFO_FIELDS = ITR1_PERSONAL_INFO_FIELDS
ITR4_FILING_FIELDS = ITR1_FILING_FIELDS
ITR4_BANK_FIELDS = ITR1_BANK_FIELDS
ITR4_OPTIONAL_FIELDS = [
    "tds_salary_entries", "tds_other_entries",
    "schedule_80d_senior_self", "schedule_80d_senior_parents",
    "schedule_80d_self_amt", "schedule_80d_parents_amt",
    "cg_sale_consideration", "cg_cost_acquisition",
    # ScheduleBP fields
    "bp_gross_turnover", "bp_digital_turnover", "bp_cash_turnover",
    "bp_other_turnover", "bp_scheme",
]


def build_itr4_json(
    result: ITR4Result,
    *,
    pan: str = "AAAAA0000A",
    first_name: str = "",
    middle_name: str = "",
    last_name: str = "",
    dob: str = "1990-01-01",
    employer_category: str = "OTH",
    residence_no: str = "1",
    locality: str = "Locality",
    city: str = "City",
    state_code: str = "07",
    country_code: str = "91",
    mobile_no: Optional[str] = None,
    email: Optional[str] = None,
    aadhaar: Optional[str] = None,
    secondary_add: str = "N",
    pin_code: Optional[str] = None,
    opt_out_new_regime: str = "N",
    return_file_sec: int = 11,
    assessee_ver_name: str = "",
    father_name: str = "",
    ver_place: str = "Delhi",
    bank_name: str = "BankName",
    account_no: str = "0000000000",
    ifsc: str = "SBIN0000001",
    tds_salary_entries: Optional[list[dict]] = None,
    tds_other_entries: Optional[list[dict]] = None,
    schedule_80d_senior_self: str = "N",
    schedule_80d_senior_parents: str = "N",
    schedule_80d_self_amt: Optional[Decimal] = None,
    schedule_80d_parents_amt: Optional[Decimal] = None,
    cg_sale_consideration: Optional[Decimal] = None,
    cg_cost_acquisition: Optional[Decimal] = None,
    bp_gross_turnover: Optional[Decimal] = None,
    bp_digital_turnover: Optional[Decimal] = None,
    bp_cash_turnover: Optional[Decimal] = None,
    bp_other_turnover: Optional[Decimal] = None,
    bp_scheme: str = "44AD",
) -> dict:
    """
    Build an ITD-compliant ITR-4 JSON document.

    Parameters
    ----------
    result : ITR4Result
        The output of ``app.engine.calculators.itr4.compute()``.
    All other parameters mirror ``build_itr1_json()`` with additional
    ScheduleBP fields for presumptive income.
    """
    # ── Mandatory sections ──────────────────────────────────────────────

    form = _form_itr("ITR-4")
    personal = _personal_info(
        pan=pan, first_name=first_name, middle_name=middle_name, last_name=last_name,
        dob=dob, employer_category=employer_category,
        residence_no=residence_no, locality=locality, city=city,
        state_code=state_code, country_code=country_code,
        mobile_no=mobile_no, email=email, aadhaar=aadhaar,
        secondary_add=secondary_add, pin_code=pin_code,
    )
    filing = _filing_status(
        opt_out_new_regime=opt_out_new_regime,
        return_file_sec=return_file_sec,
    )
    ver = _verification(
        assessee_name=first_name + " " + last_name,
        father_name=father_name,
        pan=pan,
        place=ver_place,
    )

    # ── Income & Tax computation ────────────────────────────────────────

    gti_cg = result.gross_total_income + result.capital_gains_112a
    income = _income_deductions(
        gross_salary=result.salary_income,
        net_salary=max(Decimal("0"), result.salary_income),
        ded_us16=Decimal("0"),
        ded_us16ia=Decimal("0"),
        ded_us16ii=Decimal("0"),
        ded_us16iii=Decimal("0"),
        income_from_sal=result.salary_income,
        income_hp=result.house_property_income,
        income_os=result.other_sources_income,
        gti=result.gross_total_income - result.capital_gains_112a - result.presumptive_income,
        gti_cg=gti_cg,
        total_income=result.taxable_income,
        deductions_total=result.deductions_total,
    )
    # ITR-4 adds IncomeFromBusinessProf at the top of IncomeDeductions
    income["IncomeFromBusinessProf"] = _to_paise(result.presumptive_income)

    tax = _tax_computation(
        slab_tax=result.tax_before_rebate,
        rebate_87a=result.rebate_87a,
        tax_after_rebate=result.tax_after_rebate,
        surcharge=result.surcharge,
        cess=result.health_education_cess,
        gross_tax_liability=result.gross_tax_liability,
        net_tax_liability=result.net_tax_liability,
        relief_89=result.relief_89,
        total_interest=result.total_interest,
        interest_234a=result.interest_234a,
        interest_234b=result.interest_234b,
        interest_234c=result.interest_234c,
        late_fee_234f=result.late_fee_234f,
    )

    tax_paid = _tax_paid_section(
        total_tds=result.total_tds,
        total_tcs=result.total_tcs,
        advance_tax=Decimal("0"),
        self_assessment_tax=Decimal("0"),
        balance_payable=result.balance_payable,
    )

    refund = _refund_section(
        refund_due=result.refund_due,
        bank_name=bank_name,
        account_no=account_no,
        ifsc=ifsc,
    )

    # ── ScheduleBP (presumptive business income) ────────────────────────

    bp = _schedule_bp(
        gross_turnover=_zero_if_none(bp_gross_turnover),
        digital_turnover=_zero_if_none(bp_digital_turnover),
        cash_turnover=_zero_if_none(bp_cash_turnover),
        other_turnover=_zero_if_none(bp_other_turnover),
        presumptive_income=result.presumptive_income,
        scheme=bp_scheme,
    )

    # ── Assemble the ITR-4 object ───────────────────────────────────────

    itr4: dict[str, Any] = {
        "CreationInfo": _creation_info(),
        "Form_ITR4": form,
        "PersonalInfo": personal,
        "FilingStatus": filing,
        "IncomeDeductions": income,
        "TaxComputation": tax,
        "TaxPaid": tax_paid,
        "Refund": refund,
        "Verification": ver,
        "ScheduleBP": bp,
        "ScheduleIT": {
            "TotalTurnoverGrsRcptUs44AD": _to_paise(_zero_if_none(bp_gross_turnover)),
            "TotPresumIncUs44AD": _to_paise(result.presumptive_income),
        },
        "Schedule80G": _schedule_80g(Decimal("0"), Decimal("0")),
        "Schedule80GGA": {
            "DonationDtlsSciRsrchRuralDev": [],
            "TotalDonationAmtCash80GGA": 0,
            "TotalDonationAmtOtherMode80GGA": 0,
            "TotalDonationsUs80GGA": 0,
            "TotalEligibleDonationAmt80GGA": 0,
        },
        "Schedule80GGC": {
            "Schedule80GGCDetails": [],
            "TotalDonationAmtCash80GGC": 0,
            "TotalDonationAmtOtherMode80GGC": 0,
            "TotalDonationsUs80GGC": 0,
            "TotalEligibleDonationAmt80GGC": 0,
        },
        "Schedule80D": _schedule_80d(
            senior_flag_self=schedule_80d_senior_self,
            senior_flag_parents=schedule_80d_senior_parents,
            self_amt=_zero_if_none(schedule_80d_self_amt),
            parents_amt=_zero_if_none(schedule_80d_parents_amt),
            eligible_deduction=_zero_if_none(schedule_80d_self_amt) + _zero_if_none(schedule_80d_parents_amt),
        ),
        "Schedule80DD": {
            "NatureOfDisability": "1",
            "TypeOfDisability": "2",
            "DeductionAmount": 0,
            "DependentType": "1",
        },
        "Schedule80U": {
            "NatureOfDisability": "1",
            "TypeOfDisability": "2",
            "DeductionAmount": 0,
        },
        "Schedule80E": {
            "Schedule80EDtls": [],
            "TotalInterest80E": 0,
        },
        "Schedule80EE": {
            "Schedule80EEDtls": [],
            "TotalInterest80EE": 0,
        },
        "Schedule80EEA": {
            "PropStmpDtyVal": 0,
            "Schedule80EEADtls": [],
            "TotalInterest80EEA": 0,
        },
        "Schedule80EEB": {
            "Schedule80EEBDtls": [],
            "TotalInterest80EEB": 0,
        },
        "Schedule80C": _schedule_80c(Decimal("0")),
        "TDSonSalaries": _tds_salary_schedule(tds_salary_entries),
        "TDSonOthThanSals": _tds_other_schedule(tds_other_entries),
        "ScheduleTDS3Dtls": {
            "TDS3Details": [],
            "TotalTDS3Details": 0,
        },
        "ScheduleTCS": {
            "TCS": [],
            "TotalSchTCS": _to_paise(result.total_tcs),
        },
        "TaxPayments": {
            "TaxPayment": [],
            "TotalTaxPayments": 0,
        },
        "TaxReturnPreparer": {
            "IdentificationNoOfTRP": "T000000000",
            "NameOfTRP": "Tax Preparer",
            "ReImbFrmGov": 0,
        },
    }

    # LTCG 112A schedule (if applicable)
    if cg_sale_consideration is not None and cg_cost_acquisition is not None:
        itr4["LTCG112A"] = _ltcg_112a_schedule(
            sale_consideration=cg_sale_consideration,
            cost_acquisition=cg_cost_acquisition,
            long_cap_112a=result.capital_gains_112a,
        )

    # Compute the digest AFTER the full ITR4 object is built
    itr4["CreationInfo"]["Digest"] = _compute_digest(itr4)

    return {"ITR": {"ITR4": itr4}}
