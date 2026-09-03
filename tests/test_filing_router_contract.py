"""Static route and worker contract tests for Type-3 filing."""

from __future__ import annotations

import inspect

import pytest

from app.automation import job_worker
from app.db.models import AutomationJob, FilingJob
from app.filing_automation import worker as filing_worker
from app.main import app
from app.routers.filing import _normalize_form
from fastapi import HTTPException


def test_itr2_form_normalizes_and_itr3_is_rejected() -> None:
    assert _normalize_form("itr2") == "ITR-2"
    with pytest.raises(HTTPException) as caught:
        _normalize_form("ITR-3")
    assert caught.value.status_code == 422
    assert "ITR-3" in str(caught.value.detail)


def _registered_paths(router) -> set[str]:
    """Collect every route path reachable from an app or router.

    Starlette now wraps anything added via ``include_router`` in an
    ``_IncludedRouter`` rather than flattening its routes into ``app.routes``.
    Those wrappers expose the nested router as ``original_router`` and have no
    ``path`` of their own, so reading ``route.path`` off every entry raises
    AttributeError. Recurse instead of assuming a flat list.
    """
    paths: set[str] = set()
    for route in getattr(router, "routes", []):
        path = getattr(route, "path", None)
        if path is not None:
            paths.add(path)
        nested = getattr(route, "original_router", None)
        if nested is not None:
            paths |= _registered_paths(nested)
    return paths


def test_unified_filing_routes_are_registered() -> None:
    paths = _registered_paths(app)

    assert "/api/v1/filing/{client_id}/{ay}/{itr_type}/generate" in paths
    assert "/api/v1/filing/{client_id}/{ay}/{itr_type}/download" in paths
    assert "/api/v1/filing/{client_id}/{ay}/{itr_type}/submit" in paths
    assert "/api/v1/filing/jobs/{job_id}/otp" in paths
    assert "/api/v1/filing/jobs/{job_id}" in paths
    assert "/api/v1/filing/{client_id}/{ay}/status" in paths
    assert "/api/v1/filing/{client_id}/{ay}/{itr_type}/acknowledgement" in paths


def test_filing_uses_independent_job_model_and_queue() -> None:
    assert FilingJob.__tablename__ == "filing_job"
    assert "request_payload" not in AutomationJob.__table__.columns
    assert filing_worker._queue is not job_worker._job_queue


def test_existing_download_worker_has_no_filing_dispatch() -> None:
    source = inspect.getsource(job_worker._run_job)

    assert "PORTAL_UPLOAD_ITR" not in source
    assert "_run_portal_upload_job" not in source


def test_filing_worker_has_no_prefill_or_import_downloads() -> None:
    source = inspect.getsource(filing_worker._run_filing_job)

    assert "download_prefill" not in source
    assert "download_26as" not in source
    assert "run_request_ais" not in source


def _force_type3_uat_mode(monkeypatch) -> None:
    """Pin (ERI_MODE, ERI_ENV) to type3/uat for this test regardless of
    what an earlier-imported test module left in os.environ.

    test_eri_routers.py sets os.environ["ERI_MODE"] = "type2" at MODULE
    IMPORT time (not via monkeypatch), so it never reverts within a test
    session -- any test relying on submit_via_portal's own mode check
    (which runs before the ITR-2 guard) must pin the mode itself rather
    than assume ERI_MODE=type3, or its outcome depends on collection order.
    """
    monkeypatch.setenv("ERI_MODE", "type3")
    monkeypatch.setenv("ERI_ENV", "uat")


def test_submit_via_portal_rejects_itr2_even_though_normalize_form_allows_it(
    monkeypatch,
) -> None:
    """_normalize_form() allows ITR-2 (for /generate and /download, where a
    still-under-build-out form's JSON preparation is fine), but the
    frontend deliberately hides Direct Submit for ITR-2 because its
    compute/validation pipeline has not been through the same
    production-readiness audit as ITR-1/ITR-4. /submit triggers a REAL
    automated Playwright portal submission, so that restriction must be
    enforced server-side too, not left to the UI alone."""
    from app.routers.filing import SubmitFilingRequest, submit_via_portal

    _force_type3_uat_mode(monkeypatch)
    with pytest.raises(HTTPException) as caught:
        submit_via_portal(
            client_id="1",
            ay="2026-27",
            itr_type="ITR-2",
            request=SubmitFilingRequest(verification_mode="LATER"),
            current_user=None,  # never reached — rejected before use
            db=None,  # never reached — rejected before use
        )
    assert caught.value.status_code == 501
    assert "ITR-1 and ITR-4" in str(caught.value.detail)


def test_submit_via_portal_still_accepts_itr1_and_itr4_at_the_form_check(
    monkeypatch,
) -> None:
    """The new ITR-2 guard must not over-broaden and also reject ITR-1/ITR-4
    — confirmed by checking the guard passes and the function proceeds to
    the next step (resolve_owned_client), which fails on the fake client_id
    instead, proving the form check itself did not raise."""
    from app.routers.filing import SubmitFilingRequest, submit_via_portal

    _force_type3_uat_mode(monkeypatch)
    for form in ("itr1", "ITR-4"):
        with pytest.raises(Exception) as caught:
            submit_via_portal(
                client_id="not-a-real-id",
                ay="2026-27",
                itr_type=form,
                request=SubmitFilingRequest(verification_mode="LATER"),
                current_user=None,
                db=None,
            )
        # Must NOT be the 501 "ITR-1 and ITR-4 only" guard — any other
        # failure (e.g. AttributeError resolving current_user.id on None)
        # proves the form check was passed.
        if isinstance(caught.value, HTTPException):
            assert caught.value.status_code != 501 or "ITR-1 and ITR-4" not in str(
                caught.value.detail
            )
