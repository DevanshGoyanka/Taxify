"""ITR-2 ITD JSON builder — AY 2026-27 canonical serializer.

Produces a CBDT-compliant JSON document matching the official ITR-2 schema
``ITR-2_2026_Main_V1.1`` with ``additionalProperties: false`` enforcement.

Every schedule is serialized from real input evidence or computed results —
no fabricated addresses, TANs, bank accounts, or employer names.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.engine.calculators.itr2 import ITR2Result
from app.engine.schedules.capital_gains import deemed_consideration_50c
from app.engine.itd.common import (
    _to_rupees,
    _to_rupees_rounded10,
    _creation_info,
    _form_itr,
    _verification,
    _compute_digest,
    _str_or,
)
from app.schemas.itr1 import BankAccountType
from app.schemas.itr2 import (
    ForeignAssetType,
    ITR2Input,
    ITR2FilingProfile,
)

_ZERO = Decimal("0")


# ============================================================================
# Helpers
# ============================================================================

def _date(value: Any) -> str:
    """Return an ISO date string for a date-like value."""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _required_profile(input_data: ITR2Input) -> ITR2FilingProfile:
    """Return the filing profile, rejecting identity-free filing requests."""
    if input_data.filing_profile is None:
        raise ValueError("ITR-2 JSON generation requires filing_profile")
    return input_data.filing_profile


def _positive_val(obj: Any, attr: str) -> Decimal:
    """Return max(0, getattr(obj, attr)) safely."""
    return max(_ZERO, getattr(obj, attr, _ZERO))


def _z6() -> dict[str, int]:
    """All-zero CG loss set-off matrix."""
    return {
        "StclSetoff20Per": 0,
        "StclSetoff30Per": 0,
        "StclSetoffAppRate": 0,
        "StclSetoffDTAARate": 0,
        "LtclSetOff12_5Per": 0,
        "LtclSetOffDTAARate": 0,
    }


def _date_range() -> dict[str, Any]:
    """All-zero DateRangeType."""
    return {
        "DateRange": {
            "Upto15Of6": 0,
            "Upto15Of9": 0,
            "Up16Of9To15Of12": 0,
            "Up16Of12To15Of3": 0,
            "Up16Of3To31Of3": 0,
        }
    }


# ============================================================================
# Part A — Personal info and filing status
# ============================================================================

def _part_a_gen1(input_data: ITR2Input) -> dict[str, Any]:
    """Serialize Part A from the real filing profile."""
    profile = _required_profile(input_data)
    addr = profile.primary_address
    personal_info: dict[str, Any] = {
        "AssesseeName": {
            "FirstName": profile.first_name,
            "MiddleName": profile.middle_name,
            "SurNameOrOrgName": profile.surname_or_org_name,
        },
        "PAN": profile.pan,
        "Address": {
            "ResidenceNo": addr.residence_no,
            "ResidenceName": addr.residence_name,
            "RoadOrStreet": addr.road_or_street,
            "LocalityOrArea": addr.locality_or_area,
            "CityOrTownOrDistrict": addr.city_or_town_or_district,
            "StateCode": addr.state_code,
            "CountryCode": addr.country_code,
            "PinCode": int(addr.pin_code) if addr.pin_code else 0,
            "ZipCode": "",
            "CountryCodeMobile": 91,
            "MobileNo": int(addr.mobile_no) if addr.mobile_no.isdigit() else 0,
            "CountryCodeMobileNoSec": 0,
            "MobileNoSec": 0,
            "EmailAddress": addr.email,
        },
        "SecondaryAdd": "Y" if profile.alternate_address else "N",
        "DOB": _date(profile.date_of_birth_or_formation),
        "Status": profile.assessee_status.value,
    }
    if profile.aadhaar_number:
        personal_info["AadhaarCardNo"] = profile.aadhaar_number
    if profile.alternate_address:
        alt = profile.alternate_address
        personal_info["AlternateAddress"] = {
            "ResidenceNo": alt.residence_no,
            "ResidenceName": alt.residence_name,
            "RoadOrStreet": alt.road_or_street,
            "LocalityOrArea": alt.locality_or_area,
            "CityOrTownOrDistrict": alt.city_or_town_or_district,
            "StateCode": alt.state_code,
            "CountryCode": alt.country_code,
            "PinCode": int(alt.pin_code) if alt.pin_code else 0,
            "ZipCode": alt.zip_code,
        }
    filing_status: dict[str, Any] = {
        "ReturnFileSec": int(profile.return_file_section),
        "OptOutNewTaxRegime": "Y" if profile.opted_out_new_tax_regime else "N",
        "SeventhProvisio139": "Y" if profile.seventh_proviso_139 else "N",
        "ResidentialStatus": profile.residential_status.value,
        "AsseseeRepFlg": "N",
        "ItrFilingDueDate": _date(profile.filing_due_date),
        "HeldUnlistedEqShrPrYrFlg": "Y" if profile.held_unlisted_equity else "N",
        "FiiFpiFlag": "Y" if profile.is_fii_fpi else "N",
    }
    if profile.receipt_number:
        filing_status["ReceiptNo"] = profile.receipt_number
    if profile.original_return_date:
        filing_status["OrigRetFiledDate"] = _date(profile.original_return_date)
    if profile.notice_number:
        filing_status["NoticeNo"] = profile.notice_number
    if profile.notice_date:
        filing_status["NoticeDate"] = _date(profile.notice_date)
    if profile.sebi_registration_number:
        # Official schema key is "SebiRegnNo", NOT "SEBIRegNo" -- confirmed
        # via live Draft4Validator schema validation (the wrong key was
        # rejected outright with "Additional properties are not allowed").
        filing_status["SebiRegnNo"] = profile.sebi_registration_number
    if profile.lei_number:
        filing_status["LEIDtls"] = {"LEINumber": profile.lei_number}
        if profile.lei_valid_upto_date:
            filing_status["LEIDtls"]["ValidUptoDate"] = _date(profile.lei_valid_upto_date)
    return {"PersonalInfo": personal_info, "FilingStatus": filing_status}


# ============================================================================
# CYLA / BFLA / CFL helpers
# ============================================================================

def _inc_cyla(inc: Decimal, hp_setoff: Decimal, os_setoff: Decimal, after: Decimal) -> dict[str, int]:
    return {
        "IncOfCurYrUnderThatHead": _to_rupees(inc),
        "HPlossCurYrSetoff": _to_rupees(hp_setoff),
        "OthSrcLossNoRaceHorseSetoff": _to_rupees(os_setoff),
        "IncOfCurYrAfterSetOff": _to_rupees(after),
    }


def _inc_cyla_hp(inc: Decimal, os_setoff: Decimal, after: Decimal) -> dict[str, int]:
    return {
        "IncOfCurYrUnderThatHead": _to_rupees(inc),
        "OthSrcLossNoRaceHorseSetoff": _to_rupees(os_setoff),
        "IncOfCurYrAfterSetOff": _to_rupees(after),
    }


def _inc_cyla_os(inc: Decimal, hp_setoff: Decimal, after: Decimal) -> dict[str, int]:
    return {
        "IncOfCurYrUnderThatHead": _to_rupees(inc),
        "HPlossCurYrSetoff": _to_rupees(hp_setoff),
        "IncOfCurYrAfterSetOff": _to_rupees(after),
    }


def _inc_bfla(inc_cyla: Decimal, bf_setoff: Decimal, after: Decimal) -> dict[str, int]:
    return {
        "IncOfCurYrUndHeadFromCYLA": _to_rupees(inc_cyla),
        "BFlossPrevYrUndSameHeadSetoff": _to_rupees(bf_setoff),
        "IncOfCurYrAfterSetOffBFLosses": _to_rupees(after),
    }


def _inc_bfla_no_bf(inc_cyla: Decimal, after: Decimal) -> dict[str, int]:
    return {
        "IncOfCurYrUndHeadFromCYLA": _to_rupees(inc_cyla),
        "IncOfCurYrAfterSetOffBFLosses": _to_rupees(after),
    }


# ============================================================================
# Schedule CYLA (required)
# ============================================================================

def _schedule_cyla(result: ITR2Result) -> dict[str, Any]:
    """Build Schedule CYLA from the typed 6-sub-basket CYLA result."""
    cyla = result.schedules.get("cyla")
    z = _ZERO
    hp_setoff = getattr(cyla, "hp_setoff", z) if cyla else z

    salary = max(z, result.salary_income)
    hp_inc = max(z, result.house_property_income)
    os_inc = max(z, result.other_sources_income)

    # Per-basket income and set-offs from the typed CYLA result
    stcg20_inc = _positive_val(cyla, "stcg20_income") if cyla else z
    stcg30_inc = _positive_val(cyla, "stcg30_income") if cyla else z
    stcg_app_inc = _positive_val(cyla, "stcg_app_income") if cyla else z
    stcg_dtaa_inc = _positive_val(cyla, "stcg_dtaa_income") if cyla else z
    ltcg125_inc = _positive_val(cyla, "ltcg125_income") if cyla else z
    ltcg_dtaa_inc = _positive_val(cyla, "ltcg_dtaa_income") if cyla else z

    stcg20_setoff = getattr(cyla, "stcg20_setoff", z) if cyla else z
    stcg30_setoff = getattr(cyla, "stcg30_setoff", z) if cyla else z
    stcg_app_setoff = getattr(cyla, "stcg_app_setoff", z) if cyla else z
    stcg_dtaa_setoff = getattr(cyla, "stcg_dtaa_setoff", z) if cyla else z
    ltcg125_setoff = getattr(cyla, "ltcg125_setoff", z) if cyla else z
    ltcg_dtaa_setoff = getattr(cyla, "ltcg_dtaa_setoff", z) if cyla else z

    hp_remaining = abs(min(z, result.house_property_income)) if result.house_property_income < z else z
    return {
        "Salary": {"IncCYLA": _inc_cyla(salary, z, z, salary)},
        "HP": {"IncCYLA": _inc_cyla_hp(hp_inc, z, hp_inc)},
        "STCG20Per": {"IncCYLA": _inc_cyla(stcg20_inc, z, z, max(z, stcg20_inc - stcg20_setoff))},
        "STCG30Per": {"IncCYLA": _inc_cyla(stcg30_inc, z, z, max(z, stcg30_inc - stcg30_setoff))},
        "STCGAppRate": {"IncCYLA": _inc_cyla(stcg_app_inc, z, z, max(z, stcg_app_inc - stcg_app_setoff))},
        "STCGDTAARate": {"IncCYLA": _inc_cyla(stcg_dtaa_inc, z, z, max(z, stcg_dtaa_inc - stcg_dtaa_setoff))},
        "LTCG12_5Per": {"IncCYLA": _inc_cyla(ltcg125_inc, z, z, max(z, ltcg125_inc - ltcg125_setoff))},
        "LTCGDTAARate": {"IncCYLA": _inc_cyla(ltcg_dtaa_inc, z, z, max(z, ltcg_dtaa_inc - ltcg_dtaa_setoff))},
        "IncOSDTAA": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "OthSrcExclRaceHorse": {"IncCYLA": _inc_cyla_os(os_inc, hp_setoff, max(z, os_inc - hp_setoff))},
        "OthSrcRaceHorse": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "LossRemAftSetOff": {
            "BalHPlossCurYrAftSetoff": _to_rupees(hp_remaining),
            "BalOthSrcLossNoRaceHorseAftSetoff": 0,
        },
        "TotalCurYr": {
            "TotHPlossCurYr": _to_rupees(hp_remaining),
            "TotOthSrcLossNoRaceHorse": 0,
        },
        "TotalLossSetOff": {
            "TotHPlossCurYrSetoff": _to_rupees(hp_setoff),
            "TotOthSrcLossNoRaceHorseSetoff": 0,
        },
    }


# ============================================================================
# Schedule BFLA (required)
# ============================================================================

def _schedule_bfla(result: ITR2Result) -> dict[str, Any]:
    """Build Schedule BFLA from the typed 6-sub-basket BFLA result."""
    bfla = result.schedules.get("bfla")
    z = _ZERO
    hp_bf_setoff = getattr(bfla, "hp_setoff", z) if bfla else z

    salary = max(z, result.salary_income)
    hp_inc = max(z, result.house_property_income)
    os_inc = max(z, result.other_sources_income)

    # Per-basket post-CYLA incomes and BF set-offs
    cyla = result.schedules.get("cyla")
    stcg20_cyla = _positive_val(cyla, "stcg20_remaining") if cyla else z
    stcg30_cyla = _positive_val(cyla, "stcg30_remaining") if cyla else z
    stcg_app_cyla = _positive_val(cyla, "stcg_app_remaining") if cyla else z
    stcg_dtaa_cyla = _positive_val(cyla, "stcg_dtaa_remaining") if cyla else z
    ltcg125_cyla = _positive_val(cyla, "ltcg125_remaining") if cyla else z
    ltcg_dtaa_cyla = _positive_val(cyla, "ltcg_dtaa_remaining") if cyla else z

    # Residual after BFLA
    stcg20_after = _positive_val(bfla, "stcg20_remaining") if bfla else stcg20_cyla
    stcg30_after = _positive_val(bfla, "stcg30_remaining") if bfla else stcg30_cyla
    stcg_app_after = _positive_val(bfla, "stcg_app_remaining") if bfla else stcg_app_cyla
    stcg_dtaa_after = _positive_val(bfla, "stcg_dtaa_remaining") if bfla else stcg_dtaa_cyla
    ltcg125_after = _positive_val(bfla, "ltcg125_remaining") if bfla else ltcg125_cyla
    ltcg_dtaa_after = _positive_val(bfla, "ltcg_dtaa_remaining") if bfla else ltcg_dtaa_cyla

    return {
        "Salary": {"IncBFLA": _inc_bfla_no_bf(salary, salary)},
        "HP": {"IncBFLA": _inc_bfla(hp_inc, hp_bf_setoff, max(z, hp_inc - hp_bf_setoff))},
        "STCG20Per": {"IncBFLA": _inc_bfla(stcg20_cyla, max(z, stcg20_cyla - stcg20_after), stcg20_after)},
        "STCG30Per": {"IncBFLA": _inc_bfla(stcg30_cyla, max(z, stcg30_cyla - stcg30_after), stcg30_after)},
        "STCGAppRate": {"IncBFLA": _inc_bfla(stcg_app_cyla, max(z, stcg_app_cyla - stcg_app_after), stcg_app_after)},
        "STCGDTAARate": {"IncBFLA": _inc_bfla(stcg_dtaa_cyla, max(z, stcg_dtaa_cyla - stcg_dtaa_after), stcg_dtaa_after)},
        "LTCG12_5Per": {"IncBFLA": _inc_bfla(ltcg125_cyla, max(z, ltcg125_cyla - ltcg125_after), ltcg125_after)},
        "LTCGDTAARate": {"IncBFLA": _inc_bfla(ltcg_dtaa_cyla, max(z, ltcg_dtaa_cyla - ltcg_dtaa_after), ltcg_dtaa_after)},
        "IncOSDTAA": {"IncBFLA": _inc_bfla_no_bf(z, z)},
        "OthSrcExclRaceHorse": {"IncBFLA": _inc_bfla_no_bf(os_inc, os_inc)},
        "OthSrcRaceHorse": {"IncBFLA": _inc_bfla(z, z, z)},
        "IncomeOfCurrYrAftCYLABFLA": _to_rupees(result.gross_total_income),
        "TotalBFLossSetOff": {"TotBFLossSetoff": _to_rupees(result.bfla_total_set_off)},
    }


# ============================================================================
# Schedule CFL
# ============================================================================

def _schedule_cfl(result: ITR2Result, input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Build Schedule CFL from typed carry-forward results and actual filing dates."""
    cfl_collections = result.schedules.get("cfl", [])
    flattened = [entry for collection in cfl_collections for entry in collection.entries]
    if not flattened:
        return None

    def summary(entries: list) -> dict[str, int]:
        return {
            "TotalHPPTILossCF": _to_rupees(sum((e.loss_remaining for e in entries if e.head in ("HP", "HouseProperty")), _ZERO)),
            "TotalSTCGPTILossCF": _to_rupees(sum((e.loss_remaining for e in entries if e.head in ("STCG", "CG")), _ZERO)),
            "TotalLTCGPTILossCF": _to_rupees(sum((e.loss_remaining for e in entries if e.head == "LTCG"), _ZERO)),
            "OthSrcLossRaceHorseCF": 0,
        }

    by_year: dict[str, list] = {}
    for entry in flattened:
        by_year.setdefault(entry.assessment_year_of_loss, []).append(entry)
    year_keys = {
        "2018-19": "LossCFFromPrev8thYearFromAY",
        "2019-20": "LossCFFromPrev7thYearFromAY",
        "2020-21": "LossCFFromPrev6thYearFromAY",
        "2021-22": "LossCFFromPrev5thYearFromAY",
        "2022-23": "LossCFFromPrev4thYearFromAY",
        "2023-24": "LossCFFromPrev3rdYearFromAY",
        "2024-25": "LossCFFromPrev2ndYearFromAY",
        "2025-26": "LossCFFromPrevYrToAY",
    }
    output: dict[str, Any] = {}
    filing_dates = {
        item.assessment_year: item.date_of_filing
        for item in input_data.bf_losses
        if item.date_of_filing is not None
    }
    for year, entries in by_year.items():
        key = year_keys.get(year)
        if key:
            detail: dict[str, Any] = summary(entries)
            if year in filing_dates:
                detail["DateOfFiling"] = _date(filing_dates[year])
            output[key] = {"CarryFwdLossDetail": detail}
    all_summary = summary(flattened)
    output["TotalOfBFLossesEarlierYrs"] = {"LossSummaryDetail": all_summary}
    output["TotalLossCFSummary"] = {"LossSummaryDetail": all_summary}
    return output


