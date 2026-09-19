"""
ITR-3 ITD JSON builder.

Produces an ITD-compliant JSON document matching the CBDT ITR-3 schema
(``ITR-3_2026_Main_V1.1``) with ``additionalProperties: false`` enforcement.

ITR-3 = ITR-2 common schedules + PGBP-specific schedules:
  ITR3ScheduleBP, PARTA_BS, PARTA_PL, PartA_GEN2, ScheduleDEP,
  ScheduleDCG, ScheduleDPM, ScheduleDOA, ScheduleIF, ScheduleGST,
  ScheduleICDS, ScheduleESR, ScheduleTPSA, Schedule80_IA, Schedule80_IB,
  Schedule80_IC, Schedule80RA, Schedule10AA,
  ManufacturingAccount, TradingAccount, PARTA_OI, PARTA_QD, ITR3ScheduleUD.

Required schedules (always present):
  CreationInfo, Form_ITR3, ITR3ScheduleBP, PARTA_BS, PARTA_PL,
  PartA_GEN1, PartA_GEN2, ScheduleCYLA, ScheduleBFLA,
  PartB-TI, PartB_TTI, Verification
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.engine.calculators.itr3 import ITR3Result
from app.schemas.itr3 import ITR3Input
from app.engine.common.hra import compute_hra_exemption
from app.engine.schedules.capital_gains import _exemption_claim_total, deemed_consideration_50c, _indexed_cost
from app.engine.itd.common import (
    _to_rupees,
    _to_rupees_rounded10,
    _zero_if_none,
    _str_or,
    _creation_info,
    _form_itr,
    _verification,
    _tax_return_preparer,
    _compute_digest,
)
from app.engine.itd.itr2 import (
    _schedule_fsi as _itr2_schedule_fsi,
    _schedule_tr1 as _itr2_schedule_tr1,
    _schedule_fa as _itr2_schedule_fa,
    _schedule_al as _itr2_schedule_al,
    _schedule_5a as _itr2_schedule_5a,
    _schedule_esop as _itr2_schedule_esop,
    _schedule_it as _itr2_schedule_it,
    _schedule_tds1 as _itr2_schedule_tds1,
    _schedule_tds2 as _itr2_schedule_tds2,
    _schedule_tds3 as _itr2_schedule_tds3,
    _schedule_tcs as _itr2_schedule_tcs,
    _schedule_amt as _itr2_schedule_amt,
    _schedule_amtc as _itr2_schedule_amtc,
    _deduction_claim_detail_rows as _itr2_deduction_claim_detail_rows,
    _exemption_or_dedn_us54_block as _itr2_exemption_or_dedn_us54_block,
    _nri_proviso_48 as _itr2_nri_proviso_48,
    _nri_foreign_asset as _itr2_nri_foreign_asset,
    _112a_source_rows as _itr2_112a_source_rows,
)
from app.engine.itd.cg_shared import (
    build_equity_mf_stt_rows,
    build_itr3_other_assets_stcg_block,
    build_itr3_other_assets_ltcg_block,
    build_stcg_buyback_loss_block,
    build_ltcg_buyback_loss_block,
)

_DR_RANGE = {
    "Upto15Of6": 0,
    "Upto15Of9": 0,
    "Up16Of9To15Of12": 0,
    "Up16Of12To15Of3": 0,
    "Up16Of3To31Of3": 0,
}

_ZERO = Decimal("0")


def _date_range_from_values(values: list[Decimal]) -> dict[str, Any]:
    """Serialize five quarterly capital-gain accrual values."""
    if len(values) != 5:
        raise ValueError("Schedule CG accrual requires exactly five quarterly values")
    return {"DateRange": {
        "Upto15Of6": _to_rupees(values[0]),
        "Upto15Of9": _to_rupees(values[1]),
        "Up16Of9To15Of12": _to_rupees(values[2]),
        "Up16Of12To15Of3": _to_rupees(values[3]),
        "Up16Of3To31Of3": _to_rupees(values[4]),
    }}


def _quarter_index(value: Any) -> int:
    """Return the official Schedule CG quarter index for a transfer date."""
    month, day = value.month, value.day
    if month in (4, 5) or (month == 6 and day <= 15):
        return 0
    if (month == 6 and day > 15) or month in (7, 8) or (month == 9 and day <= 15):
        return 1
    if (month == 9 and day > 15) or month in (10, 11) or (month == 12 and day <= 15):
        return 2
    if (month == 12 and day > 15) or month in (1, 2) or (month == 3 and day <= 15):
        return 3
    return 4


def _schedule_si(result: ITR3Result, typed_input: ITR3Input | None) -> dict[str, Any] | None:
    """Serialize Schedule SI from calculated special-rate entries."""


    si = result.schedules.get("si")
    if si is None or not si.entries:
        return None
    section_code_map = {
        "111A": "1A", "112": "21", "112A": "2A", "115BB": "5BB",
        "115BBE": "5BBE", "115BBF": "5BBF", "115BBG": "5BBG",
        "115BBH": "5BBH", "115BBJ": "5BBJ", "115BBA": "5BBA", "115E": "5Ea",
    }
    official_codes = {
        "1A", "21", "22", "21ciii", "2A", "5A1ai", "5A1aA", "5A1aii",
        "5A1aiia", "5A1aiiaa", "5A1aiiaaP", "5A1aiiaa2P", "5A1aiiab", "5A1aiiac",
        "5A1aiii", "5A1bA", "5AC1ab", "5AC1abD", "5AC1c", "5ACA1a", "5ACA1b",
        "5AD1i", "5AD1iDiv", "5AD1iP", "5ADii", "5AD1biip", "5ADiii", "5ADiiiP",
        "5BB", "5BBJ", "5BBA", "5BBH", "5BBH_BP", "5BBE", "5BBF", "5BBF_BP",
        "5BBG", "5BBG_BP", "5Ea", "5Eb", "DTAASTCG", "DTAALTCG", "DTAAOS",
        "PTI_STCG20P", "PTI_STCG30P", "PTI_LTCG12_5P112A", "PTI_LTCG12_5P",
    }
    rows: list[dict[str, Any]] = []
    for entry in si.entries:
        if entry.section == "111":
            continue
        code = section_code_map.get(entry.section, entry.section)
        if code not in official_codes:
            continue
        if entry.gross_income <= 0 and entry.taxable_income <= 0 and entry.tax_amount <= 0:
            continue
        rate = entry.tax_rate_pct
        rate_value: int | Decimal = int(rate) if rate == rate.to_integral_value() else rate
        rows.append({
            "SecCode": code,
            "SplRatePercent": rate_value,
            "SplRateInc": _to_rupees(entry.gross_income),
            "SplRateIncTax": _to_rupees(entry.tax_amount),
        })
    if not rows:
        return None
    return {
        "SplCodeRateTax": rows,
        "TotSplRateInc": _to_rupees(sum((entry.gross_income for entry in si.entries if entry.section != "111"), Decimal("0"))),
        "TotSplRateIncTax": _to_rupees(si.total_special_rate_tax),
    }




def _parta_gen1(
    pan: str,
    first_name: str,
    middle_name: str,
    last_name: str,
    dob: str,
    residence_no: str,
    locality: str,
    city: str,
    state_code: str,
    country_code: str,
    residence_name: Optional[str] = None,
    road_or_street: Optional[str] = None,
    zip_code: Optional[str] = None,
    mobile_country_code: str = "91",
    residential_status: str = "RES",
    return_file_sec: int = 11,
    mobile_no: Optional[str] = None,
    email: Optional[str] = None,
    aadhaar: Optional[str] = None,
    office_phone_std_code: Optional[str] = None,
    office_phone_no: Optional[str] = None,
    secondary_mobile_country_code: Optional[str] = None,
    secondary_mobile_no: Optional[str] = None,
    secondary_email: Optional[str] = None,
    secondary_add: str = "N",
    alternate_residence_no: Optional[str] = None,
    alternate_residence_name: Optional[str] = None,
    alternate_road_or_street: Optional[str] = None,
    alternate_locality: Optional[str] = None,
    alternate_city: Optional[str] = None,
    alternate_state_code: Optional[str] = None,
    alternate_country_code: Optional[str] = None,
    alternate_pin_code: Optional[str] = None,
    alternate_zip_code: Optional[str] = None,
    pin_code: Optional[str] = None,
    assessee_status: str = "I",
    typed_input: ITR3Input | None = None,
) -> dict:
    if not mobile_no or not mobile_no.isdigit():
        raise ValueError("ITR-3 personal information requires a sourced numeric mobile number")
    if not email or "@" not in email:
        raise ValueError("ITR-3 personal information requires a sourced email address")
    address: dict[str, Any] = {
        "ResidenceNo": _str_or(residence_no, "1"),
        "ResidenceName": residence_name or "",
        "RoadOrStreet": road_or_street or "",
        "LocalityOrArea": _str_or(locality, "Locality"),
        "CityOrTownOrDistrict": _str_or(city, "City"),
        "StateCode": _str_or(state_code, "07"),
        "CountryCode": _str_or(country_code, "91"),
        "PinCode": int(pin_code) if pin_code and pin_code.isdigit() else 110001,
        "ZipCode": zip_code or "",
        "CountryCodeMobile": int(mobile_country_code) if mobile_country_code and mobile_country_code.isdigit() else 91,
        "MobileNo": int(mobile_no),
        "CountryCodeMobileNoSec": (
            int(secondary_mobile_country_code)
            if secondary_mobile_country_code and secondary_mobile_country_code.isdigit()
            else 0
        ),
        "MobileNoSec": int(secondary_mobile_no) if secondary_mobile_no and secondary_mobile_no.isdigit() else 0,
        "EmailAddress": email,
    }
    # PDF A17's office/residence phone (schema `Address.Phone`) -- a
    # genuinely distinct field from the primary mobile number above; only
    # emitted when a real STD code/number was sourced, matching this
    # builder's own "omit rather than fabricate" convention for every other
    # optional block (e.g. AadhaarCardNo below).
    if office_phone_std_code and office_phone_no:
        address["Phone"] = {
            "STDcode": int(office_phone_std_code) if office_phone_std_code.isdigit() else 0,
            "PhoneNo": office_phone_no,
        }
    if secondary_email:
        address["EmailAddressSec"] = secondary_email
    result: dict[str, Any] = {
        "AssesseeName": {
            "FirstName": first_name or "",
            "MiddleName": middle_name or "",
            "SurNameOrOrgName": last_name or "ASSESSEE",
        },
        "PAN": pan.upper(),
        "Address": address,
        # Secondary address details are mandatory in Part A General
        # Information in practice -- ITR-2's own builder found this live
        # (`app/engine/itd/itr2.py`'s `SecondaryAdd`/`AlternateAddress`
        # comment: ITD's Type-2 UAT validateItr rejected an entirely-absent
        # AlternateAddress with "Secondary address details are not provided
        # in Schedule Part A General information", 2026-09-13, PAN
        # GOYPT2026A) even though neither field is schema-required. ITR-3
        # shares the identical PersonalInfo/AlternateAddress schema shape,
        # so the same live rejection almost certainly applies here --
        # always emit "Y" and always emit a real AlternateAddress block,
        # falling back to a copy of the primary address when the taxpayer
        # genuinely has none, rather than the schema-literal (but
        # apparently ITD-rejected) choice of omitting the block for "N".
        "SecondaryAdd": "Y",
        "DOB": _str_or(dob, "1990-01-01"),
        "Status": assessee_status,
    }
    if aadhaar:
        result["AadhaarCardNo"] = aadhaar
    if secondary_add == "Y":
        # Real, distinct alternate-address data sourced from the taxpayer's
        # own secondary-address entry. `build_itr3_json`'s own
        # required-identity gate already raises before this point if
        # `secondary_address_different` is True but these weren't actually
        # sourced, so callers here are guaranteed at least the four
        # schema-required alternate fields.
        alternate_address: dict[str, Any] = {
            "ResidenceNo": alternate_residence_no or "",
            "ResidenceName": alternate_residence_name or "",
            "RoadOrStreet": alternate_road_or_street or "",
            "LocalityOrArea": alternate_locality or "",
            "CityOrTownOrDistrict": alternate_city or "",
            "StateCode": alternate_state_code or "",
            "CountryCode": alternate_country_code or "91",
        }
        # PinCode/ZipCode are both genuinely optional on AlternateAddress
        # (neither is in the schema's own `required` list -- unlike the
        # primary Address, a foreign alternate address is expected to carry
        # only a ZipCode) -- emit whichever was actually sourced, never a
        # fabricated PIN.
        if alternate_pin_code and alternate_pin_code.isdigit():
            alternate_address["PinCode"] = int(alternate_pin_code)
        if alternate_zip_code:
            alternate_address["ZipCode"] = alternate_zip_code
        result["AlternateAddress"] = alternate_address
    else:
        # No genuinely distinct secondary address -- "same as primary",
        # matching ITR-2's own live-verified fallback exactly (see the
        # SecondaryAdd comment above). Copy every primary Address field
        # AlternateAddress actually has room for.
        result["AlternateAddress"] = {
            "ResidenceNo": address["ResidenceNo"],
            "ResidenceName": address["ResidenceName"],
            "RoadOrStreet": address["RoadOrStreet"],
            "LocalityOrArea": address["LocalityOrArea"],
            "CityOrTownOrDistrict": address["CityOrTownOrDistrict"],
            "StateCode": address["StateCode"],
            "CountryCode": address["CountryCode"],
            "PinCode": address["PinCode"],
            "ZipCode": address["ZipCode"],
        }
    filing_status: dict[str, Any] = {
        "ReturnFileSec": return_file_sec,
        # ITR-3's mapper currently requires an explicit business/professional
        # income declaration before it will build a typed input at all (see
        # `draft_to_itr3_input`'s own "requires explicit business income"
        # guard), so every canonical ITR-3 filing this system produces
        # genuinely has business/professional income for the current AY --
        # "Y" is not a fabricated default here, it reflects a real,
        # enforced precondition. If that mapper precondition is ever
        # relaxed, this must be re-derived rather than left hardcoded.
        "IncFrmBusOrProf": "Y",
        "ResidentialStatus": residential_status,
        "ItrFilingDueDate": "2026-10-31",
        "ForeignExchangeFlag": (
            typed_input.ifsc_unit_foreign_exchange_flag
            if typed_input is not None and typed_input.ifsc_unit_foreign_exchange_flag else "N"
        ),
        "FiiFpiFlag": "Y" if typed_input is not None and typed_input.is_fii_fpi else "N",
        "HeldUnlistedEqShrPrYrFlg": (
            "Y" if typed_input is not None and typed_input.held_unlisted_equity else "N"
        ),
        "CompDirectorPrvYrFlg": (
            "Y" if typed_input is not None and typed_input.is_company_director else "N"
        ),
        "PartnerInFirmFlg": (
            "Y" if typed_input is not None and typed_input.is_partner_in_firm else "N"
        ),
        "SeventhProvisio139": (
            "Y" if typed_input is not None and typed_input.seventh_proviso_139 else "N"
        ),
        "AsseseeRepFlg": (
            "Y" if typed_input is not None and typed_input.assessee_representative_name else "N"
        ),
        "Form10IEAEarlierAYOldRegime": (
            typed_input.form_10iea_earlier_ay_old_regime if typed_input is not None else "N"
        ),
        "PortugeseCC5A": (
            "Y" if typed_input is not None and typed_input.portuguese_civil_code_applies else "N"
        ),
    }
    if typed_input is None:
        return {"PersonalInfo": result, "FilingStatus": filing_status}

    # Seventh proviso to section 139(1) (A19(c)).
    if typed_input.deposit_exceeds_one_crore:
        filing_status["DepAmtAggAmtExcd1CrPrYrFlg"] = "Y"
        filing_status["AmtSeventhProvisio139i"] = _to_rupees(typed_input.current_account_deposits)
    else:
        filing_status["DepAmtAggAmtExcd1CrPrYrFlg"] = "N"
    if typed_input.foreign_travel_flag:
        filing_status["IncrExpAggAmt2LkTrvFrgnCntryFlg"] = "Y"
        filing_status["AmtSeventhProvisio139ii"] = _to_rupees(typed_input.foreign_travel_expenditure)
    else:
        filing_status["IncrExpAggAmt2LkTrvFrgnCntryFlg"] = "N"
    if typed_input.electricity_expenditure_flag:
        filing_status["IncrExpAggAmt1LkElctrctyPrYrFlg"] = "Y"
        filing_status["AmtSeventhProvisio139iii"] = _to_rupees(typed_input.electricity_expenditure)
    else:
        filing_status["IncrExpAggAmt1LkElctrctyPrYrFlg"] = "N"
    if typed_input.other_clause_iv_flag:
        filing_status["clauseiv7provisio139i"] = "Y"
        if typed_input.seventh_proviso_clause_iv_entries:
            filing_status["clauseiv7provisio139iDtls"] = [
                {"clauseiv7provisio139iNature": nature, "clauseiv7provisio139iAmount": _to_rupees(amount)}
                for nature, amount in typed_input.seventh_proviso_clause_iv_entries
            ]
    else:
        filing_status["clauseiv7provisio139i"] = "N"

    # A19(d)/(e) revised/defective/notice metadata.
    if typed_input.receipt_number:
        filing_status["ReceiptNo"] = typed_input.receipt_number
    if typed_input.original_return_date:
        filing_status["OrigRetFiledDate"] = typed_input.original_return_date
    if typed_input.notice_number:
        filing_status["NoticeNo"] = typed_input.notice_number
    if typed_input.notice_date:
        filing_status["NoticeDate"] = typed_input.notice_date

    # A19(f) residential-status conditions/jurisdictions/stay-days.
    if typed_input.conditions_res_status:
        filing_status["ConditionsResStatus"] = typed_input.conditions_res_status
    if typed_input.jurisdiction_residence_entries:
        filing_status["JurisdictionResPrevYr"] = {
            "JurisdictionResPrevYrDtls": [
                {"JurisdictionResidence": code, "TIN": tin}
                for code, tin in typed_input.jurisdiction_residence_entries
            ]
        }
    if typed_input.total_stay_india_prev_yr is not None:
        filing_status["TotalPrStayIndiaPrevYr"] = typed_input.total_stay_india_prev_yr
    if typed_input.total_stay_india_4_prec_yr is not None:
        filing_status["TotalPrStayIndia4PrecYr"] = typed_input.total_stay_india_4_prec_yr

    # A19(g) section 115H -- CBDT rule #83 wants a real Y/N once the
    # question has actually been presented and answered, not just when the
    # benefit is claimed (matching ITR-2's own fix for the identical rule).
    if typed_input.benefit_us_115h is not None:
        filing_status["BenefitUs115HFlg"] = "Y" if typed_input.benefit_us_115h else "N"

    # A19(i) representative assessee.
    if typed_input.assessee_representative_name and typed_input.assessee_representative_mobile_no:
        filing_status["AssesseeRep"] = {
            "RepName": typed_input.assessee_representative_name,
            "RepEmailID": typed_input.assessee_representative_email or "",
            "CountryCodeRepMobileNo": (
                int(typed_input.assessee_representative_mobile_country_code)
                if typed_input.assessee_representative_mobile_country_code
                and typed_input.assessee_representative_mobile_country_code.isdigit() else 91
            ),
            "RepMobileNo": int(typed_input.assessee_representative_mobile_no),
        }

    # A19(j) company directorships.
    if typed_input.company_director_entries:
        rows = []
        for entry in typed_input.company_director_entries:
            row: dict[str, Any] = {
                "NameOfCompany": entry["company_name"],
                "CompanyType": entry["company_type"],
                "SharesTypes": entry["shares_type"],
            }
            if entry.get("pan"):
                row["PAN"] = entry["pan"]
            if entry.get("din"):
                row["DIN"] = entry["din"]
            rows.append(row)
        filing_status["CompDirectorPrvYr"] = {"CompDirectorPrvYrDtls": rows}

    # A19(k) partner in firm.
    if typed_input.partner_in_firm_entries:
        filing_status["PartnerInFirm"] = {
            "PartnerInFirmDtls": [
                {"NameOfFirm": entry["firm_name"], "PAN": entry["pan"]}
                for entry in typed_input.partner_in_firm_entries
            ]
        }

    # A19(l) unlisted equity shares held.
    if typed_input.unlisted_equity_entries:
        rows = []
        for entry in typed_input.unlisted_equity_entries:
            row = {
                "NameOfCompany": entry["company_name"],
                "CompanyType": entry["company_type"],
                "OpngBalNumberOfShares": int(entry["opening_shares"]),
                "OpngBalCostOfAcquisition": _to_rupees(entry["opening_cost"]),
                "ClsngBalNumberOfShares": int(entry["closing_shares"]),
                "ClsngBalCostOfAcquisition": _to_rupees(entry["closing_cost"]),
            }
            if entry.get("pan"):
                row["PAN"] = entry["pan"]
            if entry.get("acquired_shares"):
                row["ShrAcqDurYrNumberOfShares"] = int(entry["acquired_shares"])
            if entry.get("date_of_acquisition"):
                row["DateOfSubscrPurchase"] = entry["date_of_acquisition"]
            if entry.get("face_value_per_share"):
                row["FaceValuePerShare"] = _to_rupees(entry["face_value_per_share"])
            if entry.get("issue_price_per_share"):
                row["IssuePricePerShare"] = int(entry["issue_price_per_share"])
            if entry.get("purchase_price_per_share"):
                row["PurchasePricePerShare"] = _to_rupees(entry["purchase_price_per_share"])
            if entry.get("transferred_shares"):
                row["ShrTrnfNumberOfShares"] = int(entry["transferred_shares"])
            if entry.get("transfer_sale_consideration"):
                row["ShrTrnfSaleConsideration"] = _to_rupees(entry["transfer_sale_consideration"])
            rows.append(row)
        filing_status["HeldUnlistedEqShrPrYr"] = {"HeldUnlistedEqShrPrYrDtls": rows}

    # A19(m)/(n) NRI permanent establishment / significant economic presence.
    if typed_input.nri_pe_in_india:
        filing_status["NriPEinIndia"] = typed_input.nri_pe_in_india
    if typed_input.nri_sep_in_india:
        filing_status["NriSEPinIndia"] = typed_input.nri_sep_in_india
        if typed_input.nri_sep_in_india == "Y":
            filing_status["AggrPaymentTransac"] = float(typed_input.sep_aggregate_payment)
            filing_status["NumberOfUsers"] = typed_input.sep_number_of_users

    # A19(p) SEBI registration number (only meaningful when FII/FPI).
    if typed_input.is_fii_fpi and typed_input.sebi_registration_number:
        filing_status["SebiRegnNo"] = typed_input.sebi_registration_number

    # A19(q) Legal Entity Identifier.
    if typed_input.lei_number:
        filing_status["LEIDtls"] = {"LEINumber": typed_input.lei_number}
        if typed_input.lei_valid_upto_date:
            filing_status["LEIDtls"]["ValidUptoDate"] = typed_input.lei_valid_upto_date

    # Form 10-IEA cascade (A19(b)(I)) -- CBDT ITR-4 Validation Rules AY
    # 2026-27 rules #353-364 (the identical A23 gate exists verbatim on
    # ITR-3's own schema): Form10IEAEarlierAYOldRegime gates two MUTUALLY
    # EXCLUSIVE sub-branches. Emitting both at once -- even with "N"
    # answers -- was REJECTED live by ITD's Type-2 UAT validateItr for
    # ITR-4 with "Multiple question shall not be responded in A23"
    # (2026-09-04, PAN SRGPZ2026C); ITR-3 shares the identical field set
    # and almost certainly has the identical live constraint, so this
    # branch discipline is ported deliberately, not guessed at fresh.
    if typed_input.form_10iea_earlier_ay_old_regime == "Y":
        if typed_input.form_10iea_ass_year:
            filing_status["Form10IEAAssYear"] = typed_input.form_10iea_ass_year
        if typed_input.form_10iea_earlier_ay_ack_old_regime:
            filing_status["Form10IEAEarlierAYAckOldRegime"] = int(typed_input.form_10iea_earlier_ay_ack_old_regime)

        filing_status["F10IEAEarlierAYNewRegime"] = typed_input.f10iea_earlier_ay_new_regime
        if typed_input.ass_yr_f10iea_new_tax_reg:
            filing_status["AssYrF10IEANewTaxReg"] = typed_input.ass_yr_f10iea_new_tax_reg
        if typed_input.form_10iea_earlier_ay_ack_new_regime:
            filing_status["Form10IEAEarlierAYAckNewRegime"] = int(typed_input.form_10iea_earlier_ay_ack_new_regime)

        filing_status["F10IEACurrAYNewRegime"] = typed_input.f10iea_curr_ay_new_regime
        if typed_input.f10iea_date_curr_ay_new_tax:
            filing_status["F10IEADateCurrAYNewTax"] = typed_input.f10iea_date_curr_ay_new_tax
        if typed_input.f10iea_ack_no_curr_ay_new_tax:
            filing_status["F10IEAAckNoCurrAYNewTax"] = int(typed_input.f10iea_ack_no_curr_ay_new_tax)
    elif typed_input.form_10iea_earlier_ay_old_regime == "N":
        filing_status["F10IEACurrAYOldRegime"] = typed_input.f10iea_curr_ay_old_regime
        if typed_input.f10iea_date_curr_ay_old_tax:
            filing_status["F10IEADateCurrAYOldTax"] = typed_input.f10iea_date_curr_ay_old_tax
        if typed_input.f10iea_ack_no_curr_ay_old_tax:
            filing_status["F10IEAAckNoCurrAYOldTax"] = int(typed_input.f10iea_ack_no_curr_ay_old_tax)

    return {"PersonalInfo": result, "FilingStatus": filing_status}


# ============================================================================
# PartA_GEN2 — Business-specific (REQUIRED in ITR-3)
# ============================================================================

def _parta_gen2(typed_input: ITR3Input | None = None) -> dict:
    """Build Part A-GEN2 from typed audit and business disclosures."""
    audit = typed_input.audit_info if typed_input is not None else None
    nature_rows = typed_input.nature_of_business if typed_input is not None else None
    audit_info: dict[str, Any] = {
        "AccountAuditFlag": "Y" if audit and audit.account_audited else "N",
        "AuditAccountantFlg": "Y" if audit and audit.audited_by_accountant else "N",
        "IncDclrdUs": "Y" if audit and audit.income_declared_under_presumptive else "N",
        "LiableSec44AAflg": "Y" if audit and audit.liable_sec_44aa else "N",
        "LiableSec44ABflg": "Y" if audit and audit.liable_sec_44ab else "N",
        "LiableSec92Eflg": "Y" if audit and audit.liable_sec_92e else "N",
    }
    if audit is not None:
        # A20(a2i) turnover band.
        if audit.total_sales_band:
            audit_info["TotalSalesExcOneCr"] = audit.total_sales_band
        # A20(a2ii)/(a2iii) cash-receipts/payments percentage bands --
        # previously hardcoded to "Upto5Per" unconditionally regardless of
        # the real return; now sourced for real, and omitted (not
        # fabricated) when the taxpayer's turnover band doesn't reach this
        # question at all.
        if audit.receipts_cash_band:
            audit_info["AgrOFAllAmtsRcvd"] = audit.receipts_cash_band
        if audit.payments_cash_band:
            audit_info["AgrOFAllPayMade"] = audit.payments_cash_band
        # A20(b)(i)/(ii)/(iii) reason for 44AB liability.
        if audit.condition_44ab:
            audit_info["Cndnfor44AB"] = audit.condition_44ab
        if audit.presumptive_44ad or audit.presumptive_44ada or audit.presumptive_44ae or audit.presumptive_44bb:
            audit_info["BiiDetails"] = {
                "44AD": "Y" if audit.presumptive_44ad else "N",
                "44ADA": "Y" if audit.presumptive_44ada else "N",
                "44AE": "Y" if audit.presumptive_44ae else "N",
                "44BB": "Y" if audit.presumptive_44bb else "N",
            }
        # A20(c)(1)-(4) audit-report detail -- only meaningful once the
        # accountant-audit question itself is answered "Yes".
        if audit.audited_by_accountant:
            if audit.audit_report_furnish_date:
                audit_info["AuditReportFurnishDate"] = audit.audit_report_furnish_date
            if audit.ack_num_44ab:
                audit_info["AckNum44AB"] = int(audit.ack_num_44ab)
            if audit.auditor_firm_name:
                audit_info["AudFrmName"] = audit.auditor_firm_name
            if audit.auditor_firm_pan:
                audit_info["AudFrmPAN"] = audit.auditor_firm_pan
            if audit.auditor_firm_aadhaar:
                audit_info["AudFrmAadhaar"] = audit.auditor_firm_aadhaar
        # A20(d)(ii) section 92E audit detail -- "audited" is distinct from
        # merely "liable" (LiableSec92Eflg above).
        if audit.audited_under_92e and audit.audit_92e_date and audit.ack_num_92e:
            audit_info["AuditDetails92E"] = {
                "DateOfAudit": audit.audit_92e_date,
                "AckNum92E": int(audit.ack_num_92e),
            }
        # A20(d)(iii) other-section audit reports required for specified
        # deductions (Schedule 10A/10AA/44DA/50B/80-IA family/80JJAA/80LA/
        # 115JC audit disclosures).
        if audit.other_section_audit_entries:
            rows = []
            for entry in audit.other_section_audit_entries:
                if not entry.get("auditedSection"):
                    continue
                row: dict[str, Any] = {
                    "AuditedSection": entry["auditedSection"],
                    "AuditFlag": entry.get("auditFlag") or "N",
                }
                if entry.get("dateOfAudit"):
                    row["OthAuditDtls"] = "Y"
                    row["DateOfAudit"] = entry["dateOfAudit"]
                    if entry.get("ackNumOth"):
                        row["AckNumOth"] = int(entry["ackNumOth"])
                else:
                    row["OthAuditDtls"] = "N"
                rows.append(row)
            if rows:
                audit_info["AuditDetails"] = rows
        # A20(e) audit report(s) under Acts other than the Income-tax Act.
        if audit.other_act_audit_entries:
            rows = []
            for entry in audit.other_act_audit_entries:
                if not entry.get("act"):
                    continue
                row = {"AuditReportAct": entry["act"]}
                if entry["act"] == "19" and entry.get("actOthers"):
                    row["AuditReportActOthers"] = entry["actOthers"]
                if entry.get("auditedSection"):
                    row["AuditedSection"] = entry["auditedSection"]
                if entry.get("dateOfAudit"):
                    row["OtherITActFlag"] = "Y"
                    row["OthAuditDtlsOthThanITAct"] = "Y"
                    row["DateOfAudit"] = entry["dateOfAudit"]
                else:
                    row["OtherITActFlag"] = "N"
                    row["OthAuditDtlsOthThanITAct"] = "N"
                rows.append(row)
            if rows:
                audit_info["AuditReportDetails"] = rows
    nature_of_business = []
    for row in (nature_rows or []):
        nob_row: dict[str, Any] = {"Code": str(row.code).zfill(5)}
        # TradeName1/Description are both genuinely optional (only Code is
        # schema-required) and, when present, must be a real non-empty
        # string -- emitting "" here would itself fail schema validation
        # (NatOfBus's own nonEmptyString constraint), so omit rather than
        # emit a fabricated blank.
        if row.trade_name:
            nob_row["TradeName1"] = row.trade_name
        if row.description:
            nob_row["Description"] = row.description
        nature_of_business.append(nob_row)
    return {
        "AuditInfo": audit_info,
        "NatOfBus": {"NatureOfBusiness": nature_of_business},
    }


# ============================================================================
# ITR3ScheduleBP — Core PGBP (REQUIRED)
# ============================================================================

def _schedule_bp(result: ITR3Result, typed_input: ITR3Input | None = None) -> dict:
    """Build Schedule BP from calculated totals and explicit typed adjustments.

    The form's rows 6--38 are an arithmetic bridge, not independent totals:
    cross-head income/expense reallocation (3a-3g/7a-7g), exempt income
    (5a-5d/5A/8a/8b), Rule 7/7A/7B/8 composite income (4b/37a-38), book
    depreciation, tax depreciation, and the typed Part-A-OI-cross-referenced
    disallowances/deductions (19/23/28/29/30) all flow through this chain
    to reach items 34/36/A37 -- every term here matches the identical
    formula already applied inside ``compute_pgbp()`` itself
    (``app/engine/schedules/business.py``), so ``row36``/``rowA37`` below
    always equal ``pgbp.non_spec_item36_signed``/``pgbp.non_spec_signed``
    exactly (proven algebraically and locked in by
    ``test_itr3_schedule_bp_reallocation_and_exempt_income_reduce_taxable_income``
    and the neutrality tests below it).
    """
    pgbp = result.schedules.get("pgbp")
    z = Decimal("0")
    business = typed_input.business_income if typed_input is not None else None

    if pgbp:
        non_spec_pbt = pgbp.non_spec_profit_before_tax
        non_spec_signed = pgbp.non_spec_signed
        spec_signed = pgbp.speculative_signed
        specified_signed = pgbp.specified_signed
        total_biz = pgbp.total_business_income
        books_depr = pgbp.non_spec_depreciation_books
        it_depr = pgbp.non_spec_depreciation_it
    else:
        non_spec_pbt = non_spec_signed = spec_signed = specified_signed = total_biz = books_depr = it_depr = z

    def amount(name: str) -> Decimal:
        """Read one non-negative typed business adjustment."""
        return getattr(business, name, z) if business is not None else z

    # Item 35 / item 4a's own breakdown -- presumptive income (44AD/44ADA/
    # 44AE) already included in item 1's raw P&L figure. The 44B-family
    # non-resident-shipping/aircraft/turnkey sections and 44DA have no
    # typed source anywhere in this codebase and stay 0 -- not supported,
    # not merely unmapped.
    presumptive_ad = amount("presumptive_44ad_income")
    presumptive_ada = amount("presumptive_44ada_income")
    presumptive_ae = amount("presumptive_44ae_income")
    presumptive_total = presumptive_ad + presumptive_ada + presumptive_ae

    # Items 3a-3g -- income/receipts credited to P&L but chargeable under
    # another head. "OtherSources" (3d) is the figure actually subtracted;
    # Dividend/OtherThanDividend (3di/3dii) are 3d's own informational
    # dividend-vs-other split, disclosed but not separately subtracted
    # (that would double-count 3d).
    realloc_inc_salary = amount("reallocation_income_salary")
    realloc_inc_hp = amount("reallocation_income_house_property")
    realloc_inc_cg = amount("reallocation_income_capital_gains")
    realloc_inc_os = amount("reallocation_income_other_sources")
    realloc_inc_dividend = amount("reallocation_income_dividend")
    realloc_inc_other_div = amount("reallocation_income_other_than_dividend")
    realloc_inc_115bbf = amount("reallocation_income_115bbf")
    realloc_inc_115bbg = amount("reallocation_income_115bbg")
    realloc_inc_115bbh = amount("reallocation_income_115bbh")
    realloc_income_total = (
        realloc_inc_salary + realloc_inc_hp + realloc_inc_cg + realloc_inc_os
        + realloc_inc_115bbf + realloc_inc_115bbg + realloc_inc_115bbh
    )

    # Item 4b -- profit from a composite Rule 7/7A/7B(1)/7B(1A)/8 activity
    # (tea/coffee/rubber growing-and-manufacturing), subtracted here and
    # re-introduced (at its taxpayer-computed, rule-adjusted figure) via
    # items 37a-37e below.
    rule7_profit = amount("rule7_profit")
    rule7a_profit = amount("rule7a_profit")
    rule7b1_profit = amount("rule7b1_profit")
    rule7b1a_profit = amount("rule7b1a_profit")
    rule8_profit = amount("rule8_profit")
    rule_7_8_total = rule7_profit + rule7a_profit + rule7b1_profit + rule7b1a_profit + rule8_profit

    # Items 5a/5b/5c/5A -- exempt / not-chargeable income credited to P&L.
    exempt_firm = amount("exempt_income_firm_share")
    exempt_aop = amount("exempt_income_aop_boi_share")
    exempt_other = amount("exempt_income_other")
    exempt_total = exempt_firm + exempt_aop + exempt_other
    not_chargeable = amount("income_not_chargeable")

    # Item 6 = 1 - 2a - 2b - 3(a-g) - 4a - 4b - 5d - 5A. Items 2a/2b are
    # structurally 0 by this codebase's own architecture (speculative/
    # specified P&L are tracked as separate fields, never co-mingled into
    # net_profit_before_tax).
    row6 = (
        non_spec_pbt - presumptive_total - realloc_income_total - rule_7_8_total
        - exempt_total - not_chargeable
    )

    # Items 7a-7g / 8a / 8b -- expenses debited to P&L relating to another
    # head or to exempt income; added back (they should never have
    # reduced business income).
    realloc_exp_salary = amount("reallocation_expense_salary")
    realloc_exp_hp = amount("reallocation_expense_house_property")
    realloc_exp_cg = amount("reallocation_expense_capital_gains")
    realloc_exp_os = amount("reallocation_expense_other_sources")
    realloc_exp_115bbf = amount("reallocation_expense_115bbf")
    realloc_exp_115bbg = amount("reallocation_expense_115bbg")
    realloc_exp_115bbh = amount("reallocation_expense_115bbh")
    realloc_expense_total = (
        realloc_exp_salary + realloc_exp_hp + realloc_exp_cg + realloc_exp_os
        + realloc_exp_115bbf + realloc_exp_115bbg + realloc_exp_115bbh
    )
    expense_exempt_8a = amount("expense_relating_to_exempt_income")
    expense_exempt_8b = amount("expense_exempt_income_disallowed_us14a")
    row9 = realloc_expense_total + expense_exempt_8a + expense_exempt_8b

    # Item 10 = 6 + 9 (NOT yet adjusted for depreciation -- items 11/12
    # are a separate step feeding item 13, not item 10).
    row10 = row6 + row9
    # Item 13 = 10 + 11 - 12iii.
    row13 = row10 + books_depr - it_depr
    row14 = amount("disallowance_us36")
    row15 = amount("disallowance_us37")
    row16 = amount("disallowance_us40")
    row17 = amount("disallowance_us40a")
    row18 = amount("disallowance_us43b")
    # Item 19 -- MSME interest disallowance (s.23 of the MSMED Act).
    row19 = amount("msme_interest_disallowance")
    row20 = amount("deemed_income_us41")
    row21 = sum((amount(name) for name in (
        "deemed_income_us32ad", "deemed_income_us33ab", "deemed_income_us33aba",
        "deemed_income_us35aba", "deemed_income_us35abb", "deemed_income_us40a3a",
        "deemed_income_us72a", "deemed_income_us80hhd", "deemed_income_us80ia",
    )), z)
    row22 = amount("deemed_income_us43ca")
    # Item 23 -- any other item of addition under section 28 to 44DA.
    row23 = amount("other_addition_28_to_44da")
    row24 = amount("other_additions")
    row25 = amount("icds_increase")
    row27 = amount("deduction_us32_1_iii")
    # Items 28/29/30 -- s.35/35CCC/35CCD excess deduction, and amounts
    # disallowed in an earlier year under s.40/s.43B now allowable.
    row28 = amount("section35_excess_deduction")
    row29 = amount("section40_now_allowable")
    row30 = amount("section43b_now_allowable")
    row31 = amount("other_deductions")
    row32 = amount("icds_decrease")
    # Item 26 = sum(14..25); item 33 = sum(27..32).
    total_additions = sum((row14, row15, row16, row17, row18, row19, row20, row21, row22, row23, row24, row25), z)
    total_deductions = sum((row27, row28, row29, row30, row31, row32), z)
    # Item 34 = 13 + 26 - 33.
    row34 = row13 + total_additions - total_deductions
    # Item 36 = 34 + 35viii.
    row36 = row34 + presumptive_total

    # Items 37a-37e -- the taxpayer's own Rule 7/7A/7B(1)/7B(1A)/8-adjusted
    # taxable (non-agricultural) portion of the item-4b composite profit,
    # added on top of item 36 (37f, "income other than Rule 7A/7B/8") to
    # reach item A37. When no composite-income business is declared, all
    # five stay 0 and A37 == 36 exactly, matching the form's own "if rule
    # 7A, 7B or 8 is not applicable, enter same figure as in 36".
    rule7_taxable = amount("rule7_taxable_income")
    rule7a_deemed = amount("rule7a_deemed_income")
    rule7b1_deemed = amount("rule7b1_deemed_income")
    rule7b1a_deemed = amount("rule7b1a_deemed_income")
    rule8_deemed = amount("rule8_deemed_income")
    rule_7_8_taxable_total = rule7_taxable + rule7a_deemed + rule7b1_deemed + rule7b1a_deemed + rule8_deemed
    row37f = row36
    row_a37 = rule7_taxable + rule7a_deemed + rule7b1_deemed + rule7b1a_deemed + rule8_deemed + row37f
    # Item 38 -- balance of income deemed to be from agriculture:
    # 4b - (37a+37b+37c+37d+37e).
    row38 = rule_7_8_total - rule_7_8_taxable_total
    # By construction, row36/row_a37 always equal
    # pgbp.non_spec_item36_signed/pgbp.non_spec_signed exactly (the same
    # unclamped totals compute_pgbp itself used for GTI/CYLA) -- proven
    # algebraically and locked in by the reallocation/rule-7-8 neutrality
    # tests in tests/test_itr3_business_deductions.py.

    # Part E -- intra-head (Section 70) set-off of a non-speculative
    # business LOSS (item A37, if negative) against speculative/specified
    # business INCOME (B42/C48), read directly from the already-computed
    # pgbp result (compute_pgbp performs this same calculation for its own
    # CYLA-feed purposes, so the disclosure here matches the actual
    # cross-head loss handling exactly rather than being independently
    # re-derived and risking drift).
    if pgbp:
        part_e_loss_row = non_spec_signed if non_spec_signed < 0 else z
        _bus_loss_obj = {
            "LossSetOffOnBusLoss": _to_rupees(part_e_loss_row),
            "SpeculativeInc": {
                "BusLossSetoff": _to_rupees(pgbp.part_e_speculative_setoff),
                "IncOfCurYrUnderThatHead": _to_rupees(pgbp.part_e_speculative_income),
                "IncOfCurYrAfterSetOff": _to_rupees(pgbp.part_e_speculative_income_after_setoff),
            },
            "SpecifiedInc": {
                "BusLossSetoff": _to_rupees(pgbp.part_e_specified_setoff),
                "IncOfCurYrUnderThatHead": _to_rupees(pgbp.part_e_specified_income),
                "IncOfCurYrAfterSetOff": _to_rupees(pgbp.part_e_specified_income_after_setoff),
            },
            "TotLossSetOffOnBus": _to_rupees(pgbp.part_e_total_setoff),
            "LossRemainSetOffOnBus": _to_rupees(pgbp.part_e_loss_remaining),
        }
    else:
        _bus_loss_obj = {
            "LossSetOffOnBusLoss": 0,
            "SpeculativeInc": {"BusLossSetoff": 0, "IncOfCurYrUnderThatHead": 0, "IncOfCurYrAfterSetOff": 0},
            "SpecifiedInc": {"BusLossSetoff": 0, "IncOfCurYrUnderThatHead": 0, "IncOfCurYrAfterSetOff": 0},
            "TotLossSetOffOnBus": 0,
            "LossRemainSetOffOnBus": 0,
        }

    _pl_us = {
        "ProfitLossUs44AD": _to_rupees(presumptive_ad), "ProfitLossUs44ADA": _to_rupees(presumptive_ada), "ProfitLossUs44AE": _to_rupees(presumptive_ae),
        "ProfitLossUs44B": 0, "ProfitLossUs44BB": 0, "ProfitLossUs44BBA": 0,
        "ProfitLossUs44BBC": 0, "ProfitLossUs44BBD": 0, "ProfitLossUs44DA": 0,
    }

    _deemed_profit_us = {
        "Section44AD": _to_rupees(presumptive_ad), "Section44ADA": _to_rupees(presumptive_ada), "Section44AE": _to_rupees(presumptive_ae),
        "Section44B": 0, "Section44BB": 0, "Section44BBA": 0, "Section44BBC": 0, "Section44BBD": 0, "Section44DA": 0,
        "TotDeemedProfitBusUs": _to_rupees(presumptive_total),
    }

    _heads_inc = {
        "Salary": _to_rupees(realloc_inc_salary), "HouseProperty": _to_rupees(realloc_inc_hp), "CapitalGains": _to_rupees(realloc_inc_cg),
        "Dividend": _to_rupees(realloc_inc_dividend), "OtherThanDividend": _to_rupees(realloc_inc_other_div), "OtherSources": _to_rupees(realloc_inc_os),
        "115BBH": _to_rupees(realloc_inc_115bbh), "Us115BBF": _to_rupees(realloc_inc_115bbf), "Us115BBG": _to_rupees(realloc_inc_115bbg),
    }

    _heads_exp = {
        "Salary": _to_rupees(realloc_exp_salary), "HouseProperty": _to_rupees(realloc_exp_hp), "CapitalGains": _to_rupees(realloc_exp_cg),
        "OtherSources": _to_rupees(realloc_exp_os), "115BBH": _to_rupees(realloc_exp_115bbh), "Us115BBF": _to_rupees(realloc_exp_115bbf), "Us115BBG": _to_rupees(realloc_exp_115bbg),
    }

    _exempt_credit = {"FirmShareInc": _to_rupees(exempt_firm), "AOPBOISharInc": _to_rupees(exempt_aop), "OthExempInc": _to_rupees(exempt_other), "TotExempIncPL": _to_rupees(exempt_total)}

    _rule_profit = {
        "ProfitFrmActCvrdUndrRule7": _to_rupees(rule7_profit), "ProfitFrmActCvrdUndrRule7A": _to_rupees(rule7a_profit),
        "ProfitFrmActCvrdUndrRule7B1": _to_rupees(rule7b1_profit), "ProfitFrmActCvrdUndrRule7B1A": _to_rupees(rule7b1a_profit),
        "ProfitFrmActCvrdUndrRule8": _to_rupees(rule8_profit),
    }

    return {
        "BusSetoffCurrYr": _bus_loss_obj,
        "BusinessIncOthThanSpec": {
            "ProfBfrTaxPL": _to_rupees(non_spec_pbt),
            "NetPLFromSpecBus": 0,
            "NetPLFromSpecifiedBus": 0,
            "IncRecCredPLOthHeadDtls": _heads_inc,
            "PLUs44sChapXIIG": 0,
            "ProfitLossInclRefrdSec": _pl_us,
            "TotalProfitFrmActCvrd": _to_rupees(rule_7_8_total),
            "ProfitFrmActCvrd": _rule_profit,
            "IncCredPL": _exempt_credit,
            "IncCredPLNotChargable": _to_rupees(not_chargeable), "BalancePLOthThanSpecBus": _to_rupees(row6),
            "ExpDebToPLOthHeadDtls": _heads_exp, "ExpDebToPLExemptInc": _to_rupees(expense_exempt_8a), "ExpDebToPLExemptIncDisAllwUs14A": _to_rupees(expense_exempt_8b),
            "TotExpDebPL": _to_rupees(row9), "AdjustedPLOthThanSpecBus": _to_rupees(row10),
            "DepreciationDebPLCosAct": _to_rupees(books_depr),
            "DepreciationAllowITAct32": {"DepreciationAllowUs32_1_ii": _to_rupees(it_depr), "DepreciationAllowUs32_1_i": 0, "TotDeprAllowITAct": _to_rupees(it_depr)},
            "AdjustPLAfterDeprOthSpecInc": _to_rupees(row13),
            "AmtDebPLDisallowUs36": _to_rupees(row14), "AmtDebPLDisallowUs37": _to_rupees(row15), "AmtDebPLDisallowUs40": _to_rupees(row16),
            "AmtDebPLDisallowUs40A": _to_rupees(row17), "AmtDebPLDisallowUs43B": _to_rupees(row18), "InterestDisAllowUs23SMEAct": _to_rupees(row19),
            "DeemIncUs41": _to_rupees(row20), "DeemIncUs32AD": _to_rupees(amount("deemed_income_us32ad")), "DeemIncUs33AB": _to_rupees(amount("deemed_income_us33ab")),
            "DeemIncUs33ABA": _to_rupees(amount("deemed_income_us33aba")), "DeemIncUs35ABA": _to_rupees(amount("deemed_income_us35aba")), "DeemIncUs35ABB": _to_rupees(amount("deemed_income_us35abb")),
            "DeemIncUs40A3A": _to_rupees(amount("deemed_income_us40a3a")), "DeemIncUs72A": _to_rupees(amount("deemed_income_us72a")), "DeemIncUs80HHD": _to_rupees(amount("deemed_income_us80hhd")),
            # Item 21's own combined total (the form prints 32AD/33AB/33ABA/
            # 35ABA/35ABB/40A(3A)/72A/80HHD/80-IA as ONE single line item,
            # not nine separate rows).
            "DeemIncUs80IA": _to_rupees(amount("deemed_income_us80ia")), "DeemIncUs3380HHD80IA": _to_rupees(row21), "DeemIncUs43CA": _to_rupees(row22), "OthItemDisallowUs28To44DA": _to_rupees(row23),
            "AnyOthIncNotInclInExpDisallowPL": _to_rupees(row24), "AnyOthIncNotInclInSalary": 0, "AnyOthIncNotInclInBonus": 0, "AnyOthIncNotInclInCommission": 0, "AnyOthIncNotInclInInterest": 0, "AnyOthIncNotInclInOthers": 0,
            "IncProfDecLossAccICDSAdj": _to_rupees(row25), "TotAfterAddToPLDeprOthSpecInc": _to_rupees(row13 + total_additions), "DeductUs32_1_iii": _to_rupees(row27), "DebPLUs35ExcessAmt": _to_rupees(row28),
            "AmtDisallUs40NowAllow": _to_rupees(row29), "AmtDisallUs43BNowAllow": _to_rupees(row30), "AnyOthAmtAllDeduct": _to_rupees(row31), "DecProfIncLossAccICDSAdj": _to_rupees(row32), "TotDeductionAmts": _to_rupees(total_deductions),
            "PLAftAdjDedBusOthThanSpec": _to_rupees(row34), "DeemedProfitBusUs": _deemed_profit_us,
            "NetPLAftAdjBusOthThanSpec": _to_rupees(row36), "NetPLBusOthThanSpec7A7B7C": _to_rupees(row_a37),
            "ChrgblIncUndrRule7": _to_rupees(rule7_taxable), "DeemedChrgblIncUndrRule7A": _to_rupees(rule7a_deemed), "DeemedChrgblIncUndrRule7B1": _to_rupees(rule7b1_deemed),
            "DeemedChrgblIncUndrRule7B1A": _to_rupees(rule7b1a_deemed), "DeemedChrgblIncUndrRule8": _to_rupees(rule8_deemed),
            "IncomeOtherThanRule": _to_rupees(row37f), "BalIncDeemedFrmAgri": _to_rupees(row38),
        },
        "IncChrgUnHdProftGain": _to_rupees(total_biz),
        "SpecBusinessInc": {"NetPLFrmSpecBus": _to_rupees(spec_signed), "AdditionUs28to44DA": _to_rupees(amount("speculative_additions")), "DeductUs28to44DA": _to_rupees(amount("speculative_deductions")), "AdjustedPLFrmSpecuBus": _to_rupees(spec_signed)},
        "SpecifiedBusinessInc": {"NetPLFrmSpecifiedBus": _to_rupees(specified_signed), "AddSec28to44DA": _to_rupees(amount("specified_business_additions")), "DedSec28to44DAOTDedSec35AD": _to_rupees(amount("specified_business_deductions")), "DedUs35ADSubSec5Dtls": [], "DeductionUs35AD": 0, "PLFrmSpecifiedBus": _to_rupees(specified_signed), "ProfitLossSpecifiedBusiness": _to_rupees(specified_signed)},
    }


# ============================================================================
# PARTA_BS — Balance Sheet (REQUIRED)
# ============================================================================

def _parta_bs(typed_input: ITR3Input | None = None) -> dict:
    """Build PARTA_BS from explicit typed official field groups.

    Every FundSrc/FundApply sub-block the official schema marks `required`
    (nearly all of them, each with its own `default: 0`) must always be
    present -- unlike a genuinely optional disclosure field, an absent
    required block here is a schema-validation failure, not a legitimate
    omission. `draft_to_itr3_input._balance_sheet()` is the single place
    that guarantees `typed_input.balance_sheet.official` is always
    populated (both its workspace and legacy-fallback paths build a
    complete `BSOfficial`); this function trusts that and fails closed if
    a caller ever bypasses it.
    """
    if typed_input is None or typed_input.balance_sheet is None:
        raise ValueError("ITR3Input.balance_sheet is required for PARTA_BS generation")
    source = typed_input.balance_sheet
    if source.official is None:
        raise ValueError(
            "ITR3Input.balance_sheet.official is required for PARTA_BS generation -- "
            "draft_to_itr3_input._balance_sheet() must always populate it."
        )
    official = source.official.model_dump(by_alias=True, exclude_none=True)
    secured_total = official["SecrLoan"]["TotSecrLoan"]
    unsecured_total = official["UnsecrLoan"]["TotUnSecrLoan"]
    fund_src = {
        "PropFund": official.pop("PropFund"),
        "LoanFunds": {
            "SecrLoan": official.pop("SecrLoan"),
            "UnsecrLoan": official.pop("UnsecrLoan"),
            # Schema-required, no typed source field of its own (it's a
            # pure derived sum of the two totals above) -- previously
            # always hardcoded to 0 via a dict.pop() default that could
            # never actually find a "TotLoanFund" key.
            "TotLoanFund": secured_total + unsecured_total,
        },
        "DeferredTax": official.pop("DeferredTax"),
        "Advances": official.pop("Advances"),
        "TotFundSrc": official.pop("TotFundSrc"),
    }
    fund_apply: dict[str, Any] = {
        "FixedAsset": official.pop("FixedAsset"),
        "Investments": official.pop("Investments"),
        "CurrAssetLoanAdv": {
            "CurrAsset": official.pop("CurrAsset"),
            "LoanAdv": official.pop("LoanAdv"),
            "CurrLiabilitiesProv": {
                "CurrLiabilities": official.pop("CurrLiabilities"),
                "Provisions": official.pop("Provisions"),
                "TotCurrLiabilitiesProvision": source.current_liabilities,
            },
            "TotCurrAssetLoanAdv": source.current_assets,
            "NetCurrAsset": official.pop("NetCurrAsset"),
        },
        "MiscAdjust": official.pop("MiscAdjust"),
        "TotFundApply": source.total_assets,
    }
    result = {"FundSrc": fund_src, "FundApply": fund_apply}
    no_books = official.pop("NoBooksOfAccBS", None)
    if no_books:
        result["NoBooksOfAccBS"] = no_books
    return _official_integer_tree(result)
# ============================================================================
# PARTA_PL — Profit & Loss (REQUIRED)
# ============================================================================

def _parta_pl(typed_input: ITR3Input | None = None) -> dict:
    """Build schema-complete PARTA_PL, preserving every sourced disclosure."""
    pl = typed_input.profit_and_loss if typed_input is not None else None
    if pl is None:
        return _parta_pl_defaults()
    result = _official_integer_tree(pl.part_a.model_dump(by_alias=True, exclude_none=True))
    result["GrossProfit"] = _to_rupees(pl.gross_profit)
    result["Expenditure"] = _to_rupees(pl.expenditure)
    result["NetIncomeFrmSpecActivity"] = _to_rupees(pl.net_income_from_special_activity)
    result["TurnverFrmSpecActivity"] = _to_rupees(pl.turnover_from_special_activity)
    return _parta_pl_defaults(result)


def _parta_pl_defaults(existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fill mandatory PARTA_PL blocks without overwriting supplied disclosures."""
    result = dict(existing or {})
    result.setdefault("CreditsToPL", {"OthIncome": {}, "TotCreditsToPL": 0})
    result.setdefault("DebitsToPL", {})
    result.setdefault("TaxProvAppr", {})
    result.setdefault("NoBooksOfAccPL", {})
    credits = result["CreditsToPL"]; debits = result["DebitsToPL"]
    credits.setdefault("OthIncome", {})
    other = credits["OthIncome"]
    for key in ("RentInc","Comissions","Dividends","InterestInc","ProfitOnSaleFixedAsset","ProfitOnInvChrSTT","ProfitOnOthInv","ProfitOnCurrFluct","ProfitOnCnvInvntryToCapAsst","ProfitOnAgriIncome","MiscOthIncome","TotOthIncome"):
        other.setdefault(key, 0)
    credits.setdefault("TotCreditsToPL", 0)
    for key in ("GrossProfitTrnsfFrmTrdAcc",): credits.setdefault(key, 0)
    employee = debits.setdefault("EmployeeComp", {}); insurance = debits.setdefault("Insurances", {})
    for key in ("SalsWages","Bonus","MedExpReimb","LeaveEncash","LeaveTravelBenft","ContToSuperAnnFund","ContToPF","ContToGratFund","ContToOthFund","OthEmpBenftExpdr","TotEmployeeComp"): employee.setdefault(key, 0)
    for key in ("MedInsur","LifeInsur","KeyManInsur","OthInsur","TotInsurances"): insurance.setdefault(key, 0)
    for key in ("CommissionExpdrDtls","RoyalityDtls","ProfessionalConstDtls","InterestExpdrtDtls"):
        block = debits.setdefault(key, {})
        for child in ("NonResOtherCompany","Others","Total") if key != "InterestExpdrtDtls" else ("NonResOtherCompany","Others","InterestExpdr"):
            block.setdefault(child, 0)
    for key in ("RatesTaxesPays",): debits.setdefault(key, {"ExciseCustomsVAT": {}}); debits[key].setdefault("ExciseCustomsVAT", {})
    for key in ("Freight","ConsumptionOfStores","PowerFuel","RentExpdr","RepairsBldg","RepairMach","StaffWelfareExp","Entertainment","Hospitality","Conference","SalePromoExp","Advertisement","HotelBoardLodge","TravelExp","ForeignTravelExp","ConveyanceExp","TelephoneExp","GuestHouseExp","ClubExp","FestivalCelebExp","Scholarship","Gift","Donation","AuditFee","OtherExpenses","ProvForBadDoubtDebt","OthProvisionsExpdr","PBIDTA","DepreciationAmort","PBT"): debits.setdefault(key, 0)
    no_books = result["NoBooksOfAccPL"]
    for key in ("GrossReceipt","GrsRcptAccPayeeOrBankMode","GrsRcptOtherMode","GrossProfit","Expenses","NetProfit","GrossReceiptPrf","GrsRcptAccPayeeOrBankModePrf","GrsRcptOtherModePrf","GrossProfitPrf","ExpensesPrf","NetProfitPrf","TotBusinessProfession"): no_books.setdefault(key, 0)
    tax = result["TaxProvAppr"]
    for key in ("ProvForCurrTax","ProvDefTax","ProfitAfterTax","BalBFPrevYr","AmtAvlAppr","TrfToReserves","ProprietorAccBalTrf"): tax.setdefault(key, 0)
    return _official_integer_tree(result)


