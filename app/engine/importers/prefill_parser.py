"""
Form-agnostic ITD Prefill JSON parser.

Extracts every field available in the official CBDT/ITD pre-filled JSON
(PreFillSchemaJSON V6.5) into a flat intermediate representation.  The
extractor does NOT know which ITR form the taxpayer will eventually file
— it pulls personal info, salary, house property, other sources income,
deductions, bank accounts, TDS/TCS schedules, tax payments, and
carry-forward losses regardless of form, and lets the form-specific
mappers in the frontend pick what they need.

The ITD prefill JSON may arrive in one of these wrapper shapes:
  1. ``{"personalInfo": {...}, "filingStatus": {...}, ...}``  (flat root)
  2. ``{"data": {"personalInfo": {...}, ...}}``  (wrapped in ``data``)
  3. ``{"prefillData": {"personalInfo": {...}, ...}}``  (wrapped in ``prefillData``)

The parser probes all three and extracts from whichever root contains
the ``personalInfo`` marker.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


# ──────────────────────────────────────────────────────────────────────────────
# Root-unwrapping helpers
# ──────────────────────────────────────────────────────────────────────────────

_PREFILL_ROOT_KEYS: tuple[str, ...] = (
    "personalInfo",
    "filingStatus",
    "salaries",
    "tdsOnSalaries",
    "tdsOnOthThanSals",
    "insights",
    "lastFiledITR",
    "verification",
    "scheduleHP",
    "scheduleOS",
    "incDeductionsOthIncCPC",
    "scheduleAL",
    "scheduleCFL",
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

    # Case 1: flat root — personalInfo is a direct key.
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
class PrefillTaxPayment:
    """One tax payment (advance tax / self-assessment) from the prefill."""

    bsr_code: str = ""
    challan_serial_no: str = ""
    deposit_date: str = ""
    tax_amount: int = 0
    surcharge: int = 0
    education_cess: int = 0
    total_amount: int = 0
    minor_head: str = ""


@dataclass
class PrefillDeductions:
    """Chapter VI-A deductions from the prefill."""

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
class PrefillExtraction:
    """Complete form-agnostic extraction from the ITD Prefill JSON.

    Every field is populated on a best-effort basis — if the prefill
    JSON doesn't contain a particular section, the corresponding field
    remains at its default (empty/zero).  The frontend mappers pick
    what they need for the target ITR form.
    """

    personal_info: PrefillPersonalInfo = field(default_factory=PrefillPersonalInfo)
    filing_status: PrefillFilingStatus = field(default_factory=PrefillFilingStatus)
    employer_entries: list[PrefillEmployerEntry] = field(default_factory=list)
    salary_insights: PrefillSalaryInsights = field(default_factory=PrefillSalaryInsights)
    house_property: list[PrefillHouseProperty] = field(default_factory=list)
    other_sources: PrefillOtherSourcesIncome = field(default_factory=PrefillOtherSourcesIncome)
    bank_accounts: list[PrefillBankAccount] = field(default_factory=list)
    tds_salary_entries: list[PrefillTDSEntry] = field(default_factory=list)
    tds_other_entries: list[PrefillTDSEntry] = field(default_factory=list)
    tax_payments: list[PrefillTaxPayment] = field(default_factory=list)
    deductions: PrefillDeductions = field(default_factory=PrefillDeductions)
    carry_forward_losses: list[PrefillCarryForwardLoss] = field(default_factory=list)
    verification: PrefillVerification = field(default_factory=PrefillVerification)
    capital_gains_property: list[dict[str, Any]] = field(default_factory=list)
    other_income_cpc: list[dict[str, Any]] = field(default_factory=list)
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
        first_name=_to_str(name_obj.get("firstName") or name_obj.get("firstname")),
        middle_name=_to_str(name_obj.get("middleName") or name_obj.get("middlename")),
        surname_or_org_name=_to_str(
            name_obj.get("surNameOrOrgName")
            or name_obj.get("surnameOrOrgName")
            or name_obj.get("surname")
        ),
    )


def _extract_address(address_obj: Any) -> PrefillAddress:
    """Extract the address + contact fields from the ``address`` object."""
    if not isinstance(address_obj, Mapping):
        return PrefillAddress()
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
        phone_std_code=_to_int(
            address_obj.get("phone", {}).get("stDcode") if isinstance(address_obj.get("phone"), Mapping) else 0
        ),
        phone_no=_to_int(
            address_obj.get("phone", {}).get("phoneNo") if isinstance(address_obj.get("phone"), Mapping) else 0
        ),
    )


def _extract_personal_info(root: dict[str, Any]) -> PrefillPersonalInfo:
    """Extract the personal info block from the prefill root."""
    pi = root.get("personalInfo")
    if not isinstance(pi, Mapping):
        return PrefillPersonalInfo()
    name = _extract_name(pi.get("assesseeName") or pi.get("assesseName"))
    address = _extract_address(pi.get("address"))
    pan = _to_str(pi.get("pan") or pi.get("PAN"))
    return PrefillPersonalInfo(
        pan=pan,
        aadhaar_card_no=_decode_aadhaar(pi.get("aadhaarCardNo") or pi.get("aadharCardNo")),
        name=name,
        assessee_ver_name=_to_str(pi.get("assesseeVerName") or pi.get("assesseVerName")),
        father_name=_to_str(pi.get("fatherName")),
        dob=_to_date(pi.get("dob")),
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

    The prefill schema has two filingStatus definitions — a narrow one
    under ``personalInfo`` (just ``residentialStatus``) and a broader
    one under ``lastFiledITR`` (with returnFileSec, section115BA, etc).
    We check both.
    """
    fs = root.get("filingStatus")
    if not isinstance(fs, Mapping):
        # Try lastFiledITR.filingStatus
        lfi = root.get("lastFiledITR")
        if isinstance(lfi, Mapping):
            fs = lfi.get("filingStatus")
            if not isinstance(fs, Mapping):
                return PrefillFilingStatus()
        else:
            return PrefillFilingStatus()
    return PrefillFilingStatus(
        return_file_sec=_to_int(fs.get("returnFileSec")),
        residential_status=_to_str(fs.get("residentialStatus")),
        section_115ba=_to_str(fs.get("section115BA")),
        assessee_rep_flg=_to_str(fs.get("asseseeRepFlg")),
        business_trust_flag=_to_str(fs.get("businessTrustFlag")),
        fii_fpi_flag=_to_str(fs.get("fiiFpiFlag")),
        foreign_exchange_flag=_to_str(fs.get("foreignExchangeFlag")),
        orig_ret_filed_date=_to_date(fs.get("origRetFiledDate")),
        receipt_no=_to_str(fs.get("receiptNo")),
        notice_date_under_sec=_to_date(fs.get("noticeDateUnderSec")),
        unique_no=_to_str(fs.get("uniqueNo")),
    )


