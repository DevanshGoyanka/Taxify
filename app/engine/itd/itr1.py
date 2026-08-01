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
from typing import Any, Mapping, Optional

from app.engine.calculators.itr1 import ITR1Result
from app.schemas.itr1 import BankAccountType, ITR1Input


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
    allowance_rows: Optional[list[dict]] = None,
    other_source_rows: Optional[list[dict]] = None,
    deduction_57iia: Decimal = Decimal("0"),
    exempt_income_rows: Optional[list[dict]] = None,
    exempt_income_total: Decimal = Decimal("0"),
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
            "AllwncExemptUs10Dtls": allowance_rows or [],
            "TotalAllwncExemptUs10": sum(
                row["SalOthAmount"] for row in (allowance_rows or [])
            ),
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
            "OthersIncDtlsOthSrc": other_source_rows or [],
        },
        "DeductionUs57iia": _to_rupees(deduction_57iia),
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
            "ExemptIncAgriOthUs10Dtls": exempt_income_rows or [],
            "ExemptIncAgriOthUs10Total": _to_rupees(exempt_income_total),
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
    bank_accounts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the mandatory refund section from real bank-account rows."""
    if not bank_accounts:
        raise ValueError("At least one bank account is required for ITD JSON")
    return {
        "RefundDue": _to_rupees_rounded10(refund_due),
        "BankAccountDtls": {"AddtnlBankDetails": bank_accounts},
    }


def _bank_row(
    *,
    ifsc: str,
    bank_name: str,
    account_number: str,
    account_type: str,
    use_for_refund: bool,
) -> dict[str, Any]:
    """Build one official bank-account row."""
    return {
        "IFSCCode": ifsc,
        "BankName": bank_name,
        "BankAccountNo": account_number,
        "AccountType": account_type,
        "UseForRefund": "true" if use_for_refund else "false",
    }


def _bank_accounts_from_input(input_data: ITR1Input) -> list[dict[str, Any]]:
    """Map validated bank accounts to official account codes without defaults."""
    primary_count = sum(account.is_primary for account in input_data.bank_accounts)
    if primary_count != 1:
        raise ValueError("Exactly one bank account must be selected for refund")
    rows: list[dict[str, Any]] = []
    for account in input_data.bank_accounts:
        if not account.bank_name:
            raise ValueError("Every bank account requires bank_name for ITD JSON")
        rows.append(_bank_row(
            ifsc=account.ifsc_code,
            bank_name=account.bank_name,
            account_number=account.account_number,
            account_type=BankAccountType(account.account_type).itd_code,
            use_for_refund=account.is_primary,
        ))
    return rows


# ---------------------------------------------------------------------------
# ITR-1 Schedule helpers
# ---------------------------------------------------------------------------

def _schedule_80d(
    senior_flag_self: str,
    senior_flag_parents: str,
    self_premium: Decimal,
    parents_premium: Decimal,
    preventive_self: Decimal,
    preventive_parents: Decimal,
    eligible_deduction: Decimal,
) -> dict:
    return {
        "Sec80DSelfFamSrCtznHealth": {
            "SeniorCitizenFlag": senior_flag_self,
            "SelfAndFamily": _to_rupees(self_premium) if senior_flag_self == "N" else 0,
            "HealthInsPremSlfFam": _to_rupees(self_premium) if senior_flag_self == "N" else 0,
            "Sec80DSelfFamHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_rupees(self_premium) if senior_flag_self == "N" else 0,
            },
            "PrevHlthChckUpSlfFam": _to_rupees(preventive_self) if senior_flag_self == "N" else 0,
            "SelfAndFamilySeniorCitizen": _to_rupees(self_premium) if senior_flag_self == "Y" else 0,
            "HlthInsPremSlfFamSrCtzn": _to_rupees(self_premium) if senior_flag_self == "Y" else 0,
            "Sec80DSelfFamSrCtznHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_rupees(self_premium) if senior_flag_self == "Y" else 0,
            },
            "PrevHlthChckUpSlfFamSrCtzn": _to_rupees(preventive_self) if senior_flag_self == "Y" else 0,
            "MedicalExpSlfFamSrCtzn": 0,
            "ParentsSeniorCitizenFlag": senior_flag_parents,
            "Parents": _to_rupees(parents_premium) if senior_flag_parents == "N" else 0,
            "HlthInsPremParents": _to_rupees(parents_premium) if senior_flag_parents == "N" else 0,
            "Sec80DParentsHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_rupees(parents_premium) if senior_flag_parents == "N" else 0,
            },
            "PrevHlthChckUpParents": _to_rupees(preventive_parents) if senior_flag_parents == "N" else 0,
            "ParentsSeniorCitizen": _to_rupees(parents_premium) if senior_flag_parents == "Y" else 0,
            "HlthInsPremParentsSrCtzn": _to_rupees(parents_premium) if senior_flag_parents == "Y" else 0,
            "Sec80DParentsSrCtznHIDtls": {
                "Sch80DInsDtls": [],
                "TotalPayments": _to_rupees(parents_premium) if senior_flag_parents == "Y" else 0,
            },
            "PrevHlthChckUpParentsSrCtzn": _to_rupees(preventive_parents) if senior_flag_parents == "Y" else 0,
            "MedicalExpParentsSrCtzn": 0,
            "EligibleAmountOfDedn": _to_rupees(eligible_deduction),
        }
    }


def _schedule_80c(input_data: ITR1Input, total_amt: Decimal) -> dict[str, Any]:
    """Build Schedule 80C rows allocated to the allowed capped deduction."""
    positive_entries = [
        entry for entry in input_data.schedule_80c_entries if entry.amount > 0
    ]
    if total_amt > 0 and not positive_entries:
        raise ValueError(
            "A positive Section 80C claim requires Schedule 80C detail rows"
        )
    raw_total = sum((entry.amount for entry in positive_entries), Decimal("0"))
    rows: list[dict[str, Any]] = []
    allocated = Decimal("0")
    for index, entry in enumerate(positive_entries):
        if not entry.identifier_number:
            raise ValueError("Schedule 80C entries require identifier_number")
        if index == len(positive_entries) - 1:
            allowed_amount = total_amt - allocated
        else:
            allowed_amount = (entry.amount / raw_total * total_amt).quantize(Decimal("1"))
            allocated += allowed_amount
        rows.append({
            "IdentificationNo": entry.identifier_number,
            "Amount": _to_rupees(max(Decimal("0"), allowed_amount)),
        })
    return {
        "Schedule80CDtls": rows,
        "TotalAmt": sum(row["Amount"] for row in rows),
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


def _positive_rows(
    values: Mapping[str, Decimal],
    label_key: str,
    amount_key: str,
) -> list[dict[str, Any]]:
    """Convert positive labelled amounts to official two-column row objects."""
    return [
        {label_key: label, amount_key: _to_rupees(amount)}
        for label, amount in values.items()
        if amount > 0
    ]


def _allowance_rows(input_data: Optional[ITR1Input]) -> list[dict[str, Any]]:
    """Build Section 10 salary-exemption rows from validated input."""
    if input_data is None:
        return []
    salary = input_data.salary_income
    amounts = {
        "10(5)": salary.lta_exempt_amount,
        "10(6)": salary.sec10_6_embassy_exempt,
        "10(7)": salary.sec10_7_foreign_allowance,
        "10(10)": salary.gratuity_received,
        "10(10A)": salary.commuted_pension_received,
        "10(10AA)": salary.leave_encashment_received,
        "10(10B)(i)": salary.retrenchment_compensation,
        "10(10C)": salary.vrs_compensation,
        "10(10CC)": salary.sec10_10cc_perquisite_tax,
        "10(13A)": salary.hra_exempt_amount,
        "10(14)(i)": salary.sec10_14i_prescribed_allowance,
        "10(14)(ii)": salary.sec10_14ii_personal_allowance,
    }
    return _positive_rows(amounts, "SalNatureDesc", "SalOthAmount")


def _other_source_rows(result: ITR1Result) -> list[dict[str, Any]]:
    """Build exact other-source category rows retained by the calculator."""
    schedule = result.schedules.get("os") if result.schedules else None
    if schedule is None:
        return []
    amounts = {
        "SAV": schedule.savings_bank_interest,
        "IFD": schedule.fixed_deposit_interest,
        "TAX": schedule.interest_on_it_refund,
        "FAP": schedule.family_pension_gross,
        "DIV": schedule.dividend_income,
    }
    return _positive_rows(amounts, "OthSrcNatureDesc", "OthSrcOthAmount")


def _exempt_income_rows(input_data: Optional[ITR1Input]) -> list[dict[str, Any]]:
    """Build exempt-income rows that can be represented without invention."""
    if input_data is None or input_data.agriculture_income <= 0:
        return []
    return [{
        "Category": "AGRI",
        "SubCategory": "10(1)",
        "Description": "Agricultural income",
        "OthAmount": _to_rupees(input_data.agriculture_income),
    }]


def _official_tds_section(section: str) -> str:
    """Translate an Income-tax Act section label to the official schema code."""
    normalized = section.strip().upper().replace("SECTION", "").replace(" ", "")
    direct_codes = {
        "192A", "193", "194", "195",
    }
    if normalized in direct_codes:
        return normalized
    if normalized.startswith("194"):
        return f"9{normalized[2:]}"
    if normalized.startswith("196"):
        return f"9{normalized[2:]}"
    return normalized


def _tds_salary_from_input(input_data: ITR1Input) -> Optional[dict[str, Any]]:
    """Build Schedule TDS1 exclusively from validated Form 16 rows."""
    rows = []
    for entry in input_data.tds1_entries or []:
        if not entry.employer_tan or not entry.employer_name:
            raise ValueError("TDS1 entries require employer TAN and name for ITD JSON")
        rows.append({
            "EmployerOrDeductorOrCollectDetl": {
                "TAN": entry.employer_tan,
                "EmployerOrDeductorOrCollecterName": entry.employer_name,
            },
            "IncChrgSal": _to_rupees(entry.income_chargeable),
            "TotalTDSSal": _to_rupees(entry.tds_deducted),
        })
    if not rows:
        return None
    return {
        "TDSonSalary": rows,
        "TotalTDSonSalaries": sum(row["TotalTDSSal"] for row in rows),
    }


def _tds_other_from_input(input_data: ITR1Input) -> Optional[dict[str, Any]]:
    """Build Schedule TDS2 exclusively from validated Form 16A rows."""
    rows = []
    for entry in input_data.tds2_entries or []:
        if not entry.deductor_name:
            raise ValueError("TDS2 entries require deductor name for ITD JSON")
        rows.append({
            "EmployerOrDeductorOrCollectDetl": {
                "TAN": entry.deductor_tan,
                "EmployerOrDeductorOrCollecterName": entry.deductor_name,
            },
            "TDSSection": _official_tds_section(entry.tds_section),
            "AmtForTaxDeduct": _to_rupees(entry.gross_amount),
            "DeductedYr": "2025",
            "TotTDSOnAmtPaid": _to_rupees(entry.tds_deducted),
            "ClaimOutOfTotTDSOnAmtPaid": _to_rupees(entry.tds_claimed_this_year),
        })
    if not rows:
        return None
    return {
        "TDSonOthThanSal": rows,
        "TotalTDSonOthThanSals": sum(
            row["ClaimOutOfTotTDSOnAmtPaid"] for row in rows
        ),
    }


def _tcs_from_input(input_data: ITR1Input) -> Optional[dict[str, Any]]:
    """Build Schedule TCS exclusively from validated collector rows."""
    rows = []
    for entry in input_data.tcs_entries or []:
        if not entry.collector_name:
            raise ValueError("TCS entries require collector name for ITD JSON")
        rows.append({
            "EmployerOrDeductorOrCollectDetl": {
                "TAN": entry.collector_tan,
                "EmployerOrDeductorOrCollecterName": entry.collector_name,
            },
            "AmtTaxCollected": _to_rupees(entry.gross_amount),
            "CollectedYr": "2025",
            "TotalTCS": _to_rupees(entry.tcs_collected),
            "AmtTCSClaimedThisYear": _to_rupees(entry.tcs_credit_claimed),
        })
    if not rows:
        return None
    return {
        "TCS": rows,
        "TotalSchTCS": sum(row["AmtTCSClaimedThisYear"] for row in rows),
    }


def _tax_payments_from_input(input_data: ITR1Input) -> Optional[dict[str, Any]]:
    """Build Schedule IT from complete challan rows without fabricating data."""
    rows = []
    for entry in input_data.tax_payment_entries:
        if not entry.bsr_code or not entry.payment_date or not entry.challan_serial_number:
            raise ValueError(
                "Tax payment entries require BSR code, payment date, and challan serial number"
            )
        rows.append({
            "BSRCode": entry.bsr_code,
            "DateDep": entry.payment_date.isoformat(),
            "SrlNoOfChaln": int(entry.challan_serial_number),
            "Amt": _to_rupees(entry.amount),
        })
    if not rows:
        return None
    return {
        "TaxPayment": rows,
        "TotalTaxPayments": sum(row["Amt"] for row in rows),
    }


# ============================================================================
# Public API
# ============================================================================

def build_itr1_json(
    result: ITR1Result,
    input_data: Optional[ITR1Input] = None,
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
    bank_name: Optional[str] = None,
    account_no: Optional[str] = None,
    ifsc: Optional[str] = None,
    tds_salary_entries: Optional[list[dict]] = None,
    tds_other_entries: Optional[list[dict]] = None,
    hra_received: Optional[Decimal] = None,
    rent_paid: Optional[Decimal] = None,
    hra_metro: bool = False,
    schedule_80d_senior_self: str = "N",
    schedule_80d_senior_parents: str = "N",
    schedule_80d_self_premium: Optional[Decimal] = None,
    schedule_80d_parents_premium: Optional[Decimal] = None,
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

    # -- Extract per-section deduction amounts from the request-local result --
    ded_sched = result.schedules.get("deductions") if result.schedules else None
    ded_breakdown: Mapping[str, Decimal] = (
        getattr(ded_sched, "breakdown", {}) if ded_sched else {}
    )

    def deduction(key: str) -> Decimal:
        """Return one computed deduction amount for this build only."""
        if key == "80C":
            combined = ded_breakdown.get("80C+80CCC+80CCD(1)", Decimal("0"))
            return max(
                Decimal("0"),
                combined
                - ded_breakdown.get("80CCC", Decimal("0"))
                - ded_breakdown.get("80CCD(1)", Decimal("0")),
            )
        return ded_breakdown.get(key, Decimal("0"))

    os_schedule = result.schedules.get("os") if result.schedules else None
    allowance_rows = _allowance_rows(input_data)
    other_source_rows = _other_source_rows(result)
    exempt_income_rows = _exempt_income_rows(input_data)
    exempt_income_total = (
        input_data.agriculture_income if input_data is not None else Decimal("0")
    )

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
        allowance_rows=allowance_rows,
        other_source_rows=other_source_rows,
        deduction_57iia=(os_schedule.deduction_57iia if os_schedule else Decimal("0")),
        exempt_income_rows=exempt_income_rows,
        exempt_income_total=exempt_income_total,
        perquisites_value=result.salary_perquisites,
        profits_in_lieu=result.salary_profits_in_lieu,
        ded_80c=deduction("80C"), ded_80ccc=deduction("80CCC"), ded_80ccd1=deduction("80CCD(1)"),
        ded_80ccd1b=deduction("80CCD(1B)"),
        ded_80ccd2=deduction("80CCD(2)"),
        ded_80d=deduction("80D"),
        ded_80dd=deduction("80DD"),
        ded_80ddb=deduction("80DDB"),
        ded_80u=deduction("80U"),
        ded_80tta=deduction("80TTA"),
        ded_80ttb=deduction("80TTB"),
        ded_80e=deduction("80E"),
        ded_80ee=deduction("80EE"),
        ded_80eea=deduction("80EEA"),
        ded_80eeb=deduction("80EEB"),
        ded_80g=deduction("80G"),
        ded_80gg=deduction("80GG"),
        ded_80gga=deduction("80GGA"),
        ded_80ggc=deduction("80GGC"),
        ded_80cch=deduction("80CCH"),
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

    if input_data is not None:
        bank_rows = _bank_accounts_from_input(input_data)
    elif bank_name and account_no and ifsc:
        bank_rows = [_bank_row(
            ifsc=ifsc,
            bank_name=bank_name,
            account_number=account_no,
            account_type="SB",
            use_for_refund=True,
        )]
    else:
        raise ValueError("Bank account details are required for ITD JSON")
    refund = _refund_itr1(result.refund_due, bank_rows)

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
    }

    if input_data is not None:
        if deduction("80C") > 0 or input_data.schedule_80c_entries:
            itr1["Schedule80C"] = _schedule_80c(input_data, deduction("80C"))

        if deduction("80D") > 0:
            ded_input = input_data.deductions_chapter6a
            schedule_80d = input_data.schedule_80d
            self_flag = (
                "S" if schedule_80d and schedule_80d.not_claiming_self
                else "Y" if input_data.age_bracket.value != "below_60"
                else "N"
            )
            parents_flag = (
                "P" if schedule_80d and schedule_80d.not_claiming_parents
                else "Y" if ded_input.has_parents_senior
                else "N"
            )
            itr1["Schedule80D"] = _schedule_80d(
                senior_flag_self=self_flag,
                senior_flag_parents=parents_flag,
                self_premium=ded_input.amount_80d_self_family,
                parents_premium=ded_input.amount_80d_parents,
                preventive_self=ded_input.amount_80d_preventive_self,
                preventive_parents=ded_input.amount_80d_preventive_parents,
                eligible_deduction=deduction("80D"),
            )

        incomplete_claims = {
            "80G": deduction("80G"),
            "80GGA": deduction("80GGA"),
            "80GGC": deduction("80GGC"),
            "80DD": deduction("80DD"),
            "80DDB": deduction("80DDB"),
            "80U": deduction("80U"),
            "80E": deduction("80E"),
            "80EE": deduction("80EE"),
            "80EEA": deduction("80EEA"),
            "80EEB": deduction("80EEB"),
        }
        unsupported = [name for name, amount in incomplete_claims.items() if amount > 0]
        if unsupported:
            raise ValueError(
                "Complete official schedule details are required for: "
                + ", ".join(unsupported)
            )

        hra = input_data.hra_details or input_data.schedule_10_13a
        if hra is not None:
            hra_schedule = _schedule_ea10_13a(
                place_of_work=("1" if hra.is_metro_city else "2"),
                hra_received=hra.actual_hra_received,
                rent_paid=hra.rent_paid,
                basic_salary=hra.salary_for_hra,
            )
            claimed_hra = _to_rupees(input_data.salary_income.hra_exempt_amount)
            if hra_schedule["EligbleExmpAllwncUs13A"] != claimed_hra:
                raise ValueError(
                    "Schedule 10(13A) eligible exemption must equal the HRA exemption claimed"
                )
            itr1["ScheduleEA10_13A"] = hra_schedule
    else:
        # Legacy callers may still provide aggregate schedules explicitly.
        if deduction("80C") > 0:
            raise ValueError("Schedule 80C detail rows are required for ITD JSON")
        if deduction("80D") > 0:
            itr1["Schedule80D"] = _schedule_80d(
                senior_flag_self=schedule_80d_senior_self,
                senior_flag_parents=schedule_80d_senior_parents,
                self_premium=_zero_if_none(schedule_80d_self_premium),
                parents_premium=_zero_if_none(schedule_80d_parents_premium),
                preventive_self=Decimal("0"),
                preventive_parents=Decimal("0"),
                eligible_deduction=deduction("80D"),
            )

    if input_data is not None:
        tds_salary = _tds_salary_from_input(input_data)
        if tds_salary:
            itr1["TDSonSalaries"] = tds_salary

        tds_other = _tds_other_from_input(input_data)
        if tds_other:
            itr1["TDSonOthThanSals"] = tds_other

        tcs = _tcs_from_input(input_data)
        if tcs:
            itr1["ScheduleTCS"] = tcs

        tax_payments = _tax_payments_from_input(input_data)
        if tax_payments:
            itr1["TaxPayments"] = tax_payments

        if input_data.tds3_entries:
            raise ValueError(
                "TDS3 ITD JSON requires tenant PAN and name, which are absent from the input model"
            )
    else:
        # Compatibility path for legacy callers that supply already-mapped rows.
        tds_salary = _tds_salary_schedule_itr1(tds_salary_entries)
        if tds_salary:
            itr1["TDSonSalaries"] = tds_salary
        tds_other = _tds_other_schedule_itr1(tds_other_entries)
        if tds_other:
            itr1["TDSonOthThanSals"] = tds_other

    # TDS3 is optional; emitting an empty details array violates minItems=1.

    # Conditional: LTCG 112A
    if cg_sale_consideration is not None and cg_cost_acquisition is not None:
        itr1["LTCG112A"] = _ltcg_112a_schedule(
            sale_consideration=cg_sale_consideration,
            cost_acquisition=cg_cost_acquisition,
            long_cap_112a=result.capital_gains_112a,
        )

    itr1["CreationInfo"]["Digest"] = _compute_digest(itr1)

    return {"ITR": {"ITR1": itr1}}
