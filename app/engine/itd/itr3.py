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


# ============================================================================
# PartA_GEN1 (same as ITR-2)
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
            "IncFrmBusOrProf": "Y",
            "SeventhProvisio139": "N",
            "ResidentialStatus": residential_status,
            "HeldUnlistedEqShrPrYrFlg": "N",
            "ForeignExchangeFlag": "N",
            "FiiFpiFlag": "N",
            "ItrFilingDueDate": "2026-10-31",
        },
    }


# ============================================================================
# PartA_GEN2 — Business-specific (REQUIRED in ITR-3)
# ============================================================================

def _parta_gen2() -> dict:
    return {
        "AuditInfo": {
            "AccountAuditFlag": "N",
            "AuditAccountantFlg": "N",
            "AgrOFAllAmtsRcvd": "Upto5Per",
            "AgrOFAllPayMade": "Upto5Per",
            "IncDclrdUs": "N",
            "LiableSec44AAflg": "N",
            "LiableSec44ABflg": "N",
            "LiableSec92Eflg": "N",
            "AckNum44AB": 0,
        },
        "NatOfBus": {
            "NatureOfBusiness": [{"Code": "00001", "Description": "Business"}],
        },
    }


# ============================================================================
# ITR3ScheduleBP — Core PGBP (REQUIRED)
# ============================================================================

def _schedule_bp(result: ITR3Result) -> dict:
    """Build the required ITR3ScheduleBP from calculator result."""
    pgbp = result.schedules.get("pgbp")
    z = Decimal("0")

    if pgbp:
        non_spec = pgbp.non_spec_net_income
        spec = pgbp.speculative_net_income
        specified = pgbp.specified_net_income
        total_biz = pgbp.total_business_income
    else:
        non_spec = spec = specified = total_biz = z

    _bus_loss_obj = {
        "LossSetOffOnBusLoss": 0,
        "SpeculativeInc": {"BusLossSetoff": 0, "IncOfCurYrUnderThatHead": 0, "IncOfCurYrAfterSetOff": 0},
        "SpecifiedInc": {"BusLossSetoff": 0, "IncOfCurYrUnderThatHead": 0, "IncOfCurYrAfterSetOff": 0},
        "TotLossSetOffOnBus": 0,
        "LossRemainSetOffOnBus": 0,
    }

    _pl_us = {
        "ProfitLossUs44AD": 0, "ProfitLossUs44ADA": 0, "ProfitLossUs44AE": 0,
        "ProfitLossUs44B": 0, "ProfitLossUs44BB": 0, "ProfitLossUs44BBA": 0,
        "ProfitLossUs44BBC": 0, "ProfitLossUs44BBD": 0, "ProfitLossUs44DA": 0,
    }

    _heads_inc = {
        "Salary": 0, "HouseProperty": 0, "CapitalGains": 0,
        "Dividend": 0, "OtherThanDividend": 0, "OtherSources": 0,
        "115BBH": 0, "Us115BBF": 0, "Us115BBG": 0,
    }

    _heads_exp = {
        "Salary": 0, "HouseProperty": 0, "CapitalGains": 0,
        "OtherSources": 0, "115BBH": 0, "Us115BBF": 0, "Us115BBG": 0,
    }

    return {
        "BusSetoffCurrYr": _bus_loss_obj,
        "BusinessIncOthThanSpec": {
            "ProfBfrTaxPL": _to_rupees(non_spec),
            "NetPLFromSpecBus": 0,
            "NetPLFromSpecifiedBus": 0,
            "IncRecCredPLOthHeadDtls": _heads_inc,
            "PLUs44sChapXIIG": 0,
            "ProfitLossInclRefrdSec": _pl_us,
            "TotalProfitFrmActCvrd": 0,
            "ProfitFrmActCvrd": {"ProfitFrmActCvrdUndrRule7": 0, "ProfitFrmActCvrdUndrRule7A": 0, "ProfitFrmActCvrdUndrRule7B1": 0, "ProfitFrmActCvrdUndrRule7B1A": 0, "ProfitFrmActCvrdUndrRule8": 0,},
            "IncCredPL": {
                "FirmShareInc": 0,
                "AOPBOISharInc": 0,
                "OtherExmptIncDtl": {
                    "OperatingDividendName": "Dividend",
                    "OperatingDividendAmt": 0,
                },
                "OthExempInc": 0,
                "TotExempIncPL": 0,
            },
            "IncCredPLNotChargable": 0,
            "BalancePLOthThanSpecBus": 0,
            "ExpDebToPLOthHeadDtls": _heads_exp,
            "ExpDebToPLExemptInc": 0,
            "ExpDebToPLExemptIncDisAllwUs14A": 0,
            "TotExpDebPL": 0,
            "AdjustedPLOthThanSpecBus": 0,
            "DepreciationDebPLCosAct": _to_rupees(getattr(pgbp, "non_spec_depreciation_books", z) if pgbp else z),
            "DepreciationAllowITAct32": {
                "DepreciationAllowUs32_1_ii": 0,
                "DepreciationAllowUs32_1_i": 0,
                "TotDeprAllowITAct": 0,
            },
            "AdjustPLAfterDeprOthSpecInc": 0,
            "AmtDebPLDisallowUs36": 0,
            "AmtDebPLDisallowUs37": 0,
            "AmtDebPLDisallowUs40": 0,
            "AmtDebPLDisallowUs40A": 0,
            "AmtDebPLDisallowUs43B": 0,
            "InterestDisAllowUs23SMEAct": 0,
            "DeemIncUs41": 0,
            "DeemIncUs32AD": 0,
            "DeemIncUs33AB": 0,
            "DeemIncUs33ABA": 0,
            "DeemIncUs35ABA": 0,
            "DeemIncUs35ABB": 0,
            "DeemIncUs40A3A": 0,
            "DeemIncUs72A": 0,
            "DeemIncUs80HHD": 0,
            "DeemIncUs80IA": 0,
            "DeemIncUs3380HHD80IA": 0,
            "DeemIncUs43CA": 0,
            "OthItemDisallowUs28To44DA": 0,
            "AnyOthIncNotInclInExpDisallowPL": 0,
            "AnyOthIncNotInclInSalary": 0,
            "AnyOthIncNotInclInBonus": 0,
            "AnyOthIncNotInclInCommission": 0,
            "AnyOthIncNotInclInInterest": 0,
            "AnyOthIncNotInclInOthers": 0,
            "IncProfDecLossAccICDSAdj": 0,
            "TotAfterAddToPLDeprOthSpecInc": 0,
            "DeductUs32_1_iii": 0,
            "DebPLUs35ExcessAmt": 0,
            "AmtDisallUs40NowAllow": 0,
            "AmtDisallUs43BNowAllow": 0,
            "AnyOthAmtAllDeduct": 0,
            "DecProfIncLossAccICDSAdj": 0,
            "TotDeductionAmts": 0,
            "PLAftAdjDedBusOthThanSpec": 0,
            "DeemedProfitBusUs": {
                "Section44AD": 0, "Section44ADA": 0, "Section44AE": 0,
                "Section44B": 0, "Section44BB": 0, "Section44BBA": 0,
                "Section44BBC": 0, "Section44BBD": 0, "Section44DA": 0,
                "TotDeemedProfitBusUs": 0,
            },
            "NetPLAftAdjBusOthThanSpec": _to_rupees(non_spec),
            "NetPLBusOthThanSpec7A7B7C": _to_rupees(non_spec),
            "ChrgblIncUndrRule7": 0,
            "DeemedChrgblIncUndrRule7A": 0,
            "DeemedChrgblIncUndrRule7B1": 0,
            "DeemedChrgblIncUndrRule7B1A": 0,
            "DeemedChrgblIncUndrRule8": 0,
            "IncomeOtherThanRule": 0,
            "BalIncDeemedFrmAgri": 0,
        },
        "IncChrgUnHdProftGain": _to_rupees(total_biz),
        "SpecBusinessInc": {
            "NetPLFrmSpecBus": _to_rupees(spec),
            "AdditionUs28to44DA": 0,
            "DeductUs28to44DA": 0,
            "AdjustedPLFrmSpecuBus": _to_rupees(spec),
        },
        "SpecifiedBusinessInc": {
            "NetPLFrmSpecifiedBus": _to_rupees(specified),
            "AddSec28to44DA": 0,
            "DedSec28to44DAOTDedSec35AD": 0,
            "DedUs35ADSubSec5Dtls": [],
            "DeductionUs35AD": 0,
            "PLFrmSpecifiedBus": _to_rupees(specified),
            "ProfitLossSpecifiedBusiness": _to_rupees(specified),
        },
    }