def _extract_employers(root: dict[str, Any]) -> list[PrefillEmployerEntry]:
    """Extract the employer entries from the ``salaries`` schedule.

    The prefill schema places employer details under:
      ``salaries.salary[]`` where each item has ``nameOfEmployer``,
      ``tanOfEmployer``, ``addressDetail``, and ``salarys`` (with
      ``grossSalary``, ``salary``, ``valueOfPerquisites``,
      ``profitsinLieuOfSalary``, etc.).
    """
    employers: list[PrefillEmployerEntry] = []
    salaries = root.get("salaries")
    if not isinstance(salaries, Mapping):
        # Try insights.salaries as a fallback.
        insights = root.get("insights")
        if isinstance(insights, Mapping):
            salaries = insights.get("salaries")
        if not isinstance(salaries, Mapping):
            return employers
    salary_list = salaries.get("salary")
    if not isinstance(salary_list, list):
        return employers
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
    return employers


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

    Checks both ``insights.scheduleHP`` and top-level ``scheduleHP``.
    """
    hp_list: list[PrefillHouseProperty] = []
    # Source 1: insights.scheduleHP.propertyDetails[]
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
                        co_owners=list(item.get("coOwners") or []),
                        tenant_details=list(item.get("tenantDetails") or []),
                    ))
    # Source 2: top-level scheduleHP (if insights didn't yield anything).
    if not hp_list:
        hp = root.get("scheduleHP")
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

    Checks ``insights.scheduleOS`` and top-level ``scheduleOS``.
    Also pulls ``insights.intrstFrmSavingBank`` and ``insights.intrstFrmTermDeposit``.
    """
    insights = root.get("insights")
    if not isinstance(insights, Mapping):
        insights = {}
    os_obj = insights.get("scheduleOS") or root.get("scheduleOS")
    if not isinstance(os_obj, Mapping):
        os_obj = {}
    inc_oth = os_obj.get("incOthThanOwnRaceHorse") or {}
    if not isinstance(inc_oth, Mapping):
        inc_oth = {}
    others_inc = inc_oth.get("othersInc") or {}
    if not isinstance(others_inc, Mapping):
        others_inc = {}
    other_details = others_inc.get("othersIncDtls")
    if not isinstance(other_details, list):
        other_details = []
    other_income_details: list[dict[str, Any]] = []
    for d in other_details:
        if isinstance(d, Mapping):
            other_income_details.append({
                "nature": _to_str(d.get("othNatOfInc")),
                "amount": _to_int(d.get("othAmount")),
            })
    return PrefillOtherSourcesIncome(
        dividend_gross=_to_int(inc_oth.get("dividendGross") or inc_oth.get("DividendOthThan22e")),
        interest_from_savings_bank=_to_int(insights.get("intrstFrmSavingBank")),
        interest_from_term_deposit=_to_int(insights.get("intrstFrmTermDeposit")),
        interest_from_others=_to_int(inc_oth.get("intrstFrmOthers")),
        rent_from_mach_plant_bldgs=_to_int(inc_oth.get("rentFromMachPlantBldgs")),
        lottery_puzzle_income=_to_int(inc_oth.get("ltryPzzlChrgblUs115BB")),
        other_income_details=other_income_details,
    )


