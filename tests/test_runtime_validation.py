"""Runtime guard regression tests for the supported Taxify launcher."""

from __future__ import annotations

import builtins
from types import ModuleType

import pytest

import run


def test_runtime_rejects_free_threaded_python(monkeypatch: pytest.MonkeyPatch) -> None:
    """The launcher must reject unsupported free-threaded Python builds."""
    monkeypatch.setattr(run.sysconfig, "get_config_var", lambda _: 1)
    with pytest.raises(SystemExit, match="py -3.14 run.py"):
        run._validate_runtime()


def test_runtime_reports_missing_pdf_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launcher must fail clearly when PDF dependencies are unavailable."""
    monkeypatch.setattr(run.sysconfig, "get_config_var", lambda _: 0)
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict | None = None,
        locals: dict | None = None,
        fromlist: tuple = (),
        level: int = 0,
    ) -> ModuleType:
        if name in {"fitz", "pikepdf"}:
            raise ImportError(name)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(SystemExit, match="PyMuPDF, pikepdf"):
        run._validate_runtime()


def test_runtime_accepts_supported_interpreter_and_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launcher must accept the standard runtime with PDF packages."""
    monkeypatch.setattr(run.sysconfig, "get_config_var", lambda _: 0)
    run._validate_runtime()
