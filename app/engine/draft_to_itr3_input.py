"""Canonical ReturnDraft to ITR-3 typed input mapping."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from app.engine.draft_to_itr1_input import DraftMappingError, draft_to_itr1_input, _to_date
from app.schemas.itr3 import AuditInfo, BalanceSheet, BSOfficial, BSProprietorsFund, BSReserves, BSLoanGroup, BSUnsecuredLoanGroup, BSAdvances, BSFixedAsset, BSCurrentAssets, BSInventory, BSCashBank, BSCurrentLiabilities, BSProvisions, BSInvestments, BSLongTermInv, BSTradeInv, BSLoanAdvances, BSMiscAdjust, BSNoBooks, BSRupeeLoan, BusinessIncome, ITR3BusinessAccounts, ITR3Input, ITR3ScheduleSEmployer, ITR3ScheduleHPProperty, ManufacturingAccount, MfgOpeningInventory, MfgClosingStock, NatureOfBusiness, ProfitAndLoss, PLPartA, PLPLPartACreditsToPL, PLPLPartATaxProvAppr, PLPLPartANoBooksOfAccPL, PLPLPartADebitsToPL, PLPLPLPartADebitsToPLInterestExpdrtDtls, PLPLPLPartACreditsToPLOthIncome, TradingAccount, TradingOtherRevenueEntry, TradingOtherIncomeEntry, TradingExciseCustomsVAT, TradingDutyTaxPay, TradingDutyTaxPayExciseCustomsVAT, ITR3PartAOI, ITR3PartAQD, ScheduleESR, ScheduleGST, ScheduleICDS, ITR3ScheduleTPSA, ITR3DeductionDetails, ITR3DeductionDonation, ITR3DeductionLoan, ITR3Schedule80IA, ITR3Schedule80IB, ITR3Schedule80IC, ITR3Schedule80RA, ITR3Schedule10AA, ITR3Schedule80D, ITR3Schedule80DCategory, ITR3Schedule80DHealth, ITR3Schedule80DInsurance, ITR3Schedule80DD, ITR3Schedule80U, \
    ITR3DepreciationSchedules, ScheduleDPM, ScheduleDOA, ScheduleDEP, ScheduleDCG
from app.schemas.itr2 import ResidentialStatus as ITR3ResidentialStatus, ReturnFileSection
from app.engine.draft_to_itr2_input import _map_112a_scrips, _map_immovable_gains, _map_equity_stt_stcg, _map_other_assets, _map_nri_fii_securities, _map_nri_112_115_securities, _map_buyback_losses, _map_vda_transactions, _map_fsi_entries, _map_tr1_entries, _map_foreign_assets, _map_asset_liability, _map_schedule_5a, _map_esop_deferrals
from app.schemas.itr2 import CG112AScrip, CGTransaction, CGAssetType, ScheduleSIEntry, VDATransaction, SPIEntry, PTIEntry
from app.schemas.return_draft import ReturnDraft
from app.engine.validators.itr3.parta_pl import validate_parta_pl_arithmetic


_RESIDENTIAL_STATUS: dict[str, ITR3ResidentialStatus] = {
    "ROR": ITR3ResidentialStatus.RESIDENT,
    "RNOR": ITR3ResidentialStatus.NOT_ORDINARILY_RESIDENT,
    "NR": ITR3ResidentialStatus.NON_RESIDENT,
}

# PDF item 4's own Code column -- 5 digits, optionally with a disambiguating
# "_N" suffix (e.g. 16019_1 "Medical Profession", 20023_1 "Sports
# Management", 21008_1 "Event Management" -- confirmed present as distinct,
# legitimate values in the real official enum, alongside their un-suffixed
# base codes). A plain `.isdigit()` filter silently drops these three real
# codes from the return entirely.
_NATURE_OF_BUSINESS_CODE = re.compile(r"[0-9]{5}(_[0-9]+)?")

_FILING_SECTION: dict[str, ReturnFileSection] = {
    "139(1)": ReturnFileSection.ON_TIME_139_1,
    "139(4)": ReturnFileSection.BELATED_139_4,
    "142(1)": ReturnFileSection.NOTICE_142_1,
    "148": ReturnFileSection.NOTICE_148,
    "153C": ReturnFileSection.NOTICE_153C,
    "139(5)": ReturnFileSection.REVISED_139_5,
    "139(9)": ReturnFileSection.DEFECTIVE_139_9,
    "92CD": ReturnFileSection.MODIFIED_92CD,
    "119(2)(b)": ReturnFileSection.CONDONATION_119_2B,
}


def _decimal_value(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Convert a persisted workspace scalar to a finite Decimal."""
    if value is None or value == "":
        return default
    try:
        converted = Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return default
    return converted if converted.is_finite() else default


def _workspace_value(workspace: dict[str, Any], *path: str) -> Any:
    """Read a nested workspace value without silently traversing non-mappings."""
    current: Any = workspace
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


# Schedule ESR's 9 section rows (form item i-ix) plus its own "Total" row
# (item x). The frontend's generic auxiliary-schedule editor
# (ITR3BusinessAuxiliaryManager.tsx) uses a lazy `pathSet()` that only ever
# creates the exact nested path the taxpayer actually touches -- a return
# using only, say, Section35_1_i and Section35_2AB leaves the other 7
# section keys genuinely ABSENT from the saved draft, not present with
# zero values (the identical "realistic partial input" shape already found
# and fixed for Schedule DPM/DOA, tracker rows #15-18). The official
# schema requires all 10 keys unconditionally, so validating the raw,
# possibly-partial dict directly would raise a hard Pydantic
# ValidationError for this entirely ordinary case.
_ESR_SECTION_KEYS = (
    "Section35_1_i", "Section35_1_ii", "Section35_1_iia", "Section35_1_iii",
    "Section35_1_iv", "Section35_2AA", "Section35_2AB", "Section35_CCC",
    "Section35_CCD", "TotUs35",
)


# CBDT's own official ITR-3 Validation Rules for AY 2026-27 (`Reference
# Docs by CBDT & ITD/Official Validations/CBDT_e-filing_ITR-3_Validation
# Rules_V1.0_AY 26-27 (1).pdf`, rule #354, quoted verbatim): "If 'New Tax
# Regime' is selected, then in schedule ESR at column 3 [AmtUs35Allowable],
# amount cannot be more than zero for section 35(1)(ii), 35(1)(iia),
# 35(1)(iii), 35(2AA) and 35(CCC)." These five sub-clauses are all
# third-party contribution/donation-style research funding (payments to an
# approved research association/university/college, a National Laboratory,
# or an agricultural-extension-project sponsor) -- the same category of
# deduction the new regime (s.115BAC) generally disallows, the same
# principle already familiar from 80G/80C elsewhere in this codebase. The
# remaining 4 sub-clauses -- 35(1)(i)/35(1)(iv) (the taxpayer's own
# revenue/capital scientific-research expenditure) and 35(2AB)/35CCD
# (in-house R&D / skill-development, the taxpayer's own direct business
# expenditure, not a third-party contribution) -- are NOT in this
# new-regime disallow list and remain 100% allowable under either regime.
_ESR_NEW_REGIME_DISALLOWED_SECTIONS = frozenset({
    "Section35_1_ii", "Section35_1_iia", "Section35_1_iii",
    "Section35_2AA", "Section35_CCC",
})


def _normalize_esr_source(esr_source: Mapping, is_new_regime: bool) -> dict[str, Any] | None:
    """Default every Schedule ESR section/leaf a taxpayer left genuinely
    untouched to 0, matching the official schema's own per-field
    ``default: 0`` -- without this, a return using only some of the 9
    section rows crashes JSON generation entirely rather than merely
    disclosing zero for the untouched ones. Returns None when every leaf
    across all 9 sections is genuinely zero (nothing entered, or a section
    typed into and then cleared back to 0) -- matching the established
    "an explicitly all-zero block must not be mistaken for a real one"
    precedent from Schedule DPM/DOA (tracker rows #15-18), so this schedule
    is correctly OMITTED from the JSON rather than emitted as a fabricated
    zero-filled stub.

    ``TotUs35`` (form item x, the "Total" row) is RECOMPUTED here as the
    sum of the 9 section rows, rather than trusted from whatever the
    frontend's own client-side ``recompute()`` last sent -- unlike DPM/DOA/
    DEP/DCG's own per-field derived values (disclosure-only), this
    specific total now also feeds Schedule BP's item 28 and, through it,
    real tax computation (see ``_business_income``'s own
    ``section35_excess_deduction``); trusting a client-computed aggregate
    for a tax-affecting figure is the wrong place to add that risk when
    the exact same arithmetic is trivial to re-derive server-side.
    """
    deduction_us35 = esr_source.get("DeductionUs35") if isinstance(esr_source.get("DeductionUs35"), Mapping) else {}
    sections: dict[str, Any] = {}
    totals = {"AmtDebPL": Decimal("0"), "AmtUs35Allowable": Decimal("0"), "ExcessAmtOverDebPL": Decimal("0")}
    for key in _ESR_SECTION_KEYS:
        if key == "TotUs35":
            continue
        raw_section = deduction_us35.get(key) if isinstance(deduction_us35, Mapping) else None
        raw_detail = raw_section.get("DeductUs35") if isinstance(raw_section, Mapping) else None
        amt_deb_pl = _decimal_value(raw_detail.get("AmtDebPL")) if isinstance(raw_detail, Mapping) else Decimal("0")
        # Every one of Schedule ESR's 9 section-35 sub-clauses allows
        # 100% of the amount debited to P&L as of AY 2026-27 under the OLD
        # regime -- the weighted (150%/200%) deductions historically
        # available under 35(1)(ii)/(iia)/(iii)/35(2AA)/35(2AB)/35CCC/
        # 35CCD were all phased down to a flat 100% by Finance Act 2020
        # (effective AY 2021-22), with no subsequent reversal; 35(1)(i)/
        # (iv) never carried a weighted multiplier at all. Under the NEW
        # regime, 5 of the 9 sub-clauses are instead disallowed entirely
        # (see `_ESR_NEW_REGIME_DISALLOWED_SECTIONS`'s own citation of
        # official rule #354). The frontend's own AmtUs35Allowable/
        # ExcessAmtOverDebPL fields are marked `readonly` in its editor
        # (esrFields(), implying "auto-computed") but nothing -- neither
        # the frontend's own recompute() (confirmed by reading it in
        # full: it only derives TotUs35, never a per-section Allowable/
        # Excess, and is entirely regime-unaware) nor, before this fix,
        # the backend -- ever actually computed them, so they are
        # genuinely absent for every real taxpayer interaction. This
        # function's general "default an absent field to 0" policy would
        # be WRONG here specifically for the old-regime/allowed case: it
        # would silently disclose a Rs.0 allowable deduction against
        # real, entered R&D expenditure. Default to the correct,
        # regime-aware figure instead, only when genuinely absent -- an
        # explicitly-provided value is still honored as-is (even one that
        # would violate rule #354 -- this push does not add new
        # validators, see the tracker's own ground rules).
        if is_new_regime and key in _ESR_NEW_REGIME_DISALLOWED_SECTIONS:
            allowable_default = Decimal("0")
        else:
            allowable_default = amt_deb_pl
        raw_allowable = raw_detail.get("AmtUs35Allowable") if isinstance(raw_detail, Mapping) else None
        amt_us35_allowable = _decimal_value(raw_allowable, default=allowable_default)
        raw_excess = raw_detail.get("ExcessAmtOverDebPL") if isinstance(raw_detail, Mapping) else None
        # Sl.No.4 = Sl.No.3 - Sl.No.2 per official rule #352 -- floored at
        # 0 per the schema's own `minimum: 0` on this field; a genuine
        # shortfall (allowable < debited, e.g. a new-regime-disallowed
        # section) is a disallowed EXPENSE, not a negative "excess" --
        # official rule #286 routes that shortfall into Schedule BP's own
        # item 24(e) instead (added back into taxable business income by
        # `_esr_shortfall_addback()`/`_business_income()` below, not left
        # at this schedule's own disclosure layer).
        excess_default = max(Decimal("0"), amt_us35_allowable - amt_deb_pl)
        excess_amt_over_deb_pl = _decimal_value(raw_excess, default=excess_default)
        detail = {
            "AmtDebPL": amt_deb_pl,
            "AmtUs35Allowable": amt_us35_allowable,
            "ExcessAmtOverDebPL": excess_amt_over_deb_pl,
        }
        sections[key] = {"DeductUs35": detail}
        for leaf in totals:
            totals[leaf] += detail[leaf]
    if not any(totals.values()):
        return None
    sections["TotUs35"] = {"DeductUs35": totals}
    return {"DeductionUs35": sections}


