#!/usr/bin/env python3
"""Generate the checked-in frontend ITR-3 coverage manifest and gap reports."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
OUT = FRONTEND / "src" / "domain" / "itr3CoverageManifest.ts"
REPORT_JSON = FRONTEND / "docs" / "itr3-coverage-gaps.json"
REPORT_MD = FRONTEND / "docs" / "itr3-coverage-gaps.md"
SCHEMA = ROOT / "Reference Docs by CBDT & ITD" / "Official JSON Schema" / "ITR-3_2026_Main_V1.1 (2).json"

ROLE_BY_SCHEDULE: dict[str, str] = {
    "CreationInfo": "metadata", "Form_ITR3": "filing", "Verification": "filing",
    "PartA_GEN1": "identity", "PartA_GEN2": "business", "PARTA_BS": "business",
    "ManufacturingAccount": "business", "TradingAccount": "business", "PARTA_PL": "business",
    "PARTA_OI": "business", "PARTA_QD": "business", "ScheduleS": "salary",
    "ScheduleHP": "house-property", "ITR3ScheduleBP": "business", "ScheduleDPM": "business",
    "ScheduleDOA": "business", "ScheduleDEP": "business", "ScheduleDCG": "business",
    "ScheduleESR": "business", "ScheduleCGFor23": "capital-gains", "Schedule112A": "capital-gains",
    "Schedule115AD": "capital-gains", "ScheduleVDA": "capital-gains", "ScheduleOS": "other-sources",
    "ScheduleCYLA": "loss-setoff", "ScheduleBFLA": "loss-setoff", "ScheduleCFL": "loss-setoff",
    "ITR3ScheduleUD": "business", "ScheduleICDS": "business", "Schedule10AA": "deduction",
    "Schedule80G": "deduction", "Schedule80GGA": "deduction", "Schedule80GGC": "deduction",
    "Schedule80C": "deduction", "Schedule80D": "deduction", "Schedule80DD": "deduction",
    "Schedule80U": "deduction", "Schedule80E": "deduction", "Schedule80EE": "deduction",
    "Schedule80EEA": "deduction", "Schedule80EEB": "deduction", "Schedule80RA": "deduction",
    "Schedule80_IA": "deduction", "Schedule80_IB": "deduction", "Schedule80_IC": "deduction",
    "ScheduleVIA": "deduction", "ScheduleAMT": "tax", "ScheduleAMTC": "tax", "ScheduleSI": "tax",
    "ScheduleSPI": "income-attribution", "ScheduleIF": "income-attribution", "ScheduleEI": "other-sources",
    "SchedulePTI": "other-sources", "ScheduleTPSA": "international", "ScheduleFSI": "international",
    "ScheduleTR1": "international", "ScheduleFA": "international", "Schedule5A2014": "income-attribution",
    "ScheduleAL": "assets", "ScheduleGST": "business", "PartB-TI": "tax", "PartB_TTI": "tax",
    "TaxReturnPreparer": "filing", "ScheduleIT": "tax-payment", "ScheduleTDS1": "tax-payment",
    "ScheduleTDS2": "tax-payment", "ScheduleTDS3": "tax-payment", "ScheduleTCS": "tax-payment",
    "ScheduleESOP": "capital-gains",
}

COMPUTED_SCHEDULES = {"ScheduleCYLA", "ScheduleBFLA", "ScheduleCFL", "PartB-TI", "PartB_TTI", "ScheduleAMT", "ScheduleAMTC", "ScheduleSI"}
METADATA_SCHEDULES = {"CreationInfo"}
IMPORTED_SCHEDULES = {"ScheduleTDS1", "ScheduleTDS2", "ScheduleTDS3", "ScheduleTCS"}
BACKEND_ONLY_SCHEDULES = {"Form_ITR3", "Verification", "TaxReturnPreparer"}
BP_COMPUTED_TERMINALS = {
    "TotDeemedProfitBusUs", "TotDeprAllowITAct", "TotExmpInc", "TotExpDebPL",
    "TotProfitFrmActCvrd", "TotLossSetOffOnBus", "TotIncomeOfBusProf", "TotIncomeOfSpecBus",
    "TotIncomeOfSpecifiedBus", "BalancePLOthThanSpecBus", "AdjustedPLOthThanSpecBus",
    "AdjustPLAfterDeprOthSpecInc", "TotAfterAddToPLDeprOthSpecInc", "TotDeductionAmts",
    "TotProfitLossOfBusiness", "IncOfCurYrAfterSetOff", "LossRemainSetOffOnBus",
    "LossSetOffOnBusLoss", "BusLossSetoff", "IncOfCurYrUnderThatHead", "ProfitLossOfSpecBus",
    "ProfitLossOfSpecifiedBus", "TotalProfitFrmActCvrd", "TotExempIncPL", "TotIncFromBusProf",
}

# Official deduction schedules represented by typed editors. Structural nodes are
# backend-only containers; editable scalar leaves are dedicated inputs; displayed
# statutory totals/eligible amounts are backend-computed and must be read-only.
DEDUCTION_SCHEDULES = {
    "Schedule80G", "Schedule80GGA", "Schedule80GGC", "Schedule80D", "Schedule80DD",
    "Schedule80U", "Schedule80E", "Schedule80EE", "Schedule80EEA", "Schedule80EEB",
}
DEDUCTION_COMPUTED_TERMINALS = {
    "EligibleAmountOfDedn", "EligibleDonationAmt", "TotalAmt", "TotalPayments",
    "TotalInterest80E", "TotalInterest80EE", "TotalInterest80EEA", "TotalInterest80EEB",
    "TotalDonationAmtCash80GGA", "TotalDonationAmtOtherMode80GGA", "TotalDonationsUs80GGA",
    "TotalEligibleDonationAmt80GGA", "TotalDonationAmtCash80GGC", "TotalDonationAmtOtherMode80GGC",
    "TotalDonationsUs80GGC", "TotalEligibleDonationAmt80GGC", "TotDon100Percent", "TotDon100PercentCash",
    "TotDon100PercentOtherMode", "TotEligibleDon100Percent", "TotDon50PercentNoApprReqd",
    "TotDon50PercentNoApprReqdCash", "TotDon50PercentNoApprReqdOtherMode", "TotEligibleDon50Percent",
    "TotDon100PercentApprReqd", "TotDon100PercentApprReqdCash", "TotDon100PercentApprReqdOtherMode",
    "TotEligibleDon100PercentApprReqd", "TotDon50PercentApprReqd", "TotDon50PercentApprReqdCash",
    "TotDon50PercentApprReqdOtherMode", "TotEligibleDon50PercentApprReqd", "TotalDonationsUs80GCash",
    "TotalDonationsUs80GOtherMode", "TotalDonationsUs80G", "TotalEligibleDonationsUs80G",
}


def deduction_schedule_disposition(schedule: str, path: str, entry: dict[str, Any]) -> str:
    """Classify the official 80-series schedules by input ownership."""
    if schedule not in DEDUCTION_SCHEDULES:
        return "missing"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in DEDUCTION_COMPUTED_TERMINALS:
        return "computed"
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    return "dedicated-input"



def schedule_ud_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule UD source fields, computed balances, and structural rows."""
    terminal = path.rsplit(".", 1)[-1]
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    if terminal in {"BalCFNY", "AllowBalCFNY", "TotAdjustAccTax115BACAmt", "TotBFUAllowAmt", "TotBFUDepritAmt", "TotCurYrAllowSetoffInc", "TotCurYrdepritSetoffInc", "TotDepritBalCFNY", "TotalBalCFNY"}:
        return "computed"
    if terminal == "CurrAssYr":
        return "backend-only"
    return "dedicated-input"


