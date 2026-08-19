"""
AIS PDF Extractor v2 - State Machine Architecture.

Parses AIS PDFs line-by-line using a state machine that respects
the Summary->Detail parent-child pairing inherent in AIS documents.

Structure for each category within B1/B2/B7:
    CATEGORY_NAME
    SUMMARY_HEADER (SR.NO. | INFO CODE | INFO DESC | INFO SOURCE | COUNT | AMOUNT)
    SUMMARY_DATA_ROW  (SR | CODE | DESC | SOURCE | COUNT | AMOUNT)
    DETAIL_HEADER     (SR.NO. | category-specific columns)
    DETAIL_DATA_ROW_1
    ...
    DETAIL_DATA_ROW_N
    SUMMARY_HEADER    (next pair starts)
    ...

Produces JSON with properly nested detail arrays under each summary entry.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


# ============================================================
# Income Head Mapping
# ============================================================

class IncomeHead(str, Enum):
    SALARY = "Salary"
    HOUSE_PROPERTY = "Income from House Property"
    BUSINESS_PROFESSION = "Profits and Gains of Business or Profession"
    CAPITAL_GAINS = "Capital Gains"
    OTHER_SOURCES = "Income from Other Sources"
    TDS = "Tax Deducted at Source"
    TCS = "Tax Collected at Source"
    REFUND = "Refund"
    TAX_PAID = "Taxes Paid"


SFT_CATEGORIES = [
    "sale of securities and units of mutual fund",
    "purchase of securities and units of mutual funds",
    "purchase of immovable property",
    "purchase of time deposits",
    "interest from savings bank",
    "interest from deposit",
    "sale of land or building",
    "cash withdrawals",
    "cash deposits",
    "gst purchases",
    "gst turnover",
    "dividend",
]

SFT_TO_INCOME_HEAD: dict[str, IncomeHead] = {
    "salary": IncomeHead.SALARY,
    "business receipts": IncomeHead.BUSINESS_PROFESSION,
    "dividend": IncomeHead.OTHER_SOURCES,
    "interest from savings bank": IncomeHead.OTHER_SOURCES,
    "interest from deposit": IncomeHead.OTHER_SOURCES,
    "sale of securities and units of mutual fund": IncomeHead.CAPITAL_GAINS,
    "sale of land or building": IncomeHead.CAPITAL_GAINS,
    "purchase of securities and units of mutual funds": IncomeHead.CAPITAL_GAINS,
    "purchase of immovable property": IncomeHead.CAPITAL_GAINS,
    # Virtual Digital Asset transfers are capital-gains transactions
    # (Schedule VDA in ITR-2/3), not Other Sources.
    "receipts on transfer of virtual digital asset": IncomeHead.CAPITAL_GAINS,
    "gst turnover": IncomeHead.BUSINESS_PROFESSION,
    "gst purchases": IncomeHead.BUSINESS_PROFESSION,
    # Commission / insurance commission / partner receipts are business
    # income (PGBP), not Other Sources.
    "commission income": IncomeHead.BUSINESS_PROFESSION,
    "insurance commission": IncomeHead.BUSINESS_PROFESSION,
    "receipt from partnership firm": IncomeHead.BUSINESS_PROFESSION,
    "professional fees": IncomeHead.BUSINESS_PROFESSION,
    "purchase of time deposits": IncomeHead.OTHER_SOURCES,
    "cash deposits": IncomeHead.OTHER_SOURCES,
    "cash withdrawals": IncomeHead.OTHER_SOURCES,
    "winnings from online games": IncomeHead.OTHER_SOURCES,
    "purchase of vehicle": IncomeHead.OTHER_SOURCES,
}

B1_CATEGORIES = [
    "salary",
    "business receipts",
    "commission or brokerage",
    "professional fees",
    "rent",
    "interest",
    "dividend",
    "winnings",
    "contract",
]


# ============================================================
# Data Models
# ============================================================

@dataclass
class AISMetadata:
    pan: str = ""
    aadhaar_masked: str = ""
    name: str = ""
    dob: str = ""
    mobile: str = ""
    email: str = ""
    address: str = ""
    financial_year: str = ""
    assessment_year: str = ""
    download_id: str = ""
    generation_date: str = ""


@dataclass
class DetailRow:
    """A single detail row from a summary's detail table."""
    sr_no: int = 0
    data: dict[str, str] = field(default_factory=dict)


@dataclass
class AISEntry:
    """A complete Summary + Detail pair entry."""
    sr_no: int = 0
    information_code: str = ""
    information_description: str = ""
    information_source: str = ""
    institution_pan: str = ""
    count: int = 0
    amount: float = 0.0
    category: str = ""
    section: str = ""  # "B1", "B2", or "B7"
    income_head: str = ""
    detail_header: list[str] = field(default_factory=list)
    details: list[DetailRow] = field(default_factory=list)


@dataclass
class RefundEntry:
    sr_no: int = 0
    financial_year: str = ""
    mode: str = ""
    nature: str = ""
    amount: float = 0.0
    date: str = ""


@dataclass
class TaxPaymentEntry:
    sr_no: int = 0
    financial_year: str = ""
    major_head: str = ""
    minor_head: str = ""
    tax: float = 0.0
    surcharge: float = 0.0
    cess: float = 0.0
    others: float = 0.0
    total: float = 0.0
    bsr_code: str = ""
    deposit_date: str = ""
    challan_serial: str = ""
    cin: str = ""


@dataclass
class IncomeHeadGroup:
    income_head: str
    entries: list[AISEntry] = field(default_factory=list)
    refunds: list[RefundEntry] = field(default_factory=list)
    tax_payments: list[TaxPaymentEntry] = field(default_factory=list)
    total_amount: float = 0.0


@dataclass
class AISDocument:
    metadata: AISMetadata = field(default_factory=AISMetadata)
    b1_entries: list[AISEntry] = field(default_factory=list)
    b2_entries: list[AISEntry] = field(default_factory=list)
    b7_entries: list[AISEntry] = field(default_factory=list)
    tax_payments: list[TaxPaymentEntry] = field(default_factory=list)
    refunds: list[RefundEntry] = field(default_factory=list)
    income_head_groups: dict[str, IncomeHeadGroup] = field(default_factory=dict)


