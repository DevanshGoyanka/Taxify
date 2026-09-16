"""Tests for actual emitted-document ITR-3 completeness coverage."""

from __future__ import annotations

import pytest

from app.engine.itd.itr3_preparation import (
    ITR3PreparationIncompleteError,
    extract_itr3_source_paths,
    require_complete_itr3_document,
)


def test_extract_itr3_source_paths_uses_manifest_array_notation() -> None:
    """Nested object and array leaves are extracted using official paths."""
    document = {"ITR": {"ITR3": {"ScheduleGST": {"Rows": [{"GSTIN": "1"}]}}}}
    paths = extract_itr3_source_paths(document)
    assert "ScheduleGST.Rows[].GSTIN" in paths


def test_actual_incomplete_document_reports_emitted_coverage_gaps() -> None:
    """The gate reports actual absent paths instead of using an empty registry."""
    document = {"ITR": {"ITR3": {"CreationInfo": {"Digest": "x"}}}}
    with pytest.raises(ITR3PreparationIncompleteError) as caught:
        require_complete_itr3_document(document)
    assert "CreationInfo.SWVersionNo" in caught.value.report.missing_source_paths
    assert "CreationInfo.Digest" not in caught.value.report.missing_source_paths
