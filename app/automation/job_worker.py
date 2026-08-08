"""
Job worker for ITD portal automation.

Manages a serial asyncio queue of automation jobs. One browser context
at a time -- downloads 26AS, AIS, and TIS from ITD portal, unlocks PDFs,
parses them via ais_extractor, and stores results on the AutomationJob DB record.

Architecture:
  - A single asyncio.Queue holds job IDs.
  - A background asyncio task (start at app startup) processes jobs
    FIFO with no concurrency.
  - The endpoint POST /clients/{id}/automation/import enqueues a job
    and returns immediately.
  - GET /automation/jobs/{job_id} polls for status.
"""

import asyncio
import datetime
import json
import logging
import os
import traceback
from typing import Optional

from sqlalchemy.orm import Session

from app.automation.auth import login_itd, logout_itd
from app.automation.browser import browser_manager
from app.automation.downloader_26as import download_26as
from app.automation.downloader_ais_tis import run_request_ais, run_download_ais_tis
from app.automation.downloader_prefill import PrefillState, download_prefill
from app.automation.errors import _friendly_error
from app.automation.filed_returns_inventory import (
    InventoryState,
    capture_filed_return_inventory,
)
from app.automation.filing_mode_classifier import classify_filing_mode
from app.automation.navigation import resolve_itd_anchor
from app.automation.pdf_unlocker import unlock_pdf, verify_pdf_decryptable
from app.automation.privacy import (
    install_automation_privacy_filter,
    sanitize_automation_text,
)
from app.automation.timing import AutomationTimeline
from app.automation.years import TaxYearContext
from app.db.database import SessionLocal
from app.db.models import AutomationJob
from app.schemas.security.portal_crypto import decrypt_portal_password

# PDF extractors (ais_extractor integration)
from ais_extractor.as26_extractor import extract_26as as _extract_26as
from ais_extractor.extractor import extract_ais as _extract_ais, ais_to_frontend_json as _ais_to_frontend
from ais_extractor.tis_extractor import extract_tis as _extract_tis, tis_to_frontend_json as _tis_to_frontend
from ais_extractor.reconciliation import reconcile as _reconcile_data

logger = logging.getLogger("taxify.automation.worker")
install_automation_privacy_filter(logger)

# ---------------------------------------------------------------------------
# Queue + worker state
# ---------------------------------------------------------------------------

_job_queue: asyncio.Queue[int] = asyncio.Queue()
_worker_task: Optional[asyncio.Task] = None
_worker_running: bool = False

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Each automation step is mapped to a user-friendly progress indicator.
# The frontend StatusBox uses current_step and progress_pct for display.
_STEP_PROGRESS: dict[str, dict] = {
    "login":             {"pct": 5,  "label": "Signing into ITD portal",       "icon": "\U0001f510"},
    "download_26as":     {"pct": 10, "label": "Downloading Form 26AS",         "icon": "\U0001f4c4"},
    "request_ais":       {"pct": 30, "label": "Requesting AIS generation",     "icon": "\U0001f4cb"},
    "download_tis":      {"pct": 55, "label": "Downloading TIS statement",      "icon": "\U0001f4e5"},
    "poll_ais":          {"pct": 65, "label": "Waiting for AIS to generate",     "icon": "\u23f3"},
    "download_prefill":  {"pct": 80, "label": "Downloading ITD Prefill JSON",   "icon": "\U0001f4e5"},
    "filed_return_inventory": {"pct": 83, "label": "Reading filed-return inventory", "icon": "\U0001f4cb"},
    "unlock":         {"pct": 85, "label": "Decrypting PDFs",               "icon": "\U0001f513"},
    "extract":        {"pct": 88, "label": "Extracting PDF data",           "icon": "\U0001f4ca"},
    "logout":         {"pct": 95, "label": "Signing out",                   "icon": "\U0001f6aa"},
    "complete":       {"pct": 100,"label": "All downloads complete",        "icon": "\u2705"},
}