# ============================================================
# Utility Functions
# ============================================================

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
    m = re.search(r'([A-Z]{5}[0-9]{4}[A-Z])', source)
    return m.group(1) if m else ""


def map_to_head(category: str, section: str = "B2") -> str:
    """Map an AIS entry's category+section to its CBDT income head.

    CBDT placement rules (ITR schedules + AIS Part B1/B2/B7 design):

    * **Salary** (TDS-192/192A in Part B1, ``category == "salary"``) →
      Income from Salary.
    * **Dividend** (SFT-015 in B2, TDS-194/194K/194D in B1) → Income from
      Other Sources — dividend is chargeable u/s 56(2)(i)/(ii) under OS, not
      PGBP.  A dealer-in-securities may report trading dividends under PGBP,
      but that is the taxpayer's elective reclassification at return-filing
      time; the AIS faithfully reports dividend under OS by default.
    * **Interest** (SFT-016 savings/term-deposit in B2, TDS-193/194A in B1)
      → Income from Other Sources.
    * Listed-equity / MF security sales (SFT-17/18) → Capital Gains.
    * Immovable property (SFT-012 sale / SFT-003 purchase) → Capital Gains.
    * GST turnover / GST purchases → Profits and Gains of Business or
      Profession.

    Previously every non-salary Part B1 TDS entry was force-routed to PGBP,
    which misclassified TDS-194 (dividend) and TDS-194A (interest) credits
    as business income — contrary to CBDT.  B1 now routes by the same
    category map as B2, falling back to OS (the residual head for income
    with no more-specific match), with only ``salary`` explicitly routed
    to Salary.
    """
    cat = category.lower().strip()
    if section == "B1":
        if "salary" in cat:
            return IncomeHead.SALARY.value
        # Route by underlying income nature (dividend/interest/etc.) — the
        # AIS category on a B1 TDS entry describes what the tax was deducted
        # on, which determines the income head for return filing.
        for key, head in SFT_TO_INCOME_HEAD.items():
            if key in cat:
                return head.value
        # GST turnover / purchases and business receipts stay PGBP.
        if "gst" in cat or "business" in cat or "receipts" in cat:
            return IncomeHead.BUSINESS_PROFESSION.value
        # Anything else in B1 (e.g. commission, professional fees, rent,
        # winnings, contract) is reported under Other Sources unless the
        # taxpayer elects PGBP — OS is the CBDT residual head.
        return IncomeHead.OTHER_SOURCES.value
    for key, head in SFT_TO_INCOME_HEAD.items():
        if key in cat:
            return head.value
    return IncomeHead.OTHER_SOURCES.value


# ============================================================
# SUMMARY_HEADER signature for detection
# ============================================================

# The standard summary header is exactly these 7 tokens on consecutive lines
SUMMARY_HEADER_SIG = [
    "SR. NO.",
    "INFORMATION CODE",
    "INFORMATION DESCRIPTION",
    "INFORMATION SOURCE",
    "COUNT",
    "AMOUNT",
]


def is_summary_header(lines: list[str], start_idx: int) -> bool:
    """Check if lines starting at start_idx match the summary header signature."""
    if start_idx + len(SUMMARY_HEADER_SIG) >= len(lines):
        return False
    return all(
        lines[start_idx + i].strip() == SUMMARY_HEADER_SIG[i]
        for i in range(len(SUMMARY_HEADER_SIG))
    )


def is_detail_header_start(lines: list[str], start_idx: int) -> bool:
    """Check if line is SR. NO. but NOT followed by INFORMATION CODE (i.e., it's a detail header)."""
    if start_idx >= len(lines):
        return False
    if lines[start_idx].strip() != "SR. NO.":
        return False
    if start_idx + 1 >= len(lines):
        return False
    return lines[start_idx + 1].strip() != "INFORMATION CODE"


def is_category_line(line: str) -> Optional[str]:
    """Check if a line is a known category name. Returns the category or None."""
    stripped = line.strip().lower()
    if not stripped:
        return None
    # Skip lines that are clearly not categories
    if stripped.startswith("part b") or stripped.startswith("---"):
        return None
    if any(kw in stripped for kw in ["no transactions present", "note -", "sft-", "sr."]):
        return None
    # Check against known categories (longest first)
    all_cats = SFT_CATEGORIES + B1_CATEGORIES
    all_cats.sort(key=len, reverse=True)
    for cat in all_cats:
        if cat in stripped:
            return cat
    return None


# ============================================================
# Line-by-Line State Machine Parser
# ============================================================

from enum import Enum as PyEnum


class State(PyEnum):
    IDLE = "idle"
    CATEGORY = "category"
    SUMMARY_HEADER = "summary_header"
    SUMMARY_DATA = "summary_data"
    DETAIL_HEADER = "detail_header"
    DETAIL_DATA = "detail_data"
    NOTE = "note"


def _parse_summary_data(lines: list[str], idx: int) -> tuple[AISEntry, int]:
    """Parse a summary data block starting at idx (at the SR number line).

    Format is always:
        SR_NO          (digit)
        INFO_CODE      (TDS-XXX, SFT-XXX, EXC-XXX)
        INFO_DESC      (may span 1+ lines)
        INFO_SOURCE    (may span 1+ lines, ends with (PAN) or similar)
        COUNT          (digit, last 1-2 lines before amount)
        AMOUNT         (digit/comma)

    Returns (entry, next_index).
    """
    sr = int(lines[idx].strip())
    code = lines[idx + 1].strip()
    i = idx + 2

    # Read description: lines until we hit something that looks like source
    desc_lines = []
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        # Source lines contain (PAN) pattern or institution names ending with (
        if '(' in line and (re.search(r'\([A-Z]{5}[0-9]{4}[A-Z]', line) or
                            re.search(r'\([A-Z]{4}[0-9]', line)):
            break
        # Source lines start with capital letters and are institution-like
        # But description continuation lines also might. We check if we've seen enough.
        desc_lines.append(line)
        i += 1

    # Read source: lines until we find a line that's a count (looks like a 1-2 digit number
    # or a number with commas, but not a date)
    source_lines = []
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        # Check if this line is the COUNT (a pure number)
        if re.match(r'^\d{1,3}$', line):
            break
        # Check if this could be an amount (number with commas and at most 2 decimal places)
        if re.match(r'^[\d,]+(?:\.\d{2})?$', line):
            # Could be count or amount. If previous line was a source, this is count
            break
        source_lines.append(line)
        i += 1

    # Read count and amount
    count = 0
    amount = 0.0
    count_read = False
    while i < len(lines) and not count_read:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if re.match(r'^\d{1,3}$', line):
            count = int(line)
            count_read = True
        i += 1

    # Amount is the next numeric line after count
    amount_found = False
    while i < len(lines) and not amount_found:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if re.match(r'^[\d,]+(?:\.\d{2})?$', line):
            amount = parse_indian_amount(line)
            amount_found = True
        i += 1

    desc = ' '.join(desc_lines).strip()
    source = ' '.join(source_lines).strip()

    entry = AISEntry(
        sr_no=sr,
        information_code=code,
        information_description=desc,
        information_source=source,
        institution_pan=extract_pan(source),
        count=count,
        amount=amount,
    )
    return entry, i


