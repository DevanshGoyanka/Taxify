"""Generic, form-agnostic data model for the Statement of Income report.

Per-form builder functions (``app/engine/reports/builders.py``) populate
this structure from the real calculator results; the renderer
(``app/engine/reports/renderer.py``) only knows how to lay these generic
shapes out on a page. Keeping the two halves separate means the layout
code never needs to know that "ITR-1" or "ITR-4" exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class SummaryRow:
    """One row of the page-1 "Statement of Income" income/tax summary.

    ``kind`` drives how the renderer places the two money columns:
      - "head": a bold income-head title (e.g. "Income from Salaries").
      - "item": a line item under a head (e.g. one employer's gross salary),
        shown in the inner money column, with an optional schedule number.
      - "headtotal": the head's "Income chargeable under the head ..." row,
        shown in the outer (running-total) money column.
      - "grand": a full-width total (Gross Total Income, Total Income, ...).
      - "plain": a two-column label/amount row (tax computation lines).
      - "info": an informational line not included in the total (e.g.
        Agricultural Income, shown for rate purposes only).
      - "spacer": blank row for visual separation.
    """

    kind: str
    label: str = ""
    sch_no: str = ""
    amount: Optional[Decimal] = None
    bold: bool = False
    italic: bool = False


@dataclass
class ScheduleTable:
    """One numbered schedule (e.g. "Schedule 3 — Interest income")."""

    number: int
    title: str
    columns: list[str]
    rows: list[list[str]] = field(default_factory=list)
    total_row: Optional[list[str]] = None
    subtitle: str = ""
    note: str = ""


@dataclass
class StatementOfIncomeContext:
    """Everything the renderer needs to produce one Statement of Income PDF."""

    assessment_year: str
    previous_year: str
    form: str
    regime_label: str

    name: str
    father_name: str
    address_lines: list[str]
    pan: str
    aadhaar: str
    date_of_birth: str
    status_label: str
    resident_status_label: str

    summary_rows: list[SummaryRow]
    schedules: list[ScheduleTable]

    place: str
    date_str: str
    signatory_name: str
