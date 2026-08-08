"""Deterministic, conservative classification of filed-return inventories.

Phase 3B classifies captured metadata only. It never clicks portal actions,
downloads artifacts, imports return data, or chooses a legal response workflow
when the observed evidence is incomplete or ambiguous.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Optional

from app.automation.filed_returns_inventory import (
    FiledReturnInventoryOutcome,
    FiledReturnRecord,
    InventoryState,
)
from app.automation.years import TaxYearContext


class FilingModeState(str, Enum):
    """Supported conservative filing-mode classifications."""

    NEW_FILING = "new_filing"
    CURRENT_RETURN_EXISTS = "current_return_exists"
    REVISION_CANDIDATE = "revision_candidate"
    UPDATED_RETURN_CANDIDATE = "updated_return_candidate"
    NOTICE_RESPONSE_REQUIRED = "notice_response_required"
    REVIEW_REQUIRED = "review_required"


class EffectiveVersionState(str, Enum):
    """Resolution state for one assessment-year version group."""

    NONE = "none"
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"


_INVALID_EVENT_TYPES = frozenset(
    {
        "invalid",
        "withdrawn",
        "draft",
        "incomplete",
        "defective_uncured",
    }
)
_VALID_EVENT_TYPES = frozenset(
    {
        "successfully_e_verified",
        "under_processing",
        "processed_with_demand_due",
        "processed_with_no_demand_or_refund",
    }
)
_NOTICE_INDICATOR_EVENTS = frozenset(
    {
        "processed_with_demand_due",
        "notice_issued",
        "defective",
        "defective_uncured",
    }
)
_NOTICE_INDICATOR_ACTIONS = frozenset(
    {
        "download_intimation_order",
        "submit_rectification_request",
        "pay_now",
    }
)
_DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d")


@dataclass(frozen=True, slots=True)
class VersionGroup:
    """Derived grouping of submissions for one assessment year."""

    assessment_year: str
    row_identities: tuple[str, ...]
    effective_version_state: EffectiveVersionState
    effective_row_identity: Optional[str]
    excluded_row_identities: tuple[str, ...]
    ambiguity_reasons: tuple[str, ...]
    grouping_basis: str = "assessment_year"
    explicit_parent_relationship_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe group without protected acknowledgement data."""
        result = asdict(self)
        result["effective_version_state"] = self.effective_version_state.value
        return result


