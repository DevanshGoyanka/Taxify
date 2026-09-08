"""
Reconciliation Engine for AIS, TIS, and 26AS data.

Takes JSON outputs from the three PDF extractors and produces
a unified, reconciled view organized by income head.

Priority for final amount: TIS (accepted_by_taxpayer) > AIS (amount) > 26AS
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ============================================================
# Category → Section → Income Head Mapping
# ============================================================

CATEGORY_TO_INCOME_HEAD = {
    "salary":                           "Salary",
    "business receipts":                "Profits and Gains of Business or Profession",
    "dividend":                         "Income from Other Sources",
    "interest from savings bank":       "Income from Other Sources",
    "interest from deposit":            "Income from Other Sources",
    "sale of securities and units of mutual fund": "Capital Gains",
    "purchase of securities and units of mutual funds": "Capital Gains",
    "sale of land or building":         "Capital Gains",
    "purchase of immovable property":   "Capital Gains",
    "gst turnover":                     "Profits and Gains of Business or Profession",
    "gst purchases":                    "Profits and Gains of Business or Profession",
    "purchase of time deposits":        "Informational Transaction",
    "cash deposits":                     "Informational Transaction",
    "cash withdrawals":                 "Informational Transaction",
    "winnings from online games":       "Income from Other Sources",
    "purchase of vehicle":              "Informational Transaction",
    "commission income":                "Profits and Gains of Business or Profession",
    "insurance commission":             "Profits and Gains of Business or Profession",
    "receipt from partnership firm":    "Profits and Gains of Business or Profession",
    "professional fees":                "Profits and Gains of Business or Profession",
    "receipts on transfer of virtual digital asset": "Capital Gains",
    "miscellaneous payment":            "Informational Transaction",
    "outward foreign remittance":       "Informational Transaction",
    "tax payments":                     "Taxes Paid",
    "refund":                           "Refund",
    # TCS (Tax Collected at Source) is a tax credit, not income.  CBDT rules
    # place TCS on business receipts ONLY when the collectee is in business
    # for the corresponding goods; for a non-business collectee (e.g. a
    # salaried person buying a car under 206CF) the TCS is a refundable/
    # brought-forward credit against tax payable, NOT PGBP income.  26AS
    # alone cannot determine collectee business status, so the safe CBDT-
    # compliant default is to route every 206C* section to a dedicated
    # ``TCS Credit`` bucket (remediation R1).  The engine surfaces TCS via
    # ``as26_tcs`` on the entry regardless of routing, so the credit is
    # preserved; only the income-head attribution changes.
    "tcs credit":                       "TCS Credit",
}

SECTION_TO_CATEGORY = {
    "192": "salary", "192A": "salary",
    "193": "interest from deposit",
    "194": "dividend", "194K": "dividend",
    "194A": "interest from deposit",
    "194B": "winnings from online games", "194BA": "winnings from online games",
    "194BB": "winnings from online games",
    "194C": "business receipts", "194D": "insurance commission",
    "194H": "commission income", "194I": "business receipts",
    "194J": "business receipts", "194M": "business receipts",
    "194N": "cash withdrawals", "194O": "business receipts",
    "194Q": "business receipts",
    # 194S = TDS on transfer of Virtual Digital Asset — a capital-gains
    # transaction (Schedule VDA), NOT business receipts.
    "194S": "receipts on transfer of virtual digital asset",
    "194IA": "sale of land or building", "194IB": "sale of land or building",
    # 206CF (vehicle purchase TCS), 206CQ (LRS remittance TCS), and the
    # generic 206C are Tax Collected at Source — they are NOT income.  The
    # assessee who buys a car or remits forex is not earning income; the
    # amount is only a tax credit claimable against tax payable.  Route to
    # the ``tcs credit`` bucket so no income entry is produced (only the
    # Schedule TCS credit), while the transaction still surfaces in the
    # import summary for transparency.
    "206C": "tcs credit", "206CF": "tcs credit", "206CQ": "tcs credit",
    "206CE": "tcs credit", "206CG": "tcs credit",
}

TRANSACTION_LEVEL_CATEGORIES = frozenset({
    "sale of securities and units of mutual fund",
    "purchase of securities and units of mutual funds",
    "sale of land or building",
    "purchase of immovable property",
    "receipts on transfer of virtual digital asset",
})

# ── Informational / tax-credit-only categories (NOT income) ───────────────────
# CBDT placement (Income Tax Act 1961, AY 2026-27): the following AIS/TIS
# transactions are NOT chargeable as income — they are SFT reportable
# events or TDS/TCS book entries where the assessee is the payor/buyer,
# not a recipient of income.  They must NOT produce an income entry; any
# tax deducted/collected (TDS/TCS) flows only as a Schedule TDS/TCS
# credit claimable against tax payable.  The transactions still appear in
# the import summary for transparency.
#
#   * ``purchase of time deposits`` (SFT-005): buying an FD is not income;
#     the interest from the FD is, captured separately as SFT-016 interest.
#   * ``cash deposits`` / ``cash withdrawals`` (SFT-004, SFT-003): cash
#     movements into/out of a bank account; not income.  §194N TDS on cash
#     withdrawals is a refundable credit.
#   * ``purchase of vehicle`` (§206CF): TCS collected on vehicle purchase;
#     the buyer earns no income — only a TCS credit.
#   * ``miscellaneous payment`` (SFT-006 credit-card payments): a payment,
#     not income.
#   * ``outward foreign remittance`` (§206CQ LRS): TCS on forex remittance;
#     a credit, not income.
NON_INCOME_CATEGORIES: frozenset[str] = frozenset({
    "purchase of time deposits",
    "cash deposits",
    "cash withdrawals",
    "purchase of vehicle",
    "miscellaneous payment",
    "outward foreign remittance",
})


class CreditType(str, Enum):
    """Tax-credit kind sourced authoritatively from Form 26AS."""

    TDS = "TDS"
    TCS = "TCS"


class SelectedSource(str, Enum):
    """Source selected for the reconciled value."""

    TIS = "TIS"
    AIS = "AIS"
    FORM_26AS = "26AS"


# ============================================================
# Name normalization
# ============================================================

_CODE_SUFFIX_RE = re.compile(r'\s*\([A-Z0-9.]+\s*\)\s*$', re.IGNORECASE)


# ── Canonical category normalization ─────────────────────────────────────────
# The AIS and TIS extractors sometimes emit semantically-identical categories
# under different text labels (e.g. AIS ``interest income (sft-016) – savings``
# vs TIS ``interest from savings bank``).  Without canonicalization, the
# reconciliation engine treats these as different categories, so the same
# income appears as two separate entries instead of being merged.  This
# function maps every known variant label to its canonical form, so the
# engine's ``Entry.key`` and ``CATEGORY_TO_INCOME_HEAD`` lookups produce
# matching keys across documents.
_CATEGORY_CANON_PATTERNS: list[tuple[str, str]] = [
    # ── Interest ──
    # AIS emits "interest income (sft-016) – savings" / "– term deposit";
    # TIS emits "interest from savings bank" / "interest from deposit".
    # AIS also emits "interest other than "interest on securities" received
    # (section 194a)" — the same as TIS "interest from deposit".
    (r"sft[- ]?016.*savings|interest.*savings|savings.*interest", "interest from savings bank"),
    (r"sft[- ]?016.*term|interest.*deposit|deposit.*interest|sft[- ]?016.*td|interest\s+other\s+than.*securities|interest\s+other\s+than.*194a", "interest from deposit"),
    # ── Dividend ── (AIS "Dividend income (SFT-015)" already matches, but be safe)
    (r"dividend", "dividend"),
    # ── Capital gains ── (sale/purchase of securities/MF)
    (r"sale.*equity|sale.*securities|sale.*mutual fund|sale.*unit", "sale of securities and units of mutual fund"),
    (r"purchase.*securities|purchase.*mutual fund|purchase.*units", "purchase of securities and units of mutual funds"),
    (r"sale.*land|sale.*building|sale.*immovable|transfer.*immovable|receipts.*immovable", "sale of land or building"),
    (r"purchase.*immovable|purchase.*property", "purchase of immovable property"),
    # ── SFT deposit purchases ──
    (r"purchase.*time deposit|time deposit", "purchase of time deposits"),
    (r"cash deposit", "cash deposits"),
    (r"cash withdrawal", "cash withdrawals"),
    # ── Salary / business ──
    (r"salary", "salary"),
    (r"business receipts|business receipt|receipts from contract|perquisites.*business|benefits.*business", "business receipts"),
    (r"gst turnover|sales reported under gstr|sales.*gstr", "gst turnover"),
    (r"gst purchase|purchases reported under gstr|purchases.*gstr", "gst purchases"),
    (r"receipt.*partnership|partnership.*firm", "receipt from partnership firm"),
    (r"insurance commission", "insurance commission"),
    (r"commission or brokerage|commission income", "commission income"),
    (r"professional fees", "professional fees"),
    (r"purchase.*vehicle", "purchase of vehicle"),
    # ── VDA (Virtual Digital Asset) — capital gains, NOT winnings ──
    # TIS "Receipts on transfer of virtual digital asset" and AIS
    # "TDS-194S Amount received on transfer of virtual digital asset" are
    # capital-gains transactions (Schedule VDA in ITR-2/3), distinct from
    # "Winnings from Online Games" (194BA) which is Other Sources.  Keep
    # them separate so VDA routes to the Capital Gains tab.
    (r"virtual digital asset|vda|transfer of virtual digital", "receipts on transfer of virtual digital asset"),
    (r"winnings.*online|online.*games", "winnings from online games"),
    (r"rent", "rent"),
]


def canonical_category(category: str) -> str:
    """Map any variant category label to its canonical form.

    This is the single point of truth for category equivalence across the
    AIS, TIS, and 26AS extractors.  Every ``Entry`` is canonicalized at
    construction so ``Entry.key``, ``CATEGORY_TO_INCOME_HEAD``, and the
    cross-document matchers all see the same canonical label regardless
    of which extractor produced the row.  Without this, the AIS label
    ``interest income (sft-016) – savings`` and the TIS label
    ``interest from savings bank`` would produce different keys and the
    engine would emit duplicate entries for the same income.
    """
    if not category:
        return "other"
    c = category.strip().lower()
    for pattern, canonical in _CATEGORY_CANON_PATTERNS:
        if re.search(pattern, c):
            return canonical
    return c


# Trailing descriptive suffixes that TIS/26AS append to the source name but
# AIS does not (e.g. "Total purchase amount 24,999 24,999", "Value of
# consideration 1,40,229 1,40,229", "Amount paid/ credited 60,000 60,000",
# "Gross purchase amount 13,50,000 13,50,000", "Interest 839 839").  These
# make the same reporting entity produce different normalized names across
# AIS and TIS/26AS, which breaks transaction-level (capital-gains) and
# interest matching.  Stripped before normalization.
_TRAILING_AMOUNT_SUFFIX_RE = re.compile(
    r'\s*(?:'
    r'total\s+\w+\s+amount|'
    r'value\s+of\s+consideration|'
    r'amount\s+paid\s*/?\s*credited|'
    r'amount\s+paid|'
    r'gross\s+purchase\s+amount|'
    r'gross\s+sale\s+amount|'
    r'interest|'
    r'dividend\s+amount|'
    r'total\s+amount'
    r')'
    r'\s+-?[\d,]+(?:\.\d+)?'           # first amount (optional leading -)
    r'(?:\s+-?[\d,]+(?:\.\d+)?)?'      # optional second amount
    r'\s*-\s*$'                        # OR trailing " -" reversal marker
    r'|\s*(?:'
    r'total\s+\w+\s+amount|value\s+of\s+consideration|amount\s+paid\s*/?\s*credited|'
    r'amount\s+paid|gross\s+purchase\s+amount|gross\s+sale\s+amount|interest|'
    r'dividend\s+amount|total\s+amount'
    r')\s+[\d,]+(?:\.\d+)?(?:\s+[\d,]+(?:\.\d+)?)?\s*$',
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Equivalence-normalize a reporting-entity name for cross-document matching.

    This is the single identity function used to match the same deductor
    across AIS, TIS, and 26AS, which key on different identifiers (AIS SFT
    entries carry a PAN; 26AS Part I rows carry a TAN, never a PAN; TIS SFT
    entries carry a PAN).  Because the PAN and TAN differ for the same bank,
    the NAME is the only stable bridge.  Evidence from the 61-client corpus:

      * AIS reports SBI interest as "STATE BANK OF INDIA (AAACS8577K.AB703)"
        under SFT-016 (PAN) AND as "STATE BANK OF INDIA (MUMS89569E)" under
        TDS-194A (TAN) — same bank, different identifier suffix.
      * 26AS reports the same SBI as "STATE BANK OF INDIA" with TAN
        MUMS89569E.
      * Co-operative banks appear as both "CO-OP" and "CO-OPERATIVE".

    So this function: lowercases; strips parenthetical PAN/TAN codes; strips
    trailing descriptive amount suffixes ("Total purchase amount 24,999
    24,999", "Amount paid/ credited 60,000 60,000", "Interest 839 839");
    collapses CO-OP/CO-OPERATIVE → coop, LIMITED → ltd; drops a leading
    "the"; and collapses whitespace.  The result is a stable identity that
    matches across all three documents for the same real-world deductor.
    """
    if not name:
        return ""
    n = _TRAILING_AMOUNT_SUFFIX_RE.sub('', name)
    n = _CODE_SUFFIX_RE.sub('', n)
    n = re.sub(r'\s*\([^)]*\)\s*', ' ', n)
    n = re.sub(r'co[- ]?operative', 'coop', n, flags=re.IGNORECASE)
    n = re.sub(r'\blimited\b', 'ltd', n, flags=re.IGNORECASE)
    n = re.sub(r'[^a-z0-9\s]', '', n.lower())
    n = re.sub(r'^the\s+', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def normalize_source_identity(category: str, source: str) -> str:
    """Return a controlled fallback identity for cross-document matching."""
    normalized = normalize_name(source)
    if category.strip().lower() == "salary":
        normalized = re.sub(r'^salary(?:\s+received)?\s+', '', normalized)
    return normalized


def extract_pan(source: str) -> str:
    """Extract PAN from source like 'BANK (ABCDE1234F.XYZ)'."""
    if not source:
        return ""
    m = re.search(r'\(([A-Z]{5}[0-9]{4}[A-Z])[.)]', source)
    if m:
        return m.group(1)
    return ""


def canonical_section(section: str, description: str = "") -> str:
    """Normalize statutory section text for cross-source matching."""
    combined = f"{section} {description}".upper()
    match = re.search(r'(?:SECTION\s*)?(192A?|193|194[A-Z]{0,2}|206C[A-Z]?)', combined)
    return match.group(1) if match else ""


def sections_compatible(left: Entry, right: Entry) -> bool:
    """Return whether two entries can represent the same statutory field."""
    left_section = canonical_section(left.section, left.description)
    right_section = canonical_section(right.section, right.description)
    return not left_section or not right_section or left_section == right_section


def _parse_amount(val: Any) -> float:
    """Parse a string amount safely, handling '-' and commas."""
    if val is None:
        return 0.0
    s = str(val).strip().replace(",", "")
    if s in ("", "-", "--", "—"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


# ============================================================
# Entry extraction from each document
# ============================================================

class RecordGranularity(str, Enum):
    """Granularity of a capital-gain source record."""

    TRANSACTION_DETAIL = "TRANSACTION_DETAIL"
    ACCOUNT_PERIOD_AGGREGATE = "ACCOUNT_PERIOD_AGGREGATE"
    REPORTING_SOURCE_AGGREGATE = "REPORTING_SOURCE_AGGREGATE"
    CATEGORY_CONTROL = "CATEGORY_CONTROL"


@dataclass
class CapitalGainEvidence:
    """One immutable AIS capital-gain detail or aggregate evidence record."""

    evidence_id: str
    granularity: RecordGranularity
    side: str
    category: str
    information_code: str
    summary_sr_no: int
    detail_sr_no: Optional[int]
    reporting_source: str
    reporting_entity_pan: str
    account_id: str = ""
    transaction_date: str = ""
    # SFT-18(Pur)/SFT-17(Pur) purchase aggregates carry no transaction date;
    # instead the AIS reports a quarter string e.g. "Q2(Jul-Sep)".  Preserved
    # verbatim so the UI can render it alongside an editable date input.
    quarter: str = ""
    security_class: str = ""
    security_name: str = ""
    security_identifier: str = ""
    quantity: Optional[float] = None
    amount: float = 0.0
    acquisition_cost: Optional[float] = None
    fair_market_value: Optional[float] = None
    unit_fmv: Optional[float] = None
    sale_price_per_unit: Optional[float] = None
    stt_amount: Optional[float] = None
    debit_type: str = ""
    credit_type: str = ""
    asset_type: str = ""
    stt_paid_on_acquisition: Optional[bool] = None
    stt_paid_on_transfer: Optional[bool] = None
    recognized_exchange: Optional[bool] = None
    acquired_before_31_jan_2018: Optional[bool] = None
    acquisition_mode: str = ""
    status: str = ""
    parser_confidence: str = "LOW"


@dataclass
class CapitalGainControl:
    """AIS or TIS aggregate used solely to cross-foot detail records."""

    control_id: str
    source_document: str
    granularity: RecordGranularity
    category: str
    side: str
    information_code: str
    reporting_source: str
    reporting_entity_pan: str
    amount: float
    accepted_amount: Optional[float] = None


_HEADER_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")


def _stable_source_id(*parts: object) -> str:
    """Return a deterministic non-PII-prefixed identity for a source row."""
    payload = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _capital_gain_side(category: str) -> str:
    """Infer purchase or sale side from an AIS/TIS category."""
    normalized = category.strip().lower()
    if "purchase" in normalized:
        return "PURCHASE"
    if "sale" in normalized or "transfer" in normalized:
        return "SALE"
    return "UNKNOWN"


def _normalized_header(value: str) -> str:
    """Normalize a PDF table heading for semantic field matching."""
    return _HEADER_NON_ALNUM_RE.sub(" ", value.upper()).strip()


def _detail_cells(headers: list[str], detail: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    """Map positional AIS detail values to normalized headings."""
    raw = detail.get("data", {})
    if not isinstance(raw, dict):
        return {}, []
    values = [str(raw.get(f"col_{index}", "") or "").strip() for index in range(max(len(headers), len(raw)))]
    mapped: dict[str, str] = {}
    for index, value in enumerate(values):
        header = _normalized_header(headers[index]) if index < len(headers) else f"COLUMN {index}"
        if header:
            mapped[header] = value
    return mapped, values


def _first_semantic_value(cells: dict[str, str], *terms: str) -> str:
    """Return the first non-empty cell whose heading contains all terms."""
    normalized_terms = tuple(term.upper() for term in terms)
    for heading, value in cells.items():
        if value and all(term in heading for term in normalized_terms):
            return value
    return ""


def _optional_amount(value: str) -> Optional[float]:
    """Parse an amount while distinguishing missing or malformed data from zero."""
    if not value or value.strip() in {"-", "--", "—"}:
        return None
    cleaned = re.sub(r"[₹\s]", "", value).replace(",", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    try:
        amount = float(cleaned)
    except ValueError:
        return None
    return -amount if negative else amount


def _first_amount(cells: dict[str, str], candidates: tuple[tuple[str, ...], ...]) -> Optional[float]:
    """Return the first valid amount under a semantically matching heading."""
    for terms in candidates:
        normalized_terms = tuple(term.upper() for term in terms)
        for heading, value in cells.items():
            if not all(term in heading for term in normalized_terms):
                continue
            parsed = _optional_amount(value)
            if parsed is not None:
                return parsed
    return None


def _optional_number(value: str) -> Optional[float]:
    """Parse an optional numeric value without inventing zero for missing data."""
    if not value or value.strip() in {"-", "--", "—"}:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_sft18_detail(data: dict[str, Any]) -> dict[str, Any]:
    """Parse one SFT-18(Pur) detail row with AMC-name-wrapping detection.

    Schema (8 columns): SR. NO. | QUARTER | CLIENT ID | AMC NAME (CODE) | HOLDER FLAG | TOTAL PURCHASE AMOUNT | TOTAL SALES VALUE | STATUS

    The AMC name can wrap across col_3, col_4, col_5 ... shifting holder flag
    and amounts rightward.  Strategy: scan forward from col_4 until finding a
    known holder-flag token — every cell before it is part of the AMC name.
    This handles 1-, 2-, and 3+-part names uniformly.
    """
    holder_flags = {"First", "Second", "Joint", "Single", "Either or Survivor"}

    client_id = str(data.get("col_2", "")).strip()
    if client_id == "None":
        client_id = ""

    quarter = str(data.get("col_1", "")).strip()
    if quarter == "None":
        quarter = ""

    # col_3 is always the first AMC fragment; col_4 onward may be more.
    amc_parts = [str(data.get("col_3", "")).strip()]
    holder_col: int | None = None
    for col_idx in range(4, 10):
        val = str(data.get(f"col_{col_idx}", "")).strip()
        if not val or val == "None":
            break
        if val in holder_flags:
            holder_col = col_idx
            break
        amc_parts.append(val)

    amc_name = " ".join(p for p in amc_parts if p and p != "None")

    # Columns immediately after the holder flag are PURCHASE, SALES, STATUS
    if holder_col is not None:
        purchase_raw = str(data.get(f"col_{holder_col + 1}", "")).strip()
        sales_raw    = str(data.get(f"col_{holder_col + 2}", "")).strip()
        status       = str(data.get(f"col_{holder_col + 3}", "")).strip()
    else:
        # Fallback: no holder flag found — treat as no-wrap (fixed positions)
        purchase_raw = str(data.get("col_5", "")).strip()
        sales_raw    = str(data.get("col_6", "")).strip()
        status       = str(data.get("col_7", "")).strip()

    if status == "None":
        status = ""

    return {
        "amc_name": amc_name,
        "client_id": client_id,
        "quarter": quarter,
        "purchase_amount": _parse_amount(purchase_raw),
        "sale_amount": _parse_amount(sales_raw),
        "status": status,
    }


def _parse_sft17_detail(data: dict[str, Any]) -> dict[str, Any]:
    """Parse one SFT-17(Pur) detail row (listed equity, no AMC column).

    Schema (7 columns): SR. NO. | QUARTER | CLIENT ID | HOLDER FLAG | MARKET PURCHASE | MARKET SALES | STATUS
    """
    client_id = str(data.get("col_2", "")).strip()
    status = str(data.get("col_6", "")).strip()
    quarter = str(data.get("col_1", "")).strip()

    if client_id == "None":
        client_id = ""
    if status == "None":
        status = ""
    if quarter == "None":
        quarter = ""

    return {
        "amc_name": "",
        "client_id": client_id,
        "quarter": quarter,
        "purchase_amount": _parse_amount(data.get("col_4", "0")),
        "sale_amount": _parse_amount(data.get("col_5", "0")),
        "status": status,
    }


def _extract_capital_gain_ledger(ais: dict, tis: dict) -> tuple[list[dict], list[dict]]:
    """Extract flat, per-transaction capital-gains rows from the AIS.

    Returns two simple lists — ``sales`` and ``purchases`` — each a list of
    plain dicts carrying the per-scrip/per-transaction fields the Capital
    Gains tab needs (ISIN, name, quantity, sale price, total sale value,
    cost, FMV, date for sales; AMC name, period, amount, account id for
    purchases).  No evidence/granularity/control abstraction — the AIS is
    the single source, each detail row becomes one entry, and the frontend
    maps them directly onto the schedule.

    Recognised AIS detail tables:
      * SFT-17-LES / SFT-18-EMF sale tables  → sales[]
      * SFT-17(Pur) / SFT-18(Pur) purchase tables → purchases[]
      * SFT-012 sale of immovable property → sales[] (immovable)
      * SFT-012(P) purchase of immovable property → purchases[]
      * VDA (194S) rows without an AIS table arrive via the income-head
        bridge in the frontend; nothing to do here.
    """
    sales: list[dict] = []
    purchases: list[dict] = []
    financial_year = str(ais.get("metadata", {}).get("financial_year", ""))
    download_id = str(ais.get("metadata", {}).get("download_id", ""))

    for income_head in ais.get("income_heads", {}).values():
        for entry in income_head.get("entries", []):
            category = canonical_category(str(entry.get("category", "")).strip())
            if category not in TRANSACTION_LEVEL_CATEGORIES:
                continue
            source = str(entry.get("information_source", ""))
            code = str(entry.get("information_code", ""))
            pan = str(entry.get("institution_pan", "")) or extract_pan(source)
            summary_sr = int(entry.get("sr_no", 0) or 0)
            headers = [str(h) for h in entry.get("detail_header", [])]
            # Collapse internal whitespace so 'DATE OF SALE/ TRANSFER' (space
            # after the slash) matches 'DATE OF SALE/TRANSFER'.
            headers_upper = re.sub(r"\s+", " ", " ".join(headers)).upper().replace("/ ", "/")
            is_immovable_property_table = "PROPERTY ADDRESS" in headers_upper
            is_sale_table = (
                not is_immovable_property_table
                and "DATE OF SALE/TRANSFER" in headers_upper
                and "SECURITY NAME" in headers_upper
                and "SALES CONSIDERATION" in headers_upper
            )
            is_purchase_table = (
                not is_immovable_property_table
                and (
                    ("AMC NAME" in headers_upper and "TOTAL PURCHASE AMOUNT" in headers_upper)
                    or "MARKET PURCHASE" in headers_upper
                )
            )
            details = entry.get("details", [])

            # Summary-only entry (no per-scrip detail table).  Emit one
            # aggregate sale row so the reconciled total still surfaces in
            # the Capital Gains tab even when the AIS carries only a total.
            if not details:
                summary_amount = _parse_amount(entry.get("amount", 0))
                if summary_amount <= 0:
                    continue
                row = {
                    "id": _stable_source_id("AIS", financial_year, download_id, code, summary_sr, "SUMMARY"),
                    "information_code": code,
                    "reporting_source": source,
                    "reporting_entity_pan": pan,
                    "security_name": "",
                    "security_identifier": "",
                    "quantity": None,
                    "sale_price_per_unit": None,
                    "total_sale_value": summary_amount,
                    "acquisition_cost": None,
                    "fair_market_value": None,
                    "unit_fmv": None,
                    "transaction_date": "",
                    "asset_type": "",
                    "security_class": "",
                    "status": "",
                    "is_summary": True,
                }
                if "purchase" in category:
                    purchases.append({**row, "period": "", "account_id": ""})
                else:
                    sales.append(row)
                continue

            for detail in details:
                data = detail.get("data", {})
                detail_sr = int(detail.get("sr_no", 0) or 0)

                if is_immovable_property_table:
                    cells, _ = _detail_cells(headers, detail)
                    property_address = _first_semantic_value(cells, "PROPERTY", "ADDRESS")
                    property_type = _first_semantic_value(cells, "PROPERTY", "TYPE")
                    transaction_type = _first_semantic_value(cells, "TRANSACTION", "TYPE")
                    # SFT-012(P) has a "TRANSACTION RELATION" column.
                    transaction_relation = _first_semantic_value(cells, "TRANSACTION", "RELATION")
                    transaction_date = _first_semantic_value(cells, "TRANSACTION", "DATE")
                    transaction_amount = _first_amount(cells, (
                        ("TRANSACTION", "AMOUNT", "ASSIGNED"),
                        ("TRANSACTION", "AMOUNT"),
                    ))
                    stamp_duty_value = _first_amount(cells, (
                        ("VALUE", "PROPERTY", "STAMP", "DUTY"),
                        ("VALUE", "STAMP", "DUTY"),
                    ))
                    amount_assigned = _first_amount(cells, (
                        ("TRANSACTION", "AMOUNT", "ASSIGNED"),
                    ))
                    reported_on = _first_semantic_value(cells, "REPORTED", "ON")
                    status = _first_semantic_value(cells, "STATUS")
                    party_count_raw = _first_semantic_value(cells, "PARTY")
                    is_purchase = "purchase" in category
                    # The sale-amount for CG purposes is the transaction
                    # amount assigned to the assessee (per-party share when
                    # multiple parties are involved).
                    sale_value = amount_assigned or transaction_amount or 0.0
                    if sale_value <= 0:
                        continue
                    base = {
                        "id": _stable_source_id(
                            "AIS", financial_year, download_id, code,
                            summary_sr, detail_sr,
                            "IMMPUR" if is_purchase else "IMMSAL",
                            property_address, transaction_date, sale_value,
                        ),
                        "information_code": code,
                        "reporting_source": source,
                        "reporting_entity_pan": pan,
                        "security_name": property_address or source,
                        "transaction_date": transaction_date,
                        "asset_type": "Immovable Property",
                        "security_class": property_type,
                        "status": status,
                        "is_summary": False,
                        "property_address": property_address,
                        "property_type": property_type,
                        "transaction_type": transaction_type,
                        "transaction_amount": transaction_amount,
                        "stamp_duty_value": stamp_duty_value,
                        "transaction_amount_assigned": amount_assigned,
                        "reported_on": reported_on,
                        "party_count": _optional_number(party_count_raw),
                    }
                    if is_purchase:
                        purchases.append({
                            **base,
                            "purchase_amount": sale_value,
                            "transaction_relation": transaction_relation,
                        })
                    else:
                        sales.append({
                            **base,
                            "security_identifier": "",
                            "quantity": None,
                            "sale_price_per_unit": None,
                            "total_sale_value": sale_value,
                            "acquisition_cost": None,
                            "fair_market_value": stamp_duty_value,
                            "unit_fmv": None,
                        })
                    continue

                if is_sale_table:
                    cells, _ = _detail_cells(headers, detail)
                    security_value = _first_semantic_value(cells, "SECURITY", "NAME")
                    identifier_match = re.search(r"\b(IN[EA][A-Z0-9]{9})\b", security_value, re.IGNORECASE)
                    security_identifier = identifier_match.group(1).upper() if identifier_match else ""
                    security_name = re.sub(
                        r"\s*\(?IN[EA][A-Z0-9]{9}\)?\s*$",
                        "",
                        security_value,
                        flags=re.IGNORECASE,
                    ).strip()
                    transaction_date = _first_semantic_value(cells, "DATE", "SALE")
                    consideration = _first_amount(cells, (("SALES", "CONSIDERATION"),))
                    acquisition_cost = _first_amount(cells, (("COST", "ACQUISITION"),))
                    fair_market_value = _first_amount(cells, (("FAIR", "MARKET", "VALUE"),))
                    unit_fmv = _first_amount(cells, (("UNIT", "FMV"),))
                    sale_price = _first_amount(cells, (("SALE", "PRICE", "UNIT"),))
                    quantity = _optional_number(_first_semantic_value(cells, "QUANTITY"))
                    asset_type = _first_semantic_value(cells, "ASSET", "TYPE")
                    security_class = _first_semantic_value(cells, "SECURITY", "CLASS")
                    status = _first_semantic_value(cells, "STATUS")
                    if consideration is None:
                        continue
                    sales.append({
                        "id": _stable_source_id("AIS", financial_year, download_id, code, summary_sr, detail_sr, "SALE", security_identifier, transaction_date, consideration),
                        "information_code": code,
                        "reporting_source": source,
                        "reporting_entity_pan": pan,
                        "security_name": security_name,
                        "security_identifier": security_identifier,
                        "quantity": quantity,
                        "sale_price_per_unit": sale_price,
                        "total_sale_value": consideration,
                        "acquisition_cost": acquisition_cost,
                        "fair_market_value": fair_market_value,
                        "unit_fmv": unit_fmv,
                        "transaction_date": transaction_date,
                        "asset_type": asset_type,
                        "security_class": security_class,
                        "status": status,
                        "is_summary": False,
                    })
                    continue

                if is_purchase_table:
                    parsed = _parse_sft18_detail(data) if "AMC NAME" in headers_upper else _parse_sft17_detail(data)
                    purchase_amount = parsed["purchase_amount"]
                    sale_amount = parsed.get("sale_amount", 0) or 0
                    if purchase_amount and purchase_amount > 0:
                        purchases.append({
                            "id": _stable_source_id("AIS", financial_year, download_id, code, summary_sr, detail_sr, "PUR", parsed["client_id"], purchase_amount),
                            "information_code": code,
                            "reporting_source": source,
                            "reporting_entity_pan": pan,
                            "security_name": parsed["amc_name"],
                            "account_id": parsed["client_id"],
                            "period": parsed.get("quarter", ""),
                            "purchase_amount": purchase_amount,
                            "status": parsed["status"],
                            "is_summary": False,
                        })
                    # SFT-18(Pur) / SFT-17(Pur) tables also carry a "TOTAL SALES
                    # VALUE" / "MARKET SALES" column representing actual sales
                    # of securities/MF units by the assessee.  Emit those as
                    # sale entries so the Capital Gains tab can compute gains.
                    if sale_amount and sale_amount > 0:
                        sales.append({
                            "id": _stable_source_id("AIS", financial_year, download_id, code, summary_sr, detail_sr, "SALE", parsed["client_id"], sale_amount),
                            "information_code": code,
                            "reporting_source": source,
                            "reporting_entity_pan": pan,
                            "security_name": parsed["amc_name"],
                            "security_identifier": "",
                            "quantity": None,
                            "sale_price_per_unit": None,
                            "total_sale_value": sale_amount,
                            "acquisition_cost": None,
                            "fair_market_value": None,
                            "unit_fmv": None,
                            "transaction_date": "",
                            "asset_type": "",
                            "security_class": "",
                            "status": parsed["status"],
                            "is_summary": False,
                        })
                    continue

                # SFT-012 immovable property (sale/purchase) — only a summary
                # amount is available; emit a single aggregate row.
                summary_amount = _parse_amount(entry.get("amount", 0))
                if summary_amount <= 0:
                    continue
                is_purchase = "purchase" in category
                row = {
                    "id": _stable_source_id("AIS", financial_year, download_id, code, summary_sr, "IMM" + ("PUR" if is_purchase else "SAL")),
                    "information_code": code,
                    "reporting_source": source,
                    "reporting_entity_pan": pan,
                    "security_name": source,
                    "transaction_date": "",
                    "status": "",
                    "is_summary": True,
                    "total_sale_value" if not is_purchase else "purchase_amount": summary_amount,
                }
                (purchases if is_purchase else sales).append(row)

    return sales, purchases


@dataclass
class Entry:
    category: str
    source: str           # normalized
    raw_source: str        # original
    amount: float
    tds: float = 0.0
    section: str = ""
    description: str = ""
    income_head: str = ""
    pan: str = ""
    tan: str = ""
    credit_type: Optional[CreditType] = None

    def __post_init__(self) -> None:
        """Canonicalize the category so every Entry built from any extractor
        uses the same label, regardless of the source PDF's wording.

        This is the single chokepoint that prevents the same income from
        appearing as two entries when AIS and TIS label it differently
        (e.g. ``interest income (sft-016) – savings`` vs ``interest from
        savings bank``).  ``Entry.key`` and ``CATEGORY_TO_INCOME_HEAD``
        both consume ``self.category``, so canonicalizing here makes every
        downstream match consistent.
        """
        if self.category:
            self.category = canonical_category(self.category)
        # Keep income_head consistent with the canonical category if the
        # caller didn't set a meaningful head (some callers pass "" and
        # rely on the engine to fill it later).
        if self.income_head and self.income_head not in (
            CATEGORY_TO_INCOME_HEAD.get(self.category, self.income_head),
        ):
            # Re-derive from the canonical category when the caller's head
            # was set against the pre-canonical label.
            mapped = CATEGORY_TO_INCOME_HEAD.get(self.category)
            if mapped:
                self.income_head = mapped

    @property
    def key(self) -> str:
        """Stable cross-document identity for this income/credit entry.

        Evidence-based design (61-client corpus): AIS SFT entries key on a
        PAN, 26AS Part I rows key on a TAN (never a PAN), and TIS SFT
        entries key on a PAN — but the PAN and TAN differ for the same
        deductor (e.g. SBI: PAN AAACS8577K in SFT, TAN MUMS89569E in 26AS).
        So PAN/TAN CANNOT be the identity.  The normalized deductor NAME is
        the only stable bridge, so it is the primary key.

        For transaction-level capital-gains categories, the same broker
        reports multiple distinct funds, so the full source description
        (broker + fund name) is preserved as the transaction identity.

        Matching priority at the engine level: section → amount → name/PAN.
        The key encodes (canonical_category, identity); sections_compatible
        and the amount-based validation gate actual merges.
        """
        category = canonical_category(self.category)
        identity = normalize_source_identity(category, self.source)
        if category in TRANSACTION_LEVEL_CATEGORIES:
            # A reporting entity can report multiple distinct funds/assets.
            # Preserve the full source description as transaction identity.
            return f"{category}|transaction:{identity}"
        # Non-transaction categories: identity is the normalized deductor
        # name.  PAN/TAN are carried as metadata, not as the key, because
        # they differ across documents for the same deductor.
        return f"{category}|name:{identity}"


def _extract_ais(ais: dict) -> list[Entry]:
    entries: list[Entry] = []
    for ih_name, ih_data in ais.get("income_heads", {}).items():
        for e in ih_data.get("entries", []):
            cat = e.get("category", "").lower()
            raw = e.get("information_source", "")
            src = normalize_name(raw)
            pan = e.get("institution_pan", "") or extract_pan(raw)

            # Edge case: source normalizes to empty (e.g., just "(AAAAT0875H.AC997)")
            if not src:
                desc = e.get("information_description", "")
                desc_clean = re.sub(
                    r'interest\s+income\s*\(?sft[^)]*\)?\s*(savings|deposit)?\s*',
                    '', normalize_name(desc)
                ).strip()
                if desc_clean:
                    src = desc_clean
                    raw = f"{desc_clean} ({pan})" if pan else desc_clean

            if src:
                entries.append(Entry(
                    category=cat, source=src, raw_source=raw,
                    amount=_parse_amount(e.get("amount", 0)),
                    section=e.get("information_code", ""),
                    description=e.get("information_description", ""),
                    income_head=ih_name, pan=pan,
                ))
    return entries


def _tis_accepted_totals(tis: dict) -> dict[str, float]:
    """Return authoritative system-deduplicated TIS totals by category."""
    totals: dict[str, float] = {}
    for income_head in tis.get("income_heads", {}).values():
        for entry in income_head.get("entries", []):
            category = str(entry.get("category", "")).strip().lower()
            if category and "accepted_by_taxpayer" in entry:
                totals[category] = totals.get(category, 0.0) + _parse_amount(
                    entry.get("accepted_by_taxpayer")
                )
    return totals


def _extract_tis(tis: dict) -> list[Entry]:
    entries: list[Entry] = []
    for ih_name, ih_data in tis.get("income_heads", {}).items():
        for e in ih_data.get("entries", []):
            cat = e.get("category", "").lower()
            details = e.get("details", [])
            detail_entries: list[Entry] = []
            for d in details:
                raw = d.get("information_source", "")
                src = normalize_name(raw)
                pan = d.get("institution_pan", "") or extract_pan(raw)
                if src:
                    detail_entries.append(Entry(
                        category=cat, source=src, raw_source=raw,
                        amount=_parse_amount(d.get("accepted_by_taxpayer", "0")),
                        section=d.get("part", ""),
                        description=d.get("information_description", ""),
                        income_head=ih_name, pan=pan,
                    ))

            entries.extend(detail_entries)
    return entries


def _extract_26as(as26: dict) -> list[Entry]:
    entries: list[Entry] = []

    for part_id in ["I", "VI"]:
        part = as26.get("parts", {}).get(part_id, {})
        if part.get("empty", True):
            continue
        for row in part.get("rows", []):
            raw = row.get("Name of Deductor", row.get("Name of Collector", ""))
            src = normalize_name(raw)
            if not src:
                continue
            # Use deductor-level total, not per-transaction details
            amt_field = "Total Amount Paid/Credited" if part_id == "I" else "Total Amount Paid/Debited"
            tds_field = "Total Tax Deducted" if part_id == "I" else "Total Tax Collected"
            amt = _parse_amount(row.get(amt_field, "0"))
            tds = _parse_amount(row.get(tds_field, "0"))

            # Determine category from section in detail rows
            section = ""
            cat = "other"
            for d in row.get("_details", []):
                sec = d.get("Section", "")
                if sec:
                    section = sec
                    cat = SECTION_TO_CATEGORY.get(sec.strip().upper(), "other")
                    break

            # R1 (CBDT compliance): Part VI is TCS.  Route TCS rows to the
            # ``tcs credit`` bucket (a tax-credit income head), NOT to the
            # section's default business-receipts category.  26AS cannot
            # determine the collectee's business status, so the safe default
            # is the dedicated credit bucket rather than PGBP income.
            is_tcs_part = (part_id == "VI")
            if is_tcs_part:
                cat = "tcs credit"

            entries.append(Entry(
                category=cat, source=src, raw_source=raw,
                amount=amt, tds=tds,
                section=section,
                description=f"TDS/TCS u/s {section}" if section else "TDS/TCS",
                income_head=CATEGORY_TO_INCOME_HEAD.get(cat, "Income from Other Sources"),
                pan=str(row.get("PAN of Deductor", row.get("PAN of Collector", "")) or "").strip().upper(),
                tan=str(row.get("TAN of Deductor", row.get("TAN of Collector", "")) or "").strip().upper(),
                credit_type=CreditType.TDS if part_id == "I" else CreditType.TCS,
            ))

    # Part IV: Property Seller
    part_iv = as26.get("parts", {}).get("IV", {})
    if not part_iv.get("empty", True):
        for row in part_iv.get("rows", []):
            raw = row.get("Name of Deductor", "")
            src = normalize_name(raw)
            if src:
                entries.append(Entry(
                    category="sale of land or building", source=src, raw_source=raw,
                    amount=_parse_amount(row.get("Total Transaction Amount", "0")),
                    section="194IA", description="Sale of property",
                    income_head="Capital Gains",
                    pan=row.get("PAN of Deductor", ""),
                ))

    # Part VII: Refunds
    part_vii = as26.get("parts", {}).get("VII", {})
    if not part_vii.get("empty", True):
        for row in part_vii.get("rows", []):
            entries.append(Entry(
                category="refund",
                source=f"refund_{row.get('Assessment Year', '')}",
                raw_source=f"Refund AY {row.get('Assessment Year', '')}",
                amount=_parse_amount(row.get("Amount of Refund", "0")),
                description=f"Refund: {row.get('Nature of Refund', '')}",
                income_head="Refund",
            ))

    return entries


def _collapse_within_map_by_name(
    m: dict[str, list[Entry]],
) -> None:
    """Collapse entries within a single map that share category + identity.

    A single document (especially TIS) can produce two rows for the same
    reporting entity under different keys: one keyed by PAN/TAN
    (``|id:AAACS8577K``) and one keyed by name only (``|name:state bank of
    india``) when the detail row carries no PAN.  The cross-document
    matchers only merge ACROSS maps, so without this collapse the same
    entity appears as two separate entries in the final reconciled list.

    This merges the name-only-keyed rows into the id-keyed rows when both
    share the same canonical category and normalized source identity.
    """
    # Build (category, identity) -> list of keys, preferring id-keyed over name-keyed.
    by_identity: dict[tuple[str, str], list[str]] = {}
    for key, grouped in m.items():
        if not grouped:
            continue
        first = grouped[0]
        if first.category in TRANSACTION_LEVEL_CATEGORIES:
            continue
        identity = normalize_source_identity(first.category, first.source)
        if not identity:
            continue
        by_identity.setdefault((first.category, identity), []).append(key)

    for (cat, identity), keys in by_identity.items():
        if len(keys) < 2:
            continue
        # Only collapse when one entry is a no-amount "book" row (e.g. the
        # TIS TDS detail with amount 0 and no PAN) and another is a real
        # income row (amount > 0, has PAN/TAN).  This avoids merging two
        # genuinely-distinct AIS line items (e.g. SFT-016 interest 261841
        # and 194A interest 261841) which would double-count the income.
        real_keys = [k for k in keys if max((e.amount for e in m[k]), default=0.0) > 0]
        book_keys = [k for k in keys if max((e.amount for e in m[k]), default=0.0) == 0]
        if not real_keys or not book_keys:
            continue
        preferred = real_keys[0]
        for k in keys:
            if k == preferred:
                continue
            m.setdefault(preferred, []).extend(m.pop(k))


def _pan_cross_match(
    map_a: dict[str, list[Entry]], map_b: dict[str, list[Entry]],
    entries_a: list[Entry], entries_b: list[Entry],
) -> None:
    """Merge entries from two documents by PAN when source names don't match.

    If an entry in map_a has a PAN and an entry in map_b has the same PAN
    in the same category but different normalized source names, merge them
    under the entry from map_a's key (which typically has a better name).
    """
    for e_a in entries_a:
        if e_a.category in TRANSACTION_LEVEL_CATEGORIES:
            continue
        if not e_a.pan or e_a.key not in map_a:
            continue
        for e_b in entries_b:
            if e_b.category in TRANSACTION_LEVEL_CATEGORIES:
                continue
            if not e_b.pan or e_b.pan != e_a.pan:
                continue
            if e_b.category != e_a.category or not sections_compatible(e_a, e_b):
                continue
            if e_b.key == e_a.key:
                continue  # already matched
            # Found: same PAN, same category, different source names
            # Merge e_b's entries under e_a's key
            b_key = e_b.key
            if b_key in map_b:
                merged = map_b.pop(b_key, [])
                map_b.setdefault(e_a.key, []).extend(merged)
            break

def _name_cross_match(
    map_a: dict[str, list[Entry]], map_b: dict[str, list[Entry]],
    entries_a: list[Entry], entries_b: list[Entry],
) -> None:
    """Merge exact category-aware fallback names using indexed lookup."""
    del entries_a
    index_b: dict[tuple[str, str], str] = {}
    for entry in entries_b:
        if entry.key not in map_b:
            continue
        identity = normalize_source_identity(entry.category, entry.source)
        if identity:
            index_b.setdefault((entry.category, identity), entry.key)

    for key_a, grouped_entries in list(map_a.items()):
        if not grouped_entries:
            continue
        entry_a = grouped_entries[0]
        if entry_a.category in TRANSACTION_LEVEL_CATEGORIES:
            continue
        identity_a = normalize_source_identity(entry_a.category, entry_a.source)
        key_b = index_b.get((entry_a.category, identity_a))
        if not key_b or key_b == key_a or key_b not in map_b:
            continue
        candidate = map_b[key_b][0]
        if not sections_compatible(entry_a, candidate):
            continue
        map_b.setdefault(key_a, []).extend(map_b.pop(key_b))


@dataclass
class ReconciledEntry:
    category: str
    source: str                    # best display name (TIS > AIS > 26AS)
    description: str
    section: str
    income_head: str
    final_amount: float
    tis_amount: float = 0.0
    ais_amount: float = 0.0
    as26_amount: float = 0.0
    as26_tds: float = 0.0
    as26_tcs: float = 0.0
    credit_type: Optional[CreditType] = None
    credit_selected_source: Optional[SelectedSource] = None
    credit_selection_reason: str = ""
    selected_source: SelectedSource = SelectedSource.AIS
    selection_reason: str = "AIS_INCOME_FALLBACK"
    pan: str = ""
    tan: str = ""
    source_id: str = ""
    present_in: dict[str, bool] = field(default_factory=lambda: {"tis": False, "ais": False, "as26": False})
    has_discrepancy: bool = False
    discrepancy_detail: str = ""


def reconcile(ais_data: dict, tis_data: dict, as26_data: dict, prefill_data: dict | None = None) -> dict:
    ais_entries = _extract_ais(ais_data)
    tis_entries = _extract_tis(tis_data)
    as26_entries = _extract_26as(as26_data)
    tis_accepted_totals = _tis_accepted_totals(tis_data)
    capital_gain_sales, capital_gain_purchases = _extract_capital_gain_ledger(ais_data, tis_data)

    # Index by key
    ais_map: dict[str, list[Entry]] = {}
    tis_map: dict[str, list[Entry]] = {}
    as26_map: dict[str, list[Entry]] = {}

    for e in ais_entries:
        ais_map.setdefault(e.key, []).append(e)
    for e in tis_entries:
        tis_map.setdefault(e.key, []).append(e)
    for e in as26_entries:
        as26_map.setdefault(e.key, []).append(e)

    # === Within-map collapse by name ===
    # A single document (especially TIS) can produce two rows for the same
    # entity under different keys (one id-keyed, one name-keyed).  Collapse
    # them before cross-document matching so the entity isn't duplicated.
    _collapse_within_map_by_name(ais_map)
    _collapse_within_map_by_name(tis_map)
    _collapse_within_map_by_name(as26_map)

    # === PAN-based cross-matching for unmatched entries ===
    # If entry A from doc1 and entry B from doc2 share category + PAN but
    # have different normalized names, merge them under a single key.
    _pan_cross_match(ais_map, tis_map, ais_entries, tis_entries)
    _pan_cross_match(ais_map, as26_map, ais_entries, as26_entries)
    _pan_cross_match(tis_map, as26_map, tis_entries, as26_entries)

    # Identifier-free AIS/TIS salary labels commonly include document-specific
    # prefixes (for example "salary received"). Match only when the controlled,
    # category-aware fallback names are exactly equal.
    _name_cross_match(ais_map, tis_map, ais_entries, tis_entries)
    _name_cross_match(ais_map, as26_map, ais_entries, as26_entries)
    _name_cross_match(tis_map, as26_map, tis_entries, as26_entries)

    all_keys = set(ais_map.keys()) | set(tis_map.keys()) | set(as26_map.keys())

    # Build reconciled entries
    reconciled: list[ReconciledEntry] = []
    unmatched_tis: list[Entry] = []
    unmatched_ais: list[Entry] = []
    unmatched_as26: list[Entry] = []

    for key in sorted(all_keys):
        a = ais_map.get(key, [])
        t = tis_map.get(key, [])
        as_list = as26_map.get(key, [])

        # AIS total: use max (not sum) because AIS reports the same income
        # under multiple codes (SFT-016 income + TDS-194A book entry for the
        # same deductor); summing would double-count the income in the
        # displayed ais_amount and trigger a spurious discrepancy.  The
        # canonical AIS income for a deductor is the single largest figure.
        ais_total = max((e.amount for e in a), default=0.0)
        # TIS total: use sum to preserve the full detail total so the
        # category-control discrepancy (accepted overview vs detail sum) is
        # surfaced correctly (e.g. dividend accepted 514 vs details 528).
        tis_total = sum(e.amount for e in t)
        # 26AS amount: deductor-level total already aggregated by the
        # extractor; max is correct (one canonical amount per deductor).
        as26_total = max((e.amount for e in as_list), default=0.0)
        as26_tds_total = sum(e.tds for e in as_list if e.credit_type is CreditType.TDS)
        as26_tcs_total = sum(e.tds for e in as_list if e.credit_type is CreditType.TCS)

        has_tis = bool(t)
        has_ais = bool(a)
        has_as26 = bool(as_list)

        # Best metadata
        best = (t or a or as_list)[0]
        best_source = best.raw_source

        # Section: prefer 26AS section, then AIS code
        section = (as_list[0].section if as_list else best.section)

        # Income head
        ih = best.income_head or CATEGORY_TO_INCOME_HEAD.get(best.category, "Income from Other Sources")

        # Income/transaction values use TIS, then AIS, then 26AS fallback.
        # Tax credits themselves always come from 26AS fields below.
        if has_tis:
            final = tis_total
            selected_source = SelectedSource.TIS
            selection_reason = "TIS_ACCEPTED_INCOME"
        elif has_ais:
            final = ais_total
            selected_source = SelectedSource.AIS
            selection_reason = "AIS_INCOME_FALLBACK"
        else:
            final = 0.0 if as_list and any(entry.credit_type for entry in as_list) else as26_total
            selected_source = SelectedSource.FORM_26AS
            selection_reason = (
                "26AS_CREDIT_EVIDENCE_ONLY"
                if as_list and any(entry.credit_type for entry in as_list)
                else "26AS_INCOME_FALLBACK"
            )
        credit_types = {entry.credit_type for entry in as_list if entry.credit_type is not None}
        credit_type = next(iter(credit_types)) if len(credit_types) == 1 else None

        rec = ReconciledEntry(
            category=best.category,
            source=best_source,
            description=best.description,
            section=section,
            income_head=ih,
            final_amount=final,
            tis_amount=tis_total,
            ais_amount=ais_total,
            as26_amount=as26_total,
            as26_tds=as26_tds_total,
            as26_tcs=as26_tcs_total,
            credit_type=credit_type,
            credit_selected_source=(SelectedSource.FORM_26AS if credit_type else None),
            credit_selection_reason=("26AS_TAX_CREDIT" if credit_type else ""),
            selected_source=selected_source,
            selection_reason=selection_reason,
            pan=next((e.pan for e in as_list + t + a if e.pan), ""),
            tan=next((e.tan for e in as_list + t + a if e.tan), ""),
            source_id=key,
            present_in={"tis": has_tis, "ais": has_ais, "as26": has_as26},
        )

        # Compare every available source pair; do not hide later mismatches.
        comparisons: list[str] = []
        source_amounts = [
            ("TIS", has_tis, tis_total),
            ("AIS", has_ais, ais_total),
            ("26AS", has_as26, as26_total),
        ]
        for left_index, (left_name, left_present, left_amount) in enumerate(source_amounts):
            if not left_present:
                continue
            for right_name, right_present, right_amount in source_amounts[left_index + 1:]:
                if right_present and abs(left_amount - right_amount) > 1.0:
                    comparisons.append(
                        f"{left_name}={left_amount:,.2f} vs {right_name}={right_amount:,.2f}"
                    )
        rec.has_discrepancy = bool(comparisons)
        rec.discrepancy_detail = "; ".join(comparisons)

        reconciled.append(rec)

    # Unmatched (present in only one document)
    for key in sorted(all_keys):
        has_tis = key in tis_map
        has_ais = key in ais_map
        has_as26 = key in as26_map
        if has_tis and not has_ais and not has_as26:
            unmatched_tis.extend(tis_map[key])
        if has_ais and not has_tis and not has_as26:
            unmatched_ais.extend(ais_map[key])
        if has_as26 and not has_tis and not has_ais:
            unmatched_as26.extend(as26_map[key])

    # TIS accepted totals are system-deduplicated category controls. Preserve
    # every raw source amount unchanged. AIS/26AS-only representations in a
    # controlled category remain evidence but contribute no additional income.
    category_control_discrepancies: list[dict[str, object]] = []
    controlled_head_adjustments: dict[str, float] = {}
    for category, accepted_total in tis_accepted_totals.items():
        if category in TRANSACTION_LEVEL_CATEGORIES:
            continue
        category_rows = [row for row in reconciled if row.category == category]
        tis_rows = [row for row in category_rows if row.present_in["tis"]]
        if not tis_rows:
            continue
        detail_total = sum(row.tis_amount for row in tis_rows)
        for row in category_rows:
            if not row.present_in["tis"]:
                row.final_amount = 0.0
        income_head = tis_rows[0].income_head
        controlled_head_adjustments[income_head] = (
            controlled_head_adjustments.get(income_head, 0.0)
            + accepted_total - sum(row.final_amount for row in category_rows)
        )
        if abs(detail_total - accepted_total) > 0.01:
            category_control_discrepancies.append({
                "category": category,
                "tis_accepted_total": round(accepted_total, 2),
                "tis_detail_total": round(detail_total, 2),
                "difference": round(detail_total - accepted_total, 2),
            })

    # Group by income head
    by_head: dict[str, dict] = {}
    for rec in reconciled:
        ih = rec.income_head
        if ih not in by_head:
            by_head[ih] = {
                "income_head": ih, "total_final": 0.0,
                "total_tis": 0.0, "total_ais": 0.0, "total_as26": 0.0,
                "total_as26_tds": 0.0, "total_as26_tcs": 0.0,
                "discrepancy_count": 0, "entries": [],
            }
        g = by_head[ih]
        g["total_final"] += rec.final_amount
        g["total_tis"] += rec.tis_amount
        g["total_ais"] += rec.ais_amount
        g["total_as26"] += rec.as26_amount
        g["total_as26_tds"] += rec.as26_tds
        g["total_as26_tcs"] += rec.as26_tcs
        if rec.has_discrepancy:
            g["discrepancy_count"] += 1
        g["entries"].append(rec)

    def _entry_dict(e: Entry) -> dict:
        return {
            "category": e.category, "source": e.raw_source,
            "source_id": e.key,
            "amount": round(e.amount, 2), "tds": round(e.tds, 2),
            "section": e.section, "description": e.description,
            "income_head": e.income_head, "pan": e.pan, "tan": e.tan,
        }

    # === Prefill-TDS vs 26AS-TDS cross-check (R2) ===
    # Compare the Prefill's TDS entries (salary TDS + other TDS) against the
    # reconciled 26AS TDS entries.  Each prefill TDS entry that matches a 26AS
    # entry by TAN (+/- section) is reported as a duplicate-match (kept, 26AS
    # TAN authoritative); each prefill TDS entry with NO 26AS match is
    # flagged as "prefill-only" (the deductor isn't in 26AS — investigate).
    prefill_tds_discrepancies: list[dict[str, object]] = []
    prefill_tds_match_count = 0
    prefill_tds_only_count = 0
    if prefill_data:
        # Collect prefill TDS entries from both the salary and other-sources
        # sections of the prefill extraction.
        prefill_tds_entries: list[dict[str, object]] = []
        for src_list in (
            prefill_data.get("tds_salary_entries", []),
            prefill_data.get("tds_other_entries", []),
        ):
            for entry in src_list or []:
                prefill_tds_entries.append(entry)
        # Index reconciled 26AS TDS entries by uppercased TAN.
        as26_tds_by_tan: dict[str, list[ReconciledEntry]] = {}
        for rec in reconciled:
            if rec.credit_type is CreditType.TDS and rec.tan:
                as26_tds_by_tan.setdefault(rec.tan.upper(), []).append(rec)
        for pt in prefill_tds_entries:
            tan = str(pt.get("tan", "") or pt.get("deductor_tan", "") or "").strip().upper()
            amount = _parse_amount(pt.get("tds_amount", pt.get("tax_deducted", "0")))
            matched = as26_tds_by_tan.get(tan, []) if tan else []
            if matched:
                prefill_tds_match_count += 1
                as26_amt = sum(r.as26_tds for r in matched)
                if abs(as26_amt - amount) > 1.0:
                    prefill_tds_discrepancies.append({
                        "type": "amount_mismatch",
                        "tan": tan,
                        "deductor": pt.get("deductor_name", matched[0].source),
                        "prefill_tds": round(amount, 2),
                        "as26_tds": round(as26_amt, 2),
                        "difference": round(amount - as26_amt, 2),
                    })
            else:
                prefill_tds_only_count += 1
                prefill_tds_discrepancies.append({
                    "type": "prefill_only_no_26as_match",
                    "tan": tan or "(no TAN)",
                    "deductor": pt.get("deductor_name", "Unknown"),
                    "prefill_tds": round(amount, 2),
                })

    def _rec_dict(r: ReconciledEntry) -> dict:
        return {
            "category": r.category, "source": r.source,
            "source_id": r.source_id, "pan": r.pan, "tan": r.tan,
            "description": r.description, "section": r.section,
            "income_head": r.income_head,
            "amounts": {
                "tis": round(r.tis_amount, 2),
                "ais": round(r.ais_amount, 2),
                "as26": round(r.as26_amount, 2),
            },
            "as26_tds": round(r.as26_tds, 2),
            "as26_tcs": round(r.as26_tcs, 2),
            "credit_type": r.credit_type.value if r.credit_type else None,
            "credit_selected_source": r.credit_selected_source.value if r.credit_selected_source else None,
            "credit_selection_reason": r.credit_selection_reason,
            "selected_source": r.selected_source.value,
            "selection_reason": r.selection_reason,
            "final_amount": round(r.final_amount, 2),
            "present_in": r.present_in,
            "has_discrepancy": r.has_discrepancy,
            "discrepancy_detail": r.discrepancy_detail,
        }

    result = {
        "metadata": {
            "pan": (ais_data.get("metadata", {}).get("pan")
                    or tis_data.get("metadata", {}).get("pan")
                    or as26_data.get("header", {}).get("Permanent Account Number (PAN)", "")),
            "name": (ais_data.get("metadata", {}).get("name")
                     or tis_data.get("metadata", {}).get("name")
                     or as26_data.get("header", {}).get("Name of Assessee", "")),
            "financial_year": (ais_data.get("metadata", {}).get("financial_year")
                               or tis_data.get("metadata", {}).get("financial_year")
                               or as26_data.get("header", {}).get("Financial Year", "")),
        },
        "income_heads": {
            ih: {
                "income_head": g["income_head"],
                "total_final": round(g["total_final"] + controlled_head_adjustments.get(ih, 0.0), 2),
                "total_tis": round(g["total_tis"], 2),
                "total_ais": round(g["total_ais"], 2),
                "total_as26": round(g["total_as26"], 2),
                "total_as26_tds": round(g["total_as26_tds"], 2),
                "total_as26_tcs": round(g["total_as26_tcs"], 2),
                "discrepancy_count": g["discrepancy_count"],
                "entries": [_rec_dict(r) for r in g["entries"]],
            }
            for ih, g in sorted(by_head.items())
        },
        "category_controls": {
            category: round(amount, 2)
            for category, amount in sorted(tis_accepted_totals.items())
        },
        "category_control_discrepancies": category_control_discrepancies,
        "capital_gain_sales": capital_gain_sales,
        "capital_gain_purchases": capital_gain_purchases,
        "unmatched": {
            "tis_only": [_entry_dict(e) for e in unmatched_tis],
            "ais_only": [_entry_dict(e) for e in unmatched_ais],
            "as26_only": [_entry_dict(e) for e in unmatched_as26],
        },
        "summary": {
            "total_entries": len(reconciled),
            "total_final_income": round(
                sum(r.final_amount for r in reconciled)
                + sum(controlled_head_adjustments.values()),
                2,
            ),
            "total_discrepancies": sum(1 for r in reconciled if r.has_discrepancy),
            "matched_all_three": sum(1 for r in reconciled if all(r.present_in.values())),
            "matched_two": sum(1 for r in reconciled if sum(r.present_in.values()) == 2),
            "matched_one": sum(1 for r in reconciled if sum(r.present_in.values()) == 1),
            "unmatched_tis": len(unmatched_tis),
            "unmatched_ais": len(unmatched_ais),
            "unmatched_as26": len(unmatched_as26),
            "prefill_tds_matched": prefill_tds_match_count,
            "prefill_tds_only": prefill_tds_only_count,
        },
        "prefill_tds_discrepancies": prefill_tds_discrepancies,
    }

    return result


# ============================================================
# Convenience
# ============================================================

def reconcile_from_files(ais_path: str, tis_path: str, as26_path: str,
                         output_path: Optional[str] = None) -> dict:
    with open(ais_path, 'r', encoding='utf-8') as f:
        ais_data = json.load(f)
    with open(tis_path, 'r', encoding='utf-8') as f:
        tis_data = json.load(f)
    with open(as26_path, 'r', encoding='utf-8') as f:
        as26_data = json.load(f)
    result = reconcile(ais_data, tis_data, as26_data)
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    return result