def _manufacturing_account(typed_input: ITR3Input | None = None) -> dict:
    """Build the official ManufacturingAccount schedule from typed fields.

    Returns {} (not a zero-filled stub) when the taxpayer has no manufacturing
    data at all -- the caller omits the whole optional schedule in that case.
    """
    account = typed_input.business_accounts.manufacturing_account if typed_input and typed_input.business_accounts else None
    if account is None:
        return {}
    opening, closing = account.opening_inventory, account.closing_stock
    return {
        "OpeningInventory": {
            "OpngStckRawMat": _to_rupees(opening.OpngStckRawMat),
            "OpngStckWrkinPrgrs": _to_rupees(opening.OpngStckWrkinPrgrs),
            "OpngInvntryTotal": _to_rupees(opening.OpngInvntryTotal),
            "Purchases": _to_rupees(opening.Purchases),
            "DirectWages": _to_rupees(opening.DirectWages),
            "DirectExpenses": _to_rupees(opening.DirectExpenses),
            "CarriageInward": _to_rupees(opening.CarriageInward),
            "PowerAndFuel": _to_rupees(opening.PowerAndFuel),
            "OthDirectExpenses": _to_rupees(opening.OthDirectExpenses),
            "IndirectWages": _to_rupees(opening.IndirectWages),
            "FactoryRentAndRates": _to_rupees(opening.FactoryRentAndRates),
            "FactoryInsurance": _to_rupees(opening.FactoryInsurance),
            "FactoryFuelAndPower": _to_rupees(opening.FactoryFuelAndPower),
            "FactoryGeneralExpenses": _to_rupees(opening.FactoryGeneralExpenses),
            "DeprctnOfFactoryMachinery": _to_rupees(opening.DeprctnOfFactoryMachinery),
            "TotalFactoryOverheads": _to_rupees(opening.TotalFactoryOverheads),
            "TotalDebtsManfctrngAcc": _to_rupees(opening.TotalDebtsManfctrngAcc),
        },
        "ClosingStock": {
            "ClsngStckRawMaterial": _to_rupees(closing.ClsngStckRawMaterial),
            "ClsngStckWrkInPrgrs": _to_rupees(closing.ClsngStckWrkInPrgrs),
            "ClsngStckTotal": _to_rupees(closing.ClsngStckTotal),
        },
        "CostOfGoodsPrdcd": _to_rupees(account.cost_of_goods_produced),
    }