def _esr_shortfall_addback(schedule_esr: "ScheduleESR | None") -> Decimal:
    """
    Schedule BP item 24(e) -- official CBDT ITR-3 Validation Rules for AY
    2026-27, rule #286 (quoted verbatim): "Schedule BP, sl no 24(e) should
    be minimum of Absolute value of total of negative values of 'col 3 -
    col 2' of all fields in Schedule ESR."

    Column 3 (AmtUs35Allowable) can be LESS than column 2 (AmtDebPL) --
    most commonly a new-regime return with real expenditure debited under
    one of the 5 sections rule #354 disallows (see
    `_ESR_NEW_REGIME_DISALLOWED_SECTIONS`) -- meaning the expenditure was
    already debited to (and reduced) the P&L account's own net profit
    figure, but is not actually an allowable deduction. That shortfall
    must be added BACK into taxable business income via item 24
    (`AnyOthIncNotInclInExpDisallowPL`) or `total_business_income` would
    silently understate real tax by the full disallowed amount -- this is
    not merely a disclosure gap, it is the direct tax-computation
    consequence of the new-regime disallowance itself.

    Additive with (not a replacement for) whatever the taxpayer separately
    entered into the raw Schedule-BP workspace's own item 24 field --
    unlike item 28 (which the official form ties EXCLUSIVELY to Schedule
    ESR's own total, see `_business_income`'s own comment), item 24 is a
    broad "any other expense not allowable" bucket ESR's shortfall is
    only ever one possible contributor to.
    """
    if schedule_esr is None:
        return Decimal("0")
    shortfall = Decimal("0")
    for key in _ESR_SECTION_KEYS:
        if key == "TotUs35":
            continue
        detail = getattr(schedule_esr.DeductionUs35, key).DeductUs35
        shortfall += max(Decimal("0"), detail.AmtDebPL - detail.AmtUs35Allowable)
    return shortfall


def _core_schedule(draft: ReturnDraft, name: str) -> dict[str, Any] | None:
    """Return a non-empty official core schedule from the business workspace."""
    value = draft.itr3BusinessWorkspace.core.get(name)
    return dict(value) if isinstance(value, Mapping) and value else None


def _balance_sheet(draft: ReturnDraft) -> Any:
    """Map PARTA_BS workspace data, falling back to the legacy summary."""
    source = draft.itr3BalanceSheet
    workspace = _core_schedule(draft, "PARTA_BS")
    if workspace:
        fund_src = workspace.get("FundSrc", {})
        prop_fund = fund_src.get("PropFund", {}) if isinstance(fund_src, Mapping) else {}
        loan_funds = fund_src.get("LoanFunds", {}) if isinstance(fund_src, Mapping) else {}
        secr_loan = loan_funds.get("SecrLoan", {}) if isinstance(loan_funds, Mapping) else {}
        rupee_loan = secr_loan.get("RupeeLoan", {}) if isinstance(secr_loan, Mapping) else {}
        unsecr_loan = loan_funds.get("UnsecrLoan", {}) if isinstance(loan_funds, Mapping) else {}
        fund_apply = workspace.get("FundApply", {})
        fixed_asset = fund_apply.get("FixedAsset", {}) if isinstance(fund_apply, Mapping) else {}
        current = fund_apply.get("CurrAssetLoanAdv", {}) if isinstance(fund_apply, Mapping) else {}
        current_asset = current.get("CurrAsset", {}) if isinstance(current, Mapping) else {}
        inventories = current_asset.get("Inventories", {}) if isinstance(current_asset, Mapping) else {}
        cash_bank = current_asset.get("CashOrBankBal", {}) if isinstance(current_asset, Mapping) else {}
        liabilities = current.get("CurrLiabilitiesProv", {}) if isinstance(current, Mapping) else {}
        current_liabilities = liabilities.get("CurrLiabilities", {}) if isinstance(liabilities, Mapping) else {}
        provisions = liabilities.get("Provisions", {}) if isinstance(liabilities, Mapping) else {}
        prop_reserves = prop_fund.get("ResrNSurp", {}) if isinstance(prop_fund.get("ResrNSurp"), Mapping) else {}
        rupee_loan = secr_loan.get("RupeeLoan", {}) if isinstance(secr_loan.get("RupeeLoan"), Mapping) else {}
        inventories = current_asset.get("Inventories", {}) if isinstance(current_asset.get("Inventories"), Mapping) else {}
        cash_bank = current_asset.get("CashOrBankBal", {}) if isinstance(current_asset.get("CashOrBankBal"), Mapping) else {}
        investments = fund_apply.get("Investments", {}) if isinstance(fund_apply, Mapping) else {}
        long_term_inv = investments.get("LongTermInv", {}) if isinstance(investments.get("LongTermInv"), Mapping) else {}
        trade_inv = investments.get("TradeInv", {}) if isinstance(investments.get("TradeInv"), Mapping) else {}
        loan_adv = current.get("LoanAdv", {}) if isinstance(current, Mapping) else {}
        misc_adjust = fund_apply.get("MiscAdjust", {}) if isinstance(fund_apply, Mapping) else {}
        no_books_ws = workspace.get("NoBooksOfAccBS") if isinstance(workspace, Mapping) else None
        official = BSOfficial(
            proprietors_fund=BSProprietorsFund(
                PropCap=_decimal_value(prop_fund.get("PropCap")),
                ResrNSurp=BSReserves(
                    RevResr=_decimal_value(prop_reserves.get("RevResr")),
                    CapResr=_decimal_value(prop_reserves.get("CapResr")),
                    StatResr=_decimal_value(prop_reserves.get("StatResr")),
                    OthResr=_decimal_value(prop_reserves.get("OthResr")),
                    TotResrNSurp=_decimal_value(prop_reserves.get("TotResrNSurp")),
                ),
                TotPropFund=_decimal_value(prop_fund.get("TotPropFund")),
            ),
            secured_loans=BSLoanGroup(
                ForeignCurrLoan=_decimal_value(secr_loan.get("ForeignCurrLoan")),
                RupeeLoan=BSRupeeLoan(
                    FrmBank=_decimal_value(rupee_loan.get("FrmBank")),
                    FrmOthrs=_decimal_value(rupee_loan.get("FrmOthrs")),
                    TotRupeeLoan=_decimal_value(rupee_loan.get("TotRupeeLoan")),
                ),
                TotSecrLoan=_decimal_value(secr_loan.get("TotSecrLoan")),
            ),
            unsecured_loans=BSUnsecuredLoanGroup(
                FrmBank=_decimal_value(unsecr_loan.get("FrmBank")),
                FrmOthrs=_decimal_value(unsecr_loan.get("FrmOthrs")),
                TotUnSecrLoan=_decimal_value(unsecr_loan.get("TotUnSecrLoan")),
            ),
            advances=BSAdvances(
                FromPrsn=_decimal_value((fund_src.get("Advances", {}) or {}).get("FromPrsn")),
                FromOthers=_decimal_value((fund_src.get("Advances", {}) or {}).get("FromOthers")),
                TotalAdvances=_decimal_value((fund_src.get("Advances", {}) or {}).get("TotalAdvances")),
            ),
            DeferredTax=_decimal_value(fund_src.get("DeferredTax")),
            TotFundSrc=_decimal_value(fund_src.get("TotFundSrc")),
            fixed_assets=BSFixedAsset(
                GrossBlock=_decimal_value(fixed_asset.get("GrossBlock")),
                Depreciation=_decimal_value(fixed_asset.get("Depreciation")),
                NetBlock=_decimal_value(fixed_asset.get("NetBlock")),
                CapWrkProg=_decimal_value(fixed_asset.get("CapWrkProg")),
                TotFixedAsset=_decimal_value(fixed_asset.get("TotFixedAsset")),
            ),
            investments=BSInvestments(
                LongTermInv=BSLongTermInv(
                    GovtOthSecQuoted=_decimal_value(long_term_inv.get("GovtOthSecQuoted")),
                    GovOthSecUnQoted=_decimal_value(long_term_inv.get("GovOthSecUnQoted")),
                    TotLongTermInv=_decimal_value(long_term_inv.get("TotLongTermInv")),
                ),
                TradeInv=BSTradeInv(
                    EquityShares=_decimal_value(trade_inv.get("EquityShares")),
                    PreferShares=_decimal_value(trade_inv.get("PreferShares")),
                    Debenture=_decimal_value(trade_inv.get("Debenture")),
                    TotTradeInv=_decimal_value(trade_inv.get("TotTradeInv")),
                ),
                TotInvestments=_decimal_value(investments.get("TotInvestments")),
            ),
            current_assets=BSCurrentAssets(
                Inventories=BSInventory(
                    StoresConsumables=_decimal_value(inventories.get("StoresConsumables")),
                    RawMatl=_decimal_value(inventories.get("RawMatl")),
                    StkInProcess=_decimal_value(inventories.get("StkInProcess")),
                    FinOrTradGood=_decimal_value(inventories.get("FinOrTradGood")),
                    TotInventries=_decimal_value(inventories.get("TotInventries")),
                ),
                SndryDebtors=_decimal_value(current_asset.get("SndryDebtors")),
                CashOrBankBal=BSCashBank(
                    CashinHand=_decimal_value(cash_bank.get("CashinHand")),
                    BankBal=_decimal_value(cash_bank.get("BankBal")),
                    TotCashOrBankBal=_decimal_value(cash_bank.get("TotCashOrBankBal")),
                ),
                OthCurrAsset=_decimal_value(current_asset.get("OthCurrAsset")),
                TotCurrAsset=_decimal_value(current_asset.get("TotCurrAsset")),
            ),
            current_liabilities=BSCurrentLiabilities(
                SundryCred=_decimal_value(current_liabilities.get("SundryCred")),
                LiabForLeasedAsset=_decimal_value(current_liabilities.get("LiabForLeasedAsset")),
                AccrIntonLeasedAsset=_decimal_value(current_liabilities.get("AccrIntonLeasedAsset")),
                AccrIntNotDue=_decimal_value(current_liabilities.get("AccrIntNotDue")),
                TotCurrLiabilities=_decimal_value(current_liabilities.get("TotCurrLiabilities")),
            ),
            provisions=BSProvisions(
                ITProvision=_decimal_value(provisions.get("ITProvision")),
                ELSuperAnnGratProvision=_decimal_value(provisions.get("ELSuperAnnGratProvision")),
                OthProvision=_decimal_value(provisions.get("OthProvision")),
                TotProvisions=_decimal_value(provisions.get("TotProvisions")),
            ),
            loan_advances=BSLoanAdvances(
                AdvRecoverable=_decimal_value(loan_adv.get("AdvRecoverable")),
                Deposits=_decimal_value(loan_adv.get("Deposits")),
                BalWithRevAuth=_decimal_value(loan_adv.get("BalWithRevAuth")),
                TotLoanAdv=_decimal_value(loan_adv.get("TotLoanAdv")),
            ),
            NetCurrAsset=_decimal_value(current.get("NetCurrAsset")),
            misc_adjust=BSMiscAdjust(
                MiscExpndr=_decimal_value(misc_adjust.get("MiscExpndr")),
                DefTaxAsset=_decimal_value(misc_adjust.get("DefTaxAsset")),
                AccumaltedLosses=_decimal_value(misc_adjust.get("AccumaltedLosses")),
                TotMiscAdjust=_decimal_value(misc_adjust.get("TotMiscAdjust")),
            ),
            no_books=(
                BSNoBooks(
                    TotSundryDbtAmt=_decimal_value(no_books_ws.get("TotSundryDbtAmt")),
                    TotSundryCrdAmt=_decimal_value(no_books_ws.get("TotSundryCrdAmt")),
                    TotStkInTradAmt=_decimal_value(no_books_ws.get("TotStkInTradAmt")),
                    CashBalAmt=_decimal_value(no_books_ws.get("CashBalAmt")),
                ) if isinstance(no_books_ws, Mapping) and no_books_ws else None
            ),
        )
        return BalanceSheet(
            proprietors_fund=_decimal_value(prop_fund.get("TotPropFund")),
            secured_loans=_decimal_value(secr_loan.get("TotSecrLoan")),
            unsecured_loans=_decimal_value(unsecr_loan.get("TotUnSecrLoan")),
            current_liabilities=_decimal_value(liabilities.get("TotCurrLiabilitiesProvision")),
            total_liabilities=_decimal_value(fund_src.get("TotFundSrc")),
            fixed_assets=_decimal_value(fixed_asset.get("TotFixedAsset")),
            current_assets=_decimal_value(current.get("TotCurrAssetLoanAdv")),
            total_assets=_decimal_value(fund_apply.get("TotFundApply")),
            official=official,
        )
    total_liabilities = source.totalSources or (
        source.proprietorCapital
        + source.reservesAndSurplus
        + source.securedLoans
        + source.unsecuredLoans
        + source.deferredTaxLiability
        + source.advancesFromCustomers
    )
    # Current liabilities and provisions (creditors/provisions) are netted
    # against current assets per form item 3e, not summed into liabilities.
    current_assets = (
        source.inventories
        + source.tradeReceivables
        + source.cashAndBank
        + source.loansAndAdvances
        - source.creditors
        - source.provisions
        + source.otherAssets
    )
    total_assets = source.totalApplications or source.fixedAssets + source.investments + current_assets
    # The legacy flat summary has no LongTermInv/TradeInv/AdvRecoverable/
    # Deposits/BalWithRevAuth/MiscExpndr/DefTaxAsset breakdown -- only bare
    # aggregates. Still build a complete BSOfficial (every schema-required
    # sub-block present, defaulting to 0 where no finer source exists)
    # rather than leaving `official=None`, which previously sent this path
    # through the builder's minimal fallback and produced a PARTA_BS
    # missing more than a dozen required properties (confirmed live via
    # direct schema validation).
    legacy_official = BSOfficial(
        proprietors_fund=BSProprietorsFund(
            PropCap=source.proprietorCapital,
            ResrNSurp=BSReserves(TotResrNSurp=source.reservesAndSurplus),
            TotPropFund=source.proprietorCapital + source.reservesAndSurplus,
        ),
        secured_loans=BSLoanGroup(TotSecrLoan=source.securedLoans),
        unsecured_loans=BSUnsecuredLoanGroup(TotUnSecrLoan=source.unsecuredLoans),
        advances=BSAdvances(
            FromOthers=source.advancesFromCustomers, TotalAdvances=source.advancesFromCustomers,
        ),
        DeferredTax=source.deferredTaxLiability,
        TotFundSrc=total_liabilities,
        fixed_assets=BSFixedAsset(NetBlock=source.fixedAssets, TotFixedAsset=source.fixedAssets),
        investments=BSInvestments(TotInvestments=source.investments),
        current_assets=BSCurrentAssets(
            Inventories=BSInventory(TotInventries=source.inventories),
            SndryDebtors=source.tradeReceivables,
            CashOrBankBal=BSCashBank(TotCashOrBankBal=source.cashAndBank),
            OthCurrAsset=source.otherAssets,
            TotCurrAsset=(
                source.inventories + source.tradeReceivables + source.cashAndBank + source.otherAssets
            ),
        ),
        loan_advances=BSLoanAdvances(TotLoanAdv=source.loansAndAdvances),
        current_liabilities=BSCurrentLiabilities(SundryCred=source.creditors, TotCurrLiabilities=source.creditors),
        provisions=BSProvisions(OthProvision=source.provisions, TotProvisions=source.provisions),
        NetCurrAsset=current_assets,
        misc_adjust=BSMiscAdjust(),
        no_books=(
            BSNoBooks(
                TotSundryDbtAmt=source.noBooksSundryDebtors,
                TotSundryCrdAmt=source.noBooksSundryCreditors,
                TotStkInTradAmt=source.noBooksStockInTrade,
                CashBalAmt=source.noBooksCashBalance,
            ) if source.noBooksOfAccounts else None
        ),
    )
    return BalanceSheet(
        proprietors_fund=source.proprietorCapital + source.reservesAndSurplus,
        secured_loans=source.securedLoans,
        unsecured_loans=source.unsecuredLoans,
        current_liabilities=source.deferredTaxLiability + source.advancesFromCustomers,
        total_liabilities=total_liabilities,
        fixed_assets=source.fixedAssets,
        current_assets=current_assets,
        total_assets=total_assets,
        official=legacy_official,
    )


