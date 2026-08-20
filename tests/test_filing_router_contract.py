"""Static route and worker contract tests for Type-3 filing."""

from __future__ import annotations

import inspect

from app.automation import job_worker
from app.db.models import AutomationJob, FilingJob
from app.filing_automation import worker as filing_worker
from app.main import app


def test_unified_filing_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}

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