SCHEDULE_FSI_SOURCE_TERMINALS = {
    "CountryName", "CountryCodeExcludingIndia", "TaxIdentificationNo", "IncFrmOutsideInd",
    "TaxPaidOutsideInd", "DTAAReliefUs90or90A",
}
SCHEDULE_FSI_COMPUTED_TERMINALS = {"TaxPayableinInd", "TaxReliefinInd"}


def schedule_fsi_disposition(schedule: str, path: str, entry: dict[str, Any]) -> str:
    """Classify official FSI/TR1 paths by source ownership and computation.

    Country identity, foreign income, foreign tax, treaty article, and filing
    disclosures are taxpayer/source facts. Indian attributable tax, relief,
    and every statutory aggregate are backend projections. Schema containers
    are never editable JSON blobs.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if schedule == "ScheduleFSI":
        if terminal in SCHEDULE_FSI_COMPUTED_TERMINALS or terminal == "TotalCountryWise":
            return "computed"
        if terminal in SCHEDULE_FSI_SOURCE_TERMINALS:
            return "dedicated-input"
        return "backend-only"
    if terminal in {"TotalTaxPaidOutsideIndia", "TotalTaxReliefOutsideIndia", "TaxReliefOutsideIndiaDTAA", "TaxReliefOutsideIndiaNotDTAA"}:
        return "computed"
    if terminal in {"TaxReliefOutsideIndia", "TaxPaidOutsideIndia"}:
        return "dedicated-input" if terminal == "TaxPaidOutsideIndia" else "computed"
    if terminal in {"TaxPaidOutsideIndFlg", "AmtTaxRefunded", "AssmtYrTaxRelief", "CountryName", "CountryCodeExcludingIndia", "TaxIdentificationNo", "ReliefClaimedUsSection"}:
        return "dedicated-input"
    return "backend-only"
SCHEDULE_EI_COMPUTED_TERMINALS = {
    "NetAgriIncOrOthrIncRule7", "Others", "TotalExemptInc",
    "IncChrgblAsPerDTAA", "PassThrIncNotChrgblTax",
}


def schedule_ei_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify the complete official AY 2026-27 Schedule EI contract.

    Schedule EI source facts (amounts, section/nature, land and treaty evidence)
    are owned by the typed exempt-income editor.  Detail arrays and wrapper
    objects are serialization structure, while net/aggregate exempt-income
    values are calculated by the backend and protected from frontend edits.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_EI_COMPUTED_TERMINALS:
        return "computed"
    return "dedicated-input"


SCHEDULE_OS_COMPUTED_TERMINALS = {
    "GrossIncChrgblTaxAtAppRate", "DividendGross", "InterestGross", "Tot562x",
    "Aggrtvaluewithoutcons562x", "IncChargeableSpecialRates", "OthersGross",
    "PassThrIncOSChrgblSplRate", "TotalAmtTaxUsDTAASchOs", "TotDeductions",
    "AmtNotDeductibleUs58", "ProfitChargTaxUs59", "Increliefus89AOS",
    "BalanceNoRaceHorse", "TotOthSrcNoRaceHorse", "BalanceOwnRaceHorse", "IncChargeable",
}


SCHEDULE_ESR_COMPUTED_TERMINALS = {
    "AmtUs35Allowable", "ExcessAmtOverDebPL",
}


SCHEDULE_VDA_SOURCE_TERMINALS = {
    "DateofAcquisition", "DateofTransfer", "AcquisitionCost", "ConsidReceived", "HeadUndIncTaxed",
}
SCHEDULE_VDA_COMPUTED_TERMINALS = {"IncomeFromVDA", "TotIncBusiness", "TotIncCapGain"}


def schedule_vda_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify VDA source facts versus backend gains under section 115BBH."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_VDA_COMPUTED_TERMINALS:
        return "computed"
    if terminal in SCHEDULE_VDA_SOURCE_TERMINALS:
        return "dedicated-input"
    return "backend-only"
SCHEDULE_DCG_COMPUTED_TERMINALS = {
    "DeprBlockTot5Percent", "DeprBlockTot10Percent", "DeprBlockTot40Percent", "TotBuildng",
    "DeprBlockTot15Percent", "DeprBlockTot30Percent", "DeprBlockTot45Percent", "TotPlntMach",
    "FurnitureSummary", "IntangibleAssetSummary", "ShipsSummary", "TotalDepreciation",
}


def schedule_dcg_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule DCG as a backend-owned section 50 projection.

    Schedule DCG is not a taxpayer-entered transaction ledger: its required
    block totals and optional asset-category summaries are produced from the
    depreciation schedules and capital-gains calculation.  Objects are schema
    structure; every scalar leaf is therefore protected computed output.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_DCG_COMPUTED_TERMINALS:
        return "computed"
    return "backend-only"




def schedule_esr_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule ESR section 35 facts and protected outputs.

    Book expenditure debited to the P&L is a taxpayer/source fact. Eligible
    expenditure, excess over the P&L debit, statutory caps, and aggregate rows
    are backend projections and must remain read-only. Schema objects are
    structural containers, never generic JSON editors.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_ESR_COMPUTED_TERMINALS or terminal == "TotUs35":
        return "computed"
    if terminal == "AmtDebPL":
        return "dedicated-input"
    return "backend-only"


SCHEDULE_IF_COMPUTED_TERMINALS = {
    "ProfitShareAmt", "TotalProfitShareAmt", "TotalIntrstAmtDueOrRecv",
    "TotalRemunernAmtDueOrRecv", "TotalFirmCapBalOn31Mar",
}


def schedule_if_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify official Schedule IF identity, source facts, and projections.

    Partner-firm identity, flags, percentage, interest/remuneration and capital
    balance are explicit taxpayer/source facts. Allocated profit share and all
    statutory totals are produced by the backend; schema arrays are structural
    containers and never generic editable JSON.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_IF_COMPUTED_TERMINALS:
        return "computed"
    return "dedicated-input"


SCHEDULE_ESOP_COMPUTED_TERMINALS = {
    "TaxPayableCurrentAY", "BalanceTaxCF", "TotalTaxAttributedAmt",
    "TotalTaxAttributedAmt21", "TotalTaxAttributedAmt22", "TotalTaxAttributedAmt23",
    "TotalTaxAttributedAmt24", "TotalTaxAttributedAmt25",
}

SCHEDULE_ESOP_IMPORTED_TERMINALS = {"TaxDeferredBFEarlierAY"}


def schedule_esop_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule ESOP facts and backend projections explicitly.

    Startup identity and event disclosures are taxpayer/source facts. Historical
    brought-forward tax is imported from the prior return/prefill. Tax payable,
    attributed tax, carried balances, and statutory totals are backend outputs;
    schema containers remain backend-only and are never generic JSON editors.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_ESOP_COMPUTED_TERMINALS:
        return "computed"
    if terminal in SCHEDULE_ESOP_IMPORTED_TERMINALS:
        return "imported"
    if terminal in {"PanofStartUp", "DPIITRegNo", "SecurityType", "CeasedEmployee", "DateOfCeasing"}:
        return "dedicated-input"
    # Assessment-year branches are represented by fixed official containers;
    # their scalar value is selected by the backend from the canonical AY.
    if terminal == "AssessmentYear":
        return "backend-only"
    return "backend-only"


# Schedule VIA is represented twice by the official schema: the backend-owned
# `DeductUndChapVIA` projection and the user-entered `UsrDeductUndChapVIA`
# projection. Keep this table explicit rather than relying on source-string
# matching, so every one of the 77 official paths has a stable disposition.
PTI_COMPUTED_TERMINALS = {
    "AmountOfInc", "CurrYrLossShareByInvstFund", "NetIncomeLoss", "TDSAmount",
}


def schedule_pti_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify official Schedule PTI paths without generic input leakage.

    Entity identity/type and exemption section codes are source facts; all
    distributed income, loss-share, and tax-credit amounts are projections of
    the typed PTI domain and are backend-computed. Objects and arrays are
    schema structure, never editable JSON blobs.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in PTI_COMPUTED_TERMINALS:
        return "computed"
    if terminal in {"InvstmntCvrdUs115UA115UB", "BusinessName", "BusinessPAN", "SectionCode"}:
        return "dedicated-input"
    return "backend-only"


SCHEDULE_VIA_COMPUTED_TERMINALS = {
    "TotPartBchapterVIA", "TotPartCchapterVIA", "TotPartCAandDchapterVIA",
    "TotalChapVIADeductions",
}


def schedule_80_ra_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule 80RA source disclosures and protected aggregates.

    Donee identity, address, PAN, and claimed donation amounts are source facts.
    Eligible donation and all schedule totals are backend projections; the array
    and address wrapper are serialization structure, never generic JSON inputs.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in {"EligibleDonationAmt", "TotalDonationAmtCash80RA", "TotalDonationAmtOtherMode80RA", "TotalDonationsUs80RA", "TotalEligibleDonationAmt80RA"}:
        return "computed"
    if terminal in {"NameOfDonee", "DoneePAN", "DonationAmtCash", "DonationAmtOtherMode", "DonationAmt"} or ".AddressDetail." in path:
        return "dedicated-input"
    return "backend-only"


def schedule_80_ib_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule 80IB activity facts and backend deduction output."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in {"DeductAmountSec80", "TotSchedule80_IB"}:
        return "computed"
    if terminal in {"Sch80SectionCode", "Sch80LocOrDescCode"}:
        return "dedicated-input"
    return "backend-only"


def schedule_80_ia_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule 80IA activity facts and backend deduction output."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in {"DeductAmountSec80", "TotSchedule80_IA"}:
        return "computed"
    if terminal in {"Sch80SectionCode", "Sch80LocOrDescCode"}:
        return "dedicated-input"
    return "backend-only"


def schedule_80_ic_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify the official AY 2026-27 Schedule 80IC contract.

    The undertaking/state code is the only taxpayer/source scalar. The
    deduction amount and totals are backend calculations; arrays and wrapper
    objects are serialization structure.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in {"DeductAmountSec80", "TotDeductInNorthEast", "TotSchedule80_IC"}:
        return "computed"
    if terminal in {"Sch80SectionCode", "Sch80LocOrDescCode"}:
        return "dedicated-input"
    return "backend-only"
def schedule_via_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify all official Schedule VIA paths by ownership.

    The `DeductUndChapVIA` branch is a backend-computed form projection. The
    `UsrDeductUndChapVIA` branch contains taxpayer claims and supporting facts;
    structural nodes are never editable JSON blobs.
    """
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_VIA_COMPUTED_TERMINALS:
        return "computed"
    if ".DeductUndChapVIA." in path:
        return "computed"
    if ".UsrDeductUndChapVIA." not in path:
        return "backend-only"
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    return "dedicated-input"