def _read_detail_header(lines: list[str], idx: int) -> tuple[list[str], int]:
    """Read detail header tokens starting at idx (SR. NO. line).
    Returns (header_tokens, next_index).
    """
    tokens: list[str] = []
    i = idx
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        # Stop at first numeric line (data row) or at a summary header signature
        if line.isdigit():
            break
        if line == "SR. NO." and i > idx:
            break
        # Check if next lines would form a summary header
        if is_summary_header(lines, i):
            break
        tokens.append(line)
        i += 1

    # PyMuPDF splits multi-word column header phrases (``REPORTED ON``,
    # ``PROPERTY ADDRESS``, ``TRANSACTION AMOUNT``, ``VALUE OF PROPERTY FOR
    # STAMP DUTY``) across separate lines, inflating the token count past the
    # true column count and causing ``collect_row_tokens`` to overshoot each
    # data row into the next entry.  Merge consecutive tokens back into their
    # canonical single-token column names (longest phrases first).
    return _merge_multi_word_header_tokens(tokens), i


# Multi-word AIS detail-header column phrases, ordered longest-first so that
# ``VALUE OF PROPERTY FOR STAMP DUTY`` is merged as one token before any of
# its sub-phrases (``STAMP DUTY``, ``PROPERTY``) are considered.
_MULTI_WORD_HEADER_PHRASES: list[str] = [
    "VALUE OF PROPERTY FOR STAMP DUTY",
    "TRANSACTION AMOUNT ASSIGNED",
    "TRANSACTION AMOUNT",
    "TRANSACTION DATE",
    "TRANSACTION TYPE",
    "GROSS AMOUNT RECEIVED FROM THE PERSON",
    "GROSS AMOUNT PAID TO THE PERSON",
    "GROSS AMOUNT",
    "COST OF ACQUISITION",
    "INDEXED COST OF ACQUISITION",
    "SALE PRICE PER UNIT",
    "SALES CONSIDERATION",
    "FAIR MARKET VALUE",
    "UNIT FMV",
    "DATE OF SALE/TRANSFER",
    "DATE OF PURCHASE",
    "REPORTED ON",
    "PROPERTY ADDRESS",
    "PROPERTY TYPE",
    "SECURITY NAME (SECURITY CODE)",
    "SECURITY NAME",
    "SECURITY CLASS",
    "DEBIT TYPE",
    "CREDIT TYPE",
    "ASSET TYPE",
    "AMC NAME (CODE)",
    "HOLDER FLAG",
    "PARTY COUNT",
    "STAMP DUTY",
    "DEPOSIT DATE",
    "DATE OF DEPOSIT",
    "ACCOUNT TYPE",
    "ACCOUNT NUMBER",
    "DIVIDEND AMOUNT",
    "INTEREST AMOUNT",
    "BSR CODE",
    "CHALLAN SERIAL NUMBER",
    "CHALLAN IDENTIFICATION NUMBER",
    "MAJOR HEAD",
    "MINOR HEAD",
    "MODE",
    "NATURE OF REFUND",
    "REFUND AMOUNT",
    "DATE OF PAYMENT",
    "FINANCIAL YEAR",
    "TAX (A)",
    "SURCHARGE (B)",
    "EDUCATION CESS (C)",
    "OTHERS (D)",
    "TOTAL (A+B+C+D)",
    "MARKET PURCHASE",
    "MARKET SALES",
    "TOTAL PURCHASE AMOUNT",
    "TOTAL SALES VALUE",
    "CLIENT ID",
    "QUARTER",
    "STATUS",
]


def _merge_multi_word_header_tokens(tokens: list[str]) -> list[str]:
    """Merge consecutive detail-header tokens that form known multi-word column phrases.

    Scans the token list and, wherever a run of consecutive tokens (joined
    with a single space) matches a known phrase, collapses the run into a
    single token.  Phrases are matched longest-first so a long phrase like
    ``VALUE OF PROPERTY FOR STAMP DUTY`` is merged before its sub-phrases.
    """
    if not tokens:
        return tokens
    result: list[str] = []
    i = 0
    while i < len(tokens):
        merged: str | None = None
        consumed = 0
        # Try the longest possible phrase starting at i (cap at 8 tokens).
        max_run = min(8, len(tokens) - i)
        for run_len in range(max_run, 1, -1):
            candidate = " ".join(tokens[i : i + run_len]).upper()
            for phrase in _MULTI_WORD_HEADER_PHRASES:
                if phrase == candidate:
                    merged = " ".join(tokens[i : i + run_len])
                    consumed = run_len
                    break
            if merged is not None:
                break
        if merged is not None:
            result.append(merged)
            i += consumed
        else:
            result.append(tokens[i])
            i += 1
    return result