# ============================================================================
# PARTA_BS — Balance Sheet (REQUIRED)
# ============================================================================

def _parta_bs() -> dict:
    """PARTA_BS — Balance Sheet (ITR-3 specific structure)."""
    return {
        "FundSrc": {
            "PropFund": {
                "PropCap": 0,
                "ResrNSurp": {"RevResr": 0, "CapResr": 0, "StatResr": 0, "OthResr": 0, "TotResrNSurp": 0},
                "TotPropFund": 0,
            },
            "LoanFunds": {
                "SecrLoan": {
                    "ForeignCurrLoan": 0,
                    "RupeeLoan": {"FrmBank": 0, "FrmOthrs": 0, "TotRupeeLoan": 0},
                    "TotSecrLoan": 0,
                },
                "UnsecrLoan": {"FrmBank": 0, "FrmOthrs": 0, "TotUnSecrLoan": 0},
                "TotLoanFund": 0,
            },
            "DeferredTax": 0,
            "Advances": {"FromPrsn": 0, "FromOthers": 0, "TotalAdvances": 0},
            "TotFundSrc": 0,
        },
        "FundApply": {
            "FixedAsset": {"GrossBlock": 0, "Depreciation": 0, "NetBlock": 0, "CapWrkProg": 0, "TotFixedAsset": 0},
            "Investments": {
                "LongTermInv": {"GovtOthSecQuoted": 0, "GovOthSecUnQoted": 0, "TotLongTermInv": 0},
                "TradeInv": {"EquityShares": 0, "PreferShares": 0, "Debenture": 0, "TotTradeInv": 0},
                "TotInvestments": 0,
            },
            "CurrAssetLoanAdv": {
                "CurrAsset": {
                    "Inventories": {"StoresConsumables": 0, "RawMatl": 0, "StkInProcess": 0,
                                    "FinOrTradGood": 0, "TotInventries": 0},
                    "SndryDebtors": 0,
                    "CashOrBankBal": {"CashinHand": 0, "BankBal": 0, "TotCashOrBankBal": 0},
                    "OthCurrAsset": 0, "TotCurrAsset": 0,
                },
                "LoanAdv": {"AdvRecoverable": 0, "Deposits": 0, "BalWithRevAuth": 0, "TotLoanAdv": 0},
                "TotCurrAssetLoanAdv": 0,
                "CurrLiabilitiesProv": {
                    "CurrLiabilities": {"SundryCred": 0, "LiabForLeasedAsset": 0,
                                         "AccrIntonLeasedAsset": 0, "AccrIntNotDue": 0,
                                         "TotCurrLiabilities": 0},
                    "Provisions": {"ITProvision": 0, "ELSuperAnnGratProvision": 0,
                                    "OthProvision": 0, "TotProvisions": 0},
                    "TotCurrLiabilitiesProvision": 0,
                },
                "NetCurrAsset": 0,
            },
            "MiscAdjust": {"MiscExpndr": 0, "DefTaxAsset": 0, "AccumaltedLosses": 0, "TotMiscAdjust": 0},
            "TotFundApply": 0,
        },
    }


# ============================================================================
# PARTA_PL — Profit & Loss (REQUIRED)
# ============================================================================

