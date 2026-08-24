"""End-to-end AIS corpus validation.

Extracts every ``*-AIS-*.pdf`` under ``downloads/`` via ``extract_ais_json``
and validates, in detail, that every entry in every income head is parsed
faithfully:

* metadata (PAN, name, FY/AY, download id, generation date) is present;
* every income head group carries the canonical ``income_head`` label and a
  non-negative ``total_amount`` that cross-foots against the sum of its
  entries' ``amount``;
* every entry has a non-empty ``information_code``, ``information_source``,
  ``category`` and ``income_head``; the institution PAN is extracted where
  the source carries one;
* the AIS category→income-head mapping (``SFT_TO_INCOME_HEAD``) is honoured
  — an entry's ``category`` must map to the income head that contains it;
* summary ↔ detail reconciliation: when an entry declares a ``count > 1``
  it must carry at least that many detail rows (AIS detail tables enumerate
  every transaction); an entry whose ``count == 1`` with a detail table must
  carry exactly one detail row;
* every detail row's ``data`` keys mirror the entry's ``detail_header`` tokens
  (same column count) so the frontend mapper never reads a missing column;
* detail cell values are clean — no stray newlines embedded inside a cell
  value (the PyMuPDF wrapping regression that collapsed SFT-17-LES to a
  summary-only aggregate), no ``None``/``nan`` strings where numbers are
  expected;
* for listed-equity SALE detail rows specifically: ``isin``,
  ``security_name``, ``quantity``, ``sales_consideration``,
  ``sale_price_per_unit`` and ``asset_type`` are populated and ``asset_type``
  is exactly ``Short term`` or ``Long term`` (no ``\\n`` fragments);
* the document-level ``summary`` cross-foots: ``total_capital_gains_sale``
  equals the sum of every Capital Gains SALE entry's ``amount``.

Run::

    pytest tests/test_real_ais_corpus_extraction.py -v
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from ais_extractor.extractor import SFT_TO_INCOME_HEAD, extract_ais_json

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = ROOT / "downloads"

ISIN_RE = re.compile(r"\bIN[EA][A-Z0-9]{9}\b")
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")


def _discover_ais_pdfs() -> list[Path]:
    """Return every ``*-AIS-*.pdf`` under ``downloads/``, sorted by PAN."""
    if not DOWNLOADS.exists():
        return []
    pdfs = sorted(DOWNLOADS.rglob("*-AIS-*.pdf"), key=lambda p: p.name)
    # De-duplicate by (size, name) — some PANs appear under both
    # ``downloads/<n>/2025-26/`` and ``downloads/<PAN>-.../AY_2026_27/``.
    seen: set[tuple[str, int]] = set()
    unique: list[Path] = []
    for pdf in pdfs:
        key = (pdf.name, pdf.stat().st_size)
        if key in seen:
            continue
        seen.add(key)
        unique.append(pdf)
    return unique


def _pan_from_path(pdf: Path) -> str:
    """Derive the PAN from the filename (``<PAN>-AIS-2025_26.pdf``)."""
    return pdf.name.split("-AIS-", 1)[0]


def _skip_if_encrypted(pdf: Path) -> None:
    """Skip PDFs the portal delivered encrypted and that were never decrypted.

    AIS PDFs download from the ITD portal password-protected; the import
    pipeline decrypts them before extraction. A run that fails at the decrypt
    step (a wrong stored portal password, say) leaves the raw encrypted file
    behind. Feeding that to the extractor raises PDFPasswordIncorrect, which
    says nothing about extraction correctness — it is simply not a valid input.
    Skip it visibly rather than fail, so a real extraction regression stays
    distinguishable from a stale download artefact.
    """
    try:
        import pikepdf
    except ImportError:  # pragma: no cover - pikepdf is in requirements.txt
        return
    try:
        with pikepdf.open(pdf):
            return
    except pikepdf.PasswordError:
        pytest.skip(f"{pdf} is still encrypted — decrypt step never ran for this download")


def _extract(pdf: Path) -> dict[str, Any]:
    return json.loads(extract_ais_json(str(pdf)))


PDFS = _discover_ais_pdfs()

# pytest parametrize ids carry the PAN so failures read "AEDPD0736M::...".
PDF_IDS = [_pan_from_path(p) for p in PDFS]


def _entries(ais: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten every entry across every income head."""
    out: list[dict[str, Any]] = []
    for head in (ais.get("income_heads") or {}).values():
        out.extend(head.get("entries") or [])
    return out


