"""TIS PDF extractor (pdfplumber).

Rewrites the parsing core of ``ais_extractor.tis_extractor`` to use
pdfplumber's table extraction instead of a PyMuPDF line-state machine.
pdfplumber recovers proper cell boundaries and the summary/detail row
pairing, eliminating the line-anchoring fragility of the legacy parser.

Output shape is unchanged — ``TISDocument`` / ``TISEntry`` / ``TISDetailRow``
dataclasses, the ``overview``/``income_heads``/``reconciliation`` JSON
contract, and the ``extract_tis`` / ``tis_to_frontend_json`` entry points are
preserved, so callers (``reconciliation.py``, the frontend mappers) work
unchanged.

TIS PDF structure (verified across the real 64-PDF corpus):

* **Page 1** carries an overview table (4 cols: ``SR. NO. | INFORMATION
  CATEGORY | PROCESSED BY SYSTEM | ACCEPTED BY TAXPAYER/CONFIRMED BY SOURCE``)
  with one row per category — the cross-foot totals to reconcile against.
* **Pages 2+** carry the Annexure: each category renders as its own table
  whose row 0 is the overview row (repeated), row 1 is the overview data
  (``sr | category | ... | processed | accepted``), row 2 is the detail
  header (``SR. NO. | PART | INFORMATION DESCRIPTION | INFORMATION SOURCE |
  AMOUNT DESCRIPTION | REPORTED BY SOURCE | PROCESSED BY SYSTEM | ACCEPTED
  BY...``), and rows 3+ are detail rows.  Empty padding cells appear between
  merged header columns and are dropped during normalisation.
* Footer/header noise tables (1 column) carry page metadata and are skipped.
"""
from __future__ import annotations

import re
from typing import Any