def _audit_info(draft: ReturnDraft) -> AuditInfo:
    """Map PartA_GEN2 audit data (form A20), falling back to the legacy profile."""
    workspace = _core_schedule(draft, "PartA_GEN2")
    audit = workspace.get("AuditInfo") if workspace else None
    if isinstance(audit, Mapping) and audit:
        bii = audit.get("BiiDetails") if isinstance(audit.get("BiiDetails"), Mapping) else {}
        audit_92e = audit.get("AuditDetails92E") if isinstance(audit.get("AuditDetails92E"), Mapping) else {}
        return AuditInfo(
            liable_sec_44ab=audit.get("LiableSec44ABflg") == "Y",
            liable_sec_44aa=audit.get("LiableSec44AAflg") == "Y",
            liable_sec_92e=audit.get("LiableSec92Eflg") == "Y",
            account_audited=audit.get("AccountAuditFlag") == "Y",
            audited_by_accountant=audit.get("AuditAccountantFlg") == "Y",
            income_declared_under_presumptive=audit.get("IncDclrdUs") == "Y",
            total_sales_band=audit.get("TotalSalesExcOneCr") or None,
            receipts_cash_band=audit.get("AgrOFAllAmtsRcvd") or None,
            payments_cash_band=audit.get("AgrOFAllPayMade") or None,
            condition_44ab=audit.get("Cndnfor44AB") or None,
            presumptive_44ad=bii.get("44AD") == "Y",
            presumptive_44ada=bii.get("44ADA") == "Y",
            presumptive_44ae=bii.get("44AE") == "Y",
            presumptive_44bb=bii.get("44BB") == "Y",
            audit_report_furnish_date=audit.get("AuditReportFurnishDate") or None,
            ack_num_44ab=str(audit["AckNum44AB"]) if audit.get("AckNum44AB") else None,
            auditor_firm_name=audit.get("AudFrmName") or None,
            auditor_firm_pan=audit.get("AudFrmPAN") or None,
            auditor_firm_aadhaar=audit.get("AudFrmAadhaar") or None,
            audited_under_92e=bool(audit_92e),
            audit_92e_date=audit_92e.get("DateOfAudit") or None,
            ack_num_92e=str(audit_92e["AckNum92E"]) if audit_92e.get("AckNum92E") else None,
            other_section_audit_entries=list(audit.get("AuditDetails") or []),
            other_act_audit_entries=list(audit.get("AuditReportDetails") or []),
        )
    source = draft.itr3AuditInfo
    return AuditInfo(
        liable_sec_44ab=source.liableSec44AB == "Y",
        liable_sec_44aa=source.liableSec44AA == "Y",
        liable_sec_92e=source.liableSec92E == "Y",
        account_audited=source.accountAudit == "Y",
        audited_by_accountant=source.auditAccountant == "Y",
        income_declared_under_presumptive=source.incomeDeclaredUnderPresumptive == "Y",
        total_sales_band=source.totalSalesBand or None,
        receipts_cash_band=source.receiptsCashBand or None,
        payments_cash_band=source.paymentsCashBand or None,
        condition_44ab=source.condition44AB or None,
        presumptive_44ad=source.presumptive44AD == "Y",
        presumptive_44ada=source.presumptive44ADA == "Y",
        presumptive_44ae=source.presumptive44AE == "Y",
        presumptive_44bb=source.presumptive44BB == "Y",
        audit_report_furnish_date=source.auditReportFurnishDate or None,
        ack_num_44ab=source.acknowledgement44AB or None,
        auditor_firm_name=source.auditorName or None,
        auditor_firm_pan=source.auditorPAN or None,
        auditor_firm_aadhaar=source.auditorAadhaar or None,
        audited_under_92e=source.auditedUnder92E == "Y",
        audit_92e_date=source.auditReport92EDate or None,
        ack_num_92e=source.acknowledgement92E or None,
        other_section_audit_entries=[
            {
                "auditedSection": row.auditedSection, "auditFlag": row.auditFlag,
                "dateOfAudit": row.dateOfAudit, "ackNumOth": row.ackNumOth,
            }
            for row in source.otherAuditReportEntries if row.auditedSection
        ],
        other_act_audit_entries=[
            {
                "act": row.act, "actOthers": row.actOthers,
                "auditedSection": row.auditedSection, "dateOfAudit": row.dateOfAudit,
            }
            for row in source.auditUnderOtherActEntries if row.act
        ],
    )


def _mfg_opening_inventory(opening: Mapping[str, Any]) -> MfgOpeningInventory:
    return MfgOpeningInventory(
        OpngStckRawMat=_decimal_value(opening.get("OpngStckRawMat")),
        OpngStckWrkinPrgrs=_decimal_value(opening.get("OpngStckWrkinPrgrs")),
        OpngInvntryTotal=_decimal_value(opening.get("OpngInvntryTotal")),
        Purchases=_decimal_value(opening.get("Purchases")),
        DirectWages=_decimal_value(opening.get("DirectWages")),
        DirectExpenses=_decimal_value(opening.get("DirectExpenses")),
        CarriageInward=_decimal_value(opening.get("CarriageInward")),
        PowerAndFuel=_decimal_value(opening.get("PowerAndFuel")),
        OthDirectExpenses=_decimal_value(opening.get("OthDirectExpenses")),
        IndirectWages=_decimal_value(opening.get("IndirectWages")),
        FactoryRentAndRates=_decimal_value(opening.get("FactoryRentAndRates")),
        FactoryInsurance=_decimal_value(opening.get("FactoryInsurance")),
        FactoryFuelAndPower=_decimal_value(opening.get("FactoryFuelAndPower")),
        FactoryGeneralExpenses=_decimal_value(opening.get("FactoryGeneralExpenses")),
        DeprctnOfFactoryMachinery=_decimal_value(opening.get("DeprctnOfFactoryMachinery")),
        TotalFactoryOverheads=_decimal_value(opening.get("TotalFactoryOverheads")),
        TotalDebtsManfctrngAcc=_decimal_value(opening.get("TotalDebtsManfctrngAcc")),
    )


def _mfg_closing_stock(closing: Mapping[str, Any]) -> MfgClosingStock:
    return MfgClosingStock(
        ClsngStckRawMaterial=_decimal_value(closing.get("ClsngStckRawMaterial")),
        ClsngStckWrkInPrgrs=_decimal_value(closing.get("ClsngStckWrkInPrgrs")),
        ClsngStckTotal=_decimal_value(closing.get("ClsngStckTotal")),
    )