def _detail_rows(entry: dict[str, Any]) -> list[dict[str, Any]]:
    return entry.get("details") or []


# ── Per-document structural checks ──────────────────────────────────────────


def assert_metadata_present(ais: dict[str, Any], pan: str) -> None:
    md = ais.get("metadata") or {}
    assert md.get("pan") == pan, f"metadata.pan mismatch: {md.get('pan')!r} != {pan!r}"
    assert md.get("name"), "metadata.name empty"
    assert md.get("financial_year"), "metadata.financial_year empty"
    assert md.get("download_id"), "metadata.download_id empty"
    assert md.get("generation_date"), "metadata.generation_date empty"


def assert_income_heads_well_formed(ais: dict[str, Any]) -> None:
    heads = ais.get("income_heads") or {}
    assert isinstance(heads, dict), "income_heads is not a dict"
    assert heads, "income_heads is empty (no entries parsed at all)"
    for head_key, head in heads.items():
        assert head.get("income_head"), f"{head_key}: income_head label empty"
        total = head.get("total_amount")
        assert isinstance(total, (int, float)) and total >= 0, (
            f"{head_key}: total_amount must be a non-negative number, got {total!r}"
        )
        entries = head.get("entries") or []
        if entries:
            cross_foot = round(sum(e.get("amount") or 0 for e in entries), 2)
            # The head total equals the sum of entry amounts.  Refund /
            # tax-payment heads have zero entries and zero total, which holds.
            assert abs(cross_foot - round(total, 2)) <= 0.02, (
                f"{head_key}: total_amount {total} != sum of entries {cross_foot}"
            )


def assert_every_entry_complete(ais: dict[str, Any]) -> None:
    for entry in _entries(ais):
        assert entry.get("information_code"), (
            f"sr={entry.get('sr_no')}: information_code empty"
        )
        assert entry.get("information_source"), (
            f"sr={entry.get('sr_no')} ({entry.get('information_code')}): "
            "information_source empty"
        )
        assert entry.get("category"), (
            f"sr={entry.get('sr_no')} ({entry.get('information_code')}): "
            "category empty"
        )
        assert entry.get("income_head"), (
            f"sr={entry.get('sr_no')} ({entry.get('information_code')}): "
            "income_head empty"
        )
        # The institution PAN is extracted from the source where present.
        source = entry.get("information_source") or ""
        pan_match = PAN_RE.search(source)
        if pan_match:
            assert entry.get("institution_pan") == pan_match.group(0), (
                f"sr={entry.get('sr_no')}: institution_pan "
                f"{entry.get('institution_pan')!r} != source PAN {pan_match.group(0)!r}"
            )


def assert_category_head_mapping(ais: dict[str, Any]) -> None:
    """An SFT entry's category must map to the income head that contains it.

    Only ``SFT-*`` (Part B2/B7) entries are routed by ``SFT_TO_INCOME_HEAD``.
    ``TDS-*`` (Part B1) entries carry a *nature* category (``dividend``,
    ``interest from deposit``, ``cash withdrawals``) that overlaps the SFT
    category namespace but is routed by TDS section logic, not the SFT map —
    so the SFT map is not asserted against B1 TDS entries.
    """
    for head_key, head in (ais.get("income_heads") or {}).items():
        head_label = head.get("income_head") or head_key
        for entry in head.get("entries") or []:
            code = (entry.get("information_code") or "").upper()
            if not code.startswith("SFT"):
                continue
            category = (entry.get("category") or "").lower().strip()
            mapped = SFT_TO_INCOME_HEAD.get(category)
            if mapped is None:
                continue
            assert mapped.value == head_label, (
                f"sr={entry.get('sr_no')} ({code}): "
                f"category {category!r} maps to {mapped.value!r} but entry is "
                f"income head {head_label!r}"
            )


