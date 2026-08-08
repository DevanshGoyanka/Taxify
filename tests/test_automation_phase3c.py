"""Focused tests for Phase 3C filing advisory and prior-year reference download."""

from __future__ import annotations

import json
from typing import Any, Optional

import pytest

from app.automation import filed_returns_inventory as inventory_mod
from app.automation.downloader_filed_return import (
    FiledReturnDownloadOutcome,
    FiledReturnDownloadState,
    download_filed_return_json,
)
from app.automation.filed_returns_inventory import (
    FiledReturnInventoryOutcome,
    FiledReturnRecord,
    InventoryState,
    StatusEvent,
)
from app.automation.filing_advisory import FilingAdvisory, generate_filing_advisory
from app.automation.filing_mode_classifier import (
    EffectiveVersionState,
    FilingModeClassification,
    FilingModeState,
    VersionGroup,
    classify_filing_mode,
)


def record(
    row_identity: str,
    ay: str,
    *,
    filing_type: str = "original",
    filing_date: str = "Jul 31, 2025",
    events: tuple[str, ...] = ("successfully_e_verified",),
) -> FiledReturnRecord:
    """Build a non-sensitive inventory record."""
    return FiledReturnRecord(
        row_identity=row_identity,
        assessment_year=ay,
        itr_form="ITR-2",
        filing_type=filing_type,
        filing_date=filing_date,
        filing_section="139(1)",
        filed_by="self",
        status_events=tuple(StatusEvent(event, event) for event in events),
        available_actions=("download_json",),
        json_available=True,
        source_page_number=1,
        position_on_page=1,
        acknowledgement_present=True,
        protected_acknowledgement="".join(["1"] * 15),
    )


# ── Advisory tests ──────────────────────────────────────────────────────────


def test_already_filed_advisory_when_current_return_exists() -> None:
    """A visible current-AY return must trigger the already-filed advisory."""
    inv = FiledReturnInventoryOutcome(
        InventoryState.CAPTURED,
        (record("current", "2026-27"), record("prior", "2025-26")),
    )
    cls = classify_filing_mode(inv, "2026-27")
    advisory = generate_filing_advisory(cls, inv)

    assert advisory.already_filed_advisory is True
    assert "already filed" in advisory.already_filed_advisory_message
    assert "2026-27" in advisory.already_filed_advisory_message
    assert advisory.revision_selected is False
    assert advisory.updated_return_selected is False
    assert advisory.notice_response_selected is False


def test_no_advisory_on_new_filing() -> None:
    """A new filing with no current-AY return must not trigger the advisory."""
    inv = FiledReturnInventoryOutcome(
        InventoryState.CAPTURED,
        (record("prior", "2025-26"),),
    )
    cls = classify_filing_mode(inv, "2026-27")
    advisory = generate_filing_advisory(cls, inv)

    assert advisory.already_filed_advisory is False
    assert advisory.already_filed_advisory_message == ""


def test_no_advisory_on_no_returns_inventory() -> None:
    """An empty inventory must not trigger an already-filed advisory."""
    inv = FiledReturnInventoryOutcome(InventoryState.NO_RETURNS)
    cls = classify_filing_mode(inv, "2026-27")
    advisory = generate_filing_advisory(cls, inv)

    assert advisory.already_filed_advisory is False
    assert advisory.download_row_identity is None


def test_advisory_surfaces_nearest_prior_reference_ay() -> None:
    """The advisory must identify the nearest prior resolved version as reference."""
    inv = FiledReturnInventoryOutcome(
        InventoryState.CAPTURED,
        (record("current", "2026-27"), record("prior", "2025-26")),
    )
    cls = classify_filing_mode(inv, "2026-27")
    advisory = generate_filing_advisory(cls, inv)

    assert advisory.prior_return_reference_ay == "2025-26"
    assert advisory.download_row_identity == "prior"
    assert advisory.download_assessment_year == "2025-26"


def test_advisory_does_not_serialize_protected_acknowledgement() -> None:
    """Advisory serialization must not contain acknowledgement values."""
    inv = FiledReturnInventoryOutcome(
        InventoryState.CAPTURED,
        (record("current", "2026-27"), record("prior", "2025-26")),
    )
    cls = classify_filing_mode(inv, "2026-27")
    advisory = generate_filing_advisory(cls, inv)
    encoded = json.dumps(advisory.to_dict())

    assert "".join(["1"] * 15) not in encoded
    assert "protected_acknowledgement" not in encoded


def test_advisory_no_download_target_when_inventory_failed() -> None:
    """A failed inventory must not produce a download target."""
    inv = FiledReturnInventoryOutcome(InventoryState.RETRYABLE_FAILURE)
    cls = classify_filing_mode(inv, "2026-27")
    advisory = generate_filing_advisory(cls, inv)

    assert advisory.download_row_identity is None
    assert advisory.download_assessment_year is None


# ── Downloader tests ────────────────────────────────────────────────────────


class DownloadLocator:
    """Minimal locator with download click tracking."""

    def __init__(self, *, visible: bool = True) -> None:
        """Configure locator visibility."""
        self.visible = visible
        self.clicks = 0

    @property
    def first(self) -> "DownloadLocator":
        """Return this locator."""
        return self

    async def is_visible(self, timeout: int = 0) -> bool:
        """Return configured visibility."""
        del timeout
        return self.visible

    async def click(self, timeout: int = 0) -> None:
        """Record activation."""
        del timeout
        self.clicks += 1


class Download:
    """Fake browser download object."""

    def __init__(self, content: bytes) -> None:
        """Store content."""
        self.content = content

    async def save_as(self, path: str) -> None:
        """Write content to path."""
        from pathlib import Path

        Path(path).write_bytes(self.content)


