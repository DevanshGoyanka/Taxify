"""Focused tests for conservative Phase 3B filing-mode classification."""

from __future__ import annotations

import inspect
import json
from typing import Optional

import pytest

from app.automation import job_worker
from app.automation.filed_returns_inventory import (
    FiledReturnInventoryOutcome,
    FiledReturnRecord,
    InventoryState,
    StatusEvent,
)
from app.automation.filing_mode_classifier import (
    EffectiveVersionState,
    FilingModeState,
    classify_filing_mode,
)


def record(
    row_identity: str,
    ay: str,
    *,
    filing_type: Optional[str] = "original",
    filing_date: Optional[str] = "Jul 31, 2025",
    events: tuple[str, ...] = ("successfully_e_verified",),
    actions: tuple[str, ...] = (),
) -> FiledReturnRecord:
    """Build a non-sensitive inventory record fixture."""
    return FiledReturnRecord(
        row_identity=row_identity,
        assessment_year=ay,
        itr_form="ITR-2",
        filing_type=filing_type,
        filing_date=filing_date,
        filing_section="139(1)",
        filed_by="self",
        status_events=tuple(StatusEvent(event, event) for event in events),
        available_actions=actions,
        json_available=True,
        source_page_number=1,
        position_on_page=1,
        acknowledgement_present=True,
        protected_acknowledgement="".join(["1"] * 15),
    )


def inventory(*records: FiledReturnRecord) -> FiledReturnInventoryOutcome:
    """Build a captured inventory fixture."""
    return FiledReturnInventoryOutcome(InventoryState.CAPTURED, tuple(records))


def test_no_current_ay_return_is_new_filing_with_nearest_prior_baseline() -> None:
    """A historical gap must remain explicit while the nearest prior is identified."""
    result = classify_filing_mode(
        inventory(record("prior", "2023-24", filing_date="Jul 31, 2023")),
        "2026-27",
    )

    assert result.state is FilingModeState.NEW_FILING
    assert result.filing_context is FilingModeState.NEW_FILING
    assert result.current_return_count == 0
    assert result.nearest_prior_assessment_year == "2023-24"
    assert result.nearest_prior_effective_row_identity == "prior"
    assert result.review_required is False


def test_no_returns_is_valid_new_filing() -> None:
    """An explicit no-return inventory allows a conservative original context."""
    result = classify_filing_mode(
        FiledReturnInventoryOutcome(InventoryState.NO_RETURNS),
        "2026-27",
    )

    assert result.state is FilingModeState.NEW_FILING
    assert result.version_groups == ()
    assert result.review_required is False


def test_current_valid_return_stops_new_filing_assumption() -> None:
    """A clearly valid current return must classify as an existing return."""
    result = classify_filing_mode(
        inventory(record("current", "2026-27")),
        "2026-27",
    )

    assert result.state is FilingModeState.CURRENT_RETURN_EXISTS
    assert result.filing_context is FilingModeState.CURRENT_RETURN_EXISTS
    assert result.current_effective_row_identity == "current"
    assert result.review_required is False
    assert result.revision_selected is False


def test_pending_e_verification_forces_review_without_new_or_revision_guess() -> None:
    """A submitted current return pending verification is a review-required state."""
    result = classify_filing_mode(
        inventory(
            record(
                "pending",
                "2026-27",
                events=("pending_for_e_verification", "itr_filed"),
            )
        ),
        "2026-27",
    )

    assert result.state is FilingModeState.REVIEW_REQUIRED
    assert result.filing_context is FilingModeState.CURRENT_RETURN_EXISTS
    assert "current_return_pending_e_verification" in result.review_reasons
    assert result.revision_selected is False
    assert result.updated_return_selected is False


def test_original_and_later_revised_resolve_by_filing_date_not_dom_order() -> None:
    """The latest valid submission must be resolved by date, not record order."""
    revised = record(
        "revised",
        "2025-26",
        filing_type="revised",
        filing_date="Dec 31, 2025",
    )
    original = record(
        "original",
        "2025-26",
        filing_type="original",
        filing_date="Sep 16, 2025",
    )

    result = classify_filing_mode(inventory(revised, original), "2026-27")
    group = result.version_groups[0]

    assert group.assessment_year == "2025-26"
    assert group.effective_version_state is EffectiveVersionState.RESOLVED
    assert group.effective_row_identity == "revised"
    assert group.explicit_parent_relationship_available is False
    assert result.nearest_prior_effective_row_identity == "revised"