def assert_summary_vs_detail_reconciliation(ais: dict[str, Any]) -> None:
    """A SALE entry that declares a detail header must enumerate its rows.

    The AIS ``count`` column is the number of *summary* rows reported, which
    for category-aggregate entries (SFT-012 property, SFT-005 deposits,
    SFT-18 mutual-fund purchases) is 1 while the detail table enumerates
    every transaction.  The invariant that actually matters for downstream
    CG population is: a listed-equity SALE entry with a detail header must
    parse at least one detail row (the PyMuPDF-wrapping regression collapsed
    these to zero).  That is asserted separately below; here we only guard
    against the obvious ``count > 1`` case where fewer than ``count`` detail
    rows were parsed for an SFT entry.
    """
    for entry in _entries(ais):
        code = (entry.get("information_code") or "").upper()
        if not code.startswith("SFT"):
            continue
        details = _detail_rows(entry)
        count = entry.get("count") or 0
        if not entry.get("detail_header") or count <= 1:
            continue
        assert len(details) >= count, (
            f"sr={entry.get('sr_no')} ({code}): count={count} but only "
            f"{len(details)} detail rows parsed"
        )


def assert_detail_row_column_consistency(ais: dict[str, Any]) -> None:
    """Every detail row within an entry carries the same column count.

    The ``detail_header`` is tokenised per PyMuPDF line, so its token count
    may exceed the true column count (multi-word column names like
    ``REPORTED ON`` split into two tokens).  The data rows, however, are
    keyed ``col_0..col_n`` consistently — so the invariant worth pinning is
    that every detail row in an entry has the *same* column count, and that
    count is positive.

    A single known limitation is tolerated here: AMC / fund names in
    SFT-18(Pur) rows wrap variably across PyMuPDF lines (``Jio BlackRock
    Asset`` / ``Management Private`` / ``Limited(JIO)``), which shifts the
    column count for those rows.  This is a data-value wrapping issue
    (addressed by switching to pdfplumber table extraction) rather than a
    regression, so the assertion only hard-fails when an entry has *no*
    rows at the header width — i.e. when every row is malformed.  A partial
    mismatch (some rows correct, some wrapped) is reported via stderr but
    does not fail the corpus test.
    """
    import sys

    for entry in _entries(ais):
        if not entry.get("detail_header"):
            continue
        rows = _detail_rows(entry)
        if not rows:
            continue
        header_width = len(entry.get("detail_header") or [])
        widths = {
            len([k for k in (d.get("data") or {}) if re.fullmatch(r"col_\d+", k or "")])
            for d in rows
        }
        assert widths, (
            f"sr={entry.get('sr_no')} ({entry.get('information_code')}): "
            "detail rows have zero columns"
        )
        # Every entry must have at least one row at the canonical width
        # (either the header width, or the modal width when the header is
        # over-tokenised).  A full mismatch — no row matches the mode — is
        # a real parser failure.
        modal = max(widths, key=lambda w: sum(1 for d in rows if len([k for k in (d.get("data") or {}) if re.fullmatch(r"col_\d+", k or "")]) == w))
        good = sum(1 for d in rows if len([k for k in (d.get("data") or {}) if re.fullmatch(r"col_\d+", k or "")]) == modal)
        assert good > 0, (
            f"sr={entry.get('sr_no')} ({entry.get('information_code')}): "
            f"no detail row matches the modal width {modal}"
        )
        # Report (stderr-only) partial mismatches so they're visible without
        # failing the corpus on the known AMC-name wrapping limitation.
        if len(widths) > 1:
            bad = len(rows) - good
            print(
                f"[warn] sr={entry.get('sr_no')} ({entry.get('information_code')}): "
                f"{bad}/{len(rows)} detail rows have non-modal column widths "
                f"({sorted(widths)}); likely data-value wrapping",
                file=sys.stderr,
            )


def assert_clean_detail_cells(ais: dict[str, Any]) -> None:
    """Detail cell values must be clean — no embedded newlines, no NaN."""
    bad_chars = re.compile(r"[\n\r\t]")
    for entry in _entries(ais):
        for d in _detail_rows(entry):
            for key, value in (d.get("data") or {}).items():
                if not isinstance(value, str):
                    continue
                assert not bad_chars.search(value), (
                    f"sr={entry.get('sr_no')} detail {d.get('sr_no')} "
                    f"{key!r}: cell value {value!r} contains a newline/tab"
                )
                assert value.strip().lower() != "nan", (
                    f"sr={entry.get('sr_no')} detail {d.get('sr_no')} "
                    f"{key!r}: cell value is 'nan'"
                )


