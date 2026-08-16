"""
Standalone entry point for the FastAPI server.

Uses loop="none" to bypass uvicorn's asyncio_setup() which on Windows
deliberately switches to WindowsSelectorEventLoopPolicy — a loop that cannot
spawn subprocesses (NotImplementedError). Keeping the default
WindowsProactorEventLoopPolicy lets Playwright launch Chromium.

As defense-in-depth, we *also* set WindowsProactorEventLoopPolicy
explicitly before importing uvicorn, so that even if a caller runs
``uvicorn app.main:app --reload`` (which bypasses run.py) the policy is
already correct for the imported app's background tasks.
"""
from __future__ import annotations

import asyncio
import sys
import sysconfig

if sys.platform == "win32":
    # The Proactor event loop supports subprocesses (required by Playwright).
    # This must run BEFORE any uvicorn import that calls asyncio.set_event_loop_policy.
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn


def _validate_runtime() -> None:
    """Reject unsupported Python runtimes and missing PDF dependencies.

    Taxify's AIS/TIS pipeline requires PyMuPDF (``fitz``) and ``pikepdf``.
    Their Windows wheels currently do not support free-threaded CPython, so
    running via a ``python*t.exe`` interpreter would allow the server to start
    but make every PDF extraction fail later in the background worker.

    Raises:
        SystemExit: If Python is free-threaded or a PDF dependency is missing.
    """
    if sysconfig.get_config_var("Py_GIL_DISABLED") == 1:
        raise SystemExit(
            "Taxify PDF extraction does not support free-threaded Python yet. "
            "Start the server with the standard interpreter: py -3.14 run.py"
        )

    missing: list[str] = []
    try:
        import fitz  # noqa: F401
    except ImportError:
        missing.append("PyMuPDF")
    try:
        import pikepdf  # noqa: F401
    except ImportError:
        missing.append("pikepdf")

    if missing:
        packages = " ".join(missing)
        raise SystemExit(
            f"Missing PDF dependencies: {', '.join(missing)}. "
            f"Install them with: {sys.executable} -m pip install {packages}"
        )


if __name__ == "__main__":
    _validate_runtime()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        loop="none",
    )