def _read_detail_rows(lines: list[str], idx: int, col_count: int) -> tuple[list[DetailRow], int]:
    """Read detail data rows from idx with the given column count.
    Returns (detail_rows, next_index).
    """
    rows: list[DetailRow] = []
    i = idx
    while i < len(lines):
        line = lines[i].strip()

        # Stop conditions
        if not line:
            i += 1
            continue
        if line == "SR. NO.":
            break
        # A detail table ends where the next summary entry begins.  The summary
        # header signature (``SR. NO.`` + ``INFORMATION CODE`` + ...) is the
        # reliable terminator — without it, the next entry's serial number +
        # information-code/description/source/count/amount tokens are misread
        # as a detail row of this entry (the "detail bleeding" bug where an
        # SFT-012 property table acquired SFT-005 deposit summary rows).
        if is_summary_header(lines, i):
            break
        if is_category_line(line):
            break
        if line.startswith("Note -") or line.startswith("Note-"):
            break
        if line.startswith("---"):
            break
        if "No Transactions Present" in line:
            break
        if line.startswith("Annual Information Statement"):
            break
        if line.startswith("Financial Year"):
            break
        if line.startswith("Download ID"):
            break
        if line.startswith("PAN") and i + 1 < len(lines) and lines[i + 1].strip().startswith("Name"):
            break

        if not line.isdigit():
            i += 1
            continue

        # Read col_count consecutive tokens starting with this numeric SR
        row_tokens = collect_row_tokens(lines, i, col_count)
        if row_tokens:
            detail = DetailRow(
                sr_no=int(line),
                data={f"col_{j}": row_tokens[j] if j < len(row_tokens) else "" for j in range(len(row_tokens))},
            )
            rows.append(detail)
            i += col_count
        else:
            i += 1

    return rows, i


def collect_row_tokens(lines: list[str], idx: int, expected_cols: int) -> list[str]:
    """Collect ``expected_cols`` tokens starting at idx.

    Each AIS detail row begins with a serial number immediately followed by a
    date (``dd/mm/yyyy``).  PyMuPDF emits every cell on a separate line, but
    multi-word column headers (``REPORTED ON``, ``PROPERTY ADDRESS``) are
    split across lines and the ``detail_header`` token count can overshoot the
    true data width.  To avoid overshooting one row into the next entry's
    summary (the "detail bleeding" bug), collection stops early when it hits
    a structural marker — a category line, a summary-header signature, a
    page footer, or the start of the next detail row (a serial number
    followed by a date).
    """
    tokens: list[str] = []
    i = idx
    while i < len(lines) and len(tokens) < expected_cols:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line == "SR. NO.":
            break
        if is_summary_header(lines, i):
            break
        if is_category_line(line):
            break
        if line.startswith("Note -") or line.startswith("Note-"):
            break
        if line.startswith("---"):
            break
        if "No Transactions Present" in line:
            break
        if line.startswith("Annual Information Statement"):
            break
        if line.startswith("Financial Year"):
            break
        if line.startswith("Download ID"):
            break
        if line.startswith("PAN") and i + 1 < len(lines) and lines[i + 1].strip().startswith("Name"):
            break
        # Stop at the next detail row's start: a serial number immediately
        # followed by a date.  ``isdigit`` here matches a 1-4 digit sr token,
        # and the date guard prevents swallowing the current row's own sr as
        # a column value once we've already captured it.
        if (
            tokens
            and line.isdigit()
            and i + 1 < len(lines)
            and re.match(r"^\d{2}/\d{2}/\d{4}$", lines[i + 1].strip())
        ):
            break
        tokens.append(line)
        i += 1
    return tokens


def _consume_note(lines: list[str], idx: int) -> int:
    """Skip past a 'Note -' block. Returns next index."""
    i = idx
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            return i + 1
        if line.startswith("Part B") or is_summary_header(lines, i) or is_detail_header_start(lines, i):
            return i
        if is_category_line(line):
            return i
        i += 1
    return i