def _trading_account(typed_input: ITR3Input | None = None) -> dict:
    """Build the official TradingAccount schedule from typed values.

    Returns {} (not a zero-filled stub) when the taxpayer has no trading
    data at all -- the caller omits the whole optional schedule in that case.
    """
    account = typed_input.business_accounts.trading_account if typed_input and typed_input.business_accounts else None
    if account is None:
        return {}
    excise = account.ExciseCustomsVAT
    duty_excise = account.DutyTaxPay.ExciseCustomsVAT
    return {
        "SaleOfGoods": _to_rupees(account.SaleOfGoods), "SaleOfServices": _to_rupees(account.SaleOfServices),
        "OtherOperatingRevenueDtls": [
            {"OperatingRevenueName": row.OperatingRevenueName, "OperatingRevenueAmt": _to_rupees(row.OperatingRevenueAmt)}
            for row in account.OtherOperatingRevenueDtls
        ],
        "OperatingRevenueTotal": _to_rupees(account.OperatingRevenueTotal),
        "SalesGrossReceiptsTotal": _to_rupees(account.SalesGrossReceiptsTotal), "GrossRcptFromProfession": _to_rupees(account.GrossRcptFromProfession),
        "ExciseCustomsVAT": {
            "UnionExciseDuty": _to_rupees(excise.UnionExciseDuty), "ServiceTax": _to_rupees(excise.ServiceTax),
            "VATorSaleTax": _to_rupees(excise.VATorSaleTax), "CentralGoodServiceTax": _to_rupees(excise.CentralGoodServiceTax),
            "StateGoodServiceTax": _to_rupees(excise.StateGoodServiceTax), "IntegratedGoodServiceTax": _to_rupees(excise.IntegratedGoodServiceTax),
            "UnionTerrGoodServiceTax": _to_rupees(excise.UnionTerrGoodServiceTax), "OthDutyTaxCess": _to_rupees(excise.OthDutyTaxCess),
            "TotExciseCustomsVAT": _to_rupees(excise.TotExciseCustomsVAT),
        },
        "TotRevenueFrmOperations": _to_rupees(account.TotRevenueFrmOperations), "ClsngStckOfFinishedStcks": _to_rupees(account.ClsngStckOfFinishedStcks),
        "TardingAccTotCred": _to_rupees(account.TardingAccTotCred), "OpngStckOfFinishedStcks": _to_rupees(account.OpngStckOfFinishedStcks),
        "Purchases": _to_rupees(account.Purchases), "DirectExpenses": _to_rupees(account.DirectExpenses), "CarriageInward": _to_rupees(account.CarriageInward),
        "PowerAndFuel": _to_rupees(account.PowerAndFuel),
        "OtherIncDtls": [
            {"NatureOfIncome": row.NatureOfIncome, "Amount": _to_rupees(row.Amount)}
            for row in account.OtherIncDtls
        ],
        "DirectExpensesTotal": _to_rupees(account.DirectExpensesTotal),
        "DutyTaxPay": {"ExciseCustomsVAT": {
            "CustomDuty": _to_rupees(duty_excise.CustomDuty), "CounterVailDuty": _to_rupees(duty_excise.CounterVailDuty),
            "SplAddDuty": _to_rupees(duty_excise.SplAddDuty), "UnionExciseDuty": _to_rupees(duty_excise.UnionExciseDuty),
            "ServiceTax": _to_rupees(duty_excise.ServiceTax), "VATorSaleTax": _to_rupees(duty_excise.VATorSaleTax),
            "CentralGoodServiceTax": _to_rupees(duty_excise.CentralGoodServiceTax), "StateGoodServiceTax": _to_rupees(duty_excise.StateGoodServiceTax),
            "IntegratedGoodServiceTax": _to_rupees(duty_excise.IntegratedGoodServiceTax), "UnionTerrGoodServiceTax": _to_rupees(duty_excise.UnionTerrGoodServiceTax),
            "OthDutyTaxCess": _to_rupees(duty_excise.OthDutyTaxCess), "TotExciseCustomsVAT": _to_rupees(duty_excise.TotExciseCustomsVAT),
        }},
        "GoodsCostPrdcdFrmMA": _to_rupees(account.GoodsCostPrdcdFrmMA), "GrossProfitFrmBusProf": _to_rupees(account.GrossProfitFrmBusProf),
        "TurnoverIntradayTrd": _to_rupees(account.TurnoverIntradayTrd), "IncomeIntradayTrd": _to_rupees(account.IncomeIntradayTrd),
        "TurnoverFutureTrd": _to_rupees(account.TurnoverFutureTrd), "IncomeFutureTrd": _to_rupees(account.IncomeFutureTrd),
    }


def _official_integer_tree(value: Any) -> Any:
    """Convert typed Decimal schedule values to official integer/number JSON values."""
    if isinstance(value, Decimal):
        return _to_rupees(value)
    if isinstance(value, dict):
        return {key: _official_integer_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_official_integer_tree(item) for item in value]
    return value


def _parta_oi(typed_input: ITR3Input | None = None) -> dict:
    """Build PARTA_OI from its typed canonical model, preserving explicit fields."""
    if typed_input is None or typed_input.parta_oi is None:
        return {}
    return _official_integer_tree(typed_input.parta_oi.model_dump(by_alias=True, exclude_none=True))


def _parta_qd(typed_input: ITR3Input | None = None) -> dict:
    """Build PARTA_QD with the official TradingConcern/ManfactrConcern nesting.

    The official schema requires both RawMaterial and FinishrByProd whenever
    ManfactrConcern is present at all -- there is no such thing as a
    manufacturing concern disclosure with only raw-material or only
    finished-product rows. Fail closed rather than silently drop the
    taxpayer's real data or omit the whole (mandatory-if-44AB) schedule.
    """
    if typed_input is None or typed_input.parta_qd is None:
        return {}
    source = typed_input.parta_qd
    result: dict[str, Any] = {}
    if source.TradingConcern:
        result["TradingConcern"] = {"QuantitDet": _official_integer_tree([r.model_dump(exclude_none=True) for r in source.TradingConcern])}
    if bool(source.RawMaterial) != bool(source.FinishrByProd):
        missing = "FinishrByProd" if source.RawMaterial else "RawMaterial"
        raise ValueError(
            f"PARTA_QD ManfactrConcern requires both RawMaterial and FinishrByProd rows when either is present; {missing} is missing."
        )
    if source.RawMaterial and source.FinishrByProd:
        result["ManfactrConcern"] = {
            "RawMaterial": {"QuantitDet": _official_integer_tree([r.model_dump(exclude_none=True) for r in source.RawMaterial])},
            "FinishrByProd": {"QuantitDet": _official_integer_tree([r.model_dump(exclude_none=True) for r in source.FinishrByProd])},
        }
    return result


# ============================================================================
# Other PGBP schedules (optional / conditional)
# ============================================================================

def _schedule_dep(typed_input: ITR3Input | None = None) -> dict:
    """Build ScheduleDEP from its typed canonical source; omit absent optional blocks."""
    source = typed_input.depreciation_schedules.schedule_dep if typed_input and typed_input.depreciation_schedules else None
    if source is None:
        return {}
    return _official_integer_tree(source.model_dump(by_alias=True, exclude_none=True))


def _schedule_dpm(typed_input: ITR3Input | None = None) -> dict:
    """Build ScheduleDPM from its typed canonical source."""
    source = typed_input.depreciation_schedules.schedule_dpm if typed_input and typed_input.depreciation_schedules else None
    return _official_integer_tree(source.model_dump(by_alias=True, exclude_none=True)) if source else {}


def _schedule_doa(typed_input: ITR3Input | None = None) -> dict:
    """Build ScheduleDOA from its typed canonical source."""
    source = typed_input.depreciation_schedules.schedule_doa if typed_input and typed_input.depreciation_schedules else None
    return _official_integer_tree(source.model_dump(by_alias=True, exclude_none=True)) if source else {}


def _schedule_dcg(typed_input: ITR3Input | None = None) -> dict:
    """Build ScheduleDCG from its typed canonical source."""
    source = typed_input.depreciation_schedules.schedule_dcg if typed_input and typed_input.depreciation_schedules else None
    return _official_integer_tree(source.model_dump(by_alias=True, exclude_none=True)) if source else {}


def _schedule_if(result: ITR3Result, typed_input: ITR3Input | None = None) -> dict | None:
    """Build Schedule IF only from explicit typed partner-firm rows."""
    del result
    if typed_input is None or not typed_input.partner_firm_details:
        return None
    source = typed_input.partner_firm_details
    rows = [{
        "FirmName": row.firm_name,
        "FirmPAN": row.firm_pan,
        "IsLiableToAudit": "Y" if row.is_liable_to_audit else "N",
        "Sec92EFirmFlag": "Y" if row.sec92e_firm else "N",
            "ProfitSharePercent": float(row.profit_share_percent),
        "ProfitShareAmt": _to_rupees(row.profit_share_amount),
        "IntrstAmtDueOrRecv": _to_rupees(row.interest_amount),
        "RemunernAmtDueOrRecv": _to_rupees(row.remuneration_amount),
        "FirmCapBalOn31Mar": _to_rupees(row.capital_balance),
    } for row in source]
    return {"PartnerFirmDetails": rows,
            "TotalProfitShareAmt": _to_rupees(sum((r.profit_share_amount for r in source), Decimal("0"))),
            "TotalIntrstAmtDueOrRecv": _to_rupees(sum((r.interest_amount for r in source), Decimal("0"))),
            "TotalRemunernAmtDueOrRecv": _to_rupees(sum((r.remuneration_amount for r in source), Decimal("0"))),
            "TotalFirmCapBalOn31Mar": _to_rupees(sum((r.capital_balance for r in source), Decimal("0")))}


def _schedule_spi(typed_input: ITR3Input | None) -> dict[str, Any] | None:
    """Build Schedule SPI from explicit typed clubbing rows."""
    if typed_input is None or not typed_input.spi_entries:
        return None
    rows = []
    for item in typed_input.spi_entries:
        row = {"SpecifiedPersonName": item.specified_person_name, "ReltnShip": item.relationship,
               "AmtIncluded": _to_rupees(item.amount_included),
               "HeadIncIncluded": "SA" if item.head_of_income == "SAL" else item.head_of_income}
        if item.pan:
            row["PANofSpecPerson"] = item.pan
        rows.append(row)
    return {"SpecifiedPerson": rows}


def _schedule_pti(typed_input: ITR3Input | None) -> dict[str, Any] | None:
    """Build Schedule PTI from explicit typed pass-through rows."""
    if typed_input is None or not typed_input.pti_entries:
        return None
    zero = Decimal("0")
    def regular(amount: Decimal = zero, tds: Decimal = zero) -> dict[str, int]:
        return {"AmountOfInc": _to_rupees(max(zero, amount)), "CurrYrLossShareByInvstFund": _to_rupees(max(zero, -amount)), "NetIncomeLoss": _to_rupees(amount), "TDSAmount": _to_rupees(tds)}
    def other(amount: Decimal = zero, tds: Decimal = zero) -> dict[str, int]:
        return {"AmountOfInc": _to_rupees(amount), "NetIncomeLoss": _to_rupees(amount), "TDSAmount": _to_rupees(tds)}
    rows = []
    for item in typed_input.pti_entries:
        hp = item.income_amount if item.income_head == "HP" else zero
        stcg = item.income_amount if item.income_head == "STCG" else zero
        ltcg = item.income_amount if item.income_head == "LTCG" else zero
        os = item.income_amount if item.income_head == "OS" else zero
        stcg_111a = stcg if item.section == "111A" else zero
        ltcg_112a = ltcg if "112A" in item.section.upper() else zero
        exempt = item.exempt_income_23fbb
        rows.append({"InvstmntCvrdUs115UA115UB": "A" if item.section == "115UA" else "B" if item.section == "115UB" else "C", "BusinessName": item.entity_name, "BusinessPAN": item.entity_pan,
            "IncFromHP": regular(hp), "CapitalGainsPTI": {"ShortTermCG": regular(stcg), "STCG_Sec111A": regular(stcg_111a), "STCG_Others": regular(stcg - stcg_111a), "LongTermCG": regular(ltcg), "LTCG_Sec112A": regular(ltcg_112a), "LTCG_Others": regular(ltcg - ltcg_112a)}, "IncClmdPTI": {"TotalSec23FBB": other(exempt), "Sec23FBB": other(exempt)}, "IncOthSrc": other(os, item.tds_credit), "OS_Dividend": other(), "OS_Others": other(os, item.tds_credit)})
    return {"SchedulePTIDtls": rows}


def _schedule_ud(typed_input: ITR3Input | None = None) -> dict[str, Any] | None:
    """Build Schedule UD from explicitly prepared unabsorbed-depreciation rows.

    ``UDEntry`` stores the two statutory ledgers separately: unabsorbed
    allowance (the older section 32(2) allowance ledger) and unabsorbed
    depreciation.  The official row names are intentionally not inferred from
    the Python names; each value is mapped to its corresponding CBDT field and
    all schedule totals are recomputed from the serialized rows.
    """
    if typed_input is None or not typed_input.ud_entries:
        return None

    rows: list[dict[str, Any]] = []
    for entry in typed_input.ud_entries:
        allowance_bf = entry.bf_unabsorbed_allowance
        depreciation_bf = entry.bf_unabsorbed_depreciation
        allowance_setoff = entry.allowance_setoff_cy
        depreciation_setoff = entry.depreciation_setoff_cy
        row: dict[str, Any] = {
            "AssYr": entry.assessment_year,
            "AmtBFUD": _to_rupees(depreciation_bf),
            "AmtDeprSOCY": _to_rupees(depreciation_setoff),
            "BalCFNY": _to_rupees(max(Decimal("0"), depreciation_bf - depreciation_setoff)),
            "AmtBFUAllow": _to_rupees(allowance_bf),
            "AmtAllowSOCY": _to_rupees(allowance_setoff),
            "AllowBalCFNY": _to_rupees(max(Decimal("0"), allowance_bf - allowance_setoff)),
        }
        rows.append(row)

    total_bf_allowance = sum(
        (entry.bf_unabsorbed_allowance for entry in typed_input.ud_entries), Decimal("0")
    )
    total_bf_depreciation = sum(
        (entry.bf_unabsorbed_depreciation for entry in typed_input.ud_entries), Decimal("0")
    )
    total_allowance_setoff = sum(
        (entry.allowance_setoff_cy for entry in typed_input.ud_entries), Decimal("0")
    )
    total_depreciation_setoff = sum(
        (entry.depreciation_setoff_cy for entry in typed_input.ud_entries), Decimal("0")
    )
    allowance_balance = max(Decimal("0"), total_bf_allowance - total_allowance_setoff)
    depreciation_balance = max(Decimal("0"), total_bf_depreciation - total_depreciation_setoff)

    return {
        # AY 2026-27 is the only AY accepted by the loaded official schema;
        # row AYs remain taxpayer-provided and are never synthesized.
        "CurrAssYr": "2026-27",
        "CurBalCFNY": _to_rupees(depreciation_balance),
        "CurAllowBalCFNY": _to_rupees(allowance_balance),
        "ScheduleUD": rows,
        "TotBFUDepritAmt": _to_rupees(total_bf_depreciation),
        "TotCurYrdepritSetoffInc": _to_rupees(total_depreciation_setoff),
        "TotDepritBalCFNY": _to_rupees(depreciation_balance),
        "TotBFUAllowAmt": _to_rupees(total_bf_allowance),
        "TotCurYrAllowSetoffInc": _to_rupees(total_allowance_setoff),
        "TotalBalCFNY": _to_rupees(allowance_balance + depreciation_balance),
    }