class DownloadInfo:
    """Fake download-info holder."""

    def __init__(self, content: bytes) -> None:
        """Create a completed download."""
        self.value = _awaitable(Download(content))


class DownloadContext:
    """Async context manager for download expectation."""

    def __init__(self, page: "DownloadPage") -> None:
        """Store page reference."""
        self.page = page

    async def __aenter__(self) -> DownloadInfo:
        """Enter download context."""
        return DownloadInfo(self.page.content)

    async def __aexit__(self, *args: Any) -> None:
        """Exit download context."""
        pass


class DownloadPage:
    """Minimal page with a Download JSON action and a valid JSON payload."""

    def __init__(self, content: bytes) -> None:
        """Configure page content."""
        self.content = content
        self.url = "https://eportal.incometax.gov.in/view-filed-returns"
        self.button = DownloadLocator()

    def is_closed(self) -> bool:
        """Return that the page is live."""
        return False

    def get_by_role(self, role: str, name: Any) -> DownloadLocator:
        """Expose Download JSON by role."""
        pattern = getattr(name, "pattern", str(name)).lower()
        if "download" in pattern and "json" in pattern:
            return self.button
        return DownloadLocator(visible=False)

    def get_by_text(self, name: Any, exact: bool = False) -> DownloadLocator:
        """Mirror role lookup."""
        del exact
        return self.get_by_role("link", name)

    def locator(self, selector: str) -> DownloadLocator:
        """Expose XPath fallback."""
        if "Download JSON" in selector:
            return self.button
        return DownloadLocator(visible=False)

    def expect_download(self, timeout: int) -> DownloadContext:
        """Return download expectation."""
        del timeout
        return DownloadContext(self)


@pytest.fixture()
def bypass_session_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip session expiry detection in downloader tests unless overridden."""
    async def not_expired(page: Any) -> bool:
        del page
        return False

    monkeypatch.setattr(
        "app.automation.downloader_filed_return.session_expired", not_expired
    )


async def _awaitable(value: Any) -> Any:
    """Return a value through an awaitable."""
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize("ay", ["2025-26", "2026-27"])
async def test_download_saves_valid_json_with_expected_filename(
    tmp_path: Any, ay: str, bypass_session_check: None
) -> None:
    """A valid download must be saved without validation errors."""
    payload = {"personalInfo": {"pan": "ABCDE1234F"}}
    page = DownloadPage(json.dumps(payload).encode())

    outcome = await download_filed_return_json(
        page=page,
        assessment_year=ay,
        target_row_identity="test-row-001",
        download_dir=tmp_path,
        timeout_ms=5_000,
    )

    safe_ay = ay.replace("-", "_")
    expected = tmp_path / f"ITR-{safe_ay}-FILED-RETURN.json"
    assert outcome.state is FiledReturnDownloadState.DOWNLOADED
    assert outcome.path == str(expected)
    assert expected.exists()
    assert page.button.clicks == 1


@pytest.mark.asyncio
async def test_download_returns_expired_session_state(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An expired session must return a dedicated terminal state."""
    import app.automation.downloader_filed_return as dl

    async def expired(page: Any) -> bool:
        del page
        return True

    monkeypatch.setattr(dl, "session_expired", expired)
    page = DownloadPage(b"{}")
    outcome = await download_filed_return_json(
        page=page,
        assessment_year="2025-26",
        target_row_identity="test-row-001",
        download_dir=tmp_path,
        timeout_ms=5_000,
    )
    assert outcome.state is FiledReturnDownloadState.SESSION_EXPIRED


@pytest.mark.asyncio
async def test_download_handles_empty_portal_response(
    tmp_path: Any, bypass_session_check: None
) -> None:
    """An empty download must be rejected without leaving partial files."""
    page = DownloadPage(b"")

    outcome = await download_filed_return_json(
        page=page,
        assessment_year="2025-26",
        target_row_identity="test-row-001",
        download_dir=tmp_path,
        timeout_ms=5_000,
    )

    assert outcome.state is FiledReturnDownloadState.RETRYABLE_FAILURE
    assert outcome.path is None


def test_download_outcome_serialization_excludes_protected_data() -> None:
    """Download outcomes must not carry raw download paths in reason text."""
    outcome = FiledReturnDownloadOutcome(
        state=FiledReturnDownloadState.DOWNLOADED,
        path="/safe/path.json",
        reason="ok",
        assessment_year="2025-26",
        source_row_identity="test-row-001",
    )
    encoded = json.dumps(outcome.to_dict())

    assert "/safe/path.json" in encoded
    assert "protected_acknowledgement" not in encoded


# ── Worker integration tests ────────────────────────────────────────────────


def test_worker_integrates_advisory_and_download_after_classification() -> None:
    """Worker must produce advisory and optional download before extraction."""
    import inspect

    from app.automation import job_worker

    source = inspect.getsource(job_worker._run_job)
    classify = source.index("classification = classify_filing_mode(")
    advisory = source.index("advisory = generate_filing_advisory(")
    extraction = source.index("# Step 4.5: Extract parsed data")

    assert classify < advisory < extraction
    assert 'artifact_outcomes["filing_advisory"]' in source
    assert 'artifact_outcomes["prior_year_return"]' in source
    assert 'files["prior_year_return"]' in source
    assert "prior_year_return_downloaded" in source
    assert "filing_advisory_generated" in source
    assert 'parsed["prior_year_return"]' not in source


def test_worker_never_extracts_prior_year_return() -> None:
    """Prior-year return must not enter the extraction pipeline."""
    import inspect

    from app.automation import job_worker

    source = inspect.getsource(job_worker._run_job)
    extraction_block = source[source.index("# Step 4.5: Extract parsed data"):]

    assert 'prior_year_return' not in extraction_block