# Mapping from status_message raw server tags to clean user-facing text
_STATUS_CLEAN_MAP: dict[str, str] = {
    "Starting browser":         "Launching secure browser\u2026",
    "Launching browser":        "Launching secure browser\u2026",
    "Logging into ITD portal":  "Signing into ITD portal\u2026",
    "Login successful":         "Signed in successfully",
    "Downloading Prefill":      "Downloading current-year Prefill JSON\u2026",
    "Prefill downloaded":       "Current-year Prefill JSON ready",
    "Reading filed returns":    "Reading filed-return inventory\u2026",
    "Filed returns captured":   "Filed-return inventory ready",
    "Downloading Form 26AS":    "Fetching Form 26AS\u2026",
    "26AS downloaded":          "Form 26AS ready",
    "Requesting AIS":           "Requesting AIS generation\u2026",
    "AIS queued":               "AIS generation queued \u2014 polling\u2026",
    "Downloading TIS":          "Downloading TIS statement\u2026",
    "All downloads complete":   "All downloads complete",
    "Logging out":              "Signing out of ITD portal\u2026",
}


def _friendly_status(raw: str | None) -> str:
    """Translate raw server-side log into a clean user-facing message."""
    if not raw:
        return ""
    for tag, friendly in _STATUS_CLEAN_MAP.items():
        if tag.lower() in raw.lower():
            return friendly
    return raw[:200]


def _progress_for_step(step: str | None) -> dict:
    """Return {pct, label, icon} for the given step."""
    if step is None:
        return {"pct": 0, "label": "", "icon": ""}
    return _STEP_PROGRESS.get(step, {"pct": 0, "label": "", "icon": ""})


def _derive_fiscal_year(assessment_year: str) -> str:
    """Convert a validated assessment year to its financial year."""
    return TaxYearContext.from_assessment_year(assessment_year).fiscal_year


def _download_dir(client_id: int, fiscal_year: str) -> str:
    """Absolute path to the download directory for this job."""
    dirname = os.path.join(
        _PROJECT_ROOT, "downloads", str(client_id), fiscal_year
    )
    os.makedirs(dirname, exist_ok=True)
    return dirname


# ---------------------------------------------------------------------------
# DB helpers (operate outside of request-scoped sessions)
# ---------------------------------------------------------------------------


def _update_job(job_id: int, **kwargs) -> None:
    """Update an AutomationJob row in a new short-lived session."""
    db: Session = SessionLocal()
    try:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if job is None:
            logger.warning("_update_job: Job %d not found in DB.", job_id)
            return
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)
        db.commit()
    except Exception:
        logger.exception("_update_job: DB update failed for job %d.", job_id)
        db.rollback()
    finally:
        db.close()


def _get_job_dict(job_id: int) -> Optional[dict]:
    """Read the full AutomationJob row as a dict (for the polling endpoint)."""
    db: Session = SessionLocal()
    try:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if job is None:
            return None
        progress_info = _progress_for_step(job.current_step)
        return {
            "id": job.id,
            "client_id": job.client_id,
            "user_id": job.user_id,
            "job_type": job.job_type,
            "status": job.status,
            "assessment_year": job.assessment_year,
            "fiscal_year": job.fiscal_year,
            "steps_completed": _safe_json(job.steps_completed, []),
            "current_step": job.current_step,
            # User-facing fields (frontend uses these, not raw server logs)
            "status_message": _friendly_status(job.status_message),
            "progress_pct": progress_info["pct"],
            "progress_label": progress_info["label"],
            "progress_icon": progress_info["icon"],
            # Raw server fields (available for debugging)
            "raw_status_message": job.status_message,
            "files_downloaded": _safe_json(job.files_downloaded, {}),
            "artifact_outcomes": _safe_json(job.artifact_outcomes, {}),
            "parsed_results": _safe_json(job.parsed_results, {}),
            "ais_ref_id": job.ais_ref_id,
            "error_message": job.error_message,
            "created_at": _iso(job.created_at),
            "started_at": _iso(job.started_at),
            "completed_at": _iso(job.completed_at),
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
        }
    finally:
        db.close()


def _safe_json(raw: str, default):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _iso(dt) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------


