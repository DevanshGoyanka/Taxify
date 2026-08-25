"""Conservative filing advisory and read-only reference selection.

Phase 3C does not import, compute from, or reconcile any downloaded
filed-return JSON. It generates advisory metadata only:

- ``already_filed_advisory``: current AY return exists and must not be
  overwritten or confused with a new filing.
- ``prior_return_reference_ay``: assessment year of the read-only
  prior-year JSON reference.
- ``download_row_identity``: which inventory row to download as the
  read-only reference.

No portal action is clicked here. No revision/updated-return/belated
workflow is selected here. Those are explicit user-driven flows that
require downstream Phase 4+ validation and user confirmation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from app.automation.filed_returns_inventory import (
    FiledReturnInventoryOutcome,
    InventoryState,
)
from app.automation.filing_mode_classifier import (
    FilingModeClassification,
    FilingModeState,
)


@dataclass(frozen=True, slots=True)
class FilingAdvisory:
    """Conservative advisory metadata for one automation run.

    Attributes:
        already_filed_advisory: Whether the current AY already has a return.
        already_filed_advisory_message: Human-readable advisory text.
        prior_return_reference_ay: AY of the read-only prior-year reference.
        download_row_identity: Inventory row identity to download.
        download_assessment_year: Assessment year of the download target.
        revision_selected: Always false at this phase.
        updated_return_selected: Always false at this phase.
        notice_response_selected: Always false at this phase.
        current_ay_already_filed: True when the current AY has a filed return.
        current_ay_is_revised: True when the effective current-AY return was
            filed under section 139(5) — i.e. the last filed ITR for this AY
            was already a revised return.
        current_ay_filing_section: The filing section of the effective
            current-AY return (e.g. "139(1)", "139(5)").
        download_is_current_ay: True when the download target is the
            current-AY return (for revision) rather than a prior-AY return.
        requires_user_confirmation_for_revision: True when the user must
            explicitly confirm a revised-return flow before the current-AY
            filed ITR is populated.
    """

    already_filed_advisory: bool
    already_filed_advisory_message: str
    prior_return_reference_ay: Optional[str]
    download_row_identity: Optional[str]
    download_assessment_year: Optional[str]
    revision_selected: bool = False
    updated_return_selected: bool = False
    notice_response_selected: bool = False
    current_ay_already_filed: bool = False
    current_ay_is_revised: bool = False
    current_ay_filing_section: Optional[str] = None
    download_is_current_ay: bool = False
    requires_user_confirmation_for_revision: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe advisory without protected data."""
        return asdict(self)


def generate_filing_advisory(
    classification: FilingModeClassification,
    inventory: FiledReturnInventoryOutcome,
) -> FilingAdvisory:
    """Generate a conservative filing advisory from classification and inventory.

    Args:
        classification: Phase 3B classification outcome.
        inventory: Phase 3A inventory outcome.

    Returns:
        Advisory metadata. Revision, updated-return, and notice-response
        flags are always false because no user confirmation has been obtained.
    """
    current_ay = classification.current_assessment_year
    already_filed = classification.current_ay_already_filed
    is_revised = classification.current_ay_is_revised
    message = ""
    if already_filed:
        if is_revised:
            message = (
                f"ITR for AY {current_ay} is already filed as a REVISED return "
                f"(section {classification.current_ay_filing_section or '139(5)'}). "
                "The last filed ITR was a revised return. To file another revised "
                "return, explicitly confirm the revised-return flow."
            )
        else:
            message = (
                f"ITR for AY {current_ay} is already filed "
                f"(section {classification.current_ay_filing_section or '139(1)'}). "
                "To file a revised return, explicitly confirm the revised-return flow."
            )

    prior_ay = classification.nearest_prior_assessment_year
    download_identity: Optional[str] = None
    download_ay: Optional[str] = None

    # Download logic:
    # - If the current AY is already filed, we need the current-AY filed
    #   return for revision — but ONLY if the user has explicitly confirmed
    #   a revised-return flow.  Since revision_selected is always false at
    #   this phase, we do NOT download the current-AY return; we surface the
    #   flag so the frontend can ask the user to confirm.
    # - Otherwise, download the nearest prior-AY return as a read-only
    #   reference (no user confirmation needed).
    if (
        prior_ay
        and classification.nearest_prior_effective_row_identity
        and inventory.state in {InventoryState.CAPTURED, InventoryState.NO_RETURNS}
    ):
        download_identity = classification.nearest_prior_effective_row_identity
        download_ay = prior_ay

    return FilingAdvisory(
        already_filed_advisory=already_filed,
        already_filed_advisory_message=message,
        prior_return_reference_ay=prior_ay,
        download_row_identity=download_identity,
        download_assessment_year=download_ay,
        current_ay_already_filed=already_filed,
        current_ay_is_revised=is_revised,
        current_ay_filing_section=classification.current_ay_filing_section,
        download_is_current_ay=False,  # never auto-download current-AY for revision
        requires_user_confirmation_for_revision=already_filed,
    )
