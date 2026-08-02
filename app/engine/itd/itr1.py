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
from app.engine.constants import (
    SECTION_80DD_LIMIT,
    SECTION_80DD_SEVERE_LIMIT,
    SECTION_80U_LIMIT,
    SECTION_80U_SEVERE_LIMIT,
)
from app.engine.schedules.deductions.section_80gga import Section80GGAResult
from app.engine.schedules.deductions.section_80ggc import Section80GGCResult
from app.engine.schedules.deductions.section_80c import Section80CResult
from app.engine.schedules.deductions._loan_common import LoanDeductionResult
from app.schemas.itr1 import (
    BankAccountType,
    FilingAddress,
    ITR1FilingProfile,
    ITR1Input,
    PostalAddress,
    PropertyFilingProfile,
)


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


def _address_from_profile(address: PostalAddress, *, include_contact: bool) -> dict[str, Any]:
    """Map a typed filing address to the official address structure."""
    mapped: dict[str, Any] = {
        "ResidenceNo": address.residence_no,
        "ResidenceName": address.residence_name,
        "RoadOrStreet": address.road_or_street,
        "LocalityOrArea": address.locality_or_area,
        "CityOrTownOrDistrict": address.city_or_town_or_district,
        "StateCode": address.state_code,
        "CountryCode": address.country_code,
        "ZipCode": address.zip_code,
    }
    if address.pin_code is not None:
        mapped["PinCode"] = int(address.pin_code)
    if include_contact:
        if not isinstance(address, FilingAddress):
            raise ValueError("Primary filing address requires contact details")
        mapped.update({
            "CountryCodeMobile": address.mobile_country_code,
            "MobileNo": int(address.mobile_no),
            "CountryCodeMobileNoSec": 0,
            "MobileNoSec": 0,
            "EmailAddress": address.email,
        })
    return mapped


def _personal_info_from_profile(profile: ITR1FilingProfile) -> dict[str, Any]:
    """Build official personal information exclusively from real profile data."""
    personal: dict[str, Any] = {
        "AssesseeName": {
            "FirstName": profile.first_name,
            "MiddleName": profile.middle_name,
            "SurNameOrOrgName": profile.surname,
        },
        "PAN": profile.pan,
        "Address": _address_from_profile(profile.primary_address, include_contact=True),
        "SecondaryAdd": "Y" if profile.alternate_address else "N",
        "DOB": profile.date_of_birth.isoformat(),
        "EmployerCategory": profile.employer_category,
    }
    if profile.alternate_address is not None:
        personal["AlternateAddress"] = _address_from_profile(
            profile.alternate_address,
            include_contact=False,
        )
    if profile.aadhaar_number is not None:
        personal["AadhaarCardNo"] = profile.aadhaar_number
    return personal


def _verification_from_profile(profile: ITR1FilingProfile) -> dict[str, Any]:
    """Build official verification from the typed filing profile."""
    full_name = " ".join(
        part for part in (profile.first_name, profile.middle_name, profile.surname) if part
    )
    return _verification(
        assessee_name=full_name,
        father_name=profile.father_name,
        pan=profile.pan,
        place=profile.verification_place,
        capacity=profile.verification_capacity,
    )


