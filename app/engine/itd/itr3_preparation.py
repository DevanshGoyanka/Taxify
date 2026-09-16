"""Fail-closed preparation gates for canonical ITR-3 generation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Iterable

from app.engine.itd.itr3_manifest import (
    ITR3CompletenessReport,
    build_itr3_completeness_report,
)


# These schedules are serialized from a typed model (or a calculator result
# whose serializer covers the complete official subtree).  This is deliberately
# a conservative allow-list: PARTA_BS, PARTA_PL, and ScheduleCGFor23 are not
# included because their current builders still contain unsupported/defaulted
# fields.  A schedule is registered only when it is actually emitted.
ITR3_COMPLETE_SOURCE_SCHEDULES: frozenset[str] = frozenset({
    "ScheduleCYLA",
    "ScheduleBFLA",
    "ScheduleCFL",
    "PartB-TI",
    "PartB_TTI",
    "Verification",
    "ScheduleDEP",
    "ScheduleDCG",
    "ScheduleDPM",
    "ScheduleDOA",
    "ScheduleGST",
    "ScheduleICDS",
    "ScheduleESR",
    "ScheduleTPSA",
    "Schedule80_IA",
    "Schedule80_IB",
    "Schedule80_IC",
    "Schedule80RA",
    "Schedule10AA",
    "Schedule80D",
    "Schedule80DD",
    "Schedule80U",
})


def register_itr3_source_paths(document: Mapping[str, Any]) -> frozenset[str]:
    """Register emitted leaves and verified complete schedule subtrees.

    The returned paths are suitable for :func:`build_itr3_completeness_report`.
    Exact leaves are always retained.  A complete-schedule root is added only
    when that schedule is present and non-empty in the emitted document; this
    prevents an omitted optional schedule or an empty placeholder from being
    mistaken for typed coverage.

    Args:
        document: Wrapped or unwrapped emitted ITR-3 JSON document.

    Returns:
        Immutable source-path registry for the emitted document.
    """
    paths = set(extract_itr3_source_paths(document))
    root: Any = document.get("ITR", {}).get("ITR3", document)
    if isinstance(root, Mapping):
        for schedule_name in ITR3_COMPLETE_SOURCE_SCHEDULES:
            value = root.get(schedule_name)
            if value:
                paths.add(schedule_name)
    return frozenset(paths)


def build_itr3_emitted_completeness_report(document: Mapping[str, Any]) -> ITR3CompletenessReport:
    """Report completeness using the conservative emitted-source registry."""
    return build_itr3_completeness_report(register_itr3_source_paths(document))


class ITR3PreparationIncompleteError(ValueError):
    """Raised when canonical ITR-3 preparation lacks official field sources."""

    def __init__(self, report: ITR3CompletenessReport) -> None:
        """Store the full field coverage report for API error handling."""
        self.report = report
        preview = ", ".join(report.missing_source_paths[:12])
        suffix = " …" if len(report.missing_source_paths) > 12 else ""
        super().__init__(
            f"ITR-3 preparation is incomplete: {len(report.missing_source_paths)} "
            f"official field paths have no typed source ({preview}{suffix})."
        )


def extract_itr3_source_paths(document: Mapping[str, Any]) -> frozenset[str]:
    """Extract exact leaf paths emitted by a wrapped ITR-3 JSON document.

    Array item leaves use the manifest's ``[]`` notation, so one emitted row
    covers the typed structure without pretending that an empty array prepares
    any child field.
    """
    root: Any = document.get("ITR", {}).get("ITR3", document)
    paths: set[str] = set()

    def walk(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            if not value:
                return
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            if not value:
                return
            for child in value:
                walk(child, f"{path}[]")
            return
        paths.add(path)

    walk(root, "")
    return frozenset(paths)


def require_complete_itr3_document(document: Mapping[str, Any]) -> ITR3CompletenessReport:
    """Reject an emitted ITR-3 document when any official field is absent."""
    return require_complete_itr3_preparation(register_itr3_source_paths(document))


def require_complete_itr3_preparation(source_paths: Iterable[str]) -> ITR3CompletenessReport:
    """Require explicit typed coverage for every official ITR-3 field.

    Args:
        source_paths: Exact official JSON paths implemented by typed models and
            their builder mappings. A parent path covers its descendants only
            when the implementation genuinely maps the complete subtree.

    Returns:
        The complete report when no official field is missing.

    Raises:
        ITR3PreparationIncompleteError: If any mandatory or optional official
            field lacks an explicit source mapping.
    """
    report = build_itr3_completeness_report(frozenset(source_paths))
    if not report.complete:
        raise ITR3PreparationIncompleteError(report)
    return report


__all__ = [
    "ITR3PreparationIncompleteError",
    "ITR3_COMPLETE_SOURCE_SCHEDULES",
    "build_itr3_emitted_completeness_report",
    "extract_itr3_source_paths",
    "register_itr3_source_paths",
    "require_complete_itr3_document",
    "require_complete_itr3_preparation",
]