def _extract_bank_accounts(root: dict[str, Any]) -> list[PrefillBankAccount]:
    """Extract bank account entries from the prefill.

    Bank accounts live under ``lastFiledITR.bankAccountDtls[]`` with
    each item having ``addtnlBankDetails[]`` (the actual account rows).
    """
    accounts: list[PrefillBankAccount] = []
    lfi = root.get("lastFiledITR")
    if not isinstance(lfi, Mapping):
        return accounts
    bank_dtls = lfi.get("bankAccountDtls")
    if not isinstance(bank_dtls, list):
        return accounts
    for bd in bank_dtls:
        if not isinstance(bd, Mapping):
            continue
        addtnl = bd.get("addtnlBankDetails")
        if not isinstance(addtnl, list):
            continue
        for acct in addtnl:
            if not isinstance(acct, Mapping):
                continue
            accounts.append(PrefillBankAccount(
                bank_account_no=_to_str(acct.get("bankAccountNo")),
                bank_name=_to_str(acct.get("bankName")),
                ifsc_code=_to_str(acct.get("ifsccode") or acct.get("ifscCode")),
                use_for_refund=_to_str(acct.get("useForRefund")).lower(),
            ))
    return accounts


def _extract_tds_salary(root: dict[str, Any]) -> list[PrefillTDSEntry]:
    """Extract TDS-on-salary entries from the prefill.

    Lives under ``tdsOnSalaries.tdsOnSalary[]`` with each item having
    ``employerOrDeductorOrCollectDetl`` (name + TAN), ``incChrgSal``,
    and ``totalTDSSal``.
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

    Lives under ``tdsOnOthThanSals.tdSonOthThanSal[]`` with each item
    having ``employerOrDeductorOrCollectDetl``, ``tanOfDeductor``,
    ``grossAmount``, ``tdsDeducted``, ``tdsClaimed``, ``headOfIncome``.
    """
    entries: list[PrefillTDSEntry] = []
    tos = root.get("tdsOnOthThanSals")
    if not isinstance(tos, Mapping):
        return entries
    tds_list = tos.get("tdSonOthThanSal")
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
            tan=_to_str(item.get("tanOfDeductor") or deductor.get("tan")),
            section="",
            income_amount=_to_int(item.get("grossAmount") or item.get("amtForTaxDeduct")),
            tds_deducted=_to_int(item.get("tdsDeducted")),
            tds_claimed=_to_int(item.get("tdsClaimed")),
            gross_amount=_to_int(item.get("grossAmount")),
            head_of_income=_to_str(item.get("headOfIncome")),
            deducted_year=_to_str(item.get("deductedYr")),
            brought_fwd_tds=_to_int(item.get("broughtFwdTDSAmt")),
        ))
    return entries


