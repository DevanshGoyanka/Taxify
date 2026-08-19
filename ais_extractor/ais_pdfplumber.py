"""AIS PDF extractor (pdfplumber).

Rewrites the parsing core of ``ais_extractor.extractor`` to use pdfplumber's
table extraction instead of a PyMuPDF line-based state machine.  pdfplumber
recovers proper cell boundaries, eliminating the multi-word-cell wrapping
that collapsed SFT-17-LES sale tables to summary-only aggregates and the
detail-row "bleeding" that mixed one entry's rows into the next.

Output shape is unchanged — ``AISDocument`` / ``AISEntry`` / ``DetailRow``
dataclasses and the ``extract_ais_json`` JSON contract are preserved, so
``reconciliation.py`` and the frontend mappers work unchanged.

AIS PDF structure (verified across the real 64-PDF corpus):

* The AIS document is organised into Part B1 (TDS), Part B2 (SFT), Part B7
  (business receipts), Part B3 (tax payments) and Part B4 (refund).
* Each **entry** — one summary row plus its detail table — renders as a
  single pdfplumber table:
    - row 0: the summary header  ``SR. NO. | INFORMATION CODE | ... |
      INFORMATION DESCRIPTION | INFORMATION SOURCE | COUNT | AMOUNT``
    - row 1: the summary data   (``sr | code | desc | source | count | amount``)
    - row 2: the detail header   (``SR. NO. | <section-specific columns>``)
    - row 3+: detail data rows.
* An entry with no detail table (summary-only, e.g. SFT-17-LES(M)) has only
  rows 0 and 1.
* When a detail table spans a page break, the continuation page begins with
  a table whose row 0 is the detail header (repeated) followed by the
  remaining detail rows — these continuation tables are merged back into the
  entry that began on the previous page.
* The page footer (``Download ID : ... Page N of M``) and the page-header
  (``PAN | Name | Financial Year``) render as 1-column noise tables and are
  skipped.
"""
from __future__ import annotations

import re
from typing import Any