def schedule_bp_disposition(path: str, entry: dict[str, Any], source: str) -> str:
    """Classify every official Schedule BP path without treating computed output as input."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in BP_COMPUTED_TERMINALS or any(token in terminal for token in ("Tot", "Total", "BalancePL", "AdjustedPL", "AfterSetOff", "RemainSetOff", "LossSetOffOnBus")):
        return "computed"
    return "dedicated-input"


SCHEDULE_112A_115AD_COMPUTED_TERMINALS = {
    "AcquisitionCost", "LTCGBeforelower6and11", "TotFairMktValueCapAst",
    "TotalDeductions", "Balance",
}
SCHEDULE_112A_115AD_SOURCE_TERMINALS = {
    "ShareOnOrBefore", "ISINCode", "ShareUnitName", "NumSharesUnits",
    "SalePricePerShareUnit", "TotSaleValue", "CostAcqWithoutIndx",
    "FairMktValuePerShareunit", "ExpExclCnctTransfer",
}


def schedule_112a_115ad_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule 112A/115AD source facts and protected projections."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_112A_115AD_COMPUTED_TERMINALS:
        return "computed"
    if terminal in SCHEDULE_112A_115AD_SOURCE_TERMINALS:
        return "dedicated-input"
    return "backend-only"




SCHEDULE_IT_COMPUTED_TERMINALS = {"TotalTaxPayments"}
SCHEDULE_IT_SOURCE_TERMINALS = {
    "BSRCode", "DateDep", "SrlNoOfChaln", "Amt", "MinorHead", "AssessmentYear",
    "TaxAmount", "InterestAmount", "FeeAmount", "SurchargeAmount", "SourceReference",
}


def schedule_it_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule IT challan evidence and the protected payment total.

    Challan identity, date, amount, component split, minor head, assessment
    year, and evidence references are taxpayer/source facts. The Schedule IT
    array and its wrapper are serialization structure; the aggregate total is
    calculated by the backend and cannot be edited independently.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_IT_COMPUTED_TERMINALS:
        return "computed"
    if terminal in SCHEDULE_IT_SOURCE_TERMINALS:
        return "dedicated-input"
    return "backend-only"


SCHEDULE_TPSA_COMPUTED_TERMINALS = {
    "AmtPrimaryAdjUs92CE_2A", "AdditionalIncTax18PercAbove", "Surcharge12Perc", "HealthEducationCess",
    "TotalAdditionalTax", "TaxesPaid", "NetTaxPayable", "TotalAmountDeposited",
}

SCHEDULE_ICDS_COMPUTED_TERMINALS = {
    "NetEffect", "TotalNetAmtDetl",
}
SCHEDULE_ICDS_SOURCE_TERMINALS = {"IncreaseInProfit", "DecreaseInProfit"}


def schedule_icds_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify ICDS source adjustments and protected reconciliation outputs.

    Each standard's increase/decrease amounts are taxpayer/source facts.  Net
    effects and the aggregate total are reconciled by the backend; schema
    objects remain structural and are never generic JSON inputs.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_ICDS_COMPUTED_TERMINALS:
        return "computed"
    if terminal in SCHEDULE_ICDS_SOURCE_TERMINALS:
        return "dedicated-input"
    return "backend-only"


def schedule_gst_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify GSTIN turnover evidence as dedicated source controls."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in {"GSTINNo", "AmtTurnGrossRcptGSTIN"}:
        return "dedicated-input"
    return "backend-only"


def schedule_spi_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule SPI identity and clubbed-income source fields."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in {"SpecifiedPersonName", "PANofSpecPerson", "AaadhaarOfSpecPerson", "ReltnShip", "AmtIncluded", "HeadIncIncluded"}:
        return "dedicated-input"
    return "backend-only"


def schedule_tpsa_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify TPSA tax outputs and supporting deposit facts explicitly."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_TPSA_COMPUTED_TERMINALS:
        return "backend-computed"
    if terminal in {"Amount", "BSRCode", "BankBranchName", "DateDep", "SrlNoOfChaln"}:
        return "dedicated-input"
    return "backend-only"


def resolve(node: dict[str, Any], definitions: dict[str, Any]) -> tuple[dict[str, Any], str]:
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/definitions/"):
        name = ref.rsplit("/", 1)[-1]
        return definitions.get(name, node), name
    return node, ""


def schema_type(node: dict[str, Any]) -> str:
    value = node.get("type")
    if isinstance(value, str): return value
    if isinstance(value, list): return "|".join(map(str, value))
    if "enum" in node: return "enum"
    return "object"


def walk(node: dict[str, Any], path: str, required: bool, definitions: dict[str, Any], definition: str = "") -> list[dict[str, Any]]:
    resolved, ref_name = resolve(node, definitions)
    definition = ref_name or definition
    properties = resolved.get("properties")
    if not isinstance(properties, dict):
        return [{"path": path, "fieldName": path.rsplit(".", 1)[-1], "required": required, "type": schema_type(resolved), "enumValues": [str(x) for x in resolved.get("enum", [])], "array": resolved.get("type") == "array", "object": False, "definition": definition}]
    required_names = set(resolved.get("required", []))
    result: list[dict[str, Any]] = []
    for name, child in properties.items():
        if not isinstance(child, dict): continue
        child_path = f"{path}.{name}" if path else name
        child_resolved, child_def = resolve(child, definitions)
        is_required = name in required_names
        if child_resolved.get("type") == "array":
            item, item_def = resolve(child_resolved.get("items", {}), definitions)
            result.append({"path": child_path, "fieldName": name, "required": is_required, "type": "array", "enumValues": [str(x) for x in item.get("enum", [])], "array": True, "object": isinstance(item.get("properties"), dict), "definition": item_def or child_def})
            if isinstance(item.get("properties"), dict): result.extend(walk(item, child_path + "[]", is_required, definitions, item_def or child_def))
        elif isinstance(child_resolved.get("properties"), dict) or child_resolved.get("$ref"):
            result.extend(walk(child, child_path, is_required, definitions, child_def))
        else:
            result.append({"path": child_path, "fieldName": name, "required": is_required, "type": schema_type(child_resolved), "enumValues": [str(x) for x in child_resolved.get("enum", [])], "array": False, "object": False, "definition": child_def})
    return result


def part_a_disposition(schedule: str, path: str, entry: dict[str, Any]) -> str:
    """Classify the mandatory Part A and Verification editor contract.

    Part A fields are supplied by the dedicated ITR-3 personal-information
    editor. Array/object nodes are structural containers, not editable scalar
    values. Verification identity values are derived from the canonical draft
    and therefore remain backend-only; only the taxpayer-entered capacity,
    place, and date are editable.
    """
    if schedule == "Verification":
        if path in {"Verification.Capacity", "Verification.Date", "Verification.Place"}:
            return "dedicated-input"
        return "backend-only"
    # Part A array/object nodes represent repeatable editor sections (nature,
    # notices, director/partner rows, and addresses), so they are covered by
    # the dedicated editor even though their leaf values are the input.
    return "dedicated-input"


# PARTA_PL totals and profit rows are projections of the typed P&L inputs and
# must never be exposed as user-editable source values.  These names are the
# official AY 2026-27 terminal names; keep this allow-list explicit so a new
# schema field cannot silently become editable merely because it contains
# "Total" in its label.
PL_COMPUTED_TERMINALS = {
    "TotOthIncome", "TotCreditsToPL", "PBIDTA", "PBT", "ProfitAfterTax",
    "BadDebtAmtDtlsTotal", "OthersPANNotAvlblDtlTotal", "TotEmployeeComp",
    "TotInsurances", "Total", "TotExciseCustomsVAT", "TotPersumptiveInc44AD",
    "TotPersumptiveInc44ADA", "TotalPrsumptvIncUs44E", "TotalPrsumptvIncUs44EGoods",
    "TotBusinessProfession", "GrossProfit", "NetProfit",
}


def part_a_pl_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify every official PARTA_PL path by actual input ownership.

    Repeatable/object nodes are structural containers and are not themselves
    inputs. Their scalar leaves are dedicated source rows, including nested
    bad-debt, other-expense, and non-resident disclosures. Official subtotals,
    PBT/PAT and presumptive totals are calculated by the backend and protected.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in PL_COMPUTED_TERMINALS:
        return "computed"
    return "dedicated-input"



def part_a_oi_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify official PARTA_OI disclosures by taxpayer ownership.

    Scalar disclosure leaves are dedicated inputs. Official statutory totals and
    aggregate projections are computed by the backend; nested objects are only
    structural containers and never generic storage.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal.startswith("Tot"):
        return "computed"
    return "dedicated-input"


def part_a_bs_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify official PARTA_BS leaves by taxpayer/backend ownership.

    PARTA_BS scalar balances are dedicated inputs, while official totals are
    backend-owned projections and nested objects are structural containers.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal.startswith("Tot") or terminal.startswith("Total") or terminal in {"NetBlock", "NetCurrAsset"}:
        return "computed"
    return "dedicated-input"


def part_a_qd_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify official PARTA_QD quantitative-detail paths.

    PARTA_QD is a source disclosure schedule: item names, units and quantities
    are supplied by the taxpayer (or an explicitly imported source), while the
    three wrapper objects and QuantitDet arrays are serialization structure.
    The schedule contains no frontend-computable statutory totals; preserving
    the scalar leaves as dedicated inputs prevents fabrication and keeps the
    backend mapper authoritative for JSON shape.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    return "dedicated-input"


# Schedule CG is a mixed ownership schedule: transaction/detail arrays are
# structural containers, raw sale/purchase/exemption facts are dedicated
# inputs, and statutory gains, exemptions, totals, and loss-setoff outputs are
# calculated by the backend. Keep the terminal list explicit: matching a broad
# "Total" substring would accidentally expose protected fields in future schema
# revisions.
CG_COMPUTED_TERMINALS = {
    "AquisitCost", "ImproveCost", "ExpOnTrans", "TotalDedn", "BalanceCG",
    "CapgainonAssets", "DeemedStcgOnAssets", "ExemptionGrandTotal",
    "AmtDeemedStcg", "TotalAmtDeemedStcg", "TotalSTCG", "TotalLTCG",
    "SumOfCGIncm", "IncmFromVDATrnsf", "TotScheduleCGFor23", "SlumpBalance",
    "TotalLTCGImmblPrprty", "TotalExcessTax", "TotalAmtNotTaxUsDTAAStcg",
    "TotalAmtTaxUsDTAAStcg", "TotalAmtNotTaxUsDTAALtcg", "TotalAmtTaxUsDTAALtcg",
    "TotalCapitalLossBuyBackShares", "TotDeductClaim", "CurrYearIncome",
    "CurrYrCapGain", "StclSetoff20Per", "StclSetoff30Per", "StclSetoffAppRate",
    "StclSetoffDTAARate", "LtclSetOff12_5Per", "LtclSetOffDTAARate",
}


def schedule_cg_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify every official Schedule CG path by ownership."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in CG_COMPUTED_TERMINALS:
        return "computed"
    # Loss-setoff rows are backend projections, even when their names do not
    # carry a Total/Balance prefix.
    if ".CurrYrLosses." in path:
        return "computed"
    return "dedicated-input"


# Schedule depreciation is a mixed schedule: source acquisition/WDV facts are
# dedicated inputs, while statutory depreciation, WDV, gains, disallowances and
# structural schema nodes remain backend-owned/read-only.
DEPRECIATION_SCHEDULES = {"ScheduleDPM", "ScheduleDOA"}
DEPRECIATION_COMPUTED_TERMINALS = {
    "DepreciationAtFullRate", "DepreciationAtHalfRate", "TotalDepreciation",
    "NetAggregateDepreciation", "WDVLastDay", "CapGainUs50", "DepDisAllowUs38_2",
    "FullRateDeprAmt", "HalfRateDeprAmt", "ProportionateAggDepreciation", "Total",
}

def depreciation_disposition(schedule: str, path: str, entry: dict[str, Any]) -> str:
    """Classify official DPM/DOA paths by source ownership."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in DEPRECIATION_COMPUTED_TERMINALS:
        return "computed"
    if terminal in {"WDVFirstDay", "AdditionsGrThan180Days", "AdditionsLessThan180Days", "ExpdrOnTrforSaleAsset", "AdjustmentSec115BAC", "AddlnDeprOnAssetLessThan180Days", "AddlnDeprOnGT180DayAdditions", "AddlnDeprOnLessThan180DayAdditions", "RealizationPeriodLessThan180days", "RealizationTotalPeriod"}:
        return "dedicated-input"
    return "dedicated-input"


