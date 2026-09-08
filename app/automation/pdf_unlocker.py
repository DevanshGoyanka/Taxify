"""
automation/pdf_unlocker.py
==========================
Strip the owner/user password from a downloaded AIS or TIS PDF.

IT Department PDF password conventions (as of mid-2026)
--------------------------------------------------------
  Form 26AS   : DOB in DDMMYYYY format               (e.g. 01011990)
  AIS (PDF)   : lowercase PAN + DOB DDMMYYYY          (e.g. abcde1234f01011990)
  TIS (PDF)   : same as AIS (lowercase PAN + DDMMYYYY)

We try multiple DOB formats (DDMMYYYY, DDMMYY, DD/MM/YYYY) × PAN variants
(lowercase, none, uppercase) so the caller doesn't need to know the exact format.

DOB format auto-detection
--------------------------
The DOB can be passed in EITHER format:
  - YYYY-MM-DD  (how Client.dob is stored in the DB — e.g. "1990-01-01")
  - DD-MM-YYYY  (vault format — e.g. "01-01-1990")

``_dob_variants()`` auto-detects by checking whether the first hyphen-separated
segment has 4 digits (year-first) or 2 digits (day-first). This fixes the bug
where AIS/TIS PDFs failed to unlock when DOB was in DB format because the
function was incorrectly treating "1990" as day and "01" as year, producing
"19900101" instead of the correct "01011990".

Implementation
--------------
Uses `pikepdf` — Python bindings for the qpdf library.
Install:  pip install pikepdf
If pikepdf is absent the function logs a friendly message and leaves the
encrypted file untouched (download is NOT considered a failure).
"""

import os
import logging

from app.automation.privacy import install_automation_privacy_filter

logger = logging.getLogger(__name__)
install_automation_privacy_filter(logger)


# ── Pre-extraction integrity check ────────────────────────────────────────────

def verify_pdf_decryptable(file_path: str, log=None) -> dict:
    """Check whether a PDF file is actually readable by fitz/pikepdf.

    Called by the job worker BEFORE passing a file to any extractor.
    Returns ``{"ok": True}`` or ``{"ok": False, "reason": str, "hex_head": str}``.

    This catches the case where ``unlock_pdf`` returned ``unlocked: False``
    but the caller continued anyway — the file is still encrypted and will
    crash ``fitz.open()`` with "document closed or encrypted".
    """
    filename = os.path.basename(file_path)

    if not os.path.exists(file_path):
        return {"ok": False, "reason": "file-missing", "hex_head": ""}

    file_size = os.path.getsize(file_path)

    # Read first 16 bytes for diagnostics (PDF magic + version)
    hex_head = ""
    try:
        with open(file_path, "rb") as f:
            head = f.read(16)
            hex_head = head.hex(" ") if head else "(empty)"
    except Exception as exc:
        return {"ok": False, "reason": f"cannot-read-head: {exc}", "hex_head": ""}

    # Check PDF magic number
    if not head.startswith(b"%PDF"):
        msg = f"Not a valid PDF (header={hex_head}, size={file_size})"
        if log:
            log(f"[Verify PDF] {filename}: {msg}")
        logger.warning("verify_pdf_decryptable: %s: %s", file_path, msg)
        return {"ok": False, "reason": msg, "hex_head": hex_head}

    # Try opening via pikepdf without password — if it throws PasswordError,
    # the PDF is still encrypted
    try:
        import pikepdf
        with pikepdf.open(file_path) as pdf:
            pages = len(pdf.pages)
            if log:
                log(
                    f"[Verify PDF] {filename}: OK — {pages} page(s), "
                    f"size={file_size:,} bytes"
                )
            logger.debug("verify_pdf_decryptable: %s OK (%d pages)", file_path, pages)
            return {"ok": True}
    except ImportError:
        # Fall back to fitz (PyMuPDF) if pikepdf is absent
        try:
            import fitz
            doc = fitz.open(file_path)
            pages = doc.page_count
            doc.close()
            if log:
                log(
                    f"[Verify PDF] {filename} (fitz fallback): OK — "
                    f"{pages} page(s), size={file_size:,} bytes"
                )
            logger.debug(
                "verify_pdf_decryptable (fitz): %s OK (%d pages)", file_path, pages
            )
            return {"ok": True}
        except ImportError:
            # Neither library available — assume OK (can't verify)
            logger.warning(
                "verify_pdf_decryptable: neither pikepdf nor fitz available, "
                "skipping check for %s", file_path
            )
            return {"ok": True}
        except Exception as exc:
            msg = f"fitz cannot open: {exc} (header={hex_head}, size={file_size})"
            if log:
                log(f"[Verify PDF] {filename}: {msg}")
            logger.warning("verify_pdf_decryptable: %s: %s", file_path, msg)
            return {"ok": False, "reason": msg, "hex_head": hex_head}
    except pikepdf.PasswordError:
        msg = (
            f"PDF still encrypted — unlock may have failed silently "
            f"(header={hex_head}, size={file_size})"
        )
        if log:
            log(f"[Verify PDF] {filename}: {msg}")
        logger.warning("verify_pdf_decryptable: %s: %s", file_path, msg)
        return {"ok": False, "reason": msg, "hex_head": hex_head}
    except Exception as exc:
        msg = f"pikepdf cannot open: {exc} (header={hex_head}, size={file_size})"
        if log:
            log(f"[Verify PDF] {filename}: {msg}")
        logger.warning("verify_pdf_decryptable: %s: %s", file_path, msg)
        return {"ok": False, "reason": msg, "hex_head": hex_head}