def _trading_other_revenue_entries(rows: Any) -> list[TradingOtherRevenueEntry]:
    if not isinstance(rows, list):
        return []
    return [
        TradingOtherRevenueEntry(
            OperatingRevenueName=str(row.get("OperatingRevenueName")),
            OperatingRevenueAmt=_decimal_value(row.get("OperatingRevenueAmt")),
        )
        for row in rows
        if isinstance(row, Mapping) and row.get("OperatingRevenueName")
    ]


def _trading_other_income_entries(rows: Any) -> list[TradingOtherIncomeEntry]:
    if not isinstance(rows, list):
        return []
    return [
        TradingOtherIncomeEntry(
            NatureOfIncome=str(row.get("NatureOfIncome")),
            Amount=_decimal_value(row.get("Amount")),
        )
        for row in rows
        if isinstance(row, Mapping) and row.get("NatureOfIncome")
    ]


def _business_accounts(draft: ReturnDraft) -> ITR3BusinessAccounts | None:
    """Map official ManufacturingAccount and TradingAccount workspace objects."""
    manufacturing = _core_schedule(draft, "ManufacturingAccount")
    trading = _core_schedule(draft, "TradingAccount")
    if not manufacturing and not trading:
        return None
    opening = manufacturing.get("OpeningInventory", {}) if manufacturing else {}
    closing = manufacturing.get("ClosingStock", {}) if manufacturing else {}
    excise_customs_vat = trading.get("ExciseCustomsVAT", {}) if trading else {}
    duty_tax_pay = trading.get("DutyTaxPay", {}) if trading else {}
    duty_tax_pay_excise = duty_tax_pay.get("ExciseCustomsVAT", {}) if isinstance(duty_tax_pay, Mapping) else {}
    return ITR3BusinessAccounts(
        manufacturing_account=ManufacturingAccount(
            opening_inventory=_mfg_opening_inventory(opening if isinstance(opening, Mapping) else {}),
            closing_stock=_mfg_closing_stock(closing if isinstance(closing, Mapping) else {}),
            cost_of_goods_produced=_decimal_value(manufacturing.get("CostOfGoodsPrdcd")),
        ) if manufacturing else None,
        trading_account=TradingAccount(
            SaleOfGoods=_decimal_value(trading.get("SaleOfGoods")),
            SaleOfServices=_decimal_value(trading.get("SaleOfServices")),
            OtherOperatingRevenueDtls=_trading_other_revenue_entries(trading.get("OtherOperatingRevenueDtls")),
            OperatingRevenueTotal=_decimal_value(trading.get("OperatingRevenueTotal")),
            SalesGrossReceiptsTotal=_decimal_value(trading.get("SalesGrossReceiptsTotal")),
            GrossRcptFromProfession=_decimal_value(trading.get("GrossRcptFromProfession")),
            ExciseCustomsVAT=TradingExciseCustomsVAT(**{
                key: _decimal_value(excise_customs_vat.get(key))
                for key in ("UnionExciseDuty", "ServiceTax", "VATorSaleTax", "CentralGoodServiceTax", "StateGoodServiceTax", "IntegratedGoodServiceTax", "UnionTerrGoodServiceTax", "OthDutyTaxCess", "TotExciseCustomsVAT")
            }) if isinstance(excise_customs_vat, Mapping) else TradingExciseCustomsVAT(),
            TotRevenueFrmOperations=_decimal_value(trading.get("TotRevenueFrmOperations")),
            ClsngStckOfFinishedStcks=_decimal_value(trading.get("ClsngStckOfFinishedStcks")),
            TardingAccTotCred=_decimal_value(trading.get("TardingAccTotCred")),
            OpngStckOfFinishedStcks=_decimal_value(trading.get("OpngStckOfFinishedStcks")),
            Purchases=_decimal_value(trading.get("Purchases")),
            DirectExpenses=_decimal_value(trading.get("DirectExpenses")),
            CarriageInward=_decimal_value(trading.get("CarriageInward")),
            PowerAndFuel=_decimal_value(trading.get("PowerAndFuel")),
            OtherIncDtls=_trading_other_income_entries(trading.get("OtherIncDtls")),
            DirectExpensesTotal=_decimal_value(trading.get("DirectExpensesTotal")),
            DutyTaxPay=TradingDutyTaxPay(
                ExciseCustomsVAT=TradingDutyTaxPayExciseCustomsVAT(**{
                    key: _decimal_value(duty_tax_pay_excise.get(key))
                    for key in ("CustomDuty", "CounterVailDuty", "SplAddDuty", "UnionExciseDuty", "ServiceTax", "VATorSaleTax", "CentralGoodServiceTax", "StateGoodServiceTax", "IntegratedGoodServiceTax", "UnionTerrGoodServiceTax", "OthDutyTaxCess", "TotExciseCustomsVAT")
                }) if isinstance(duty_tax_pay_excise, Mapping) else TradingDutyTaxPayExciseCustomsVAT(),
            ),
            GoodsCostPrdcdFrmMA=_decimal_value(trading.get("GoodsCostPrdcdFrmMA")),
            GrossProfitFrmBusProf=_decimal_value(trading.get("GrossProfitFrmBusProf")),
            TurnoverIntradayTrd=_decimal_value(trading.get("TurnoverIntradayTrd")),
            IncomeIntradayTrd=_decimal_value(trading.get("IncomeIntradayTrd")),
            TurnoverFutureTrd=_decimal_value(trading.get("TurnoverFutureTrd")),
            IncomeFutureTrd=_decimal_value(trading.get("IncomeFutureTrd")),
        ) if trading else None,
    )


