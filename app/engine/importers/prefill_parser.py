"""
Form-agnostic ITD Prefill JSON parser.

Extracts every field available in the real ITD pre-filled JSON payload
into a flat intermediate representation.  The extractor does NOT know
which ITR form the taxpayer will eventually file — it pulls personal
info, salary, house property, other sources income, deductions, bank
accounts, TDS/TCS schedules, tax payments, and carry-forward losses
regardless of form, and lets the form-specific mappers in the frontend
pick what they need.

The real ITD prefill JSON is a composite payload combining pre-fill
data for all ITR forms plus statutory forms (Form 24Q, Form 26AS,
Form 3CD, etc.).  The key top-level sections are:

  - ``personalInfo`` — name, PAN, Aadhaar, DOB, address, contact
  - ``filingStatus`` — return section, residential status, new-regime
  - ``bankAccountDtls`` — list of bank-account groups
  - ``form26as`` — TDS-other-than-salary, schedule OS, dividends
  - ``form24q`` — salary-side deductions (80TTA), savings interest
  - ``insights`` — cumulative deductions (UsrDeductUndChapVIAType),
    other-sources income, savings/FD interest
  - ``lastFiledITR`` — house property, TCS, employment, audit, etc.
  - ``scheduleCFL`` — carry-forward losses
  - ``verification`` — declaration, capacity, place

The parser handles the three wrapper shapes (flat root, ``data``,
``prefillData``) and probes each section case-insensitively.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Root-unwrapping helpers
# ──────────────────────────────────────────────────────────────────────────────

_PREFILL_ROOT_KEYS: tuple[str, ...] = (
    "personalInfo",
    "filingStatus",
    "bankAccountDtls",
    "form26as",
    "form24q",
    "insights",
    "lastFiledITR",
    "scheduleCFL",
    "verification",
    "salaries",
    "tdsOnSalaries",
    "tdsOnOthThanSals",
    "scheduleDeductions",
)


def _unwrap_prefill_root(payload: Any) -> dict[str, Any]:
    """Return the prefill object from any of the known wrapper shapes.

    Args:
        payload: The parsed JSON (dict, list, or scalar).

    Returns:
        The dict containing the actual prefill fields.  If the payload
        is not a dict, returns an empty dict.
    """
    if not isinstance(payload, Mapping):
        return {}

    # Case 1: flat root — a known prefill key is a direct key.
    if any(key in payload for key in _PREFILL_ROOT_KEYS):
        return dict(payload)

    # Case 2/3: wrapped in "data" or "prefillData".
    for wrapper in ("data", "prefillData", "prefill", "formData"):
        inner = payload.get(wrapper)
        if isinstance(inner, Mapping) and any(
            key in inner for key in _PREFILL_ROOT_KEYS
        ):
            return dict(inner)

    # Fallback: return the payload as-is; the extractors handle missing keys.
    return dict(payload)


def _get(obj: Any, *keys: str, default: Any = None) -> Any:
    """Safely walk a nested object by keys; return default if any missing.

    Each key is matched case-insensitively against the object's keys.
    """
    current = obj
    for key in keys:
        if not isinstance(current, Mapping):
            return default
        # Case-insensitive match.
        match = None
        for k in current:
            if k.lower() == key.lower():
                match = current[k]
                break
        if match is None:
            return default
        current = match
    return current


def _get_list(obj: Any, *keys: str) -> list[Any]:
    """Like ``_get`` but coerces to a list; returns [] if missing."""
    val = _get(obj, *keys, default=None)
    if isinstance(val, list):
        return val
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Scalar coercion helpers
# ──────────────────────────────────────────────────────────────────────────────

def _to_str(value: Any) -> str:
    """Convert a value to a stripped string, treating None/0-length as empty."""
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _to_int(value: Any) -> int:
    """Convert a value to a non-negative integer, treating invalid as 0."""
    if value is None:
        return 0
    try:
        n = int(value)
    except (TypeError, ValueError):
        try:
            n = int(float(value))
        except (TypeError, ValueError):
            return 0
    return max(0, n)


def _to_float(value: Any) -> float:
    """Convert a value to a non-negative float, treating invalid as 0.0."""
    if value is None:
        return 0.0
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, n)


def _decode_aadhaar(value: Any) -> str:
    """Decode a base64-encoded Aadhaar number from the prefill.

    The CBDT prefill schema declares ``aadhaarCardNo`` as a base64-encoded
    string.  If the value decodes to a 12-digit number, return the plain
    digits; otherwise return the raw value stripped of whitespace.
    """
    raw = _to_str(value)
    if not raw:
        return ""
    try:
        decoded = base64.b64decode(raw, validate=True).decode("utf-8").strip()
    except Exception:
        return raw
    if re.fullmatch(r"\d{12}", decoded):
        return decoded
    return decoded or raw


def _to_date(value: Any) -> str:
    """Normalize a date value to YYYY-MM-DD; return empty if unparseable."""
    raw = _to_str(value)
    if not raw:
        return ""
    # Already ISO format.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    # DD/MM/YYYY → YYYY-MM-DD.
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        dd, mm, yyyy = m.groups()
        return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
    return raw


# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PrefillName:
    """Three-part taxpayer name from the prefill."""

    first_name: str = ""
    middle_name: str = ""
    surname_or_org_name: str = ""

    @property
    def full_name(self) -> str:
        """Derive the full name by joining non-empty parts."""
        return " ".join(
            part for part in (self.first_name, self.middle_name, self.surname_or_org_name)
            if part
        )


@dataclass
class PrefillAddress:
    """Address fields from the prefill (residence + contact)."""

    residence_no: str = ""
    residence_name: str = ""
    road_or_street: str = ""
    locality_or_area: str = ""
    city_or_town_or_district: str = ""
    state_code: str = ""
    country_code: str = ""
    pin_code: str = ""
    zip_code: str = ""
    country_code_mobile: int = 0
    mobile_no: int = 0
    country_code_mobile_sec: int = 0
    mobile_no_sec: int = 0
    email_address: str = ""
    email_address_secondary: str = ""
    phone_std_code: int = 0
    phone_no: int = 0


@dataclass
class PrefillPersonalInfo:
    """Personal information block from the prefill."""

    pan: str = ""
    aadhaar_card_no: str = ""
    name: PrefillName = field(default_factory=PrefillName)
    assessee_ver_name: str = ""
    father_name: str = ""
    dob: str = ""
    status: str = ""
    employer_category: str = ""
    address: PrefillAddress = field(default_factory=PrefillAddress)
    residential_status: str = ""
    portugese_cc5a: str = ""


@dataclass
class PrefillFilingStatus:
    """Filing status block from the prefill."""

    return_file_sec: int = 0
    residential_status: str = ""
    section_115ba: str = ""
    assessee_rep_flg: str = ""
    business_trust_flag: str = ""
    fii_fpi_flag: str = ""
    foreign_exchange_flag: str = ""
    orig_ret_filed_date: str = ""
    receipt_no: str = ""
    notice_date_under_sec: str = ""
    unique_no: str = ""
    seventh_proviso_139: str = ""
    opting_new_tax_regime_form10if: str = ""


@dataclass
class PrefillEmployerEntry:
    """One employer from the salary schedule."""

    employer_name: str = ""
    tan: str = ""
    gross_salary: int = 0
    salary: int = 0
    value_of_perquisites: int = 0
    profits_in_lieu_of_salary: int = 0
    nature_of_employment: str = ""
    employer_address: str = ""
    employer_city: str = ""
    employer_state_code: str = ""
    employer_pin_code: str = ""
    employer_zip_code: str = ""
    tds_deducted_from_salary: int = 0


@dataclass
class PrefillSalaryInsights:
    """Cumulative salary from the prefill ``insights`` block."""

    salary: int = 0
    perquisites_value: int = 0
    profits_in_salary: int = 0
    salary_update_timestamp: str = ""


@dataclass
class PrefillHouseProperty:
    """One house property from the prefill."""

    address: str = ""
    city: str = ""
    state_code: str = ""
    pin_code: int = 0
    country_code: str = ""
    zip_code: str = ""
    if_let_out: str = ""
    type_of_hp: str = ""
    gross_rent: int = 0
    co_owners: list[dict[str, Any]] = field(default_factory=list)
    tenant_details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PrefillOtherSourcesIncome:
    """Other sources income from the prefill."""

    dividend_gross: int = 0
    dividend_oth_than_22e: int = 0
    interest_from_savings_bank: int = 0
    interest_from_term_deposit: int = 0
    interest_from_others: int = 0
    rent_from_mach_plant_bldgs: int = 0
    lottery_puzzle_income: int = 0
    other_income_details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PrefillBankAccount:
    """One bank account from the prefill."""

    bank_account_no: str = ""
    bank_name: str = ""
    ifsc_code: str = ""
    account_type: str = ""
    use_for_refund: str = "false"


@dataclass
class PrefillTDSEntry:
    """One TDS entry from the prefill (salary or other-than-salary)."""

    deductor_name: str = ""
    tan: str = ""
    section: str = ""
    income_amount: int = 0
    tds_deducted: int = 0
    tds_claimed: int = 0
    gross_amount: int = 0
    head_of_income: str = ""
    deducted_year: str = ""
    brought_fwd_tds: int = 0


@dataclass
class PrefillDeductions:
    """Chapter VI-A deductions from the prefill.

    Field names use lowercase ``section_80*`` regardless of how the
    prefill capitalizes them (``Section80TTB``, ``section80TTA``, etc.).
    The extractor normalizes the casing.
    """

    section_80c: int = 0
    section_80ccc: int = 0
    section_80ccd_employee_or_se: int = 0
    section_80ccd_1b: int = 0
    section_80ccd_employer: int = 0
    section_80d: int = 0
    section_80dd: int = 0
    section_80ddb: int = 0
    section_80e: int = 0
    section_80ee: int = 0
    section_80eea: int = 0
    section_80eeb: int = 0
    section_80g: int = 0
    section_80gg: int = 0
    section_80gga: int = 0
    section_80ggc: int = 0
    section_80u: int = 0
    section_80tta: int = 0
    section_80ttb: int = 0
    section_80cch: int = 0
    section_80qqb: int = 0
    section_80rrb: int = 0
    section_80la: int = 0
    total_chap_via_deductions: int = 0


@dataclass
class PrefillCarryForwardLoss:
    """One carry-forward loss from the prefill."""

    assessment_year: str = ""
    brought_fwd_bus_loss: int = 0
    bus_loss_oth_than_spec_loss_cf: int = 0
    hp_loss_cf: int = 0
    loss_frm_insu_cf: int = 0
    loss_frm_spec_bus_cf: int = 0
    loss_frm_specified_bus_cf: int = 0
    ltcg_loss_cf: int = 0
    oth_src_loss_race_horse_cf: int = 0
    stcg_loss_cf: int = 0
    date_of_filing: str = ""


@dataclass
class PrefillVerification:
    """Verification block from the prefill."""

    assessee_ver_name: str = ""
    assessee_ver_pan: str = ""
    father_name: str = ""
    capacity: str = ""
    place: str = ""


@dataclass
class PrefillTCSEntry:
    """One TCS entry from the prefill (lastFiledITR.scheduleTCS.tcs[])."""

    collector_name: str = ""
    tan: str = ""
    pan: str = ""
    section: str = ""
    gross_amount: int = 0
    tcs_collected: int = 0
    tcs_claimed: int = 0
    head_of_income: str = ""
    collected_year: str = ""


@dataclass
class PrefillPresumptiveIncome:
    """Presumptive income details (44AD/44ADA) from the prefill."""

    gross_receipt_44ada: int = 0
    declared_income_44ada: int = 0
    business_nature_codes: list[dict[str, str]] = field(default_factory=list)


@dataclass
class Prefill80DDetails:
    """Section 80D health-insurance details from the prefill."""

    self_family_senior_citizen_flag: str = ""
    parent_senior_citizen_flag: str = ""


@dataclass
class PrefillDepreciation:
    """One depreciation block from the prefill (lastFiledITR.scheduleDOA/DPM)."""

    asset_class: str = ""
    rate: str = ""
    wdv_first_day: int = 0
    additions_180_plus: int = 0
    additions_180_minus: int = 0
    depreciation: int = 0
    wdv_last_day: int = 0


@dataclass
class PrefillAMTCredit:
    """One AMT credit entry from the prefill (lastFiledITR.scheduleAMTC)."""

    assessment_year: str = ""
    gross: int = 0
    amt_credit_setoff_earlier_ay: int = 0
    amt_credit_forwarded: int = 0


@dataclass
class PrefillESOPDeferredTax:
    """ESOP deferred-tax entry from the prefill (ScheduleESOP)."""

    assessment_year: str = ""
    tax_deferred_bf_earlier_ay: int = 0


@dataclass
class PrefillAuditInfo:
    """Audit info from the prefill (lastFiledITR.AuditInfo)."""

    income_declared_us: str = ""
    liable_sec_44aa_flag: str = ""
    audit_report_details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PrefillForm10IF:
    """Form 10IF (new tax regime election) from the prefill."""

    new_tax_regime: str = ""
    ack_no: int = 0
    filed_form_10ifa: str = ""
    return_filing_115bae: str = ""


@dataclass
class PrefillFilingStatusFlags:
    """Additional filing-status flags from lastFiledITR.filingStatus."""

    residential_status: str = ""
    fii_fpi_flag: str = ""
    opting_taxation_115bae_no: str = ""
    opting_taxation_115bae_yes: str = ""
    return_filing_115bae_24_25: str = ""


@dataclass
class PrefillLastFiledITRFlags:
    """Misc flags from lastFiledITR for ITR-2/3/4/5/6/7 forms."""

    inc_frm_bus_or_prof: str = ""
    benefit_us_115h_flg: str = ""
    foreign_exchange_flag: str = ""
    comp_director_prv_yr_flg: str = ""
    partner_in_firm_flg: str = ""
    held_unlisted_eq_shr_pr_yr_flg: str = ""
    asset_out_india_flag: str = ""
    total_num_of_months: int = 0


@dataclass
class PrefillOrgFirmInfo:
    """Org/firm info from personalInfo.orgFirmInfo."""

    assessee_name: str = ""
    date_of_formation: str = ""
    status_or_company_type: str = ""


@dataclass
class PrefillFilingStatusExt:
    """Extended filing-status details from the top-level filingStatus.

    Captures the 7th-proviso clause details, Form 10IF ack, and
    original-return filing date.
    """

    seventh_proviso_139: str = ""
    clause_iv_7_provisio_139i: str = ""
    clause_iv_7_provisio_139i_dtls: list[dict[str, Any]] = field(default_factory=list)
    opting_new_tax_regime_form10if: str = ""
    receipt_no: str = ""
    return_file_sec: int = 0
    orig_ret_filed_date: str = ""


@dataclass
class PrefillExtraction:
    """Complete form-agnostic extraction from the ITD Prefill JSON.

    Every field is populated on a best-effort basis — if the prefill
    JSON doesn't contain a particular section, the corresponding field
    remains at its default (empty/zero).  The frontend mappers pick
    what they need for the target ITR form.
    """

    personal_info: PrefillPersonalInfo = field(default_factory=PrefillPersonalInfo)
    filing_status: PrefillFilingStatus = field(default_factory=PrefillFilingStatus)
    filing_status_ext: PrefillFilingStatusExt = field(default_factory=PrefillFilingStatusExt)
    employer_entries: list[PrefillEmployerEntry] = field(default_factory=list)
    salary_insights: PrefillSalaryInsights = field(default_factory=PrefillSalaryInsights)
    house_property: list[PrefillHouseProperty] = field(default_factory=list)
    other_sources: PrefillOtherSourcesIncome = field(default_factory=PrefillOtherSourcesIncome)
    bank_accounts: list[PrefillBankAccount] = field(default_factory=list)
    tds_salary_entries: list[PrefillTDSEntry] = field(default_factory=list)
    tds_other_entries: list[PrefillTDSEntry] = field(default_factory=list)
    tcs_entries: list[PrefillTCSEntry] = field(default_factory=list)
    tax_payments: list[dict[str, Any]] = field(default_factory=list)
    deductions: PrefillDeductions = field(default_factory=PrefillDeductions)
    deductions_80d: Prefill80DDetails = field(default_factory=Prefill80DDetails)
    carry_forward_losses: list[PrefillCarryForwardLoss] = field(default_factory=list)
    verification: PrefillVerification = field(default_factory=PrefillVerification)
    capital_gains_property: list[dict[str, Any]] = field(default_factory=list)
    other_income_cpc: list[dict[str, Any]] = field(default_factory=list)
    presumptive_income: PrefillPresumptiveIncome = field(default_factory=PrefillPresumptiveIncome)
    depreciation: list[PrefillDepreciation] = field(default_factory=list)
    amt_credits: list[PrefillAMTCredit] = field(default_factory=list)
    esop_deferred_tax: list[PrefillESOPDeferredTax] = field(default_factory=list)
    audit_info: PrefillAuditInfo = field(default_factory=PrefillAuditInfo)
    form_10if: PrefillForm10IF = field(default_factory=PrefillForm10IF)
    last_filed_itr_flags: PrefillLastFiledITRFlags = field(default_factory=PrefillLastFiledITRFlags)
    last_filed_itr_filing_status: PrefillFilingStatusFlags = field(default_factory=PrefillFilingStatusFlags)
    org_firm_info: PrefillOrgFirmInfo = field(default_factory=PrefillOrgFirmInfo)
    form_3cd: dict[str, Any] = field(default_factory=dict)
    schedule_5a_2014: dict[str, Any] = field(default_factory=dict)
    schedule_spi: list[dict[str, Any]] = field(default_factory=list)
    schedule_ud: list[dict[str, Any]] = field(default_factory=list)
    manufacturing_account: dict[str, Any] = field(default_factory=dict)
    schedule_80g: list[dict[str, Any]] = field(default_factory=list)
    schedule_ei: dict[str, Any] = field(default_factory=dict)
    schedule_al: dict[str, Any] = field(default_factory=dict)
    assessment_year: str = ""
    pan: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Section extractors
# ──────────────────────────────────────────────────────────────────────────────

def _extract_name(name_obj: Any) -> PrefillName:
    """Extract the three-part name from the ``assesseeName`` object."""
    if not isinstance(name_obj, Mapping):
        return PrefillName()
    return PrefillName(
        first_name=_to_str(name_obj.get("firstName") or name_obj.get("FirstName")),
        middle_name=_to_str(name_obj.get("middleName") or name_obj.get("MiddleName")),
        surname_or_org_name=_to_str(
            name_obj.get("surNameOrOrgName")
            or name_obj.get("SurNameOrOrgName")
            or name_obj.get("surnameOrOrgName")
            or name_obj.get("surname")
        ),
    )


def _extract_address(address_obj: Any) -> PrefillAddress:
    """Extract the address + contact fields from the ``address`` object."""
    if not isinstance(address_obj, Mapping):
        return PrefillAddress()
    phone = address_obj.get("phone")
    if not isinstance(phone, Mapping):
        phone = {}
    return PrefillAddress(
        residence_no=_to_str(address_obj.get("residenceNo")),
        residence_name=_to_str(address_obj.get("residenceName")),
        road_or_street=_to_str(address_obj.get("roadOrStreet")),
        locality_or_area=_to_str(address_obj.get("localityOrArea")),
        city_or_town_or_district=_to_str(address_obj.get("cityOrTownOrDistrict")),
        state_code=_to_str(address_obj.get("stateCode")),
        country_code=_to_str(address_obj.get("countryCode")),
        pin_code=_to_str(address_obj.get("pinCode")),
        zip_code=_to_str(address_obj.get("zipCode")),
        country_code_mobile=_to_int(address_obj.get("countryCodeMobile")),
        mobile_no=_to_int(address_obj.get("mobileNo")),
        country_code_mobile_sec=_to_int(address_obj.get("countryCodeMobileNoSec")),
        mobile_no_sec=_to_int(address_obj.get("mobileNoSec")),
        email_address=_to_str(address_obj.get("emailAddress")),
        email_address_secondary=_to_str(address_obj.get("emailAddressSecondary")),
        phone_std_code=_to_int(phone.get("stDcode")),
        phone_no=_to_int(phone.get("phoneNo")),
    )


def _extract_personal_info(root: dict[str, Any]) -> PrefillPersonalInfo:
    """Extract the personal info block from the prefill root."""
    pi = root.get("personalInfo")
    if not isinstance(pi, Mapping):
        return PrefillPersonalInfo()
    name = _extract_name(pi.get("assesseeName") or pi.get("AssesseeName"))
    address = _extract_address(pi.get("address"))
    pan = _to_str(pi.get("pan") or pi.get("PAN") or pi.get("assesseVerPan"))
    return PrefillPersonalInfo(
        pan=pan,
        aadhaar_card_no=_decode_aadhaar(pi.get("aadhaarCardNo") or pi.get("aadharCardNo")),
        name=name,
        assessee_ver_name=_to_str(pi.get("assesseeVerName") or pi.get("assesseVerName")),
        father_name=_to_str(pi.get("fatherName")),
        dob=_to_date(pi.get("dob") or pi.get("DateOFFormOrIncorp")),
        status=_to_str(pi.get("status")),
        employer_category=_to_str(pi.get("employerCategory")),
        address=address,
        residential_status=_to_str(
            pi.get("filingStatus", {}).get("residentialStatus")
            if isinstance(pi.get("filingStatus"), Mapping)
            else ""
        ),
        portugese_cc5a=_to_str(pi.get("portugeseCC5A")),
    )


def _extract_filing_status(root: dict[str, Any]) -> PrefillFilingStatus:
    """Extract the filing status block from the prefill root.

    The real ITD prefill has ``filingStatus`` at the top level with
    ``returnFileSec``, ``residentialStatus``, ``SeventhProvisio139``,
    ``OptingNewTaxRegimeForm10IF``, ``receiptNo``, ``origRetFiledDate``,
    and ``clauseiv7provisio139iDtls``.
    """
    fs = root.get("filingStatus")
    if not isinstance(fs, Mapping):
        return PrefillFilingStatus()
    return PrefillFilingStatus(
        return_file_sec=_to_int(fs.get("returnFileSec")),
        residential_status=_to_str(fs.get("residentialStatus") or fs.get("ResidentialStatus")),
        section_115ba=_to_str(fs.get("section115BA")),
        assessee_rep_flg=_to_str(fs.get("asseseeRepFlg")),
        business_trust_flag=_to_str(fs.get("businessTrustFlag")),
        fii_fpi_flag=_to_str(fs.get("fiiFpiFlag") or fs.get("FiiFpiFlag")),
        foreign_exchange_flag=_to_str(fs.get("foreignExchangeFlag") or fs.get("ForeignExchangeFlag")),
        orig_ret_filed_date=_to_date(fs.get("origRetFiledDate")),
        receipt_no=_to_str(fs.get("receiptNo")),
        notice_date_under_sec=_to_date(fs.get("noticeDateUnderSec")),
        unique_no=_to_str(fs.get("uniqueNo")),
        seventh_proviso_139=_to_str(fs.get("SeventhProvisio139")),
        opting_new_tax_regime_form10if=_to_str(fs.get("OptingNewTaxRegimeForm10IF")),
    )


def _extract_employers(root: dict[str, Any]) -> list[PrefillEmployerEntry]:
    """Extract the employer entries from the prefill.

    The real ITD prefill places employment nature under
    ``lastFiledITR.natOfEmployment`` (a list of strings like "OTH").
    The ``salaries`` section (with detailed salary break-up) is present
    when the employer has filed Form 24Q.
    """
    employers: list[PrefillEmployerEntry] = []

    # Source 1: salaries.salary[] (detailed break-up, may be null)
    salaries = root.get("salaries")
    if isinstance(salaries, Mapping):
        salary_list = salaries.get("salary")
        if isinstance(salary_list, list):
            for item in salary_list:
                if not isinstance(item, Mapping):
                    continue
                addr = item.get("addressDetail") or {}
                if not isinstance(addr, Mapping):
                    addr = {}
                salarys = item.get("salarys") or {}
                if not isinstance(salarys, Mapping):
                    salarys = {}
                employers.append(PrefillEmployerEntry(
                    employer_name=_to_str(item.get("nameOfEmployer")),
                    tan=_to_str(item.get("tanOfEmployer")),
                    gross_salary=_to_int(salarys.get("grossSalary")),
                    salary=_to_int(salarys.get("salary")),
                    value_of_perquisites=_to_int(salarys.get("valueOfPerquisites")),
                    profits_in_lieu_of_salary=_to_int(salarys.get("profitsinLieuOfSalary")),
                    nature_of_employment=_to_str(item.get("natOfEmployment")),
                    employer_address=_to_str(addr.get("addDetail")),
                    employer_city=_to_str(addr.get("cityOrTownOrDistrict")),
                    employer_state_code=_to_str(addr.get("stateCode")),
                    employer_pin_code=_to_str(addr.get("pinCode")),
                    employer_zip_code=_to_str(addr.get("zipCode")),
                ))

    # Source 2: lastFiledITR.natOfEmployment[] (list of employment-nature
    # strings).  When ``salaries`` is null but natOfEmployment has
    # entries, we create stub employer entries from TDS data.
    if not employers:
        lfi = root.get("lastFiledITR")
        if isinstance(lfi, Mapping):
            nat_list = lfi.get("natOfEmployment")
            if isinstance(nat_list, list):
                # We don't have employer names from this source alone;
                # we'll enrich them from the TDS-on-salary section below.
                # For now, create stub entries with the nature code.
                for nat in nat_list:
                    if isinstance(nat, str):
                        employers.append(PrefillEmployerEntry(
                            nature_of_employment=nat,
                        ))

    # Source 3: form24q may carry salary-side TDS (Form 24Q is the
    # employer's TDS return).  We don't extract employer entries from
    # form24q here; the TDS-on-salary extractor handles it.

    # Source 4: tdsOnSalaries.tdsOnSalary[].  When the detailed salary
    # breakdown (``salaries.salary[]``) is absent, the salary TDS rows
    # still carry the employer's name + TAN + income charged + total TDS.
    # Derive employer stubs from them so the frontend can populate the
    # salary schedule even when only Form 24Q data is present.
    if not employers:
        ts = root.get("tdsOnSalaries")
        if isinstance(ts, Mapping):
            tds_list = ts.get("tdsOnSalary")
            if isinstance(tds_list, list):
                for item in tds_list:
                    if not isinstance(item, Mapping):
                        continue
                    deductor = item.get("employerOrDeductorOrCollectDetl") or {}
                    if not isinstance(deductor, Mapping):
                        deductor = {}
                    name = _to_str(deductor.get("employerOrDeductorOrCollecterName"))
                    tan = _to_str(deductor.get("tan"))
                    if not name and not tan:
                        continue
                    employers.append(PrefillEmployerEntry(
                        employer_name=name,
                        tan=tan,
                        gross_salary=_to_int(item.get("incChrgSal")),
                        salary=_to_int(item.get("incChrgSal")),
                        tds_deducted_from_salary=_to_int(item.get("totalTDSSal")),
                    ))

    # Note: We do NOT enrich employer entries from TDS-other data.
    # TDS-other entries (section 94A, 194A, 194, etc.) are income from
    # Other Sources, NOT salary.  Treating them as employer entries
    # misclassifies other-sources income as salary income.  The frontend
    # mapper (mapPrefillToFormData) builds bankInterestEntries and
    # dividendEntries from TDS-other entries based on their section code.

    # Deduplicate employer entries by TAN (keep first occurrence).
    seen_tans: set[str] = set()
    deduped_employers: list[PrefillEmployerEntry] = []
    for emp in employers:
        key = emp.tan.upper() if emp.tan else emp.employer_name.lower()
        if key and key in seen_tans:
            continue
        if key:
            seen_tans.add(key)
        deduped_employers.append(emp)
    return deduped_employers


def _extract_salary_insights(root: dict[str, Any]) -> PrefillSalaryInsights:
    """Extract cumulative salary from the ``insights.cumulativeSalary`` block."""
    insights = root.get("insights")
    if not isinstance(insights, Mapping):
        return PrefillSalaryInsights()
    cs = insights.get("cumulativeSalary")
    if not isinstance(cs, Mapping):
        return PrefillSalaryInsights()
    return PrefillSalaryInsights(
        salary=_to_int(cs.get("salary")),
        perquisites_value=_to_int(cs.get("perquisitesValue")),
        profits_in_salary=_to_int(cs.get("profitsInSalary")),
        salary_update_timestamp=_to_str(cs.get("salaryUpdateTimestamp")),
    )


def _extract_house_property(root: dict[str, Any]) -> list[PrefillHouseProperty]:
    """Extract house property entries from the prefill.

    Checks ``lastFiledITR.scheduleHP.propertyDetails[]`` first (the real
    ITD structure), then falls back to ``insights.scheduleHP``.
    """
    hp_list: list[PrefillHouseProperty] = []

    # Source 1: lastFiledITR.scheduleHP.propertyDetails[]
    lfi = root.get("lastFiledITR")
    if isinstance(lfi, Mapping):
        hp = lfi.get("scheduleHP")
        if isinstance(hp, Mapping):
            details = hp.get("propertyDetails")
            if isinstance(details, list):
                for item in details:
                    if not isinstance(item, Mapping):
                        continue
                    addr = item.get("addressDetailWithZipCode") or {}
                    if not isinstance(addr, Mapping):
                        addr = {}
                    hp_list.append(PrefillHouseProperty(
                        address=_to_str(addr.get("addrDetail")),
                        city=_to_str(addr.get("cityOrTownOrDistrict")),
                        state_code=_to_str(addr.get("stateCode")),
                        pin_code=_to_int(addr.get("pinCode")),
                        country_code=_to_str(addr.get("countryCode")),
                        zip_code=_to_str(addr.get("zipCode")),
                        if_let_out=_to_str(item.get("ifLetOut")),
                        type_of_hp=_to_str(item.get("typeOfHP")),
                        gross_rent=_to_int(item.get("grossRent")),
                        co_owners=list(item.get("coOwners") or []),
                        tenant_details=list(item.get("tenantDetails") or []),
                    ))

    # Source 2: insights.scheduleHP.propertyDetails[]
    if not hp_list:
        insights = root.get("insights")
        if isinstance(insights, Mapping):
            hp = insights.get("scheduleHP")
            if isinstance(hp, Mapping):
                details = hp.get("propertyDetails")
                if isinstance(details, list):
                    for item in details:
                        if not isinstance(item, Mapping):
                            continue
                        addr = item.get("addressDetailWithZipCode") or {}
                        if not isinstance(addr, Mapping):
                            addr = {}
                        hp_list.append(PrefillHouseProperty(
                            address=_to_str(addr.get("addrDetail")),
                            city=_to_str(addr.get("cityOrTownOrDistrict")),
                            state_code=_to_str(addr.get("stateCode")),
                            pin_code=_to_int(addr.get("pinCode")),
                            country_code=_to_str(addr.get("countryCode")),
                            zip_code=_to_str(addr.get("zipCode")),
                            if_let_out=_to_str(item.get("ifLetOut")),
                            type_of_hp=_to_str(item.get("typeOfHP")),
                            gross_rent=_to_int(item.get("grossRent")),
                        ))
    return hp_list


def _extract_other_sources(root: dict[str, Any]) -> PrefillOtherSourcesIncome:
    """Extract other sources income from the prefill.

    The real ITD prefill places this under ``insights.scheduleOS`` and
    also under ``form26as.scheduleOS``.  Interest figures come from
    ``insights.intrstFrmSavingBank``, ``insights.intrstFrmTermDeposit``,
    and ``form24q.intrstFrmSavingBank``.

    ``insights.incomeDeductionsOthersInc[]`` carries a list of
    {othSrcNatureDesc, othSrcOthAmount} items (e.g. IFD, DIV, SAV).
    """
    insights = root.get("insights")
    if not isinstance(insights, Mapping):
        insights = {}

    # scheduleOS — may be under insights or form26as
    os_obj = insights.get("scheduleOS")
    if not isinstance(os_obj, Mapping):
        form26as = root.get("form26as")
        if isinstance(form26as, Mapping):
            os_obj = form26as.get("scheduleOS")
    if not isinstance(os_obj, Mapping):
        os_obj = {}
    inc_oth = os_obj.get("incOthThanOwnRaceHorse") or {}
    if not isinstance(inc_oth, Mapping):
        inc_oth = {}

    # incomeDeductionsOthersInc[] — list of {othSrcNatureDesc, othSrcOthAmount}
    other_details: list[dict[str, Any]] = []
    idi_list = insights.get("incomeDeductionsOthersInc")
    if not isinstance(idi_list, list):
        form26as = root.get("form26as")
        if isinstance(form26as, Mapping):
            idi_list = form26as.get("incomeDeductionsOthersInc")
    if isinstance(idi_list, list):
        for d in idi_list:
            if isinstance(d, Mapping):
                other_details.append({
                    "nature": _to_str(d.get("othSrcNatureDesc")),
                    "amount": _to_int(d.get("othSrcOthAmount")),
                })

    # Interest sources: insights or form24q
    form24q = root.get("form24q")
    if not isinstance(form24q, Mapping):
        form24q = {}
    interest_sb = (
        _to_int(insights.get("intrstFrmSavingBank"))
        or _to_int(form24q.get("intrstFrmSavingBank"))
    )
    interest_fd = _to_int(insights.get("intrstFrmTermDeposit"))
    # form26as also carries intrstFrmTermDeposit
    if not interest_fd:
        form26as = root.get("form26as")
        if isinstance(form26as, Mapping):
            interest_fd = _to_int(form26as.get("intrstFrmTermDeposit"))

    return PrefillOtherSourcesIncome(
        dividend_gross=_to_int(inc_oth.get("dividendGross")),
        dividend_oth_than_22e=_to_int(inc_oth.get("DividendOthThan22e")),
        interest_from_savings_bank=interest_sb,
        interest_from_term_deposit=interest_fd,
        interest_from_others=_to_int(inc_oth.get("intrstFrmOthers")),
        rent_from_mach_plant_bldgs=_to_int(inc_oth.get("rentFromMachPlantBldgs")),
        lottery_puzzle_income=_to_int(inc_oth.get("ltryPzzlChrgblUs115BB")),
        other_income_details=other_details,
    )


def _extract_bank_accounts(root: dict[str, Any]) -> list[PrefillBankAccount]:
    """Extract bank account entries from the prefill.

    The real ITD prefill places ``bankAccountDtls`` at the **top level**
    (not inside lastFiledITR).  It's a list where each item has an
    ``addtnlBankDetails`` array with the actual account rows.

    The ITD sometimes emits the same account twice — once with the real
    account number and once with leading zeros (e.g. ``31228369139`` and
    ``00000031228369139``).  We deduplicate by stripping leading zeros
    from the account number and keeping the first occurrence.

    Only one account may be marked for refund.  If multiple accounts have
    ``useForRefund="true"``, only the first one wins; the rest are reset
    to ``"false"``.
    """
    raw_accounts: list[PrefillBankAccount] = []

    def _collect_from(bank_dtls: Any) -> None:
        if not isinstance(bank_dtls, list):
            return
        for bd in bank_dtls:
            if not isinstance(bd, Mapping):
                continue
            addtnl = bd.get("addtnlBankDetails")
            if not isinstance(addtnl, list):
                continue
            for acct in addtnl:
                if not isinstance(acct, Mapping):
                    continue
                raw_accounts.append(PrefillBankAccount(
                    bank_account_no=_to_str(acct.get("bankAccountNo")),
                    bank_name=_to_str(acct.get("bankName")),
                    ifsc_code=_to_str(acct.get("ifsccode") or acct.get("ifscCode")),
                    account_type=_to_str(acct.get("AccountType") or acct.get("accountType")),
                    use_for_refund=_to_str(acct.get("useForRefund")).lower(),
                ))

    # Source 1: top-level bankAccountDtls[]
    _collect_from(root.get("bankAccountDtls"))

    # Source 2: lastFiledITR.bankAccountDtls[] (fallback if top-level empty)
    if not raw_accounts:
        lfi = root.get("lastFiledITR")
        if isinstance(lfi, Mapping):
            _collect_from(lfi.get("bankAccountDtls"))

    if not raw_accounts:
        return []

    # Deduplicate: strip leading zeros from account number for comparison.
    # Keep the first occurrence of each unique account.
    seen: set[str] = set()
    deduped: list[PrefillBankAccount] = []
    for acct in raw_accounts:
        # Normalized key: lowercase bank name + IFSC + zero-stripped acct no
        normalized_no = acct.bank_account_no.lstrip("0").upper()
        key = f"{acct.bank_name.lower()}|{acct.ifsc_code.upper()}|{normalized_no}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(acct)

    # Select a single refund account: if multiple accounts have
    # useForRefund="true", only the first one keeps it; the rest are
    # reset to "false".  If none has it, mark the first as refund.
    refund_assigned = False
    for acct in deduped:
        if acct.use_for_refund == "true":
            if refund_assigned:
                acct.use_for_refund = "false"
            else:
                refund_assigned = True
    if not refund_assigned and deduped:
        deduped[0].use_for_refund = "true"

    return deduped


def _extract_tds_salary(root: dict[str, Any]) -> list[PrefillTDSEntry]:
    """Extract TDS-on-salary entries from the prefill.

    The real ITD prefill places these under ``tdsOnSalaries.tdsOnSalary[]``
    when present.  In many prefill payloads this section is null — the
    salary TDS is then available only via Form 26AS reconciliation.
    """
    entries: list[PrefillTDSEntry] = []
    ts = root.get("tdsOnSalaries")
    if not isinstance(ts, Mapping):
        return entries
    tds_list = ts.get("tdsOnSalary")
    if not isinstance(tds_list, list):
        return entries
    for item in tds_list:
        if not isinstance(item, Mapping):
            continue
        deductor = item.get("employerOrDeductorOrCollectDetl") or {}
        if not isinstance(deductor, Mapping):
            deductor = {}
        entries.append(PrefillTDSEntry(
            deductor_name=_to_str(deductor.get("employerOrDeductorOrCollecterName")),
            tan=_to_str(deductor.get("tan")),
            section="192",
            income_amount=_to_int(item.get("incChrgSal")),
            tds_deducted=_to_int(item.get("totalTDSSal")),
            tds_claimed=_to_int(item.get("totalTDSSal")),
        ))
    return entries


def _extract_tds_other(root: dict[str, Any]) -> list[PrefillTDSEntry]:
    """Extract TDS-other-than-salary entries from the prefill.

    The real ITD prefill places these under
    ``form26as.tdsOnOthThanSals.tdSonOthThanSal[]`` (not a top-level
    ``tdsOnOthThanSals``).  Each item has ``sectionCode``,
    ``grossAmount``, ``headOfIncome``, ``employerOrDeductorOrCollectDetl``
    (with ``tan`` and ``employerOrDeductorOrCollecterName``), and
    ``taxDeductCreditDtls`` (with ``taxDeductedOwnHands`` and
    ``taxClaimedOwnHands``).
    """
    entries: list[PrefillTDSEntry] = []

    # Source 1: form26as.tdsOnOthThanSals.tdSonOthThanSal[]
    form26as = root.get("form26as")
    if isinstance(form26as, Mapping):
        tos = form26as.get("tdsOnOthThanSals")
        if isinstance(tos, Mapping):
            tds_list = tos.get("tdSonOthThanSal")
            if isinstance(tds_list, list):
                for item in tds_list:
                    if not isinstance(item, Mapping):
                        continue
                    deductor = item.get("employerOrDeductorOrCollectDetl") or {}
                    if not isinstance(deductor, Mapping):
                        deductor = {}
                    credit = item.get("taxDeductCreditDtls") or {}
                    if not isinstance(credit, Mapping):
                        credit = {}
                    entries.append(PrefillTDSEntry(
                        deductor_name=_to_str(deductor.get("employerOrDeductorOrCollecterName")),
                        tan=_to_str(deductor.get("tan") or item.get("tanOfDeductor")),
                        section=_to_str(item.get("sectionCode")),
                        income_amount=_to_int(item.get("grossAmount") or item.get("amtForTaxDeduct")),
                        tds_deducted=_to_int(credit.get("taxDeductedOwnHands") or item.get("tdsDeducted")),
                        tds_claimed=_to_int(credit.get("taxClaimedOwnHands") or item.get("tdsClaimed")),
                        gross_amount=_to_int(item.get("grossAmount")),
                        head_of_income=_to_str(item.get("headOfIncome")),
                        deducted_year=_to_str(item.get("deductedYr")),
                        brought_fwd_tds=_to_int(item.get("broughtFwdTDSAmt")),
                    ))

    # Source 2: top-level tdsOnOthThanSals.tdSonOthThanSal[] (fallback)
    if not entries:
        tos = root.get("tdsOnOthThanSals")
        if isinstance(tos, Mapping):
            tds_list = tos.get("tdSonOthThanSal")
            if isinstance(tds_list, list):
                for item in tds_list:
                    if not isinstance(item, Mapping):
                        continue
                    deductor = item.get("employerOrDeductorOrCollectDetl") or {}
                    if not isinstance(deductor, Mapping):
                        deductor = {}
                    credit = item.get("taxDeductCreditDtls") or {}
                    if not isinstance(credit, Mapping):
                        credit = {}
                    entries.append(PrefillTDSEntry(
                        deductor_name=_to_str(deductor.get("employerOrDeductorOrCollecterName")),
                        tan=_to_str(deductor.get("tan") or item.get("tanOfDeductor")),
                        section=_to_str(item.get("sectionCode")),
                        income_amount=_to_int(item.get("grossAmount") or item.get("amtForTaxDeduct")),
                        tds_deducted=_to_int(credit.get("taxDeductedOwnHands") or item.get("tdsDeducted")),
                        tds_claimed=_to_int(credit.get("taxClaimedOwnHands") or item.get("tdsClaimed")),
                        gross_amount=_to_int(item.get("grossAmount")),
                        head_of_income=_to_str(item.get("headOfIncome")),
                        deducted_year=_to_str(item.get("deductedYr")),
                        brought_fwd_tds=_to_int(item.get("broughtFwdTDSAmt")),
                    ))
    return entries


def _extract_deductions(root: dict[str, Any]) -> PrefillDeductions:
    """Extract Chapter VI-A deductions from the prefill.

    The real ITD prefill places these under two locations:
      1. ``insights.UsrDeductUndChapVIAType`` (capital U) — e.g.
         ``Section80TTB``
      2. ``form24q.usrDeductUndChapVIAType`` — e.g. ``section80TTA``

    We merge both, normalizing the key casing to lowercase
    ``section_80*``.
    """
    merged: dict[str, int] = {}

    def _merge_deductions(obj: Any) -> None:
        """Merge deduction keys from a mapping into the merged dict."""
        if not isinstance(obj, Mapping):
            return
        for key, value in obj.items():
            key_lower = key.lower()
            # Only accept keys that look like section 80* deductions.
            if not key_lower.startswith("section80"):
                continue
            # Normalize: section80c → section_80c, section80ttb → section_80ttb
            normalized = "section_" + key_lower[len("section"):]
            amount = _to_int(value)
            if amount > 0:
                merged[normalized] = merged.get(normalized, 0) + amount

    # Source 1: insights.UsrDeductUndChapVIAType
    insights = root.get("insights")
    if isinstance(insights, Mapping):
        _merge_deductions(insights.get("UsrDeductUndChapVIAType"))
        _merge_deductions(insights.get("usrDeductUndChapVIAType"))

    # Source 2: form24q.usrDeductUndChapVIAType
    form24q = root.get("form24q")
    if isinstance(form24q, Mapping):
        _merge_deductions(form24q.get("usrDeductUndChapVIAType"))
        _merge_deductions(form24q.get("UsrDeductUndChapVIAType"))

    # Source 3: lastFiledITR.usrDeductUndChapVIAType (fallback)
    lfi = root.get("lastFiledITR")
    if isinstance(lfi, Mapping):
        _merge_deductions(lfi.get("usrDeductUndChapVIAType"))
        _merge_deductions(lfi.get("UsrDeductUndChapVIAType"))

    # Source 4: scheduleDeductions.usrDeductUndChapVIA (schema-documented fallback)
    sd = root.get("scheduleDeductions")
    if isinstance(sd, Mapping):
        _merge_deductions(sd.get("usrDeductUndChapVIA"))
        _merge_deductions(sd.get("deductUndChapVIA"))

    total = sum(merged.values())
    return PrefillDeductions(
        section_80c=merged.get("section_80c", 0),
        section_80ccc=merged.get("section_80ccc", 0),
        section_80ccd_employee_or_se=merged.get("section_80ccd_employee_or_se", 0),
        section_80ccd_1b=merged.get("section_80ccd_1b", 0) or merged.get("section_80ccd1b", 0),
        section_80ccd_employer=merged.get("section_80ccd_employer", 0),
        section_80d=merged.get("section_80d", 0),
        section_80dd=merged.get("section_80dd", 0),
        section_80ddb=merged.get("section_80ddb", 0),
        section_80e=merged.get("section_80e", 0),
        section_80ee=merged.get("section_80ee", 0),
        section_80eea=merged.get("section_80eea", 0),
        section_80eeb=merged.get("section_80eeb", 0),
        section_80g=merged.get("section_80g", 0),
        section_80gg=merged.get("section_80gg", 0),
        section_80gga=merged.get("section_80gga", 0),
        section_80ggc=merged.get("section_80ggc", 0),
        section_80u=merged.get("section_80u", 0),
        section_80tta=merged.get("section_80tta", 0),
        section_80ttb=merged.get("section_80ttb", 0),
        section_80cch=merged.get("section_80cch", 0),
        section_80qqb=merged.get("section_80qqb", 0),
        section_80rrb=merged.get("section_80rrb", 0),
        section_80la=merged.get("section_80la", 0),
        total_chap_via_deductions=total,
    )


def _extract_carry_forward_losses(root: dict[str, Any]) -> list[PrefillCarryForwardLoss]:
    """Extract carry-forward loss entries from ``scheduleCFL``."""
    losses: list[PrefillCarryForwardLoss] = []
    cfl = root.get("scheduleCFL")
    if not isinstance(cfl, Mapping):
        return losses
    # The real ITD prefill uses ``CarryFwdLossDetail`` (capital C).
    details = cfl.get("carryFwdLossDetail")
    if not isinstance(details, list):
        details = cfl.get("CarryFwdLossDetail")
    if not isinstance(details, list):
        return losses
    for item in details:
        if not isinstance(item, Mapping):
            continue
        losses.append(PrefillCarryForwardLoss(
            assessment_year=_to_str(item.get("assessmentYear")),
            brought_fwd_bus_loss=_to_int(item.get("broughtFrwrdBusLoss")),
            bus_loss_oth_than_spec_loss_cf=_to_int(item.get("busLossOthThanSpecLossCF")),
            hp_loss_cf=_to_int(item.get("hpLossCF")),
            loss_frm_insu_cf=_to_int(item.get("lossFrmInsuCF")),
            loss_frm_spec_bus_cf=_to_int(item.get("lossFrmSpecBusCF")),
            loss_frm_specified_bus_cf=_to_int(item.get("lossFrmSpecifiedBusCF")),
            ltcg_loss_cf=_to_int(item.get("ltcgLossCF")),
            oth_src_loss_race_horse_cf=_to_int(item.get("othSrcLossRaceHorseCF")),
            stcg_loss_cf=_to_int(item.get("stcgLossCF")),
            date_of_filing=_to_date(item.get("dateOfFiling")),
        ))
    return losses


def _extract_verification(root: dict[str, Any]) -> PrefillVerification:
    """Extract the verification block from the prefill."""
    v = root.get("verification")
    if not isinstance(v, Mapping):
        return PrefillVerification()
    decl = v.get("declaration") or {}
    if not isinstance(decl, Mapping):
        decl = {}
    return PrefillVerification(
        assessee_ver_name=_to_str(decl.get("assesseeVerName") or decl.get("assesseVerName")),
        assessee_ver_pan=_to_str(decl.get("assesseeVerPAN") or decl.get("assesseVerPAN")),
        father_name=_to_str(decl.get("fatherName")),
        capacity=_to_str(v.get("capacity") or v.get("repCapacity")),
        place=_to_str(v.get("place")),
    )


def _extract_capital_gains_property(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract capital-gains property transactions from the prefill.

    Lives under ``insights.capitalGains.propertyDetails[]``.
    """
    cg_list: list[dict[str, Any]] = []
    insights = root.get("insights")
    if not isinstance(insights, Mapping):
        return cg_list
    cg = insights.get("capitalGains")
    if not isinstance(cg, Mapping):
        return cg_list
    details = cg.get("propertyDetails")
    if not isinstance(details, list):
        return cg_list
    for item in details:
        if not isinstance(item, Mapping):
            continue
        addr = item.get("addressDetailWithZipCode") or {}
        if not isinstance(addr, Mapping):
            addr = {}
        buyers_list = item.get("buyers") or []
        if not isinstance(buyers_list, list):
            buyers_list = []
        buyers: list[dict[str, Any]] = []
        for b in buyers_list:
            if isinstance(b, Mapping):
                buyers.append({
                    "name": _to_str(b.get("nameBuyer")),
                    "pan": _to_str(b.get("panBuyer")),
                    "aadhaar": _to_str(b.get("aadhaarBuyer")),
                    "amount_paid": _to_int(b.get("amountPaidbyBuyer")),
                })
        cg_list.append({
            "address": _to_str(addr.get("addrDetail")),
            "city": _to_str(addr.get("cityOrTownOrDistrict")),
            "state_code": _to_str(addr.get("stateCode")),
            "pin_code": _to_int(addr.get("pinCode")),
            "country_code": _to_str(addr.get("countryCode")),
            "stamp_duty": _to_int(item.get("stampDuty")),
            "transaction_amount": _to_int(item.get("transactionAmount")),
            "buyers": buyers,
        })
    return cg_list


