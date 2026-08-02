"""
Reconciliation Engine for AIS, TIS, and 26AS data.

Takes JSON outputs from the three PDF extractors and produces
a unified, reconciled view organized by income head.

Priority for final amount: TIS (accepted_by_taxpayer) > AIS (amount) > 26AS
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
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
    "purchase of time deposits":        "Income from Other Sources",
    "cash deposits":                    "Income from Other Sources",
    "cash withdrawals":                 "Income from Other Sources",
    "winnings from online games":       "Income from Other Sources",
    "purchase of vehicle":              "Income from Other Sources",
    "commission income":                "Income from Other Sources",
    "insurance commission":             "Profits and Gains of Business or Profession",
    "receipt from partnership firm":    "Profits and Gains of Business or Profession",
    "tax payments":                     "Taxes Paid",
    "refund":                           "Refund",
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
    "194N": "business receipts", "194O": "business receipts",
    "194Q": "business receipts", "194S": "business receipts",
    "194IA": "sale of land or building", "194IB": "sale of land or building",
    "206C": "business receipts", "206CE": "business receipts",
    "206CF": "business receipts",
}


# ============================================================
# Name normalization
# ============================================================

_CODE_SUFFIX_RE = re.compile(r'\s*\([A-Z0-9.]+\s*\)\s*$', re.IGNORECASE)

def normalize_name(name: str) -> str:
    """Strip PAN/CODE suffix, lowercase, collapse whitespace."""
    if not name:
        return ""
    n = _CODE_SUFFIX_RE.sub('', name)
    n = re.sub(r'\s*\([^)]*\)\s*', ' ', n)
    n = re.sub(r'[^a-z0-9\s]', '', n.lower())
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def extract_pan(source: str) -> str:
    """Extract PAN from source like 'BANK (ABCDE1234F.XYZ)'."""
    if not source:
        return ""
    m = re.search(r'\(([A-Z]{5}[0-9]{4}[A-Z])[.)]', source)
    if m:
        return m.group(1)
    return ""


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

    @property
    def key(self) -> str:
        return f"{self.category}|{self.source}"


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


def _extract_tis(tis: dict) -> list[Entry]:
    entries: list[Entry] = []
    for ih_name, ih_data in tis.get("income_heads", {}).items():
        for e in ih_data.get("entries", []):
            cat = e.get("category", "").lower()
            for d in e.get("details", []):
                raw = d.get("information_source", "")
                src = normalize_name(raw)
                pan = d.get("institution_pan", "") or extract_pan(raw)
                if src:
                    entries.append(Entry(
                        category=cat, source=src, raw_source=raw,
                        amount=_parse_amount(d.get("accepted_by_taxpayer", "0")),
                        section=d.get("part", ""),
                        description=d.get("information_description", ""),
                        income_head=ih_name, pan=pan,
                    ))
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

            entries.append(Entry(
                category=cat, source=src, raw_source=raw,
                amount=amt, tds=tds,
                section=section,
                description=f"TDS/TCS u/s {section}" if section else "TDS/TCS",
                income_head=CATEGORY_TO_INCOME_HEAD.get(cat, "Income from Other Sources"),
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
        if not e_a.pan or e_a.key not in map_a:
            continue
        for e_b in entries_b:
            if not e_b.pan or e_b.pan != e_a.pan:
                continue
            if e_b.category != e_a.category:
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
    present_in: dict[str, bool] = field(default_factory=lambda: {"tis": False, "ais": False, "as26": False})
    has_discrepancy: bool = False
    discrepancy_detail: str = ""


def reconcile(ais_data: dict, tis_data: dict, as26_data: dict) -> dict:
    ais_entries = _extract_ais(ais_data)
    tis_entries = _extract_tis(tis_data)
    as26_entries = _extract_26as(as26_data)

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

    # === PAN-based cross-matching for unmatched entries ===
    # If entry A from doc1 and entry B from doc2 share category + PAN but
    # have different normalized names, merge them under a single key.
    _pan_cross_match(ais_map, tis_map, ais_entries, tis_entries)
    _pan_cross_match(ais_map, as26_map, ais_entries, as26_entries)
    _pan_cross_match(tis_map, as26_map, tis_entries, as26_entries)

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

        ais_total = sum(e.amount for e in a)
        tis_total = sum(e.amount for e in t)
        as26_total = sum(e.amount for e in as_list)
        as26_tds_total = sum(e.tds for e in as_list)

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

        # Final amount: TIS > AIS > 26AS
        final = tis_total if has_tis else (ais_total if has_ais else as26_total)

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
            present_in={"tis": has_tis, "ais": has_ais, "as26": has_as26},
        )

        # Discrepancy check (tolerance: 1 rupee)
        if has_tis and has_ais and abs(tis_total - ais_total) > 1.0:
            rec.has_discrepancy = True
            rec.discrepancy_detail = f"TIS={tis_total:,.2f} vs AIS={ais_total:,.2f}"
        elif has_ais and has_as26 and abs(ais_total - as26_total) > 1.0:
            rec.has_discrepancy = True
            rec.discrepancy_detail = f"AIS={ais_total:,.2f} vs 26AS={as26_total:,.2f}"

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

    # Group by income head
    by_head: dict[str, dict] = {}
    for rec in reconciled:
        ih = rec.income_head
        if ih not in by_head:
            by_head[ih] = {
                "income_head": ih, "total_final": 0.0,
                "total_tis": 0.0, "total_ais": 0.0, "total_as26": 0.0,
                "total_as26_tds": 0.0, "discrepancy_count": 0, "entries": [],
            }
        g = by_head[ih]
        g["total_final"] += rec.final_amount
        g["total_tis"] += rec.tis_amount
        g["total_ais"] += rec.ais_amount
        g["total_as26"] += rec.as26_amount
        g["total_as26_tds"] += rec.as26_tds
        if rec.has_discrepancy:
            g["discrepancy_count"] += 1
        g["entries"].append(rec)

    def _entry_dict(e: Entry) -> dict:
        return {
            "category": e.category, "source": e.raw_source,
            "amount": round(e.amount, 2), "tds": round(e.tds, 2),
            "section": e.section, "description": e.description,
            "income_head": e.income_head,
        }

    def _rec_dict(r: ReconciledEntry) -> dict:
        return {
            "category": r.category, "source": r.source,
            "description": r.description, "section": r.section,
            "income_head": r.income_head,
            "amounts": {
                "tis": round(r.tis_amount, 2),
                "ais": round(r.ais_amount, 2),
                "as26": round(r.as26_amount, 2),
            },
            "as26_tds": round(r.as26_tds, 2),
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
                "total_final": round(g["total_final"], 2),
                "total_tis": round(g["total_tis"], 2),
                "total_ais": round(g["total_ais"], 2),
                "total_as26": round(g["total_as26"], 2),
                "total_as26_tds": round(g["total_as26_tds"], 2),
                "discrepancy_count": g["discrepancy_count"],
                "entries": [_rec_dict(r) for r in g["entries"]],
            }
            for ih, g in sorted(by_head.items())
        },
        "unmatched": {
            "tis_only": [_entry_dict(e) for e in unmatched_tis],
            "ais_only": [_entry_dict(e) for e in unmatched_ais],
            "as26_only": [_entry_dict(e) for e in unmatched_as26],
        },
        "summary": {
            "total_entries": len(reconciled),
            "total_final_income": round(sum(r.final_amount for r in reconciled), 2),
            "total_discrepancies": sum(1 for r in reconciled if r.has_discrepancy),
            "matched_all_three": sum(1 for r in reconciled if all(r.present_in.values())),
            "matched_two": sum(1 for r in reconciled if sum(r.present_in.values()) == 2),
            "matched_one": sum(1 for r in reconciled if sum(r.present_in.values()) == 1),
            "unmatched_tis": len(unmatched_tis),
            "unmatched_ais": len(unmatched_ais),
            "unmatched_as26": len(unmatched_as26),
        },
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