def _extract_tax_payments(root: dict[str, Any]) -> list[PrefillTaxPayment]:
    """Extract tax payment (advance tax / self-assessment) entries.

    The prefill schema carries these under ``taxPayments`` or
    ``insights.taxPayments``.  Each entry has ``bsrCode``,
    ``challanSerialNo``, ``depositDate``, ``taxAmount``, ``surcharge``,
    ``educationCess``, ``totalAmount``, and ``minorHead``.
    """
    payments: list[PrefillTaxPayment] = []
    tp = root.get("taxPayments")
    if not isinstance(tp, list):
        insights = root.get("insights")
        if isinstance(insights, Mapping):
            tp = insights.get("taxPayments")
        if not isinstance(tp, list):
            return payments
    for item in tp:
        if not isinstance(item, Mapping):
            continue
        payments.append(PrefillTaxPayment(
            bsr_code=_to_str(item.get("bsrCode")),
            challan_serial_no=_to_str(item.get("challanSerialNo")),
            deposit_date=_to_date(item.get("depositDate")),
            tax_amount=_to_int(item.get("taxAmount")),
            surcharge=_to_int(item.get("surcharge")),
            education_cess=_to_int(item.get("educationCess")),
            total_amount=_to_int(item.get("totalAmount")),
            minor_head=_to_str(item.get("minorHead")),
        ))
    return payments


def _extract_deductions(root: dict[str, Any]) -> PrefillDeductions:
    """Extract Chapter VI-A deductions from the prefill.

    The prefill schema carries these under ``scheduleDeductions`` or
    ``insights.scheduleDeductions`` with ``usrDeductUndChapVIA`` and
    ``deductUndChapVIA`` sub-objects.
    """
    sd = root.get("scheduleDeductions")
    if not isinstance(sd, Mapping):
        insights = root.get("insights")
        if isinstance(insights, Mapping):
            sd = insights.get("scheduleDeductions")
        if not isinstance(sd, Mapping):
            return PrefillDeductions()
    # Try usrDeductUndChapVIA first (user-entered), then deductUndChapVIA.
    usr = sd.get("usrDeductUndChapVIA") or sd.get("deductUndChapVIA") or {}
    if not isinstance(usr, Mapping):
        usr = {}
    total = _to_int(usr.get("totalChapVIADeductions") or sd.get("totalChapVIADeductions"))
    return PrefillDeductions(
        section_80c=_to_int(usr.get("section80C") or usr.get("Section80C")),
        section_80ccc=_to_int(usr.get("section80CCC") or usr.get("Section80CCC")),
        section_80ccd_employee_or_se=_to_int(usr.get("section80CCDEmployeeOrSE") or usr.get("Section80CCDEmployeeOrSE")),
        section_80ccd_1b=_to_int(usr.get("section80CCD1B") or usr.get("Section80CCD1B")),
        section_80ccd_employer=_to_int(usr.get("section80CCDEmployer") or usr.get("Section80CCDEmployer")),
        section_80d=_to_int(usr.get("section80D") or usr.get("Section80D")),
        section_80dd=_to_int(usr.get("section80DD") or usr.get("Section80DD")),
        section_80ddb=_to_int(usr.get("section80DDB") or usr.get("Section80DDB")),
        section_80e=_to_int(usr.get("section80E") or usr.get("Section80E")),
        section_80ee=_to_int(usr.get("section80EE") or usr.get("Section80EE")),
        section_80eea=_to_int(usr.get("section80EEA") or usr.get("Section80EEA")),
        section_80eeb=_to_int(usr.get("section80EEB") or usr.get("Section80EEB")),
        section_80g=_to_int(usr.get("section80G") or usr.get("Section80G")),
        section_80gg=_to_int(usr.get("section80GG") or usr.get("Section80GG")),
        section_80gga=_to_int(usr.get("section80GGA") or usr.get("Section80GGA")),
        section_80ggc=_to_int(usr.get("section80GGC") or usr.get("Section80GGC")),
        section_80u=_to_int(usr.get("section80U") or usr.get("Section80U")),
        section_80tta=_to_int(usr.get("section80TTA") or usr.get("Section80TTA")),
        section_80ttb=_to_int(usr.get("section80TTB") or usr.get("Section80TTB")),
        section_80cch=_to_int(usr.get("section80CCH") or usr.get("Section80CCH")),
        section_80qqb=_to_int(usr.get("section80QQB") or usr.get("Section80QQB")),
        section_80rrb=_to_int(usr.get("section80RRB") or usr.get("Section80RRB")),
        section_80la=_to_int(usr.get("section80LA") or usr.get("Section80LA")),
        total_chap_via_deductions=total,
    )


