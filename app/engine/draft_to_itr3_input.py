"""Canonical ReturnDraft to ITR-3 typed input mapping."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from app.engine.draft_to_itr1_input import DraftMappingError, draft_to_itr1_input, _to_date
from app.schemas.itr3 import AuditInfo, BalanceSheet, BSOfficial, BSProprietorsFund, BSReserves, BSLoanGroup, BSUnsecuredLoanGroup, BSAdvances, BSFixedAsset, BSCurrentAssets, BSInventory, BSCashBank, BSCurrentLiabilities, BSProvisions, BusinessIncome, ITR3BusinessAccounts, ITR3Input, ITR3ScheduleSEmployer, ITR3ScheduleHPProperty, ManufacturingAccount, NatureOfBusiness, ProfitAndLoss, PLOtherIncome, PLInterestExpense, TradingAccount, ITR3PartAOI, ITR3PartAQD, ScheduleESR, ScheduleGST, ScheduleICDS, ITR3ScheduleTPSA, ITR3DeductionDetails, ITR3DeductionDonation, ITR3DeductionLoan, ITR3Schedule80IA, ITR3Schedule80IB, ITR3Schedule80IC, ITR3Schedule80RA, ITR3Schedule10AA, ITR3Schedule80D, ITR3Schedule80DCategory, ITR3Schedule80DHealth, ITR3Schedule80DInsurance, ITR3Schedule80DD, ITR3Schedule80U
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
                FrmBank=_decimal_value(rupee_loan.get("FrmBank")),
                FrmOthrs=_decimal_value(rupee_loan.get("FrmOthrs")),
                TotRupeeLoan=_decimal_value(rupee_loan.get("TotRupeeLoan")),
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
    return BalanceSheet(
        proprietors_fund=source.proprietorCapital + source.reservesAndSurplus,
        secured_loans=source.securedLoans,
        unsecured_loans=source.unsecuredLoans,
        current_liabilities=source.deferredTaxLiability + source.advancesFromCustomers,
        total_liabilities=total_liabilities,
        fixed_assets=source.fixedAssets,
        current_assets=current_assets,
        total_assets=total_assets,
    )


def _audit_info(draft: ReturnDraft) -> AuditInfo:
    """Map PartA_GEN2 audit data, falling back to the legacy profile."""
    workspace = _core_schedule(draft, "PartA_GEN2")
    audit = workspace.get("AuditInfo") if workspace else None
    if isinstance(audit, Mapping) and audit:
        return AuditInfo(
            liable_sec_44ab=audit.get("LiableSec44ABflg") == "Y",
            liable_sec_44aa=audit.get("LiableSec44AAflg") == "Y",
            liable_sec_92e=audit.get("LiableSec92Eflg") == "Y",
            account_audited=audit.get("AccountAuditFlag") == "Y",
            income_declared_under_presumptive=audit.get("IncDclrdUs") == "Y",
        )
    source = draft.itr3AuditInfo
    return AuditInfo(
        liable_sec_44ab=source.liableSec44AB == "Y",
        liable_sec_44aa=source.liableSec44AA == "Y",
        liable_sec_92e=source.liableSec92E == "Y",
        account_audited=source.accountAudit == "Y",
        income_declared_under_presumptive=source.incomeDeclaredUnderPresumptive == "Y",
    )


def _decimal_map(value: Any) -> dict[str, Decimal]:
    """Convert a flat official schedule object to Decimal values."""
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _decimal_value(item) for key, item in value.items() if not isinstance(item, Mapping) and item not in (None, "")}


def _business_accounts(draft: ReturnDraft) -> ITR3BusinessAccounts | None:
    """Map official ManufacturingAccount and TradingAccount workspace objects."""
    manufacturing = _core_schedule(draft, "ManufacturingAccount")
    trading = _core_schedule(draft, "TradingAccount")
    if not manufacturing and not trading:
        return None
    opening = manufacturing.get("OpeningInventory", {}) if manufacturing else {}
    closing = manufacturing.get("ClosingStock", {}) if manufacturing else {}
    return ITR3BusinessAccounts(
        manufacturing_account=ManufacturingAccount(
            opening_inventory=_decimal_map(opening),
            closing_stock=_decimal_map(closing),
            cost_of_goods_produced=_decimal_value(manufacturing.get("CostOfGoodsPrdcd")),
        ) if manufacturing else None,
        trading_account=TradingAccount(values=_decimal_map(trading)) if trading else None,
    )


def _profit_and_loss(draft: ReturnDraft) -> ProfitAndLoss | None:
    """Map the authoritative PARTA_PL workspace totals when present."""
    workspace = _core_schedule(draft, "PARTA_PL")
    if not workspace:
        return None
    no_books = workspace.get("NoBooksOfAccPL", {})
    tax = workspace.get("TaxProvAppr", {})
    credits = workspace.get("CreditsToPL", {})
    other_income = credits.get("OthIncome", {}) if isinstance(credits, Mapping) else {}
    debits = workspace.get("DebitsToPL", {})
    interest = debits.get("InterestExpdrtDtls", {}) if isinstance(debits, Mapping) else {}
    return ProfitAndLoss(
        gross_profit=_decimal_value(workspace.get("GrossProfit")),
        expenditure=_decimal_value(workspace.get("Expenditure")),
        net_income_from_special_activity=_decimal_value(workspace.get("NetIncomeFrmSpecActivity")),
        turnover_from_special_activity=_decimal_value(workspace.get("TurnverFrmSpecActivity")),
        no_books_gross_receipt=_decimal_value(no_books.get("GrossReceipt") if isinstance(no_books, Mapping) else None),
        no_books_gross_profit=_decimal_value(no_books.get("GrossProfit") if isinstance(no_books, Mapping) else None),
        no_books_expenses=_decimal_value(no_books.get("Expenses") if isinstance(no_books, Mapping) else None),
        no_books_net_profit=_decimal_value(no_books.get("NetProfit") if isinstance(no_books, Mapping) else None),
        provision_current_tax=_decimal_value(tax.get("ProvForCurrTax") if isinstance(tax, Mapping) else None),
        provision_deferred_tax=_decimal_value(tax.get("ProvDefTax") if isinstance(tax, Mapping) else None),
        profit_after_tax=_decimal_value(tax.get("ProfitAfterTax") if isinstance(tax, Mapping) else None),
        gross_profit_from_trading=_decimal_value(credits.get("GrossProfitTrnsfFrmTrdAcc") if isinstance(credits, Mapping) else None),
        other_income=_decimal_value(other_income.get("TotOthIncome") if isinstance(other_income, Mapping) else None),
        other_income_breakdown=PLOtherIncome(
            RentInc=_decimal_value(other_income.get("RentInc")),
            Comissions=_decimal_value(other_income.get("Comissions")),
            Dividends=_decimal_value(other_income.get("Dividends")),
            InterestInc=_decimal_value(other_income.get("InterestInc")),
            ProfitOnSaleFixedAsset=_decimal_value(other_income.get("ProfitOnSaleFixedAsset")),
            ProfitOnInvChrSTT=_decimal_value(other_income.get("ProfitOnInvChrSTT")),
            ProfitOnOthInv=_decimal_value(other_income.get("ProfitOnOthInv")),
            ProfitOnCurrFluct=_decimal_value(other_income.get("ProfitOnCurrFluct")),
            ProfitOnCnvInvntryToCapAsst=_decimal_value(other_income.get("ProfitOnCnvInvntryToCapAsst")),
            ProfitOnAgriIncome=_decimal_value(other_income.get("ProfitOnAgriIncome")),
            MiscOthIncome=_decimal_value(other_income.get("MiscOthIncome")),
            TotOthIncome=_decimal_value(other_income.get("TotOthIncome")),
        ),
        total_credits=_decimal_value(credits.get("TotCreditsToPL") if isinstance(credits, Mapping) else None),
        interest_expense=PLInterestExpense(
            NonResOtherCompany=_decimal_value(interest.get("NonResOtherCompany")),
            Others=_decimal_value(interest.get("Others")),
            InterestExpdr=_decimal_value(interest.get("InterestExpdr")),
        ),
        total_expenses=_decimal_value(debits.get("OtherExpenses") if isinstance(debits, Mapping) else None),
        pbidta=_decimal_value(debits.get("PBIDTA") if isinstance(debits, Mapping) else None),
        depreciation_amortization=_decimal_value(debits.get("DepreciationAmort") if isinstance(debits, Mapping) else None),
        profit_before_tax=_decimal_value(debits.get("PBT") if isinstance(debits, Mapping) else None),
    )


def _business_income(draft: ReturnDraft) -> BusinessIncome:
    """Map canonical business rows and the persisted Schedule BP workspace."""
    if not draft.businesses:
        raise DraftMappingError(
            "ITR-3 requires business or professional income; ReturnDraft.businesses is empty."
        )
    unsupported = [b for b in draft.businesses if b.scheme not in {"44AD", "44ADA", "44AE"}]
    if unsupported:
        raise DraftMappingError("ReturnDraft contains unsupported business schemes for the ITR-3 foundation.")
    declared = sum((b.declaredIncome for b in draft.businesses), Decimal("0"))
    core = draft.itr3BusinessWorkspace.core
    bp = core.get("ITR3ScheduleBP", {}) if isinstance(core, dict) else {}
    regular = bp.get("BusinessIncOthThanSpec", {}) if isinstance(bp, dict) else {}
    return BusinessIncome(
        net_profit_before_tax=_decimal_value(
            regular.get("ProfBfrTaxPL"), declared
        ),
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
    esr_source = draft.itr3BusinessWorkspace.scheduleESR or draft.itr3BusinessWorkspace.core.get("ScheduleESR")
    tpsa_source = draft.itr3BusinessWorkspace.scheduleTPSA or draft.itr3BusinessWorkspace.core.get("ScheduleTPSA") or draft.itr3BusinessWorkspace.auxiliary.get("ScheduleTPSA")
    gst_source = draft.itr3BusinessWorkspace.scheduleGST or draft.itr3BusinessWorkspace.core.get("ScheduleGST")
    schedule_icds = ScheduleICDS.model_validate(icds_source) if isinstance(icds_source, Mapping) else None
    schedule_esr = ScheduleESR.model_validate(esr_source) if isinstance(esr_source, Mapping) else None
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
        business_income=_business_income(draft),
        depreciation_schedules=draft.itr3BusinessWorkspace.depreciationSchedules,
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
            NatureOfBusiness(code=row.get("Code", ""), description=row.get("Description") or None)
            for row in (_core_schedule(draft, "PartA_GEN2") or {}).get("NatOfBus", {}).get("NatureOfBusiness", [])
            if isinstance(row, Mapping) and str(row.get("Code", "")).isdigit()
        ] or [
            NatureOfBusiness(code=row.code, description=row.description or None)
            for row in draft.itr3NatureOfBusiness
            if row.code.isdigit()
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