def _parse_listed_equity_sale_rows(text: str) -> tuple[list[str], list[DetailRow]]:
    """Parse row-level SFT-17 listed-equity sales from extracted AIS text.

    PyMuPDF emits each table cell on separate lines and splits several cells
    (for example, ``Listed Equity Share`` and ``Off market``) across lines.
    This parser anchors each row on its serial number and transfer date, then
    parses the stable categorical and numeric suffix from the row.

    Args:
        text: Text containing an AIS section or complete AIS document.

    Returns:
        A canonical header and all valid listed-equity sale rows found.
    """
    header = [
        "SR. NO.",
        "DATE OF SALE/TRANSFER",
        "SECURITY NAME (SECURITY CODE)",
        "SECURITY CLASS",
        "DEBIT TYPE",
        "CREDIT TYPE",
        "ASSET TYPE",
        "QUANTITY",
        "SALE PRICE PER UNIT",
        "SALES CONSIDERATION",
        "COST OF ACQUISITION",
        "UNIT FMV",
        "FAIR MARKET VALUE",
        "INDEXED COST OF ACQUISITION",
        "STATUS",
    ]
    row_start = re.compile(r"(?m)^(?P<sr>\d+)\s*\n(?P<date>\d{2}/\d{2}/\d{4})\s*\n")
    starts = list(row_start.finditer(text))
    rows: list[DetailRow] = []
    numeric = r"[\d,]+(?:\.\d+)?"
    # PyMuPDF splits multi-word cell tokens (``Listed Equity Share``, ``Off
    # market``, ``Short term``) across lines arbitrarily — for example
    # ``Listed Equity \nShare`` or ``Off \nmarket`` with a trailing space
    # before the newline.  Each ``\w+`` sub-token below matches one word and
    # ``[\s]*`` allows any amount of whitespace/newlines between words, so the
    # pattern matches regardless of how the cell was wrapped.  The original
    # rigid ``Listed\s*\nEquity Share\s*\n`` form failed on ``Listed Equity
    # \nShare`` and parsed zero rows (the whole entry collapsed to a
    # summary-only aggregate with ``amount`` but no detail rows).
    listed_equity_share = r"Listed[\s]*Equity[\s]*Share"
    off_market = r"Off[\s]*market"
    market_or_off = rf"(?:Market|{off_market})"
    short_or_long_term = r"(?:Short|Long)[\s]*term"
    body_pattern = re.compile(
        rf"^(?P<security>.*?)\s*\n{listed_equity_share}\s*\n"
        rf"(?P<debit>{market_or_off})\s*\n"
        rf"(?P<credit>{market_or_off})\s*\n"
        rf"(?P<term>{short_or_long_term})\s*\n"
        rf"(?P<quantity>{numeric})\s*\n"
        rf"(?P<sale_price>{numeric})\s*\n"
        rf"(?P<consideration>{numeric})\s*\n"
        rf"(?P<cost>{numeric})\s*\n"
        rf"(?P<unit_fmv>{numeric})\s*\n"
        rf"(?P<fmv>{numeric})\s*\n"
        rf"(?P<indexed_cost>{numeric})\s*\n"
        rf"(?P<status>Active|Inactive)",
        re.DOTALL | re.IGNORECASE,
    )

    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        body = text[start.end():end]
        match = body_pattern.search(body)
        if match is None:
            continue

        security = re.sub(r"\s+", " ", match.group("security")).strip()
        isin_match = re.search(r"\b(IN[EA][A-Z0-9]{9})\b", security, re.IGNORECASE)
        isin = isin_match.group(1).upper() if isin_match else ""
        description = re.sub(r"\s*\(?IN[EA][A-Z0-9]{9}\)?\s*$", "", security, flags=re.IGNORECASE).strip()
        # Normalize whitespace (incl. the newlines PyMuPDF leaves inside the
        # multi-word ``Off market`` / ``Short term`` captures) before casing.
        debit_type = re.sub(r"\s+", " ", match.group("debit")).strip().title()
        credit_type = re.sub(r"\s+", " ", match.group("credit")).strip().title()
        # The ``term`` capture group already includes the word ``term``
        # (pattern ``(?:Short|Long)[\s]*term``), so no suffix is appended.
        # Normalise whitespace then capitalise only the first letter, so the
        # canonical form is ``Long term`` / ``Short term`` (matching the AIS
        # detail-header and the frontend CG mapper's expected casing).
        raw_term = re.sub(r"\s+", " ", match.group("term")).strip()
        asset_type = raw_term[:1].upper() + raw_term[1:] if raw_term else ""
        values = [
            str(int(start.group("sr"))),
            start.group("date"),
            security,
            "Listed Equity Share",
            debit_type,
            credit_type,
            asset_type,
            match.group("quantity"),
            match.group("sale_price"),
            match.group("consideration"),
            match.group("cost"),
            match.group("unit_fmv"),
            match.group("fmv"),
            match.group("indexed_cost"),
            match.group("status").title(),
        ]
        data = {f"col_{column}": value for column, value in enumerate(values)}
        data.update({
            "transfer_date": start.group("date"),
            "security_name": description,
            "security_code": isin,
            "isin": isin,
            "security_class": "Listed Equity Share",
            "debit_type": debit_type,
            "credit_type": credit_type,
            "asset_type": asset_type,
            "quantity": match.group("quantity"),
            "sale_price_per_unit": match.group("sale_price"),
            "sales_consideration": match.group("consideration"),
            "cost_of_acquisition": match.group("cost"),
            "unit_fmv": match.group("unit_fmv"),
            "fair_market_value": match.group("fmv"),
            "indexed_cost_of_acquisition": match.group("indexed_cost"),
            "status": match.group("status").title(),
        })
        rows.append(DetailRow(sr_no=int(start.group("sr")), data=data))

    return header, rows


def _parse_equity_mutual_fund_sale_rows(text: str) -> tuple[list[str], list[DetailRow]]:
    """Parse row-level SFT-18 equity-oriented mutual-fund disposals.

    Args:
        text: Text containing an AIS B2 section.

    Returns:
        A canonical header and every complete SFT-18 disposal row found.
    """
    header = [
        "SR. NO.", "AMC NAME (CODE)", "DATE OF SALE/TRANSFER",
        "SECURITY CLASS", "SECURITY NAME (SECURITY CODE)", "DEBIT TYPE",
        "CREDIT TYPE", "ASSET TYPE", "QUANTITY", "SALE PRICE PER UNIT",
        "SALES CONSIDERATION", "STT", "COST OF ACQUISITION", "UNIT FMV",
        "FAIR MARKET VALUE", "INDEXED COST OF ACQUISITION", "STATUS",
    ]
    numeric = r"[\d,]+(?:\.\d+)?"
    pattern = re.compile(
        rf"(?m)(?:(?<=STATUS\n)|(?<=Active\n))(?P<sr>\d+)\s*\n"
        rf"(?P<amc>.*?)\s*\n(?P<date>\d{{2}}/\d{{2}}/\d{{4}})\s*\n"
        rf"Unit of\s*\nEquity\s*\nOriented\s*\nMutual\s*\nFund\s*\n"
        rf"(?P<security>.*?)\s*\nAMC\s*\n\(redemption\s*\n?\)\s*\n"
        rf"AMC\s*\n\(purchase\s*\n?\)\s*\n"
        rf"(?P<term>Short|Long)\s*\nterm\s*\n"
        rf"(?P<quantity>{numeric})\s*\n(?P<sale_price>{numeric})\s*\n"
        rf"(?P<consideration>{numeric})\s*\n(?P<stt>{numeric})\s*\n"
        rf"(?P<cost>{numeric})\s*\n(?P<unit_fmv>{numeric})\s*\n"
        rf"(?P<fmv>{numeric})\s*\n(?P<indexed_cost>{numeric})\s*\n"
        rf"(?P<status>Active|Inactive)",
        re.DOTALL | re.IGNORECASE,
    )
    rows: list[DetailRow] = []
    for match in pattern.finditer(text):
        compact_amc = re.sub(r"\s+", "", match.group("amc")).strip()
        header_marker = compact_amc.rfind("STATUS")
        if header_marker >= 0:
            compact_amc = re.sub(r"^\d+", "", compact_amc[header_marker + len("STATUS"):])
        compact_security = re.sub(r"\s+", "", match.group("security")).strip()
        isin_match = re.search(r"\b(INF[A-Z0-9]{9})\b", compact_security, re.IGNORECASE)
        isin = isin_match.group(1).upper() if isin_match else ""
        security_name = re.sub(
            r"\(?INF[A-Z0-9]{9}\)?$", "", compact_security, flags=re.IGNORECASE
        ).strip()
        security_name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", security_name)
        asset_type = f"{match.group('term').title()} term"
        values = [
            match.group("sr"), compact_amc, match.group("date"),
            "Unit of Equity Oriented Mutual Fund", security_name,
            "AMC (redemption)", "AMC (purchase)", asset_type,
            match.group("quantity"), match.group("sale_price"),
            match.group("consideration"), match.group("stt"), match.group("cost"),
            match.group("unit_fmv"), match.group("fmv"), match.group("indexed_cost"),
            match.group("status").title(),
        ]
        data = {f"col_{index}": value for index, value in enumerate(values)}
        data.update({
            "amc_name": compact_amc,
            "transfer_date": match.group("date"),
            "security_name": security_name,
            "security_code": isin,
            "isin": isin,
            "security_class": "Unit of Equity Oriented Mutual Fund",
            "debit_type": "AMC (redemption)",
            "credit_type": "AMC (purchase)",
            "asset_type": asset_type,
            "quantity": match.group("quantity"),
            "sale_price_per_unit": match.group("sale_price"),
            "sales_consideration": match.group("consideration"),
            "stt": match.group("stt"),
            "cost_of_acquisition": match.group("cost"),
            "unit_fmv": match.group("unit_fmv"),
            "fair_market_value": match.group("fmv"),
            "indexed_cost_of_acquisition": match.group("indexed_cost"),
            "status": match.group("status").title(),
        })
        rows.append(DetailRow(sr_no=int(match.group("sr")), data=data))
    return header, rows


