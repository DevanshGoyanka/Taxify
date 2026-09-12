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

from app.engine.calculators.itr2 import ITR2Result, PTI_OS_SPECIAL_RATE_SECTIONS
from app.engine.constants import (
    SECTION_80DD_LIMIT,
    SECTION_80DD_SEVERE_LIMIT,
    SECTION_80U_LIMIT,
    SECTION_80U_SEVERE_LIMIT,
)
from app.engine.schedules.capital_gains import _exemption_claim_total, deemed_consideration_50c
from app.engine.itd.country_codes import country_name as _country_name
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
    AssesseeStatus,
    ForeignAssetEntry,
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


def _date_range(
    q1: Decimal = _ZERO, q2: Decimal = _ZERO, q3: Decimal = _ZERO,
    q4: Decimal = _ZERO, q5: Decimal = _ZERO,
) -> dict[str, Any]:
    """DateRangeType -- quarterly income breakdown used for advance-tax-
    interest (234C) purposes across Schedule OS's dividend/lottery/89A
    categories. Q1-Q5 map in order to the five official periods, matching
    the established convention already used for ITR-1's own dividend
    quarterly breakdown (`itd/itr1.py`'s ``dividend_quarterly_breakdown``).
    Defaults to all-zero when the source data carries no quarter breakdown.
    """
    return {
        "DateRange": {
            "Upto15Of6": _to_rupees(q1),
            "Upto15Of9": _to_rupees(q2),
            "Up16Of9To15Of12": _to_rupees(q3),
            "Up16Of12To15Of3": _to_rupees(q4),
            "Up16Of3To31Of3": _to_rupees(q5),
        }
    }


# ============================================================================
# Part A — Personal info and filing status
# ============================================================================

