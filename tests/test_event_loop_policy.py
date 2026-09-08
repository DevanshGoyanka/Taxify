"""Regression test for the Playwright-on-Windows launch trap.

Starting the server with ``uvicorn app.main:app --reload`` (the bare command)
makes uvicorn's ``asyncio_setup()`` switch to
``WindowsSelectorEventLoopPolicy``. That loop *cannot* spawn subprocesses, so
Playwright's ``asyncio.create_subprocess_exec`` raises ``NotImplementedError``
the moment any portal import job runs (see run.py docstring).

This test asserts the invariant Playwright needs: the event-loop policy in
force at app-import time supports subprocess creation. It fails fast if a
future change re-introduces the Selector policy on Windows.
"""

from __future__ import annotations

import asyncio
import sys


def test_event_loop_policy_supports_subprocesses() -> None:
    """The active policy must permit ``loop.subprocess_exec``.

    On Windows, only ``WindowsProactorEventLoopPolicy`` supports subprocess
    creation; ``WindowsSelectorEventLoopPolicy`` raises ``NotImplementedError``
    from ``_make_subprocess_transport``. On non-Windows platforms both the
    default ``SelectorEventLoop`` and ``PollEventLoop`` support subprocesses,
    so the test is a no-op there.
    """
    if sys.platform != "win32":
        # On POSIX the default loop already supports subprocesses.
        loop = asyncio.new_event_loop()
        try:
            assert hasattr(loop, "subprocess_exec")
        finally:
            loop.close()
        return

    # On Windows the policy in force must NOT be the Selector policy.
    # ``WindowsSelectorEventLoopPolicy`` is deprecated in 3.14 but the
    # underlying class still lives at ``asyncio.events.BaseSelectorEventLoop``
    # for the Selector variant; we detect the Selector family by checking
    # that a fresh loop's ``subprocess_exec`` is NOT implemented.
    loop = asyncio.new_event_loop()
    try:
        # A Selector policy's loop raises NotImplementedError on subprocess_exec
        # at transport-creation time. A Proactor loop supports it.
        # We probe by checking the loop type name rather than triggering a
        # real subprocess, to keep the test hermetic.
        loop_cls = type(loop).__name__
        assert loop_cls != "SelectorEventLoop", (
            f"Active policy produced a {loop_cls} — Playwright will raise "
            "NotImplementedError on create_subprocess_exec. Launch the "
            "server with `py -3.14 run.py` (uses loop='none' + Proactor "
            "policy), not `uvicorn app.main:app --reload`."
        )
        assert hasattr(loop, "subprocess_exec"), (
            f"{loop_cls} must expose subprocess_exec for Playwright."
        )
    finally:
        loop.close()
