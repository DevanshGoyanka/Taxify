"""
TIS PDF Extractor.

Parses TIS (Taxpayer Information Summary) PDFs using a state machine.

Structure:
  Page 1: Overview table (skip - duplicated in Annexure)
  Pages 2-N (Annexure): Cyclical pattern:
    OVERVIEW_ROW  (SR.NO. \n CATEGORY \n PROCESSED \n ACCEPTED)
    DETAIL_HEADER (SR.NO. \n PART \n INFO \n DESC \n INFO SOURCE \n AMOUNT \n DESC \n REPORTED...)
    DETAIL_ROW_1  (SR \n PART \n DESC... \n SOURCE... \n AMT_DESC... \n AMT1 \n AMT2 \n AMT3)
    DETAIL_ROW_N
    OVERVIEW_ROW  (next category)

The ending of each detail row is always 3 consecutive amount lines.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum as PyEnum
from typing import Any, Optional


# ============================================================
# Income Head Mapping
# ============================================================

SFT_TO_INCOME_HEAD: dict[str, str] = {
    "salary": "Salary",
    "business receipts": "Profits and Gains of Business or Profession",
    "dividend": "Income from Other Sources",
    "interest from savings bank": "Income from Other Sources",
    "interest from deposit": "Income from Other Sources",
    "sale of securities and units of mutual fund": "Capital Gains",
    "sale of land or building": "Capital Gains",
    "purchase of securities and units of mutual funds": "Capital Gains",
    "purchase of immovable property": "Capital Gains",
    "gst turnover": "Profits and Gains of Business or Profession",
    "gst purchases": "Profits and Gains of Business or Profession",
    "purchase of time deposits": "Income from Other Sources",
    "cash deposits": "Income from Other Sources",
    "cash withdrawals": "Income from Other Sources",
    "winnings from online games": "Income from Other Sources",
    "purchase of vehicle": "Income from Other Sources",
    "insurance commission": "Profits and Gains of Business or Profession",
    "receipt of amount by partners from partnership firm": "Profits and Gains of Business or Profession",
}


# ============================================================
# Data Models
# ============================================================

@dataclass
class TISMetadata:
    pan: str = ""
    aadhaar_masked: str = ""
    name: str = ""
    dob: str = ""
    mobile: str = ""
    email: str = ""
    address: str = ""
    financial_year: str = ""
    download_id: str = ""
    generation_date: str = ""


@dataclass
class TISDetailRow:
    sr_no: int = 0
    part: str = ""
    information_description: str = ""
    information_source: str = ""
    institution_pan: str = ""
    amount_description: str = ""
    reported_by_source: str = ""
    processed_by_system: str = ""
    accepted_by_taxpayer: str = ""


@dataclass
class TISEntry:
    sr_no: int = 0
    category: str = ""
    processed_by_system: float = 0.0
    accepted_by_taxpayer: float = 0.0
    income_head: str = ""
    details: list[TISDetailRow] = field(default_factory=list)


@dataclass
class TISSummaryRow:
    """One row from the Page 1 overview table."""
    sr_no: int = 0
    category: str = ""
    processed_by_system: float = 0.0
    accepted_by_taxpayer: float = 0.0


@dataclass
class TISDocument:
    metadata: TISMetadata = field(default_factory=TISMetadata)
    overview: list[TISSummaryRow] = field(default_factory=list)
    entries: list[TISEntry] = field(default_factory=list)
    income_head_groups: dict[str, dict] = field(default_factory=dict)
    reconciliation: dict[str, dict] = field(default_factory=dict)


# ============================================================
# Utilities
# ============================================================

_AMOUNT_RE = re.compile(r'^[\d,]+(?:\.\d{2})?$|^-$')
_PAN_RE = re.compile(r'([A-Z]{5}[0-9]{4}[A-Z])')
_CODE_RE = re.compile(r'\([A-Z]{4,10}[0-9]{2,5}[A-Z]?')


def parse_indian_amount(val: str) -> float:
    if not val or val.strip() in ("", "-", "--"):
        return 0.0
    s = re.sub(r'[₹\s]', '', str(val)).strip()
    is_negative = s.startswith('(') and s.endswith(')')
    s = s.strip('()').replace(',', '')
    try:
        v = float(s)
        return -v if is_negative else v
    except ValueError:
        return 0.0


def extract_pan(source: str) -> str:
    m = _PAN_RE.search(source)
    return m.group(1) if m else ""


def map_category(cat: str) -> str:
    cat_lower = cat.lower().strip()
    for key, head in SFT_TO_INCOME_HEAD.items():
        if key in cat_lower:
            return head
    return "Income from Other Sources"


# ============================================================
# Footer Detection
# ============================================================

_FOOTER_TOKENS = {
    "PAN", "Name", "Financial Year", "Download ID",
    "Page ", "IP Address", "Generation Date",
}


def _is_footer_line(line: str) -> bool:
    """Check if a line is part of the page footer."""
    s = line.strip()
    if not s:
        return False
    for kw in _FOOTER_TOKENS:
        if kw in s and ':' not in s:
            # "PAN" as a standalone line, not "Download ID :"
            if kw in ("PAN", "Name", "Financial Year"):
                return True
        if s.startswith(kw):
            return True
    # Footer data lines: PAN number, full name, FY value
    if re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', s):
        return True
    if re.match(r'^\d{4}-\d{2}$', s):
        return True
    return False


def _skip_footer_block(lines: list[str], i: int) -> int:
    """Skip past a footer block (PAN/Name/FY/DownloadID/etc.)"""
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            return i + 1
        if _is_footer_line(line):
            i += 1
        else:
            return i
    return i


# ============================================================
# Detail Row Parser: Find 3 trailing amounts
# ============================================================

AMT_DESC_PATTERNS = [
    "interest",
    "dividend",
    "amount paid/credited",
    "amount paid/ credited",
    "amount received/debited",
    "amount received/ debited",
    "total turnover",
    "taxable turnover",
    "value of consideration",
    "transaction amount",
    "purchase from supplier",
    "purchase from supplier",
    "cash deposit",
    "cash withdrawal",
    "salary",
    "commission",
    "total purchase amount",
    "total sales value",
    "receipt from partnership",
    "purchase from",
    "amount paid/",
    "credited",
]


def _parse_detail_row(lines: list[str], i: int) -> tuple[Optional[TISDetailRow], int]:
    """Parse one detail row by finding 3 trailing amount values first."""
    if i >= len(lines):
        return None, i

    first = lines[i].strip()
    if not first.isdigit():
        return None, i
    sr = int(first)

    # Scan forward to find 3 consecutive amounts
    search = i + 1
    candidates: list[int] = []
    while search < len(lines):
        line = lines[search].strip()
        if not line:
            search += 1
            continue
        if _AMOUNT_RE.match(line):
            candidates.append(search)
            if len(candidates) == 3:
                break
        else:
            # Only reset if we haven't found 3 yet AND this line couldn't be part of a detail row field
            candidates = []
        search += 1

    if len(candidates) < 3:
        return None, i

    reported = lines[candidates[0]].strip()
    processed = lines[candidates[1]].strip()
    accepted = lines[candidates[2]].strip()
    row_end = candidates[2] + 1

    # Collect all tokens between SR digit and first amount
    tokens: list[str] = []
    for j in range(i + 1, candidates[0]):
        t = lines[j].strip()
        if t:
            tokens.append(t)

    if len(tokens) < 2:
        return None, i

    # Parse PART
    part = tokens[0]
    if part in ("TDS/", "TDS") and len(tokens) > 1 and tokens[1] == "TCS":
        part = "TDS/TCS"
        tokens.pop(0)
    tokens.pop(0)

    if part not in ("SFT", "TDS/TCS", "Other"):
        return None, i

    # Now tokens = [desc..., source..., amt_desc...]
    # Find amount description: look for the 1-2 tokens before the amounts that match known pattern
    # Strategy: The last 1-2 tokens of `tokens` that are NOT an institution source are the amt_desc.

    # First, identify institution source START: first token that is
    # either all-uppercase institution name or ends with (CODE/PAN)
    source_start_idx = len(tokens)
    for idx in range(len(tokens)):
        # A source line typically:
        # - is all caps (e.g., "STATE BANK OF INDIA")
        # - or contains a (PAN/CODE) pattern
        # - is NOT an SFT code like (SFT-016)
        t = tokens[idx]
        if t.startswith('(SFT') or t.startswith('(EXC'):
            continue
        if '(' in t and (_PAN_RE.search(t) or re.search(r'\([A-Z]{4,10}[0-9]{2,5}', t)):
            # This is either a standalone (PAN) line or "NAME (PAN)" combined
            source_start_idx = min(source_start_idx, idx)
            continue
        if t.isupper() and len(t) > 3 and not t.isdigit():
            source_start_idx = min(source_start_idx, idx)
            continue

    if source_start_idx > len(tokens):
        # No source found in tokens; try reverse search
        for idx in range(len(tokens) - 1, -1, -1):
            if '(' in tokens[idx] and not tokens[idx].startswith('(SFT') and not tokens[idx].startswith('(EXC'):
                source_start_idx = idx
                break

    if source_start_idx >= len(tokens):
        source_start_idx = max(0, len(tokens) - 2)

    desc_tokens = tokens[:source_start_idx]
    remaining = tokens[source_start_idx:]

    # Split remaining into source and amt_desc
    # Source is at the beginning, amt_desc at the end (1-2 tokens)
    if len(remaining) <= 2:
        source_tokens = []
        amt_desc_tokens = remaining
    else:
        # Source ends with the line containing (CODE/PAN)
        source_end_in_remaining = len(remaining)
        for idx in range(len(remaining) - 1, -1, -1):
            if _CODE_RE.search(remaining[idx]) or _PAN_RE.search(remaining[idx]):
                source_end_in_remaining = idx + 1
                break
        source_tokens = remaining[:source_end_in_remaining]
        amt_desc_tokens = remaining[source_end_in_remaining:]

    desc = ' '.join(desc_tokens).strip()
    source = ' '.join(source_tokens).strip()
    amt_desc = ' '.join(amt_desc_tokens).strip()

    row = TISDetailRow(
        sr_no=sr,
        part=part,
        information_description=desc[:300],
        information_source=source[:300],
        institution_pan=extract_pan(source),
        amount_description=amt_desc[:100],
        reported_by_source=reported,
        processed_by_system=processed,
        accepted_by_taxpayer=accepted,
    )
    return row, row_end


# ============================================================
# State Machine Parser (Annexure only)
# ============================================================

class State(PyEnum):
    IDLE = "idle"
    OVERVIEW_HEADER = "overview_header"
    OVERVIEW_DATA = "overview_data"
    DETAIL_HEADER = "detail_header"
    DETAIL_DATA = "detail_data"


def _is_overview_header(lines: list[str], i: int) -> bool:
    return (i + 4 < len(lines) and
            lines[i].strip() == "SR. NO." and
            lines[i + 1].strip() == "INFORMATION CATEGORY")


def _is_detail_header(lines: list[str], i: int) -> bool:
    return (i + 3 < len(lines) and
            lines[i].strip() == "SR. NO." and
            lines[i + 1].strip() == "PART")


def _skip_header_tokens(lines: list[str], i: int) -> int:
    """Skip all header tokens at position i."""
    while i < len(lines):
        line = lines[i].strip()
        if line in (
            "SR. NO.", "INFORMATION CATEGORY", "PROCESSED BY", "SYSTEM",
            "ACCEPTED BY", "TAXPAYER/", "CONFIRMED BY", "SOURCE",
            "PART", "INFORMATION", "DESCRIPTION", "INFORMATION SOURCE",
            "AMOUNT", "DESCRIPTION", "REPORTED", "BY SOURCE",
            "REPORTED BY", "PROCESSED", "BY SYSTEM",
            "ACCEPTED BY", "TAXPAYER/", "CONFIRMED BY", "SOURCE",
            "TAXPAYER/ CONFIRMED",
        ):
            i += 1
        else:
            break
    return i


def _read_overview_row(lines: list[str], i: int) -> tuple[Optional[TISEntry], int]:
    """Read: SR (digit) \n CATEGORY \n PROCESSED \n ACCEPTED"""
    if i + 3 >= len(lines):
        return None, i
    sr_line = lines[i].strip()
    if not sr_line.isdigit():
        return None, i
    sr = int(sr_line)
    category = lines[i + 1].strip()
    proc = parse_indian_amount(lines[i + 2])
    acc = parse_indian_amount(lines[i + 3])
    entry = TISEntry(
        sr_no=sr, category=category,
        processed_by_system=proc, accepted_by_taxpayer=acc,
    )
    return entry, i + 4


# ============================================================
# Page 1 Overview Parser
# ============================================================

def parse_tis_overview(text: str) -> list[TISSummaryRow]:
    """Parse the Page 1 overview table.

    Structure: SR. NO. | INFO CATEGORY | PROCESSED BY SYSTEM | ACCEPTED BY ...
    """
    rows: list[TISSummaryRow] = []
    lines = text.split('\n')

    # Find the overview header
    hdr_idx = None
    for i in range(len(lines)):
        if lines[i].strip() == "SR. NO." and i + 1 < len(lines) and lines[i + 1].strip() == "INFORMATION CATEGORY":
            hdr_idx = i
            break

    if hdr_idx is None:
        return rows

    # Skip header tokens
    i = hdr_idx + 1
    while i < len(lines) and lines[i].strip() in (
        "INFORMATION CATEGORY", "PROCESSED BY", "SYSTEM",
        "ACCEPTED BY", "TAXPAYER/", "CONFIRMED BY", "SOURCE",
    ):
        i += 1

    # Read data rows: SR | CATEGORY | PROCESSED | ACCEPTED
    while i + 3 < len(lines):
        sr_line = lines[i].strip()
        if not sr_line.isdigit():
            break
        sr = int(sr_line)
        category = lines[i + 1].strip()
        proc = parse_indian_amount(lines[i + 2])
        acc = parse_indian_amount(lines[i + 3])
        rows.append(TISSummaryRow(
            sr_no=sr, category=category,
            processed_by_system=proc, accepted_by_taxpayer=acc,
        ))
        i += 4

    return rows


# ============================================================
# Reconciliation
# ============================================================

def reconcile(overview: list[TISSummaryRow], entries: list[TISEntry]) -> dict[str, dict]:
    """Compare Page 1 overview totals against computed detail sums for each category."""
    result: dict[str, dict] = {}

    for ov in overview:
        cat = ov.category
        # Find matching annexure entry
        matching_entry = None
        for e in entries:
            if e.category.lower() == cat.lower() and e.sr_no == ov.sr_no:
                matching_entry = e
                break

        # Sum detail amounts
        detail_reported = sum(parse_indian_amount(d.reported_by_source) for d in matching_entry.details) if matching_entry else 0.0
        detail_processed = sum(parse_indian_amount(d.processed_by_system) for d in matching_entry.details) if matching_entry else 0.0
        detail_accepted = sum(parse_indian_amount(d.accepted_by_taxpayer) for d in matching_entry.details) if matching_entry else 0.0

        proc_match = abs(ov.processed_by_system - detail_processed) < 0.01
        acc_match = abs(ov.accepted_by_taxpayer - detail_accepted) < 0.01

        result[cat] = {
            "sr_no": ov.sr_no,
            "overview_processed": ov.processed_by_system,
            "overview_accepted": ov.accepted_by_taxpayer,
            "detail_sum_reported": detail_reported,
            "detail_sum_processed": detail_processed,
            "detail_sum_accepted": detail_accepted,
            "processed_matches": proc_match,
            "accepted_matches": acc_match,
            "detail_count": len(matching_entry.details) if matching_entry else 0,
        }

    return result


def parse_tis_annexure(text: str) -> list[TISEntry]:
    """Parse only the Annexure portion of TIS text."""
    lines = text.split('\n')
    entries: list[TISEntry] = []
    state = State.IDLE
    current: Optional[TISEntry] = None
    i = 0

    def _finalize():
        nonlocal current
        if current:
            current.income_head = map_category(current.category)
            entries.append(current)
        current = None

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        # Skip footers
        if _is_footer_line(line):
            i = _skip_footer_block(lines, i)
            continue

        # Skip noise
        if line.startswith("---") or "(All amount" in line:
            i += 1
            continue
        if "Annexure" in line or "Disclaimer" in line:
            i += 1
            continue
        if line in ("Reported by Source -", "Processed by System -",
                     "Accepted by Taxpayer/"):
            i += 1
            continue

        # ============================================================
        # State: IDLE - find first overview header
        # ============================================================
        if state == State.IDLE:
            if _is_overview_header(lines, i):
                state = State.OVERVIEW_HEADER
                i = _skip_header_tokens(lines, i)
                continue
            i += 1
            continue

        # ============================================================
        # State: OVERVIEW_HEADER
        # ============================================================
        if state == State.OVERVIEW_HEADER:
            entry, i = _read_overview_row(lines, i)
            if entry:
                _finalize()
                current = entry
                state = State.OVERVIEW_DATA
                continue
            i += 1
            continue

        # ============================================================
        # State: OVERVIEW_DATA
        # ============================================================
        if state == State.OVERVIEW_DATA:
            if _is_overview_header(lines, i):
                _finalize()
                state = State.OVERVIEW_HEADER
                i = _skip_header_tokens(lines, i)
                continue

            if _is_detail_header(lines, i):
                state = State.DETAIL_HEADER
                i = _skip_header_tokens(lines, i)
                continue

            # Could be a numeric overview row without the header
            if line.isdigit() and current:
                new_entry, new_i = _read_overview_row(lines, i)
                if new_entry and new_i > i:
                    _finalize()
                    current = new_entry
                    state = State.OVERVIEW_DATA
                    i = new_i
                    continue

            i += 1
            continue

        # ============================================================
        # State: DETAIL_HEADER
        # ============================================================
        if state == State.DETAIL_HEADER:
            i = _skip_header_tokens(lines, i)
            state = State.DETAIL_DATA
            continue

        # ============================================================
        # State: DETAIL_DATA
        # ============================================================
        if state == State.DETAIL_DATA:
            if _is_overview_header(lines, i):
                _finalize()
                state = State.OVERVIEW_HEADER
                i = _skip_header_tokens(lines, i)
                continue

            if _is_detail_header(lines, i):
                state = State.DETAIL_HEADER
                i = _skip_header_tokens(lines, i)
                continue

            if _is_footer_line(line):
                i = _skip_footer_block(lines, i)
                continue

            # Try to parse a detail row
            detail_row, new_i = _parse_detail_row(lines, i)
            if detail_row:
                if current:
                    current.details.append(detail_row)
                i = new_i
                continue

            # Could be a new overview row (no header between categories)
            if line.isdigit() and current:
                new_entry, new_i = _read_overview_row(lines, i)
                if new_entry and new_i > i:
                    _finalize()
                    current = new_entry
                    state = State.OVERVIEW_DATA
                    i = new_i
                    continue

            i += 1
            continue

        i += 1

    _finalize()
    return entries


# ============================================================
# TIS Extractor
# ============================================================

class TISExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract(self) -> TISDocument:
        import fitz
        result = TISDocument()

        pdf = fitz.open(self.pdf_path)
        full_text = ""
        try:
            for page in pdf:
                full_text += page.get_text()
        finally:
            pdf.close()

        result.metadata = _extract_metadata(full_text)

        # Extract Page 1 overview (before the Annexure section)
        page1_end = full_text.find("The information details under each")
        if page1_end == -1:
            page1_end = full_text.find("Annexure")
        page1_text = full_text[:page1_end] if page1_end != -1 else full_text
        result.overview = parse_tis_overview(page1_text)

        # Extract Annexure detail entries
        annexure_idx = full_text.find("Annexure")
        if annexure_idx != -1:
            result.entries = parse_tis_annexure(full_text[annexure_idx:])
        else:
            result.entries = parse_tis_annexure(full_text)

        # Reconcile overview vs detail sums
        result.reconciliation = reconcile(result.overview, result.entries)

        result.income_head_groups = _group_by_head(result)
        return result


def _extract_metadata(text: str) -> TISMetadata:
    meta = TISMetadata()
    lines = text.split('\n')
    gi_start = next((i for i, l in enumerate(lines) if 'General Information' in l), 0)

    try:
        if gi_start + 4 < len(lines):
            meta.pan = lines[gi_start + 4].strip()
        if gi_start + 5 < len(lines):
            meta.aadhaar_masked = lines[gi_start + 5].strip()
        if gi_start + 6 < len(lines):
            meta.name = lines[gi_start + 6].strip()
        if gi_start + 10 < len(lines):
            meta.dob = lines[gi_start + 10].strip()
        if gi_start + 11 < len(lines):
            meta.mobile = lines[gi_start + 11].strip()
        if gi_start + 12 < len(lines):
            meta.email = lines[gi_start + 12].strip()
        if gi_start + 14 < len(lines):
            addr_lines = []
            for j in range(gi_start + 14, min(gi_start + 25, len(lines))):
                if lines[j].startswith('---') or 'Taxpayer Information Summary' in lines[j]:
                    break
                addr_lines.append(lines[j].strip())
            meta.address = ', '.join(a for a in addr_lines if a)
    except IndexError:
        pass

    if not meta.pan:
        m = re.search(r'([A-Z]{5}[0-9]{4}[A-Z])\n', text)
        if m:
            meta.pan = m.group(1)

    fy_match = re.search(r'Financial Year\s*\n\s*(\d{4}-\d{2})', text)
    if fy_match:
        meta.financial_year = fy_match.group(1)

    dl_match = re.search(r'Download ID\s*:\s*(\S+)', text)
    if dl_match:
        meta.download_id = dl_match.group(1)

    gd_match = re.search(r'Generation Date\s*:\s*([^\n]+)', text)
    if gd_match:
        meta.generation_date = gd_match.group(1).strip()

    return meta


def _group_by_head(doc: TISDocument) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for entry in doc.entries:
        ih = map_category(entry.category)
        if ih not in groups:
            groups[ih] = {
                "income_head": ih,
                "total_processed": 0.0,
                "total_accepted": 0.0,
                "entries": [],
            }
        groups[ih]["total_processed"] += entry.processed_by_system
        groups[ih]["total_accepted"] += entry.accepted_by_taxpayer
        groups[ih]["entries"].append(entry_to_dict(entry))
    return groups


# ============================================================
# JSON Export
# ============================================================

def detail_to_dict(d: TISDetailRow) -> dict:
    return asdict(d)


def entry_to_dict(e: TISEntry) -> dict:
    return {
        "sr_no": e.sr_no,
        "category": e.category,
        "processed_by_system": e.processed_by_system,
        "accepted_by_taxpayer": e.accepted_by_taxpayer,
        "income_head": e.income_head,
        "details": [detail_to_dict(d) for d in e.details],
    }


def tis_to_frontend_json(doc: TISDocument, indent: int = 2) -> str:
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


def extract_tis(pdf_path: str) -> TISDocument:
    return TISExtractor(pdf_path).extract()