def _part_a_gen1(input_data: ITR2Input) -> dict[str, Any]:
    """Serialize Part A from the real filing profile."""
    profile = _required_profile(input_data)
    addr = profile.primary_address
    address_data: dict[str, Any] = {
        "ResidenceNo": addr.residence_no,
        "ResidenceName": addr.residence_name,
        "RoadOrStreet": addr.road_or_street,
        "LocalityOrArea": addr.locality_or_area,
        "CityOrTownOrDistrict": addr.city_or_town_or_district,
        "StateCode": addr.state_code,
        "CountryCode": addr.country_code,
        "CountryCodeMobile": addr.mobile_country_code,
        "MobileNo": int(addr.mobile_no) if addr.mobile_no.isdigit() else 0,
        "CountryCodeMobileNoSec": addr.secondary_mobile_country_code,
        "MobileNoSec": int(addr.secondary_mobile_no) if addr.secondary_mobile_no and addr.secondary_mobile_no.isdigit() else 0,
        "EmailAddress": addr.email,
    }
    if addr.country_code == "91":
        address_data["PinCode"] = int(addr.pin_code) if addr.pin_code else 0
    else:
        address_data["ZipCode"] = addr.zip_code
    if addr.secondary_email:
        address_data["EmailAddressSec"] = addr.secondary_email
    phone = profile.primary_address
    address_data["Phone"] = {
        "STDcode": phone.landline_std_code,
        "PhoneNo": phone.landline_phone_no,
    }
    personal_info: dict[str, Any] = {
        "AssesseeName": {
            "FirstName": profile.first_name,
            "MiddleName": profile.middle_name,
            "SurNameOrOrgName": profile.surname_or_org_name,
        },
        "PAN": profile.pan,
        "Address": address_data,
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
        "AsseseeRepFlg": "Y" if profile.verification_capacity == "R" else "N",
        "ItrFilingDueDate": _date(profile.filing_due_date),
        "HeldUnlistedEqShrPrYrFlg": "Y" if profile.held_unlisted_equity else "N",
        # Previously never emitted at all -- is_company_director was read
        # from the draft but silently dropped here, unlike its sibling
        # HeldUnlistedEqShrPrYrFlg one line above.
        "CompDirectorPrvYrFlg": "Y" if profile.is_company_director else "N",
        "FiiFpiFlag": "Y" if profile.is_fii_fpi else "N",
        # Sibling per-clause flags under the SeventhProvisio139 umbrella --
        # previously never emitted at all, even though ITR2FilingProfile
        # already carried the individual deposit/foreign-travel/electricity
        # amounts (they were captured all the way from the frontend's
        # SeventhProviso block through _itr2_filing_profile(), then silently
        # dropped here before ever reaching the JSON). Found during the
        # Phase 4 P0 exit re-audit -- confirms the §4.6 current-account-
        # deposit fix was itself incomplete: the frontend control and the
        # ITR2FilingProfile wiring were both correct, but the actual filed
        # JSON never carried the disclosure at all.
        "DepAmtAggAmtExcd1CrPrYrFlg": "Y" if profile.deposit_exceeds_one_crore else "N",
        "IncrExpAggAmt2LkTrvFrgnCntryFlg": "Y" if profile.foreign_travel_flag else "N",
        "IncrExpAggAmt1LkElctrctyPrYrFlg": "Y" if profile.electricity_expenditure_flag else "N",
        "clauseiv7provisio139i": "Y" if profile.other_clause_iv_flag else "N",
        "PortugeseCC5A": "Y" if profile.portuguese_civil_code_applies else "N",
    }
    if profile.deposit_exceeds_one_crore:
        filing_status["AmtSeventhProvisio139i"] = _to_rupees(profile.current_account_deposits)
    if profile.foreign_travel_flag:
        filing_status["AmtSeventhProvisio139ii"] = _to_rupees(profile.foreign_travel_expenditure)
    if profile.electricity_expenditure_flag:
        filing_status["AmtSeventhProvisio139iii"] = _to_rupees(profile.electricity_expenditure)
    if profile.seventh_proviso_clause_iv_entries:
        filing_status["clauseiv7provisio139iDtls"] = [
            {
                "clauseiv7provisio139iNature": entry.nature,
                "clauseiv7provisio139iAmount": _to_rupees(entry.amount),
            }
            for entry in profile.seventh_proviso_clause_iv_entries
        ]
    if profile.receipt_number:
        filing_status["ReceiptNo"] = profile.receipt_number
    if profile.original_return_date:
        filing_status["OrigRetFiledDate"] = _date(profile.original_return_date)
    if profile.notice_number:
        filing_status["NoticeNo"] = profile.notice_number
    if profile.notice_date:
        filing_status["NoticeDate"] = _date(profile.notice_date)
    if profile.assessee_representative is not None:
        representative = profile.assessee_representative
        filing_status["AssesseeRep"] = {
            "RepName": representative.name,
            "RepEmailID": representative.email,
            "CountryCodeRepMobileNo": representative.mobile_country_code,
            "RepMobileNo": int(representative.mobile_no),
        }
    if profile.sebi_registration_number:
        # Official schema key is "SebiRegnNo", NOT "SEBIRegNo" -- confirmed
        # via live Draft4Validator schema validation (the wrong key was
        # rejected outright with "Additional properties are not allowed").
        filing_status["SebiRegnNo"] = profile.sebi_registration_number
    if profile.lei_number:
        filing_status["LEIDtls"] = {"LEINumber": profile.lei_number}
        if profile.lei_valid_upto_date:
            filing_status["LEIDtls"]["ValidUptoDate"] = _date(profile.lei_valid_upto_date)
    if profile.conditions_res_status:
        filing_status["ConditionsResStatus"] = profile.conditions_res_status
    if profile.jurisdiction_residence_entries:
        filing_status["JurisdictionResPrevYr"] = {
            "JurisdictionResPrevYrDtls": [
                {"JurisdictionResidence": entry.jurisdiction_code, "TIN": entry.tin}
                for entry in profile.jurisdiction_residence_entries
            ]
        }
    if profile.total_stay_india_prev_yr is not None:
        filing_status["TotalPrStayIndiaPrevYr"] = profile.total_stay_india_prev_yr
    if profile.total_stay_india_4_prec_yr is not None:
        filing_status["TotalPrStayIndia4PrecYr"] = profile.total_stay_india_4_prec_yr
    # CBDT rule #83: emit a real Y/N once the question has actually been
    # answered (was previously only emitted -- as "Y" -- when the benefit
    # was claimed, silently omitting the field for every explicit "No",
    # even though the official schema's own enum is {"Y","N"}).
    if profile.benefit_us_115h is not None:
        filing_status["BenefitUs115HFlg"] = "Y" if profile.benefit_us_115h else "N"
    if profile.company_director_entries:
        rows = []
        for entry in profile.company_director_entries:
            row: dict[str, Any] = {
                "NameOfCompany": entry.company_name,
                "CompanyType": entry.company_type,
                "SharesTypes": entry.shares_type,
            }
            if entry.pan:
                row["PAN"] = entry.pan
            if entry.din:
                row["DIN"] = entry.din
            rows.append(row)
        filing_status["CompDirectorPrvYr"] = {"CompDirectorPrvYrDtls": rows}
    if profile.unlisted_equity_entries:
        rows = []
        for entry in profile.unlisted_equity_entries:
            row = {
                "NameOfCompany": entry.company_name,
                "CompanyType": entry.company_type,
                "OpngBalNumberOfShares": entry.opening_shares,
                "OpngBalCostOfAcquisition": _to_rupees(entry.opening_cost),
                "ClsngBalNumberOfShares": entry.closing_shares,
                "ClsngBalCostOfAcquisition": _to_rupees(entry.closing_cost),
            }
            if entry.pan:
                row["PAN"] = entry.pan
            if entry.acquired_shares:
                row["ShrAcqDurYrNumberOfShares"] = entry.acquired_shares
            if entry.date_of_acquisition:
                row["DateOfSubscrPurchase"] = _date(entry.date_of_acquisition)
            if entry.face_value_per_share:
                row["FaceValuePerShare"] = _to_rupees(entry.face_value_per_share)
            if entry.issue_price_per_share:
                row["IssuePricePerShare"] = entry.issue_price_per_share
            if entry.purchase_price_per_share:
                row["PurchasePricePerShare"] = _to_rupees(entry.purchase_price_per_share)
            if entry.transferred_shares:
                row["ShrTrnfNumberOfShares"] = entry.transferred_shares
            if entry.transfer_sale_consideration:
                row["ShrTrnfSaleConsideration"] = _to_rupees(entry.transfer_sale_consideration)
            rows.append(row)
        filing_status["HeldUnlistedEqShrPrYr"] = {"HeldUnlistedEqShrPrYrDtls": rows}
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
    # `os_inc` above is deliberately racehorse-inclusive (matches
    # `result.other_sources_income`'s own gross, pre-set-off convention --
    # see the calculator's own note on this). The OthSrcExclRaceHorse row
    # needs the racehorse-EXCLUSIVE figure (CBDT rule #260); derive it by
    # subtracting the original gross racehorse profit, recovered as
    # racehorse_setoff + racehorse_remaining since CYLA's own racehorse
    # pool only ever decreases from that starting value.
    racehorse_setoff = getattr(cyla, "racehorse_setoff", z) if cyla else z
    racehorse_remaining = getattr(cyla, "racehorse_remaining", z) if cyla else z
    racehorse_gross = racehorse_setoff + racehorse_remaining
    os_inc_excl_rh = os_inc - racehorse_gross

    # Per-basket "current year income" figures for Schedule CYLA's own six
    # CG rows must be Table E's own Column-8 (post-Section-70-intra-CG-
    # netting) output (`cyla.cg_intra_head_remaining`) -- CONFIRMED against
    # the official CBDT Validation Rules PDF (rules #257/#258/#259/#263/
    # #567/#568: "In Schedule CYLA [bucket] should be equal to Sl.No.8[x]
    # of item E of Schedule CG", where "Sl.No.8" is Table E's own Column 8,
    # per rule #563's "Column 8 of each row should be equal to
    # 1-(2+3+4+5+6+7)" -- i.e. the intra-CG-netted remaining figure, not
    # the raw pre-netting gross figure) -- Phase 6h, 2026-09-11. Table E's
    # Section-70 intra-CG netting runs FIRST; its output is what Schedule
    # CYLA's own Section-71 cross-head netting is meant to start FROM, per
    # the form's own pipeline sequencing. `cg_gross_income` (used here
    # previously) is Table E's own INPUT, not its output, and using it
    # instead made Schedule CYLA silently disagree with Table E on the same
    # bucket whenever any intra-CG (STCG-vs-STCG or LTCG-vs-LTCG) loss was
    # set off -- a real, CBDT-rule-violating disclosure bug, not a design
    # choice; confirmed genuinely fixable, unlike Part B-TI's own separate
    # divergence from Table E (rules #496/#497/#565/#566), which reflects a
    # legitimately LATER pipeline stage (cross-head AND brought-forward
    # absorption) that Table E was never meant to show and Part B-TI
    # correctly cannot use Table E's narrower basis without becoming wrong
    # itself -- see this function's own module-level notes in
    # Docs/ITR2_VALIDATOR_GAP_MAPPING_AY2026_27.md, Phase 6h, for the full
    # investigation and why that half is deliberately left undisclosed-
    # inconsistent rather than "fixed" into incorrectness.
    cg_intra_remaining = getattr(cyla, "cg_intra_head_remaining", None) or {} if cyla else {}
    stcg20_inc = cg_intra_remaining.get("stcg20", z)
    stcg30_inc = cg_intra_remaining.get("stcg30", z)
    stcg_app_inc = cg_intra_remaining.get("stcg_app", z)
    stcg_dtaa_inc = cg_intra_remaining.get("stcg_dtaa", z)
    ltcg125_inc = cg_intra_remaining.get("ltcg125", z)
    ltcg_dtaa_inc = cg_intra_remaining.get("ltcg_dtaa", z)

    # Col4 ("current year's income remaining after set-off") is CYLAResult's
    # own already-correct final per-basket pool (post-intra-CG AND
    # cross-head absorption) -- the exact same figures `_post_loss_cg_
    # baskets()` sources from for the real tax computation, so Schedule
    # CYLA's own disclosed "remaining" figure is now guaranteed consistent
    # with what the return actually gets taxed on (before BFLA's further,
    # separate brought-forward-loss stage).
    stcg20_after = getattr(cyla, "stcg20_remaining", z) if cyla else z
    stcg30_after = getattr(cyla, "stcg30_remaining", z) if cyla else z
    stcg_app_after = getattr(cyla, "stcg_app_remaining", z) if cyla else z
    stcg_dtaa_after = getattr(cyla, "stcg_dtaa_remaining", z) if cyla else z
    ltcg125_after = getattr(cyla, "ltcg125_remaining", z) if cyla else z
    ltcg_dtaa_after = getattr(cyla, "ltcg_dtaa_remaining", z) if cyla else z

    hp_remaining = abs(min(z, result.house_property_income)) if result.house_property_income < z else z
    return {
        "Salary": {"IncCYLA": _inc_cyla(salary, z, z, salary)},
        "HP": {"IncCYLA": _inc_cyla_hp(hp_inc, z, hp_inc)},
        "STCG20Per": {"IncCYLA": _inc_cyla(stcg20_inc, z, z, stcg20_after)},
        "STCG30Per": {"IncCYLA": _inc_cyla(stcg30_inc, z, z, stcg30_after)},
        "STCGAppRate": {"IncCYLA": _inc_cyla(stcg_app_inc, z, z, stcg_app_after)},
        "STCGDTAARate": {"IncCYLA": _inc_cyla(stcg_dtaa_inc, z, z, stcg_dtaa_after)},
        "LTCG12_5Per": {"IncCYLA": _inc_cyla(ltcg125_inc, z, z, ltcg125_after)},
        "LTCGDTAARate": {"IncCYLA": _inc_cyla(ltcg_dtaa_inc, z, z, ltcg_dtaa_after)},
        # CBDT rule #371: DTAA-rate Other Sources income (Schedule OS's own
        # NRIDTAADtlsSchOS rows) is a special-rate basket not eligible for
        # loss set-off (same treatment as VDA/salary income elsewhere in
        # this schedule) -- disclosed at its own real value, no setoff ever
        # applied to it.
        "IncOSDTAA": {"IncCYLA": _inc_cyla(result.os_dtaa_income, z, z, result.os_dtaa_income)},
        "OthSrcExclRaceHorse": {
            "IncCYLA": _inc_cyla_os(os_inc_excl_rh, hp_setoff, max(z, os_inc_excl_rh - hp_setoff))
        },
        "OthSrcRaceHorse": {
            "IncCYLA": _inc_cyla(racehorse_gross, z, racehorse_setoff, racehorse_remaining)
        },
        "LossRemAftSetOff": {
            "BalHPlossCurYrAftSetoff": _to_rupees(hp_remaining),
            "BalOthSrcLossNoRaceHorseAftSetoff": _to_rupees(getattr(cyla, "os_loss_remaining", z) if cyla else z),
        },
        "TotalCurYr": {
            "TotHPlossCurYr": _to_rupees(hp_remaining),
            "TotOthSrcLossNoRaceHorse": _to_rupees(getattr(cyla, "os_loss_total", z) if cyla else z),
        },
        "TotalLossSetOff": {
            "TotHPlossCurYrSetoff": _to_rupees(hp_setoff),
            "TotOthSrcLossNoRaceHorseSetoff": _to_rupees(getattr(cyla, "os_loss_setoff_total", z) if cyla else z),
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
    # Same racehorse-exclusion derivation as _schedule_cyla() -- OthSrcExclRaceHorse
    # never receives a brought-forward set-off (no BF-loss head targets it),
    # so its BFLA figure is unchanged from CYLA's own os_inc_excl_rh.
    racehorse_setoff_cyla = getattr(cyla, "racehorse_setoff", z) if cyla else z
    racehorse_remaining_cyla = getattr(cyla, "racehorse_remaining", z) if cyla else z
    os_inc_excl_rh = os_inc - racehorse_setoff_cyla - racehorse_remaining_cyla
    racehorse_bf_setoff = getattr(bfla, "racehorse_setoff", z) if bfla else z
    racehorse_bf_remaining = getattr(bfla, "racehorse_remaining", z) if bfla else racehorse_remaining_cyla
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
        "IncOSDTAA": {"IncBFLA": _inc_bfla_no_bf(result.os_dtaa_income, result.os_dtaa_income)},
        "OthSrcExclRaceHorse": {"IncBFLA": _inc_bfla_no_bf(os_inc_excl_rh, os_inc_excl_rh)},
        "OthSrcRaceHorse": {
            "IncBFLA": _inc_bfla(racehorse_remaining_cyla, racehorse_bf_setoff, racehorse_bf_remaining)
        },
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

    def summary(entries: list, *, include_race_horse: bool) -> dict[str, int]:
        detail: dict[str, int] = {
            "TotalHPPTILossCF": _to_rupees(sum((e.loss_remaining for e in entries if e.head in ("HP", "HouseProperty")), _ZERO)),
            "TotalSTCGPTILossCF": _to_rupees(sum((e.loss_remaining for e in entries if e.head in ("STCG", "CG")), _ZERO)),
            "TotalLTCGPTILossCF": _to_rupees(sum((e.loss_remaining for e in entries if e.head == "LTCG"), _ZERO)),
        }
        if include_race_horse:
            detail["OthSrcLossRaceHorseCF"] = _to_rupees(sum((e.loss_remaining for e in entries if e.head == "RaceHorse"), _ZERO))
        return detail

    by_year: dict[str, list] = {}
    for entry in flattened:
        by_year.setdefault(entry.assessment_year_of_loss, []).append(entry)
    # Section 74A caps race-horse-activity loss carry-forward at 4 years, so
    # the official schema's own year-slot types structurally omit
    # OthSrcLossRaceHorseCF for the 5th-8th-year-back slots (type
    # CarryFwdWithoutLossDetail) -- only the 1st-4th-year-back slots (type
    # CarryFwdLossDetail) carry that field at all. additionalProperties is
    # false on both, so emitting it in the older slots is itself a schema
    # violation, not just a wrong value.
    year_keys: dict[str, tuple[str, bool]] = {
        "2018-19": ("LossCFFromPrev8thYearFromAY", False),
        "2019-20": ("LossCFFromPrev7thYearFromAY", False),
        "2020-21": ("LossCFFromPrev6thYearFromAY", False),
        "2021-22": ("LossCFFromPrev5thYearFromAY", False),
        "2022-23": ("LossCFFromPrev4thYearFromAY", True),
        "2023-24": ("LossCFFromPrev3rdYearFromAY", True),
        "2024-25": ("LossCFFromPrev2ndYearFromAY", True),
        "2025-26": ("LossCFFromPrevYrToAY", True),
    }
    output: dict[str, Any] = {}
    filing_dates = {
        item.assessment_year: item.date_of_filing
        for item in input_data.bf_losses
        if item.date_of_filing is not None
    }
    for year, entries in by_year.items():
        mapping = year_keys.get(year)
        if mapping is None:
            continue
        key, include_race_horse = mapping
        # DateOfFiling is unconditionally required by both year-slot schema
        # types (CarryFwdLossDetail and CarryFwdWithoutLossDetail) -- a
        # brought-forward loss with no known original-return filing date
        # would previously omit the field silently and fail official-schema
        # validation downstream instead of failing here with a clear cause.
        if year not in filing_dates:
            raise ValueError(
                f"Schedule CFL requires date_of_filing for the brought-forward "
                f"loss from AY {year} (the original return's filing date is "
                "mandatory for carry-forward eligibility under Section 80)."
            )
        detail: dict[str, Any] = summary(entries, include_race_horse=include_race_horse)
        detail["DateOfFiling"] = _date(filing_dates[year])
        output[key] = {"CarryFwdLossDetail": detail}
    # LossSummaryDetail (the aggregate wrapper) allows OthSrcLossRaceHorseCF
    # unconditionally regardless of loss age, unlike the per-year slots.
    #
    # Form rows: ix "Total of earlier year losses" (TotalOfBFLossesEarlierYrs)
    # covers ONLY the genuine brought-forward AY2018-19..2025-26 entries; xi
    # "2026-27 (Current year losses)" (CurrentAYloss) is this year's own
    # fresh unabsorbed loss, disclosed separately; xii "Total loss carried
    # forward to future years" (TotalLossCFSummary) is ix+xi combined -- the
    # full, unfiltered ``flattened`` total. Previously ``flattened`` was
    # never split: both TotalOfBFLossesEarlierYrs and TotalLossCFSummary read
    # the same unfiltered total (so a fresh current-year loss was mislabeled
    # as an "earlier year" loss and CurrentAYloss, the schema's own dedicated
    # slot for it, was never emitted at all).
    current_ay_entries = [e for e in flattened if e.assessment_year_of_loss == "2026-27"]
    earlier_year_entries = [e for e in flattened if e.assessment_year_of_loss != "2026-27"]
    output["TotalOfBFLossesEarlierYrs"] = {
        "LossSummaryDetail": summary(earlier_year_entries, include_race_horse=True)
    }
    if current_ay_entries:
        output["CurrentAYloss"] = {
            "LossSummaryDetail": summary(current_ay_entries, include_race_horse=True)
        }
    output["TotalLossCFSummary"] = {"LossSummaryDetail": summary(flattened, include_race_horse=True)}
    return output


# ============================================================================
# Schedule S — Salary
# ============================================================================

# Maps a SalaryResult per-exemption field to its official Section 10
# sub-clause enum value and a human-readable label, for AllwncExemptUs10Dtls.
# 10(13A) (HRA) is deliberately excluded -- it has its own dedicated
# Section10_13A structure below, not this generic array.
_SALARY_EXEMPTION_ROWS: tuple[tuple[str, str, str], ...] = (
    ("lta_exempt", "10(5)", "Leave travel allowance"),
    ("gratuity_exempt", "10(10)", "Gratuity"),
    ("commuted_pension_exempt", "10(10A)", "Commuted pension"),
    ("leave_encashment_exempt", "10(10AA)", "Leave encashment"),
    ("retrenchment_exempt", "10(10B)(i)", "Retrenchment compensation"),
    ("vrs_exempt", "10(10C)", "Voluntary retirement compensation"),
    ("transport_exempt", "10(14)(ii)", "Transport allowance"),
    ("children_education_exempt", "10(14)(ii)", "Children education allowance"),
    ("hostel_exempt", "10(14)(ii)", "Hostel expenditure allowance"),
    # Unlike transport/CEA/hostel above (fixed statutory-rate allowances,
    # correctly 10(14)(ii): "granted to meet personal expenses... or to
    # compensate for increased cost of living"), uniform allowance is
    # exempt only to the extent of actual expenditure incurred
    # (`_exempt_uniform_allowance()`'s own docstring: "u/s 10(14)(i) / Rule
    # 2BB(1)(f)") -- matching the official schema's own 10(14)(i)
    # description ("...to the extent actually incurred..."), not 10(14)(ii).
    ("uniform_allowance_exempt", "10(14)(i)", "Uniform allowance"),
)


def _schedule_s(result: ITR2Result, input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule S from the real calculator SalaryResult and TDS1 employer identity."""
    source = input_data.salary_income
    if source is None:
        return None
    if not input_data.tds1_entries:
        if not input_data.employer_filing_details:
            raise ValueError("Salary income requires at least one employer filing detail")
    if input_data.tds1_entries and len(input_data.employer_filing_details) != len(input_data.tds1_entries):
        raise ValueError("Schedule S requires one employer_filing_details row per TDS1 employer")
    sal = result.schedules.get("salary")
    if sal is None:
        raise ValueError("Salary income present but no computed SalaryResult is available")

    # TDS is a credit schedule and may legitimately be empty. When TDS1 rows
    # exist, retain the strict cross-foot against the salary income they claim.
    gross_total = sum((e.income_chargeable for e in input_data.tds1_entries), _ZERO)
    if input_data.tds1_entries and _to_rupees(gross_total) != _to_rupees(sal.gross_salary):
        raise ValueError(
            f"Schedule S cannot cross-foot: tds1_entries income_chargeable "
            f"({gross_total}) does not match the taxed salary income's real gross "
            f"({sal.gross_salary}). Check that tds1_entries and salary_income reflect "
            "the same underlying salary facts."
        )

    # TDS-backed rows preserve their exact TDS identity. With no TDS, build
    # Schedule S directly from employer filing details so salary-only returns
    # remain serializable.
    if input_data.tds1_entries:
        employer_rows = list(zip(input_data.tds1_entries, input_data.employer_filing_details))
    else:
        employer_rows = [(None, detail) for detail in input_data.employer_filing_details]

    single_employer = len(employer_rows) == 1
    employers = []
    # Real per-employer Section 10 exemption rows (10(6)/10(7)/10(10CC)/EIC/
    # 10(17)/10(14)(i)/10(14)(ii)/etc., a frontend-captured dropdown+amount
    # list -- EmployerEntryManager.tsx's own "Section 10 Exemption" row
    # editor) collected across ALL employers, for merging into the final
    # AllwncExemptUs10Dtls array below. These codes are disjoint from
    # _SALARY_EXEMPTION_ROWS's own set (LTA/gratuity/pension/leave/
    # retrenchment/VRS/transport/CEA/hostel/uniform, none of which this
    # editor offers), so no double-counting risk in merging the two.
    frontend_section10_rows: list[dict[str, Any]] = []
    for entry, detail in employer_rows:
        employer_name = entry.employer_name if entry is not None else detail.employer_name
        employer_tan = entry.employer_tan if entry is not None else detail.employer_tan
        if not employer_name:
            raise ValueError("Schedule S requires employer name")
        if entry is not None and (
            detail.employer_tan != entry.employer_tan
            or detail.employer_name != entry.employer_name
        ):
            raise ValueError("Schedule S employer filing details must match TDS1 identity")
        gross = entry.income_chargeable if entry is not None else sal.gross_salary
        perquisites = source.perquisites_value if single_employer else _ZERO
        profits_in_lieu = source.profits_in_lieu_of_salary if single_employer else _ZERO
        notified_89a = detail.income_notified_89a
        notified_other_89a = detail.income_notified_other_89a
        notified_prior_89a = detail.income_notified_prior_year_89a
        gross_components = perquisites + profits_in_lieu + notified_89a + notified_other_89a + notified_prior_89a
        if entry is not None and _to_rupees(gross) != _to_rupees(
            (gross - gross_components) + gross_components
        ):
            raise ValueError(f"Schedule S employer {employer_name!r}: gross component reconciliation failed")
        base_salary = gross - gross_components
        if base_salary < _ZERO:
            raise ValueError(
                f"Schedule S employer {employer_name!r}: perquisites "
                f"({perquisites}) plus profits in lieu ({profits_in_lieu}) exceed "
                f"gross salary ({gross})."
            )
        address: dict[str, Any] = {
            "AddrDetail": detail.address_detail,
            "CityOrTownOrDistrict": detail.city_or_town_or_district,
            "StateCode": detail.state_code,
        }
        if detail.pin_code is not None:
            address["PinCode"] = int(detail.pin_code)
        elif detail.zip_code is not None:
            address["ZipCode"] = detail.zip_code
        row: dict[str, Any] = {
            "NameOfEmployer": employer_name,
            "NatureOfEmployment": detail.nature_of_employment,
            "AddressDetail": address,
            "Salarys": {
                "GrossSalary": _to_rupees(gross),
                "Salary": _to_rupees(base_salary),
                "NatureOfSalary": {"OthersIncDtls": detail.nature_of_salary_rows},
                "ValueOfPerquisites": _to_rupees(perquisites),
                "NatureOfPerquisites": {"OthersIncDtls": detail.nature_of_perquisites_rows},
                "ProfitsinLieuOfSalary": _to_rupees(profits_in_lieu),
                "NatureOfProfitInLieuOfSalary": {"OthersIncDtls": detail.nature_of_profit_in_lieu_rows},
                "IncomeNotified89A": _to_rupees(detail.income_notified_89a),
                # Official schema keys are NOT89ACountrycode/NOT89AAmount (the
                # same NOT89AType structure Schedule OS's own
                # IncomeNotified89ATypeOS uses) -- was previously passed
                # straight through with no key transform at all, unlike the
                # three sibling row types immediately above.
                "IncomeNotified89AType": [
                    {"NOT89ACountrycode": row.country_code, "NOT89AAmount": _to_rupees(row.amount)}
                    for row in detail.income_notified_89a_country_rows
                ],
                "IncomeNotifiedOther89A": _to_rupees(detail.income_notified_other_89a),
                "IncomeNotifiedPrYr89A": _to_rupees(detail.income_notified_prior_year_89a),
            },
        }
        # Previously built here, then never attached to the output at all --
        # discarded once the loop moved on, so this real frontend-captured
        # data silently vanished from the filed JSON. Collected into the
        # return-scope list instead, guarding against "OTH" (offered by the
        # frontend dropdown as a free-text catch-all, but not a valid
        # official SalNatureDesc code -- the schema's enum has no generic
        # "other" bucket for this specific array).
        for section10_row in detail.section10_exemption_rows:
            amount = section10_row.get("SalOthAmount", 0)
            if amount <= 0:
                continue
            code = section10_row["SalNatureDesc"]
            if code == "OTH":
                raise ValueError(
                    f"Schedule S employer {employer_name!r}: Section 10 exemption row uses "
                    "code \"OTH\", which has no official ITD schema code -- select a specific "
                    "Section 10 sub-clause instead."
                )
            frontend_section10_rows.append({
                "SalNatureDesc": code,
                "SalOthNatOfInc": section10_row["SalOthNatOfInc"],
                "SalOthAmount": amount,
            })
        row["Salarys"]["NatureOfSalary"] = {"OthersIncDtls": detail.nature_of_salary_rows}
        if employer_tan:
            row["TANofEmployer"] = employer_tan
        employers.append(row)

    employer_gross_total = sum((e["Salarys"]["GrossSalary"] for e in employers), 0)
    if employer_gross_total != _to_rupees(sal.gross_salary):
        raise ValueError("Schedule S gross reconciliation failed: employer totals do not equal computed gross salary")

    section13a_details = input_data.employer_filing_details
    if len({detail.is_metro_city for detail in section13a_details}) > 1:
        raise ValueError("Schedule S Section 10(13A) cannot represent mixed metro and non-metro employers")
    hra_received = sum((detail.actual_hra_received for detail in section13a_details), _ZERO)
    rent_paid = sum((detail.actual_rent_paid for detail in section13a_details), _ZERO)
    hra_salary = sum((detail.salary_for_hra for detail in section13a_details), _ZERO)
    is_metro = section13a_details[0].is_metro_city
    rent_minus_ten = max(_ZERO, rent_paid - hra_salary * Decimal("0.1"))
    salary_rate = hra_salary * (Decimal("0.5") if is_metro else Decimal("0.4"))
    hra_calc = min(hra_received, rent_minus_ten, salary_rate)
    if input_data.tax_regime.value == "new":
        hra_received = rent_paid = hra_salary = salary_rate = hra_calc = _ZERO
    if _to_rupees(hra_calc) != _to_rupees(source.hra_exempt_amount) and source.hra_exempt_amount > _ZERO:
        raise ValueError("Schedule S Section 10(13A) exemption reconciliation failed")

    exemption_rows = [
        {"SalNatureDesc": code, "SalOthNatOfInc": label, "SalOthAmount": _to_rupees(amount)}
        for field, code, label in _SALARY_EXEMPTION_ROWS
        if (amount := getattr(sal, field)) > _ZERO
    ] + frontend_section10_rows
    section13a_detail = section13a_details[0]
    relief_89a = _to_rupees(result.relief_89)
    total_gross_salary = employer_gross_total
    total_exempt = _to_rupees(sal.exempt_allowances)
    salary_89a_relief = _to_rupees(sal.salary_89a_relief)
    total_exempt_non_89a = _to_rupees(sal.exempt_allowances_excluding_89a)
    net_salary = total_gross_salary - total_exempt_non_89a - salary_89a_relief
    deduction_u16 = _to_rupees(sal.deductions_u16)
    income_under_salary = net_salary - deduction_u16
    if income_under_salary != _to_rupees(result.salary_income):
        # Section 89 relief is supplied by the return-level Form 10E input;
        # the salary calculator cannot infer it from salary facts.
        expected_income_under_salary = _to_rupees(sal.income_chargeable)
        if income_under_salary != expected_income_under_salary:
            raise ValueError("Schedule S salary equation reconciliation failed")

    return {
        "Salaries": employers,
        "TotalGrossSalary": total_gross_salary,
        "AllwncExemptUs10": {"AllwncExemptUs10Dtls": exemption_rows},
        "AllwncExtentExemptUs10": total_exempt_non_89a,
        "NetSalary": net_salary,
        "DeductionUS16": deduction_u16,
        "DeductionUnderSection16ia": _to_rupees(sal.standard_deduction),
        "EntertainmntalwncUs16ii": _to_rupees(sal.entertainment_allowance),
        "ProfessionalTaxUs16iii": _to_rupees(sal.professional_tax),
        "Increliefus89A": relief_89a,
        "Section10_13A": {
            "Placeofwork": "1" if section13a_detail.is_metro_city else "2",
            "ActlHRARecv": _to_rupees(section13a_detail.actual_hra_received),
            "ActlRentPaid": _to_rupees(section13a_detail.actual_rent_paid),
            "DtlsSalUsSec171": _to_rupees(hra_salary),
            "ActlRentPaid10Per": _to_rupees(rent_minus_ten),
            "Sal40Or50Per": _to_rupees(salary_rate),
            "EligbleExmpAllwncUs13A": _to_rupees(hra_calc),
        },
        "TotIncUnderHeadSalaries": income_under_salary,
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
        # Use the real per-property HPResult the calculator already computed
        # -- it correctly applies the Sec 24(b) self-occupied interest cap,
        # rent_not_realized, and the Sec 25A 70%-taxable arrears inclusion.
        # Re-deriving these locally from raw input fields (the previous
        # approach) silently dropped all three adjustments, so a
        # schema-valid but WRONG per-property IncomeOfHP could disagree with
        # the calculator's own income_chargeable and, in aggregate, with
        # result.house_property_income.
        rent_not_realized = _to_rupees(hp_res.rent_not_realized)
        local_taxes = _to_rupees(hp_res.municipal_taxes)
        alv = _to_rupees(hp_res.net_annual_value)
        annual_of_prop_owned = _to_rupees(hp_res.annual_value_owned)
        std_ded = _to_rupees(hp_res.standard_deduction_30pct)
        arrears = _to_rupees(hp_res.arrears_unrealised_rent)
        income = _to_rupees(hp_res.income_chargeable)
        if ptype == "S":
            # HPResult.interest_on_loan stores the RAW interest paid for
            # self-occupied property, not the Sec 24(b) allowed/capped
            # amount -- income_chargeable is the one field that already
            # reflects the real cap (old regime) or full disallowance (new
            # regime), and equals exactly -allowed_interest by construction
            # (app/engine/schedules/house_property.py), so derive from it
            # rather than re-implementing the cap/regime logic here.
            interest = -income
        else:
            interest = _to_rupees(hp_res.interest_on_loan)

        loan_rows = []
        for loan in detail.home_loan_details:
            loan_rows.append({
                "LoanTknFrom": loan.loan_taken_from,
                "BankOrInstnName": loan.bank_or_institution_name,
                "LoanAccNoOfBankOrInstnRefNo": loan.loan_account_or_ref_no,
                "DateofLoan": _date(loan.date_of_loan),
                "TotalLoanAmt": _to_rupees(loan.total_loan_amount),
                "LoanOutstndngAmt": _to_rupees(loan.loan_outstanding_amount),
                "InterestUs24B": _to_rupees(loan.interest_this_year),
            })
        if loan_rows:
            loan_total = sum(row["InterestUs24B"] for row in loan_rows)
            if loan_total != interest:
                raise ValueError(
                    f"Schedule HP property {idx}: home_loan_details interest_this_year "
                    f"({loan_total}) does not cross-foot to the property's real Section "
                    f"24(b) interest ({interest})."
                )

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
        prop: dict[str, Any] = {
            "HPSNo": idx,
            "AddressDetailWithZipCode": address,
            "PropertyOwner": detail.property_owner,
            "PropCoOwnedFlg": "YES" if detail.co_owned else "NO",
            **(
                {"PropertyOwnerOther": detail.property_owner_other}
                if detail.property_owner == "OT"
                else {}
            ),
            "AsseseeShareProperty": float(detail.assessee_share_percent),
            # Official schema enum is exactly {"L", "D", "S"} (Let Out /
            # Deemed Let Out / Self Occupied), matching PropertyType.value
            # verbatim -- was previously collapsed to "S"/"L" only, so a
            # deemed-let-out property (section 23(4), owner has more
            # properties than the self-occupied-exempt limit) was
            # misrepresented as ordinary "Let Out". ITR-1's own builder
            # (`itd/itr1.py:277`) already passes `.property_type.value`
            # straight through unchanged.
            "ifLetOut": ptype,
            "Rentdetails": {
                "AnnualLetableValue": _to_rupees(source.annual_rent_received),
                "RentNotRealized": rent_not_realized,
                "LocalTaxes": local_taxes,
                "TotalUnrealizedAndTax": rent_not_realized + local_taxes,
                "BalanceALV": alv,
                "AnnualOfPropOwned": annual_of_prop_owned,
                "ArrearsUnrealizedRentRcvd": arrears,
                "ThirtyPercentOfBalance": std_ded,
                "IntOnBorwCap": interest,
                "Section24B": {"Section24BDtls": loan_rows, "TotalInterestUs24B": interest},
                "TotalDeduct": std_ded + interest,
                "IncomeOfHP": income,
            },
        }
        if detail.co_owner_details:
            prop["CoOwners"] = [
                {
                    k: v for k, v in {
                        "CoOwnersSNo": i,
                        "NameCoOwner": co.name,
                        "PAN_CoOwner": co.pan,
                        "Aadhaar_CoOwner": co.aadhaar,
                        "PercentShareProperty": float(co.percent_share) if co.percent_share is not None else None,
                    }.items() if v is not None
                }
                for i, co in enumerate(detail.co_owner_details, 1)
            ]
        if detail.tenant_details:
            prop["TenantDetails"] = [
                {
                    k: v for k, v in {
                        "TenantSNo": i,
                        "NameofTenant": t.name,
                        "PANofTenant": t.pan,
                        "AadhaarofTenant": t.aadhaar,
                        "PANTANofTenant": t.pan_or_tan,
                    }.items() if v is not None
                }
                for i, t in enumerate(detail.tenant_details, 1)
            ]
        props.append(prop)
    # CBDT rule #79 -- "Sch HP Sl.2 pass-through income = HP income in
    # Schedule PTI": the calculator already folds real Schedule-PTI HP-head
    # income into result.house_property_income (so TotalIncomeChargeableUnHP
    # below was always correct in aggregate), but this line item disclosing
    # specifically how much of that total came via pass-through was
    # unconditionally 0 regardless of any actual PTI HP income.
    pti_hp_income = sum(
        (p.income_amount for p in input_data.pti_entries if p.income_head == "HP"), _ZERO,
    )
    return {
        "PropertyDetails": props,
        "PassThroghIncome": _to_rupees(pti_hp_income),
        "TotalIncomeChargeableUnHP": _to_rupees(result.house_property_income),
    }


# ============================================================================
# Schedule OS — Other Sources
# ============================================================================

# Draft DividendSection -> official top-level DateRangeType field. "194"
# (ordinary domestic-company dividend), "10(22e)", and "10(22f)" have no
# top-level date-range field of their own -- they only ever appear inside
# IncOthThanOwnRaceHorse's DividendOthThan22e/Dividend22e/Dividend22f.
_DIVIDEND_SECTION_DATE_RANGE_FIELD: dict[str, str] = {
    "DTAA": "DividendDTAA",
    "115A1aA": "DividendIncUs115A1aA",
    "115A1ai": "DividendIncUs115A1ai",
    "115AC": "DividendIncUs115AC",
    "115ACA": "DividendIncUs115ACA",
    "115AD1i": "DividendIncUs115AD1i",
    "115BBDA": "DividendIncUs115BBDA",
    "115BBDAaiii": "DividendIncUs115BBDAaiii",
}


def _schedule_os(result: ITR2Result, input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule OS from source-income components."""
    source = input_data.other_sources_income
    if (
        source is None and not input_data.si_entries
        and input_data.os_gift_breakdown is None
        and not (input_data.os_pf_income_benefit or input_data.os_pf_tax_benefit)
        and input_data.os_unexplained_income is None
        and input_data.os_section_89a is None
        and not input_data.os_other_income_entries
        and not input_data.os_dividend_entries
        and not input_data.os_dtaa_entries
        and not input_data.os_dtaa_aggregate
        and input_data.os_deductions is None
        and input_data.os_race_horse is None
        and not (
            input_data.os_pf_interest_10_11_first_proviso or input_data.os_pf_interest_10_11_second_proviso
            or input_data.os_pf_interest_10_12_first_proviso or input_data.os_pf_interest_10_12_second_proviso
        )
        and not input_data.os_interest_from_others
        and not input_data.os_machinery_plant_rent
        and not input_data.os_pass_through_income
        and not input_data.os_special_rate_entries
    ):
        return None
    os_schedule = result.schedules.get("os")
    deduction_57iia = getattr(os_schedule, "deduction_57iia", _ZERO) if os_schedule else _ZERO

    race_horse = input_data.os_race_horse
    race_horse_profit = max(_ZERO, race_horse.balance) if race_horse else _ZERO
    os_excl_race_horse = result.other_sources_income - race_horse_profit

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
        "NatofPassThrghIncome": _to_rupees(input_data.os_pass_through_income),
        "IntrstSec10XIFirstProviso": _to_rupees(input_data.os_pf_interest_10_11_first_proviso),
        "IntrstSec10XISecondProviso": _to_rupees(input_data.os_pf_interest_10_11_second_proviso),
        "IntrstSec10XIIFirstProviso": _to_rupees(input_data.os_pf_interest_10_12_first_proviso),
        "IntrstSec10XIISecondProviso": _to_rupees(input_data.os_pf_interest_10_12_second_proviso),
        "IntrstFrmOthers": _to_rupees(input_data.os_interest_from_others),
        "RentFromMachPlantBldgs": _to_rupees(input_data.os_machinery_plant_rent),
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
        "IncChargblSplRateOS": {"TotalAmtTaxUsDTAASchOs": _to_rupees(input_data.os_dtaa_aggregate)},
        "Deductions": {
            "DeductionUs57iia": _to_rupees(deduction_57iia),
            "Depreciation": 0,
            "Expenses": 0,
            "IntExp57": 0,
            "TotDeductions": _to_rupees(deduction_57iia),
            "UsrIntExp57": 0,
        },
        "AmtNotDeductibleUs58": 0,
        "ProfitChargTaxUs59": 0,
        "Increliefus89AOS": 0,
        "BalanceNoRaceHorse": _to_rupees(os_excl_race_horse),
    }
    if source:
        block["DividendGross"] = _to_rupees(source.dividend_income)
        block["DividendOthThan22e"] = _to_rupees(source.dividend_income)
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
        # TaxAccmltdBalRecPFDtls is the form's own per-assessment-year
        # sub-table -- previously always [] even when the user entered full
        # per-year detail, since draft_to_itr2_input.py collapsed it to the
        # aggregate totals alone before it ever reached ITR2Input.
        block["TaxAccumulatedBalRecPF"] = {
            "TaxAccmltdBalRecPFDtls": [
                {
                    "AssessmentYear": e.assessment_year,
                    "IncomeBenefit": _to_rupees(e.income_benefit),
                    "TaxBenefit": _to_rupees(e.tax_benefit),
                }
                for e in input_data.os_pf_accumulated_entries
            ],
            "TotalIncomeBenefit": _to_rupees(input_data.os_pf_income_benefit),
            "TotalTaxBenefit": _to_rupees(input_data.os_pf_tax_benefit),
        }

    # Item 2e: OS-head Schedule PTI income that retains a special-rate
    # character in the unit holder's hands (section 115UA(2)/115UB(1)
    # proviso) -- already correctly taxed via the calculator's own
    # PTI_OS_SPECIAL_RATE_SECTIONS-keyed dispatch (calculators/itr2.py);
    # this is purely the matching disclosure total, using the identical
    # section-code set so it can never disagree with what was actually
    # taxed.
    block["PassThrIncOSChrgblSplRate"] = _to_rupees(sum(
        (
            p.income_amount for p in input_data.pti_entries
            if p.income_head == "OS" and p.section in PTI_OS_SPECIAL_RATE_SECTIONS
        ),
        _ZERO,
    ))

    # Section 68/69/69A/69B/69C/69D unexplained-income breakdown -- the
    # combined total already reached GTI via the "115BBE" Schedule-SI entry
    # (see draft_to_itr2_input.py's wiring); this is the disclosure detail.
    unexplained = input_data.os_unexplained_income
    if unexplained is not None:
        block["CashCreditsUs68"] = _to_rupees(unexplained.cash_credits_us68)
        block["UnExplndInvstmntsUs69"] = _to_rupees(unexplained.unexplained_investments_us69)
        block["SumRecdPrYrBusTRU562xii"] = _to_rupees(unexplained.prior_year_business_trust_562xii)
        block["SumRecdPrYrLifIns562xiii"] = _to_rupees(unexplained.prior_year_life_insurance_562xiii)
        block["UnExplndMoneyUs69A"] = _to_rupees(unexplained.unexplained_money_us69a)
        block["UnDsclsdInvstmntsUs69B"] = _to_rupees(unexplained.undisclosed_investments_us69b)
        block["UnExplndExpndtrUs69C"] = _to_rupees(unexplained.unexplained_expenditure_us69c)
        block["AmtBrwdRepaidOnHundiUs69D"] = _to_rupees(unexplained.hundi_borrowing_us69d)

    # Section 89A (foreign-retirement-account income deferral) -- notified
    # income is deliberately excluded from current-year taxation, so only
    # the relief amount (Increliefus89AOS) interacts with tax liability;
    # everything else here is disclosure.
    section_89a = input_data.os_section_89a
    if section_89a is not None:
        block["IncomeNotified89AOS"] = _to_rupees(section_89a.income_notified)
        block["IncomeNotifiedOther89AOS"] = _to_rupees(section_89a.income_notified_other)
        block["IncomeNotifiedPrYr89AOS"] = _to_rupees(section_89a.income_notified_prior_yr)
        block["Increliefus89AOS"] = _to_rupees(section_89a.relief)
        block["IncomeNotified89ATypeOS"] = [
            {"NOT89ACountrycode": entry.country_code, "NOT89AAmount": _to_rupees(entry.amount)}
            for entry in section_89a.country_entries
        ]

    other_income_entries = input_data.os_other_income_entries
    if other_income_entries:
        block["AnyOtherIncome"] = _to_rupees(sum((e.amount for e in other_income_entries), _ZERO))
        block["OthersInc"] = {
            "OthersIncDtls": [
                {"OthNatOfInc": e.nature, "OthAmount": _to_rupees(e.amount)}
                for e in other_income_entries
            ]
        }

    deductions = input_data.os_deductions
    if deductions is not None:
        # Interest expenditure on dividend (Sl 3aii, `IntExp57`) is the raw
        # claim -- rule #216 caps it at 20% of dividend income, checked
        # separately as a pre-compute validator (ITR2-IN-OS-001). The TOTAL
        # must use the post-cap ELIGIBLE amount (Sl 3aiia, "Eligible Interest
        # expenditure u/s 57(1) -- Computed Amount", `interest_expense_
        # eligible_us57`/`UsrIntExp57`), matching the frontend's own already-
        # correct total-deductions formula (ScheduleOSWorkspace.tsx:296:
        # `expenses + interestExpenseEligibleUs57 + familyPensionDeductionUs57iia
        # + depreciation`) -- the backend builder previously summed neither
        # interest-expense field at all, silently under-totaling `Deductions`
        # for every taxpayer with dividend-related interest expense.
        total_deductions = (
            deduction_57iia + deductions.expenses + deductions.depreciation
            + deductions.interest_expense_eligible_us57
        )
        block["Deductions"] = {
            "DeductionUs57iia": _to_rupees(deduction_57iia),
            "Depreciation": _to_rupees(deductions.depreciation),
            "Expenses": _to_rupees(deductions.expenses),
            "IntExp57": _to_rupees(deductions.interest_expense_us57),
            "TotDeductions": _to_rupees(total_deductions),
            "UsrIntExp57": _to_rupees(deductions.interest_expense_eligible_us57),
        }
        block["AmtNotDeductibleUs58"] = _to_rupees(deductions.amount_not_deductible_us58)
        block["ProfitChargTaxUs59"] = _to_rupees(deductions.profit_chargeable_us59)

    # Dividend Dividend22e/Dividend22f split -- "194" (ordinary domestic
    # dividend) plus every other section not individually broken out falls
    # into DividendOthThan22e (the residual after removing 22(e)/22(f)).
    dividend_22e = sum(
        (e.amount for e in input_data.os_dividend_entries if e.section == "10(22e)"), _ZERO
    )
    dividend_22f = sum(
        (e.amount for e in input_data.os_dividend_entries if e.section == "10(22f)"), _ZERO
    )
    if dividend_22e or dividend_22f:
        block["Dividend22e"] = _to_rupees(dividend_22e)
        block["Dividend22f"] = _to_rupees(dividend_22f)
        block["DividendOthThan22e"] = _to_rupees(
            max(_ZERO, (source.dividend_income if source else _ZERO) - dividend_22e - dividend_22f)
        )

    dividend_date_ranges: dict[str, Any] = {}
    for entry in input_data.os_dividend_entries:
        field = _DIVIDEND_SECTION_DATE_RANGE_FIELD.get(entry.section)
        if field is None:
            continue
        dividend_date_ranges[field] = _date_range(entry.q1, entry.q2, entry.q3, entry.q4, entry.q5)

    if input_data.os_dtaa_entries:
        block["IncChargblSplRateOS"]["NRIOsDTAA"] = {
            "NRIDTAADtlsSchOS": [
                {
                    "DTAAamt": _to_rupees(e.amount),
                    "NatureOfIncome": e.nature_of_income,
                    "CountryName": e.country_name,
                    "CountryCodeExcludingIndia": e.country_code,
                    "DTAAarticle": e.dtaa_article,
                    "RateAsPerTreaty": float(e.rate_as_per_treaty),
                    "TaxRescertifiedFlag": e.tax_residency_certificate,
                    "ItemNoincl": e.item_no_incl,
                    "RateAsPerITAct": float(e.rate_as_per_it_act),
                    "ApplicableRate": float(e.applicable_rate),
                }
                for e in input_data.os_dtaa_entries
            ]
        }

    # NRI/FII special-rate income (Section 115A/115AC/115ACA/115AD/115E/
    # 115BBF/115BBG family) -- Schedule OS's "OthersGrossDtls" dropdown.
    # OthersGross is the plain sum of every disclosed row; the tax itself is
    # computed via Schedule SI (see calculators/itr2.py's dispatch loop over
    # `os_special_rate_entries`), this is disclosure only.
    special_rate_entries = input_data.os_special_rate_entries
    if special_rate_entries:
        block["OthersGross"] = _to_rupees(
            sum((e.source_amount for e in special_rate_entries), _ZERO)
        )
        block["OthersGrossDtls"] = [
            {
                "SourceDescription": e.source_description,
                "SourceAmount": _to_rupees(e.source_amount),
            }
            for e in special_rate_entries
        ]
    # IncChargeableSpecialRates aggregates every OS sub-category taxed at a
    # special (non-slab) rate rather than the "chargeable at applicable
    # rate" head -- lottery/game-show (115BB), online-games (115BBJ),
    # unexplained income (115BBE), the 115A-family NRI/FII rows above,
    # accumulated PF income u/s 111 (2c, TaxAccumulatedBalRecPF -- already
    # correctly taxed via the calculator's own `_OS_HEAD_SI_SECTIONS`
    # dispatch, just previously never folded into this disclosure total),
    # and pass-through OS income chargeable at special rates (2e,
    # PassThrIncOSChrgblSplRate -- now dispatched by the calculator's own
    # PTI_OS_SPECIAL_RATE_SECTIONS-keyed loop, see `block`'s own assignment
    # above).
    # CBDT rule #208: Sl.no 2 (this total) must fold in 2f (DTAA-rate OS
    # income, result.os_dtaa_income) alongside 2a/2b/2c/2d/2e above -- this
    # component was previously omitted entirely.
    block["IncChargeableSpecialRates"] = (
        block["LtryPzzlChrgblUs115BB"]
        + block["IncChrgblUs115BBJ"]
        + block["IncChrgblUs115BBE"]
        + block["OthersGross"]
        + block["TaxAccumulatedBalRecPF"]["TotalIncomeBenefit"]
        + block["PassThrIncOSChrgblSplRate"]
        + _to_rupees(result.os_dtaa_income)
    )
    # Form item "1b": Interest, Gross (bi+bii+biii+biv+bv+bvi+bvii+bviii+bix).
    # Previously only bi+bii+biii (savings/FD/refund interest) -- the other
    # six sibling sub-items (pass-through interest, the four PF-proviso
    # buckets, and "interest from others") were all correctly populated a
    # few lines above but never folded into their own declared header total,
    # even though the underlying amounts DO reach taxable income (via
    # result.other_sources_income, either directly for os_pass_through_income
    # or through the still-open "untraceable channel" this document's own
    # §20.5 finding describes for the PF-proviso/NSC/bonds categories).
    # Computed from the block's own final values, not independently
    # re-derived, so it can never itself drift from them.
    block["InterestGross"] = (
        block["IntrstFrmSavingBank"]
        + block["IntrstFrmTermDeposit"]
        + block["IntrstFrmIncmTaxRefund"]
        + block["NatofPassThrghIncome"]
        + block["IntrstSec10XIFirstProviso"]
        + block["IntrstSec10XISecondProviso"]
        + block["IntrstSec10XIIFirstProviso"]
        + block["IntrstSec10XIISecondProviso"]
        + block["IntrstFrmOthers"]
    )
    # Form item "1": Gross income chargeable to tax at normal applicable
    # rates (1a+1b+1c+1d+1e). Was hardcoded to 0 unconditionally, while its
    # five components (Dividends/Interest/Rent/56(2)(x)/Any other income)
    # were all correctly populated a few lines above -- a visible
    # self-contradiction against item "6" (BalanceNoRaceHorse below), which
    # already correctly derives from the real calculator total that this
    # sum is supposed to feed into. Computed from the block's own final
    # values (all five are stable by this point in the function), not
    # independently re-derived, so it can never itself drift from them.
    block["GrossIncChrgblTaxAtAppRate"] = (
        block["DividendGross"]
        + block["InterestGross"]
        + block["RentFromMachPlantBldgs"]
        + block["Tot562x"]
        + block["AnyOtherIncome"]
    )

    lottery_q = input_data.os_lottery_quarters
    gaming_q = input_data.os_gaming_quarters

    result_dict: dict[str, Any] = {
        "DividendDTAA": dividend_date_ranges.get("DividendDTAA", _date_range()),
        "DividendIncUs115A1aA": dividend_date_ranges.get("DividendIncUs115A1aA", _date_range()),
        "DividendIncUs115A1ai": dividend_date_ranges.get("DividendIncUs115A1ai", _date_range()),
        "DividendIncUs115AC": dividend_date_ranges.get("DividendIncUs115AC", _date_range()),
        "DividendIncUs115ACA": dividend_date_ranges.get("DividendIncUs115ACA", _date_range()),
        "DividendIncUs115AD1i": dividend_date_ranges.get("DividendIncUs115AD1i", _date_range()),
        "DividendIncUs115BBDA": dividend_date_ranges.get("DividendIncUs115BBDA", _date_range()),
        "DividendIncUs115BBDAaiii": dividend_date_ranges.get("DividendIncUs115BBDAaiii", _date_range()),
        "IncChargeable": _to_rupees(result.other_sources_income),
        "IncFrmLottery": (
            _date_range(lottery_q.q1, lottery_q.q2, lottery_q.q3, lottery_q.q4, lottery_q.q5)
            if lottery_q else _date_range()
        ),
        "IncFrmOnGames": (
            _date_range(gaming_q.q1, gaming_q.q2, gaming_q.q3, gaming_q.q4, gaming_q.q5)
            if gaming_q else _date_range()
        ),
        "IncFromOwnHorse": {
            "Receipts": _to_rupees(race_horse.receipts) if race_horse else 0,
            "DeductSec57": _to_rupees(race_horse.deduction_us57) if race_horse else 0,
            "AmtNotDeductibleUs58": _to_rupees(race_horse.amount_not_deductible_us58) if race_horse else 0,
            "ProfitChargTaxUs59": _to_rupees(race_horse.profit_chargeable_us59) if race_horse else 0,
            "BalanceOwnRaceHorse": _to_rupees(race_horse.balance) if race_horse else 0,
        },
        "IncOthThanOwnRaceHorse": block,
        "NOT89A": _date_range(),
        "TotOthSrcNoRaceHorse": _to_rupees(os_excl_race_horse),
    }
    return result_dict


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

# The subset of the generic "other assets" bucket that are genuinely
# "securities" for section 115AD purposes (an FII/FPI's own gains on
# these route to NRISecur115AD/NRIOnSec112and115Dtls instead of the
# ordinary SaleOnOtherAssets/SaleofAssetNADtls, per the official form's
# Schedule CG item 4/5 "For NON-RESIDENT- from sale of securities... by
# an FII as per section 115AD"). `jewellery`/`depreciable_asset`/
# `foreign_asset`/`other` are NOT securities and always stay in the
# ordinary bucket regardless of FII/FPI status.
_FII_SECURITIES_ASSET_TYPES = frozenset({
    "unlisted_shares",
    "listed_security",
    "debt_mutual_fund",
    "specified_mutual_fund_50aa",
    "market_linked_debenture_50aa",
    "bonds_debentures",
})


def _other_assets_block(
    transactions: list,
    is_long_term: bool,
    asset_types: frozenset = _GENERIC_OTHER_ASSET_TYPES,
) -> dict[str, Any]:
    """Aggregate the generic "other assets" bucket for Schedule CG item 5/8.

    Both the STCG (``EquityOrUnitSec94Type``, ``SaleOnOtherAssets``) and
    LTCG (``EquityOrUnitSec54Type``, ``SaleofAssetNADtls.SaleofAssetNA``)
    variants share this structure: consideration/cost aggregated across
    every matching-``asset_types`` transaction of the matching
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
    deduction_us54f = _ZERO

    for tx in transactions or []:
        asset_type = tx.asset_type.value if hasattr(tx.asset_type, "value") else tx.asset_type
        if asset_type not in asset_types:
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
        # Section 54F (any capital asset other than a residential house,
        # reinvested into a new residential house) is the only §54-series
        # exemption applicable to this bucket -- confirmed by the official
        # form's item 5d/8d, which cites only section 54F here (54/54B/54EC
        # belong to land/building or bonds specifically). Aggregated across
        # every matching transaction, mirroring the bucket's own
        # transaction-level aggregation (no per-row detail exists for this
        # bucket, matching land/building's DIFFERENT, per-row treatment).
        if is_long_term:
            deduction_us54f += _exemption_claim_total(getattr(tx, "exemptions", None), frozenset({"54F"}))

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
            else {"DeductionUs54F": _to_rupees(deduction_us54f)}
        ),
        "CapgainonAssets": _to_rupees(balance - deduction_us54f),
    }


def _cg_loss_setoff_table(result: ITR2Result) -> dict[str, Any]:
    """Build Schedule CG's own Table E (`CurrYrLosses`) -- the
    within-Schedule-CG section-70 current-year capital-loss set-off matrix
    (STCL against any CG rate bucket, LTCL against LTCG only). Previously
    hardcoded to all-zero regardless of real data; sourced from the CYLA
    engine's own intra-head computation (``cyla.py``'s ``cg_setoff_matrix``
    and siblings), a snapshot taken before that same engine's later,
    separate section-71 cross-head absorption of business/HP losses runs.
    Part B-TI's own capital-gains figures are independently sourced from
    ``post_loss_cg`` and unaffected by this table either way -- see
    ``_partb_ti()``.
    """
    cyla = result.schedules.get("cyla")
    income = getattr(cyla, "cg_gross_income", None) or {}
    loss = getattr(cyla, "cg_gross_loss", None) or {}
    matrix = getattr(cyla, "cg_setoff_matrix", None) or {}
    remaining = getattr(cyla, "cg_intra_head_remaining", None) or {}
    setoff_total = getattr(cyla, "cg_source_setoff_total", None) or {}
    loss_remaining = getattr(cyla, "cg_source_loss_remaining", None) or {}

    def gross_loss(name: str) -> int:
        return _to_rupees(loss.get(name, _ZERO))

    def gross_income(name: str) -> int:
        return _to_rupees(income.get(name, _ZERO))

    def net_remaining(name: str) -> int:
        return _to_rupees(remaining.get(name, _ZERO))

    def setoff(source: str, target: str) -> int:
        return _to_rupees(matrix.get((source, target), _ZERO))

    def total_setoff(name: str) -> int:
        return _to_rupees(setoff_total.get(name, _ZERO))

    def total_remaining(name: str) -> int:
        return _to_rupees(loss_remaining.get(name, _ZERO))

    return {
        "InLossSetOff": {
            "StclSetoff20Per": gross_loss("stcg20"),
            "StclSetoff30Per": gross_loss("stcg30"),
            "StclSetoffAppRate": gross_loss("stcg_app"),
            "StclSetoffDTAARate": gross_loss("stcg_dtaa"),
            "LtclSetOff12_5Per": gross_loss("ltcg125"),
            "LtclSetOffDTAARate": gross_loss("ltcg_dtaa"),
        },
        "InStcg20Per": {
            "CurrYearIncome": gross_income("stcg20"),
            "StclSetoff30Per": setoff("stcg30", "stcg20"),
            "StclSetoffAppRate": setoff("stcg_app", "stcg20"),
            "StclSetoffDTAARate": setoff("stcg_dtaa", "stcg20"),
            "CurrYrCapGain": net_remaining("stcg20"),
        },
        "InStcg30Per": {
            "CurrYearIncome": gross_income("stcg30"),
            "StclSetoff20Per": setoff("stcg20", "stcg30"),
            "StclSetoffAppRate": setoff("stcg_app", "stcg30"),
            "StclSetoffDTAARate": setoff("stcg_dtaa", "stcg30"),
            "CurrYrCapGain": net_remaining("stcg30"),
        },
        "InStcgAppRate": {
            "CurrYearIncome": gross_income("stcg_app"),
            "StclSetoff20Per": setoff("stcg20", "stcg_app"),
            "StclSetoff30Per": setoff("stcg30", "stcg_app"),
            "StclSetoffDTAARate": setoff("stcg_dtaa", "stcg_app"),
            "CurrYrCapGain": net_remaining("stcg_app"),
        },
        "InStcgDTAARate": {
            "CurrYearIncome": gross_income("stcg_dtaa"),
            "StclSetoff20Per": setoff("stcg20", "stcg_dtaa"),
            "StclSetoff30Per": setoff("stcg30", "stcg_dtaa"),
            "StclSetoffAppRate": setoff("stcg_app", "stcg_dtaa"),
            "CurrYrCapGain": net_remaining("stcg_dtaa"),
        },
        "InLtcg12_5Per": {
            "CurrYearIncome": gross_income("ltcg125"),
            "StclSetoff20Per": setoff("stcg20", "ltcg125"),
            "StclSetoff30Per": setoff("stcg30", "ltcg125"),
            "StclSetoffAppRate": setoff("stcg_app", "ltcg125"),
            "StclSetoffDTAARate": setoff("stcg_dtaa", "ltcg125"),
            "LtclSetOffDTAARate": setoff("ltcg_dtaa", "ltcg125"),
            "CurrYrCapGain": net_remaining("ltcg125"),
        },
        "InLtcgDTAARate": {
            "CurrYearIncome": gross_income("ltcg_dtaa"),
            "StclSetoff20Per": setoff("stcg20", "ltcg_dtaa"),
            "StclSetoff30Per": setoff("stcg30", "ltcg_dtaa"),
            "StclSetoffAppRate": setoff("stcg_app", "ltcg_dtaa"),
            "StclSetoffDTAARate": setoff("stcg_dtaa", "ltcg_dtaa"),
            "LtclSetOff12_5Per": setoff("ltcg125", "ltcg_dtaa"),
            "CurrYrCapGain": net_remaining("ltcg_dtaa"),
        },
        "TotLossSetOff": {
            "StclSetoff20Per": total_setoff("stcg20"),
            "StclSetoff30Per": total_setoff("stcg30"),
            "StclSetoffAppRate": total_setoff("stcg_app"),
            "StclSetoffDTAARate": total_setoff("stcg_dtaa"),
            "LtclSetOff12_5Per": total_setoff("ltcg125"),
            "LtclSetOffDTAARate": total_setoff("ltcg_dtaa"),
        },
        "LossRemainSetOff": {
            "StclSetoff20Per": total_remaining("stcg20"),
            "StclSetoff30Per": total_remaining("stcg30"),
            "StclSetoffAppRate": total_remaining("stcg_app"),
            "StclSetoffDTAARate": total_remaining("stcg_dtaa"),
            "LtclSetOff12_5Per": total_remaining("ltcg125"),
            "LtclSetOffDTAARate": total_remaining("ltcg_dtaa"),
        },
    }


def _schedule_cg(input_data: ITR2Input, result: ITR2Result) -> Optional[dict[str, Any]]:
    """Serialize Schedule CG from actual classified transactions."""
    # Phase 6i-5: a taxpayer with ONLY NRI-proviso-48/115F bare entries or
    # DTAA claim rows (no ordinary cg_transactions/112A scrips/VDA) still
    # has real, taxed capital-gains data -- the presence gate must include
    # these or the schedule would silently vanish while Part B-TI still
    # shows a nonzero CapGain figure with no supporting disclosure.
    has_nri_cg_data = (
        input_data.cg_nri_stcg_stt_paid > _ZERO or input_data.cg_nri_stcg_stt_not_paid > _ZERO
        or input_data.cg_nri_ltcg_without_indexation > _ZERO or input_data.cg_nri_115f_sale_value > _ZERO
        or input_data.cg_stcg_dtaa_entries or input_data.cg_ltcg_dtaa_entries
    )
    if (
        not input_data.cg_transactions and not input_data.cg_112a_scrips
        and not input_data.vda_transactions and not has_nri_cg_data
    ):
        return None
    cg = result.schedules.get("cg")
    z = _ZERO
    stcg = getattr(cg, "stcg", None) if cg else None
    ltcg = getattr(cg, "ltcg", None) if cg else None
    post_loss = result.schedules.get("post_loss_cg", {})
    # Section 115AD: an FII/FPI's OWN capital gains on securities route to
    # a parallel set of Schedule-CG fields (NRISecur115AD/
    # NRISaleOfEquityShareUs112A/NRIOnSec112and115Dtls/EquityMFonSTT's
    # "5AD1biip" code) instead of the ordinary ones -- same underlying tax
    # treatment (calculators/itr2.py already computes identical rates),
    # this is purely a disclosure-routing decision keyed off the filing
    # profile's own FII/FPI flag.
    is_fii_fpi = bool(input_data.filing_profile and input_data.filing_profile.is_fii_fpi)

    # Land/building STCG rows
    stcg_land_rows = []
    for asset in (getattr(stcg, "land_building", []) if stcg else []):
        stcg_land_rows.append(_cg_land_building_row_stcg(asset))
    # Land/building LTCG rows
    ltcg_land_rows = []
    for asset in (getattr(ltcg, "land_building", []) if ltcg else []):
        ltcg_land_rows.append(_cg_land_building_row_ltcg(asset))

    # 111A equity rows (or, for an FII/FPI, the 115AD(1)(b)(ii) proviso
    # equivalent -- same 20% rate, distinct MFSectionCode/SecCode).
    #
    # Official schema: "EquityMFonSTT" is an array capped at maxItems: 2,
    # one row per MFSectionCode ("1A" ordinary / "5AD1biip" FII-FPI), and
    # each row's own "EquityMFonSTTDtls" (EquityOrUnitSec94TypeMFonSTT) is
    # AGGREGATE-ONLY -- no scrip identifier field exists at all. Previously
    # appended one row PER TRANSACTION instead, so any taxpayer with 3+
    # STT-paid equity/MF STCG transactions in the year produced a
    # schema-invalid array (outright validateItr rejection, not a
    # disclosure-quality issue) -- the common case for retail equity
    # investors. `is_fii_fpi` is a single filing-profile-level flag (not
    # per-transaction), so every matching transaction for a given filer
    # always shares the same MFSectionCode -- at most one aggregate row is
    # ever needed, never two, for a single return.
    #
    # Also fixes an incidental bug found while rewriting this exact
    # formula: BalanceCG/CapgainonAssets previously omitted improvement_cost
    # from the subtraction even though DeductSec48.TotalDedn (computed one
    # line below it) already included it -- the two fields disagreed on
    # what "total deduction" meant for the identical transaction.
    equity_111a_rows = []
    matching_111a_txs = [
        tx for tx in input_data.cg_transactions
        if tx.asset_type.value in ("listed_equity_111a", "equity_oriented_fund_111a")
    ]
    if matching_111a_txs:
        total_consideration = sum((tx.full_consideration for tx in matching_111a_txs), z)
        total_acquisition_cost = sum((tx.cost_of_acquisition for tx in matching_111a_txs), z)
        total_improvement_cost = sum((tx.improvement_cost for tx in matching_111a_txs), z)
        total_expenditure = sum((tx.expenditure_on_transfer for tx in matching_111a_txs), z)
        total_deduction = total_acquisition_cost + total_improvement_cost + total_expenditure
        balance_cg = total_consideration - total_deduction
        equity_111a_rows.append({
            "MFSectionCode": "5AD1biip" if is_fii_fpi else "1A",
            "EquityMFonSTTDtls": {
                "FullConsideration": _to_rupees(total_consideration),
                "DeductSec48": {
                    "AquisitCost": _to_rupees(total_acquisition_cost),
                    "ImproveCost": _to_rupees(total_improvement_cost),
                    "ExpOnTrans": _to_rupees(total_expenditure),
                    "TotalDedn": _to_rupees(total_deduction),
                },
                "BalanceCG": _to_rupees(balance_cg),
                "LossSec94of7Or94of8": 0,
                "CapgainonAssets": _to_rupees(balance_cg),
            },
        })

    # Generic "other assets" bucket, split for FII/FPI: securities-type
    # transactions route to the 115AD-specific fields below; non-security
    # types (jewellery/depreciable/foreign/other) always stay in the
    # ordinary bucket regardless of FII/FPI status.
    other_asset_types_ordinary = (
        _GENERIC_OTHER_ASSET_TYPES - _FII_SECURITIES_ASSET_TYPES if is_fii_fpi
        else _GENERIC_OTHER_ASSET_TYPES
    )
    stcg_other_ordinary = _other_assets_block(input_data.cg_transactions, is_long_term=False, asset_types=other_asset_types_ordinary)
    ltcg_other_ordinary = _other_assets_block(input_data.cg_transactions, is_long_term=True, asset_types=other_asset_types_ordinary)
    fii_stcg_securities = None
    fii_ltcg_securities = None
    if is_fii_fpi:
        fii_stcg_securities = _other_assets_block(input_data.cg_transactions, is_long_term=False, asset_types=_FII_SECURITIES_ASSET_TYPES)
        fii_ltcg_securities = _other_assets_block(input_data.cg_transactions, is_long_term=True, asset_types=_FII_SECURITIES_ASSET_TYPES)

    # Section 112A summary (Schedule CG item 3a/3c, "LTCG u/s 112A (column
    # 14 of Schedule 112A)") -- the GROSS per-scrip aggregate before the
    # ₹1.25L annual threshold (that threshold is applied separately, only
    # for Schedule-SI tax purposes via compute_112a_taxable()), routed to
    # the FII-specific field instead when FII/FPI. Previously hardcoded to
    # zero regardless of actual 112A gain or FII status.
    gain_112a = getattr(ltcg, "income_112a", z) if ltcg else z
    # Section 54F on 112A-eligible gains: attributable only to CGTransaction
    # rows classified into the 112A basket (`cg_112a_scrips`'s own
    # CG112AScrip type has no `exemptions` field at all -- a separate,
    # narrower pre-existing limitation of the explicit-scrip path, not
    # expanded here).
    _112a_types = {"listed_equity_112a", "equity_oriented_fund_112a", "business_trust_unit_112a"}
    ded_54f_112a = sum(
        (
            _exemption_claim_total(getattr(tx, "exemptions", None), frozenset({"54F"}))
            for tx in input_data.cg_transactions
            if (tx.asset_type.value if hasattr(tx.asset_type, "value") else tx.asset_type) in _112a_types
        ),
        _ZERO,
    )
    equity_share_112a_block = {
        "BalanceCG": _to_rupees(gain_112a),
        "DeductionUs54F": _to_rupees(ded_54f_112a),
        "CapgainonAssets": _to_rupees(gain_112a - ded_54f_112a),
    }

    exemptions = getattr(cg, "exemptions", None) if cg else None
    total_54 = getattr(exemptions, "section_54", z) if exemptions else z
    total_54b = getattr(exemptions, "section_54b", z) if exemptions else z
    total_54ec = getattr(exemptions, "section_54ec", z) if exemptions else z
    total_54f = getattr(exemptions, "section_54f", z) if exemptions else z
    total_exempt = getattr(exemptions, "total_exemption", z) if exemptions else z

    # Schedule CG items A8/B11 -- DTAA-rate capital-gains claims (official
    # NRIDTAADtls). "Not chargeable in India" (A8a/B11a, rate_as_per_treaty
    # == 0 / NIL -- the form's own literal instruction for that column) is
    # excluded from the taxable STCG/LTCG total entirely (a treaty
    # exemption); "chargeable at DTAA special rate" (A8b/B11b) is already
    # counted in the underlying item and only re-tagged here for rate
    # disclosure -- both totals are real regardless.
    def _cg_dtaa_rows(entries) -> list[dict[str, Any]]:
        return [
            {
                "DTAAamt": _to_rupees(e.amount),
                "ItemNoincl": e.item_no_incl,
                "CountryName": e.country_name,
                "CountryCodeExcludingIndia": e.country_code,
                "DTAAarticle": e.dtaa_article,
                "RateAsPerTreaty": float(e.rate_as_per_treaty),
                "TaxRescertifiedFlag": e.tax_residency_certificate,
                "SecITAct": e.sec_it_act,
                "RateAsPerITAct": float(e.rate_as_per_it_act),
                "ApplicableRate": float(e.applicable_rate),
            }
            for e in entries
        ]

    stcg_dtaa_rows = _cg_dtaa_rows(input_data.cg_stcg_dtaa_entries)
    stcg_dtaa_not_chargeable = sum(
        (e.amount for e in input_data.cg_stcg_dtaa_entries if not e.chargeable_in_india), _ZERO,
    )
    stcg_dtaa_chargeable = sum(
        (e.amount for e in input_data.cg_stcg_dtaa_entries if e.chargeable_in_india), _ZERO,
    )
    ltcg_dtaa_rows = _cg_dtaa_rows(input_data.cg_ltcg_dtaa_entries)
    ltcg_dtaa_not_chargeable = sum(
        (e.amount for e in input_data.cg_ltcg_dtaa_entries if not e.chargeable_in_india), _ZERO,
    )
    ltcg_dtaa_chargeable = sum(
        (e.amount for e in input_data.cg_ltcg_dtaa_entries if e.chargeable_in_india), _ZERO,
    )

    stcg_block: dict[str, Any] = {
        "SaleofLandBuild": {"SaleofLandBuildDtls": stcg_land_rows},
        "EquityMFonSTT": equity_111a_rows,
        # Schedule CG item A3 -- "for NON-RESIDENT, not being an FII, from
        # sale of shares or debentures of an Indian company (to be computed
        # with foreign exchange adjustment under first proviso to section
        # 48)". Confirmed by reading the official form directly: A3a/A3b
        # are bare, off-form-computed rupee figures, not per-transaction
        # detail.
        "NRITransacSec48Dtl": {
            "NRItaxSTTPaid": _to_rupees(input_data.cg_nri_stcg_stt_paid),
            "NRItaxSTTNotPaid": _to_rupees(input_data.cg_nri_stcg_stt_not_paid),
        },
        "NRISecur115AD": fii_stcg_securities if fii_stcg_securities is not None else _equity_or_unit_sec94(),
        "SaleOnOtherAssets": stcg_other_ordinary,
        "UnutilizedStcgFlag": "N",
        "AmtDeemedStcg": 0,
        "TotalAmtDeemedStcg": 0,
        "PassThrIncNatureSTCG": 0,
        "PassThrIncNatureSTCG20Per": 0,
        "PassThrIncNatureSTCG30Per": 0,
        "PassThrIncNatureSTCGAppRate": 0,
        **({"NRICgDTAA": {"NRIDTAADtls": stcg_dtaa_rows}} if stcg_dtaa_rows else {}),
        "TotalAmtNotTaxUsDTAAStcg": _to_rupees(stcg_dtaa_not_chargeable),
        "TotalAmtTaxUsDTAAStcg": _to_rupees(stcg_dtaa_chargeable),
        "CapitalLossBuyBackShares": {"CapitalLossBuyBackSharesDtls": [], "TotalCapitalLossBuyBackShares": 0},
        "TotalSTCG": _to_rupees(getattr(stcg, "total_stcg", z) if stcg else z),
    }
    ltcg_block: dict[str, Any] = {
        "SaleofLandBuild": {
            "SaleofLandBuildDtls": ltcg_land_rows,
            "TotalExcessTax": _to_rupees(getattr(ltcg, "total_excess_tax_112_1a", _ZERO) if ltcg else _ZERO),
            "TotalLTCGImmblPrprty": _to_rupees(sum((r["LTCGonImmvblPrprty"] for r in ltcg_land_rows), _ZERO)),
        },
        "Proviso112Applicable": [],
        "SaleOfEquityShareUs112A": _equity_share_112a() if is_fii_fpi else equity_share_112a_block,
        "NRIProvisoSec48": _nri_proviso_48(input_data),
        "NRISaleOfEquityShareUs112A": equity_share_112a_block if is_fii_fpi else _equity_share_112a(),
        "NRISaleofForeignAsset": _nri_foreign_asset(input_data),
        "SaleofAssetNADtls": {"SaleofAssetNA": ltcg_other_ordinary},
        **(
            {"NRIOnSec112and115": {"NRIOnSec112and115Dtls": [
                {"SectionCode": "5ADiii", **fii_ltcg_securities}
            ]}}
            if is_fii_fpi and fii_ltcg_securities is not None and fii_ltcg_securities["FullConsideration"] > 0
            else {}
        ),
        "UnutilizedLtcgFlag": "N",
        "AmtDeemedLtcg": 0,
        "TotalAmtDeemedLtcg": 0,
        "PassThrIncNatureLTCG": 0,
        "PassThrIncNatureLTCGUs112A12_5Per": 0,
        "PassThrIncNatureLTCG12_5Per": 0,
        **({"NRICgDTAA": {"NRIDTAADtls": ltcg_dtaa_rows}} if ltcg_dtaa_rows else {}),
        "TotalAmtNotTaxUsDTAALtcg": _to_rupees(ltcg_dtaa_not_chargeable),
        "CapitalLossBuyBackShares": {"TotalCapitalLossBuyBackShares": 0},
        "TotalAmtTaxUsDTAALtcg": _to_rupees(ltcg_dtaa_chargeable),
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
            "DeducClaimDtlsUs115F": _deduction_claim_detail_rows(input_data.cg_transactions, "115F"),
            "DeducClaimDtlsUs54": _deduction_claim_detail_rows(input_data.cg_transactions, "54"),
            "DeducClaimDtlsUs54B": _deduction_claim_detail_rows(input_data.cg_transactions, "54B"),
            "DeducClaimDtlsUs54EC": _deduction_claim_detail_rows(input_data.cg_transactions, "54EC"),
            "DeducClaimDtlsUs54F": _deduction_claim_detail_rows(input_data.cg_transactions, "54F"),
            "TotDeductClaim": _to_rupees(total_exempt),
        },
        "CurrYrLosses": _cg_loss_setoff_table(result),
        "IncmFromVDATrnsf": vda_inc,
        "AccruOrRecOfCG": _accrued_cg(input_data, result),
        "SumOfCGIncm": total_cg,
        "TotScheduleCGFor23": total_cg,
    }


_LAND_BUILDING_EXEMPTION_SECCODES = ("54", "54B", "54EC", "54F")


def _claim_amount(claim: Any) -> Decimal:
    """Return one canonical exemption claim's disclosed amount."""
    investment = getattr(claim, "investment_amount", None) or _ZERO
    cgas = getattr(claim, "cgas_deposit_amount", None) or _ZERO
    return investment + cgas


def _exemption_or_dedn_us54_block(exemptions: Optional[list], seccodes: tuple) -> dict[str, Any]:
    """Build one land/building row's nested ExemptionOrDednUs54SaleLandType
    block: a per-code (54/54B/54EC/54F) breakdown of THIS asset's own
    exemption claims. ExemptionOrDednUs54Dtls is schema-optional (only
    ExemptionGrandTotal is required), so it is omitted entirely when this
    asset has no claims -- not emitted as an empty placeholder array.
    """
    dtls = []
    grand_total = _ZERO
    for code in seccodes:
        amount = sum(
            (_claim_amount(c) for c in (exemptions or []) if getattr(c, "section", None) == code),
            _ZERO,
        )
        if amount > 0:
            dtls.append({"ExemptionSecCode": code, "ExemptionAmount": _to_rupees(amount)})
            grand_total += amount
    result: dict[str, Any] = {"ExemptionGrandTotal": _to_rupees(grand_total)}
    if dtls:
        result["ExemptionOrDednUs54Dtls"] = dtls
    return result


def _deduction_claim_detail_rows(transactions: list, section: str) -> list[dict[str, Any]]:
    """Build the top-level DeducClaimDtlsUs{54,54B,54EC,54F,115F} rows from
    every transaction's own canonical exemption claims for one section,
    regardless of which Schedule CG bucket the transaction itself belongs
    to (land/building, generic-other, 112A) -- these are flat, section-only
    arrays at the DeducClaimInfo level, not per-bucket.
    """
    rows: list[dict[str, Any]] = []
    for tx in transactions or []:
        for claim in getattr(tx, "exemptions", None) or []:
            if getattr(claim, "section", None) != section:
                continue
            investment_amount = getattr(claim, "investment_amount", None) or _ZERO
            investment_date = getattr(claim, "investment_date", None)
            cgas_amount = getattr(claim, "cgas_deposit_amount", None) or _ZERO
            amt_deducted = investment_amount + cgas_amount
            row: dict[str, Any] = {
                "DateofTransfer": claim.transfer_date.isoformat(),
                "AmtDeducted": _to_rupees(amt_deducted),
            }
            if section in ("54", "54F"):
                row["CostofNewResHouse"] = _to_rupees(investment_amount)
                if investment_date is not None:
                    row["DateofPurchase"] = investment_date.isoformat()
            elif section == "54B":
                row["CostofNewAgriLand"] = _to_rupees(investment_amount)
                if investment_date is not None:
                    row["DateofPurchase"] = investment_date.isoformat()
            else:  # 54EC / 115F -- no CGAS scheme exists for these sections
                row["AmtInvested"] = _to_rupees(investment_amount)
                # DateofInvestment is required for both; the canonical
                # schema guarantees investment_date is set whenever
                # investment_amount > 0, but fall back to the transfer
                # date for a genuinely zero-investment (CGAS-only) claim
                # rather than omit a required field.
                row["DateofInvestment"] = (investment_date or claim.transfer_date).isoformat()
            if section in ("54", "54B", "54F") and cgas_amount > 0:
                row["AmtDeposited"] = _to_rupees(cgas_amount)
                if getattr(claim, "cgas_deposit_date", None) is not None:
                    row["DepositDate"] = claim.cgas_deposit_date.isoformat()
                if getattr(claim, "cgas_account_number", None):
                    row["AccountNo"] = claim.cgas_account_number
                if getattr(claim, "cgas_ifsc", None):
                    row["IFSC"] = claim.cgas_ifsc
            rows.append(row)
    return rows


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
        "DeductionUs54B": _to_rupees(getattr(asset, "exemption_total", _ZERO)),
        "STCGonImmvblPrprty": _to_rupees(asset.balance - getattr(asset, "exemption_total", _ZERO)),
    }


