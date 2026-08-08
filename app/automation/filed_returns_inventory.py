"""Privacy-safe inventory capture for ITD filed-return submissions.

Phase 3A observes filed returns and their visible lifecycle metadata only. It does
not select an effective return, classify a filing mode, download an artifact,
or import return data.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from app.automation.navigation import (
    MonotonicDeadline,
    navigate_income_tax_returns,
    resolve_itd_anchor,
    session_expired,
)

LogCallback = Callable[[str], None]

_AY = re.compile(r"\b(?:A\.?\s*Y\.?\s*[:.-]?\s*)?(20\d{2})\s*[-–]\s*(\d{2})\b", re.I)
_ITR = re.compile(r"\bITR\s*[:.-]?\s*(ITR[-\s]?\d+[A-Z]?)\b", re.I)
_ACK = re.compile(r"\b(?:Acknowledg(?:e)?ment\s*(?:No\.?|Number)?\s*[:.-]?\s*)?(\d{12,20})\b", re.I)
_FILING_TYPE = re.compile(r"Filing\s*Type\s*[:.-]?\s*(Original|Revised|Belated|Updated)\b", re.I)
_FILING_DATE = re.compile(r"Filing\s*Date\s*[:.-]?\s*([^\r\n]+)", re.I)
_FILING_SECTION = re.compile(r"Filing\s*Section\s*[:.-]?\s*([^\r\n]+)", re.I)
_FILED_BY = re.compile(r"Filed\s*By\s*[:.-]?\s*([^\r\n]+)", re.I)
_PAGE_RANGE = re.compile(r"\b(\d+)\s*[–-]\s*(\d+)\s+of\s+(\d+)\s+items?\b", re.I)
_PAGE_COUNT = re.compile(r"\b(\d+)\s+of\s+(\d+)\s+pages?\b", re.I)
_PAGE_SIZE = re.compile(r"Items\s+per\s+page\s*[:.-]?\s*(\d+)", re.I)
_FILINGS_TILL_DATE = re.compile(r"\b(\d+)\s+Filings?\s+till\s+date\b", re.I)

_STATUS_LABELS: tuple[tuple[str, str], ...] = (
    ("processed_with_demand_due", "Processed with demand due"),
    ("processed_with_no_demand_or_refund", "Processed with no demand/refund"),
    ("successfully_e_verified", "Successfully e-verified"),
    ("pending_for_e_verification", "Pending for e-verification"),
    ("under_processing", "Under Processing"),
    ("itr_filed", "ITR Filed"),
)
_ACTION_LABELS: tuple[tuple[str, str], ...] = (
    ("view_details", "View Details"),
    ("download_form", "Download Form"),
    ("download_receipt", "Download Receipt"),
    ("download_json", "Download JSON"),
    ("download_intimation_order", "Download Intimation Order"),
    ("submit_rectification_request", "Submit Rectification Request"),
    ("e_verify_return", "E-verify return"),
    ("pay_now", "Pay now"),
)


class InventoryState(str, Enum):
    """Terminal states for a filed-return inventory observation."""

    CAPTURED = "captured"
    NO_RETURNS = "no_returns"
    SESSION_EXPIRED = "session_expired"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass(frozen=True, slots=True)
class StatusEvent:
    """One visible, non-sensitive filed-return lifecycle event."""

    event_type: str
    portal_label: str


@dataclass(frozen=True, slots=True)
class FiledReturnRecord:
    """One observed portal submission with protected acknowledgement state.

    The acknowledgement is retained only in memory for future same-session
    matching. It is intentionally excluded from ``to_dict`` and object repr.
    """

    row_identity: str
    assessment_year: str
    itr_form: Optional[str]
    filing_type: Optional[str]
    filing_date: Optional[str]
    filing_section: Optional[str]
    filed_by: Optional[str]
    status_events: tuple[StatusEvent, ...]
    available_actions: tuple[str, ...]
    json_available: Optional[bool]
    source_page_number: int
    position_on_page: int
    acknowledgement_present: bool
    protected_acknowledgement: Optional[str] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize only allowlisted metadata, excluding protected values."""
        return {
            "row_identity": self.row_identity,
            "assessment_year": self.assessment_year,
            "itr_form": self.itr_form,
            "filing_type": self.filing_type,
            "filing_date": self.filing_date,
            "filing_section": self.filing_section,
            "filed_by": self.filed_by,
            "status_events": [asdict(event) for event in self.status_events],
            "available_actions": list(self.available_actions),
            "json_available": self.json_available,
            "source_page_number": self.source_page_number,
            "position_on_page": self.position_on_page,
            "acknowledgement_present": self.acknowledgement_present,
        }