def _normalize_parta_pl(value: Any) -> Any:
    """Normalize an official PARTA_PL workspace tree into finite Decimal leaves."""
    if isinstance(value, Mapping):
        return {str(key): _normalize_parta_pl(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_parta_pl(item) for item in value]
    if isinstance(value, (int, float, Decimal)):
        return _decimal_value(value)
    return value


def _profit_and_loss(draft: ReturnDraft) -> ProfitAndLoss | None:
    """Map the authoritative PARTA_PL workspace totals when present."""
    workspace = _core_schedule(draft, "PARTA_PL")
    if not workspace:
        return None
    part_a = PLPartA.model_validate(_normalize_parta_pl(workspace))
    no_books = part_a.NoBooksOfAccPL
    tax = part_a.TaxProvAppr
    credits = part_a.CreditsToPL
    debits = part_a.DebitsToPL
    return ProfitAndLoss(
        gross_profit=_decimal_value(workspace.get("GrossProfit")),
        expenditure=_decimal_value(workspace.get("Expenditure")),
        net_income_from_special_activity=_decimal_value(workspace.get("NetIncomeFrmSpecActivity")),
        turnover_from_special_activity=_decimal_value(workspace.get("TurnverFrmSpecActivity")),
        part_a=part_a,
        no_books_gross_receipt=no_books.GrossReceipt,
        no_books_gross_profit=no_books.GrossProfit,
        no_books_expenses=no_books.Expenses,
        no_books_net_profit=no_books.NetProfit,
        provision_current_tax=tax.ProvForCurrTax,
        provision_deferred_tax=tax.ProvDefTax,
        profit_after_tax=tax.ProfitAfterTax,
        gross_profit_from_trading=credits.GrossProfitTrnsfFrmTrdAcc or Decimal("0"),
        other_income_breakdown=credits.OthIncome,
        other_income=credits.OthIncome.TotOthIncome,
        total_credits=credits.TotCreditsToPL,
        total_expenses=debits.OtherExpenses,
        pbidta=debits.PBIDTA,
        interest_expense=debits.InterestExpdrtDtls,
        depreciation_amortization=debits.DepreciationAmort,
        profit_before_tax=debits.PBT,
    )


_ZERO = Decimal("0")


# Every possible leaf field across the three DepreciationDetail shapes
# (the 16-21-field DPM/DOA block, and the smaller 11-13-field Rate45
# block). Passing the full superset to `model_validate()` is safe for
# either shape: Pydantic silently ignores keys a given model doesn't
# declare (none of these classes set `extra="forbid"`), so one dict
# construction serves both without needing to know which shape a given
# rate block is ahead of time.
_DEPRECIATION_DETAIL_KEYS = (
    "WDVFirstDay", "AdjustmentSec115BAC", "Total", "AdditionsGrThan180Days",
    "RealizationTotalPeriod", "FullRateDeprAmt", "AdditionsLessThan180Days",
    "RealizationPeriodLessThan180days", "HalfRateDeprAmt", "DepreciationAtFullRate",
    "DepreciationAtHalfRate", "AddlnDeprOnGT180DayAdditions",
    "AddlnDeprOnLessThan180DayAdditions", "AddlnDeprOnAssetLessThan180Days",
    "TotalDepreciation", "DepDisAllowUs38_2", "NetAggregateDepreciation",
    "ProportionateAggDepreciation", "ExpdrOnTrforSaleAsset", "CapGainUs50", "WDVLastDay",
)


def _dpm_rate_detail(raw: Any) -> dict[str, Any] | None:
    """Return one Schedule DPM/DOA rate block's DepreciationDetail dict if
    it carries any real (nonzero) taxpayer-entered value, else None.

    The frontend's ITR3BusinessAuxiliaryManager only ever writes a rate
    block's DERIVED fields (Total/FullRateDeprAmt/HalfRateDeprAmt/
    TotalDepreciation/NetAggregateDepreciation/WDVLastDay) once the block
    already exists (i.e. the taxpayer has typed into at least one of its
    own raw-input fields) -- an untouched block is simply absent, not
    zero-filled. But once a block DOES exist, its OTHER required raw-input
    fields (AdditionsGrThan180Days, RealizationTotalPeriod,
    DepreciationAtFullRate, ...) are still genuinely optional from the
    taxpayer's own point of view -- a furniture block with no additions
    and no half-rate depreciation this year is correctly left blank on
    those specific inputs, not typed as an explicit "0". Every leaf field
    here therefore defaults to 0 when missing, matching the official
    schema's own per-field `"default": 0` -- constructing the model
    directly from whatever subset the frontend happened to send would
    raise a hard Pydantic ValidationError (missing required field) for
    this entirely ordinary, expected input shape.
    """
    if not isinstance(raw, Mapping):
        return None
    detail = raw.get("DepreciationDetail")
    if not isinstance(detail, Mapping):
        return None
    if not any(_decimal_value(v) != _ZERO for v in detail.values()):
        return None
    return {key: _decimal_value(detail.get(key)) for key in _DEPRECIATION_DETAIL_KEYS}


def _depreciation_schedules(draft: ReturnDraft) -> ITR3DepreciationSchedules | None:
    """Map the real, taxpayer-entered Schedule DPM/DOA/DEP/DCG data.

    ``draft.itr3BusinessWorkspace.depreciationSchedules`` (the typed field
    this schedule used to read exclusively) is never populated by any
    frontend code -- a pure dead end. The actual, working editor
    (``ITR3BusinessAuxiliaryManager.tsx``) writes into
    ``draft.itr3BusinessWorkspace.auxiliary["ScheduleDPM"/"ScheduleDOA"]``
    instead, keyed by the exact official JSON field names, with its own
    client-side ``recompute()`` already deriving every statutory total
    (FullRateDeprAmt, TotalDepreciation, NetAggregateDepreciation,
    CapGainUs50, WDVLastDay, ...) from the taxpayer's raw block facts --
    this is a genuine, already-working depreciation engine, just
    implemented in the frontend rather than the backend.

    Schedule DEP/DCG's own summary figures are NOT computed by that
    frontend code at all (their fields are marked read-only there with
    nothing ever writing to them), so both are derived here from the
    mapped DPM/DOA block totals, matching the official form's own
    item-by-item cross-references exactly: Schedule DEP item 1a = Schedule
    DPM item 17(i) (NetAggregateDepreciation of the 15% block); Schedule
    DCG item 1a = Schedule DPM item 20(i) (CapGainUs50 of the same block);
    and so on for every rate across both plant/machinery and the four DOA
    asset categories.
    """
    auxiliary = draft.itr3BusinessWorkspace.auxiliary
    dpm_raw = auxiliary.get("ScheduleDPM") if isinstance(auxiliary, Mapping) else None
    doa_raw = auxiliary.get("ScheduleDOA") if isinstance(auxiliary, Mapping) else None
    dpm_pm = dpm_raw.get("PlantMachinery") if isinstance(dpm_raw, Mapping) else None

    dpm_rates: dict[str, Any] = {}
    for rate in ("Rate15", "Rate30", "Rate40", "Rate45"):
        detail = _dpm_rate_detail(dpm_pm.get(rate) if isinstance(dpm_pm, Mapping) else None)
        if detail is not None:
            dpm_rates[rate] = {"DepreciationDetail": detail}
    schedule_dpm = ScheduleDPM.model_validate({"PlantMachinery": dpm_rates}) if dpm_rates else None

    doa_land_raw = doa_raw.get("Land") if isinstance(doa_raw, Mapping) else None
    land_detail = doa_land_raw.get("DepreciationDetail") if isinstance(doa_land_raw, Mapping) else None
    land_used = isinstance(land_detail, Mapping) and any(_decimal_value(v) != _ZERO for v in land_detail.values())

    doa_building_raw = doa_raw.get("Building") if isinstance(doa_raw, Mapping) else None
    building_rates: dict[str, Any] = {}
    for rate in ("Rate5", "Rate10", "Rate40"):
        detail = _dpm_rate_detail(doa_building_raw.get(rate) if isinstance(doa_building_raw, Mapping) else None)
        if detail is not None:
            building_rates[rate] = {"DepreciationDetail": detail}

    def _single_doa_block(schedule_key: str, rate_key: str) -> dict[str, Any] | None:
        source = doa_raw.get(schedule_key) if isinstance(doa_raw, Mapping) else None
        detail = _dpm_rate_detail(source.get(rate_key) if isinstance(source, Mapping) else None)
        return {rate_key: {"DepreciationDetail": detail}} if detail is not None else None

    doa_fields: dict[str, Any] = {}
    if land_used:
        # Land has only WDVFirstDay/WDVLastDay, both required, neither
        # backed by a readonly/derived field on the frontend -- default
        # the same way as every other block for the identical reason.
        doa_fields["Land"] = {"DepreciationDetail": {
            "WDVFirstDay": _decimal_value(land_detail.get("WDVFirstDay")),
            "WDVLastDay": _decimal_value(land_detail.get("WDVLastDay")),
        }}
    if building_rates:
        doa_fields["Building"] = building_rates
    furniture = _single_doa_block("FurnitureFittings", "Rate10")
    if furniture:
        doa_fields["FurnitureFittings"] = furniture
    intangible = _single_doa_block("IntangibleAssets", "Rate25")
    if intangible:
        doa_fields["IntangibleAssets"] = intangible
    ships = _single_doa_block("Ships", "Rate20")
    if ships:
        doa_fields["Ships"] = ships
    schedule_doa = ScheduleDOA.model_validate(doa_fields) if doa_fields else None

    if schedule_dpm is None and schedule_doa is None:
        return None

    pm = schedule_dpm.PlantMachinery if schedule_dpm is not None else None
    dep_15 = pm.Rate15.DepreciationDetail.NetAggregateDepreciation if pm and pm.Rate15 else _ZERO
    cg_15 = pm.Rate15.DepreciationDetail.CapGainUs50 if pm and pm.Rate15 else _ZERO
    dep_30 = pm.Rate30.DepreciationDetail.NetAggregateDepreciation if pm and pm.Rate30 else _ZERO
    cg_30 = pm.Rate30.DepreciationDetail.CapGainUs50 if pm and pm.Rate30 else _ZERO
    dep_40 = pm.Rate40.DepreciationDetail.NetAggregateDepreciation if pm and pm.Rate40 else _ZERO
    cg_40 = pm.Rate40.DepreciationDetail.CapGainUs50 if pm and pm.Rate40 else _ZERO
    dep_45 = pm.Rate45.DepreciationDetail.NetAggregateDepreciation if pm and pm.Rate45 else _ZERO
    cg_45 = pm.Rate45.DepreciationDetail.CapGainUs50 if pm and pm.Rate45 else _ZERO
    pm_total_dep = dep_15 + dep_30 + dep_40 + dep_45
    pm_total_cg = cg_15 + cg_30 + cg_40 + cg_45

    bld = schedule_doa.Building if schedule_doa is not None else None
    bdep_5 = bld.Rate5.DepreciationDetail.NetAggregateDepreciation if bld and bld.Rate5 else _ZERO
    bcg_5 = bld.Rate5.DepreciationDetail.CapGainUs50 if bld and bld.Rate5 else _ZERO
    bdep_10 = bld.Rate10.DepreciationDetail.NetAggregateDepreciation if bld and bld.Rate10 else _ZERO
    bcg_10 = bld.Rate10.DepreciationDetail.CapGainUs50 if bld and bld.Rate10 else _ZERO
    bdep_40 = bld.Rate40.DepreciationDetail.NetAggregateDepreciation if bld and bld.Rate40 else _ZERO
    bcg_40 = bld.Rate40.DepreciationDetail.CapGainUs50 if bld and bld.Rate40 else _ZERO
    bld_total_dep = bdep_5 + bdep_10 + bdep_40
    bld_total_cg = bcg_5 + bcg_10 + bcg_40

    furn_rate = schedule_doa.FurnitureFittings.Rate10 if schedule_doa and schedule_doa.FurnitureFittings else None
    furn_dep = furn_rate.DepreciationDetail.NetAggregateDepreciation if furn_rate else _ZERO
    furn_cg = furn_rate.DepreciationDetail.CapGainUs50 if furn_rate else _ZERO

    intang_rate = schedule_doa.IntangibleAssets.Rate25 if schedule_doa and schedule_doa.IntangibleAssets else None
    intang_dep = intang_rate.DepreciationDetail.NetAggregateDepreciation if intang_rate else _ZERO
    intang_cg = intang_rate.DepreciationDetail.CapGainUs50 if intang_rate else _ZERO

    ships_rate = schedule_doa.Ships.Rate20 if schedule_doa and schedule_doa.Ships else None
    ships_dep = ships_rate.DepreciationDetail.NetAggregateDepreciation if ships_rate else _ZERO
    ships_cg = ships_rate.DepreciationDetail.CapGainUs50 if ships_rate else _ZERO

    total_dep = pm_total_dep + bld_total_dep + furn_dep + intang_dep + ships_dep
    total_cg = pm_total_cg + bld_total_cg + furn_cg + intang_cg + ships_cg

    schedule_dep = ScheduleDEP.model_validate({
        "SummaryFromDeprSch": {
            "PlantMachinerySummary": {"DeprBlockTot15Percent": dep_15, "DeprBlockTot30Percent": dep_30, "DeprBlockTot40Percent": dep_40, "DeprBlockTot45Percent": dep_45, "TotPlntMach": pm_total_dep} if pm else None,
            "BuildingSummary": {"DeprBlockTot5Percent": bdep_5, "DeprBlockTot10Percent": bdep_10, "DeprBlockTot40Percent": bdep_40, "TotBuildng": bld_total_dep} if bld else None,
            "FurnitureSummary": furn_dep if furn_rate else None,
            "IntangibleAssetSummary": intang_dep if intang_rate else None,
            "ShipsSummary": ships_dep if ships_rate else None,
            "TotalDepreciation": total_dep,
        }
    })

    schedule_dcg = ScheduleDCG.model_validate({
        "SummaryFromDeprSchCG": {
            "PlantMachinerySummaryCG": {"DeprBlockTot15Percent": cg_15, "DeprBlockTot30Percent": cg_30, "DeprBlockTot40Percent": cg_40, "DeprBlockTot45Percent": cg_45, "TotPlntMach": pm_total_cg} if pm else None,
            "BuildingSummaryCG": {"DeprBlockTot5Percent": bcg_5, "DeprBlockTot10Percent": bcg_10, "DeprBlockTot40Percent": bcg_40, "TotBuildng": bld_total_cg} if bld else None,
            "FurnitureSummary": furn_cg if furn_rate else None,
            "IntangibleAssetSummary": intang_cg if intang_rate else None,
            "ShipsSummary": ships_cg if ships_rate else None,
            "TotalDepreciation": total_cg,
        }
    })

    return ITR3DepreciationSchedules(
        schedule_dpm=schedule_dpm, schedule_doa=schedule_doa,
        schedule_dep=schedule_dep, schedule_dcg=schedule_dcg,
    )


def _business_income(draft: ReturnDraft, schedule_esr: "ScheduleESR | None" = None) -> BusinessIncome:
    """Map canonical business rows and the persisted Schedule BP workspace."""
    if not draft.businesses:
        raise DraftMappingError(
            "ITR-3 requires business or professional income; ReturnDraft.businesses is empty."
        )
    unsupported = [b for b in draft.businesses if b.scheme not in {"44AD", "44ADA", "44AE"}]
    if unsupported:
        raise DraftMappingError("ReturnDraft contains unsupported business schemes for the ITR-3 foundation.")
    declared = sum((b.declaredIncome for b in draft.businesses), Decimal("0"))
    presumptive_44ad = sum((b.declaredIncome for b in draft.businesses if b.scheme == "44AD"), Decimal("0"))
    presumptive_44ada = sum((b.declaredIncome for b in draft.businesses if b.scheme == "44ADA"), Decimal("0"))
    presumptive_44ae = sum((b.declaredIncome for b in draft.businesses if b.scheme == "44AE"), Decimal("0"))
    core = draft.itr3BusinessWorkspace.core
    bp = core.get("ITR3ScheduleBP", {}) if isinstance(core, dict) else {}
    regular = bp.get("BusinessIncOthThanSpec", {}) if isinstance(bp, dict) else {}
    income_heads = regular.get("IncRecCredPLOthHeadDtls", {}) if isinstance(regular.get("IncRecCredPLOthHeadDtls"), dict) else {}
    expense_heads = regular.get("ExpDebToPLOthHeadDtls", {}) if isinstance(regular.get("ExpDebToPLOthHeadDtls"), dict) else {}
    exempt_credits = regular.get("IncCredPL", {}) if isinstance(regular.get("IncCredPL"), dict) else {}
    rule_profit = regular.get("ProfitFrmActCvrd", {}) if isinstance(regular.get("ProfitFrmActCvrd"), dict) else {}
    return BusinessIncome(
        net_profit_before_tax=_decimal_value(
            regular.get("ProfBfrTaxPL"), declared
        ),
        presumptive_44ad_income=presumptive_44ad,
        presumptive_44ada_income=presumptive_44ada,
        presumptive_44ae_income=presumptive_44ae,
        disallowance_us36=_decimal_value(regular.get("AmtDebPLDisallowUs36")),
        disallowance_us37=_decimal_value(regular.get("AmtDebPLDisallowUs37")),
        disallowance_us40=_decimal_value(regular.get("AmtDebPLDisallowUs40")),
        disallowance_us40a=_decimal_value(regular.get("AmtDebPLDisallowUs40A")),
        disallowance_us43b=_decimal_value(regular.get("AmtDebPLDisallowUs43B")),
        deemed_income_us41=_decimal_value(regular.get("DeemIncUs41")),
        deemed_income_us32ad=_decimal_value(regular.get("DeemIncUs32AD")),
        deemed_income_us33ab=_decimal_value(regular.get("DeemIncUs33AB")),
        deemed_income_us33aba=_decimal_value(regular.get("DeemIncUs33ABA")),
        deemed_income_us35aba=_decimal_value(regular.get("DeemIncUs35ABA")),
        deemed_income_us35abb=_decimal_value(regular.get("DeemIncUs35ABB")),
        deemed_income_us40a3a=_decimal_value(regular.get("DeemIncUs40A3A")),
        deemed_income_us43ca=_decimal_value(regular.get("DeemIncUs43CA")),
        deemed_income_us72a=_decimal_value(regular.get("DeemIncUs72A")),
        deemed_income_us80hhd=_decimal_value(regular.get("DeemIncUs80HHD")),
        deemed_income_us80ia=_decimal_value(regular.get("DeemIncUs80IA")),
        deduction_us32_1_iii=_decimal_value(regular.get("DeductUs32_1_iii")),
        icds_increase=_decimal_value(regular.get("IncProfDecLossAccICDSAdj")),
        icds_decrease=_decimal_value(regular.get("DecProfIncLossAccICDSAdj")),
        # Item 24 / item 31 -- other income not included / other amount
        # allowable as deduction. Item 24 additionally folds in item
        # 24(e) -- any Schedule ESR shortfall (AmtDebPL exceeding what's
        # actually allowable, e.g. a new-regime-disallowed section, see
        # `_esr_shortfall_addback`'s own citation of official rule #286)
        # -- additive with, not a replacement for, the taxpayer's own
        # separately-entered item 24 figure.
        other_additions=(
            _decimal_value(regular.get("AnyOthIncNotInclInExpDisallowPL"))
            + _esr_shortfall_addback(schedule_esr)
        ),
        other_deductions=_decimal_value(regular.get("AnyOthAmtAllDeduct")),
        # Items 3a-3g -- income credited to P&L belonging to another head.
        reallocation_income_salary=_decimal_value(income_heads.get("Salary")),
        reallocation_income_house_property=_decimal_value(income_heads.get("HouseProperty")),
        reallocation_income_capital_gains=_decimal_value(income_heads.get("CapitalGains")),
        reallocation_income_other_sources=_decimal_value(income_heads.get("OtherSources")),
        reallocation_income_dividend=_decimal_value(income_heads.get("Dividend")),
        reallocation_income_other_than_dividend=_decimal_value(income_heads.get("OtherThanDividend")),
        reallocation_income_115bbf=_decimal_value(income_heads.get("Us115BBF")),
        reallocation_income_115bbg=_decimal_value(income_heads.get("Us115BBG")),
        reallocation_income_115bbh=_decimal_value(income_heads.get("115BBH")),
        # Items 7a-7g -- expenses debited to P&L relating to another head.
        reallocation_expense_salary=_decimal_value(expense_heads.get("Salary")),
        reallocation_expense_house_property=_decimal_value(expense_heads.get("HouseProperty")),
        reallocation_expense_capital_gains=_decimal_value(expense_heads.get("CapitalGains")),
        reallocation_expense_other_sources=_decimal_value(expense_heads.get("OtherSources")),
        reallocation_expense_115bbf=_decimal_value(expense_heads.get("Us115BBF")),
        reallocation_expense_115bbg=_decimal_value(expense_heads.get("Us115BBG")),
        reallocation_expense_115bbh=_decimal_value(expense_heads.get("115BBH")),
        # Items 5a/5b/5c/5A -- exempt / not-chargeable income credited to P&L.
        exempt_income_firm_share=_decimal_value(exempt_credits.get("FirmShareInc")),
        exempt_income_aop_boi_share=_decimal_value(exempt_credits.get("AOPBOISharInc")),
        exempt_income_other=_decimal_value(exempt_credits.get("OthExempInc")),
        income_not_chargeable=_decimal_value(regular.get("IncCredPLNotChargable")),
        # Items 8a/8b -- expenses relating to exempt income.
        expense_relating_to_exempt_income=_decimal_value(regular.get("ExpDebToPLExemptInc")),
        expense_exempt_income_disallowed_us14a=_decimal_value(regular.get("ExpDebToPLExemptIncDisAllwUs14A")),
        # Items 19/23 -- additional disallowances.
        msme_interest_disallowance=_decimal_value(regular.get("InterestDisAllowUs23SMEAct")),
        other_addition_28_to_44da=_decimal_value(regular.get("OthItemDisallowUs28To44DA")),
        # Item 28 -- deduction u/s 35/35CCC/35CCD in excess of the amount
        # debited to P&L. The official form's own item 28 text cites this
        # figure as literally "item x(4) of Schedule ESR" (the ESR
        # schedule's own "Total" row, column 4) -- not an independently
        # re-derived figure. When Schedule ESR has been filled in (its own
        # itemized breakdown, auto-totaled by the frontend across all nine
        # section rows), that computed total is authoritative here, so a
        # taxpayer's raw `DebPLUs35ExcessAmt` entry can never silently
        # disagree with their own ESR disclosure. Falls back to the raw
        # Schedule-BP-workspace value (matching every sibling item 19/23/
        # 29/30's own established "entered directly" precedent from
        # Schedule 14's closure) when no ESR data exists at all -- a
        # taxpayer who only ever used Schedule BP's own quick field keeps
        # working exactly as before.
        section35_excess_deduction=(
            schedule_esr.DeductionUs35.TotUs35.DeductUs35.ExcessAmtOverDebPL
            if schedule_esr is not None
            else _decimal_value(regular.get("DebPLUs35ExcessAmt"))
        ),
        section40_now_allowable=_decimal_value(regular.get("AmtDisallUs40NowAllow")),
        section43b_now_allowable=_decimal_value(regular.get("AmtDisallUs43BNowAllow")),
        # Item 4b's own breakdown (Rule 7/7A/7B(1)/7B(1A)/8 activity profit).
        rule7_profit=_decimal_value(rule_profit.get("ProfitFrmActCvrdUndrRule7")),
        rule7a_profit=_decimal_value(rule_profit.get("ProfitFrmActCvrdUndrRule7A")),
        rule7b1_profit=_decimal_value(rule_profit.get("ProfitFrmActCvrdUndrRule7B1")),
        rule7b1a_profit=_decimal_value(rule_profit.get("ProfitFrmActCvrdUndrRule7B1A")),
        rule8_profit=_decimal_value(rule_profit.get("ProfitFrmActCvrdUndrRule8")),
        # Items 37a-37e -- the taxpayer's own rule-adjusted taxable income.
        rule7_taxable_income=_decimal_value(regular.get("ChrgblIncUndrRule7")),
        rule7a_deemed_income=_decimal_value(regular.get("DeemedChrgblIncUndrRule7A")),
        rule7b1_deemed_income=_decimal_value(regular.get("DeemedChrgblIncUndrRule7B1")),
        rule7b1a_deemed_income=_decimal_value(regular.get("DeemedChrgblIncUndrRule7B1A")),
        rule8_deemed_income=_decimal_value(regular.get("DeemedChrgblIncUndrRule8")),
    )


def draft_to_itr3_input(draft: ReturnDraft) -> tuple[ITR3Input, dict[str, Any]]:
    """Map a canonical draft to ITR3Input without inventing identity data."""
    if draft.form != "ITR-3":
        raise DraftMappingError("draft_to_itr3_input requires draft.form == 'ITR-3'.")
    itr1, breakdown = draft_to_itr1_input(draft)
    values = itr1.model_dump()
    oi_source = draft.itr3BusinessWorkspace.core.get("PARTA_OI")
    pl_source = draft.itr3BusinessWorkspace.core.get("PARTA_PL")
    if isinstance(pl_source, Mapping):
        validate_parta_pl_arithmetic(pl_source)
    qd_source = draft.itr3BusinessWorkspace.core.get("PARTA_QD")
    oi = ITR3PartAOI.model_validate(oi_source) if isinstance(oi_source, Mapping) else None
    qd = ITR3PartAQD.model_validate(qd_source) if isinstance(qd_source, Mapping) else None
    icds_source = draft.itr3BusinessWorkspace.scheduleICDS or draft.itr3BusinessWorkspace.core.get("ScheduleICDS")
    esr_source = draft.itr3BusinessWorkspace.scheduleESR or draft.itr3BusinessWorkspace.core.get("ScheduleESR") or draft.itr3BusinessWorkspace.auxiliary.get("ScheduleESR")
    tpsa_source = draft.itr3BusinessWorkspace.scheduleTPSA or draft.itr3BusinessWorkspace.core.get("ScheduleTPSA") or draft.itr3BusinessWorkspace.auxiliary.get("ScheduleTPSA")
    gst_source = draft.itr3BusinessWorkspace.scheduleGST or draft.itr3BusinessWorkspace.core.get("ScheduleGST")
    schedule_icds = ScheduleICDS.model_validate(icds_source) if isinstance(icds_source, Mapping) else None
    _esr_normalized = (
        _normalize_esr_source(esr_source, is_new_regime=values["tax_regime"] == "new")
        if isinstance(esr_source, Mapping) else None
    )
    schedule_esr = ScheduleESR.model_validate(_esr_normalized) if _esr_normalized is not None else None
    schedule_tpsa = ITR3ScheduleTPSA.model_validate(tpsa_source) if isinstance(tpsa_source, Mapping) else None
    schedule_gst = ScheduleGST.model_validate(gst_source) if isinstance(gst_source, Mapping) else None
    schedule_80ia = ITR3Schedule80IA.model_validate(draft.itr3BusinessWorkspace.schedule80IA) if draft.itr3BusinessWorkspace.schedule80IA else None
    schedule_80ib = ITR3Schedule80IB.model_validate(draft.itr3BusinessWorkspace.schedule80IB) if draft.itr3BusinessWorkspace.schedule80IB else None
    schedule_80ic = ITR3Schedule80IC.model_validate(draft.itr3BusinessWorkspace.schedule80IC) if draft.itr3BusinessWorkspace.schedule80IC else None
    schedule_80ra = ITR3Schedule80RA.model_validate(draft.itr3BusinessWorkspace.schedule80RA) if draft.itr3BusinessWorkspace.schedule80RA else None
    schedule_10aa = ITR3Schedule10AA.model_validate(draft.itr3BusinessWorkspace.schedule10AA) if draft.itr3BusinessWorkspace.schedule10AA else None
    d = draft.deductions.section80D
    via = draft.deductions.chapterVIA
    def health(category: Any) -> ITR3Schedule80DHealth | None:
        rows = [ITR3Schedule80DInsurance(InsurerName=p.insurerName, PolicyNo=p.policyNo, HealthInsAmt=p.premiumAmount) for p in category.policies if p.premiumAmount > 0]
        return ITR3Schedule80DHealth(Sch80DInsDtls=rows, TotalPayments=sum((p.HealthInsAmt for p in rows), Decimal("0"))) if rows else None
    c = d.selfFamily; cs = d.selfFamilySenior; p = d.parents; ps = d.parentsSenior
    def premium(category: Any) -> Decimal:
        return sum((policy.premiumAmount for policy in category.policies), Decimal("0"))
    schedule_80d = ITR3Schedule80D(Sec80DSelfFamSrCtznHealth=ITR3Schedule80DCategory(
        SeniorCitizenFlag=d.selfSeniorCitizen, SelfAndFamily=premium(c) or None,
        HealthInsPremSlfFam=premium(c) or None, Sec80DSelfFamHIDtls=health(c), PrevHlthChckUpSlfFam=c.preventiveCheckup or None,
        SelfAndFamilySeniorCitizen=premium(cs) or None,
        HlthInsPremSlfFamSrCtzn=premium(cs) or None, Sec80DSelfFamSrCtznHIDtls=health(cs), PrevHlthChckUpSlfFamSrCtzn=cs.preventiveCheckup or None,
        MedicalExpSlfFamSrCtzn=cs.medicalExpense or None, ParentsSeniorCitizenFlag=d.parentsSeniorCitizen,
        Parents=premium(p) or None, HlthInsPremParents=premium(p) or None, Sec80DParentsHIDtls=health(p),
        PrevHlthChckUpParents=p.preventiveCheckup or None, ParentsSeniorCitizen=premium(ps) or None,
        HlthInsPremParentsSrCtzn=premium(ps) or None, Sec80DParentsSrCtznHIDtls=health(ps), PrevHlthChckUpParentsSrCtzn=ps.preventiveCheckup or None,
        MedicalExpParentsSrCtzn=ps.medicalExpense or None, EligibleAmountOfDedn=via.section80D)) if via.section80D > 0 else None
    dd = ITR3Schedule80DD(NatureOfDisability=via.section80DDNatureOfDisability, TypeOfDisability=via.section80DDTypeOfDisability, DeductionAmount=via.section80DD, DependentType=via.section80DDDependentType, DependentPan=via.section80DDDependentPAN or None, DependentAadhaar=via.section80DDDependentAadhaar or None, Form10IAFilingDate=via.section80DDForm10IA.filingDate, Form10IAAckNum=via.section80DDForm10IA.acknowledgementNumber or None, FormAckNum11A=via.section80DDForm10IA.formAckNum11A or None, UDIDNum=via.section80DDUDIDNumber or None) if via.section80DD > 0 else None
    uu = ITR3Schedule80U(NatureOfDisability=via.section80UNatureOfDisability, TypeOfDisability=via.section80UTypeOfDisability, DeductionAmount=via.section80U, Form10IAFilingDate=via.section80UForm10IA.filingDate, Form10IAAckNum=via.section80UForm10IA.acknowledgementNumber or None, FormAckNum11A=via.section80UForm10IA.formAckNum11A or None, UDIDNum=via.section80UUDIDNumber or None) if via.section80U > 0 else None
    via = draft.deductions.chapterVIA
    details = ITR3DeductionDetails(
        investments_80c=[ITR3DeductionDonation(donee_name=row.institutionName, transaction_ref=row.identificationNo, other_mode_amount=row.amount) for row in draft.deductions.section80C if row.amount > 0],
        donations_80g=[ITR3DeductionDonation(category=row.category, donee_name=row.doneeName, donee_pan=row.doneePAN, address_line=row.addrDetail, city=row.city, state_code=row.stateCode, pin_code=row.pinCode, cash_amount=row.donationAmtCash, other_mode_amount=row.donationAmtOtherMode, transaction_ref=row.transactionRefNum, ifsc_code=row.ifscCode) for row in draft.deductions.section80G if row.donationAmtCash + row.donationAmtOtherMode > 0],
        donations_80gga=[ITR3DeductionDonation(category=row.relevantClause, donee_name=row.doneeName, donee_pan=row.doneePAN, address_line=row.addressLine, city=row.city, state_code=row.stateCode, pin_code=row.pinCode, cash_amount=row.cashAmount, other_mode_amount=row.otherModeAmount) for row in draft.deductions.schedule80GGA if row.cashAmount + row.otherModeAmount > 0],
        contributions_80ggc=[ITR3DeductionDonation(donee_name=row.politicalPartyName, donee_pan=row.politicalPartyPAN, contribution_date=row.contributionDate, transaction_ref=row.transactionRef, ifsc_code=row.ifscCode, political_party_name=row.politicalPartyName, political_party_pan=row.politicalPartyPAN, cash_amount=row.cashAmount, other_mode_amount=row.otherModeAmount) for row in draft.deductions.schedule80GGC if row.cashAmount + row.otherModeAmount > 0],
        loans=[ITR3DeductionLoan(section=row.section, loan_taken_from=row.loanTakenFrom, lender_name=row.lenderName, loan_account_no=row.loanAccountNo, date_of_loan=row.dateOfLoan, total_loan_amount=row.totalLoanAmount, outstanding_amount=row.outstandingAmount, interest_amount=row.interestAmount, vehicle_reg_no=row.vehicleRegNo) for row in draft.deductions.loans.loans if row.interestAmount > 0],
        stamp_duty_80eea=draft.deductions.loans.section80EEAStampDutyValue,
    )
    cg_scrips, cg_115ad_scrips, _ = _map_112a_scrips(draft)
    cg_transactions = (
        _map_immovable_gains(draft) + _map_equity_stt_stcg(draft) + _map_other_assets(draft)
        + _map_nri_fii_securities(draft) + _map_nri_112_115_securities(draft)
    )
    cg_buyback_losses = _map_buyback_losses(draft)
    vda_transactions = _map_vda_transactions(draft)
    fsi_entries = _map_fsi_entries(draft)
    tr1_entries = _map_tr1_entries(draft)
    foreign_assets = _map_foreign_assets(draft)
    asset_liability = _map_asset_liability(draft)
    schedule_5a = _map_schedule_5a(draft)
    esop_deferrals = _map_esop_deferrals(draft)
    input_data = ITR3Input(
        schedule_s_employers=[ITR3ScheduleSEmployer(
            employer_name=e.employerName or e.customEmployerName,
            nature_of_employment=e.natureOfEmployment or "OTH",
            employer_tan=e.employerTAN or None,
            address_detail=e.employerAddress,
            city=e.employerCity or e.city,
            state_code=e.employerStateCode,
            pin_code=e.employerPinCode or None,
            zip_code=e.employerZipCode or None,
            basic=e.basic, da=e.da, commission=e.commission, hra=e.hra,
            bonus=e.bonus, allowances=e.allowances, lta=e.lta,
            other_allowance=e.otherAllowance, arrear_salary=e.arrearSalary,
            perquisites=e.perquisites, profits_in_lieu=e.profitsInLieu,
            income_notified_89a=e.incomeNotified89A,
            income_notified_other_89a=e.incomeNotifiedOther89A,
            income_notified_prior_year_89a=e.incomeNotifiedPriorYear89A,
            salary_nature_rows=[{"NatureDesc": r.natureCode, "OthNatOfInc": r.otherDescription, "OthAmount": r.amount} for r in e.salaryNatureRows],
            perquisite_nature_rows=[{"NatureDesc": r.natureCode, "OthNatOfInc": r.otherDescription, "OthAmount": r.amount} for r in e.perquisiteNatureRows],
            profit_in_lieu_nature_rows=[{"NatureDesc": r.natureCode, "OthNatOfInc": r.otherDescription, "OthAmount": r.amount} for r in e.profitInLieuNatureRows],
            notified_89a_country_rows=e.incomeNotified89ACountryRows,
            rent_paid=e.rentPaid,
            is_metro_city=e.isMetroCity,
            section10_exemption_rows=[{"SalNatureDesc": r.natureCode, "SalOthNatOfInc": r.otherDescription, "SalOthAmount": r.amount} for r in e.section10ExemptionRows],
        ) for e in draft.employers] or None,
        schedule_hp_properties=[ITR3ScheduleHPProperty(
            sequence_no=p.propertySequenceNo or i,
            address_detail=p.address,
            city=p.city,
            state_code=p.state,
            country_code=p.countryCode,
            pin_code=p.pinCode or None,
            zip_code=p.zipCode or None,
            property_owner=p.propertyOwnerType,
            property_owner_other=p.propertyOwnerOther or None,
            co_owned=p.isCoOwned,
            assessee_share_percent=p.ownershipShare,
            property_type={"SELF_OCCUPIED": "S", "LET_OUT": "L", "DEEMED_LET_OUT": "D"}.get(str(p.propertyType), str(p.propertyType)),
            annual_lettable_value=p.annualLettingValue or p.annualRent,
            rent_not_realized=p.unrealizedRent,
            local_taxes=p.municipalTaxesPaid,
            # Form item 1f = own-share % x item 1e (1a-1d). Computed directly
            # from the raw per-property inputs rather than trusting
            # p.netAnnualValue, which is never actually written back with a
            # real computed value anywhere in the frontend (it sits at its
            # factory default of 0) -- and even when populated, item 1e
            # itself (see _schedule_hp's BalanceALV) must NOT already have
            # the ownership share applied, so reusing it here would double
            # the wrong direction of the same defect.
            annual_value_owned=(
                max(Decimal("0"), (p.annualLettingValue or p.annualRent) - p.unrealizedRent - p.municipalTaxesPaid)
                * (p.ownershipShare / Decimal("100"))
            ),
            standard_deduction=p.standardDeduction30Pct,
            interest_on_loan=p.interestOnLoan,
            income_of_hp=p.incomeFromHP,
            arrears_unrealised_rent=p.arrearsOfRent,
            home_loan_details=[{"LoanTknFrom": l.lenderType, "BankOrInstnName": l.lenderName, "LoanAccNoOfBankOrInstnRefNo": l.loanAccountNo, "DateofLoan": l.dateOfLoan, "TotalLoanAmt": l.totalLoanAmount, "LoanOutstndngAmt": l.loanOutstandingAmount, "InterestUs24B": l.interestUs24B} for l in p.homeLoans],
            co_owner_details=[{"CoOwnersSNo": c.coOwnerSNo or j, "NameCoOwner": c.name, "PAN_CoOwner": c.pan or None, "Aadhaar_CoOwner": c.aadhaar or None, "PercentShareProperty": c.share} for j, c in enumerate(p.coOwners, 1)],
            tenant_details=[{"TenantSNo": t.tenantSNo or j, "NameofTenant": t.name, "PANofTenant": t.pan or None, "AadhaarofTenant": t.aadhaar or None, "PANTANofTenant": t.panOrTan or None} for j, t in enumerate(p.tenantDetails, 1)],
        ) for i, p in enumerate(draft.houseProperties, 1)] or None,
        age_bracket=values["age_bracket"],
        tax_regime=values["tax_regime"],
        residential_status=_RESIDENTIAL_STATUS.get(
            draft.personal.residentialStatus,
            ITR3ResidentialStatus.RESIDENT,
        ),
        filing_section=_FILING_SECTION.get(
            str(draft.filing.filingSection),
            ReturnFileSection.ON_TIME_139_1,
        ),
        business_income=_business_income(draft, schedule_esr),
        depreciation_schedules=draft.itr3BusinessWorkspace.depreciationSchedules or _depreciation_schedules(draft),
        business_accounts=_business_accounts(draft),
        parta_oi=oi,
        parta_qd=qd,
        cg_transactions=cg_transactions,
        cg_112a_scrips=cg_scrips,
        **cg_buyback_losses,
        cg_115ad_scrips=cg_115ad_scrips,
        vda_transactions=vda_transactions,
        spi_entries=[SPIEntry(specified_person_name=row.specifiedPersonName, pan=row.pan or None, relationship=row.relationship, amount_included=row.amountIncluded, head_of_income=row.headOfIncome) for row in draft.clubbedIncome if row.specifiedPersonName and row.relationship],
        pti_entries=[PTIEntry(entity_name=row.entityName, entity_pan=row.entityPAN, income_head=row.incomeHead, section=row.section, income_amount=row.incomeAmount, tds_credit=row.tdsCredit) for row in draft.passThroughIncomeEntries if row.entityName and row.entityPAN],
        si_entries=[ScheduleSIEntry(section=entry.section, description=entry.description or None, gross_income=entry.grossIncome, deductions=entry.deductions, tax_rate_pct=entry.taxRatePct) for entry in draft.scheduleSIEntries],
        schedule_icds=schedule_icds,
        schedule_esr=schedule_esr,
        schedule_tpsa=schedule_tpsa,
        schedule_gst=schedule_gst,
        schedule_80ia=schedule_80ia,
        schedule_80ib=schedule_80ib,
        schedule_80ic=schedule_80ic,
        schedule_80ra=schedule_80ra,
        schedule_10aa=schedule_10aa,
        schedule_80d=schedule_80d,
        schedule_80dd=dd,
        schedule_80u=uu,
        profit_and_loss=_profit_and_loss(draft),
        balance_sheet=_balance_sheet(draft),
        audit_info=_audit_info(draft),
        nature_of_business=[
            NatureOfBusiness(
                code=row.get("Code", ""), trade_name=row.get("TradeName1") or None,
                description=row.get("Description") or None,
            )
            for row in (_core_schedule(draft, "PartA_GEN2") or {}).get("NatOfBus", {}).get("NatureOfBusiness", [])
            if isinstance(row, Mapping) and _NATURE_OF_BUSINESS_CODE.fullmatch(str(row.get("Code", "")))
        ] or [
            NatureOfBusiness(code=row.code, trade_name=row.tradeName or None, description=row.description or None)
            for row in draft.itr3NatureOfBusiness
            if _NATURE_OF_BUSINESS_CODE.fullmatch(row.code)
        ] or None,
        salary_income=values.get("salary_income"),
        house_property_income=values.get("house_property_income"),
        other_sources_income=values.get("other_sources_income"),
        deductions_chapter6a=values.get("deductions_chapter6a"),
        deduction_details=details,
        fsi_entries=fsi_entries,
        tr1_entries=tr1_entries,
        foreign_assets=foreign_assets,
        asset_liability=asset_liability,
        schedule_5a=schedule_5a,
        esop_deferrals=esop_deferrals,
        tax_payment_entries=values.get("tax_payment_entries", []),
        tds3_entries=values.get("tds3_entries"),
        tds3_filing_details=values.get("tds3_filing_details", []),
        foreign_tax_relief_refunded=values.get("foreign_tax_relief_refunded", False),
        foreign_tax_relief_refunded_amount=values.get("foreign_tax_relief_refunded_amount", Decimal("0")),
        tds1_entries=values.get("tds1_entries"),
        tds2_entries=values.get("tds2_entries"),
        tcs_entries=values.get("tcs_entries"),
        advance_tax_paid=values.get("advance_tax_paid", Decimal("0")),
        advance_tax_q1=values.get("advance_tax_q1"),
        advance_tax_q2=values.get("advance_tax_q2"),
        advance_tax_q3=values.get("advance_tax_q3"),
        advance_tax_q4=values.get("advance_tax_q4"),
        self_assessment_tax_paid=values.get("self_assessment_tax_paid", Decimal("0")),
        filing_date=values.get("filing_date"),
        due_date=values.get("due_date"),
        assessee_pan=draft.personal.pan or None,
        assessee_first_name=draft.personal.firstName,
        assessee_middle_name=draft.personal.middleName,
        assessee_last_name=draft.personal.surnameOrOrgName,
        assessee_dob=draft.personal.dateOfBirth or None,
        assessee_father_name=draft.personal.fatherName,
        assessee_status=(
            draft.personal.assesseeStatus if draft.personal.assesseeStatus in ("I", "H") else "I"
        ),
        verification_place=draft.verification.place or None,
        verification_date=draft.verification.date or None,
        residence_no=draft.personal.flatNo or draft.personal.residenceName or None,
        residence_name=draft.personal.residenceName or None,
        road_or_street=draft.personal.roadOrStreet or None,
        locality=draft.personal.localityOrArea or None,
        city=draft.personal.city or None,
        state_code=draft.personal.stateCode or None,
        country_code=draft.personal.countryCode or None,
        pin_code=draft.personal.pinCode or None,
        zip_code=draft.personal.zipCode or None,
        mobile_country_code=draft.personal.mobileCountryCode or "91",
        mobile_no=draft.personal.mobile or None,
        email=draft.personal.email or None,
        assessee_aadhaar=draft.personal.aadhaar or None,
        # PDF A17's own "Residential/Office Phone Number with STD code" --
        # shares the draft's landline field with ITR-4's identical Address.
        # Phone block (see PersonalInfo.landlineStdCode's own docstring);
        # "0"/"0" is the draft's own default for "no landline declared" and
        # is treated as absent here, matching that field's documented intent.
        office_phone_std_code=(
            draft.personal.landlineStdCode
            if draft.personal.landlineStdCode not in ("", "0") else None
        ),
        office_phone_no=(
            draft.personal.landlinePhoneNo
            if draft.personal.landlinePhoneNo not in ("", "0") else None
        ),
        secondary_mobile_country_code=draft.personal.secondaryMobileCountryCode or None,
        secondary_mobile_no=draft.personal.secondaryMobile or None,
        secondary_email=draft.personal.secondaryEmail or None,
        secondary_address_different=draft.personal.secondaryAddressDifferent,
        alternate_residence_no=(
            draft.personal.alternateAddress.residenceNo or None
            if draft.personal.alternateAddress else None
        ),
        alternate_residence_name=(
            draft.personal.alternateAddress.residenceName or None
            if draft.personal.alternateAddress else None
        ),
        alternate_road_or_street=(
            draft.personal.alternateAddress.roadOrStreet or None
            if draft.personal.alternateAddress else None
        ),
        alternate_locality=(
            draft.personal.alternateAddress.localityOrArea or None
            if draft.personal.alternateAddress else None
        ),
        alternate_city=(
            draft.personal.alternateAddress.cityOrTownOrDistrict or None
            if draft.personal.alternateAddress else None
        ),
        alternate_state_code=(
            draft.personal.alternateAddress.stateCode or None
            if draft.personal.alternateAddress else None
        ),
        alternate_country_code=(
            draft.personal.alternateAddress.countryCode or None
            if draft.personal.alternateAddress else None
        ),
        alternate_pin_code=(
            draft.personal.alternateAddress.pinCode or None
            if draft.personal.alternateAddress else None
        ),
        alternate_zip_code=(
            draft.personal.alternateAddress.zipCode or None
            if draft.personal.alternateAddress else None
        ),
        # --- Filing Status (A19) ---
        form_10iea_earlier_ay_old_regime=draft.filing.form10IEAEarlierAYOldRegime,
        form_10iea_ass_year=draft.filing.form10IEAAssessmentYear or None,
        form_10iea_earlier_ay_ack_old_regime=draft.filing.form10IEAEarlierAYAckOldRegime or None,
        f10iea_earlier_ay_new_regime=draft.filing.form10IEAEarlierAYNewRegime,
        ass_yr_f10iea_new_tax_reg=draft.filing.form10IEANewRegimeAssessmentYear or None,
        form_10iea_earlier_ay_ack_new_regime=draft.filing.form10IEAEarlierAYAckNewRegime or None,
        f10iea_curr_ay_new_regime="Y" if draft.filing.form10IEACurrentAYNewRegime else "N",
        f10iea_date_curr_ay_new_tax=draft.filing.form10IEACurrentAYNewRegimeDate or None,
        f10iea_ack_no_curr_ay_new_tax=draft.filing.form10IEACurrentAYNewRegimeAck or None,
        f10iea_curr_ay_old_regime="Y" if draft.filing.form10IEACurrentAYOldRegime else "N",
        f10iea_date_curr_ay_old_tax=draft.filing.form10IEACurrentAYOldRegimeDate or None,
        f10iea_ack_no_curr_ay_old_tax=draft.filing.form10IEACurrentAYOldRegimeAck or None,
        seventh_proviso_139=draft.filing.seventhProvisoApplies,
        deposit_exceeds_one_crore=draft.filing.seventhProviso.depositExceedsOneCrore,
        current_account_deposits=draft.filing.seventhProviso.depositAmount,
        foreign_travel_flag=draft.filing.seventhProviso.foreignTravel,
        foreign_travel_expenditure=draft.filing.seventhProviso.foreignTravelAmount,
        electricity_expenditure_flag=draft.filing.seventhProviso.electricityExpenditure,
        electricity_expenditure=draft.filing.seventhProviso.electricityExpenditureAmount,
        other_clause_iv_flag=draft.filing.seventhProviso.otherClauseIV,
        seventh_proviso_clause_iv_entries=[
            (row.nature, row.amount) for row in draft.filing.seventhProviso.clauseIVDetails
        ],
        receipt_number=draft.filing.originalAcknowledgementNumber or None,
        original_return_date=draft.filing.originalFilingDate or None,
        notice_number=draft.filing.noticeNumber or None,
        notice_date=draft.filing.noticeDate or None,
        conditions_res_status=draft.filing.conditionsResStatus or None,
        jurisdiction_residence_entries=[
            (row.jurisdictionCode, row.tin) for row in draft.filing.jurisdictionResidenceEntries
        ],
        total_stay_india_prev_yr=draft.filing.totalStayIndiaPrevYr,
        total_stay_india_4_prec_yr=draft.filing.totalStayIndia4PrecYr,
        benefit_us_115h=(
            draft.filing.benefitUs115H if draft.filing.benefitUs115HAnswered else None
        ),
        portuguese_civil_code_applies=draft.filing.portugueseCivilCodeApplies,
        assessee_representative_name=(
            draft.filing.representative.name or None if draft.filing.representative else None
        ),
        assessee_representative_email=(
            draft.filing.representative.email or None if draft.filing.representative else None
        ),
        assessee_representative_mobile_country_code=(
            draft.filing.representative.mobileCountryCode or None
            if draft.filing.representative else None
        ),
        assessee_representative_mobile_no=(
            draft.filing.representative.mobile or None if draft.filing.representative else None
        ),
        is_company_director=draft.personal.isDirector,
        company_director_entries=[
            {
                "company_name": row.companyName, "company_type": row.companyType,
                "pan": row.pan or None, "shares_type": row.sharesType, "din": row.din or None,
            }
            for row in draft.personal.companyDirectorEntries
        ],
        is_partner_in_firm=draft.filing.isPartnerInFirm,
        partner_in_firm_entries=[
            {"firm_name": row.firmName, "pan": row.pan}
            for row in draft.filing.partnerInFirmEntries
        ],
        held_unlisted_equity=draft.personal.holdsUnlistedShares,
        unlisted_equity_entries=[
            {
                "company_name": row.companyName, "company_type": row.companyType,
                "pan": row.pan or None,
                "opening_shares": row.openingShares, "opening_cost": row.openingCost,
                "acquired_shares": row.acquiredShares or None,
                "date_of_acquisition": row.dateOfAcquisition or None,
                "face_value_per_share": row.faceValuePerShare or None,
                "issue_price_per_share": row.issuePricePerShare or None,
                "purchase_price_per_share": row.purchasePricePerShare or None,
                "transferred_shares": row.transferredShares or None,
                "transfer_sale_consideration": row.transferSaleConsideration or None,
                "closing_shares": row.closingShares,
                "closing_cost": row.closingCost,
            }
            for row in draft.personal.unlistedEquityEntries
        ],
        nri_pe_in_india=draft.filing.nriPEinIndia or None,
        nri_sep_in_india=draft.filing.nriSEPinIndia or None,
        sep_aggregate_payment=draft.filing.aggrPaymentTransac,
        sep_number_of_users=draft.filing.numberOfUsers,
        ifsc_unit_foreign_exchange_flag=draft.filing.foreignExchangeFlag or None,
        is_fii_fpi=draft.filing.isFiiFpi,
        sebi_registration_number=draft.filing.sebiRegistrationNumber or None,
        lei_number=draft.filing.leiNumber or None,
        lei_valid_upto_date=draft.filing.leiValidUptoDate or None,
        bank_accounts=[account.model_dump() for account in draft.bankAccounts],
        relief_89=values.get("relief_89", Decimal("0")),
    )
    breakdown = dict(breakdown)
    breakdown["business_income"] = input_data.business_income.net_profit_before_tax
    return input_data, breakdown
