"""
Router for ITD portal automation jobs.

Endpoints:
  POST /clients/{client_id}/automation/import  — enqueue a download job
  GET  /automation/jobs/{job_id}               — poll job status
  GET  /automation/jobs                        — list jobs (filter by client_id)
"""

import datetime
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.automation.job_worker import _get_job_dict, enqueue_job, _download_dir
from app.automation.privacy import install_automation_privacy_filter
from app.automation.years import TaxYearContext
from app.db.database import get_db
from app.db.models import AutomationJob, Client, User
from app.routers.clients import resolve_owned_client

logger = logging.getLogger("taxify.automation.router")
install_automation_privacy_filter(logger)
router = APIRouter(tags=["automation"])


# ── Request / Response shapes ───────────────────────────────────────────────


@router.post("/clients/{client_id}/automation/import")
def start_automation_import(
    client_id: str,
    assessment_year: str = Query(
        default="2026-27",
        description="Assessment year, e.g. '2026-27'. Converted to financial year internally.",
    ),
    job_type: str = Query(
        default="DOWNLOAD_ALL",
        description="DOWNLOAD_ALL | DOWNLOAD_AIS_TIS | DOWNLOAD_26AS",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start an ITD portal automation job for a client.

    Creates an AutomationJob row (status="queued"), enqueues it into the
    background worker, and returns immediately with job_id.

    The job downloads Form 26AS, AIS, and TIS PDFs from the ITD portal
    using the client's stored PAN, DOB, and portal_password.
    """
    try:
        tax_years = TaxYearContext.from_assessment_year(assessment_year)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    assessment_year = tax_years.assessment_year
    fiscal_year = tax_years.fiscal_year

    # Resolve client by public_id (or legacy integer id) with ownership check
    client = resolve_owned_client(client_id, current_user.id, db)

    logger.info(
        "User %d requesting automation import for client %s, AY=%s, type=%s",
        current_user.id, client.public_id, assessment_year, job_type,
    )

    # Require portal password
    if not client.portal_password:
        logger.warning(
            "Automation import: Client %s (%s) has no portal_password set.",
            client.public_id, client.pan or "no PAN",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Client does not have a portal password. "
                "Update the client with portal_password first."
            ),
        )

    # Create job — store both explicit AY and derived FY.
    job = AutomationJob(
        client_id=client.id,
        user_id=current_user.id,
        job_type=job_type,
        status="queued",
        assessment_year=assessment_year,
        fiscal_year=fiscal_year,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = job.id

    # Enqueue for background processing
    enqueue_job(job_id)
    logger.info(
        "Automation import: Created job %d for client %s (%s), FY=%s, type=%s.",
        job_id, client.public_id, client.pan, fiscal_year, job_type,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "assessment_year": assessment_year,
        "fiscal_year": fiscal_year,
        "download_dir": _download_dir(client.id, fiscal_year),
        "message": "Automation job created and queued. Poll GET /automation/jobs/{job_id} for progress.",
    }


# ── Polling endpoint ────────────────────────────────────────────────────────


@router.get("/automation/jobs/{job_id}")
def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Poll the status of an automation job.

    Returns current status, progress, and — on completion — file paths.
    """
    job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    # Only the job owner or the user who created it can view it
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    return _get_job_dict(job_id)


# ── List endpoint ───────────────────────────────────────────────────────────


@router.get("/automation/jobs")
def list_jobs(
    client_id: Optional[str] = Query(default=None, description="Filter by client public_id or legacy id"),
    status_filter: Optional[str] = Query(
        default=None, alias="status", description="Filter by status"
    ),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List automation jobs for the current user, optionally filtered.
    """
    query = db.query(AutomationJob).filter(
        AutomationJob.user_id == current_user.id
    )
    if client_id is not None:
        # Resolve the client by public_id or legacy integer id, then
        # filter jobs by the internal integer client.id.
        resolved = resolve_owned_client(client_id, current_user.id, db)
        query = query.filter(AutomationJob.client_id == resolved.id)
    if status_filter:
        query = query.filter(AutomationJob.status == status_filter)

    query = query.order_by(AutomationJob.created_at.desc()).limit(limit)
    jobs = query.all()

    return {
        "jobs": [
            {
                "id": j.id,
                "client_id": j.client_id,
                "job_type": j.job_type,
                "status": j.status,
                "assessment_year": j.assessment_year,
                "fiscal_year": j.fiscal_year,
                "current_step": j.current_step,
                "status_message": j.status_message,
                "progress_pct": j.progress_pct,
                "artifact_outcomes": json.loads(j.artifact_outcomes or "{}"),
                "error_message": j.error_message,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]
    }