def _cg_land_building_row_ltcg(asset: Any) -> dict[str, Any]:
    """Build one Schedule CG LTCG SaleofLandBuildDtls row.

    Field names match ``LongTermCapGain23.SaleofLandBuild.SaleofLandBuildDtls``
    exactly -- see ``_cg_land_building_row_stcg``'s docstring for why the
    previous shared implementation was wrong for both STCG and LTCG.

    The official schema additionally carries a second, indexed-cost-basis
    total/balance/tax-comparison track (``TotalDednForEiB``, ``BalanceForEiB``,
    ``LTCGonImmvblPrprtyBE``, ``TaxSec1121aiiB``, ``TaxSec1121a``,
    ``ExcessAmtSec1121a``) -- the section 112(1)(a) second-proviso comparison
    for residents who acquired before 23-Jul-2024, protecting against a tax
    increase from the 2024 indexation-removal change. ``compute_ltcg()``
    computes these per asset (``asset.eib_applicable``/``balance_for_eib``/
    etc.); none of these fields are schema-``required``, so they are omitted
    entirely (not zero-placeholder emitted) when the row isn't eligible.
    """
    stamp_value = getattr(asset, "stamp_duty_value", _ZERO) or _ZERO
    deemed = deemed_consideration_50c(asset.full_consideration, stamp_value)
    row: dict[str, Any] = {
        "DateofPurchase": asset.date_of_acquisition or "",
        "DateofSale": asset.date_of_transfer,
        "FullConsideration": _to_rupees(asset.full_consideration),
        "PropertyValuation": _to_rupees(stamp_value),
        "FullConsideration50C": _to_rupees(deemed),
        "AquisitCost": _to_rupees(asset.acquisition_cost),
        "AquisitCostIndex": _to_rupees(asset.indexed_acquisition_cost),
        # Unlike STCG's flat ImproveCost, the LTCG schema's CostOfImprovements
        # is a nested object with a per-improvement detail array (one
        # aggregate row when year_of_improvement is known -- CBDT rule #186)
        # plus indexed/non-indexed totals.
        "CostOfImprovements": {
            "CostOfImprovementsDtls": (
                [{
                    "slno": 1,
                    "ImproveCost": _to_rupees(asset.improvement_cost),
                    "ImproveDate": asset.year_of_improvement,
                    "CostOfImpIndex": _to_rupees(asset.indexed_improvement_cost),
                }]
                if asset.improvement_cost > 0 and asset.year_of_improvement
                else []
            ),
            "TotalImprovecost": _to_rupees(asset.improvement_cost),
            "TotalindexImprovecost": _to_rupees(asset.indexed_improvement_cost),
        },
        "ExpOnTrans": _to_rupees(asset.expenditure_on_transfer),
        "TotalDedn": _to_rupees(asset.total_deductions),
        "Balance": _to_rupees(asset.balance),
        # Like CostOfImprovements, this is a nested exemption-detail block
        # (ExemptionOrDednUs54SaleLandType), not a flat integer -- per-code
        # (54/54B/54EC/54F) breakdown of this asset's own exemption claims.
        "ExemptionOrDednUs54": _exemption_or_dedn_us54_block(getattr(asset, "exemptions", None), _LAND_BUILDING_EXEMPTION_SECCODES),
        "LTCGonImmvblPrprty": _to_rupees(asset.balance - getattr(asset, "exemption_total", _ZERO)),
    }
    if getattr(asset, "eib_applicable", False):
        indexed_acquisition = asset.indexed_acquisition_cost or asset.acquisition_cost
        indexed_improvement = asset.indexed_improvement_cost or asset.improvement_cost
        total_dedn_for_eib = indexed_acquisition + indexed_improvement + asset.expenditure_on_transfer
        row["TotalDednForEiB"] = _to_rupees(total_dedn_for_eib)
        row["BalanceForEiB"] = _to_rupees(asset.balance_for_eib)
        # "1ea = 1ca - 1d" per the form's own text -- same exemption total
        # ("1d") subtracted from both the primary and EiB tracks.
        row["LTCGonImmvblPrprtyBE"] = _to_rupees(
            max(_ZERO, asset.balance_for_eib - getattr(asset, "exemption_total", _ZERO))
        )
        row["TaxSec1121a"] = _to_rupees(asset.tax_sec_112_1a)
        row["TaxSec1121aiiB"] = _to_rupees(asset.tax_sec_112_1a_iib)
        row["ExcessAmtSec1121a"] = _to_rupees(asset.excess_amt_sec_112_1a)
    return row


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