@dataclass(frozen=True, slots=True)
class PaginationObservation:
    """Visible pagination metadata without implying return ordering."""

    page_number: int
    total_pages: Optional[int]
    page_size: Optional[int]
    visible_start: Optional[int]
    visible_end: Optional[int]
    total_items: Optional[int]


@dataclass(frozen=True, slots=True)
class FiledReturnInventoryOutcome:
    """Structured result of a Phase 3A inventory-only observation."""

    state: InventoryState
    records: tuple[FiledReturnRecord, ...] = ()
    pagination: tuple[PaginationObservation, ...] = ()
    portal_filings_till_date: Optional[int] = None
    count_semantics: str = "unknown"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe result that cannot expose acknowledgements."""
        return {
            "state": self.state.value,
            "records": [record.to_dict() for record in self.records],
            "pagination": [asdict(item) for item in self.pagination],
            "portal_filings_till_date": self.portal_filings_till_date,
            "count_semantics": self.count_semantics,
            "reason": self.reason,
        }


async def capture_filed_return_inventory(
    page: Any,
    *,
    timeout_ms: int = 30_000,
    max_pages: int = 100,
    log: Optional[LogCallback] = None,
) -> FiledReturnInventoryOutcome:
    """Capture visible filed-return inventory without selecting or downloading.

    Args:
        page: Authenticated Playwright-compatible ITD page.
        timeout_ms: Shared elapsed-time budget for navigation and pagination.
        max_pages: Defensive upper bound on portal pages to observe.
        log: Optional privacy-safe operational callback.

    Returns:
        Inventory metadata. Raw card text and acknowledgement values are never
        serialized or emitted to the callback.
    """
    if page is None:
        return _failure(InventoryState.PERMANENT_FAILURE, "A browser page is required.")
    if timeout_ms < 0 or max_pages <= 0:
        return _failure(InventoryState.PERMANENT_FAILURE, "Invalid inventory configuration.")

    deadline = MonotonicDeadline.after(timeout_ms)
    try:
        anchor = await resolve_itd_anchor(page)
        if await session_expired(anchor):
            return _failure(InventoryState.SESSION_EXPIRED, "The portal session has expired.")
        _emit(log, "[FILED RETURNS] Opening filed-return inventory.")
        if not await _open_filed_returns(anchor, deadline, log):
            return _failure(InventoryState.RETRYABLE_FAILURE, "View Filed Returns was not available.")

        records: list[FiledReturnRecord] = []
        pages: list[PaginationObservation] = []
        filings_till_date: Optional[int] = None
        seen_pages: set[int] = set()

        for fallback_page_number in range(1, max_pages + 1):
            if deadline.expired:
                return _failure(InventoryState.RETRYABLE_FAILURE, "Filed-return inventory timed out.")
            if await session_expired(anchor):
                return _failure(InventoryState.SESSION_EXPIRED, "The portal session has expired.")

            snapshot = await _snapshot_visible_inventory(anchor, deadline.remaining_ms)
            body_text = str(snapshot.get("body_text", ""))
            pagination = _parse_pagination(body_text, fallback_page_number)
            if pagination.page_number in seen_pages:
                break
            seen_pages.add(pagination.page_number)
            pages.append(pagination)
            if filings_till_date is None:
                match = _FILINGS_TILL_DATE.search(body_text)
                filings_till_date = int(match.group(1)) if match else None

            card_texts = snapshot.get("cards", [])
            if not isinstance(card_texts, list):
                card_texts = []
            for position, raw_text in enumerate(card_texts, start=1):
                record = _parse_card(str(raw_text), pagination.page_number, position)
                if record is not None:
                    records.append(record)
            _emit(
                log,
                f"[FILED RETURNS] Observed page {pagination.page_number}; "
                f"records_on_page={sum(1 for item in records if item.source_page_number == pagination.page_number)}.",
            )

            if pagination.total_pages is not None and pagination.page_number >= pagination.total_pages:
                break
            if not await _go_to_next_page(
                anchor,
                pagination.page_number,
                deadline,
            ):
                break

        if not records:
            if any((item.total_items or 0) > 0 for item in pages):
                return _failure(
                    InventoryState.RETRYABLE_FAILURE,
                    "Filed-return records were reported but their cards were not readable.",
                )
            if not _explicit_no_returns(body_text):
                return _failure(
                    InventoryState.RETRYABLE_FAILURE,
                    "Filed-return inventory did not reach a terminal state.",
                )
            return FiledReturnInventoryOutcome(
                state=InventoryState.NO_RETURNS,
                pagination=tuple(pages),
                portal_filings_till_date=filings_till_date,
                reason="No filed-return records were observed.",
            )
        _emit(log, f"[FILED RETURNS] Inventory captured; records={len(records)}.")
        return FiledReturnInventoryOutcome(
            state=InventoryState.CAPTURED,
            records=tuple(records),
            pagination=tuple(pages),
            portal_filings_till_date=filings_till_date,
        )
    except Exception:
        return _failure(
            InventoryState.RETRYABLE_FAILURE,
            "Filed-return inventory could not be captured.",
        )


async def _open_filed_returns(
    page: Any,
    deadline: MonotonicDeadline,
    log: Optional[LogCallback],
) -> bool:
    """Navigate to View Filed Returns using shared menus and semantic controls."""
    existing = await _find_visible_action(page, "View Filed Returns", min(250, deadline.remaining_ms))
    if existing is None:
        try:
            await navigate_income_tax_returns(
                page, timeout_ms=min(5_000, deadline.remaining_ms), log=log
            )
        except Exception as exc:
            _emit(
                log,
                "[FILED RETURNS] Shared navigation did not expose the action; "
                f"using local click fallback ({type(exc).__name__}).",
            )
        existing = await _find_visible_action(
            page, "View Filed Returns", min(500, deadline.remaining_ms)
        )
    if existing is None and not deadline.expired:
        existing = await _open_filed_returns_locally(page, deadline, log)
    if existing is None:
        _emit(log, "[FILED RETURNS] View Filed Returns action was not found.")
        return False
    _emit(log, "[FILED RETURNS] View Filed Returns action ready.")
    await existing.click(timeout=max(1, min(750, deadline.remaining_ms)))
    ready = await _wait_for_inventory_page(page, deadline)
    if ready:
        _emit(log, "[FILED RETURNS] Filed-return inventory page ready.")
    return ready


async def _open_filed_returns_locally(
    page: Any,
    deadline: MonotonicDeadline,
    log: Optional[LogCallback],
) -> Optional[Any]:
    """Explicitly click menu levels when hover-only shared navigation stalls."""
    efile = await _find_visible_action(page, "e-File", min(2_000, deadline.remaining_ms))
    if efile is None:
        _emit(log, "[FILED RETURNS] Local fallback could not find e-File.")
        return None
    if not await _activate_menu(efile, deadline):
        return None

    returns = await _find_visible_action(
        page, "Income Tax Returns", min(2_000, deadline.remaining_ms)
    )
    if returns is None:
        _emit(log, "[FILED RETURNS] Local fallback could not find Income Tax Returns.")
        return None
    if not await _activate_menu(returns, deadline):
        return None

    action = await _find_visible_action(
        page, "View Filed Returns", min(3_000, deadline.remaining_ms)
    )
    if action is not None:
        _emit(log, "[FILED RETURNS] Local click fallback exposed the action.")
    return action


async def _activate_menu(locator: Any, deadline: MonotonicDeadline) -> bool:
    """Click a menu control, falling back to force-click and hover."""
    timeout_ms = max(1, min(750, deadline.remaining_ms))
    for operation in (
        lambda: locator.click(timeout=timeout_ms),
        lambda: locator.click(force=True, timeout=timeout_ms),
        lambda: locator.hover(timeout=timeout_ms),
    ):
        try:
            await operation()
            return True
        except Exception:
            continue
    return False


async def _find_visible_action(page: Any, label: str, timeout_ms: int) -> Optional[Any]:
    """Find one exact visible semantic action under a bounded probe."""
    deadline = MonotonicDeadline.after(timeout_ms)
    pattern = re.compile(rf"^\s*{re.escape(label)}\s*$", re.I)
    while True:
        candidates: list[Any] = []
        for role in ("link", "button", "menuitem"):
            try:
                candidates.append(page.get_by_role(role, name=pattern).first)
            except Exception:
                continue
        try:
            candidates.append(page.get_by_text(pattern, exact=True).first)
        except Exception:
            pass
        try:
            candidates.append(page.locator(f"//*[normalize-space(.)='{label}']").first)
        except Exception:
            pass
        for candidate in candidates:
            try:
                if await candidate.is_visible(timeout=1):
                    return candidate
            except Exception:
                continue
        if deadline.expired:
            return None
        await deadline.sleep(0.05)


async def _wait_for_inventory_page(page: Any, deadline: MonotonicDeadline) -> bool:
    """Wait for cards, positive pagination, or an explicit no-return message.

    The Angular page initially renders its heading and a ``0 of 0`` paginator
    before the asynchronous inventory request completes. Those shell values are
    not a terminal empty state and must never be captured as ``NO_RETURNS``.
    """
    while not deadline.expired:
        snapshot = await _snapshot_visible_inventory(page, deadline.remaining_ms)
        text = str(snapshot.get("body_text", ""))
        cards = snapshot.get("cards", [])
        if isinstance(cards, list) and cards:
            return True
        if _explicit_no_returns(text):
            return True
        pagination = _parse_pagination(text, 1)
        if (
            pagination.total_items is not None
            and pagination.total_items > 0
            and pagination.total_pages is not None
            and pagination.total_pages > 0
        ):
            return True
        await deadline.sleep(0.1)
    return False


def _explicit_no_returns(text: str) -> bool:
    """Return whether the portal explicitly states that no returns exist."""
    return bool(
        re.search(
            r"no\s+(?:filed\s+)?returns?(?:\s+(?:available|found))?"
            r"|no\s+records?\s+(?:available|found)",
            text,
            re.IGNORECASE,
        )
    )


async def _snapshot_visible_inventory(page: Any, timeout_ms: int) -> dict[str, Any]:
    """Read card text and page text in memory without logging or persistence."""
    if timeout_ms <= 0:
        raise TimeoutError("Inventory deadline expired.")
    script = """
