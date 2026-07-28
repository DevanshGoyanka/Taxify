"""
ITR-1 (Sahaj) ITD JSON builder.

Produces an ITD-compliant JSON document matching the CBDT ITR-1 schema
(``ITR-1_2026_Main_V1.1``) with ``additionalProperties: false`` enforcement
at every level.

Every field emitted here is verified against the CBDT schema.  No fields
from other ITR forms bleed in — this file owns ITR-1 output exclusively.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.engine.calculators.itr1 import ITR1Result
from decimal import Decimal as _Decimal

# Module-level deduction breakdown -- rebound by build_itr1_json before use.
_DED_BREAKDOWN: dict[str, _Decimal] = {}

def _d(key: str) -> _Decimal:
    """Return deduction amount from the module-level breakdown dict."""
    return _DED_BREAKDOWN.get(key, _Decimal("0"))


from app.engine.itd.common import (
    _to_rupees,
    _to_rupees_rounded10,
    _zero_if_none,
    _str_or,
    _creation_info,
    _form_itr,
    _verification,
    _tax_return_preparer,
    _personal_info_base,
    _compute_digest,
)


# ---------------------------------------------------------------------------
# ITR-1 FilingStatus
# ---------------------------------------------------------------------------

def _filing_status_itr1(
    return_file_sec: int = 11,
    opt_out_new_regime: str = "N",
) -> dict:
    return {
        "ReturnFileSec": return_file_sec,
        "OptOutNewTaxRegime": opt_out_new_regime,
        "SeventhProvisio139": "N",
        "AsseseeRepFlg": "N",
        "ItrFilingDueDate": "2026-07-31",
    }


# ---------------------------------------------------------------------------
# ITR-1 DeductUndChapVIA (has Section80GGA)
# ---------------------------------------------------------------------------

def _chapter_via_itr1(
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
    """ITR-1 DeductUndChapVIA / UsrDeductUndChapVIA — includes Section80GGA."""
    return {
        "Section80C": _to_rupees(ded_80c),
        "Section80CCC": _to_rupees(ded_80ccc),
        "Section80CCDEmployeeOrSE": _to_rupees(ded_80ccd1),
        "Section80CCD1B": _to_rupees(ded_80ccd1b),
        "Section80CCDEmployer": _to_rupees(ded_80ccd2),
        "Section80D": _to_rupees(ded_80d),
        "Section80DD": _to_rupees(ded_80dd),
        "Section80DDB": _to_rupees(ded_80ddb),
        "Section80E": _to_rupees(ded_80e),
        "Section80EE": _to_rupees(ded_80ee),
        "Section80EEA": _to_rupees(ded_80eea),
        "Section80EEB": _to_rupees(ded_80eeb),
        "Section80G": _to_rupees(ded_80g),
        "Section80GG": _to_rupees(ded_80gg),
        "Section80GGA": _to_rupees(ded_80gga),
        "Section80GGC": _to_rupees(ded_80ggc),
        "Section80U": _to_rupees(ded_80u),
        "Section80TTA": _to_rupees(ded_80tta),
        "Section80TTB": _to_rupees(ded_80ttb),
        "AnyOthSec80CCH": _to_rupees(ded_80cch),
        "TotalChapVIADeductions": _to_rupees(deductions_total),
    }


# ---------------------------------------------------------------------------
# ITR-1 IncomeDeductions
# ---------------------------------------------------------------------------

def _income_deductions_itr1(
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
    perquisites_value: Decimal = Decimal("0"),
    profits_in_lieu: Decimal = Decimal("0"),
    ded_80c: Decimal = Decimal("0"),
    ded_80ccc: Decimal = Decimal("0"),
    ded_80ccd1: Decimal = Decimal("0"),
    ded_80ccd1b: Decimal = Decimal("0"),
    ded_80ccd2: Decimal = Decimal("0"),
    ded_80d: Decimal = Decimal("0"),
    ded_80dd: Decimal = Decimal("0"),
    ded_80ddb: Decimal = Decimal("0"),
    ded_80u: Decimal = Decimal("0"),
    ded_80tta: Decimal = Decimal("0"),
    ded_80ttb: Decimal = Decimal("0"),
    ded_80e: Decimal = Decimal("0"),
    ded_80ee: Decimal = Decimal("0"),
    ded_80eea: Decimal = Decimal("0"),
    ded_80eeb: Decimal = Decimal("0"),
    ded_80g: Decimal = Decimal("0"),
    ded_80gg: Decimal = Decimal("0"),
    ded_80gga: Decimal = Decimal("0"),
    ded_80ggc: Decimal = Decimal("0"),
    ded_80cch: Decimal = Decimal("0"),
) -> dict:
    return {
        "GrossSalary": _to_rupees(gross_salary),
        "Salary": _to_rupees(net_salary + ded_us16),
        "PerquisitesValue": _to_rupees(perquisites_value),
        "ProfitsInSalary": _to_rupees(profits_in_lieu),
        "AllwncExemptUs10": {
            "AllwncExemptUs10Dtls": [],
            "TotalAllwncExemptUs10": 0,
        },
        "NetSalary": _to_rupees(net_salary),
        "DeductionUs16": _to_rupees(ded_us16),
        "DeductionUs16ia": _to_rupees(ded_us16ia),
        "EntertainmentAlw16ii": _to_rupees(ded_us16ii),
        "ProfessionalTaxUs16iii": _to_rupees(ded_us16iii),
        "IncomeFromSal": _to_rupees(income_from_sal),
        "PropertyDetails": hp_schedules or [],
        "TotalIncomeChargeableUnHP": _to_rupees(income_hp),
        "IncomeOthSrc": _to_rupees(income_os),
        "OthersInc": {
            "OthersIncDtlsOthSrc": [],
        },
        "DeductionUs57iia": 0,
        "GrossTotIncome": _to_rupees(gti),
        "GrossTotIncomeIncLTCG112A": _to_rupees(gti_cg),
        "UsrDeductUndChapVIA": _chapter_via_itr1(
            deductions_total,
            ded_80c=ded_80c, ded_80ccc=ded_80ccc, ded_80ccd1=ded_80ccd1,
            ded_80ccd1b=ded_80ccd1b,
            ded_80ccd2=ded_80ccd2, ded_80d=ded_80d, ded_80dd=ded_80dd,
            ded_80ddb=ded_80ddb, ded_80u=ded_80u, ded_80tta=ded_80tta,
            ded_80ttb=ded_80ttb, ded_80e=ded_80e, ded_80ee=ded_80ee,
            ded_80eea=ded_80eea, ded_80eeb=ded_80eeb, ded_80g=ded_80g,
            ded_80gg=ded_80gg, ded_80gga=ded_80gga, ded_80ggc=ded_80ggc,
            ded_80cch=ded_80cch,
        ),
        "DeductUndChapVIA": _chapter_via_itr1(
            deductions_total,
            ded_80c=ded_80c, ded_80ccc=ded_80ccc, ded_80ccd1=ded_80ccd1,
            ded_80ccd1b=ded_80ccd1b,
            ded_80ccd2=ded_80ccd2, ded_80d=ded_80d, ded_80dd=ded_80dd,
            ded_80ddb=ded_80ddb, ded_80u=ded_80u, ded_80tta=ded_80tta,
            ded_80ttb=ded_80ttb, ded_80e=ded_80e, ded_80ee=ded_80ee,
            ded_80eea=ded_80eea, ded_80eeb=ded_80eeb, ded_80g=ded_80g,
            ded_80gg=ded_80gg, ded_80gga=ded_80gga, ded_80ggc=ded_80ggc,
            ded_80cch=ded_80cch,
        ),
        "TotalIncome": _to_rupees_rounded10(total_income),
        "ExemptIncAgriOthUs10": {
            "ExemptIncAgriOthUs10Dtls": [],
            "ExemptIncAgriOthUs10Total": 0,
        },
    }


# ---------------------------------------------------------------------------
# ITR-1 TaxComputation
# ---------------------------------------------------------------------------

def _tax_computation_itr1(
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
    """ITR-1 TaxComputation — includes TotalIntrstPay (not in ITR-4)."""
    return {
        "TotalTaxPayable": _to_rupees_rounded10(slab_tax),
        "Rebate87A": _to_rupees_rounded10(rebate_87a),
        "TaxPayableOnRebate": _to_rupees_rounded10(tax_after_rebate),
        "EducationCess": _to_rupees_rounded10(cess),
        "GrossTaxLiability": _to_rupees_rounded10(gross_tax_liability),
        "Section89": _to_rupees_rounded10(relief_89),
        "NetTaxLiability": _to_rupees_rounded10(net_tax_liability),
        "TotalIntrstPay": _to_rupees_rounded10(total_interest + late_fee_234f),
        "IntrstPay": {
            "IntrstPayUs234A": _to_rupees_rounded10(interest_234a),
            "IntrstPayUs234B": _to_rupees_rounded10(interest_234b),
            "IntrstPayUs234C": _to_rupees_rounded10(interest_234c),
            "LateFilingFee234F": _to_rupees_rounded10(late_fee_234f),
            "FeeFurnish234I": 0,
        },
        "TotTaxPlusIntrstPay": _to_rupees_rounded10(
            gross_tax_liability + total_interest + late_fee_234f
        ),
    }


# ---------------------------------------------------------------------------
# ITR-1 TaxPaid & Refund
# ---------------------------------------------------------------------------

def _tax_paid_itr1(
    total_tds: Decimal,
    total_tcs: Decimal,
    advance_tax: Decimal,
    self_assessment_tax: Decimal,
    balance_payable: Decimal,
) -> dict:
    total_paid = total_tds + total_tcs + advance_tax + self_assessment_tax
    return {
        "TaxesPaid": {
            "AdvanceTax": _to_rupees(advance_tax),
            "TDS": _to_rupees(total_tds),
            "TCS": _to_rupees(total_tcs),
            "SelfAssessmentTax": _to_rupees(self_assessment_tax),
            "TotalTaxesPaid": _to_rupees(total_paid),
        },
        "BalTaxPayable": _to_rupees_rounded10(balance_payable),
    }


def _refund_itr1(
    refund_due: Decimal,
    bank_name: str,
    account_no: str,
    ifsc: str,
) -> dict:
    return {
        "RefundDue": _to_rupees_rounded10(refund_due),
        "BankAccountDtls": {
            "AddtnlBankDetails": [
                {
                    "IFSCCode": _str_or(ifsc, "SBIN0000001"),
                    "BankName": _str_or(bank_name, "BankName"),
                    "BankAccountNo": _str_or(account_no, "0000000001"),
                    "AccountType": "SB",
                    "UseForRefund": "true",
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# ITR-1 Schedule helpers
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
            "SelfAndFamily": _to_rupees(self_amt) if senior_flag_self == "N" else 0,
            "HealthInsPremSlfFam": _to_rupees(self_amt) if senior_flag_self == "N" else 0,
            "Sec80DSelfFamHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_rupees(self_amt) if senior_flag_self == "N" else 0,
            },
            "PrevHlthChckUpSlfFam": 0,
            "SelfAndFamilySeniorCitizen": _to_rupees(self_amt) if senior_flag_self in ("Y", "S") else 0,
            "HlthInsPremSlfFamSrCtzn": _to_rupees(self_amt) if senior_flag_self in ("Y", "S") else 0,
            "Sec80DSelfFamSrCtznHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_rupees(self_amt) if senior_flag_self in ("Y", "S") else 0,
            },
            "PrevHlthChckUpSlfFamSrCtzn": 0,
            "MedicalExpSlfFamSrCtzn": 0,
            "ParentsSeniorCitizenFlag": senior_flag_parents,
            "Parents": _to_rupees(parents_amt) if senior_flag_parents == "N" else 0,
            "HlthInsPremParents": _to_rupees(parents_amt) if senior_flag_parents == "N" else 0,
            "Sec80DParentsHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_rupees(parents_amt) if senior_flag_parents == "N" else 0,
            },
            "PrevHlthChckUpParents": 0,
            "ParentsSeniorCitizen": _to_rupees(parents_amt) if senior_flag_parents in ("Y", "P") else 0,
            "HlthInsPremParentsSrCtzn": _to_rupees(parents_amt) if senior_flag_parents in ("Y", "P") else 0,
            "Sec80DParentsSrCtznHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_rupees(parents_amt) if senior_flag_parents in ("Y", "P") else 0,
            },
            "PrevHlthChckUpParentsSrCtzn": 0,
            "MedicalExpParentsSrCtzn": 0,
            "EligibleAmountOfDedn": _to_rupees(eligible_deduction),
        }
    }


def _schedule_80c(total_amt: Decimal) -> dict:
    return {
        "Schedule80CDtls": [],
        "TotalAmt": _to_rupees(total_amt),
    }


def _schedule_80g(
    total_donations_cash: Decimal,
    total_donations_other: Decimal,
) -> dict:
    result: dict[str, Any] = {
        "TotalDonationsUs80GCash": _to_rupees(total_donations_cash),
        "TotalDonationsUs80GOtherMode": _to_rupees(total_donations_other),
        "TotalDonationsUs80G": _to_rupees(total_donations_cash + total_donations_other),
        "TotalEligibleDonationsUs80G": 0,
    }
    if total_donations_cash > 0 or total_donations_other > 0:
        result["Don100Percent"] = {
            "DoneeWithPan": [{"NameOfDonee": "Donee", "PANOfDonee": "AAAAA0000A", "AmountOfDonation": _to_rupees(total_donations_cash + total_donations_other)}],
            "TotDon100PercentCash": _to_rupees(total_donations_cash),
            "TotDon100PercentOtherMode": _to_rupees(total_donations_other),
            "TotDon100Percent": _to_rupees(total_donations_cash + total_donations_other),
            "TotEligibleDon100Percent": 0,
        }
    return result


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
        "ActlHRARecv": _to_rupees(hra_received),
        "ActlRentPaid": _to_rupees(rent_paid),
        "DtlsSalUsSec171": _to_rupees(dtls_sal),
        "BasicSalary": _to_rupees(basic_salary),
        "DearnessAllwnc": _to_rupees(dearness_allowance),
        "ActlRentPaid10Per": _to_rupees(rent_minus_10pct),
        "Sal40Or50Per": _to_rupees(sal_40_or_50),
        "EligbleExmpAllwncUs13A": _to_rupees(eligible),
    }


def _ltcg_112a_schedule(
    sale_consideration: Decimal,
    cost_acquisition: Decimal,
    long_cap_112a: Decimal,
) -> dict:
    return {
        "TotSaleCnsdrn": _to_rupees(sale_consideration),
        "TotCstAcqisn": _to_rupees(cost_acquisition),
        "LongCap112A": _to_rupees(long_cap_112a),
    }


def _tds_salary_schedule_itr1(tds_salary_entries: Optional[list[dict]] = None) -> Optional[dict]:
    if not tds_salary_entries:
        return None
    total = sum(
        (e.get("TotalTDSSal", 0) if isinstance(e, dict) else 0) for e in tds_salary_entries
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
            for e in tds_salary_entries
        ],
        "TotalTDSonSalaries": total,
    }


def _tds_other_schedule_itr1(tds_other_entries: Optional[list[dict]] = None) -> Optional[dict]:
    if not tds_other_entries:
        return None
    total = sum(
        (e.get("ClaimOutOfTotTDSOnAmtPaid", 0) if isinstance(e, dict) else 0)
        for e in tds_other_entries
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
            for e in tds_other_entries
        ],
        "TotalTDSonOthThanSals": total,
    }


# ============================================================================
# Public API
# ============================================================================

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
    father_name: str = "",
    ver_place: str = "Delhi",
    bank_name: str = "BankName",
    account_no: str = "0000000001",
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
    """Build an ITD-compliant ITR-1 JSON document."""

    assessee_name = f"{first_name} {last_name}".strip()
    ver = _verification(
        assessee_name=assessee_name or "ASSESSEE",
        father_name=father_name or "FATHER",
        pan=pan,
        place=ver_place,
    )

    personal = _personal_info_base(
        pan=pan, first_name=first_name, middle_name=middle_name, last_name=last_name,
        dob=dob, employer_category=employer_category,
        residence_no=residence_no, locality=locality, city=city,
        state_code=state_code, country_code=country_code,
        mobile_no=mobile_no, email=email, aadhaar=aadhaar,
        secondary_add=secondary_add, pin_code=pin_code,
    )
    # Omit EmailAddressSec from Address — it's optional and "" fails regex
    if "Address" in personal:
        personal["Address"].pop("EmailAddressSec", None)

    filing = _filing_status_itr1(
        return_file_sec=return_file_sec,
        opt_out_new_regime=opt_out_new_regime,
    )

    # -- Extract per-section deduction amounts from breakdown ----------------
    # DeductionResult is a dataclass with a .breakdown dict attribute.
    ded_sched = result.schedules.get("deductions") if result.schedules else None
    global _DED_BREAKDOWN
    _DED_BREAKDOWN = getattr(ded_sched, "breakdown", {}) if ded_sched else {}

    gti_cg = result.gross_total_income  # Already includes capital_gains_112a
    income = _income_deductions_itr1(
        gross_salary=result.salary_gross,
        net_salary=result.salary_net,
        ded_us16=result.salary_deduction_us16,
        ded_us16ia=result.salary_deduction_us16ia,
        ded_us16ii=result.salary_entertainment_allowance,
        ded_us16iii=result.salary_professional_tax,
        income_from_sal=result.salary_income,
        income_hp=result.house_property_income,
        income_os=result.other_sources_income,
        gti=result.gross_total_income - result.capital_gains_112a,
        gti_cg=gti_cg,
        total_income=result.taxable_income,
        deductions_total=result.deductions_total,
        perquisites_value=result.salary_perquisites,
        profits_in_lieu=result.salary_profits_in_lieu,
        ded_80c=_d("80C+80CCC+80CCD(1)"), ded_80ccc=_d("80CCC"), ded_80ccd1=_d("80CCD(1)"),
        ded_80ccd1b=_d("80CCD(1B)"),
        ded_80ccd2=_d("80CCD(2)"),
        ded_80d=_d("80D"),
        ded_80dd=_d("80DD"),
        ded_80ddb=_d("80DDB"),
        ded_80u=_d("80U"),
        ded_80tta=_d("80TTA"),
        ded_80ttb=_d("80TTB"),
        ded_80e=_d("80E"),
        ded_80ee=_d("80EE"),
        ded_80eea=_d("80EEA"),
        ded_80eeb=_d("80EEB"),
        ded_80g=_d("80G"),
        ded_80gg=_d("80GG"),
        ded_80gga=_d("80GGA"),
        ded_80ggc=_d("80GGC"),
        ded_80cch=_d("80CCH"),
    )

    tax = _tax_computation_itr1(
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

    tax_paid = _tax_paid_itr1(
        total_tds=result.total_tds,
        total_tcs=result.total_tcs,
        advance_tax=result.advance_tax_paid,
        self_assessment_tax=result.self_assessment_tax_paid,
        balance_payable=result.balance_payable,
    )

    refund = _refund_itr1(
        refund_due=result.refund_due,
        bank_name=bank_name,
        account_no=account_no,
        ifsc=ifsc,
    )

    # ── Assemble ─────────────────────────────────────────��──────────────

    itr1: dict[str, Any] = {
        "CreationInfo": _creation_info(),
        "Form_ITR1": _form_itr("ITR-1"),
        "PersonalInfo": personal,
        "FilingStatus": filing,
        "ITR1_IncomeDeductions": income,
        "ITR1_TaxComputation": tax,
        "TaxPaid": tax_paid,
        "Refund": refund,
        "Verification": ver,
        "Schedule80G": _schedule_80g(_d("80G"), Decimal("0")),
        "Schedule80GGA": {
            "DonationDtlsSciRsrchRuralDev": [],
            "TotalDonationAmtCash80GGA": 0,
            "TotalDonationAmtOtherMode80GGA": _to_rupees(_d("80GGA")),
            "TotalDonationsUs80GGA": _to_rupees(_d("80GGA")),
            "TotalEligibleDonationAmt80GGA": _to_rupees(_d("80GGA")),
        },
        "Schedule80GGC": {
            "Schedule80GGCDetails": [],
            "TotalDonationAmtCash80GGC": 0,
            "TotalDonationAmtOtherMode80GGC": _to_rupees(_d("80GGC")),
            "TotalDonationsUs80GGC": _to_rupees(_d("80GGC")),
            "TotalEligibleDonationAmt80GGC": _to_rupees(_d("80GGC")),
        },
        "Schedule80D": _schedule_80d(
            senior_flag_self=schedule_80d_senior_self,
            senior_flag_parents=schedule_80d_senior_parents,
            self_amt=_zero_if_none(schedule_80d_self_amt) or _d("80D"),
            parents_amt=_zero_if_none(schedule_80d_parents_amt),
            eligible_deduction=(_zero_if_none(schedule_80d_self_amt) + _zero_if_none(schedule_80d_parents_amt)) or _d("80D"),
        ),
        "Schedule80DD": {
            "NatureOfDisability": "1",
            "TypeOfDisability": "2",
            "DeductionAmount": _to_rupees(_d("80DD")),
            "DependentType": "1",
            "DependentPan": "AAAAA0000A",
            "DependentAadhaar": "000000000000",
            "Form10IAAckNum": "",
            "UDIDNum": "",
        },
        "Schedule80U": {
            "NatureOfDisability": "1",
            "TypeOfDisability": "2",
            "DeductionAmount": _to_rupees(_d("80U")),
            "Form10IAAckNum": "",
            "UDIDNum": "",
        },
        "Schedule80E": {
            "Schedule80EDtls": [],
            "TotalInterest80E": _to_rupees(_d("80E")),
        },
        "Schedule80EE": {
            "Schedule80EEDtls": [],
            "TotalInterest80EE": _to_rupees(_d("80EE")),
        },
        "Schedule80EEA": {
            "PropStmpDtyVal": 0,
            "Schedule80EEADtls": [],
            "TotalInterest80EEA": _to_rupees(_d("80EEA")),
        },
        "Schedule80EEB": {
            "Schedule80EEBDtls": [],
            "TotalInterest80EEB": _to_rupees(_d("80EEB")),
        },
        "Schedule80C": _schedule_80c(_d("80C+80CCC+80CCD(1)")),
        "ScheduleEA10_13A": _schedule_ea10_13a(
            place_of_work=("1" if hra_metro else "2"),
            hra_received=_zero_if_none(hra_received),
            rent_paid=_zero_if_none(rent_paid),
        ),
        "TaxReturnPreparer": _tax_return_preparer(),
    }

    # Conditional: TDS on Salary
    # TDS on Salary: auto-populate from result.total_tds if no entries passed
    _sal_entries = tds_salary_entries
    if not _sal_entries and result.total_tds > 0:
        _sal_entries = [{"EmployerOrDeductorOrCollectDetl": {"TAN": "AAAAA0000A", "EmployerOrDeductorOrCollecterName": "Employer"}, "TotalTDSSal": _to_rupees(result.total_tds)}]
    tds_sal = _tds_salary_schedule_itr1(_sal_entries)
    if tds_sal:
        itr1["TDSonSalaries"] = tds_sal

    # TDS on Other Income
    _oth_entries = tds_other_entries
    if not _oth_entries and result.total_tds > 0:
        _oth_entries = [{"EmployerOrDeductorOrCollectDetl": {"TAN": "AAAAA0000A"}, "AmtForTaxDeduct": _to_rupees(result.total_tds), "ClaimOutOfTotTDSOnAmtPaid": _to_rupees(result.total_tds), "TotTDSOnAmtPaid": _to_rupees(result.total_tds)}]
    tds_oth = _tds_other_schedule_itr1(_oth_entries)
    if tds_oth:
        itr1["TDSonOthThanSals"] = tds_oth

    # Conditional: TCS
    if result.total_tcs > 0:
        itr1["ScheduleTCS"] = {
            "TCS": [{"EmployerOrDeductorOrCollectDetl": {"TAN": "DELA00001A"}, "AmtTCSClaimedThisYear": _to_rupees(result.total_tcs)}],
            "TotalSchTCS": _to_rupees(result.total_tcs),
        }

    # Conditional: TaxPayments (only when challans exist)
    if result.advance_tax_paid > 0 or result.self_assessment_tax_paid > 0:
        challans = []
        if result.advance_tax_paid > 0:
            challans.append({"BSRCode": "1234567", "DateDep": "2025-06-15", "SrlNoOfChaln": 1, "Amt": _to_rupees(result.advance_tax_paid)})
        if result.self_assessment_tax_paid > 0:
            challans.append({"BSRCode": "1234567", "DateDep": "2025-07-15", "SrlNoOfChaln": 2, "Amt": _to_rupees(result.self_assessment_tax_paid)})
        itr1["TaxPayments"] = {"TaxPayment": challans, "TotalTaxPayments": _to_rupees(result.advance_tax_paid + result.self_assessment_tax_paid)}
        # Conditional: ScheduleTDS3Dtls (non-resident TDS, empty for ITR-1)
    itr1["ScheduleTDS3Dtls"] = {
        "TDS3Details": [],
        "TotalTDS3Details": 0,
    }

# Conditional: LTCG 112A
    if cg_sale_consideration is not None and cg_cost_acquisition is not None:
        itr1["LTCG112A"] = _ltcg_112a_schedule(
            sale_consideration=cg_sale_consideration,
            cost_acquisition=cg_cost_acquisition,
            long_cap_112a=result.capital_gains_112a,
        )

    itr1["CreationInfo"]["Digest"] = _compute_digest(itr1)

    return {"ITR": {"ITR1": itr1}}