def parse_section_text(text: str, section: str) -> list[AISEntry]:
    """Parse a complete section (B1, B2, or B7) into AISEntry objects
    using a line-by-line state machine.

    Args:
        text: Full text of the section
        section: "B1", "B2", or "B7"

    Returns:
        List of AISEntry objects, each with its detail rows populated
    """
    lines = text.split('\n')
    entries: list[AISEntry] = []
    state = State.IDLE
    current_category = ""
    current_entry: Optional[AISEntry] = None
    detail_header: list[str] = []
    col_count = 0
    i = 0

    def _finalize_entry():
        nonlocal current_entry, detail_header, col_count
        if current_entry:
            current_entry.category = current_category
            current_entry.section = section
            current_entry.income_head = map_to_head(current_category, section)
            current_entry.detail_header = detail_header
            entries.append(current_entry)
        current_entry = None
        detail_header = []
        col_count = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Skip page markers and noise
        if line.startswith("Page ") and "of" in line:
            i += 1
            continue
        if line.startswith("Annual Information Statement"):
            i += 1
            continue
        if line.startswith("Financial Year"):
            i += 1
            continue
        if "Download ID" in line or "IP Address" in line or "Generation Date" in line:
            i += 1
            continue
        if line.startswith("PAN") and i + 1 < len(lines) and "Name" in lines[i + 1]:
            i += 2  # skip footer
            continue

        # ============================================================
        # State: IDLE - looking for start
        # ============================================================
        if state == State.IDLE:
            cat = is_category_line(line)
            if cat:
                current_category = cat
                state = State.CATEGORY
                i += 1
                continue
            # Skip section header lines like "Part B2-..."
            if line.startswith("Part B"):
                i += 1
                continue
            if "(All amount" in line:
                i += 1
                continue
            i += 1
            continue

        # ============================================================
        # State: CATEGORY - looking for "SR. NO." summary header
        # ============================================================
        if state == State.CATEGORY:
            if line.startswith("No Transactions Present"):
                _finalize_entry()
                state = State.IDLE
                current_category = ""
                i += 1
                continue

            if is_summary_header(lines, i):
                state = State.SUMMARY_HEADER
                i += len(SUMMARY_HEADER_SIG)  # skip past header tokens
                continue

            # New category override
            next_cat = is_category_line(line)
            if next_cat:
                _finalize_entry()
                current_category = next_cat
                state = State.CATEGORY
                i += 1
                continue

            # Skip non-matching lines
            i += 1
            continue

        # ============================================================
        # State: SUMMARY_HEADER - verify and transition to SUMMARY_DATA
        # ============================================================
        if state == State.SUMMARY_HEADER:
            if not line.isdigit():
                # Not a data row - might be "No Transactions"
                if "No Transactions" in line:
                    _finalize_entry()
                    state = State.IDLE
                    current_category = ""
                    i += 1
                    continue
                # Unexpected - try to recover
                next_cat = is_category_line(line)
                if next_cat:
                    _finalize_entry()
                    current_category = next_cat
                    state = State.CATEGORY
                    i += 1
                    continue
                i += 1
                continue

            # Parse the 6-line summary data row
            entry, i = _parse_summary_data(lines, i)
            entry.category = current_category
            current_entry = entry
            state = State.SUMMARY_DATA
            continue

        # ============================================================
        # State: SUMMARY_DATA - determine what comes next
        # ============================================================
        if state == State.SUMMARY_DATA:
            if is_summary_header(lines, i):
                # New summary block - finalize current and start new
                _finalize_entry()
                state = State.SUMMARY_HEADER
                i += len(SUMMARY_HEADER_SIG)
                continue

            if is_detail_header_start(lines, i):
                state = State.DETAIL_HEADER
                continue  # i stays, let detail_header state handle it

            # New category
            next_cat = is_category_line(line)
            if next_cat:
                _finalize_entry()
                current_category = next_cat
                state = State.CATEGORY
                i += 1
                continue

            # No Transactions
            if "No Transactions" in line:
                i += 1
                continue

            # Note block
            if line.startswith("Note -") or line.startswith("Note-"):
                _finalize_entry()
                state = State.NOTE
                i += 1
                continue

            # End of section marker
            if line.startswith("Part B"):
                _finalize_entry()
                return entries

            # Default: skip unknown line
            i += 1
            continue

        # ============================================================
        # State: DETAIL_HEADER - read detail column headers
        # ============================================================
        if state == State.DETAIL_HEADER:
            detail_tokens, i = _read_detail_header(lines, i)
            if detail_tokens:
                detail_header = detail_tokens
                col_count = len(detail_tokens)
                state = State.DETAIL_DATA
            else:
                state = State.SUMMARY_DATA
            continue

        # ============================================================
        # State: DETAIL_DATA - read detail data rows
        # ============================================================
        if state == State.DETAIL_DATA:
            if line.isdigit():
                detail_rows, i = _read_detail_rows(lines, i, col_count)
                if current_entry:
                    current_entry.details.extend(detail_rows)
                continue

            # End of detail block
            if is_summary_header(lines, i):
                _finalize_entry()
                state = State.SUMMARY_HEADER
                i += len(SUMMARY_HEADER_SIG)
                continue

            if is_detail_header_start(lines, i):
                state = State.DETAIL_HEADER
                continue

            next_cat = is_category_line(line)
            if next_cat:
                _finalize_entry()
                current_category = next_cat
                state = State.CATEGORY
                i += 1
                continue

            if line.startswith("Note -"):
                _finalize_entry()
                state = State.NOTE
                i += 1
                continue

            if "No Transactions" in line:
                i += 1
                continue

            if line.startswith("Part B"):
                _finalize_entry()
                return entries

            i += 1
            continue

        # ============================================================
        # State: NOTE - consume note text until next section
        # ============================================================
        if state == State.NOTE:
            if line.startswith("Part B"):
                _finalize_entry()
                state = State.IDLE
                return entries
            next_cat = is_category_line(line)
            if next_cat:
                _finalize_entry()
                current_category = next_cat
                state = State.CATEGORY
                i += 1
                continue
            if is_summary_header(lines, i):
                _finalize_entry()
                state = State.SUMMARY_HEADER
                i += len(SUMMARY_HEADER_SIG)
                continue
            i += 1
            continue

        i += 1

    _finalize_entry()
    return entries