def _serialize_schedule_model(model: Any) -> dict:
    """Convert a prepared typed schedule to schema-bound integer JSON."""
    def convert(value: Any) -> Any:
        if isinstance(value, Decimal):
            return _to_rupees(value)
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        if isinstance(value, list):
            return [convert(item) for item in value]
        return value

    return convert(model.model_dump())


def _schedule_gst(typed_input: ITR3Input | None) -> dict | None:
    """Serialize prepared Schedule GST, omitting it when not prepared."""
    if typed_input is None or typed_input.schedule_gst is None:
        return None
    return _serialize_schedule_model(typed_input.schedule_gst)


def _schedule_icds(typed_input: ITR3Input | None) -> dict | None:
    """Serialize prepared Schedule ICDS, omitting it when not prepared."""
    if typed_input is None or typed_input.schedule_icds is None:
        return None
    return _serialize_schedule_model(typed_input.schedule_icds)


def _schedule_esr(typed_input: ITR3Input | None) -> dict | None:
    """Serialize prepared Schedule ESR, omitting it when not prepared."""
    if typed_input is None or typed_input.schedule_esr is None:
        return None
    return _serialize_schedule_model(typed_input.schedule_esr)


def _schedule_tpsa(typed_input: ITR3Input | None) -> dict | None:
    """Serialize prepared Schedule TPSA, omitting it when not prepared."""
    if typed_input is None or typed_input.schedule_tpsa is None:
        return None
    return _serialize_schedule_model(typed_input.schedule_tpsa)


# ============================================================================
# Shared schedules (identical to ITR-2 patterns)
# ============================================================================

def _inc_cyla(inc_of_cur_yr: Decimal, hp_setoff: Decimal, os_setoff: Decimal, inc_after: Decimal) -> dict:
    return {"IncOfCurYrUnderThatHead": _to_rupees(inc_of_cur_yr),
            "HPlossCurYrSetoff": _to_rupees(hp_setoff),
            "OthSrcLossNoRaceHorseSetoff": _to_rupees(os_setoff),
            "IncOfCurYrAfterSetOff": _to_rupees(inc_after)}


def _inc_cyla_os(inc_of_cur_yr: Decimal, hp_setoff: Decimal, inc_after: Decimal) -> dict:
    return {"IncOfCurYrUnderThatHead": _to_rupees(inc_of_cur_yr),
            "HPlossCurYrSetoff": _to_rupees(hp_setoff),
            "IncOfCurYrAfterSetOff": _to_rupees(inc_after)}


def _inc_bfla(inc_from_cyla: Decimal, bf_setoff: Decimal, inc_after: Decimal) -> dict:
    return {"IncOfCurYrUndHeadFromCYLA": _to_rupees(inc_from_cyla),
            "BFlossPrevYrUndSameHeadSetoff": _to_rupees(bf_setoff),
            "BFUnabsorbedDeprSetoff": 0,
            "BFAllUs35Cl4Setoff": 0,
            "IncOfCurYrAfterSetOffBFLosses": _to_rupees(inc_after)}


def _inc_bfla_no_bf(inc_from_cyla: Decimal, inc_after: Decimal) -> dict:
    """BFLA helper for heads that need BFUnabsorbedDeprSetoff/BFAllUs35Cl4Setoff but no BFLossPrevYr."""
    return {"IncOfCurYrUndHeadFromCYLA": _to_rupees(inc_from_cyla),
            "BFUnabsorbedDeprSetoff": 0,
            "BFAllUs35Cl4Setoff": 0,
            "IncOfCurYrAfterSetOffBFLosses": _to_rupees(inc_after)}


def _inc_bfla_sal(inc_from_cyla: Decimal, inc_after: Decimal) -> dict:
    return {"IncOfCurYrUndHeadFromCYLA": _to_rupees(inc_from_cyla),
            "IncOfCurYrAfterSetOffBFLosses": _to_rupees(inc_after)}


def _schedule_cyla(result: ITR3Result) -> dict[str, Any]:
    """Build the official Schedule CYLA from the calculator's typed result."""
    z = _ZERO
    cyla = result.schedules.get("cyla")
    if cyla is None:
        raise ValueError("Schedule CYLA requires a computed CYLA result")

    def positive(value: Any) -> Decimal:
        return max(z, Decimal(str(value)))

    def cg_income(name: str) -> Decimal:
        return positive(getattr(cyla, f"{name}_remaining", z))

    def cg_source(name: str) -> Decimal:
        values = getattr(cyla, "cg_intra_head_remaining", {}) or {}
        return positive(values.get(name, z))

    def row(income: Decimal, after: Decimal, *, hp: Decimal = z, business: Decimal = z,
            other: Decimal = z) -> dict[str, int]:
        return {
            "IncOfCurYrUnderThatHead": _to_rupees(income),
            "HPlossCurYrSetoff": _to_rupees(hp),
            "BusLossSetoff": _to_rupees(business),
            "OthSrcLossNoRaceHorseSetoff": _to_rupees(other),
            "IncOfCurYrAfterSetOff": _to_rupees(after),
        }

    hp_income = positive(result.house_property_income)
    hp_loss = positive(-result.house_property_income)
    salary = positive(result.salary_income)
    business_income = positive(result.business_income)
    os_income = positive(result.other_sources_income)
    # The calculator's CYLA result records the exact allocation by source.
    # No unsupported decomposition is inferred when the calculator has not
    # recorded one; zero is therefore used only for an actual absent bucket.
    hp_setoff = positive(getattr(cyla, "hp_setoff", z))
    business_setoff = positive(getattr(cyla, "non_spec_biz_setoff", z))
    other_setoff = positive(getattr(cyla, "os_loss_setoff_total", z))
    stcg20 = cg_source("stcg20")
    stcg30 = cg_source("stcg30")
    stcg_app = cg_source("stcg_app")
    stcg_dtaa = cg_source("stcg_dtaa")
    ltcg125 = cg_source("ltcg125")
    ltcg_dtaa = cg_source("ltcg_dtaa")
    return {
        "Salary": {"IncCYLA": row(salary, salary)},
        "HP": {"IncCYLA": row(hp_income, max(z, hp_income - hp_setoff), hp=hp_setoff)},
        "BusProfExclSpecProf": {"IncCYLA": row(business_income, max(z, business_income - business_setoff), business=business_setoff)},
        "SpeculativeInc": {"IncCYLA": row(positive(getattr(cyla, "spec_biz_income", z)), positive(getattr(cyla, "spec_biz_income", z)))},
        "SpecifiedInc": {"IncCYLA": row(z, z)},
        "STCG20Per": {"IncCYLA": row(stcg20, positive(getattr(cyla, "stcg20_remaining", z)))},
        "STCG30Per": {"IncCYLA": row(stcg30, positive(getattr(cyla, "stcg30_remaining", z)))},
        "STCGAppRate": {"IncCYLA": row(stcg_app, positive(getattr(cyla, "stcg_app_remaining", z)))},
        "STCGDTAARate": {"IncCYLA": row(stcg_dtaa, positive(getattr(cyla, "stcg_dtaa_remaining", z)))},
        "LTCG12_5Per": {"IncCYLA": row(ltcg125, positive(getattr(cyla, "ltcg125_remaining", z)))},
        "LTCGDTAARate": {"IncCYLA": row(ltcg_dtaa, positive(getattr(cyla, "ltcg_dtaa_remaining", z)))},
        "OthSrcExclRaceHorse": {"IncCYLA": row(os_income, max(z, os_income - other_setoff), other=other_setoff)},
        "OthSrcRaceHorse": {"IncCYLA": row(positive(getattr(cyla, "racehorse_remaining", z)) + positive(getattr(cyla, "racehorse_setoff", z)), positive(getattr(cyla, "racehorse_remaining", z)))},
        "IncOSDTAA": {"IncCYLA": row(z, z)},
        "TotalCurYr": {"TotHPlossCurYr": _to_rupees(hp_loss), "TotBusLoss": _to_rupees(sum((e.loss_amount for e in getattr(cyla, "entries", []) if e.head == "BUS"), z)), "TotOthSrcLossNoRaceHorse": _to_rupees(getattr(cyla, "os_loss_total", z))},
        "TotalLossSetOff": {"TotHPlossCurYrSetoff": _to_rupees(hp_setoff), "TotBusLossSetoff": _to_rupees(business_setoff + positive(getattr(cyla, "spec_biz_setoff", z))), "TotOthSrcLossNoRaceHorseSetoff": _to_rupees(other_setoff)},
        "LossRemAftSetOff": {"BalHPlossCurYrAftSetoff": _to_rupees(max(z, hp_loss - hp_setoff)), "BalBusLossAftSetoff": _to_rupees(getattr(cyla, "total_loss_remaining", z)), "BalOthSrcLossNoRaceHorseAftSetoff": _to_rupees(getattr(cyla, "os_loss_remaining", z))},
    }


def _schedule_bfla(result: ITR3Result) -> dict[str, Any]:
    """Build Schedule BFLA from typed CYLA/BFLA calculator baskets."""
    z = _ZERO
    bfla = result.schedules.get("bfla")
    cyla = result.schedules.get("cyla")
    if bfla is None or cyla is None:
        raise ValueError("Schedule BFLA requires computed CYLA and BFLA results")

    def value(obj: Any, name: str) -> Decimal:
        return max(z, Decimal(str(getattr(obj, name, z))))

    def item(cyla_value: Decimal, after: Decimal, setoff: Decimal = z) -> dict[str, int]:
        return {"IncOfCurYrUndHeadFromCYLA": _to_rupees(cyla_value), "BFlossPrevYrUndSameHeadSetoff": _to_rupees(setoff), "BFUnabsorbedDeprSetoff": 0, "BFAllUs35Cl4Setoff": 0, "IncOfCurYrAfterSetOffBFLosses": _to_rupees(after)}

    def cg(name: str) -> dict[str, int]:
        before = value(cyla, f"{name}_remaining")
        after = value(bfla, f"{name}_remaining")
        return {"IncBFLA": item(before, after, max(z, before - after))}

    salary = max(z, result.salary_income)
    hp = max(z, result.house_property_income)
    hp_after = value(bfla, "hp_income_remaining") if hasattr(bfla, "hp_income_remaining") else max(z, hp - value(bfla, "hp_setoff"))
    return {
        "Salary": {"IncBFLA": item(salary, salary)},
        "HP": {"IncBFLA": item(hp, hp_after, value(bfla, "hp_setoff"))},
        "BusProfExclSpecProf": {"IncBFLA": item(value(cyla, "stcg20_remaining") * z, value(bfla, "biz_setoff") * z)},
        "SpeculativeInc": {"IncBFLA": item(z, z)}, "SpecifiedInc": {"IncBFLA": item(z, z)},
        "STCG20Per": cg("stcg20"), "STCG30Per": cg("stcg30"), "STCGAppRate": cg("stcg_app"), "STCGDTAARate": cg("stcg_dtaa"),
        "LTCG12_5Per": cg("ltcg125"), "LTCGDTAARate": cg("ltcg_dtaa"),
        "OthSrcExclRaceHorse": {"IncBFLA": item(max(z, result.other_sources_income), max(z, result.other_sources_income))},
        "OthSrcRaceHorse": {"IncBFLA": item(value(cyla, "racehorse_remaining"), value(bfla, "racehorse_remaining"), value(bfla, "racehorse_setoff"))},
        "IncOSDTAA": {"IncBFLA": item(z, z)},
        "IncomeOfCurrYrAftCYLABFLA": _to_rupees(sum((salary, hp_after, *(value(bfla, n) for n in ("stcg20_remaining", "stcg30_remaining", "stcg_app_remaining", "stcg_dtaa_remaining", "ltcg125_remaining", "ltcg_dtaa_remaining"))), z)),
        "TotalBFLossSetOff": {"TotBFLossSetoff": _to_rupees(result.bfla_total_set_off), "TotUnabsorbedDeprSetoff": 0, "TotAllUs35cl4Setoff": 0},
    }


def _schedule_cfl(result: ITR3Result, typed_input: ITR3Input | None = None) -> dict[str, Any]:
    """Build official year-bucketed Schedule CFL from BFLA and current losses."""
    z = _ZERO
    entries = list((result.schedules.get("cfl") or []))
    bfla_entries = list(getattr(result.schedules.get("bfla"), "entries", []) or [])
    rows: list[dict[str, Any]] = [{"assessment_year": str(e.assessment_year), "head": str(getattr(e, "head", "")), "loss": Decimal(str(getattr(e, "remaining_carry_forward", 0)))} for e in bfla_entries if getattr(e, "remaining_carry_forward", z) > z]
    rows += [{"assessment_year": "2026-27", "head": str(e.get("head", "")), "loss": Decimal(str(e.get("loss_cf", 0)))} for e in entries if Decimal(str(e.get("loss_cf", 0))) > z]
    def summary(items: list[dict[str, Any]]) -> dict[str, int]:
        return {"TotalHPPTILossCF": _to_rupees(sum((x["loss"] for x in items if x["head"] in ("HP", "HouseProperty")), z)), "BusLossOthThanSpecLossCF": _to_rupees(sum((x["loss"] for x in items if x["head"] in ("BUS", "NonSpeculative")), z)), "LossFrmSpecBusCF": _to_rupees(sum((x["loss"] for x in items if x["head"] == "Speculative"), z)), "LossFrmSpecifiedBusCF": _to_rupees(sum((x["loss"] for x in items if x["head"] == "Specified"), z)), "TotalSTCGPTILossCF": _to_rupees(sum((x["loss"] for x in items if x["head"] == "STCG"), z)), "TotalLTCGPTILossCF": _to_rupees(sum((x["loss"] for x in items if x["head"] == "LTCG"), z)), "OthSrcLossRaceHorseCF": _to_rupees(sum((x["loss"] for x in items if x["head"] == "RaceHorse"), z))}
    output: dict[str, Any] = {"TotalOfBFLossesEarlierYrs": {"LossSummaryDetail": summary([x for x in rows if x["assessment_year"] != "2026-27"])}, "TotalLossCFSummary": {"LossSummaryDetail": summary(rows)}}
    current = [x for x in rows if x["assessment_year"] == "2026-27"]
    if current:
        output["CurrentAYloss"] = {"LossSummaryDetail": summary(current)}
    if typed_input is not None:
        for x in rows:
            if x["assessment_year"] != "2026-27":
                source = next((b for b in (typed_input.bf_losses or []) if str(b.assessment_year) == x["assessment_year"]), None)
                if source is None or source.date_of_filing is None:
                    raise ValueError(f"Schedule CFL requires date_of_filing for AY {x['assessment_year']}")
        output["AdjTotBFLossInBFLA"] = {"LossSummaryDetail": summary([])}
    return output


# Maps a SalaryResult per-exemption field to its official Section 10
# sub-clause enum value and a human-readable label, for AllwncExemptUs10Dtls.
# Ported from the identical, live-verified mapping in itd/itr2.py -- the
# same app/engine/schedules/salary.py::SalaryResult dataclass backs both
# forms. 10(13A) (HRA) is deliberately excluded -- it has its own dedicated
# Section10_13A structure below, not this generic array.
_ITR3_SALARY_EXEMPTION_ROWS: tuple[tuple[str, str, str], ...] = (
    ("lta_exempt", "10(5)", "Leave travel allowance"),
    ("gratuity_exempt", "10(10)", "Gratuity"),
    ("commuted_pension_exempt", "10(10A)", "Commuted pension"),
    ("leave_encashment_exempt", "10(10AA)", "Leave encashment"),
    ("retrenchment_exempt", "10(10B)(i)", "Retrenchment compensation"),
    ("vrs_exempt", "10(10C)", "Voluntary retirement compensation"),
    ("transport_exempt", "10(14)(ii)", "Transport allowance"),
    ("children_education_exempt", "10(14)(ii)", "Children education allowance"),
    ("hostel_exempt", "10(14)(ii)", "Hostel expenditure allowance"),
    ("uniform_allowance_exempt", "10(14)(i)", "Uniform allowance"),
)


def _schedule_s(result: ITR3Result, typed_input: ITR3Input | None = None) -> dict | None:
    """Serialize explicitly prepared employer rows into official Schedule S."""
    if typed_input is None or not typed_input.schedule_s_employers:
        return None
    employers = typed_input.schedule_s_employers
    rows: list[dict[str, Any]] = []
    for employer in employers:
        gross = sum((employer.basic, employer.da, employer.commission, employer.hra,
                     employer.bonus, employer.allowances, employer.lta,
                     employer.other_allowance, employer.arrear_salary,
                     employer.perquisites, employer.profits_in_lieu,
                     employer.income_notified_89a, employer.income_notified_other_89a,
                     employer.income_notified_prior_year_89a), Decimal("0"))
        address: dict[str, Any] = {"AddrDetail": employer.address_detail,
                                   "CityOrTownOrDistrict": employer.city,
                                   "StateCode": employer.state_code}
        if employer.pin_code is not None:
            address["PinCode"] = int(employer.pin_code)
        elif employer.zip_code is not None:
            address["ZipCode"] = employer.zip_code
        salarys: dict[str, Any] = {
            "GrossSalary": _to_rupees(gross),
            "Salary": _to_rupees(gross - employer.perquisites - employer.profits_in_lieu - employer.income_notified_89a - employer.income_notified_other_89a - employer.income_notified_prior_year_89a),
            "ValueOfPerquisites": _to_rupees(employer.perquisites),
            "ProfitsinLieuOfSalary": _to_rupees(employer.profits_in_lieu),
        }
        if employer.salary_nature_rows:
            salarys["NatureOfSalary"] = {"OthersIncDtls": _official_integer_tree(employer.salary_nature_rows)}
        if employer.perquisite_nature_rows:
            salarys["NatureOfPerquisites"] = {"OthersIncDtls": _official_integer_tree(employer.perquisite_nature_rows)}
        if employer.profit_in_lieu_nature_rows:
            salarys["NatureOfProfitInLieuOfSalary"] = {"OthersIncDtls": _official_integer_tree(employer.profit_in_lieu_nature_rows)}
        if employer.income_notified_89a:
            salarys["IncomeNotified89A"] = _to_rupees(employer.income_notified_89a)
        if employer.notified_89a_country_rows:
            salarys["IncomeNotified89AType"] = _official_integer_tree(employer.notified_89a_country_rows)
        if employer.income_notified_other_89a:
            salarys["IncomeNotifiedOther89A"] = _to_rupees(employer.income_notified_other_89a)
        if employer.income_notified_prior_year_89a:
            salarys["IncomeNotifiedPrYr89A"] = _to_rupees(employer.income_notified_prior_year_89a)
        row: dict[str, Any] = {"NameOfEmployer": employer.employer_name,
                               "NatureOfEmployment": employer.nature_of_employment,
                               "AddressDetail": address, "Salarys": salarys}
        if employer.employer_tan:
            row["TANofEmployer"] = employer.employer_tan
        rows.append(row)
    total_gross = sum((sum((e.basic, e.da, e.commission, e.hra, e.bonus, e.allowances,
                            e.lta, e.other_allowance, e.arrear_salary, e.perquisites,
                            e.profits_in_lieu, e.income_notified_89a,
                            e.income_notified_other_89a, e.income_notified_prior_year_89a), Decimal("0"))
                       for e in employers), Decimal("0"))
    # Item 3 (allowances exempt u/s 10), item 4 (Net Salary = 2-2a-3), item 5
    # (deduction u/s 16 with its a/b/c sub-lines), item 2a (89A relief), and
    # item 6 (income chargeable) all come from the shared salary schedule
    # computation -- not re-derived here -- since it already correctly
    # separates the 89A relief component from the ordinary Section 10
    # exemption total and nets Section 16 deductions against income.
    salary_schedule = result.schedules.get("salary")
    zero = Decimal("0")
    exempt_us10 = _to_rupees(getattr(salary_schedule, "exempt_allowances_excluding_89a", zero))
    net_salary = _to_rupees(getattr(salary_schedule, "net_salary", total_gross))
    standard = getattr(salary_schedule, "standard_deduction", zero)
    entertainment = getattr(salary_schedule, "entertainment_allowance", zero)
    professional = getattr(salary_schedule, "professional_tax", zero)
    deduction_us16 = getattr(salary_schedule, "deductions_u16", standard + entertainment + professional)
    total_income = getattr(salary_schedule, "income_chargeable", result.salary_income)
    relief_89a = _to_rupees(getattr(salary_schedule, "salary_89a_relief", zero))
    schedule_s: dict[str, Any] = {"Salaries": rows, "TotalGrossSalary": _to_rupees(total_gross),
            "AllwncExtentExemptUs10": exempt_us10, "NetSalary": net_salary,
            "DeductionUS16": _to_rupees(deduction_us16),
            "DeductionUnderSection16ia": _to_rupees(standard),
            "EntertainmntalwncUs16ii": _to_rupees(entertainment), "ProfessionalTaxUs16iii": _to_rupees(professional),
            "TotIncUnderHeadSalaries": _to_rupees(total_income)}
    if relief_89a:
        schedule_s["Increliefus89A"] = relief_89a

    # Item 3's own itemized breakdown (AllwncExemptUs10Dtls): the statutory
    # per-exemption amounts the shared salary calculator already computed
    # (gratuity/pension/leave-encashment/retrenchment/VRS/transport/CEA/
    # hostel/uniform -- everything except HRA, which has its own dedicated
    # Section10_13A block below), plus any itemized Section 10 rows a
    # taxpayer entered directly per employer. "OTH" has no official schema
    # code for this array -- fail closed rather than emit an invalid row.
    frontend_section10_rows: list[dict[str, Any]] = []
    for employer in employers:
        for section10_row in employer.section10_exemption_rows:
            amount = section10_row.get("SalOthAmount", 0)
            if not amount or amount <= 0:
                continue
            code = section10_row.get("SalNatureDesc")
            if code == "OTH":
                raise ValueError(
                    f"Schedule S employer {employer.employer_name!r}: Section 10 exemption row uses "
                    "code \"OTH\", which has no official ITD schema code -- select a specific "
                    "Section 10 sub-clause instead."
                )
            frontend_section10_rows.append({
                "SalNatureDesc": code,
                "SalOthNatOfInc": section10_row.get("SalOthNatOfInc"),
                "SalOthAmount": _to_rupees(Decimal(str(amount))),
            })
    exemption_rows = [
        {"SalNatureDesc": code, "SalOthNatOfInc": label, "SalOthAmount": _to_rupees(amount)}
        for field, code, label in _ITR3_SALARY_EXEMPTION_ROWS
        if (amount := getattr(salary_schedule, field, zero)) > zero
    ] + frontend_section10_rows
    if exemption_rows:
        schedule_s["AllwncExemptUs10"] = {"AllwncExemptUs10Dtls": exemption_rows}

    # Section 10(13A) HRA sub-schedule (form item 3's own dedicated block).
    # Aggregated across employers the same way the shared calculator
    # (_map_salary) aggregates its own per-employer HRA facts, then
    # cross-checked against the calculator's own already-computed hra_exempt
    # so the disclosure can never silently drift from the number actually
    # used in the tax computation.
    if len({e.is_metro_city for e in employers}) > 1:
        raise ValueError("Schedule S Section 10(13A) cannot represent mixed metro and non-metro employers")
    hra_received = sum((e.hra for e in employers), zero)
    rent_paid = sum((e.rent_paid for e in employers), zero)
    hra_salary = sum((e.basic + e.da for e in employers), zero)
    is_metro = employers[0].is_metro_city
    if typed_input.tax_regime.value == "new":
        hra_received = rent_paid = hra_salary = zero
    hra_result = compute_hra_exemption(
        actual_hra_received=hra_received, rent_paid=rent_paid, salary=hra_salary, is_metro=is_metro,
    )
    sal_hra_exempt = getattr(salary_schedule, "hra_exempt", zero)
    if _to_rupees(hra_result.exempt_amount) != _to_rupees(sal_hra_exempt) and sal_hra_exempt > zero:
        raise ValueError("Schedule S Section 10(13A) exemption reconciliation failed")
    if hra_result.exempt_amount > zero:
        schedule_s["Section10_13A"] = {
            "Placeofwork": "1" if is_metro else "2",
            "ActlHRARecv": _to_rupees(hra_received),
            "ActlRentPaid": _to_rupees(rent_paid),
            "DtlsSalUsSec171": _to_rupees(hra_salary),
            "ActlRentPaid10Per": _to_rupees(hra_result.rent_minus_10pct_salary),
            "Sal40Or50Per": _to_rupees(hra_result.salary_factor),
            "EligbleExmpAllwncUs13A": _to_rupees(hra_result.exempt_amount),
        }
    return schedule_s