@dataclass(frozen=True, slots=True)
class FilingModeClassification:
    """Phase 3B classification with explicit evidence and uncertainty."""

    state: FilingModeState
    filing_context: FilingModeState
    current_assessment_year: str
    current_return_count: int
    current_effective_row_identity: Optional[str]
    nearest_prior_assessment_year: Optional[str]
    nearest_prior_effective_row_identity: Optional[str]
    review_required: bool
    review_reasons: tuple[str, ...]
    notice_indicators: tuple[str, ...]
    version_groups: tuple[VersionGroup, ...]
    revision_selected: bool = False
    updated_return_selected: bool = False
    notice_response_selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize classification metadata without sensitive identifiers."""
        return {
            "state": self.state.value,
            "filing_context": self.filing_context.value,
            "current_assessment_year": self.current_assessment_year,
            "current_return_count": self.current_return_count,
            "current_effective_row_identity": self.current_effective_row_identity,
            "nearest_prior_assessment_year": self.nearest_prior_assessment_year,
            "nearest_prior_effective_row_identity": self.nearest_prior_effective_row_identity,
            "review_required": self.review_required,
            "review_reasons": list(self.review_reasons),
            "notice_indicators": list(self.notice_indicators),
            "version_groups": [group.to_dict() for group in self.version_groups],
            "revision_selected": self.revision_selected,
            "updated_return_selected": self.updated_return_selected,
            "notice_response_selected": self.notice_response_selected,
        }


def classify_filing_mode(
    inventory: FiledReturnInventoryOutcome,
    current_assessment_year: str,
) -> FilingModeClassification:
    """Classify filing mode from a completed inventory observation.

    Args:
        inventory: Phase 3A filed-return inventory outcome.
        current_assessment_year: AY independently requested by the current job.

    Returns:
        A conservative classification. Candidate legal workflows remain false
        unless a future phase supplies explicit evidence and user intent.

    Raises:
        ValueError: If the current assessment year is malformed.
    """
    current_ay = TaxYearContext.from_assessment_year(current_assessment_year).assessment_year
    if inventory.state not in {InventoryState.CAPTURED, InventoryState.NO_RETURNS}:
        return _classification(
            FilingModeState.REVIEW_REQUIRED,
            current_ay,
            (),
            (),
            review_reasons=("inventory_not_available",),
        )

    records = tuple(inventory.records)
    groups = tuple(
        _build_version_group(ay, grouped)
        for ay, grouped in _group_by_assessment_year(records)
    )
    current_records = tuple(record for record in records if record.assessment_year == current_ay)
    current_group = next((group for group in groups if group.assessment_year == current_ay), None)
    prior_group = _nearest_prior_group(groups, current_ay)
    notice_indicators = _notice_indicators(records)
    reasons: list[str] = []

    if not current_records:
        state = FilingModeState.NEW_FILING
    else:
        state = FilingModeState.CURRENT_RETURN_EXISTS
        if current_group is None or current_group.effective_version_state is not EffectiveVersionState.RESOLVED:
            reasons.append("current_effective_version_unresolved")
        if any(_has_event(record, "pending_for_e_verification") and not _has_any_event(record, _VALID_EVENT_TYPES) for record in current_records):
            reasons.append("current_return_pending_e_verification")
        if any(_has_any_event(record, _INVALID_EVENT_TYPES) for record in current_records):
            reasons.append("current_return_has_excluded_status")

    if notice_indicators:
        reasons.append("notice_or_demand_indicator_requires_review")
    reasons.extend(
        f"ambiguous_version_group:{group.assessment_year}"
        for group in groups
        if group.effective_version_state is EffectiveVersionState.AMBIGUOUS
    )
    reasons = list(dict.fromkeys(reasons))
    review_required = bool(reasons)
    final_state = FilingModeState.REVIEW_REQUIRED if review_required else state
    return FilingModeClassification(
        state=final_state,
        filing_context=state,
        current_assessment_year=current_ay,
        current_return_count=len(current_records),
        current_effective_row_identity=(
            current_group.effective_row_identity if current_group is not None else None
        ),
        nearest_prior_assessment_year=(prior_group.assessment_year if prior_group else None),
        nearest_prior_effective_row_identity=(
            prior_group.effective_row_identity if prior_group else None
        ),
        review_required=bool(reasons),
        review_reasons=tuple(reasons),
        notice_indicators=notice_indicators,
        version_groups=groups,
    )


def _classification(
    state: FilingModeState,
    current_ay: str,
    records: tuple[FiledReturnRecord, ...],
    groups: tuple[VersionGroup, ...],
    *,
    review_reasons: tuple[str, ...],
) -> FilingModeClassification:
    """Build an outcome for terminal inventory-level uncertainty."""
    del records
    return FilingModeClassification(
        state=state,
        filing_context=FilingModeState.REVIEW_REQUIRED,
        current_assessment_year=current_ay,
        current_return_count=0,
        current_effective_row_identity=None,
        nearest_prior_assessment_year=None,
        nearest_prior_effective_row_identity=None,
        review_required=True,
        review_reasons=review_reasons,
        notice_indicators=(),
        version_groups=groups,
    )


def _group_by_assessment_year(
    records: Iterable[FiledReturnRecord],
) -> tuple[tuple[str, tuple[FiledReturnRecord, ...]], ...]:
    """Group records by normalized AY in descending year order."""
    grouped: dict[str, list[FiledReturnRecord]] = {}
    for record in records:
        grouped.setdefault(record.assessment_year, []).append(record)
    return tuple(
        (ay, tuple(grouped[ay]))
        for ay in sorted(grouped, key=_ay_start, reverse=True)
    )


def _build_version_group(
    assessment_year: str,
    records: tuple[FiledReturnRecord, ...],
) -> VersionGroup:
    """Resolve the latest clearly valid version without relying on DOM order."""
    excluded = tuple(record for record in records if _has_any_event(record, _INVALID_EVENT_TYPES))
    eligible = tuple(record for record in records if record not in excluded and _has_any_event(record, _VALID_EVENT_TYPES))
    ambiguities: list[str] = []
    effective: Optional[FiledReturnRecord] = None

    if not eligible:
        if records:
            ambiguities.append("no_clearly_valid_submission")
        state = EffectiveVersionState.NONE if not records else EffectiveVersionState.AMBIGUOUS
    else:
        dated = [(record, _parse_filing_date(record.filing_date)) for record in eligible]
        if any(date is None for _, date in dated):
            ambiguities.append("filing_date_missing_or_unparseable")
        known = [(record, date) for record, date in dated if date is not None]
        if known:
            latest_date = max(date for _, date in known)
            latest = [record for record, date in known if date == latest_date]
            if len(latest) == 1:
                effective = latest[0]
            else:
                ambiguities.append("multiple_valid_submissions_share_latest_date")
        if effective is None and len(eligible) == 1:
            effective = eligible[0]
        state = EffectiveVersionState.RESOLVED if effective and not ambiguities else EffectiveVersionState.AMBIGUOUS

    return VersionGroup(
        assessment_year=assessment_year,
        row_identities=tuple(sorted(record.row_identity for record in records)),
        effective_version_state=state,
        effective_row_identity=effective.row_identity if state is EffectiveVersionState.RESOLVED else None,
        excluded_row_identities=tuple(sorted(record.row_identity for record in excluded)),
        ambiguity_reasons=tuple(ambiguities),
    )


def _nearest_prior_group(
    groups: tuple[VersionGroup, ...],
    current_ay: str,
) -> Optional[VersionGroup]:
    """Return the nearest earlier AY with a resolved effective version."""
    current_start = _ay_start(current_ay)
    candidates = [
        group
        for group in groups
        if _ay_start(group.assessment_year) < current_start
        and group.effective_version_state is EffectiveVersionState.RESOLVED
    ]
    return max(candidates, key=lambda group: _ay_start(group.assessment_year), default=None)


def _notice_indicators(records: Iterable[FiledReturnRecord]) -> tuple[str, ...]:
    """Return normalized indicators without selecting any response workflow."""
    indicators: set[str] = set()
    for record in records:
        event_types = {event.event_type for event in record.status_events}
        indicators.update(event_types & _NOTICE_INDICATOR_EVENTS)
        indicators.update(set(record.available_actions) & _NOTICE_INDICATOR_ACTIONS)
    return tuple(sorted(indicators))


def _has_event(record: FiledReturnRecord, event_type: str) -> bool:
    """Return whether one normalized event is present."""
    return any(event.event_type == event_type for event in record.status_events)


def _has_any_event(record: FiledReturnRecord, event_types: frozenset[str]) -> bool:
    """Return whether any event from a normalized set is present."""
    return any(event.event_type in event_types for event in record.status_events)


def _parse_filing_date(value: Optional[str]) -> Optional[datetime]:
    """Parse portal display dates conservatively without locale guessing."""
    if not value:
        return None
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), date_format)
        except ValueError:
            continue
    return None


def _ay_start(value: str) -> int:
    """Return the starting calendar year from a validated AY string."""
    return int(TaxYearContext.from_assessment_year(value).assessment_year[:4])