def _nri_proviso_48(input_data: ITR2Input) -> dict[str, int]:
    """Schedule CG item B4 -- "for NON-RESIDENTS, from sale of unlisted
    shares or listed debenture of Indian company (to be computed with
    foreign exchange adjustment under first proviso to section 48)".
    Confirmed by reading the official form directly: B4a is a bare,
    off-form-computed rupee figure, not a per-transaction breakdown."""
    ltcg_without_benefit = input_data.cg_nri_ltcg_without_indexation
    deduction_54f = input_data.cg_nri_ltcg_deduction_54f
    return {
        "LTCGWithoutBenefit": _to_rupees(ltcg_without_benefit),
        "DeductionUs54F": _to_rupees(deduction_54f),
        "BalanceCG": _to_rupees(max(_ZERO, ltcg_without_benefit - deduction_54f)),
    }


def _nri_foreign_asset(input_data: ITR2Input) -> dict[str, int]:
    """Schedule CG item B7 -- "sale of foreign exchange asset by
    NON-RESIDENT INDIAN (if opted under chapter XII-A)", section 115F.
    Same bare direct-entry pattern as B4, aggregated across the draft's own
    generic ``ltForeignAssets`` row list (the form's own B7 is a single
    pair, 7a/7b, not per-row)."""
    sale_value = input_data.cg_nri_115f_sale_value
    deduction = input_data.cg_nri_115f_deduction
    return {
        "SaleonSpecAsset": _to_rupees(sale_value),
        "DednSpecAssetus115": _to_rupees(deduction),
        "BalonSpeciAsset": _to_rupees(max(_ZERO, sale_value - deduction)),
    }