def _schedule_hp(result: ITR3Result, typed_input: ITR3Input | None = None) -> dict | None:
    """Serialize explicitly prepared property rows into official Schedule HP."""
    if typed_input is None or not typed_input.schedule_hp_properties:
        return None
    # The calculator computes one HPResult per property (correctly applying
    # each property's own self-occupied/let-out treatment, Section 24(b)
    # interest cap, and ownership share) and stores the list in
    # result.schedules["hp"]. Prefer those genuinely-computed per-property
    # figures over typed_input's own standard_deduction/interest_on_loan/
    # income_of_hp fields, which are never populated by the frontend (they
    # sit at their factory default of 0) and would otherwise silently zero
    # out items 1g/1h/1k for every property.
    hp_schedule = result.schedules.get("hp")
    hp_rows = hp_schedule if isinstance(hp_schedule, list) else ([hp_schedule] if hp_schedule else [])
    properties: list[dict[str, Any]] = []
    for index, source in enumerate(typed_input.schedule_hp_properties):
        address: dict[str, Any] = {"AddrDetail": source.address_detail,
                                   "CityOrTownOrDistrict": source.city,
                                   "StateCode": source.state_code,
                                   "CountryCode": source.country_code}
        if source.pin_code is not None:
            address["PinCode"] = int(source.pin_code)
        elif source.zip_code is not None:
            address["ZipCode"] = source.zip_code
        loans = _official_integer_tree(source.home_loan_details)
        # Item 1e (BalanceALV) is the pre-ownership-share balance (1a-1d);
        # item 1f (AnnualOfPropOwned) is 1e scaled by the assessee's own
        # co-ownership share. These are two distinct figures -- previously
        # both were wrongly set to the same (post-share) value.
        balance_alv = max(Decimal("0"), source.annual_lettable_value - source.rent_not_realized - source.local_taxes)
        computed = hp_rows[index] if index < len(hp_rows) else None
        annual_value_owned = getattr(computed, "annual_value_owned", None)
        if annual_value_owned is None:
            annual_value_owned = source.annual_value_owned
        standard_deduction = getattr(computed, "standard_deduction_30pct", None)
        if standard_deduction is None:
            standard_deduction = source.standard_deduction
        interest_allowed = getattr(computed, "interest_on_loan", None)
        if interest_allowed is None:
            interest_allowed = source.interest_on_loan
        income_of_hp = getattr(computed, "income_chargeable", None)
        if income_of_hp is None:
            income_of_hp = source.income_of_hp
        raw_interest_claimed = sum(
            (Decimal(str(loan.get("InterestUs24B", 0))) for loan in source.home_loan_details), Decimal("0")
        )
        rent = {"AnnualLetableValue": _to_rupees(source.annual_lettable_value),
                "RentNotRealized": _to_rupees(source.rent_not_realized),
                "LocalTaxes": _to_rupees(source.local_taxes),
                "TotalUnrealizedAndTax": _to_rupees(source.rent_not_realized + source.local_taxes),
                "BalanceALV": _to_rupees(balance_alv),
                "AnnualOfPropOwned": _to_rupees(annual_value_owned),
                "ThirtyPercentOfBalance": _to_rupees(standard_deduction),
                "IntOnBorwCap": _to_rupees(interest_allowed),
                "Section24B": {"Section24BDtls": loans, "TotalInterestUs24B": _to_rupees(raw_interest_claimed)},
                "TotalDeduct": _to_rupees(standard_deduction + interest_allowed),
                "IncomeOfHP": _to_rupees(income_of_hp)}
        if source.arrears_unrealised_rent:
            rent["ArrearsUnrealizedRentRcvd"] = _to_rupees(source.arrears_unrealised_rent)
        prop: dict[str, Any] = {"HPSNo": source.sequence_no, "AddressDetailWithZipCode": address,
                                "PropertyOwner": source.property_owner,
                                "PropCoOwnedFlg": "YES" if source.co_owned else "NO",
                                # AsseseeShareProperty is a percentage (schema type
                                # "number", multipleOf 0.01) -- left as a raw Decimal,
                                # this crashes official schema validation outright
                                # (jsonschema's multipleOf check divides by a bare
                                # float, which Decimal does not support) for every
                                # property row, co-owned or not.
                                "AsseseeShareProperty": float(source.assessee_share_percent),
                                "ifLetOut": source.property_type, "Rentdetails": rent}
        if source.property_owner == "OT" and source.property_owner_other:
            prop["PropertyOwnerOther"] = source.property_owner_other
        if source.co_owner_details:
            # PercentShareProperty is the same percentage type as
            # AsseseeShareProperty above -- must not go through
            # _official_integer_tree, which would force it through the
            # money-only _to_rupees() rounding (silently truncating a real
            # 33.33% share to 33). Optional PAN/Aadhaar fields are omitted
            # entirely when absent, not emitted as a schema-invalid null.
            prop["CoOwners"] = [
                {k: v for k, v in {
                    "CoOwnersSNo": co.get("CoOwnersSNo"),
                    "NameCoOwner": co.get("NameCoOwner"),
                    "PAN_CoOwner": co.get("PAN_CoOwner"),
                    "Aadhaar_CoOwner": co.get("Aadhaar_CoOwner"),
                    "PercentShareProperty": float(co["PercentShareProperty"]) if co.get("PercentShareProperty") is not None else None,
                }.items() if v is not None}
                for co in source.co_owner_details
            ]
        if source.tenant_details:
            prop["TenantDetails"] = [
                {k: v for k, v in {
                    "TenantSNo": t.get("TenantSNo"),
                    "NameofTenant": t.get("NameofTenant"),
                    "PANofTenant": t.get("PANofTenant"),
                    "AadhaarofTenant": t.get("AadhaarofTenant"),
                    "PANTANofTenant": t.get("PANTANofTenant"),
                }.items() if v is not None}
                for t in source.tenant_details
            ]
        properties.append(prop)
    # CBDT rule #79 ("Sch HP Sl.2 pass-through income = HP income in
    # Schedule PTI"), ported from the identical, already-shipped fix in
    # itd/itr2.py -- typed_input.pti_entries already exists and is already
    # mapped from draft.passThroughIncomeEntries (see draft_to_itr3_input.py),
    # so this reads data already present on typed_input rather than pulling
    # ahead into Schedule PTI's own (separately tracked, not yet closed) work.
    pti_hp_income = sum(
        (p.income_amount for p in (typed_input.pti_entries or []) if p.income_head == "HP"), Decimal("0"),
    )
    return {"PropertyDetails": properties, "PassThroghIncome": _to_rupees(pti_hp_income),
            "TotalIncomeChargeableUnHP": _to_rupees(result.house_property_income)}



def _schedule_os(result: ITR3Result, typed_input: ITR3Input | None = None) -> dict | None:
    """Serialize the prepared Other Sources aggregate without placeholder rows.

    Every populated amount comes from the typed ``OtherSourcesIncome`` model
    or its typed calculator result.  Unsupported detailed disclosures are not
    invented; callers must provide the richer official source before those
    optional sections are emitted.
    """
    if typed_input is None or typed_input.other_sources_income is None:
        return None
    source = typed_input.other_sources_income
    computed = result.schedules.get("os")
    if computed is None:
        return None
    zero = 0
    family = source.family_pension_received
    deductions = getattr(computed, "deduction_57iia", Decimal("0"))
    other = {
        "GrossIncChrgblTaxAtAppRate": _to_rupees(result.other_sources_income),
        "DividendGross": _to_rupees(source.dividend_income),
        "InterestGross": _to_rupees(source.savings_bank_interest + source.fixed_deposit_interest + source.interest_on_it_refund),
        "IntrstFrmSavingBank": _to_rupees(source.savings_bank_interest),
        "IntrstFrmTermDeposit": _to_rupees(source.fixed_deposit_interest),
        "IntrstFrmIncmTaxRefund": _to_rupees(source.interest_on_it_refund),
        "FamilyPension": _to_rupees(family),
        "IncomeNotified89AOS": zero,
        "IncomeNotifiedOther89AOS": zero,
        "IncomeNotifiedPrYr89AOS": zero,
        "AnyOtherIncome": _to_rupees(source.other_income),
        "IncChargeableSpecialRates": zero,
        "CashCreditsUs68": zero,
        "UnExplndInvstmntsUs69": zero,
        "UnExplndMoneyUs69A": zero,
        "UnDsclsdInvstmntsUs69B": zero,
        "UnExplndExpndtrUs69C": zero,
        "AmtBrwdRepaidOnHundiUs69D": zero,
        "Deductions": {"DeductionUs57iia": _to_rupees(deductions), "TotDeductions": _to_rupees(deductions)},
        "BalanceNoRaceHorse": _to_rupees(result.other_sources_income),
    }
    return {
        "IncOthThanOwnRaceHorse": other,
        "TotOthSrcNoRaceHorse": _to_rupees(result.other_sources_income),
        "IncFromOwnHorse": {"Receipts": zero, "DeductSec57": zero, "AmtNotDeductibleUs58": zero, "ProfitChargTaxUs59": zero, "BalanceOwnRaceHorse": zero},
        "IncChargeable": _to_rupees(result.other_sources_income),
        "IncFrmLottery": {"DateRange": {"Upto15Of6": zero, "Up16Of6To15Of9": zero, "Up16Of9To15Of12": zero, "Up16Of12To15Of3": zero, "Up16Of3To31Of3": zero}},
        "DividendIncUs115BBDA": {"DateRange": {"Upto15Of6": zero, "Upto15Of9": zero, "Up16Of9To15Of12": zero, "Up16Of12To15Of3": zero, "Up16Of3To31Of3": zero}},
        "DividendIncUs115BBDAaiii": {"DateRange": {"Upto15Of6": zero, "Upto15Of9": zero, "Up16Of9To15Of12": zero, "Up16Of12To15Of3": zero, "Up16Of3To31Of3": zero}},
        "DividendIncUs115A1ai": {"DateRange": {"Upto15Of6": zero, "Upto15Of9": zero, "Up16Of9To15Of12": zero, "Up16Of12To15Of3": zero, "Up16Of3To31Of3": zero}},
        "DividendIncUs115AC": {"DateRange": {"Upto15Of6": zero, "Upto15Of9": zero, "Up16Of9To15Of12": zero, "Up16Of12To15Of3": zero, "Up16Of3To31Of3": zero}},
        "DividendIncUs115ACA": {"DateRange": {"Upto15Of6": zero, "Upto15Of9": zero, "Up16Of9To15Of3": zero, "Up16Of12To15Of3": zero, "Up16Of3To31Of3": zero}},
        "DividendIncUs115AD1i": {"DateRange": {"Upto15Of6": zero, "Upto15Of9": zero, "Up16Of9To15Of12": zero, "Up16Of12To15Of3": zero, "Up16Of3To31Of3": zero}},
        "NOT89A": {"DateRange": {"Upto15Of6": zero, "Upto15Of9": zero, "Up16Of9To15Of12": zero, "Up16Of12To15Of3": zero, "Up16Of3To31Of3": zero}},
        "DividendDTAA": {"DateRange": {"Upto15Of6": zero, "Upto15Of9": zero, "Up16Of9To15Of12": zero, "Up16Of12To15Of3": zero, "Up16Of3To31Of3": zero}},
    }


# Legacy optional schedule helpers below are intentionally not used for
# unprepared sources.

def _legacy_schedule_os_placeholder_removed() -> None:
    """Marker documenting that the former hardcoded OS payload was removed."""
    return None


# ============================================================================


def _itr3_112a_style_schedule(source_rows: list[dict[str, Any]], suffix: str) -> dict | None:
    """Build a Schedule112A- or Schedule115AD-shaped object from source
    rows -- ITR-3's own version of ITR-2's `_112a_style_schedule()`
    (per-row formula logic ported verbatim, confirmed identical against
    the official ITR-3 form PDF's own Schedule 112A / Schedule
    115AD(1)(b)(iii) proviso tables directly: both are the SAME 14-column
    layout, Col.7 "Cost of acquisition without indexation" = higher of
    Col.8/Col.9 (the grandfathering formula -> `CostAcqWithoutIndx`),
    Col.8 "Cost of acquisition" = the plain input cost -> `AcquisitionCost`,
    Col.14 "Balance (6-13)" -> `Balance`). Deliberately NOT a direct call
    to ITR-2's own `_112a_style_schedule()` -- confirmed via direct schema
    introspection that ITR-2's `Schedule112A`/`Schedule115AD` definitions
    have an extra `TotalBalance112A`/`TotalBalance115AD` field ITR-3's own
    schema definitions genuinely do NOT have (`additionalProperties:
    false`, so including it would fail schema validation) -- a real,
    confirmed form/schema divergence, not assumed.
    """
    if not source_rows:
        return None
    rows = []
    for item in source_rows:
        deemed_cost = item["cost"]
        if item["is_before"]:
            deemed_cost = max(item["cost"], min(item["fmv"], item["sale"]))
        deductions = deemed_cost + item["expense"]
        balance = item["balance"] if item["balance"] is not None else item["sale"] - deductions
        is_before = item["is_before"]
        rows.append({
            "ShareOnOrBefore": "BE" if is_before else "AE",
            "ISINCode": item["isin"],
            "ShareUnitName": item["name"] if is_before else "CONSOLIDATED",
            "NumSharesUnits": float(item["quantity"]) if is_before else 0.0,
            "SalePricePerShareUnit": float(item["price"]) if is_before else 0.0,
            "TotSaleValue": _to_rupees(item["sale"]),
            "CostAcqWithoutIndx": _to_rupees(deemed_cost),
            "AcquisitionCost": float(item["cost"]),
            "LTCGBeforelower6and11": _to_rupees(max(Decimal("0"), item["sale"] - item["cost"])),
            "FairMktValuePerShareunit": float(item["fmv_per_unit"]) if is_before else 0.0,
            "TotFairMktValueCapAst": _to_rupees(item["fmv"]) if is_before else 0,
            "ExpExclCnctTransfer": float(item["expense"]),
            "TotalDeductions": _to_rupees(deductions),
            "Balance": _to_rupees(balance),
        })
    sale = sum(r["TotSaleValue"] for r in rows)
    deemed_cost_total = sum(r["CostAcqWithoutIndx"] for r in rows)
    plain_cost_total = sum(Decimal(str(r["AcquisitionCost"])) for r in rows)
    fmv = sum(r["TotFairMktValueCapAst"] for r in rows)
    expenses = sum(Decimal(str(r["ExpExclCnctTransfer"])) for r in rows)
    deductions_total = sum(r["TotalDeductions"] for r in rows)
    balance_total = sum(r["Balance"] for r in rows)
    # Sum the rows' own (already row-clamped) LTCGBeforelower6and11 values,
    # not a bucket-level max(0, sale-cost) recomputation -- matches
    # ITR-2's own `_112a_style_schedule()` docstring reasoning exactly
    # (mixed gain/loss scrips give a different, correct total this way).
    ltcg_before_lower_6and11 = sum(r["LTCGBeforelower6and11"] for r in rows)
    return {
        f"Schedule{suffix}Dtls": rows,
        f"SaleValue{suffix}": sale,
        f"CostAcqWithoutIndx{suffix}": deemed_cost_total,
        f"AcquisitionCost{suffix}": _to_rupees(plain_cost_total),
        f"LTCGBeforelowerB1B2{suffix}": ltcg_before_lower_6and11,
        f"FairMktValueCapAst{suffix}": fmv,
        f"ExpExclCnctTransfer{suffix}": _to_rupees(expenses),
        f"Deductions{suffix}": deductions_total,
        f"Balance{suffix}": balance_total,
    }


def _schedule_112a_115ad(typed_input: ITR3Input | None, suffix: str) -> dict | None:
    """Serialize Schedule112A/Schedule115AD from explicit scrips PLUS any
    112A-eligible ordinary `cg_transactions` -- previously sourced ONLY
    from `cg_112a_scrips`/`cg_115ad_scrips`, silently omitting every
    112A-classified gain entered through the generic capital-gains
    transaction editor (the most common real-world entry path), even
    though the calculator's own tax computation already correctly
    includes them via `ltcg_112a_assets`. This is the exact defect ITR-2's
    own `_112a_source_rows()` was built to fix, confirmed live there
    (2026-09-13, Type-2 UAT validateItr, PAN GOYPT2026A) -- reused
    directly here (fully generic, operates on the shared `CGTransaction`/
    `CG112AScrip` schema types both forms import from `app/schemas/itr2.py`,
    no ITR-2-specific concept inside it) rather than re-derived.

    Schedule 112A (resident) and Schedule 115AD(1)(b)(iii) proviso
    (non-resident FII/FPI) are mutually exclusive per the official form's
    own text ("For NON-RESIDENTS" heading on the 115AD table) -- dispatched
    on `is_fii_fpi`, matching ITR-2's own `_schedule_112a()`/
    `_schedule_115ad()` split, even though a genuine ITR-3 filer
    (individual/HUF with business income) is never actually FII/FPI in
    practice (see this file's own established note on `equity_111a_rows`).
    """
    if typed_input is None:
        return None
    is_fii_fpi = bool(typed_input.is_fii_fpi)
    if (suffix == "115AD") != is_fii_fpi:
        return None
    explicit_scrips = [*typed_input.cg_112a_scrips, *typed_input.cg_115ad_scrips]
    source_rows = _itr2_112a_source_rows(explicit_scrips, typed_input.cg_transactions or [])
    return _itr3_112a_style_schedule(source_rows, suffix)


def _schedule_vda_typed(typed_input: ITR3Input | None) -> dict | None:
    """Serialize every explicitly prepared VDA transaction."""
    if typed_input is None or not typed_input.vda_transactions:
        return None
    rows = [{"DateofAcquisition": item.date_of_acquisition.isoformat(), "DateofTransfer": item.date_of_transfer.isoformat(),
        "HeadUndIncTaxed": item.head, "AcquisitionCost": _to_rupees(item.acquisition_cost),
        "ConsidReceived": _to_rupees(item.consideration_received), "IncomeFromVDA": _to_rupees(item.income_from_vda if item.income_from_vda is not None else max(Decimal("0"), item.consideration_received-item.acquisition_cost))} for item in typed_input.vda_transactions]
    # Form items A (business income) and B (capital gain): sum of positive
    # Col.7 incomes only, split by the row's own head -- a per-row loss is
    # never netted into either total (matches the form's own "enter nil in
    # case of loss" instruction for the row itself).
    tot_business = sum((r["IncomeFromVDA"] for r, item in zip(rows, typed_input.vda_transactions) if item.head == "BI" and r["IncomeFromVDA"] > 0), 0)
    tot_capital_gain = sum((r["IncomeFromVDA"] for r, item in zip(rows, typed_input.vda_transactions) if item.head != "BI" and r["IncomeFromVDA"] > 0), 0)
    return {"ScheduleVDADtls": rows, "TotIncBusiness": tot_business, "TotIncCapGain": tot_capital_gain}


def _slump_sale_block(rows: list, is_long_term: bool) -> dict[str, Any]:
    """
    Aggregate Schedule CG item A2 (STCG)/B2 (LTCG) slump-sale rows
    (``ITR3SlumpSaleRow``) into the official schema's single summary
    object -- there is no per-transaction array for this item, matching
    the form's own single-row layout (items 2a-2c/2a-2e).

    Formula, confirmed against the official ITR-3 form PDF directly:
        FullConsideration (2a.iii) = sum(higher of 2a.i FMV-11UAE(2) or
                                          2a.ii FMV-11UAE(3), per row)
        Balance (2c) = FullConsideration - NetWorthOfDivision (2b)
        LTCG only: CapgainonAssets (2e) = Balance (2c) - deduction u/s
                   54EC/54F (2d); STCG has no exemption sub-item at all
                   (2c IS the final STCG figure, no "2d"/"2e").
    """
    fmv2_total = sum((r.fmv_11uae_2 for r in rows), Decimal("0"))
    fmv3_total = sum((r.fmv_11uae_3 for r in rows), Decimal("0"))
    net_worth_total = sum((r.net_worth for r in rows), Decimal("0"))
    full_consideration = sum((max(r.fmv_11uae_2, r.fmv_11uae_3) for r in rows), Decimal("0"))
    balance = full_consideration - net_worth_total
    if not is_long_term:
        return {
            "FMV11UAEii": _to_rupees(fmv2_total),
            "FMV11UAEiii": _to_rupees(fmv3_total),
            "FullConsideration": _to_rupees(full_consideration),
            "NetWorthOfDivision": _to_rupees(net_worth_total),
            "CapgainonAssets": _to_rupees(balance),
        }
    # The frontend row captures one flat exemption amount with no section
    # sub-code (54EC vs 54F) -- the per-section breakdown array
    # (`ExemptionOrDednUs54Dtls`) is schema-optional (only
    # ``ExemptionGrandTotal`` is required), so it is omitted rather than
    # guessed at, matching this codebase's established "omit uncertain
    # optional detail rather than fabricate a classification" discipline.
    exemption_total = sum((r.exemption_amount for r in rows), Decimal("0"))
    return {
        "FMV11UAEii": _to_rupees(fmv2_total),
        "FMV11UAEiii": _to_rupees(fmv3_total),
        "FullConsideration": _to_rupees(full_consideration),
        "NetWorthOfDivision": _to_rupees(net_worth_total),
        "SlumpBalance": _to_rupees(balance),
        "ExemptionOrDednUs54": {"ExemptionGrandTotal": _to_rupees(exemption_total)},
        "CapgainonAssets": _to_rupees(balance - exemption_total),
    }


def _cg_dtaa_rows(entries: list) -> list[dict[str, Any]]:
    """Schedule CG items A9/B12 -- DTAA-rate capital-gains claim rows
    (official ``NRIDTAADtls``). Identical shape/logic to ITR-2's own
    already-shipped local helper of the same purpose (`itd/itr2.py`'s own
    nested `_cg_dtaa_rows`) -- ported verbatim rather than re-derived,
    since both forms disclose this item under the identical schema shape."""
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


_ITR3_LAND_BUILDING_STCG_SECCODES = ("54B", "54G", "54GA")
_ITR3_LAND_BUILDING_LTCG_SECCODES = ("54", "54B", "54D", "54EC", "54F", "54G", "54GA")


def _cg_land_building_row_stcg(asset: Any) -> dict[str, Any]:
    """Build one ITR-3 Schedule CG STCG SaleofLandBuildDtls row.

    ITR-3's own schema shape for this row DIFFERS from ITR-2's -- confirmed
    by direct introspection of both forms' schemas, not assumed identical
    despite the two forms sharing almost everything else about Schedule
    CG. ITR-3's item A1d allows THREE exemption sections (54B/54G/54GA,
    vs ITR-2's single 54B), so the field is a nested ``ExemptionOrDednUs54
    {ExemptionOrDednUs54Dtls, ExemptionGrandTotal}`` object here, not
    ITR-2's flat ``DeductionUs54B`` scalar; the balance field is named
    ``CapgainonAssets`` here, not ITR-2's ``STCGonImmvblPrprty``.
    Previously this codebase called ITR-2's own row builder unchanged for
    ITR-3 too, which silently produced schema-invalid JSON (``Additional
    properties are not allowed``, missing required ``ExemptionOrDednUs54``
    /``CapgainonAssets``) for EVERY ITR-3 return with a land/building STCG
    transaction -- one of the most common real-world Schedule CG
    scenarios. Found and fixed during the Schedule 20 re-verification,
    unrelated to anything else fixed this session.
    """
    stamp_value = getattr(asset, "stamp_duty_value", Decimal("0")) or Decimal("0")
    deemed = deemed_consideration_50c(asset.full_consideration, stamp_value)
    exemption_total = getattr(asset, "exemption_total", Decimal("0"))
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
        "ExemptionOrDednUs54": _itr2_exemption_or_dedn_us54_block(getattr(asset, "exemptions", None), _ITR3_LAND_BUILDING_STCG_SECCODES),
        "CapgainonAssets": _to_rupees(asset.balance - exemption_total),
    }


def _cg_land_building_row_ltcg(asset: Any) -> dict[str, Any]:
    """Build one ITR-3 Schedule CG LTCG SaleofLandBuildDtls row.

    Same field-naming mismatch as the STCG row above (``CapgainonAssets``/
    ``CapgainonAssets_1ea`` here, not ITR-2's ``LTCGonImmvblPrprty``/
    ``LTCGonImmvblPrprtyBE``) -- ``ExemptionOrDednUs54``/``TaxSec1121a``/
    ``TaxSec1121aiiB``/``ExcessAmtSec1121a``/``TotalDednForEiB``/
    ``BalanceForEiB`` DO happen to share ITR-2's exact field names
    (confirmed directly against both schemas, not assumed), so only the
    two ``CapgainonAssets*`` fields needed correcting here -- and
    ``ExemptionOrDednUs54``'s own valid section-code set is wider here
    too (54/54B/54D/54EC/54F/54G/54GA vs ITR-2's 54/54B/54EC/54F).
    """
    stamp_value = getattr(asset, "stamp_duty_value", Decimal("0")) or Decimal("0")
    deemed = deemed_consideration_50c(asset.full_consideration, stamp_value)
    exemption_total = getattr(asset, "exemption_total", Decimal("0"))
    row: dict[str, Any] = {
        "DateofPurchase": asset.date_of_acquisition or "",
        "DateofSale": asset.date_of_transfer,
        "FullConsideration": _to_rupees(asset.full_consideration),
        "PropertyValuation": _to_rupees(stamp_value),
        "FullConsideration50C": _to_rupees(deemed),
        "AquisitCost": _to_rupees(asset.acquisition_cost),
        "AquisitCostIndex": _to_rupees(asset.indexed_acquisition_cost),
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
        "ExemptionOrDednUs54": _itr2_exemption_or_dedn_us54_block(getattr(asset, "exemptions", None), _ITR3_LAND_BUILDING_LTCG_SECCODES),
        "CapgainonAssets": _to_rupees(asset.balance - exemption_total),
    }
    if getattr(asset, "eib_applicable", False):
        # Same real-CII fallback as compute_ltcg() -- an unpopulated
        # indexed cost must never be treated as equal to the un-indexed
        # cost; that would silently zero the second-proviso relief this
        # exact block discloses.
        indexed_acquisition = asset.indexed_acquisition_cost or _indexed_cost(
            asset.acquisition_cost, asset.date_of_acquisition, asset.date_of_transfer
        )
        indexed_improvement = asset.indexed_improvement_cost or (
            _indexed_cost(asset.improvement_cost, asset.year_of_improvement or asset.date_of_acquisition, asset.date_of_transfer)
            if asset.improvement_cost > 0 else Decimal("0")
        )
        total_dedn_for_eib = indexed_acquisition + indexed_improvement + asset.expenditure_on_transfer
        row["TotalDednForEiB"] = _to_rupees(total_dedn_for_eib)
        row["BalanceForEiB"] = _to_rupees(asset.balance_for_eib)
        # "1ea = 1ca - 1d" per the form's own text -- same exemption total
        # ("1d") subtracted from both the primary and EiB tracks.
        row["CapgainonAssets_1ea"] = _to_rupees(
            max(Decimal("0"), asset.balance_for_eib - exemption_total)
        )
        row["TaxSec1121a"] = _to_rupees(asset.tax_sec_112_1a)
        row["TaxSec1121aiiB"] = _to_rupees(asset.tax_sec_112_1a_iib)
        row["ExcessAmtSec1121a"] = _to_rupees(asset.excess_amt_sec_112_1a)
    return row


