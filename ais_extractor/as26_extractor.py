"""
26AS PDF Extractor using pdfplumber table extraction.

Each 26AS PDF renders each Part as a single pdfplumber table containing
mixed summary/detail rows. The PART marker text (e.g., "PART-I - Details...")
appears outside the table as standalone text. We:

1. Extract all tables via pdfplumber
2. Identify data tables (skip metadata, legends, section descriptions)
3. Determine which PART each table belongs to via its column signature
4. Walk rows to build Deductor→Detail hierarchy

Output shape mirrors the existing TXT parser format for frontend interchangeability.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional


# ============================================================
# Part Metadata (from TXT parser)
# ============================================================

PART_META = {
    "I":    {"title": "TDS - Salary / Professional / Interest / VDA",               "credit": True},
    "II":   {"title": "TDS on Interest (15G/15H - No TDS Deducted)",                "credit": True},
    "III":  {"title": "TDS on Winnings / Benefits / VDA (Tax Paid Before Release)", "credit": True},
    "IV":   {"title": "TDS u/s 194IA/IB/M/S (Seller of Property / VDA)",            "credit": True},
    "V":    {"title": "26QE - Seller of Virtual Digital Asset",                      "credit": True},
    "VI":   {"title": "TCS - Tax Collected at Source",                               "credit": True},
    "VII":  {"title": "Refunds Paid",                                                "credit": False},
    "VIII": {"title": "TDS u/s 194IA/IB/M/S (Buyer of Property / VDA)",             "credit": False},
    "IX":   {"title": "26QE - Buyer of Virtual Digital Asset",                       "credit": False},
    "X":    {"title": "TDS/TCS Defaults (Processing of Statements)",                 "credit": False},
}

# ============================================================
# Column signatures per part (used to identify which part a table belongs to)
# ============================================================

# Summary column signatures (non-empty column names ordered)
_SUMMARY_SIG = {
    # (part, num_columns, unique_keyword_in_header)
    "I":    (9, ["Name of Deductor", "TAN of Deductor", "Total Tax Deducted"]),
    "II":   (8, ["Name of Deductor", "TAN of Deductor", "Total Tax Deducted", "15G", "15H"]),
    "III":  (6, ["Name of Deductor", "TAN of Deductor"]),
    "IV":   (8, ["Acknowledgement", "Name of Deductor", "PAN of Deductor", "Total Transaction"]),
    "V":    (7, ["Acknowledgement", "Name of Buyer", "PAN of Buyer", "Total Transaction"]),
    "VI":   (9, ["Name of Collector", "TAN of Collector", "Total Tax Collected"]),
    "VII":  (9, ["Assessment Year", "Mode", "Refund Issued", "Nature of Refund"]),
    "VIII": (9, ["Acknowledgement", "Name Of Deductee", "PAN of Deductee", "Total Transaction"]),
    "IX":   (8, ["Acknowledgement", "Name of Seller", "PAN of Seller", "Total Transaction"]),
    "X":    (9, ["Financial Year", "Short Payment", "Short Deduction"]),
}

# Summary output column names (what we map data to)
_SUMMARY_COLS = {
    "I":    ["Name of Deductor", "TAN of Deductor", "Total Amount Paid/Credited",
             "Total Tax Deducted", "Total TDS Deposited"],
    "II":   ["Name of Deductor", "TAN of Deductor", "Total Amount Paid/Credited",
             "Total Tax Deducted", "Total TDS Deposited"],
    "III":  ["Name of Deductor", "TAN of Deductor", "Total Amount Paid/Credited"],
    "IV":   ["Acknowledgement Number", "Name of Deductor", "PAN of Deductor",
             "Transaction Date", "Total Transaction Amount", "Total TDS Deposited"],
    "V":    ["Acknowledgement Number", "Name of Buyer", "PAN of Buyer",
             "Transaction Date", "Total Transaction Amount"],
    "VI":   ["Name of Collector", "TAN of Collector", "Total Amount Paid/Debited",
             "Total Tax Collected", "Total TCS Deposited"],
    "VIII": ["Acknowledgement Number", "Name of Deductee", "PAN of Deductee",
             "Transaction Date", "Total Transaction Amount", "Total TDS Deposited",
             "Total Amount Deposited other than TDS"],
    "IX":   ["Acknowledgement Number", "Name of Seller", "PAN of Seller",
             "Transaction Date", "Total Transaction Amount",
             "Total Amount Deposited other than TDS"],
}

_DETAIL_COLS = {
    "I":    ["Section", "Transaction Date", "Status of Booking", "Date of Booking",
             "Remarks", "Amount Paid/Credited", "Tax Deducted", "TDS Deposited"],
    "II":   ["Section", "Transaction Date", "Date of Booking",
             "Remarks", "Amount Paid/Credited", "Tax Deducted", "TDS Deposited"],
    "III":  ["Section", "Transaction Date", "Status of Booking",
             "Remarks", "Amount Paid/Credited"],
    "IV":   ["TDS Certificate Number", "Section", "Date of Deposit",
             "Status of Booking", "Date of Booking", "Demand Payment", "TDS Deposited"],
    "V":    ["BSR Code", "Date of Deposit", "Challan Serial Number",
             "Total Tax Amount", "Status of Booking"],
    "VI":   ["Section", "Transaction Date", "Status of Booking", "Date of Booking",
             "Remarks", "Amount Paid/Debited", "Tax Collected", "TCS Deposited"],
    "VIII": ["TDS Certificate Number", "Section", "Date of Deposit",
             "Status of Booking", "Date of Booking", "Demand Payment",
             "TDS Deposited", "Total Amount Deposited other than TDS"],
    "IX":   ["BSR Code", "Date of Deposit", "Challan Serial Number",
             "Total Tax Amount", "Status of Booking", "Demand Payment",
             "Total Amount Deposited other than TDS"],
}

_FLAT_COLS = {
    "VII":  ["Assessment Year", "Mode", "Refund Issued", "Nature of Refund",
             "Amount of Refund", "Interest", "Date of Payment", "Remarks"],
    "X":    ["Financial Year", "Short Payment", "Short Deduction/Collection",
             "Interest on TDS/TCS Payments Default",
             "Interest on TDS/TCS Deduction/Collection Default",
             "Late Filing Fee u/s 234E", "Interest u/s 220(2)", "Total Default"],
}

# ============================================================
# Utilities
# ============================================================

def _clean(cell: Any) -> str:
    if cell is None:
        return ""
    s = str(cell).strip()
    s = s.replace('\n', ' ').replace('\r', ' ')
    return ' '.join(s.split())


def _parse_amount(val: str) -> float:
    if not val or val.strip() in ("", "-", "--"):
        return 0.0
    s = val.strip().replace(",", "")
    is_negative = s.startswith('(') and s.endswith(')')
    s = s.strip('()')
    try:
        v = float(s)
        return -v if is_negative else v
    except ValueError:
        return 0.0


def _identify_part(table: list[list[str]]) -> Optional[str]:
    """Identify which 26AS Part this table belongs to by its column header signature."""
    header_text = ' '.join(
        _clean(c) for row in table[:3] for c in row
    )

    # Check for Part II special case (15G/15H)
    if ('15G' in header_text or '15H' in header_text) and 'Name of Deductor' in header_text:
        return "II"

    # Check each part signature
    for part_id, (expected_cols, keywords) in _SUMMARY_SIG.items():
        if all(kw in header_text for kw in keywords):
            return part_id

    # Also check flat tables
    if 'Assessment Year' in header_text and 'Refund Issued' in header_text:
        return "VII"
    if 'Financial Year' in header_text and 'Short Payment' in header_text:
        return "X"

    return None


def _is_data_table(table: list[list[str]]) -> bool:
    """Check if a table is a data-bearing table (not metadata, legends, footnotes)."""
    all_text = ' '.join(_clean(c) for row in table for c in row).lower()

    # Metadata table
    if 'permanent account number' in all_text or 'current status of pan' in all_text:
        return False
    # Legend / appendix tables (metadata, footnotes, legend)
    if any(kw in all_text for kw in [
        'legends used',
        'abbreviation', 'part of annual tax statement', 'contact in case',
        'assessee pan:', 'rectification of error',
        'reprocessing of statement', 'lower/ no deduction',
        'contact information',
        'refer www.tinpan', 'nsdl e-governance', 'above data',
    ]):
        return False
    # Legend sub-tables with "Legend | Description | Definition" or "Legend | Description"
    first_cell = _clean(table[0][0]) if table and table[0] else ""
    if first_cell.lower() in ("legend", "code"):
        return False
    if first_cell.lower() == "section" and len(table) > 5:
        return False
    if first_cell == "Code" and "Description" in all_text:
        return False
    # Section continuation: rows like "194LC(2)(i) | Income under clause..."
    # These are 4-column pairs of code/description, 10+ rows
    if len(table) > 10 and re.search(r'^\d{3,4}[A-Za-z]', first_cell):
        return False

    # Part marker rows appear standalone but might be in tables sometimes
    if any('PART-' in _clean(c) for row in table for c in row):
        # Still data if it has actual columns after the PART marker
        if _identify_part(table):
            return True

    return True


def _skip_noise(chunk: str) -> bool:
    """Check if a standalone text line (between tables) is noise."""
    noise = {
        "", " ", "(All amount values are in INR)",
        "Above data / Status of PAN is as per PAN details.",
        "Refer www.tinpan.proteantech.in / www.utiitsl.com for more details.",
    }
    if chunk.strip() in noise:
        return True
    if chunk.strip().startswith("No Transactions Present"):
        return False  # We need this for empty part detection
    if chunk.strip().startswith("PART-"):
        return False  # We need this too
    return False


# ============================================================
# Row classification within a table
# ============================================================

def _is_summary_header(cells: list[str]) -> bool:
    """Check if this row is a summary header row."""
    text = ' '.join(cells)
    return ('Sr. No.' in text and
            ('Name of Deductor' in text or 'Name of Collector' in text or
             'Name Of Deductee' in text or 'Name of Buyer' in text or
             'Name of Seller' in text or 'Acknowledgement' in text))


def _is_detail_header(cells: list[str]) -> bool:
    """Check if this row is a detail header row."""
    text = ' '.join(cells)
    return ('Sr. No.' in text and
            ('Section' in text or 'TDS Certificate' in text or
             'BSR Code' in text or 'Challan Details' in text or
             'TANs' in text))


def _is_subtotal_row(cells: list[str]) -> bool:
    """Check if this is a 'Gross Total' or subtotal row."""
    text = ' '.join(cells)
    return 'Gross Total' in text or 'Grand Total' in text


# ============================================================
# Data row extraction
# ============================================================

def _extract_summary_data(cells: list[str], part_id: str) -> dict[str, str]:
    """Map a summary row's cells to named columns."""
    col_names = _SUMMARY_COLS.get(part_id, [])
    # First cell is SR number, skip it
    data_cells = [c for c in cells if c][1:]
    result: dict[str, str] = {}

    # The mapping: the deductor name may span 1-3 PDF cells, TAN is next, then amounts
    # Strategy: fill right-to-left for the known last columns (amounts, TAN),
    # everything else is merged into the name column

    if part_id in ("I", "II", "VI"):
        # Pattern: name name name TAN amount amount amount
        n_amt = 3
        n_name_cols = 1
        expected_data = n_name_cols + 1 + n_amt  # name + TAN + amounts

        if len(data_cells) >= expected_data:
            amts = data_cells[-n_amt:]
            tan = data_cells[-(n_amt + 1)]
            name_parts = data_cells[:-(n_amt + 1)]
            result[col_names[0]] = ' '.join(name_parts)
            result[col_names[1]] = tan
            for ci, amt in enumerate(amts):
                result[col_names[2 + ci]] = amt
        elif len(data_cells) >= n_amt + 1:
            amts = data_cells[-n_amt:]
            name_parts = data_cells[:-n_amt]
            result[col_names[0]] = ' '.join(name_parts)
            for ci, amt in enumerate(amts):
                result[col_names[2 + ci]] = amt
        else:
            for ci in range(len(data_cells)):
                if ci < len(col_names):
                    result[col_names[ci]] = data_cells[ci]

    elif part_id == "III":
        # Pattern: name name name TAN amount
        if len(data_cells) >= 2:
            amt = data_cells[-1]
            tan = data_cells[-2] if len(data_cells) >= 3 else ""
            name_parts = data_cells[:-2] if len(data_cells) >= 3 else data_cells[:-1]
            result[col_names[0]] = ' '.join(name_parts) if name_parts else ""
            result[col_names[1]] = tan
            result[col_names[2]] = amt
        else:
            for ci in range(min(len(data_cells), len(col_names))):
                result[col_names[ci]] = data_cells[ci]

    elif part_id in ("IV", "V", "VIII", "IX"):
        # Pattern: ack name name PAN date amount(s)
        n_amt = len(col_names) - 5  # after ack, name, pan, date
        if n_amt < 0:
            n_amt = 1

        if len(data_cells) >= 5 + n_amt:
            amts = data_cells[-(n_amt):]
            date = data_cells[-(n_amt + 1)]
            pan = data_cells[-(n_amt + 2)]
            name_parts = data_cells[-(n_amt + 3):-2] if len(data_cells) > (n_amt + 3) else []
            ack = ' '.join(data_cells[:-(n_amt + 3 + len(name_parts))]) if len(data_cells) > (n_amt + 3) else ""

            result[col_names[0]] = ack
            result[col_names[1]] = ' '.join(name_parts) if name_parts else ""
            result[col_names[2]] = pan
            result[col_names[3]] = date
            for ci, amt in enumerate(amts):
                result[col_names[4 + ci]] = amt
        else:
            for ci in range(min(len(data_cells), len(col_names))):
                result[col_names[ci]] = data_cells[ci]

    else:
        for ci in range(min(len(data_cells), len(col_names))):
            result[col_names[ci]] = data_cells[ci]

    return result