@pytest.mark.parametrize("records", [
    (
        record("first", "2026-27", filing_date="Jul 31, 2026"),
        record("second", "2026-27", filing_date="Jul 31, 2026"),
    ),
    (
        record("first", "2026-27", filing_date=None),
        record("second", "2026-27", filing_date=None),
    ),
])
def test_ambiguous_current_versions_never_use_dom_order(
    records: tuple[FiledReturnRecord, ...],
) -> None:
    """Tied or absent dates must produce review instead of positional selection."""
    result = classify_filing_mode(inventory(*records), "2026-27")

    assert result.state is FilingModeState.REVIEW_REQUIRED
    assert result.filing_context is FilingModeState.CURRENT_RETURN_EXISTS
    assert result.current_effective_row_identity is None
    assert any(reason.startswith("ambiguous_version_group:") for reason in result.review_reasons)


def test_invalid_latest_record_is_excluded_before_effective_version_resolution() -> None:
    """Invalid submissions must not displace an earlier clearly valid version."""
    valid = record("valid", "2025-26", filing_date="Sep 16, 2025")
    invalid = record(
        "invalid",
        "2025-26",
        filing_type="revised",
        filing_date="Dec 31, 2025",
        events=("invalid",),
    )

    result = classify_filing_mode(inventory(invalid, valid), "2026-27")
    group = result.version_groups[0]

    assert group.effective_row_identity == "valid"
    assert group.excluded_row_identities == ("invalid",)


def test_demand_and_rectification_actions_require_review_without_selecting_response() -> None:
    """Demand/intimation evidence must not choose rectification or notice response."""
    result = classify_filing_mode(
        inventory(
            record(
                "current",
                "2026-27",
                events=("processed_with_demand_due",),
                actions=(
                    "download_intimation_order",
                    "submit_rectification_request",
                    "pay_now",
                ),
            )
        ),
        "2026-27",
    )

    assert result.state is FilingModeState.REVIEW_REQUIRED
    assert result.filing_context is FilingModeState.CURRENT_RETURN_EXISTS
    assert "notice_or_demand_indicator_requires_review" in result.review_reasons
    assert result.notice_response_selected is False
    assert result.revision_selected is False
    assert result.updated_return_selected is False


def test_inventory_failure_is_review_required() -> None:
    """Missing inventory evidence must never default to a new filing."""
    result = classify_filing_mode(
        FiledReturnInventoryOutcome(InventoryState.RETRYABLE_FAILURE),
        "2026-27",
    )

    assert result.state is FilingModeState.REVIEW_REQUIRED
    assert result.filing_context is FilingModeState.REVIEW_REQUIRED
    assert result.review_reasons == ("inventory_not_available",)


def test_serialization_contains_no_protected_acknowledgement() -> None:
    """Classification output must contain only non-sensitive row identities."""
    result = classify_filing_mode(inventory(record("safe-row", "2026-27")), "2026-27")
    encoded = json.dumps(result.to_dict())

    assert "".join(["1"] * 15) not in encoded
    assert "protected_acknowledgement" not in encoded
    assert "acknowledgement_number" not in encoded


def test_invalid_assessment_year_is_rejected() -> None:
    """Classification must not guess malformed current assessment years."""
    with pytest.raises(ValueError):
        classify_filing_mode(inventory(), "2026-28")


def test_worker_integrates_classification_without_portal_or_tax_actions() -> None:
    """Worker must classify captured metadata before existing extraction only."""
    source = inspect.getsource(job_worker._run_job)
    capture = source.index("inventory_outcome = await capture_filed_return_inventory(")
    classify = source.index("classification = classify_filing_mode(")
    extraction = source.index("# Step 4.5: Extract parsed data")

    assert capture < classify < extraction
    assert 'artifact_outcomes["filing_mode_classification"]' in source
    assert 'files["filing_mode_classification"]' not in source
    assert 'parsed["filing_mode_classification"]' not in source
    assert "download_filed" not in source
    assert "click_revision" not in source