from .tis_extractor import (
    TISDetailRow,
    TISDocument,
    TISEntry,
    TISMetadata,
    TISSummaryRow,
    asdict,
    detail_to_dict,
    entry_to_dict,
    extract_pan,
    map_category,
    parse_indian_amount,
    _extract_metadata as _legacy_extract_metadata,
    reconcile as _reconcile_overview,
    _group_by_head,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

_PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
_DOWNLOAD_ID_RE = re.compile(r"Download ID\s*:\s*(\S+)")
_GEN_DATE_RE = re.compile(r"Generation Date\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4},\s*[0-9]{2}:[0-9]{2}:[0-9]{2})")
_FY_RE = re.compile(r"Financial Year\s+(\d{4}-\d{2})")
_AMT_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def _clean(cell: Any) -> str:
    """Normalise a pdfplumber cell to a single-line trimmed string."""
    if cell is None:
        return ""
    s = str(cell).replace("\n", " ").replace("\r", " ").replace("\t", " ")
    return " ".join(s.split())


def _is_amount(s: str) -> bool:
    s = s.strip()
    if not s or s in ("-", "--"):
        return False
    return bool(re.fullmatch(r"[\d,]+(?:\.\d+)?", s))


# ── Overview / detail header detection ───────────────────────────────────────

_OVERVIEW_HEADER_SIG = ("SR. NO.", "INFORMATION CATEGORY")
_DETAIL_HEADER_SIG = ("SR. NO.", "PART")


def _is_overview_header(cells: list[str]) -> bool:
    nonempty = [c for c in cells if c]
    return len(nonempty) >= 2 and tuple(nonempty[:2]) == _OVERVIEW_HEADER_SIG


def _is_detail_header(cells: list[str]) -> bool:
    nonempty = [c for c in cells if c]
    return len(nonempty) >= 2 and tuple(nonempty[:2]) == _DETAIL_HEADER_SIG


def _is_noise_table(table: list[list[str]]) -> bool:
    if not table:
        return True
    ncols = max((len(r) for r in table), default=0)
    if ncols <= 1:
        joined = " ".join(_clean(c) for row in table for c in row)
        return bool(joined)
    return False


# TIS part labels that appear as the second column of a detail row.
_KNOWN_PART_LABELS = {"SFT", "TDS", "TCS", "TDS/TCS", "TDS/ TCS", "Other", "EXC"}


def _is_detail_header_only_continuation(table: list[list[str]]) -> bool:
    """A TIS continuation table whose first non-empty row is a detail header
    (``SR. NO. | PART | ...``) with no preceding overview-data row — the
    detail section spilled onto a new page and pdfplumber emitted the detail
    header again before resuming the rows.

    Returns False when the table also carries an overview-data row (``sr |
    category | proc | acc``) — that makes it a genuine new entry, not a
    continuation, even if the detail header appears first (the overview row
    can be in a later row of the same table).
    """
    has_overview_data = False
    for row in table:
        cells = [_clean(c) for c in row]
        nonempty = [c for c in cells if c]
        if not nonempty:
            continue
        if _is_overview_header(cells):
            continue
        if _is_detail_header(cells):
            continue
        # Overview-data row: sr + category + two trailing amounts, where the
        # category is NOT a part label.
        if (
            len(nonempty) >= 4
            and nonempty[0].isdigit()
            and not _looks_like_part_label(nonempty[1])
            and _is_amount(nonempty[-1])
            and _is_amount(nonempty[-2])
        ):
            has_overview_data = True
            break
    if has_overview_data:
        return False
    for row in table:
        cells = [_clean(c) for c in row]
        nonempty = [c for c in cells if c]
        if not nonempty:
            continue
        return _is_detail_header(cells)
    return False


def _parse_detail_header_continuation(table: list[list[str]]) -> list[TISDetailRow]:
    """Parse a detail-header-only continuation table into detail rows.

    Skips the leading detail-header row(s) and parses every subsequent
    detail row until an overview header or the table ends.
    """
    rows: list[TISDetailRow] = []
    past_header = False
    for raw in table:
        cells = [_clean(c) for c in raw]
        nonempty = [c for c in cells if c]
        if not nonempty:
            continue
        if _is_overview_header(cells):
            break
        if _is_detail_header(cells):
            past_header = True
            continue
        if not past_header:
            continue
        detail = _parse_detail_row(cells)
        if detail:
            rows.append(detail)
    return rows


def _is_detail_only_continuation(table: list[list[str]]) -> bool:
    """A TIS continuation table: first non-empty row is a detail row (no
    overview header, no detail header) — the detail section spilled onto the
    next page and resumes the row numbering directly."""
    for row in table:
        cells = [_clean(c) for c in row]
        nonempty = [c for c in cells if c]
        if not nonempty:
            continue
        if _is_overview_header(cells) or _is_detail_header(cells):
            return False
        # A detail row's first cell is a digit or a part label.
        if nonempty[0].isdigit() or nonempty[0] in _KNOWN_PART_LABELS:
            return True
        return False
    return False


def _parse_detail_only_continuation(table: list[list[str]]) -> list[TISDetailRow]:
    """Parse a detail-only continuation table into detail rows."""
    rows: list[TISDetailRow] = []
    for raw in table:
        cells = [_clean(c) for c in raw]
        if _is_overview_header(cells) or _is_detail_header(cells):
            continue
        detail = _parse_detail_row(cells)
        if detail:
            rows.append(detail)
    return rows


def _looks_like_part_label(token: str) -> bool:
    """True when a detail row's second cell is a part label, not a category."""
    return token in _KNOWN_PART_LABELS


# ── Overview parsing (page 1) ───────────────────────────────────────────────


def _parse_overview_row(cells: list[str]) -> TISSummaryRow | None:
    """Parse an overview data row: ``sr | category | processed | accepted``."""
    nonempty = [c for c in cells if c]
    if len(nonempty) < 4:
        return None
    if not nonempty[0].isdigit():
        return None
    try:
        sr = int(nonempty[0])
    except ValueError:
        return None
    category = nonempty[1]
    # Processed + accepted are the trailing two amount tokens.
    if not (_is_amount(nonempty[-1]) and _is_amount(nonempty[-2])):
        return None
    processed = parse_indian_amount(nonempty[-2])
    accepted = parse_indian_amount(nonempty[-1])
    return TISSummaryRow(
        sr_no=sr, category=category,
        processed_by_system=processed, accepted_by_taxpayer=accepted,
    )


def _parse_overview_table(table: list[list[str]]) -> list[TISSummaryRow]:
    rows: list[TISSummaryRow] = []
    for raw in table:
        cells = [_clean(c) for c in raw]
        if _is_overview_header(cells):
            continue
        row = _parse_overview_row(cells)
        if row:
            rows.append(row)
    return rows


# ── Entry (overview + detail) parsing ────────────────────────────────────────


def _parse_overview_data_row(cells: list[str]) -> tuple[int, str, float, float] | None:
    """Parse an annexure overview data row → (sr, category, processed, accepted)."""
    nonempty = [c for c in cells if c]
    if len(nonempty) < 4 or not nonempty[0].isdigit():
        return None
    try:
        sr = int(nonempty[0])
    except ValueError:
        return None
    category = nonempty[1]
    if not (_is_amount(nonempty[-1]) and _is_amount(nonempty[-2])):
        return None
    return sr, category, parse_indian_amount(nonempty[-2]), parse_indian_amount(nonempty[-1])


def _parse_detail_row(cells: list[str]) -> TISDetailRow | None:
    """Parse a TIS detail data row.

    TIS detail rows have two shapes:

    * ``sr | part | description | source | amount_description | reported |
      processed | accepted`` — the canonical 8-column row.
    * ``part | description | source | amount_description | reported |
      processed | accepted`` — when the AIS collapses the serial number into
      the part cell (rows sharing a source) the leading sr is absent; the
      part may be ``SFT``, ``TDS/TCS`` or ``Other``.

    The trailing three tokens are amounts (reported / processed / accepted).
    Some rows carry only two trailing amounts when processed == accepted and
    pdfplumber merged cells, or when a TDS row has ``-`` placeholders.

    The serial number defaults to 0 when absent/merged (e.g. ``"1 2"``); the
    part is detected from the first token when it is a known part label.
    """
    nonempty = [c for c in cells if c]
    if len(nonempty) < 5:
        return None

    # Determine the leading sr and part.  The first token may be a pure
    # digit (``"1"``), a merged pair (``"1 2"``), or a part label.
    known_parts = {"SFT", "TDS", "TCS", "TDS/TCS", "TDS/ TCS", "Other", "EXC"}
    first = nonempty[0]
    sr = 0
    part = "SFT"
    body_start = 0
    if first.isdigit():
        sr = int(first)
        # Second token is the part.
        if len(nonempty) >= 2 and nonempty[1] in known_parts:
            part = "TDS/TCS" if nonempty[1] in ("TDS", "TCS", "TDS/TCS", "TDS/ TCS") else nonempty[1]
            body_start = 2
        else:
            body_start = 1
    elif first in known_parts:
        part = "TDS/TCS" if first in ("TDS", "TCS", "TDS/TCS", "TDS/ TCS") else first
        body_start = 1
    else:
        # A merged sr like ``"1 2"`` — take the first digit run.
        m = re.match(r"(\d+)", first)
        if m:
            sr = int(m.group(1))
            body_start = 1
            # The remainder of the cell may be a part label.
            rest = first[m.end():].strip()
            if rest in known_parts:
                part = "TDS/TCS" if rest in ("TDS", "TCS", "TDS/TCS", "TDS/ TCS") else rest
        else:
            return None

    body = nonempty[body_start:]
    if len(body) < 4:
        return None

    # The trailing amounts: reported / processed / accepted.  Accept ``-`` as
    # a zero placeholder for TDS rows.
    def _is_amt_or_dash(s: str) -> bool:
        return _is_amount(s) or s in ("-", "--")

    if not (_is_amt_or_dash(body[-1]) and _is_amt_or_dash(body[-2])):
        return None
    accepted = parse_indian_amount(body[-1]) if body[-1] not in ("-", "--") else 0.0
    processed = parse_indian_amount(body[-2]) if body[-2] not in ("-", "--") else 0.0
    if len(body) >= 3 and _is_amt_or_dash(body[-3]):
        reported = parse_indian_amount(body[-3]) if body[-3] not in ("-", "--") else 0.0
        middle = body[:-3]
    else:
        reported = 0.0
        middle = body[:-2]

    # middle = [description..., source..., amount_description...]
    # Source is the trailing run containing a PAN/code in parentheses.
    source_start = len(middle)
    for idx in range(len(middle)):
        if re.search(r"\([A-Z]{4,10}[0-9]{2,5}[A-Z]?[^\)]*\)", middle[idx]) or _PAN_RE.search(middle[idx]):
            source_start = idx
            break
    description = " ".join(middle[:source_start]).strip()
    remaining = body[source_start:]
    if len(remaining) <= 1:
        amount_desc = " ".join(remaining).strip()
        source = ""
    else:
        source = " ".join(remaining[:-1]).strip()
        amount_desc = remaining[-1]
    return TISDetailRow(
        sr_no=sr,
        part=part,
        information_description=description[:300],
        information_source=source[:300],
        institution_pan=extract_pan(source),
        amount_description=amount_desc[:100],
        reported_by_source=f"{reported:.0f}",
        processed_by_system=f"{processed:.0f}",
        accepted_by_taxpayer=f"{accepted:.0f}",
    )


def _parse_entry_table(table: list[list[str]]) -> list[TISEntry]:
    """Parse an Annexure table into one or more TIS entries.

    Each entry is laid out as: overview-header → overview-data → detail-header
    → detail-rows.  A single pdfplumber table may contain multiple entries
    merged together.  We walk the table with a small state machine so that a
    row is only treated as overview-data while we are between the overview
    header and the detail header; once the detail header appears, subsequent
    numeric rows are detail rows until the next overview header appears.
    """
    entries: list[TISEntry] = []
    current: TISEntry | None = None
    seen_detail_header = False
    i = 0
    n = len(table)
    while i < n:
        cells = [_clean(c) for c in table[i]]
        nonempty = [c for c in cells if c]
        if not nonempty:
            i += 1
            continue
        # Overview header — marks a new entry's overview section.
        if _is_overview_header(cells):
            if current is not None:
                entries.append(current)
                current = None
            seen_detail_header = False
            i += 1
            continue
        # Detail header — marks the transition from overview to detail rows.
        if _is_detail_header(cells):
            seen_detail_header = True
            i += 1
            continue
        if not seen_detail_header:
            # Overview data row → starts a new entry.
            ov = _parse_overview_data_row(cells)
            if ov is not None:
                if current is not None:
                    entries.append(current)
                sr, category, processed, accepted = ov
                current = TISEntry(
                    sr_no=sr, category=category,
                    processed_by_system=processed, accepted_by_taxpayer=accepted,
                )
                i += 1
                continue
        else:
            # We are past a detail header.  A numeric row here is usually a
            # detail row, but it may be the next entry's overview-data row
            # (the AIS repeats the overview row before each entry's detail
            # table).  Distinguish: an overview-data row's second token is a
            # category *description* (e.g. ``Interest from deposit``) while a
            # detail row's second token is a part label (``SFT``/``TDS/``).
            # If this row looks like an overview-data row, start a new entry
            # instead of treating it as a detail.
            ov = _parse_overview_data_row(cells)
            looks_like_overview = (
                ov is not None
                and len(nonempty) >= 2
                and not _looks_like_part_label(nonempty[1])
            )
            if looks_like_overview:
                if current is not None:
                    entries.append(current)
                sr, category, processed, accepted = ov  # type: ignore[misc]
                current = TISEntry(
                    sr_no=sr, category=category,
                    processed_by_system=processed, accepted_by_taxpayer=accepted,
                )
                seen_detail_header = False
                i += 1
                continue
            if current is not None:
                detail = _parse_detail_row(cells)
                if detail:
                    current.details.append(detail)
        i += 1
    if current is not None:
        entries.append(current)
    for e in entries:
        e.income_head = map_category(e.category)
    return entries


# ── Metadata ─────────────────────────────────────────────────────────────────


def _extract_metadata_from_text(text: str) -> TISMetadata:
    """Parse Part A - General Information + footer for TIS metadata.

    TIS carries the same Part A label/value grid as AIS:
    ``Permanent Account Number (PAN) Aadhaar Number Name of Assessee``
    followed by a values line, then ``Date of Birth Mobile Number E-mail
    Address`` + values, then ``Address`` + the address block.
    """
    meta = TISMetadata()
    lines = [ln.strip() for ln in text.split("\n")]
    try:
        pan_label_idx = next(i for i, ln in enumerate(lines) if "Permanent Account Number" in ln)
    except StopIteration:
        pan_label_idx = -1
    if pan_label_idx >= 0 and pan_label_idx + 1 < len(lines):
        vals = lines[pan_label_idx + 1].split()
        if vals and _PAN_RE.fullmatch(vals[0]):
            meta.pan = vals[0]
        if len(vals) >= 3:
            meta.aadhaar_masked = " ".join(vals[1:4]) if len(vals) >= 4 else vals[1]
            meta.name = " ".join(vals[4:]) if len(vals) > 4 else " ".join(vals[2:])
    if not meta.pan:
        for ln in lines:
            m = _PAN_RE.search(ln)
            if m:
                meta.pan = m.group(0)
                break
    try:
        dob_label_idx = next(i for i, ln in enumerate(lines) if "Date of Birth" in ln)
    except StopIteration:
        dob_label_idx = -1
    if dob_label_idx >= 0 and dob_label_idx + 1 < len(lines):
        vals = lines[dob_label_idx + 1].split()
        if vals and re.fullmatch(r"\d{2}/\d{2}/\d{4}", vals[0]):
            meta.dob = vals[0]
        if len(vals) >= 2 and re.fullmatch(r"\d{10}", vals[1]):
            meta.mobile = vals[1]
        if len(vals) >= 3 and "@" in vals[2]:
            meta.email = vals[2]
    try:
        addr_idx = next(i for i, ln in enumerate(lines) if ln == "Address")
    except StopIteration:
        addr_idx = -1
    if addr_idx >= 0:
        addr_lines: list[str] = []
        for ln in lines[addr_idx + 1 : addr_idx + 6]:
            if not ln or ln.startswith("---") or "Taxpayer Information Summary" in ln:
                break
            addr_lines.append(ln)
        meta.address = ", ".join(a for a in addr_lines if a)
    dl_match = _DOWNLOAD_ID_RE.search(text)
    if dl_match:
        meta.download_id = dl_match.group(1)
    gd_match = _GEN_DATE_RE.search(text)
    if gd_match:
        meta.generation_date = gd_match.group(1)
    fy_match = _FY_RE.search(text)
    if fy_match:
        meta.financial_year = fy_match.group(1)
    if not meta.name:
        footer = re.search(rf"{meta.pan}\s+(.+?)\s+\d{{4}}-\d{{2}}\b", text)
        if footer:
            meta.name = " ".join(footer.group(1).split())
    return meta


# ── Main entry point ─────────────────────────────────────────────────────────


def extract_tis(pdf_path: str) -> TISDocument:
    """Extract a TIS PDF into the canonical ``TISDocument``.

    Walks every pdfplumber table on every page: the page-1 overview table
    yields the cross-foot ``overview`` rows; each Annexure table yields one
    or more entries (overview data + detail rows).  Footer/header noise
    tables are skipped.  Overview-vs-detail reconciliation is computed at
    the end so the frontend can surface any mismatch.
    """
    import pdfplumber

    doc = TISDocument()
    full_text_parts: list[str] = []
    overview_rows: list[TISSummaryRow] = []
    ordered_tables: list[tuple[str, list[list[str]]]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            full_text_parts.append(page.extract_text() or "")
            for raw in page.extract_tables():
                if not raw:
                    continue
                table = [[_clean(c) for c in row] for row in raw]
                if _is_noise_table(table):
                    continue
                # Classify in page order so continuations merge into the right
                # entry.  A table is:
                #  - ``overview``   : the page-1 summary (no PART detail header)
                #  - ``entry``      : an Annexure table with an overview row +
                #                      a PART detail header
                #  - ``continuation``: a detail-only table (page-break spill of
                #                      the previous entry's detail section)
                has_detail_header = any(
                    _is_detail_header([_clean(c) for c in row]) for row in table
                )
                # A detail-header-only table (no preceding overview-data row)
                # is a page-break continuation of the previous entry's detail
                # section — merge its rows into the last entry, not a new one.
                if has_detail_header and _is_detail_header_only_continuation(table):
                    ordered_tables.append(("continuation", table))
                elif has_detail_header:
                    ordered_tables.append(("entry", table))
                elif _is_detail_only_continuation(table):
                    ordered_tables.append(("continuation", table))
                else:
                    ordered_tables.append(("overview", table))

    full_text = "\n".join(full_text_parts)
    doc.metadata = _extract_metadata_from_text(full_text)

    # First, the page-1 overview rows come from the leading ``overview``
    # tables (before any ``entry`` table appears).
    for kind, table in ordered_tables:
        if kind == "overview":
            overview_rows.extend(_parse_overview_table(table))
        else:
            break
    doc.overview = overview_rows

    # Build entries in order.  An "entry" table yields one or more entries
    # directly; an "overview" table may carry an overview-data row whose
    # detail table was split off into a later "continuation" table (a page
    # break can separate the overview row from its detail header).  We track
    # "pending" overview-data rows that haven't yet acquired detail rows, and
    # when a continuation table appears, attach it to the most recent pending
    # entry (creating it from the pending overview row if needed).
    entries: list[TISEntry] = []
    pending: TISEntry | None = None
    # The page-1 overview table comes before any entry/continuation; once we
    # see the first entry/continuation we are in the Annexure and standalone
    # overview-data rows are split-off entry overviews to hold pending.
    in_annexure = False
    for kind, table in ordered_tables:
        if kind in ("entry", "continuation"):
            in_annexure = True
        if kind == "entry":
            if pending is not None:
                entries.append(pending)
                pending = None
            new_entries = _parse_entry_table(table)
            entries.extend(new_entries)
            if new_entries:
                pending = None
        elif kind == "overview":
            if not in_annexure:
                # Page-1 overview — already captured in overview_rows above.
                continue
            for row in table:
                cells = [_clean(c) for c in row]
                if _is_overview_header(cells) or _is_detail_header(cells):
                    continue
                ov = _parse_overview_data_row(cells)
                if ov is None:
                    continue
                if pending is not None:
                    entries.append(pending)
                sr, category, processed, accepted = ov
                pending = TISEntry(
                    sr_no=sr, category=category,
                    processed_by_system=processed, accepted_by_taxpayer=accepted,
                    income_head=map_category(category),
                )
        elif kind == "continuation":
            if _is_detail_header_only_continuation(table):
                cont_rows = _parse_detail_header_continuation(table)
            else:
                cont_rows = _parse_detail_only_continuation(table)
            if pending is not None:
                pending.details.extend(cont_rows)
                entries.append(pending)
                pending = None
            elif entries:
                entries[-1].details.extend(cont_rows)
    if pending is not None:
        entries.append(pending)
    doc.entries = entries
    doc.reconciliation = _reconcile_overview(doc.overview, doc.entries)
    doc.income_head_groups = _group_by_head(doc)
    return doc


def tis_to_frontend_json(doc: TISDocument, indent: int = 2) -> str:
    """Serialise a TISDocument to the frontend JSON contract."""
    import json

    output = {
        "metadata": asdict(doc.metadata),
        "income_heads": doc.income_head_groups,
        "overview": [asdict(o) for o in doc.overview],
        "reconciliation": doc.reconciliation,
        "summary": {
            "total_categories": len(doc.entries),
            "total_details": sum(len(e.details) for e in doc.entries),
        },
    }
    return json.dumps(output, indent=indent, ensure_ascii=False)