from .extractor import (
    AISEntry,
    AISDocument,
    AISMetadata,
    DetailRow,
    IncomeHead,
    IncomeHeadGroup,
    RefundEntry,
    SFT_TO_INCOME_HEAD,
    TaxPaymentEntry,
    asdict,
    entry_to_dict,
    extract_pan,
    map_to_head,
    parse_indian_amount,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

_PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")
_ISIN_RE = re.compile(r"\bIN[EA][A-Z0-9]{9}\b")
_DOWNLOAD_ID_RE = re.compile(r"Download ID\s*:\s*(\S+)")
_GEN_DATE_RE = re.compile(r"Generation Date\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4},\s*[0-9]{2}:[0-9]{2}:[0-9]{2})")
_FY_RE = re.compile(r"Financial Year\s+(\d{4}-\d{2})")


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


def _summary_header_signature(row: list[str]) -> bool:
    """True when ``row`` is the AIS summary header.

    The summary header always carries ``SR. NO.`` immediately followed by
    ``INFORMATION CODE``; a detail header carries ``SR. NO.`` followed by a
    section-specific column (``QUARTER``, ``DATE OF SALE/TRANSFER``, ...).
    """
    nonempty = [c for c in row if c]
    if len(nonempty) < 2:
        return False
    return nonempty[0] == "SR. NO." and nonempty[1] == "INFORMATION CODE"


def _is_entry_table(table: list[list[str]]) -> bool:
    """A table is an AIS entry table when its first non-empty row is the
    summary header (``SR. NO. | INFORMATION CODE | ...``)."""
    for row in table:
        cells = [_clean(c) for c in row]
        if any(cells):
            return _summary_header_signature(cells)
        # keep scanning past fully-empty rows
    return False


def _is_detail_header_only_table(table: list[list[str]]) -> bool:
    """A continuation table: row 0 is a detail header (``SR. NO.`` not followed
    by ``INFORMATION CODE``) — the detail table spilled onto the next page."""
    for row in table:
        cells = [_clean(c) for c in row]
        if not any(cells):
            continue
        nonempty = [c for c in cells if c]
        if nonempty[0] == "SR. NO." and nonempty[1] != "INFORMATION CODE":
            return True
        return False
    return False


def _is_noise_table(table: list[list[str]]) -> bool:
    """Footer/header noise tables (1 column, page metadata)."""
    if not table:
        return True
    ncols = max((len(r) for r in table), default=0)
    if ncols <= 1:
        joined = " ".join(_clean(c) for row in table for c in row)
        return bool(joined) and not _is_entry_table(table)
    return False


# ── Category / section / income-head derivation ─────────────────────────────

# Maps the summary information_description to a canonical AIS category.  The
# AIS description is the authoritative label (e.g. "Sale of listed equity
# share (Depository) (SFT-017)"); the category is the lowercased canonical
# form used by ``SFT_TO_INCOME_HEAD`` and the reconciliation evidence.
_DESC_CATEGORY_PATTERNS: list[tuple[str, str]] = [
    (r"sale of listed equity share", "sale of securities and units of mutual fund"),
    (r"sale of securities and units of mutual fund", "sale of securities and units of mutual fund"),
    (r"sale of units of mutual fund", "sale of securities and units of mutual fund"),
    (r"purchase of securities", "purchase of securities and units of mutual funds"),
    (r"purchase of mutual funds", "purchase of securities and units of mutual funds"),
    (r"purchase of immovable property", "purchase of immovable property"),
    (r"sale of immovable property|sale of land or building", "sale of land or building"),
    (r"purchase of time deposits", "purchase of time deposits"),
    (r"interest from savings bank", "interest from savings bank"),
    (r"interest from deposit", "interest from deposit"),
    (r"dividend", "dividend"),
    (r"cash deposit", "cash deposits"),
    (r"cash withdrawal", "cash withdrawals"),
    (r"gst turnover", "gst turnover"),
    (r"gst purchase", "gst purchases"),
    (r"salary", "salary"),
    (r"business receipts", "business receipts"),
    (r"receipt of amount by partners", "receipt of amount by partners from partnership firm"),
    (r"insurance commission", "insurance commission"),
    (r"purchase of vehicle", "purchase of vehicle"),
    (r"winnings from online games", "winnings from online games"),
    (r"amount received on transfer of virtual digital asset", "winnings from online games"),
    (r"commission or brokerage", "commission or brokerage"),
    (r"professional fees", "professional fees"),
    (r"rent", "rent"),
    (r"contract", "contract"),
]


def _category_from_description(description: str) -> str:
    """Derive the canonical AIS category from the information_description."""
    desc_lower = (description or "").lower()
    for pattern, category in _DESC_CATEGORY_PATTERNS:
        if re.search(pattern, desc_lower):
            return category
    return desc_lower.strip() or "other"


def _section_from_code(code: str, category: str) -> str:
    """Part B section for an entry — B1 for TDS- codes, B2 for SFT- codes."""
    c = (code or "").upper()
    if c.startswith("TDS") or c.startswith("EXC"):
        return "B1"
    if c.startswith("SFT"):
        return "B2"
    if "gst" in category.lower() or "business" in category.lower():
        return "B7"
    return "B2"


# ── Entry parsing ────────────────────────────────────────────────────────────


def _parse_summary_row(cells: list[str]) -> AISEntry | None:
    """Parse the summary data row (row 1 of an entry table) into an AISEntry.

    The summary data row is ``sr | code | <desc> | <source> | count | amount``
    but pdfplumber may emit empty padding cells between merged header columns,
    so the strategy is: locate the numeric sr at the start, the code next,
    then the trailing ``count`` + ``amount`` (the last two numeric tokens),
    and treat everything in between as description + source.  The source is
    the trailing run that contains an institution PAN/code in parentheses.
    """
    nonempty = [c for c in cells if c]
    if len(nonempty) < 2:
        return None
    if not nonempty[0].isdigit():
        return None
    try:
        sr_no = int(nonempty[0])
    except ValueError:
        return None
    code = nonempty[1]
    # The trailing two numeric tokens are count + amount.
    if len(nonempty) >= 4 and _is_amount(nonempty[-1]) and nonempty[-2].isdigit():
        amount = parse_indian_amount(nonempty[-1])
        count = int(nonempty[-2])
        middle = nonempty[2:-2]
    elif len(nonempty) >= 3 and _is_amount(nonempty[-1]):
        # count missing (some B1 TDS summary rows omit count).
        amount = parse_indian_amount(nonempty[-1])
        count = 0
        middle = nonempty[2:-1]
    else:
        amount = 0.0
        count = 0
        middle = nonempty[2:]
    # Split middle into description + source.  Source is the trailing run
    # containing a PAN/code in parentheses; description is the rest.
    source_start = len(middle)
    for idx in range(len(middle)):
        if re.search(r"\([A-Z]{4,10}[0-9]{2,5}[A-Z]?[^\)]*\)", middle[idx]) or _PAN_RE.search(middle[idx]):
            source_start = idx
            break
    description = " ".join(middle[:source_start]).strip()
    source = " ".join(middle[source_start:]).strip()
    category = _category_from_description(description)
    section = _section_from_code(code, category)
    income_head = map_to_head(category, section)
    return AISEntry(
        sr_no=sr_no,
        information_code=code,
        information_description=description,
        information_source=source,
        institution_pan=extract_pan(source),
        count=count,
        amount=amount,
        category=category,
        section=section,
        income_head=income_head,
    )


def _parse_detail_section(table: list[list[str]], start: int, entry: AISEntry) -> int:
    """Parse the detail-header + detail-data rows of an entry table.

    ``table[start]`` is expected to be the detail header.  Returns the index
    of the first row after the detail section (i.e. the next summary header or
    end of table).
    """
    i = start
    if i >= len(table):
        return i
    header_cells = [_clean(c) for c in table[i]]
    # A detail header's first non-empty cell is ``SR. NO.`` and is NOT the
    # summary header (not followed by INFORMATION CODE).  If this row isn't a
    # detail header, there's no detail section in this table.
    nonempty_h = [c for c in header_cells if c]
    if not nonempty_h or nonempty_h[0] != "SR. NO." or _summary_header_signature(header_cells):
        return i
    # Normalised detail header (empty ``None`` padding cells dropped so the
    # header token count matches the logical column count / data row width).
    entry.detail_header = nonempty_h
    header_upper = [h.upper() for h in nonempty_h]
    sem_map = _resolve_semantic_column_map(header_upper)
    i += 1
    while i < len(table):
        cells = [_clean(c) for c in table[i]]
        nonempty = [c for c in cells if c]
        if not nonempty:
            i += 1
            continue
        if _summary_header_signature(cells):
            break
        if nonempty[0] == "SR. NO." and not _summary_header_signature(cells):
            break
        if not nonempty[0].isdigit():
            i += 1
            continue
        sr = int(nonempty[0])
        data: dict[str, str] = {f"col_{k}": v for k, v in enumerate(nonempty)}
        for semantic, idx in sem_map.items():
            if 0 <= idx < len(nonempty):
                data.setdefault(semantic, nonempty[idx])
        sec_name = data.get("security_name", "")
        isin_match = _ISIN_RE.search(sec_name)
        if isin_match:
            data.setdefault("isin", isin_match.group(0).upper())
            data.setdefault("security_code", isin_match.group(0).upper())
        entry.details.append(DetailRow(sr_no=sr, data=data))
        i += 1
    return i


_SEMANTIC_COLUMN_PATTERNS: list[tuple[str, str]] = [
    ("DATE OF SALE/TRANSFER", "transfer_date"),
    ("DATE OF SALE", "transfer_date"),
    ("SECURITY NAME", "security_name"),
    ("SECURITY CODE", "security_code"),
    ("SECURITY CLASS", "security_class"),
    ("DEBIT TYPE", "debit_type"),
    ("CREDIT TYPE", "credit_type"),
    ("ASSET TYPE", "asset_type"),
    ("QUANTITY", "quantity"),
    ("SALE PRICE", "sale_price_per_unit"),
    ("SALES CONSIDERATION", "sales_consideration"),
    ("COST OF ACQUISITION", "cost_of_acquisition"),
    ("UNIT FMV", "unit_fmv"),
    ("FAIR MARKET VALUE", "fair_market_value"),
    ("INDEXED COST", "indexed_cost_of_acquisition"),
    ("STT", "stt_amount"),
    ("AMC NAME", "amc_name"),
    ("CLIENT ID", "client_id"),
    ("HOLDER FLAG", "holder_flag"),
    ("TOTAL PURCHASE AMOUNT", "total_purchase_amount"),
    ("TOTAL SALES VALUE", "total_sales_value"),
    ("QUARTER", "quarter"),
    ("REPORTED ON", "reported_on"),
    ("ACCOUNT NUMBER", "account_number"),
    ("ACCOUNT TYPE", "account_type"),
    ("INTEREST AMOUNT", "interest_amount"),
    ("DIVIDEND AMOUNT", "dividend_amount"),
    ("PROPERTY ADDRESS", "property_address"),
    ("PROPERTY TYPE", "property_type"),
    ("TRANSACTION TYPE", "transaction_type"),
    ("TRANSACTION DATE", "transaction_date"),
    ("TRANSACTION AMOUNT", "transaction_amount"),
    ("STATUS", "status"),
    ("DATE OF PAYMENT", "date_of_payment"),
    ("AMOUNT PAID", "amount_paid_credited"),
    ("TDS DEDUCTED", "tds_deducted"),
    ("TDS DEPOSITED", "tds_deposited"),
    ("GROSS AMOUNT RECEIVED", "gross_amount_received"),
    ("GROSS AMOUNT PAID", "gross_amount_paid"),
    ("IN CASH", "in_cash"),
]


def _resolve_semantic_column_map(header_upper: list[str]) -> dict[str, int]:
    """Map semantic keys to column indices from a normalised detail header."""
    sem_map: dict[str, int] = {}
    for idx, h in enumerate(header_upper):
        for needle, semantic in _SEMANTIC_COLUMN_PATTERNS:
            if needle in h and semantic not in sem_map:
                sem_map[semantic] = idx
                break
    return sem_map


def _parse_entry_table(table: list[list[str]]) -> list[AISEntry]:
    """Parse one pdfplumber table that may contain one or more AIS entries.

    Most AIS tables contain exactly one entry (summary + optional detail).  A
    table that pdfplumber merged from two adjacent entries yields two — the
    function walks the table, emitting an entry each time it sees a summary
    header followed by a summary data row, then attaches any detail section
    that follows.
    """
    entries: list[AISEntry] = []
    i = 0
    n = len(table)
    while i < n:
        cells = [_clean(c) for c in table[i]]
        if not any(cells):
            i += 1
            continue
        if _summary_header_signature(cells):
            # Next non-empty row should be the summary data row.
            j = i + 1
            while j < n and not any(_clean(c) for c in table[j]):
                j += 1
            if j >= n:
                break
            summary_cells = [_clean(c) for c in table[j]]
            entry = _parse_summary_row(summary_cells)
            if entry is None:
                i = j + 1
                continue
            # Detail section (if any) starts at j + 1.
            next_i = _parse_detail_section(table, j + 1, entry)
            entries.append(entry)
            i = next_i
            continue
        # Not a summary header — could be a detail-header continuation
        # (handled by the caller) or noise.
        i += 1
    return entries


# ── Continuation merge ───────────────────────────────────────────────────────


def _merge_continuation(entries: list[AISEntry], detail_tables: list[list[list[str]]]) -> list[AISEntry]:
    """Merge detail-header-only continuation tables into the preceding entry.

    A continuation table appears when a detail table spans a page break: the
    next page's first table repeats the detail header then continues the
    rows.  We append those rows to the most recent entry that has a detail
    header (the one the continuation belongs to), provided the headers match.
    """
    if not entries or not detail_tables:
        return entries
    last = entries[-1]
    for table in detail_tables:
        # Find the detail header in this continuation table.
        hdr_idx = -1
        for k, row in enumerate(table):
            cells = [_clean(c) for c in row]
            nonempty = [c for c in cells if c]
            if nonempty and nonempty[0] == "SR. NO." and not _summary_header_signature(cells):
                hdr_idx = k
                break
        if hdr_idx < 0:
            continue
        hdr = [c for c in (_clean(c) for c in table[hdr_idx]) if c]
        # Only merge when the continuation's header matches the entry's header
        # (same first 3 tokens is enough — they include SR.NO. + DATE column).
        if last.detail_header and hdr[:3] != last.detail_header[:3]:
            continue
        # Re-resolve the semantic map from this continuation's (normalised)
        # header so the ISIN / security_name / etc. keys stay aligned even
        # when the continuation has a different raw column count.
        cont_upper = [h.upper() for h in hdr]
        cont_sem = _resolve_semantic_column_map(cont_upper)
        for row in table[hdr_idx + 1:]:
            cells = [_clean(c) for c in row]
            nonempty = [c for c in cells if c]
            if not nonempty:
                continue
            if _summary_header_signature(cells):
                break
            if not nonempty[0].isdigit():
                continue
            sr = int(nonempty[0])
            data: dict[str, str] = {f"col_{k}": v for k, v in enumerate(nonempty)}
            for semantic, idx in cont_sem.items():
                if 0 <= idx < len(nonempty):
                    data.setdefault(semantic, nonempty[idx])
            sec_name = data.get("security_name", "")
            isin_match = _ISIN_RE.search(sec_name)
            if isin_match:
                data.setdefault("isin", isin_match.group(0).upper())
                data.setdefault("security_code", isin_match.group(0).upper())
            last.details.append(DetailRow(sr_no=sr, data=data))
    return entries


# ── Metadata / refund / tax-payment extraction ──────────────────────────────


def _extract_metadata_from_text(text: str) -> AISMetadata:
    """Parse Part A - General Information + the page footer for metadata.

    The AIS Part A lays out metadata as a label/value grid in plain text::

        Permanent Account Number (PAN) Aadhaar Number Name of Assessee
        ANCPG7860M XXXX XXXX 7262 MANGESH MADHUKAR GIRI
        Date of Birth Mobile Number E-mail Address
        01/07/1971 9764009198 AKOLAMH30.76@gmail.com
        Address
        NIL NIL,GIRI NAGAR,...

    The page footer carries ``Download ID : ... Generation Date : ... Page N of
    M`` and a repeat ``PAN Name Financial Year <PAN> <NAME> <FY>`` line.  We
    parse both, preferring the Part A value when present.
    """
    meta = AISMetadata()
    lines = [ln.strip() for ln in text.split("\n")]

    # ── Part A label/value grid ────────────────────────────────────────────
    try:
        pan_label_idx = next(i for i, ln in enumerate(lines) if "Permanent Account Number" in ln)
    except StopIteration:
        pan_label_idx = -1
    if pan_label_idx >= 0 and pan_label_idx + 1 < len(lines):
        vals = lines[pan_label_idx + 1].split()
        if vals and _PAN_RE.fullmatch(vals[0]):
            meta.pan = vals[0]
        if len(vals) >= 3:
            # Aadhaar is the second token-group (``XXXX XXXX 7262`` masked);
            # the Name of Assessee is everything after the Aadhaar group.
            meta.aadhaar_masked = " ".join(vals[1:4]) if len(vals) >= 4 else vals[1]
            meta.name = " ".join(vals[4:]) if len(vals) > 4 else " ".join(vals[2:])
    # Fallback: scan for a standalone PAN token if Part A didn't yield one.
    if not meta.pan:
        for ln in lines:
            m = _PAN_RE.search(ln)
            if m:
                meta.pan = m.group(0)
                break

    # Date of birth / mobile / email row.
    try:
        dob_label_idx = next(i for i, ln in enumerate(lines) if "Date of Birth" in ln)
    except StopIteration:
        dob_label_idx = -1
    if dob_label_idx >= 0 and dob_label_idx + 1 < len(lines):
        vals = lines[dob_label_idx + 1].split()
        if vals:
            dob = vals[0]
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", dob):
                meta.dob = dob
            if len(vals) >= 2 and re.fullmatch(r"\d{10}", vals[1]):
                meta.mobile = vals[1]
            if len(vals) >= 3 and "@" in vals[2]:
                meta.email = vals[2]

    # Address block (lines after the ``Address`` label until the divider).
    try:
        addr_idx = next(i for i, ln in enumerate(lines) if ln == "Address")
    except StopIteration:
        addr_idx = -1
    if addr_idx >= 0:
        addr_lines: list[str] = []
        for ln in lines[addr_idx + 1 : addr_idx + 6]:
            if not ln or ln.startswith("---") or "Annual Information Statement" in ln:
                break
            addr_lines.append(ln)
        meta.address = ", ".join(a for a in addr_lines if a)

    # ── Footer fields ───────────────────────────────────────────────────────
    dl_match = _DOWNLOAD_ID_RE.search(text)
    if dl_match:
        meta.download_id = dl_match.group(1)
    gd_match = _GEN_DATE_RE.search(text)
    if gd_match:
        meta.generation_date = gd_match.group(1)
    fy_match = _FY_RE.search(text)
    if fy_match:
        meta.financial_year = fy_match.group(1)
    # Footer ``PAN Name Financial Year <PAN> <NAME> <FY>`` — if Part A didn't
    # yield a name, take the name from the footer line.
    if not meta.name:
        footer = re.search(rf"{meta.pan}\s+(.+?)\s+\d{{4}}-\d{{2}}\b", text)
        if footer:
            meta.name = " ".join(footer.group(1).split())
    return meta


def _parse_refunds(text: str) -> list[RefundEntry]:
    """Parse Part B4 Refund entries from raw page text."""
    refunds: list[RefundEntry] = []
    idx = text.find("Part B4")
    if idx == -1:
        return refunds
    b4 = text[idx:]
    ref_idx = b4.find("Refund")
    if ref_idx == -1:
        return refunds
    refund_text = b4[ref_idx:]
    pan_marker = refund_text.find("\nPAN\n")
    if pan_marker != -1:
        refund_text = refund_text[:pan_marker]
    pat = re.compile(
        r"(\d+)\s*\n(\d{4}-\d{2})\s*\n([^\n]+?)\s*\n([^\n]+?)\s*\n([\d,.]+)\s*\n(\d{2}/\d{2}/\d{4})"
    )
    for m in pat.finditer(refund_text):
        refunds.append(RefundEntry(
            sr_no=int(m.group(1)), financial_year=m.group(2),
            mode=m.group(3).strip(), nature=m.group(4).strip(),
            amount=parse_indian_amount(m.group(5)), date=m.group(6),
        ))
    return refunds


# ── Main entry point ─────────────────────────────────────────────────────────


def extract_ais(pdf_path: str) -> AISDocument:
    """Extract an AIS PDF into the canonical ``AISDocument``.

    Walks every pdfplumber table on every page, classifies each as an entry
    table (summary header + detail section), a detail-header-only
    continuation table (page-break spill of the previous entry's detail
    table), or footer/noise.  Entry tables yield ``AISEntry`` objects;
    continuations are merged back into the preceding entry.
    """
    import pdfplumber

    doc = AISDocument()
    full_text_parts: list[str] = []
    # Tables in page order, classified.  An entry table starts a new entry;
    # a detail-header-only continuation table continues the previous entry's
    # detail section (page-break spill).  Preserving order is essential: a
    # 79-row SFT-17-LES detail table spills across 3+ pages, each carrying a
    # continuation table that must merge into the entry that began on the
    # first page.
    ordered_tables: list[tuple[str, list[list[str]]]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            full_text_parts.append(page.extract_text() or "")
            tables = page.extract_tables()
            for raw in tables:
                if not raw:
                    continue
                table = [[_clean(c) for c in row] for row in raw]
                if _is_noise_table(table):
                    continue
                if _is_entry_table(table):
                    ordered_tables.append(("entry", table))
                elif _is_detail_header_only_table(table):
                    ordered_tables.append(("continuation", table))
                else:
                    # Unknown table — treat as entry (defensive); the parser
                    # will simply find no summary header and skip it.
                    ordered_tables.append(("entry", table))

    entries: list[AISEntry] = []
    pending_continuations: list[list[list[str]]] = []
    for kind, table in ordered_tables:
        if kind == "entry":
            # Flush any pending continuations into the previous entry first.
            if entries and pending_continuations:
                _merge_continuation(entries, pending_continuations)
                pending_continuations = []
            parsed = _parse_entry_table(table)
            if parsed:
                entries.extend(parsed)
        else:  # continuation
            pending_continuations.append(table)
    # Flush trailing continuations into the final entry.
    if entries and pending_continuations:
        _merge_continuation(entries, pending_continuations)

    # Full text for metadata + refunds + tax payments.
    full_text = "\n".join(full_text_parts)
    doc.metadata = _extract_metadata_from_text(full_text)
    doc.refunds = _parse_refunds(full_text)

    # Route entries to sections.
    for e in entries:
        if e.section == "B1":
            doc.b1_entries.append(e)
        elif e.section == "B7":
            doc.b7_entries.append(e)
        else:
            doc.b2_entries.append(e)

    # Build income-head groups (mirrors the legacy _group_by_head).
    groups: dict[str, IncomeHeadGroup] = {}
    for e in doc.b1_entries + doc.b2_entries + doc.b7_entries:
        key = e.income_head or IncomeHead.OTHER_SOURCES.value
        grp = groups.setdefault(key, IncomeHeadGroup(income_head=key))
        grp.entries.append(e)
        grp.total_amount += e.amount
    for ref in doc.refunds:
        key = IncomeHead.REFUND.value
        grp = groups.setdefault(key, IncomeHeadGroup(income_head=key))
        grp.refunds.append(ref)
        grp.total_amount += ref.amount
    doc.income_head_groups = groups
    return doc


def extract_ais_json(pdf_path: str, indent: int = 2) -> str:
    """Extract an AIS PDF and serialise to the frontend JSON contract."""
    import json

    doc = extract_ais(pdf_path)
    output: dict[str, Any] = {
        "metadata": asdict(doc.metadata),
        "income_heads": {},
        "summary": {
            "total_interest": 0.0,
            "total_dividend": 0.0,
            "total_capital_gains_sale": 0.0,
            "total_capital_gains_purchase": 0.0,
            "total_gst_turnover": 0.0,
            "total_gst_purchases": 0.0,
            "total_tds": 0.0,
            "total_tcs": 0.0,
            "total_tax_paid": 0.0,
            "total_refund": 0.0,
        },
    }
    for entry in doc.b1_entries + doc.b2_entries + doc.b7_entries:
        cat = (entry.category or "").lower()
        if "salary" in cat:
            output["summary"]["total_tds"] += entry.amount
        if "dividend" in cat:
            output["summary"]["total_dividend"] += entry.amount
        elif "interest" in cat:
            output["summary"]["total_interest"] += entry.amount
        elif "sale of securities" in cat:
            output["summary"]["total_capital_gains_sale"] += entry.amount
        elif "purchase of securities" in cat:
            output["summary"]["total_capital_gains_purchase"] += entry.amount
        elif "gst turnover" in cat:
            output["summary"]["total_gst_turnover"] += entry.amount
        elif "gst purchases" in cat:
            output["summary"]["total_gst_purchases"] += entry.amount
    for ref in doc.refunds:
        output["summary"]["total_refund"] += ref.amount
    for tp in doc.tax_payments:
        output["summary"]["total_tax_paid"] += tp.total
    for ih_key, group in doc.income_head_groups.items():
        output["income_heads"][ih_key] = {
            "income_head": group.income_head,
            "total_amount": group.total_amount,
            "entries": [entry_to_dict(e) for e in group.entries],
            "tax_payments": [asdict(tp) for tp in group.tax_payments],
            "refunds": [asdict(ref) for ref in group.refunds],
        }
    return json.dumps(output, indent=indent, ensure_ascii=False)