() => {
  const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  const labels = Array.from(document.querySelectorAll('body *')).filter(
    (el) => visible(el) && /^Filing\\s*Type$/i.test((el.textContent || '').trim())
  );
  const cards = [];
  const seen = new Set();
  for (const label of labels) {
    let node = label;
    let metadataCandidate = null;
    let completeCandidate = null;
    while (node && node !== document.body) {
      const text = (node.innerText || '').trim();
      const hasMetadata = /Acknowledg(?:e)?ment\s*No/i.test(text) &&
        /Filing\s*(?:Date|Section)/i.test(text) && /A\.?\s*Y\.?\s*20\d{2}/i.test(text);
      if (hasMetadata && !metadataCandidate) metadataCandidate = node;
      if (hasMetadata && /(View\s+Details|Download\s+JSON|ITR\s+Filed|Processed|e-verification)/i.test(text)) {
        completeCandidate = node;
        break;
      }
      node = node.parentElement;
    }
    const card = completeCandidate || metadataCandidate;
    if (card && !seen.has(card)) {
      seen.add(card);
      cards.push((card.innerText || '').trim());
    }
  }
  return { body_text: document.body ? document.body.innerText : '', cards };
}
"""
    result = await page.evaluate(script)
    return result if isinstance(result, dict) else {"body_text": "", "cards": []}


def _parse_card(text: str, page_number: int, position: int) -> Optional[FiledReturnRecord]:
    """Parse one card through an allowlist and retain its acknowledgement privately."""
    ay_match = _AY.search(text)
    if ay_match is None:
        return None
    assessment_year = f"{ay_match.group(1)}-{ay_match.group(2)}"
    itr_match = _ITR.search(text)
    type_match = _FILING_TYPE.search(text)
    date_match = _FILING_DATE.search(text)
    section_match = _FILING_SECTION.search(text)
    filed_by_match = _FILED_BY.search(text)
    ack_match = _ACK.search(text)

    events = tuple(
        StatusEvent(event_type=event_type, portal_label=label)
        for event_type, label in _STATUS_LABELS
        for _ in range(len(re.findall(re.escape(label), text, re.I)))
    )
    actions = tuple(
        action_type
        for action_type, label in _ACTION_LABELS
        if re.search(re.escape(label), text, re.I)
    )
    json_available: Optional[bool] = True if "download_json" in actions else None
    return FiledReturnRecord(
        row_identity=f"filed-return-{uuid.uuid4().hex}",
        assessment_year=assessment_year,
        itr_form=itr_match.group(1).replace(" ", "-").upper() if itr_match else None,
        filing_type=type_match.group(1).lower() if type_match else None,
        filing_date=_clean_value(date_match.group(1)) if date_match else None,
        filing_section=_clean_value(section_match.group(1)) if section_match else None,
        filed_by=_normalize_filed_by(filed_by_match.group(1)) if filed_by_match else None,
        status_events=events,
        available_actions=actions,
        json_available=json_available,
        source_page_number=page_number,
        position_on_page=position,
        acknowledgement_present=ack_match is not None,
        protected_acknowledgement=ack_match.group(1) if ack_match else None,
    )


def _parse_pagination(text: str, fallback_page_number: int) -> PaginationObservation:
    """Parse visible page counters while preserving unknown values as null."""
    page_match = _PAGE_COUNT.search(text)
    range_match = _PAGE_RANGE.search(text)
    size_match = _PAGE_SIZE.search(text)
    return PaginationObservation(
        page_number=int(page_match.group(1)) if page_match else fallback_page_number,
        total_pages=int(page_match.group(2)) if page_match else None,
        page_size=int(size_match.group(1)) if size_match else None,
        visible_start=int(range_match.group(1)) if range_match else None,
        visible_end=int(range_match.group(2)) if range_match else None,
        total_items=int(range_match.group(3)) if range_match else None,
    )


async def _go_to_next_page(
    page: Any,
    current_page_number: int,
    deadline: MonotonicDeadline,
) -> bool:
    """Activate an enabled next control and wait for the page index to change."""
    if deadline.expired:
        return False
    pattern = re.compile(r"^\s*(?:Next|Next page)\s*$", re.I)
    candidates: list[Any] = []
    for role in ("button", "link"):
        try:
            candidates.append(page.get_by_role(role, name=pattern).first)
        except Exception:
            continue
    for selector in (
        "button[aria-label*='next' i]",
        "a[aria-label*='next' i]",
        ".mat-paginator-navigation-next",
    ):
        try:
            candidates.append(page.locator(selector).first)
        except Exception:
            continue
    for candidate in candidates:
        try:
            if not await candidate.is_visible(timeout=1):
                continue
            if await candidate.is_disabled():
                continue
            aria_disabled = await candidate.get_attribute("aria-disabled")
            if str(aria_disabled).lower() == "true":
                continue
            await candidate.click(timeout=max(1, min(750, deadline.remaining_ms)))
            while not deadline.expired:
                snapshot = await _snapshot_visible_inventory(page, deadline.remaining_ms)
                next_page = _PAGE_COUNT.search(str(snapshot.get("body_text", "")))
                if next_page and int(next_page.group(1)) != current_page_number:
                    return True
                await deadline.sleep(0.1)
            return False
        except Exception:
            continue
    return False


def _clean_value(value: str) -> Optional[str]:
    """Normalize one allowlisted single-line portal value."""
    cleaned = re.sub(r"\s+", " ", value).strip(" :.-")
    return cleaned[:100] or None


def _normalize_filed_by(value: str) -> Optional[str]:
    """Retain only non-identifying filed-by categories."""
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    lowered = cleaned.casefold()
    if lowered in {"self", "eri", "trp", "representative assessee"}:
        return lowered
    return "other"


def _failure(state: InventoryState, reason: str) -> FiledReturnInventoryOutcome:
    """Build a terminal outcome containing only constant safe diagnostics."""
    return FiledReturnInventoryOutcome(state=state, reason=reason)


def _emit(log: Optional[LogCallback], message: str) -> None:
    """Emit privacy-safe operational metadata only."""
    if log is not None:
        log(message)