# ---------------------------------------------------------------------------
# Password candidate generation (mirrors unlocker.js from the Electron project)
# ---------------------------------------------------------------------------

def _dob_variants(dob: str) -> list[str]:
    """
    Return all plausible DOB string formats for PDF password generation.

    Handles BOTH common DOB storage formats:
      - DD-MM-YYYY  (vault standard format)
      - YYYY-MM-DD  (DB column format — the Client.dob column)

    Auto-detects which format is used by checking whether the FIRST
    segment has 4 digits (year-first → YYYY-MM-DD) or 2 digits
    (day-first → DD-MM-YYYY).

    Returns empty list if DOB cannot be parsed.
    """
    variants: list[str] = []
    try:
        dob_stripped = dob.strip()
        parts = dob_stripped.split("-")
        if len(parts) != 3:
            logger.warning(
                "_dob_variants: cannot parse DOB=%r — expected 3 hyphen-separated "
                "parts, got %d (raw=%r)",
                "***", len(parts), dob_stripped[:2] + "***",
            )
            return variants

        if not all(p.isdigit() for p in parts):
            logger.warning(
                "_dob_variants: cannot parse DOB=%r — non-digit characters in "
                "segments: %s",
                "***", [p[:2] + "***" for p in parts],
            )
            return variants

        # ── Auto-detect format ──────────────────────────────────────────────
        # YYYY-MM-DD: first segment is 4 digits (e.g. "1990")
        # DD-MM-YYYY: first segment is 2 digits (e.g. "01")
        if len(parts[0]) == 4:
            # → YYYY-MM-DD (DB column format)
            yyyy, mm, dd = parts[0], parts[1], parts[2]
            detected_format = "YYYY-MM-DD (DB)"
            logger.info(
                "_dob_variants: detected YYYY-MM-DD format and normalized it for PDF unlocking."
            )
        else:
            # → DD-MM-YYYY (vault format) — also handles DD/MM/YYYY-ish input
            dd, mm, yyyy = parts[0], parts[1], parts[2]
            detected_format = "DD-MM-YYYY (vault)"

        # Validate ranges (warn but don't fail — ITD might have edge cases)
        try:
            d, m, y = int(dd), int(mm), int(yyyy)
            if not (1 <= d <= 31 and 1 <= m <= 12 and 1900 <= y <= 2100):
                logger.warning(
                    "_dob_variants: DOB out of plausible range — "
                    "d=%d, m=%d, y=%d (detected format=%s, raw=%s)",
                    d, m, y, detected_format,
                    dob_stripped[:2] + "***",
                )
        except ValueError:
            logger.warning(
                "_dob_variants: DOB segments not parseable as ints — "
                "dd=%r, mm=%r, yyyy=%r (detected format=%s)",
                dd, mm, yyyy, detected_format,
            )
            return variants

        yy = yyyy[-2:]

        variants = [
            dd + mm + yyyy,                   # DDMMYYYY  — most common for AIS/TIS
            dd + mm + yy,                     # DDMMYY    — 2-digit year variant
            dd + "/" + mm + "/" + yyyy,       # DD/MM/YYYY — slash variant
        ]

        # Debug: log detected format and resulting variants (masked for security)
        logger.debug(
            "_dob_variants: detected_format=%s, variants_generated=%d",
            detected_format,
            len(variants),
        )

    except Exception:
        logger.exception("_dob_variants: unexpected error parsing DOB")
        return []

    return variants


