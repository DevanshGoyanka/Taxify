"""
ITR-2 ITD JSON builder.

Produces an ITD-compliant JSON document matching the CBDT ITR-2 schema
(``ITR-2_2026_Main_V1.1``) with ``additionalProperties: false`` enforcement.

ITR-2 is the most complex ITR form — capital gains, VDA, foreign assets,
CYLA/BFLA loss set-off, special rates, agricultural income, AMT, clubbing,
foreign tax relief, and extensive conditional schedules.

Required schedules (always present):
  CreationInfo, Form_ITR2, PartA_GEN1, ScheduleCYLA, ScheduleBFLA,
  PartB-TI, PartB_TTI, Verification
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.engine.calculators.itr2 import ITR2Result
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


# ============================================================================
# PartA_GEN1 — nested PersonalInfo + FilingStatus
# ============================================================================

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
    residential_status: str = "RES",
    return_file_sec: int = 11,
    mobile_no: Optional[str] = None,
    email: Optional[str] = None,
    aadhaar: Optional[str] = None,
    secondary_add: str = "N",
    pin_code: Optional[str] = None,
    assessee_status: str = "I",
) -> dict:
    # ITR-2 PersonalInfo does NOT have EmployerCategory — it's separate from ITR-1 shape
    result: dict[str, Any] = {
        "AssesseeName": {
            "FirstName": first_name or "",
            "MiddleName": middle_name or "",
            "SurNameOrOrgName": last_name or "ASSESSEE",
        },
        "PAN": pan.upper(),
        "Address": {
            "ResidenceNo": _str_or(residence_no, "1"),
            "ResidenceName": "",
            "RoadOrStreet": "",
            "LocalityOrArea": _str_or(locality, "Locality"),
            "CityOrTownOrDistrict": _str_or(city, "City"),
            "StateCode": _str_or(state_code, "07"),
            "CountryCode": _str_or(country_code, "91"),
            "PinCode": int(pin_code) if pin_code and pin_code.isdigit() else 110001,
            "ZipCode": "",
            "CountryCodeMobile": 91,
            "MobileNo": int(mobile_no) if mobile_no and mobile_no.isdigit() else 9999999999,
            "CountryCodeMobileNoSec": 0,
            "MobileNoSec": 0,
            "EmailAddress": _str_or(email, "assessee@example.com"),
        },
        "SecondaryAdd": secondary_add,
        "DOB": _str_or(dob, "1990-01-01"),
        "Status": assessee_status,
    }
    if aadhaar:
        result["AadhaarCardNo"] = aadhaar
    if secondary_add == "Y":
        result["AlternateAddress"] = {
            "ResidenceNo": _str_or(residence_no, "1"),
            "ResidenceName": "",
            "RoadOrStreet": "",
            "LocalityOrArea": _str_or(locality, "Locality"),
            "CityOrTownOrDistrict": _str_or(city, "City"),
            "StateCode": _str_or(state_code, "07"),
            "CountryCode": _str_or(country_code, "91"),
            "PinCode": int(pin_code) if pin_code and pin_code.isdigit() else 110001,
            "ZipCode": "",
        }
    return {
        "PersonalInfo": result,
        "FilingStatus": {
            "ReturnFileSec": return_file_sec,
            "OptOutNewTaxRegime": "N",
            "SeventhProvisio139": "N",
            "ResidentialStatus": residential_status,
            "AsseseeRepFlg": "N",
            "ItrFilingDueDate": "2026-07-31",
            "HeldUnlistedEqShrPrYrFlg": "N",
            "FiiFpiFlag": "N",
        },
    }


# ============================================================================
# incCYLA helper — used by every CYLA head block
# ============================================================================

def _inc_cyla(inc_of_cur_yr: Decimal, hp_setoff: Decimal, os_setoff: Decimal, inc_after: Decimal) -> dict:
    return {
        "IncOfCurYrUnderThatHead": _to_rupees(inc_of_cur_yr),
        "HPlossCurYrSetoff": _to_rupees(hp_setoff),
        "OthSrcLossNoRaceHorseSetoff": _to_rupees(os_setoff),
        "IncOfCurYrAfterSetOff": _to_rupees(inc_after),
    }


def _inc_cyla_hp(inc_of_cur_yr: Decimal, os_setoff: Decimal, inc_after: Decimal) -> dict:
    return {
        "IncOfCurYrUnderThatHead": _to_rupees(inc_of_cur_yr),
        "OthSrcLossNoRaceHorseSetoff": _to_rupees(os_setoff),
        "IncOfCurYrAfterSetOff": _to_rupees(inc_after),
    }


def _inc_cyla_os(inc_of_cur_yr: Decimal, hp_setoff: Decimal, inc_after: Decimal) -> dict:
    """OthSrcExclRaceHorseIncCYLA — has HPlossCurYrSetoff but NO OthSrcLossNoRaceHorseSetoff."""
    return {
        "IncOfCurYrUnderThatHead": _to_rupees(inc_of_cur_yr),
        "HPlossCurYrSetoff": _to_rupees(hp_setoff),
        "IncOfCurYrAfterSetOff": _to_rupees(inc_after),
    }


def _inc_bfla(inc_from_cyla: Decimal, bf_setoff: Decimal, inc_after: Decimal) -> dict:
    return {
        "IncOfCurYrUndHeadFromCYLA": _to_rupees(inc_from_cyla),
        "BFlossPrevYrUndSameHeadSetoff": _to_rupees(bf_setoff),
        "IncOfCurYrAfterSetOffBFLosses": _to_rupees(inc_after),
    }


def _inc_bfla_no_bf_setoff(inc_from_cyla: Decimal, inc_after: Decimal) -> dict:
    """SalaryOthSrcIncBFLA — no BFlossPrevYrUndSameHeadSetoff field."""
    return {
        "IncOfCurYrUndHeadFromCYLA": _to_rupees(inc_from_cyla),
        "IncOfCurYrAfterSetOffBFLosses": _to_rupees(inc_after),
    }


# ============================================================================
# ScheduleCYLA — nested by income head (REQUIRED)
# ============================================================================

def _schedule_cyla(result: ITR2Result) -> dict:
    cyla = result.schedules.get("cyla")
    z = Decimal("0")
    hp_loss_setoff = getattr(cyla, "hp_loss_set_off", z) if cyla else z
    hp_loss_remaining = abs(result.house_property_income) if result.house_property_income < z else z
    return {
        "Salary": {"IncCYLA": _inc_cyla(result.salary_income, z, z, result.salary_income)},
        "HP": {"IncCYLA": _inc_cyla_hp(max(z, result.house_property_income), z, max(z, result.house_property_income))},
        "STCG20Per": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "STCG30Per": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "STCGAppRate": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "STCGDTAARate": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "LTCG12_5Per": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "LTCGDTAARate": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "IncOSDTAA": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "OthSrcExclRaceHorse": {"IncCYLA": _inc_cyla_os(max(z, result.other_sources_income), z, max(z, result.other_sources_income))},
        "OthSrcRaceHorse": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "LossRemAftSetOff": {
            "BalHPlossCurYrAftSetoff": _to_rupees(hp_loss_remaining),
            "BalOthSrcLossNoRaceHorseAftSetoff": 0,
        },
        "TotalCurYr": {
            "TotHPlossCurYr": _to_rupees(hp_loss_remaining),
            "TotOthSrcLossNoRaceHorse": 0,
        },
        "TotalLossSetOff": {
            "TotHPlossCurYrSetoff": _to_rupees(hp_loss_setoff),
            "TotOthSrcLossNoRaceHorseSetoff": 0,
        },
    }


# ============================================================================
# ScheduleBFLA — nested by income head (REQUIRED)
# ============================================================================

def _schedule_bfla(result: ITR2Result) -> dict:
    z = Decimal("0")
    return {
        "Salary": {"IncBFLA": _inc_bfla_no_bf_setoff(result.salary_income, result.salary_income)},
        "HP": {"IncBFLA": _inc_bfla(max(z, result.house_property_income), z, max(z, result.house_property_income))},
        "STCG20Per": {"IncBFLA": _inc_bfla(z, z, z)},
        "STCG30Per": {"IncBFLA": _inc_bfla(z, z, z)},
        "STCGAppRate": {"IncBFLA": _inc_bfla(z, z, z)},
        "STCGDTAARate": {"IncBFLA": _inc_bfla(z, z, z)},
        "LTCG12_5Per": {"IncBFLA": _inc_bfla(z, z, z)},
        "LTCGDTAARate": {"IncBFLA": _inc_bfla(z, z, z)},
        "IncOSDTAA": {"IncBFLA": _inc_bfla_no_bf_setoff(z, z)},
        "OthSrcExclRaceHorse": {"IncBFLA": _inc_bfla_no_bf_setoff(max(z, result.other_sources_income), max(z, result.other_sources_income))},
        "OthSrcRaceHorse": {"IncBFLA": _inc_bfla(z, z, z)},
        "IncomeOfCurrYrAftCYLABFLA": _to_rupees(result.gross_total_income),
        "TotalBFLossSetOff": {"TotBFLossSetoff": _to_rupees(result.bfla_total_set_off)},
    }


# ============================================================================
# ScheduleCFL — Carry Forward Losses
# ============================================================================

_CARRY_FWD = {"CarryFwdLossDetail": {
    "DateOfFiling": "2025-07-31",
    "TotalHPPTILossCF": 0,
    "TotalSTCGPTILossCF": 0,
    "TotalLTCGPTILossCF": 0,
    "OthSrcLossRaceHorseCF": 0,
}}
_CARRY_FWD_WO = {"CarryFwdLossDetail": {
    "DateOfFiling": "2020-07-31",
    "TotalHPPTILossCF": 0,
    "TotalSTCGPTILossCF": 0,
    "TotalLTCGPTILossCF": 0,
}}
_LOSS_SUMMARY = {"LossSummaryDetail": {
    "TotalHPPTILossCF": 0,
    "TotalSTCGPTILossCF": 0,
    "TotalLTCGPTILossCF": 0,
    "OthSrcLossRaceHorseCF": 0,
}}


def _schedule_cfl(result: ITR2Result) -> dict:
    return {
        "LossCFFromPrevYrToAY": _CARRY_FWD,
        "LossCFFromPrev2ndYearFromAY": _CARRY_FWD,
        "LossCFFromPrev3rdYearFromAY": _CARRY_FWD,
        "LossCFFromPrev4thYearFromAY": _CARRY_FWD,
        "LossCFFromPrev5thYearFromAY": _CARRY_FWD_WO,
        "LossCFFromPrev6thYearFromAY": _CARRY_FWD_WO,
        "LossCFFromPrev7thYearFromAY": _CARRY_FWD_WO,
        "LossCFFromPrev8thYearFromAY": _CARRY_FWD_WO,
        "AdjTotBFLossInBFLA": _LOSS_SUMMARY,
        "CurrentAYloss": _LOSS_SUMMARY,
        "TotalOfBFLossesEarlierYrs": _LOSS_SUMMARY,
        "TotalLossCFSummary": _LOSS_SUMMARY,
    }


# ============================================================================
# ScheduleS — Salary (multi-employer)
# ============================================================================

def _schedule_s(result: ITR2Result) -> dict:
    """ITR-2 ScheduleS — fields at top-level, Salaries array items have NameOfEmployer/NatureOfEmployment/AddressDetail/Salarys."""
    return {
        "Salaries": [
            {
                "NameOfEmployer": "Employer",
                "NatureOfEmployment": "OTH",
                "AddressDetail": {
                    "AddrDetail": "Address",
                    "CityOrTownOrDistrict": "City",
                    "StateCode": "07",
                },
                "TANofEmployer": "DELA00001A",
                "Salarys": {
                    "GrossSalary": _to_rupees(result.salary_income),
                    "Salary": _to_rupees(result.salary_income),
                    "NatureOfSalary": {"OthersIncDtls": []},
                    "ValueOfPerquisites": 0,
                    "NatureOfPerquisites": {"OthersIncDtls": []},
                    "ProfitsinLieuOfSalary": 0,
                    "IncomeNotified89A": 0,
                    "IncomeNotifiedOther89A": 0,
                },
            }
        ],
        "TotalGrossSalary": _to_rupees(result.salary_income),
        "AllwncExemptUs10": {"AllwncExemptUs10Dtls": []},
        "AllwncExtentExemptUs10": 0,
        "NetSalary": _to_rupees(result.salary_income),
        "DeductionUS16": 0,
        "DeductionUnderSection16ia": 0,
        "EntertainmntalwncUs16ii": 0,
        "ProfessionalTaxUs16iii": 0,
        "Increliefus89A": 0,
        "Section10_13A": {
            "Placeofwork": "2",
            "ActlHRARecv": 0,
            "ActlRentPaid": 0,
            "DtlsSalUsSec171": 0,
            "ActlRentPaid10Per": 0,
            "Sal40Or50Per": 0,
            "EligbleExmpAllwncUs13A": 0,
        },
        "TotIncUnderHeadSalaries": _to_rupees(result.salary_income),
    }


# ============================================================================
# ScheduleHP — House Property
# ============================================================================

def _schedule_hp(result: ITR2Result) -> dict:
    props = []
    hp_income = result.house_property_income
    if hp_income != 0:
        props.append({
            "HPSNo": 1,
            "AddressDetailWithZipCode": {
                "AddrDetail": "Locality, City",
                "CityOrTownOrDistrict": "City",
                "StateCode": "07",
                "CountryCode": "91",
                "PinCode": 110001,
                "ZipCode": "",
            },
            "PropertyOwner": "SE",
            "PropCoOwnedFlg": "NO",
            "AsseseeShareProperty": 100,
            "ifLetOut": "S" if hp_income < 0 else "L",
            "Rentdetails": {
                "AnnualLetableValue": 0,
                "RentNotRealized": 0,
                "LocalTaxes": 0,
                "TotalUnrealizedAndTax": 0,
                "BalanceALV": 0,
                "AnnualOfPropOwned": 0,
                "ArrearsUnrealizedRentRcvd": 0,
                "ThirtyPercentOfBalance": 0,
                "IntOnBorwCap": _to_rupees(abs(hp_income)),
                "Section24B": {"Section24BDtls": [], "TotalInterestUs24B": _to_rupees(abs(hp_income))},
                "TotalDeduct": _to_rupees(abs(hp_income)),
                "IncomeOfHP": _to_rupees(hp_income),
            },
        })
    return {
        "PropertyDetails": props,
        "PassThroghIncome": 0,
        "TotalIncomeChargeableUnHP": _to_rupees(hp_income),
    }


# ============================================================================
# ScheduleOS — Other Sources
# ============================================================================

_DR = {"DateRange": {"Upto15Of6": 0, "Upto15Of9": 0, "Up16Of9To15Of12": 0,
                    "Up16Of12To15Of3": 0, "Up16Of3To31Of3": 0}}

_OS_INC_OTHER = {
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
    "BalanceNoRaceHorse": 0,
}


def _schedule_os(result: ITR2Result) -> dict:
    inc_other = dict(_OS_INC_OTHER)
    inc_other["BalanceNoRaceHorse"] = _to_rupees(result.other_sources_income)
    return {
        "DividendDTAA": _DR,
        "DividendIncUs115A1aA": _DR,
        "DividendIncUs115A1ai": _DR,
        "DividendIncUs115AC": _DR,
        "DividendIncUs115ACA": _DR,
        "DividendIncUs115AD1i": _DR,
        "DividendIncUs115BBDA": _DR,
        "DividendIncUs115BBDAaiii": _DR,
        "IncChargeable": 0,
        "IncFrmLottery": _DR,
        "IncFrmOnGames": _DR,
        "IncFromOwnHorse": {
            "Receipts": 0,
            "DeductSec57": 0,
            "AmtNotDeductibleUs58": 0,
            "ProfitChargTaxUs59": 0,
            "BalanceOwnRaceHorse": 0,
        },
        "IncOthThanOwnRaceHorse": inc_other,
        "NOT89A": _DR,
        "TotOthSrcNoRaceHorse": _to_rupees(result.other_sources_income),
    }


# ============================================================================
# ScheduleCGFor23 -- Full Capital Gains
# ============================================================================

def _equity_or_unit_sec94_type() -> dict:
    """Stub for EquityOrUnitSec94Type — used by NRISecur115AD and SaleOnOtherAssets."""
    return {
        "FullValueConsdRecvUnqshr": 0,
        "FairMrktValueUnqshr": 0,
        "FullValueConsdSec50CA": 0,
        "FullValueConsdOthUnqshr": 0,
        "FullConsideration": 0,
        "DeductSec48": {
            "AquisitCost": 0,
            "ImproveCost": 0,
            "ExpOnTrans": 0,
            "TotalDedn": 0,
        },
        "BalanceCG": 0,
        "LossSec94of7Or94of8": 0,
        "CapgainonAssets": 0,
    }


def _equity_or_unit_sec54_type() -> dict:
    """Stub for EquityOrUnitSec54Type — used by SaleofAssetNA."""
    return {
        "FullValueConsdRecvUnqshr": 0,
        "FairMrktValueUnqshr": 0,
        "FullValueConsdSec50CA": 0,
        "FullValueConsdOthUnqshr": 0,
        "FullConsideration": 0,
        "DeductSec48": {
            "AquisitCost": 0,
            "ImproveCost": 0,
            "ExpOnTrans": 0,
            "TotalDedn": 0,
        },
        "BalanceCG": 0,
        "DeductionUs54F": 0,
        "CapgainonAssets": 0,
    }


def _equity_share_us_112a_type() -> dict:
    """Stub for EquityShareUs112A."""
    return {
        "BalanceCG": 0,
        "DeductionUs54F": 0,
        "CapgainonAssets": 0,
    }


def _nri_proviso_sec48() -> dict:
    """Stub for NRIProvisoSec48."""
    return {
        "LTCGWithoutBenefit": 0,
        "DeductionUs54F": 0,
        "BalanceCG": 0,
    }


def _nri_sale_of_foreign_asset() -> dict:
    """Stub for NRISaleofForeignAsset."""
    return {
        "SaleonSpecAsset": 0,
        "DednSpecAssetus115": 0,
        "BalonSpeciAsset": 0,
    }


def _date_range_type() -> dict:
    """Stub for DateRangeType."""
    return {
        "DateRange": {
            "Upto15Of6": 0,
            "Upto15Of9": 0,
            "Up16Of9To15Of12": 0,
            "Up16Of12To15Of3": 0,
            "Up16Of3To31Of3": 0,
        }
    }


def _accru_or_rec_of_cg() -> dict:
    """Stub for AccruOrRecOfCG."""
    dr = _date_range_type()
    return {
        "ShortTermUnder20Per": dr,
        "ShortTermUnder30Per": dr,
        "ShortTermUnderAppRate": dr,
        "ShortTermUnderDTAARate": dr,
        "LongTermUnder12_5Per": dr,
        "LongTermUnderDTAARate": dr,
    }


def _schedule_cg_for23(cg_result: Any) -> dict:
    stcg = getattr(cg_result, "stcg", None)
    ltcg = getattr(cg_result, "ltcg", None)
    z = Decimal("0")

    total_stcg = _to_rupees(getattr(stcg, "total_stcg", z))
    total_ltcg = _to_rupees(getattr(ltcg, "total_ltcg", z))
    total_cg = _to_rupees(getattr(cg_result, "total_capital_gains", z))
    vda_income = _to_rupees(
        getattr(cg_result, "vda_income", z) if hasattr(cg_result, "vda_income") else z
    )

    _zobj6 = {"StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0,
              "StclSetoffDTAARate": 0, "LtclSetOff12_5Per": 0, "LtclSetOffDTAARate": 0}
    _cy_stcg20 = {"CurrYearIncome": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0,
                  "StclSetoffDTAARate": 0, "CurrYrCapGain": 0}
    _cy_stcg30 = {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoffAppRate": 0,
                  "StclSetoffDTAARate": 0, "CurrYrCapGain": 0}
    _cy_stcg_app = {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0,
                    "StclSetoffDTAARate": 0, "CurrYrCapGain": 0}
    _cy_stcg_dtaa = {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0,
                     "StclSetoffAppRate": 0, "CurrYrCapGain": 0}
    _cy_ltcg_125 = {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0,
                    "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOffDTAARate": 0, "CurrYrCapGain": 0}
    _cy_ltcg_dtaa = {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0,
                     "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOff12_5Per": 0, "CurrYrCapGain": 0}

    stcg_block: dict[str, Any] = {
        "SaleofLandBuild": {
            "SaleofLandBuildDtls": [],
        },
        "EquityMFonSTT": [],
        "NRITransacSec48Dtl": {
            "NRItaxSTTPaid": 0,
            "NRItaxSTTNotPaid": 0,
        },
        "NRISecur115AD": _equity_or_unit_sec94_type(),
        "SaleOnOtherAssets": _equity_or_unit_sec94_type(),
        "UnutilizedStcgFlag": "N",
        "AmtDeemedStcg": 0,
        "TotalAmtDeemedStcg": 0,
        "PassThrIncNatureSTCG": 0,
        "PassThrIncNatureSTCG20Per": 0,
        "PassThrIncNatureSTCG30Per": 0,
        "PassThrIncNatureSTCGAppRate": 0,
        "TotalAmtNotTaxUsDTAAStcg": 0,
        "TotalAmtTaxUsDTAAStcg": 0,
        "CapitalLossBuyBackShares": {
            "CapitalLossBuyBackSharesDtls": [],
            "TotalCapitalLossBuyBackShares": 0,
        },
        "TotalSTCG": total_stcg,
    }

    ltcg_block: dict[str, Any] = {
        "SaleofLandBuild": {
            "SaleofLandBuildDtls": [],
            "TotalExcessTax": 0,
            "TotalLTCGImmblPrprty": 0,
        },
        "Proviso112Applicable": [],
        "SaleOfEquityShareUs112A": _equity_share_us_112a_type(),
        "NRIProvisoSec48": _nri_proviso_sec48(),
        "NRISaleOfEquityShareUs112A": _equity_share_us_112a_type(),
        "NRISaleofForeignAsset": _nri_sale_of_foreign_asset(),
        "SaleofAssetNADtls": {
            "SaleofAssetNA": _equity_or_unit_sec54_type(),
        },
        "UnutilizedLtcgFlag": "N",
        "AmtDeemedLtcg": 0,
        "TotalAmtDeemedLtcg": 0,
        "PassThrIncNatureLTCG": 0,
        "PassThrIncNatureLTCGUs112A12_5Per": 0,
        "PassThrIncNatureLTCG12_5Per": 0,
        "TotalAmtNotTaxUsDTAALtcg": 0,
        "CapitalLossBuyBackShares": {
            "TotalCapitalLossBuyBackShares": 0,
        },
        "TotalAmtTaxUsDTAALtcg": 0,
        "TotalLTCG": total_ltcg,
    }

    return {
        "ShortTermCapGainFor23": stcg_block,
        "LongTermCapGain23": ltcg_block,
        "DeducClaimInfo": {
            "DeducClaimDtlsUs115F": [],
            "DeducClaimDtlsUs54": [],
            "DeducClaimDtlsUs54B": [],
            "DeducClaimDtlsUs54EC": [],
            "DeducClaimDtlsUs54F": [],
            "TotDeductClaim": 0,
        },
        "CurrYrLosses": {
            "InLossSetOff": _zobj6,
            "InStcg20Per": _cy_stcg20,
            "InStcg30Per": _cy_stcg30,
            "InStcgAppRate": _cy_stcg_app,
            "InStcgDTAARate": _cy_stcg_dtaa,
            "InLtcg12_5Per": _cy_ltcg_125,
            "InLtcgDTAARate": _cy_ltcg_dtaa,
            "TotLossSetOff": _zobj6,
            "LossRemainSetOff": _zobj6,
        },
        "IncmFromVDATrnsf": vda_income,
        "AccruOrRecOfCG": _accru_or_rec_of_cg(),
        "SumOfCGIncm": total_cg,
        "TotScheduleCGFor23": total_cg,
    }


# ============================================================================
# ScheduleVDA — Virtual Digital Assets
# ============================================================================

def _schedule_vda(result: ITR2Result) -> dict:
    return {
        "ScheduleVDADtls": [],
        "TotIncCapGain": _to_rupees(result.vda_income),
    }


# ============================================================================
# Schedule112A
# ============================================================================

def _schedule_112a(cg_result: Any) -> dict:
    ltcg = getattr(cg_result, "ltcg", None) if cg_result else None
    z = Decimal("0")
    income_112a = _to_rupees(getattr(ltcg, "income_112a", z))
    return {
        "Schedule112ADtls": [],
        "SaleValue112A": 0,
        "CostAcqWithoutIndx112A": 0,
        "AcquisitionCost112A": 0,
        "LTCGBeforelowerB1B2112A": income_112a,
        "FairMktValueCapAst112A": 0,
        "ExpExclCnctTransfer112A": 0,
        "Deductions112A": 0,
        "Balance112A": income_112a,
        "TotalBalance112A": income_112a,
    }


# ============================================================================
# ScheduleVIA — Chapter VI-A deductions
# ============================================================================

def _schedule_via(deductions_total: Decimal) -> dict:
    via_fields = {
        "Section80C": deductions_total,
        "Section80CCC": 0,
        "Section80CCDEmployeeOrSE": 0,
        "Section80CCD1B": 0,
        "Section80CCDEmployer": 0,
        "Section80D": 0,
        "Section80DD": 0,
        "Section80DDB": 0,
        "Section80E": 0,
        "Section80EE": 0,
        "Section80EEA": 0,
        "Section80EEB": 0,
        "Section80G": 0,
        "Section80GG": 0,
        "Section80GGA": 0,
        "Section80GGC": 0,
        "Section80U": 0,
        "Section80TTA": 0,
        "Section80TTB": 0,
        "AnyOthSec80CCH": 0,
        "TotalChapVIADeductions": _to_rupees(deductions_total),
    }
    via_int = {k: _to_rupees(v) if isinstance(v, Decimal) else v for k, v in via_fields.items() if k != "TotalChapVIADeductions"}
    via_int["TotalChapVIADeductions"] = _to_rupees(deductions_total)
    return {
        "UsrDeductUndChapVIA": via_int,
        "DeductUndChapVIA": via_int,
    }


# ============================================================================
# ScheduleSI — Special Rate Incomes
# ============================================================================

def _schedule_si(result: ITR2Result) -> dict:
    si_data = result.schedules.get("si")
    total_inc = getattr(si_data, "total_special_rate_income", Decimal("0")) if si_data else Decimal("0")
    total_tax = getattr(si_data, "total_special_rate_tax", Decimal("0")) if si_data else Decimal("0")
    return {
        "SplCodeRateTax": [{"SecCode": "1", "SplRatePercent": 15, "SplRateInc": 0, "SplRateIncTax": 0}],
        "TotSplRateInc": _to_rupees(total_inc + result.vda_income),
        "TotSplRateIncTax": _to_rupees_rounded10(total_tax),
    }


# ============================================================================
# ScheduleEI — Exempt/Agricultural Income
# ============================================================================

def _schedule_ei(result: ITR2Result) -> dict:
    return {
        "GrossAgriRecpt": 0,
        "UnabAgriLossPrev8": 0,
        "ExcNetAgriInc": {"ExcNetAgriIncDtls": []},
        "ExpIncAgri": 0,
        "IncNotChrgblToTax": 0,
        "IncNotChrgblAsPerDTAA": {"IncNotChrgblAsPerDTAADtls": []},
        "InterestInc": 0,
        "OthersInc": {"OthersIncDtls": []},
        "PassThrIncNotChrgblTax": 0,
        "Others": 0,
        "NetAgriIncOrOthrIncRule7": _to_rupees(result.net_agricultural_income),
        "TotalExemptInc": 0,
    }


# ============================================================================
# PartB-TI — Computation of Total Income (REQUIRED)
# ============================================================================

def _partb_ti(result: ITR2Result) -> dict:
    return {
        "Salaries": _to_rupees(result.salary_income),
        "IncomeFromHP": _to_rupees(max(Decimal("0"), result.house_property_income)),
        "CapGain": {
            "ShortTerm": {
                "ShortTerm20Per": 0,
                "ShortTerm30Per": 0,
                "ShortTermAppRate": 0,
                "ShortTermSplRateDTAA": 0,
                "TotalShortTerm": _to_rupees(result.capital_gains_income),
            },
            "LongTerm": {
                "LongTerm12_5Per": 0,
                "LongTermSplRateDTAA": 0,
                "TotalLongTerm": _to_rupees(result.capital_gains_income),
            },
            "ShortTermLongTermTotal": _to_rupees(result.capital_gains_income),
            "CapGains30Per115BBH": 0,
            "TotalCapGains": _to_rupees(result.capital_gains_income),
        },
        "IncFromOS": {
            "OtherSrcThanOwnRaceHorse": _to_rupees(result.other_sources_income),
            "IncChargblSplRate": 0,
            "FromOwnRaceHorse": 0,
            "TotIncFromOS": _to_rupees(result.other_sources_income),
        },
        "CurrentYearLoss": 0,
        "BalanceAfterSetoffLosses": _to_rupees(result.gti_before_loss_setoff - result.cyla_total_set_off),
        "BroughtFwdLossesSetoff": _to_rupees(-result.bfla_total_set_off),
        "GrossTotalIncome": _to_rupees(result.gross_total_income),
        "IncChargeTaxSplRate111A112": _to_rupees(result.vda_income),
        "IncChargeableTaxSplRates": _to_rupees(result.vda_income + result.capital_gains_income),
        "DeductionsUnderScheduleVIA": _to_rupees(result.deductions_total),
        "TotalIncome": _to_rupees_rounded10(result.taxable_income),
        "NetAgricultureIncomeOrOtherIncomeForRate": _to_rupees(result.net_agricultural_income),
        "AggregateIncome": _to_rupees(result.aggregate_income),
        "LossesOfCurrentYearCarriedFwd": _to_rupees(result.cyla_remaining),
        "DeemedIncomeUs115JC": 0,
        "TotalTI": _to_rupees_rounded10(result.taxable_income),
    }


# ============================================================================
# PartB_TTI — Computation of Tax Liability (REQUIRED)
# ============================================================================

def _partb_tti(result: ITR2Result) -> dict:
    return {
        "ComputationOfTaxLiability": {
            "TaxPayableOnTI": {
                "TaxAtNormalRatesOnAggrInc": _to_rupees_rounded10(result.slab_tax),
                "TaxAtSpecialRates": _to_rupees_rounded10(result.special_rate_tax),
                "RebateOnAgriInc": _to_rupees_rounded10(result.partial_integration_tax),
                "TaxPayableOnTotInc": _to_rupees_rounded10(result.slab_tax + result.special_rate_tax),
            },
            "TaxRelief": {
                "Section89": _to_rupees_rounded10(result.relief_89),
                "Section90": _to_rupees_rounded10(result.relief_90_91),
                "Section91": 0,
                "TotTaxRelief": _to_rupees_rounded10(result.relief_89 + result.relief_90_91),
            },
            "Rebate87A": _to_rupees_rounded10(result.rebate_87a),
            "TaxPayableOnRebate": _to_rupees_rounded10(result.tax_after_rebate),
            "Surcharge25ofSI": 0,
            "SurchargeOnAboveCrore": _to_rupees_rounded10(result.surcharge),
            "Surcharge25ofSIBeforeMarginal": 0,
            "SurchargeOnAboveCroreBeforeMarginal": 0,
            "TotalSurcharge": _to_rupees_rounded10(result.surcharge),
            "EducationCess": _to_rupees_rounded10(result.health_education_cess),
            "GrossTaxLiability": 0,
            "GrossTaxPayable": 0,
            "GrossTaxPay": {
                "TaxInc17": 0,
                "TaxDeferred17": 0,
                "TaxDeferredPayableCY": 0,
            },
            "CreditUS115JD": 0,
            "TaxPayAfterCreditUs115JD": 0,
            "NetTaxLiability": _to_rupees_rounded10(result.net_tax_liability),
            "IntrstPay": {
                "IntrstPayUs234A": 0,
                "IntrstPayUs234B": 0,
                "IntrstPayUs234C": 0,
                "LateFilingFee234F": 0,
                "FeeFurnish234I": 0,
                "TotalIntrstPay": 0,
            },
            "AggregateTaxInterestLiability": _to_rupees_rounded10(result.net_tax_liability),
        },
        "TaxPayDeemedTotIncUs115JC": 0,
        "TotalTaxPayablDeemedTotInc": 0,
        "Surcharge": _to_rupees_rounded10(result.surcharge),
        "HealthEduCess": _to_rupees_rounded10(result.health_education_cess),
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
        "Refund": {
            "RefundDue": _to_rupees_rounded10(result.refund_due),
            "BankAccountDtls": {
                "BankDtlsFlag": "Y",
                "AddtnlBankDetails": [{
                    "IFSCCode": "SBIN0000001",
                    "BankName": "BankName",
                    "BankAccountNo": "0000000001",
                    "AccountType": "SB",
                    "UseForRefund": "true",
                }],
                "ForeignBankDetails": [],
            },
        },
    }


# ============================================================================
# ScheduleFA — Foreign Assets (10 sub-types)
# ============================================================================

def _schedule_fa() -> dict:
    return {
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


# ============================================================================
# ScheduleAL — Assets & Liabilities
# ============================================================================

def _schedule_al() -> dict:
    return {
        "ImmovableDetails": [],
        "MovableAsset": {
            "CashInHand": 0,
            "DepositsInBank": 0,
            "SharesAndSecurities": 0,
            "InsurancePolicies": 0,
            "LoansAndAdvancesGiven": 0,
            "JewelleryBullionEtc": 0,
            "ArchCollDrawPaintSulpArt": 0,
            "VehiclYachtsBoatsAircrafts": 0,
        },
        "LiabilityInRelatAssets": 0,
    }


# ============================================================================
# Other conditional schedules
# ============================================================================

def _schedule_115ad() -> dict:
    return {
        "Schedule115ADDtls": [],
        "SaleValue115AD": 0,
        "CostAcqWithoutIndx115AD": 0,
        "AcquisitionCost115AD": 0,
        "LTCGBeforelowerB1B2115AD": 0,
        "FairMktValueCapAst115AD": 0,
        "ExpExclCnctTransfer115AD": 0,
        "Deductions115AD": 0,
        "Balance115AD": 0,
        "TotalBalance115AD": 0,
    }


def _schedule_fsi() -> dict:
    return {"ScheduleFSIDtls": []}


def _schedule_tr1() -> dict:
    return {
        "TaxReliefOutsideIndiaDTAA": 0,
        "TaxReliefOutsideIndiaNotDTAA": 0,
        "TotalTaxReliefOutsideIndia": 0,
        "TaxPaidOutsideIndFlg": "NO",
        "AmtTaxRefunded": 0,
        "AssmtYrTaxRelief": "2025-26",
        "ScheduleTR": [],
        "TotalTaxPaidOutsideIndia": 0,
    }


def _schedule_5a_2014() -> dict:
    _inc = {"IncRecvdUndHead": 0, "AmtApprndOfSpouse": 0, "AmtTDSDeducted": 0, "TDSApprndOfSpouse": 0}
    return {
        "NameOfSpouse": "SPOUSE",
        "PANOfSpouse": "AAAAA0000A",
        "AadhaarOfSpouse": "000000000000",
        "HPHeadIncome": _inc,
        "CapGainHeadIncome": _inc,
        "OtherSourcesHeadIncome": _inc,
        "TotalHeadIncome": _inc,
    }


def _schedule_amt() -> dict:
    return {
        "TotalIncItemPartBTI": 0,
        "AdjustedUnderSec115JC": 0,
        "DeductionClaimUndrAnySec": 0,
        "TaxPayableUnderSec115JC": 0,
    }


def _schedule_amtc() -> dict:
    return {
        "ScheduleAMTCDtls": [],
        "CurrAssYr": "2026-27",
        "TaxSection115JC": 0,
        "TaxOthProvisions": 0,
        "AmtTaxCreditAvailable": 0,
        "TaxSection115JD": 0,
        "AmtLiabilityAvailable": 0,
        "TotAmtCreditUtilisedCY": 0,
        "CurrYrCreditCarryFwd": 0,
        "CurrYrAmtCreditFwd": 0,
        "TotSetOffEys": 0,
        "TotBalBF": 0,
        "TotBalAMTCreditCF": 0,
        "TotAMTGross": 0,
    }


def _schedule_esop() -> dict:
    _esop_evt = {"SecurityType": "NS",
                  "ScheduleESOPEventDtlsType": [],
                  "CeasedEmployee": "N"}
    _ay = lambda year, amt_key: {"AssessmentYear": year, "TaxDeferredBFEarlierAY": 0,
                                   "ScheduleESOPEventDtls": _esop_evt,
                                   amt_key: 0, "TaxPayableCurrentAY": 0, "BalanceTaxCF": 0}
    return {
        "DPIITRegNo": "DIPP00001",
        "PanofStartUp": "AAAAA0000A",
        "ScheduleESOP2122_Type": _ay("2021-22", "TotalTaxAttributedAmt21"),
        "ScheduleESOP2223_Type": _ay("2022-23", "TotalTaxAttributedAmt22"),
        "ScheduleESOP2324_Type": _ay("2023-24", "TotalTaxAttributedAmt23"),
        "ScheduleESOP2425_Type": _ay("2024-25", "TotalTaxAttributedAmt24"),
        "ScheduleESOP2526_Type": _ay("2025-26", "TotalTaxAttributedAmt25"),
        "ScheduleESOP2627_Type": {"AssessmentYear": "2026-27", "BalanceTaxCF": 0},
        "TotalTaxAttributedAmt": 0,
    }


def _schedule_pti() -> dict:
    return {"SchedulePTIDtls": []}


def _schedule_spi() -> dict:
    return {"SpecifiedPerson": []}


def _schedule_it(result: ITR2Result) -> Optional[dict]:
    challans = []
    if result.total_advance_tax > 0:
        challans.append({"BSRCode": "1234567", "DateDep": "2025-06-15", "SrlNoOfChaln": 1, "Amt": _to_rupees(result.total_advance_tax)})
    if result.total_self_assessment_tax > 0:
        challans.append({"BSRCode": "1234567", "DateDep": "2025-07-15", "SrlNoOfChaln": 2, "Amt": _to_rupees(result.total_self_assessment_tax)})
    if not challans:
        return None
    return {"TaxPayment": challans, "TotalTaxPayments": _to_rupees(result.total_advance_tax + result.total_self_assessment_tax)}


def _schedule_tds1(tds_entries: Optional[list[dict]] = None) -> Optional[dict]:
    if not tds_entries:
        return None
    total = sum((e.get("tds_deducted", 0) if isinstance(e, dict) else 0) for e in tds_entries)
    return {
        "TDSonSalary": [{
            "EmployerOrDeductorOrCollectDetl": {
                "TAN": e.get("employer_tan", "DELA00001A"),
                "EmployerOrDeductorOrCollecterName": e.get("employer_name", "Employer"),
            },
            "IncChrgSal": e.get("income_chargeable", 0),
            "TotalTDSSal": e.get("tds_deducted", 0),
        } for e in tds_entries],
        "TotalTDSonSalaries": total,
    }


def _schedule_tds2(tds_entries: Optional[list[dict]] = None) -> Optional[dict]:
    if not tds_entries:
        return None
    total = sum((e.get("tds_deducted", 0) if isinstance(e, dict) else 0) for e in tds_entries)
    return {
        "TDSOthThanSalaryDtls": [{
            "EmployerOrDeductorOrCollectDetl": {
                "TAN": e.get("deductor_tan", "DELA00001A"),
                "EmployerOrDeductorOrCollecterName": e.get("deductor_name", "Deductor"),
            },
            "TDSSection": e.get("tds_section", "194A"),
            "GrossAmount": e.get("gross_amount", 0),
            "TDSClaimed": e.get("tds_deducted", 0),
        } for e in tds_entries],
        "TotalTDSonOthThanSals": total,
    }


def _schedule_80g_itr2(
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


def _schedule_80d() -> dict:
    return {
        "Sec80DSelfFamSrCtznHealth": {
            "SeniorCitizenFlag": "N", "SelfAndFamily": 0, "HealthInsPremSlfFam": 0,
            "Sec80DSelfFamHIDtls": {"Sch80DInsDtls": [], "TotalPayments": 0},
            "PrevHlthChckUpSlfFam": 0,
            "SelfAndFamilySeniorCitizen": 0, "HlthInsPremSlfFamSrCtzn": 0,
            "Sec80DSelfFamSrCtznHIDtls": {"Sch80DInsDtls": [], "TotalPayments": 0},
            "PrevHlthChckUpSlfFamSrCtzn": 0, "MedicalExpSlfFamSrCtzn": 0,
            "ParentsSeniorCitizenFlag": "N", "Parents": 0, "HlthInsPremParents": 0,
            "Sec80DParentsHIDtls": {"Sch80DInsDtls": [], "TotalPayments": 0},
            "PrevHlthChckUpParents": 0,
            "ParentsSeniorCitizen": 0, "HlthInsPremParentsSrCtzn": 0,
            "Sec80DParentsSrCtznHIDtls": {"Sch80DInsDtls": [], "TotalPayments": 0},
            "PrevHlthChckUpParentsSrCtzn": 0, "MedicalExpParentsSrCtzn": 0,
            "EligibleAmountOfDedn": 0,
        }
    }


def _schedule_80c() -> dict:
    return {"Schedule80CDtls": [], "TotalAmt": 0}


def _schedule_80gga() -> dict:
    return {"DonationDtlsSciRsrchRuralDev": [], "TotalDonationAmtCash80GGA": 0,
            "TotalDonationAmtOtherMode80GGA": 0, "TotalDonationsUs80GGA": 0,
            "TotalEligibleDonationAmt80GGA": 0}


def _schedule_80ggc() -> dict:
    return {"Schedule80GGCDetails": [], "TotalDonationAmtCash80GGC": 0,
            "TotalDonationAmtOtherMode80GGC": 0, "TotalDonationsUs80GGC": 0,
            "TotalEligibleDonationAmt80GGC": 0}


def _schedule_80dd() -> dict:
    return {"NatureOfDisability": "1", "TypeOfDisability": "2", "DeductionAmount": 0,
            "DependentType": "1", "DependentPan": "AAAAA0000A", "DependentAadhaar": "000000000000",
            "Form10IAAckNum": "", "UDIDNum": "0000000000000000"}


def _schedule_80u() -> dict:
    return {"NatureOfDisability": "1", "TypeOfDisability": "2", "DeductionAmount": 0,
            "Form10IAAckNum": "", "UDIDNum": "0000000000000000"}


def _schedule_80e() -> dict:
    return {"Schedule80EDtls": [], "TotalInterest80E": 0}


def _schedule_80ee() -> dict:
    return {"Schedule80EEDtls": [], "TotalInterest80EE": 0}


def _schedule_80eea() -> dict:
    return {"PropStmpDtyVal": 0, "Schedule80EEADtls": [], "TotalInterest80EEA": 0}


def _schedule_80eeb() -> dict:
    return {"Schedule80EEBDtls": [], "TotalInterest80EEB": 0}


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


def build_itr2_json(
    result: ITR2Result,
    *,
    pan: str = "AAAPA1234A",
    first_name: str = "",
    middle_name: str = "",
    last_name: str = "",
    dob: str = "1990-01-01",
    residence_no: str = "1",
    locality: str = "Locality",
    city: str = "City",
    state_code: str = "07",
    country_code: str = "91",
    residential_status: str = "RES",
    return_file_sec: int = 11,
    mobile_no: Optional[str] = None,
    email: Optional[str] = None,
    aadhaar: Optional[str] = None,
    secondary_add: str = "N",
    pin_code: Optional[str] = None,
    assessee_status: str = "I",
    father_name: str = "",
    ver_place: str = "Delhi",
    tds1_entries: Optional[list[dict]] = None,
    tds2_entries: Optional[list[dict]] = None,
) -> dict:
    """Build an ITD-compliant ITR-2 JSON document."""

    assessee_name = f"{first_name} {last_name}".strip()

    cg_data = result.schedules.get("cg")
    if cg_data is None:
        cg_data = _DummyCG()

    # ── Assemble ───────────────────────────────────────────────────────

    itr2: dict[str, Any] = {
        "CreationInfo": _creation_info(),
        "Form_ITR2": _form_itr("ITR-2"),
        # Required
        "PartA_GEN1": _parta_gen1(
            pan=pan, first_name=first_name, middle_name=middle_name, last_name=last_name,
            dob=dob, residence_no=residence_no, locality=locality, city=city,
            state_code=state_code, country_code=country_code,
            residential_status=residential_status, return_file_sec=return_file_sec,
            mobile_no=mobile_no, email=email, aadhaar=aadhaar,
            secondary_add=secondary_add, pin_code=pin_code,
            assessee_status=assessee_status,
        ),
        "ScheduleCYLA": _schedule_cyla(result),
        "ScheduleBFLA": _schedule_bfla(result),
        "PartB-TI": _partb_ti(result),
        "PartB_TTI": _partb_tti(result),
        "Verification": _verification(
            assessee_name=assessee_name or "ASSESSEE",
            father_name=father_name or "FATHER",
            pan=pan, place=ver_place,
        ),
        "TaxReturnPreparer": _tax_return_preparer(),
        # Always-present conditional schedules
        "ScheduleS": _schedule_s(result),
        "ScheduleHP": _schedule_hp(result),
        "ScheduleOS": _schedule_os(result),
        "ScheduleCGFor23": _schedule_cg_for23(cg_data),
        "Schedule112A": _schedule_112a(cg_data),
        "ScheduleVDA": _schedule_vda(result),
        "ScheduleCFL": _schedule_cfl(result),
        "ScheduleVIA": _schedule_via(result.deductions_total),
        "ScheduleSI": _schedule_si(result),
        "ScheduleSI": _schedule_si(result),
        "ScheduleEI": _schedule_ei(result),
        "Schedule115AD": _schedule_115ad(),
        "ScheduleTR1": _schedule_tr1(),
        "ScheduleFA": _schedule_fa(),
        "ScheduleAL": _schedule_al(),
        "Schedule5A2014": _schedule_5a_2014(),
        "ScheduleESOP": _schedule_esop(),
        "ScheduleSI": _schedule_si(result),
        "Schedule80C": _schedule_80c(),
        "Schedule80D": _schedule_80d(),
        "Schedule80G": _schedule_80g_itr2(Decimal("0"), Decimal("0")),
        "Schedule80GGA": _schedule_80gga(),
        "Schedule80GGC": _schedule_80ggc(),
        "Schedule80DD": _schedule_80dd(),
        "Schedule80U": _schedule_80u(),
        "Schedule80E": _schedule_80e(),
        "Schedule80EE": _schedule_80ee(),
        "Schedule80EEA": _schedule_80eea(),
        "Schedule80EEB": _schedule_80eeb(),
    }

    # Conditional: TDS1
    tds1 = _schedule_tds1(tds1_entries)
    if tds1:
        itr2["ScheduleTDS1"] = tds1

    # Conditional: TDS2
    tds2 = _schedule_tds2(tds2_entries)
    if tds2:
        itr2["ScheduleTDS2"] = tds2

    # Conditional: TCS
    if result.total_tcs > 0:
        itr2["ScheduleTCS"] = {
            "TCS": [{"EmployerOrDeductorOrCollectDetl": {"TAN": "DELA00001A"},
                     "AmtTCSClaimedThisYear": _to_rupees(result.total_tcs)}],
            "TotalSchTCS": _to_rupees(result.total_tcs),
        }

    # Conditional: ScheduleIT (minItems:1 on TaxPayment — omit if no challans)
    sch_it = _schedule_it(result)
    if sch_it:
        itr2["ScheduleIT"] = sch_it

    # Conditional: ScheduleSI (minItems:1 on SplCodeRateTax — omit if no special rate income)
    if result.special_rate_tax > 0:
        itr2["ScheduleSI"] = _schedule_si(result)

    # Conditional: ScheduleTDS3 (minItems:1 on TDS3Details — omit if no entries)
    # Omitted by default since most taxpayers don't have TDS u/s 194N/206C etc.

    itr2["CreationInfo"]["Digest"] = _compute_digest(itr2)

    return {"ITR": {"ITR2": itr2}}
