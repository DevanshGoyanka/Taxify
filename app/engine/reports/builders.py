"""Build a ``StatementOfIncomeContext`` from a computed ITR-1/2/4 pipeline result.

Design rule this whole module follows: every amount that ends up in the
income/tax summary or a schedule's *total* row is read directly off the
calculator's own result dataclass (``ITR1Result``/``ITR2Result``/
``ITR4Result``) or off raw, non-computed input facts (an employer's name,
a bank account number, a TDS certificate's deductor) — never re-derived
here. Where a schedule wants finer-grained detail than the calculator
preserves (e.g. a per-scrip capital-gains row), the row is shown for
disclosure only and the schedule's authoritative total still comes from
the calculator, exactly as documented per-section below.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.engine.common.slab_tax import slab_breakdown
from app.engine.reports.formatting import (
    format_assessment_year,
    format_date,
    previous_year_label,
)
from app.engine.reports.models import ScheduleTable, StatementOfIncomeContext, SummaryRow
from app.schemas.return_draft import ReturnDraft

_ZERO = Decimal("0")

_STATUS_LABELS = {"I": "Individual", "H": "HUF", "F": "Firm"}
_RESIDENT_LABELS = {
    "ROR": "Resident",
    "RNOR": "Resident but Not Ordinarily Resident",
    "NR": "Non-Resident",
}
_AGE_BRACKET_SUFFIX = {
    "60_to_80": " - Senior Citizen",
    "above_80": " - Super Senior Citizen",
}


class _ScheduleBook:
    """Accumulates numbered schedules so summary rows can cite them."""

    def __init__(self) -> None:
        self.schedules: list[ScheduleTable] = []

    def add(
        self,
        title: str,
        columns: list[str],
        rows: list[list[str]],
        total_row: Optional[list[str]] = None,
        subtitle: str = "",
        note: str = "",
    ) -> str:
        number = len(self.schedules) + 1
        self.schedules.append(ScheduleTable(
            number=number, title=title, columns=columns, rows=rows,
            total_row=total_row, subtitle=subtitle, note=note,
        ))
        return str(number)


def _employer_gross(e: Any) -> Decimal:
    """Total salary "received" for one employer row.

    Mirrors ``app/engine/draft_to_itr1_input.py::_map_salary``'s per-row
    sum exactly (section 17(1) components + perquisites/profits-in-lieu +
    retirement receipts) so this schedule's per-employer figures foot to
    the calculator's own aggregate ``salary_gross``.
    """
    return (
        e.basic + e.da + e.bonus + e.commission + e.hra + e.lta + e.allowances
        + e.otherAllowance + e.arrearSalary + e.uniformAllowance
        + e.perquisites + e.profitsInLieu
        + e.gratuity + e.commutedPension + e.leaveEncashment
        + e.vrsCompensation + e.retrenchmentCompensation
    )


def _address_lines(personal: Any) -> list[str]:
    lines = [p for p in (personal.flatNo, personal.residenceName, personal.roadOrStreet, personal.localityOrArea) if p]
    tail_parts = [p for p in (personal.city,) if p]
    tail = ", ".join(tail_parts)
    if personal.pinCode:
        tail = f"{tail} - {personal.pinCode}" if tail else personal.pinCode
    if tail:
        lines.append(tail)
    return lines or ["-"]


def _status_label(personal: Any) -> str:
    return _STATUS_LABELS.get(personal.assesseeStatus, str(personal.assesseeStatus))


def _resident_status_label(personal: Any, age_bracket: Any) -> str:
    base = _RESIDENT_LABELS.get(personal.residentialStatus, str(personal.residentialStatus))
    if personal.residentialStatus == "ROR":
        base += _AGE_BRACKET_SUFFIX.get(getattr(age_bracket, "value", age_bracket), "")
    return base


def _header_context(draft: ReturnDraft, client: Any, regime_label: str) -> dict[str, Any]:
    personal = draft.personal
    return dict(
        assessment_year=format_assessment_year(draft.assessmentYear),
        previous_year=previous_year_label(draft.assessmentYear),
        form=draft.form or "ITR-1",
        regime_label=regime_label,
        name=personal.name or client.name or "",
        father_name=personal.fatherName or "",
        address_lines=_address_lines(personal),
        pan=personal.pan or client.pan or "",
        aadhaar=personal.aadhaar or "",
        date_of_birth=format_date(personal.dateOfBirth),
        status_label=_status_label(personal),
        place=draft.verification.place or personal.city or "",
        date_str=format_date(draft.verification.date),
        signatory_name=personal.name or client.name or "",
    )


def _tds_schedules(draft: ReturnDraft, book: _ScheduleBook) -> tuple[Optional[str], Optional[str]]:
    """Build the "TDS from Salaries" and "TDS as per Form 16A" schedules.

    Salary TDS is read from each ``Employer.tdsDeducted`` — a distinct
    field from ``draft.taxes.tds``, which only ever carries non-salary
    (Form 16A style) certificates (its ``headOfIncome`` enum has no
    salary value). Returns the two schedule numbers (``None`` when a
    table had nothing to show).
    """
    salary_rows: list[list[str]] = []
    salary_total_tds = _ZERO
    salary_total_gross = _ZERO
    for e in draft.employers:
        if e.tdsDeducted <= 0:
            continue
        gross = _employer_gross(e)
        salary_rows.append([
            f"{e.employerName or 'Employer'}, TAN- {e.employerTAN or '-'}",
            _fmt(e.tdsDeducted), _fmt(e.tdsDeducted), _fmt(gross),
        ])
        salary_total_tds += e.tdsDeducted
        salary_total_gross += gross

    salary_no = None
    if salary_rows:
        salary_no = book.add(
            "TDS from Salaries",
            ["Employer & TAN", "TDS Deducted", "TDS Claimed", "Gross Salary"],
            salary_rows,
            total_row=["Total", _fmt(salary_total_tds), _fmt(salary_total_tds), _fmt(salary_total_gross)],
        )

    other_rows: list[list[str]] = []
    total_tds = total_gross = _ZERO
    for t in draft.taxes.tds:
        claimed = t.tdsClaimed if t.tdsClaimed else t.taxDeducted
        other_rows.append([
            f"{t.deductorName or 'Deductor'}, TAN- {t.deductorTAN or '-'}, Section- {t.section or '-'}",
            _fmt(t.taxDeducted), _fmt(claimed), _fmt(t.grossAmount),
        ])
        total_tds += t.taxDeducted
        total_gross += t.grossAmount

    other_no = None
    if other_rows:
        other_no = book.add(
            "TDS as per Form 16A",
            ["Deductor, TAN & Section", "TDS Deducted", "TDS Claimed", "Gross Receipt Offered"],
            other_rows,
            total_row=["Total", _fmt(total_tds), _fmt(total_tds), _fmt(total_gross)],
        )
    return salary_no, other_no


def _tcs_schedule(draft: ReturnDraft, book: _ScheduleBook) -> Optional[str]:
    if not draft.taxes.tcs:
        return None
    rows = []
    total_collected = total_gross = _ZERO
    for t in draft.taxes.tcs:
        rows.append([
            f"{t.collectorName or 'Collector'}, TAN- {t.collectorTAN or '-'}",
            _fmt(t.taxCollected), _fmt(t.grossAmount),
        ])
        total_collected += t.taxCollected
        total_gross += t.grossAmount
    return book.add(
        "Tax Collected at Source (TCS)",
        ["Collector & TAN", "TCS Collected", "Gross Amount"],
        rows,
        total_row=["Total", _fmt(total_collected), _fmt(total_gross)],
    )


def _challans_schedule(draft: ReturnDraft, book: _ScheduleBook) -> tuple[Optional[str], Decimal, Decimal]:
    advance = [c for c in draft.taxes.challans if c.kind == "ADVANCE_TAX"]
    self_assessment = [c for c in draft.taxes.challans if c.kind == "SELF_ASSESSMENT"]
    advance_total = sum((c.amount for c in advance), _ZERO)
    self_total = sum((c.amount for c in self_assessment), _ZERO)
    if not advance and not self_assessment:
        return None, advance_total, self_total
    rows = []
    for c in advance:
        rows.append(["Advance Tax", c.bsrCode or "-", format_date(c.depositDate), c.challanSerialNo or "-", _fmt(c.amount)])
    for c in self_assessment:
        rows.append(["Self-Assessment Tax", c.bsrCode or "-", format_date(c.depositDate), c.challanSerialNo or "-", _fmt(c.amount)])
    no = book.add(
        "Advance Tax / Self-Assessment Tax Challans",
        ["Kind", "BSR Code", "Date of Deposit", "Challan Serial No.", "Amount"],
        rows,
        total_row=["Total", "", "", "", _fmt(advance_total + self_total)],
    )
    return no, advance_total, self_total


def _bank_accounts_schedule(draft: ReturnDraft, book: _ScheduleBook) -> Optional[str]:
    if not draft.bankAccounts:
        return None
    rows = [
        [f"{b.bankName or '-'} - {b.accountNumber or '-'}", b.ifscCode or "-", b.accountType, "Yes" if b.useForRefund else "No"]
        for b in draft.bankAccounts
    ]
    return book.add(
        "Bank Accounts",
        ["Bank Name and Account No.", "IFSC Code", "Type of Account", "For Refund?"],
        rows,
    )


def _agricultural_schedule(draft: ReturnDraft, book: _ScheduleBook, net_agri: Decimal) -> Optional[str]:
    gross = draft.exemptIncome.grossAgriculturalReceipts
    expenses = draft.exemptIncome.agriculturalExpenses
    if gross <= 0 and net_agri <= 0:
        return None
    return book.add(
        "Agricultural Income",
        ["Particulars", "Amount"],
        [["Gross Receipts", _fmt(gross)], ["Less: Expenditure", _fmt(expenses)]],
        total_row=["Net Income", _fmt(net_agri)],
    )


def _house_property_schedules(draft: ReturnDraft, book: _ScheduleBook, hp_results: list) -> list[str]:
    numbers: list[str] = []
    for idx, prop in enumerate(draft.houseProperties):
        hp = hp_results[idx] if idx < len(hp_results) else None
        if hp is None:
            continue
        rows = [
            ["Property Type", prop.propertyType.replace("_", " ").title()],
            ["Gross Annual Value", _fmt(hp.gross_annual_value)],
            ["Municipal Taxes Paid", _fmt(hp.municipal_taxes)],
            ["Net Annual Value", _fmt(hp.net_annual_value)],
            ["Standard Deduction u/s 24(a) (30%)", _fmt(hp.standard_deduction_30pct)],
            ["Interest on Borrowed Capital u/s 24(b)", _fmt(hp.interest_on_loan)],
        ]
        title = f"House Property — {prop.address}" if prop.address else f"House Property {idx + 1}"
        numbers.append(book.add(
            title, ["Particulars", "Amount"], rows,
            total_row=["Income Chargeable", _fmt(hp.income_chargeable)],
        ))
    return numbers


def _other_sources_schedules(book: _ScheduleBook, os_result: Any) -> tuple[Optional[str], Optional[str]]:
    interest_rows = []
    if os_result.fixed_deposit_interest:
        interest_rows.append(["Interest on Fixed/Time Deposits", _fmt(os_result.fixed_deposit_interest)])
    if os_result.savings_bank_interest:
        interest_rows.append(["Interest on Savings Bank Account", _fmt(os_result.savings_bank_interest)])
    if os_result.interest_on_it_refund:
        interest_rows.append(["Interest on Income-Tax Refund", _fmt(os_result.interest_on_it_refund)])
    other_misc = os_result.other_income + os_result.income_56_2_x + os_result.income_56_2_vib
    if other_misc:
        interest_rows.append(["Other Interest / Income", _fmt(other_misc)])
    if os_result.family_pension_gross:
        interest_rows.append(["Family Pension (Gross)", _fmt(os_result.family_pension_gross)])
    interest_total = (
        os_result.fixed_deposit_interest + os_result.savings_bank_interest
        + os_result.interest_on_it_refund + other_misc + os_result.family_pension_gross
    )
    interest_no = None
    if interest_rows:
        interest_no = book.add(
            "Interest / Other Income", ["Particulars", "Amount"], interest_rows,
            total_row=["Taxable Interest / Other Income", _fmt(interest_total)],
        )

    dividend_no = None
    if os_result.dividend_income:
        dividend_no = book.add(
            "Dividends", ["Particulars", "Amount"],
            [["Dividends from Domestic Company (other than u/s 2(22)(e)/(f))", _fmt(os_result.dividend_income)]],
            total_row=["Total Dividends", _fmt(os_result.dividend_income)],
        )
    return interest_no, dividend_no


def _slab_breakdown_schedule(
    book: _ScheduleBook, normal_rate_income: Decimal, age_bracket: Any, regime: Any, slab_tax_total: Decimal,
) -> Optional[str]:
    breakdown = slab_breakdown(normal_rate_income, age_bracket, regime)
    if not breakdown:
        return None
    rows = []
    for lower, upper, rate, bracket_income, bracket_tax in breakdown:
        label = "Nil rate" if rate == 0 else f"@ {rate}%"
        rows.append([label, _fmt(bracket_income), _fmt(bracket_tax)])
    return book.add(
        "Slab-Rate Tax Computation", ["Slab", "Income in Slab", "Tax"], rows,
        total_row=["Total", _fmt(normal_rate_income), _fmt(slab_tax_total)],
    )


def _fmt(amount: Any) -> str:
    from app.engine.reports.formatting import format_inr
    return format_inr(amount)


def _income_tax_schedule_itr1_itr4(
    book: _ScheduleBook, result: Any, normal_rate_income: Decimal,
) -> str:
    rows = [["Income taxable at normal (slab) rates", _fmt(normal_rate_income), _fmt(result.slab_tax)]]
    if result.capital_gains_112a:
        rows.append(["Long-term capital gain u/s 112A", _fmt(result.capital_gains_112a), _fmt(result.special_rate_tax)])
    return book.add(
        "Tax on Total Income", ["Particulars", "Income", "Tax"], rows,
        total_row=["Tax on Total Income", "", _fmt(result.tax_before_rebate)],
    )


def _income_tax_schedule_itr2(book: _ScheduleBook, result: Any, si_result: Any, normal_rate_income: Decimal) -> str:
    rows = [["Income taxable at normal (slab) rates", _fmt(normal_rate_income), _fmt(result.slab_tax)]]
    for entry in si_result.entries:
        if entry.taxable_income or entry.tax_amount:
            rows.append([entry.description or entry.section, _fmt(entry.taxable_income), _fmt(entry.tax_amount)])
    note = "Amount before rebate; excludes any AMT adjustment (see AMT schedule if applicable)."
    return book.add(
        "Tax on Total Income", ["Particulars", "Income", "Tax"], rows,
        total_row=["Tax on Total Income", "", _fmt(result.tax_before_rebate)],
        note=note,
    )


def _tax_computation_rows(result: Any, total_taxes_paid_label_amount: Decimal) -> list[SummaryRow]:
    rows: list[SummaryRow] = []
    if result.rebate_87a:
        rows.append(SummaryRow("plain", "Rebate u/s 87A", amount=result.rebate_87a))
        rows.append(SummaryRow("plain", "Tax after Rebate", amount=result.tax_after_rebate, italic=True))
    if result.surcharge:
        rows.append(SummaryRow("plain", "Add: Surcharge", amount=result.surcharge))
    rows.append(SummaryRow("plain", "Add: Health & Education Cess", amount=result.health_education_cess))
    rows.append(SummaryRow("plain", "Tax with Cess", amount=result.gross_tax_liability, italic=True))
    if result.relief_89:
        rows.append(SummaryRow("plain", "Less: Relief u/s 89", amount=result.relief_89))
    if getattr(result, "relief_90_91", None):
        rows.append(SummaryRow("plain", "Less: Relief u/s 90/90A/91", amount=result.relief_90_91))
    if result.total_interest:
        if result.interest_234a:
            rows.append(SummaryRow("plain", "Add: Interest u/s 234A", amount=result.interest_234a))
        if result.interest_234b:
            rows.append(SummaryRow("plain", "Add: Interest u/s 234B", amount=result.interest_234b))
        if result.interest_234c:
            rows.append(SummaryRow("plain", "Add: Interest u/s 234C", amount=result.interest_234c))
    if result.late_fee_234f:
        rows.append(SummaryRow("plain", "Add: Late Fee u/s 234F", amount=result.late_fee_234f))
    if result.relief_89 or result.total_interest or result.late_fee_234f or getattr(result, "relief_90_91", None):
        rows.append(SummaryRow("plain", "Net Tax Liability", amount=result.net_tax_liability, bold=True))
    if total_taxes_paid_label_amount:
        rows.append(SummaryRow("plain", "TDS / TCS", amount=total_taxes_paid_label_amount))
    return rows


def build_itr1_context(draft: ReturnDraft, client: Any, pipeline_result: Any) -> StatementOfIncomeContext:
    result = pipeline_result.computation
    typed_input = pipeline_result.typed_input
    regime_label = "New Tax Regime (Section 115BAC)" if draft.regime == "new" else "Old (Existing) Tax Regime"
    header = _header_context(draft, client, regime_label)
    header["resident_status_label"] = _resident_status_label(draft.personal, typed_input.age_bracket)

    book = _ScheduleBook()
    rows: list[SummaryRow] = []

    # ── Salary ──────────────────────────────────────────────────────────
    if result.salary_income or draft.employers:
        rows.append(SummaryRow("head", "Income from Salaries"))
        for idx, e in enumerate(draft.employers, start=1):
            sch_no = book.add(
                "Employer Details",
                ["Field", "Value"],
                [
                    ["Name", e.employerName or "-"],
                    ["TAN", e.employerTAN or "-"],
                    ["Address", ", ".join(p for p in (e.employerAddress, e.employerCity, e.employerStateCode, e.employerPinCode) if p) or "-"],
                    ["Nature of Employment", e.natureOfEmployment or "-"],
                ],
            )
            rows.append(SummaryRow("item", f"Employer-{idx}: {e.employerName or 'Employer'}", sch_no=sch_no, amount=_employer_gross(e)))
        rows.append(SummaryRow("item", "Total Salary", amount=result.salary_gross, italic=True))
        std_ded = result.salary_deduction_us16
        if std_ded:
            rows.append(SummaryRow("item", "Standard Deduction u/s 16", amount=std_ded, italic=True))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "Salaries"', amount=result.salary_income))

    # ── House Property ──────────────────────────────────────────────────
    if draft.houseProperties:
        hp_numbers = _house_property_schedules(draft, book, result.hp_results)
        rows.append(SummaryRow("head", "Income from House Property"))
        for idx, sch_no in enumerate(hp_numbers, start=1):
            rows.append(SummaryRow("item", f"House Property {idx}", sch_no=sch_no))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "House Property"', amount=result.house_property_income))

    # ── Capital Gains (simplified 112A) ─────────────────────────────────
    simplified = draft.capitalGainsSchedule.simplified112A
    if result.capital_gains_112a or simplified.totalSaleConsideration:
        cg_no = book.add(
            "Capital Gains — Section 112A (LTCG on STT-paid Equity/Units)",
            ["Particulars", "Amount"],
            [
                ["Total Sale Consideration", _fmt(simplified.totalSaleConsideration)],
                ["Total Cost of Acquisition", _fmt(simplified.totalCostAcquisition)],
            ],
            total_row=["Long-term Capital Gain chargeable u/s 112A", _fmt(result.capital_gains_112a)],
        )
        rows.append(SummaryRow("head", "Capital Gains"))
        rows.append(SummaryRow("item", "Long-term Capital Gain u/s 112A", sch_no=cg_no, amount=result.capital_gains_112a))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "Capital Gains"', amount=result.capital_gains_112a))

    # ── Other Sources ───────────────────────────────────────────────────
    os_result = result.schedules.get("os")
    if os_result is not None and (result.other_sources_income or os_result.income_chargeable):
        interest_no, dividend_no = _other_sources_schedules(book, os_result)
        rows.append(SummaryRow("head", "Income from Other Sources"))
        if interest_no:
            rows.append(SummaryRow("item", "Interest Income", sch_no=interest_no))
        if dividend_no:
            rows.append(SummaryRow("item", "Dividends", sch_no=dividend_no))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "Other Sources"', amount=result.other_sources_income))

    # ── Gross Total Income / Deductions / Total Income ─────────────────
    rows.append(SummaryRow("grand", "Gross Total Income", amount=result.gross_total_income, bold=True))
    if result.deductions_total:
        rows.append(SummaryRow("plain", "Less: Deductions under Chapter VI-A", amount=result.deductions_total))
    total_income_pre_round = getattr(result, "total_income_before_288a", result.taxable_income)
    rows.append(SummaryRow("grand", "Total Income", amount=total_income_pre_round, bold=True))
    if result.net_agricultural_income:
        agri_no = _agricultural_schedule(draft, book, result.net_agricultural_income)
        rows.append(SummaryRow("info", "Agricultural Income (for rate purposes only)", sch_no=agri_no or "", amount=result.net_agricultural_income))
    rows.append(SummaryRow("plain", "Total Income Rounded Off u/s 288A", amount=result.taxable_income, italic=True))

    # ── Tax computation ─────────────────────────────────────────────────
    normal_rate_income = getattr(result, "normal_rate_income", None)
    if normal_rate_income is None:
        normal_rate_income = max(_ZERO, result.taxable_income - result.capital_gains_112a)
    tax_no = _income_tax_schedule_itr1_itr4(book, result, normal_rate_income)
    _slab_breakdown_schedule(book, normal_rate_income, typed_input.age_bracket, typed_input.tax_regime, result.slab_tax)
    rows.append(SummaryRow("plain", "Tax on Total Income", sch_no=tax_no, amount=result.tax_before_rebate))
    rows.extend(_tax_computation_rows(result, result.total_tds + result.total_tcs))

    challan_no, advance_tax, self_assessment_tax = _challans_schedule(draft, book)
    if advance_tax:
        rows.append(SummaryRow("plain", "Advance Tax Paid", sch_no=challan_no or "", amount=advance_tax))
    if self_assessment_tax:
        rows.append(SummaryRow("plain", "Self-Assessment Tax Paid", sch_no=challan_no or "", amount=self_assessment_tax))

    if result.refund_due:
        rows.append(SummaryRow("grand", "Refund Due", amount=result.refund_due, bold=True))
    elif result.balance_payable:
        rows.append(SummaryRow("grand", "Balance Tax Payable", amount=result.balance_payable, bold=True))
    else:
        rows.append(SummaryRow("grand", "Balance Tax Payable", amount=_ZERO, bold=True))

    _tds_schedules(draft, book)
    _tcs_schedule(draft, book)
    _bank_accounts_schedule(draft, book)

    return StatementOfIncomeContext(summary_rows=rows, schedules=book.schedules, **header)


def build_itr4_context(draft: ReturnDraft, client: Any, pipeline_result: Any) -> StatementOfIncomeContext:
    result = pipeline_result.computation
    typed_input = pipeline_result.typed_input
    regime_label = "New Tax Regime (Section 115BAC)" if draft.regime == "new" else "Old (Existing) Tax Regime"
    header = _header_context(draft, client, regime_label)
    header["resident_status_label"] = _resident_status_label(draft.personal, typed_input.age_bracket)

    book = _ScheduleBook()
    rows: list[SummaryRow] = []

    if result.salary_income or draft.employers:
        rows.append(SummaryRow("head", "Income from Salaries"))
        for idx, e in enumerate(draft.employers, start=1):
            sch_no = book.add(
                "Employer Details", ["Field", "Value"],
                [
                    ["Name", e.employerName or "-"],
                    ["TAN", e.employerTAN or "-"],
                    ["Address", ", ".join(p for p in (e.employerAddress, e.employerCity, e.employerStateCode, e.employerPinCode) if p) or "-"],
                    ["Nature of Employment", e.natureOfEmployment or "-"],
                ],
            )
            rows.append(SummaryRow("item", f"Employer-{idx}: {e.employerName or 'Employer'}", sch_no=sch_no, amount=_employer_gross(e)))
        rows.append(SummaryRow("item", "Total Salary", amount=result.salary_gross, italic=True))
        std_ded = result.salary_deduction_us16
        if std_ded:
            rows.append(SummaryRow("item", "Standard Deduction u/s 16", amount=std_ded, italic=True))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "Salaries"', amount=result.salary_income))

    if draft.houseProperties:
        # ITR4Result has no top-level `hp_results` (unlike ITR1Result) --
        # ITR-4 allows at most one house property, so its calculator stores
        # a single HPResult at schedules["hp"], not a list.
        itr4_hp = result.schedules.get("hp")
        hp_numbers = _house_property_schedules(draft, book, [itr4_hp] if itr4_hp is not None else [])
        rows.append(SummaryRow("head", "Income from House Property"))
        for idx, sch_no in enumerate(hp_numbers, start=1):
            rows.append(SummaryRow("item", f"House Property {idx}", sch_no=sch_no))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "House Property"', amount=result.house_property_income))

    if draft.businesses:
        rows.append(SummaryRow("head", "Profits and Gains of Business or Profession"))
        biz_rows = []
        for b in draft.businesses:
            if b.scheme == "44AE":
                receipts = "-"
                declared = b.declaredIncome
            elif b.scheme == "44ADA":
                receipts = _fmt(b.grossReceipts)
                declared = b.declaredIncome
            else:
                receipts = _fmt(b.digitalReceipts + b.nonDigitalReceipts + b.otherModeReceipts)
                declared = b.declaredIncome or (b.digitalPresumptiveIncome + b.nonDigitalPresumptiveIncome)
            biz_rows.append([b.businessName or "Business", b.scheme, receipts, _fmt(declared)])
            rows.append(SummaryRow(
                "item", f"Business: {b.businessName or 'Business'} (Presumptive u/s {b.scheme})",
                amount=declared,
            ))
            if b.scheme == "44AE" and b.vehicles:
                for v in b.vehicles:
                    biz_rows.append([f"  Vehicle {v.vehicleNumber or '-'} ({v.vehicleType})", "", "", _fmt(v.presumptiveIncome)])
        book.add(
            "Presumptive Business Income (44AD/44ADA/44AE)",
            ["Business", "Scheme", "Turnover / Receipts", "Declared Income"],
            biz_rows,
            total_row=["Total", "", "", _fmt(result.presumptive_income)],
        )
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "Business and Profession"', amount=result.presumptive_income))

    simplified = draft.capitalGainsSchedule.simplified112A
    if result.capital_gains_112a or simplified.totalSaleConsideration:
        cg_no = book.add(
            "Capital Gains — Section 112A (LTCG on STT-paid Equity/Units)",
            ["Particulars", "Amount"],
            [
                ["Total Sale Consideration", _fmt(simplified.totalSaleConsideration)],
                ["Total Cost of Acquisition", _fmt(simplified.totalCostAcquisition)],
            ],
            total_row=["Long-term Capital Gain chargeable u/s 112A", _fmt(result.capital_gains_112a)],
        )
        rows.append(SummaryRow("head", "Capital Gains"))
        rows.append(SummaryRow("item", "Long-term Capital Gain u/s 112A", sch_no=cg_no, amount=result.capital_gains_112a))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "Capital Gains"', amount=result.capital_gains_112a))

    os_result = result.schedules.get("os")
    if os_result is not None and (result.other_sources_income or os_result.income_chargeable):
        interest_no, dividend_no = _other_sources_schedules(book, os_result)
        rows.append(SummaryRow("head", "Income from Other Sources"))
        if interest_no:
            rows.append(SummaryRow("item", "Interest Income", sch_no=interest_no))
        if dividend_no:
            rows.append(SummaryRow("item", "Dividends", sch_no=dividend_no))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "Other Sources"', amount=result.other_sources_income))

    rows.append(SummaryRow("grand", "Gross Total Income", amount=result.gross_total_income, bold=True))
    if result.deductions_total:
        rows.append(SummaryRow("plain", "Less: Deductions under Chapter VI-A", amount=result.deductions_total))
    rows.append(SummaryRow("grand", "Total Income", amount=result.taxable_income, bold=True))
    net_agri = getattr(result, "net_agricultural_income", _ZERO)
    if net_agri:
        agri_no = _agricultural_schedule(draft, book, net_agri)
        rows.append(SummaryRow("info", "Agricultural Income (for rate purposes only)", sch_no=agri_no or "", amount=net_agri))
    rows.append(SummaryRow("plain", "Total Income Rounded Off u/s 288A", amount=result.taxable_income, italic=True))

    normal_rate_income = max(_ZERO, result.taxable_income - result.capital_gains_112a)
    tax_no = _income_tax_schedule_itr1_itr4(book, result, normal_rate_income)
    _slab_breakdown_schedule(book, normal_rate_income, typed_input.age_bracket, typed_input.tax_regime, result.slab_tax)
    rows.append(SummaryRow("plain", "Tax on Total Income", sch_no=tax_no, amount=result.tax_before_rebate))
    rows.extend(_tax_computation_rows(result, result.total_tds + result.total_tcs))

    challan_no, advance_tax, self_assessment_tax = _challans_schedule(draft, book)
    if advance_tax:
        rows.append(SummaryRow("plain", "Advance Tax Paid", sch_no=challan_no or "", amount=advance_tax))
    if self_assessment_tax:
        rows.append(SummaryRow("plain", "Self-Assessment Tax Paid", sch_no=challan_no or "", amount=self_assessment_tax))

    if result.refund_due:
        rows.append(SummaryRow("grand", "Refund Due", amount=result.refund_due, bold=True))
    else:
        rows.append(SummaryRow("grand", "Balance Tax Payable", amount=result.balance_payable, bold=True))

    _tds_schedules(draft, book)
    _tcs_schedule(draft, book)
    _bank_accounts_schedule(draft, book)

    return StatementOfIncomeContext(summary_rows=rows, schedules=book.schedules, **header)


def build_itr2_context(draft: ReturnDraft, client: Any, pipeline_result: Any) -> StatementOfIncomeContext:
    result = pipeline_result.computation
    typed_input = pipeline_result.typed_input
    regime_label = "New Tax Regime (Section 115BAC)" if draft.regime == "new" else "Old (Existing) Tax Regime"
    header = _header_context(draft, client, regime_label)
    header["resident_status_label"] = _resident_status_label(draft.personal, typed_input.age_bracket)

    book = _ScheduleBook()
    rows: list[SummaryRow] = []

    if result.salary_income or draft.employers:
        rows.append(SummaryRow("head", "Income from Salaries"))
        for idx, e in enumerate(draft.employers, start=1):
            sch_no = book.add(
                "Employer Details", ["Field", "Value"],
                [
                    ["Name", e.employerName or "-"],
                    ["TAN", e.employerTAN or "-"],
                    ["Address", ", ".join(p for p in (e.employerAddress, e.employerCity, e.employerStateCode, e.employerPinCode) if p) or "-"],
                    ["Nature of Employment", e.natureOfEmployment or "-"],
                ],
            )
            rows.append(SummaryRow("item", f"Employer-{idx}: {e.employerName or 'Employer'}", sch_no=sch_no, amount=_employer_gross(e)))
        if hasattr(result, "salary_gross"):
            rows.append(SummaryRow("item", "Total Salary", amount=result.salary_gross, italic=True))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "Salaries"', amount=result.salary_income))

    if draft.houseProperties:
        hp_results = result.schedules.get("hp", [])
        hp_numbers = _house_property_schedules(draft, book, hp_results)
        rows.append(SummaryRow("head", "Income from House Property"))
        for idx, sch_no in enumerate(hp_numbers, start=1):
            rows.append(SummaryRow("item", f"House Property {idx}", sch_no=sch_no))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "House Property"', amount=result.house_property_income))

    cg_result = result.schedules.get("cg")
    si_result = result.schedules.get("si")
    if result.capital_gains_income or (cg_result and cg_result.total_capital_gains):
        rows.append(SummaryRow("head", "Capital Gains"))
        if typed_input.cg_transactions:
            tx_rows = []
            for tx in typed_input.cg_transactions:
                asset_type = getattr(tx.asset_type, "value", tx.asset_type)
                tx_rows.append([
                    tx.description or asset_type.replace("_", " ").title(),
                    format_date(tx.date_of_acquisition) if tx.date_of_acquisition else "-",
                    format_date(tx.date_of_transfer),
                    _fmt(tx.full_consideration),
                    _fmt(tx.cost_of_acquisition),
                    _fmt(tx.expenditure_on_transfer),
                ])
            cg_no = book.add(
                "Capital Gains — Transaction Detail",
                ["Description", "Date of Acquisition", "Date of Transfer", "Sale Consideration", "Cost of Acquisition", "Transfer Expenses"],
                tx_rows,
                note="Gain/loss classification (short-term/long-term, section) and the Section 112A/54-series exemptions are applied in aggregate — see the Tax on Total Income schedule for the taxable figures.",
            )
            rows.append(SummaryRow("item", "Capital Gains — see transaction schedule", sch_no=cg_no, amount=result.capital_gains_income))
        else:
            rows.append(SummaryRow("item", "Capital Gains", amount=result.capital_gains_income))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "Capital Gains"', amount=result.capital_gains_income))

    os_result = result.schedules.get("os")
    if os_result is not None and (result.other_sources_income or os_result.income_chargeable):
        interest_no, dividend_no = _other_sources_schedules(book, os_result)
        rows.append(SummaryRow("head", "Income from Other Sources"))
        if interest_no:
            rows.append(SummaryRow("item", "Interest Income", sch_no=interest_no))
        if dividend_no:
            rows.append(SummaryRow("item", "Dividends", sch_no=dividend_no))
        rows.append(SummaryRow("headtotal", 'Income chargeable under the head "Other Sources"', amount=result.other_sources_income))

    rows.append(SummaryRow("grand", "Gross Total Income", amount=result.gross_total_income, bold=True))
    if result.deductions_total:
        rows.append(SummaryRow("plain", "Less: Deductions under Chapter VI-A", amount=result.deductions_total))
    rows.append(SummaryRow("grand", "Total Income", amount=result.taxable_income, bold=True))
    if result.net_agricultural_income:
        agri_no = _agricultural_schedule(draft, book, result.net_agricultural_income)
        rows.append(SummaryRow("info", "Agricultural Income (for rate purposes only)", sch_no=agri_no or "", amount=result.net_agricultural_income))
    rows.append(SummaryRow("plain", "Total Income Rounded Off u/s 288A", amount=result.taxable_income, italic=True))

    total_special = si_result.total_special_rate_income if si_result else _ZERO
    normal_rate_income = max(_ZERO, result.taxable_income - total_special)
    if si_result is not None:
        tax_no = _income_tax_schedule_itr2(book, result, si_result, normal_rate_income)
    else:
        tax_no = _income_tax_schedule_itr1_itr4(book, result, normal_rate_income)
    _slab_breakdown_schedule(book, normal_rate_income, typed_input.age_bracket, typed_input.tax_regime, result.slab_tax)
    rows.append(SummaryRow("plain", "Tax on Total Income", sch_no=tax_no, amount=result.tax_before_rebate))
    if getattr(result, "amt_tax", None):
        rows.append(SummaryRow("plain", "Alternate Minimum Tax u/s 115JC (if higher)", amount=result.amt_tax))
    rows.extend(_tax_computation_rows(result, result.total_tds + result.total_tcs))

    challan_no, advance_tax, self_assessment_tax = _challans_schedule(draft, book)
    if advance_tax:
        rows.append(SummaryRow("plain", "Advance Tax Paid", sch_no=challan_no or "", amount=advance_tax))
    if self_assessment_tax:
        rows.append(SummaryRow("plain", "Self-Assessment Tax Paid", sch_no=challan_no or "", amount=self_assessment_tax))

    if result.refund_due:
        rows.append(SummaryRow("grand", "Refund Due", amount=result.refund_due, bold=True))
    else:
        rows.append(SummaryRow("grand", "Balance Tax Payable", amount=result.balance_payable, bold=True))

    _tds_schedules(draft, book)
    _tcs_schedule(draft, book)
    _bank_accounts_schedule(draft, book)

    return StatementOfIncomeContext(summary_rows=rows, schedules=book.schedules, **header)


_BUILDERS = {
    "ITR-1": build_itr1_context,
    "ITR-2": build_itr2_context,
    "ITR-4": build_itr4_context,
}


def build_statement_of_income_context(draft: ReturnDraft, client: Any, pipeline_result: Any) -> StatementOfIncomeContext:
    builder = _BUILDERS.get(draft.form)
    if builder is None:
        raise ValueError(f"No Statement of Income builder for form {draft.form!r}")
    return builder(draft, client, pipeline_result)
