"""
ITR-4 (Sugam) ITD JSON builder.

Produces an ITD-compliant JSON document matching the CBDT ITR-4 schema
(``ITR-4_2026_Main_V1.1``) with ``additionalProperties: false`` enforcement
at every level.

ITR-4 differs from ITR-1 in several critical ways:
- FilingStatus uses Form 10-IEA cascade (no OptOutNewTaxRegime)
- PersonalInfo requires Status (I/H/F) and Address.Phone
- IncomeDeductions uses ``EntertainmntalwncUs16ii`` (not ``EntertainmentAlw16ii``)
- IncomeDeductions has IncomeFromBusinessProf + TaxExmpIntIncDtls (not ExemptIncAgriOthUs10)
- TaxComputation has NO TotalIntrstPay
- Chapter VIA has NO Section80GGA (statutory: 80GGA not available for biz income)
- Top-level has ScheduleBP, ScheduleIT (challan array!), TaxExmpIntIncDtls
- NO root-level TaxPayments (ITR-4 folds that into ScheduleIT)
- NO Schedule80GGA
- TDSonOthThanSals key is ``TDSonOthThanSalDtls`` (not ``TDSonOthThanSal``)
- ItrFilingDueDate is ``2026-08-31`` (not ``2026-07-31``)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.engine.calculators.itr4 import ITR4Result
# Module-level deduction breakdown dict -- rebound by build_itr4_json before use.
_DED_BREAKDOWN: dict[str, Decimal] = {}

def _d(key: str) -> Decimal:
    """Return deduction amount from the module-level breakdown dict."""
    return _DED_BREAKDOWN.get(key, Decimal("0"))


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
# ITR-4 FilingStatus (Form 10-IEA cascade)
# ---------------------------------------------------------------------------

def _filing_status_itr4(
    return_file_sec: int = 11,
    form_10iea_earlier_ay_old_regime: str = "NA",
    form_10iea_ass_year: str = "",
    form_10iea_earlier_ay_ack_old_regime: int = 0,
    f10iea_earlier_ay_new_regime: str = "N",
    ass_yr_f10iea_new_tax_reg: str = "",
    form_10iea_earlier_ay_ack_new_regime: int = 0,
    f10iea_curr_ay_new_regime: str = "N",
    f10iea_date_curr_ay_new_tax: str = "",
    f10iea_ack_no_curr_ay_new_tax: int = 0,
    f10iea_curr_ay_old_regime: str = "N",
    f10iea_date_curr_ay_old_tax: str = "",
    f10iea_ack_no_curr_ay_old_tax: int = 0,
) -> dict:
    result: dict[str, Any] = {
        "ReturnFileSec": return_file_sec,
        "Form10IEAEarlierAYOldRegime": form_10iea_earlier_ay_old_regime,
        "SeventhProvisio139": "N",
        "AsseseeRepFlg": "N",
        "ItrFilingDueDate": "2026-08-31",
    }
    if form_10iea_ass_year:
        result["Form10IEAAssYear"] = form_10iea_ass_year
    if form_10iea_earlier_ay_ack_old_regime > 0:
        result["Form10IEAEarlierAYAckOldRegime"] = form_10iea_earlier_ay_ack_old_regime

    result["F10IEAEarlierAYNewRegime"] = f10iea_earlier_ay_new_regime
    if ass_yr_f10iea_new_tax_reg:
        result["AssYrF10IEANewTaxReg"] = ass_yr_f10iea_new_tax_reg
    if form_10iea_earlier_ay_ack_new_regime > 0:
        result["Form10IEAEarlierAYAckNewRegime"] = form_10iea_earlier_ay_ack_new_regime

    result["F10IEACurrAYNewRegime"] = f10iea_curr_ay_new_regime
    if f10iea_date_curr_ay_new_tax:
        result["F10IEADateCurrAYNewTax"] = f10iea_date_curr_ay_new_tax
    if f10iea_ack_no_curr_ay_new_tax > 0:
        result["F10IEAAckNoCurrAYNewTax"] = f10iea_ack_no_curr_ay_new_tax

    result["F10IEACurrAYOldRegime"] = f10iea_curr_ay_old_regime
    if f10iea_date_curr_ay_old_tax:
        result["F10IEADateCurrAYOldTax"] = f10iea_date_curr_ay_old_tax
    if f10iea_ack_no_curr_ay_old_tax > 0:
        result["F10IEAAckNoCurrAYOldTax"] = f10iea_ack_no_curr_ay_old_tax

    return result


# ---------------------------------------------------------------------------
# ITR-4 DeductUndChapVIA — NO Section80GGA (unlike ITR-1)
# ---------------------------------------------------------------------------

def _chapter_via_itr4(
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
    ded_80ggc: Decimal = Decimal("0"),
    ded_80u: Decimal = Decimal("0"),
    ded_80tta: Decimal = Decimal("0"),
    ded_80ttb: Decimal = Decimal("0"),
    ded_80cch: Decimal = Decimal("0"),
) -> dict:
    """ITR-4 DeductUndChapVIA / UsrDeductUndChapVIA — NO Section80GGA."""
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
        "Section80GGC": _to_rupees(ded_80ggc),
        "Section80U": _to_rupees(ded_80u),
        "Section80TTA": _to_rupees(ded_80tta),
        "Section80TTB": _to_rupees(ded_80ttb),
        "AnyOthSec80CCH": _to_rupees(ded_80cch),
        "TotalChapVIADeductions": _to_rupees(deductions_total),
    }


# ---------------------------------------------------------------------------
# ITR-4 IncomeDeductions — different structure from ITR-1
# ---------------------------------------------------------------------------

def _income_deductions_itr4(
    gross_salary: Decimal,
    net_salary: Decimal,
    ded_us16: Decimal,
    ded_us16ia: Decimal,
    ded_us16ii: Decimal,
    ded_us16iii: Decimal,
    income_from_sal: Decimal,
    income_hp: Decimal,
    income_os: Decimal,
    presumptive_income: Decimal,
    gti: Decimal,
    gti_cg: Decimal,
    total_income: Decimal,
    deductions_total: Decimal,
    hp_schedules: Optional[list[dict]] = None,
    perquisites_value: Decimal = Decimal("0"),
    profits_in_lieu: Decimal = Decimal("0"),
) -> dict:
    """ITR-4 IncomeDeductions.

    Key differences from ITR-1:
    - Uses ``EntertainmntalwncUs16ii`` (not ``EntertainmentAlw16ii``)
    - Has ``IncomeFromBusinessProf`` at top
    - Has ``TaxExmpIntIncDtls`` instead of ``ExemptIncAgriOthUs10``
    """
    return {
        "IncomeFromBusinessProf": _to_rupees(presumptive_income),
        "GrossSalary": _to_rupees(gross_salary),
        "PerquisitesValue": _to_rupees(perquisites_value),
        "ProfitsInSalary": _to_rupees(profits_in_lieu),
        "Salary": _to_rupees(net_salary + ded_us16),
        "AllwncExemptUs10": {
            "AllwncExemptUs10Dtls": [],
            "TotalAllwncExemptUs10": 0,
        },
        "NetSalary": _to_rupees(net_salary),
        "DeductionUs16": _to_rupees(ded_us16),
        "DeductionUs16ia": _to_rupees(ded_us16ia),
        "EntertainmntalwncUs16ii": _to_rupees(ded_us16ii),
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
        "UsrDeductUndChapVIA": _chapter_via_itr4(
            deductions_total,
            ded_80c=_d("80C+80CCC+80CCD(1)"), ded_80ccc=_d("80CCC"),
            ded_80ccd1b=_d("80CCD(1B)"), ded_80ccd2=_d("80CCD(2)"),
            ded_80d=_d("80D"), ded_80dd=_d("80DD"), ded_80ddb=_d("80DDB"),
            ded_80u=_d("80U"), ded_80tta=_d("80TTA"), ded_80ttb=_d("80TTB"),
            ded_80e=_d("80E"), ded_80ee=_d("80EE"), ded_80eea=_d("80EEA"),
            ded_80eeb=_d("80EEB"), ded_80g=_d("80G"), ded_80gg=_d("80GG"),
            ded_80ggc=_d("80GGC"), ded_80cch=_d("80CCH"),
        ),
        "DeductUndChapVIA": _chapter_via_itr4(
            deductions_total,
            ded_80c=_d("80C+80CCC+80CCD(1)"), ded_80ccc=_d("80CCC"),
            ded_80ccd1b=_d("80CCD(1B)"), ded_80ccd2=_d("80CCD(2)"),
            ded_80d=_d("80D"), ded_80dd=_d("80DD"), ded_80ddb=_d("80DDB"),
            ded_80u=_d("80U"), ded_80tta=_d("80TTA"), ded_80ttb=_d("80TTB"),
            ded_80e=_d("80E"), ded_80ee=_d("80EE"), ded_80eea=_d("80EEA"),
            ded_80eeb=_d("80EEB"), ded_80g=_d("80G"), ded_80gg=_d("80GG"),
            ded_80ggc=_d("80GGC"), ded_80cch=_d("80CCH"),
        ),
        "TotalIncome": _to_rupees_rounded10(total_income),
    }


# ---------------------------------------------------------------------------
# ITR-4 TaxComputation — NO TotalIntrstPay, Section89 NOT required
# ---------------------------------------------------------------------------

def _tax_computation_itr4(
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
    """ITR-4 TaxComputation — no TotalIntrstPay, Section89 not required."""
    return {
        "TotalTaxPayable": _to_rupees_rounded10(slab_tax),
        "Rebate87A": _to_rupees_rounded10(rebate_87a),
        "TaxPayableOnRebate": _to_rupees_rounded10(tax_after_rebate),
        "EducationCess": _to_rupees_rounded10(cess),
        "GrossTaxLiability": _to_rupees_rounded10(gross_tax_liability),
        "Section89": _to_rupees_rounded10(relief_89),
        "NetTaxLiability": _to_rupees_rounded10(net_tax_liability),
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
# ITR-4 TaxPaid & Refund (same structure as ITR-1)
# ---------------------------------------------------------------------------

def _tax_paid_itr4(
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


def _refund_itr4(
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
# ITR-4 ScheduleBP (presumptive business income)
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
            "GrsTotalTrnOver": _to_rupees(gross_turnover),
            "GrsTrnOverBank": _to_rupees(digital_turnover),
            "GrsTotalTrnOverInCash": _to_rupees(cash_turnover),
            "GrsTrnOverAnyOthMode": _to_rupees(other_turnover),
            "PersumptiveInc44AD6Per": 0,
            "PersumptiveInc44AD8Per": 0,
            "TotPersumptiveInc44AD": _to_rupees(presumptive_income),
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
            "GrsReceipt": _to_rupees(gross_turnover),
            "GrsTrnOverBank44ADA": _to_rupees(digital_turnover),
            "GrsTotalTrnOverInCash44ADA": _to_rupees(cash_turnover),
            "GrsTrnOverAnyOthMode44ADA": _to_rupees(other_turnover),
            "TotPersumptiveInc44ADA": _to_rupees(presumptive_income),
        }
        bp["NatOfBus44ADA"] = [{
            "NameOfBusiness": "Profession",
            "CodeADA": "14001",
            "Description": "",
        }]
    elif scheme == "44AE":
        bp["PersumptiveInc44AE"] = {
            "TotPersumInc44AE": _to_rupees(presumptive_income),
            "SalInterestByFirm": 0,
            "TotalPersumptiveInc": _to_rupees(presumptive_income),
            "IncChargeableUnderBus": _to_rupees(presumptive_income),
        }
    else:
        bp["NatOfBus44AD"] = [{
            "NameOfBusiness": "Business",
            "CodeAD": "01001",
            "Description": "",
        }]
        cash_limit = gross_turnover * Decimal("0.05")
        if cash_turnover > cash_limit:
            bp["PersumptiveInc44AD"]["PersumptiveInc44AD8Per"] = _to_rupees(presumptive_income)
        else:
            bp["PersumptiveInc44AD"]["PersumptiveInc44AD6Per"] = _to_rupees(presumptive_income)

    return bp


# ---------------------------------------------------------------------------
# ITR-4 ScheduleIT — challan payment array (NOT turnover summary!)
# ---------------------------------------------------------------------------

def _schedule_it_itr4(
    advance_tax: Decimal,
    self_assessment_tax: Decimal,
) -> dict:
    """ITR-4 ScheduleIT — TaxPayment array of challans."""
    challans = []
    if advance_tax > 0:
        challans.append({
            "BSRCode": "1234567",
            "DateDep": "2025-06-15",
            "SrlNoOfChaln": 1,
            "Amt": _to_rupees(advance_tax),
        })
    if self_assessment_tax > 0:
        challans.append({
            "BSRCode": "1234567",
            "DateDep": "2025-07-15",
            "SrlNoOfChaln": 2,
            "Amt": _to_rupees(self_assessment_tax),
        })
    return {
        "TaxPayment": challans,
        "TotalTaxPayments": _to_rupees(advance_tax + self_assessment_tax),
    }


# ---------------------------------------------------------------------------
# ITR-4 Schedule80G (same fields as ITR-1)
# ---------------------------------------------------------------------------

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


def _schedule_80c(total_amt: Decimal) -> dict:
    return {
        "Schedule80CDtls": [],
        "TotalAmt": _to_rupees(total_amt),
    }


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


def _tds_salary_schedule_itr4(tds_salary_entries: Optional[list[dict]] = None) -> Optional[dict]:
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


def _tds_other_schedule_itr4(tds_other_entries: Optional[list[dict]] = None) -> Optional[dict]:
    """ITR-4 TDS on other than salary — uses ``TDSonOthThanSalDtls`` key."""
    if not tds_other_entries:
        return None
    total = sum(
        (e.get("TDSClaimed", 0) if isinstance(e, dict) else 0)
        for e in tds_other_entries
    )
    return {
        "TDSonOthThanSalDtls": [
            {
                "TANOfDeductor": e.get("TAN", "DELA00001A"),
                "DeductedYr": e.get("DeductedYr", "2025"),
                "TDSSection": e.get("TDSSection", "193"),
                "TDSClaimed": e.get("TDSClaimed", 0),
                "GrossAmount": e.get("GrossAmount", 0),
                "HeadOfIncome": e.get("HeadOfIncome", "OS"),
                "TDSCreditCarriedFwd": e.get("TDSCreditCarriedFwd", 0),
            }
            for e in tds_other_entries
        ],
        "TotalTDSonOthThanSals": total,
    }


# ============================================================================
# Public API
# ============================================================================

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
    assesee_status: str = "I",
    itr4_return_file_sec: int = 11,
    father_name: str = "",
    ver_place: str = "Delhi",
    bank_name: str = "BankName",
    account_no: str = "0000000001",
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
    form_10iea_earlier_ay_old_regime: str = "NA",
    form_10iea_ass_year: str = "",
    form_10iea_earlier_ay_ack_old_regime: int = 0,
    f10iea_earlier_ay_new_regime: str = "N",
    ass_yr_f10iea_new_tax_reg: str = "",
    form_10iea_earlier_ay_ack_new_regime: int = 0,
    f10iea_curr_ay_new_regime: str = "N",
    f10iea_date_curr_ay_new_tax: str = "",
    f10iea_ack_no_curr_ay_new_tax: int = 0,
    f10iea_curr_ay_old_regime: str = "N",
    f10iea_date_curr_ay_old_tax: str = "",
    f10iea_ack_no_curr_ay_old_tax: int = 0,
    phone_std_code: int = 0,
    phone_no: str = "0",
) -> dict:
    """Build an ITD-compliant ITR-4 JSON document."""

    assessee_name = f"{first_name} {last_name}".strip()

    personal = _personal_info_base(
        pan=pan, first_name=first_name, middle_name=middle_name, last_name=last_name,
        dob=dob, employer_category=employer_category,
        residence_no=residence_no, locality=locality, city=city,
        state_code=state_code, country_code=country_code,
        mobile_no=mobile_no, email=email, aadhaar=aadhaar,
        secondary_add=secondary_add, pin_code=pin_code,
    )
    # ITR-4-specific additions
    personal["Status"] = assesee_status
    if "Address" in personal:
        personal["Address"].pop("EmailAddressSec", None)
        personal["Address"]["Phone"] = {
            "STDcode": phone_std_code,
            "PhoneNo": phone_no,
        }

    ver = _verification(
        assessee_name=assessee_name or "ASSESSEE",
        father_name=father_name or "FATHER",
        pan=pan,
        place=ver_place,
    )

    filing = _filing_status_itr4(
        return_file_sec=itr4_return_file_sec,
        form_10iea_earlier_ay_old_regime=form_10iea_earlier_ay_old_regime,
        form_10iea_ass_year=form_10iea_ass_year,
        form_10iea_earlier_ay_ack_old_regime=form_10iea_earlier_ay_ack_old_regime,
        f10iea_earlier_ay_new_regime=f10iea_earlier_ay_new_regime,
        ass_yr_f10iea_new_tax_reg=ass_yr_f10iea_new_tax_reg,
        form_10iea_earlier_ay_ack_new_regime=form_10iea_earlier_ay_ack_new_regime,
        f10iea_curr_ay_new_regime=f10iea_curr_ay_new_regime,
        f10iea_date_curr_ay_new_tax=f10iea_date_curr_ay_new_tax,
        f10iea_ack_no_curr_ay_new_tax=f10iea_ack_no_curr_ay_new_tax,
        f10iea_curr_ay_old_regime=f10iea_curr_ay_old_regime,
        f10iea_date_curr_ay_old_tax=f10iea_date_curr_ay_old_tax,
        f10iea_ack_no_curr_ay_old_tax=f10iea_ack_no_curr_ay_old_tax,
    )

    # -- Extract per-section deduction amounts from breakdown --------------
    # DeductionResult is a dataclass with a .breakdown dict attribute.
    # Rebind the module-level _DED_BREAKDOWN so _income_deductions_itr4
    # (which calls module-level _d()) sees the correct breakdown.
    ded_sched = result.schedules.get("deductions") if result.schedules else None
    global _DED_BREAKDOWN
    _DED_BREAKDOWN = getattr(ded_sched, "breakdown", {}) if ded_sched else {}

    gti_cg = result.gross_total_income  # Already includes capital_gains_112a
    income = _income_deductions_itr4(
        gross_salary=result.salary_gross,
        net_salary=result.salary_net,
        ded_us16=result.salary_deduction_us16,
        ded_us16ia=result.salary_deduction_us16ia,
        ded_us16ii=result.salary_entertainment_allowance,
        ded_us16iii=result.salary_professional_tax,
        income_from_sal=result.salary_income,
        income_hp=result.house_property_income,
        income_os=result.other_sources_income,
        presumptive_income=result.presumptive_income,
        gti=result.gross_total_income - result.capital_gains_112a,
        gti_cg=gti_cg,
        total_income=result.taxable_income,
        deductions_total=result.deductions_total,
        perquisites_value=result.salary_perquisites,
        profits_in_lieu=result.salary_profits_in_lieu,
    )

    tax = _tax_computation_itr4(
        slab_tax=result.slab_tax,
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

    tax_paid = _tax_paid_itr4(
        total_tds=result.total_tds,
        total_tcs=result.total_tcs,
        advance_tax=result.advance_tax_paid,
        self_assessment_tax=result.self_assessment_tax_paid,
        balance_payable=result.balance_payable,
    )

    refund = _refund_itr4(
        refund_due=result.refund_due,
        bank_name=bank_name,
        account_no=account_no,
        ifsc=ifsc,
    )

    bp = _schedule_bp(
        gross_turnover=_zero_if_none(bp_gross_turnover),
        digital_turnover=_zero_if_none(bp_digital_turnover),
        cash_turnover=_zero_if_none(bp_cash_turnover),
        other_turnover=_zero_if_none(bp_other_turnover),
        presumptive_income=result.presumptive_income,
        scheme=bp_scheme,
    )

    # ── Assemble ITR-4 ─────────────────────────────────────────────────

    itr4: dict[str, Any] = {
        "CreationInfo": _creation_info(),
        "Form_ITR4": _form_itr("ITR-4"),
        "PersonalInfo": personal,
        "FilingStatus": filing,
        "IncomeDeductions": income,
        "TaxComputation": tax,
        "TaxPaid": tax_paid,
        "Refund": refund,
        "Verification": ver,
        "ScheduleBP": bp,
        "ScheduleIT": _schedule_it_itr4(
            advance_tax=result.advance_tax_paid,
            self_assessment_tax=result.self_assessment_tax_paid,
        ),
        "TaxExmpIntIncDtls": {
            "OthersInc": {
                "OthersIncDtls": [],
                "OthersTotalTaxExe": 0,
            }
        },
        "Schedule80G": _schedule_80g(Decimal("0"), _d("80G")),
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
            "DeductionAmount": int(_d("80DD")),
            "DependentType": "1",
            "DependentPan": "AAAAA0000A",
            "DependentAadhaar": "000000000000",
            "Form10IAAckNum": "",
            "UDIDNum": "",
        },
        "Schedule80U": {
            "NatureOfDisability": "1",
            "TypeOfDisability": "2",
            "DeductionAmount": int(_d("80U")),
            "Form10IAAckNum": "",
            "UDIDNum": "",
        },
        "Schedule80E": {
            "Schedule80EDtls": [],
            "TotalInterest80E": int(_d("80E")),
        },
        "Schedule80EE": {
            "Schedule80EEDtls": [],
            "TotalInterest80EE": int(_d("80EE")),
        },
        "Schedule80EEA": {
            "PropStmpDtyVal": 0,
            "Schedule80EEADtls": [],
            "TotalInterest80EEA": int(_d("80EEA")),
        },
        "Schedule80EEB": {
            "Schedule80EEBDtls": [],
            "TotalInterest80EEB": int(_d("80EEB")),
        },
        "Schedule80C": _schedule_80c(_d("80C+80CCC+80CCD(1)")),
        "TaxReturnPreparer": _tax_return_preparer(),
    }

    # Conditional: ScheduleTDS3Dtls (minItems:1 on TDS3Details — omit if empty)

    # Conditional: TDS on Salary
    tds_sal = _tds_salary_schedule_itr4(tds_salary_entries)
    if tds_sal:
        itr4["TDSonSalaries"] = tds_sal

    # Conditional: TDS Other (uses ITR-4-specific key)
    tds_oth = _tds_other_schedule_itr4(tds_other_entries)
    if tds_oth:
        itr4["TDSonOthThanSals"] = tds_oth

    # Conditional: TCS
    if result.total_tcs > 0:
        itr4["ScheduleTCS"] = {
            "TCS": [{"EmployerOrDeductorOrCollectDetl": {"TAN": "DELA00001A"}, "AmtTCSClaimedThisYear": _to_rupees(result.total_tcs)}],
            "TotalSchTCS": _to_rupees(result.total_tcs),
        }

    # Conditional: LTCG 112A
    if cg_sale_consideration is not None and cg_cost_acquisition is not None:
        itr4["LTCG112A"] = _ltcg_112a_schedule(
            sale_consideration=cg_sale_consideration,
            cost_acquisition=cg_cost_acquisition,
            long_cap_112a=result.capital_gains_112a,
        )

    itr4["CreationInfo"]["Digest"] = _compute_digest(itr4)

    return {"ITR": {"ITR4": itr4}}