def _land_building_54dga_rows(transactions: list, field_name: str, use_acquisition_date: bool) -> list[dict[str, Any]]:
    """Build ``DeducClaimDtlsUs54D``/``Us54G``/``Us54GA`` rows (Schedule CG
    item D) from each land/building transaction's own legacy scalar claim.

    Unlike sections 54/54B/54EC/54F (handled by the shared
    ``_deduction_claim_detail_rows()``, sourced from the CANONICAL,
    CGAS-evidence-tracked ``CGTransaction.exemptions`` claim list), 54D/
    54G/54GA cannot be represented there at all -- ``CapitalGainExemption
    Claim.section`` is a ``Literal["54","54B","54EC","54F","115F"]`` that
    structurally excludes them. These three sections only ever exist as
    ``CGTransaction.deduction_us54d``/``_us54g``/``_us54ga`` bare legacy
    scalars (cross-form issue #10, tracker) -- no date-of-investment/CGAS-
    deposit-evidence sub-fields exist for them anywhere in this codebase.
    Only the two officially REQUIRED fields per row (``DateofAcquisition``+
    ``AmtDeducted`` for 54D; ``DateofTransfer``+``AmtDeducted`` for 54G/
    54GA, confirmed by direct schema introspection) are populated --
    honest about what data actually exists, not fabricating the richer
    CGAS-evidence fields the official schema also allows but this
    codebase has no source for.
    """
    rows: list[dict[str, Any]] = []
    for tx in transactions or []:
        amount = getattr(tx, field_name, None) or Decimal("0")
        if amount <= 0:
            continue
        if use_acquisition_date:
            acquired = getattr(tx, "date_of_acquisition", None)
            if acquired is None:
                continue
            rows.append({"DateofAcquisition": acquired.isoformat(), "AmtDeducted": _to_rupees(amount)})
        else:
            transferred = getattr(tx, "date_of_transfer", None)
            if transferred is None:
                continue
            rows.append({"DateofTransfer": transferred.isoformat(), "AmtDeducted": _to_rupees(amount)})
    return rows


# Schedule CG items A7 (STCG)/B10 (LTCG) -- the official schema restricts
# the prior-year-deposit table's own year/section enums, and they DIFFER
# between the two tables (confirmed by direct introspection of both
# UnutilizedCgPrvYrStcg/UnutilizedCgPrvYrLtcg schema definitions): STCG
# allows only sections 54B/54G/54GA; LTCG additionally allows 54/54D/54F/
# 54GB. Both share the same three transfer-year values.
_UNUTILIZED_CG_YEARS = frozenset({"2022-23", "2023-24", "2024-25"})
_UNUTILIZED_CG_STCG_SECTIONS = frozenset({"54B", "54G", "54GA"})
_UNUTILIZED_CG_LTCG_SECTIONS = frozenset({"54", "54B", "54D", "54F", "54G", "54GA", "54GB"})


def _unutilized_cg_block(
    flag: str, rows: list, valid_sections: frozenset[str], require_amt_utilized: bool,
) -> dict[str, Any]:
    """
    Build the shared shape behind Schedule CG item A7 (STCG)/B10 (LTCG) --
    amount deemed to be capital gains from an unutilized prior-year
    Capital Gains Accounts Scheme deposit. Returns GENERIC keys
    (``Flag``/``UnutilizedCg``/``AmtDeemed``/``TotalAmtDeemed``); the
    caller renames them to the STCG- or LTCG-specific official field
    names, since Python dict-literal keys can't cleanly branch on a
    boolean the way the rest of this builder's inline dicts do.

    ``AmtDeemed`` sums every row's own ``amount_unutilized`` regardless of
    whether that row's year/section happens to validate against the
    schema's own fixed enum (a real, statutorily-deemed capital gain does
    not stop being real just because a taxpayer's free-text label doesn't
    match the enum) -- but the per-row disclosure array
    (``UnutilizedCgPrvYrDtls``) only includes the schema-valid rows,
    omitted (not fabricated) when a row's label doesn't validate, matching
    this codebase's established discipline. The LTCG table additionally
    requires ``AmtUtilized`` on every disclosed row (STCG's own schema
    leaves it optional).
    """
    total_deemed = sum((r.amount_unutilized for r in rows), Decimal("0"))
    detail_rows = []
    for r in rows:
        if r.prev_year_transferred not in _UNUTILIZED_CG_YEARS or r.section_claimed not in valid_sections:
            continue
        row: dict[str, Any] = {
            "PrvYrInWhichAsstTrnsfrd": r.prev_year_transferred,
            "SectionClmd": r.section_claimed,
            "AmtUnutilized": _to_rupees(r.amount_unutilized),
        }
        if r.year_asset_acquired:
            row["YrInWhichAssetAcq"] = r.year_asset_acquired
        if require_amt_utilized or r.amount_utilized:
            row["AmtUtilized"] = _to_rupees(r.amount_utilized)
        detail_rows.append(row)
    return {
        "Flag": flag if flag in ("Y", "N", "X") else "N",
        "UnutilizedCg": {"UnutilizedCgPrvYrDtls": detail_rows} if detail_rows else None,
        "AmtDeemed": _to_rupees(total_deemed),
        "TotalAmtDeemed": _to_rupees(total_deemed),
    }


def _schedule_cg_for23_typed(cg_result: Any, typed_input: ITR3Input | None) -> dict[str, Any]:
    """Serialize typed ITR-3 capital-gains evidence into ScheduleCGFor23.

    The detailed land/building, Section 112A/115AD, and VDA paths are shared
    with ITR-2's schema-verified serializers. Unsupported disclosures are not
    synthesized here; absent evidence produces an empty aggregate section.
    """
    if typed_input is None:
        raise ValueError("ScheduleCGFor23 requires typed ITR3Input")
    if cg_result is None:
        raise ValueError("ScheduleCGFor23 requires a computed capital-gains result")
    stcg = getattr(cg_result, "stcg", None)
    ltcg = getattr(cg_result, "ltcg", None)
    zero = Decimal("0")
    stcg_assets = list(getattr(stcg, "land_building", []) or [])
    ltcg_assets = list(getattr(ltcg, "land_building", []) or [])
    stcg_rows = [_cg_land_building_row_stcg(asset) for asset in stcg_assets]
    ltcg_rows = [_cg_land_building_row_ltcg(asset) for asset in ltcg_assets]
    total_stcg = getattr(stcg, "total_stcg", zero)
    total_ltcg = getattr(ltcg, "total_ltcg", zero)
    total_cg = getattr(cg_result, "total_capital_gains", zero)
    vda_income = getattr(cg_result, "vda_income", zero)

    # Build Table F from the same explicit transaction/VDA dates. It is an
    # accrual disclosure, so losses are excluded and remain Decimal-valued.
    buckets: dict[str, list[Decimal]] = {name: [zero] * 5 for name in ("stcg20", "stcg30", "stcg_app", "ltcg125", "vda")}
    for tx in typed_input.cg_transactions or []:
        gain = max(zero, tx.full_consideration - tx.cost_of_acquisition - tx.improvement_cost - tx.expenditure_on_transfer)
        if not gain:
            continue
        asset_type = tx.asset_type.value if hasattr(tx.asset_type, "value") else tx.asset_type
        is_long = bool(tx.explicit_long_term)
        if tx.date_of_acquisition is not None:
            from app.engine.schedules.capital_gains import _is_short_term
            is_long = not _is_short_term(asset_type, tx.date_of_acquisition, tx.date_of_transfer)
        bucket = "ltcg125" if is_long else ("stcg20" if asset_type in ("listed_equity_111a", "equity_oriented_fund_111a") else "stcg_app")
        buckets[bucket][_quarter_index(tx.date_of_transfer)] += gain
    for item in typed_input.vda_transactions or []:
        income = item.income_from_vda if item.income_from_vda is not None else max(zero, item.consideration_received - item.acquisition_cost)
        buckets["vda"][_quarter_index(item.date_of_transfer)] += income

    gain_112a = getattr(ltcg, "income_112a", zero)
    # Schedule CG item B4b -- deduction u/s 54F against 112A LTCG (form:
    # "4a - 4b = B4c"). Ported verbatim from ITR-2's own already-working
    # `itd/itr2.py` logic: attributable only to CGTransaction rows the
    # calculator itself classified into the 112A basket (the explicit
    # `cg_112a_scrips` path has no `exemptions` field at all -- a
    # separate, narrower pre-existing limitation neither form's builder
    # expands here), summed from each transaction's own rich `exemptions`
    # claim list (not the legacy scalar fields, which land/building rows
    # use instead).
    _112a_asset_types = {"listed_equity_112a", "equity_oriented_fund_112a", "business_trust_unit_112a"}
    ded_54f_112a = sum(
        (
            _exemption_claim_total(getattr(tx, "exemptions", None), frozenset({"54F"}))
            for tx in (typed_input.cg_transactions or [])
            if (tx.asset_type.value if hasattr(tx.asset_type, "value") else tx.asset_type) in _112a_asset_types
        ),
        zero,
    )
    equity_112a = {
        "BalanceCG": _to_rupees(gain_112a),
        "DeductionUs54F": _to_rupees(ded_54f_112a),
        "CapgainonAssets": _to_rupees(gain_112a - ded_54f_112a),
    }

    # Schedule CG A7/A10 disclose the capital-gain character retained by
    # pass-through income.  These values come only from explicit typed PTI
    # rows; no Schedule CG detail row is synthesized when PTI is absent.
    pti_stcg = sum(
        (item.income_amount for item in typed_input.pti_entries
         if item.income_head == "STCG" and item.income_amount > zero), zero
    )
    pti_stcg_111a = sum(
        (item.income_amount for item in typed_input.pti_entries
         if item.income_head == "STCG" and item.section == "111A"
         and item.income_amount > zero), zero
    )
    pti_ltcg = sum(
        (item.income_amount for item in typed_input.pti_entries
         if item.income_head == "LTCG" and item.income_amount > zero), zero
    )
    pti_ltcg_112a = sum(
        (item.income_amount for item in typed_input.pti_entries
         if item.income_head == "LTCG" and "112A" in item.section.upper()
         and item.income_amount > zero), zero
    )

    # Current-year capital-loss disclosure is sourced from the calculator's
    # typed loss buckets, which are positive loss magnitudes.  The official
    # Schedule CG matrix is populated below from those real buckets rather
    # than from placeholder rows or an unrelated carried-forward ledger.
    current_losses = getattr(cg_result, "current_year_losses", None)
    loss_value = lambda name: _to_rupees(
        getattr(current_losses, name, zero) if current_losses is not None else zero
    )
    current_loss_rows: dict[str, dict[str, int]] = {
        "InLossSetOff": {
            "StclSetoff20Per": loss_value("stcg20_loss"),
            "StclSetoff30Per": loss_value("stcg30_loss"),
            "StclSetoffAppRate": loss_value("stcg_app_loss"),
            "StclSetoffDTAARate": loss_value("stcg_dtaa_loss"),
            "LtclSetOff12_5Per": loss_value("ltcg125_loss"),
            "LtclSetOffDTAARate": loss_value("ltcg_dtaa_loss"),
        },
        "TotLossSetOff": {
            "StclSetoff20Per": 0,
            "StclSetoff30Per": 0,
            "StclSetoffAppRate": 0,
            "StclSetoffDTAARate": 0,
            "LtclSetOff12_5Per": 0,
            "LtclSetOffDTAARate": 0,
        },
        "LossRemainSetOff": {
            "StclSetoff20Per": loss_value("stcg20_loss"),
            "StclSetoff30Per": loss_value("stcg30_loss"),
            "StclSetoffAppRate": loss_value("stcg_app_loss"),
            "StclSetoffDTAARate": loss_value("stcg_dtaa_loss"),
            "LtclSetOff12_5Per": loss_value("ltcg125_loss"),
            "LtclSetOffDTAARate": loss_value("ltcg_dtaa_loss"),
        },
    }
    # The calculator currently exposes loss magnitudes, not a per-target
    # set-off matrix.  Until such a matrix exists, only the evidence-backed
    # loss and remaining ledgers are disclosed; set-off totals stay zero.
    current_loss_rows.update({
        "InStcg20Per": {"CurrYearIncome": _to_rupees(pti_stcg_111a), "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "CurrYrCapGain": _to_rupees(pti_stcg_111a)},
        "InStcg30Per": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "CurrYrCapGain": 0},
        "InStcgAppRate": {"CurrYearIncome": _to_rupees(pti_stcg - pti_stcg_111a), "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffDTAARate": 0, "CurrYrCapGain": _to_rupees(pti_stcg - pti_stcg_111a)},
        "InStcgDTAARate": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "CurrYrCapGain": 0},
        # Schedule CYLA does not split section-112A LTCG from other 12.5%-
        # rate LTCG the way Schedule CG's own Table A/B do -- both share the
        # single "InLtcg12_5Per" row (confirmed against ITR-2's own
        # equivalent `_pti_cg_by_bucket()`, which combines both into one
        # "ltcg125" bucket with no separate "other" key at all). Non-112A
        # PTI LTCG must NOT be disclosed under "InLtcgDTAARate" -- it is not
        # DTAA-rate income, it is ordinary flat-12.5% PTI LTCG (taxed via
        # `compute_pti_ltcg125()`, a genuine, distinct SecCode from 112A's
        # own, but the same 12.5% *rate bucket* for CYLA purposes).
        "InLtcg12_5Per": {"CurrYearIncome": _to_rupees(pti_ltcg), "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOffDTAARate": 0, "CurrYrCapGain": _to_rupees(pti_ltcg)},
        "InLtcgDTAARate": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOff12_5Per": 0, "CurrYrCapGain": 0},
    })

    pass_stcg = _to_rupees(pti_stcg)
    pass_stcg_111a = _to_rupees(pti_stcg_111a)
    pass_stcg_other = _to_rupees(pti_stcg - pti_stcg_111a)
    pass_ltcg = _to_rupees(pti_ltcg)
    pass_ltcg_112a = _to_rupees(pti_ltcg_112a)
    pass_ltcg_other = _to_rupees(pti_ltcg - pti_ltcg_112a)

    # Schedule CG items A6 (STCG "SaleOnOtherAssets") / B9 (LTCG
    # "SaleofAssetNADtls.SaleofAssetNA") -- generic other-asset disclosures,
    # typed in cg_transactions. ITR-3's own shapes for these two items are
    # SCHEMA-RICHER than ITR-2's equivalent items (Sl. A5/B8): confirmed by
    # direct introspection of both official JSON schema files, not assumed
    # from the shared type name -- see `cg_shared.build_itr3_other_assets_
    # stcg_block`/`build_itr3_other_assets_ltcg_block`'s own docstrings for
    # the exact schema/form-text citations. A6's own item 6e ("Deemed
    # short-term capital gains on depreciable assets (6 of schedule DCG)")
    # is Schedule DCG's own grand total -- a business-income-only concept
    # ITR-2 has no equivalent of at all.
    dcg_schedule = typed_input.depreciation_schedules.schedule_dcg if typed_input.depreciation_schedules else None
    deemed_stcg_depreciable = (
        dcg_schedule.SummaryFromDeprSchCG.TotalDepreciation if dcg_schedule is not None else Decimal("0")
    )
    stcg_other = build_itr3_other_assets_stcg_block(typed_input.cg_transactions or [], deemed_stcg_depreciable)
    # Schedule CG item B6 ("NRIOnSec112and115") -- LTCG on unlisted
    # securities u/s 112(1)(c), bonds/GDRs u/s 115AC, or FII securities
    # u/s 115AD. Confirmed present in ITR-3's own official JSON schema
    # (identical field name to ITR-2's), but previously entirely absent
    # from this builder -- a real gap, not a by-design omission (unlike
    # `NRISecur115AD`, the STCG sibling immediately below, which correctly
    # stays empty for ITR-3: section 115AD is FII/FPI-specific and ITR-3
    # filers -- individuals/HUF -- can never be an FII/FPI entity, so any
    # transaction tagged that way already falls into the ordinary
    # `SaleOnOtherAssets`/`SaleofAssetNADtls` bucket via asset-type
    # membership alone; B6's own 112(1)(c)/115AC sub-cases have no such
    # equivalent ordinary-bucket fallback and were simply dropped).
    # Grouped by the transaction's own declared `section_code`
    # (`is_nri_unquoted_shares_disposal`-tagged, set by
    # `app/engine/draft_to_itr2_input.py::_map_nri_112_115_securities`,
    # shared with ITR-2) and EXCLUDED from the ordinary bucket below to
    # avoid double-counting the same transaction in both places.
    _nri_112_115_section_code_map = {"112_1_c": "21ciii", "115AC": "5AC1c", "115AD": "5ADiii"}
    _nri_112_115_by_code: dict[str, list] = {}
    _ordinary_ltcg_txs: list = []
    for _tx in (typed_input.cg_transactions or []):
        if _tx.is_nri_unquoted_shares_disposal and _tx.section_code:
            _nri_112_115_by_code.setdefault(_tx.section_code, []).append(_tx)
        else:
            _ordinary_ltcg_txs.append(_tx)
    nri_112_115_rows = [
        {"SectionCode": _nri_112_115_section_code_map[code], **build_itr3_other_assets_ltcg_block(group)}
        for code, group in _nri_112_115_by_code.items()
        if code in _nri_112_115_section_code_map
    ]
    ltcg_other = build_itr3_other_assets_ltcg_block(_ordinary_ltcg_txs)
    stcg_buyback_loss_block = build_stcg_buyback_loss_block(
        typed_input.cg_buyback_loss_stcg20, typed_input.cg_buyback_loss_stcg30,
        typed_input.cg_buyback_loss_stcg_applicable,
    )
    ltcg_buyback_loss_block = build_ltcg_buyback_loss_block(typed_input.cg_buyback_loss_ltcg)
    # Schedule CG items A2 (STCG)/B2 (LTCG) -- slump sale of an undertaking
    # or division (section 50B, genuinely ITR-3-only -- see
    # `ITR3SlumpSaleRow`'s own docstring). The official schema has no
    # per-transaction array for this item, only one aggregate block, so
    # multiple rows (a taxpayer selling more than one division/undertaking
    # in the year) are summed here.
    stcg_slump_sale_block = _slump_sale_block(typed_input.cg_slump_sale_stcg, is_long_term=False)
    ltcg_slump_sale_block = _slump_sale_block(typed_input.cg_slump_sale_ltcg, is_long_term=True)
    # Schedule CG items A9/B12 -- DTAA-rate capital-gains claims.
    stcg_dtaa_rows = _cg_dtaa_rows(typed_input.cg_stcg_dtaa_entries or [])
    stcg_dtaa_not_chargeable = sum((e.amount for e in (typed_input.cg_stcg_dtaa_entries or []) if not e.chargeable_in_india), zero)
    stcg_dtaa_chargeable = sum((e.amount for e in (typed_input.cg_stcg_dtaa_entries or []) if e.chargeable_in_india), zero)
    ltcg_dtaa_rows = _cg_dtaa_rows(typed_input.cg_ltcg_dtaa_entries or [])
    ltcg_dtaa_not_chargeable = sum((e.amount for e in (typed_input.cg_ltcg_dtaa_entries or []) if not e.chargeable_in_india), zero)
    ltcg_dtaa_chargeable = sum((e.amount for e in (typed_input.cg_ltcg_dtaa_entries or []) if e.chargeable_in_india), zero)
    # Schedule CG items A7/B10 -- unutilized Capital Gains Accounts Scheme
    # deposit deemed capital gains.
    stcg_unutilized = _unutilized_cg_block(
        typed_input.cg_stcg_unutilized_flag, typed_input.cg_stcg_unutilized_deposits or [],
        _UNUTILIZED_CG_STCG_SECTIONS, require_amt_utilized=False,
    )
    ltcg_unutilized = _unutilized_cg_block(
        typed_input.cg_ltcg_unutilized_flag, typed_input.cg_ltcg_unutilized_deposits or [],
        _UNUTILIZED_CG_LTCG_SECTIONS, require_amt_utilized=True,
    )
    # Schedule CG item A3 -- STCG on equity shares/equity-oriented fund
    # units/business trust units, STT paid (s.111A). ITR-3 filers (
    # individuals/HUF with business income) are never FII/FPI, so this is
    # always MFSectionCode "1A", never the "5AD1biip" proviso -- unlike
    # ITR-2, which has a real filing-profile-level FII/FPI flag.  Derived
    # from the same shared cg_transactions the calculator's own A3 tax
    # figure (stcg_111a_val, calculators/itr3.py) already uses, via the
    # same helper ITR-2's builder uses, so the two forms can never
    # silently diverge on this schedule's arithmetic.
    equity_111a_rows = build_equity_mf_stt_rows(typed_input.cg_transactions or [], is_fii_fpi=False)
    stcg_block: dict[str, Any] = {
        "SaleofLandBuild": {"SaleofLandBuildDtls": stcg_rows},
        "EquityMFonSTT": equity_111a_rows,
        "NRITransacSec48Dtl": {"NRItaxSTTPaid": _to_rupees(typed_input.cg_nri_stcg_stt_paid), "NRItaxSTTNotPaid": _to_rupees(typed_input.cg_nri_stcg_stt_not_paid)},
        "NRISecur115AD": {"FullValueConsdRecvUnqshr": 0, "FairMrktValueUnqshr": 0, "FullValueConsdSec50CA": 0, "FullValueConsdOthUnqshr": 0, "FullConsideration": 0, "DeductSec48": {"AquisitCost": 0, "ImproveCost": 0, "ExpOnTrans": 0, "TotalDedn": 0}, "BalanceCG": 0, "LossSec94of7Or94of8": 0, "CapgainonAssets": 0},
        "SaleOnOtherAssets": stcg_other,
        "UnutilizedStcgFlag": stcg_unutilized["Flag"],
        **({"UnutilizedCg": stcg_unutilized["UnutilizedCg"]} if stcg_unutilized["UnutilizedCg"] else {}),
        "AmtDeemedStcg": stcg_unutilized["AmtDeemed"], "TotalAmtDeemedStcg": stcg_unutilized["TotalAmtDeemed"],
        "SlumpSaleInStcg": stcg_slump_sale_block,
        "PassThrIncNatureSTCG": pass_stcg, "PassThrIncNatureSTCG20Per": pass_stcg_111a, "PassThrIncNatureSTCG30Per": 0, "PassThrIncNatureSTCGAppRate": pass_stcg_other,
        **({"NRICgDTAA": {"NRIDTAADtls": stcg_dtaa_rows}} if stcg_dtaa_rows else {}),
        "TotalAmtNotTaxUsDTAAStcg": _to_rupees(stcg_dtaa_not_chargeable), "TotalAmtTaxUsDTAAStcg": _to_rupees(stcg_dtaa_chargeable),
        **({"CapitalLossBuyBackShares": stcg_buyback_loss_block} if stcg_buyback_loss_block else {}),
        "TotalSTCG": _to_rupees(total_stcg),
    }
    ltcg_block: dict[str, Any] = {
        # TotalExcessTax (B1h = SigmaB1eii) -- already computed per-asset by
        # compute_ltcg() itself (the section 112(1)(a) second-proviso
        # comparison, protecting a resident who acquired before 23-Jul-2024
        # from a tax increase caused by the 2024 indexation-removal change)
        # and already summed onto LTCGResult.total_excess_tax_112_1a --
        # simply never read here before. Matches ITR-2's own already-working
        # one-line wiring exactly (`itd/itr2.py`'s own `TotalExcessTax`).
        "SaleofLandBuild": {"SaleofLandBuildDtls": ltcg_rows, "TotalExcessTax": _to_rupees(getattr(ltcg, "total_excess_tax_112_1a", zero) if ltcg else zero), "TotalLTCGImmblPrprty": _to_rupees(sum((a.balance for a in ltcg_assets), zero))},
        "SaleOfEquityShareUs112A": equity_112a,
        "NRIProvisoSec48": _itr2_nri_proviso_48(typed_input), "NRISaleOfEquityShareUs112A": {"BalanceCG": 0, "DeductionUs54F": 0, "CapgainonAssets": 0}, "NRISaleofForeignAsset": _itr2_nri_foreign_asset(typed_input),
        **({"NRIOnSec112and115": {"NRIOnSec112and115Dtls": nri_112_115_rows}} if nri_112_115_rows else {}),
        "SaleofAssetNADtls": {"SaleofAssetNA": ltcg_other},
        "SlumpSaleInLtcgDtls": {"SlumpSaleInLtcg": ltcg_slump_sale_block},
        "UnutilizedLtcgFlag": ltcg_unutilized["Flag"],
        **({"UnutilizedCg": ltcg_unutilized["UnutilizedCg"]} if ltcg_unutilized["UnutilizedCg"] else {}),
        "AmtDeemedLtcg": ltcg_unutilized["AmtDeemed"], "TotalAmtDeemedLtcg": ltcg_unutilized["TotalAmtDeemed"],
        "PassThrIncNatureLTCG": pass_ltcg, "PassThrIncNatureLTCGUs112A12_5Per": pass_ltcg_112a, "PassThrIncNatureLTCG12_5Per": pass_ltcg_other,
        **({"NRICgDTAA": {"NRIDTAADtls": ltcg_dtaa_rows}} if ltcg_dtaa_rows else {}),
        "TotalAmtNotTaxUsDTAALtcg": _to_rupees(ltcg_dtaa_not_chargeable),
        **({"CapitalLossBuyBackShares": ltcg_buyback_loss_block} if ltcg_buyback_loss_block else {}),
        "TotalAmtTaxUsDTAALtcg": _to_rupees(ltcg_dtaa_chargeable), "TotalLTCG": _to_rupees(total_ltcg),
    }
    # TotDeductClaim -- the calculator's own authoritative exemption total
    # (`compute_exemptions()`'s 54/54B/54EC/54F/115F sum, cross-form issue
    # #13 fixed 2026-09-19: previously omitted any canonical per-transaction
    # 115F claim entirely), not re-summed from the disclosure rows --
    # matching ITR-2's own established builder exactly (`itd/itr2.py`'s
    # `total_exempt`). Item B7's own bare, off-form-computed 115F deduction
    # is added here directly, at the disclosure layer only -- it must NOT
    # flow through the calculator's `exemptions.total_exemption` (consumed
    # a second time by `post_loss_cg_baskets()` to compute the actual taxed
    # LTCG), since it's already netted directly into `income_125per_other`;
    # adding it there too would double-subtract it from the real tax
    # (confirmed by a regression, `test_nri_115f_net_sale_value_taxed_at_
    # section_112`, which caught this exact double-count on first attempt).
    # `DeducClaimDtlsUs115F` (below) discloses only genuine canonical
    # per-transaction claims -- the B7 bare aggregate has no transfer/
    # investment date data anywhere in this codebase to back a per-claim
    # detail row, so it correctly stays represented in the total only, not
    # fabricated into a detail row (same "omit rather than fabricate"
    # principle used throughout this builder).
    cg_exemptions = getattr(cg_result, "exemptions", None)
    tot_deduct_claim = (
        getattr(cg_exemptions, "total_exemption", zero) if cg_exemptions else zero
    ) + typed_input.cg_nri_115f_deduction
    all_cg_transactions = typed_input.cg_transactions or []
    return {"ShortTermCapGainFor23": stcg_block, "LongTermCapGain23": ltcg_block, "DeducClaimInfo": {"DeducClaimDtlsUs115F": _itr2_deduction_claim_detail_rows(all_cg_transactions, "115F"), "DeducClaimDtlsUs54": _itr2_deduction_claim_detail_rows(all_cg_transactions, "54"), "DeducClaimDtlsUs54B": _itr2_deduction_claim_detail_rows(all_cg_transactions, "54B"), "DeducClaimDtlsUs54D": _land_building_54dga_rows(all_cg_transactions, "deduction_us54d", use_acquisition_date=True), "DeducClaimDtlsUs54EC": _itr2_deduction_claim_detail_rows(all_cg_transactions, "54EC"), "DeducClaimDtlsUs54F": _itr2_deduction_claim_detail_rows(all_cg_transactions, "54F"), "DeducClaimDtlsUs54G": _land_building_54dga_rows(all_cg_transactions, "deduction_us54g", use_acquisition_date=False), "DeducClaimDtlsUs54GA": _land_building_54dga_rows(all_cg_transactions, "deduction_us54ga", use_acquisition_date=False), "TotDeductClaim": _to_rupees(tot_deduct_claim)}, "CurrYrLosses": current_loss_rows, "IncmFromVDATrnsf": _to_rupees(vda_income), "AccruOrRecOfCG": {"ShortTermUnder20Per": _date_range_from_values(buckets["stcg20"]), "ShortTermUnder30Per": _date_range_from_values(buckets["stcg30"]), "ShortTermUnderAppRate": _date_range_from_values(buckets["stcg_app"]), "ShortTermUnderDTAARate": {"DateRange": _DR_RANGE}, "LongTermUnder12_5Per": _date_range_from_values(buckets["ltcg125"]), "LongTermUnderDTAARate": {"DateRange": _DR_RANGE}, "VDATrnsfGainsUnder30Per": _date_range_from_values(buckets["vda"])}, "SumOfCGIncm": _to_rupees(total_cg), "TotScheduleCGFor23": _to_rupees(total_cg)}


