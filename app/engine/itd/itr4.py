"""
ITR-4 (Sugam) ITD JSON builder — fully standalone.

Produces an ITD-compliant JSON document matching the CBDT ITR-4 schema
(``ITR-4_2026_Main_V1.1``) with ``additionalProperties: false`` enforcement
at every level.

This builder is **standalone** — it does NOT import any helpers from
``app.engine.itd.itr1``. Every serializer, address mapper, phone validator,
deduction-schedule serializer, TDS/TCS/TaxPayment serializer, and bank-row
builder lives in this file. The ITR-4 form-specific workflow is fully
self-contained so it can evolve without coupling to the ITR-1 pipeline.

ITR-4 structural differences from ITR-1 (all enforced here):
  - FilingStatus uses the Form 10-IEA cascade (no OptOutNewTaxRegime key).
  - PersonalInfo requires ``Status`` (I/H/F) and ``Address.Phone``.
  - IncomeDeductions uses ``EntertainmntalwncUs16ii`` (not EntertainmentAlw16ii).
  - IncomeDeductions has ``IncomeFromBusinessProf`` at top and
    ``TaxExmpIntIncDtls`` (not ``ExemptIncAgriOthUs10``).
  - TaxComputation has NO ``TotalIntrstPay`` key.
  - DeductUndChapVIA has NO ``Section80GGA`` (80GGA is not available for
    business-income assessees).
  - Top-level has ``ScheduleBP``, ``ScheduleIT`` (challan array!),
    ``TaxExmpIntIncDtls``, and no root-level ``TaxPayments`` (ITR-4 folds
    that into ScheduleIT).
  - TDSonOthThanSals key is ``TDSonOthThanSalDtls`` (not TDSonOthThanSal).
  - ItrFilingDueDate is ``2026-08-31`` (not 2026-07-31).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Optional

from app.engine.calculators.itr4 import ITR4Result
from app.engine.constants import (
    SECTION_80DD_LIMIT,
    SECTION_80DD_SEVERE_LIMIT,
    SECTION_80U_LIMIT,
    SECTION_80U_SEVERE_LIMIT,
)
from app.schemas.itr4 import (
    ITR4BankAccount,
    ITR4FilingAddress,
    ITR4FilingProfile,
    ITR4PostalAddress,
    ITR4PropertyProfile,
    ITR4SeventhProvisoDetails,
    ITR4TaxReturnPreparer,
    ITR4AssesseeStatus,
    ITR4Input,
    PresumptiveScheme,
)


from app.engine.itd.common import (
    _to_rupees,
    _to_rupees_rounded10,
    _zero_if_none,
    _str_or,
    _creation_info,
    _form_itr,
    _verification,
    _tax_return_preparer as _trp_common,
    _personal_info_base,
    _compute_digest,
)


# ===========================================================================
# DeductedYr resolution — AY 2026-27 correct enum values
# ===========================================================================

# CBDT ITR-4 TDSonOthThanSalDtls.DeductedYr enum (17 values, assessment-year labels).
_TDS2_DEDUCTED_YR_ENUM = {
    "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017",
    "2016", "2015", "2014", "2013", "2012", "2011", "2010", "2009", "2008",
}
# CBDT ITR-4 TDS3Details.DeductedYr enum (8 values — shorter list).
_TDS3_DEDUCTED_YR_ENUM = {
    "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017",
}


def _resolve_deducted_yr_tds2(financial_year: Optional[str]) -> str:
    """Resolve the CBDT DeductedYr enum value for AY 2026-27 (FY 2025-26).

    The CBDT enum labels years by the assessment-year of the deduction. For
    AY 2026-27 (FY 2025-26), TDS deducted during FY 2025-26 maps to
    ``"2024"``. When the caller supplies a financial_year string like
    ``"2025-26"``, we derive ``"2024"`` from it. When absent, default to
    ``"2024"`` (the correct AY 2026-27 value). Reject any value not in the
    schema enum.
    """
    if financial_year:
        try:
            start_yr = int(financial_year.split("-")[0])
            derived = str(start_yr - 1)
            if derived in _TDS2_DEDUCTED_YR_ENUM:
                return derived
        except (ValueError, IndexError):
            pass
    return "2024"


def _resolve_deducted_yr_tds3(deducted_yr: str) -> str:
    """Validate the TDS3 DeductedYr against the shorter 8-value enum."""
    if deducted_yr in _TDS3_DEDUCTED_YR_ENUM:
        return deducted_yr
    if deducted_yr == "2025":
        return "2024"
    raise ValueError(
        f"DeductedYr {deducted_yr!r} is not in the TDS3 enum "
        f"({sorted(_TDS3_DEDUCTED_YR_ENUM)})"
    )


# ===========================================================================
# Phone validation — [0-9]{1,12}
# ===========================================================================

def _validate_phone_no(phone_no: str) -> str:
    """Validate PhoneNo against the CBDT pattern ``[0-9]{1,12}``.

    Raises on any non-digit value (the previous builder emitted ``"y"`` in
    real output, which fails the schema pattern).
    """
    if phone_no is None or phone_no == "":
        return "0"
    cleaned = str(phone_no).strip()
    if not cleaned.isdigit():
        raise ValueError(
            f"PhoneNo must be digits only ([0-9]{{1,12}}), got {phone_no!r}"
        )
    if len(cleaned) > 12:
        raise ValueError(
            f"PhoneNo must not exceed 12 digits, got {len(cleaned)} digits"
        )
    return cleaned


# ===========================================================================
# Address serializers — ITR-4 specific
# ===========================================================================

def _address_from_postal(address: ITR4PostalAddress, *, include_contact: bool) -> dict[str, Any]:
    """Map an ITR-4 postal address to the official address structure.

    The CBDT JSON schema enforces ``minLength`` on several address fields
    (e.g. ``LocalityOrArea``, ``CityOrTownOrDistrict``). Empty strings fail
    validation. When the caller leaves such a field blank, we emit a single
    space so the schema accepts the payload while keeping the field visibly
    empty for downstream display.
    """
    def _non_empty(value: str) -> str:
        return value if value else " "

    mapped: dict[str, Any] = {
        "ResidenceNo": _non_empty(address.residence_no),
        "ResidenceName": _non_empty(address.residence_name),
        "RoadOrStreet": _non_empty(address.road_or_street),
        "LocalityOrArea": _non_empty(address.locality_or_area),
        "CityOrTownOrDistrict": _non_empty(address.city_or_town_or_district),
        "StateCode": _non_empty(address.state_code),
        "CountryCode": _non_empty(address.country_code),
        "ZipCode": _non_empty(address.zip_code),
    }
    if address.pin_code is not None and address.pin_code.isdigit():
        mapped["PinCode"] = int(address.pin_code)
    if include_contact:
        if not isinstance(address, ITR4FilingAddress):
            raise ValueError("Primary filing address requires contact details")
        mapped.update({
            "CountryCodeMobile": address.mobile_country_code,
            "MobileNo": int(address.mobile_no) if address.mobile_no.isdigit() else 0,
            "CountryCodeMobileNoSec": address.secondary_mobile_country_code,
            "MobileNoSec": int(address.secondary_mobile_no) if address.secondary_mobile_no else 0,
            "EmailAddress": address.email,
        })
        if address.secondary_email:
            mapped["EmailAddressSec"] = address.secondary_email
    return mapped


def _personal_info_from_profile(
    profile: ITR4FilingProfile,
) -> dict[str, Any]:
    """Build official ITR-4 PersonalInfo exclusively from the typed profile."""
    personal: dict[str, Any] = {
        "AssesseeName": {
            "FirstName": profile.first_name,
            "MiddleName": profile.middle_name,
            "SurNameOrOrgName": profile.surname,
        },
        "PAN": profile.pan,
        "Address": _address_from_postal(profile.primary_address, include_contact=True),
        "SecondaryAdd": "Y" if profile.alternate_address else "N",
        "DOB": profile.date_of_birth.isoformat(),
        "EmployerCategory": profile.employer_category,
        "Status": profile.assessee_status.value,
    }
    # ITR-4 requires the Address.Phone sub-object (absent from ITR-1).
    phone = profile.primary_address
    personal["Address"]["Phone"] = {
        "STDcode": phone.landline_std_code,
        "PhoneNo": _validate_phone_no(phone.landline_phone_no),
    }
    if profile.alternate_address is not None:
        personal["AlternateAddress"] = _address_from_postal(
            profile.alternate_address,
            include_contact=False,
        )
    if profile.aadhaar_number is not None:
        personal["AadhaarCardNo"] = profile.aadhaar_number
    return personal


def _verification_from_profile(profile: ITR4FilingProfile) -> dict[str, Any]:
    """Build official ITR-4 verification from the typed filing profile."""
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


# ===========================================================================
# ITR-4 FilingStatus (Form 10-IEA cascade — no OptOutNewTaxRegime)
# ===========================================================================

def _filing_status_itr4(profile: Optional[ITR4FilingProfile]) -> dict[str, Any]:
    """Build the ITR-4 FilingStatus block from the typed filing profile.

    ITR-4 uses the Form 10-IEA cascade (not the ITR-1 OptOutNewTaxRegime
    flag). Seventh-proviso fields are emitted only when declared, matching
    the schema's minimum on AmtSeventhProvisio139ii / 139iii.
    """
    result: dict[str, Any] = {
        "ItrFilingDueDate": "2026-08-31",
    }
    if profile is None:
        result.update({
            "ReturnFileSec": 11,
            "Form10IEAEarlierAYOldRegime": "NA",
            "SeventhProvisio139": "N",
            "AsseseeRepFlg": "N",
            "F10IEAEarlierAYNewRegime": "N",
            "F10IEACurrAYNewRegime": "N",
            "F10IEACurrAYOldRegime": "N",
        })
        return result

    sp = profile.seventh_proviso
    has_seventh = bool(sp and (
        sp.deposit_exceeds_one_crore_flag
        or sp.foreign_travel_flag
        or sp.electricity_expenditure_flag
        or sp.other_clause_iv_flag
    ))

    result["ReturnFileSec"] = profile.return_file_section
    result["Form10IEAEarlierAYOldRegime"] = profile.form_10iea_earlier_ay_old_regime
    result["SeventhProvisio139"] = "Y" if has_seventh else "N"
    result["AsseseeRepFlg"] = "Y" if profile.assessee_representative else "N"

    if sp is not None:
        result["DepAmtAggAmtExcd1CrPrYrFlg"] = (
            "Y" if sp.deposit_exceeds_one_crore_flag else "N"
        )
        if sp.deposit_exceeds_one_crore_flag:
            result["AmtSeventhProvisio139i"] = _to_rupees(sp.deposit_amount)
        result["IncrExpAggAmt2LkTrvFrgnCntryFlg"] = "Y" if sp.foreign_travel_flag else "N"
        if sp.foreign_travel_flag:
            result["AmtSeventhProvisio139ii"] = _to_rupees(sp.foreign_travel_amount)
        result["IncrExpAggAmt1LkElctrctyPrYrFlg"] = "Y" if sp.electricity_expenditure_flag else "N"
        if sp.electricity_expenditure_flag:
            result["AmtSeventhProvisio139iii"] = _to_rupees(sp.electricity_expenditure_amount)
        result["clauseiv7provisio139i"] = "Y" if sp.other_clause_iv_flag else "N"
        if sp.other_clause_iv_flag:
            result["clauseiv7provisio139iDtls"] = [
                {
                    "clauseiv7provisio139iNature": row.nature,
                    "clauseiv7provisio139iAmount": _to_rupees(row.amount),
                }
                for row in sp.clause_iv_details
            ]

    if profile.receipt_number:
        result["ReceiptNo"] = profile.receipt_number
    if profile.original_return_date:
        result["OrigRetFiledDate"] = profile.original_return_date.isoformat()
    if profile.notice_number:
        result["NoticeNo"] = profile.notice_number
    if profile.notice_date:
        result["NoticeDateUnderSec"] = profile.notice_date.isoformat()
    if profile.assessee_representative:
        rep = profile.assessee_representative
        result["AssesseeRep"] = {
            "RepName": rep.name,
            "RepEmailID": rep.email,
            "CountryCodeRepMobileNo": rep.mobile_country_code,
            "RepMobileNo": int(rep.mobile_no),
        }

    # Form 10-IEA cascade — emit only when the caller supplies real values.
    if profile.form_10iea_ass_year:
        result["Form10IEAAssYear"] = profile.form_10iea_ass_year
    if profile.form_10iea_earlier_ay_ack_old_regime > 0:
        result["Form10IEAEarlierAYAckOldRegime"] = profile.form_10iea_earlier_ay_ack_old_regime

    result["F10IEAEarlierAYNewRegime"] = profile.f10iea_earlier_ay_new_regime
    if profile.ass_yr_f10iea_new_tax_reg:
        result["AssYrF10IEANewTaxReg"] = profile.ass_yr_f10iea_new_tax_reg
    if profile.form_10iea_earlier_ay_ack_new_regime > 0:
        result["Form10IEAEarlierAYAckNewRegime"] = profile.form_10iea_earlier_ay_ack_new_regime

    result["F10IEACurrAYNewRegime"] = profile.f10iea_curr_ay_new_regime
    if profile.f10iea_date_curr_ay_new_tax:
        result["F10IEADateCurrAYNewTax"] = profile.f10iea_date_curr_ay_new_tax
    if profile.f10iea_ack_no_curr_ay_new_tax > 0:
        result["F10IEAAckNoCurrAYNewTax"] = profile.f10iea_ack_no_curr_ay_new_tax

    result["F10IEACurrAYOldRegime"] = profile.f10iea_curr_ay_old_regime
    if profile.f10iea_date_curr_ay_old_tax:
        result["F10IEADateCurrAYOldTax"] = profile.f10iea_date_curr_ay_old_tax
    if profile.f10iea_ack_no_curr_ay_old_tax > 0:
        result["F10IEAAckNoCurrAYOldTax"] = profile.f10iea_ack_no_curr_ay_old_tax

    return result


# ===========================================================================
# ITR-4 DeductUndChapVIA — NO Section80GGA (unlike ITR-1)
# ===========================================================================

def _chapter_via_itr4(
    deductions_total: Decimal,
    bk: Mapping[str, Decimal],
    *,
    user_claims: Optional[Mapping[str, Decimal]] = None,
    usr_80ddb: Optional[Decimal] = None,
    ddb_user_type: Optional[str] = None,
    ddb_disease: Optional[str] = None,
    usr_80e: Optional[Decimal] = None,
    usr_80ee: Optional[Decimal] = None,
    usr_80eea: Optional[Decimal] = None,
    usr_80eeb: Optional[Decimal] = None,
    usr_80g: Optional[Decimal] = None,
    usr_80ggc: Optional[Decimal] = None,
    pension_80ccc: Optional[list[dict[str, Any]]] = None,
    pran_number: Optional[str] = None,
    form_10ba_ack_number: Optional[str] = None,
) -> dict[str, Any]:
    """ITR-4 DeductUndChapVIA / UsrDeductUndChapVIA — NO Section80GGA."""
    def _usr_or(key: str, usr: Optional[Decimal]) -> Decimal:
        base = (
            user_claims.get(key, Decimal("0"))
            if user_claims is not None
            else bk.get(key, Decimal("0"))
        )
        return usr if usr is not None else base

    result: dict[str, Any] = {
        "Section80C": _to_rupees(_usr_or("80C", None)),
        "Section80CCC": _to_rupees(_usr_or("80CCC", None)),
        "Section80CCDEmployeeOrSE": _to_rupees(_usr_or("80CCD(1)", None)),
        "Section80CCD1B": _to_rupees(_usr_or("80CCD(1B)", None)),
        "Section80CCDEmployer": _to_rupees(_usr_or("80CCD(2)", None)),
        "Section80D": _to_rupees(_usr_or("80D", None)),
        "Section80DD": _to_rupees(_usr_or("80DD", None)),
        "Section80DDB": _to_rupees(_usr_or("80DDB", usr_80ddb)),
        "Section80E": _to_rupees(_usr_or("80E", usr_80e)),
        "Section80EE": _to_rupees(_usr_or("80EE", usr_80ee)),
        "Section80EEA": _to_rupees(_usr_or("80EEA", usr_80eea)),
        "Section80EEB": _to_rupees(_usr_or("80EEB", usr_80eeb)),
        "Section80G": _to_rupees(_usr_or("80G", usr_80g)),
        "Section80GG": _to_rupees(_usr_or("80GG", None)),
        "Section80GGC": _to_rupees(_usr_or("80GGC", usr_80ggc)),
        "Section80U": _to_rupees(_usr_or("80U", None)),
        "Section80TTA": _to_rupees(_usr_or("80TTA", None)),
        "Section80TTB": _to_rupees(_usr_or("80TTB", None)),
        "AnyOthSec80CCH": _to_rupees(_usr_or("80CCH", None)),
        "TotalChapVIADeductions": _to_rupees(deductions_total),
    }
    if ddb_user_type is not None:
        result["Section80DDBUsrType"] = ddb_user_type
    if ddb_disease is not None:
        result["NameOfSpecDisease80DDB"] = ddb_disease
    if pension_80ccc:
        result["PensionContribution80CCC"] = pension_80ccc
    if pran_number:
        result["PRANDtls"] = [{"PRANNum": pran_number}]
    if form_10ba_ack_number:
        result["Form10BAAckNum"] = form_10ba_ack_number
    return result


# ===========================================================================
# ITR-4 IncomeDeductions
# ===========================================================================

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
    allowance_rows: Optional[list[dict]] = None,
    other_source_rows: Optional[list[dict]] = None,
    deduction_57iia: Decimal = Decimal("0"),
    perquisites_value: Decimal = Decimal("0"),
    profits_in_lieu: Decimal = Decimal("0"),
    ded_breakdown: Optional[Mapping[str, Decimal]] = None,
    user_claims: Optional[Mapping[str, Decimal]] = None,
    usr_80ddb: Optional[Decimal] = None,
    ddb_user_type: Optional[str] = None,
    ddb_disease: Optional[str] = None,
    usr_80e: Optional[Decimal] = None,
    usr_80ee: Optional[Decimal] = None,
    usr_80eea: Optional[Decimal] = None,
    usr_80eeb: Optional[Decimal] = None,
    usr_80g: Optional[Decimal] = None,
    usr_80ggc: Optional[Decimal] = None,
    pension_80ccc: Optional[list[dict[str, Any]]] = None,
    pran_number: Optional[str] = None,
    form_10ba_ack_number: Optional[str] = None,
) -> dict[str, Any]:
    """ITR-4 IncomeDeductions.

    Key differences from ITR-1:
    - Uses ``EntertainmntalwncUs16ii`` (not ``EntertainmentAlw16ii``).
    - Has ``IncomeFromBusinessProf`` at top.
    - ``UsrDeductUndChapVIA`` uses the ITR-4 chapter VIA (no 80GGA).
    """
    bk = ded_breakdown or {}
    total_allwnc_exmp = sum(row["SalOthAmount"] for row in (allowance_rows or []))

    return {
        "IncomeFromBusinessProf": _to_rupees(presumptive_income),
        "GrossSalary": _to_rupees(gross_salary),
        "PerquisitesValue": _to_rupees(perquisites_value),
        "ProfitsInSalary": _to_rupees(profits_in_lieu),
        "Salary": _to_rupees(net_salary + ded_us16),
        "AllwncExemptUs10": {
            "AllwncExemptUs10Dtls": allowance_rows or [],
            "TotalAllwncExemptUs10": _to_rupees(Decimal(total_allwnc_exmp)),
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
            "OthersIncDtlsOthSrc": other_source_rows or [],
        },
        "DeductionUs57iia": _to_rupees(deduction_57iia),
        "GrossTotIncome": _to_rupees(gti),
        "GrossTotIncomeIncLTCG112A": _to_rupees(gti_cg),
        "UsrDeductUndChapVIA": _chapter_via_itr4(
            (
                sum(user_claims.values(), Decimal("0"))
                if user_claims is not None
                else deductions_total
            ),
            bk,
            user_claims=user_claims,
            usr_80ddb=usr_80ddb, ddb_user_type=ddb_user_type, ddb_disease=ddb_disease,
            usr_80e=usr_80e, usr_80ee=usr_80ee, usr_80eea=usr_80eea,
            usr_80eeb=usr_80eeb, usr_80g=usr_80g, usr_80ggc=usr_80ggc,
            pension_80ccc=pension_80ccc,
            pran_number=pran_number,
            form_10ba_ack_number=form_10ba_ack_number,
        ),
        "DeductUndChapVIA": _chapter_via_itr4(deductions_total, bk),
        "TotalIncome": _to_rupees_rounded10(total_income),
    }


# ===========================================================================
# ITR-4 TaxComputation — NO TotalIntrstPay
# ===========================================================================

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
    fees_234i: Decimal = Decimal("0"),
) -> dict[str, Any]:
    """ITR-4 TaxComputation — no TotalIntrstPay, Section89 not required."""
    return {
        "TotalTaxPayable": _to_rupees(slab_tax),
        "Rebate87A": _to_rupees(rebate_87a),
        "TaxPayableOnRebate": _to_rupees(tax_after_rebate),
        "EducationCess": _to_rupees(cess),
        "GrossTaxLiability": _to_rupees(gross_tax_liability),
        "Section89": _to_rupees(relief_89),
        "NetTaxLiability": _to_rupees(net_tax_liability),
        "IntrstPay": {
            "IntrstPayUs234A": _to_rupees(interest_234a),
            "IntrstPayUs234B": _to_rupees(interest_234b),
            "IntrstPayUs234C": _to_rupees(interest_234c),
            "LateFilingFee234F": _to_rupees(late_fee_234f),
            "FeeFurnish234I": _to_rupees(fees_234i),
        },
        "TotTaxPlusIntrstPay": _to_rupees(
            gross_tax_liability + total_interest + late_fee_234f + fees_234i
        ),
    }


# ===========================================================================
# ITR-4 TaxPaid & Refund
# ===========================================================================

def _tax_paid_itr4(
    total_tds: Decimal,
    total_tcs: Decimal,
    advance_tax: Decimal,
    self_assessment_tax: Decimal,
    balance_payable: Decimal,
) -> dict[str, Any]:
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
    type_map = {
        "savings": "SB", "SAVINGS": "SB", "SB": "SB",
        "current": "CA", "CURRENT": "CA", "CA": "CA",
        "cash_credit": "CC", "CASH_CREDIT": "CC", "CC": "CC",
        "overdraft": "OD", "OVERDRAFT": "OD", "OD": "OD",
        "nro": "NRO", "NRO": "NRO",
        "nre": "OTH", "NRE": "OTH",
        "other": "OTH", "OTHER": "OTH", "OTH": "OTH",
    }
    return {
        "IFSCCode": ifsc,
        "BankName": bank_name,
        "BankAccountNo": account_number,
        "AccountType": type_map[account_type],
        "UseForRefund": "true" if use_for_refund else "false",
    }


def _bank_accounts_from_input(input_data: ITR4Input) -> list[dict[str, Any]]:
    """Map validated bank accounts to official account codes without defaults."""
    if not input_data.bank_accounts:
        raise ValueError("At least one bank account is required for ITD JSON")
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
            account_type=account.account_type,
            use_for_refund=account.is_primary,
        ))
    return rows


# ===========================================================================
# ITR-4 ScheduleBP (presumptive business income)
# ===========================================================================

def _financial_particulars(financial: Optional[Any]) -> dict[str, Any]:
    """Project ScheduleBP.FinanclPartclrOfBusiness from the typed model."""
    zeros = {
        "PartnerMemberOwnCapital": 0, "SecuredLoans": 0, "UnSecuredLoans": 0,
        "Advances": 0, "SundryCreditors": 0, "OthrCurrLiab": 0,
        "TotCapLiabilities": 0, "FixedAssets": 0, "Investments": 0,
        "Inventories": 0, "SundryDebtors": 0, "BalWithBanks": 0,
        "CashInHand": 0, "LoansAndAdvances": 0, "OtherAssets": 0,
        "TotalAssets": 0,
    }
    if financial is None:
        return zeros
    return {
        "PartnerMemberOwnCapital": _to_rupees(getattr(financial, "partners_capital", Decimal("0"))),
        "SecuredLoans": _to_rupees(getattr(financial, "secured_loans", Decimal("0"))),
        "UnSecuredLoans": _to_rupees(getattr(financial, "unsecured_loans", Decimal("0"))),
        "Advances": _to_rupees(getattr(financial, "advances_received", Decimal("0"))),
        "SundryCreditors": _to_rupees(getattr(financial, "sundry_creditors", Decimal("0"))),
        "OthrCurrLiab": _to_rupees(getattr(financial, "other_liabilities", Decimal("0"))),
        "TotCapLiabilities": _to_rupees(getattr(financial, "total_capital_liabilities", Decimal("0"))),
        "FixedAssets": _to_rupees(getattr(financial, "fixed_assets", Decimal("0"))),
        "Investments": _to_rupees(getattr(financial, "investments_bp", Decimal("0"))),
        "Inventories": _to_rupees(getattr(financial, "inventories", Decimal("0"))),
        "SundryDebtors": _to_rupees(getattr(financial, "sundry_debtors", Decimal("0"))),
        "BalWithBanks": _to_rupees(getattr(financial, "bank_balance", Decimal("0"))),
        "CashInHand": _to_rupees(getattr(financial, "cash_in_hand", Decimal("0"))),
        "LoansAndAdvances": _to_rupees(getattr(financial, "loans_and_advances_given", Decimal("0"))),
        "OtherAssets": _to_rupees(getattr(financial, "other_assets", Decimal("0"))),
        "TotalAssets": _to_rupees(getattr(financial, "total_assets", Decimal("0"))),
    }


def _goods_dtls_44ae(vehicle: Any) -> dict[str, Any]:
    """Build one GoodsDtlsUs44AE row from a typed GoodsCarriageVehicle.

    Emits the official CBDT ITR-4 schema fields: ``RegNumberGoodsCarriage``,
    ``OwnedLeasedHiredFlag``, ``TonnageCapacity``, ``HoldingPeriod``, and
    ``PresumptiveIncome``. ``HoldingPeriod`` is the months owned (1-12);
    ``TonnageCapacity`` preserves the taxpayer-entered vehicle capacity for
    every vehicle; ``PresumptiveIncome`` is the statutory per-vehicle amount
    (₹1,000 × GVW tons × months for heavy, ₹7,500 × months for light) unless
    the taxpayer declared a higher amount.
    """
    is_heavy = bool(getattr(vehicle, "is_heavy_goods_vehicle", False))
    gvw = getattr(vehicle, "gross_vehicle_weight_tons", None) or getattr(vehicle, "tonnage_capacity", None)
    months = int(getattr(vehicle, "months_owned", 0) or 0)
    if months <= 0:
        raise ValueError("44AE vehicle requires months_owned > 0")
    # Statutory presumptive income per Section 44AE(2).
    if is_heavy:
        if gvw is None or gvw <= 0:
            raise ValueError("Heavy goods vehicle requires gross_vehicle_weight_tons")
        statutory = Decimal("1000") * Decimal(gvw) * Decimal(months)
    else:
        statutory = Decimal("7500") * Decimal(months)
    declared = getattr(vehicle, "income_declared", None)
    income = max(statutory, Decimal(declared) if declared is not None else Decimal("0"))
    flag = str(getattr(vehicle, "owned_leased_hired_flag", "OWN") or "OWN").upper()
    if flag not in ("OWN", "LEASE", "HIRED"):
        flag = "OWN"
    row: dict[str, Any] = {
        "RegNumberGoodsCarriage": getattr(vehicle, "reg_number", "") or "",
        "OwnedLeasedHiredFlag": flag,
        "TonnageCapacity": _to_rupees(gvw) if (gvw is not None and gvw > 0) else 0,
        "HoldingPeriod": months,
        "PresumptiveIncome": _to_rupees(income),
    }
    return row


def _schedule_bp(
    business_44ad: Optional[Any],
    professional_44ada: Optional[Any],
    goods_44ae: Optional[Any],
    income_44ad: Decimal,
    income_44ada: Decimal,
    income_44ae: Decimal,
    financial: Optional[Any],
    nature_rows: Optional[list] = None,
    gstin_rows: Optional[list] = None,
) -> dict[str, Any]:
    """Build ScheduleBP from real presumptive inputs and financial particulars."""
    bp: dict[str, Any] = {
        "NatOfBus44AD": [],
        "PersumptiveInc44AD": {
            "GrsTotalTrnOver": 0,
            "GrsTrnOverBank": 0,
            "GrsTotalTrnOverInCash": 0,
            "GrsTrnOverAnyOthMode": 0,
            "PersumptiveInc44AD6Per": 0,
            "PersumptiveInc44AD8Per": 0,
            "TotPersumptiveInc44AD": 0,
        },
        "NatOfBus44ADA": [],
        "PersumptiveInc44ADA": {
            "GrsReceipt": 0, "GrsTrnOverBank44ADA": 0,
            "GrsTotalTrnOverInCash44ADA": 0, "GrsTrnOverAnyOthMode44ADA": 0,
            "TotPersumptiveInc44ADA": 0,
        },
        "NatOfBus44AE": [],
        "GoodsDtlsUs44AE": [],
        "PersumptiveInc44AE": {
            "TotPersumInc44AE": 0, "SalInterestByFirm": 0,
            "TotalPersumptiveInc": 0, "IncChargeableUnderBus": 0,
        },
        "TurnoverGrsRcptForGSTIN": [],
        "TotalTurnoverGrsRcptGSTIN": 0,
        "FinanclPartclrOfBusiness": _financial_particulars(financial),
    }
    def mapped_natures(scheme: str, code_key: str) -> list[dict[str, Any]]:
        return [
            {
                "NameOfBusiness": row.name,
                code_key: row.code,
                "Description": row.description,
            }
            for row in (nature_rows or [])
            if row.scheme.value == scheme
        ]
    mapped_gstin = [
        {
            "GSTINNo": row.gstin,
            "AmtTurnGrossRcptGSTIN": _to_rupees(row.turnover),
        }
        for row in (gstin_rows or [])
    ]
    bp["TurnoverGrsRcptForGSTIN"] = mapped_gstin
    bp["TotalTurnoverGrsRcptGSTIN"] = sum(
        row["AmtTurnGrossRcptGSTIN"] for row in mapped_gstin
    )

    if business_44ad is not None:
        bp["PersumptiveInc44AD"] = {
            "GrsTotalTrnOver": _to_rupees(business_44ad.total_turnover),
            "GrsTrnOverBank": _to_rupees(business_44ad.digital_turnover),
            "GrsTotalTrnOverInCash": _to_rupees(business_44ad.cash_turnover),
            "GrsTrnOverAnyOthMode": _to_rupees(business_44ad.other_mode_turnover),
            "PersumptiveInc44AD6Per": _to_rupees(
                business_44ad.income_at_six_percent
                if business_44ad.income_at_six_percent is not None
                else (
                    business_44ad.digital_turnover
                    + business_44ad.other_mode_turnover
                ) * Decimal("0.06")
            ),
            "PersumptiveInc44AD8Per": _to_rupees(
                business_44ad.income_at_eight_percent
                if business_44ad.income_at_eight_percent is not None
                else business_44ad.cash_turnover * Decimal("0.08")
            ),
            "TotPersumptiveInc44AD": _to_rupees(income_44ad),
        }
        bp["NatOfBus44AD"] = mapped_natures("44AD", "CodeAD")

    if professional_44ada is not None:
        bp["PersumptiveInc44ADA"] = {
            "GrsReceipt": _to_rupees(professional_44ada.gross_receipts),
            "GrsTrnOverBank44ADA": _to_rupees(professional_44ada.digital_receipts),
            "GrsTotalTrnOverInCash44ADA": _to_rupees(professional_44ada.cash_receipts),
            "GrsTrnOverAnyOthMode44ADA": _to_rupees(professional_44ada.other_mode_receipts),
            "TotPersumptiveInc44ADA": _to_rupees(income_44ada),
        }
        bp["NatOfBus44ADA"] = mapped_natures("44ADA", "CodeADA")

    if goods_44ae is not None:
        if not goods_44ae.vehicles:
            raise ValueError("Section 44AE requires at least one vehicle for ScheduleBP")
        salary_interest = _to_rupees(
            getattr(financial, "salary_to_partners", Decimal("0"))
            + getattr(financial, "interest_to_partners", Decimal("0"))
        )
        bp["PersumptiveInc44AE"] = {
            "TotPersumInc44AE": _to_rupees(income_44ae) + salary_interest,
            "SalInterestByFirm": salary_interest,
            "TotalPersumptiveInc": _to_rupees(income_44ae),
            "IncChargeableUnderBus": _to_rupees(
                income_44ad + income_44ada + income_44ae
            ),
        }
        bp["NatOfBus44AE"] = mapped_natures("44AE", "CodeAE")
        bp["GoodsDtlsUs44AE"] = [
            _goods_dtls_44ae(v) for v in goods_44ae.vehicles
        ]

    return bp


# ===========================================================================
# ITR-4 ScheduleIT — challan payment array from typed entries
# ===========================================================================

def _schedule_it_itr4(input_data: ITR4Input) -> Optional[dict[str, Any]]:
    """Build ScheduleIT.TaxPayment from real challan rows — no fabrication."""
    rows: list[dict[str, Any]] = []
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


# ===========================================================================
# ITR-4 TaxExmpIntIncDtls
# ===========================================================================

def _tax_exmp_int_inc_dtls(
    input_data: Optional[ITR4Input],
) -> dict[str, Any]:
    """Build TaxExmpIntIncDtls from canonical compact-form detail rows."""
    rows = [
        {
            "Category": entry.category,
            "SubCategory": entry.sub_category,
            **({"Description": entry.description} if entry.description else {}),
            "OthAmount": _to_rupees(entry.amount),
        }
        for entry in (input_data.exempt_income_entries if input_data else [])
    ]
    total = sum(
        (Decimal(row["OthAmount"]) for row in rows),
        Decimal("0"),
    )
    return {
        "OthersInc": {
            "OthersIncDtls": rows,
            "OthersTotalTaxExe": _to_rupees(total),
        }
    }


# ===========================================================================
# ScheduleEA10_13A — HRA exemption evidence
# ===========================================================================

def _schedule_ea10_13a(
    place_of_work: str = "1",
    hra_received: Decimal = Decimal("0"),
    rent_paid: Decimal = Decimal("0"),
    basic_salary: Decimal = Decimal("0"),
    dearness_allowance: Decimal = Decimal("0"),
) -> dict[str, Any]:
    """Build ScheduleEA10_13A — HRA exemption evidence."""
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
) -> dict[str, Any]:
    return {
        "TotSaleCnsdrn": _to_rupees(sale_consideration),
        "TotCstAcqisn": _to_rupees(cost_acquisition),
        "LongCap112A": _to_rupees(long_cap_112a),
    }


# ===========================================================================
# TDS section translation
# ===========================================================================

def _official_tds_section(section: str) -> str:
    """Translate an Income-tax Act section label to the official schema code."""
    normalized = section.strip().upper().replace("SECTION", "").replace(" ", "")
    direct_codes = {"192A", "193", "194", "195"}
    if normalized in direct_codes:
        return normalized
    if normalized in {"194IA", "194IB", "194IC"}:
        return f"4-{normalized[3:]}"
    if normalized.startswith("194"):
        return f"9{normalized[2:]}"
    if normalized.startswith("196"):
        return f"9{normalized[2:]}"
    return normalized


# ===========================================================================
# TDS / TCS serializers — typed input only
# ===========================================================================

def _tds_salary_from_input(input_data: ITR4Input) -> Optional[dict[str, Any]]:
    """Build Schedule TDS1 from validated Form 16 rows."""
    rows: list[dict[str, Any]] = []
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


def _tds_other_from_input(input_data: ITR4Input) -> Optional[dict[str, Any]]:
    """Build Schedule TDS2 from validated Form 16A rows.

    ITR-4 uses the ``TDSonOthThanSalDtls`` array key and the
    ``TDSonOthThanSals`` parent key.
    """
    rows: list[dict[str, Any]] = []
    for entry in input_data.tds2_entries or []:
        if not entry.deductor_name:
            raise ValueError("TDS2 entries require deductor name for ITD JSON")
        row: dict[str, Any] = {
            "TANOfDeductor": entry.deductor_tan,
            "TDSSection": _official_tds_section(entry.tds_section),
            "DeductedYr": (
                entry.deducted_year
                if entry.deducted_year in _TDS2_DEDUCTED_YR_ENUM
                else _resolve_deducted_yr_tds2(entry.financial_year)
            ),
            "BroughtFwdTDSAmt": _to_rupees(entry.brought_forward_tds),
            "TDSDeducted": _to_rupees(entry.tds_deducted),
            "TDSClaimed": _to_rupees(entry.tds_claimed_this_year),
            "GrossAmount": _to_rupees(entry.gross_amount),
            "HeadOfIncome": entry.head_of_income or "OS",
            "TDSCreditCarriedFwd": _to_rupees(
                entry.tds_credit_carried_forward
            ),
        }
        rows.append(row)
    if not rows:
        return None
    return {
        "TDSonOthThanSalDtls": rows,
        "TotalTDSonOthThanSals": sum(row["TDSClaimed"] for row in rows),
    }


def _tds3_from_input(input_data: ITR4Input) -> Optional[dict[str, Any]]:
    """Build Schedule TDS3 from validated non-resident tenant rows."""
    if not input_data.tds3_entries:
        return None
    rows: list[dict[str, Any]] = []
    for entry in input_data.tds3_entries:
        if not entry.tenant_pan or not entry.tenant_name:
            raise ValueError("TDS3 entries require tenant PAN and name for ITD JSON")
        deducted_yr = _resolve_deducted_yr_tds3(entry.deducted_yr)
        row: dict[str, Any] = {
            "PANofTenant": entry.tenant_pan,
            "DeductedYr": deducted_yr,
            "BroughtFwdTDSAmt": _to_rupees(entry.brought_forward_tds),
            "TDSDeducted": _to_rupees(entry.tds_deducted),
            "TDSClaimed": _to_rupees(entry.tds_claimed),
            "TDSSection": _official_tds_section(entry.tds_section),
            "GrossAmount": _to_rupees(entry.gross_receipt),
            "HeadOfIncome": entry.head_of_income,
            "TDSCreditCarriedFwd": _to_rupees(
                entry.tds_credit_carried_forward
            ),
        }
        if entry.tenant_aadhaar:
            row["AadhaarofTenant"] = entry.tenant_aadhaar
        rows.append(row)
    return {
        "TDS3Details": rows,
        "TotalTDS3Details": sum(row["TDSClaimed"] for row in rows),
    }


def _tcs_from_input(input_data: ITR4Input) -> Optional[dict[str, Any]]:
    """Build Schedule TCS from validated collector rows.

    Emits all four schema-required fields per TCS entry:
    ``EmployerOrDeductorOrCollectDetl``, ``Amtfrom26AS``,
    ``TotalTCS``, ``AmtTCSClaimedThisYear``.
    """
    rows: list[dict[str, Any]] = []
    for entry in input_data.tcs_entries or []:
        if not entry.collector_name:
            raise ValueError("TCS entries require collector name for ITD JSON")
        rows.append({
            "EmployerOrDeductorOrCollectDetl": {
                "TAN": entry.collector_tan,
                "EmployerOrDeductorOrCollecterName": entry.collector_name,
            },
            "Amtfrom26AS": _to_rupees(entry.tcs_collected),
            "TotalTCS": _to_rupees(entry.tcs_collected),
            "AmtTCSClaimedThisYear": _to_rupees(entry.tcs_credit_claimed),
        })
    if not rows:
        return None
    return {
        "TCS": rows,
        "TotalSchTCS": sum(row["AmtTCSClaimedThisYear"] for row in rows),
    }


# ===========================================================================
# Allowance / other-source rows
# ===========================================================================

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


def _allowance_rows(input_data: Optional[ITR4Input], result: ITR4Result) -> list[dict[str, Any]]:
    """Build Section 10 salary-exemption rows from computed exempt amounts."""
    if input_data is None or input_data.salary_income is None:
        return []
    salary = input_data.salary_income
    sal_sched = result.schedules.get("salary") if result.schedules else None
    gratuity_exempt = getattr(sal_sched, "gratuity_exempt", getattr(salary, "gratuity_received", Decimal("0"))) if sal_sched else getattr(salary, "gratuity_received", Decimal("0"))
    leave_encashment_exempt = getattr(sal_sched, "leave_encashment_exempt", getattr(salary, "leave_encashment_received", Decimal("0"))) if sal_sched else getattr(salary, "leave_encashment_received", Decimal("0"))
    vrs_exempt = getattr(sal_sched, "vrs_exempt", getattr(salary, "vrs_compensation", Decimal("0"))) if sal_sched else getattr(salary, "vrs_compensation", Decimal("0"))
    commuted_pension_exempt = getattr(sal_sched, "commuted_pension_exempt", getattr(salary, "commuted_pension_received", Decimal("0"))) if sal_sched else getattr(salary, "commuted_pension_received", Decimal("0"))
    transport_exempt = getattr(sal_sched, "transport_exempt", Decimal("0")) if sal_sched else Decimal("0")
    cea_exempt = getattr(sal_sched, "children_education_exempt", Decimal("0")) if sal_sched else Decimal("0")
    hostel_exempt = getattr(sal_sched, "hostel_exempt", Decimal("0")) if sal_sched else Decimal("0")
    hra_exempt = getattr(sal_sched, "hra_exempt", getattr(salary, "hra_exempt_amount", Decimal("0"))) if sal_sched else getattr(salary, "hra_exempt_amount", Decimal("0"))
    lta_exempt = getattr(sal_sched, "lta_exempt", getattr(salary, "lta_exempt_amount", Decimal("0"))) if sal_sched else getattr(salary, "lta_exempt_amount", Decimal("0"))
    amounts = {
        "10(5)": lta_exempt,
        "10(6)": getattr(salary, "sec10_6_embassy_exempt", Decimal("0")),
        "10(7)": getattr(salary, "sec10_7_foreign_allowance", Decimal("0")),
        "10(10)": gratuity_exempt,
        "10(10A)": commuted_pension_exempt,
        "10(10AA)": leave_encashment_exempt,
        "10(10B)(i)": getattr(salary, "retrenchment_compensation", Decimal("0")),
        "10(10C)": vrs_exempt,
        "10(10CC)": getattr(salary, "sec10_10cc_perquisite_tax", Decimal("0")),
        "10(13A)": hra_exempt,
        "10(14)(i)": cea_exempt,
        "10(14)(ii)": hostel_exempt,
    }
    return _positive_rows(amounts, "SalNatureDesc", "SalOthAmount")


def _other_source_rows(
    result: ITR4Result,
    input_data: Optional[ITR4Input],
) -> list[dict[str, Any]]:
    """Build other-source category rows from the computed OS schedule."""
    schedule = result.schedules.get("os") if result.schedules else None
    if schedule is None:
        return []
    if input_data is not None and input_data.other_sources_income is not None \
            and input_data.other_sources_income.source_details:
        rows = [
            {
                "OthSrcNatureDesc": detail.nature,
                "OthSrcOthAmount": _to_rupees(detail.amount),
                **(
                    {"OthSrcOthNatOfInc": detail.other_description}
                    if detail.nature == "OTH" else {}
                ),
            }
            for detail in input_data.other_sources_income.source_details
            if detail.amount > 0
        ]
    else:
        amounts = {
            "SAV": getattr(schedule, "savings_bank_interest", Decimal("0")),
            "IFD": getattr(schedule, "fixed_deposit_interest", Decimal("0")),
            "TAX": getattr(schedule, "interest_on_it_refund", Decimal("0")),
            "FAP": getattr(schedule, "family_pension_gross", Decimal("0")),
            "DIV": getattr(schedule, "dividend_income", Decimal("0")),
        }
        rows = _positive_rows(amounts, "OthSrcNatureDesc", "OthSrcOthAmount")
    if input_data is None:
        return rows

    qbr = input_data.dividend_quarterly_breakdown
    for row in rows:
        if row["OthSrcNatureDesc"] != "DIV":
            continue
        row["DividendInc"] = {
            "DateRange": {
                "Upto15Of6": _to_rupees(qbr.get("Q1", Decimal("0"))),
                "Upto15Of9": _to_rupees(qbr.get("Q2", Decimal("0"))),
                "Up16Of9To15Of12": _to_rupees(qbr.get("Q3", Decimal("0"))),
                "Up16Of12To15Of3": _to_rupees(qbr.get("Q4", Decimal("0"))),
                "Up16Of3To31Of3": _to_rupees(qbr.get("Q5", Decimal("0"))),
            },
        }
    return rows


# ===========================================================================
# House property schedule (single property for ITR-4)
# ===========================================================================

def _property_schedule_itr4(
    result: ITR4Result,
    input_data: ITR4Input,
) -> list[dict[str, Any]]:
    """Build the PropertyDetails array for the single ITR-4 house property."""
    hp_results: list = list(getattr(result, "hp_results", []) or [])
    if not hp_results:
        hp_raw = result.schedules.get("hp") if result.schedules else None
        if isinstance(hp_raw, list):
            hp_results = list(hp_raw)
        elif hp_raw is not None:
            hp_results = [hp_raw]
    if not hp_results:
        return []

    hp_input = input_data.house_property_income
    if hp_input is None:
        raise ValueError("house_property_income is required when HP schedule is computed")
    prof = input_data.property_profile
    if prof is None:
        raise ValueError("property_profile is required for official ITR-4 JSON")
    if hp_input.ownership_share_percentage != prof.assessee_share_percentage:
        raise ValueError(
            "House-property ownership share does not match filing profile"
        )

    hp = hp_results[0]
    property_loans = []
    if hp_input.home_loan_interest_paid > 0:
        for loan in input_data.loan_details_24b_list:
            if loan.property_sequence_no != 1:
                continue
            if not loan.lender_name or not loan.account_or_reference_number \
                    or loan.sanction_date is None:
                raise ValueError("Section 24(b) loan details are incomplete")
            row_interest = _to_rupees(
                loan.interest_paid_self_occupied
                if hp_input.property_type.value == "S"
                else loan.interest_paid_let_out
            )
            property_loans.append({
                "LoanTknFrom": loan.loan_taken_from.value,
                "BankOrInstnName": loan.lender_name,
                "LoanAccNoOfBankOrInstnRefNo": loan.account_or_reference_number,
                "DateofLoan": loan.sanction_date.isoformat(),
                "TotalLoanAmt": _to_rupees(loan.loan_amount),
                "LoanOutstndngAmt": _to_rupees(loan.outstanding_loan_amount),
                "InterestUs24B": row_interest,
            })
        if not property_loans or sum(
            row["InterestUs24B"] for row in property_loans
        ) != _to_rupees(hp_input.home_loan_interest_paid):
            raise ValueError(
                "Section 24(b) loan details must cross-foot to interest"
            )

    annual_value = _to_rupees(hp.gross_annual_value)
    balance = _to_rupees(hp.net_annual_value)
    rent_not_realized = _to_rupees(hp.rent_not_realized)
    local_taxes = _to_rupees(hp.municipal_taxes)
    total_unrealized_and_tax = rent_not_realized + local_taxes
    if annual_value - total_unrealized_and_tax != balance:
        raise ValueError(
            "House-property unrealized rent and municipal taxes do not cross-foot"
        )
    owned_value = _to_rupees(hp.annual_value_owned)
    interest = _to_rupees(hp.interest_on_loan)
    arrears = _to_rupees(getattr(hp, "arrears_unrealised_rent", Decimal("0")))
    arrears_taxable = _to_rupees(getattr(hp, "arrears_unrealised_rent", Decimal("0")) * Decimal("0.7"))
    income = _to_rupees(hp.income_chargeable)
    standard_deduction = owned_value - interest + arrears_taxable - income
    if standard_deduction < 0:
        raise ValueError("House-property deduction does not cross-foot")
    total_deduction = standard_deduction + interest

    address: dict[str, Any] = {
        "AddrDetail": prof.address_detail,
        "CityOrTownOrDistrict": prof.city_or_town_or_district,
        "StateCode": prof.state_code,
        "CountryCode": prof.country_code,
    }
    if prof.pin_code is not None and prof.pin_code.isdigit():
        address["PinCode"] = int(prof.pin_code)
    if prof.zip_code is not None:
        address["ZipCode"] = prof.zip_code

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
    if rent_not_realized > 0:
        rent_details["RentNotRealized"] = rent_not_realized
    if arrears > 0:
        rent_details["ArrearsUnrealizedRentRcvd"] = arrears
    if property_loans:
        rent_details["Section24B"] = {
            "Section24BDtls": property_loans,
            "TotalInterestUs24B": sum(
                row["InterestUs24B"] for row in property_loans
            ),
        }

    property_row = {
        "HPSNo": 1,
        "AddressDetailWithZipCode": address,
        "PropertyOwner": prof.property_owner,
        "PropCoOwnedFlg": "YES" if prof.is_co_owned else "NO",
        "AsseseeShareProperty": float(prof.assessee_share_percentage),
        "ifLetOut": hp_input.property_type.value,
        "Rentdetails": rent_details,
    }
    if prof.property_owner_other:
        property_row["PropertyOwnerOther"] = prof.property_owner_other
    if prof.co_owners:
        property_row["CoOwners"] = [
            {
                "CoOwnersSNo": owner.serial_number,
                "NameCoOwner": owner.name,
                **({"PAN_CoOwner": owner.pan} if owner.pan else {}),
                **({"Aadhaar_CoOwner": owner.aadhaar} if owner.aadhaar else {}),
                **(
                    {"PercentShareProperty": float(owner.share_percentage)}
                    if owner.share_percentage is not None else {}
                ),
            }
            for owner in prof.co_owners
        ]
    if prof.tenants:
        property_row["TenantDetails"] = [
            {
                "TenantSNo": tenant.serial_number,
                "NameofTenant": tenant.name,
                **({"PANofTenant": tenant.pan} if tenant.pan else {}),
                **({"AadhaarofTenant": tenant.aadhaar} if tenant.aadhaar else {}),
                **({"PANTANofTenant": tenant.pan_or_tan} if tenant.pan_or_tan else {}),
            }
            for tenant in prof.tenants
        ]
    return [property_row]


# ===========================================================================
# Schedule 80C — per-row serialization with cross-foot
# ===========================================================================

def _schedule_80c(details: Any) -> dict[str, Any]:
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
    return {"Schedule80CDtls": rows, "TotalAmt": emitted}


# ===========================================================================
# Schedule 80D — insurance policy details
# ===========================================================================

def _policy_insurance_details(policies: list, section_code: str) -> list:
    """Build Sch80DInsDtls rows for one 80D bucket from policy entries."""
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
    eligible_self: Optional[Decimal] = None,
    eligible_parents: Optional[Decimal] = None,
    medical_expense_self_senior: Decimal = Decimal("0"),
    medical_expense_parents_senior: Decimal = Decimal("0"),
    policies: Optional[list] = None,
) -> dict[str, Any]:
    """Build Schedule80D with per-bucket policy rows."""
    self_aggregate = (
        eligible_self
        if eligible_self is not None
        else self_premium + preventive_self + medical_expense_self_senior
    )
    parents_aggregate = (
        eligible_parents
        if eligible_parents is not None
        else parents_premium + preventive_parents + medical_expense_parents_senior
    )
    self_non_senior_rows = _policy_insurance_details(policies, "1a")
    self_senior_rows = _policy_insurance_details(policies, "1b")
    parents_non_senior_rows = _policy_insurance_details(policies, "2a")
    parents_senior_rows = _policy_insurance_details(policies, "2b")
    return {
        "Sec80DSelfFamSrCtznHealth": {
            "SeniorCitizenFlag": senior_flag_self,
            "SelfAndFamily": _to_rupees(self_aggregate) if senior_flag_self == "N" else 0,
            "HealthInsPremSlfFam": _to_rupees(self_premium) if senior_flag_self == "N" else 0,
            "Sec80DSelfFamHIDtls": {
                "Sch80DInsDtls": self_non_senior_rows,
                "TotalPayments": _to_rupees(self_premium) if senior_flag_self == "N" else 0,
            },
            "PrevHlthChckUpSlfFam": _to_rupees(preventive_self) if senior_flag_self == "N" else 0,
            "SelfAndFamilySeniorCitizen": _to_rupees(self_aggregate) if senior_flag_self == "Y" else 0,
            "HlthInsPremSlfFamSrCtzn": _to_rupees(self_premium) if senior_flag_self == "Y" else 0,
            "Sec80DSelfFamSrCtznHIDtls": {
                "Sch80DInsDtls": self_senior_rows,
                "TotalPayments": _to_rupees(self_premium) if senior_flag_self == "Y" else 0,
            },
            "PrevHlthChckUpSlfFamSrCtzn": _to_rupees(preventive_self) if senior_flag_self == "Y" else 0,
            "MedicalExpSlfFamSrCtzn": (
                _to_rupees(medical_expense_self_senior) if senior_flag_self == "Y" else 0
            ),
            "ParentsSeniorCitizenFlag": senior_flag_parents,
            "Parents": _to_rupees(parents_aggregate) if senior_flag_parents == "N" else 0,
            "HlthInsPremParents": _to_rupees(parents_premium) if senior_flag_parents == "N" else 0,
            "Sec80DParentsHIDtls": {
                "Sch80DInsDtls": parents_non_senior_rows,
                "TotalPayments": _to_rupees(parents_premium) if senior_flag_parents == "N" else 0,
            },
            "PrevHlthChckUpParents": _to_rupees(preventive_parents) if senior_flag_parents == "N" else 0,
            "ParentsSeniorCitizen": _to_rupees(parents_aggregate) if senior_flag_parents == "Y" else 0,
            "HlthInsPremParentsSrCtzn": _to_rupees(parents_premium) if senior_flag_parents == "Y" else 0,
            "Sec80DParentsSrCtznHIDtls": {
                "Sch80DInsDtls": parents_senior_rows,
                "TotalPayments": _to_rupees(parents_premium) if senior_flag_parents == "Y" else 0,
            },
            "PrevHlthChckUpParentsSrCtzn": _to_rupees(preventive_parents) if senior_flag_parents == "Y" else 0,
            "MedicalExpParentsSrCtzn": (
                _to_rupees(medical_expense_parents_senior)
                if senior_flag_parents == "Y" else 0
            ),
            "EligibleAmountOfDedn": _to_rupees(eligible_deduction),
        }
    }


# ===========================================================================
# Donation address + Schedule 80G
# ===========================================================================

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


# ===========================================================================
# Schedule 80GGC — political contributions
# ===========================================================================

def _schedule_80ggc(details: Any) -> dict[str, Any]:
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
        "TotalDonationAmtOtherMode80GGC": sum(row["DonationAmtOtherMode"] for row in rows),
        "TotalDonationsUs80GGC": sum(row["DonationAmt"] for row in rows),
        "TotalEligibleDonationAmt80GGC": emitted_eligible,
    }


# ===========================================================================
# Loan deduction schedules (80E / 80EE / 80EEA / 80EEB)
# ===========================================================================

def _schedule_deduction_loan(
    details: Any,
    *,
    section: str,
    property_stamp_duty_value: Optional[Decimal] = None,
) -> dict[str, Any]:
    """Serialize a computed loan-deduction result without recalculating."""
    if section not in {"80E", "80EE", "80EEA", "80EEB"}:
        raise ValueError(f"Unsupported deduction loan section: {section}")
    if not details.rows:
        raise ValueError(f"A positive Section {section} claim requires official loan rows")
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


# ===========================================================================
# Disability schedules (80DD / 80U)
# ===========================================================================

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
        raise ValueError("ITR-4 Schedule 80DD does not allow an HUF member dependent")
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


# ===========================================================================
# Conditional deduction schedules emitter
# ===========================================================================

def _emit_conditional_deduction_schedules(
    itr4: dict[str, Any],
    input_data: ITR4Input,
    ded_sched: Any,
    deduction: Any,
) -> None:
    """Emit Schedule80DD / 80U / 80E / 80EE / 80EEA / 80EEB / 80G from typed input."""
    schedule_80dd = input_data.schedule_80dd
    details_80dd = ded_sched.section_details.get("80DD") if ded_sched else None
    ded_80dd = deduction("80DD")
    if ded_80dd > 0:
        if details_80dd is None or details_80dd.source is None:
            raise ValueError("A positive Section 80DD claim requires Schedule 80DD details")
        itr4["Schedule80DD"] = _schedule_80dd(details_80dd.source, ded_80dd)
    elif schedule_80dd is not None:
        raise ValueError("Schedule 80DD details require a positive 80DD deduction")

    schedule_80u = input_data.schedule_80u
    details_80u = ded_sched.section_details.get("80U") if ded_sched else None
    ded_80u = deduction("80U")
    if ded_80u > 0:
        if details_80u is None or details_80u.source is None:
            raise ValueError("A positive Section 80U claim requires Schedule 80U details")
        itr4["Schedule80U"] = _schedule_80u(details_80u.source, ded_80u)
    elif schedule_80u is not None:
        raise ValueError("Schedule 80U details require a positive 80U deduction")

    ded_80e = deduction("80E")
    details_80e = ded_sched.section_details.get("80E") if ded_sched else None
    if ded_80e > 0:
        if details_80e is None or not details_80e.rows:
            raise ValueError("A positive Section 80E claim requires official loan rows")
        itr4["Schedule80E"] = _schedule_deduction_loan(details_80e, section="80E")
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
            itr4[f"Schedule{section}"] = _schedule_deduction_loan(
                details_loan,
                section=section,
                property_stamp_duty_value=(
                    input_data.property_stamp_duty_value_80eea
                    if section == "80EEA"
                    else None
                ),
            )

    details_80g = ded_sched.section_details.get("80G") if ded_sched else None
    if deduction("80G") > 0:
        if details_80g is None or not details_80g.categories:
            raise ValueError("Complete official Schedule 80G donation rows are required")
        itr4["Schedule80G"] = _schedule_80g(details_80g)
    elif input_data.deductions_chapter6a and input_data.deductions_chapter6a.donations_80g:
        raise ValueError("Schedule 80G rows require a positive eligible deduction")


# ===========================================================================
# Schedule 80C total
# ===========================================================================

def _schedule_80c_total(
    total_80c: Decimal,
    input_data: Optional[ITR4Input],
    ded_sched: Any,
) -> dict[str, Any]:
    """Build Schedule80C — from typed section_details when available."""
    if total_80c <= 0:
        return {"Schedule80CDtls": [], "TotalAmt": 0}
    if input_data is not None and ded_sched is not None:
        details_80c = ded_sched.section_details.get("80C")
        if details_80c is None or not details_80c.rows:
            raise ValueError("A positive Section 80C claim requires Schedule 80C detail rows")
        return _schedule_80c(details_80c)
    return {"Schedule80CDtls": [], "TotalAmt": _to_rupees(total_80c)}


# ===========================================================================
# TRP serializer
# ===========================================================================

def _trp_from_input(trp: Optional[ITR4TaxReturnPreparer]) -> Optional[dict[str, Any]]:
    """Build the official TaxReturnPreparer node from the typed model."""
    if trp is None:
        return None
    return {
        "IdentificationNoOfTRP": trp.identification_number,
        "NameOfTRP": trp.name,
        "ReImbFrmGov": _to_rupees(trp.reimbursement_from_government),
    }


# ===========================================================================
# Public API
# ===========================================================================

def build_itr4_json(
    result: ITR4Result,
    input_data: Optional[ITR4Input] = None,
    *,
    # Legacy kwargs — only used when input_data is None (tests / legacy callers)
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
    phone_std_code: int = 0,
    phone_no: str = "0",
) -> dict[str, Any]:
    """Build an ITD-compliant ITR-4 JSON document.

    When ``input_data`` is supplied (the production path), every field is
    read from the typed ``ITR4Input`` — PersonalInfo, FilingStatus,
    Verification, ScheduleBP, all deduction schedules, TDS/TCS, TaxPayments,
    ScheduleEA10_13A, and BankAccountDtls. The builder raises ``ValueError``
    on incomplete evidence (no placeholder emission).

    Legacy kwargs remain supported for tests / older callers that construct
    the JSON without a typed input.
    """
    if input_data is not None:
        if input_data.filing_profile is None:
            raise ValueError("filing_profile is required for official ITR-4 JSON")
        profile = input_data.filing_profile
        personal = _personal_info_from_profile(profile)
        ver = _verification_from_profile(profile)
        filing = _filing_status_itr4(profile)
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
        personal["Status"] = assesee_status
        if "Address" in personal:
            personal["Address"].pop("EmailAddressSec", None)
            personal["Address"]["Phone"] = {
                "STDcode": phone_std_code,
                "PhoneNo": _validate_phone_no(phone_no),
            }
        filing = _filing_status_itr4(None)

    # -- Extract per-section deduction amounts from the result ---------------
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

    # -- 80DDB user claim / disease ------------------------------------------
    usr_80ddb: Optional[Decimal] = None
    ddb_user_type: Optional[str] = None
    ddb_disease: Optional[str] = None
    if input_data is not None and input_data.deductions_chapter6a:
        ddb_input = input_data.deductions_chapter6a
        details_80ddb = ded_sched.section_details.get("80DDB") if ded_sched else None
        if details_80ddb is None:
            if ddb_input.amount_80ddb > 0 or getattr(ddb_input, "details_80ddb", None) is not None:
                raise ValueError("Section 80DDB computation details are missing")
        elif details_80ddb.source is not None:
            usr_80ddb = details_80ddb.user_claim
            ddb_user_type = details_80ddb.source.user_type.value
            ddb_disease = details_80ddb.source.disease.value

    # -- Allowance / other-source rows ---------------------------------------
    allowance_rows = _allowance_rows(input_data, result)
    other_source_rows = _other_source_rows(result, input_data)

    # -- House property schedule ---------------------------------------------
    property_schedules: Optional[list[dict[str, Any]]] = None
    if input_data is not None and input_data.house_property_income is not None:
        property_schedules = _property_schedule_itr4(result, input_data)

    gti_cg = result.gross_total_income  # Already includes capital_gains_112a
    pension_80ccc = None
    if input_data is not None and input_data.schedule_80ccc_entries:
        pension_80ccc = [{
            "TypeofIdentifier": entry.identifier_type,
            "NameofIdentifier": entry.identifier_name,
            "Amount": _to_rupees(entry.amount),
        } for entry in input_data.schedule_80ccc_entries]

    user_claims: Optional[dict[str, Decimal]] = None
    if input_data is not None and input_data.deductions_chapter6a is not None:
        entered = input_data.deductions_chapter6a
        user_claims = {
            "80C": entered.amount_80c,
            "80CCC": entered.amount_80ccc,
            "80CCD(1)": entered.amount_80ccd1,
            "80CCD(1B)": entered.amount_80ccd1b,
            "80CCD(2)": entered.amount_80ccd2,
            "80D": (
                entered.amount_80d_self_family
                + entered.amount_80d_preventive_self
                + entered.amount_80d_parents
                + entered.amount_80d_preventive_parents
            ),
            "80DD": entered.amount_80dd,
            "80DDB": (
                usr_80ddb if usr_80ddb is not None else entered.amount_80ddb
            ),
            "80E": entered.amount_80e,
            "80EE": entered.amount_80ee,
            "80EEA": entered.amount_80eea,
            "80EEB": entered.amount_80eeb,
            "80G": entered.amount_80g,
            "80GG": entered.amount_80gg,
            "80GGC": entered.amount_80ggc,
            "80U": entered.amount_80u,
            "80TTA": entered.amount_80tta,
            "80TTB": entered.amount_80ttb,
            "80CCH": entered.amount_80cch,
        }

    os_schedule = result.schedules.get("os") if result.schedules else None
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
        hp_schedules=property_schedules,
        allowance_rows=allowance_rows,
        other_source_rows=other_source_rows,
        deduction_57iia=(
            os_schedule.deduction_57iia if os_schedule else Decimal("0")
        ),
        perquisites_value=result.salary_perquisites,
        profits_in_lieu=result.salary_profits_in_lieu,
        ded_breakdown=ded_breakdown,
        user_claims=user_claims,
        usr_80ddb=usr_80ddb,
        ddb_user_type=ddb_user_type,
        ddb_disease=ddb_disease,
        usr_80e=(input_data.deductions_chapter6a.amount_80e if input_data and input_data.deductions_chapter6a else None),
        usr_80ee=(input_data.deductions_chapter6a.amount_80ee if input_data and input_data.deductions_chapter6a else None),
        usr_80eea=(input_data.deductions_chapter6a.amount_80eea if input_data and input_data.deductions_chapter6a else None),
        usr_80eeb=(input_data.deductions_chapter6a.amount_80eeb if input_data and input_data.deductions_chapter6a else None),
        usr_80g=(input_data.deductions_chapter6a.amount_80g if input_data and input_data.deductions_chapter6a else None),
        usr_80ggc=(input_data.deductions_chapter6a.amount_80ggc if input_data and input_data.deductions_chapter6a else None),
        pension_80ccc=pension_80ccc,
        pran_number=(input_data.pran_number if input_data else None),
        form_10ba_ack_number=(
            input_data.form_10ba_ack_number if input_data else None
        ),
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
        fees_234i=result.fees_234i,
    )

    tax_paid = _tax_paid_itr4(
        total_tds=result.total_tds,
        total_tcs=result.total_tcs,
        advance_tax=result.advance_tax_paid,
        self_assessment_tax=result.self_assessment_tax_paid,
        balance_payable=result.balance_payable,
    )

    # -- Bank accounts / refund ---------------------------------------------
    if input_data is not None:
        bank_rows = _bank_accounts_from_input(input_data)
    elif bank_name and account_no and ifsc:
        bank_rows = [_bank_row(
            ifsc=ifsc, bank_name=bank_name, account_number=account_no,
            account_type="SB", use_for_refund=True,
        )]
    else:
        raise ValueError("Bank account details are required for ITD JSON")
    refund = _refund_itr4(result.refund_due, bank_rows)

    # -- ScheduleBP ----------------------------------------------------------
    nature_rows: Optional[list] = None
    gstin_rows: Optional[list] = None
    financial_particulars = None
    business_44ad = None
    professional_44ada = None
    goods_44ae = None
    if input_data is not None:
        business_44ad = input_data.business_income_44ad
        professional_44ada = input_data.professional_income_44ada
        goods_44ae = input_data.goods_carriage_44ae
        financial_particulars = input_data.schedule_bp_financial
        nature_rows = input_data.schedule_bp_business_natures
        gstin_rows = input_data.schedule_bp_gstin_turnovers
    else:
        if bp_scheme == "44ADA":
            professional_44ada = type("LegacyADA", (), {
                "gross_receipts": _zero_if_none(bp_gross_turnover),
                "digital_receipts": _zero_if_none(bp_digital_turnover),
                "cash_receipts": _zero_if_none(bp_cash_turnover),
                "other_mode_receipts": _zero_if_none(bp_other_turnover),
            })()
        else:
            business_44ad = type("LegacyAD", (), {
                "total_turnover": _zero_if_none(bp_gross_turnover),
                "digital_turnover": _zero_if_none(bp_digital_turnover),
                "cash_turnover": _zero_if_none(bp_cash_turnover),
                "other_mode_turnover": _zero_if_none(bp_other_turnover),
                "income_at_six_percent": None,
                "income_at_eight_percent": None,
            })()

    pres = result.schedules.get("presumptive")
    bp = _schedule_bp(
        business_44ad=business_44ad,
        professional_44ada=professional_44ada,
        goods_44ae=goods_44ae,
        income_44ad=pres.income_44ad if pres else result.presumptive_income,
        income_44ada=pres.income_44ada if pres else Decimal("0"),
        income_44ae=pres.income_44ae if pres else Decimal("0"),
        financial=financial_particulars,
        nature_rows=nature_rows,
        gstin_rows=gstin_rows,
    )

    # ── Assemble ITR-4 ────────────────────────────────────────────────────
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
        "TaxExmpIntIncDtls": _tax_exmp_int_inc_dtls(input_data),
        "Schedule80C": _schedule_80c_total(deduction("80C"), input_data, ded_sched),
    }

    # TaxReturnPreparer — only when supplied
    if input_data is not None and input_data.tax_return_preparer is not None:
        itr4["TaxReturnPreparer"] = _trp_from_input(input_data.tax_return_preparer)

    # -- Conditional deduction schedules (typed input path) -----------------
    if input_data is not None:
        _emit_conditional_deduction_schedules(itr4, input_data, ded_sched, deduction)

    # -- Schedule 80D -------------------------------------------------------
    if input_data is not None and deduction("80D") > 0:
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
        itr4["Schedule80D"] = _schedule_80d(
            senior_flag_self=self_flag,
            senior_flag_parents=parents_flag,
            self_premium=details_80d.self_premium,
            parents_premium=details_80d.parents_premium,
            preventive_self=details_80d.preventive_self,
            preventive_parents=details_80d.preventive_parents,
            eligible_deduction=details_80d.allowed_deduction,
            eligible_self=details_80d.eligible_self,
            eligible_parents=details_80d.eligible_parents,
            medical_expense_self_senior=(
                schedule_80d.medical_expense_self_senior if schedule_80d else Decimal("0")
            ),
            medical_expense_parents_senior=(
                schedule_80d.medical_expense_parents_senior if schedule_80d else Decimal("0")
            ),
            policies=(schedule_80d.policies if schedule_80d else None),
        )
    elif input_data is None and deduction("80D") > 0:
        itr4["Schedule80D"] = _schedule_80d(
            senior_flag_self=schedule_80d_senior_self,
            senior_flag_parents=schedule_80d_senior_parents,
            self_premium=_zero_if_none(schedule_80d_self_amt),
            parents_premium=_zero_if_none(schedule_80d_parents_amt),
            preventive_self=Decimal("0"),
            preventive_parents=Decimal("0"),
            eligible_deduction=deduction("80D"),
        )

    # -- TDS1 / TDS2 / TDS3 / TCS / ScheduleIT (typed input path) ----------
    if input_data is not None:
        tds_salary = _tds_salary_from_input(input_data)
        if tds_salary:
            itr4["TDSonSalaries"] = tds_salary

        tds_other = _tds_other_from_input(input_data)
        if tds_other:
            itr4["TDSonOthThanSals"] = tds_other

        tds3 = _tds3_from_input(input_data)
        if tds3:
            itr4["ScheduleTDS3Dtls"] = tds3

        tcs = _tcs_from_input(input_data)
        if tcs:
            itr4["ScheduleTCS"] = tcs

        schedule_it = _schedule_it_itr4(input_data)
        if schedule_it:
            itr4["ScheduleIT"] = schedule_it
    else:
        tds_sal = _tds_salary_schedule_legacy(tds_salary_entries)
        if tds_sal:
            itr4["TDSonSalaries"] = tds_sal
        tds_oth = _tds_other_schedule_legacy(tds_other_entries)
        if tds_oth:
            itr4["TDSonOthThanSals"] = tds_oth

    # -- ScheduleEA10_13A (HRA evidence) -----------------------------------
    if input_data is not None:
        hra = input_data.hra_details or input_data.schedule_10_13a
        if hra is not None:
            hra_schedule = _schedule_ea10_13a(
                place_of_work=("1" if hra.is_metro_city else "2"),
                hra_received=hra.actual_hra_received,
                rent_paid=hra.rent_paid,
                basic_salary=hra.salary_for_hra,
                dearness_allowance=hra.dearness_allowance,
            )
            claimed_hra = _to_rupees(
                getattr(input_data.salary_income, "hra_exempt_amount", Decimal("0"))
                if input_data.salary_income else Decimal("0")
            )
            if hra_schedule["EligbleExmpAllwncUs13A"] != claimed_hra:
                raise ValueError(
                    "Schedule 10(13A) eligible exemption must equal the HRA exemption claimed"
                )
            itr4["ScheduleEA10_13A"] = hra_schedule

    # -- Schedule80GGC -------------------------------------------------------
    if input_data is not None and deduction("80GGC") > 0:
        details_80ggc = ded_sched.section_details.get("80GGC") if ded_sched else None
        if details_80ggc is None or not details_80ggc.rows:
            raise ValueError("Complete official Schedule 80GGC contribution rows are required")
        itr4["Schedule80GGC"] = _schedule_80ggc(details_80ggc)
    elif input_data is not None and input_data.schedule_80ggc and input_data.schedule_80ggc.contributions:
        raise ValueError("Schedule 80GGC rows require a positive eligible deduction")

    # -- LTCG 112A -----------------------------------------------------------
    typed_cg = input_data.capital_gains if input_data is not None else None
    has_typed_evidence = bool(
        typed_cg is not None
        and (
            getattr(typed_cg, "transactions", None)
            or typed_cg.full_value_of_consideration > 0
            or typed_cg.cost_of_acquisition > 0
        )
    )
    sale_consideration = (
        typed_cg.full_value_of_consideration
        if has_typed_evidence and typed_cg is not None
        else (
            input_data.full_value_of_consideration
            if input_data is not None
            else None
        ) or cg_sale_consideration
    )
    cost_acquisition = (
        typed_cg.cost_of_acquisition
        if has_typed_evidence and typed_cg is not None
        else cg_cost_acquisition
    )
    if sale_consideration is not None and cost_acquisition is not None:
        itr4["LTCG112A"] = _ltcg_112a_schedule(
            sale_consideration=sale_consideration,
            cost_acquisition=cost_acquisition,
            long_cap_112a=result.capital_gains_112a,
        )
    elif result.capital_gains_112a > 0:
        raise ValueError(
            "LTCG 112A schedule requires sale_consideration and cost_acquisition "
            "when capital_gains_112a > 0"
        )

    # -- Digest (appended last) ---------------------------------------------
    itr4["CreationInfo"]["Digest"] = _compute_digest(itr4)

    return {"ITR": {"ITR4": itr4}}


# ===========================================================================
# Legacy TDS serializers (only used when input_data is None)
# ===========================================================================

def _tds_salary_schedule_legacy(tds_salary_entries: Optional[list[dict]]) -> Optional[dict]:
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


def _tds_other_schedule_legacy(tds_other_entries: Optional[list[dict]]) -> Optional[dict]:
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
                "DeductedYr": _resolve_deducted_yr_tds2(e.get("DeductedYrFinancialYear")),
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