def _property_schedule(
    result: ITR1Result,
    input_data: ITR1Input,
    profile: PropertyFilingProfile,
) -> list[dict[str, Any]]:
    """Build the single self-owned house-property schedule from computed values."""
    if input_data.is_property_co_owned or input_data.co_ownership_details is not None:
        raise ValueError("Co-owned property ITD JSON is not implemented")
    hp_input = input_data.house_property_income
    if hp_input.home_loan_interest_paid > 0:
        raise ValueError("Section 24(b) loan details are required for ITD JSON")
    hp = result.schedules.get("hp") if result.schedules else None
    if hp is None:
        raise ValueError("Computed house-property schedule is missing")

    annual_value = _to_rupees(hp.gross_annual_value)
    balance = _to_rupees(hp.net_annual_value)
    local_taxes = annual_value - balance
    if local_taxes < 0:
        raise ValueError("House-property municipal taxes do not cross-foot")
    total_unrealized_and_tax = local_taxes
    owned_value = balance
    interest = _to_rupees(hp.interest_on_loan)
    arrears = _to_rupees(hp.arrears_unrealised_rent)
    arrears_taxable = _to_rupees(hp.arrears_unrealised_rent * Decimal("0.7"))
    income = _to_rupees(hp.income_chargeable)
    standard_deduction = owned_value - interest + arrears_taxable - income
    if standard_deduction < 0:
        raise ValueError("House-property deduction does not cross-foot")
    total_deduction = standard_deduction + interest

    address: dict[str, Any] = {
        "AddrDetail": profile.address_detail,
        "CityOrTownOrDistrict": profile.city_or_town_or_district,
        "StateCode": profile.state_code,
        "CountryCode": profile.country_code,
    }
    if profile.pin_code is not None:
        address["PinCode"] = int(profile.pin_code)
    if profile.zip_code is not None:
        address["ZipCode"] = profile.zip_code

    rent_details: dict[str, Any] = {
        "AnnualLetableValue": annual_value,
        "TotalUnrealizedAndTax": total_unrealized_and_tax,
        "BalanceALV": balance,
        "AnnualOfPropOwned": owned_value,
        "ThirtyPercentOfBalance": standard_deduction,
        "IntOnBorwCap": interest,
        "TotalDeduct": total_deduction,
        "IncomeOfHP": income,
    }
    if local_taxes > 0:
        rent_details["LocalTaxes"] = local_taxes
    if arrears > 0:
        rent_details["ArrearsUnrealizedRentRcvd"] = arrears

    return [{
        "HPSNo": 1,
        "AddressDetailWithZipCode": address,
        "PropertyOwner": "SE",
        "PropCoOwnedFlg": "NO",
        "AsseseeShareProperty": 100,
        "ifLetOut": hp_input.property_type.value,
        "Rentdetails": rent_details,
    }]


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
    ddb_user_type: Optional[str] = None,
    ddb_disease: Optional[str] = None,
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
    result = {
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
    if ddb_user_type is not None:
        result["Section80DDBUsrType"] = ddb_user_type
    if ddb_disease is not None:
        result["NameOfSpecDisease80DDB"] = ddb_disease
    return result


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
    usr_80ddb: Optional[Decimal] = None,
    ddb_user_type: Optional[str] = None,
    ddb_disease: Optional[str] = None,
    ded_80u: Decimal = Decimal("0"),
    ded_80tta: Decimal = Decimal("0"),
    ded_80ttb: Decimal = Decimal("0"),
    ded_80e: Decimal = Decimal("0"),
    usr_80e: Optional[Decimal] = None,
    ded_80ee: Decimal = Decimal("0"),
    usr_80ee: Optional[Decimal] = None,
    ded_80eea: Decimal = Decimal("0"),
    usr_80eea: Optional[Decimal] = None,
    ded_80eeb: Decimal = Decimal("0"),
    usr_80eeb: Optional[Decimal] = None,
    ded_80g: Decimal = Decimal("0"),
    usr_80g: Optional[Decimal] = None,
    ded_80gg: Decimal = Decimal("0"),
    ded_80gga: Decimal = Decimal("0"),
    usr_80gga: Optional[Decimal] = None,
    ded_80ggc: Decimal = Decimal("0"),
    usr_80ggc: Optional[Decimal] = None,
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
            deductions_total
            - ded_80ddb
            + (usr_80ddb if usr_80ddb is not None else ded_80ddb)
            - ded_80e
            + (usr_80e if usr_80e is not None else ded_80e)
            - ded_80ee
            + (usr_80ee if usr_80ee is not None else ded_80ee)
            - ded_80eea
            + (usr_80eea if usr_80eea is not None else ded_80eea)
            - ded_80eeb
            + (usr_80eeb if usr_80eeb is not None else ded_80eeb)
            - ded_80g
            + (usr_80g if usr_80g is not None else ded_80g)
            - ded_80gga
            + (usr_80gga if usr_80gga is not None else ded_80gga)
            - ded_80ggc
            + (usr_80ggc if usr_80ggc is not None else ded_80ggc),
            ded_80c=ded_80c, ded_80ccc=ded_80ccc, ded_80ccd1=ded_80ccd1,
            ded_80ccd1b=ded_80ccd1b,
            ded_80ccd2=ded_80ccd2, ded_80d=ded_80d, ded_80dd=ded_80dd,
            ded_80ddb=(usr_80ddb if usr_80ddb is not None else ded_80ddb),
            ddb_user_type=ddb_user_type,
            ddb_disease=ddb_disease,
            ded_80u=ded_80u, ded_80tta=ded_80tta,
            ded_80ttb=ded_80ttb,
            ded_80e=(usr_80e if usr_80e is not None else ded_80e),
            ded_80ee=(usr_80ee if usr_80ee is not None else ded_80ee),
            ded_80eea=(usr_80eea if usr_80eea is not None else ded_80eea),
            ded_80eeb=(usr_80eeb if usr_80eeb is not None else ded_80eeb),
            ded_80g=(usr_80g if usr_80g is not None else ded_80g),
            ded_80gg=ded_80gg,
            ded_80gga=(usr_80gga if usr_80gga is not None else ded_80gga),
            ded_80ggc=(usr_80ggc if usr_80ggc is not None else ded_80ggc),
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

def _policy_insurance_details(policies: list, section_code: str) -> list:
    """Build ``Sch80DInsDtls`` rows for one 80D bucket from policy entries.

    Args:
        policies: ``InsurancePolicy`` rows from ``Schedule80D``.
        section_code: The bucket code ("1a" self non-senior, "1b" self senior,
            "2a" parents non-senior, "2b" parents senior).

    Returns:
        A list of dicts with ``InsurerName``, ``PolicyNo`` and
        ``HealthInsAmt`` keys, per the official V1.1 ``Sch80DInsDtls`` schema.
    """
    rows: list[dict] = []
    for p in policies or []:
        if str(getattr(p, "section", "1a")) != section_code:
            continue
        insurer = (getattr(p, "insurer_name", None) or "").strip() or "Not Provided"
        policy_no = (getattr(p, "policy_number", None) or "").strip() or "Not Provided"
        amount = _to_rupees(getattr(p, "premium_paid", Decimal("0")) or Decimal("0"))
        rows.append({
            "InsurerName": insurer[:125],
            "PolicyNo": policy_no[:75],
            "HealthInsAmt": amount,
        })
    return rows


def _schedule_80d(
    senior_flag_self: str,
    senior_flag_parents: str,
    self_premium: Decimal,
    parents_premium: Decimal,
    preventive_self: Decimal,
    preventive_parents: Decimal,
    eligible_deduction: Decimal,
    policies: Optional[list] = None,
) -> dict:
    self_non_senior_rows = _policy_insurance_details(policies, "1a")
    self_senior_rows = _policy_insurance_details(policies, "1b")
    parents_non_senior_rows = _policy_insurance_details(policies, "2a")
    parents_senior_rows = _policy_insurance_details(policies, "2b")
    return {
        "Sec80DSelfFamSrCtznHealth": {
            "SeniorCitizenFlag": senior_flag_self,
            "SelfAndFamily": _to_rupees(self_premium) if senior_flag_self == "N" else 0,
            "HealthInsPremSlfFam": _to_rupees(self_premium) if senior_flag_self == "N" else 0,
            "Sec80DSelfFamHIDtls": {
                "Sch80DInsDtls": self_non_senior_rows,
                "TotalPayments": _to_rupees(self_premium) if senior_flag_self == "N" else 0,
            },
            "PrevHlthChckUpSlfFam": _to_rupees(preventive_self) if senior_flag_self == "N" else 0,
            "SelfAndFamilySeniorCitizen": _to_rupees(self_premium) if senior_flag_self == "Y" else 0,
            "HlthInsPremSlfFamSrCtzn": _to_rupees(self_premium) if senior_flag_self == "Y" else 0,
            "Sec80DSelfFamSrCtznHIDtls": {
                "Sch80DInsDtls": self_senior_rows,
                "TotalPayments": _to_rupees(self_premium) if senior_flag_self == "Y" else 0,
            },
            "PrevHlthChckUpSlfFamSrCtzn": _to_rupees(preventive_self) if senior_flag_self == "Y" else 0,
            "MedicalExpSlfFamSrCtzn": 0,
            "ParentsSeniorCitizenFlag": senior_flag_parents,
            "Parents": _to_rupees(parents_premium) if senior_flag_parents == "N" else 0,
            "HlthInsPremParents": _to_rupees(parents_premium) if senior_flag_parents == "N" else 0,
            "Sec80DParentsHIDtls": {
                "Sch80DInsDtls": parents_non_senior_rows,
                "TotalPayments": _to_rupees(parents_premium) if senior_flag_parents == "N" else 0,
            },
            "PrevHlthChckUpParents": _to_rupees(preventive_parents) if senior_flag_parents == "N" else 0,
            "ParentsSeniorCitizen": _to_rupees(parents_premium) if senior_flag_parents == "Y" else 0,
            "HlthInsPremParentsSrCtzn": _to_rupees(parents_premium) if senior_flag_parents == "Y" else 0,
            "Sec80DParentsSrCtznHIDtls": {
                "Sch80DInsDtls": parents_senior_rows,
                "TotalPayments": _to_rupees(parents_premium) if senior_flag_parents == "Y" else 0,
            },
            "PrevHlthChckUpParentsSrCtzn": _to_rupees(preventive_parents) if senior_flag_parents == "Y" else 0,
            "MedicalExpParentsSrCtzn": 0,
            "EligibleAmountOfDedn": _to_rupees(eligible_deduction),
        }
    }


def _schedule_80c(details: Section80CResult) -> dict[str, Any]:
    """Serialize a computed Section 80C result without recalculating eligibility."""
    eligible_rupees = _to_rupees(details.allowed_deduction)
    allocated_eligible = 0
    rows: list[dict[str, Any]] = []
    for index, computed in enumerate(details.rows):
        source = computed.source
        if not source.identifier_number:
            raise ValueError("Schedule 80C entries require identifier_number")
        if index == len(details.rows) - 1:
            eligible = eligible_rupees - allocated_eligible
        else:
            eligible = min(
                _to_rupees(computed.eligible_amount),
                eligible_rupees - allocated_eligible,
            )
            allocated_eligible += eligible
        rows.append({
            "IdentificationNo": source.identifier_number,
            "Amount": eligible,
        })
    emitted = sum(row["Amount"] for row in rows)
    if emitted != eligible_rupees:
        raise ValueError("Schedule 80C eligible rows do not cross-foot")
    return {
        "Schedule80CDtls": rows,
        "TotalAmt": emitted,
    }


def _donation_address(address: Any) -> dict[str, Any]:
    """Serialize one official donation-recipient address."""
    return {
        "AddrDetail": address.address_line,
        "CityOrTownOrDistrict": address.city_or_district,
        "StateCode": address.state_code,
        "PinCode": address.pin_code,
    }


def _schedule_80g(details: Any) -> dict[str, Any]:
    """Serialize a computed Section 80G result without recalculating eligibility."""
    category_specs = {
        "100_without_limit": (
            "Don100Percent", "TotDon100PercentCash",
            "TotDon100PercentOtherMode", "TotDon100Percent",
            "TotEligibleDon100Percent",
        ),
        "50_without_limit": (
            "Don50PercentNoApprReqd", "TotDon50PercentNoApprReqdCash",
            "TotDon50PercentNoApprReqdOtherMode", "TotDon50PercentNoApprReqd",
            "TotEligibleDon50Percent",
        ),
        "100_with_limit": (
            "Don100PercentApprReqd", "TotDon100PercentApprReqdCash",
            "TotDon100PercentApprReqdOtherMode", "TotDon100PercentApprReqd",
            "TotEligibleDon100PercentApprReqd",
        ),
        "50_with_limit": (
            "Don50PercentApprReqd", "TotDon50PercentApprReqdCash",
            "TotDon50PercentApprReqdOtherMode", "TotDon50PercentApprReqd",
            "TotEligibleDon50PercentApprReqd",
        ),
    }
    schedule: dict[str, Any] = {}
    emitted_eligible = 0
    for category_key, keys in category_specs.items():
        category = details.categories.get(category_key)
        if category is None or not category.rows:
            continue
        rows = []
        category_eligible = _to_rupees(category.eligible_amount)
        allocated = 0
        for index, computed in enumerate(category.rows):
            source = computed.source
            if not source.donee_name or not source.donee_pan or source.address is None:
                raise ValueError("Complete donee identity and address are required for Schedule 80G")
            eligible = (
                category_eligible - allocated
                if index == len(category.rows) - 1
                else min(_to_rupees(computed.eligible_amount), category_eligible - allocated)
            )
            allocated += eligible
            row = {
                "DoneeWithPanName": source.donee_name,
                "DoneePAN": source.donee_pan,
                "AddressDetail": _donation_address(source.address),
                "DonationAmtCash": _to_rupees(source.cash_amount),
                "DonationAmtOtherMode": _to_rupees(source.non_cash_amount),
                "DonationAmt": _to_rupees(computed.gross_amount),
                "EligibleDonationAmt": eligible,
            }
            if source.approval_reference_number:
                row["ArnNbr"] = source.approval_reference_number
            if source.transaction_ref:
                row["TransactionRefNum"] = source.transaction_ref
            if source.ifsc_code:
                row["IFSCCode"] = source.ifsc_code
            rows.append(row)
        object_key, cash_key, other_key, gross_key, eligible_key = keys
        schedule[object_key] = {
            "DoneeWithPan": rows,
            cash_key: sum(row["DonationAmtCash"] for row in rows),
            other_key: sum(row["DonationAmtOtherMode"] for row in rows),
            gross_key: sum(row["DonationAmt"] for row in rows),
            eligible_key: sum(row["EligibleDonationAmt"] for row in rows),
        }
        emitted_eligible += schedule[object_key][eligible_key]
    schedule.update({
        "TotalDonationsUs80GCash": _to_rupees(details.cash_amount),
        "TotalDonationsUs80GOtherMode": _to_rupees(details.other_mode_amount),
        "TotalDonationsUs80G": _to_rupees(details.gross_amount),
        "TotalEligibleDonationsUs80G": emitted_eligible,
    })
    if emitted_eligible != _to_rupees(details.allowed_deduction):
        raise ValueError("Schedule 80G eligible rows do not cross-foot")
    return schedule


def _schedule_80gga(details: Section80GGAResult) -> dict[str, Any]:
    """Serialize a computed Section 80GGA result without eligibility logic."""
    eligible_rupees = _to_rupees(details.allowed_deduction)
    allocated_eligible = 0
    eligible_indices = [
        index for index, computed in enumerate(details.rows)
        if computed.eligible_amount > 0
    ]
    final_eligible_index = eligible_indices[-1] if eligible_indices else None
    rows: list[dict[str, Any]] = []
    for index, computed in enumerate(details.rows):
        cash = _to_rupees(computed.source.cash_amount)
        other = _to_rupees(computed.source.other_mode_amount)
        if index == final_eligible_index:
            eligible = eligible_rupees - allocated_eligible
        elif computed.eligible_amount > 0:
            eligible = min(
                _to_rupees(computed.eligible_amount),
                eligible_rupees - allocated_eligible,
            )
            allocated_eligible += eligible
        else:
            eligible = 0
        rows.append({
            "RelevantClauseUndrDedClaimed": computed.source.relevant_clause.value,
            "NameOfDonee": computed.source.donee_name,
            "AddressDetail": _donation_address(computed.source.address),
            "DoneePAN": computed.source.donee_pan,
            "DonationAmtCash": cash,
            "DonationAmtOtherMode": other,
            "DonationAmt": cash + other,
            "EligibleDonationAmt": eligible,
        })
    emitted_eligible = sum(row["EligibleDonationAmt"] for row in rows)
    if emitted_eligible != _to_rupees(details.allowed_deduction):
        raise ValueError("Schedule 80GGA eligible rows do not cross-foot")
    return {
        "DonationDtlsSciRsrchRuralDev": rows,
        "TotalDonationAmtCash80GGA": sum(row["DonationAmtCash"] for row in rows),
        "TotalDonationAmtOtherMode80GGA": sum(
            row["DonationAmtOtherMode"] for row in rows
        ),
        "TotalDonationsUs80GGA": sum(row["DonationAmt"] for row in rows),
        "TotalEligibleDonationAmt80GGA": emitted_eligible,
    }


def _schedule_80ggc(details: Section80GGCResult) -> dict[str, Any]:
    """Serialize a computed Section 80GGC result without eligibility logic."""
    eligible_rupees = _to_rupees(details.allowed_deduction)
    allocated_eligible = 0
    eligible_indices = [
        index for index, computed in enumerate(details.rows)
        if computed.eligible_amount > 0
    ]
    final_eligible_index = eligible_indices[-1] if eligible_indices else None
    rows: list[dict[str, Any]] = []
    for index, computed in enumerate(details.rows):
        source = computed.source
        cash = _to_rupees(source.cash_amount)
        other = _to_rupees(source.other_mode_amount)
        if index == final_eligible_index:
            eligible = eligible_rupees - allocated_eligible
        elif computed.eligible_amount > 0:
            eligible = min(
                _to_rupees(computed.eligible_amount),
                eligible_rupees - allocated_eligible,
            )
            allocated_eligible += eligible
        else:
            eligible = 0
        if source.contribution_date is None:
            raise ValueError("Schedule 80GGC requires a contribution date")
        row: dict[str, Any] = {
            "DonationDate": source.contribution_date.isoformat(),
            "DonationAmtCash": cash,
            "DonationAmtOtherMode": other,
            "DonationAmt": cash + other,
            "EligibleDonationAmt": eligible,
        }
        if source.transaction_ref:
            row["TransactionRefNum"] = source.transaction_ref
        if source.ifsc_code:
            row["IFSCCode"] = source.ifsc_code
        if source.political_party_name:
            row["PoliticalPartyName"] = source.political_party_name
        if source.political_party_pan:
            row["PoliticalPartyPAN"] = source.political_party_pan
        rows.append(row)
    emitted_eligible = sum(row["EligibleDonationAmt"] for row in rows)
    if emitted_eligible != eligible_rupees:
        raise ValueError("Schedule 80GGC eligible rows do not cross-foot")
    return {
        "Schedule80GGCDetails": rows,
        "TotalDonationAmtCash80GGC": sum(row["DonationAmtCash"] for row in rows),
        "TotalDonationAmtOtherMode80GGC": sum(
            row["DonationAmtOtherMode"] for row in rows
        ),
        "TotalDonationsUs80GGC": sum(row["DonationAmt"] for row in rows),
        "TotalEligibleDonationAmt80GGC": emitted_eligible,
    }


def _schedule_deduction_loan(
    details: LoanDeductionResult,
    *,
    section: str,
    property_stamp_duty_value: Optional[Decimal] = None,
) -> dict[str, Any]:
    """Serialize a computed loan-deduction result without recalculating.

    Consumes the typed ``LoanDeductionResult`` produced by the dedicated
    section module and emits official rows with deterministic whole-rupee
    eligibility already allocated.
    """
    if section not in {"80E", "80EE", "80EEA", "80EEB"}:
        raise ValueError(f"Unsupported deduction loan section: {section}")
    if not details.rows:
        raise ValueError(
            f"A positive Section {section} claim requires official loan rows"
        )
    eligible_rupees = _to_rupees(details.allowed_deduction)
    allocated = 0
    interest_key = f"Interest{section}"
    mapped: list[dict[str, Any]] = []
    for index, computed in enumerate(details.rows):
        entry = computed.source
        if index == len(details.rows) - 1:
            row_interest = eligible_rupees - allocated
        else:
            row_interest = min(
                _to_rupees(computed.eligible_interest),
                eligible_rupees - allocated,
            )
            allocated += row_interest
        row = {
            "LoanTknFrom": entry.loan_taken_from.value,
            "BankOrInstnName": entry.lender_name,
            "LoanAccNoOfBankOrInstnRefNo": entry.account_or_reference_number,
            "DateofLoan": entry.loan_date.isoformat(),
            "TotalLoanAmt": _to_rupees(entry.total_loan_amount),
            "LoanOutstndngAmt": _to_rupees(entry.outstanding_loan_amount),
            interest_key: row_interest,
        }
        if section == "80EEB":
            row["VehicleRegNo"] = entry.vehicle_registration_number
        mapped.append(row)

    total = sum(row[interest_key] for row in mapped)
    if total != eligible_rupees:
        raise ValueError(f"Schedule {section} emitted rows do not cross-foot")
    schedule = {
        f"Schedule{section}Dtls": mapped,
        f"TotalInterest{section}": total,
    }
    if section == "80EEA":
        if property_stamp_duty_value is None:
            raise ValueError("Schedule 80EEA requires property stamp-duty value")
        schedule["PropStmpDtyVal"] = _to_rupees(property_stamp_duty_value)
    return schedule


def _schedule_80e(details: LoanDeductionResult) -> dict[str, Any]:
    """Serialize Schedule 80E from a computed loan-deduction result."""
    return _schedule_deduction_loan(details, section="80E")


def _disability_schedule_fields(
    schedule: Any,
    computed_deduction: Decimal,
    section: str,
) -> dict[str, Any]:
    """Map and cross-foot fields shared by official 80DD and 80U schedules."""
    amount = _to_rupees(computed_deduction)
    limits = {
        "80DD": (SECTION_80DD_LIMIT, SECTION_80DD_SEVERE_LIMIT),
        "80U": (SECTION_80U_LIMIT, SECTION_80U_SEVERE_LIMIT),
    }
    normal_limit, severe_limit = limits[section]
    expected = severe_limit if schedule.disability_type.value == "severe" else normal_limit
    expected_rupees = _to_rupees(expected)
    if _to_rupees(schedule.deduction_amount) != expected_rupees:
        raise ValueError(
            f"Schedule {section} deduction must be Rs {expected_rupees} "
            "for the selected severity"
        )
    if amount <= 0 or amount > expected_rupees:
        raise ValueError(
            f"Schedule {section} computed deduction must be positive and not exceed "
            f"Rs {expected_rupees}"
        )
    mapped: dict[str, Any] = {
        "NatureOfDisability": schedule.disability_type.itd_code,
        "TypeOfDisability": schedule.disability_category.itd_code,
        "DeductionAmount": amount,
    }
    if schedule.form_10ia_ack_number:
        mapped["Form10IAAckNum"] = schedule.form_10ia_ack_number
    if schedule.udid_number:
        mapped["UDIDNum"] = schedule.udid_number
    return mapped


def _schedule_80dd(schedule: Any, computed_deduction: Decimal) -> dict[str, Any]:
    """Build the official Section 80DD dependent-disability schedule."""
    if schedule is None:
        raise ValueError("A positive Section 80DD claim requires Schedule 80DD details")
    if schedule.dependent_relationship is None:
        raise ValueError("Schedule 80DD requires dependent_relationship")
    if schedule.dependent_relationship.value == "member_of_huf":
        raise ValueError("ITR-1 Schedule 80DD does not allow an HUF member dependent")
    mapped = _disability_schedule_fields(schedule, computed_deduction, "80DD")
    mapped["DependentType"] = schedule.dependent_relationship.itd_code
    if schedule.dependent_pan:
        mapped["DependentPan"] = schedule.dependent_pan
    if schedule.dependent_aadhaar:
        mapped["DependentAadhaar"] = schedule.dependent_aadhaar
    return mapped


def _schedule_80u(schedule: Any, computed_deduction: Decimal) -> dict[str, Any]:
    """Build the official Section 80U self-disability schedule."""
    if schedule is None:
        raise ValueError("A positive Section 80U claim requires Schedule 80U details")
    return _disability_schedule_fields(schedule, computed_deduction, "80U")


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

    if input_data is not None:
        if input_data.filing_profile is None:
            raise ValueError("filing_profile is required for official ITR-1 JSON")
        profile = input_data.filing_profile
        personal = _personal_info_from_profile(profile)
        ver = _verification_from_profile(profile)
        filing = _filing_status_itr1(
            return_file_sec=profile.return_file_section,
            opt_out_new_regime=("Y" if input_data.tax_regime.value == "old" else "N"),
        )
    else:
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
            direct = ded_breakdown.get("80C")
            if direct is not None:
                return direct
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
    if input_data is not None:
        if input_data.property_profile is None:
            raise ValueError("property_profile is required for official ITR-1 JSON")
        property_schedules = _property_schedule(
            result,
            input_data,
            input_data.property_profile,
        )
    else:
        property_schedules = None

    if input_data is not None:
        ddb_input = input_data.deductions_chapter6a
        details_80ddb = (
            ded_sched.section_details.get("80DDB") if ded_sched else None
        )
        if details_80ddb is None:
            if ddb_input.amount_80ddb > 0 or ddb_input.details_80ddb is not None:
                raise ValueError("Section 80DDB computation details are missing")
            usr_80ddb = None
            ddb_user_type = None
            ddb_disease = None
        elif details_80ddb.source is not None:
            usr_80ddb = details_80ddb.user_claim
            ddb_user_type = details_80ddb.source.user_type.value
            ddb_disease = details_80ddb.source.disease.value
        else:
            usr_80ddb = None
            ddb_user_type = None
            ddb_disease = None
    else:
        usr_80ddb = None
        ddb_user_type = None
        ddb_disease = None

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
        hp_schedules=property_schedules,
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
        usr_80ddb=usr_80ddb,
        ddb_user_type=ddb_user_type,
        ddb_disease=ddb_disease,
        ded_80u=deduction("80U"),
        ded_80tta=deduction("80TTA"),
        ded_80ttb=deduction("80TTB"),
        ded_80e=deduction("80E"),
        usr_80e=(
            input_data.deductions_chapter6a.amount_80e
            if input_data is not None
            else None
        ),
        ded_80ee=deduction("80EE"),
        usr_80ee=(input_data.deductions_chapter6a.amount_80ee if input_data else None),
        ded_80eea=deduction("80EEA"),
        usr_80eea=(input_data.deductions_chapter6a.amount_80eea if input_data else None),
        ded_80eeb=deduction("80EEB"),
        usr_80eeb=(input_data.deductions_chapter6a.amount_80eeb if input_data else None),
        ded_80g=deduction("80G"),
        usr_80g=(input_data.deductions_chapter6a.amount_80g if input_data else None),
        ded_80gg=deduction("80GG"),
        ded_80gga=deduction("80GGA"),
        usr_80gga=(input_data.deductions_chapter6a.amount_80gga if input_data else None),
        ded_80ggc=deduction("80GGC"),
        usr_80ggc=(input_data.deductions_chapter6a.amount_80ggc if input_data else None),
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
            details_80c = ded_sched.section_details.get("80C") if ded_sched else None
        combined_80c = ded_breakdown.get("80C+80CCC+80CCD(1)", Decimal("0"))
        if combined_80c > 0:
            if details_80c is None or not details_80c.rows:
                raise ValueError("A positive Section 80C claim requires Schedule 80C detail rows")
            itr1["Schedule80C"] = _schedule_80c(details_80c)

        if deduction("80D") > 0:
            ded_input = input_data.deductions_chapter6a
            details_80d = ded_sched.section_details.get("80D") if ded_sched else None
            schedule_80d = input_data.schedule_80d
            if details_80d is None:
                raise ValueError("Section 80D computation details are missing")
            self_flag = (
                "S" if schedule_80d and schedule_80d.not_claiming_self
                else "Y" if details_80d.senior_self
                else "N"
            )
            parents_flag = (
                "P" if schedule_80d and schedule_80d.not_claiming_parents
                else "Y" if details_80d.senior_parents
                else "N"
            )
            itr1["Schedule80D"] = _schedule_80d(
                senior_flag_self=self_flag,
                senior_flag_parents=parents_flag,
                self_premium=details_80d.self_premium,
                parents_premium=details_80d.parents_premium,
                preventive_self=details_80d.preventive_self,
                preventive_parents=details_80d.preventive_parents,
                eligible_deduction=details_80d.allowed_deduction,
                policies=(schedule_80d.policies if schedule_80d else None),
            )

        schedule_80dd = input_data.disability_schedule_80dd()
        schedule_80u = input_data.disability_schedule_80u()
        details_80dd = ded_sched.section_details.get("80DD") if ded_sched else None
        details_80u = ded_sched.section_details.get("80U") if ded_sched else None
        ded_80dd = deduction("80DD")
        ded_80u = deduction("80U")
        if ded_80dd > 0:
            if details_80dd is None or details_80dd.source is None:
                raise ValueError("A positive Section 80DD claim requires Schedule 80DD details")
            itr1["Schedule80DD"] = _schedule_80dd(details_80dd.source, ded_80dd)
        elif schedule_80dd is not None:
            raise ValueError("Schedule 80DD details require a positive 80DD deduction")

        if ded_80u > 0:
            if details_80u is None or details_80u.source is None:
                raise ValueError("A positive Section 80U claim requires Schedule 80U details")
            itr1["Schedule80U"] = _schedule_80u(details_80u.source, ded_80u)
        elif schedule_80u is not None:
            raise ValueError("Schedule 80U details require a positive 80U deduction")

        ded_80e = deduction("80E")
        details_80e = ded_sched.section_details.get("80E") if ded_sched else None
        if ded_80e > 0:
            if details_80e is None or not details_80e.rows:
                raise ValueError("A positive Section 80E claim requires official loan rows")
            itr1["Schedule80E"] = _schedule_80e(details_80e)
        elif input_data.schedule_80e_entries:
            raise ValueError("Schedule 80E rows require a positive eligible deduction")

        for section in ("80EE", "80EEA", "80EEB"):
            eligible = deduction(section)
            details_loan = ded_sched.section_details.get(section) if ded_sched else None
            if eligible > 0:
                if details_loan is None or not details_loan.rows:
                    raise ValueError(
                        f"A positive Section {section} claim requires official loan rows"
                    )
                itr1[f"Schedule{section}"] = _schedule_deduction_loan(
                    details_loan,
                    section=section,
                    property_stamp_duty_value=(
                        input_data.property_stamp_duty_value_80eea
                        if section == "80EEA"
                        else None
                    ),
                )

        details_80g = result.schedules["deductions"].section_details.get("80G")
        if deduction("80G") > 0:
            if details_80g is None or not details_80g.categories:
                raise ValueError("Complete official Schedule 80G donation rows are required")
            itr1["Schedule80G"] = _schedule_80g(details_80g)
        elif input_data.deductions_chapter6a.donations_80g:
            raise ValueError("Schedule 80G rows require a positive eligible deduction")

        details_80gga = result.schedules["deductions"].section_details.get("80GGA")
        if deduction("80GGA") > 0:
            if details_80gga is None or not details_80gga.rows:
                raise ValueError("Complete official Schedule 80GGA donation rows are required")
            itr1["Schedule80GGA"] = _schedule_80gga(details_80gga)
        elif input_data.schedule_80gga and input_data.schedule_80gga.donations:
            raise ValueError("Schedule 80GGA rows require a positive eligible deduction")

        details_80ggc = result.schedules["deductions"].section_details.get("80GGC")
        if deduction("80GGC") > 0:
            if details_80ggc is None or not details_80ggc.rows:
                raise ValueError("Complete official Schedule 80GGC contribution rows are required")
            itr1["Schedule80GGC"] = _schedule_80ggc(details_80ggc)
        elif input_data.schedule_80ggc and input_data.schedule_80ggc.contributions:
            raise ValueError("Schedule 80GGC rows require a positive eligible deduction")

        incomplete_claims: dict[str, Decimal] = {}
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