def _parta_pl() -> dict:
    """PARTA_PL — Profit & Loss (ITR-3 specific structure)."""
    _obj = {"NonResOtherCompany": 0, "Others": 0, "Total": 0}
    return {
        "GoodsDtlsUs44AE": [],
        "GrossProfit": 0,
        "NetIncomeFrmSpecActivity": 0,
        "NoBooksOfAccPL": {
            "GrossReceipt": 0, "GrsRcptAccPayeeOrBankMode": 0, "GrsRcptOtherMode": 0,
            "GrossProfit": 0, "Expenses": 0, "NetProfit": 0,
            "GrossReceiptPrf": 0, "GrsRcptAccPayeeOrBankModePrf": 0,
            "GrsRcptOtherModePrf": 0, "GrossProfitPrf": 0,
            "ExpensesPrf": 0, "NetProfitPrf": 0, "TotBusinessProfession": 0,
        },
        "TaxProvAppr": {
            "ProvForCurrTax": 0, "ProvDefTax": 0, "ProfitAfterTax": 0,
            "BalBFPrevYr": 0, "AmtAvlAppr": 0, "TrfToReserves": 0,
            "ProprietorAccBalTrf": 0,
        },
        "TurnverFrmSpecActivity": 0,
        "Expenditure": 0,
        "CreditsToPL": {
            "OthIncome": {
                "RentInc": 0, "Comissions": 0, "Dividends": 0, "InterestInc": 0,
                "ProfitOnSaleFixedAsset": 0, "ProfitOnInvChrSTT": 0, "ProfitOnOthInv": 0,
                "ProfitOnCurrFluct": 0, "ProfitOnCnvInvntryToCapAsst": 0, "ProfitOnAgriIncome": 0,
                "LiabilityWrittenBack": 0, "AmtofInterest": 0, "AmtofRem": 0,
                "MiscOthIncome": 0, "TotOthIncome": 0,
            },
            "GrossProfitTrnsfFrmTrdAcc": 0,
            "TotCreditsToPL": 0,
        },
        "DebitsToPL": {
            "Freight": 0, "ConsumptionOfStores": 0, "PowerFuel": 0,
            "RentExpdr": 0, "RepairsBldg": 0, "RepairMach": 0,
            "EmployeeComp": {
                "SalsWages": 0, "Bonus": 0, "MedExpReimb": 0, "LeaveEncash": 0,
                "LeaveTravelBenft": 0, "ContToSuperAnnFund": 0, "ContToPF": 0,
                "ContToGratFund": 0, "ContToOthFund": 0, "OthEmpBenftExpdr": 0,
                "TotEmployeeComp": 0,
            },
            "Insurances": {"MedInsur": 0, "LifeInsur": 0, "KeyManInsur": 0, "OthInsur": 0, "TotInsurances": 0},
            "StaffWelfareExp": 0, "Entertainment": 0, "Hospitality": 0,
            "Conference": 0, "SalePromoExp": 0, "Advertisement": 0,
            "CommissionExpdrDtls": _obj, "RoyalityDtls": _obj, "ProfessionalConstDtls": _obj,
            "HotelBoardLodge": 0, "TravelExp": 0, "ForeignTravelExp": 0,
            "ConveyanceExp": 0, "TelephoneExp": 0, "GuestHouseExp": 0,
            "ClubExp": 0, "FestivalCelebExp": 0, "Scholarship": 0,
            "Gift": 0, "Donation": 0,
            "RatesTaxesPays": {
                "ExciseCustomsVAT": {
                    "UnionExciseDuty": 0, "ServiceTax": 0, "VATorSaleTax": 0,
                    "CentralGoodServiceTax": 0, "StateGoodServiceTax": 0,
                    "IntegratedGoodServiceTax": 0, "UnionTerrGoodServiceTax": 0,
                    "OthDutyTaxCess": 0, "Cess": 0, "TotExciseCustomsVAT": 0,
                },
            },
            "AuditFee": 0, "OtherExpensesDtls": [], "OtherExpenses": 0,
            "BadDebtDtls": {
                "BadDebt": 0,
                "BadDebtAmtDtls": [],
                "BadDebtAmtDtlsTotal": 0,
                "OthersAmtLt1Lakh": 0,
                "OthersPANNotAvlblDtl": [],
                "OthersPANNotAvlblDtlTotal": 0,
            },
            "ProvForBadDoubtDebt": 0, "OthProvisionsExpdr": 0, "PBIDTA": 0,
            "InterestExpdrtDtls": {
                "InterestExpdr": 0,
                "NonResOtherCompany": 0,
                "Others": 0,
            },
            "DepreciationAmort": 0, "PBT": 0,
        },
    }


# ============================================================================
# Other PGBP schedules (optional / conditional)
# ============================================================================

def _schedule_dep() -> dict:
    """ScheduleDEP — Depreciation as per IT Act."""
    return {
        "SummaryFromDeprSch": {
            "BuildingSummary": {
                "DeprBlockTot5Percent": 0, "DeprBlockTot10Percent": 0,
                "DeprBlockTot40Percent": 0, "TotBuildng": 0,
            },
            "PlantMachinerySummary": {
                "DeprBlockTot15Percent": 0, "DeprBlockTot30Percent": 0,
                "DeprBlockTot40Percent": 0, "DeprBlockTot45Percent": 0,
                "TotPlntMach": 0,
            },
            "FurnitureSummary": 0,
            "IntangibleAssetSummary": 0,
            "ShipsSummary": 0,
            "TotalDepreciation": 0,
        },
    }


def _schedule_dcg() -> dict:
    """ScheduleDCG — Deemed Capital Gains on depreciable assets."""
    return {
        "SummaryFromDeprSchCG": {
            "BuildingSummaryCG": {
                "DeprBlockTot5Percent": 0, "DeprBlockTot10Percent": 0,
                "DeprBlockTot40Percent": 0, "TotBuildng": 0,
            },
            "PlantMachinerySummaryCG": {
                "DeprBlockTot15Percent": 0, "DeprBlockTot30Percent": 0,
                "DeprBlockTot40Percent": 0, "DeprBlockTot45Percent": 0,
                "TotPlntMach": 0,
            },
            "FurnitureSummary": 0,
            "IntangibleAssetSummary": 0,
            "ShipsSummary": 0,
            "TotalDepreciation": 0,
        },
    }


def _schedule_if(result: ITR3Result) -> dict:
    """ScheduleIF — Interest from Firms."""
    return {
        "PartnerFirmDetails": [{"FirmName": "Firm", "FirmPAN": "AAAAA0000A", "IsLiableToAudit": "N", "ProfitSharePercent": 100, "ProfitShareAmt": 0, "FirmCapBalOn31Mar": 0}],
        "TotalFirmCapBalOn31Mar": 0,
        "TotalIntrstAmtDueOrRecv": 0,
        "TotalProfitShareAmt": _to_rupees(result.partner_firm_income),
        "TotalRemunernAmtDueOrRecv": 0,
    }


def _schedule_ud() -> dict:
    """ITR3ScheduleUD — Unabsorbed Depreciation."""
    return {
        "CurrAssYr": "2026-27",
        "ScheduleUD": [],
        "TotBFUAllowAmt": 0,
        "TotBFUDepritAmt": 0,
        "TotCurYrAllowSetoffInc": 0,
        "TotCurYrdepritSetoffInc": 0,
        "CurAllowBalCFNY": 0,
        "CurBalCFNY": 0,
        "TotDepritBalCFNY": 0,
        "TotalBalCFNY": 0,
    }