def _extract_detail_data(cells: list[str], part_id: str) -> dict[str, str]:
    """Map a detail row's cells to named columns."""
    col_names = _DETAIL_COLS.get(part_id, [])
    data_cells = [c for c in cells if c][1:]  # skip SR
    result: dict[str, str] = {}
    for ci in range(min(len(data_cells), len(col_names))):
        result[col_names[ci]] = data_cells[ci]
    return result


def _extract_flat_data(cells: list[str], part_id: str) -> dict[str, str]:
    """Map a flat table row to named columns."""
    col_names = _FLAT_COLS.get(part_id, [])
    data_cells = [c for c in cells if c][1:]  # skip SR
    result: dict[str, str] = {}
    for ci in range(min(len(data_cells), len(col_names))):
        result[col_names[ci]] = data_cells[ci]
    return result


# ============================================================
# Single table parser
# ============================================================

def _parse_part_tables(tables: list[list[list[str]]], part_id: str) -> dict:
    """Parse one or more pdfplumber tables for a single 26AS Part.

    Merges rows from multiple tables spanning the same part into a single result.
    """
    if not tables:
        return _empty_part_result(part_id)

    meta = PART_META.get(part_id, {"title": "", "credit": False})
    is_flat = part_id in ("VII", "X")

    # Check for "No Transactions Present" in any table
    for table in tables:
        all_text = ' '.join(_clean(c) for row in table for c in row)
        if 'No Transactions Present' in all_text:
            return _empty_part_result(part_id)

    rows_out: list[dict] = []
    current_deductor: Optional[dict] = None

    for table in tables:
        for row in table:
            cells = [_clean(c) for c in row]
            non_empty = [c for c in cells if c]
            if not non_empty:
                continue

            first_cell = non_empty[0]

            # Skip header rows
            if _is_summary_header(cells) or _is_detail_header(cells):
                continue

            # Skip subtotal
            if _is_subtotal_row(cells):
                if current_deductor is not None:
                    current_deductor.setdefault("_details", [])
                    rows_out.append(current_deductor)
                    current_deductor = None
                continue

            # Skip noise
            if not first_cell.isdigit():
                continue

            # FLAT TABLE: every numeric-starting row is a data row
            if is_flat:
                row_data = _extract_flat_data(non_empty, part_id)
                row_data["_details"] = []
                rows_out.append(row_data)
                continue

            # Summary rows: after SR, next cells are deductor name words (alpha)
            # Detail rows: after SR, next cell is a section code (digits+letters, short)
            # Amount values are large numbers with commas/decimals - NOT section codes
            second_cell = non_empty[1] if len(non_empty) > 1 else ""
            is_detail = (bool(re.match(r'^\d{3,4}[A-Za-z]*(?:\s*\(.*\))?$', second_cell)) and
                         len(second_cell) <= 15)

            if is_detail:
                if current_deductor is not None:
                    detail = _extract_detail_data(non_empty, part_id)
                    current_deductor.setdefault("_details", []).append(detail)
            else:
                if current_deductor is not None:
                    current_deductor.setdefault("_details", [])
                    rows_out.append(current_deductor)
                current_deductor = _extract_summary_data(non_empty, part_id)

    # Save last deductor
    if current_deductor is not None:
        current_deductor.setdefault("_details", [])
        rows_out.append(current_deductor)

    if not rows_out:
        return _empty_part_result(part_id)

    return {
        "empty": False,
        "title": meta["title"],
        "credit": meta["credit"],
        "col_headers": _SUMMARY_COLS.get(part_id, _FLAT_COLS.get(part_id, [])),
        "detail_headers": _DETAIL_COLS.get(part_id, []),
        "rows": rows_out,
    }