def password_candidates(pan: str, dob: str) -> list[str]:
    """
    Build the ordered list of password strings to try against a PDF.

    :param pan: PAN number (any case — we normalise internally)
    :param dob: Date of birth in EITHER YYYY-MM-DD (DB format) or DD-MM-YYYY (vault format).
                Auto-detected based on whether first segment has 2 or 4 digits.
    :returns:   De-duplicated list of candidate passwords
    """
    dob_fmts = _dob_variants(dob)
    if not dob_fmts:
        return []

    PAN = (pan or "").strip().upper()
    pan_ = (pan or "").strip().lower()

    seen: set[str] = set()
    candidates: list[str] = []

    # Primary DOB format (DDMMYYYY) tried first with all PAN variants,
    # then additional DOB formats as fallbacks.
    for dob_fmt in dob_fmts:
        for pwd in [
            pan_ + dob_fmt,   # lowercase PAN + DOB  (AIS/TIS confirmed format)
            dob_fmt,          # DOB only             (26AS)
            PAN + dob_fmt,    # uppercase PAN + DOB  (fallback)
        ]:
            if pwd and pwd not in seen:
                seen.add(pwd)
                candidates.append(pwd)

    return candidates


# ---------------------------------------------------------------------------
# Core unlock logic
# ---------------------------------------------------------------------------