def _schedule_gst() -> dict:
    """ScheduleGST — GST details."""
    return {"TurnoverGrsRcptForGSTIN": []}


def _schedule_icds() -> dict:
    """ScheduleICDS — Income Computation and Disclosure Standards."""
    _icds = {"IncreaseInProfit": 0, "DecreaseInProfit": 0, "NetEffect": 0}
    keys = [
        "AccPolicyAmtDetl", "InventoriesValueDetl", "ConstContractsAmtDetl",
        "RevenueRcgAmtDetl", "TangibleFixedAssetDetl", "ForeignExgRatesDetl",
        "BorrowingCostsDetl", "SecuritiesDetl", "GovtGrantsDetl", "ProvAssetsDetl",
    ]
    result = {k: _icds for k in keys}
    result["TotalNetAmtDetl"] = {"DecreaseInProfit": 0, "IncreaseInProfit": 0}
    return result


def _schedule_esr() -> dict:
    """ScheduleESR — Expenditure on Scientific Research."""
    _d = {"DeductUs35": {"AmtDebPL": 0, "AmtUs35Allowable": 0, "ExcessAmtOverDebPL": 0}}
    return {
        "DeductionUs35": {
            "Section35_1_i": _d, "Section35_1_ii": _d, "Section35_1_iia": _d,
            "Section35_1_iii": _d, "Section35_1_iv": _d,
            "Section35_2AA": _d, "Section35_2AB": _d,
            "Section35_CCC": _d, "Section35_CCD": _d,
            "TotUs35": _d,
        },
    }


def _schedule_80ia() -> dict:
    return {"Sch80SectionCode": "80-IA",
            "DeductUs80_IA_4_iv": {"Sch80LocOrDescCode": "POWER", "Sch80DeductAmtDtls": [{"DeductAmountSec80": 0}]},
            "TotSchedule80_IA": 0}


def _schedule_80ib() -> dict:
    _d = {"Sch80DeductAmtDtls": [{"DeductAmountSec80": 0}]}
    return {"Sch80SectionCode": "80-IB",
            "DeductHousUs80_IB_10_Und": {"Sch80LocOrDescCode": "HOUSING_PROJECT", **_d},
            "DeductMinOilUs80_IB_9_Und": {"Sch80LocOrDescCode": "COMM_PROD", **_d},
            "DeductFoodGrainUs80_IB_11A_Und": {"Sch80LocOrDescCode": "STOR_TRANS", **_d},
            "TotSchedule80_IB": 0}


def _schedule_80ic() -> dict:
    _u = lambda code: {"Sch80LocOrDescCode": code, "Sch80DeductAmtDtls": [{"DeductAmountSec80": 0}]}
    return {"Sch80SectionCode": "80-IC_IE",
            "DeductInNorthEast": {
                "Assam_Und": _u("INDSRTL_ASSAM"),
                "ArunachalPradesh_Und": _u("INDSRTL_ARUNPRADESH"),
                "Manipur_Und": _u("INDSRTL_MANIPUR"),
                "Mizoram_Und": _u("INDSRTL_MIZORAM"),
                "Meghalaya_Und": _u("INDSRTL_MEGHALAYA"),
                "Nagaland_Und": _u("INDSRTL_NAGALND"),
                "Tripura_Und": _u("INDSRTL_TRIPURA"),
                "Sikkim_Und": _u("INDSRTL_SIKKIM"),
                "TotDeductInNorthEast": 0,
            },
            "TotSchedule80_IC": 0}


def _schedule_80ra() -> dict:
    return {"DonationDtlsRsrchAssctn": [], "TotalDonationAmtCash80RA": 0,
            "TotalDonationAmtOtherMode80RA": 0, "TotalDonationsUs80RA": 0,
            "TotalEligibleDonationAmt80RA": 0}


def _schedule_10aa() -> dict:
    return {"DeductSEZ": {"DedUs10Detail": {"Undertaking": {"DedFromUndertakingWithAy": [{"AssmtYrUnit": "2022-23", "DedUs10Sub": 0}]}, "TotalDedUs10Sub": 0}}}


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


def _schedule_cyla(result: ITR3Result) -> dict:
    z = Decimal("0")
    hp_income = max(z, result.house_property_income)
    hp_loss = abs(result.house_property_income) if result.house_property_income < z else z
    os_income = max(z, result.other_sources_income)
    cyla = result.schedules.get("cyla")
    hp_off = getattr(cyla, "hp_loss_set_off", z) if cyla else z
    return {
        "Salary": {"IncCYLA": _inc_cyla(result.salary_income, z, z, result.salary_income)},
        "HP": {"IncCYLA": {"IncOfCurYrUnderThatHead": _to_rupees(hp_income),
                              "IncOfCurYrAfterSetOff": _to_rupees(hp_income)}},
        "STCG20Per": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "STCG30Per": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "STCGAppRate": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "STCGDTAARate": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "LTCG12_5Per": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "LTCGDTAARate": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "IncOSDTAA": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "OthSrcExclRaceHorse": {"IncCYLA": _inc_cyla_os(os_income, z, os_income)},
        "OthSrcRaceHorse": {"IncCYLA": _inc_cyla(z, z, z, z)},
        "LossRemAftSetOff": {"BalHPlossCurYrAftSetoff": _to_rupees(hp_loss), "BalBusLossAftSetoff": 0, "BalOthSrcLossNoRaceHorseAftSetoff": 0},
        "TotalCurYr": {"TotHPlossCurYr": _to_rupees(hp_loss), "TotBusLoss": 0, "TotOthSrcLossNoRaceHorse": 0},
        "TotalLossSetOff": {"TotHPlossCurYrSetoff": _to_rupees(hp_off), "TotBusLossSetoff": 0, "TotOthSrcLossNoRaceHorseSetoff": 0},
    }