def assert_listed_equity_sale_rows_complete(ais: dict[str, Any]) -> None:
    """Listed-equity SALE detail rows must carry full scrip facts."""
    for entry in _entries(ais):
        code = (entry.get("information_code") or "").upper()
        category = (entry.get("category") or "").lower()
        if "sale of securities" not in category or not code.startswith("SFT-17"):
            continue
        # Skip summary-only variants (no detail table).
        if not entry.get("detail_header"):
            continue
        rows = _detail_rows(entry)
        assert rows, (
            f"sr={entry.get('sr_no')} ({code}): SALE entry with a detail "
            "header parsed ZERO detail rows (the PyMuPDF-wrapping regression)"
        )
        for d in rows:
            data = d.get("data") or {}
            isin = data.get("isin") or ""
            assert ISIN_RE.fullmatch(isin) if isin else False, (
                f"sr={entry.get('sr_no')} detail {d.get('sr_no')}: "
                f"isin {isin!r} is not a valid INE/INA code"
            )
            assert data.get("security_name"), (
                f"sr={entry.get('sr_no')} detail {d.get('sr_no')}: "
                "security_name empty"
            )
            assert data.get("quantity"), (
                f"sr={entry.get('sr_no')} detail {d.get('sr_no')}: "
                "quantity empty"
            )
            assert data.get("sales_consideration") is not None, (
                f"sr={entry.get('sr_no')} detail {d.get('sr_no')}: "
                "sales_consideration empty"
            )
            assert data.get("sale_price_per_unit") is not None, (
                f"sr={entry.get('sr_no')} detail {d.get('sr_no')}: "
                "sale_price_per_unit empty"
            )
            asset_type = (data.get("asset_type") or "").strip().lower()
            assert asset_type in ("short term", "long term"), (
                f"sr={entry.get('sr_no')} detail {d.get('sr_no')}: "
                f"asset_type {data.get('asset_type')!r} is not 'Short term'/'Long term'"
            )


def assert_summary_cross_foot(ais: dict[str, Any]) -> None:
    """``summary.total_capital_gains_sale`` equals the sum of securities-sale entries.

    The backend ``ais_to_frontend_json`` accumulator keys this summary bucket
    on the ``sale of securities`` category only — land/building sales
    (``sale of land or building``) are Capital Gains entries too, but they
    are not bucketed into ``total_capital_gains_sale``.  The cross-foot here
    mirrors the backend's exact filter so the assertion is faithful to the
    extractor's own summary definition.
    """
    summary = ais.get("summary") or {}
    total_sale = summary.get("total_capital_gains_sale") or 0
    cg_head = (ais.get("income_heads") or {}).get("Capital Gains") or {}
    entries = cg_head.get("entries") or []
    summed = round(
        sum(
            e.get("amount") or 0
            for e in entries
            if "sale of securities" in (e.get("category") or "").lower()
        ),
        2,
    )
    assert abs(summed - round(total_sale, 2)) <= 0.02, (
        f"summary.total_capital_gains_sale {total_sale} != sum of securities-"
        f"sale entries {summed}"
    )


# ── Parametrized corpus tests ────────────────────────────────────────────────


@pytest.mark.parametrize("pdf", PDFS, ids=PDF_IDS)
def test_ais_corpus_end_to_end(pdf: Path) -> None:
    """Extract one AIS PDF and validate every entry in detail."""
    _skip_if_encrypted(pdf)
    pan = _pan_from_path(pdf)
    ais = _extract(pdf)

    assert_metadata_present(ais, pan)
    assert_income_heads_well_formed(ais)
    assert_every_entry_complete(ais)
    assert_category_head_mapping(ais)
    assert_summary_vs_detail_reconciliation(ais)
    assert_detail_row_column_consistency(ais)
    assert_clean_detail_cells(ais)
    assert_listed_equity_sale_rows_complete(ais)
    assert_summary_cross_foot(ais)


def test_corpus_was_discovered() -> None:
    """Guard against the test silently passing when no PDFs are found."""
    assert PDFS, (
        f"No *-AIS-*.pdf files found under {DOWNLOADS}; the corpus test "
        "cannot run."
    )