def _cg_quarter_index(transfer_date: Any) -> int:
    """Return which of the official form's 5 accrual periods (0-4) a
    transfer date falls in -- Table F's own period definitions: upto
    15/6, 16/6-15/9, 16/9-15/12, 16/12-15/3, 16/3-31/3."""
    month, day = transfer_date.month, transfer_date.day
    if month in (4, 5) or (month == 6 and day <= 15):
        return 0
    if (month == 6 and day > 15) or month in (7, 8) or (month == 9 and day <= 15):
        return 1
    if (month == 9 and day > 15) or month in (10, 11) or (month == 12 and day <= 15):
        return 2
    if (month == 12 and day > 15) or month in (1, 2) or (month == 3 and day <= 15):
        return 3
    return 4


def _accrued_cg(input_data: ITR2Input, result: ITR2Result) -> dict[str, Any]:
    """Build Schedule CG's own Table F (`AccruOrRecOfCG`) -- which of the
    official form's 5 periods each rate bucket's gain actually accrued in.
    Previously always the zero default regardless of real transaction
    dates, despite every transaction's own transfer date already being
    captured and used elsewhere in this same schedule for the STCG/LTCG
    classification split itself.

    Land/building reuses the calculator's own already-computed per-asset
    signed gain (``asset.balance``, which already reflects section 50C
    deeming and indexation) rather than re-deriving it. Generic-other and
    section 112A/115AD scrip gains use a simplified per-transaction
    formula that does not replicate section 50CA deeming (unlisted shares)
    or section 112A grandfathering -- both are narrow refinements applied
    at the aggregate level elsewhere in this schedule, not preserved
    per-transaction, and reproducing them exactly per-transaction would
    not even reconcile back to those aggregate figures (50CA deeming in
    particular is not distributive over a sum). This table has no
    downstream consumer -- an informational disclosure supporting the
    taxpayer's own section 234C interest position, not re-read by any
    other part of this JSON (unlike Table E/`CurrYrLosses`, whose own
    figures Part B-TI's form instructions explicitly cite) -- so an
    honestly-labeled approximation here is preferable to fabricating exact
    figures this pipeline cannot actually derive per-transaction. The
    always-zero applicable-rate/DTAA buckets match every other Schedule
    CG/Part B-TI disclosure in this builder, which has no data source for
    those buckets either.
    """
    from app.engine.schedules.capital_gains import _is_short_term, _parse_date

    buckets: dict[str, list[Decimal]] = {
        "stcg20": [_ZERO] * 5,
        "stcg30": [_ZERO] * 5,
        "ltcg125": [_ZERO] * 5,
        "vda": [_ZERO] * 5,
    }

    def add(bucket: str, transfer_date: Any, amount: Decimal) -> None:
        # Table F discloses accrual of GAIN specifically (its own schema
        # fields are non-negative) -- a loss-making transaction has no gain
        # to accrue in any quarter, matching how a signed loss doesn't
        # reduce another quarter's own disclosed figure either.
        amount = max(_ZERO, amount)
        if transfer_date is None or amount == _ZERO:
            return
        buckets[bucket][_cg_quarter_index(transfer_date)] += amount

    for tx in input_data.cg_transactions:
        asset_type = tx.asset_type.value if hasattr(tx.asset_type, "value") else tx.asset_type
        is_111a = asset_type in ("listed_equity_111a", "equity_oriented_fund_111a")
        if not is_111a and asset_type not in _GENERIC_OTHER_ASSET_TYPES:
            continue  # land/building (below) or 112A (via cg_112a_scrips/cg_115ad_scrips)
        gain = tx.full_consideration - tx.cost_of_acquisition - tx.improvement_cost - tx.expenditure_on_transfer
        if is_111a:
            add("stcg20", tx.date_of_transfer, gain)
            continue
        is_short = True
        if tx.date_of_acquisition is not None:
            is_short = _is_short_term(asset_type, tx.date_of_acquisition, tx.date_of_transfer)
        elif tx.explicit_long_term is not None:
            is_short = not tx.explicit_long_term
        add("stcg30" if is_short else "ltcg125", tx.date_of_transfer, gain)

    cg = result.schedules.get("cg")
    stcg = getattr(cg, "stcg", None) if cg else None
    ltcg = getattr(cg, "ltcg", None) if cg else None
    for asset in (getattr(stcg, "land_building", []) if stcg else []):
        add("stcg30", _parse_date(asset.date_of_transfer), asset.balance)
    for asset in (getattr(ltcg, "land_building", []) if ltcg else []):
        add("ltcg125", _parse_date(asset.date_of_transfer), asset.balance)

    for scrip in (*input_data.cg_112a_scrips, *input_data.cg_115ad_scrips):
        # `scrip.total_deductions` is a redundant disclosure-only summary
        # field (validated, when supplied, to equal cost + expenditure --
        # see the identical fix and rationale in
        # capital_gains.py::compute_112a()) and must not also be subtracted
        # here alongside cost_acq_without_index/expenditure_on_transfer, or
        # this simplified approximation double-counts the same deduction.
        gain = scrip.total_sale_value - scrip.cost_acq_without_index - scrip.expenditure_on_transfer
        add("ltcg125", scrip.date_of_transfer, gain)

    # VDA transfers (section 115BBH, 30% flat) -- each transaction already
    # carries its own date_of_transfer and directly computable income
    # (mirroring _schedule_vda()'s own income-derivation formula), unlike
    # the always-zero applicable-rate/DTAA buckets below, which have no
    # data source anywhere in this builder. Previously omitted entirely
    # rather than even zero-filled, despite the schema's own dedicated
    # VDATrnsfGainsUnder30Per field for exactly this.
    for vda in input_data.vda_transactions:
        income = (
            vda.income_from_vda if vda.income_from_vda is not None
            else max(_ZERO, vda.consideration_received - vda.acquisition_cost)
        )
        add("vda", vda.date_of_transfer, income)

    zero_dr = _date_range()
    return {
        "ShortTermUnder20Per": _date_range(*buckets["stcg20"]),
        "ShortTermUnder30Per": _date_range(*buckets["stcg30"]),
        "ShortTermUnderAppRate": zero_dr,
        "ShortTermUnderDTAARate": zero_dr,
        "LongTermUnder12_5Per": _date_range(*buckets["ltcg125"]),
        "LongTermUnderDTAARate": zero_dr,
        "VDATrnsfGainsUnder30Per": _date_range(*buckets["vda"]),
    }


# ============================================================================
# Schedule 112A
# ============================================================================

_112A_ELIGIBLE_TX_TYPES = frozenset({"listed_equity_112a", "equity_oriented_fund_112a", "business_trust_unit_112a"})


def _112a_source_rows(
    explicit_scrips: list, transactions: list
) -> list[dict[str, Any]]:
    """Build the common per-row working dicts shared by Schedule112A and
    Schedule115AD from a set of explicit ``CG112AScrip`` rows plus any
    112A-eligible ``CGTransaction`` rows entered through the generic
    capital-gains editor (not just the dedicated scrip-editor rows) --
    matching how ``_schedule_112a()`` always sourced both before this
    function was split out."""
    source_rows: list[dict[str, Any]] = []
    for item in explicit_scrips:
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
    for tx in transactions:
        if tx.asset_type.value not in _112A_ELIGIBLE_TX_TYPES:
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
    return source_rows


def _112a_style_schedule(source_rows: list[dict[str, Any]], suffix: str) -> Optional[dict[str, Any]]:
    """Build a Schedule112A- or Schedule115AD-shaped object from source
    rows. Both official schedules share an identical per-row type
    (``Schedule112A115ADType``) and an identical set of aggregate fields,
    differing only by a ``112A``/``115AD`` field-name suffix -- so one
    shared builder serves both schedules.

    CBDT rules #85/86/92/93 (ITR-2 official Validation Rules PDF) read
    "Col. 7 Cost of acquisition without indexation should be higher of
    Col. 8 and Col. 9" -- which by label would suggest the ``deemed_cost``
    grandfathering formula below (``max(cost, min(fmv, sale))``) belongs in
    the ``CostAcqWithoutIndx`` output key, not ``AcquisitionCost``. This was
    investigated (2026-09-12): the official ITR-2 JSON schema
    (``Reference Docs by CBDT & ITD/Official JSON Schema/ITR-2_2026_Main_
    V1.1 (2).json``) confirms both keys exist as separate mandatory fields
    on ``Schedule112A115ADType`` but carries no field-level description text
    to resolve which is which, and the gazetted ITR-2 form PDF (``Official
    ITR FORMS/ITR-2-2026-Eng.pdf``) does not print Schedule 112A's own
    per-scrip column table (only cross-references it from Schedule CG). No
    primary source available in this repo definitively confirms which key
    the grandfathering formula belongs in -- current code's split (raw
    ``item["cost"]`` -> ``CostAcqWithoutIndx``, ``deemed_cost`` ->
    ``AcquisitionCost``) is applied consistently at both row and aggregate
    level, so this is not an obviously-accidental swap either. Do not change
    this assignment without either (a) a live ITD ``validateItr``/portal
    test distinguishing the two field values, or (b) locating an actual
    field-description source -- guessing from the JSON key name alone risks
    the exact class of bug this codebase has already been burned by (see
    CLAUDE.md's note on ``ITR{N}_TaxComputation.NetTaxLiability``). Rules
    #85/86/92/93 remain tracked as Partially Implemented pending that
    verification, not Implemented or silently "fixed"."""
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
    # Sum the rows' own (already row-clamped) LTCGBeforelowerB1B2 values,
    # not a bucket-level max(0, sale-cost) recomputation -- when scrips mix
    # gains and losses, clamping each row to 0 before summing gives a
    # different (correct, schema-consistent) total than clamping the
    # summed bucket totals afterward (e.g. two scrips +20,000/-20,000: the
    # loss row clamps to 0 individually, so the true sum is 20,000, not the
    # bucket formula's max(0, 0) = 0).
    ltcg_before_lower_b1b2 = sum(r["LTCGBeforelowerB1B2"] for r in rows)
    return {
        f"Schedule{suffix}Dtls": rows,
        f"SaleValue{suffix}": sale,
        f"CostAcqWithoutIndx{suffix}": raw_cost,
        f"AcquisitionCost{suffix}": _to_rupees(acquisition),
        f"LTCGBeforelowerB1B2{suffix}": ltcg_before_lower_b1b2,
        f"FairMktValueCapAst{suffix}": fmv,
        f"ExpExclCnctTransfer{suffix}": _to_rupees(expenses),
        f"Deductions{suffix}": deductions,
        f"Balance{suffix}": balance,
        f"TotalBalance{suffix}": balance,
    }


def _schedule_112a(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize the resident-taxpayer Schedule 112A scrip table.

    Routing between this and ``_schedule_115ad()`` is entirely determined
    by the assessee's own FII/FPI status (matching how ``_schedule_cg()``'s
    aggregate-level 112A routing already works) -- not by which of
    ``cg_112a_scrips``/``cg_115ad_scrips`` a given scrip happens to sit in.
    Both explicit-scrip lists are unioned here so a scrip is never silently
    dropped from disclosure just because it arrived through the "wrong"
    list for a caller that doesn't distinguish them (the calculator itself
    already unions both for tax computation, for the same reason). An
    assessee is never both FII/FPI and not in the same return, so exactly
    one of this function and ``_schedule_115ad()`` ever returns non-None.
    """
    is_fii_fpi = bool(input_data.filing_profile and input_data.filing_profile.is_fii_fpi)
    if is_fii_fpi:
        return None
    explicit_scrips = [*input_data.cg_112a_scrips, *input_data.cg_115ad_scrips]
    source_rows = _112a_source_rows(explicit_scrips, input_data.cg_transactions)
    return _112a_style_schedule(source_rows, "112A")


def _schedule_115ad(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize the FII/FPI-specific Schedule 115AD scrip table -- the
    official form's "115AD(1)(b)(iii) proviso" table, structurally
    identical to Schedule 112A but for exactly this taxpayer population.
    Previously never built at all; FII/FPI scrips fell into
    ``_schedule_112a()`` (the resident taxpayer's table) despite the
    frontend/draft already modeling the split via
    ``CapitalGainsSchedule.schedule115AD``. See ``_schedule_112a()``'s own
    docstring for why both explicit-scrip lists are unioned here too.
    """
    is_fii_fpi = bool(input_data.filing_profile and input_data.filing_profile.is_fii_fpi)
    if not is_fii_fpi:
        return None
    explicit_scrips = [*input_data.cg_112a_scrips, *input_data.cg_115ad_scrips]
    source_rows = _112a_source_rows(explicit_scrips, input_data.cg_transactions)
    return _112a_style_schedule(source_rows, "115AD")


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

# Maps the deduction engine's internal breakdown keys to the official
# Schedule VIA named field. Internal keys with no official ITR-2 field at
# all (80-IA/80-IB/80-IC/10AA/80RA -- business-income-linked sections that
# cannot arise on this form, since ITR-2 excludes profits and gains of
# business or profession) are deliberately absent; see the fail-loud check
# in _schedule_via() below if one somehow appears with a nonzero amount.
_VIA_SECTION_TO_FIELD: dict[str, str] = {
    "80C": "Section80C",
    "80CCC": "Section80CCC",
    "80CCD(1)": "Section80CCDEmployeeOrSE",
    "80CCD(1B)": "Section80CCD1B",
    "80CCD(2)": "Section80CCDEmployer",
    "80CCH": "AnyOthSec80CCH",
    "80D": "Section80D",
    "80DD": "Section80DD",
    "80DDB": "Section80DDB",
    "80U": "Section80U",
    "80TTA": "Section80TTA",
    "80TTB": "Section80TTB",
    "80E": "Section80E",
    "80EE": "Section80EE",
    "80EEA": "Section80EEA",
    "80EEB": "Section80EEB",
    "80G": "Section80G",
    "80GG": "Section80GG",
    "80GGA": "Section80GGA",
    "80GGC": "Section80GGC",
    "80QQB": "Section80QQB",
    "80RRB": "Section80RRB",
}


def _schedule_via(result: ITR2Result, input_data: Optional[ITR2Input] = None) -> Optional[dict[str, Any]]:
    """Serialize Schedule VIA with the real per-section breakdown.

    ``result.schedules["deductions"].breakdown`` already holds each
    section's own statutory-capped, GTI-capped amount (see
    ``app/engine/schedules/deductions/__init__.py``'s ``_add()``, where
    every section module's own ``compute_details().allowed_deduction`` is
    already post-cap, and ``_cap_breakdown_to_gti()``, which applies the
    aggregate GTI-availability cap on top) -- exactly the figure the
    official schema's ``DeductUndChapVIA`` wants for each named section
    field. ``UsrDeductUndChapVIA`` is meant to carry the taxpayer's own
    claimed (pre-cap) amount; this codebase does not separately track a
    raw, uncapped figure per section today (each section module already
    enforces its own statutory cap before returning ``allowed_deduction``,
    and the frontend/Pydantic input layer already bounds most sections at
    or below their statutory limit before compute ever runs), so both
    objects are populated from the same capped breakdown here -- an
    honest interim state: in every case this pipeline can currently
    produce, "claimed" and "allowed" already coincide, since nothing
    upstream lets a taxpayer submit an amount this codebase would then
    reduce. A genuinely separate raw-claim figure would need each of the
    ~20 section modules under app/engine/schedules/deductions/ to report
    its own pre-cap input alongside allowed_deduction -- not attempted
    here.
    """
    if result.deductions_total <= 0:
        return None
    ded = result.schedules.get("deductions")
    breakdown = getattr(ded, "breakdown", {}) if ded else {}

    # "80C" is only present as its own key once _cap_breakdown_to_gti()
    # has run, which only happens when the aggregate GTI cap actually
    # binds (app/engine/schedules/deductions/__init__.py). In the common
    # case (deductions comfortably below GTI) the raw combined key
    # "80C+80CCC+80CCD(1)" -- the shared ₹1.5L section-80CCE ceiling
    # amount -- is what's actually present instead, and would otherwise
    # look like an unrepresentable section. Decompose it the same way
    # ITR-1's own working Schedule VIA builder already does
    # (itd/itr1.py's deduction() closure): subtract out whatever is
    # separately recorded under "80CCC"/"80CCD(1)" to avoid double-
    # counting them once under the combined key and again under their
    # own.
    combined_80c_key = "80C+80CCC+80CCD(1)"
    if "80C" not in breakdown and combined_80c_key in breakdown:
        breakdown = dict(breakdown)
        breakdown["80C"] = max(
            Decimal("0"),
            breakdown.pop(combined_80c_key)
            - breakdown.get("80CCC", Decimal("0"))
            - breakdown.get("80CCD(1)", Decimal("0")),
        )

    unmapped = {
        key: amount for key, amount in breakdown.items()
        if key not in _VIA_SECTION_TO_FIELD and amount > 0
    }
    if unmapped:
        raise ValueError(
            f"Schedule VIA cannot represent deduction section(s) {sorted(unmapped)} -- "
            "no official ITR-2 schema field mapping exists for them (these are "
            "business-income-linked sections that should never reach ITR-2's "
            "deduction breakdown)."
        )

    section_fields: dict[str, int] = {}
    for key, amount in breakdown.items():
        field = _VIA_SECTION_TO_FIELD.get(key)
        if field is not None and amount > 0:
            section_fields[field] = _to_rupees(amount)

    # Required even when unclaimed (schema: DeductUndChapVIA.required
    # includes Section80D/Section80G/Section80GGA alongside the total).
    deduct_und_chap_via: dict[str, Any] = {
        "Section80D": section_fields.get("Section80D", 0),
        "Section80G": section_fields.get("Section80G", 0),
        "Section80GGA": section_fields.get("Section80GGA", 0),
    }
    for field, amount in section_fields.items():
        deduct_und_chap_via.setdefault(field, amount)
    # Sum the already-rounded per-section rupee figures actually emitted,
    # rather than independently rounding result.deductions_total, so this
    # schedule's own total always cross-foots against its own section
    # fields (the same "sibling fields must agree" discipline that a
    # missing cross-foot elsewhere in this codebase has already been
    # found to violate -- see the ITR2_FRONTEND_AND_SERIALIZATION_AUDIT
    # doc's Schedule OS GrossIncChrgblTaxAtAppRate finding).
    deduct_und_chap_via["TotalChapVIADeductions"] = sum(section_fields.values())

    usr_deduct_und_chap_via = dict(deduct_und_chap_via)
    # CBDT rules #693/#758: per-row Section 80CCC pension-fund detail
    # (official schema: UsrDeductUndChapVIA.PensionContribution80CCC only --
    # DeductUndChapVIA has no such array).
    if input_data is not None and input_data.schedule_80ccc_entries:
        usr_deduct_und_chap_via["PensionContribution80CCC"] = [
            {
                "TypeofIdentifier": entry.identifier_type,
                "NameofIdentifier": entry.identifier_name,
                "Amount": _to_rupees(entry.amount),
            }
            for entry in input_data.schedule_80ccc_entries
        ]

    return {
        "UsrDeductUndChapVIA": usr_deduct_und_chap_via,
        "DeductUndChapVIA": deduct_und_chap_via,
    }