def _schedule_bfla(result: ITR3Result) -> dict:
    z = Decimal("0")
    hp_income = max(z, result.house_property_income)
    os_income = max(z, result.other_sources_income)
    return {
        "Salary": {"IncBFLA": _inc_bfla_sal(result.salary_income, result.salary_income)},
        "HP": {"IncBFLA": _inc_bfla(hp_income, z, hp_income)},
        "STCG20Per": {"IncBFLA": _inc_bfla(z, z, z)},
        "STCG30Per": {"IncBFLA": _inc_bfla(z, z, z)},
        "STCGAppRate": {"IncBFLA": _inc_bfla(z, z, z)},
        "STCGDTAARate": {"IncBFLA": _inc_bfla(z, z, z)},
        "LTCG12_5Per": {"IncBFLA": _inc_bfla(z, z, z)},
        "LTCGDTAARate": {"IncBFLA": _inc_bfla(z, z, z)},
        "IncOSDTAA": {"IncBFLA": _inc_bfla_no_bf(z, z)},
        "OthSrcExclRaceHorse": {"IncBFLA": _inc_bfla_no_bf(os_income, os_income)},
        "OthSrcRaceHorse": {"IncBFLA": _inc_bfla(z, z, z)},
        "IncomeOfCurrYrAftCYLABFLA": _to_rupees(result.gross_total_income),
        "TotalBFLossSetOff": {"TotBFLossSetoff": _to_rupees(result.bfla_total_set_off),
                                "TotUnabsorbedDeprSetoff": 0,
                                "TotAllUs35cl4Setoff": 0},
    }


def _schedule_cfl(result: ITR3Result) -> dict:
    """Build ScheduleCFL from computed loss carry-forward data."""
    cfl_entries = result.schedules.get("cfl", [])
    if not cfl_entries:
        return {"LossCF": {"TotLossCF": 0}}

    hp_cf = sum(e.get("loss_cf", 0) for e in cfl_entries if e.get("head") == "HP")
    stcg_cf = sum(e.get("loss_cf", 0) for e in cfl_entries if e.get("head") == "STCG")
    ltcg_cf = sum(e.get("loss_cf", 0) for e in cfl_entries if e.get("head") == "LTCG")
    biz_cf = sum(e.get("loss_cf", 0) for e in cfl_entries
                 if e.get("head") in ("BUS", "NonSpeculative", "Speculative"))
    total_cf = hp_cf + stcg_cf + ltcg_cf + biz_cf

    return {
        "LossCF": {
            "TotLossCF": float(total_cf),
            "TotalHPPTILossCF": float(hp_cf),
            "TotalBusinessLossCF": float(biz_cf),
            "TotalSTCGPTILossCF": float(stcg_cf),
            "TotalLTCGPTILossCF": float(ltcg_cf),
        }
    }


def _schedule_s(result: ITR3Result) -> dict:
    return {
        "Salaries": [{
            "NameOfEmployer": "Employer", "NatureOfEmployment": "OTH",
            "AddressDetail": {"AddrDetail": "Address", "CityOrTownOrDistrict": "City", "StateCode": "07"},
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
        }],
        "TotalGrossSalary": _to_rupees(result.salary_income),
        "AllwncExemptUs10": {"AllwncExemptUs10Dtls": []},
        "AllwncExtentExemptUs10": 0,
        "NetSalary": _to_rupees(result.salary_income),
        "DeductionUS16": 0,
        "DeductionUnderSection16ia": 0,
        "EntertainmntalwncUs16ii": 0,
        "ProfessionalTaxUs16iii": 0,
        "TotIncUnderHeadSalaries": _to_rupees(result.salary_income),
    }


def _schedule_hp(result: ITR3Result) -> dict:
    props = []
    hp_income = result.house_property_income
    if hp_income != 0:
        props.append({
            "HPSNo": 1,
            "AddressDetailWithZipCode": {"AddrDetail": "Locality, City", "CityOrTownOrDistrict": "City",
                                          "StateCode": "07", "CountryCode": "91", "PinCode": 110001, "ZipCode": ""},
            "PropertyOwner": "SE", "PropCoOwnedFlg": "NO", "AsseseeShareProperty": 100,
            "ifLetOut": "S" if hp_income < 0 else "L",
            "Rentdetails": {
                "AnnualLetableValue": 0, "RentNotRealized": 0, "LocalTaxes": 0,
                "TotalUnrealizedAndTax": 0, "BalanceALV": 0, "AnnualOfPropOwned": 0,
                "ArrearsUnrealizedRentRcvd": 0, "ThirtyPercentOfBalance": 0,
                "IntOnBorwCap": _to_rupees(abs(hp_income)),
                "Section24B": {"Section24BDtls": [], "TotalInterestUs24B": _to_rupees(abs(hp_income))},
                "TotalDeduct": _to_rupees(abs(hp_income)), "IncomeOfHP": _to_rupees(hp_income),
            },
        })
    return {"PropertyDetails": props, "PassThroghIncome": 0, "TotalIncomeChargeableUnHP": _to_rupees(hp_income)}