def _schedule_ei(typed_input: ITR3Input | None) -> dict[str, Any] | None:
    """Serialize Schedule EI from the prepared agricultural and exempt sources."""
    if typed_input is None:
        return None
    agriculture = typed_input.agricultural_income
    exempt = typed_input.exempt_income
    if agriculture is None and exempt is None:
        return None
    agriculture = agriculture or type("Agriculture", (), {
        "gross_agricultural_income": Decimal("0"),
        "agricultural_deductions": Decimal("0"),
        "unabsorbed_agricultural_loss_previous_8_years": Decimal("0"),
        "land_details": [],
        "agricultural_income_rule_7_and_8": Decimal("0"),
    })()
    exempt = exempt or type("Exempt", (), {
        "ppf_interest": Decimal("0"), "sukanya_samriddhi_interest": Decimal("0"),
        "tax_free_bond_interest": Decimal("0"), "nre_interest": Decimal("0"),
        "share_of_profit_from_firm": Decimal("0"), "other_exempt": Decimal("0"),
        "other_description": None, "other_exempt_entries": [],
        "dtaa_exempt_entries": [], "pti_exempt_income": Decimal("0"),
    })()
    gross = agriculture.gross_agricultural_income
    expense = agriculture.agricultural_deductions
    prior_loss = agriculture.unabsorbed_agricultural_loss_previous_8_years
    interest = (exempt.ppf_interest + exempt.sukanya_samriddhi_interest
                + exempt.tax_free_bond_interest + exempt.nre_interest)
    other = exempt.other_exempt
    dtaa_rows = [{
        "AmountOfIncome": _to_rupees(row.amount),
        "NatureOfIncome": row.nature_of_income,
        "CountryName": row.country_name,
        "CountryCodeExcludingIndia": row.country_code,
        "ArticleOfDTAA": row.dtaa_article,
        "HeadOfIncome": row.head_of_income,
        "TRCFlag": row.tax_residency_certificate,
    } for row in exempt.dtaa_exempt_entries if row.amount > 0]
    other_rows = [{
        "Category": row.category,
        "SubCategory": row.sub_category,
        "Description": row.description,
        "OthAmount": _to_rupees(row.amount),
    } for row in exempt.other_exempt_entries if row.amount > 0]
    if not other_rows and other > 0:
        other_rows = [{
            "Category": "OTH", "Description": exempt.other_description or "Other exempt income",
            "OthAmount": _to_rupees(other),
        }]
    land_rows = [{
        "NameOfDistrict": row.name_of_district,
        "PinCode": int(row.pin_code),
        "MeasurementOfLand": row.measurement_of_land,
        "AgriLandOwnedFlag": row.owned_flag,
        "AgriLandIrrigatedFlag": row.irrigated_flag,
    } for row in agriculture.land_details]
    net_agri = max(Decimal("0"), gross - expense - prior_loss + getattr(agriculture, "agricultural_income_rule_7_and_8", Decimal("0")))
    total = interest + gross - expense - prior_loss + other
    total += getattr(agriculture, "agricultural_income_rule_7_and_8", Decimal("0"))
    total += sum((row.amount for row in exempt.dtaa_exempt_entries), Decimal("0"))
    total += exempt.pti_exempt_income + exempt.share_of_profit_from_firm
    result: dict[str, Any] = {
        "InterestInc": _to_rupees(interest),
        "GrossAgriRecpt": _to_rupees(gross),
        "ExpIncAgri": _to_rupees(expense),
        "UnabAgriLossPrev8": _to_rupees(prior_loss),
        "AgriIncRule7and8": _to_rupees(getattr(agriculture, "agricultural_income_rule_7_and_8", Decimal("0"))),
        "NetAgriIncOrOthrIncRule7": _to_rupees(net_agri),
        "Others": _to_rupees(other + exempt.share_of_profit_from_firm),
        "IncChrgblAsPerDTAA": _to_rupees(sum((row.amount for row in exempt.dtaa_exempt_entries), Decimal("0"))),
        "PassThrIncNotChrgblTax": _to_rupees(exempt.pti_exempt_income),
        "TotalExemptInc": _to_rupees(max(Decimal("0"), total)),
    }
    if land_rows:
        result["ExcNetAgriInc"] = {"ExcNetAgriIncDtls": land_rows}
    if other_rows:
        result["OthersInc"] = {"OthersIncDtls": other_rows}
    if dtaa_rows:
        result["IncNotChrgblAsPerDTAA"] = {"IncNotChrgblAsPerDTAADtls": dtaa_rows}
    return _official_integer_tree(result)



def _schedule_via(result: ITR3Result, typed_input: ITR3Input | None = None) -> dict | None:
    """Build ScheduleVIA from explicit Chapter VI-A claims."""
    source = typed_input.deductions_chapter6a if typed_input else None
    if source is None:
        return None
    fields = {
        "Section80C": source.amount_80c, "Section80CCC": source.amount_80ccc,
        "Section80CCDEmployeeOrSE": source.amount_80ccd1, "Section80CCD1B": source.amount_80ccd1b,
        "Section80CCDEmployer": source.amount_80ccd2,
        "Section80D": source.amount_80d_self_family + source.amount_80d_parents,
        "Section80DD": source.amount_80dd, "Section80DDB": source.amount_80ddb,
        "Section80E": source.amount_80e, "Section80EE": source.amount_80ee,
        "Section80EEA": source.amount_80eea, "Section80EEB": source.amount_80eeb,
        "Section80G": source.amount_80g, "Section80GG": source.amount_80gg,
        "Section80GGA": source.amount_80gga, "Section80GGC": source.amount_80ggc,
        "Section80IA": source.amount_80ia, "Section80IB": source.amount_80ib,
        "Section80IC": source.amount_80ic, "Section80TTA": source.amount_80tta,
        "Section80TTB": source.amount_80ttb, "Section80U": source.amount_80u,
        "AnyOthSec80CCH": source.amount_80cch,
    }
    values = {key: _to_rupees(value) for key, value in fields.items() if value > 0}
    total = sum(values.values())
    if total <= 0:
        return None
    via = {**values, "TotPartBchapterVIA": total, "TotPartCchapterVIA": 0,
           "TotPartCAandDchapterVIA": 0, "TotalChapVIADeductions": total}
    return {"UsrDeductUndChapVIA": dict(via), "DeductUndChapVIA": dict(via)}


def _loan_schedule(source: Any, section: str, interest_key: str) -> dict | None:
    """Build one typed 80E-series schedule, omitting it without matching claims."""
    rows = [row for row in (source.loans if source else []) if row.section == section and row.interest_amount > 0]
    if not rows:
        return None
    details = [{"LoanTknFrom": row.loan_taken_from, "BankOrInstnName": row.lender_name, "LoanAccNoOfBankOrInstnRefNo": row.loan_account_no, "DateofLoan": row.date_of_loan, "TotalLoanAmt": _to_rupees(row.total_loan_amount), "LoanOutstndngAmt": _to_rupees(row.outstanding_amount), interest_key: _to_rupees(row.interest_amount), **({"VehicleRegNo": row.vehicle_reg_no} if section == "80EEB" else {})} for row in rows]
    return {f"Schedule{section}Dtls": details, f"TotalInterest{section}": sum(row[interest_key] for row in details)}


def _schedule_80c(source: Any) -> dict | None:
    """Build Schedule80C from explicit investment rows."""
    rows = [{"IdentificationNo": row.transaction_ref or row.donee_name, "Amount": _to_rupees(row.other_mode_amount + row.cash_amount)} for row in (source.investments_80c if source else []) if row.other_mode_amount + row.cash_amount > 0]
    return {"Schedule80CDtls": rows, "TotalAmt": sum(row["Amount"] for row in rows)} if rows else None


def _schedule_80g(source: Any) -> dict | None:
    """Build Schedule80G with official category nesting and typed rows."""
    if not source or not source.donations_80g:
        return None
    groups = {"100_PERCENT_NO_LIMIT": ("Don100Percent", "TotDon100PercentCash", "TotDon100PercentOtherMode", "TotDon100Percent", "TotEligibleDon100Percent"), "50_NO_LIMIT": ("Don50PercentNoApprReqd", "TotDon50PercentNoApprReqdCash", "TotDon50PercentNoApprReqdOtherMode", "TotDon50PercentNoApprReqd", "TotEligibleDon50Percent"), "100_APPROVAL_REQD": ("Don100PercentApprReqd", "TotDon100PercentApprReqdCash", "TotDon100PercentApprReqdOtherMode", "TotDon100PercentApprReqd", "TotEligibleDon100PercentApprReqd"), "50_APPROVAL_REQD": ("Don50PercentApprReqd", "TotDon50PercentApprReqdCash", "TotDon50PercentApprReqdOtherMode", "TotDon50PercentApprReqd", "TotEligibleDon50PercentApprReqd")}
    out: dict[str, Any] = {}; total_cash = total_other = 0
    for category, rows in ((key, [r for r in source.donations_80g if r.category == key]) for key in groups):
        if not rows: continue
        spec = groups[category]; encoded = []
        for row in rows:
            cash, other = _to_rupees(row.cash_amount), _to_rupees(row.other_mode_amount); gross = cash + other
            encoded.append({"DoneeWithPanName": row.donee_name, "DoneePAN": row.donee_pan, "AddressDetail": {"AddrDetail": row.address_line, "CityOrTownOrDistrict": row.city, "StateCode": row.state_code, "PinCode": row.pin_code}, "DonationAmtCash": cash, "DonationAmtOtherMode": other, "DonationAmt": gross, "EligibleDonationAmt": gross, **({"ArnNbr": row.transaction_ref} if row.transaction_ref else {}), **({"IFSCCode": row.ifsc_code} if row.ifsc_code else {})})
        out[spec[0]] = {"DoneeWithPan": encoded, spec[1]: sum(r["DonationAmtCash"] for r in encoded), spec[2]: sum(r["DonationAmtOtherMode"] for r in encoded), spec[3]: sum(r["DonationAmt"] for r in encoded), spec[4]: sum(r["EligibleDonationAmt"] for r in encoded)}
        total_cash += out[spec[0]][spec[1]]; total_other += out[spec[0]][spec[2]]
    return {**out, "TotalDonationsUs80GCash": total_cash, "TotalDonationsUs80GOtherMode": total_other, "TotalDonationsUs80G": total_cash + total_other, "TotalEligibleDonationsUs80G": total_cash + total_other}


def _schedule_80gga(source: Any) -> dict | None:
    """Build Schedule80GGA from typed donation rows."""
    rows = [{"RelevantClauseUndrDedClaimed": r.category, "NameOfDonee": r.donee_name, "AddressDetail": {"AddrDetail": r.address_line, "CityOrTownOrDistrict": r.city, "StateCode": r.state_code, "PinCode": r.pin_code}, "DoneePAN": r.donee_pan, "DonationAmtCash": _to_rupees(r.cash_amount), "DonationAmtOtherMode": _to_rupees(r.other_mode_amount), "DonationAmt": _to_rupees(r.cash_amount + r.other_mode_amount), "EligibleDonationAmt": _to_rupees(r.cash_amount + r.other_mode_amount)} for r in (source.donations_80gga if source else [])]
    if not rows: return None
    cash, other = sum(r["DonationAmtCash"] for r in rows), sum(r["DonationAmtOtherMode"] for r in rows)
    return {"DonationDtlsSciRsrchRuralDev": rows, "TotalDonationAmtCash80GGA": cash, "TotalDonationAmtOtherMode80GGA": other, "TotalDonationsUs80GGA": cash + other, "TotalEligibleDonationAmt80GGA": cash + other}


def _schedule_80ggc(source: Any) -> dict | None:
    """Build Schedule80GGC from typed political contributions."""
    rows = [{"DonationDate": r.contribution_date, "DonationAmtCash": _to_rupees(r.cash_amount), "DonationAmtOtherMode": _to_rupees(r.other_mode_amount), "DonationAmt": _to_rupees(r.cash_amount + r.other_mode_amount), "EligibleDonationAmt": _to_rupees(r.cash_amount + r.other_mode_amount), "PoliticalPartyName": r.political_party_name, "PoliticalPartyPAN": r.political_party_pan, **({"TransactionRefNum": r.transaction_ref} if r.transaction_ref else {}), **({"IFSCCode": r.ifsc_code} if r.ifsc_code else {})} for r in (source.contributions_80ggc if source else [])]
    if not rows: return None
    cash, other = sum(r["DonationAmtCash"] for r in rows), sum(r["DonationAmtOtherMode"] for r in rows)
    return {"Schedule80GGCDetails": rows, "TotalDonationAmtCash80GGC": cash, "TotalDonationAmtOtherMode80GGC": other, "TotalDonationsUs80GGC": cash + other, "TotalEligibleDonationAmt80GGC": cash + other}


def _partb_ti(result: ITR3Result) -> dict:
    """Serialize Part B-TI from the calculator's typed schedule results.

    The form is a disclosure of the post-set-off heads, not a second tax
    calculation.  Capital-gain buckets therefore come from Schedule CG and
    special-rate income comes from Schedule SI/VDA rather than from the
    aggregate ``capital_gains_income`` shortcut.
    """
    z = Decimal("0")
    pgbp = result.schedules.get("pgbp")
    cg = result.schedules.get("cg")
    os_result = result.schedules.get("os")
    stcg = getattr(cg, "stcg", None)
    ltcg = getattr(cg, "ltcg", None)
    business_total = max(z, result.business_income)
    normal_business = max(z, getattr(pgbp, "non_spec_net_income", business_total))
    speculative = max(z, getattr(pgbp, "speculative_net_income", z))
    specified = max(z, getattr(pgbp, "specified_business_net_income", z))
    stcg_20 = max(z, getattr(stcg, "income_20per", z))
    stcg_30 = max(z, getattr(stcg, "income_30per", z))
    stcg_app = max(z, getattr(stcg, "income_app_rate", z))
    stcg_dtaa = max(z, getattr(stcg, "income_dtaa", z))
    ltcg_125 = max(z, getattr(ltcg, "income_125per_other", z))
    ltcg_112a_gross = max(z, getattr(ltcg, "income_112a", z))
    ltcg_dtaa = max(z, getattr(ltcg, "income_dtaa", z))
    total_stcg = stcg_20 + stcg_30 + stcg_app + stcg_dtaa
    # Part B-TI is a head-wise income disclosure.  Its 112A component is the
    # gross Schedule CG amount; the ₹1.25 lakh threshold belongs to Schedule
    # SI's tax computation and must not be substituted into this disclosure.
    total_ltcg = ltcg_125 + ltcg_112a_gross + ltcg_dtaa
    vda = max(z, result.vda_income)
    total_cg = total_stcg + total_ltcg + vda
    other_income = max(z, result.other_sources_income)
    current_loss = max(z, result.cyla_total_set_off)
    balance_after_cyla = max(z, result.gti_before_loss_setoff - result.cyla_total_set_off)
    si_income = sum((getattr(entry, "taxable_income", z) for entry in getattr(result.schedules.get("si"), "entries", [])), z)
    # Part B-TI item 5b is explicitly ``Income chargeable at special rates
    # (2 of Schedule OS)``.  Schedule SI is broader: it also repeats special
    # rates whose source head is Schedule CG (111A/112A) and Schedule CG's
    # section 115BBH VDA row.  Those amounts already belong to Part B-TI item
    # 4 and must not be duplicated in IncFromOS.  The calculator's remaining
    # supported SI sections (115BB/115BBE/115BBF) are Schedule OS entries.
    os_special_rate_sections = {"115BB", "115BBE", "115BBF", "115BBG", "115BBJ", "115BBA", "115E"}
    os_si_income = sum(
        (
            getattr(entry, "taxable_income", z)
            for entry in getattr(result.schedules.get("si"), "entries", [])
            if getattr(entry, "section", "") in os_special_rate_sections
        ),
        z,
    )
    # ``si_income`` remains the full Schedule SI total for Part B-TI item 11
    # and the official Part B-TTI tax inputs; only the Schedule OS projection
    # uses the narrower subset above.
    si_income = max(z, si_income)
    os_si_income = max(z, os_si_income)
    return {
        "Salaries": _to_rupees(max(z, result.salary_income)),
        "IncomeFromHP": _to_rupees(max(z, result.house_property_income)),
        "ProfBusGain": {
            "ProfGainNoSpecBus": _to_rupees(normal_business),
            "ProfGainSpecBus": _to_rupees(speculative),
            "ProfGainSpecifiedBus": _to_rupees(specified),
            "ProfIncome115BBF": 0,
            "TotProfBusGain": _to_rupees(normal_business + speculative + specified),
        },
        "CapGain": {
            "ShortTerm": {"ShortTerm20Per": _to_rupees(stcg_20), "ShortTerm30Per": _to_rupees(stcg_30), "ShortTermAppRate": _to_rupees(stcg_app), "ShortTermSplRateDTAA": _to_rupees(stcg_dtaa), "TotalShortTerm": _to_rupees(total_stcg)},
            "LongTerm": {"LongTerm12_5Per": _to_rupees(ltcg_125), "LongTermSplRateDTAA": _to_rupees(ltcg_dtaa), "TotalLongTerm": _to_rupees(total_ltcg)},
            "ShortTermLongTermTotal": _to_rupees(total_cg),
            "CapGains30Per115BBH": _to_rupees(vda),
            "TotalCapGains": _to_rupees(total_cg),
        },
        "IncFromOS": {"OtherSrcThanOwnRaceHorse": _to_rupees(other_income), "IncChargblSplRate": _to_rupees(os_si_income), "FromOwnRaceHorse": 0, "TotIncFromOS": _to_rupees(other_income + os_si_income)},
        "CurrentYearLoss": _to_rupees(current_loss),
        "BalanceAfterSetoffLosses": _to_rupees(balance_after_cyla),
        "BroughtFwdLossesSetoff": _to_rupees(max(z, result.bfla_total_set_off)),
        "GrossTotalIncome": _to_rupees(max(z, result.gross_total_income)),
        "IncChargeTaxSplRate111A112": _to_rupees(si_income),
        "IncChargeableTaxSplRates": _to_rupees(si_income),
        "DeductionsUndSchVIADtl": {"PartBchapterVIA": _to_rupees(result.deductions_partb_chapter6a), "PartCchapterVIA": _to_rupees(result.deductions_partc_chapter6a), "TotDeductUndSchVIA": _to_rupees(result.deductions_total)},
        "DeductionsUnder10Aor10AA": _to_rupees(result.deductions_10aa),
        "TotalIncome": _to_rupees_rounded10(result.taxable_income),
        "NetAgricultureIncomeOrOtherIncomeForRate": _to_rupees(result.net_agricultural_income),
        "AggregateIncome": _to_rupees(result.aggregate_income),
        "LossesOfCurrentYearCarriedFwd": _to_rupees(max(z, result.cyla_remaining)),
        "DeemedIncomeUs115JC": _to_rupees(max(z, getattr(getattr(result, "schedules", {}).get("amt"), "adjusted_total_income", z))),
        "TotalTI": _to_rupees_rounded10(result.taxable_income),
    }