# ============================================================================
# Chapter VI-A detail schedules — 80D, 80G, 80GGA, 80GGC, 80DD, 80U
#
# Beyond ScheduleVIA's aggregate per-section figures (above), the official
# schema separately requires six independent top-level schedules carrying
# donee/insurer/dependent-level disclosure for these same sections. The
# eligibility computation itself (per-section statutory caps, GTI capping,
# per-row allocation) already runs identically to ITR-1/ITR-4 via the
# shared `app/engine/schedules/deductions/` engine
# (`app/engine/calculators/itr2.py`'s own `compute_deductions()` call) --
# these builders only serialize that already-computed result, mirroring
# `app/engine/itd/itr1.py`'s proven, production implementation of the same
# six schedules field-for-field (confirmed identical against ITR-2's own
# official schema). Two deliberate differences from ITR-1's version:
# Schedule80DD/80U here also emit `Form10IAFilingDate`/`FormAckNum11A`
# (ITR-2/ITR-3-only schema fields ITR-1/ITR-4 don't have -- the frontend's
# own `DeductionsWorkspace.tsx` already gates these fields on `fullForm10IA
# = form === 'ITR-2' || form === 'ITR-3'`), and Schedule80DD here allows an
# HUF-member dependent (ITR-1 rejects it since ITR-1 is individual-only;
# ITR-2 also files for HUF assessees, for whom this is a valid dependent).
# ============================================================================

def _policy_insurance_details(policies: Optional[list], section_code: str) -> list[dict[str, Any]]:
    """Build ``Sch80DInsDtls`` rows for one 80D bucket from policy entries.

    ``InsurerName``/``PolicyNo`` are both required by the official schema
    (``Sch80DInsDtls.required``) for every row -- ``InsurancePolicy.
    insurer_name``/``policy_number`` are Optional at the Pydantic level
    (a real, user-suppliable claim can genuinely reach this function with
    either left blank), so a missing value here must reject the claim, not
    substitute a fabricated "Not Provided" placeholder string. Emitting a
    fabricated string previously risked a live ITD rejection or defect
    notice, since the official JSON would carry made-up evidentiary data
    rather than what the taxpayer actually entered.
    """
    rows: list[dict[str, Any]] = []
    for p in policies or []:
        if str(getattr(p, "section", "1a")) != section_code:
            continue
        premium = getattr(p, "premium_paid", _ZERO) or _ZERO
        if premium <= _ZERO:
            continue
        insurer = (getattr(p, "insurer_name", None) or "").strip()
        policy_no = (getattr(p, "policy_number", None) or "").strip()
        missing = [
            field for field, value in (("insurer name", insurer), ("policy number", policy_no))
            if not value
        ]
        if missing:
            raise ValueError(
                f"Schedule 80D policy (section {section_code}, premium {premium}) is "
                f"missing: {', '.join(missing)}."
            )
        rows.append({
            "InsurerName": insurer[:125],
            "PolicyNo": policy_no[:75],
            "HealthInsAmt": _to_rupees(premium),
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
    medical_expense_self_senior: Decimal = _ZERO,
    medical_expense_parents_senior: Decimal = _ZERO,
    policies: Optional[list] = None,
) -> dict[str, Any]:
    """Serialize a computed Section 80D result without recalculating eligibility."""
    self_aggregate = (
        eligible_self if eligible_self is not None
        else self_premium + preventive_self + medical_expense_self_senior
    )
    parents_aggregate = (
        eligible_parents if eligible_parents is not None
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
                "TotalPayments": sum((r["HealthInsAmt"] for r in self_non_senior_rows), 0),
            },
            "PrevHlthChckUpSlfFam": _to_rupees(preventive_self) if senior_flag_self == "N" else 0,
            "SelfAndFamilySeniorCitizen": _to_rupees(self_aggregate) if senior_flag_self == "Y" else 0,
            "HlthInsPremSlfFamSrCtzn": _to_rupees(self_premium) if senior_flag_self == "Y" else 0,
            "Sec80DSelfFamSrCtznHIDtls": {
                "Sch80DInsDtls": self_senior_rows,
                "TotalPayments": sum((r["HealthInsAmt"] for r in self_senior_rows), 0),
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
                "TotalPayments": sum((r["HealthInsAmt"] for r in parents_non_senior_rows), 0),
            },
            "PrevHlthChckUpParents": _to_rupees(preventive_parents) if senior_flag_parents == "N" else 0,
            "ParentsSeniorCitizen": _to_rupees(parents_aggregate) if senior_flag_parents == "Y" else 0,
            "HlthInsPremParentsSrCtzn": _to_rupees(parents_premium) if senior_flag_parents == "Y" else 0,
            "Sec80DParentsSrCtznHIDtls": {
                "Sch80DInsDtls": parents_senior_rows,
                "TotalPayments": sum((r["HealthInsAmt"] for r in parents_senior_rows), 0),
            },
            "PrevHlthChckUpParentsSrCtzn": _to_rupees(preventive_parents) if senior_flag_parents == "Y" else 0,
            "MedicalExpParentsSrCtzn": (
                _to_rupees(medical_expense_parents_senior) if senior_flag_parents == "Y" else 0
            ),
            "EligibleAmountOfDedn": _to_rupees(eligible_deduction),
        }
    }


def _donation_address_80g(address: Any) -> dict[str, Any]:
    """Serialize one official donation-recipient address (80G/80GGA)."""
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
                "AddressDetail": _donation_address_80g(source.address),
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


def _schedule_80gga(details: Any) -> dict[str, Any]:
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
            "AddressDetail": _donation_address_80g(computed.source.address),
            "DoneePAN": computed.source.donee_pan,
            "DonationAmtCash": cash,
            "DonationAmtOtherMode": other,
            "DonationAmt": cash + other,
            "EligibleDonationAmt": eligible,
        })
    emitted_eligible = sum(row["EligibleDonationAmt"] for row in rows)
    if emitted_eligible != eligible_rupees:
        raise ValueError("Schedule 80GGA eligible rows do not cross-foot")
    return {
        "DonationDtlsSciRsrchRuralDev": rows,
        "TotalDonationAmtCash80GGA": sum(row["DonationAmtCash"] for row in rows),
        "TotalDonationAmtOtherMode80GGA": sum(row["DonationAmtOtherMode"] for row in rows),
        "TotalDonationsUs80GGA": sum(row["DonationAmt"] for row in rows),
        "TotalEligibleDonationAmt80GGA": emitted_eligible,
    }


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


