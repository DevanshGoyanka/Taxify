"""Unified filing API for Type-3 now and Type-2 transport later."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.automation.years import TaxYearContext
from app.db.database import get_db
from app.db.models import FilingJob, FilingRecord, User
from app.engine.filing_orchestrator import FilingOrchestratorError, produce_itd_json
from app.eri.config import get_eri_credentials
from app.eri.type3.json_exporter import (
    Type3JsonExportError,
    export_itd_json_file,
    load_saved_filing_draft,
)
from app.filing_automation.uploader import job_is_awaiting_otp, provide_job_otp
from app.filing_automation.worker import enqueue_filing_job, get_filing_job_dict
from app.routers.clients import resolve_owned_client
from app.services.filing_record_service import upsert_filing_record

router = APIRouter(prefix="/api/v1/filing", tags=["filing"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class SubmitFilingRequest(BaseModel):
    """Options for Type-3 portal submission."""

    verification_mode: Literal["LATER", "AADHAAR_OTP", "BANK_EVC"] = "LATER"


class FilingOtpRequest(BaseModel):
    """Ephemeral OTP/EVC input, never persisted."""

    otp: str


def _normalize_form(itr_type: str) -> str:
    value = itr_type.strip().upper().replace("_", "-")
    if value in {"ITR1", "ITR2", "ITR3", "ITR4"}:
        value = f"ITR-{value[-1]}"
    if value not in {"ITR-1", "ITR-4"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This season's Type-3 filing supports ITR-1 and ITR-4 only.",
        )
    return value


def _filing_dir(client_id: int, ay: str) -> Path:
    year = TaxYearContext.from_assessment_year(ay)
    return _PROJECT_ROOT / "downloads" / str(client_id) / year.fiscal_year / "filing"


def _draft(db: Session, client_id: int, ay: str, form: str) -> dict:
    try:
        return load_saved_filing_draft(
            db=db,
            client_id=client_id,
            ay=ay,
            itr_type=form,
        )
    except Type3JsonExportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{client_id}/{ay}/{itr_type}/generate")
def generate_itd_json(
    client_id: str,
    ay: str,
    itr_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate, validate, digest, and persist the current saved draft."""
    client = resolve_owned_client(client_id, current_user.id, db)
    form = _normalize_form(itr_type)
    payload = _draft(db, client.id, ay, form)
    try:
        official = produce_itd_json(
            client_id=client.id,
            ay=ay,
            itr_type=form,
            flat_draft=payload,
            user=current_user,
            db=db,
        )
    except FilingOrchestratorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    body = official["ITR"][form.replace("-", "")]
    return {
        "json": official,
        "digest": body["CreationInfo"]["Digest"],
        "itr_type": form,
        "assessment_year": ay,
    }


@router.get("/{client_id}/{ay}/{itr_type}/download")
def download_itd_json(
    client_id: str,
    ay: str,
    itr_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a deterministic CBDT JSON for manual portal upload."""
    client = resolve_owned_client(client_id, current_user.id, db)
    form = _normalize_form(itr_type)
    try:
        path = export_itd_json_file(
            client_id=client.id,
            ay=ay,
            itr_type=form,
            flat_draft=None,
            user=current_user,
            db=db,
            output_dir=_filing_dir(client.id, ay),
        )
    except (Type3JsonExportError, FilingOrchestratorError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FileResponse(path, filename=path.name, media_type="application/json")


@router.post("/{client_id}/{ay}/{itr_type}/submit")
def submit_via_portal(
    client_id: str,
    ay: str,
    itr_type: str,
    request: SubmitFilingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Queue an explicitly authorized Type-3 portal filing job."""
    creds = get_eri_credentials()
    if creds.mode != "type3":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Type-2 submission is deferred until the next implementation phase.",
        )
    client = resolve_owned_client(client_id, current_user.id, db)
    if not client.portal_password:
        raise HTTPException(
            status_code=400,
            detail="Client does not have an ITD portal password.",
        )
    form = _normalize_form(itr_type)
    try:
        path = export_itd_json_file(
            client_id=client.id,
            ay=ay,
            itr_type=form,
            flat_draft=None,
            user=current_user,
            db=db,
            output_dir=_filing_dir(client.id, ay),
        )
    except (Type3JsonExportError, FilingOrchestratorError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filing = upsert_filing_record(
        db=db,
        client_id=client.id,
        user_id=current_user.id,
        assessment_year=ay,
        itr_type=form,
        eri_mode=creds.mode,
        eri_environment=creds.environment,
        status="queued",
        json_path=str(path),
        error_message=None,
    )
    years = TaxYearContext.from_assessment_year(ay)
    job = FilingJob(
        filing_record_id=filing.id,
        client_id=client.id,
        user_id=current_user.id,
        status="queued",
        assessment_year=years.assessment_year,
        itr_type=form,
        verification_mode=request.verification_mode,
        json_path=str(path),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_filing_job(job.id)
    return {
        "job_id": job.id,
        "filing_id": filing.id,
        "status": "queued",
        "verification_mode": request.verification_mode,
    }


@router.post("/jobs/{job_id}/otp")
def supply_filing_otp(
    job_id: int,
    request: FilingOtpRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deliver an OTP/EVC only to the active in-memory filing job."""
    job = db.query(FilingJob).filter(FilingJob.id == job_id).first()
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Filing job not found.")
    if not job_is_awaiting_otp(job_id):
        raise HTTPException(status_code=409, detail="This filing job is not awaiting an OTP/EVC.")
    if not provide_job_otp(job_id, request.otp.strip()):
        raise HTTPException(status_code=409, detail="OTP/EVC input window has closed.")
    return {"accepted": True}


@router.get("/jobs/{job_id}")
def get_filing_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Poll a filing job without entering the import-automation router."""
    job = db.query(FilingJob).filter(FilingJob.id == job_id).first()
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Filing job not found.")
    return get_filing_job_dict(job_id)


@router.get("/{client_id}/{ay}/status")
def filing_status(
    client_id: str,
    ay: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return durable filing state for the owned client and assessment year."""
    client = resolve_owned_client(client_id, current_user.id, db)
    rows = (
        db.query(FilingRecord)
        .filter(
            FilingRecord.client_id == client.id,
            FilingRecord.assessment_year == ay,
        )
        .order_by(FilingRecord.updated_at.desc())
        .all()
    )
    return {
        "filings": [
            {
                "id": row.id,
                "itr_type": row.itr_type,
                "mode": row.eri_mode,
                "environment": row.eri_environment,
                "status": row.status,
                "acknowledgement_number": row.acknowledgement_number,
                "everify_status": row.everify_status,
                "has_acknowledgement": bool(row.acknowledgement_path),
                "error_message": row.error_message,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]
    }


@router.get("/{client_id}/{ay}/{itr_type}/acknowledgement")
def get_acknowledgement(
    client_id: str,
    ay: str,
    itr_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a previously captured acknowledgement PDF."""
    client = resolve_owned_client(client_id, current_user.id, db)
    form = _normalize_form(itr_type)
    record = (
        db.query(FilingRecord)
        .filter(
            FilingRecord.client_id == client.id,
            FilingRecord.assessment_year == ay,
            FilingRecord.itr_type == form,
        )
        .first()
    )
    if record is None or not record.acknowledgement_path:
        raise HTTPException(status_code=404, detail="Acknowledgement is not available.")
    path = Path(record.acknowledgement_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Acknowledgement file is missing.")
    return FileResponse(
        path,
        filename=f"{form}_{ay}_Acknowledgement.pdf",
        media_type="application/pdf",
    )
