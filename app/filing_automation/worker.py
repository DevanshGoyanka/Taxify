"""Independent serial worker for Type-3 portal filing jobs.

This module deliberately does not import or modify
``app.automation.job_worker``. The proven Prefill/AIS/TIS/26AS download
pipeline and the filing pipeline have separate queues and lifecycles.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.automation.auth import login_itd, logout_itd
from app.automation.browser import browser_manager
from app.automation.errors import _friendly_error
from app.automation.privacy import sanitize_automation_text
from app.automation.timing import AutomationTimeline
from app.db.database import SessionLocal
from app.db.models import Client, FilingJob, FilingRecord
from app.filing_automation.uploader import (
    PortalUploadState,
    PortalUploader,
    wait_for_job_otp,
)
from app.schemas.security.portal_crypto import decrypt_portal_password

logger = logging.getLogger("taxify.filing.worker")

_queue: asyncio.Queue[int] = asyncio.Queue()
_task: Optional[asyncio.Task] = None
_running = False
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_PROGRESS = {
    "filing_login": (10, "Signing into ITD portal"),
    "filing_upload": (40, "Uploading validated ITR JSON"),
    "filing_otp": (70, "Waiting for OTP or EVC"),
    "filing_complete": (100, "Return submitted"),
}


def enqueue_filing_job(job_id: int) -> None:
    """Queue a filing job without touching the import/download worker."""
    _queue.put_nowait(job_id)
    logger.info("Filing job %d queued.", job_id)


def get_filing_job_dict(job_id: int) -> Optional[dict]:
    """Return polling data for one independent filing job."""
    db: Session = SessionLocal()
    try:
        job = db.query(FilingJob).filter(FilingJob.id == job_id).first()
        if job is None:
            return None
        pct, label = _PROGRESS.get(
            job.current_step,
            (job.progress_pct or 0, job.status_message or ""),
        )
        return {
            "id": job.id,
            "client_id": job.client_id,
            "status": job.status,
            "assessment_year": job.assessment_year,
            "current_step": job.current_step,
            "status_message": job.status_message,
            "progress_pct": pct,
            "progress_label": label,
            "result": _safe_json(job.result),
            "error_message": job.error_message,
            "created_at": _iso(job.created_at),
            "started_at": _iso(job.started_at),
            "completed_at": _iso(job.completed_at),
        }
    finally:
        db.close()


def _update_job(job_id: int, **values) -> None:
    db: Session = SessionLocal()
    try:
        row = db.query(FilingJob).filter(FilingJob.id == job_id).first()
        if row is not None:
            for key, value in values.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            db.commit()
    finally:
        db.close()


def _update_filing(filing_id: int, **values) -> None:
    db: Session = SessionLocal()
    try:
        row = db.query(FilingRecord).filter(FilingRecord.id == filing_id).first()
        if row is not None:
            for key, value in values.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            db.commit()
    finally:
        db.close()


async def _run_filing_job(job_id: int) -> None:
    """Execute one Type-3 filing without entering the download worker."""
    db: Session = SessionLocal()
    try:
        job = db.query(FilingJob).filter(FilingJob.id == job_id).first()
        if job is None:
            return
        client = db.query(Client).filter(Client.id == job.client_id).first()
        filing_id = job.filing_record_id
        json_path = Path(job.json_path).resolve()
        itr_type = job.itr_type.upper()
        verification_mode = job.verification_mode.upper()
        assessment_year = job.assessment_year or ""
        attempt_count = job.attempt_count
        if client is None or not client.pan or not client.portal_password:
            raise RuntimeError("Client is missing PAN or ITD portal password.")
        portal_password = decrypt_portal_password(client.portal_password)
        allowed_root = (_PROJECT_ROOT / "downloads").resolve()
        if allowed_root not in json_path.parents or not json_path.is_file():
            raise RuntimeError("The filing JSON path is invalid.")
        pan = client.pan
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            error_message=str(exc),
            completed_at=datetime.datetime.utcnow(),
        )
        return
    finally:
        db.close()

    def log(message: str) -> None:
        safe = sanitize_automation_text(message)[:500]
        _update_job(job_id, status_message=safe)
        logger.info("Filing job %d: %s", job_id, safe)

    _update_job(
        job_id,
        status="running",
        started_at=datetime.datetime.utcnow(),
        attempt_count=attempt_count + 1,
        current_step="filing_login",
        status_message="Signing into ITD portal...",
        progress_pct=10,
    )
    _update_filing(filing_id, status="running", error_message=None)

    context = None
    page = None
    timeline = AutomationTimeline(log)
    try:
        # Direct-Submit (Type-3) runs a *visible* browser so the operator can
        # watch the portal upload and intervene if the portal throws an
        # unexpected prompt.  Headless mode is reserved for unattended batch
        # jobs, which is not this path.
        context = await browser_manager.get_context(
            log_callback=log,
            interactive=True,
            timeline=timeline,
        )
        page = await login_itd(
            user_id=pan,
            password=portal_password,
            log_callback=log,
            context=context,
            timeline=timeline,
        )
        _update_job(
            job_id,
            current_step="filing_upload",
            status_message="Uploading validated ITR JSON...",
            progress_pct=40,
        )

        async def otp_callback(prompt: str) -> str:
            _update_job(
                job_id,
                current_step="filing_otp",
                status_message=prompt,
                progress_pct=70,
            )
            return await wait_for_job_otp(job_id, prompt)

        outcome = await PortalUploader().upload(
            page,
            assessment_year=assessment_year,
            itr_type=itr_type,
            json_path=json_path,
            verification_mode=verification_mode,
            otp_callback=otp_callback if verification_mode != "LATER" else None,
            acknowledgement_dir=json_path.parent / "acknowledgement",
            log=log,
        )
        result = outcome.to_dict()
        result_json = json.dumps(result, ensure_ascii=False)
        if outcome.state is not PortalUploadState.SUBMITTED:
            _update_filing(
                filing_id,
                status="failed",
                portal_result=result_json,
                error_message=outcome.reason,
            )
            _update_job(
                job_id,
                status="failed",
                current_step=None,
                status_message=f"Filing failed: {outcome.reason}",
                error_message=outcome.reason,
                result=json.dumps({"filing": result}),
                completed_at=datetime.datetime.utcnow(),
                progress_pct=0,
            )
            return

        filing_status = "verified" if outcome.everify_status == "verified" else "submitted"
        _update_filing(
            filing_id,
            status=filing_status,
            acknowledgement_number=outcome.acknowledgement_number,
            everify_status=outcome.everify_status,
            acknowledgement_path=outcome.acknowledgement_path,
            portal_result=result_json,
            error_message=None,
        )
        _update_job(
            job_id,
            status="completed",
            current_step="filing_complete",
            status_message="Return submitted",
            result=json.dumps({"filing": result}),
            completed_at=datetime.datetime.utcnow(),
            progress_pct=100,
        )
    except Exception as exc:
        friendly = _friendly_error(str(exc)) or type(exc).__name__
        _update_filing(filing_id, status="failed", error_message=friendly)
        _update_job(
            job_id,
            status="failed",
            current_step=None,
            status_message=f"Filing failed: {friendly}",
            error_message=friendly,
            completed_at=datetime.datetime.utcnow(),
            progress_pct=0,
        )
    finally:
        if page is not None and not page.is_closed():
            try:
                await logout_itd(page, log, timeline=timeline)
            except Exception:
                pass
            try:
                await page.close()
            except Exception:
                pass
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass


async def _loop() -> None:
    global _running
    _running = True
    while _running:
        try:
            job_id = await _queue.get()
            await _run_filing_job(job_id)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Unexpected failure in filing worker loop.")


def start_filing_worker() -> None:
    """Start the filing worker independently from import automation."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())


async def stop_filing_worker() -> None:
    """Stop only the filing worker."""
    global _running, _task
    _running = False
    if _task is not None and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass


def _safe_json(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _iso(value: datetime.datetime | None) -> Optional[str]:
    return value.isoformat() if value is not None else None
