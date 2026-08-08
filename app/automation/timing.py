"""Credential-safe timing instrumentation for portal automation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

LogCallback = Callable[[str], None]
Clock = Callable[[], float]

_ALLOWED_EVENTS = frozenset(
    {
        "context requested",
        "context ready",
        "login page requested",
        "login page ready",
        "PAN submitted",
        "SAM ready",
        "password submitted",
        "dashboard ready",
        "Prefill navigation started",
        "Prefill download completed",
        "26AS navigation started",
        "26AS download completed",
        "AIS portal navigation started",
        "AIS and TIS request phase completed",
        "logout started",
        "logout completed",
    }
)


@dataclass(slots=True)
class AutomationTimeline:
    """Record monotonic automation events without storing sensitive values.

    Attributes:
        log_callback: Destination for formatted timing events.
        clock: Monotonic clock used to calculate elapsed durations.
    """

    log_callback: LogCallback
    clock: Clock = time.monotonic
    _started_at: float = field(init=False, repr=False)
    _last_at: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the timeline from the supplied monotonic clock."""
        now = self.clock()
        self._started_at = now
        self._last_at = now

    def mark(self, event: str) -> None:
        """Emit one sanitized timing event.

        Args:
            event: Static event name. It must not contain credentials, PANs,
                taxpayer names, URLs with tokens, or downloaded file contents.

        Raises:
            ValueError: If the event is not a predefined credential-safe label.
        """
        normalized = event.strip()
        if normalized not in _ALLOWED_EVENTS:
            raise ValueError("Timing event name is not in the credential-safe allowlist.")
        now = self.clock()
        total = max(0.0, now - self._started_at)
        delta = max(0.0, now - self._last_at)
        self._last_at = now
        self.log_callback(
            f"[Timing] {normalized} total={total:.3f}s delta={delta:.3f}s"
        )