def _schedule_cg_for23(cg_result: Any) -> dict:
    if cg_result is None:
        return {"ShortTermCapGainFor23": {}, "LongTermCapGain23": {}, "DeducClaimInfo": {},
                "CurrYrLosses": {}, "AccruOrRecOfCG": {"ShortTermUnder20Per": {"DateRange": _DR_RANGE}, "ShortTermUnder30Per": {"DateRange": _DR_RANGE},
                                                         "ShortTermUnderAppRate": {"DateRange": _DR_RANGE}, "ShortTermUnderDTAARate": {"DateRange": _DR_RANGE},
                                                         "LongTermUnder12_5Per": {"DateRange": _DR_RANGE}, "LongTermUnderDTAARate": {"DateRange": _DR_RANGE},
                                                         "VDATrnsfGainsUnder30Per": {"DateRange": _DR_RANGE}},
                 "IncmFromVDATrnsf": 0, "SumOfCGIncm": 0, "TotScheduleCGFor23": 0}
    stcg = getattr(cg_result, "stcg", None)
    ltcg = getattr(cg_result, "ltcg", None)
    z = Decimal("0")
    total_stcg = _to_rupees(getattr(stcg, "total_stcg", z))
    total_ltcg = _to_rupees(getattr(ltcg, "total_ltcg", z))
    total_cg = _to_rupees(getattr(cg_result, "total_capital_gains", z))
    vda_inc = _to_rupees(getattr(cg_result, "vda_income", z) if hasattr(cg_result, "vda_income") else z)
    _zobj6 = {"StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0,
              "StclSetoffDTAARate": 0, "LtclSetOff12_5Per": 0, "LtclSetOffDTAARate": 0}
    _cy_stcg = lambda: {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0,
                          "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "CurrYrCapGain": 0}
    return {
        "ShortTermCapGainFor23": {
            "SaleofLandBuild": {"SaleofLandBuildDtls": []}, "EquityMFonSTT": [],
            "NRITransacSec48Dtl": {"NRItaxSTTPaid": 0, "NRItaxSTTNotPaid": 0},
            "NRISecur115AD": {"FullValueConsdRecvUnqshr": 0, "FairMrktValueUnqshr": 0,
                              "FullValueConsdSec50CA": 0, "FullValueConsdOthUnqshr": 0, "FullConsideration": 0,
                              "DeductSec48": {"AquisitCost": 0, "ImproveCost": 0, "ExpOnTrans": 0, "TotalDedn": 0},
                              "BalanceCG": 0, "LossSec94of7Or94of8": 0, "CapgainonAssets": 0,},
            "SaleOnOtherAssets": {"FullValueConsdRecvUnqshr": 0, "FairMrktValueUnqshr": 0,
                                  "FullValueConsdSec50CA": 0, "FullValueConsdOthUnqshr": 0, "FullConsideration": 0,
                                  "DeductSec48": {"AquisitCost": 0, "ImproveCost": 0, "ExpOnTrans": 0, "TotalDedn": 0},
                                  "BalanceCG": 0, "LossSec94of7Or94of8": 0,
                                  "DeemedStcgOnAssets": 0,
                                  "ExemptionOrDednUs54": {"ExemptionGrandTotal": 0},
                                  "CapgainonAssets": 0,},
            "UnutilizedStcgFlag": "N", "AmtDeemedStcg": 0, "TotalAmtDeemedStcg": 0,
            "SlumpSaleInStcg": {"FMV11UAEii": 0, "FMV11UAEiii": 0, "FullConsideration": 0,
                                "NetWorthOfDivision": 0, "CapgainonAssets": 0,},
            "PassThrIncNatureSTCG": 0, "PassThrIncNatureSTCG20Per": 0,
            "PassThrIncNatureSTCG30Per": 0, "PassThrIncNatureSTCGAppRate": 0,
            "TotalAmtNotTaxUsDTAAStcg": 0, "TotalAmtTaxUsDTAAStcg": 0,
            "CapitalLossBuyBackShares": {"CapitalLossBuyBackSharesDtls": [], "TotalCapitalLossBuyBackShares": 0},
            "TotalSTCG": total_stcg,
        },
        "LongTermCapGain23": {
            "SaleofLandBuild": {"SaleofLandBuildDtls": [], "TotalExcessTax": 0, "TotalLTCGImmblPrprty": 0},
            "Proviso112Applicable": [],
            "SaleOfEquityShareUs112A": {"BalanceCG": 0, "DeductionUs54F": 0, "CapgainonAssets": 0},
            "NRIProvisoSec48": {"LTCGWithoutBenefit": 0, "DeductionUs54F": 0, "BalanceCG": 0},
            "NRISaleOfEquityShareUs112A": {"BalanceCG": 0, "DeductionUs54F": 0, "CapgainonAssets": 0},
            "NRISaleofForeignAsset": {"SaleonSpecAsset": 0, "DednSpecAssetus115": 0, "BalonSpeciAsset": 0},
            "SaleofAssetNADtls": {"SaleofAssetNA": {"FullValueConsdRecvUnqshr": 0, "FairMrktValueUnqshr": 0,
                                                      "FullValueConsdSec50CA": 0, "FullValueConsdOthUnqshr": 0,
                                                      "FullConsideration": 0,
                                                      "DeductSec48": {"AquisitCost": 0, "ImproveCost": 0, "ExpOnTrans": 0, "TotalDedn": 0},
                                                      "BalanceCG": 0,
                                                      "ExemptionOrDednUs54": {"ExemptionGrandTotal": 0},
                                                      "CapgainonAssets": 0,}},
            "SlumpSaleInLtcgDtls": {"SlumpSaleInLtcg": {
                "FMV11UAEii": 0, "FMV11UAEiii": 0, "FullConsideration": 0,
                "NetWorthOfDivision": 0, "SlumpBalance": 0,
                "ExemptionOrDednUs54": {"ExemptionGrandTotal": 0},
                "CapgainonAssets": 0,}},
            "UnutilizedLtcgFlag": "N", "AmtDeemedLtcg": 0, "TotalAmtDeemedLtcg": 0,
            "PassThrIncNatureLTCG": 0, "PassThrIncNatureLTCGUs112A12_5Per": 0, "PassThrIncNatureLTCG12_5Per": 0,
            "TotalAmtNotTaxUsDTAALtcg": 0, "CapitalLossBuyBackShares": {"TotalCapitalLossBuyBackShares": 0},
            "TotalAmtTaxUsDTAALtcg": 0, "TotalLTCG": total_ltcg,
        },
        "DeducClaimInfo": {"DeducClaimDtlsUs115F": [], "DeducClaimDtlsUs54": [], "DeducClaimDtlsUs54B": [],
                            "DeducClaimDtlsUs54EC": [], "DeducClaimDtlsUs54F": [], "TotDeductClaim": 0},
        "CurrYrLosses": {
            "InLossSetOff": {"StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOff12_5Per": 0, "LtclSetOffDTAARate": 0},
            "InStcg20Per": {"CurrYearIncome": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "CurrYrCapGain": 0},
            "InStcg30Per": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "CurrYrCapGain": 0},
            "InStcgAppRate": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffDTAARate": 0, "CurrYrCapGain": 0},
            "InStcgDTAARate": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "CurrYrCapGain": 0},
            "InLtcg12_5Per": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOffDTAARate": 0, "CurrYrCapGain": 0},
            "InLtcgDTAARate": {"CurrYearIncome": 0, "StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOff12_5Per": 0, "CurrYrCapGain": 0},
            "TotLossSetOff": {"StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOff12_5Per": 0, "LtclSetOffDTAARate": 0},
            "LossRemainSetOff": {"StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0, "LtclSetOff12_5Per": 0, "LtclSetOffDTAARate": 0},
        },
        "IncmFromVDATrnsf": vda_inc,
        "AccruOrRecOfCG": {"ShortTermUnder20Per": {"DateRange": _DR_RANGE}, "ShortTermUnder30Per": {"DateRange": _DR_RANGE},
                            "ShortTermUnderAppRate": {"DateRange": _DR_RANGE}, "ShortTermUnderDTAARate": {"DateRange": _DR_RANGE},
                            "LongTermUnder12_5Per": {"DateRange": _DR_RANGE}, "LongTermUnderDTAARate": {"DateRange": _DR_RANGE},
                            "VDATrnsfGainsUnder30Per": {"DateRange": _DR_RANGE}},
        "SumOfCGIncm": total_cg, "TotScheduleCGFor23": total_cg,
    }