def _empty_part_result(part_id: str) -> dict:
    """Create an empty part result."""
    meta = PART_META.get(part_id, {"title": "", "credit": False})
    return {
        "empty": True,
        "title": meta["title"],
        "credit": meta["credit"],
        "col_headers": _SUMMARY_COLS.get(part_id, _FLAT_COLS.get(part_id, [])),
        "detail_headers": _DETAIL_COLS.get(part_id, []),
        "rows": [],
    }


# ============================================================
# Metadata extraction
# ============================================================

def _extract_meta(tables: list[list[list[str]]]) -> dict[str, str]:
    """Extract taxpayer metadata from the metadata table on Page 1."""
    meta = {}
    for table in tables:
        first_row = [_clean(c) for c in table[0]]
        if 'Permanent Account Number' not in ' '.join(first_row):
            continue
        flat = []
        for row in table:
            for cell in row:
                v = _clean(cell)
                if v:
                    flat.append(v)
        for i in range(0, len(flat) - 1, 2):
            key = flat[i].rstrip(':').strip()
            val = flat[i + 1]
            meta[key] = val
    return meta


# ============================================================
# Main extraction entry point
# ============================================================

def extract_26as(pdf_path: str) -> dict:
    """Extract 26AS PDF into structured dict.

    Returns:
        {"header": {...}, "parts": {"I": {...}, "II": {...}, ...}}
    """
    import pdfplumber

    # === Collect all tables ===
    all_tables: list[list[list[str]]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for t in tables:
                if t and len(t) >= 1:
                    cleaned = [[_clean(c) for c in row] for row in t]
                    all_tables.append(cleaned)

    # === Extract metadata ===
    meta = _extract_meta(all_tables)
    header = {
        "Permanent Account Number (PAN)": meta.get("Permanent Account Number (PAN)", ""),
        "Current Status of PAN": meta.get("Current Status of PAN", ""),
        "Financial Year": meta.get("Financial Year", ""),
        "Assessment Year": meta.get("Assessment Year", ""),
        "Name of Assessee": meta.get("Name of Assessee", ""),
        "Address of Assessee": meta.get("Address of Assessee", ""),
    }

    # === Identify data tables and their parts ===
    part_tables: dict[str, list[list[list[str]]]] = {}  # part_id -> [tables]

    for table in all_tables:
        if not _is_data_table(table):
            continue
        part_id = _identify_part(table)
        if part_id:
            part_tables.setdefault(part_id, []).append(table)

    # === Parse each part (merge multiple tables for same part) ===
    parts_result: dict[str, dict] = {}

    for part_id in part_tables:
        tables = part_tables[part_id]
        part_data = _parse_part_tables(tables, part_id)
        parts_result[part_id] = part_data

    # Fill in any missing standard parts as empty
    for pid in ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]:
        if pid not in parts_result:
            parts_result[pid] = _empty_part_result(pid)

    return {"header": header, "parts": parts_result}


def extract_26as_json(pdf_path: str, indent: int = 2) -> str:
    """Extract and return JSON string."""
    return json.dumps(extract_26as(pdf_path), indent=indent, ensure_ascii=False)