# ============================================================
# AIS Extractor
# ============================================================

class AISExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self._text = ""

    def extract(self) -> AISDocument:
        doc_result = AISDocument()

        with open(self.pdf_path, 'rb') as f:
            import fitz
            pdf = fitz.open(self.pdf_path)
            try:
                for page in pdf:
                    self._text += page.get_text()
            finally:
                pdf.close()

        doc_result.metadata = self._extract_metadata()
        doc_result.b1_entries = self._extract_section("Part B1", "Part B2", "B1")
        doc_result.b2_entries = self._extract_section("Part B2", "Part B7", "B2")
        doc_result.b7_entries = self._extract_section("Part B7", "Part B3", "B7")
        doc_result.tax_payments = self._extract_b3()
        doc_result.refunds = self._extract_b4()
        doc_result.income_head_groups = self._group_by_head(doc_result)
        return doc_result

    def _extract_section(self, start_marker: str, end_marker: str, section: str) -> list[AISEntry]:
        idx = self._text.find(start_marker)
        if idx == -1:
            return []

        # Check if end marker exists; if not found try next known marker
        end = self._text.find(end_marker, idx)
        if end == -1:
            for alt in ["Part B3", "Part B4", "Part B7"]:
                end = self._text.find(alt, idx)
                if end != -1 and end > idx:
                    break

        section_text = self._text[idx:end if end != -1 else len(self._text)]
        entries = parse_section_text(section_text, section)
        if section == "B2":
            listed_header, listed_rows = _parse_listed_equity_sale_rows(section_text)
            mutual_fund_header, mutual_fund_rows = _parse_equity_mutual_fund_sale_rows(section_text)
            listed_offset = 0
            mutual_fund_offset = 0
            for entry in entries:
                code = entry.information_code.upper()
                expected_count = max(entry.count, 0)
                if code.startswith("SFT-17-LES"):
                    assigned_rows = listed_rows[listed_offset:listed_offset + expected_count]
                    if assigned_rows:
                        entry.detail_header = listed_header
                        entry.details = assigned_rows
                        listed_offset += len(assigned_rows)
                elif code.startswith("SFT-18-EMF"):
                    assigned_rows = mutual_fund_rows[mutual_fund_offset:mutual_fund_offset + expected_count]
                    if assigned_rows:
                        entry.detail_header = mutual_fund_header
                        entry.details = assigned_rows
                        mutual_fund_offset += len(assigned_rows)
        return entries

    def _extract_metadata(self) -> AISMetadata:
        text = self._text
        meta = AISMetadata()
        lines = text.split('\n')

        pa_start = next((i for i, l in enumerate(lines) if 'Part A' in l), 0)

        # Block-based offset extraction (see analysis above)
        try:
            if pa_start + 4 < len(lines):
                meta.pan = lines[pa_start + 4].strip()
            if pa_start + 5 < len(lines):
                meta.aadhaar_masked = lines[pa_start + 5].strip()
            if pa_start + 6 < len(lines):
                meta.name = lines[pa_start + 6].strip()
            if pa_start + 10 < len(lines):
                meta.dob = lines[pa_start + 10].strip()
            if pa_start + 11 < len(lines):
                meta.mobile = lines[pa_start + 11].strip()
            if pa_start + 12 < len(lines):
                meta.email = lines[pa_start + 12].strip()
            if pa_start + 14 < len(lines):
                addr_start = pa_start + 14
                addr_lines = []
                for j in range(addr_start, min(addr_start + 10, len(lines))):
                    if lines[j].startswith('---') or 'Annual Information' in lines[j]:
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

    def _extract_b3(self) -> list[TaxPaymentEntry]:
        payments: list[TaxPaymentEntry] = []
        idx = self._text.find("Part B3")
        if idx == -1:
            return payments
        end = self._text.find("Part B4", idx)
        b3 = self._text[idx:end if end != -1 else len(self._text)]
        if "No Transactions Present" in b3:
            return payments

        pat = re.compile(
            r'(\d+)\s*\n(\d{4}-\d{2})\s*\n([^\n]+?)\s*\n([^\n]+?)\s*\n'
            r'([\d,.]+)\s*\n([\d,.]+)\s*\n([\d,.]+)\s*\n([\d,.]+)\s*\n'
            r'([\d,.]+)\s*\n([^\n]+?)\s*\n(\d{2}/\d{2}/\d{4})\s*\n([^\n]+?)\s*\n([^\n]+)'
        )
        for m in pat.finditer(b3):
            payments.append(TaxPaymentEntry(
                sr_no=int(m.group(1)), financial_year=m.group(2),
                major_head=m.group(3).strip(), minor_head=m.group(4).strip(),
                tax=parse_indian_amount(m.group(5)),
                surcharge=parse_indian_amount(m.group(6)),
                cess=parse_indian_amount(m.group(7)),
                others=parse_indian_amount(m.group(8)),
                total=parse_indian_amount(m.group(9)),
                bsr_code=m.group(10).strip(), deposit_date=m.group(11),
                challan_serial=m.group(12).strip(), cin=m.group(13).strip(),
            ))
        return payments

    def _extract_b4(self) -> list[RefundEntry]:
        refunds: list[RefundEntry] = []
        idx = self._text.find("Part B4")
        if idx == -1:
            return refunds
        b4 = self._text[idx:]
        ref_idx = b4.find("Refund")
        if ref_idx == -1:
            return refunds
        refund_text = b4[ref_idx:]
        pan_marker = refund_text.find("\nPAN\n")
        if pan_marker != -1:
            refund_text = refund_text[:pan_marker]

        pat = re.compile(
            r'(\d+)\s*\n(\d{4}-\d{2})\s*\n([^\n]+?)\s*\n([^\n]+?)\s*\n([\d,.]+)\s*\n(\d{2}/\d{2}/\d{4})'
        )
        for m in pat.finditer(refund_text):
            refunds.append(RefundEntry(
                sr_no=int(m.group(1)), financial_year=m.group(2),
                mode=m.group(3).strip(), nature=m.group(4).strip(),
                amount=parse_indian_amount(m.group(5)), date=m.group(6),
            ))
        return refunds

    def _group_by_head(self, doc: AISDocument) -> dict[str, IncomeHeadGroup]:
        groups: dict[str, IncomeHeadGroup] = {}

        def g(key: str) -> IncomeHeadGroup:
            if key not in groups:
                groups[key] = IncomeHeadGroup(income_head=key)
            return groups[key]

        for entry in doc.b1_entries:
            grp = g(entry.income_head)
            grp.entries.append(entry)
            grp.total_amount += entry.amount

        for entry in doc.b2_entries:
            grp = g(entry.income_head)
            grp.entries.append(entry)
            grp.total_amount += entry.amount

        for entry in doc.b7_entries:
            grp = g(entry.income_head)
            grp.entries.append(entry)
            grp.total_amount += entry.amount

        for tp in doc.tax_payments:
            grp = g(IncomeHead.TAX_PAID.value)
            grp.tax_payments.append(tp)
            grp.total_amount += tp.total

        for ref in doc.refunds:
            grp = g(IncomeHead.REFUND.value)
            grp.refunds.append(ref)
            grp.total_amount += ref.amount

        return groups