def _schedule_via(deductions_total: Decimal) -> dict:
    v = _to_rupees(deductions_total)
    via = {"Section80C": v, "Section80CCC": 0, "Section80CCDEmployeeOrSE": 0, "Section80CCD1B": 0,
           "Section80CCDEmployer": 0, "Section80D": 0, "Section80DD": 0, "Section80DDB": 0,
           "Section80E": 0, "Section80EE": 0, "Section80EEA": 0, "Section80EEB": 0,
           "Section80G": 0, "Section80GG": 0, "Section80GGA": 0, "Section80GGC": 0,
           "Section80QQB": 0, "Section80RRB": 0, "Section80TTA": 0, "Section80TTB": 0,
           "Section80U": 0, "AnyOthSec80CCH": 0,
           "TotPartBchapterVIA": v, "TotPartCchapterVIA": 0, "TotPartCAandDchapterVIA": 0,
           "TotalChapVIADeductions": v}
    return {"UsrDeductUndChapVIA": via, "DeductUndChapVIA": via}


def _partb_ti(result: ITR3Result) -> dict:
    return {
        "Salaries": _to_rupees(result.salary_income),
        "IncomeFromHP": _to_rupees(max(Decimal("0"), result.house_property_income)),
        "ProfBusGain": {
            "ProfGainNoSpecBus": _to_rupees(result.business_income),
            "ProfGainSpecBus": 0,
            "ProfGainSpecifiedBus": 0,
            "ProfIncome115BBF": 0,
            "TotProfBusGain": _to_rupees(result.business_income),
        },
        "CapGain": {
            "ShortTerm": {"ShortTerm20Per": 0, "ShortTerm30Per": 0, "ShortTermAppRate": 0,
                          "ShortTermSplRateDTAA": 0, "TotalShortTerm": _to_rupees(result.capital_gains_income)},
            "LongTerm": {"LongTerm12_5Per": 0, "LongTermSplRateDTAA": 0,
                         "TotalLongTerm": _to_rupees(result.capital_gains_income)},
            "ShortTermLongTermTotal": _to_rupees(result.capital_gains_income),
            "CapGains30Per115BBH": 0,
            "TotalCapGains": _to_rupees(result.capital_gains_income),
        },
        "IncFromOS": {"OtherSrcThanOwnRaceHorse": _to_rupees(result.other_sources_income),
                      "IncChargblSplRate": 0, "FromOwnRaceHorse": 0,
                      "TotIncFromOS": _to_rupees(result.other_sources_income)},
        "CurrentYearLoss": 0,
        "BalanceAfterSetoffLosses": _to_rupees(result.gross_total_income),
        "BroughtFwdLossesSetoff": _to_rupees(result.bfla_total_set_off),
        "GrossTotalIncome": _to_rupees(result.gross_total_income),
        "IncChargeTaxSplRate111A112": _to_rupees(result.vda_income),
        "IncChargeableTaxSplRates": _to_rupees(result.vda_income + result.capital_gains_income),
        "DeductionsUndSchVIADtl": {
            "PartBchapterVIA": _to_rupees(result.deductions_total),
            "PartCchapterVIA": 0,
            "TotDeductUndSchVIA": _to_rupees(result.deductions_total),
        },
        "DeductionsUnder10Aor10AA": _to_rupees(result.deductions_10aa),
        "TotalIncome": _to_rupees_rounded10(result.taxable_income),
        "NetAgricultureIncomeOrOtherIncomeForRate": _to_rupees(result.net_agricultural_income),
        "AggregateIncome": _to_rupees(result.aggregate_income),
        "LossesOfCurrentYearCarriedFwd": _to_rupees(result.cyla_remaining),
        "DeemedIncomeUs115JC": 0,
        "TotalTI": _to_rupees_rounded10(result.taxable_income),
    }


def _partb_tti(result: ITR3Result) -> dict:
    return {
        "ComputationOfTaxLiability": {
            "TaxPayableOnTI": {
                "TaxAtNormalRatesOnAggrInc": _to_rupees(result.slab_tax),
                "TaxAtSpecialRates": _to_rupees(result.special_rate_tax),
                "RebateOnAgriInc": _to_rupees(result.partial_integration_tax),
                "TaxPayableOnTotInc": _to_rupees(result.slab_tax + result.special_rate_tax),
                "Rebate87A": _to_rupees(result.rebate_87a),
                "TaxPayableOnRebate": _to_rupees(result.slab_tax + result.special_rate_tax),
                "Surcharge25ofSI": 0,
                "SurchargeOnAboveCrore": 0,
                "Surcharge25ofSIBeforeMarginal": 0,
                "SurchargeOnAboveCroreBeforeMarginal": 0,
                "TotalSurcharge": 0,
                "EducationCess": 0,
                "GrossTaxLiability": _to_rupees(result.slab_tax + result.special_rate_tax),
            },
            "TaxRelief": {"Section89": _to_rupees(result.relief_89),
                          "Section90": _to_rupees(result.relief_90_91),
                          "Section91": 0,
                          "TotTaxRelief": _to_rupees(result.relief_89 + result.relief_90_91)},
            "GrossTaxPay": {"TaxInc17": 0, "TaxDeferred17": 0, "TaxDeferredPayableCY": 0},
            "GrossTaxPayable": 0,
            "CreditUS115JD": 0,
            "TaxPayAfterCreditUs115JD": 0,
            "IntrstPay": {"IntrstPayUs234A": _to_rupees(result.interest_234a),
                          "IntrstPayUs234B": 0, "IntrstPayUs234C": 0,
                          "LateFilingFee234F": _to_rupees(result.late_fee_234f),
                          "FeeFurnish234I": 0, "TotalIntrstPay": _to_rupees(result.total_interest + result.late_fee_234f)},
            "NetTaxLiability": _to_rupees(result.net_tax_liability),
            "TaxPayableOnDeemedTI": {"TaxDeemedTISec115JC": 0, "SurchargeOnAboveCrore": 0, "EducationCess": 0, "TotalTax": 0},
            "AggregateTaxInterestLiability": _to_rupees(result.net_tax_liability),
        },
        "TaxPaid": {"TaxesPaid": {"AdvanceTax": _to_rupees(result.total_advance_tax), "TDS": _to_rupees(result.total_tds),
                                   "TCS": _to_rupees(result.total_tcs),
                                   "SelfAssessmentTax": _to_rupees(result.total_self_assessment_tax),
                                   "TotalTaxesPaid": _to_rupees(result.total_taxes_paid)}},
        "Refund": {"RefundDue": _to_rupees_rounded10(result.refund_due),
                   "BankAccountDtls": {"BankDtlsFlag": "Y",
                                       "AddtnlBankDetails": [{"IFSCCode": "SBIN0000001", "BankName": "BankName",
                                                              "BankAccountNo": "0000000001", "AccountType": "SB",
                                                              "UseForRefund": "true"}], "ForeignBankDetails": []}},
        "AssetOutIndiaFlag": "NO",
    }


