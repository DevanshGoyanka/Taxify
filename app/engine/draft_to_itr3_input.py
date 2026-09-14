"""Canonical ReturnDraft to ITR-3 typed input mapping."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from app.engine.draft_to_itr1_input import DraftMappingError, draft_to_itr1_input
from app.schemas.itr3 import AuditInfo, BalanceSheet, BusinessIncome, ITR3Input, NatureOfBusiness
from app.schemas.itr2 import ResidentialStatus as ITR3ResidentialStatus, ReturnFileSection
from app.schemas.return_draft import ReturnDraft


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
        return BalanceSheet(
            proprietors_fund=_decimal_value(prop_fund.get("TotPropFund")),
            secured_loans=_decimal_value(secr_loan.get("TotSecrLoan")),
            unsecured_loans=_decimal_value(unsecr_loan.get("TotUnSecrLoan")),
            current_liabilities=_decimal_value(liabilities.get("TotCurrLiabilitiesProvision")),
            total_liabilities=_decimal_value(fund_src.get("TotFundSrc")),
            fixed_assets=_decimal_value(fixed_asset.get("TotFixedAsset")),
            current_assets=_decimal_value(current.get("TotCurrAssetLoanAdv")),
            total_assets=_decimal_value(fund_apply.get("TotFundApply")),
        )
    total_liabilities = source.totalSources or (
        source.proprietorCapital
        + source.reservesAndSurplus
        + source.securedLoans
        + source.unsecuredLoans
        + source.advancesFromCustomers
        + source.otherLiabilities
        + source.creditors
        + source.provisions
    )
    current_assets = (
        source.inventories
        + source.tradeReceivables
        + source.cashAndBank
        + source.loansAndAdvances
        + source.otherAssets
    )
    total_assets = source.totalApplications or source.fixedAssets + source.investments + current_assets
    return BalanceSheet(
        proprietors_fund=source.proprietorCapital + source.reservesAndSurplus,
        secured_loans=source.securedLoans,
        unsecured_loans=source.unsecuredLoans,
        current_liabilities=(
            source.advancesFromCustomers
            + source.otherLiabilities
            + source.creditors
            + source.provisions
        ),
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
    input_data = ITR3Input(
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
        verification_place=draft.verification.place or None,
        verification_date=draft.verification.date or None,
        residence_no=draft.personal.flatNo or draft.personal.residenceName or None,
        locality=draft.personal.localityOrArea or None,
        city=draft.personal.city or None,
        state_code=draft.personal.stateCode or None,
        country_code=draft.personal.countryCode or None,
        pin_code=draft.personal.pinCode or None,
        mobile_no=draft.personal.mobile or None,
        email=draft.personal.email or None,
        relief_89=values.get("relief_89", Decimal("0")),
    )
    breakdown = dict(breakdown)
    breakdown["business_income"] = input_data.business_income.net_profit_before_tax
    return input_data, breakdown