# ============================================================
# JSON Export
# ============================================================

def entry_to_dict(entry: AISEntry) -> dict:
    return {
        "sr_no": entry.sr_no,
        "information_code": entry.information_code,
        "information_description": entry.information_description,
        "information_source": entry.information_source,
        "institution_pan": entry.institution_pan,
        "count": entry.count,
        "amount": entry.amount,
        "category": entry.category,
        "section": entry.section,
        "income_head": entry.income_head,
        "detail_header": entry.detail_header,
        "details": [{"sr_no": d.sr_no, "data": d.data} for d in entry.details],
    }


def ais_to_frontend_json(doc: AISDocument, indent: int = 2) -> str:
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

    # Compute totals from entries
    for entry in doc.b1_entries:
        cat = entry.category.lower()
        if "salary" in cat:
            output["summary"]["total_tds"] += entry.amount
        else:
            output["summary"]["total_tds"] += entry.amount

    for entry in doc.b2_entries:
        cat = entry.category.lower()
        if "interest" in cat:
            output["summary"]["total_interest"] += entry.amount
        elif "dividend" in cat:
            output["summary"]["total_dividend"] += entry.amount
        elif "sale of securities" in cat:
            output["summary"]["total_capital_gains_sale"] += entry.amount
        elif "purchase of securities" in cat:
            output["summary"]["total_capital_gains_purchase"] += entry.amount

    for entry in doc.b7_entries:
        cat = entry.category.lower()
        if "gst turnover" in cat:
            output["summary"]["total_gst_turnover"] += entry.amount
        elif "gst purchases" in cat:
            output["summary"]["total_gst_purchases"] += entry.amount

    for tp in doc.tax_payments:
        output["summary"]["total_tax_paid"] += tp.total
    for ref in doc.refunds:
        output["summary"]["total_refund"] += ref.amount

    # Build income head groups
    for ih_key, group in doc.income_head_groups.items():
        output["income_heads"][ih_key] = {
            "income_head": group.income_head,
            "total_amount": group.total_amount,
            "entries": [entry_to_dict(e) for e in group.entries],
            "tax_payments": [asdict(tp) for tp in group.tax_payments],
            "refunds": [asdict(ref) for ref in group.refunds],
        }

    return json.dumps(output, indent=indent, ensure_ascii=False)


# ============================================================
# Convenience — delegates to the pdfplumber-based implementation.
#
# The pdfplumber extractor (``ais_extractor.ais_pdfplumber``) replaces the
# PyMuPDF line-state-machine parsing core because pdfplumber recovers proper
# cell boundaries and eliminates the multi-word-cell wrapping / detail-row
# bleeding regressions.  The ``AISDocument`` / ``AISEntry`` / ``DetailRow``
# dataclass contract and the JSON serialisation are unchanged, so callers
# (``reconciliation.py``, the frontend mappers, the corpus tests) work
# unchanged.  The legacy ``AISExtractor`` class above is retained for
# reference but is no longer the live path.
# ============================================================

def extract_ais(pdf_path: str) -> AISDocument:
    """Extract an AIS PDF via the pdfplumber-based implementation."""
    from .ais_pdfplumber import extract_ais as _extract_ais

    return _extract_ais(pdf_path)


def extract_ais_json(pdf_path: str, indent: int = 2) -> str:
    """Extract an AIS PDF to JSON via the pdfplumber-based implementation."""
    from .ais_pdfplumber import extract_ais_json as _extract_ais_json

    return _extract_ais_json(pdf_path, indent)