# Module-level constants
_DR_RANGE = {"Upto15Of6": 0, "Upto15Of9": 0, "Up16Of9To15Of12": 0,
             "Up16Of12To15Of3": 0, "Up16Of3To31Of3": 0}

# ============================================================================
# Optional sub-schedule stubs
# ============================================================================

def _schedule_os(result: ITR3Result) -> dict:
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
    """Build an ITD-compliant ITR-3 JSON document."""

    assessee_name = f"{first_name} {last_name}".strip()

    cg_data = result.schedules.get("cg")
    if cg_data is None:
        cg_data = _DummyCG()

    itr3: dict[str, Any] = {
        "CreationInfo": _creation_info(),
        "Form_ITR3": _form_itr("ITR-3"),
        # Required schedules
        "PartA_GEN1": _parta_gen1(
            pan=pan, first_name=first_name, middle_name=middle_name, last_name=last_name,
            dob=dob, residence_no=residence_no, locality=locality, city=city,
            state_code=state_code, country_code=country_code,
            residential_status=residential_status, return_file_sec=return_file_sec,
            mobile_no=mobile_no, email=email, aadhaar=aadhaar,
            secondary_add=secondary_add, pin_code=pin_code,
            assessee_status=assessee_status,
        ),
        "PartA_GEN2": _parta_gen2(),
        "ITR3ScheduleBP": _schedule_bp(result),
        "PARTA_BS": _parta_bs(),
        "PARTA_PL": _parta_pl(),
        "ScheduleCYLA": _schedule_cyla(result),
        "ScheduleBFLA": _schedule_bfla(result),
        "ScheduleCFL": _schedule_cfl(result),
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
        "ScheduleVIA": _schedule_via(result.deductions_total),
        "ScheduleDEP": _schedule_dep(),
        "ScheduleDCG": _schedule_dcg(),
        "ScheduleIF": _schedule_if(result),
        "ScheduleGST": _schedule_gst(),
        "ScheduleICDS": _schedule_icds(),
        "ScheduleESR": _schedule_esr(),
        "Schedule80_IA": _schedule_80ia(),
        "Schedule80_IB": _schedule_80ib(),
        "Schedule80_IC": _schedule_80ic(),
        "Schedule80RA": _schedule_80ra(),
        "Schedule10AA": _schedule_10aa(),
        "ScheduleSI": {"SplCodeRateTax": [{"SecCode": "1", "SplRatePercent": 15, "SplRateInc": 0, "SplRateIncTax": 0}],
                       "TotSplRateInc": 0,
                       "TotSplRateIncTax": 0},
        "ScheduleEI": {"ExcNetAgriInc": {"ExcNetAgriIncDtls": []},
                       "OthersInc": {"OthersIncDtls": []},
                       "IncNotChrgblAsPerDTAA": {"IncNotChrgblAsPerDTAADtls": []},
                       "NetAgriIncOrOthrIncRule7": 0,
                       "Others": 0,
                       "TotalExemptInc": 0},
    }

    # Conditional: TDS1
    if tds1_entries:
        total = sum((e.get("tds_deducted", 0) if isinstance(e, dict) else 0) for e in tds1_entries)
        itr3["ScheduleTDS1"] = {
            "TDSonSalary": [{"EmployerOrDeductorOrCollectDetl": {"TAN": e.get("employer_tan", "DELA00001A")},
                             "IncChrgSal": e.get("income_chargeable", 0),
                             "TotalTDSSal": e.get("tds_deducted", 0)} for e in tds1_entries],
            "TotalTDSonSalaries": total}

    # Conditional: TDS2
    if tds2_entries:
        total = sum((e.get("tds_deducted", 0) if isinstance(e, dict) else 0) for e in tds2_entries)
        itr3["ScheduleTDS2"] = {
            "TDSOthThanSalaryDtls": [{"EmployerOrDeductorOrCollectDetl": {"TAN": e.get("deductor_tan", "DELA00001A")},
                                      "TDSSection": e.get("tds_section", "194A"),
                                      "GrossAmount": e.get("gross_amount", 0),
                                      "TDSClaimed": e.get("tds_deducted", 0)} for e in tds2_entries],
            "TotalTDSonOthThanSals": total}

    # Conditional: TCS
    if result.total_tcs > 0:
        itr3["ScheduleTCS"] = {
            "TCS": [{"EmployerOrDeductorOrCollectDetl": {"TAN": "DELA00001A"},
                     "AmtTCSClaimedThisYear": _to_rupees(result.total_tcs)}],
            "TotalSchTCS": _to_rupees(result.total_tcs)}

    # Conditional: SI
    if result.special_rate_tax > 0:
        itr3["ScheduleSI"] = {"SplCodeRateTax": [{"SecCode": "1", "SplRatePercent": 15, "SplRateInc": 0, "SplRateIncTax": 0}],
                               "TotSplRateInc": 0, "TotSplRateIncTax": 0}

    # Conditional: UD
    if result.unabsorbed_dep_setoff > 0:
        itr3["ITR3ScheduleUD"] = _schedule_ud()

    # ITR-3 Verification requires Date
    itr3["Verification"]["Date"] = "2026-07-31"

    # Digest is computed over the COMPLETE ITR document (the whole
    # ``{"ITR": {"ITR3": ...}}`` JSON, matching the ITD reference
    # ``API_Testing/digest_generator.py`` and SOP §5.3 Step 1), with the
    # Digest value replaced by the placeholder "-".
    wrapped = {"ITR": {"ITR3": itr3}}
    itr3["CreationInfo"]["Digest"] = _compute_digest(wrapped)

    return wrapped