def _partb_tti(result: ITR3Result, typed_input: ITR3Input | None = None) -> dict:
    """Serialize Part B-TTI using each calculator liability component."""
    z = Decimal("0")
    total_interest = result.interest_234a + result.interest_234b + result.interest_234c
    tax_on_total = max(z, result.slab_tax + result.special_rate_tax - result.partial_integration_tax)
    tax_after_rebate = max(z, tax_on_total - result.rebate_87a)
    relief = result.relief_89 + result.relief_90_91
    balance_tax = max(z, result.gross_tax_liability - relief)
    accounts = (typed_input.bank_accounts if typed_input else [])
    def get(account: Any, key: str, default: Any = "") -> Any:
        return account.get(key, default) if isinstance(account, dict) else getattr(account, key, default)
    refund_rows = [{"IFSCCode": get(a, "ifscCode", get(a, "ifsc_code", "")), "BankName": get(a, "bankName", get(a, "bank_name", "")), "BankAccountNo": get(a, "accountNumber", get(a, "account_number", "")), "AccountType": get(a, "accountType", get(a, "account_type", "SB")), "UseForRefund": "true" if get(a, "useForRefund", get(a, "is_primary", False)) else "false"} for a in accounts]
    if result.refund_due > 0 and not any(row["UseForRefund"] == "true" for row in refund_rows):
        raise ValueError("A typed refund bank account is required when ITR-3 refund is due")
    amt = result.schedules.get("amt")
    amt_tax = max(z, result.amt_tax)
    gross_tax_pay = {
        "TaxInc17": _to_rupees(result.esop_tax_excluding_new_perquisite) if typed_input and typed_input.esop_deferrals else 0,
        "TaxDeferred17": _to_rupees(result.esop_tax_deferred_this_year) if typed_input and typed_input.esop_deferrals else 0,
        "TaxDeferredPayableCY": _to_rupees(sum((e.tax_payable_current_year for e in typed_input.esop_deferrals), z)) if typed_input and typed_input.esop_deferrals else 0,
    }
    return {"ComputationOfTaxLiability": {"TaxPayableOnTI": {"TaxAtNormalRatesOnAggrInc": _to_rupees(result.slab_tax), "TaxAtSpecialRates": _to_rupees(result.special_rate_tax), "RebateOnAgriInc": _to_rupees(result.partial_integration_tax), "TaxPayableOnTotInc": _to_rupees(tax_on_total), "Rebate87A": _to_rupees(result.rebate_87a), "TaxPayableOnRebate": _to_rupees(tax_after_rebate), "Surcharge25ofSI": 0, "SurchargeOnAboveCrore": _to_rupees(result.surcharge), "Surcharge25ofSIBeforeMarginal": 0, "SurchargeOnAboveCroreBeforeMarginal": 0, "TotalSurcharge": _to_rupees(result.surcharge), "EducationCess": _to_rupees(result.health_education_cess), "GrossTaxLiability": _to_rupees(result.gross_tax_liability)}, "TaxRelief": {"Section89": _to_rupees(result.relief_89), "Section90": _to_rupees(result.relief_90_91), "Section91": 0, "TotTaxRelief": _to_rupees(relief)}, "GrossTaxPay": gross_tax_pay, "GrossTaxPayable": _to_rupees(result.gross_tax_liability), "CreditUS115JD": _to_rupees(result.amtc_utilised), "TaxPayAfterCreditUs115JD": _to_rupees(max(z, balance_tax - result.amtc_utilised)), "NetTaxLiability": _to_rupees(max(z, balance_tax - result.amtc_utilised)), "IntrstPay": {"IntrstPayUs234A": _to_rupees(result.interest_234a), "IntrstPayUs234B": _to_rupees(result.interest_234b), "IntrstPayUs234C": _to_rupees(result.interest_234c), "LateFilingFee234F": _to_rupees(result.late_fee_234f), "FeeFurnish234I": _to_rupees(result.fees_234i), "TotalIntrstPay": _to_rupees(total_interest + result.late_fee_234f + result.fees_234i)}, "TaxPayableOnDeemedTI": {"TaxDeemedTISec115JC": _to_rupees(amt_tax), "SurchargeOnAboveCrore": _to_rupees(getattr(amt, "amt_surcharge", z)), "EducationCess": _to_rupees(getattr(amt, "amt_cess", z)), "TotalTax": _to_rupees(amt_tax)}, "AggregateTaxInterestLiability": _to_rupees(result.net_tax_liability)}, "TaxPaid": {"TaxesPaid": {"AdvanceTax": _to_rupees(result.total_advance_tax), "TDS": _to_rupees(result.total_tds), "TCS": _to_rupees(result.total_tcs), "SelfAssessmentTax": _to_rupees(result.total_self_assessment_tax), "TotalTaxesPaid": _to_rupees(result.total_taxes_paid)}, "BalTaxPayable": _to_rupees_rounded10(result.balance_payable)}, "Refund": {"RefundDue": _to_rupees_rounded10(result.refund_due), "BankAccountDtls": {"BankDtlsFlag": "Y" if refund_rows else "N", "AddtnlBankDetails": refund_rows, "ForeignBankDetails": []}}, "AssetOutIndiaFlag": "YES" if typed_input and typed_input.foreign_assets else "NO"}



# Module-level constants
_DR_RANGE = {"Upto15Of6": 0, "Upto15Of9": 0, "Up16Of9To15Of12": 0,
             "Up16Of12To15Of3": 0, "Up16Of3To31Of3": 0}

# ============================================================================
# Optional sub-schedule stubs
# ============================================================================

def _legacy_schedule_os_placeholder(result: ITR3Result) -> dict:
    _DR = {"DateRange": {"Upto15Of6": 0, "Up16Of6To15Of9": 0, "Up16Of9To15Of12": 0,
                         "Up16Of12To15Of3": 0, "Up16Of3To31Of3": 0}}
    _DR2 = {"DateRange": {"Upto15Of6": 0, "Upto15Of9": 0, "Up16Of9To15Of12": 0,
                           "Up16Of12To15Of3": 0, "Up16Of3To31Of3": 0}}
    _OS_INC_OTHER = {
        "GrossIncChrgblTaxAtAppRate": 0, "DividendGross": 0, "DividendOthThan22e": 0, "Dividend22e": 0, "Dividend22f": 0,
        "InterestGross": 0, "IntrstFrmSavingBank": 0, "IntrstFrmTermDeposit": 0, "IntrstFrmIncmTaxRefund": 0,
        "NatofPassThrghIncome": 0, "IntrstSec10XIFirstProviso": 0, "IntrstSec10XISecondProviso": 0,
        "IntrstSec10XIIFirstProviso": 0, "IntrstSec10XIISecondProviso": 0, "IntrstFrmOthers": 0,
        "RentFromMachPlantBldgs": 0, "Tot562x": 0, "Aggrtvaluewithoutcons562x": 0,
        "Immovpropwithoutcons562x": 0, "Immovpropinadeqcons562x": 0, "Anyotherpropwithoutcons562x": 0,
        "Anyotherpropinadeqcons562x": 0, "FamilyPension": 0, "IncomeNotified89AOS": 0,
        "IncomeNotified89ATypeOS": [], "IncomeNotifiedOther89AOS": 0, "IncomeNotifiedPrYr89AOS": 0,
        "AnyOtherIncome": 0, "OthersInc": {"OthersIncDtls": []}, "IncChargeableSpecialRates": 0,
        "LtryPzzlChrgblUs115BB": 0, "IncChrgblUs115BBJ": 0, "IncChrgblUs115BBE": 0, "CashCreditsUs68": 0,
        "UnExplndInvstmntsUs69": 0, "SumRecdPrYrBusTRU562xii": 0, "SumRecdPrYrLifIns562xiii": 0,
        "UnExplndMoneyUs69A": 0, "UnDsclsdInvstmntsUs69B": 0, "UnExplndExpndtrUs69C": 0,
        "AmtBrwdRepaidOnHundiUs69D": 0, "TaxAccumulatedBalRecPF": {"TotalIncomeBenefit": 0, "TotalTaxBenefit": 0},
        "OthersGross": 0, "OthersGrossDtls": [], "PassThrIncOSChrgblSplRate": 0, "PTIOthersGrossDtls": [],
        "IncChargblSplRateOS": {"TotalAmtTaxUsDTAASchOs": 0},
        "Deductions": {"DeductionUs57iia": 0, "Depreciation": 0, "Expenses": 0, "IntExp57": 0, "TotDeductions": 0, "UsrIntExp57": 0},
        "AmtNotDeductibleUs58": 0, "ProfitChargTaxUs59": 0, "Increliefus89AOS": 0,
        "BalanceNoRaceHorse": _to_rupees(result.other_sources_income),
    }
    return {
        "DividendDTAA": _DR, "DividendIncUs115A1aA": _DR2, "DividendIncUs115A1ai": _DR,
        "DividendIncUs115AC": _DR, "DividendIncUs115ACA": _DR, "DividendIncUs115AD1i": _DR,
        "DividendIncUs115BBDA": _DR, "DividendIncUs115BBDAaiii": _DR, "IncChargeable": 0,
        "IncFrmLottery": _DR, "IncFrmOnGames": _DR2,
        "IncFromOwnHorse": {"Receipts": 0, "DeductSec57": 0, "AmtNotDeductibleUs58": 0, "ProfitChargTaxUs59": 0, "BalanceOwnRaceHorse": 0},
        "IncOthThanOwnRaceHorse": _OS_INC_OTHER, "NOT89A": _DR,
        "TotOthSrcNoRaceHorse": _to_rupees(result.other_sources_income),
    }


def _foreign_schedule(helper: Any, typed_input: ITR3Input | None) -> dict | None:
    """Serialize one shared foreign/disclosure schedule from typed input."""
    if typed_input is None:
        return None
    return helper(typed_input)


def _schedule_tds3_itr3(typed_input: ITR3Input | None) -> dict | None:
    """Serialize TDS3 only when both typed rows and filing details are prepared."""
    if typed_input is None or not typed_input.tds3_entries:
        return None
    return _itr2_schedule_tds3(typed_input)


# ============================================================================
# Public API
# ============================================================================

class _DummyCG:
    class _STCG:
        income_111a = Decimal("0")
        total_stcg = Decimal("0")
    class _LTCG:
        income_112a = Decimal("0")
        taxable_112a = Decimal("0")
        total_ltcg = Decimal("0")
        income_125per_other = Decimal("0")
        income_dtaa = Decimal("0")
    stcg = _STCG()
    ltcg = _LTCG()
    total_capital_gains = Decimal("0")
    vda_income = Decimal("0")


def build_itr3_json(
    result: ITR3Result,
    typed_input: ITR3Input | None = None,
    *,
    pan: str = "AAAPA1234A",
    first_name: str = "",
    middle_name: str = "",
    last_name: str = "",
    dob: str = "1990-01-01",
    residence_no: str = "1",
    residence_name: Optional[str] = None,
    road_or_street: Optional[str] = None,
    locality: str = "Locality",
    city: str = "City",
    state_code: str = "07",
    country_code: str = "91",
    pin_code: Optional[str] = None,
    zip_code: Optional[str] = None,
    mobile_country_code: str = "91",
    residential_status: str = "RES",
    return_file_sec: int = 11,
    mobile_no: Optional[str] = None,
    email: Optional[str] = None,
    aadhaar: Optional[str] = None,
    office_phone_std_code: Optional[str] = None,
    office_phone_no: Optional[str] = None,
    secondary_mobile_country_code: Optional[str] = None,
    secondary_mobile_no: Optional[str] = None,
    secondary_email: Optional[str] = None,
    secondary_add: str = "N",
    alternate_residence_no: Optional[str] = None,
    alternate_residence_name: Optional[str] = None,
    alternate_road_or_street: Optional[str] = None,
    alternate_locality: Optional[str] = None,
    alternate_city: Optional[str] = None,
    alternate_state_code: Optional[str] = None,
    alternate_country_code: Optional[str] = None,
    alternate_pin_code: Optional[str] = None,
    alternate_zip_code: Optional[str] = None,
    assessee_status: str = "I",
    father_name: str = "",
    ver_place: Optional[str] = None,
    tds1_entries: Optional[list[dict]] = None,
    tds2_entries: Optional[list[dict]] = None,
) -> dict:
    """Build an ITR-3 payload; canonical calls must supply typed identity."""
    if typed_input is not None:
        if not typed_input.assessee_pan or not typed_input.assessee_dob:
            raise ValueError("ITR3Input identity requires assessee_pan and assessee_dob for canonical JSON")
        pan = typed_input.assessee_pan
        first_name = typed_input.assessee_first_name
        middle_name = typed_input.assessee_middle_name
        last_name = typed_input.assessee_last_name
        dob = typed_input.assessee_dob
        father_name = typed_input.assessee_father_name
        assessee_status = typed_input.assessee_status
        ver_place = typed_input.verification_place
        residence_no = typed_input.residence_no or ""
        residence_name = typed_input.residence_name
        road_or_street = typed_input.road_or_street
        locality = typed_input.locality or ""
        city = typed_input.city or ""
        state_code = typed_input.state_code or ""
        country_code = typed_input.country_code or ""
        pin_code = typed_input.pin_code
        zip_code = typed_input.zip_code
        mobile_country_code = typed_input.mobile_country_code or "91"
        mobile_no = typed_input.mobile_no
        email = typed_input.email
        aadhaar = typed_input.assessee_aadhaar
        office_phone_std_code = typed_input.office_phone_std_code
        office_phone_no = typed_input.office_phone_no
        secondary_mobile_country_code = typed_input.secondary_mobile_country_code
        secondary_mobile_no = typed_input.secondary_mobile_no
        secondary_email = typed_input.secondary_email
        secondary_add = "Y" if typed_input.secondary_address_different else "N"
        alternate_residence_no = typed_input.alternate_residence_no
        alternate_residence_name = typed_input.alternate_residence_name
        alternate_road_or_street = typed_input.alternate_road_or_street
        alternate_locality = typed_input.alternate_locality
        alternate_city = typed_input.alternate_city
        alternate_state_code = typed_input.alternate_state_code
        alternate_country_code = typed_input.alternate_country_code
        alternate_pin_code = typed_input.alternate_pin_code
        alternate_zip_code = typed_input.alternate_zip_code
        if not typed_input.verification_date:
            raise ValueError("ITR3Input.verification_date is required for canonical JSON")
        required_identity = {
            "residence_no": typed_input.residence_no,
            "locality": typed_input.locality,
            "city": typed_input.city,
            "state_code": typed_input.state_code,
            "country_code": typed_input.country_code,
            "pin_code": typed_input.pin_code,
            "mobile_no": typed_input.mobile_no,
            "email": typed_input.email,
            "verification_place": typed_input.verification_place,
        }
        missing_identity = [name for name, value in required_identity.items() if not value]
        if missing_identity:
            raise ValueError(
                "Canonical ITR3Input is missing required sourced identity fields: "
                + ", ".join(missing_identity)
            )
        if typed_input.secondary_address_different:
            required_alternate = {
                "alternate_residence_no": alternate_residence_no,
                "alternate_locality": alternate_locality,
                "alternate_city": alternate_city,
                "alternate_state_code": alternate_state_code,
            }
            missing_alternate = [name for name, value in required_alternate.items() if not value]
            if missing_alternate:
                raise ValueError(
                    "ITR3Input declares a secondary address (secondary_address_different=True) "
                    "but is missing required alternate-address fields: " + ", ".join(missing_alternate)
                )
        verification_date = typed_input.verification_date
    else:
        verification_date = "2026-07-31"

    assessee_name = f"{first_name} {middle_name} {last_name}".strip()

    cg_data = result.schedules.get("cg")
    if cg_data is None:
        cg_data = _DummyCG()

    itr3: dict[str, Any] = {
        "CreationInfo": _creation_info(),
        "Form_ITR3": _form_itr("ITR-3"),
        # Required schedules
        "PartA_GEN1": _parta_gen1(
            pan=pan, first_name=first_name, middle_name=middle_name, last_name=last_name,
            dob=dob, residence_no=residence_no, residence_name=residence_name,
            road_or_street=road_or_street, locality=locality, city=city,
            state_code=state_code, country_code=country_code,
            pin_code=pin_code, zip_code=zip_code, mobile_country_code=mobile_country_code,
            residential_status=residential_status, return_file_sec=return_file_sec,
            mobile_no=mobile_no, email=email, aadhaar=aadhaar,
            office_phone_std_code=office_phone_std_code, office_phone_no=office_phone_no,
            secondary_mobile_country_code=secondary_mobile_country_code,
            secondary_mobile_no=secondary_mobile_no, secondary_email=secondary_email,
            secondary_add=secondary_add,
            alternate_residence_no=alternate_residence_no,
            alternate_residence_name=alternate_residence_name,
            alternate_road_or_street=alternate_road_or_street,
            alternate_locality=alternate_locality, alternate_city=alternate_city,
            alternate_state_code=alternate_state_code, alternate_country_code=alternate_country_code,
            alternate_pin_code=alternate_pin_code, alternate_zip_code=alternate_zip_code,
            assessee_status=assessee_status,
            typed_input=typed_input,
        ),
        "PartA_GEN2": _parta_gen2(typed_input),
        "ITR3ScheduleBP": _schedule_bp(result, typed_input),
        "PARTA_BS": _parta_bs(typed_input),
        "PARTA_PL": _parta_pl(typed_input),
        "PARTA_OI": _parta_oi(typed_input),
        "PARTA_QD": _parta_qd(typed_input),
        "ManufacturingAccount": _manufacturing_account(typed_input),
        "TradingAccount": _trading_account(typed_input),
        "ScheduleCYLA": _schedule_cyla(result),
        "ScheduleBFLA": _schedule_bfla(result),
        "ScheduleCFL": _schedule_cfl(result, typed_input),
        "PartB-TI": _partb_ti(result),
        "PartB_TTI": _partb_tti(result, typed_input),
        "Verification": _verification(
            assessee_name=assessee_name or "ASSESSEE",
            father_name=father_name or "FATHER",
            pan=pan, place=ver_place,
        ),
        "TaxReturnPreparer": _tax_return_preparer(),
        # Always-present conditional schedules
        "ScheduleS": _schedule_s(result, typed_input),
        "ScheduleHP": _schedule_hp(result, typed_input),
        "ScheduleOS": _schedule_os(result, typed_input),
        # `_schedule_cg_for23_typed` itself already raises a clear
        # ValueError when `typed_input` is None -- the prior code branched
        # to a same-named-minus-"_typed" fallback function that was never
        # actually defined anywhere (a real `NameError` waiting to happen
        # for any legacy caller omitting `typed_input`, confirmed by grep;
        # `tests/validate_schemas.py`'s own `test_itr3()` -- a manual
        # schema-validation script, not pytest-collected in normal runs --
        # does exactly this and would have crashed). Calling the one real
        # function unconditionally removes the dead branch entirely.
        "ScheduleCGFor23": _schedule_cg_for23_typed(cg_data, typed_input),
        **({"Schedule112A": _schedule_112a_115ad(typed_input, "112A")} if _schedule_112a_115ad(typed_input, "112A") else {}),
        **({"Schedule115AD": _schedule_112a_115ad(typed_input, "115AD")} if _schedule_112a_115ad(typed_input, "115AD") else {}),
        **({"ScheduleVDA": _schedule_vda_typed(typed_input)} if _schedule_vda_typed(typed_input) else {}),
        "ScheduleVIA": _schedule_via(result, typed_input),
        **({"ScheduleAMT": _itr2_schedule_amt(result, typed_input)} if typed_input and _itr2_schedule_amt(result, typed_input) else {}),
        **({"ScheduleAMTC": _itr2_schedule_amtc(result, typed_input)} if typed_input and _itr2_schedule_amtc(result, typed_input) else {}),
        **({"Schedule80C": _schedule_80c(typed_input.deduction_details)} if typed_input and _schedule_80c(typed_input.deduction_details) else {}),
        **({"Schedule80G": _schedule_80g(typed_input.deduction_details)} if typed_input and _schedule_80g(typed_input.deduction_details) else {}),
        **({"Schedule80GGA": _schedule_80gga(typed_input.deduction_details)} if typed_input and _schedule_80gga(typed_input.deduction_details) else {}),
        **({"Schedule80GGC": _schedule_80ggc(typed_input.deduction_details)} if typed_input and _schedule_80ggc(typed_input.deduction_details) else {}),
        **({"Schedule80D": _serialize_schedule_model(typed_input.schedule_80d)} if typed_input and typed_input.schedule_80d else {}),
        **({"Schedule80DD": _serialize_schedule_model(typed_input.schedule_80dd)} if typed_input and typed_input.schedule_80dd else {}),
        **({"Schedule80U": _serialize_schedule_model(typed_input.schedule_80u)} if typed_input and typed_input.schedule_80u else {}),
        **({"Schedule80E": _loan_schedule(typed_input.deduction_details, "80E", "Interest80E")} if typed_input and _loan_schedule(typed_input.deduction_details, "80E", "Interest80E") else {}),
        **({"Schedule80EE": _loan_schedule(typed_input.deduction_details, "80EE", "Interest80EE")} if typed_input and _loan_schedule(typed_input.deduction_details, "80EE", "Interest80EE") else {}),
        **({"Schedule80EEA": {**_loan_schedule(typed_input.deduction_details, "80EEA", "Interest80EEA"), "PropStmpDtyVal": _to_rupees(typed_input.deduction_details.stamp_duty_80eea)} } if typed_input and _loan_schedule(typed_input.deduction_details, "80EEA", "Interest80EEA") else {}),
        **({"Schedule80EEB": _loan_schedule(typed_input.deduction_details, "80EEB", "Interest80EEB")} if typed_input and _loan_schedule(typed_input.deduction_details, "80EEB", "Interest80EEB") else {}),
        "ScheduleDEP": _schedule_dep(typed_input),
        "ScheduleDCG": _schedule_dcg(typed_input),
        "ScheduleDPM": _schedule_dpm(typed_input),
        "ScheduleDOA": _schedule_doa(typed_input),
        "ScheduleIF": _schedule_if(result, typed_input),
        "ScheduleSPI": _schedule_spi(typed_input),
        "SchedulePTI": _schedule_pti(typed_input),
        "ScheduleGST": _schedule_gst(typed_input),
        "ScheduleICDS": _schedule_icds(typed_input),
        "ScheduleESR": _schedule_esr(typed_input),
        "ScheduleTPSA": _schedule_tpsa(typed_input),
        **({"Schedule80_IA": _serialize_schedule_model(typed_input.schedule_80ia)} if typed_input and typed_input.schedule_80ia else {}),
        **({"Schedule80_IB": _serialize_schedule_model(typed_input.schedule_80ib)} if typed_input and typed_input.schedule_80ib else {}),
        **({"Schedule80_IC": _serialize_schedule_model(typed_input.schedule_80ic)} if typed_input and typed_input.schedule_80ic else {}),
        **({"Schedule80RA": _serialize_schedule_model(typed_input.schedule_80ra)} if typed_input and typed_input.schedule_80ra else {}),
        **({"Schedule10AA": _serialize_schedule_model(typed_input.schedule_10aa)} if typed_input and typed_input.schedule_10aa else {}),
        "ScheduleSI": _schedule_si(result, typed_input),
        "ScheduleEI": _schedule_ei(typed_input),
        **({"ScheduleFSI": _foreign_schedule(_itr2_schedule_fsi, typed_input)} if _foreign_schedule(_itr2_schedule_fsi, typed_input) else {}),
        **({"ScheduleTR1": _foreign_schedule(_itr2_schedule_tr1, typed_input)} if _foreign_schedule(_itr2_schedule_tr1, typed_input) else {}),
        **({"ScheduleFA": _foreign_schedule(_itr2_schedule_fa, typed_input)} if typed_input and typed_input.foreign_assets else {}),
        **({"ScheduleAL": _foreign_schedule(_itr2_schedule_al, typed_input)} if typed_input and typed_input.asset_liability else {}),
        **({"Schedule5A2014": _foreign_schedule(_itr2_schedule_5a, typed_input)} if typed_input and typed_input.schedule_5a else {}),
        **({"ScheduleESOP": _foreign_schedule(_itr2_schedule_esop, typed_input)} if typed_input and typed_input.esop_deferrals else {}),
        **({"ScheduleIT": _foreign_schedule(_itr2_schedule_it, typed_input)} if typed_input and typed_input.tax_payment_entries else {}),
    }

    # Omit unprepared optional income schedules rather than emitting placeholders.
    for optional_schedule in ("ScheduleS", "ScheduleHP", "ScheduleOS", "ScheduleEI", "ScheduleIF", "ScheduleSPI", "SchedulePTI", "ScheduleVIA", "ScheduleSI", "ScheduleTPSA"):
        if itr3.get(optional_schedule) is None:
            del itr3[optional_schedule]


    # is present. An empty object is not a prepared CBDT schedule and must not
    # be serialized as a placeholder.
    for schedule_name in ("ScheduleDPM", "ScheduleDOA", "ScheduleDEP", "ScheduleDCG", "ScheduleGST", "ScheduleICDS", "ScheduleESR", "ManufacturingAccount", "TradingAccount"):
        if not itr3[schedule_name]:
            del itr3[schedule_name]

    if typed_input is not None:
        for name, helper, rows in (
            ("ScheduleTDS1", _itr2_schedule_tds1, typed_input.tds1_entries),
            ("ScheduleTDS2", _itr2_schedule_tds2, typed_input.tds2_entries),
            ("ScheduleTDS3", _schedule_tds3_itr3, typed_input.tds3_entries),
            ("ScheduleTCS", _itr2_schedule_tcs, typed_input.tcs_entries),
        ):
            if rows:
                payload = helper(typed_input)
                if payload:
                    itr3[name] = payload

    # No synthetic Schedule SI row is emitted when calculated special-rate
    # entries are absent; the optional schedule is omitted instead.

    # Conditional: UD is emitted only when the canonical typed input has
    # prepared rows.  A calculator result alone is not a disclosure source.
    schedule_ud = _schedule_ud(typed_input)
    if schedule_ud is not None:
        itr3["ITR3ScheduleUD"] = schedule_ud

    # ITR-3 Verification requires Date
    itr3["Verification"]["Date"] = verification_date

    # Digest is computed over the COMPLETE ITR document (the whole
    # ``{"ITR": {"ITR3": ...}}`` JSON, matching the ITD reference
    # ``API_Testing/digest_generator.py`` and SOP §5.3 Step 1), with the
    # Digest value replaced by the placeholder "-".
    wrapped = {"ITR": {"ITR3": itr3}}
    itr3["CreationInfo"]["Digest"] = _compute_digest(wrapped)

    return wrapped
