"""Renders a ``StatementOfIncomeContext`` to PDF bytes using reportlab Platypus.

Pure layout code — it does not know anything about ITR forms or tax law,
only how to draw the generic ``SummaryRow``/``ScheduleTable`` shapes
produced by ``app/engine/reports/builders.py``.
"""

from __future__ import annotations

import io
from typing import Any
from xml.sax.saxutils import escape as _xml_escape

from app.engine.reports.formatting import format_inr
from app.engine.reports.models import ScheduleTable, StatementOfIncomeContext, SummaryRow

_PAGE_MARGIN = 36


def _esc(value: Any) -> str:
    """Escape a value for embedding in a reportlab ``Paragraph``.

    ``Paragraph`` parses its input as a small XML/HTML-like markup
    language. A raw ``&``/``<``/``>`` in real data (an "R & K Enterprises"
    business name, an address containing "<"/">") is invalid markup that
    reportlab silently *drops* rather than raising — truncating the
    visible text with no error, no exception, and a structurally valid
    but wrong PDF. Every dynamic value (names, addresses, TAN, bank
    names, deductor names, ...) must pass through this before reaching a
    Paragraph; this module's own literal tags (``<br/>``, ``<para>``) are
    written directly in the f-string, never through this function.
    """
    if value is None:
        return ""
    return _xml_escape(str(value))