def _disability_schedule_fields(schedule: Any, computed_deduction: Decimal, section: str) -> dict[str, Any]:
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
            f"Schedule {section} deduction must be Rs {expected_rupees} for the selected severity"
        )
    if amount <= 0 or amount > expected_rupees:
        raise ValueError(
            f"Schedule {section} computed deduction must be positive and not exceed Rs {expected_rupees}"
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
    # ITR-2/ITR-3-only fields (see this section's own module docstring).
    if schedule.form_10ia_filing_date:
        mapped["Form10IAFilingDate"] = _date(schedule.form_10ia_filing_date)
    if schedule.form_ack_num_11a:
        mapped["FormAckNum11A"] = schedule.form_ack_num_11a
    return mapped


def _schedule_80dd(schedule: Any, computed_deduction: Decimal) -> dict[str, Any]:
    """Build the official Section 80DD dependent-disability schedule."""
    if schedule is None:
        raise ValueError("A positive Section 80DD claim requires Schedule 80DD details")
    if schedule.dependent_relationship is None:
        raise ValueError("Schedule 80DD requires dependent_relationship")
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
    return {
        "Schedule80CDtls": rows,
        "TotalAmt": emitted,
    }


def _schedule_deduction_loan(
    details: Any,
    *,
    section: str,
    property_stamp_duty_value: Optional[Decimal] = None,
) -> dict[str, Any]:
    """Serialize a computed loan-deduction result (80E/80EE/80EEA/80EEB)
    without recalculating -- one shared builder for all four sections,
    which differ only in field-name suffix and 80EEB's extra
    ``VehicleRegNo``/80EEA's extra ``PropStmpDtyVal``, matching the
    official schema's own near-identical per-row shape across all four.
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


def _chapter6a_detail_schedules(result: ITR2Result, input_data: ITR2Input) -> dict[str, Optional[dict[str, Any]]]:
    """Build the eleven Chapter VI-A detail schedules from the already-
    computed per-section eligibility result -- see this section's own
    module docstring for the full rationale and ITR-1 precedent this
    mirrors. Every section follows the same "required detail if claimed,
    rejected detail if not claimed" discipline.
    """
    ded = result.schedules.get("deductions")
    section_details = getattr(ded, "section_details", {}) if ded else {}

    def claimed(section: str) -> Decimal:
        breakdown = getattr(ded, "breakdown", {}) if ded else {}
        if section == "80C":
            # "80C" is only present as its own key once
            # _cap_breakdown_to_gti() has run (the aggregate GTI cap
            # actually binds) -- in the common case (deductions
            # comfortably below GTI) the raw combined key
            # "80C+80CCC+80CCD(1)" is what's present instead, matching
            # _schedule_via()'s own identical decomposition.
            direct = breakdown.get("80C")
            if direct is not None:
                return direct
            combined = breakdown.get("80C+80CCC+80CCD(1)", _ZERO)
            return max(
                _ZERO,
                combined - breakdown.get("80CCC", _ZERO) - breakdown.get("80CCD(1)", _ZERO),
            )
        return breakdown.get(section, _ZERO)

    out: dict[str, Optional[dict[str, Any]]] = {}

    details_80d = section_details.get("80D")
    if claimed("80D") > 0:
        if details_80d is None:
            raise ValueError("Section 80D computation details are missing")
        schedule_80d = details_80d.source
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
        out["Schedule80D"] = _schedule_80d(
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
                schedule_80d.medical_expense_self_senior if schedule_80d else _ZERO
            ),
            medical_expense_parents_senior=(
                schedule_80d.medical_expense_parents_senior if schedule_80d else _ZERO
            ),
            policies=(schedule_80d.policies if schedule_80d else None),
        )

    details_80g = section_details.get("80G")
    if claimed("80G") > 0:
        if details_80g is None or not details_80g.categories:
            raise ValueError("Complete official Schedule 80G donation rows are required")
        out["Schedule80G"] = _schedule_80g(details_80g)
    elif input_data.deductions_chapter6a and input_data.deductions_chapter6a.donations_80g:
        raise ValueError("Schedule 80G rows require a positive eligible deduction")

    details_80gga = section_details.get("80GGA")
    if claimed("80GGA") > 0:
        if details_80gga is None or not details_80gga.rows:
            raise ValueError("Complete official Schedule 80GGA donation rows are required")
        out["Schedule80GGA"] = _schedule_80gga(details_80gga)
    elif input_data.schedule_80gga and input_data.schedule_80gga.donations:
        raise ValueError("Schedule 80GGA rows require a positive eligible deduction")

    details_80ggc = section_details.get("80GGC")
    if claimed("80GGC") > 0:
        if details_80ggc is None or not details_80ggc.rows:
            raise ValueError("Complete official Schedule 80GGC contribution rows are required")
        out["Schedule80GGC"] = _schedule_80ggc(details_80ggc)
    elif input_data.schedule_80ggc and input_data.schedule_80ggc.contributions:
        raise ValueError("Schedule 80GGC rows require a positive eligible deduction")

    if claimed("80DD") > 0:
        out["Schedule80DD"] = _schedule_80dd(input_data.schedule_80dd, claimed("80DD"))
    elif input_data.schedule_80dd is not None:
        raise ValueError("Schedule 80DD details require a positive 80DD deduction")

    if claimed("80U") > 0:
        out["Schedule80U"] = _schedule_80u(input_data.schedule_80u, claimed("80U"))
    elif input_data.schedule_80u is not None:
        raise ValueError("Schedule 80U details require a positive 80U deduction")

    details_80c = section_details.get("80C")
    if claimed("80C") > 0:
        if details_80c is None or not details_80c.rows:
            raise ValueError("A positive Section 80C claim requires Schedule 80C detail rows")
        out["Schedule80C"] = _schedule_80c(details_80c)
    elif input_data.schedule_80c_entries:
        raise ValueError("Schedule 80C rows require a positive eligible deduction")

    details_80e = section_details.get("80E")
    if claimed("80E") > 0:
        if details_80e is None or not details_80e.rows:
            raise ValueError("A positive Section 80E claim requires official loan rows")
        out["Schedule80E"] = _schedule_deduction_loan(details_80e, section="80E")
    elif input_data.schedule_80e_entries:
        raise ValueError("Schedule 80E rows require a positive eligible deduction")

    loan_rows_by_section = {
        "80EE": input_data.loan_details_80ee_list,
        "80EEA": input_data.loan_details_80eea_list,
        "80EEB": input_data.loan_details_80eeb_list,
    }
    for section, loan_rows in loan_rows_by_section.items():
        details_loan = section_details.get(section)
        eligible = claimed(section)
        if eligible > 0:
            if details_loan is None or not details_loan.rows:
                raise ValueError(f"A positive Section {section} claim requires official loan rows")
            out[f"Schedule{section}"] = _schedule_deduction_loan(
                details_loan,
                section=section,
                property_stamp_duty_value=(
                    input_data.property_stamp_duty_value_80eea if section == "80EEA" else None
                ),
            )
        elif loan_rows:
            raise ValueError(f"Schedule {section} rows require a positive eligible deduction")

    return out


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
        "115E": "5Ea",
        # The "any other income chargeable at special rate" dropdown family
        # (compute_other_special_rate_income()) already uses the exact
        # official SecCode string as its internal section value, so these
        # are identity mappings, not translations -- kept explicit here
        # (rather than relying on section_code_map.get(section, section))
        # so a genuinely-unmapped internal code still visibly falls through
        # to the "1" default instead of silently passing through Any string.
        "5A1ai": "5A1ai", "5A1aA": "5A1aA", "5A1aii": "5A1aii",
        "5A1aiia": "5A1aiia", "5A1aiiaa": "5A1aiiaa", "5A1aiiab": "5A1aiiab",
        "5A1aiiac": "5A1aiiac", "5A1aiii": "5A1aiii", "5A1bA": "5A1bA",
        "5AC1ab": "5AC1ab", "5AC1abD": "5AC1abD", "5ACA1a": "5ACA1a",
        "5AD1i": "5AD1i", "5AD1iP": "5AD1iP", "5AD1iDiv": "5AD1iDiv",
        "5A1aiiaaP": "5A1aiiaaP", "5A1aiiaa2P": "5A1aiiaa2P",
        # DTAA-rate Other Sources income (compute_dtaa_os()) -- same
        # identity-mapping rationale as the block above.
        "DTAAOS": "DTAAOS",
        # DTAA-rate STCG/LTCG (Schedule CG items A8b/B11b, Phase 6i-5) --
        # same identity-mapping rationale; distinct official SecCode values
        # from DTAAOS (confirmed via the schema's own SecCode enum text).
        "DTAASTCG": "DTAASTCG", "DTAALTCG": "DTAALTCG",
        # Section 115AD FII/FPI capital-gains codes (calculators/itr2.py
        # relabels the ordinary 111A/112/112A entries' `.section` to these
        # when the filing profile is flagged FII/FPI) -- same identity-
        # mapping rationale as the blocks above.
        "5AD1biip": "5AD1biip", "5ADii": "5ADii",
        "5ADiii": "5ADiii", "5ADiiiP": "5ADiiiP",
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
    if exempt:
        interest_inc = exempt.ppf_interest + exempt.sukanya_samriddhi_interest + exempt.tax_free_bond_interest + exempt.nre_interest
        others = exempt.share_of_profit_from_firm + exempt.other_exempt
    # Form item 4 ("Income claimed as not chargeable to tax as per DTAA")
    # is "III Total Income from DTAA claimed as not chargeable to tax" --
    # the SUM of the paired detail rows immediately above it
    # (IncNotChrgblAsPerDTAADtls), not a duplicate of item 1 (InterestInc).
    # CBDT rule #434 (Phase 4, 2026-09-12): the mapper now populates
    # ExemptIncome.dtaa_exempt_entries, so this self-corrects automatically
    # as the comment here originally anticipated.
    inc_not_chrgbl_as_per_dtaa_dtls: list[dict[str, Any]] = [
        {
            "AmountOfIncome": _to_rupees(row.amount),
            "NatureOfIncome": row.nature_of_income,
            "CountryName": row.country_name,
            "CountryCodeExcludingIndia": row.country_code,
            "ArticleOfDTAA": row.dtaa_article,
            "HeadOfIncome": row.head_of_income,
            "TRCFlag": row.tax_residency_certificate,
        }
        for row in (exempt.dtaa_exempt_entries if exempt else [])
    ]
    inc_not_chrgbl_to_tax = sum(
        (row.get("AmountOfIncome", _ZERO) for row in inc_not_chrgbl_as_per_dtaa_dtls), _ZERO
    )
    # Item 5 ("Pass through income claimed as not chargeable to tax").
    # CBDT rule #432 requires this to equal Schedule PTI's own exempt total
    # (IncClmdPTI.TotalSec23FBB summed across pti_entries) -- `PTIEntry.
    # exempt_income_23fbb` now carries that per-entity figure and
    # `ITR2-IN-EI-002` (input_rules.py) enforces the cross-schedule equality
    # pre-compute, so the two numbers can never diverge by the time this
    # builder runs.
    pass_thr_inc_not_chrgbl_tax = exempt.pti_exempt_income if exempt else _ZERO
    # Form item 6 "Total (1+2+3+4+5)".
    total_exempt = (
        interest_inc + result.net_agricultural_income + others
        + inc_not_chrgbl_to_tax + pass_thr_inc_not_chrgbl_tax
    )
    # Item 3's own OthersIncDtls detail rows -- CBDT rules #698-745
    # (Phase 4, 2026-09-12): one row per other_exempt_entries item, each
    # carrying its own official Category/SubCategory, so the per-clause
    # classification the frontend already captures is no longer collapsed
    # into a single undifferentiated total. Falls back to the old
    # single-row-with-no-Category/SubCategory shape only when
    # other_exempt_entries is empty (e.g. an ExemptIncome constructed
    # directly, bypassing the mapper) so `other_exempt`'s total is never
    # silently dropped from disclosure.
    if exempt and exempt.other_exempt_entries:
        others_inc_dtls = [
            {
                "Category": row.category,
                "SubCategory": row.sub_category,
                "Description": row.description,
                "OthAmount": _to_rupees(row.amount),
            }
            for row in exempt.other_exempt_entries
        ]
    elif exempt and exempt.other_exempt > 0:
        others_inc_dtls = [{
            "Description": (exempt.other_description if exempt else None) or "Other exempt income",
            "OthAmount": _to_rupees(exempt.other_exempt),
        }]
    else:
        others_inc_dtls = []
    # CBDT rule #445 (Phase 4, 2026-09-12): per-parcel agricultural land
    # detail, previously always [] regardless of AgriculturalIncome.
    # land_details -- the mapper now populates that field from the
    # frontend's already-collected agriculturalLandParcels.
    exc_net_agri_inc_dtls = [
        {
            "NameOfDistrict": land.name_of_district,
            "PinCode": int(land.pin_code),
            "MeasurementOfLand": float(land.measurement_of_land),
            "AgriLandOwnedFlag": land.owned_flag,
            "AgriLandIrrigatedFlag": land.irrigated_flag,
        }
        for land in (agri.land_details if agri else [])
    ]
    return {
        "InterestInc": _to_rupees(interest_inc),
        "GrossAgriRecpt": _to_rupees(agri.gross_agricultural_income if agri else _ZERO),
        "ExpIncAgri": _to_rupees(agri.agricultural_deductions if agri else _ZERO),
        "UnabAgriLossPrev8": _to_rupees(agri.unabsorbed_agricultural_loss_previous_8_years if agri else _ZERO),
        "NetAgriIncOrOthrIncRule7": _to_rupees(result.net_agricultural_income),
        "ExcNetAgriInc": {"ExcNetAgriIncDtls": exc_net_agri_inc_dtls},
        "OthersInc": {"OthersIncDtls": others_inc_dtls},
        "Others": _to_rupees(others),
        "IncNotChrgblAsPerDTAA": {"IncNotChrgblAsPerDTAADtls": inc_not_chrgbl_as_per_dtaa_dtls},
        "IncNotChrgblToTax": _to_rupees(inc_not_chrgbl_to_tax),
        "PassThrIncNotChrgblTax": _to_rupees(pass_thr_inc_not_chrgbl_tax),
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
        # IncFromSal/IncFromHP/IncCapGain/IncOthSrc/TotalCountryWise are all
        # NESTED objects in the official schema (ScheduleFSIIncType /
        # TotalScheduleFSIIncType: IncFrmOutsideInd/TaxPaidOutsideInd/
        # TaxPayableinInd/TaxReliefinInd each), not plain integers -- the
        # previous code emitted plain integers for all five and three
        # fabricated top-level fields (TaxPaidOutsideIndia/TaxPayableInIndia/
        # TaxReliefAvailable) that do not exist in the real schema at all,
        # meaning every Schedule FSI disclosure this builder ever produced
        # was schema-invalid, not just under-detailed.
        #
        # FSICountryEntry only carries one tax-paid/payable figure per
        # jurisdiction (not per income head), so the per-head breakdown is
        # only attributable when exactly one head has nonzero income for
        # this country -- matching the same single-attributable-source
        # precedent as Schedule S's per-employer perquisites.
        heads = {
            "IncFromSal": item.salary_income,
            "IncFromHP": item.hp_income,
            "IncCapGain": item.cg_income,
            "IncOthSrc": item.os_income,
        }
        nonzero_heads = [k for k, v in heads.items() if v != _ZERO]
        single_head = nonzero_heads[0] if len(nonzero_heads) == 1 else None

        def head_block(key: str, income: Decimal) -> dict[str, int]:
            if key == single_head:
                tax_paid, tax_payable = item.tax_paid_outside_india, item.tax_payable_in_india
            else:
                tax_paid = tax_payable = _ZERO
            return {
                "IncFrmOutsideInd": _to_rupees(income),
                "TaxPaidOutsideInd": _to_rupees(tax_paid),
                "TaxPayableinInd": _to_rupees(tax_payable),
                "TaxReliefinInd": _to_rupees(min(tax_paid, tax_payable)),
            }

        rows.append({
            "CountryName": _country_name(item.country_code),
            "CountryCodeExcludingIndia": item.country_code,
            "TaxIdentificationNo": item.tax_identification_no,
            "IncFromSal": head_block("IncFromSal", item.salary_income),
            "IncFromHP": head_block("IncFromHP", item.hp_income),
            "IncCapGain": head_block("IncCapGain", item.cg_income),
            "IncOthSrc": head_block("IncOthSrc", item.os_income),
            "TotalCountryWise": {
                "IncFrmOutsideInd": _to_rupees(item.total_income or _ZERO),
                "TaxPaidOutsideInd": _to_rupees(item.tax_paid_outside_india),
                "TaxPayableinInd": _to_rupees(item.tax_payable_in_india),
                "TaxReliefinInd": _to_rupees(min(item.tax_paid_outside_india, item.tax_payable_in_india)),
            },
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
    # dtaa/non_dtaa were previously computed by re-searching every entry
    # sharing a row's own country_code for ANY DTAA-type (90/90A) or
    # non-DTAA (91) relief_section -- a per-COUNTRY test, not a per-ROW
    # one. Two rows for the same country under different relief sections
    # (a taxpayer with two income sources in one country under different
    # TINs, one DTAA-relieved and one unilaterally-relieved) would each
    # match BOTH tests, so both rows' relief got summed into BOTH dtaa and
    # non_dtaa -- overstating TotalTaxReliefOutsideIndia. Each row already
    # carries its own relief_section directly; read that instead.
    dtaa = 0
    non_dtaa = 0
    for item in input_data.tr1_entries:
        relief = _to_rupees(item.relief_claimed)
        rows.append({
            "CountryName": _country_name(item.country_code),
            "CountryCodeExcludingIndia": item.country_code,
            "TaxIdentificationNo": item.tax_identification_no,
            "TaxPaidOutsideIndia": _to_rupees(item.tax_paid_outside_india),
            "TaxReliefOutsideIndia": relief,
            "ReliefClaimedUsSection": item.relief_section,
        })
        if item.relief_section in ("90", "90A"):
            dtaa += relief
        else:
            non_dtaa += relief
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

# Maps ForeignAssetEntry.income_head to the official IncTaxSch enum, which
# names which OTHER schedule of this same return the asset's income is
# already included under -- "NI" (no income) when the asset produced none.
_FA_INC_TAX_SCH: dict[Optional[str], str] = {
    "SAL": "SA", "HP": "HP", "CG": "CG", "OS": "OS", "EI": "EI", None: "NI",
}

# Official Ownership/OwnerStatus enums differ by category: bank accounts use
# "OWNER", every other category here uses "DIRECT" for the equivalent
# direct-ownership value; both share BENEFICIAL_OWNER/BENIFICIARY (the
# schema's own spelling, not a transcription error here).
_FA_BANK_OWNER_STATUS = {"OWNER", "BENEFICIAL_OWNER", "BENIFICIARY"}
_FA_OTHER_OWNERSHIP = {"DIRECT", "BENEFICIAL_OWNER", "BENIFICIARY"}


def _fa_inc_tax_sch(item: ForeignAssetEntry) -> str:
    return _FA_INC_TAX_SCH[item.income_head]


def _fa_inc_tax_sch_no(item: ForeignAssetEntry, label: str) -> str:
    if not item.income_tax_schedule_item_no:
        raise ValueError(
            f"Schedule FA {label} entry requires income_tax_schedule_item_no "
            "(the item/row reference within the schedule its income is included under)."
        )
    return item.income_tax_schedule_item_no


def _schedule_fa(input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize foreign-asset disclosures by category.

    CBDT rule #746 ("Schedule FA has to be filled if Sl.19 of Part B-TTI
    [``AssetOutIndiaFlag``] is 'Yes'") is structurally guaranteed: both this
    schedule's presence and ``AssetOutIndiaFlag`` (set below, near
    ``"AssetOutIndiaFlag": "YES" if input_data.foreign_assets else "NO"``)
    derive from the exact same ``input_data.foreign_assets`` list, so they
    can never disagree.
    """
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
            if item.ownership_status not in _FA_BANK_OWNER_STATUS:
                raise ValueError(
                    f"Schedule FA bank account OwnerStatus must be one of "
                    f"{sorted(_FA_BANK_OWNER_STATUS)}, got {item.ownership_status!r}"
                )
            result["DetailsForiegnBank"].append({
                "CountryName": _country_name(item.country_code),
                "CountryCodeExcludingIndia": item.country_code,
                "Bankname": item.institution_or_entity_name,
                "AddressOfBank": item.address,
                "ZipCode": item.zip_code,
                "ForeignAccountNumber": item.account_or_asset_identifier[:34],
                "OwnerStatus": item.ownership_status,
                "AccOpenDate": _date(item.opening_or_acquisition_date),
                "PeakBalanceDuringYear": _to_rupees(item.peak_value),
                "ClosingBalance": _to_rupees(item.closing_value),
                "IntrstAccured": _to_rupees(item.gross_income),
            })
        elif item.asset_type == ForeignAssetType.IMMOVABLE_PROPERTY:
            if item.ownership_status not in _FA_OTHER_OWNERSHIP:
                raise ValueError(
                    f"Schedule FA immovable property Ownership must be one of "
                    f"{sorted(_FA_OTHER_OWNERSHIP)}, got {item.ownership_status!r}"
                )
            if not item.nature_of_income:
                raise ValueError("Schedule FA immovable property entry requires nature_of_income")
            result["DetailsImmovableProperty"].append({
                "CountryName": _country_name(item.country_code),
                "CountryCodeExcludingIndia": item.country_code,
                "ZipCode": item.zip_code,
                "AddressOfProperty": item.address,
                "Ownership": item.ownership_status,
                "DateOfAcq": _date(item.opening_or_acquisition_date),
                "TotalInvestment": _to_rupees(item.peak_value),
                "IncDrvProperty": _to_rupees(item.gross_income),
                "NatureOfInc": item.nature_of_income,
                "IncTaxAmt": _to_rupees(item.income_offered),
                "IncTaxSch": _fa_inc_tax_sch(item),
                "IncTaxSchNo": _fa_inc_tax_sch_no(item, "immovable property"),
            })
        elif item.asset_type == ForeignAssetType.OTHER_ASSET:
            if item.ownership_status not in _FA_OTHER_OWNERSHIP:
                raise ValueError(
                    f"Schedule FA other-asset Ownership must be one of "
                    f"{sorted(_FA_OTHER_OWNERSHIP)}, got {item.ownership_status!r}"
                )
            if not item.nature_of_asset:
                raise ValueError("Schedule FA other-asset entry requires nature_of_asset")
            if not item.nature_of_income:
                raise ValueError("Schedule FA other-asset entry requires nature_of_income")
            result["DetailsOthAssets"].append({
                "CountryName": _country_name(item.country_code),
                "CountryCodeExcludingIndia": item.country_code,
                "ZipCode": item.zip_code,
                "NatureOfAsset": item.nature_of_asset,
                "Ownership": item.ownership_status,
                "DateOfAcq": _date(item.opening_or_acquisition_date),
                "TotalInvestment": _to_rupees(item.peak_value),
                "IncDrvAsset": _to_rupees(item.gross_income),
                "NatureOfInc": item.nature_of_income,
                "IncTaxAmt": _to_rupees(item.income_offered),
                "IncTaxSch": _fa_inc_tax_sch(item),
                "IncTaxSchNo": _fa_inc_tax_sch_no(item, "other-asset"),
            })
        else:
            # Custodial account, equity/debt interest, cash-value insurance,
            # financial interest in an entity, signing authority, trust, and
            # other foreign-sourced income each require official fields
            # ForeignAssetEntry does not capture (e.g. equity/debt's
            # InitialValOfInvstmnt/TotGrossProceeds, trust's settlor/trustee/
            # beneficiary names) -- silently folding these into
            # DetailsOthAssets, as the previous code did, would misclassify
            # them into the wrong official category entirely, not just omit
            # detail. Fail closed until each category gets its own typed
            # model and serializer path.
            raise ValueError(
                f"Schedule FA category {item.asset_type.value!r} is not yet "
                "supported by the ITR-2 JSON builder -- it requires a "
                "dedicated typed model, not the generic ForeignAssetEntry."
            )
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
    """Serialize Schedule AMT from computed AMT result.

    Emitted whenever the section 115JC comparison was genuinely made this
    year (``chapter_xii_ba_applicable``), not only when AMT actually binds
    (``amt_applicable``) -- confirmed against the official form directly
    (Schedule AMT itself has no "if applicable" gate on its own four items;
    the form only starts conditioning behaviour once Schedule AMTC computes
    Sl.3 from Sl.1/Sl.2, which needs Sl.1 -- Schedule AMT's own Sl.4 -- to be
    real every such year, not just years AMT wins).
    """
    amt = result.schedules.get("amt")
    if amt is None or not getattr(amt, "chapter_xii_ba_applicable", False):
        return None
    # `AMTResult` (app/engine/schedules/amt.py) has no `total_deductions`
    # field at all -- reading it via getattr(..., default=0) always fell
    # through to zero, wrong on every return this schedule is even built
    # for. The real figure is exactly recoverable without touching amt.py:
    # adjusted_total_income = taxable_income + addition_total (see
    # compute()'s own `adjusted_income = income + addition_total`, where
    # `income` is exactly `result.taxable_income` at the calculator's own
    # call site) -- both terms are already-rounded/unrounded Decimals with
    # no intermediate rounding on either side, so the subtraction is exact.
    adjusted_total_income = getattr(amt, "adjusted_total_income", _ZERO)
    deduction_claim = adjusted_total_income - result.taxable_income
    return {
        "TotalIncItemPartBTI": _to_rupees(result.taxable_income),
        "DeductionClaimUndrAnySec": _to_rupees(deduction_claim),
        "AdjustedUnderSec115JC": _to_rupees(adjusted_total_income),
        # Sl.4 "Tax payable under section 115JC [18.5% of (3)]" -- confirmed
        # against the official form directly: Schedule AMT itself has no
        # surcharge/cess line items at all (those are added separately as
        # Part B-TTI's own items 1b/1c, applied to 1a = this same Sl.4
        # figure) -- previously read amt.amt_tax (surcharge+cess inclusive),
        # which is the item-1d total, not Sl.4/item-1a's own raw figure.
        "TaxPayableUnderSec115JC": _to_rupees(getattr(amt, "amt_tax_before_surcharge_and_cess", _ZERO)),
    }


# The schema's AssYr enum on ScheduleAMTCDtls covers only prior years
# (2013-14 through 2025-26) -- the current AY's own newly-generated credit
# is disclosed via the top-level CurrYrAmtCreditFwd field instead, never as
# a ScheduleAMTCDtls row (that array is schema-capped at 13 items, exactly
# matching AY2013-14 through AY2025-26, with no 14th slot for it).
# AMTCreditItem.assessment_year is Pydantic-typed as any "YYYY-YY"-shaped
# string (broader than this closed set), so an out-of-range year is only
# caught here, at serialization time.
_AMTC_VALID_PRIOR_YEARS = frozenset({
    "2013-14", "2014-15", "2015-16", "2016-17", "2017-18", "2018-19",
    "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26",
})


def _schedule_amtc(result: ITR2Result, input_data: ITR2Input) -> Optional[dict[str, Any]]:
    """Serialize Schedule AMTC from the calculator's own AMTC computation.

    Confirmed against the official form directly (Reference Docs by CBDT &
    ITD/Official ITR FORMS/ITR-2-2026-Eng.pdf, Schedule AMTC page): Sl.1 =
    this year's 115JC tax (Part B-TTI item 1d), Sl.2 = this year's
    normal-provisions tax (Part B-TTI item 7), Sl.3 = (Sl.2-Sl.1) if
    Sl.2>Sl.1 else 0 -- the utilization CAP, computed every year the 115JC
    comparison is made, not gated on AMT winning. The brought-forward-credit
    table (rows i-xiii) plus a distinct "Current AY" row (xiv, holding this
    year's own newly-generated credit, not a brought-forward balance) are
    disclosed by the calculator's own single FIFO computation
    (``result.schedules["amtc"]``, ``app/engine/schedules/amt.py::
    compute_amtc()``) -- the same total this schedule discloses is the exact
    total already subtracted from the actual tax payable
    (``result.amt_credit_utilised``), not a second, independently-derived
    figure that could silently disagree with it.
    """
    amt = result.schedules.get("amt")
    if amt is None or not getattr(amt, "chapter_xii_ba_applicable", False):
        return None

    amtc = result.schedules.get("amtc")
    rows: list[dict[str, Any]] = []
    total_gross = _ZERO
    total_bal_bf = _ZERO
    if amtc is not None:
        for entry in amtc.entries:
            if entry.assessment_year not in _AMTC_VALID_PRIOR_YEARS:
                raise ValueError(
                    f"Schedule AMTC assessment_year {entry.assessment_year!r} is not one of "
                    f"the official schema's valid prior years {sorted(_AMTC_VALID_PRIOR_YEARS)}."
                )
            # AMTCreditItem captures only the resulting balance brought
            # forward into this year, not a separate original-year "Gross"
            # figure or how much was already set off in still-earlier years
            # -- that finer breakdown isn't tracked anywhere in this
            # codebase today. Treating the known balance as both Gross and
            # AmtCreditBalBroughtFwd (with AmtCreditSetOfEy at 0) is an
            # honest degenerate mapping: the schema's own implied identity
            # (Gross - AmtCreditSetOfEy == AmtCreditBalBroughtFwd) holds
            # exactly, it just can't disclose an already-partially-utilized
            # year's original size separately from its current balance. An
            # expired (>15-assessment-year-old) entry discloses its full
            # original balance as still "brought forward" with zero
            # utilized/carried-forward -- the official schema has no
            # dedicated "expired" flag, so this is the closest honest
            # representation: the credit no longer legally exists, not that
            # it was somehow all utilized or is still available.
            bal_brought_forward = entry.brought_forward
            rows.append({
                "AssYr": entry.assessment_year,
                "Gross": _to_rupees(bal_brought_forward),
                "AmtCreditSetOfEy": 0,
                "AmtCreditBalBroughtFwd": _to_rupees(bal_brought_forward),
                "AmtCreditUtilized": _to_rupees(entry.utilised),
                "BalAmtCreditCarryFwd": _to_rupees(entry.remaining_carry_forward),
            })
            total_gross += bal_brought_forward
            total_bal_bf += bal_brought_forward

    total_utilised = result.amt_credit_utilised
    # Sl.6, "Amount of AMT liability available for credit in subsequent
    # assessment years [total of 4(D)]" -- sum of EVERY row's own carry-
    # forward column, i-xiii (old, unutilized) PLUS row xiv (this year's own
    # newly-generated credit, amt.amt_credit) -- confirmed distinct from
    # CurrYrAmtCreditFwd (row xiv's own value alone) by the two fields' near-
    # identical names and the form's own row-xiv-vs-Sl.6 distinction.
    old_credit_carry_forward = total_bal_bf - total_utilised
    current_year_new_credit = getattr(amt, "amt_credit", _ZERO)
    grand_total_carry_forward = old_credit_carry_forward + current_year_new_credit
    tax_115jc = result.amt_tax
    tax_other_provisions = result.gross_tax_liability
    credit_available_this_year = max(_ZERO, tax_other_provisions - tax_115jc)
    document: dict[str, Any] = {
        "CurrAssYr": "2026-27",
        "TaxSection115JC": _to_rupees(tax_115jc),
        "TaxOthProvisions": _to_rupees(tax_other_provisions),
        "AmtTaxCreditAvailable": _to_rupees(credit_available_this_year),
        "TaxSection115JD": _to_rupees(tax_115jc),
        "AmtLiabilityAvailable": _to_rupees(credit_available_this_year),
        "TotAmtCreditUtilisedCY": _to_rupees(total_utilised),
        "CurrYrCreditCarryFwd": _to_rupees(grand_total_carry_forward),
        "CurrYrAmtCreditFwd": _to_rupees(current_year_new_credit),
        "TotAMTGross": _to_rupees(total_gross),
        # "Total of AMT credit set-off in earlier years" -- a real monetary
        # total, correctly 0 given AmtCreditSetOfEy is 0 on every row per
        # the data-model limitation noted above; will self-correct once/if
        # a genuine per-year set-off figure is ever captured.
        "TotSetOffEys": sum(row["AmtCreditSetOfEy"] for row in rows),
        "TotBalBF": _to_rupees(total_bal_bf),
        "TotBalAMTCreditCF": _to_rupees(old_credit_carry_forward),
    }
    # ScheduleAMTCDtls is optional on the official schema, but minItems: 1
    # when present -- omit it entirely rather than emit an empty array when
    # there's no brought-forward credit at all (chapter in play, first year
    # of AMT liability with nothing carried in yet).
    if rows:
        document["ScheduleAMTCDtls"] = rows
    return document


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
    """Serialize actual pass-through income rows.

    CBDT rules #654-657/#441/#658 (Col.9=Col.7-Col.8; ShortTermCG=
    STCG_Sec111A+STCG_Others; LongTermCG=LTCG_Sec112A+LTCG_Others; IncOthSrc=
    OS_Dividend+OS_Others; IncClmdPTI total=Sec23FBB+SecB+SecC) are all
    structurally guaranteed here, not merely asserted: every "regular()" row
    sets NetIncomeLoss=amount and AmountOfInc-CurrYrLossShareByInvstFund=
    max(0,amount)-max(0,-amount)=amount identically, so Col.9=Col.7-Col.8
    always; each CG/OS split (stcg_111a/stcg_other, ltcg_112a/ltcg_other,
    OS_Dividend=0/OS_Others=os) is built as two mutually exclusive branches of
    the same source amount, so the two halves always sum back to the whole;
    IncClmdPTI's SecB/SecC are omitted (optional in the official schema) and
    TotalSec23FBB==Sec23FBB by construction below, so the a+b+c identity
    holds too. No separate cross-check code is needed for these six rules.
    """
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
        # Route to the same 111A/112A-vs-"Others" sub-bucket the calculator
        # itself taxes this entry under (calculators/itr2.py's own PTI
        # dispatch loop: `pti.section == "111A"` for STCG,
        # `"112A" in pti.section.upper()` for LTCG) -- previously always
        # zeroed Sec111A/Sec112A and routed the full amount into "Others"
        # regardless of `item.section`, misrepresenting a 111A/112A PTI
        # entry as "Others" and disagreeing with Schedule SI's own line
        # items for the identical income.
        stcg_111a = stcg if item.section == "111A" else _ZERO
        stcg_other = stcg if item.section != "111A" else _ZERO
        ltcg_112a = ltcg if "112A" in item.section.upper() else _ZERO
        ltcg_other = ltcg if "112A" not in item.section.upper() else _ZERO
        rows.append({
            "InvstmntCvrdUs115UA115UB": "A" if item.section == "115UA" else "B" if item.section == "115UB" else "C",
            "BusinessName": item.entity_name,
            "BusinessPAN": item.entity_pan,
            "IncFromHP": regular(hp, item.tds_credit if hp else _ZERO),
            "CapitalGainsPTI": {
                "ShortTermCG": regular(stcg),
                "STCG_Sec111A": regular(stcg_111a, item.tds_credit if stcg_111a else _ZERO),
                "STCG_Others": regular(stcg_other, item.tds_credit if stcg_other else _ZERO),
                "LongTermCG": regular(ltcg),
                "LTCG_Sec112A": regular(ltcg_112a, item.tds_credit if ltcg_112a else _ZERO),
                "LTCG_Others": regular(ltcg_other, item.tds_credit if ltcg_other else _ZERO),
            },
            "IncClmdPTI": {
                "TotalSec23FBB": other(item.exempt_income_23fbb),
                "Sec23FBB": other(item.exempt_income_23fbb),
            },
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

    # Each AY block's schema fields (TaxDeferredBFEarlierAY, TaxPayableCurrentAY,
    # BalanceTaxCF) are single scalars, not an array -- multiple entries
    # sharing the same assessment_year (e.g. more than one qualifying grant
    # vesting the same year) must be SUMMED into one block. The previous
    # `{e.assessment_year: e for e in ...}` dict comprehension instead kept
    # only the last entry for a given year, silently discarding every
    # earlier same-year entry's deferred/payable/carried-forward amounts.
    # SecurityType/CeasedEmployee are categorical, not additive -- the first
    # entry for a given AY is the representative row (real-world usage is
    # almost always one entry per AY).
    aggregated_by_ay: dict[str, dict[str, Any]] = {}
    for e in input_data.esop_deferrals:
        bucket = aggregated_by_ay.setdefault(
            e.assessment_year,
            {"bf": _ZERO, "payable": _ZERO, "cf": _ZERO,
             "security_type": e.security_type, "ceased_employee": e.ceased_employee},
        )
        bucket["bf"] += e.tax_deferred_brought_forward
        bucket["payable"] += e.tax_payable_current_year
        bucket["cf"] += e.balance_tax_carried_forward

    def ay_block(ay_label: str, tax_key: str) -> dict[str, Any]:
        bucket = aggregated_by_ay.get(ay_label)
        if bucket is None:
            esop_event = {"SecurityType": "NS", "ScheduleESOPEventDtlsType": [], "CeasedEmployee": "N"}
            return {"AssessmentYear": ay_label, "TaxDeferredBFEarlierAY": 0, "ScheduleESOPEventDtls": esop_event, tax_key: 0, "TaxPayableCurrentAY": 0, "BalanceTaxCF": 0}
        esop_event = {
            "SecurityType": bucket["security_type"],
            "ScheduleESOPEventDtlsType": [],
            "CeasedEmployee": "Y" if bucket["ceased_employee"] else "N",
        }
        return {
            "AssessmentYear": ay_label,
            "TaxDeferredBFEarlierAY": _to_rupees(bucket["bf"]),
            "ScheduleESOPEventDtls": esop_event,
            tax_key: _to_rupees(bucket["payable"]),
            "TaxPayableCurrentAY": _to_rupees(bucket["payable"]),
            "BalanceTaxCF": _to_rupees(bucket["cf"]),
        }

    total_attributed = sum((e.tax_payable_current_year for e in input_data.esop_deferrals), _ZERO)
    # The running balance carried into the current AY is the sum of every
    # outstanding entry's carry-forward, not just the first entry's --
    # using `first.balance_tax_carried_forward` alone silently dropped every
    # other entry's remaining deferred-tax balance.
    total_balance_cf = sum((e.balance_tax_carried_forward for e in input_data.esop_deferrals), _ZERO)
    return {
        "DPIITRegNo": first.dpiit_registration_number,
        "PanofStartUp": first.employer_pan,
        "ScheduleESOP2122_Type": ay_block("2021-22", "TotalTaxAttributedAmt21"),
        "ScheduleESOP2223_Type": ay_block("2022-23", "TotalTaxAttributedAmt22"),
        "ScheduleESOP2324_Type": ay_block("2023-24", "TotalTaxAttributedAmt23"),
        "ScheduleESOP2425_Type": ay_block("2024-25", "TotalTaxAttributedAmt24"),
        "ScheduleESOP2526_Type": ay_block("2025-26", "TotalTaxAttributedAmt25"),
        "ScheduleESOP2627_Type": {"AssessmentYear": "2026-27", "BalanceTaxCF": _to_rupees(total_balance_cf)},
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
    for index, item in enumerate(input_data.tax_payment_entries, start=1):
        missing = [
            field for field, value in (
                ("BSR code", item.bsr_code),
                ("payment date", item.payment_date),
                ("challan serial number", item.challan_serial_number),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                f"Tax payment entry #{index} is missing: {', '.join(missing)}."
            )
        rows.append({
            "BSRCode": item.bsr_code,
            "DateDep": _date(item.payment_date),
            "SrlNoOfChaln": int(item.challan_serial_number),
            "Amt": _to_rupees(item.amount),
        })
    return {"TaxPayment": rows, "TotalTaxPayments": sum(r["Amt"] for r in rows)}


# Income-tax Act section label (e.g. "194A", as captured by TDS2Entry/TDS3Entry
# .tds_section) -> the official schema's TDSSection enum code (e.g. "94A").
# Ported from frontend/src/domain/returns/tdsSections.ts's TDS_SECTION_TO_SCHEMA
# -- keep the two in sync; that file is the original source of truth (built
# against the schema's own enum + description text, Reference Docs by CBDT &
# ITD/Official JSON Schema/ITR-2_2026_Main_V1.1 (2).json). Audit finding §22.4:
# the builder previously emitted entry.tds_section verbatim, which is never a
# schema-valid code for any "194"/"196"-prefixed section (the schema's own
# enum never contains a "1"-prefixed 3-digit code) -- this broke Schedule TDS2
# for essentially every real ITR-2 return with common bank/company-deducted
# TDS (194A interest alone is close to universal for any taxpayer with a bank
# account).
_TDS_SECTION_TO_SCHEMA: dict[str, str] = {
    "92A": "92A", "92B": "92B", "92C": "92C",
    "192": "92B",  # salary -- non-govt default; TDS1 rows never reach this table
    "192A": "192A",
    "193": "193",
    "194": "194",
    "194A": "94A",
    "194B": "94B", "194BA": "94BA",
    "194BB": "4BB",
    "194C": "94C",
    "194D": "94D",
    "194DA": "4DA",
    "194E": "94E",
    "194EE": "4EE",
    "194F": "4F",
    "194G": "4G",
    "194H": "4H",
    "194I(a)": "4-IA", "194I(b)": "4-IB",
    "194IA": "4IA",
    "194IB": "4IB",
    "194IC": "4IC",
    "194J(a)": "94J-A", "194J(b)": "94J-B",
    "194K": "94K",
    "194LA": "4LA",
    "194LB": "4LB",
    "194LC": "4LC1",
    "194LBA": "4BA1",
    "194LBB": "LBB",
    "194LBC": "LBC",
    "194LD": "4LD",
    "194M": "94M",
    "194N": "94N",
    "194O": "94O",
    "194P": "94P",
    "194Q": "94Q",
    "195": "195",
    "196A": "96A", "196B": "96B", "196C": "96C", "196D": "96D", "196DA": "96DA",
}


def _official_tds_section(section: str) -> str:
    """Translate a user-facing TDS section label to the schema's TDSSection code.

    Falls back to the stripped raw value when it isn't in the table -- a code
    already in schema form (e.g. imported from a filed return) passes through
    unchanged rather than being mangled.
    """
    key = (section or "").strip()
    return _TDS_SECTION_TO_SCHEMA.get(key, key)


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
        row: dict[str, Any] = {
            "TDSCreditName": entry.ownership,
            "TANOfDeductor": entry.deductor_tan,
            "TDSSection": _official_tds_section(entry.tds_section),
            "BroughtFwdTDSAmt": _to_rupees(entry.brought_forward_tds),
            "TaxDeductCreditDtls": {
                "TaxDeductedOwnHands": _to_rupees(entry.tds_deducted),
                "TaxClaimedOwnHands": _to_rupees(entry.tds_claimed_this_year),
            },
            "GrossAmount": _to_rupees(entry.gross_amount),
            "HeadOfIncome": entry.head_of_income or "OS",
            "AmtCarriedFwd": _to_rupees(entry.tds_credit_carried_forward),
        }
        # DeductedYr is not required by the schema (only TDSCreditName/
        # TANOfDeductor/TDSSection/TaxDeductCreditDtls/AmtCarriedFwd are) and
        # its own enum caps at 2024 with no current-AY value ever included --
        # it exists to disclose TDS genuinely brought forward from an earlier
        # year, not the current year's own credit. entry.deducted_year is the
        # dedicated field the frontend's "Deducted Year (FY tax deducted)"
        # control writes for exactly that case; only emit the key when it's
        # actually set, instead of always deriving a (schema-invalid, for the
        # current AY) year from entry.financial_year.
        if entry.deducted_year:
            row["DeductedYr"] = int(entry.deducted_year)
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
            **({"AadhaarOfBuyerTenant": entry.tenant_aadhaar} if entry.tenant_aadhaar else {}),
            "TDSSection": _official_tds_section(entry.tds_section or "195"),
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
        # DeductedYr is not required by TDS3's schema either, and shares the
        # same enum (max 2024, no current-AY value) as TDS2's -- unlike
        # TDS2Entry, TDS3Entry.deducted_yr is non-Optional (defaults to the
        # current AY's own "2025", per its own Field default), so the signal
        # here is the *value* itself, not presence: only emit the key when
        # it's a real, schema-valid earlier year.
        if deducted_year <= 2024:
            row["DeductedYr"] = deducted_year
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

def _partb_ti(result: ITR2Result, input_data: ITR2Input) -> dict[str, Any]:
    """Serialize Part B-TI from computed income heads."""
    post_loss = result.schedules.get("post_loss_cg", {})
    # ``post_loss_cg_baskets()``'s own dict keys are the SI engine's naming,
    # not the schema's: "normal_stcg" is the 30%-normal-rate bucket (taxed at
    # slab/applicable rate for an ordinary taxpayer, 30% flat under
    # 115AD(1)(ii) for an FII/FPI) and "111a" is the true 20%-flat 111A
    # bucket -- routing below mirrors how ``_schedule_cg()``/``_schedule_115ad()``
    # already branch on ``is_fii_fpi`` for the equivalent Schedule CG fields.
    is_fii_fpi = bool(input_data.filing_profile and input_data.filing_profile.is_fii_fpi)
    stcg_111a = _to_rupees(post_loss.get("111a", _ZERO))
    stcg_normal = _to_rupees(post_loss.get("normal_stcg", _ZERO))
    stcg_20 = stcg_111a
    stcg_30 = stcg_normal if is_fii_fpi else 0
    stcg_app_rate = 0 if is_fii_fpi else stcg_normal
    ltcg_112 = _to_rupees(post_loss.get("112", _ZERO))
    ltcg_112a_gross = _to_rupees(post_loss.get("112a_gross", _ZERO))
    # Schedule CG items A8b/B11b (Phase 6i-5) -- DTAA-special-rate STCG/LTCG,
    # each its own post-loss basket (see _post_loss_cg_baskets), previously
    # hardcoded to 0 regardless of real data, silently understating
    # TotalShortTerm/TotalLongTerm/TotalCapGains whenever a real DTAA claim
    # existed even though the income was already taxed via Schedule SI.
    stcg_dtaa = _to_rupees(post_loss.get("stcg_dtaa", _ZERO))
    ltcg_dtaa = _to_rupees(post_loss.get("ltcg_dtaa", _ZERO))
    total_stcg = stcg_111a + stcg_normal + stcg_dtaa
    total_ltcg = ltcg_112 + ltcg_112a_gross + ltcg_dtaa
    total_cg = total_stcg + total_ltcg + _to_rupees(result.vda_income)
    # Form items 4a/4b/4c (schema IncFromOS.OtherSrcThanOwnRaceHorse/
    # IncChargblSplRate/FromOwnRaceHorse) are, per the official form, "6 of
    # Schedule OS" / "2 of Schedule OS" / "8e of Schedule OS" -- sourced from
    # _schedule_os()'s own already-computed totals so this split can never
    # drift from what Schedule OS itself discloses (CBDT rules 500-502
    # require exactly this consistency). Was previously 0/0 with the entire
    # blended total dumped into 4a alone.
    os_schedule = _schedule_os(result, input_data)
    os_special_rate = os_schedule["IncOthThanOwnRaceHorse"]["IncChargeableSpecialRates"] if os_schedule else 0
    os_excl_race_horse_total = os_schedule["TotOthSrcNoRaceHorse"] if os_schedule else 0
    os_race_horse_income = max(0, os_schedule["IncFromOwnHorse"]["BalanceOwnRaceHorse"]) if os_schedule else 0
    os_normal_rate = max(0, os_excl_race_horse_total - os_special_rate)
    # Form items 10/13 (schema IncChargeTaxSplRate111A112/
    # IncChargeableTaxSplRates) are both explicitly "total of column (i) of
    # schedule SI" per the form text and CBDT rule 374/376 -- the full
    # Schedule SI total (all special-rate income: 111A/112/112A, VDA,
    # lottery/gaming/unexplained-income/patent-royalty/carbon-credits/
    # sportsman, NRI/FII special-rate OS, DTAA-OS, PTI), not just the
    # CG-only 111A+112+112A(+VDA) subset previously summed here directly
    # from post_loss_cg.
    si_result = result.schedules.get("si")
    total_special_rate_income = _to_rupees(getattr(si_result, "total_special_rate_income", _ZERO))
    amt_for_ti = result.schedules.get("amt")
    deemed_income_115jc = (
        getattr(amt_for_ti, "adjusted_total_income", _ZERO)
        if getattr(amt_for_ti, "chapter_xii_ba_applicable", False) else _ZERO
    )
    return {
        "Salaries": _to_rupees(result.salary_income),
        "IncomeFromHP": _to_rupees(max(_ZERO, result.house_property_income)),
        "CapGain": {
            "ShortTerm": {
                "ShortTerm20Per": stcg_20,
                "ShortTerm30Per": stcg_30,
                "ShortTermAppRate": stcg_app_rate,
                "ShortTermSplRateDTAA": stcg_dtaa,
                "TotalShortTerm": total_stcg,
            },
            "LongTerm": {
                "LongTerm12_5Per": ltcg_112,
                "LongTermSplRateDTAA": ltcg_dtaa,
                "TotalLongTerm": total_ltcg,
            },
            "ShortTermLongTermTotal": total_cg,
            "CapGains30Per115BBH": _to_rupees(result.vda_income),
            "TotalCapGains": total_cg,
        },
        "IncFromOS": {
            "OtherSrcThanOwnRaceHorse": os_normal_rate,
            "IncChargblSplRate": os_special_rate,
            "FromOwnRaceHorse": os_race_horse_income,
            "TotIncFromOS": _to_rupees(result.other_sources_income),
        },
        "CurrentYearLoss": _to_rupees(result.cyla_total_set_off),
        "BalanceAfterSetoffLosses": _to_rupees(max(_ZERO, result.gti_before_loss_setoff - result.cyla_total_set_off)),
        "BroughtFwdLossesSetoff": _to_rupees(result.bfla_total_set_off),
        "GrossTotalIncome": _to_rupees(result.gross_total_income),
        "IncChargeTaxSplRate111A112": total_special_rate_income,
        "DeductionsUnderScheduleVIA": _to_rupees(result.deductions_total),
        "TotalIncome": _to_rupees_rounded10(result.taxable_income),
        "IncChargeableTaxSplRates": total_special_rate_income,
        "NetAgricultureIncomeOrOtherIncomeForRate": _to_rupees(result.net_agricultural_income),
        "AggregateIncome": _to_rupees(result.aggregate_income),
        "LossesOfCurrentYearCarriedFwd": _to_rupees(result.cyla_remaining),
        # Item 17, "Deemed income under section 115JC (3 of Schedule AMT)" --
        # real whenever the 115JC comparison was made this year, not only
        # when AMT actually binds (matches _schedule_amt()'s own gate).
        "DeemedIncomeUs115JC": _to_rupees(deemed_income_115jc),
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
    # Form item 12 "Net tax liability (10 - 11d)" is computed BEFORE
    # interest/fees -- distinct from item 14's "Aggregate liability (12 +
    # 13e)", which adds them. Same bug class CLAUDE.md documents as already
    # fixed for ITR-1 (`itd/itr1.py:628-639`): reusing the calculator's own
    # ``net_tax_liability`` (which is item 14's fully-aggregated FINAL total,
    # interest/fees included) for item 12 mislabeled it, and made item 12
    # identical to item 14 (AggregateTaxInterestLiability, below) whenever
    # any interest/fee applied -- a direct self-contradiction, since item 12
    # must be strictly less than item 14 in that case.
    #
    # Items 1a-1d, 8, 9, 10, 12 (Phase 6i-4): confirmed against the official
    # form directly (Reference Docs by CBDT & ITD/Official ITR FORMS/
    # ITR-2-2026-Eng.pdf, Part B-TTI page). 1a = Schedule AMT's own Sl.4 (raw
    # 18.5% figure, no surcharge/cess); 1b/1c = that figure's own surcharge/
    # cess (added here, not inside Schedule AMT); 1d = 1a+1b+1c, the fully-
    # inclusive 115JC tax = result.amt_tax (real whenever the chapter is "in
    # play" this year, not only when AMT binds -- see calculators/itr2.py's
    # own comment on this field). 8 = higher of 1d and 7 (result.
    # gross_tax_payable, computed once in the calculator, never a second,
    # independently-hardcoded value here). 9 = brought-forward AMT credit
    # utilized this year (result.amt_credit_utilised, only nonzero when the
    # chapter is in play but AMT does NOT bind, i.e. 7 > 1d). 10 = 8a + 8c -
    # 9, where 8a = 8 (8b, this year's NEW eligible-startup ESOP deferral, is
    # zero in this engine today -- ESOPDeferralInput has no field for the
    # gross pre-deferral perquisite figure, a separate, already-documented
    # gap) and 8c = TaxDeferredPayableCY (real, already-computed ESOP data,
    # previously sitting in GrossTaxPay's own block but never reaching the
    # actual tax-payable arithmetic at all).
    amt = result.schedules.get("amt")
    chapter_active = getattr(amt, "chapter_xii_ba_applicable", False)
    tax_1a = getattr(amt, "amt_tax_before_surcharge_and_cess", _ZERO) if chapter_active else _ZERO
    surcharge_1b = getattr(amt, "amt_surcharge", _ZERO) if chapter_active else _ZERO
    cess_1c = getattr(amt, "amt_cess", _ZERO) if chapter_active else _ZERO
    total_1d = result.amt_tax
    tax_pay_after_credit_10 = max(
        _ZERO,
        result.gross_tax_payable + result.esop_deferred_payable_this_year - result.amt_credit_utilised,
    )
    balance_tax_after_relief = max(
        _ZERO, tax_pay_after_credit_10 - result.relief_89 - result.relief_90_91
    )
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
                "Section90": _to_rupees(result.relief_90_90a),
                "Section91": _to_rupees(result.relief_91),
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
            "GrossTaxPayable": _to_rupees(result.gross_tax_payable),
            # "GrossTaxPay" (distinct from "GrossTaxPayable" above, and
            # unrelated in meaning) is the eligible-startup ESOP-deferred-tax
            # structure (17(2)(vi)/80-IAC) -- see Schedule ESOP.
            # TaxDeferredPayableCY (item 8c) feeds item 10's own "8a+8c-9"
            # formula above. TaxInc17 (8a)/TaxDeferred17 (8b) now derive from
            # `ESOPDeferralInput.gross_perquisite_tax` for entries newly
            # created this assessment year (see the calculator's own
            # esop_tax_excluding_new_perquisite/esop_tax_deferred_this_year
            # computation for the full reasoning) -- both stay item-7-and-0
            # respectively when no such entry exists, matching prior
            # behaviour exactly for every return without a brand-new
            # ESOP deferral this year.
            "GrossTaxPay": {
                "TaxInc17": _to_rupees(result.esop_tax_excluding_new_perquisite),
                "TaxDeferred17": _to_rupees(result.esop_tax_deferred_this_year),
                "TaxDeferredPayableCY": _to_rupees(result.esop_deferred_payable_this_year),
            },
            "CreditUS115JD": _to_rupees(result.amt_credit_utilised),
            "TaxPayAfterCreditUs115JD": _to_rupees(tax_pay_after_credit_10),
            "NetTaxLiability": _to_rupees(balance_tax_after_relief),
            "IntrstPay": {
                "IntrstPayUs234A": _to_rupees(result.interest_234a),
                "IntrstPayUs234B": _to_rupees(result.interest_234b),
                "IntrstPayUs234C": _to_rupees(result.interest_234c),
                "LateFilingFee234F": _to_rupees(result.late_fee_234f),
                # Form item "13da"/"FeeFurnish234I" (fee u/s 234-I for
                # furnishing a revised return) -- was hardcoded 0 even though
                # the calculator already computes it (``result.fees_234i``);
                # TotalIntrstPay below sums it in, so leaving this sibling
                # disclosure field at 0 would itself no longer cross-foot.
                "FeeFurnish234I": _to_rupees(result.fees_234i),
                # Form item "13e" = 13a+13b+13c+13d+13da -- previously
                # summed only 234A/B/C (13a-13c), silently excluding the
                # 234F late-filing fee (13d, disclosed one field above) and
                # the 234-I fee (13da) from its own declared formula.
                "TotalIntrstPay": _to_rupees(total_interest + result.late_fee_234f + result.fees_234i),
            },
            "AggregateTaxInterestLiability": _to_rupees(result.net_tax_liability),
        },
        # PartB_TTI's own top-level "TaxPayDeemedTotIncUs115JC"/"Surcharge"/
        # "HealthEduCess"/"TotalTaxPayablDeemedTotInc" are items 1a/1b/1c/1d
        # -- confirmed by the field-name match against the official form's
        # own text ("Tax Pay[able on] Deemed Tot[al] Inc[ome] Under Sec
        # 115JC" = item 1a; "Total Tax Payabl[e] Deemed Tot[al] Inc[ome]" =
        # item 1d) and by their position as siblings of each other, distinct
        # from ComputationOfTaxLiability's own "TotalSurcharge"/
        # "EducationCess" (the NORMAL-provisions items 5iv/6). Previously
        # "Surcharge"/"HealthEduCess" here duplicated the normal-provisions
        # figures (result.surcharge/health_education_cess) -- the AMT-side
        # surcharge/cess, not the normal-provisions ones.
        "TaxPayDeemedTotIncUs115JC": _to_rupees(tax_1a),
        "TotalTaxPayablDeemedTotInc": _to_rupees(total_1d),
        "Surcharge": _to_rupees(surcharge_1b),
        "HealthEduCess": _to_rupees(cess_1c),
        # Form item 19 / schema description: "any interest in any asset
        # (including financial interest in any entity)/signing authority in
        # any account located outside India" -- Schedule FA is exactly the
        # disclosure this flag cross-references ("Ensure Schedule FA is
        # filled up if the answer is Yes"), so it must track whether any
        # real Schedule FA entry exists, not a hardcoded "No" regardless.
        "AssetOutIndiaFlag": "YES" if input_data.foreign_assets else "NO",
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
    # The schema's AssesseeVerPAN pattern requires an individual's own PAN
    # (4th character "P") -- an HUF's own `pan` (4th character "H") cannot
    # satisfy it. ITR2FilingProfile's own validator guarantees karta_pan is
    # set whenever assessee_status is HUF, so this is safe unconditionally.
    # CBDT rule #8: when verified by a REPRESENTATIVE (not Karta), the
    # declaration's own PAN is the representative's own PAN -- they are the
    # one actually signing/uploading the return, not the assessee. Was
    # previously always the assessee's own `profile.pan` regardless of
    # capacity, silently misrepresenting who made the declaration.
    # ITR2-IN-PROFILE-009 (input_rules.py) makes this pre-compute mandatory.
    if profile.assessee_status == AssesseeStatus.HUF:
        verification_pan = profile.karta_pan
    elif profile.verification_capacity == "R" and profile.assessee_representative is not None:
        verification_pan = profile.assessee_representative.pan
    else:
        verification_pan = profile.pan
    return _verification(name, profile.father_name, verification_pan, profile.verification_place, profile.verification_capacity)


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
        "PartB-TI": _partb_ti(result, input_data),
        "PartB_TTI": _partb_tti(result, input_data),
        "Verification": _verification_block(input_data),
    }
    if profile.tax_return_preparer is not None:
        tax_return_preparer = profile.tax_return_preparer
        itr2["TaxReturnPreparer"] = {
            "IdentificationNoOfTRP": tax_return_preparer.identification_number,
            "NameOfTRP": tax_return_preparer.name,
            "ReImbFrmGov": _to_rupees(tax_return_preparer.reimbursement_from_government),
        }
    optional: dict[str, Optional[dict[str, Any]]] = {
        "ScheduleS": _schedule_s(result, input_data),
        "ScheduleHP": _schedule_hp(result, input_data),
        "ScheduleOS": _schedule_os(result, input_data),
        "ScheduleCGFor23": _schedule_cg(input_data, result),
        "Schedule112A": _schedule_112a(input_data),
        "Schedule115AD": _schedule_115ad(input_data),
        "ScheduleVDA": _schedule_vda(input_data),
        "ScheduleCFL": _schedule_cfl(result, input_data),
        "ScheduleVIA": _schedule_via(result, input_data),
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
        **_chapter6a_detail_schedules(result, input_data),
    }
    itr2.update({k: v for k, v in optional.items() if v is not None})
    # Digest is computed over the COMPLETE ITR document (the whole
    # ``{"ITR": {"ITR2": ...}}`` JSON, matching the ITD reference
    # ``API_Testing/digest_generator.py`` and SOP §5.3 Step 1), with the
    # Digest value replaced by the placeholder "-".
    wrapped = {"ITR": {"ITR2": itr2}}
    itr2["CreationInfo"]["Digest"] = _compute_digest(wrapped)
    return wrapped