def unlock_pdf(
    file_path: str,
    pan: str,
    dob: str,
    log=None,
) -> dict:
    """
    Attempt to remove the PDF password from *file_path* in-place.

    :param file_path: Absolute path to the PDF file.
    :param pan:       PAN number of the assessee.
    :param dob:       Date of birth — auto-detects YYYY-MM-DD (DB format) or DD-MM-YYYY (vault).
    :param log:       Optional callable for status messages (e.g. a GUI log fn).
    :returns: dict with keys:
              ``unlocked`` (bool)
              ``password`` (str, only when unlocked=True)
              ``reason``   (str, only when unlocked=False) —
                           one of 'file-missing', 'pikepdf-missing',
                           'not-encrypted', 'no-dob',
                           'no-password-matched'
    """

    def _log(msg: str):
        if log:
            log(msg)
        logger.debug(msg)

    # ------------------------------------------------------------------
    # Guard: file must exist
    # ------------------------------------------------------------------
    if not os.path.exists(file_path):
        _log(f"[PDF Unlock] File not found: {file_path}")
        logger.warning("unlock_pdf: file not found: %s", file_path)
        return {"unlocked": False, "reason": "file-missing"}

    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    # Debug: log file details
    logger.info(
        "unlock_pdf starting for an artifact: size=%d, pan_present=%s, dob_present=%s",
        file_size,
        bool(pan),
        bool(dob),
    )

    # Read first bytes to verify it's actually a PDF
    try:
        with open(file_path, "rb") as fh:
            pdf_head = fh.read(16)
            pdf_head_hex = pdf_head.hex(" ")
        _log(
            f"[PDF Unlock] {filename}: size={file_size:,} bytes, "
            f"header={pdf_head_hex}"
        )
        logger.debug(
            "unlock_pdf %s: header=%s, size=%d",
            filename, pdf_head_hex, file_size,
        )
        if not pdf_head.startswith(b"%PDF"):
            _log(
                f"[PDF Unlock] {filename}: WARNING — not a valid PDF! "
                f"Header is '{pdf_head_hex}'. Unlock will likely fail."
            )
            logger.warning(
                "unlock_pdf %s: invalid PDF header '%s'", file_path, pdf_head_hex,
            )
    except Exception as exc:
        _log(f"[PDF Unlock] {filename}: Cannot read file header: {exc}")
        logger.exception("unlock_pdf: cannot read header for %s", file_path)
        return {"unlocked": False, "reason": f"cannot-read-file: {exc}"}

    # ------------------------------------------------------------------
    # Guard: pikepdf must be importable
    # ------------------------------------------------------------------
    try:
        import pikepdf
    except ImportError:
        _log(
            f"[PDF Unlock] pikepdf not installed — leaving {filename} encrypted.\n"
            "  Install it with:  pip install pikepdf"
        )
        return {"unlocked": False, "reason": "pikepdf-missing"}

    # ------------------------------------------------------------------
    # Guard: is the PDF actually encrypted?
    # ------------------------------------------------------------------
    try:
        # Opening without a password succeeds for unencrypted files.
        with pikepdf.open(file_path) as pdf:
            _log(f"[PDF Unlock] {filename} is not encrypted — nothing to do.")
            return {"unlocked": False, "reason": "not-encrypted"}
    except pikepdf.PasswordError:
        pass   # encrypted — fall through to brute-force the password
    except Exception as e:
        _log(f"[PDF Unlock] Could not open {filename}: {e}")
        return {"unlocked": False, "reason": f"open-error: {e}"}

    # ------------------------------------------------------------------
    # Build candidate list
    # ------------------------------------------------------------------
    # ── Diagnostic: log the RAW dob value format before parsing ──────────
    # We mask the actual DOB but show the FORMAT pattern (how many chars in
    # each hyphen-separated segment) so we can tell YYYY-MM-DD from DD-MM-YYYY.
    dob_stripped = (dob or "").strip()
    dob_seg_lengths = [str(len(s)) for s in dob_stripped.split("-")] if dob_stripped else []
    logger.info(
        "unlock_pdf: DOB format analysis — raw_dob_seg_lengths=%s, "
        "total_parts=%d, has_hyphens=%s, pan_present=%s, dob_present=%s",
        "-".join(dob_seg_lengths) if dob_seg_lengths else "empty",
        len(dob_seg_lengths),
        "-" in dob_stripped,
        bool(pan),
        bool(dob_stripped),
    )

    candidates = password_candidates(pan, dob)
    if not candidates:
        _log(
            f"[PDF Unlock] No DOB stored for PAN {pan} — "
            f"leaving {filename} encrypted."
        )
        logger.warning(
            "unlock_pdf: no password candidates for an artifact "
            "(pan_available=%s, dob_available=%s, raw_dob_seg_lengths=%s)",
            bool(pan),
            bool(dob),
            "-".join(dob_seg_lengths) if dob_seg_lengths else "empty",
        )
        return {"unlocked": False, "reason": "no-dob"}

    logger.info(
        "unlock_pdf: trying %d password candidates for an artifact "
        "(dob_seg_lengths=%s, first_candidate_len=%d)",
        len(candidates),
        "-".join(dob_seg_lengths) if dob_seg_lengths else "empty",
        len(candidates[0]) if candidates else 0,
    )
    _log(
        f"[PDF Unlock] {len(candidates)} candidate(s) prepared for an artifact "
        f"(pan={'yes' if pan else 'no'}, dob={'yes' if dob else 'no'})"
    )

    # ------------------------------------------------------------------
    # Try each candidate
    # ------------------------------------------------------------------
    tmp_path = file_path + ".unlocked.tmp"

    last_error = ""
    for i, pwd in enumerate(candidates, 1):
        # Never log any portion of a generated password candidate.
        logger.debug(
            "unlock_pdf candidate %d/%d for an artifact",
            i,
            len(candidates),
        )
        try:
            with pikepdf.open(file_path, password=pwd) as pdf:
                pdf.save(tmp_path)
            # Success — replace original
            os.replace(tmp_path, file_path)
            _log(
                f"[PDF Unlock] ✓ {filename} unlocked with candidate {i}"
            )
            logger.info(
                "unlock_pdf: SUCCESS for %s (candidate %d/%d)",
                file_path, i, len(candidates),
            )
            return {"unlocked": True, "password": pwd}
        except pikepdf.PasswordError:
            last_error = f"bad-password (candidate {i})"
            logger.debug("unlock_pdf: candidate %d rejected (wrong password)", i)
            continue       # wrong password — try next
        except Exception as e:
            last_error = f"unexpected-error at candidate {i}: {e}"
            _log(f"[PDF Unlock] Unexpected error for {filename}: {e}")
            logger.exception(
                "unlock_pdf: unexpected error at candidate %d for %s", i, file_path,
            )
            break

    # Cleanup temp if left over
    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass

    _log(
        f"[PDF Unlock] ✗ {filename}: all {len(candidates)} candidate(s) failed. "
        f"Last error: {last_error}. PDF remains encrypted."
    )
    # Build masked candidate summary for server logs
    masked_candidates = []
    for c in candidates:
        if len(c) > 6:
            masked_candidates.append(c[:4] + "***" + c[-2:])
        else:
            masked_candidates.append("***")

    logger.warning(
        "unlock_pdf: FAILED for %s — %d candidates exhausted, last_error=%s, "
        "candidates_masked=%s, pan_present=%s, dob_seg_lengths=%s, file_size=%d",
        file_path,
        len(candidates),
        last_error,
        masked_candidates,
        bool(pan),
        "-".join(dob_seg_lengths) if dob_seg_lengths else "empty",
        file_size,
    )
    return {
        "unlocked": False,
        "reason": "no-password-matched",
        "candidates_tried": len(candidates),
        "last_error": last_error,
        "candidates_masked": masked_candidates,
    }


# ---------------------------------------------------------------------------
# Convenience: unlock a whole folder
# ---------------------------------------------------------------------------

def unlock_pdfs_in_dir(
    directory: str,
    pan: str,
    dob: str,
    log=None,
    glob_pattern: str = "*.pdf",
) -> list[dict]:
    """
    Unlock every PDF in *directory* that matches *glob_pattern*.

    :returns: List of result dicts (one per file attempted), each containing
              ``file``, ``unlocked``, and either ``password`` or ``reason``.
    """
    import glob

    results = []
    pdf_files = sorted(glob.glob(os.path.join(directory, glob_pattern)))

    if not pdf_files:
        if log:
            log(f"[PDF Unlock] No PDFs found in {directory}")
        return results

    for pdf_file in pdf_files:
        result = unlock_pdf(pdf_file, pan=pan, dob=dob, log=log)
        result["file"] = pdf_file
        results.append(result)

    return results