def render_statement_of_income(ctx: StatementOfIncomeContext) -> bytes:
    """Render the Statement of Income report to PDF bytes.

    Raises:
        ImportError: if reportlab is not installed — callers should fall
            back to a minimal PDF shell, matching this endpoint's
            existing degrade-gracefully convention.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    styles = {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=13, leading=16, alignment=1),
        "sched_title": ParagraphStyle("sched_title", fontName="Helvetica-Bold", fontSize=10, leading=13, spaceBefore=10, spaceAfter=3),
        "sched_subtitle": ParagraphStyle("sched_subtitle", fontName="Helvetica-Oblique", fontSize=8.5, leading=11, spaceAfter=3),
        "note": ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=7.5, leading=10, textColor=colors.HexColor("#555555"), spaceBefore=3),
        "footer": ParagraphStyle("footer", fontName="Helvetica", fontSize=9, leading=12),
    }

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=_PAGE_MARGIN, rightMargin=_PAGE_MARGIN,
        topMargin=_PAGE_MARGIN, bottomMargin=_PAGE_MARGIN,
        title=f"Statement of Income — {ctx.name}",
    )
    content_width = A4[0] - 2 * _PAGE_MARGIN

    story: list = []
    story.append(_build_header_table(ctx, content_width, colors))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Statement of Income", styles["title"]))
    story.append(Spacer(1, 6))
    story.append(_build_summary_table(ctx.summary_rows, content_width, colors))

    for sched in ctx.schedules:
        block = [Paragraph(f"Schedule {sched.number} — {_esc(sched.title)}", styles["sched_title"])]
        if sched.subtitle:
            block.append(Paragraph(_esc(sched.subtitle), styles["sched_subtitle"]))
        block.append(_build_schedule_table(sched, content_width, colors))
        if sched.note:
            block.append(Paragraph(_esc(sched.note), styles["note"]))
        story.append(KeepTogether(block))

    story.append(Spacer(1, 24))
    story.append(_build_signature_block(ctx, content_width, styles["footer"]))

    doc.build(story)
    return buf.getvalue()


def _build_header_table(ctx: StatementOfIncomeContext, width: float, colors) -> "Table":
    from reportlab.platypus import Table, TableStyle

    # Escape each address line individually, then join with a LITERAL
    # <br/> — escaping the joined string instead would also mangle that
    # intentional tag into "&lt;br/&gt;", printing it as visible text.
    address = "<br/>".join(_esc(line) for line in ctx.address_lines) if ctx.address_lines else "-"
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    cell_style = ParagraphStyle("cell", fontName="Helvetica", fontSize=9, leading=11)
    label_style = ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=9, leading=11)

    left_rows = [
        [Paragraph("Name", label_style), Paragraph(f": {_esc(ctx.name) or '-'}", cell_style)],
        [Paragraph("Father's Name", label_style), Paragraph(f": {_esc(ctx.father_name) or '-'}", cell_style)],
        [Paragraph("Address", label_style), Paragraph(f": {address}", cell_style)],
    ]
    right_rows = [
        [Paragraph("Previous Year", label_style), Paragraph(f": {_esc(ctx.previous_year)}", cell_style)],
        [Paragraph("PAN", label_style), Paragraph(f": {_esc(ctx.pan) or '-'}", cell_style)],
        [Paragraph("Aadhaar No.", label_style), Paragraph(f": {_esc(ctx.aadhaar) or '-'}", cell_style)],
        [Paragraph("Date of Birth", label_style), Paragraph(f": {_esc(ctx.date_of_birth) or '-'}", cell_style)],
        [Paragraph("Status", label_style), Paragraph(f": {_esc(ctx.status_label)}", cell_style)],
        [Paragraph("Residential Status", label_style), Paragraph(f": {_esc(ctx.resident_status_label)}", cell_style)],
        [Paragraph("Tax Regime", label_style), Paragraph(f": {_esc(ctx.regime_label)}", cell_style)],
    ]
    while len(left_rows) < len(right_rows):
        left_rows.append(["", ""])

    ay_style = ParagraphStyle("ay", fontName="Helvetica-Bold", fontSize=10, alignment=1)
    ay_box = Table(
        [[Paragraph("A.Y.", ay_style), Paragraph(_esc(ctx.assessment_year), ay_style)]],
        colWidths=[width * 0.15, width * 0.2],
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.75, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]),
    )

    label_value_style = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ])
    left_table = Table(left_rows, colWidths=[width * 0.16, width * 0.34], style=label_value_style)
    right_table = Table(right_rows, colWidths=[width * 0.16, width * 0.34], style=label_value_style)
    two_col = Table(
        [[left_table, right_table]],
        colWidths=[width * 0.5, width * 0.5],
        style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
    )

    outer = Table(
        [[ay_box], [two_col]],
        colWidths=[width],
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]),
    )
    return outer


_KIND_SPAN = {"headtotal": (0, 2), "grand": (0, 2), "plain": (0, 2), "info": (0, 2)}


def _build_summary_table(rows: list[SummaryRow], width: float, colors) -> "Table":
    from reportlab.platypus import Table, TableStyle

    col_widths = [width * 0.52, width * 0.08, width * 0.20, width * 0.20]
    # A header row ("Sch.No" / "Rs." / "Rs.") matching the reference
    # Winman-style layout this report is modeled on -- not present before,
    # not a deliberate omission, just not carried over when this table was
    # first built.
    data: list[list[str]] = [["", "Sch.No", "Rs.", "Rs."]]
    style_cmds: list[tuple] = [
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (2, 0), (3, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
    ]

    for row_idx, row in enumerate(rows):
        i = row_idx + 1  # +1 to account for the header row occupying data[0]
        if row.kind == "spacer":
            data.append(["", "", "", ""])
            continue
        if row.kind == "head":
            data.append([f"■  {row.label}", "", "", ""])
            style_cmds.append(("SPAN", (0, i), (3, i)))
            style_cmds.append(("FONTNAME", (0, i), (0, i), "Helvetica-Bold"))
            style_cmds.append(("TOPPADDING", (0, i), (-1, i), 6))
            continue
        if row.kind == "item":
            data.append([f"    {row.label}", row.sch_no, format_inr(row.amount) if row.amount is not None else "", ""])
            style_cmds.append(("FONTNAME", (0, i), (0, i), "Helvetica-Oblique"))
            style_cmds.append(("ALIGN", (2, i), (2, i), "RIGHT"))
            style_cmds.append(("ALIGN", (1, i), (1, i), "CENTER"))
            continue
        # headtotal / grand / plain / info — label spans cols 0-2, amount in col 3
        label = row.label
        if row.kind == "info" and row.sch_no:
            label = f"{label}"
        data.append([label, "", "", format_inr(row.amount) if row.amount is not None else ""])
        style_cmds.append(("SPAN", (0, i), (2, i)))
        style_cmds.append(("ALIGN", (3, i), (3, i), "RIGHT"))
        if row.kind == "headtotal":
            style_cmds.append(("FONTNAME", (0, i), (0, i), "Helvetica-Oblique"))
            style_cmds.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))
        elif row.kind == "grand":
            style_cmds.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
            style_cmds.append(("LINEABOVE", (0, i), (-1, i), 0.75, colors.black))
            style_cmds.append(("TOPPADDING", (0, i), (-1, i), 4))
        elif row.kind == "info":
            style_cmds.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Oblique"))
            style_cmds.append(("TEXTCOLOR", (0, i), (-1, i), colors.HexColor("#555555")))
        if row.bold:
            style_cmds.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
        if row.italic:
            style_cmds.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Oblique"))

    return Table(data, colWidths=col_widths, style=TableStyle(style_cmds))


def _build_schedule_table(sched: ScheduleTable, width: float, colors) -> "Table":
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Table, TableStyle

    n_cols = len(sched.columns)
    first_col_width = width * (0.30 if n_cols > 4 else 0.36)
    other_width = (width - first_col_width) / max(n_cols - 1, 1)
    col_widths = [first_col_width] + [other_width] * (n_cols - 1)

    left_style = ParagraphStyle("sched_left", fontName="Helvetica", fontSize=8, leading=10)
    right_style = ParagraphStyle("sched_right", fontName="Helvetica", fontSize=8, leading=10, alignment=2)
    left_bold = ParagraphStyle("sched_left_b", parent=left_style, fontName="Helvetica-Bold")
    right_bold = ParagraphStyle("sched_right_b", parent=right_style, fontName="Helvetica-Bold")

    # Right-align every column but the first -- these are almost always
    # money/numeric tables. The one exception is a 2-column "Field"/"Value"
    # identity table (e.g. Employer Details), whose second column holds
    # narrative text (an address, say), not a number; a "Particulars"/
    # "Amount" table (House Property, Interest, Dividends, ...) is still a
    # money table despite also having 2 columns, so key off the literal
    # header "Value" rather than column count -- column count alone
    # previously left-aligned every 2-column table's Amount figures,
    # visually inconsistent with every 3+ column table's right-aligned ones.
    is_identity_pair = n_cols == 2 and sched.columns[1] == "Value"
    right_align_from = n_cols if is_identity_pair else 1

    def _row(cells: list[str], bold: bool) -> list:
        out = []
        for col_idx, cell in enumerate(cells):
            is_right = col_idx >= right_align_from and col_idx > 0
            style = (right_bold if is_right else left_bold) if bold else (right_style if is_right else left_style)
            out.append(Paragraph(_esc(cell), style))
        return out

    # Headers reuse _row()'s own per-column alignment (bold=True gives the
    # header weight) so a header cell never sits at a different horizontal
    # position than the data underneath it in the same column.
    data = [_row(sched.columns, bold=True)]
    data.extend(_row(row, bold=False) for row in sched.rows)
    if sched.total_row:
        data.append(_row(sched.total_row, bold=True))

    style_cmds: list[tuple] = [
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if sched.total_row:
        last = len(data) - 1
        style_cmds.append(("LINEABOVE", (0, last), (-1, last), 0.75, colors.black))

    return Table(data, colWidths=col_widths, style=TableStyle(style_cmds), repeatRows=1)


def _build_signature_block(ctx: StatementOfIncomeContext, width: float, style) -> "Table":
    from reportlab.platypus import Paragraph, Table

    left = Paragraph(f"Place: {_esc(ctx.place) or '-'}<br/>Date: {_esc(ctx.date_str) or '-'}", style)
    right = Paragraph(f"<para alignment='right'>({_esc(ctx.signatory_name) or '-'})</para>", style)
    return Table([[left, right]], colWidths=[width * 0.5, width * 0.5])