# ============================================================================
# Schedule S — Salary
# ============================================================================

def _schedule_s(result: ITR2Result, input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule S from real employer TDS1 entries."""
    source = input_data.salary_income
    if source is None:
        return None
    if not input_data.tds1_entries:
        raise ValueError("Salary income present but no TDS1 employer entries provided")
    if len(input_data.employer_filing_details) != len(input_data.tds1_entries):
        raise ValueError("Schedule S requires one employer_filing_details row per TDS1 employer")
    employers = []
    gross_total = _ZERO
    for entry, detail in zip(input_data.tds1_entries, input_data.employer_filing_details):
        if not entry.employer_name or not entry.employer_tan:
            raise ValueError("Schedule S requires employer name and TAN")
        if detail.employer_tan != entry.employer_tan or detail.employer_name != entry.employer_name:
            raise ValueError("Schedule S employer filing details must match TDS1 identity")
        gross = entry.income_chargeable
        gross_total += gross
        employers.append({
            "NameOfEmployer": entry.employer_name,
            "NatureOfEmployment": detail.nature_of_employment,
            "AddressDetail": {"AddrDetail": detail.address_detail, "CityOrTownOrDistrict": detail.city_or_town_or_district, "StateCode": detail.state_code},
            "TANofEmployer": entry.employer_tan,
            "Salarys": {
                "GrossSalary": _to_rupees(gross),
                "Salary": _to_rupees(gross),
                "NatureOfSalary": {"OthersIncDtls": []},
                "ValueOfPerquisites": 0,
                "NatureOfPerquisites": {"OthersIncDtls": []},
                "ProfitsinLieuOfSalary": 0,
                "IncomeNotified89A": 0,
                "IncomeNotifiedOther89A": 0,
            },
        })
    exempt_10 = source.hra_exempt_amount + source.lta_exempt_amount
    net_salary = gross_total - exempt_10
    std_deduction = max(_ZERO, net_salary - result.salary_income - source.entertainment_allowance - source.professional_tax_paid)
    return {
        "Salaries": employers,
        "TotalGrossSalary": _to_rupees(gross_total),
        "AllwncExemptUs10": {"AllwncExemptUs10Dtls": []},
        "AllwncExtentExemptUs10": _to_rupees(exempt_10),
        "NetSalary": _to_rupees(net_salary),
        "DeductionUS16": _to_rupees(std_deduction + source.entertainment_allowance + source.professional_tax_paid),
        "DeductionUnderSection16ia": _to_rupees(std_deduction),
        "EntertainmntalwncUs16ii": _to_rupees(source.entertainment_allowance),
        "ProfessionalTaxUs16iii": _to_rupees(source.professional_tax_paid),
        "Increliefus89A": 0,
        "Section10_13A": {
            "Placeofwork": "2",
            "ActlHRARecv": 0,
            "ActlRentPaid": 0,
            "DtlsSalUsSec171": 0,
            "ActlRentPaid10Per": 0,
            "Sal40Or50Per": 0,
            "EligbleExmpAllwncUs13A": _to_rupees(source.hra_exempt_amount),
        },
        "TotIncUnderHeadSalaries": _to_rupees(result.salary_income),
    }


# ============================================================================
# Schedule HP — House Property
# ============================================================================

def _schedule_hp(result: ITR2Result, input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule HP from real house-property inputs."""
    sources = ([input_data.house_property_income] if input_data.house_property_income else []) + list(input_data.house_properties)
    if not sources:
        return None
    if len(input_data.property_filing_details) != len(sources):
        raise ValueError("Schedule HP requires one property_filing_details row per property")
    props = []
    hp_results = result.schedules.get("hp", [])
    for idx, (source, hp_res, detail) in enumerate(zip(sources, hp_results, input_data.property_filing_details), 1):
        ptype = source.property_type.value
        alv = max(_ZERO, source.annual_rent_received - source.municipal_taxes_paid)
        interest = hp_res.interest_deduction if hasattr(hp_res, "interest_deduction") else source.home_loan_interest_paid
        std_ded = alv * Decimal("0.3") if ptype != "S" else _ZERO
        income = alv - std_ded - interest
        address: dict[str, Any] = {
            "AddrDetail": detail.address_detail,
            "CityOrTownOrDistrict": detail.city_or_town_or_district,
            "StateCode": detail.state_code,
            "CountryCode": detail.country_code,
        }
        if detail.pin_code:
            address["PinCode"] = int(detail.pin_code)
        if detail.zip_code:
            address["ZipCode"] = detail.zip_code
        props.append({
            "HPSNo": idx,
            "AddressDetailWithZipCode": address,
            "PropertyOwner": detail.property_owner,
            "PropCoOwnedFlg": "YES" if detail.co_owned else "NO",
            "AsseseeShareProperty": float(detail.assessee_share_percent),
            "ifLetOut": "S" if ptype == "S" else "L",
            "Rentdetails": {
                "AnnualLetableValue": _to_rupees(source.annual_rent_received),
                "RentNotRealized": 0,
                "LocalTaxes": _to_rupees(source.municipal_taxes_paid),
                "TotalUnrealizedAndTax": 0,
                "BalanceALV": _to_rupees(alv),
                "AnnualOfPropOwned": _to_rupees(alv),
                "ArrearsUnrealizedRentRcvd": 0,
                "ThirtyPercentOfBalance": _to_rupees(std_ded),
                "IntOnBorwCap": _to_rupees(interest),
                "Section24B": {"Section24BDtls": [], "TotalInterestUs24B": _to_rupees(interest)},
                "TotalDeduct": _to_rupees(std_ded + interest),
                "IncomeOfHP": _to_rupees(income),
            },
        })
    return {
        "PropertyDetails": props,
        "PassThroghIncome": 0,
        "TotalIncomeChargeableUnHP": _to_rupees(result.house_property_income),
    }


# ============================================================================
# Schedule OS — Other Sources
# ============================================================================

def _schedule_os(result: ITR2Result, input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule OS from source-income components."""
    source = input_data.other_sources_income
    if source is None and not input_data.si_entries:
        return None
    block: dict[str, Any] = {
        "GrossIncChrgblTaxAtAppRate": 0,
        "DividendGross": 0,
        "DividendOthThan22e": 0,
        "Dividend22e": 0,
        "Dividend22f": 0,
        "InterestGross": 0,
        "IntrstFrmSavingBank": 0,
        "IntrstFrmTermDeposit": 0,
        "IntrstFrmIncmTaxRefund": 0,
        "NatofPassThrghIncome": 0,
        "IntrstSec10XIFirstProviso": 0,
        "IntrstSec10XISecondProviso": 0,
        "IntrstSec10XIIFirstProviso": 0,
        "IntrstSec10XIISecondProviso": 0,
        "IntrstFrmOthers": 0,
        "RentFromMachPlantBldgs": 0,
        "Tot562x": 0,
        "Aggrtvaluewithoutcons562x": 0,
        "Immovpropwithoutcons562x": 0,
        "Immovpropinadeqcons562x": 0,
        "Anyotherpropwithoutcons562x": 0,
        "Anyotherpropinadeqcons562x": 0,
        "FamilyPension": 0,
        "IncomeNotified89AOS": 0,
        "IncomeNotified89ATypeOS": [],
        "IncomeNotifiedOther89AOS": 0,
        "IncomeNotifiedPrYr89AOS": 0,
        "AnyOtherIncome": 0,
        "OthersInc": {"OthersIncDtls": []},
        "IncChargeableSpecialRates": 0,
        "LtryPzzlChrgblUs115BB": 0,
        "IncChrgblUs115BBJ": 0,
        "IncChrgblUs115BBE": 0,
        "CashCreditsUs68": 0,
        "UnExplndInvstmntsUs69": 0,
        "SumRecdPrYrBusTRU562xii": 0,
        "SumRecdPrYrLifIns562xiii": 0,
        "UnExplndMoneyUs69A": 0,
        "UnDsclsdInvstmntsUs69B": 0,
        "UnExplndExpndtrUs69C": 0,
        "AmtBrwdRepaidOnHundiUs69D": 0,
        "TaxAccumulatedBalRecPF": {"TotalIncomeBenefit": 0, "TotalTaxBenefit": 0},
        "OthersGross": 0,
        "OthersGrossDtls": [],
        "PassThrIncOSChrgblSplRate": 0,
        "PTIOthersGrossDtls": [],
        "IncChargblSplRateOS": {"TotalAmtTaxUsDTAASchOs": 0},
        "Deductions": {
            "DeductionUs57iia": 0,
            "Depreciation": 0,
            "Expenses": 0,
            "IntExp57": 0,
            "TotDeductions": 0,
            "UsrIntExp57": 0,
        },
        "AmtNotDeductibleUs58": 0,
        "ProfitChargTaxUs59": 0,
        "Increliefus89AOS": 0,
        "BalanceNoRaceHorse": _to_rupees(result.other_sources_income),
    }
    if source:
        block["DividendGross"] = _to_rupees(source.dividend_income)
        block["DividendOthThan22e"] = _to_rupees(source.dividend_income)
        block["InterestGross"] = _to_rupees(source.savings_bank_interest + source.fixed_deposit_interest + source.interest_on_it_refund)
        block["IntrstFrmSavingBank"] = _to_rupees(source.savings_bank_interest)
        block["IntrstFrmTermDeposit"] = _to_rupees(source.fixed_deposit_interest)
        block["IntrstFrmIncmTaxRefund"] = _to_rupees(source.interest_on_it_refund)
        block["FamilyPension"] = _to_rupees(source.family_pension_received)
        block["Tot562x"] = _to_rupees(source.income_56_2_x)
    for entry in input_data.si_entries:
        if entry.section == "115BB":
            block["LtryPzzlChrgblUs115BB"] += _to_rupees(entry.gross_income)
        elif entry.section == "115BBJ":
            block["IncChrgblUs115BBJ"] += _to_rupees(entry.gross_income)
        elif entry.section == "115BBE":
            block["IncChrgblUs115BBE"] += _to_rupees(entry.gross_income)
    gift = input_data.os_gift_breakdown
    if gift is not None:
        block["Aggrtvaluewithoutcons562x"] = _to_rupees(gift.aggregate_without_consideration)
        block["Immovpropwithoutcons562x"] = _to_rupees(gift.immovable_property_without_consideration)
        block["Immovpropinadeqcons562x"] = _to_rupees(gift.immovable_property_inadequate_consideration)
        block["Anyotherpropwithoutcons562x"] = _to_rupees(gift.other_property_without_consideration)
        block["Anyotherpropinadeqcons562x"] = _to_rupees(gift.other_property_inadequate_consideration)
    if input_data.os_pf_income_benefit or input_data.os_pf_tax_benefit:
        block["TaxAccumulatedBalRecPF"] = {
            "TotalIncomeBenefit": _to_rupees(input_data.os_pf_income_benefit),
            "TotalTaxBenefit": _to_rupees(input_data.os_pf_tax_benefit),
        }
    return {
        "DividendDTAA": _date_range(),
        "DividendIncUs115A1aA": _date_range(),
        "DividendIncUs115A1ai": _date_range(),
        "DividendIncUs115AC": _date_range(),
        "DividendIncUs115ACA": _date_range(),
        "DividendIncUs115AD1i": _date_range(),
        "DividendIncUs115BBDA": _date_range(),
        "DividendIncUs115BBDAaiii": _date_range(),
        "IncChargeable": 0,
        "IncFrmLottery": _date_range(),
        "IncFrmOnGames": _date_range(),
        "IncFromOwnHorse": {
            "Receipts": 0,
            "DeductSec57": 0,
            "AmtNotDeductibleUs58": 0,
            "ProfitChargTaxUs59": 0,
            "BalanceOwnRaceHorse": 0,
        },
        "IncOthThanOwnRaceHorse": block,
        "NOT89A": _date_range(),
        "TotOthSrcNoRaceHorse": _to_rupees(result.other_sources_income),
    }


# ============================================================================
# Schedule CG — Capital Gains
# ============================================================================

# Asset types with no dedicated Schedule CG block of their own -- they fall
# into the generic "sale of assets other than [111A/112A/land-building/
# FII-115AD]" catch-all the official form describes at Schedule CG items 5
# (STCG) and 8 (LTCG). Confirmed against the official form text
# (Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-2-2026-Eng.pdf,
# extracted to ITR-2-2026-Eng_extracted_text.txt): item 5/8 titles read
# "From sale of assets other than at A1 or A2 or A3 or A4 above" / "From
# sale of assets where B1 to B7 above are not applicable" -- i.e. this is
# the genuine generic bucket, not a mislabeled unquoted-shares-only field.
_GENERIC_OTHER_ASSET_TYPES = frozenset({
    "unlisted_shares",
    "listed_security",
    "debt_mutual_fund",
    "specified_mutual_fund_50aa",
    "market_linked_debenture_50aa",
    "bonds_debentures",
    "depreciable_asset",
    "jewellery",
    "foreign_asset",
    "other",
})


def _other_assets_block(
    transactions: list,
    is_long_term: bool,
) -> dict[str, Any]:
    """Aggregate the generic "other assets" bucket for Schedule CG item 5/8.

    Both the STCG (``EquityOrUnitSec94Type``, ``SaleOnOtherAssets``) and
    LTCG (``EquityOrUnitSec54Type``, ``SaleofAssetNADtls.SaleofAssetNA``)
    variants share this structure: consideration/cost aggregated across
    every ``_GENERIC_OTHER_ASSET_TYPES`` transaction of the matching
    holding period, split into "unquoted shares" (``unlisted_shares`` --
    section 50CA deeming applies) versus "assets other than unquoted
    shares" (every other generic category) sub-totals. Unlike land/building
    (section 50C, a 110%-tolerance deemed-consideration rule), section 50CA
    is a straight higher-of-consideration-or-FMV comparison with no
    tolerance band -- see ``deemed_consideration_50ca``'s docstring.

    Indexation does not apply to this bucket at all (confirmed by the
    official form's item 5b/8b, which only ever asks for "cost of
    acquisition without indexation" here -- the dual indexed/non-indexed
    track is specific to land/building's own section 112(1)(a) transitional
    provision, not this generic bucket), so only the non-indexed cost
    fields are used, matching what the calculator's own ``stcg_other``/
    ``ltcg_other`` aggregate already does.
    """
    from app.engine.schedules.capital_gains import _is_short_term, deemed_consideration_50ca

    unq_consideration = _ZERO
    unq_fmv = _ZERO
    oth_consideration = _ZERO
    total_cost = _ZERO
    total_improvement = _ZERO
    total_expenditure = _ZERO

    for tx in transactions or []:
        asset_type = tx.asset_type.value if hasattr(tx.asset_type, "value") else tx.asset_type
        if asset_type not in _GENERIC_OTHER_ASSET_TYPES:
            continue
        is_short = True
        if tx.date_of_acquisition is not None:
            is_short = _is_short_term(asset_type, tx.date_of_acquisition, tx.date_of_transfer)
        elif tx.explicit_long_term is not None:
            is_short = not tx.explicit_long_term
        wanted_short = not is_long_term
        if is_short != wanted_short:
            continue

        total_cost += tx.cost_of_acquisition
        total_improvement += tx.improvement_cost
        total_expenditure += tx.expenditure_on_transfer
        if asset_type == "unlisted_shares":
            unq_consideration += tx.full_consideration
            unq_fmv += tx.fair_market_value_50ca or _ZERO
        else:
            oth_consideration += tx.full_consideration

    unq_deemed = deemed_consideration_50ca(unq_consideration, unq_fmv)
    full_consideration = unq_deemed + oth_consideration
    total_ded = total_cost + total_improvement + total_expenditure
    balance = full_consideration - total_ded

    return {
        "FullValueConsdRecvUnqshr": _to_rupees(unq_consideration),
        "FairMrktValueUnqshr": _to_rupees(unq_fmv),
        "FullValueConsdSec50CA": _to_rupees(unq_deemed),
        "FullValueConsdOthUnqshr": _to_rupees(oth_consideration),
        "FullConsideration": _to_rupees(full_consideration),
        "DeductSec48": {
            "AquisitCost": _to_rupees(total_cost),
            "ImproveCost": _to_rupees(total_improvement),
            "ExpOnTrans": _to_rupees(total_expenditure),
            "TotalDedn": _to_rupees(total_ded),
        },
        "BalanceCG": _to_rupees(balance),
        **(
            {"LossSec94of7Or94of8": 0}
            if not is_long_term
            else {"DeductionUs54F": 0}
        ),
        "CapgainonAssets": _to_rupees(balance),
    }


def _schedule_cg(input_data: ITR2Input, result: ITR2Result) -> Optional[dict[str, Any]]:
    """Serialize Schedule CG from actual classified transactions."""
    if not input_data.cg_transactions and not input_data.cg_112a_scrips and not input_data.vda_transactions:
        return None
    cg = result.schedules.get("cg")
    z = _ZERO
    stcg = getattr(cg, "stcg", None) if cg else None
    ltcg = getattr(cg, "ltcg", None) if cg else None
    post_loss = result.schedules.get("post_loss_cg", {})

    # Land/building STCG rows
    stcg_land_rows = []
    for asset in (getattr(stcg, "land_building", []) if stcg else []):
        stcg_land_rows.append(_cg_land_building_row_stcg(asset))
    # Land/building LTCG rows
    ltcg_land_rows = []
    for asset in (getattr(ltcg, "land_building", []) if ltcg else []):
        ltcg_land_rows.append(_cg_land_building_row_ltcg(asset))

    # 111A equity rows
    equity_111a_rows = []
    for tx in input_data.cg_transactions:
        if tx.asset_type.value in ("listed_equity_111a", "equity_oriented_fund_111a"):
            gain = tx.full_consideration - tx.cost_of_acquisition - tx.expenditure_on_transfer
            equity_111a_rows.append({
                "MFSectionCode": "1A",
                "EquityMFonSTTDtls": {
                    "FullConsideration": _to_rupees(tx.full_consideration),
                    "DeductSec48": {
                        "AquisitCost": _to_rupees(tx.cost_of_acquisition),
                        "ImproveCost": _to_rupees(tx.improvement_cost),
                        "ExpOnTrans": _to_rupees(tx.expenditure_on_transfer),
                        "TotalDedn": _to_rupees(tx.cost_of_acquisition + tx.improvement_cost + tx.expenditure_on_transfer),
                    },
                    "BalanceCG": _to_rupees(gain),
                    "LossSec94of7Or94of8": 0,
                    "CapgainonAssets": _to_rupees(gain),
                },
            })

    z6 = _z6()
    exemptions = getattr(cg, "exemptions", None) if cg else None
    total_54 = getattr(exemptions, "section_54", z) if exemptions else z
    total_54b = getattr(exemptions, "section_54b", z) if exemptions else z
    total_54ec = getattr(exemptions, "section_54ec", z) if exemptions else z
    total_54f = getattr(exemptions, "section_54f", z) if exemptions else z
    total_exempt = getattr(exemptions, "total_exemption", z) if exemptions else z

    stcg_block: dict[str, Any] = {
        "SaleofLandBuild": {"SaleofLandBuildDtls": stcg_land_rows},
        "EquityMFonSTT": equity_111a_rows,
        "NRITransacSec48Dtl": {"NRItaxSTTPaid": 0, "NRItaxSTTNotPaid": 0},
        "NRISecur115AD": _equity_or_unit_sec94(),
        "SaleOnOtherAssets": _other_assets_block(input_data.cg_transactions, is_long_term=False),
        "UnutilizedStcgFlag": "N",
        "AmtDeemedStcg": 0,
        "TotalAmtDeemedStcg": 0,
        "PassThrIncNatureSTCG": 0,
        "PassThrIncNatureSTCG20Per": 0,
        "PassThrIncNatureSTCG30Per": 0,
        "PassThrIncNatureSTCGAppRate": 0,
        "TotalAmtNotTaxUsDTAAStcg": 0,
        "TotalAmtTaxUsDTAAStcg": 0,
        "CapitalLossBuyBackShares": {"CapitalLossBuyBackSharesDtls": [], "TotalCapitalLossBuyBackShares": 0},
        "TotalSTCG": _to_rupees(getattr(stcg, "total_stcg", z) if stcg else z),
    }
    ltcg_block: dict[str, Any] = {
        "SaleofLandBuild": {"SaleofLandBuildDtls": ltcg_land_rows, "TotalExcessTax": 0, "TotalLTCGImmblPrprty": _to_rupees(sum((r["LTCGonImmvblPrprty"] for r in ltcg_land_rows), _ZERO))},
        "Proviso112Applicable": [],
        "SaleOfEquityShareUs112A": _equity_share_112a(),
        "NRIProvisoSec48": _nri_proviso_48(),
        "NRISaleOfEquityShareUs112A": _equity_share_112a(),
        "NRISaleofForeignAsset": _nri_foreign_asset(),
        "SaleofAssetNADtls": {"SaleofAssetNA": _other_assets_block(input_data.cg_transactions, is_long_term=True)},
        "UnutilizedLtcgFlag": "N",
        "AmtDeemedLtcg": 0,
        "TotalAmtDeemedLtcg": 0,
        "PassThrIncNatureLTCG": 0,
        "PassThrIncNatureLTCGUs112A12_5Per": 0,
        "PassThrIncNatureLTCG12_5Per": 0,
        "TotalAmtNotTaxUsDTAALtcg": 0,
        "CapitalLossBuyBackShares": {"TotalCapitalLossBuyBackShares": 0},
        "TotalAmtTaxUsDTAALtcg": 0,
        "TotalLTCG": _to_rupees(getattr(ltcg, "total_ltcg", z) if ltcg else z),
    }
    total_stcg = _to_rupees(getattr(stcg, "total_stcg", z) if stcg else z)
    total_ltcg = _to_rupees(getattr(ltcg, "total_ltcg", z) if ltcg else z)
    total_cg = _to_rupees(result.capital_gains_income)
    vda_inc = _to_rupees(result.vda_income)
    return {
        "ShortTermCapGainFor23": stcg_block,
        "LongTermCapGain23": ltcg_block,
        "DeducClaimInfo": {
            "DeducClaimDtlsUs115F": [],
            "DeducClaimDtlsUs54": [],
            "DeducClaimDtlsUs54B": [],
            "DeducClaimDtlsUs54EC": [],
            "DeducClaimDtlsUs54F": [],
            "TotDeductClaim": _to_rupees(total_exempt),
        },
        "CurrYrLosses": {
            "InLossSetOff": dict(z6),
            "InStcg20Per": {"CurrYearIncome": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "CurrYrCapGain": 0},
            "InStcg30Per": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "CurrYrCapGain": 0},
            "InStcgAppRate": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffDTAARate": 0, "CurrYrCapGain": 0},
            "InStcgDTAARate": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "CurrYrCapGain": 0},
            "InLtcg12_5Per": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOffDTAARate": 0, "CurrYrCapGain": 0},
            "InLtcgDTAARate": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOff12_5Per": 0, "CurrYrCapGain": 0},
            "TotLossSetOff": dict(z6),
            "LossRemainSetOff": dict(z6),
        },
        "IncmFromVDATrnsf": vda_inc,
        "AccruOrRecOfCG": _accrued_cg(),
        "SumOfCGIncm": total_cg,
        "TotScheduleCGFor23": total_cg,
    }


def _cg_land_building_row_stcg(asset: Any) -> dict[str, Any]:
    """Build one Schedule CG STCG SaleofLandBuildDtls row.

    Field names match the official AY 2026-27 schema
    (``ShortTermCapGainFor23.SaleofLandBuild.SaleofLandBuildDtls`` items)
    exactly -- the previous version used an entirely different, wrong key
    set (``FullValueConsdRecvUnqshr``/nested ``DeductSec48``/``BalanceCG``,
    which is actually the shape for the *unquoted-shares/other-assets*
    block, not land/building) that would have made any land/building STCG
    submission schema-invalid. ``asset.balance``/``asset.total_deductions``
    are read directly from what ``compute_stcg()`` already computed per
    asset, so this row can never disagree with the aggregate total.
    """
    stamp_value = getattr(asset, "stamp_duty_value", _ZERO) or _ZERO
    deemed = deemed_consideration_50c(asset.full_consideration, stamp_value)
    return {
        "DateofPurchase": asset.date_of_acquisition or "",
        "DateofSale": asset.date_of_transfer,
        "FullConsideration": _to_rupees(asset.full_consideration),
        "PropertyValuation": _to_rupees(stamp_value),
        "FullConsideration50C": _to_rupees(deemed),
        "AquisitCost": _to_rupees(asset.acquisition_cost),
        "ImproveCost": _to_rupees(asset.improvement_cost),
        "ExpOnTrans": _to_rupees(asset.expenditure_on_transfer),
        "TotalDedn": _to_rupees(asset.total_deductions),
        "Balance": _to_rupees(asset.balance),
        "DeductionUs54B": 0,
        "STCGonImmvblPrprty": _to_rupees(asset.balance),
    }


def _cg_land_building_row_ltcg(asset: Any) -> dict[str, Any]:
    """Build one Schedule CG LTCG SaleofLandBuildDtls row.

    Field names match ``LongTermCapGain23.SaleofLandBuild.SaleofLandBuildDtls``
    exactly -- see ``_cg_land_building_row_stcg``'s docstring for why the
    previous shared implementation was wrong for both STCG and LTCG.

    The official schema additionally carries a second, indexed-cost-basis
    total/balance/tax-comparison track (``AquisitCostIndex``,
    ``TotalDednForEiB``, ``BalanceForEiB``, ``TaxSec1121aiiB``,
    ``TaxSec1121a``, ``ExcessAmtSec1121a`` -- the section 112(1)(a) second
    proviso comparison for residents who acquired before 23-Jul-2024,
    protecting against a tax increase from the 2024 indexation-removal
    change) that this function does not populate -- none of those fields
    are in the schema's ``required`` list, so omitting them keeps the JSON
    schema-valid; only ``AquisitCostIndex`` is required and is always
    emitted. See ``compute_ltcg()``'s docstring note for why the dual
    tax-comparison itself is a separate, not-yet-implemented finding.
    """
    stamp_value = getattr(asset, "stamp_duty_value", _ZERO) or _ZERO
    deemed = deemed_consideration_50c(asset.full_consideration, stamp_value)
    return {
        "DateofPurchase": asset.date_of_acquisition or "",
        "DateofSale": asset.date_of_transfer,
        "FullConsideration": _to_rupees(asset.full_consideration),
        "PropertyValuation": _to_rupees(stamp_value),
        "FullConsideration50C": _to_rupees(deemed),
        "AquisitCost": _to_rupees(asset.acquisition_cost),
        "AquisitCostIndex": _to_rupees(asset.indexed_acquisition_cost),
        # Unlike STCG's flat ImproveCost, the LTCG schema's CostOfImprovements
        # is a nested object with an (unused here -- no year-by-year
        # breakdown captured) per-improvement detail array plus indexed/
        # non-indexed totals.
        "CostOfImprovements": {
            "CostOfImprovementsDtls": [],
            "TotalImprovecost": _to_rupees(asset.improvement_cost),
            "TotalindexImprovecost": _to_rupees(asset.indexed_improvement_cost),
        },
        "ExpOnTrans": _to_rupees(asset.expenditure_on_transfer),
        "TotalDedn": _to_rupees(asset.total_deductions),
        "Balance": _to_rupees(asset.balance),
        # Like CostOfImprovements, this is a nested exemption-detail block
        # (ExemptionOrDednUs54SaleLandType), not a flat integer.
        # ExemptionOrDednUs54Dtls is optional (no per-claim detail
        # available here); only ExemptionGrandTotal is schema-required.
        "ExemptionOrDednUs54": {"ExemptionGrandTotal": 0},
        "LTCGonImmvblPrprty": _to_rupees(asset.balance),
    }


def _equity_or_unit_sec94() -> dict[str, int]:
    """Return the statutory zero-valued EquityOrUnitSec94Type block."""
    return {
        "FullValueConsdRecvUnqshr": 0,
        "FairMrktValueUnqshr": 0,
        "FullValueConsdSec50CA": 0,
        "FullValueConsdOthUnqshr": 0,
        "FullConsideration": 0,
        "DeductSec48": {"AquisitCost": 0, "ImproveCost": 0, "ExpOnTrans": 0, "TotalDedn": 0},
        "BalanceCG": 0,
        "LossSec94of7Or94of8": 0,
        "CapgainonAssets": 0,
    }


def _equity_share_112a() -> dict[str, int]:
    return {"BalanceCG": 0, "DeductionUs54F": 0, "CapgainonAssets": 0}


def _nri_proviso_48() -> dict[str, int]:
    return {"LTCGWithoutBenefit": 0, "DeductionUs54F": 0, "BalanceCG": 0}


def _nri_foreign_asset() -> dict[str, int]:
    return {"SaleonSpecAsset": 0, "DednSpecAssetus115": 0, "BalonSpeciAsset": 0}


def _accrued_cg() -> dict[str, Any]:
    dr = _date_range()
    return {
        "ShortTermUnder20Per": dr,
        "ShortTermUnder30Per": dr,
        "ShortTermUnderAppRate": dr,
        "ShortTermUnderDTAARate": dr,
        "LongTermUnder12_5Per": dr,
        "LongTermUnderDTAARate": dr,
    }


# ============================================================================
# Schedule 112A
# ============================================================================

def _schedule_112a(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize all section 112A scrip rows with signed balances."""
    source_rows: list[dict[str, Any]] = []
    for item in input_data.cg_112a_scrips:
        source_rows.append({
            "is_before": item.is_before_31jan2018,
            "isin": item.isin_code,
            "name": item.share_unit_name,
            "quantity": item.num_shares_units,
            "price": item.sale_price_per_share,
            "sale": item.total_sale_value,
            "cost": item.cost_acq_without_index,
            "fmv_per_unit": item.fmv_per_share,
            "fmv": item.total_fmv,
            "expense": item.expenditure_on_transfer,
            "balance": item.balance,
        })
    eligible_types = {"listed_equity_112a", "equity_oriented_fund_112a", "business_trust_unit_112a"}
    for tx in input_data.cg_transactions:
        if tx.asset_type.value not in eligible_types:
            continue
        quantity = tx.quantity or Decimal("1")
        price = tx.sale_price_per_unit if tx.sale_price_per_unit is not None else tx.full_consideration / quantity
        total_fmv = tx.fair_market_value_jan2018 or _ZERO
        source_rows.append({
            "is_before": tx.date_of_acquisition is not None and tx.date_of_acquisition < date(2018, 2, 1),
            "isin": tx.isin_code or "INNOTREQUIRD",
            "name": tx.description or "Capital asset",
            "quantity": quantity,
            "price": price,
            "sale": tx.full_consideration,
            "cost": tx.cost_of_acquisition,
            "fmv_per_unit": total_fmv / quantity if quantity else _ZERO,
            "fmv": total_fmv,
            "expense": tx.expenditure_on_transfer,
            "balance": None,
        })
    if not source_rows:
        return None
    rows = []
    for item in source_rows:
        deemed_cost = item["cost"]
        if item["is_before"]:
            deemed_cost = max(item["cost"], min(item["fmv"], item["sale"]))
        deductions = deemed_cost + item["expense"]
        balance = item["balance"] if item["balance"] is not None else item["sale"] - deductions
        rows.append({
            "ShareOnOrBefore": "BE" if item["is_before"] else "AE",
            "ISINCode": item["isin"],
            "ShareUnitName": item["name"],
            "NumSharesUnits": float(item["quantity"]),
            "SalePricePerShareUnit": float(item["price"]),
            "TotSaleValue": _to_rupees(item["sale"]),
            "CostAcqWithoutIndx": _to_rupees(item["cost"]),
            "AcquisitionCost": float(deemed_cost),
            "LTCGBeforelowerB1B2": _to_rupees(max(_ZERO, item["sale"] - item["cost"])),
            "FairMktValuePerShareunit": float(item["fmv_per_unit"]),
            "TotFairMktValueCapAst": _to_rupees(item["fmv"]),
            "ExpExclCnctTransfer": float(item["expense"]),
            "TotalDeductions": _to_rupees(deductions),
            "Balance": _to_rupees(balance),
        })
    sale = sum(r["TotSaleValue"] for r in rows)
    raw_cost = sum(r["CostAcqWithoutIndx"] for r in rows)
    acquisition = sum(Decimal(str(r["AcquisitionCost"])) for r in rows)
    fmv = sum(r["TotFairMktValueCapAst"] for r in rows)
    expenses = sum(Decimal(str(r["ExpExclCnctTransfer"])) for r in rows)
    deductions = sum(r["TotalDeductions"] for r in rows)
    balance = sum(r["Balance"] for r in rows)
    return {
        "Schedule112ADtls": rows,
        "SaleValue112A": sale,
        "CostAcqWithoutIndx112A": raw_cost,
        "AcquisitionCost112A": _to_rupees(acquisition),
        "LTCGBeforelowerB1B2112A": max(0, sale - raw_cost),
        "FairMktValueCapAst112A": fmv,
        "ExpExclCnctTransfer112A": _to_rupees(expenses),
        "Deductions112A": deductions,
        "Balance112A": balance,
        "TotalBalance112A": balance,
    }


# ============================================================================
# Schedule VDA
# ============================================================================

def _schedule_vda(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize every VDA transfer and its row total."""
    if not input_data.vda_transactions:
        return None
    rows = []
    for item in input_data.vda_transactions:
        income = item.income_from_vda if item.income_from_vda is not None else max(_ZERO, item.consideration_received - item.acquisition_cost)
        rows.append({
            "DateofAcquisition": _date(item.date_of_acquisition),
            "DateofTransfer": _date(item.date_of_transfer),
            "HeadUndIncTaxed": "CG",
            "AcquisitionCost": _to_rupees(item.acquisition_cost),
            "ConsidReceived": _to_rupees(item.consideration_received),
            "IncomeFromVDA": _to_rupees(income),
        })
    return {"ScheduleVDADtls": rows, "TotIncCapGain": sum(r["IncomeFromVDA"] for r in rows)}


# ============================================================================
# Schedule VIA — Chapter VI-A deductions
# ============================================================================

def _schedule_via(result: ITR2Result) -> Optional[dict[str, Any]]:
    """Serialize Schedule VIA with per-section breakdown from deduction schedule."""
    if result.deductions_total <= 0:
        return None
    ded = result.schedules.get("deductions")
    breakdown = getattr(ded, "breakdown", {}) if ded else {}
    details = getattr(ded, "section_details", {}) if ded else {}

    # Map engine breakdown keys to official Schedule VIA section codes
    via_section_map = {
        "80C": "A1",
        "80CCC": "A2",
        "80CCD(1)": "A3a",
        "80CCD(1B)": "A4",
        "80CCD(2)": "A5",
        "80CCH": "A8",
        "80D": "B",
        "80DD": "D",
        "80DDB": "E",
        "80U": "G",
        "80TTA": "G1a",
        "80TTB": "G1b",
        "80E": "H",
        "80EE": "EE",
        "80EEA": "EEA",
        "80EEB": "EEB",
        "80G": "G",
        "80GG": "GG",
        "80GGA": "GGA",
        "80GGC": "GGC",
        "80-IA": "C1",
        "80-IB": "C2",
        "80-IC": "C3",
        "10AA": "A6",
        "80RA": "RA",
    }
    via_entries: list[dict[str, Any]] = []
    for key, amount in breakdown.items():
        code = via_section_map.get(key, "OTH")
        via_entries.append({
            "Section": code,
            "Amount": _to_rupees(amount),
        })

    return {
        "UsrDeductUndChapVIA": {"TotalChapVIADeductions": _to_rupees(result.deductions_total)},
        "DeductUndChapVIA": {"TotalChapVIADeductions": _to_rupees(result.deductions_total)},
        "DeductUndChapVIAList": via_entries,
    }


# ============================================================================
# Schedule SI — Special Rate Incomes
# ============================================================================

def _schedule_si(result: ITR2Result) -> Optional[dict[str, Any]]:
    """Serialize Schedule SI from actual special-rate computation."""
    si = result.schedules.get("si")
    if si is None or si.total_special_rate_income <= 0:
        return None
    # Map internal section codes to official SplCodeRateTax SecCode values
    section_code_map = {
        "111A": "1A",
        "112": "21",
        "112A": "2A",
        "115BB": "5BB",
        "115BBA": "5BBA",
        "115BBE": "5BBE",
        "115BBF": "5BBF",
        "115BBG": "5BBG",
        "115BBH": "5BBH",
        "115BBJ": "5BBJ",
    }
    rows = []
    for entry in si.entries:
        if entry.taxable_income <= 0 and entry.tax_amount <= 0:
            continue
        if entry.section == "111":
            # Section 111 (accumulated PF) is taxed at slab rate, not a
            # genuine flat special rate -- compute_111() correctly models
            # it as a 0%-rate SI dispatch entry purely so its income is
            # included in GTI and excluded from the ordinary slab basket
            # (see calculators/itr2.py's special_rate_income_for_slab). The
            # official schema's SplRatePercent enum has no 0 value, so this
            # entry belongs only in Schedule OS's TaxAccumulatedBalRecPF
            # (already wired in _schedule_os()), never in ScheduleSI's
            # SplCodeRateTax rows.
            continue
        code = section_code_map.get(entry.section, "1")
        rows.append({
            "SecCode": code,
            "SplRatePercent": float(entry.tax_rate_pct) if entry.tax_rate_pct else 0,
            "SplRateInc": _to_rupees(entry.taxable_income),
            "SplRateIncTax": _to_rupees(entry.tax_amount),
        })
    return {
        "SplCodeRateTax": rows,
        "TotSplRateInc": _to_rupees(si.total_special_rate_income),
        "TotSplRateIncTax": _to_rupees(si.total_special_rate_tax),
    }


# ============================================================================
# Schedule EI — Exempt/Agricultural Income
# ============================================================================

def _schedule_ei(result: ITR2Result, input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize agricultural and exempt income when disclosed."""
    agri = input_data.agricultural_income
    exempt = input_data.exempt_income
    if agri is None and exempt is None:
        return None
    interest_inc = _ZERO
    others = _ZERO
    total_exempt = _ZERO
    if exempt:
        interest_inc = exempt.ppf_interest + exempt.sukanya_samriddhi_interest + exempt.tax_free_bond_interest + exempt.nre_interest
        others = exempt.share_of_profit_from_firm + exempt.other_exempt
        total_exempt = interest_inc + others
    total_exempt += result.net_agricultural_income
    return {
        "InterestInc": _to_rupees(interest_inc),
        "GrossAgriRecpt": _to_rupees(agri.gross_agricultural_income if agri else _ZERO),
        "ExpIncAgri": _to_rupees(agri.agricultural_deductions if agri else _ZERO),
        "UnabAgriLossPrev8": 0,
        "NetAgriIncOrOthrIncRule7": _to_rupees(result.net_agricultural_income),
        "ExcNetAgriInc": {"ExcNetAgriIncDtls": []},
        "OthersInc": {"OthersIncDtls": []},
        "Others": _to_rupees(others),
        "IncNotChrgblAsPerDTAA": {"IncNotChrgblAsPerDTAADtls": []},
        "IncNotChrgblToTax": _to_rupees(interest_inc),
        "PassThrIncNotChrgblTax": 0,
        "TotalExemptInc": _to_rupees(total_exempt),
    }


# ============================================================================
# Schedule FSI — Foreign Source Income
# ============================================================================

def _schedule_fsi(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize foreign-source income by jurisdiction."""
    if not input_data.fsi_entries:
        return None
    rows = []
    for item in input_data.fsi_entries:
        rows.append({
            "CountryName": item.country_code,
            "CountryCodeExcludingIndia": item.country_code,
            "TaxIdentificationNo": item.tax_identification_no,
            "IncFromSal": _to_rupees(item.salary_income),
            "IncFromHP": _to_rupees(item.hp_income),
            "IncCapGain": _to_rupees(item.cg_income),
            "IncOthSrc": _to_rupees(item.os_income),
            "TotalCountryWise": _to_rupees(item.total_income or _ZERO),
            "TaxPaidOutsideIndia": _to_rupees(item.tax_paid_outside_india),
            "TaxPayableInIndia": _to_rupees(item.tax_payable_in_india),
            "TaxReliefAvailable": _to_rupees(min(item.tax_paid_outside_india, item.tax_payable_in_india)),
        })
    return {"ScheduleFSIDtls": rows}


# ============================================================================
# Schedule TR1 — Foreign Tax Relief
# ============================================================================

def _schedule_tr1(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize foreign tax relief claims."""
    if not input_data.tr1_entries:
        return None
    rows = []
    for item in input_data.tr1_entries:
        rows.append({
            "CountryName": item.country_code,
            "CountryCodeExcludingIndia": item.country_code,
            "TaxIdentificationNo": item.tax_identification_no,
            "TaxPaidOutsideIndia": _to_rupees(item.tax_paid_outside_india),
            "TaxReliefOutsideIndia": _to_rupees(item.relief_claimed),
            "ReliefClaimedUsSection": item.relief_section,
        })
    dtaa = sum(r["TaxReliefOutsideIndia"] for r in rows if any(e.relief_section in {"90", "90A"} for e in input_data.tr1_entries if e.country_code == r["CountryName"]))
    non_dtaa = sum(r["TaxReliefOutsideIndia"] for r in rows if any(e.relief_section == "91" for e in input_data.tr1_entries if e.country_code == r["CountryName"]))
    return {
        "ScheduleTR": rows,
        "TotalTaxPaidOutsideIndia": sum(r["TaxPaidOutsideIndia"] for r in rows),
        "TotalTaxReliefOutsideIndia": dtaa + non_dtaa,
        "TaxReliefOutsideIndiaDTAA": dtaa,
        "TaxReliefOutsideIndiaNotDTAA": non_dtaa,
        "TaxPaidOutsideIndFlg": "YES",
        "AmtTaxRefunded": 0,
        "AssmtYrTaxRelief": "2026-27",
    }


# ============================================================================
# Schedule FA — Foreign Assets
# ============================================================================

def _schedule_fa(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize foreign-asset disclosures by category."""
    if not input_data.foreign_assets:
        return None
    result: dict[str, Any] = {
        "DetailsForiegnBank": [],
        "DtlsForeignCustodialAcc": [],
        "DtlsForeignEquityDebtInterest": [],
        "DtlsForeignCashValueInsurance": [],
        "DetailsFinancialInterest": [],
        "DetailsImmovableProperty": [],
        "DetailsOfAccntsHvngSigningAuth": [],
        "DetailsOfTrustOutIndiaTrustee": [],
        "DetailsOfOthSourcesIncOutsideIndia": [],
        "DetailsOthAssets": [],
    }
    for item in input_data.foreign_assets:
        if item.asset_type == ForeignAssetType.BANK_ACCOUNT:
            result["DetailsForiegnBank"].append({
                "CountryName": item.country_code,
                "CountryCodeExcludingIndia": item.country_code,
                "Bankname": item.institution_or_entity_name,
                "AddressOfBank": item.address,
                "ZipCode": item.account_or_asset_identifier[:8],
                "ForeignAccountNumber": item.account_or_asset_identifier[:34],
                "OwnerStatus": item.ownership_status,
                "AccOpenDate": _date(item.opening_or_acquisition_date),
                "PeakBalanceDuringYear": _to_rupees(item.peak_value),
                "ClosingBalance": _to_rupees(item.closing_value),
                "IntrstAccured": _to_rupees(item.gross_income),
            })
        elif item.asset_type == ForeignAssetType.IMMOVABLE_PROPERTY:
            result["DetailsImmovableProperty"].append({
                "CountryName": item.country_code,
                "CountryCodeExcludingIndia": item.country_code,
                "AddressOfProp": item.address,
                "ZipCode": item.account_or_asset_identifier[:8],
                "DateOfAcq": _date(item.opening_or_acquisition_date),
                "DateOfImp": _date(item.opening_or_acquisition_date),
                "PeakValueOfProp": _to_rupees(item.peak_value),
                "ClosingBalance": _to_rupees(item.closing_value),
                "IncFromProp": _to_rupees(item.gross_income),
            })
        else:
            result["DetailsOthAssets"].append({
                "CountryName": item.country_code,
                "CountryCodeExcludingIndia": item.country_code,
                "NameOfInst": item.institution_or_entity_name,
                "AddressOfInst": item.address,
                "AcctNumOrIdtyNum": item.account_or_asset_identifier,
                "OwnerStatus": item.ownership_status,
                "DateOfAcq": _date(item.opening_or_acquisition_date),
                "PeakBalanceDuringYear": _to_rupees(item.peak_value),
                "ClosingBalance": _to_rupees(item.closing_value),
                "IncFromOthSrc": _to_rupees(item.gross_income),
            })
    return result


# ============================================================================
# Schedule AL — Assets & Liabilities
# ============================================================================

def _schedule_al(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule AL aggregate assets and liabilities."""
    item = input_data.asset_liability
    if item is None:
        return None
    return {
        "ImmovableDetails": [],
        "MovableAsset": {
            "CashInHand": _to_rupees(item.cash_in_hand),
            "DepositsInBank": _to_rupees(item.bank_deposits),
            "SharesAndSecurities": _to_rupees(item.shares_and_securities),
            "InsurancePolicies": _to_rupees(item.insurance_policies),
            "LoansAndAdvancesGiven": _to_rupees(item.loans_and_advances),
            "JewelleryBullionEtc": _to_rupees(item.jewellery),
            "ArchCollDrawPaintSulpArt": _to_rupees(item.art),
            "VehiclYachtsBoatsAircrafts": _to_rupees(item.vehicles_boats_aircraft),
        },
        "LiabilityInRelatAssets": _to_rupees(item.related_liabilities),
    }


# ============================================================================
# Schedule AMT / AMTC
# ============================================================================

def _schedule_amt(result: ITR2Result, input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule AMT from computed AMT result."""
    amt = result.schedules.get("amt")
    if amt is None or not getattr(amt, "amt_applicable", False):
        return None
    return {
        "TotalIncItemPartBTI": _to_rupees(result.taxable_income),
        "DeductionClaimUndrAnySec": _to_rupees(getattr(amt, "total_deductions", _ZERO)),
        "AdjustedUnderSec115JC": _to_rupees(getattr(amt, "adjusted_total_income", _ZERO)),
        "TaxPayableUnderSec115JC": _to_rupees(getattr(amt, "amt_tax", _ZERO)),
    }


def _schedule_amtc(result: ITR2Result, input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule AMTC from brought-forward credit ledger."""
    amt_in = input_data.amt_input
    if amt_in is None or not amt_in.amt_credits:
        return None
    rows = []
    total_bf = _ZERO
    total_utilised = _ZERO
    for credit in amt_in.amt_credits:
        rows.append({
            "AssessmentYear": credit.assessment_year,
            "AmtTaxCreditBF": _to_rupees(credit.credit_brought_forward),
            "TaxSection115JD": _to_rupees(result.amt_tax),
            "AmtTaxCreditUtilisedCY": _to_rupees(min(credit.credit_brought_forward, result.amt_tax)),
            "AmtCreditCF": _to_rupees(max(_ZERO, credit.credit_brought_forward - result.amt_tax)),
        })
        total_bf += credit.credit_brought_forward
    total_utilised = sum(Decimal(str(r["AmtTaxCreditUtilisedCY"])) for r in rows)
    total_cf = max(_ZERO, total_bf - total_utilised)
    return {
        "ScheduleAMTCDtls": rows,
        "CurrAssYr": "2026-27",
        "TaxSection115JC": _to_rupees(result.amt_tax),
        "TaxOthProvisions": _to_rupees(result.gross_tax_liability - result.amt_tax),
        "AmtTaxCreditAvailable": _to_rupees(total_bf),
        "TaxSection115JD": _to_rupees(result.amt_tax),
        "AmtLiabilityAvailable": _to_rupees(result.amt_tax),
        "TotAmtCreditUtilisedCY": _to_rupees(total_utilised),
        "CurrYrCreditCarryFwd": _to_rupees(total_cf),
        "CurrYrAmtCreditFwd": _to_rupees(total_cf),
        "TotAMTGross": _to_rupees(total_bf),
        "TotSetOffEys": len(rows),
        "TotBalBF": _to_rupees(total_bf),
        "TotBalAMTCreditCF": _to_rupees(total_cf),
    }


# ============================================================================
# Schedule SPI — Clubbing
# ============================================================================

def _schedule_spi(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize actual Section 64 clubbing rows."""
    if not input_data.spi_entries:
        return None
    rows = []
    for item in input_data.spi_entries:
        row: dict[str, Any] = {
            "SpecifiedPersonName": item.specified_person_name,
            "ReltnShip": item.relationship,
            "AmtIncluded": _to_rupees(item.amount_included),
            "HeadIncIncluded": "SA" if item.head_of_income == "SAL" else item.head_of_income,
        }
        if item.pan:
            row["PANofSpecPerson"] = item.pan
        rows.append(row)
    return {"SpecifiedPerson": rows}


# ============================================================================
# Schedule PTI — Pass-Through Income
# ============================================================================

def _schedule_pti(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize actual pass-through income rows."""
    if not input_data.pti_entries:
        return None

    def regular(amount: Decimal = _ZERO, tds: Decimal = _ZERO) -> dict[str, int]:
        return {"AmountOfInc": _to_rupees(max(_ZERO, amount)), "CurrYrLossShareByInvstFund": _to_rupees(max(_ZERO, -amount)), "NetIncomeLoss": _to_rupees(amount), "TDSAmount": _to_rupees(tds)}

    def other(amount: Decimal = _ZERO, tds: Decimal = _ZERO) -> dict[str, int]:
        return {"AmountOfInc": _to_rupees(amount), "NetIncomeLoss": _to_rupees(amount), "TDSAmount": _to_rupees(tds)}

    rows = []
    for item in input_data.pti_entries:
        hp = item.income_amount if item.income_head == "HP" else _ZERO
        stcg = item.income_amount if item.income_head == "STCG" else _ZERO
        ltcg = item.income_amount if item.income_head == "LTCG" else _ZERO
        os = item.income_amount if item.income_head == "OS" else _ZERO
        rows.append({
            "InvstmntCvrdUs115UA115UB": "A" if item.section == "115UA" else "B" if item.section == "115UB" else "C",
            "BusinessName": item.entity_name,
            "BusinessPAN": item.entity_pan,
            "IncFromHP": regular(hp, item.tds_credit if hp else _ZERO),
            "CapitalGainsPTI": {
                "ShortTermCG": regular(stcg),
                "STCG_Sec111A": regular(),
                "STCG_Others": regular(stcg, item.tds_credit if stcg else _ZERO),
                "LongTermCG": regular(ltcg),
                "LTCG_Sec112A": regular(),
                "LTCG_Others": regular(ltcg, item.tds_credit if ltcg else _ZERO),
            },
            "IncClmdPTI": {"TotalSec23FBB": other(), "Sec23FBB": other()},
            "IncOthSrc": other(os, item.tds_credit if os else _ZERO),
            "OS_Dividend": other(),
            "OS_Others": other(os, item.tds_credit if os else _ZERO),
        })
    return {"SchedulePTIDtls": rows}


# ============================================================================
# Schedule 5A
# ============================================================================

def _schedule_5a(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Portuguese Civil Code apportionment data."""
    item = input_data.schedule_5a
    if item is None:
        return None

    def head(amount: Decimal, tds: Decimal = _ZERO) -> dict[str, int]:
        return {"IncRecvdUndHead": _to_rupees(amount * 2), "AmtApprndOfSpouse": _to_rupees(amount), "AmtTDSDeducted": _to_rupees(tds * 2), "TDSApprndOfSpouse": _to_rupees(tds)}

    total = item.hp_amount_apportioned + item.cg_amount_apportioned + item.os_amount_apportioned
    output: dict[str, Any] = {
        "NameOfSpouse": item.spouse_name,
        "PANOfSpouse": item.spouse_pan,
        "HPHeadIncome": head(item.hp_amount_apportioned),
        "CapGainHeadIncome": head(item.cg_amount_apportioned),
        "OtherSourcesHeadIncome": head(item.os_amount_apportioned, item.tds_apportioned),
        "TotalHeadIncome": head(total, item.tds_apportioned),
    }
    if item.spouse_aadhaar:
        output["AadhaarOfSpouse"] = item.spouse_aadhaar
    return output


# ============================================================================
# Schedule ESOP
# ============================================================================

def _schedule_esop(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize ESOP deferral ledger from actual input entries."""
    if not input_data.esop_deferrals:
        return None
    first = input_data.esop_deferrals[0]
    esop_event = {"SecurityType": "NS", "ScheduleESOPEventDtlsType": [], "CeasedEmployee": "N"}

    def ay_block(ay_label: str, tax_key: str, entry: Optional[Any] = None) -> dict[str, Any]:
        if entry is None or entry.assessment_year != ay_label:
            return {"AssessmentYear": ay_label, "TaxDeferredBFEarlierAY": 0, "ScheduleESOPEventDtls": esop_event, tax_key: 0, "TaxPayableCurrentAY": 0, "BalanceTaxCF": 0}
        return {"AssessmentYear": ay_label, "TaxDeferredBFEarlierAY": _to_rupees(entry.tax_deferred_brought_forward), "ScheduleESOPEventDtls": esop_event, tax_key: _to_rupees(entry.tax_payable_current_year), "TaxPayableCurrentAY": _to_rupees(entry.tax_payable_current_year), "BalanceTaxCF": _to_rupees(entry.balance_tax_carried_forward)}

    entry_by_ay = {e.assessment_year: e for e in input_data.esop_deferrals}
    total_attributed = sum((e.tax_payable_current_year for e in input_data.esop_deferrals), _ZERO)
    return {
        "DPIITRegNo": first.dpiit_registration_number,
        "PanofStartUp": first.employer_pan,
        "ScheduleESOP2122_Type": ay_block("2021-22", "TotalTaxAttributedAmt21", entry_by_ay.get("2021-22")),
        "ScheduleESOP2223_Type": ay_block("2022-23", "TotalTaxAttributedAmt22", entry_by_ay.get("2022-23")),
        "ScheduleESOP2324_Type": ay_block("2023-24", "TotalTaxAttributedAmt23", entry_by_ay.get("2023-24")),
        "ScheduleESOP2425_Type": ay_block("2024-25", "TotalTaxAttributedAmt24", entry_by_ay.get("2024-25")),
        "ScheduleESOP2526_Type": ay_block("2025-26", "TotalTaxAttributedAmt25", entry_by_ay.get("2025-26")),
        "ScheduleESOP2627_Type": {"AssessmentYear": "2026-27", "BalanceTaxCF": _to_rupees(first.balance_tax_carried_forward)},
        "TotalTaxAttributedAmt": _to_rupees(total_attributed),
    }


# ============================================================================
# Schedule IT, TDS1, TDS2, TDS3, TCS
# ============================================================================

def _schedule_it(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize actual tax-payment challan rows."""
    if not input_data.tax_payment_entries:
        return None
    rows = []
    for item in input_data.tax_payment_entries:
        if not item.bsr_code or not item.payment_date or not item.challan_serial_number:
            raise ValueError("Schedule IT payment requires BSR code, date, and challan serial number")
        rows.append({
            "BSRCode": item.bsr_code,
            "DateDep": _date(item.payment_date),
            "SrlNoOfChaln": int(item.challan_serial_number),
            "Amt": _to_rupees(item.amount),
        })
    return {"TaxPayment": rows, "TotalTaxPayments": sum(r["Amt"] for r in rows)}


def _schedule_tds1(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule TDS1 from real employer entries."""
    if not input_data.tds1_entries:
        return None
    rows = []
    for entry in input_data.tds1_entries:
        if not entry.employer_tan:
            raise ValueError("TDS1 entry requires employer TAN")
        rows.append({
            "EmployerOrDeductorOrCollectDetl": {
                "TAN": entry.employer_tan,
                "EmployerOrDeductorOrCollecterName": entry.employer_name or "",
            },
            "IncChrgSal": _to_rupees(entry.income_chargeable),
            "TotalTDSSal": _to_rupees(entry.tds_deducted),
        })
    return {"TDSonSalary": rows, "TotalTDSonSalaries": sum(r["TotalTDSSal"] for r in rows)}


def _schedule_tds2(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule TDS2 from real deductor entries.

    ``TDSCreditName``/``PANofOtherPerson``/``AadhaarOfOtherPerson``,
    ``HeadOfIncome``, ``BroughtFwdTDSAmt``, and ``AmtCarriedFwd`` are all
    read from ``entry``'s own fields rather than hardcoded/recomputed --
    every one of these is real, taxpayer-entered data that already flows
    through `_map_tds()` (`app/engine/draft_to_itr1_input.py`) from
    `ReturnDraft.taxes.tds`'s `TdsCredit` rows; the previous version simply
    never read it back out.
    """
    if not input_data.tds2_entries:
        return None
    rows = []
    for entry in input_data.tds2_entries:
        deducted_year = int((entry.financial_year or "2024-25").split("-")[0])
        row: dict[str, Any] = {
            "TDSCreditName": entry.ownership,
            "TANOfDeductor": entry.deductor_tan,
            "TDSSection": entry.tds_section,
            "DeductedYr": deducted_year,
            "BroughtFwdTDSAmt": _to_rupees(entry.brought_forward_tds),
            "TaxDeductCreditDtls": {
                "TaxDeductedOwnHands": _to_rupees(entry.tds_deducted),
                "TaxClaimedOwnHands": _to_rupees(entry.tds_claimed_this_year),
            },
            "GrossAmount": _to_rupees(entry.gross_amount),
            "HeadOfIncome": entry.head_of_income or "OS",
            "AmtCarriedFwd": _to_rupees(entry.tds_credit_carried_forward),
        }
        if entry.ownership == "O":
            if entry.pan_of_other_person:
                row["PANofOtherPerson"] = entry.pan_of_other_person
            if entry.aadhaar_of_other_person:
                row["AadhaarOfOtherPerson"] = entry.aadhaar_of_other_person
        rows.append(row)
    return {"TDSOthThanSalaryDtls": rows, "TotalTDSonOthThanSals": sum(r["TaxDeductCreditDtls"]["TaxClaimedOwnHands"] for r in rows)}


def _schedule_tds3(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule TDS3 from real non-resident deductor entries.

    Same fix as ``_schedule_tds2`` for ``TDSCreditName``/``PANofOtherPerson``/
    ``AadhaarOfOtherPerson``/``BroughtFwdTDSAmt``/``AmtCarriedFwd``.
    """
    if not input_data.tds3_entries:
        return None
    if len(input_data.tds3_filing_details) != len(input_data.tds3_entries):
        raise ValueError("Schedule TDS3 requires one tds3_filing_details row per entry")
    rows = []
    for entry, detail in zip(input_data.tds3_entries, input_data.tds3_filing_details):
        # TDS3Entry has no `financial_year` field (that belongs to TDS2Entry) --
        # it carries the deducted year directly as `deducted_yr` ("20XX"). The
        # old code here read a nonexistent attribute, an AttributeError that
        # fired on any return with real TDS3 data.
        deducted_year = int(entry.deducted_yr)
        row: dict[str, Any] = {
            "TDSCreditName": entry.ownership,
            "PANOfBuyerTenant": detail.buyer_tenant_pan,
            "TDSSection": entry.tds_section or "195",
            "DeductedYr": deducted_year,
            "BroughtFwdTDSAmt": _to_rupees(entry.brought_forward_tds),
            "TaxDeductCreditDtls": {
                "TaxDeductedOwnHands": _to_rupees(entry.tds_deducted),
                # TDS3Entry's field is `tds_claimed`, not `tds_claimed_this_year`
                # (that name belongs to TDS2Entry) -- the old code here
                # referenced a nonexistent attribute, an AttributeError that
                # would fire on any return with real TDS3 data. No prior
                # test ever exercised this path with a real TDS3Entry.
                "TaxClaimedOwnHands": _to_rupees(entry.tds_claimed),
            },
            # TDS3Entry's field is `gross_receipt`, not `gross_amount` (that
            # belongs to TDS2Entry) -- another nonexistent-attribute
            # AttributeError, same root cause as `deducted_yr` above.
            "GrossAmount": _to_rupees(entry.gross_receipt),
            "HeadOfIncome": detail.head_of_income,
            "AmtCarriedFwd": _to_rupees(entry.tds_credit_carried_forward),
        }
        if entry.ownership == "O":
            if entry.pan_of_other_person:
                row["PANofOtherPerson"] = entry.pan_of_other_person
            if entry.aadhaar_of_other_person:
                row["AadhaarOfOtherPerson"] = entry.aadhaar_of_other_person
        rows.append(row)
    return {"TDS3onOthThanSalDtls": rows, "TotalTDS3OnOthThanSal": sum(r["TaxDeductCreditDtls"]["TaxClaimedOwnHands"] for r in rows)}


def _schedule_tcs(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule TCS from real collector entries.

    ``TCSCreditOwner``/``PANOfSpouseOrOthrPrsn`` and the spouse-side
    collected/claimed amounts are real fields on ``TCSEntry`` (added
    alongside this fix) sourced from ``ReturnDraft.taxes.tcs``'s
    ``TcsCredit`` rows, which already captured this data -- it was
    previously dropped when mapped into the (until now, narrower)
    canonical ``TCSEntry`` type.
    """
    if not input_data.tcs_entries:
        return None
    rows = []
    for entry in input_data.tcs_entries:
        deducted_year = int(
            (entry.deducted_year or (entry.financial_year or "2024-25").split("-")[0])
        )
        row: dict[str, Any] = {
            "TCSCreditOwner": entry.ownership,
            "EmployerOrDeductorOrCollectTAN": entry.collector_tan,
            "DeductedYr": deducted_year,
            "BroughtFwdTDSAmt": _to_rupees(entry.brought_forward_tds),
            "TCSCurrFYDtls": {
                "TCSAmtCollOwnHand": _to_rupees(entry.tcs_collected),
                "TCSAmtCollSpouseOrOthrHand": _to_rupees(entry.tcs_collected_spouse_or_other),
            },
            "TCSClaimedThisYearDtls": {
                "TCSAmtCollOwnHand": _to_rupees(entry.tcs_credit_claimed),
                "TCSAmtCollSpouseOrOthrHand": _to_rupees(entry.tcs_credit_claimed_spouse_or_other),
            },
            "AmtCarriedFwd": _to_rupees(entry.tds_credit_carried_forward),
        }
        if entry.ownership == "2" and entry.pan_of_spouse_or_other_person:
            row["PANOfSpouseOrOthrPrsn"] = entry.pan_of_spouse_or_other_person
        rows.append(row)
    return {
        "TCS": rows,
        "TotalSchTCS": sum(
            r["TCSClaimedThisYearDtls"]["TCSAmtCollOwnHand"]
            + r["TCSClaimedThisYearDtls"]["TCSAmtCollSpouseOrOthrHand"]
            for r in rows
        ),
    }


# ============================================================================
# Part B-TI — Total Income (required)
# ============================================================================

def _partb_ti(result: ITR2Result) -> dict[str, Any]:
    """Serialize Part B-TI from computed income heads."""
    post_loss = result.schedules.get("post_loss_cg", {})
    stcg_20 = _to_rupees(post_loss.get("normal_stcg", _ZERO))
    stcg_111a = _to_rupees(post_loss.get("111a", _ZERO))
    ltcg_112 = _to_rupees(post_loss.get("112", _ZERO))
    ltcg_112a_gross = _to_rupees(post_loss.get("112a_gross", _ZERO))
    total_stcg = stcg_20 + stcg_111a
    total_ltcg = ltcg_112 + ltcg_112a_gross
    total_cg = total_stcg + total_ltcg + _to_rupees(result.vda_income)
    return {
        "Salaries": _to_rupees(result.salary_income),
        "IncomeFromHP": _to_rupees(max(_ZERO, result.house_property_income)),
        "CapGain": {
            "ShortTerm": {
                "ShortTerm20Per": stcg_20,
                "ShortTerm30Per": 0,
                "ShortTermAppRate": stcg_111a,
                "ShortTermSplRateDTAA": 0,
                "TotalShortTerm": total_stcg,
            },
            "LongTerm": {
                "LongTerm12_5Per": ltcg_112,
                "LongTermSplRateDTAA": 0,
                "TotalLongTerm": total_ltcg,
            },
            "ShortTermLongTermTotal": total_cg,
            "CapGains30Per115BBH": _to_rupees(result.vda_income),
            "TotalCapGains": total_cg,
        },
        "IncFromOS": {
            "OtherSrcThanOwnRaceHorse": _to_rupees(result.other_sources_income),
            "IncChargblSplRate": 0,
            "FromOwnRaceHorse": 0,
            "TotIncFromOS": _to_rupees(result.other_sources_income),
        },
        "CurrentYearLoss": _to_rupees(result.cyla_total_set_off),
        "BalanceAfterSetoffLosses": _to_rupees(max(_ZERO, result.gti_before_loss_setoff - result.cyla_total_set_off)),
        "BroughtFwdLossesSetoff": _to_rupees(result.bfla_total_set_off),
        "GrossTotalIncome": _to_rupees(result.gross_total_income),
        "IncChargeTaxSplRate111A112": _to_rupees(post_loss.get("111a", _ZERO) + post_loss.get("112", _ZERO) + post_loss.get("112a_gross", _ZERO)),
        "DeductionsUnderScheduleVIA": _to_rupees(result.deductions_total),
        "TotalIncome": _to_rupees_rounded10(result.taxable_income),
        "IncChargeableTaxSplRates": _to_rupees(post_loss.get("111a", _ZERO) + post_loss.get("112", _ZERO) + post_loss.get("112a_gross", _ZERO) + result.vda_income),
        "NetAgricultureIncomeOrOtherIncomeForRate": _to_rupees(result.net_agricultural_income),
        "AggregateIncome": _to_rupees(result.aggregate_income),
        "LossesOfCurrentYearCarriedFwd": _to_rupees(result.cyla_remaining),
        "DeemedIncomeUs115JC": 0,
        "TotalTI": _to_rupees_rounded10(result.taxable_income),
    }


# ============================================================================
# Part B-TTI — Tax Liability (required)
# ============================================================================

def _partb_tti(result: ITR2Result, input_data: ITR2Input) -> dict[str, Any]:
    """Serialize Part B-TTI from computed tax liability and real bank facts."""
    # Build refund/bank block
    accounts = input_data.bank_accounts
    if result.refund_due > 0 and not accounts:
        raise ValueError("Refund due requires at least one bank account")
    if result.refund_due > 0 and not any(a.is_primary for a in accounts):
        raise ValueError("Refund due requires a refund-designated bank account")
    bank_rows = []
    for account in accounts:
        try:
            account_type = BankAccountType(account.account_type).itd_code
        except ValueError:
            account_type = account.account_type
        bank_rows.append({
            "IFSCCode": account.ifsc_code,
            "BankName": account.bank_name or "",
            "BankAccountNo": account.account_number,
            "AccountType": account_type,
            "UseForRefund": "true" if account.is_primary else "false",
        })
    refund_block = {
        "RefundDue": _to_rupees_rounded10(result.refund_due),
        "BankAccountDtls": {
            "BankDtlsFlag": "Y" if bank_rows else "N",
            "AddtnlBankDetails": bank_rows,
            "ForeignBankDetails": [],
        },
    }
    total_interest = result.interest_234a + result.interest_234b + result.interest_234c
    return {
        "ComputationOfTaxLiability": {
            "TaxPayableOnTI": {
                "TaxAtNormalRatesOnAggrInc": _to_rupees(result.slab_tax),
                "TaxAtSpecialRates": _to_rupees(result.special_rate_tax),
                "RebateOnAgriInc": _to_rupees(result.partial_integration_tax),
                "TaxPayableOnTotInc": _to_rupees(result.slab_tax + result.special_rate_tax),
            },
            "TaxRelief": {
                "Section89": _to_rupees(result.relief_89),
                "Section90": _to_rupees(result.relief_90_91),
                "Section91": 0,
                "TotTaxRelief": _to_rupees(result.relief_89 + result.relief_90_91),
            },
            "Rebate87A": _to_rupees(result.rebate_87a),
            "TaxPayableOnRebate": _to_rupees(result.tax_after_rebate),
            "Surcharge25ofSI": 0,
            "SurchargeOnAboveCrore": _to_rupees(result.surcharge),
            "Surcharge25ofSIBeforeMarginal": 0,
            "SurchargeOnAboveCroreBeforeMarginal": 0,
            "TotalSurcharge": _to_rupees(result.surcharge),
            "EducationCess": _to_rupees(result.health_education_cess),
            "GrossTaxLiability": _to_rupees(result.gross_tax_liability),
            "GrossTaxPayable": 0,
            "GrossTaxPay": {"TaxInc17": 0, "TaxDeferred17": 0, "TaxDeferredPayableCY": 0},
            "CreditUS115JD": 0,
            "TaxPayAfterCreditUs115JD": 0,
            "NetTaxLiability": _to_rupees(result.net_tax_liability),
            "IntrstPay": {
                "IntrstPayUs234A": _to_rupees(result.interest_234a),
                "IntrstPayUs234B": _to_rupees(result.interest_234b),
                "IntrstPayUs234C": _to_rupees(result.interest_234c),
                "LateFilingFee234F": _to_rupees(result.late_fee_234f),
                "FeeFurnish234I": 0,
                "TotalIntrstPay": _to_rupees(total_interest),
            },
            "AggregateTaxInterestLiability": _to_rupees(result.net_tax_liability),
        },
        "TaxPayDeemedTotIncUs115JC": 0,
        "TotalTaxPayablDeemedTotInc": 0,
        "Surcharge": _to_rupees(result.surcharge),
        "HealthEduCess": _to_rupees(result.health_education_cess),
        "AssetOutIndiaFlag": "NO",
        "TaxPaid": {
            "TaxesPaid": {
                "AdvanceTax": _to_rupees(result.total_advance_tax),
                "TDS": _to_rupees(result.total_tds),
                "TCS": _to_rupees(result.total_tcs),
                "SelfAssessmentTax": _to_rupees(result.total_self_assessment_tax),
                "TotalTaxesPaid": _to_rupees(result.total_taxes_paid),
            },
        },
        "Refund": refund_block,
    }


# ============================================================================
# Verification
# ============================================================================

def _verification_block(input_data: ITR2Input) -> dict[str, Any]:
    """Serialize verification from the filing profile."""
    profile = _required_profile(input_data)
    name = " ".join(part for part in (profile.first_name, profile.middle_name, profile.surname_or_org_name) if part)
    return _verification(name, profile.father_name, profile.pan, profile.verification_place, profile.verification_capacity)


# ============================================================================
# Public API
# ============================================================================

def build_itr2_json(result: ITR2Result, input_data: ITR2Input) -> dict[str, Any]:
    """Build an AY 2026-27 official ITR-2 JSON document.

    Args:
        result: Calculator output produced from ``input_data``.
        input_data: Canonical filing facts and schedule evidence.

    Returns:
        Schema-shaped ITR-2 JSON object.

    Raises:
        ValueError: If mandatory identity, refund, or schedule evidence is absent.
    """
    profile = _required_profile(input_data)
    itr2: dict[str, Any] = {
        "CreationInfo": _creation_info(),
        "Form_ITR2": _form_itr("ITR-2"),
        "PartA_GEN1": _part_a_gen1(input_data),
        "ScheduleCYLA": _schedule_cyla(result),
        "ScheduleBFLA": _schedule_bfla(result),
        "PartB-TI": _partb_ti(result),
        "PartB_TTI": _partb_tti(result, input_data),
        "Verification": _verification_block(input_data),
    }
    optional: dict[str, Optional[dict[str, Any]]] = {
        "ScheduleS": _schedule_s(result, input_data),
        "ScheduleHP": _schedule_hp(result, input_data),
        "ScheduleOS": _schedule_os(result, input_data),
        "ScheduleCGFor23": _schedule_cg(input_data, result),
        "Schedule112A": _schedule_112a(input_data),
        "ScheduleVDA": _schedule_vda(input_data),
        "ScheduleCFL": _schedule_cfl(result, input_data),
        "ScheduleVIA": _schedule_via(result),
        "ScheduleSI": _schedule_si(result),
        "ScheduleEI": _schedule_ei(result, input_data),
        "ScheduleFSI": _schedule_fsi(input_data),
        "ScheduleTR1": _schedule_tr1(input_data),
        "ScheduleFA": _schedule_fa(input_data),
        "ScheduleAL": _schedule_al(input_data),
        "ScheduleAMT": _schedule_amt(result, input_data),
        "ScheduleAMTC": _schedule_amtc(result, input_data),
        "ScheduleSPI": _schedule_spi(input_data),
        "SchedulePTI": _schedule_pti(input_data),
        "Schedule5A2014": _schedule_5a(input_data),
        "ScheduleESOP": _schedule_esop(input_data),
        "ScheduleIT": _schedule_it(input_data),
        "ScheduleTDS1": _schedule_tds1(input_data),
        "ScheduleTDS2": _schedule_tds2(input_data),
        "ScheduleTDS3": _schedule_tds3(input_data),
        "ScheduleTCS": _schedule_tcs(input_data),
    }
    itr2.update({k: v for k, v in optional.items() if v is not None})
    # Digest is computed over the COMPLETE ITR document (the whole
    # ``{"ITR": {"ITR2": ...}}`` JSON, matching the ITD reference
    # ``API_Testing/digest_generator.py`` and SOP §5.3 Step 1), with the
    # Digest value replaced by the placeholder "-".
    wrapped = {"ITR": {"ITR2": itr2}}
    itr2["CreationInfo"]["Digest"] = _compute_digest(wrapped)
    return wrapped
