"""Tests for the fail-closed ITR-3 preparation contract."""

from __future__ import annotations

import pytest

from app.engine.itd.itr3_manifest import get_itr3_schedule_manifest
from app.engine.itd.itr3_preparation import (
    ITR3PreparationIncompleteError,
    build_itr3_emitted_completeness_report,
    register_itr3_source_paths,
    require_complete_itr3_preparation,
)


def test_itr3_preparation_rejects_empty_source_registry() -> None:
    """No schedule may be treated as complete without explicit sources."""
    with pytest.raises(ITR3PreparationIncompleteError) as caught:
        require_complete_itr3_preparation(set())
    report = caught.value.report
    assert not report.complete
    assert report.field_count > 0
    assert report.missing_source_paths


def test_registered_complete_subtrees_reduce_missing_paths_without_covering_incomplete_schedules() -> None:
    """Verified schedule roots reduce gaps while CG/BS/PL remain fail-closed."""
    document = {
        "ITR": {"ITR3": {
            "ScheduleCYLA": {"Salary": {"IncCYLA": {"IncOfCurYrUnderThatHead": 0}}},
            "PARTA_BS": {"Assets": {"TotalAssets": 0}},
            "PARTA_PL": {"GrossProfit": 0},
            "ScheduleCGFor23": {"TotalCapGain": 0},
        }}
    }
    registered = register_itr3_source_paths(document)
    report = build_itr3_emitted_completeness_report(document)
    assert "ScheduleCYLA" in registered
    assert len(report.missing_source_paths) < report.field_count
    assert any(path.startswith("PARTA_BS.") for path in report.missing_source_paths)
    assert any(path.startswith("PARTA_PL.") for path in report.missing_source_paths)
    assert any(path.startswith("ScheduleCGFor23.") for path in report.missing_source_paths)


def test_itr3_preparation_accepts_an_explicit_complete_registry() -> None:
    """A registry covering every manifest path is accepted."""
    paths = {
        field.path
        for schedule in get_itr3_schedule_manifest()
        for field in schedule.fields
    }
    report = require_complete_itr3_preparation(paths)
    assert report.complete
    assert report.missing_source_paths == ()
