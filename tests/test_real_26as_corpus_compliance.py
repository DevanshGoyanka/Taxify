"""Corpus compliance tests for real 26AS extractor fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.routers.integration import _map_legacy_26as


CORPUS = Path(__file__).resolve().parents[1] / "ais_extractor" / "test_output_26as"

# The corpus is generated output, not source: ais_extractor/test_26as_all.py writes
# it by running the extractor over real 26AS PDFs. It is deliberately absent from
# git because those files contain taxpayer PII. On a machine that has never
# generated it, every test here has nothing to assert against and the suite should
# report "skipped", not "failed". Where the corpus IS present the size guard below
# still fires, which is the check it exists for.
pytestmark = pytest.mark.skipif(
    not CORPUS.is_dir(),
    reason=(
        f"26AS corpus not generated at {CORPUS}. "
        "Run ais_extractor/test_26as_all.py against real 26AS PDFs to create it."
    ),
)


def _fixtures() -> list[Path]:
    """Return every real 26AS JSON fixture in deterministic order."""
    return sorted(CORPUS.glob("*.json"))


def _raw_rows(document: dict[str, Any]) -> int:
    """Count all top-level source rows across every 26AS part."""
    return sum(len(part.get("rows") or []) for part in document.get("parts", {}).values())


def _part_rows(document: dict[str, Any], part: str) -> list[dict[str, Any]]:
    """Return source rows for one 26AS part."""
    return list(document.get("parts", {}).get(part, {}).get("rows") or [])


def test_real_26as_corpus_has_at_least_sixty_files() -> None:
    """Ensure the compliance suite cannot silently run against a tiny corpus."""
    assert len(_fixtures()) >= 60


@pytest.mark.parametrize("path", _fixtures(), ids=lambda path: path.name.split("_")[0])
def test_normalization_preserves_every_part_row(path: Path) -> None:
    """Every original Part I-X row must survive as lossless source evidence."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    normalized = _map_legacy_26as(raw)
    assert len(normalized["sourceRows"]) == _raw_rows(raw)
    for source_row in normalized["sourceRows"]:
        assert source_row["part"] in raw.get("parts", {})
        assert isinstance(source_row["raw"], dict)
        assert source_row["raw"]


@pytest.mark.parametrize("path", _fixtures(), ids=lambda path: path.name.split("_")[0])
def test_part_i_tds_totals_match_extractor_summaries(path: Path) -> None:
    """Normalized TDS totals must exactly equal net extractor summary totals."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    normalized = _map_legacy_26as(raw)
    expected_tax = sum(float(row.get("Total Tax Deducted") or 0) for row in _part_rows(raw, "I"))
    expected_gross = sum(float(row.get("Total Amount Paid/Credited") or 0) for row in _part_rows(raw, "I"))
    actual_tax = sum(float(row.get("totalTDS") or 0) for row in normalized["tdsEntries"])
    actual_gross = sum(float(row.get("totalAmount") or 0) for row in normalized["tdsEntries"])
    assert actual_tax == pytest.approx(expected_tax, abs=0.01)
    assert actual_gross == pytest.approx(expected_gross, abs=0.01)


@pytest.mark.parametrize("path", _fixtures(), ids=lambda path: path.name.split("_")[0])
def test_part_vi_tcs_totals_match_extractor_summaries(path: Path) -> None:
    """Part VI TCS credits must be projected without changing source figures."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    normalized = _map_legacy_26as(raw)
    expected_rows = _part_rows(raw, "VI")
    assert len(normalized["tcsEntries"]) == len(expected_rows)
    expected_tax = sum(float(row.get("Total Tax Collected") or 0) for row in expected_rows)
    expected_gross = sum(float(row.get("Total Amount Paid/Debited") or 0) for row in expected_rows)
    actual_tax = sum(float(row.get("taxCollected") or 0) for row in normalized["tcsEntries"])
    actual_gross = sum(float(row.get("grossAmount") or 0) for row in normalized["tcsEntries"])
    assert actual_tax == pytest.approx(expected_tax, abs=0.01)
    assert actual_gross == pytest.approx(expected_gross, abs=0.01)