def _extract_carry_forward_losses(root: dict[str, Any]) -> list[PrefillCarryForwardLoss]:
    """Extract carry-forward loss entries from ``scheduleCFL``."""
    losses: list[PrefillCarryForwardLoss] = []
    cfl = root.get("scheduleCFL")
    if not isinstance(cfl, Mapping):
        return losses
    details = cfl.get("carryFwdLossDetail")
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

    Lives under ``insights.capitalGains.propertyDetails[]`` with each
    item having ``addressDetailWithZipCode``, ``buyers[]``,
    ``stampDuty``, and ``transactionAmount``.
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
    # Also check insights.incDeductionsOthIncCPC
    if not cpc_list:
        insights = root.get("insights")
        if isinstance(insights, Mapping):
            cpc = insights.get("incDeductionsOthIncCPC")
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
    # Check direct AY paths.
    for key in ("assessmentYear", "assessment_year"):
        val = root.get(key)
        if val:
            return _to_str(val)
    # Check metadata.assessmentYear.
    meta = root.get("metadata") or root.get("metaData")
    if isinstance(meta, Mapping):
        for key in ("assessmentYear", "assessment_year"):
            val = meta.get(key)
            if val:
                return _to_str(val)
    # Check IncDeductionsOthIncCPC[].itrAy.
    cpc = root.get("incDeductionsOthIncCPC")
    if isinstance(cpc, list) and cpc:
        first = cpc[0]
        if isinstance(first, Mapping):
            ay = first.get("itrAy")
            if ay:
                return _to_str(ay)
    return ""


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
    extraction = PrefillExtraction(
        personal_info=_extract_personal_info(root),
        filing_status=_extract_filing_status(root),
        employer_entries=_extract_employers(root),
        salary_insights=_extract_salary_insights(root),
        house_property=_extract_house_property(root),
        other_sources=_extract_other_sources(root),
        bank_accounts=_extract_bank_accounts(root),
        tds_salary_entries=_extract_tds_salary(root),
        tds_other_entries=_extract_tds_other(root),
        tax_payments=_extract_tax_payments(root),
        deductions=_extract_deductions(root),
        carry_forward_losses=_extract_carry_forward_losses(root),
        verification=_extract_verification(root),
        capital_gains_property=_extract_capital_gains_property(root),
        other_income_cpc=_extract_other_income_cpc(root),
        assessment_year=_extract_assessment_year(root) or assessment_year,
        pan=_extract_personal_info(root).pan,
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