def _extract_other_income_cpc(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the ``incDeductionsOthIncCPC`` array (income tax refund interest)."""
    cpc_list: list[dict[str, Any]] = []
    cpc = root.get("incDeductionsOthIncCPC")
    if isinstance(cpc, list):
        for item in cpc:
            if isinstance(item, Mapping):
                cpc_list.append({
                    "assessment_year": _to_str(item.get("itrAy")),
                    "nature": _to_str(item.get("othSrcNatureDesc")),
                    "amount": _to_int(item.get("othSrcOthAmount")),
                })
    return cpc_list


def _extract_assessment_year(root: dict[str, Any]) -> str:
    """Extract the assessment year from the prefill metadata."""
    for key in ("assessmentYear", "assessment_year"):
        val = root.get(key)
        if val:
            return _to_str(val)
    meta = root.get("metadata") or root.get("metaData")
    if isinstance(meta, Mapping):
        for key in ("assessmentYear", "assessment_year"):
            val = meta.get(key)
            if val:
                return _to_str(val)
    cpc = root.get("incDeductionsOthIncCPC")
    if isinstance(cpc, list) and cpc:
        first = cpc[0]
        if isinstance(first, Mapping):
            ay = first.get("itrAy")
            if ay:
                return _to_str(ay)
    return ""


def _extract_tcs_entries(root: dict[str, Any]) -> list[PrefillTCSEntry]:
    """Extract TCS entries from the prefill.

    Lives under ``lastFiledITR.scheduleTCS.tcs[]``.
    """
    entries: list[PrefillTCSEntry] = []
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return entries
    tcs_obj = lfi.get("scheduleTCS")
    if not isinstance(tcs_obj, Mapping):
        return entries
    tcs_list = tcs_obj.get("tcs")
    if not isinstance(tcs_list, list):
        return entries
    for item in tcs_list:
        if not isinstance(item, Mapping):
            continue
        collector = item.get("employerOrDeductorOrCollectDetl") or {}
        if not isinstance(collector, Mapping):
            collector = {}
        credit = item.get("taxDeductCreditDtls") or {}
        if not isinstance(credit, Mapping):
            credit = {}
        entries.append(PrefillTCSEntry(
            collector_name=_to_str(collector.get("employerOrDeductorOrCollecterName")),
            tan=_to_str(collector.get("tan") or item.get("tanOfCollector")),
            pan=_to_str(collector.get("pan") or item.get("panOfCollector")),
            section=_to_str(item.get("sectionCode") or item.get("section")),
            gross_amount=_to_int(item.get("grossAmount") or item.get("amtForTaxCollected")),
            tcs_collected=_to_int(credit.get("taxCollectedOwnHands") or item.get("tcsCollected")),
            tcs_claimed=_to_int(credit.get("taxClaimedOwnHands") or item.get("tcsClaimed")),
            head_of_income=_to_str(item.get("headOfIncome")),
            collected_year=_to_str(item.get("collectedYr")),
        ))
    return entries


def _extract_presumptive_income(root: dict[str, Any]) -> PrefillPresumptiveIncome:
    """Extract presumptive income (44AD/44ADA) from the prefill.

    Lives under ``form26as.persumptiveInc44ADA`` and
    ``lastFiledITR.natOfBus44ADA``.
    """
    gross_receipt = 0
    form26as = root.get("form26as")
    if isinstance(form26as, Mapping):
        pi = form26as.get("persumptiveInc44ADA")
        if isinstance(pi, Mapping):
            gross_receipt = _to_int(pi.get("grsReceipt"))

    business_codes: list[dict[str, str]] = []
    lfi = root.get("lastFiledITR")
    if isinstance(lfi, Mapping):
        nat_list = lfi.get("natOfBus44ADA")
        if isinstance(nat_list, list):
            for item in nat_list:
                if isinstance(item, Mapping):
                    business_codes.append({
                        "code": _to_str(item.get("codeADA")),
                        "name": _to_str(item.get("nameOfBusiness")),
                    })

    return PrefillPresumptiveIncome(
        gross_receipt_44ada=gross_receipt,
        business_nature_codes=business_codes,
    )


def _extract_deductions_80d(root: dict[str, Any]) -> Prefill80DDetails:
    """Extract Section 80D details from the prefill.

    Lives under ``lastFiledITR.schedule80D.Sec80DSelfFamSrCtznHealth``.
    """
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return Prefill80DDetails()
    s80d = lfi.get("schedule80D")
    if not isinstance(s80d, Mapping):
        return Prefill80DDetails()
    self_fam = s80d.get("Sec80DSelfFamSrCtznHealth") or {}
    if not isinstance(self_fam, Mapping):
        self_fam = {}
    return Prefill80DDetails(
        self_family_senior_citizen_flag=_to_str(self_fam.get("SeniorCitizenFlag")),
        parent_senior_citizen_flag=_to_str(self_fam.get("ParentSeniorCitizenFlag")),
    )


def _extract_depreciation(root: dict[str, Any]) -> list[PrefillDepreciation]:
    """Extract depreciation entries from the prefill.

    Lives under ``lastFiledITR.scheduleDOA`` (depreciation on assets)
    and ``lastFiledITR.scheduleDPM`` (plant & machinery).
    """
    entries: list[PrefillDepreciation] = []
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return entries

    def _walk_depr_block(obj: Any, asset_class: str) -> None:
        """Recursively walk a depreciation block for WdvfirstDay entries."""
        if isinstance(obj, Mapping):
            for key, value in obj.items():
                if key.lower() == "depreciationdetail" or key.lower() == "depreciationdetail":
                    if isinstance(value, Mapping):
                        entries.append(PrefillDepreciation(
                            asset_class=asset_class,
                            rate="",
                            wdv_first_day=_to_int(value.get("WdvfirstDay") or value.get("wdvfirstDay")),
                        ))
                elif key.lower().startswith("rate"):
                    _walk_depr_block(value, asset_class)
                else:
                    _walk_depr_block(value, asset_class)
        elif isinstance(obj, list):
            for item in obj:
                _walk_depr_block(item, asset_class)

    doa = lfi.get("scheduleDOA")
    if isinstance(doa, Mapping):
        for asset_class, block in doa.items():
            _walk_depr_block(block, asset_class)

    dpm = lfi.get("scheduleDPM")
    if isinstance(dpm, Mapping):
        for asset_class, block in dpm.items():
            _walk_depr_block(block, asset_class)

    return entries


def _extract_amt_credits(root: dict[str, Any]) -> list[PrefillAMTCredit]:
    """Extract AMT credit entries from the prefill.

    Lives under ``lastFiledITR.scheduleAMTC.scheduleAMTCDtls[]``.
    """
    entries: list[PrefillAMTCredit] = []
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return entries
    amtc = lfi.get("scheduleAMTC")
    if not isinstance(amtc, Mapping):
        return entries
    dtls = amtc.get("scheduleAMTCDtls")
    if not isinstance(dtls, list):
        return entries
    for item in dtls:
        if isinstance(item, Mapping):
            entries.append(PrefillAMTCredit(
                assessment_year=_to_str(item.get("assYr") or item.get("assessmentYear")),
                gross=_to_int(item.get("gross")),
                amt_credit_setoff_earlier_ay=_to_int(item.get("amtCreditSetOfEy")),
                amt_credit_forwarded=_to_int(item.get("amtCreditFwd")),
            ))
    return entries


def _extract_esop_deferred_tax(root: dict[str, Any]) -> list[PrefillESOPDeferredTax]:
    """Extract ESOP deferred-tax entries from the prefill (ScheduleESOP)."""
    entries: list[PrefillESOPDeferredTax] = []
    esop = root.get("ScheduleESOP")
    if not isinstance(esop, Mapping):
        return entries
    for key, value in esop.items():
        if isinstance(value, Mapping):
            entries.append(PrefillESOPDeferredTax(
                assessment_year=_to_str(value.get("AssessmentYear")),
                tax_deferred_bf_earlier_ay=_to_int(value.get("TaxDeferredBFEarlierAY")),
            ))
    return entries


def _extract_audit_info(root: dict[str, Any]) -> PrefillAuditInfo:
    """Extract audit info from the prefill (lastFiledITR.AuditInfo)."""
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return PrefillAuditInfo()
    ai = lfi.get("AuditInfo")
    if not isinstance(ai, Mapping):
        return PrefillAuditInfo()
    reports = ai.get("AuditReportDetails")
    if not isinstance(reports, list):
        reports = []
    return PrefillAuditInfo(
        income_declared_us=_to_str(ai.get("IncDclrdUs")),
        liable_sec_44aa_flag=_to_str(ai.get("LiableSec44AAflg")),
        audit_report_details=[dict(r) for r in reports if isinstance(r, Mapping)],
    )


def _extract_form_10if(root: dict[str, Any]) -> PrefillForm10IF:
    """Extract Form 10IF (new tax regime election) from the prefill."""
    f10if = root.get("form10IF")
    if not isinstance(f10if, Mapping):
        return PrefillForm10IF()
    f10ifa = root.get("Form10IFA")
    ack_no = 0
    filed_10ifa = ""
    ret_filing_115bae = ""
    if isinstance(f10ifa, Mapping):
        ack_no = _to_int(f10ifa.get("Form10IFAAckNo"))
        filed_10ifa = _to_str(f10ifa.get("filedForm10IFA"))
        ret_filing_115bae = _to_str(f10ifa.get("ReturnFiling115BAE"))
    return PrefillForm10IF(
        new_tax_regime=_to_str(f10if.get("newTaxRegime")),
        ack_no=ack_no,
        filed_form_10ifa=filed_10ifa,
        return_filing_115bae=ret_filing_115bae,
    )


def _extract_last_filed_itr_flags(root: dict[str, Any]) -> PrefillLastFiledITRFlags:
    """Extract misc flags from lastFiledITR."""
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return PrefillLastFiledITRFlags()
    return PrefillLastFiledITRFlags(
        inc_frm_bus_or_prof=_to_str(lfi.get("incFrmBusOrProf")),
        benefit_us_115h_flg=_to_str(lfi.get("benefitUs115HFlg")),
        foreign_exchange_flag=_to_str(lfi.get("ForeignExchangeFlag")),
        comp_director_prv_yr_flg=_to_str(lfi.get("compDirectorPrvYrFlg")),
        partner_in_firm_flg=_to_str(lfi.get("PartnerInFirmFlg")),
        held_unlisted_eq_shr_pr_yr_flg=_to_str(lfi.get("heldUnlistedEqShrPrYrFlg")),
        asset_out_india_flag=_to_str(lfi.get("assetOutIndiaFlag")),
        total_num_of_months=_to_int(lfi.get("totalNumOfMonths")),
    )


def _extract_last_filed_itr_filing_status(root: dict[str, Any]) -> PrefillFilingStatusFlags:
    """Extract the filing-status sub-block inside lastFiledITR."""
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return PrefillFilingStatusFlags()
    fs = lfi.get("filingStatus")
    if not isinstance(fs, Mapping):
        return PrefillFilingStatusFlags()
    return PrefillFilingStatusFlags(
        residential_status=_to_str(fs.get("ResidentialStatus")),
        fii_fpi_flag=_to_str(fs.get("FiiFpiFlag")),
        opting_taxation_115bae_no=_to_str(fs.get("OptingTaxation115BAENo")),
        opting_taxation_115bae_yes=_to_str(fs.get("OptingTaxation115BAEYes")),
        return_filing_115bae_24_25=_to_str(fs.get("ReturnFiling115BAE_24_25")),
    )


def _extract_org_firm_info(root: dict[str, Any]) -> PrefillOrgFirmInfo:
    """Extract org/firm info from personalInfo.orgFirmInfo."""
    pi = root.get("personalInfo")
    if not isinstance(pi, Mapping):
        return PrefillOrgFirmInfo()
    ofi = pi.get("orgFirmInfo")
    if not isinstance(ofi, Mapping):
        return PrefillOrgFirmInfo()
    name_obj = ofi.get("AssesseeName") or {}
    if not isinstance(name_obj, Mapping):
        name_obj = {}
    return PrefillOrgFirmInfo(
        assessee_name=_to_str(name_obj.get("SurNameOrOrgName") or name_obj.get("surNameOrOrgName")),
        date_of_formation=_to_date(ofi.get("DateOFFormOrIncorp")),
        status_or_company_type=_to_str(ofi.get("StatusOrCompanyType")),
    )


def _extract_filing_status_ext(root: dict[str, Any]) -> PrefillFilingStatusExt:
    """Extract the extended filing-status details from the top-level filingStatus.

    Captures the 7th-proviso clause, Form 10IF ack, and original-return
    filing date.
    """
    fs = root.get("filingStatus")
    if not isinstance(fs, Mapping):
        return PrefillFilingStatusExt()
    clause_dtls = fs.get("clauseiv7provisio139iDtls")
    if not isinstance(clause_dtls, list):
        clause_dtls = []
    return PrefillFilingStatusExt(
        seventh_proviso_139=_to_str(fs.get("SeventhProvisio139")),
        clause_iv_7_provisio_139i=_to_str(fs.get("clauseiv7provisio139i")),
        clause_iv_7_provisio_139i_dtls=[dict(d) for d in clause_dtls if isinstance(d, Mapping)],
        opting_new_tax_regime_form10if=_to_str(fs.get("OptingNewTaxRegimeForm10IF")),
        receipt_no=_to_str(fs.get("receiptNo")),
        return_file_sec=_to_int(fs.get("returnFileSec")),
        orig_ret_filed_date=_to_date(fs.get("origRetFiledDate")),
    )


def _extract_form_3cd(root: dict[str, Any]) -> dict[str, Any]:
    """Extract Form 3CD (audit particulars) from the prefill."""
    f3cd = root.get("form3CD")
    if not isinstance(f3cd, Mapping):
        return {}
    return dict(f3cd)


def _extract_schedule_5a_2014(root: dict[str, Any]) -> dict[str, Any]:
    """Extract Schedule 5A (Portuguese Civil Code) from the prefill."""
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return {}
    s5a = lfi.get("schedule5A2014")
    if not isinstance(s5a, Mapping):
        return {}
    return dict(s5a)


def _extract_schedule_spi(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract Schedule SPI (specified person) from the prefill."""
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return []
    spi = lfi.get("scheduleSPI")
    if not isinstance(spi, Mapping):
        return []
    persons = spi.get("specifiedPerson")
    if not isinstance(persons, list):
        return []
    return [dict(p) for p in persons if isinstance(p, Mapping)]


def _extract_schedule_ud(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract Schedule UD (unabsorbed depreciation) from the prefill."""
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return []
    ud = lfi.get("scheduleUD")
    if not isinstance(ud, list):
        return []
    return [dict(u) for u in ud if isinstance(u, Mapping)]


def _extract_manufacturing_account(root: dict[str, Any]) -> dict[str, Any]:
    """Extract manufacturing account from the prefill."""
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return {}
    ma = lfi.get("manufacturingAccount")
    if not isinstance(ma, Mapping):
        return {}
    return dict(ma)


def _extract_schedule_80g(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract Schedule 80G (donations) from the prefill."""
    s80g = root.get("Schedule80G")
    if not isinstance(s80g, Mapping):
        return []
    # The structure may have a list of donation entries under various keys.
    result: list[dict[str, Any]] = []
    for key, value in s80g.items():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, Mapping):
                    result.append(dict(item))
        elif isinstance(value, Mapping):
            result.append({"sub_key": key, **dict(value)})
    return result


def _extract_schedule_ei(root: dict[str, Any]) -> dict[str, Any]:
    """Extract Schedule EI (exempt income) from the prefill."""
    ei = root.get("ScheduleEI")
    if not isinstance(ei, Mapping):
        return {}
    return dict(ei)


def _extract_schedule_al(root: dict[str, Any]) -> dict[str, Any]:
    """Extract Schedule AL (assets and liabilities) from the prefill."""
    al = root.get("scheduleAL")
    if not isinstance(al, Mapping):
        return {}
    return dict(al)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def parse_prefill_json(payload: Any, assessment_year: str = "") -> PrefillExtraction:
    """Parse the ITD Prefill JSON into a form-agnostic extraction.

    Args:
        payload: The parsed JSON (dict, or any wrapper shape).
        assessment_year: The expected assessment year (e.g. "2026-27").
            Used only for metadata; the parser does not reject mismatches.

    Returns:
        A ``PrefillExtraction`` with every available field populated.
    """
    root = _unwrap_prefill_root(payload)
    pi = _extract_personal_info(root)
    extraction = PrefillExtraction(
        personal_info=pi,
        filing_status=_extract_filing_status(root),
        filing_status_ext=_extract_filing_status_ext(root),
        employer_entries=_extract_employers(root),
        salary_insights=_extract_salary_insights(root),
        house_property=_extract_house_property(root),
        other_sources=_extract_other_sources(root),
        bank_accounts=_extract_bank_accounts(root),
        tds_salary_entries=_extract_tds_salary(root),
        tds_other_entries=_extract_tds_other(root),
        tcs_entries=_extract_tcs_entries(root),
        deductions=_extract_deductions(root),
        deductions_80d=_extract_deductions_80d(root),
        carry_forward_losses=_extract_carry_forward_losses(root),
        verification=_extract_verification(root),
        capital_gains_property=_extract_capital_gains_property(root),
        other_income_cpc=_extract_other_income_cpc(root),
        presumptive_income=_extract_presumptive_income(root),
        depreciation=_extract_depreciation(root),
        amt_credits=_extract_amt_credits(root),
        esop_deferred_tax=_extract_esop_deferred_tax(root),
        audit_info=_extract_audit_info(root),
        form_10if=_extract_form_10if(root),
        last_filed_itr_flags=_extract_last_filed_itr_flags(root),
        last_filed_itr_filing_status=_extract_last_filed_itr_filing_status(root),
        org_firm_info=_extract_org_firm_info(root),
        form_3cd=_extract_form_3cd(root),
        schedule_5a_2014=_extract_schedule_5a_2014(root),
        schedule_spi=_extract_schedule_spi(root),
        schedule_ud=_extract_schedule_ud(root),
        manufacturing_account=_extract_manufacturing_account(root),
        schedule_80g=_extract_schedule_80g(root),
        schedule_ei=_extract_schedule_ei(root),
        schedule_al=_extract_schedule_al(root),
        assessment_year=_extract_assessment_year(root) or assessment_year,
        pan=pi.pan,
        metadata={
            "source": "prefill",
            "assessment_year": _extract_assessment_year(root) or assessment_year,
        },
    )
    return extraction


def parse_prefill_file(path: str | Path, assessment_year: str = "") -> PrefillExtraction:
    """Parse an ITD Prefill JSON file from disk.

    Args:
        path: Path to the downloaded Prefill JSON file.
        assessment_year: The expected assessment year (e.g. "2026-27").

    Returns:
        A ``PrefillExtraction`` with every available field populated.
    """
    p = Path(path)
    try:
        payload = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Unable to read prefill JSON at {path}: {exc}") from exc
    return parse_prefill_json(payload, assessment_year=assessment_year)


def prefill_extraction_to_dict(extraction: PrefillExtraction) -> dict[str, Any]:
    """Convert a ``PrefillExtraction`` to a JSON-serializable dict.

    This is the shape that gets stored in ``automation_job.parsed_results``
    under the ``"prefill"`` key and sent to the frontend for mapping.
    """
    import dataclasses

    def _serialize(obj: Any) -> Any:
        if dataclasses.is_dataclass(obj):
            return {k: _serialize(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list):
            return [_serialize(item) for item in obj]
        return obj

    return _serialize(extraction)