async def _run_job(job_id: int) -> None:
    """Execute a single automation job end-to-end."""

    logger.info("Job %d: Starting execution.", job_id)

    # Load job & client info
    db: Session = SessionLocal()
    try:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if job is None:
            logger.error("Job %d: Not found in database -- aborting.", job_id)
            return
        client_id = job.client_id
        job_type = job.job_type
        fiscal_year = job.fiscal_year
        assessment_year = job.assessment_year
        if not assessment_year:
            assessment_year = TaxYearContext.from_financial_year(
                fiscal_year
            ).assessment_year

        from app.db.models import Client

        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.error(
                "Job %d: Client %d not found -- marking job as failed.",
                job_id, client_id,
            )
            _update_job(
                job_id,
                status="failed",
                error_message="Client not found.",
                completed_at=datetime.datetime.utcnow(),
            )
            return

        pan = client.pan or ""
        dob = client.dob or ""
        encrypted_pw = client.portal_password or ""

        # ── DOB format diagnostic ──────────────────────────────────────────
        # Log DOB format info so we can see whether YYYY-MM-DD or DD-MM-YYYY
        # is entering the pipeline (critical for correct PDF password generation).
        dob_stripped = dob.strip() if dob else ""
        dob_parts = dob_stripped.split("-") if dob_stripped else []
        dob_seg_lengths = [str(len(p)) for p in dob_parts] if dob_parts else []
        logger.info(
            "Job %d: Client %d DOB format info — "
            "value_available=%s, hyphen_count=%d, seg_lengths=%s, "
            "pan_available=%s",
            job_id, client_id,
            bool(dob_stripped),
            dob_stripped.count("-"),
            "-".join(dob_seg_lengths) if dob_seg_lengths else "empty",
            bool(pan),
        )
        try:
            portal_pw = decrypt_portal_password(encrypted_pw) if encrypted_pw else ""
        except Exception:
            logger.warning(
                "Job %d: Failed to decrypt portal password for client %d.",
                job_id, client_id,
            )
            portal_pw = ""

        if not pan or not portal_pw:
            logger.error(
                "Job %d: Client %d missing PAN (have=%s) or portal password (have=%s).",
                job_id, client_id, bool(pan), bool(portal_pw),
            )
            _update_job(
                job_id,
                status="failed",
                error_message=(
                    "Client is missing PAN or ITD portal password. "
                    "Add portal_password on the Client before running automation."
                ),
                completed_at=datetime.datetime.utcnow(),
            )
            return

        dldir = _download_dir(client_id, fiscal_year)
        logger.info(
            "Job %d: Client %d (%s), FY=%s, download dir=%s",
            job_id, client_id, pan, fiscal_year, dldir,
        )
    finally:
        db.close()

    # Setup
    log_lines: list[str] = []

    def log(msg: str) -> None:
        safe_msg = sanitize_automation_text(msg)
        log_lines.append(safe_msg)
        short = safe_msg[:500] if len(safe_msg) > 500 else safe_msg
        _update_job(job_id, status_message=short)
        # Timing events are intentionally visible at INFO for live Phase 0
        # verification; ordinary detailed portal logs remain DEBUG-level.
        if safe_msg.startswith(("[Timing]", "[NAV]", "[PREFILL]", "[26AS]", "[FILED RETURNS]", "[CLASSIFICATION]")):
            logger.info("Job %d: %s", job_id, safe_msg)
        else:
            logger.debug("Job %d: %s", job_id, safe_msg)

    _update_job(
        job_id,
        status="running",
        started_at=datetime.datetime.utcnow(),
        attempt_count=job.attempt_count + 1,
        steps_completed="[]",
        current_step="login",
        status_message="Starting browser...",
        progress_pct=5,
    )
    logger.info("Job %d: Marked as running, attempt %d.", job_id, job.attempt_count + 1)

    timeline = AutomationTimeline(log)
    page = None
    context = None
    files: dict[str, Optional[str]] = {
        "prefill": None,
        "26as": None,
        "ais": None,
        "tis": None,
    }
    artifact_outcomes: dict[str, dict] = {}
    required_artifact_failures: list[str] = []
    steps: list[str] = []

    try:
        # Step 1: Browser + Login
        _update_job(job_id, current_step="login", status_message="Launching browser...", progress_pct=5)
        log("[Worker] Getting browser context...")
        context = await browser_manager.get_context(
            log_callback=log,
            interactive=False,
            timeline=timeline,
        )
        log("[Worker] Browser context ready. Logging into ITD portal...")

        _update_job(job_id, status_message="Logging into ITD portal...", progress_pct=7)
        page = await login_itd(
            user_id=pan,
            password=portal_pw,
            log_callback=log,
            context=context,
            timeline=timeline,
        )
        steps.append("login")
        _update_job(job_id, steps_completed=json.dumps(steps), progress_pct=9)
        log("[Worker] Login successful.")

        # Step 2: Download 26AS
        _update_job(
            job_id,
            current_step="download_26as",
            status_message="Downloading Form 26AS...",
            progress_pct=20,
        )
        timeline.mark("26AS navigation started")
        log("[Worker] Starting 26AS download...")
        ok, reason, txt_path = await download_26as(
            page=page,
            assessment_year=assessment_year,
            download_dir=dldir,
            log_callback=log,
            pan=pan,
            dob=dob,
        )
        timeline.mark("26AS download completed")
        page = await resolve_itd_anchor(page)

        if ok:
            pan_prefix = f"{pan}-" if pan else ""
            fy_str = fiscal_year.replace("-", "_")
            pdf26 = os.path.join(dldir, f"{pan_prefix}26AS-{fy_str}.pdf")
            if os.path.exists(pdf26):
                unlock_result = unlock_pdf(pdf26, pan=pan, dob=dob, log=log)
                files["26as"] = pdf26
                if unlock_result.get("unlocked"):
                    log(f"[Worker] 26AS PDF unlocked: {pdf26}")
                elif unlock_result.get("reason") == "not-encrypted":
                    log(f"[Worker] 26AS PDF is already readable; unlock not required: {pdf26}")
                else:
                    log(
                        f"[Worker] 26AS PDF saved but unlock failed: "
                        f"{unlock_result.get('reason', 'unknown')}"
                    )
            else:
                ok = False
                reason = "26AS portal flow returned without saving the expected PDF"

        if ok and files["26as"]:
            steps.append("26as_downloaded")
            _update_job(job_id, steps_completed=json.dumps(steps), progress_pct=27)
            _update_job(
                job_id,
                files_downloaded=json.dumps(files),
                status_message="26AS downloaded",
                progress_pct=28,
            )
        else:
            failure_reason = reason or "26AS download failed"
            log(f"[Worker] 26AS download failed: {failure_reason}")
            if job_type in {"DOWNLOAD_ALL", "DOWNLOAD_26AS"}:
                required_artifact_failures.append(f"26AS: {failure_reason}")

        # Step 3: Request AIS + Download TIS (Phase 1)
        _update_job(
            job_id,
            current_step="request_ais",
            status_message="Requesting AIS + downloading TIS...",
            progress_pct=30,
        )
        timeline.mark("AIS portal navigation started")
        log("[Worker] Starting AIS request + TIS download...")

        ais_outcome = await run_request_ais(
            itd_page=page,
            fiscal_year=fiscal_year,
            download_dir=dldir,
            log=log,
            pan=pan,
            dob=dob,
        )
        timeline.mark("AIS and TIS request phase completed")
        page = await resolve_itd_anchor(page)

        pan_prefix = f"{pan}-" if pan else ""
        fy_str = fiscal_year.replace("-", "_")
        tis_path = os.path.join(dldir, f"{pan_prefix}TIS-{fy_str}.pdf")
        if os.path.exists(tis_path):
            files["tis"] = tis_path

        ais_status = ais_outcome.get("status", "failed")

        if ais_status == "downloaded":
            ais_path = os.path.join(dldir, f"{pan_prefix}AIS-{fy_str}.pdf")
            if os.path.exists(ais_path):
                files["ais"] = ais_path
            steps.append("ais_downloaded")
            steps.append("tis_downloaded")
        elif ais_status == "requested":
            ref_id = ais_outcome.get("ref_id", "")
            log(f"[Worker] AIS queued (ref: {ref_id}). Starting Phase 2 polling...")

            _update_job(
                job_id,
                current_step="poll_ais",
                status_message=f"AIS queued. Polling for generation (ref: {ref_id})...",
                ais_ref_id=ref_id,
                progress_pct=65,
            )

            dl_result = await run_download_ais_tis(
                itd_page=page,
                fiscal_year=fiscal_year,
                download_dir=dldir,
                log=log,
                pan=pan,
                dob=dob,
                dl_ais=True,
                dl_tis=False,
                ais_ref_id=ref_id,
            )
            page = await resolve_itd_anchor(page)

            ais_outcome2 = dl_result.get("ais", {})
            ais_status2 = ais_outcome2.get("status", "failed")
            if ais_status2 == "downloaded":
                ais_path = os.path.join(dldir, f"{pan_prefix}AIS-{fy_str}.pdf")
                if os.path.exists(ais_path):
                    files["ais"] = ais_path
                steps.append("ais_downloaded")
            else:
                log(f"[Worker] AIS Phase 2 result: {ais_status2}")

            if os.path.exists(tis_path):
                files["tis"] = tis_path
            steps.append("tis_downloaded")
        else:
            if ais_status == "skipped":
                steps.append("ais_downloaded")
            if os.path.exists(tis_path):
                files["tis"] = tis_path
            steps.append("tis_downloaded")

        # Step 4: Download current-year Prefill JSON without importing it.
        # Keep this optional, route-mutating operation after the proven
        # dashboard -> 26AS -> AIS/TIS sequence so a Prefill failure cannot
        # contaminate required artifact downloads.
        _update_job(
            job_id,
            current_step="download_prefill",
            status_message="Downloading Prefill JSON...",
            progress_pct=80,
        )
        timeline.mark("Prefill navigation started")
        log("[Worker] Starting current-year Prefill JSON download...")
        prefill_outcome = await download_prefill(
            page=page,
            pan=pan,
            download_dir=dldir,
            assessment_year=assessment_year,
            log=log,
        )
        timeline.mark("Prefill download completed")
        page = await resolve_itd_anchor(page)
        artifact_outcomes["prefill"] = prefill_outcome.to_dict()
        if prefill_outcome.state is PrefillState.DOWNLOADED and prefill_outcome.path:
            files["prefill"] = prefill_outcome.path
            steps.append("prefill_downloaded")
            prefill_status = "Prefill downloaded"
            log("[Worker] Current-year Prefill JSON downloaded and validated.")
        else:
            prefill_status = f"Prefill: {prefill_outcome.state.value}"
            log(
                "[Worker] Current-year Prefill outcome: "
                f"{prefill_outcome.state.value} — {prefill_outcome.reason}"
            )
        _update_job(
            job_id,
            steps_completed=json.dumps(steps),
            files_downloaded=json.dumps(files),
            artifact_outcomes=json.dumps(artifact_outcomes),
            status_message=prefill_status,
            progress_pct=82,
        )

        # Step 4.1: Capture filed-return inventory metadata only. This optional,
        # nonfatal observation performs no row selection and no download/import.
        _update_job(
            job_id,
            current_step="filed_return_inventory",
            status_message="Reading filed returns...",
            progress_pct=83,
        )
        log("[Worker] Starting filed-return inventory capture...")
        inventory_outcome = await capture_filed_return_inventory(
            page=page,
            log=log,
        )
        page = await resolve_itd_anchor(page)
        artifact_outcomes["filed_return_inventory"] = inventory_outcome.to_dict()
        classification = classify_filing_mode(inventory_outcome, assessment_year)
        artifact_outcomes["filing_mode_classification"] = classification.to_dict()
        if inventory_outcome.state in {InventoryState.CAPTURED, InventoryState.NO_RETURNS}:
            steps.append("filed_return_inventory_captured")
            steps.append("filing_mode_classified")
        log(
            "[Worker] Filed-return inventory outcome: "
            f"{inventory_outcome.state.value}; records={len(inventory_outcome.records)}"
        )
        log(
            "[CLASSIFICATION] Filing-mode classification completed; "
            f"state={classification.state.value}; "
            f"context={classification.filing_context.value}; "
            f"current_returns={classification.current_return_count}; "
            f"review_required={classification.review_required}."
        )
        _update_job(
            job_id,
            steps_completed=json.dumps(steps),
            artifact_outcomes=json.dumps(artifact_outcomes),
            status_message="Filed returns captured",
            progress_pct=84,
        )

        # Step 5: Unlock remaining PDFs
        _update_job(job_id, current_step="unlock", status_message="Decrypting PDFs...", progress_pct=85)
        for label, path in [("AIS", files["ais"]), ("TIS", files["tis"])]:
            if path and os.path.exists(path):
                logger.info(
                    "Job %d: About to unlock %s PDF — path=%s, size=%d, pan_available=%s, dob_available=%s",
                    job_id, label, path, os.path.getsize(path), bool(pan), bool(dob),
                )
                unlock_result = unlock_pdf(path, pan=pan, dob=dob, log=log)
                unlock_reason = unlock_result.get("reason")
                if unlock_result.get("unlocked"):
                    log(f"[Worker] {label} PDF unlocked: {path}")
                elif unlock_reason == "not-encrypted":
                    log(f"[Worker] {label} PDF is already readable; unlock not required: {path}")
                    logger.info(
                        "Job %d: %s PDF already readable — unlock not required.",
                        job_id,
                        label,
                    )
                else:
                    log(
                        f"[Worker] {label} PDF unlock FAILED: "
                        f"reason={unlock_reason or 'unknown'}, "
                        f"last_error={unlock_result.get('last_error', 'N/A')}"
                    )
                    logger.error(
                        "Job %d: %s PDF unlock FAILED — "
                        "reason=%s, last_error=%s, candidates_tried=%d, "
                        "candidates_masked=%s",
                        job_id, label,
                        unlock_result.get("reason", "unknown"),
                        unlock_result.get("last_error", "N/A"),
                        unlock_result.get("candidates_tried", 0),
                        unlock_result.get("candidates_masked", []),
                    )

        # Step 4.5: Extract parsed data from downloaded PDFs
        _update_job(job_id, current_step="extract", status_message="Extracting data from PDFs...", progress_pct=88)
        log("[Worker] Starting PDF extraction via ais_extractor...")

        parsed: dict[str, dict] = {}
        extract_errors: list[str] = []

        # --- 26AS ---
        path_26as = files.get("26as")
        if path_26as and os.path.exists(path_26as):
            # Pre-extraction integrity check — is this PDF actually readable?
            verify_26as = verify_pdf_decryptable(path_26as, log=log)
            if not verify_26as.get("ok"):
                err = (
                    f"26AS extraction blocked: PDF not decryptable — "
                    f"{verify_26as.get('reason', 'unknown')}"
                )
                extract_errors.append(err)
                log(f"[Worker] {err}")
                logger.error("Job %d: 26AS verify failed: %s", job_id, verify_26as)
            else:
                try:
                    result_26as = _extract_26as(path_26as)
                    # Keep _details in rows — reconciliation depends on them
                    parsed["26as"] = result_26as
                    total_rows = sum(
                        len(pdata.get("rows", []))
                        for pdata in result_26as.get("parts", {}).values()
                    )
                    log(
                        f"[Worker] 26AS extracted: {total_rows} total rows "
                        f"across {len(result_26as.get('parts', {}))} parts"
                    )
                    logger.info(
                        "Job %d: 26AS extraction OK — %d rows across parts",
                        job_id, total_rows,
                    )
                except Exception as e:
                    err = f"26AS extraction failed: {e}"
                    extract_errors.append(err)
                    log(f"[Worker] {err}")
                    logger.exception("Job %d: 26AS extraction error", job_id)
        else:
            extract_errors.append("26AS file not downloaded -- skipped extraction")
            logger.warning("Job %d: 26AS file not found at %s", job_id, path_26as)

        # --- AIS ---
        path_ais = files.get("ais")
        if path_ais and os.path.exists(path_ais):
            verify_ais = verify_pdf_decryptable(path_ais, log=log)
            if not verify_ais.get("ok"):
                err = (
                    f"AIS extraction blocked: PDF not decryptable — "
                    f"{verify_ais.get('reason', 'unknown')}"
                )
                extract_errors.append(err)
                log(f"[Worker] {err}")
                logger.error("Job %d: AIS verify failed: %s", job_id, verify_ais)
            else:
                try:
                    doc_ais = _extract_ais(path_ais)
                    ais_json_str = _ais_to_frontend(doc_ais)
                    parsed["ais"] = json.loads(ais_json_str)
                    log(
                        f"[Worker] AIS extracted: B1={len(doc_ais.b1_entries)}, "
                        f"B2={len(doc_ais.b2_entries)}, B7={len(doc_ais.b7_entries)}, "
                        f"tax_payments={len(doc_ais.tax_payments)}, "
                        f"refunds={len(doc_ais.refunds)}"
                    )
                    logger.info(
                        "Job %d: AIS extraction OK — B1=%d, B2=%d, B7=%d entries",
                        job_id, len(doc_ais.b1_entries), len(doc_ais.b2_entries),
                        len(doc_ais.b7_entries),
                    )
                except Exception as e:
                    # ── Detailed extraction failure diagnostics ──────────────
                    import traceback as _tb
                    exc_tb = _tb.format_exc()
                    # Log full traceback + file info
                    logger.error(
                        "Job %d: AIS extraction FAILED — file=%s, file_size=%d, "
                        "error_type=%s, error=%s\nTRACEBACK:\n%s",
                        job_id,
                        path_ais,
                        os.path.getsize(path_ais) if os.path.exists(path_ais) else -1,
                        type(e).__name__,
                        str(e),
                        exc_tb,
                    )
                    err = f"AIS extraction failed: {type(e).__name__}: {e}"
                    extract_errors.append(err)
                    log(f"[Worker] {err}")
                    log(f"[Worker] AIS extraction traceback:\n{exc_tb}")
        else:
            extract_errors.append("AIS file not downloaded -- skipped extraction")
            logger.warning("Job %d: AIS file not found at %s", job_id, path_ais)

        # --- TIS ---
        path_tis = files.get("tis")
        if path_tis and os.path.exists(path_tis):
            verify_tis = verify_pdf_decryptable(path_tis, log=log)
            if not verify_tis.get("ok"):
                err = (
                    f"TIS extraction blocked: PDF not decryptable — "
                    f"{verify_tis.get('reason', 'unknown')}"
                )
                extract_errors.append(err)
                log(f"[Worker] {err}")
                logger.error("Job %d: TIS verify failed: %s", job_id, verify_tis)
            else:
                try:
                    doc_tis = _extract_tis(path_tis)
                    tis_json_str = _tis_to_frontend(doc_tis)
                    parsed["tis"] = json.loads(tis_json_str)
                    log(
                        f"[Worker] TIS extracted: overview={len(doc_tis.overview)}, "
                        f"entries={len(doc_tis.entries)}"
                    )
                    logger.info(
                        "Job %d: TIS extraction OK — overview=%d, entries=%d",
                        job_id, len(doc_tis.overview), len(doc_tis.entries),
                    )
                except Exception as e:
                    # ── Detailed extraction failure diagnostics ──────────────
                    import traceback as _tb
                    exc_tb = _tb.format_exc()
                    logger.error(
                        "Job %d: TIS extraction FAILED — file=%s, file_size=%d, "
                        "error_type=%s, error=%s\nTRACEBACK:\n%s",
                        job_id,
                        path_tis,
                        os.path.getsize(path_tis) if os.path.exists(path_tis) else -1,
                        type(e).__name__,
                        str(e),
                        exc_tb,
                    )
                    err = f"TIS extraction failed: {type(e).__name__}: {e}"
                    extract_errors.append(err)
                    log(f"[Worker] {err}")
                    log(f"[Worker] TIS extraction traceback:\n{exc_tb}")
        else:
            extract_errors.append("TIS file not downloaded -- skipped extraction")
            logger.warning("Job %d: TIS file not found at %s", job_id, path_tis)

        # Store errors in parsed output if any
        if extract_errors:
            parsed["_extraction_errors"] = extract_errors

        log(
            f"[Worker] Extraction complete: parsed keys={list(parsed.keys())}, "
            f"errors={len(extract_errors)}"
        )
        logger.info(
            "Job %d: extraction summary — keys=%s, errors=%d, errors_detail=%s",
            job_id, list(parsed.keys()), len(extract_errors),
            extract_errors if extract_errors else "none",
        )

        # Step 4.6: Reconcile data across all three documents
        _update_job(job_id, current_step="extract", status_message="Reconciling data...", progress_pct=92)
        log("[Worker] Starting reconciliation across 26AS, AIS, and TIS...")

        try:
            reconciled = _reconcile_data(
                ais_data=parsed.get("ais", {}),
                tis_data=parsed.get("tis", {}),
                as26_data=parsed.get("26as", {}),
            )
            # Preserve extraction errors in reconciled output
            if extract_errors:
                reconciled["_extraction_errors"] = extract_errors
            parsed_json = json.dumps(reconciled, ensure_ascii=False, default=str)
            _update_job(job_id, parsed_results=parsed_json, progress_pct=94)
            s = reconciled["summary"]
            log(
                f"[Worker] Reconciliation complete: "
                f"{s['total_entries']} entries, "
                f"{s['total_discrepancies']} discrepancies, "
                f"total income = {s['total_final_income']:,.2f}"
            )
            logger.info(
                "Job %d: reconciliation OK — entries=%d, discrepancies=%d, "
                "income=%.2f, income_heads=%s",
                job_id, s["total_entries"], s["total_discrepancies"],
                s["total_final_income"],
                list(reconciled.get("income_heads", {}).keys()),
            )
        except Exception as e:
            err = f"Reconciliation failed: {e}"
            extract_errors.append(err)
            log(f"[Worker] {err}")
            logger.exception("Job %d: reconciliation error", job_id)
            # Fall back to raw parsed data (still useful downstream)
            if extract_errors:
                parsed["_extraction_errors"] = extract_errors
            parsed_json = json.dumps(parsed, ensure_ascii=False, default=str)
            _update_job(job_id, parsed_results=parsed_json, progress_pct=90)

        # Step 5: Logout
        _update_job(job_id, current_step="logout", status_message="Logging out...", progress_pct=95)
        if page:
            try:
                await logout_itd(page, log, timeline=timeline)
            except Exception as e:
                log(f"[Worker] Logout error (non-fatal): {e}")
        steps.append("logout")

        if required_artifact_failures:
            raise RuntimeError(
                "Required artifact download failed: "
                + "; ".join(required_artifact_failures)
            )

        # Success
        _update_job(
            job_id,
            status="completed",
            current_step=None,
            status_message="All downloads complete",
            steps_completed=json.dumps(steps),
            files_downloaded=json.dumps(files),
            artifact_outcomes=json.dumps(artifact_outcomes),
            completed_at=datetime.datetime.utcnow(),
            progress_pct=100,
        )
        log("[Worker] Job completed successfully.")
        logger.info("Job %d: COMPLETED -- files=%s", job_id, files)

    except Exception as exc:
        # Failure
        tb = traceback.format_exc()
        friendly = _friendly_error(str(exc))
        if not friendly or not friendly.strip():
            raw_msg = str(exc).split("\n")[0].strip()
            friendly = raw_msg[:200] if raw_msg else type(exc).__name__
        safe_tb = sanitize_automation_text(tb)
        safe_exc = sanitize_automation_text(exc)
        log(f"[Worker] Exception: {safe_exc}")
        log(f"[Worker] Traceback:\n{safe_tb}")
        logger.error(
            "Job %d: FAILED -- %s\n%s",
            job_id,
            friendly,
            safe_tb,
        )

        _update_job(
            job_id,
            status="failed",
            current_step=None,
            status_message=f"Failed: {friendly}",
            error_message=f"{friendly}\n\n--- Full traceback ---\n{safe_tb}",
            steps_completed=json.dumps(steps),
            files_downloaded=json.dumps(files),
            artifact_outcomes=json.dumps(artifact_outcomes),
            completed_at=datetime.datetime.utcnow(),
            progress_pct=0,
        )
    finally:
        # Cleanup
        if page and not page.is_closed():
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass


async def _job_worker_loop() -> None:
    """Background asyncio task that processes jobs one at a time."""
    global _worker_running
    _worker_running = True
    logger.info("Job worker loop started.")
    while _worker_running:
        try:
            job_id = await _job_queue.get()
            logger.info("Worker picked up job #%d from queue.", job_id)
            await _run_job(job_id)
        except asyncio.CancelledError:
            logger.info("Job worker loop cancelled.")
            break
        except Exception as exc:
            logger.exception("Unexpected error in worker loop: %s", exc)
            traceback.print_exc()


def enqueue_job(job_id: int) -> None:
    """Add a job ID to the queue. Called from the API endpoint."""
    _job_queue.put_nowait(job_id)
    logger.info("Job %d: Enqueued (queue size ~ %d).", job_id, _job_queue.qsize())


def start_worker() -> None:
    """Start the background worker asyncio task.

    Must be called from within a running asyncio event loop
    (i.e., during FastAPI startup).
    """
    global _worker_task, _worker_running
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_job_worker_loop())
        logger.info("Background worker task created.")


async def stop_worker() -> None:
    """Gracefully stop the background worker. Call during app shutdown."""
    global _worker_running, _worker_task
    _worker_running = False
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    logger.info("Worker stopped.")
