"""
Form-agnostic Last Filed ITR JSON parser.

Extracts every field available in the CBDT's official ITR JSON payload
(the same JSON that gets submitted to ITD when filing a return) into a
flat intermediate representation.  The filed-return JSON is downloaded
by ``downloader_filed_return.py`` as the ``prior_year_return`` file.

The filed-return JSON is the CBDT's official ITR JSON for the previous
year (or, for revision, the current year).  It follows the schema in
``PreFillSchemaJSON_V6.5.json`` and uses **PascalCase** keys (unlike
the prefill's camelCase).  The top-level structure is:

  ``{"ITR": {"ITR2": {...}}}``  (or ITR1, ITR3, ITR4, etc.)

Inside the form-specific wrapper (ITR1/ITR2/ITR3/ITR4/ITR5/ITR6/ITR7):

  - ``PartA_GEN1.PersonalInfo`` — name, PAN, address, DOB, Aadhaar
  - ``PartA_GEN1.FilingStatus`` — return section, residential status
  - ``ScheduleS.Salaries[]`` — employer entries with salary break-up
  - ``ScheduleCGFor23`` — capital gains (ITR-2/3)
  - ``ScheduleOS`` — other sources income
  - ``ScheduleVIA.UsrDeductUndChapVIA`` — Chapter VI-A deductions
  - ``PartA_GEN1.Refund.BankAccountDtls.AddtnlBankDetails[]`` — banks
  - ``ScheduleTDS1`` — TDS on salary
  - ``ScheduleTDS2.TDSOthThanSalaryDtls[]`` — TDS other than salary
  - ``ScheduleTCS`` — TCS
  - ``ScheduleCFL`` — carry-forward losses (if any)
  - ``Verification`` — declaration, capacity, place

The parser auto-detects the ITR form (ITR1, ITR2, ITR3, ITR4, ITR5,
ITR6, ITR7) and extracts the form-agnostic fields.  Form-specific
sections (like ScheduleCG for ITR-2/3) are passed through as raw dicts
for the frontend mappers to handle.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


# ──────────────────────────────────────────────────────────────────────────────
# Root-unwrapping helpers
# ──────────────────────────────────────────────────────────────────────────────

_ITR_FORM_KEYS: tuple[str, ...] = (
    "ITR1", "ITR2", "ITR3", "ITR4", "ITR5", "ITR6", "ITR7",
)


def _unwrap_filed_return_root(payload: Any) -> tuple[dict[str, Any], str]:
    """Return (form_root, form_name) from the ITR wrapper.

    Args:
        payload: The parsed JSON (dict, list, or scalar).

    Returns:
        A tuple of (the dict inside the form-specific wrapper, the form
        name like "ITR2").  If the payload is not a dict or the wrapper
        is not recognized, returns ({}, "").
    """
    if not isinstance(payload, Mapping):
        return {}, ""

    # Top-level is usually {"ITR": {"ITR2": {...}}}
    itr = payload.get("ITR")
    if isinstance(itr, Mapping):
        for form_key in _ITR_FORM_KEYS:
            inner = itr.get(form_key)
            if isinstance(inner, Mapping):
                return dict(inner), form_key

    # Some payloads may be flat {ITR2: {...}} without the ITR wrapper.
    for form_key in _ITR_FORM_KEYS:
        inner = payload.get(form_key)
        if isinstance(inner, Mapping):
            return dict(inner), form_key

    return {}, ""


def _get(obj: Any, *keys: str, default: Any = None) -> Any:
    """Safely walk a nested object by keys; return default if any missing.

    Each key is matched case-insensitively against the object's keys.
    """
    current = obj
    for key in keys:
        if not isinstance(current, Mapping):
            return default
        match = None
        for k in current:
            if k.lower() == key.lower():
                match = current[k]
                break
        if match is None:
            return default
        current = match
    return current


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


def _to_date(value: Any) -> str:
    """Normalize a date value to YYYY-MM-DD; return empty if unparseable."""
    raw = _to_str(value)
    if not raw:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        dd, mm, yyyy = m.groups()
        return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
    return raw


# ──────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FiledReturnName:
    """Three-part taxpayer name from the filed return."""

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
class FiledReturnAddress:
    """Address fields from the filed return."""

    residence_no: str = ""
    residence_name: str = ""
    road_or_street: str = ""
    locality_or_area: str = ""
    city_or_town_or_district: str = ""
    state_code: str = ""
    country_code: str = ""
    pin_code: str = ""
    country_code_mobile: int = 0
    mobile_no: int = 0
    email_address: str = ""
    alternate_address: dict[str, Any] = field(default_factory=dict)
    secondary_add: str = ""


@dataclass
class FiledReturnPersonalInfo:
    """Personal information block from the filed return."""

    pan: str = ""
    aadhaar_card_no: str = ""
    name: FiledReturnName = field(default_factory=FiledReturnName)
    dob: str = ""
    status: str = ""
    address: FiledReturnAddress = field(default_factory=FiledReturnAddress)


@dataclass
class FiledReturnFilingStatus:
    """Filing status block from the filed return."""

    return_file_sec: int = 0
    residential_status: str = ""
    section_115ba: str = ""
    assessee_rep_flg: str = ""
    portugese_cc5a: str = ""
    fii_fpi_flag: str = ""
    comp_director_prv_yr_flg: str = ""
    held_unlisted_eq_shr_pr_yr_flg: str = ""
    seventh_provisio_139: str = ""
    opt_out_new_tax_regime: str = ""
    itr_filing_due_date: str = ""


@dataclass
class FiledReturnEmployerEntry:
    """One employer from the salary schedule."""

    employer_name: str = ""
    nature_of_employment: str = ""
    tan: str = ""
    gross_salary: int = 0
    salary: int = 0
    value_of_perquisites: int = 0
    profits_in_lieu_of_salary: int = 0
    employer_address: str = ""
    employer_city: str = ""
    employer_state_code: str = ""
    employer_pin_code: str = ""


@dataclass
class FiledReturnBankAccount:
    """One bank account from the filed return."""

    bank_account_no: str = ""
    bank_name: str = ""
    ifsc_code: str = ""
    account_type: str = ""
    use_for_refund: str = "false"


@dataclass
class FiledReturnTDSEntry:
    """One TDS entry from the filed return (salary or other-than-salary)."""

    deductor_name: str = ""
    tan: str = ""
    section: str = ""
    income_amount: int = 0
    tds_deducted: int = 0
    tds_claimed: int = 0
    gross_amount: int = 0
    head_of_income: str = ""
    brought_fwd_tds: int = 0
    amt_carried_fwd: int = 0


@dataclass
class FiledReturnDeductions:
    """Chapter VI-A deductions from the filed return."""

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
class FiledReturnOtherSources:
    """Other sources income from the filed return."""

    dividend_gross: int = 0
    interest_from_savings_bank: int = 0
    interest_from_term_deposit: int = 0
    interest_from_others: int = 0
    rent_from_mach_plant_bldgs: int = 0
    lottery_puzzle_income: int = 0
    other_income_details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FiledReturnCarryForwardLoss:
    """One carry-forward loss entry from the filed return."""

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


@dataclass
class FiledReturnVerification:
    """Verification block from the filed return."""

    assessee_ver_name: str = ""
    assessee_ver_pan: str = ""
    father_name: str = ""
    capacity: str = ""
    place: str = ""
    date: str = ""


@dataclass
class FiledReturnExtraction:
    """Complete form-agnostic extraction from the filed ITR JSON.

    Every field is populated on a best-effort basis — if the filed
    return doesn't contain a particular section, the corresponding
    field remains at its default (empty/zero).
    """

    form_name: str = ""
    assessment_year: str = ""
    schema_version: str = ""
    form_version: str = ""
    personal_info: FiledReturnPersonalInfo = field(default_factory=FiledReturnPersonalInfo)
    filing_status: FiledReturnFilingStatus = field(default_factory=FiledReturnFilingStatus)
    employer_entries: list[FiledReturnEmployerEntry] = field(default_factory=list)
    bank_accounts: list[FiledReturnBankAccount] = field(default_factory=list)
    tds_salary_entries: list[FiledReturnTDSEntry] = field(default_factory=list)
    tds_other_entries: list[FiledReturnTDSEntry] = field(default_factory=list)
    deductions: FiledReturnDeductions = field(default_factory=FiledReturnDeductions)
    other_sources: FiledReturnOtherSources = field(default_factory=FiledReturnOtherSources)
    carry_forward_losses: list[FiledReturnCarryForwardLoss] = field(default_factory=list)
    verification: FiledReturnVerification = field(default_factory=FiledReturnVerification)
    capital_gains: dict[str, Any] = field(default_factory=dict)
    schedule_cyla: dict[str, Any] = field(default_factory=dict)
    schedule_bfla: dict[str, Any] = field(default_factory=dict)
    schedule_si: dict[str, Any] = field(default_factory=dict)
    schedule_it: dict[str, Any] = field(default_factory=dict)
    schedule_amtc: dict[str, Any] = field(default_factory=dict)
    total_tax_payments: int = 0
    bal_tax_payable: int = 0
    refund_due: int = 0
    asset_out_india_flag: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Section extractors
# ──────────────────────────────────────────────────────────────────────────────

def _extract_name(name_obj: Any) -> FiledReturnName:
    """Extract the three-part name from the AssesseeName object."""
    if not isinstance(name_obj, Mapping):
        return FiledReturnName()
    return FiledReturnName(
        first_name=_to_str(name_obj.get("FirstName") or name_obj.get("firstName")),
        middle_name=_to_str(name_obj.get("MiddleName") or name_obj.get("middleName")),
        surname_or_org_name=_to_str(
            name_obj.get("SurNameOrOrgName")
            or name_obj.get("surNameOrOrgName")
            or name_obj.get("Surname")
        ),
    )


def _extract_address(address_obj: Any) -> FiledReturnAddress:
    """Extract the address + contact fields from the Address object."""
    if not isinstance(address_obj, Mapping):
        return FiledReturnAddress()
    return FiledReturnAddress(
        residence_no=_to_str(address_obj.get("ResidenceNo")),
        residence_name=_to_str(address_obj.get("ResidenceName")),
        road_or_street=_to_str(address_obj.get("RoadOrStreet")),
        locality_or_area=_to_str(address_obj.get("LocalityOrArea")),
        city_or_town_or_district=_to_str(address_obj.get("CityOrTownOrDistrict")),
        state_code=_to_str(address_obj.get("StateCode")),
        country_code=_to_str(address_obj.get("CountryCode")),
        pin_code=_to_str(address_obj.get("PinCode")),
        country_code_mobile=_to_int(address_obj.get("CountryCodeMobile")),
        mobile_no=_to_int(address_obj.get("MobileNo")),
        email_address=_to_str(address_obj.get("EmailAddress")),
        alternate_address=dict(address_obj.get("AlternateAddress") or {}),
        secondary_add=_to_str(address_obj.get("SecondaryAdd")),
    )


def _extract_personal_info(form_root: dict[str, Any]) -> FiledReturnPersonalInfo:
    """Extract personal info from PartA_GEN1.PersonalInfo."""
    parta = _get(form_root, "PartA_GEN1", default={})
    if not isinstance(parta, Mapping):
        return FiledReturnPersonalInfo()
    pi = parta.get("PersonalInfo")
    if not isinstance(pi, Mapping):
        return FiledReturnPersonalInfo()
    name = _extract_name(pi.get("AssesseeName") or pi.get("assesseeName"))
    address = _extract_address(pi.get("Address") or pi.get("address"))
    return FiledReturnPersonalInfo(
        pan=_to_str(pi.get("PAN") or pi.get("pan")),
        aadhaar_card_no=_to_str(pi.get("AadhaarCardNo") or pi.get("aadhaarCardNo")),
        name=name,
        dob=_to_date(pi.get("DOB") or pi.get("dob")),
        status=_to_str(pi.get("Status") or pi.get("status")),
        address=address,
    )


def _extract_filing_status(form_root: dict[str, Any]) -> FiledReturnFilingStatus:
    """Extract filing status from PartA_GEN1.FilingStatus."""
    parta = _get(form_root, "PartA_GEN1", default={})
    if not isinstance(parta, Mapping):
        return FiledReturnFilingStatus()
    fs = parta.get("FilingStatus")
    if not isinstance(fs, Mapping):
        return FiledReturnFilingStatus()
    return FiledReturnFilingStatus(
        return_file_sec=_to_int(fs.get("ReturnFileSec")),
        residential_status=_to_str(fs.get("ResidentialStatus")),
        section_115ba=_to_str(fs.get("Section115BA")),
        assessee_rep_flg=_to_str(fs.get("AsseseeRepFlg")),
        portugese_cc5a=_to_str(fs.get("PortugeseCC5A")),
        fii_fpi_flag=_to_str(fs.get("FiiFpiFlag")),
        comp_director_prv_yr_flg=_to_str(fs.get("CompDirectorPrvYrFlg")),
        held_unlisted_eq_shr_pr_yr_flg=_to_str(fs.get("HeldUnlistedEqShrPrYrFlg")),
        seventh_provisio_139=_to_str(fs.get("SeventhProvisio139")),
        opt_out_new_tax_regime=_to_str(fs.get("OptOutNewTaxRegime")),
        itr_filing_due_date=_to_date(fs.get("ItrFilingDueDate")),
    )


def _extract_employers(form_root: dict[str, Any]) -> list[FiledReturnEmployerEntry]:
    """Extract employer entries from ScheduleS.Salaries[]."""
    employers: list[FiledReturnEmployerEntry] = []
    sched_s = _get(form_root, "ScheduleS", default={})
    if not isinstance(sched_s, Mapping):
        return employers
    salaries = sched_s.get("Salaries")
    if not isinstance(salaries, list):
        return employers
    for item in salaries:
        if not isinstance(item, Mapping):
            continue
        addr = item.get("AddressDetail") or {}
        if not isinstance(addr, Mapping):
            addr = {}
        salarys = item.get("Salarys") or {}
        if not isinstance(salarys, Mapping):
            salarys = {}
        employers.append(FiledReturnEmployerEntry(
            employer_name=_to_str(item.get("NameOfEmployer")),
            nature_of_employment=_to_str(item.get("NatureOfEmployment")),
            tan=_to_str(item.get("TANOfEmployer") or item.get("TanOfEmployer")),
            gross_salary=_to_int(salarys.get("GrossSalary")),
            salary=_to_int(salarys.get("Salary")),
            value_of_perquisites=_to_int(salarys.get("ValueOfPerquisites")),
            profits_in_lieu_of_salary=_to_int(salarys.get("ProfitsinLieuOfSalary")),
            employer_address=_to_str(addr.get("AddrDetail") or addr.get("addDetail")),
            employer_city=_to_str(addr.get("CityOrTownOrDistrict")),
            employer_state_code=_to_str(addr.get("StateCode")),
            employer_pin_code=_to_str(addr.get("PinCode")),
        ))
    return employers


def _extract_bank_accounts(form_root: dict[str, Any]) -> list[FiledReturnBankAccount]:
    """Extract bank accounts from PartB_TTI.Refund.BankAccountDtls.AddtnlBankDetails[].

    The Refund block (with bank accounts) lives under ``PartB_TTI``, not
    ``PartA_GEN1``.  Some ITR forms may also place it under
    ``PartA_GEN1``; we check both.
    """
    accounts: list[FiledReturnBankAccount] = []

    def _collect_from_parta(part_obj: Any) -> None:
        if not isinstance(part_obj, Mapping):
            return
        refund = part_obj.get("Refund")
        if not isinstance(refund, Mapping):
            return
        bank_dtls = refund.get("BankAccountDtls")
        if not isinstance(bank_dtls, Mapping):
            return
        addtnl = bank_dtls.get("AddtnlBankDetails")
        if not isinstance(addtnl, list):
            return
        for acct in addtnl:
            if not isinstance(acct, Mapping):
                continue
            accounts.append(FiledReturnBankAccount(
                bank_account_no=_to_str(acct.get("BankAccountNo")),
                bank_name=_to_str(acct.get("BankName")),
                ifsc_code=_to_str(acct.get("IFSCCode") or acct.get("IfscCode")),
                account_type=_to_str(acct.get("AccountType")),
                use_for_refund=_to_str(acct.get("UseForRefund")).lower(),
            ))

    # Source 1: PartB_TTI.Refund.BankAccountDtls (the usual location)
    _collect_from_parta(_get(form_root, "PartB_TTI", default={}))

    # Source 2: PartA_GEN1.Refund.BankAccountDtls (fallback for some forms)
    if not accounts:
        _collect_from_parta(_get(form_root, "PartA_GEN1", default={}))

    if not accounts:
        return []

    # Deduplicate by bank name + IFSC + zero-stripped account number.
    seen: set[str] = set()
    deduped: list[FiledReturnBankAccount] = []
    for acct in accounts:
        normalized_no = acct.bank_account_no.lstrip("0").upper()
        key = f"{acct.bank_name.lower()}|{acct.ifsc_code.upper()}|{normalized_no}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(acct)
    # Only one refund account.
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


def _extract_tds_salary(form_root: dict[str, Any]) -> list[FiledReturnTDSEntry]:
    """Extract TDS on salary from ScheduleTDS1."""
    entries: list[FiledReturnTDSEntry] = []
    tds1 = _get(form_root, "ScheduleTDS1", default={})
    if not isinstance(tds1, Mapping):
        return entries
    # ScheduleTDS1 may have TDSonSalariesDtls[] or just a total.
    tds_list = tds1.get("TDSonSalariesDtls")
    if not isinstance(tds_list, list):
        return entries
    for item in tds_list:
        if not isinstance(item, Mapping):
            continue
        deductor = item.get("EmployerOrDeductorOrCollectDetl") or {}
        if not isinstance(deductor, Mapping):
            deductor = {}
        credit = item.get("TaxDeductCreditDtls") or {}
        if not isinstance(credit, Mapping):
            credit = {}
        entries.append(FiledReturnTDSEntry(
            deductor_name=_to_str(deductor.get("EmployerOrDeductorOrCollecterName")),
            tan=_to_str(deductor.get("TAN") or item.get("TANOfDeductor")),
            section="192",
            income_amount=_to_int(item.get("IncChrgSal")),
            tds_deducted=_to_int(credit.get("TaxDeductedOwnHands") or item.get("TotalTDSSal")),
            tds_claimed=_to_int(credit.get("TaxClaimedOwnHands") or item.get("TotalTDSSal")),
        ))
    return entries


def _extract_tds_other(form_root: dict[str, Any]) -> list[FiledReturnTDSEntry]:
    """Extract TDS other than salary from ScheduleTDS2.TDSOthThanSalaryDtls[]."""
    entries: list[FiledReturnTDSEntry] = []
    tds2 = _get(form_root, "ScheduleTDS2", default={})
    if not isinstance(tds2, Mapping):
        return entries
    tds_list = tds2.get("TDSOthThanSalaryDtls")
    if not isinstance(tds_list, list):
        return entries
    for item in tds_list:
        if not isinstance(item, Mapping):
            continue
        credit = item.get("TaxDeductCreditDtls") or {}
        if not isinstance(credit, Mapping):
            credit = {}
        entries.append(FiledReturnTDSEntry(
            deductor_name=_to_str(item.get("DeductorName")),
            tan=_to_str(item.get("TANOfDeductor")),
            section=_to_str(item.get("TDSSection") or item.get("SectionCode")),
            income_amount=_to_int(item.get("GrossAmount")),
            tds_deducted=_to_int(credit.get("TaxDeductedOwnHands")),
            tds_claimed=_to_int(credit.get("TaxClaimedOwnHands")),
            gross_amount=_to_int(item.get("GrossAmount")),
            head_of_income=_to_str(item.get("HeadOfIncome")),
            brought_fwd_tds=_to_int(item.get("BroughtFwdTDSAmt")),
            amt_carried_fwd=_to_int(item.get("AmtCarriedFwd")),
        ))
    return entries


def _extract_deductions(form_root: dict[str, Any]) -> FiledReturnDeductions:
    """Extract Chapter VI-A deductions from ScheduleVIA.UsrDeductUndChapVIA."""
    via = _get(form_root, "ScheduleVIA", default={})
    if not isinstance(via, Mapping):
        return FiledReturnDeductions()
    usr = via.get("UsrDeductUndChapVIA") or {}
    if not isinstance(usr, Mapping):
        usr = {}

    def _get_ded(key_variants: tuple[str, ...]) -> int:
        for key in key_variants:
            val = usr.get(key)
            if val is not None:
                return _to_int(val)
        return 0

    return FiledReturnDeductions(
        section_80c=_get_ded(("Section80C", "section80C")),
        section_80ccc=_get_ded(("Section80CCC", "section80CCC")),
        section_80ccd_employee_or_se=_get_ded(("Section80CCDEmployeeOrSE", "section80CCDEmployeeOrSE")),
        section_80ccd_1b=_get_ded(("Section80CCD1B", "section80CCD1B")),
        section_80ccd_employer=_get_ded(("Section80CCDEmployer", "section80CCDEmployer")),
        section_80d=_get_ded(("Section80D", "section80D")),
        section_80dd=_get_ded(("Section80DD", "section80DD")),
        section_80ddb=_get_ded(("Section80DDB", "section80DDB")),
        section_80e=_get_ded(("Section80E", "section80E")),
        section_80ee=_get_ded(("Section80EE", "section80EE")),
        section_80eea=_get_ded(("Section80EEA", "section80EEA")),
        section_80eeb=_get_ded(("Section80EEB", "section80EEB")),
        section_80g=_get_ded(("Section80G", "section80G")),
        section_80gg=_get_ded(("Section80GG", "section80GG")),
        section_80gga=_get_ded(("Section80GGA", "section80GGA")),
        section_80ggc=_get_ded(("Section80GGC", "section80GGC")),
        section_80u=_get_ded(("Section80U", "section80U")),
        section_80tta=_get_ded(("Section80TTA", "section80TTA")),
        section_80ttb=_get_ded(("Section80TTB", "section80TTB")),
        section_80cch=_get_ded(("Section80CCH", "section80CCH")),
        section_80qqb=_get_ded(("Section80QQB", "section80QQB")),
        section_80rrb=_get_ded(("Section80RRB", "section80RRB")),
        section_80la=_get_ded(("Section80LA", "section80LA")),
        total_chap_via_deductions=_to_int(usr.get("TotalChapVIADeductions") or via.get("TotalChapVIADeductions")),
    )


def _extract_other_sources(form_root: dict[str, Any]) -> FiledReturnOtherSources:
    """Extract other sources income from ScheduleOS."""
    os_obj = _get(form_root, "ScheduleOS", default={})
    if not isinstance(os_obj, Mapping):
        return FiledReturnOtherSources()
    inc_oth = os_obj.get("IncOthThanOwnRaceHorse") or os_obj.get("incOthThanOwnRaceHorse") or {}
    if not isinstance(inc_oth, Mapping):
        inc_oth = {}
    others_inc = inc_oth.get("OthersInc") or {}
    if not isinstance(others_inc, Mapping):
        others_inc = {}
    other_details: list[dict[str, Any]] = []
    other_dtls = others_inc.get("OthersIncDtls")
    if isinstance(other_dtls, list):
        for d in other_dtls:
            if isinstance(d, Mapping):
                other_details.append({
                    "nature": _to_str(d.get("NatureDesc") or d.get("othNatOfInc")),
                    "amount": _to_int(d.get("OthAmount") or d.get("othAmount")),
                })
    return FiledReturnOtherSources(
        dividend_gross=_to_int(inc_oth.get("DividendGross") or inc_oth.get("dividendGross")),
        interest_from_savings_bank=_to_int(inc_oth.get("IntrstFrmSavingBank")),
        interest_from_term_deposit=_to_int(inc_oth.get("IntrstFrmTermDeposit")),
        interest_from_others=_to_int(inc_oth.get("IntrstFrmOthers")),
        rent_from_mach_plant_bldgs=_to_int(inc_oth.get("RentFromMachPlantBldgs")),
        lottery_puzzle_income=_to_int(inc_oth.get("LtryPzzlChrgblUs115BB")),
        other_income_details=other_details,
    )


def _extract_carry_forward_losses(form_root: dict[str, Any]) -> list[FiledReturnCarryForwardLoss]:
    """Extract carry-forward losses from ScheduleCFL."""
    losses: list[FiledReturnCarryForwardLoss] = []
    cfl = _get(form_root, "ScheduleCFL", default={})
    if not isinstance(cfl, Mapping):
        return losses
    details = cfl.get("CarryFwdLossDetail") or cfl.get("carryFwdLossDetail")
    if not isinstance(details, list):
        return losses
    for item in details:
        if not isinstance(item, Mapping):
            continue
        losses.append(FiledReturnCarryForwardLoss(
            assessment_year=_to_str(item.get("AssessmentYear")),
            brought_fwd_bus_loss=_to_int(item.get("BroughtFrwrdBusLoss")),
            bus_loss_oth_than_spec_loss_cf=_to_int(item.get("BusLossOthThanSpecLossCF")),
            hp_loss_cf=_to_int(item.get("HpLossCF") or item.get("HPLossCF")),
            loss_frm_insu_cf=_to_int(item.get("LossFrmInsuCF")),
            loss_frm_spec_bus_cf=_to_int(item.get("LossFrmSpecBusCF")),
            loss_frm_specified_bus_cf=_to_int(item.get("LossFrmSpecifiedBusCF")),
            ltcg_loss_cf=_to_int(item.get("LTCGLossCF") or item.get("ltcgLossCF")),
            oth_src_loss_race_horse_cf=_to_int(item.get("OthSrcLossRaceHorseCF")),
            stcg_loss_cf=_to_int(item.get("STCGLossCF") or item.get("stcgLossCF")),
        ))
    return losses


def _extract_verification(form_root: dict[str, Any]) -> FiledReturnVerification:
    """Extract verification block."""
    v = _get(form_root, "Verification", default={})
    if not isinstance(v, Mapping):
        return FiledReturnVerification()
    decl = v.get("Declaration") or {}
    if not isinstance(decl, Mapping):
        decl = {}
    return FiledReturnVerification(
        assessee_ver_name=_to_str(decl.get("AssesseeVerName")),
        assessee_ver_pan=_to_str(decl.get("AssesseeVerPAN")),
        father_name=_to_str(decl.get("FatherName")),
        capacity=_to_str(v.get("Capacity")),
        place=_to_str(v.get("Place")),
        date=_to_date(v.get("Date")),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def parse_filed_return_json(payload: Any) -> FiledReturnExtraction:
    """Parse the filed ITR JSON into a form-agnostic extraction.

    Args:
        payload: The parsed JSON (dict, or any wrapper shape).

    Returns:
        A ``FiledReturnExtraction`` with every available field populated.
    """
    form_root, form_name = _unwrap_filed_return_root(payload)
    if not form_root:
        return FiledReturnExtraction()

    # Extract CreationInfo for metadata.
    creation = _get(form_root, "CreationInfo", default={})
    if not isinstance(creation, Mapping):
        creation = {}
    form_info = _get(form_root, "Form_ITR2", default={}) or _get(form_root, "Form_ITR1", default={}) or _get(form_root, "Form_ITR3", default={}) or _get(form_root, "Form_ITR4", default={})
    if not isinstance(form_info, Mapping):
        form_info = {}

    # Extract PartB_TTI for refund/tax totals (where Refund block lives).
    partb = _get(form_root, "PartB_TTI", default={})
    if not isinstance(partb, Mapping):
        partb = {}
    refund = partb.get("Refund")
    refund_due = 0
    if isinstance(refund, Mapping):
        refund_due = _to_int(refund.get("RefundDue"))
    # BalTaxPayable is under PartB_TTI.TaxPaid.BalTaxPayable
    tax_paid = partb.get("TaxPaid")
    if not isinstance(tax_paid, Mapping):
        tax_paid = {}
    bal_tax_payable = _to_int(tax_paid.get("BalTaxPayable"))
    # AssetOutIndiaFlag is under PartB_TTI
    asset_out_india_flag = _to_str(partb.get("AssetOutIndiaFlag"))

    # Extract ScheduleIT for tax payments total.
    sched_it = _get(form_root, "ScheduleIT", default={})
    if not isinstance(sched_it, Mapping):
        sched_it = {}
    total_tax_payments = _to_int(sched_it.get("TotalTaxPayments"))

    # Extract ScheduleAMTC.
    sched_amtc = _get(form_root, "ScheduleAMTC", default={})
    if not isinstance(sched_amtc, Mapping):
        sched_amtc = {}

    # Extract ScheduleSI, CYLA, BFLA as raw dicts.
    sched_si = _get(form_root, "ScheduleSI", default={})
    if not isinstance(sched_si, Mapping):
        sched_si = {}
    sched_cyla = _get(form_root, "ScheduleCYLA", default={})
    if not isinstance(sched_cyla, Mapping):
        sched_cyla = {}
    sched_bfla = _get(form_root, "ScheduleBFLA", default={})
    if not isinstance(sched_bfla, Mapping):
        sched_bfla = {}

    # Extract capital gains (ScheduleCGFor23 for ITR-2/3, may not exist for ITR-1).
    sched_cg = _get(form_root, "ScheduleCGFor23", default={})
    if not isinstance(sched_cg, Mapping):
        sched_cg = {}

    return FiledReturnExtraction(
        form_name=form_name,
        assessment_year=_to_str(form_info.get("AssessmentYear")),
        schema_version=_to_str(form_info.get("SchemaVer")),
        form_version=_to_str(form_info.get("FormVer")),
        personal_info=_extract_personal_info(form_root),
        filing_status=_extract_filing_status(form_root),
        employer_entries=_extract_employers(form_root),
        bank_accounts=_extract_bank_accounts(form_root),
        tds_salary_entries=_extract_tds_salary(form_root),
        tds_other_entries=_extract_tds_other(form_root),
        deductions=_extract_deductions(form_root),
        other_sources=_extract_other_sources(form_root),
        carry_forward_losses=_extract_carry_forward_losses(form_root),
        verification=_extract_verification(form_root),
        capital_gains=dict(sched_cg) if sched_cg else {},
        schedule_cyla=dict(sched_cyla) if sched_cyla else {},
        schedule_bfla=dict(sched_bfla) if sched_bfla else {},
        schedule_si=dict(sched_si) if sched_si else {},
        schedule_it=dict(sched_it) if sched_it else {},
        schedule_amtc=dict(sched_amtc) if sched_amtc else {},
        total_tax_payments=total_tax_payments,
        bal_tax_payable=bal_tax_payable,
        refund_due=refund_due,
        asset_out_india_flag=asset_out_india_flag,
        metadata={
            "source": "filed_return",
            "form_name": form_name,
            "schema_version": _to_str(form_info.get("SchemaVer")),
            "json_creation_date": _to_str(creation.get("JSONCreationDate")),
        },
    )


def parse_filed_return_file(path: str | Path) -> FiledReturnExtraction:
    """Parse a filed ITR JSON file from disk.

    Args:
        path: Path to the downloaded filed-return JSON file.

    Returns:
        A ``FiledReturnExtraction`` with every available field populated.
    """
    p = Path(path)
    try:
        payload = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Unable to read filed-return JSON at {path}: {exc}") from exc
    return parse_filed_return_json(payload)


def filed_return_extraction_to_dict(extraction: FiledReturnExtraction) -> dict[str, Any]:
    """Convert a ``FiledReturnExtraction`` to a JSON-serializable dict."""
    import dataclasses

    def _serialize(obj: Any) -> Any:
        if dataclasses.is_dataclass(obj):
            return {k: _serialize(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list):
            return [_serialize(item) for item in obj]
        return obj

    return _serialize(extraction)