def depreciation_summary_disposition(path: str, entry: dict[str, Any]) -> str:
    """Keep Schedule DEP as a backend-only summary projection."""
    return "backend-only" if entry.get("array") or entry.get("object") else "computed"


# Schedule S/HP are represented by canonical typed employer/property editors.  The
# schema's repeatable objects are serialization structure; their scalar leaves are
# populated from those editors.  Only statutory projections are protected.
SCHEDULE_S_HP_COMPUTED_TERMINALS = {
    "TotalGrossSalary", "NetSalary", "TotIncUnderHeadSalaries",
    "GrossAnnualValue", "NetAnnualValue", "StandardDeduction",
    "StandardDeduction30Pct", "TotalIncomeChargeableUnHP",
    "IncomeFromHP", "IncomeChargeableUnderHP", "EligibleExmpAllwncUs13A",
    "ActlRentPaid10Per", "Sal40Or50Per", "Increliefus89A",
    "PassThroghIncome",
}


def schedule_s_hp_disposition(schedule: str, path: str, entry: dict[str, Any]) -> str:
    """Classify official Schedule S and Schedule HP paths.

    Employer and property source facts are owned by the typed canonical draft
    editors.  Arrays/objects are backend serialization containers, while
    statutory totals and derived annual-value/deduction/relief fields are
    backend-computed and must remain read-only.  No employer or property data
    is fabricated when the corresponding canonical row is absent.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in SCHEDULE_S_HP_COMPUTED_TERMINALS:
        return "computed"
    return "dedicated-input"


def itr3_business_disposition(schedule: str, path: str, entry: dict[str, Any]) -> str:
    """Classify the remaining business and deduction editor contracts.

    Repeatable schema objects are serialization structure; their scalar leaves
    are still supplied by the typed business/deduction editors. Aggregate
    fields are calculated from those source rows and stay read-only.
    """
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if schedule == "ManufacturingAccount":
        return "dedicated-input"
    if schedule == "TradingAccount":
        return "dedicated-input"
    if schedule == "Schedule10AA":
        return "computed" if terminal == "TotalDedUs10Sub" else "dedicated-input"
    if schedule == "Schedule80C":
        return "computed" if terminal == "TotalAmt" else "dedicated-input"
    return "missing"


def schedule_al_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify AY 2026-27 Schedule AL source disclosures and projections."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in {"InterstAOPFlag", "DepositsInBank", "SharesAndSecurities", "InsurancePolicies", "LoansAndAdvancesGiven", "CashInHand", "JewelleryBullionEtc", "ArchCollDrawPaintSulpArt", "VehiclYachtsBoatsAircrafts", "LiabilityInRelatAssets", "Description", "ResidenceNo", "ResidenceName", "RoadOrStreet", "LocalityOrArea", "CityOrTownOrDistrict", "StateCode", "CountryCode", "PinCode", "ZipCode", "Amount", "NameOfFirm", "PanOfFirm", "AssesseInvestment"}:
        return "dedicated-input"
    return "backend-only"


def schedule_5a_disposition(path: str, entry: dict[str, Any]) -> str:
    """Classify Schedule 5A identity inputs and backend-derived values."""
    if entry.get("array") or entry.get("object"):
        return "backend-only"
    terminal = path.rsplit(".", 1)[-1]
    if terminal in {"NameOfSpouse", "PANOfSpouse", "AadhaarOfSpouse", "BooksSpouse44ABFlg", "BooksSpouse92EFlg"}:
        return "dedicated-input"
    if terminal in {"IncRecvdUndHead", "AmtApprndOfSpouse", "AmtTDSDeducted", "TDSApprndOfSpouse"}:
        return "backend-computed"
    return "backend-only"


def disposition(schedule: str, path: str, source: str, entry: dict[str, Any] | None = None) -> str:
    """Classify one official recursive schema path."""
    entry = entry or {}
    if schedule == "ScheduleGST":
        return schedule_gst_disposition(path, entry)
    if schedule == "ScheduleICDS":
        return schedule_icds_disposition(path, entry)
    if schedule == "ScheduleSPI":
        return schedule_spi_disposition(path, entry)
    if schedule == "ScheduleTPSA":
        return schedule_tpsa_disposition(path, entry)
    if schedule == "ScheduleDCG":
        return schedule_dcg_disposition(path, entry)
    if schedule in {"ManufacturingAccount", "TradingAccount", "Schedule10AA", "Schedule80C"}:
        return itr3_business_disposition(schedule, path, entry)
    if schedule == "ScheduleIF":
        return schedule_if_disposition(path, entry)
    if schedule == "ScheduleVDA":
        return schedule_vda_disposition(path, entry)
        return schedule_80_ic_disposition(path, entry)
    if schedule == "Schedule80_IA":
        return schedule_80_ia_disposition(path, entry)
    if schedule == "Schedule80_IB":
        return schedule_80_ib_disposition(path, entry)
    if schedule == "Schedule80RA":
        return schedule_80_ra_disposition(path, entry)
    if schedule == "ScheduleAL":
        return schedule_al_disposition(path, entry)
    if schedule == "Schedule5A2014":
        return schedule_5a_disposition(path, entry)
    if schedule in {"ScheduleS", "ScheduleHP"}:
        return schedule_s_hp_disposition(schedule, path, entry)
    if schedule in {"ScheduleDPM", "ScheduleDOA"}:
        return depreciation_disposition(schedule, path, entry)
    if schedule == "ScheduleDEP":
        return depreciation_summary_disposition(path, entry)
    if schedule == "PARTA_BS":
        return part_a_bs_disposition(path, entry)
    if schedule == "PARTA_PL":
        return part_a_pl_disposition(path, entry)
    if schedule == "PARTA_QD":
        return part_a_qd_disposition(path, entry)
    if schedule == "ScheduleFA":
        if entry.get("array"):
            return "backend-only"
        terminal = path.rsplit(".", 1)[-1]
        if terminal in {"CountryName", "IncTaxSch", "IncTaxSchNo", "IncOfferedSch", "IncOfferedSchNo"}:
            return "backend-computed"
        return "dedicated-input"
    if schedule in {"Schedule112A", "Schedule115AD"}:
        return schedule_112a_115ad_disposition(path, entry)
    if schedule == "ScheduleCGFor23":
        return schedule_cg_disposition(path, entry)
    if schedule == "ScheduleEI":
        return schedule_ei_disposition(path, entry)
    if schedule == "ScheduleOS" and path.rsplit(".", 1)[-1] in SCHEDULE_OS_COMPUTED_TERMINALS:
        return "computed"
    if schedule in {"PartA_GEN1", "PartA_GEN2", "Verification"}:
        return part_a_disposition(schedule, path, entry)
    if schedule in METADATA_SCHEDULES: return "metadata"
    if schedule in COMPUTED_SCHEDULES: return "computed"
    if schedule in IMPORTED_SCHEDULES: return "imported"
    if schedule in BACKEND_ONLY_SCHEDULES: return "backend-only"
    if re.search(rf"[\"'`]({re.escape(path)})[\"'`]", source): return "dedicated-input"
    return "missing"


def main() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    definitions = schema["definitions"]
    itr3 = definitions["ITR3"]
    source_files = [
        path for path in (FRONTEND / "src").rglob("*.ts*")
        if path.resolve() != OUT.resolve()
    ]
    source = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in source_files)
    entries: list[dict[str, Any]] = []
    for schedule, node in itr3["properties"].items():
        resolved, _ = resolve(node, definitions)
        for field in walk(node, schedule, schedule in set(itr3.get("required", [])), definitions):
            field["schedule"] = schedule
            field["role"] = ROLE_BY_SCHEDULE.get(schedule, "other")
            resolved_disposition = schedule_it_disposition(field["path"], field) if schedule == "ScheduleIT" else schedule_80_ic_disposition(field["path"], field) if schedule == "Schedule80_IC" else schedule_esr_disposition(field["path"], field) if schedule == "ScheduleESR" else schedule_esop_disposition(field["path"], field) if schedule == "ScheduleESOP" else schedule_fsi_disposition(schedule, field["path"], field) if schedule in {"ScheduleFSI", "ScheduleTR1"} else schedule_bp_disposition(field["path"], field, source) if schedule == "ITR3ScheduleBP" else schedule_ud_disposition(field["path"], field) if schedule == "ITR3ScheduleUD" else schedule_via_disposition(field["path"], field) if schedule == "ScheduleVIA" else deduction_schedule_disposition(schedule, field["path"], field) if schedule in DEDUCTION_SCHEDULES else part_a_oi_disposition(field["path"], field) if schedule == "PARTA_OI" else schedule_pti_disposition(field["path"], field) if schedule == "SchedulePTI" else disposition(schedule, field["path"], source, field)
            field["disposition"] = resolved_disposition
            entries.append(field)
    entries.sort(key=lambda x: x["path"])
    counts: dict[str, int] = {}
    for entry in entries: counts[entry["disposition"]] = counts.get(entry["disposition"], 0) + 1
    payload = {"schema": "ITR-3 AY 2026-27 V1.1", "officialPathCount": len(entries), "schedules": len(itr3["properties"]), "entries": entries}
    lines = ["/** Generated by scripts/generate_itr3_coverage.py; do not edit manually. */", "", "export type ITR3CoverageDisposition = 'dedicated-input' | 'generic-input' | 'computed' | 'backend-computed' | 'imported' | 'metadata' | 'backend-only' | 'missing';", "export type ITR3CoverageRole = 'metadata' | 'filing' | 'identity' | 'business' | 'salary' | 'house-property' | 'capital-gains' | 'other-sources' | 'loss-setoff' | 'deduction' | 'tax' | 'income-attribution' | 'international' | 'assets' | 'tax-payment' | 'other';", "", "export interface ITR3CoverageEntry { path: string; schedule: string; fieldName: string; type: string; required: boolean; enumValues: readonly string[]; array: boolean; object: boolean; definition: string; role: ITR3CoverageRole; disposition: ITR3CoverageDisposition; }", "", f"export const ITR3_OFFICIAL_PATH_COUNT = {len(entries)} as const;", f"export const ITR3_OFFICIAL_SCHEDULE_COUNT = {len(itr3['properties'])} as const;", "", "export const ITR3_COVERAGE_MANIFEST: readonly ITR3CoverageEntry[] = ["]
    for e in entries:
        lines.append("  " + json.dumps(e, ensure_ascii=False, separators=(",", ":")) + ",")
    lines += ["] as const;", "", "export const ITR3_COVERAGE_BY_PATH: ReadonlyMap<string, ITR3CoverageEntry> = new Map(ITR3_COVERAGE_MANIFEST.map((entry) => [entry.path, entry]));", ""]
    OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text("\n".join(lines), encoding="utf-8")
    report = {"schema": payload["schema"], "officialPathCount": len(entries), "scheduleCount": len(itr3["properties"]), "dispositionCounts": counts, "missingMandatoryPaths": [e["path"] for e in entries if e["required"] and e["disposition"] == "missing"], "missingPaths": [e["path"] for e in entries if e["disposition"] == "missing"]}
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True); REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = ["# ITR-3 frontend coverage gap report", "", f"- Official recursive paths: **{len(entries)}**", f"- Official schedules: **{len(itr3['properties'])}**", "", "## Dispositions", "", "| Disposition | Count |", "|---|---:|"] + [f"| `{k}` | {v} |" for k, v in sorted(counts.items())] + ["", f"## Missing mandatory paths ({len(report['missingMandatoryPaths'])})", "", *[f"- `{p}`" for p in report["missingMandatoryPaths"]]]
    REPORT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(OUT), **report}, indent=2))


if __name__ == "__main__": main()
