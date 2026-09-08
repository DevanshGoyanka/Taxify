"""ITR-2 pre-computation validation rules.

The rules in this module validate facts that must be internally consistent before
an ITR-2 computation is attempted.  They intentionally validate only fields
represented by :class:`app.schemas.itr2.ITR2Input`.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from app.engine.validators.base import Severity, ValidationResult
from app.schemas.itr1 import PropertyType, TaxRegime
from app.schemas.itr2 import AssesseeStatus, CGAssetType, ITR2Input, ResidentialStatus, ReturnFileSection

_ZERO = Decimal("0")
_AY_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
_ALLOWED_LOSS_HEADS = {
    "HP": 8,
    "STCG": 8,
    "LTCG": 8,
    "NONSPECULATIVE": 8,
    "SPECULATIVE": 4,
}


def _result(
    rule_id: str,
    passed: bool,
    message: str,
    field_path: str,
    expected: Any = None,
    actual: Any = None,
    severity: Severity = Severity.A,
) -> ValidationResult:
    """Build a validation result with the ITR-2 conventions."""
    return ValidationResult(
        rule_id=rule_id,
        severity=severity,
        passed=passed,
        message=message,
        field_path=field_path,
        expected=expected,
        actual=actual,
    )


def _current_assessment_year(inp: ITR2Input) -> int:
    """Return the first year of the assessment year applicable to the input."""
    reference = inp.due_date or inp.filing_date
    return reference.year if reference is not None else 2026


def _parse_assessment_year(value: str) -> int | None:
    """Parse and validate an assessment-year label, returning its first year."""
    match = _AY_PATTERN.fullmatch(value.strip())
    if match is None:
        return None
    first = int(match.group(1))
    second = int(match.group(2))
    return first if second == (first + 1) % 100 else None


def _financial_year_end(inp: ITR2Input) -> date:
    """Return 31 March of the financial year the return is filed for.

    AY 2026-27's financial year (2025-26) ends 31 March 2026; ``due_date``/
    ``filing_date`` fall within the AY (e.g. July 2026), so their calendar
    year — the same value ``_current_assessment_year`` derives — is the FY's
    closing year.
    """
    return date(_current_assessment_year(inp), 3, 31)


def validate_itr2_input(inp: ITR2Input) -> list[ValidationResult]:
    """Validate all supported ITR-2 input-level rules.

    Args:
        inp: Fully parsed ITR-2 input model.

    Returns:
        A list containing only actionable failures or warnings.  An empty list
        means that all represented pre-computation invariants passed.
    """
    results: list[ValidationResult] = []

    # Official rules 20/21 and 9 from the 1-100 audit window.
    if inp.filing_section == ReturnFileSection.ON_TIME_139_1 and inp.tax_regime == TaxRegime.OLD:
        if inp.filing_date is not None and inp.due_date is not None and inp.filing_date > inp.due_date:
            results.append(_result(
                "ITR2-IN-REGIME-001", False,
                "The old tax regime cannot be selected after the due date for a section 139(1) return.",
                "tax_regime", "new after due date", inp.tax_regime.value,
            ))

    if inp.filing_profile is not None:
        profile = inp.filing_profile
        if profile.is_fii_fpi and profile.residential_status in {
            ResidentialStatus.RESIDENT, ResidentialStatus.NOT_ORDINARILY_RESIDENT,
        }:
            results.append(_result(
                "ITR2-IN-PROFILE-002", False,
                "Residents and not ordinarily resident taxpayers cannot be FII/FPIs.",
                "filing_profile.is_fii_fpi", False, str(profile.is_fii_fpi),
            ))
        if profile.seventh_proviso_139 and not any((
            profile.foreign_travel_expenditure > _ZERO,
            profile.electricity_expenditure > _ZERO,
            profile.current_account_deposits > _ZERO,
        )):
            results.append(_result(
                "ITR2-IN-PROFILE-003", False,
                "Seventh-proviso filing requires at least one corresponding amount detail.",
                "filing_profile", "one seventh-proviso amount > 0", "all amounts are zero",
            ))

    # ── Schedule S (Salary) — Phase 5A ─────────────────────────────────────
    # Only checks pass-through exemption claims the engine does NOT itself cap
    # or compute from a statutory formula (gratuity/leave-encashment/VRS/
    # retrenchment/commuted-pension exemptions are all engine-computed from
    # gross-received amounts with their own statutory ceiling — see
    # app/engine/schedules/salary.py — so there is no user-suppliable "exempt
    # amount" for those that could violate a cap; re-validating them here
    # would be redundant). HRA's CBDT cap (50% of Basic+DA) is not checked:
    # SalaryIncome has no Basic/DA breakout to check it against — a known,
    # documented gap, not approximated with a fabricated proxy.
    sal = inp.salary_income
    if sal is not None:
        gross_salary_total = sal.gross_salary + sal.perquisites_value + sal.profits_in_lieu_of_salary
        if inp.tax_regime == TaxRegime.OLD:
            net_salary = max(_ZERO, gross_salary_total - sal.hra_exempt_amount - sal.lta_exempt_amount)
            allowed_standard = min(Decimal("50000"), net_salary)
            if sal.standard_deduction_claimed > allowed_standard:
                results.append(_result(
                    "ITR2-IN-SAL-009", False,
                    "Old-regime standard deduction cannot exceed ₹50,000 or net salary, whichever is lower.",
                    "salary_income.standard_deduction_claimed", str(allowed_standard),
                    str(sal.standard_deduction_claimed),
                ))
        if sal.professional_tax_paid > Decimal("2500"):
            results.append(_result(
                "ITR2-IN-SAL-010", False,
                "Professional tax deduction cannot exceed ₹2,500.",
                "salary_income.professional_tax_paid", "<= 2500", str(sal.professional_tax_paid),
            ))
        if sal.lta_exempt_amount > sal.lta_amount_received:
            results.append(_result(
                "ITR2-IN-SAL-001", False,
                "LTA claimed exempt cannot exceed LTA amount received.",
                "salary_income.lta_exempt_amount",
                f"<= {sal.lta_amount_received}", str(sal.lta_exempt_amount),
            ))
        if sal.sec10_6_embassy_exempt > gross_salary_total:
            results.append(_result(
                "ITR2-IN-SAL-002", False,
                "Sec 10(6) embassy/high-commission exempt allowance cannot exceed gross salary.",
                "salary_income.sec10_6_embassy_exempt",
                f"<= {gross_salary_total}", str(sal.sec10_6_embassy_exempt),
            ))
        if sal.sec10_7_foreign_allowance > gross_salary_total:
            results.append(_result(
                "ITR2-IN-SAL-003", False,
                "Sec 10(7) foreign-service allowance cannot exceed gross salary.",
                "salary_income.sec10_7_foreign_allowance",
                f"<= {gross_salary_total}", str(sal.sec10_7_foreign_allowance),
            ))
        if sal.sec10_10cc_perquisite_tax > sal.perquisites_value:
            results.append(_result(
                "ITR2-IN-SAL-004", False,
                "Sec 10(10CC) employer-paid tax on perquisite cannot exceed the value of perquisites.",
                "salary_income.sec10_10cc_perquisite_tax",
                f"<= {sal.perquisites_value}", str(sal.sec10_10cc_perquisite_tax),
            ))
        if not sal.is_government_employee and sal.entertainment_allowance > _ZERO:
            results.append(_result(
                "ITR2-IN-SAL-005", False,
                "Entertainment allowance deduction u/s 16(ii) is allowed only for government employees.",
                "salary_income.entertainment_allowance", _ZERO, str(sal.entertainment_allowance),
            ))
        if inp.tax_regime == TaxRegime.NEW:
            if sal.hra_exempt_amount > _ZERO or sal.lta_exempt_amount > _ZERO:
                results.append(_result(
                    "ITR2-IN-SAL-006", False,
                    "HRA and LTA exemptions cannot be claimed under the new tax regime.",
                    "salary_income", "hra_exempt_amount == 0 and lta_exempt_amount == 0",
                    f"hra={sal.hra_exempt_amount}, lta={sal.lta_exempt_amount}",
                ))
            if sal.entertainment_allowance > _ZERO:
                results.append(_result(
                    "ITR2-IN-SAL-007", False,
                    "Entertainment allowance u/s 16(ii) cannot be claimed under the new tax regime.",
                    "salary_income.entertainment_allowance", _ZERO, str(sal.entertainment_allowance),
                ))
            if sal.professional_tax_paid > _ZERO:
                results.append(_result(
                    "ITR2-IN-SAL-008", False,
                    "Professional tax u/s 16(iii) cannot be claimed under the new tax regime.",
                    "salary_income.professional_tax_paid", _ZERO, str(sal.professional_tax_paid),
                ))

    # ── Schedule HP (House Property) — Phase 5A ────────────────────────────
    hp_rows = list(inp.house_properties)
    if inp.house_property_income is not None:
        hp_rows.append(inp.house_property_income)
    self_occupied_count = 0
    for index, hp in enumerate(hp_rows):
        path = f"house_properties[{index}]"
        if hp.property_type == PropertyType.SELF_OCCUPIED:
            self_occupied_count += 1
            if inp.tax_regime == TaxRegime.NEW and hp.home_loan_interest_paid > _ZERO:
                results.append(_result(
                    "ITR2-IN-HP-009", False,
                    "Interest on borrowed capital cannot be claimed for a self-occupied property under the new tax regime.",
                    f"{path}.home_loan_interest_paid", _ZERO, str(hp.home_loan_interest_paid),
                ))
        if hp.annual_rent_received == _ZERO and hp.municipal_taxes_paid > _ZERO:
            results.append(_result(
                "ITR2-IN-HP-001", False,
                "Municipal tax is not allowed where gross rent received/receivable/"
                "lettable value is zero.",
                f"{path}.municipal_taxes_paid", _ZERO, str(hp.municipal_taxes_paid),
            ))
        if hp.property_type in (PropertyType.LET_OUT, PropertyType.DEEMED_LET_OUT) and hp.annual_rent_received <= _ZERO:
            results.append(_result(
                "ITR2-IN-HP-002", False,
                "A let-out or deemed-let-out property requires positive gross rent "
                "received/receivable/lettable value.",
                f"{path}.annual_rent_received", "> 0", str(hp.annual_rent_received),
            ))
    if self_occupied_count > 2:
        results.append(_result(
            "ITR2-IN-HP-003", False,
            "No more than two properties can be claimed as self-occupied.",
            "house_properties", "<= 2 self-occupied", str(self_occupied_count),
        ))
    for index, detail in enumerate(inp.property_filing_details):
        path = f"property_filing_details[{index}]"
        if detail.co_owned and detail.assessee_share_percent >= Decimal("100"):
            results.append(_result(
                "ITR2-IN-HP-004", False,
                "A co-owned property must have an assessee share below 100%.",
                f"{path}.assessee_share_percent", "< 100", str(detail.assessee_share_percent),
            ))
        if not detail.co_owned and detail.assessee_share_percent != Decimal("100"):
            results.append(_result(
                "ITR2-IN-HP-005", False,
                "A non-co-owned property's assessee share must equal 100%.",
                f"{path}.assessee_share_percent", "== 100", str(detail.assessee_share_percent),
            ))
        if index < len(hp_rows):
            hp = hp_rows[index]
            if detail.assessee_share_percent == _ZERO and hp.home_loan_interest_paid > _ZERO:
                results.append(_result(
                    "ITR2-IN-HP-007", False,
                    "Interest on borrowed capital cannot be claimed when the "
                    "assessee's co-owned property share is zero.",
                    f"{path}.assessee_share_percent", "> 0 when interest is claimed",
                    f"share={detail.assessee_share_percent}, interest={hp.home_loan_interest_paid}",
                ))

    # CBDT rule 757: unrealised rent cannot exceed the gross rent/lettable
    # value reported for the property. This is independently user-suppliable
    # in HousePropertyIncome and is consumed by the house-property schedule.
    for index, hp in enumerate(hp_rows):
        if hp.rent_not_realized > hp.annual_rent_received:
            results.append(_result(
                "ITR2-IN-HP-006", False,
                "Unrealised rent cannot exceed gross rent received, receivable, "
                "or lettable value.",
                f"house_properties[{index}].rent_not_realized",
                f"<= {hp.annual_rent_received}", str(hp.rent_not_realized),
            ))

    # ── Chapter VI-A Deductions — Phase 5C ─────────────────────────────────
    # Every section's compute() in app/engine/schedules/deductions/ already
    # self-caps to its statutory limit via min() and independently zeroes
    # under the new regime (verified against every section module: 80C/
    # 80CCC/80CCD1/80CCD1B/80D/80DD/80DDB/80E/80EE/80EEA/80EEB/80G/80GG/
    # 80GGA/80GGC/80TTA/80TTB/80U all gate on `regime == TaxRegime.NEW`;
    # 80CCD(2) and 80CCH do not, correctly, since both remain claimable
    # under the new regime) — so a pre-compute cap/regime validator would be
    # redundant for all of them. The one exception below (VIA-001) exists
    # because the *silent-drop* itself, not the cap, is the thing worth
    # surfacing to the taxpayer pre-compute — same rationale as SAL-006/7/8.
    # What the calculator genuinely does NOT check — no section module takes
    # an assessee-status or residential-status parameter at all — is
    # eligibility by assessee type/residency, which is where 5C's real gap
    # is and where the two rules below are aimed.
    ch6a = inp.deductions_chapter6a
    if ch6a is not None and inp.tax_regime == TaxRegime.NEW:
        _new_regime_disallowed = {
            "80C/80CCC/80CCD(1)": ch6a.amount_80c + ch6a.amount_80ccc + ch6a.amount_80ccd1,
            "80CCD(1B)": ch6a.amount_80ccd1b,
            "80D": ch6a.amount_80d_self_family + ch6a.amount_80d_parents,
            "80DD": ch6a.amount_80dd,
            "80DDB": ch6a.amount_80ddb,
            "80E": ch6a.amount_80e,
            "80EE": ch6a.amount_80ee,
            "80EEA": ch6a.amount_80eea,
            "80EEB": ch6a.amount_80eeb,
            "80G": ch6a.amount_80g,
            "80GG": ch6a.amount_80gg,
            "80GGA": ch6a.amount_80gga,
            "80GGC": ch6a.amount_80ggc,
            "80TTA": ch6a.amount_80tta,
            "80TTB": ch6a.amount_80ttb,
            "80U": ch6a.amount_80u,
        }
        claimed = {section: amount for section, amount in _new_regime_disallowed.items() if amount > _ZERO}
        if claimed:
            results.append(_result(
                "ITR2-IN-VIA-001", False,
                "These Chapter VI-A deductions cannot be claimed under the new tax regime: "
                + ", ".join(sorted(claimed)) + ".",
                "deductions_chapter6a", "all listed sections == 0",
                ", ".join(f"{k}={v}" for k, v in sorted(claimed.items())),
            ))
    if ch6a is not None and inp.filing_profile is not None and inp.filing_profile.assessee_status == AssesseeStatus.HUF:
        _huf_disallowed = {
            "80CCD(1)": ch6a.amount_80ccd1,
            "80CCD(1B)": ch6a.amount_80ccd1b,
            "80CCD(2)": ch6a.amount_80ccd2,
            "80E": ch6a.amount_80e,
            "80EE": ch6a.amount_80ee,
            "80EEA": ch6a.amount_80eea,
            "80EEB": ch6a.amount_80eeb,
            "80U": ch6a.amount_80u,
        }
        claimed_huf = {section: amount for section, amount in _huf_disallowed.items() if amount > _ZERO}
        if claimed_huf:
            results.append(_result(
                "ITR2-IN-VIA-002", False,
                "These Chapter VI-A deductions are not available to a HUF assessee: "
                + ", ".join(sorted(claimed_huf)) + ".",
                "deductions_chapter6a", "all listed sections == 0",
                ", ".join(f"{k}={v}" for k, v in sorted(claimed_huf.items())),
            ))
    if ch6a is not None and inp.tax_regime == TaxRegime.OLD and ch6a.amount_80ee > _ZERO and ch6a.amount_80eea > _ZERO:
        results.append(_result(
            "ITR2-IN-VIA-004", False,
            "Deductions under sections 80EE and 80EEA cannot both be claimed "
            "under the old tax regime.",
            "deductions_chapter6a", "80EE == 0 or 80EEA == 0",
            f"80EE={ch6a.amount_80ee}, 80EEA={ch6a.amount_80eea}",
        ))
    if ch6a is not None and inp.residential_status == ResidentialStatus.NON_RESIDENT:
        _nri_disallowed = {
            "80DD": ch6a.amount_80dd,
            "80DDB": ch6a.amount_80ddb,
            "80U": ch6a.amount_80u,
        }
        claimed_nri = {section: amount for section, amount in _nri_disallowed.items() if amount > _ZERO}
        if claimed_nri:
            results.append(_result(
                "ITR2-IN-VIA-003", False,
                "These Chapter VI-A deductions are not available to a non-resident: "
                + ", ".join(sorted(claimed_nri)) + ".",
                "deductions_chapter6a", "all listed sections == 0",
                ", ".join(f"{k}={v}" for k, v in sorted(claimed_nri.items())),
            ))

    # The schema has no assessee type or business-income field. Its shape itself
    # restricts this form to an individual/HUF without current PGBP income.
    if inp.filing_date is not None and inp.due_date is not None and inp.filing_date < date(2000, 1, 1):
        results.append(_result(
            "ITR2-IN-DATE-001", False, "Filing date is outside the supported filing period.",
            "filing_date", ">= 2000-01-01", str(inp.filing_date),
        ))
    if inp.due_date is not None and inp.filing_date is not None:
        # Filing after due date is legal; it drives interest and fee, so no error.
        if inp.due_date.year > inp.filing_date.year + 1:
            results.append(_result(
                "ITR2-IN-DATE-002", False,
                "Due date cannot be more than one year after the filing date.",
                "due_date", f"<= {inp.filing_date.year + 1}-12-31", str(inp.due_date),
            ))

    for index, tx in enumerate(inp.cg_transactions or []):
        path = f"cg_transactions[{index}]"
        if tx.date_of_acquisition is None or tx.date_of_transfer is None:
            results.append(_result(
                "ITR2-IN-CG-001", False,
                "Capital-gain transactions require acquisition and transfer dates.",
                path, "both dates present", None,
            ))
        elif tx.date_of_transfer <= tx.date_of_acquisition:
            results.append(_result(
                "ITR2-IN-CG-002", False,
                "Transfer date must be later than acquisition date.",
                f"{path}.date_of_transfer", f"> {tx.date_of_acquisition}", str(tx.date_of_transfer),
            ))
        if tx.full_consideration <= _ZERO:
            results.append(_result(
                "ITR2-IN-CG-003", False,
                "A reported transfer must have positive full consideration.",
                f"{path}.full_consideration", "> 0", str(tx.full_consideration),
            ))
        if tx.full_consideration <= _ZERO and tx.expenditure_on_transfer > _ZERO:
            results.append(_result(
                "ITR2-IN-CG-101", False,
                "Transfer expenses cannot be claimed when full consideration is zero.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-102", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-103", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-104", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-105", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-106", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-107", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
            results.append(_result(
                "ITR2-IN-CG-108", False,
                "Transfer expenses cannot be claimed against a zero-consideration capital-gain row.",
                f"{path}.expenditure_on_transfer", _ZERO, str(tx.expenditure_on_transfer),
            ))
        total_exemptions = (
            tx.deduction_us54 + tx.deduction_us54b + tx.deduction_us54ec + tx.deduction_us54f
        )
        gross_gain = max(
            _ZERO,
            tx.full_consideration
            - max(tx.cost_of_acquisition, tx.indexed_cost)
            - tx.expenditure_on_transfer,
        )
        if total_exemptions > gross_gain:
            results.append(_result(
                "ITR2-IN-CG-004", False,
                "Capital-gain exemptions cannot exceed the gain before exemption.",
                path, f"<= {gross_gain}", str(total_exemptions),
            ))
        if tx.asset_type in {CGAssetType.LISTED_EQUITY_111A, CGAssetType.LISTED_EQUITY_112A}:
            stt_paid = bool(tx.is_stt_paid_on_transfer) and (
                tx.asset_type == CGAssetType.LISTED_EQUITY_111A or bool(tx.is_stt_paid_on_acquisition)
            )
            if not stt_paid:
                results.append(_result(
                    "ITR2-IN-CG-005", False,
                    "Sections 111A/112A require applicable securities transaction tax to have been paid.",
                    f"{path}.is_stt_paid_on_transfer", True, stt_paid,
                ))
        if (
            tx.asset_type == CGAssetType.LISTED_EQUITY_112A
            and tx.date_of_acquisition is not None
            and tx.date_of_acquisition <= date(2018, 1, 31)
            and tx.fair_market_value_jan2018 is None
        ):
            results.append(_result(
                "ITR2-IN-CG-006", False,
                "Pre-1 February 2018 section 112A assets require 31 January 2018 FMV.",
                f"{path}.fair_market_value_jan2018", "non-null", None,
            ))
        if tx.asset_type == CGAssetType.LAND_BUILDING and tx.date_of_transfer > _financial_year_end(inp):
            results.append(_result(
                "ITR2-IN-CG-007", False,
                "Date of sale/transfer of land or building cannot be after 31 March "
                "of the financial year.",
                f"{path}.date_of_transfer", f"<= {_financial_year_end(inp)}", str(tx.date_of_transfer),
            ))
        if tx.deduction_us54ec > Decimal("5000000"):
            results.append(_result(
                "ITR2-IN-CG-008", False,
                "Deduction u/s 54EC (investment in specified bonds) is capped at ₹50,00,000.",
                f"{path}.deduction_us54ec", "<= 5000000", str(tx.deduction_us54ec),
            ))

    for index, scrip in enumerate(inp.cg_112a_scrips or []):
        path = f"cg_112a_scrips[{index}]"
        if not scrip.isin_code and not (scrip.share_unit_name or "").strip():
            results.append(_result(
                "ITR2-IN-112A-001", False,
                "Schedule 112A requires either an ISIN or a share/unit name.",
                path, "ISIN or name", None,
            ))
        if scrip.num_shares_units is None or scrip.num_shares_units <= _ZERO:
            results.append(_result(
                "ITR2-IN-112A-002", False,
                "Schedule 112A requires a positive number of shares/units.",
                f"{path}.num_shares_units", "> 0", str(scrip.num_shares_units),
            ))
        if scrip.sale_price_per_share is None or scrip.sale_price_per_share <= _ZERO:
            results.append(_result(
                "ITR2-IN-112A-003", False,
                "Schedule 112A requires a positive sale price per share/unit.",
                f"{path}.sale_price_per_share", "> 0", str(scrip.sale_price_per_share),
            ))
        if scrip.num_shares_units is not None and scrip.sale_price_per_share is not None:
            expected_sale = scrip.num_shares_units * scrip.sale_price_per_share
            if abs(scrip.total_sale_value - expected_sale) > Decimal("1"):
                results.append(_result(
                    "ITR2-IN-112A-004", False,
                    "Total sale value does not reconcile with quantity and unit sale price.",
                    f"{path}.total_sale_value", str(expected_sale), str(scrip.total_sale_value),
                ))
        if scrip.is_before_31jan2018 and (scrip.fmv_per_share is None or scrip.fmv_per_share <= _ZERO):
            results.append(_result(
                "ITR2-IN-112A-005", False,
                "Grandfathered section 112A holdings require a positive FMV per share.",
                f"{path}.fmv_per_share", "> 0", str(scrip.fmv_per_share),
            ))
        supplied_deductions = scrip.total_deductions
        expected_deductions = scrip.cost_acq_without_index + scrip.expenditure_on_transfer
        if supplied_deductions > _ZERO and abs(supplied_deductions - expected_deductions) > Decimal("1"):
            results.append(_result(
                "ITR2-IN-112A-006", False,
                "Schedule 112A total deductions must equal cost plus transfer expenditure.",
                f"{path}.total_deductions", str(expected_deductions), str(supplied_deductions),
            ))
        supplied_balance = scrip.balance
        expected_balance = scrip.total_sale_value - expected_deductions
        if supplied_balance is not None and abs(supplied_balance - expected_balance) > Decimal("1"):
            results.append(_result(
                "ITR2-IN-112A-007", False,
                "Schedule 112A balance must equal sale value less total deductions.",
                f"{path}.balance", str(expected_balance), str(supplied_balance),
            ))
        if not scrip.is_before_31jan2018 and scrip.fmv_per_share > _ZERO:
            results.append(_result(
                "ITR2-IN-112A-008", False,
                "Fair market value as on 31 January 2018 cannot be entered for shares "
                "acquired on or after 1 February 2018 (grandfathering does not apply).",
                f"{path}.fmv_per_share", _ZERO, str(scrip.fmv_per_share),
            ))

    for index, tx in enumerate(inp.vda_transactions or []):
        path = f"vda_transactions[{index}]"
        if tx.date_of_transfer <= tx.date_of_acquisition:
            results.append(_result(
                "ITR2-IN-VDA-001", False, "VDA transfer date must follow acquisition date.",
                f"{path}.date_of_transfer", f"> {tx.date_of_acquisition}", str(tx.date_of_transfer),
            ))
        if tx.date_of_acquisition > _financial_year_end(inp) or tx.date_of_transfer > _financial_year_end(inp):
            results.append(_result(
                "ITR2-IN-VDA-004", False,
                "VDA date of acquisition or date of transfer cannot be after 31 March "
                "of the financial year.",
                path, f"<= {_financial_year_end(inp)}",
                f"acquisition={tx.date_of_acquisition}, transfer={tx.date_of_transfer}",
            ))
        if tx.consideration_received <= _ZERO:
            results.append(_result(
                "ITR2-IN-VDA-002", False, "A reported VDA transfer requires positive consideration.",
                f"{path}.consideration_received", "> 0", str(tx.consideration_received),
            ))
        expected_income = max(_ZERO, tx.consideration_received - tx.acquisition_cost)
        if tx.income_from_vda is not None and tx.income_from_vda != expected_income:
            results.append(_result(
                "ITR2-IN-VDA-003", False,
                "VDA income must equal consideration less acquisition cost; VDA loss is not allowable.",
                f"{path}.income_from_vda", str(expected_income), str(tx.income_from_vda),
            ))

    current_ay = _current_assessment_year(inp)
    for index, loss in enumerate(inp.bf_losses or []):
        path = f"bf_losses[{index}]"
        head = loss.head.value if hasattr(loss.head, "value") else str(loss.head)
        head = head.strip().upper().replace("_", "")
        if head not in _ALLOWED_LOSS_HEADS:
            results.append(_result(
                "ITR2-IN-BFL-001", False,
                "Unsupported brought-forward loss category for ITR-2.",
                f"{path}.head", sorted(_ALLOWED_LOSS_HEADS), loss.head,
            ))
            continue
        loss_ay = _parse_assessment_year(loss.assessment_year)
        if loss_ay is None or loss_ay >= current_ay:
            results.append(_result(
                "ITR2-IN-BFL-002", False,
                "Loss assessment year must be a valid year preceding the current assessment year.",
                f"{path}.assessment_year", f"before {current_ay}-{str(current_ay + 1)[-2:]}", loss.assessment_year,
            ))
        elif current_ay - loss_ay > _ALLOWED_LOSS_HEADS[head]:
            results.append(_result(
                "ITR2-IN-BFL-003", False,
                "Brought-forward loss has expired for its statutory category.",
                f"{path}.assessment_year", f"not older than {_ALLOWED_LOSS_HEADS[head]} AYs", loss.assessment_year,
            ))
        if loss.brought_forward > loss.original_loss:
            results.append(_result(
                "ITR2-IN-BFL-004", False,
                "Brought-forward amount cannot exceed the original loss.",
                f"{path}.brought_forward", f"<= {loss.original_loss}", str(loss.brought_forward),
            ))

    fsi_by_country: dict[str, tuple[Decimal, Decimal]] = {}
    fsi_by_identity: dict[tuple[str, str], tuple[Decimal, Decimal, Decimal]] = {}
    for index, fsi in enumerate(inp.fsi_entries or []):
        path = f"fsi_entries[{index}]"
        expected_total = fsi.salary_income + fsi.hp_income + fsi.cg_income + fsi.os_income
        if fsi.total_income != expected_total:
            results.append(_result(
                "ITR2-IN-FSI-001", False,
                "FSI total income must equal the sum of its income heads.",
                f"{path}.total_income", str(expected_total), str(fsi.total_income),
            ))
        identity = (fsi.country_code.upper(), fsi.tax_identification_no.strip())
        prior_income, prior_tax, prior_relief = fsi_by_identity.get(
            identity, (_ZERO, _ZERO, _ZERO)
        )
        fsi_income = fsi.total_income or _ZERO
        fsi_relief = min(fsi.tax_paid_outside_india, fsi.tax_payable_in_india)
        fsi_by_identity[identity] = (
            prior_income + fsi_income,
            prior_tax + fsi.tax_paid_outside_india,
            prior_relief + fsi_relief,
        )
        income, tax = fsi_by_country.get(fsi.country_code.upper(), (_ZERO, _ZERO))
        fsi_by_country[fsi.country_code.upper()] = (income + fsi_income, tax + fsi.tax_paid_outside_india)
    if inp.fsi_entries and inp.residential_status == ResidentialStatus.NON_RESIDENT:
        results.append(_result(
            "ITR2-IN-FSI-003", False,
            "Schedule FSI is not applicable when residential status is non-resident.",
            "fsi_entries", "empty", f"{len(inp.fsi_entries)} entries",
        ))

    tr_by_country: dict[str, tuple[Decimal, Decimal]] = {}
    tr_by_identity: dict[tuple[str, str], tuple[Decimal, Decimal, Decimal]] = {}
    for index, tr in enumerate(inp.tr1_entries or []):
        path = f"tr1_entries[{index}]"
        if tr.relief_claimed > min(tr.tax_paid_outside_india, tr.indian_tax_payable):
            results.append(_result(
                "ITR2-IN-TR1-001", False,
                "Foreign-tax relief cannot exceed foreign tax paid or Indian tax payable.",
                f"{path}.relief_claimed",
                f"<= {min(tr.tax_paid_outside_india, tr.indian_tax_payable)}", str(tr.relief_claimed),
            ))
        if inp.residential_status == ResidentialStatus.NON_RESIDENT:
            results.append(_result(
                "ITR2-IN-TR1-003", False,
                "Schedule TR is not applicable when residential status is non-resident.",
                "tr1_entries", "empty", f"{len(inp.tr1_entries)} entries",
            ))
        identity = (tr.country_code.upper(), tr.tax_identification_no.strip())
        prior_income, prior_tax, prior_relief = tr_by_identity.get(
            identity, (_ZERO, _ZERO, _ZERO)
        )
        tr_by_identity[identity] = (
            prior_income + tr.income_included_in_this_return,
            prior_tax + tr.tax_paid_outside_india,
            prior_relief + tr.relief_claimed,
        )
        income, tax = tr_by_country.get(tr.country_code.upper(), (_ZERO, _ZERO))
        tr_by_country[tr.country_code.upper()] = (
            income + tr.income_included_in_this_return,
            tax + tr.tax_paid_outside_india,
        )
    for identity in sorted(set(fsi_by_identity) | set(tr_by_identity)):
        fsi_values = fsi_by_identity.get(identity, (_ZERO, _ZERO, _ZERO))
        tr_values = tr_by_identity.get(identity, (_ZERO, _ZERO, _ZERO))
        if fsi_values[1] != tr_values[1]:
            results.append(_result(
                "ITR2-IN-TR1-004", False,
                "Schedule TR tax paid outside India must match Schedule FSI for each country and TIN.",
                "tr1_entries", str(fsi_values[1]), str(tr_values[1]),
            ))
        if fsi_values[2] != tr_values[2]:
            results.append(_result(
                "ITR2-IN-TR1-005", False,
                "Schedule TR relief must match relief available in Schedule FSI for each country and TIN.",
                "tr1_entries", str(fsi_values[2]), str(tr_values[2]),
            ))
    for country in sorted(set(fsi_by_country) | set(tr_by_country)):
        if fsi_by_country.get(country, (_ZERO, _ZERO)) != tr_by_country.get(country, (_ZERO, _ZERO)):
            results.append(_result(
                "ITR2-IN-TR1-002", False,
                f"FSI and TR1 income/tax totals do not reconcile for country {country}.",
                "tr1_entries", str(fsi_by_country.get(country, (_ZERO, _ZERO))),
                str(tr_by_country.get(country, (_ZERO, _ZERO))),
            ))

    # Schedule TR must not claim relief for a non-resident return.
    if inp.tr1_entries and inp.residential_status == ResidentialStatus.NON_RESIDENT:
        results.append(_result(
            "ITR2-IN-TR1-003", False,
            "Schedule TR is not applicable when residential status is non-resident.",
            "tr1_entries", "empty", f"{len(inp.tr1_entries)} entries",
        ))

    # ── Schedule OS / Schedule SI / CYLA-BFLA-CFL — Phase 5D ───────────────
    # Schedule OS (`OtherSourcesIncome`) has almost nothing left to validate:
    # it is a flat gross-income-bucket model shared with ITR-1, and ITR-1's
    # own Schedule OS rules (R050/R052/R145) all key off ITR1Input-only
    # fields — `other_sources_dropdowns`, `other_sources_total`,
    # `dividend_quarterly_breakdown` — none of which exist on ITR2Input, so
    # there is nothing to adapt from ITR-1 here. The 57(iia) family-pension
    # deduction cap is engine-computed in app/engine/schedules/other_sources.py
    # (`min(fp/3, cap)`, only applied `if fp > 0`) exactly like 5A's salary
    # exemptions, so it needs no separate validator either.
    # CYLA/BFLA/CFL: `ITR2Input.cf_losses` is never read by the calculator
    # (`app/engine/calculators/itr2.py` derives its own "cfl" schedule from
    # `bf_losses` and current-year losses) — a vestigial input field, so a
    # validator against it would check something with no effect on the
    # filed return. The remaining CBDT catalog rules here (234–274) are
    # column-arithmetic identities against `build_itr2_json`'s own output
    # construction, already build-time-guaranteed.
    # Schedule SI: `ScheduleSIEntry.deductions` and `.tax_rate_pct` are BOTH
    # ignored by every `compute_*` function in
    # app/engine/schedules/special_rates.py (rates are hardcoded constants;
    # only `.gross_income` is read) — but unlike the caps found elsewhere,
    # that isn't itself a reason to skip a rule: Section 58(4) makes any
    # deduction against lottery/game-winning income *legally* invalid, not
    # just uncomputed, so a nonzero claim there is worth rejecting outright
    # rather than letting it silently vanish. `ScheduleSIEntry` itself already
    # has a `reject_disallowed_deductions` model validator blocking this for
    # sections 115BB/115BBE — 115BBJ (online game winnings, same Section 58(4)
    # disallowance) is the one section it does NOT cover, so that's the only
    # one left for this rule to add.
    for index, si in enumerate(inp.si_entries or []):
        if si.section == "115BBJ" and si.deductions > _ZERO:
            results.append(_result(
                "ITR2-IN-SI-001", False,
                "No deduction or allowance is permitted against income taxable "
                "under section 115BBJ (winnings from online games) — section 58(4).",
                f"si_entries[{index}].deductions", _ZERO, str(si.deductions),
            ))

    # CBDT rules 463, 471 and 472: withholding credits require corresponding
    # income in the schedule from which the credit is claimed.
    for index, entry in enumerate(inp.tds2_entries or []):
        if entry.tds_claimed_this_year > entry.gross_amount:
            results.append(_result(
                "ITR2-IN-TDS-002", False,
                "TDS claimed under Schedule TDS2 cannot exceed the corresponding gross income disclosed.",
                f"tds2_entries[{index}].tds_claimed_this_year",
                f"<= {entry.gross_amount}", str(entry.tds_claimed_this_year),
            ))
    total_salary_tds = sum((entry.tds_deducted for entry in inp.tds1_entries), _ZERO)
    if inp.tds1_entries and inp.salary_income is None:
        results.append(_result(
            "ITR2-IN-TDS-003", False,
            "Salary TDS can be claimed only when salary income is disclosed.",
            "salary_income", "present", "absent",
        ))
    elif inp.tds1_entries and inp.salary_income is not None:
        salary_income = (
            inp.salary_income.gross_salary
            + inp.salary_income.perquisites_value
            + inp.salary_income.profits_in_lieu_of_salary
        )
        if total_salary_tds > salary_income:
            results.append(_result(
                "ITR2-IN-TDS-004", False,
                "Total tax deducted from salary cannot exceed income chargeable under Salaries.",
                "tds1_entries", f"<= {salary_income}", str(total_salary_tds),
            ))

    # CBDT rule 542: relief u/s 89 requires salary details.
    if inp.relief_89 > _ZERO and (
        inp.salary_income is None
        or inp.salary_income.gross_salary
        + inp.salary_income.perquisites_value
        + inp.salary_income.profits_in_lieu_of_salary <= _ZERO
    ):
        results.append(_result(
            "ITR2-IN-FORM-003", False,
            "Relief u/s 89 cannot be claimed when salary details are zero or blank.",
            "relief_89", _ZERO, str(inp.relief_89),
        ))

    # CBDT rules 548, 763 and 764: disability claims require their official
    # supporting schedules.  These fields are canonical and calculator-used.
    if ch6a is not None and ch6a.amount_80u > _ZERO and ch6a.schedule_80u is None:
        results.append(_result(
            "ITR2-IN-VIA-005", False,
            "A positive Section 80U deduction requires Schedule 80U disability details.",
            "deductions_chapter6a.schedule_80u", "present", "absent",
        ))
    if ch6a is not None and ch6a.amount_80dd > _ZERO and ch6a.schedule_80dd is None:
        results.append(_result(
            "ITR2-IN-VIA-006", False,
            "A positive Section 80DD deduction requires Schedule 80DD disability details.",
            "deductions_chapter6a.schedule_80dd", "present", "absent",
        ))
    if (
        ch6a is not None
        and ch6a.amount_80dd > _ZERO
        and ch6a.schedule_80dd is not None
        and inp.filing_profile is not None
        and inp.filing_profile.assessee_status == AssesseeStatus.HUF
        and ch6a.schedule_80dd.dependent_relationship is None
    ):
        results.append(_result(
            "ITR2-IN-VIA-007", False,
            "An HUF claiming Section 80DD must identify the dependent as a Member of HUF.",
            "deductions_chapter6a.schedule_80dd.dependent_relationship",
            "MEMBER_OF_HUF", "missing",
        ))

    # CBDT rules 462, 464, 465, 468 and 479: withholding schedules must
    # preserve the distinction between current-year and brought-forward credit,
    # carry the corresponding income, and respect assessee eligibility.
    for index, entry in enumerate(inp.tds2_entries or []):
        path = f"tds2_entries[{index}]"
        if entry.tds_claimed_this_year > _ZERO and entry.gross_amount <= _ZERO:
            results.append(_result(
                "ITR2-IN-TDS-005", False,
                "TDS2 gross income must be disclosed when TDS is claimed.",
                f"{path}.gross_amount", "> 0", str(entry.gross_amount),
            ))
        if entry.brought_forward_tds > _ZERO and entry.tds_deducted > _ZERO:
            results.append(_result(
                "ITR2-IN-TDS-006", False,
                "Current-year TDS and brought-forward TDS must be reported in separate TDS2 rows.",
                path, "not both current-year and brought-forward credit",
                f"brought_forward={entry.brought_forward_tds}, deducted={entry.tds_deducted}",
            ))
        expected_carry_forward = max(
            _ZERO,
            entry.tds_deducted + entry.brought_forward_tds - entry.tds_claimed_this_year,
        )
        if entry.tds_credit_carried_forward != expected_carry_forward:
            results.append(_result(
                "ITR2-IN-TDS-007", False,
                "TDS2 credit carried forward must equal deducted plus brought-forward TDS less claimed TDS.",
                f"{path}.tds_credit_carried_forward", str(expected_carry_forward),
                str(entry.tds_credit_carried_forward),
            ))
    if inp.filing_profile is not None and inp.filing_profile.assessee_status == AssesseeStatus.HUF:
        salary_tds = sum((entry.tds_deducted for entry in inp.tds1_entries), _ZERO)
        if salary_tds > _ZERO:
            results.append(_result(
                "ITR2-IN-TDS-008", False,
                "An HUF cannot claim TDS on salary.",
                "tds1_entries", _ZERO, str(salary_tds),
            ))
    for index, entry in enumerate(inp.tds3_entries or []):
        if entry.tds_claimed > _ZERO and entry.gross_receipt <= _ZERO:
            results.append(_result(
                "ITR2-IN-TDS-009", False,
                "TDS3 gross receipt must be disclosed when TDS is claimed.",
                f"tds3_entries[{index}].gross_receipt", "> 0", str(entry.gross_receipt),
            ))
    # TDS3 carry-forward arithmetic mirrors the TDS2 ledger check.
    for index, entry in enumerate(inp.tds3_entries or []):
        expected_carry = max(_ZERO, entry.tds_deducted + entry.brought_forward_tds - entry.tds_claimed)
        if entry.tds_credit_carried_forward != expected_carry:
            results.append(_result(
                "ITR2-IN-TDS-012", False,
                "TDS3 credit carried forward must equal deducted plus brought-forward TDS less claimed TDS.",
                f"tds3_entries[{index}].tds_credit_carried_forward",
                str(expected_carry), str(entry.tds_credit_carried_forward),
            ))

    # CBDT rule 480: the ESOP deferred-tax ledger has an explicit balance
    # carried-forward field, so its arithmetic can be validated independently
    # of the unavailable Part B-TTI aggregate.
    for index, esop in enumerate(inp.esop_deferrals or []):
        expected_balance = max(
            _ZERO, esop.tax_deferred_brought_forward - esop.tax_payable_current_year,
        )
        if esop.balance_tax_carried_forward != expected_balance:
            results.append(_result(
                "ITR2-IN-ESOP-001", False,
                "ESOP deferred-tax balance carried forward must equal brought-forward tax less current-year tax payable.",
                f"esop_deferrals[{index}].balance_tax_carried_forward",
                str(expected_balance), str(esop.balance_tax_carried_forward),
            ))

    # CBDT rule 754: Section 115F investment must be made within six months
    # after the transfer of the original foreign-exchange asset.
    for index, tx in enumerate(inp.cg_transactions or []):
        for claim_index, claim in enumerate(tx.exemptions):
            if claim.section == "115F" and claim.investment_date is not None:
                if claim.investment_date < claim.transfer_date or (
                    claim.investment_date - claim.transfer_date
                ).days > 183:
                    results.append(_result(
                        "ITR2-IN-CG-009", False,
                        "Section 115F investment must be made within six months after the transfer date.",
                        f"cg_transactions[{index}].exemptions[{claim_index}].investment_date",
                        "within six months after transfer", str(claim.investment_date),
                    ))

    # Canonical exemption rows must not exceed the gain they purport to shelter.
    for index, tx in enumerate(inp.cg_transactions or []):
        for claim_index, claim in enumerate(tx.exemptions):
            claimed = claim.investment_amount + claim.cgas_deposit_amount
            if claimed > claim.eligible_gain:
                results.append(_result(
                    "ITR2-IN-CG-011", False,
                    "A capital-gain exemption investment cannot exceed the eligible gain.",
                    f"cg_transactions[{index}].exemptions[{claim_index}]",
                    f"investment plus CGAS <= {claim.eligible_gain}", str(claimed),
                ))

    # CBDT rule 650: section 192 is salary withholding and cannot be selected
    # on the non-salary TDS schedules.
    for index, entry in enumerate(inp.tds2_entries or []):
        if entry.tds_section.strip().upper() == "192":
            results.append(_result(
                "ITR2-IN-TDS-010", False,
                "Section 192 TDS must be reported in Schedule TDS1, not TDS2.",
                f"tds2_entries[{index}].tds_section", "not 192", entry.tds_section,
            ))
    for index, entry in enumerate(inp.tds3_entries or []):
        if entry.tds_section.strip().upper() == "192":
            results.append(_result(
                "ITR2-IN-TDS-011", False,
                "Section 192 TDS must be reported in Schedule TDS1, not TDS3.",
                f"tds3_entries[{index}].tds_section", "not 192", entry.tds_section,
            ))

    # CBDT rule 647: Section 80DDB claims require the specified-disease
    # evidence object that is carried by the canonical deduction model.
    if ch6a is not None and ch6a.amount_80ddb > _ZERO and ch6a.details_80ddb is None:
        results.append(_result(
            "ITR2-IN-VIA-012", False,
            "A Section 80DDB claim requires specified-disease details.",
            "deductions_chapter6a.details_80ddb", "present", "absent",
        ))

    # CBDT rule 652: the identity date must precede the financial year start
    # for AY 2026-27 (1 April 2025).
    profile_date = getattr(inp.filing_profile, "date_of_birth_or_formation", None) if inp.filing_profile is not None else None
    if profile_date is not None and profile_date >= date(2025, 4, 1):
        results.append(_result(
            "ITR2-IN-PROFILE-001", False,
            "Date of birth or formation must precede 1 April of the assessment year's financial year.",
            "filing_profile.date_of_birth_or_formation", "< 2025-04-01",
            str(profile_date),
        ))

    # CBDT rule 653: Schedule HP interest claims require corresponding filing
    # detail, preventing an interest amount from being emitted without the
    # property identity/address row required by the official return.
    if any(hp.home_loan_interest_paid > _ZERO for hp in hp_rows):
        if len(inp.property_filing_details) < len(hp_rows):
            results.append(_result(
                "ITR2-IN-HP-008", False,
                "House-property interest claims require corresponding property filing details.",
                "property_filing_details", f"at least {len(hp_rows)} rows",
                str(len(inp.property_filing_details)),
            ))

    # CBDT rules 658/659: 80CCH is restricted to eligible Central Government
    # employment and the AY-specific age band.
    if ch6a is not None and ch6a.amount_80cch > _ZERO:
        central_employment = any(
            detail.nature_of_employment == "CGOV"
            for detail in inp.employer_filing_details
        )
        if not central_employment:
            results.append(_result(
                "ITR2-IN-VIA-010", False,
                "Section 80CCH requires Central Government employment details.",
                "employer_filing_details", "one nature_of_employment == CGOV", "none",
            ))
        if profile_date is not None:
            dob = profile_date
            as_of = date(2025, 4, 1)
            age = as_of.year - dob.year - ((as_of.month, as_of.day) < (dob.month, dob.day))
            if age < 17 or age > 27:
                results.append(_result(
                    "ITR2-IN-VIA-011", False,
                    "Section 80CCH is available only for age 17 through 27 on 1 April 2025.",
                    "filing_profile.date_of_birth_or_formation", "age 17..27", str(age),
                ))

    # CBDT rule 662: every CGAS claim must point to a disclosed CGAS bank
    # account, matched by account number and account type.
    for index, tx in enumerate(inp.cg_transactions or []):
        for claim_index, claim in enumerate(tx.exemptions):
            if claim.cgas_deposit_amount > _ZERO:
                matched = any(
                    account.account_number == claim.cgas_account_number
                    and account.account_type.strip().upper() == "CGAS"
                    and account.ifsc_code.strip().upper() == (claim.cgas_ifsc or "").strip().upper()
                    for account in inp.bank_accounts
                )
                if not matched:
                    results.append(_result(
                        "ITR2-IN-CG-010", False,
                        "CGAS deposit details must match a disclosed CGAS bank account.",
                        f"cg_transactions[{index}].exemptions[{claim_index}].cgas_account_number",
                        "matching CGAS bank account", claim.cgas_account_number,
                    ))

    # Category D reminders (Category B/D rules 5/6 of 26): these are the
    # non-blocking half of Phase 5E — CBDT flags the return as uploadable but
    # warns that the claim may be disallowed unless the taxpayer separately
    # files the named form. Both `relief_89` and `amount_80gg` are real,
    # calculator-consumed fields (unlike the vestigial AMTInput ones below),
    # so this is a genuine reminder, not noise on a dead field.
    if inp.relief_89 > _ZERO:
        results.append(_result(
            "ITR2-IN-FORM-001", True,
            "Relief u/s 89 is claimed — Form 10E must be filed separately to "
            "sustain this claim.",
            "relief_89", severity=Severity.D,
        ))
    if inp.deductions_chapter6a is not None and inp.deductions_chapter6a.amount_80gg > _ZERO:
        results.append(_result(
            "ITR2-IN-FORM-002", True,
            "Deduction u/s 80GG (rent paid) is claimed — Form 10BA must be "
            "filed separately to sustain this claim.",
            "deductions_chapter6a.amount_80gg", severity=Severity.D,
        ))

    # AMT-001/002 below check `amt_tax`/`adjusted_total_income`/
    # `amt_credit_*` — confirmed by grep of app/engine/calculators/itr2.py
    # that NONE of these four `AMTInput` fields are ever read by the
    # calculator (only `.deduction_10aa`/`.deduction_80ia_to_80rrb_except_80p`/
    # `.deduction_35ad_net_depreciation` are); `_map_amt_input` in
    # draft_to_itr2_input.py never sets them either, so they sit at their
    # Pydantic zero-defaults for every real draft, which is why these two
    # pre-existing rules are harmless in production (0 == 0*rate) rather
    # than a landmine — but they are also not exercising anything real.
    # Left as-is (pre-existing, not part of this phase's scope to remove);
    # the genuinely computed AMT figure is `result.amt_tax`, already
    # covered by ITR2-CALC-009 (total tax reconciliation) and the
    # nonnegative-fields sweep in ITR2-CALC-021.
    if inp.amt_input is not None:
        amt = inp.amt_input
        expected_amt = amt.adjusted_total_income * amt.amt_rate_pct / Decimal("100")
        if abs(amt.amt_tax - expected_amt) > Decimal("1"):
            results.append(_result(
                "ITR2-IN-AMT-001", False,
                "AMT tax must equal adjusted total income multiplied by the AMT rate.",
                "amt_input.amt_tax", str(expected_amt), str(amt.amt_tax),
            ))
        if amt.amt_credit_utilised > amt.amt_credit_brought_forward:
            results.append(_result(
                "ITR2-IN-AMT-002", False,
                "AMT credit utilised cannot exceed credit brought forward.",
                "amt_input.amt_credit_utilised", f"<= {amt.amt_credit_brought_forward}",
                str(amt.amt_credit_utilised),
            ))

    # CBDT rule 466/467: claimed cannot exceed deducted PLUS brought-forward —
    # not deducted alone. `draft_to_itr1_input._map_tds` maps a real,
    # user-editable draft field (`TdsCredit.broughtFwdTDSAmt`) into
    # `brought_forward_tds`, so omitting it here would reject a taxpayer
    # legitimately claiming brought-forward TDS credit alongside this year's
    # deduction — a live false-rejection risk, not just a theoretical one.
    # `TDS3Entry` carries the identical check as a schema-level
    # `@model_validator` in app/schemas/itr1.py (shared with ITR-1) — that
    # one had the exact same bug (ignored `brought_forward_tds`) and was
    # fixed there instead, since a schema-level fix is the correct location.
    # No separate rule is needed here for TDS3 as a result: a `TDS3Entry`
    # violating the ceiling cannot be constructed at all, so a validator
    # re-checking it here would be unreachable dead code.
    for index, entry in enumerate(inp.tds2_entries or []):
        ceiling = entry.tds_deducted + entry.brought_forward_tds
        if entry.tds_claimed_this_year > ceiling:
            results.append(_result(
                "ITR2-IN-TDS-001", False,
                "TDS claimed this year cannot exceed TDS deducted plus brought-forward TDS.",
                f"tds2_entries[{index}].tds_claimed_this_year",
                f"<= {ceiling}", str(entry.tds_claimed_this_year),
            ))
    for index, entry in enumerate(inp.tcs_entries or []):
        if entry.tcs_credit_claimed > entry.tcs_collected:
            results.append(_result(
                "ITR2-IN-TCS-001", False,
                "TCS credit claimed cannot exceed TCS collected.",
                f"tcs_entries[{index}].tcs_credit_claimed",
                f"<= {entry.tcs_collected}", str(entry.tcs_credit_claimed),
            ))

    # Filing-evidence count checks
    if inp.employer_filing_details and len(inp.employer_filing_details) != len(inp.tds1_entries):
        results.append(_result(
            "ITR2-IN-FE-001", False,
            "employer_filing_details count must match tds1_entries count.",
            "employer_filing_details",
            f"len == {len(inp.tds1_entries)}",
            f"len == {len(inp.employer_filing_details)}",
        ))
    property_count = int(inp.house_property_income is not None) + len(inp.house_properties)
    if inp.property_filing_details and len(inp.property_filing_details) != property_count:
        results.append(_result(
            "ITR2-IN-FE-002", False,
            "property_filing_details count must match house property count.",
            "property_filing_details",
            f"len == {property_count}",
            f"len == {len(inp.property_filing_details)}",
        ))
    if inp.tds3_filing_details and len(inp.tds3_filing_details) != len(inp.tds3_entries):
        results.append(_result(
            "ITR2-IN-FE-003", False,
            "tds3_filing_details count must match tds3_entries count.",
            "tds3_filing_details",
            f"len == {len(inp.tds3_entries)}",
            f"len == {len(inp.tds3_filing_details)}",
        ))

    return results


def run_input_validation(inp: ITR2Input) -> "ValidationReport":
    """Run ITR-2 pre-computation validation and return a standard report."""
    from app.engine.validators.base import ValidationReport

    return ValidationReport(form_type="ITR2", results=validate_itr2_input(inp))
