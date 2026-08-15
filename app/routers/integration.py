import os
"""
Import/integration router.

Every endpoint in this router calls the **real** extractor for the
uploaded document type and persists both the raw and parsed content to
the ``imported_document`` table.  No hardcoded mock data is returned.

Real parsers wired:
  - AIS  → ais_extractor.extractor.extract_ais / extract_ais_json
  - TIS  → ais_extractor.tis_extractor.extract_tis / tis_to_frontend_json
  - 26AS → ais_extractor.as26_extractor.extract_26as / extract_26as_json
  - Prefill → app.engine.importers.prefill_parser.parse_prefill_json
  - Form 16 → no parser yet (returns a 501 with a clear message)

The persistence layer (ImportedDocument) enables Phase 5's re-parse /
re-reconcile endpoints without re-downloading from the ITD portal.
"""

import base64
import json
import os
import tempfile
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import ImportedDocument, User

# ── Real extractors ───────────────────────────────────────────────────────────

try:
    from ais_extractor.extractor import extract_ais, extract_ais_json
except ImportError:  # pragma: no cover
    extract_ais = None  # type: ignore[assignment]
    extract_ais_json = None  # type: ignore[assignment]

try:
    from ais_extractor.tis_extractor import extract_tis, tis_to_frontend_json
except ImportError:  # pragma: no cover
    extract_tis = None  # type: ignore[assignment]
    tis_to_frontend_json = None  # type: ignore[assignment]

try:
    from ais_extractor.as26_extractor import extract_26as, extract_26as_json
except ImportError:  # pragma: no cover
    extract_26as = None  # type: ignore[assignment]
    extract_26as_json = None  # type: ignore[assignment]

try:
    from ais_extractor.reconciliation import reconcile as _reconcile
except ImportError:  # pragma: no cover
    _reconcile = None  # type: ignore[assignment]

try:
    from app.engine.importers.prefill_parser import parse_prefill_json, prefill_extraction_to_dict
except ImportError:  # pragma: no cover
    parse_prefill_json = None  # type: ignore[assignment]
    prefill_extraction_to_dict = None  # type: ignore[assignment]

# Legacy 26AS text converter (kept as a fallback for .txt uploads).
try:
    from app.automation.as26_converter import _parse as parse_26as_txt
except ImportError:  # pragma: no cover
    parse_26as_txt = None

# AIS JSON decryptor (for encrypted AIS JSON uploads from the portal).
try:
    from app.automation.ais_json_decryptor import decrypt_ais_json
except ImportError:  # pragma: no cover
    decrypt_ais_json = None


router = APIRouter(tags=["integration"])


# ──────────────────────────────────────────────────────────────────────────────
# Persistence helpers
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_client_id(raw: Optional[str], db: Session, current_user: User) -> Optional[int]:
    """Resolve a client public_id or numeric id to a DB client id.

    Returns None if ``raw`` is None or cannot be resolved.
    """
    if not raw:
        return None
    from app.db.models import Client
    # Try numeric id first.
    try:
        cid = int(raw)
        client = db.get(Client, cid)
        if client is not None and client.user_id == current_user.id:
            return client.id
    except (ValueError, TypeError):
        pass
    # Try public_id (UUID string).
    client = db.query(Client).filter(
        Client.public_id == raw,
        Client.user_id == current_user.id,
    ).first()
    return client.id if client else None


def _upsert_imported_document(
    db: Session,
    client_id: Optional[int],
    user_id: int,
    assessment_year: str,
    document_type: str,
    source: str,
    raw_content: str,
    parsed_content: str,
) -> ImportedDocument:
    """Insert or update an ImportedDocument row.

    If a row already exists for (client_id, assessment_year,
    document_type), update its raw + parsed content and bumped
    ``updated_at``.  Otherwise insert a new row.
    """
    if client_id is None:
        # No client context — use a sentinel client_id of 0 so the row
        # is still persisted (the unique constraint allows it).  In
        # practice every upload should pass a clientId, but we degrade
        # gracefully rather than dropping the document.
        client_id = 0
    existing = db.query(ImportedDocument).filter(
        ImportedDocument.client_id == client_id,
        ImportedDocument.assessment_year == assessment_year,
        ImportedDocument.document_type == document_type,
    ).first()
    if existing is not None:
        existing.raw_content = raw_content
        existing.parsed_content = parsed_content
        existing.source = source
        db.commit()
        db.refresh(existing)
        return existing
    doc = ImportedDocument(
        client_id=client_id,
        user_id=user_id,
        assessment_year=assessment_year,
        document_type=document_type,
        source=source,
        raw_content=raw_content,
        parsed_content=parsed_content,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _b64(content: bytes) -> str:
    """Base64-encode bytes for storage in a Text column."""
    return base64.b64encode(content).decode("ascii")


def _write_temp(content: bytes, suffix: str) -> str:
    """Write bytes to a NamedTemporaryFile and return its path.

    The caller is responsible for unlinking the temp file.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content)
    tmp.close()
    return tmp.name


# ──────────────────────────────────────────────────────────────────────────────
# Upload + extract endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/integration/form16/extract")
def extract_form16(
    file: UploadFile = File(...),
    clientId: Optional[str] = Form(None),
    assessmentYear: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extract Form 16 data from a PDF.

    No Form 16 parser exists yet — this endpoint returns a 501 with a
    clear message so the frontend can show "Form 16 auto-extraction is
    not yet available" instead of mock data.
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "Form 16 auto-extraction is not yet available. "
            "Please enter the Form 16 details manually."
        ),
    )


@router.post("/api/v1/imports/ais")
@router.post("/integration/ais-json/import")
def import_ais_json(
    file: UploadFile = File(...),
    pan: Optional[str] = Form(None),
    dob: Optional[str] = Form(None),
    clientId: Optional[str] = Form(None),
    assessmentYear: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import an AIS PDF or encrypted JSON and return the parsed AIS data.

    If the upload is an encrypted AIS JSON (from the ITD portal), it is
    decrypted using the supplied PAN + DOB.  If it's a PDF, the real
    ``extract_ais`` extractor is called.

    The raw + parsed content is persisted to the ``imported_document``
    table for re-parse / re-reconcile flows.
    """
    if extract_ais is None:
        raise HTTPException(501, "AIS extractor not available on this server.")
    content = file.file.read()
    file.file.seek(0)
    ay = assessmentYear or ""
    client_db_id = _resolve_client_id(clientId, db, current_user)

    # ── Encrypted JSON path ──
    if len(content) > 64 and decrypt_ais_json is not None:
        tmp_path = _write_temp(content, ".json")
        try:
            data = decrypt_ais_json(tmp_path, pan or "", dob or "")
            parsed_str = json.dumps(data, ensure_ascii=False, default=str)
            _upsert_imported_document(
                db, client_db_id, current_user.id, ay, "ais", "upload",
                raw_content=_b64(content), parsed_content=parsed_str,
            )
            return data
        except Exception as exc:
            raise HTTPException(422, f"AIS JSON decryption failed: {exc}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ── Plain JSON path ──
    if content.startswith(b"{"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, f"Invalid AIS JSON: {exc}")
        parsed_str = json.dumps(data, ensure_ascii=False, default=str)
        _upsert_imported_document(
            db, client_db_id, current_user.id, ay, "ais", "upload",
            raw_content=content.decode("utf-8", errors="replace"), parsed_content=parsed_str,
        )
        return data

    # ── PDF path (real extractor) ──
    tmp_path = _write_temp(content, ".pdf")
    try:
        doc = extract_ais(tmp_path)
        parsed_str = extract_ais_json(tmp_path)
        data = json.loads(parsed_str)
        _upsert_imported_document(
            db, client_db_id, current_user.id, ay, "ais", "upload",
            raw_content=_b64(content), parsed_content=parsed_str,
        )
        return data
    except Exception as exc:
        raise HTTPException(422, f"AIS PDF extraction failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/integration/tis/import")
def import_tis(
    file: UploadFile = File(...),
    pan: Optional[str] = Form(None),
    dob: Optional[str] = Form(None),
    clientId: Optional[str] = Form(None),
    assessmentYear: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import a TIS PDF or JSON and return the parsed TIS data.

    Uses the real ``extract_tis`` extractor for PDFs.  JSON uploads are
    parsed directly.  Raw + parsed content is persisted.
    """
    if extract_tis is None:
        raise HTTPException(501, "TIS extractor not available on this server.")
    content = file.file.read()
    file.file.seek(0)
    ay = assessmentYear or ""
    client_db_id = _resolve_client_id(clientId, db, current_user)

    # ── Plain JSON path ──
    if content.startswith(b"{"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, f"Invalid TIS JSON: {exc}")
        parsed_str = json.dumps(data, ensure_ascii=False, default=str)
        _upsert_imported_document(
            db, client_db_id, current_user.id, ay, "tis", "upload",
            raw_content=content.decode("utf-8", errors="replace"), parsed_content=parsed_str,
        )
        return data

    # ── PDF path (real extractor) ──
    tmp_path = _write_temp(content, ".pdf")
    try:
        doc = extract_tis(tmp_path)
        parsed_str = tis_to_frontend_json(doc)
        data = json.loads(parsed_str)
        _upsert_imported_document(
            db, client_db_id, current_user.id, ay, "tis", "upload",
            raw_content=_b64(content), parsed_content=parsed_str,
        )
        return data
    except Exception as exc:
        raise HTTPException(422, f"TIS PDF extraction failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/integration/26as/import")
def import_26as(
    file: UploadFile = File(...),
    clientId: Optional[str] = Form(None),
    assessmentYear: Optional[str] = Form(None),
    pan: Optional[str] = Form(None),
    dob: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import a 26AS PDF, ZIP, TXT, or JSON and return the parsed 26AS data.

    Uses the real ``extract_26as`` extractor for PDFs and the legacy
    ``parse_26as_txt`` for TXT files.  JSON uploads are parsed directly.
    ZIP files (from the ITD/TRACES portal) are extracted using the DOB
    in DDMMYYYY format as the password.  Raw + parsed content is
    persisted.
    """
    content = file.file.read()
    file.file.seek(0)
    ay = assessmentYear or ""
    client_db_id = _resolve_client_id(clientId, db, current_user)

    # ── Plain JSON path ──
    if content.startswith(b"{"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, f"Invalid 26AS JSON: {exc}")
        parsed_str = json.dumps(data, ensure_ascii=False, default=str)
        _upsert_imported_document(
            db, client_db_id, current_user.id, ay, "26as", "upload",
            raw_content=content.decode("utf-8", errors="replace"), parsed_content=parsed_str,
        )
        return data

    # ── ZIP path (from TRACES portal) ──
    # TRACES wraps the 26AS .txt inside a password-protected ZIP.
    # Password is DOB in DDMMYYYY format (e.g. 01-01-1980 → 01011980).
    import zipfile as _zipfile
    import io as _io
    is_zip = False
    try:
        is_zip = _zipfile.is_zipfile(_io.BytesIO(content))
    except Exception:
        is_zip = False
    if is_zip:
        # TRACES ZIP password is DOB in DDMMYYYY format (e.g.
        # 01-01-1980 → 01011980).  The client DOB is stored as
        # YYYY-MM-DD.  Try multiple DOB formats for robustness.
        zip_pwds: list[bytes] = []
        if dob:
            dob_clean = dob.replace("-", "").replace("/", "")
            if len(dob_clean) == 8 and dob[:4].isdigit():
                # YYYY-MM-DD stored → convert to DDMMYYYY and variants
                yyyy, mm, dd = dob_clean[0:4], dob_clean[4:6], dob_clean[6:8]
                zip_pwds = [
                    (dd + mm + yyyy).encode(),    # DDMMYYYY — primary
                    (dd + mm + yyyy[2:4]).encode(),  # DDMMYY
                    (yyyy + mm + dd).encode(),    # YYYYMMDD — fallback
                ]
            else:
                zip_pwds = [dob_clean.encode()]
        try:
            with _zipfile.ZipFile(_io.BytesIO(content), "r") as zf:
                names = zf.namelist()
                # Prefer .txt, then .pdf
                txt_name = next((n for n in names if n.lower().endswith(".txt")), None)
                pdf_name = next((n for n in names if n.lower().endswith(".pdf")), None)
                # Try each password candidate
                extracted = None
                last_err = None
                for pwd in zip_pwds:
                    try:
                        if txt_name:
                            extracted = zf.read(txt_name, pwd=pwd)
                            break
                        elif pdf_name:
                            extracted = zf.read(pdf_name, pwd=pwd)
                            break
                    except (RuntimeError, _zipfile.BadZipFile) as e:
                        last_err = e
                        continue
                if extracted is None:
                    if not zip_pwds:
                        raise HTTPException(
                            422,
                            "26AS ZIP is password-protected but no DOB was supplied. "
                            "Please provide the client's DOB."
                        )
                    raise HTTPException(
                        422,
                        "26AS ZIP password incorrect. Please verify the client's DOB "
                        "matches the PAN card."
                    )
                if txt_name:
                    # Re-run through the TXT path
                    tmp_path = _write_temp(extracted, ".txt")
                    try:
                        if parse_26as_txt is not None:
                            parsed = parse_26as_txt(tmp_path)
                            data = _map_legacy_26as(parsed)
                            parsed_str = json.dumps(data, ensure_ascii=False, default=str)
                            _upsert_imported_document(
                                db, client_db_id, current_user.id, ay, "26as", "upload",
                                raw_content=_b64(content), parsed_content=parsed_str,
                            )
                            return data
                        raise HTTPException(501, "26AS TXT extractor not available on this server.")
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass
                elif pdf_name:
                    if extract_26as is not None:
                        tmp_path = _write_temp(extracted, ".pdf")
                        try:
                            data = extract_26as(tmp_path)
                            parsed_str = json.dumps(data, ensure_ascii=False, default=str)
                            _upsert_imported_document(
                                db, client_db_id, current_user.id, ay, "26as", "upload",
                                raw_content=_b64(content), parsed_content=parsed_str,
                            )
                            return data
                        except Exception as exc:
                            raise HTTPException(422, f"26AS PDF (from ZIP) extraction failed: {exc}")
                        finally:
                            try:
                                os.unlink(tmp_path)
                            except OSError:
                                pass
                    raise HTTPException(501, "26AS PDF extractor not available on this server.")
                else:
                    raise HTTPException(422, "26AS ZIP did not contain a .txt or .pdf file.")
        except _zipfile.BadZipFile:
            raise HTTPException(422, "Invalid 26AS ZIP file.")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, f"26AS ZIP extraction failed: {exc}")

    # ── PDF path (real extractor) ──
    # extract_26as returns {"header": {...}, "parts": {"I": {...}, ...}}
    # which is the same shape parse_26as_txt returns.  Map it through
    # _map_legacy_26as so the frontend gets partIEntries + incomeBreakdown.
    if extract_26as is not None and file.filename and file.filename.lower().endswith(".pdf"):
        tmp_path = _write_temp(content, ".pdf")
        try:
            raw_26as = extract_26as(tmp_path)
            data = _map_legacy_26as(raw_26as)
            parsed_str = json.dumps(data, ensure_ascii=False, default=str)
            _upsert_imported_document(
                db, client_db_id, current_user.id, ay, "26as", "upload",
                raw_content=_b64(content), parsed_content=parsed_str,
            )
            return data
        except Exception as exc:
            raise HTTPException(422, f"26AS PDF extraction failed: {exc}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ── TXT path (legacy converter) ──
    if parse_26as_txt is not None:
        tmp_path = _write_temp(content, ".txt")
        try:
            parsed = parse_26as_txt(tmp_path)
            # Map the legacy converter output into the 26AS frontend shape.
            data = _map_legacy_26as(parsed)
            parsed_str = json.dumps(data, ensure_ascii=False, default=str)
            _upsert_imported_document(
                db, client_db_id, current_user.id, ay, "26as", "upload",
                raw_content=content.decode("utf-8", errors="replace"), parsed_content=parsed_str,
            )
            return data
        except Exception as exc:
            raise HTTPException(422, f"26AS TXT extraction failed: {exc}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    raise HTTPException(501, "26AS extractor not available on this server.")


def _map_legacy_26as(parsed: dict) -> dict:
    """Map the legacy ``parse_26as_txt`` output into the frontend shape.

    The legacy converter returns ``{"header": {...}, "parts": {"I": {...}}}``.
    The frontend expects ``{"partIEntries": [...], "incomeBreakdown": {...}}``.

    Reversal entries (negative amounts) are netted against the matching
    positive entry for the same deductor+section so the frontend sees
    clean positive entries.
    """
    header = parsed.get("header", {})
    fy = header.get("Financial Year") or header.get("FINANCIAL YEAR") or ""

    # ── Collect raw Part I entries, then net reversals ──
    raw_entries: list[dict[str, Any]] = []
    for row in parsed.get("parts", {}).get("I", {}).get("rows", []):
        name = row.get("Name of Deductor") or "Unknown Deductor"
        tan = row.get("TAN of Deductor") or ""
        for d in row.get("_details", []):
            sec = d.get("Section") or "192"
            try:
                amt = float(str(d.get("Amount Paid / Credited(Rs.)", "")).replace(",", "") or 0)
            except ValueError:
                amt = 0.0
            try:
                tds = float(str(d.get("Tax Deducted(Rs.)", "")).replace(",", "") or 0)
            except ValueError:
                tds = 0.0
            try:
                dep = float(str(d.get("TDS Deposited(Rs.)", "")).replace(",", "") or 0)
            except ValueError:
                dep = 0.0
            raw_entries.append({
                "deductorName": name, "tan": tan, "section": sec,
                "amountPaid": amt, "taxDeducted": tds, "taxDeposited": dep,
            })

    # Net reversal entries: group by (deductorName, tan, section) and sum.
    net_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for e in raw_entries:
        key = (e["deductorName"], e["tan"], e["section"])
        if key not in net_map:
            net_map[key] = {**e}
        else:
            net_map[key]["amountPaid"] += e["amountPaid"]
            net_map[key]["taxDeducted"] += e["taxDeducted"]
            net_map[key]["taxDeposited"] += e["taxDeposited"]
    # Build partI entries with BOTH sets of field names so the frontend's
    # TDS transformation (which checks employerTAN/deductorTAN,
    # incomeAmount/totalAmount, tdsDeducted/totalTDS) works correctly.
    partI = []
    for e in net_map.values():
        partI.append({
            "deductorName": e["deductorName"],
            "employerName": e["deductorName"],
            "tan": e["tan"],
            "deductorTAN": e["tan"],
            "employerTAN": e["tan"],
            "section": e["section"],
            "sectionCode": e["section"],
            "amountPaid": e["amountPaid"],
            "incomeAmount": e["amountPaid"],
            "totalAmount": e["amountPaid"],
            "taxDeducted": e["taxDeducted"],
            "tdsDeducted": e["taxDeducted"],
            "totalTDS": e["taxDeducted"],
            "taxDeposited": e["taxDeposited"],
        })

    # Build deductor_details and compute income heads from the NET entries.
    deductor_details: list[dict[str, Any]] = []
    total_tds = 0.0
    for e in partI:
        deductor_details.append({
            "sectionCode": e["section"], "employerName": e["deductorName"],
            "employerTAN": e["tan"], "totalAmount": e["amountPaid"],
            "totalTDS": e["taxDeducted"],
        })
        total_tds += e["taxDeducted"]

    salary_income = sum(x["totalAmount"] for x in deductor_details if x["sectionCode"] in ("192", "192A"))
    interest_income = sum(x["totalAmount"] for x in deductor_details if x["sectionCode"] in ("194A", "193"))
    dividend_income = sum(x["totalAmount"] for x in deductor_details if x["sectionCode"] in ("194", "194K"))
    pan_from_header = (
        header.get("Permanent Account Number (PAN)")
        or header.get("PAN")
        or ""
    )
    return {
        "partIEntries": partI,
        "partIVEntries": [],
        "partVIIEntries": [],
        "tdsEntries": partI,
        "deductorAggregates": partI,
        "incomeBreakdown": {
            "salaryIncome": salary_income,
            "interestIncome": interest_income,
            "dividendIncome": dividend_income,
            "housePropertyIncome": 0.0,
            "capitalGains": 0.0,
            "businessIncome": sum(x["totalAmount"] for x in deductor_details if x["sectionCode"] not in ("192", "192A", "194A", "193", "194", "194K")),
            "lotteryIncome": 0.0,
            "vdaIncome": 0.0,
            "onlineGamingIncome": 0.0,
            "tcsIncome": 0.0,
            "deductorDetails": deductor_details,
        },
        "financialYear": fy,
        "totalTDS": total_tds,
        "pan": pan_from_header,
        "personalInfo": {"pan": pan_from_header} if pan_from_header else {},
    }


@router.post("/integration/prefill/import")
def import_prefill(
    file: UploadFile = File(...),
    clientId: Optional[str] = Form(None),
    assessmentYear: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import a Prefill JSON and return the form-agnostic extraction.

    Uses the real ``parse_prefill_json`` parser.  Raw + parsed content
    is persisted.
    """
    if parse_prefill_json is None:
        raise HTTPException(501, "Prefill parser not available on this server.")
    content = file.file.read()
    file.file.seek(0)
    ay = assessmentYear or ""
    client_db_id = _resolve_client_id(clientId, db, current_user)
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(422, f"Invalid Prefill JSON: {exc}")
    extraction = parse_prefill_json(payload, assessment_year=ay)
    parsed_str = json.dumps(prefill_extraction_to_dict(extraction), ensure_ascii=False, default=str)
    _upsert_imported_document(
        db, client_db_id, current_user.id, ay, "prefill", "upload",
        raw_content=content.decode("utf-8", errors="replace"), parsed_content=parsed_str,
    )
    return json.loads(parsed_str)


# ──────────────────────────────────────────────────────────────────────────────
# Autopopulate / merge endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/integration/autopopulate/form16")
def autopopulate_form16(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    """Merge Form 16 data into formData.

    No Form 16 parser exists yet, so this endpoint just merges whatever
    the frontend supplies in ``form16Data`` into ``formData``.  When a
    parser is added, it will populate ``form16Data`` automatically.
    """
    form_16 = payload.get("form16Data", {})
    form_data = payload.get("formData", {})
    updates = {
        "basic": form_16.get("basic", 0.0),
        "da": form_16.get("da", 0.0),
        "hraReceived": form_16.get("hra", 0.0),
        "bonus": form_16.get("bonus", 0.0),
        "profTax": form_16.get("professionalTax", 0.0),
        "tdsS192": form_16.get("tdsDeducted", 0.0),
    }
    return {**form_data, **updates}


@router.post("/integration/autopopulate/ais")
def autopopulate_ais(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    """Merge AIS data into formData.

    Maps the AIS income heads (salary, dividend, interest, capital
    gains) into the flat formData fields.  The frontend's
    ``mapReconciledToFormData`` does the heavy lifting; this endpoint
    is a thin server-side merge for callers that don't use the frontend
    mapper.
    """
    ais_data = payload.get("aisData", {})
    form_data = payload.get("formData", {})
    summary = ais_data.get("summary", {}) if isinstance(ais_data, dict) else {}
    updates: dict[str, Any] = {}
    if summary:
        if summary.get("total_interest"):
            updates["interestSB"] = summary["total_interest"]
        if summary.get("total_dividend"):
            updates["dividends"] = summary["total_dividend"]
    return {**form_data, **updates}


@router.post("/prefill/autoPopulateAll")
def autopopulate_all(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    """Combine 26AS + AIS + TIS into a flat formData patch.

    This endpoint is a thin server-side merge.  The real reconciliation
    + mapping happens in the frontend via ``mapReconciledToFormData``
    after the portal automation import.  This endpoint is kept for
    callers that upload individual documents and want a merged view.
    """
    ais = payload.get("aisData") or {}
    f26as = payload.get("form26ASData") or {}
    tis = payload.get("tisData") or {}
    salary = 0.0
    dividend = 0.0
    interest = 0.0
    if tis:
        salary = tis.get("salaryAmount", 0.0)
        dividend = tis.get("dividendIncome", 0.0)
        interest = tis.get("interestFromDeposit", 0.0)
    elif f26as:
        ib = f26as.get("incomeBreakdown", {})
        salary = ib.get("salaryIncome", 0.0)
        dividend = ib.get("dividendIncome", 0.0)
        interest = ib.get("interestIncome", 0.0)
    tds_entries = f26as.get("tdsEntries") or []
    employer_entries: list[dict[str, Any]] = []
    if salary > 0:
        employer_entries.append({
            "employerName": "From 26AS",
            "employerTAN": "",
            "employerPAN": "",
            "basic": salary, "da": 0, "hra": 0, "bonus": 0, "allowances": 0,
            "perquisites": 0, "professionalTax": 0,
            "tdsDeducted": sum(x.get("taxDeducted", 0.0) for x in tds_entries if x.get("section") == "192"),
            "grossSalary": salary, "netSalary": salary,
            "financialYear": "", "verified26AS": True,
        })
    bank_interest_entries: list[dict[str, Any]] = []
    if interest > 0:
        bank_interest_entries.append({
            "bankName": "From 26AS", "accountNumber": "", "accountType": "SAVINGS",
            "interestEarned": interest,
            "tdsDeducted": sum(x.get("taxDeducted", 0.0) for x in tds_entries if x.get("section") == "194A"),
            "deductorTAN": "", "section": "194A",
        })
    dividend_entries: list[dict[str, Any]] = []
    if dividend > 0:
        dividend_entries.append({
            "companyName": "From 26AS", "companyPAN": "",
            "dividendAmount": dividend, "tdsDeducted": 0.0,
            "deductorTAN": "", "isin": "", "category": "SHARES", "section": "194",
        })
    tds_salary = sum(x.get("taxDeducted", 0.0) for x in tds_entries if x.get("section") == "192")
    tds_interest = sum(x.get("taxDeducted", 0.0) for x in tds_entries if x.get("section") == "194A")
    tds_other = sum(x.get("taxDeducted", 0.0) for x in tds_entries if x.get("section") not in ("192", "194A"))
    return {
        "basic": salary, "grossSalary": salary, "salaryIncome": salary,
        "interestSB": interest, "interestFD": 0.0, "dividends": dividend,
        "employerEntries": employer_entries,
        "bankInterestEntries": bank_interest_entries,
        "dividendEntries": dividend_entries,
        "tdsEntries": tds_entries,
        "tdsS192": tds_salary, "tds194A": tds_interest, "tdsOther": tds_other,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Reconciliation endpoint (real)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/integration/reconciliation")
def reconciliation(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    """Reconcile AIS + TIS + 26AS data using the real reconciliation engine.

    Returns the reconciled output with income heads, unmatched entries,
    and discrepancies.  If the reconciliation engine is not available,
    returns a 501.
    """
    if _reconcile is None:
        raise HTTPException(501, "Reconciliation engine not available on this server.")
    ais_data = payload.get("aisData", {})
    tis_data = payload.get("tisData", {})
    as26_data = payload.get("data26AS", payload.get("form26ASData", {}))
    try:
        return _reconcile(ais_data, tis_data, as26_data)
    except Exception as exc:
        raise HTTPException(422, f"Reconciliation failed: {exc}")


@router.post("/prefill/autopopulate")
def prefill_autopopulate(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    """Merge Prefill data into formData.

    Uses the real ``parse_prefill_json`` parser to extract form-agnostic
    fields from the uploaded Prefill JSON, then merges them into the
    supplied formData.
    """
    if parse_prefill_json is None:
        raise HTTPException(501, "Prefill parser not available on this server.")
    prefill = payload.get("prefillData", {})
    form_data = payload.get("formData", {})
    if not prefill:
        return {**form_data}
    try:
        extraction = parse_prefill_json(prefill)
        extraction_dict = prefill_extraction_to_dict(extraction)
    except Exception as exc:
        raise HTTPException(422, f"Prefill parse failed: {exc}")
    # Thin server-side merge: personal info + bank accounts + deductions.
    pi = extraction_dict.get("personal_info", {})
    name = pi.get("name", {})
    addr = pi.get("address", {})
    banks = extraction_dict.get("bank_accounts", [])
    deductions = extraction_dict.get("deductions", {})
    updates: dict[str, Any] = {}
    if pi.get("pan"):
        updates["pan"] = pi["pan"]
    if name.get("first_name"):
        updates["firstName"] = name["first_name"]
    if name.get("middle_name"):
        updates["middleName"] = name["middle_name"]
    if name.get("surname_or_org_name"):
        updates["surnameOrOrgName"] = name["surname_or_org_name"]
    if pi.get("dob"):
        updates["dob"] = pi["dob"]
    if addr.get("city_or_town_or_district"):
        updates["city"] = addr["city_or_town_or_district"]
    if addr.get("state_code"):
        updates["state"] = addr["state_code"]
    if addr.get("pin_code"):
        updates["pincode"] = str(addr["pin_code"])
    if banks:
        updates["bankAccountData"] = {
            "accounts": [
                {
                    "bankName": b.get("bank_name", ""),
                    "accountNumber": b.get("bank_account_no", ""),
                    "ifscCode": b.get("ifsc_code", ""),
                    "accountType": (b.get("account_type") or "SB").upper(),
                    "useForRefund": b.get("use_for_refund") == "true",
                }
                for b in banks
            ]
        }
    if deductions.get("section_80tta"):
        updates["s80TTA"] = deductions["section_80tta"]
    if deductions.get("section_80ttb"):
        updates["s80TTB"] = deductions["section_80ttb"]
    if deductions.get("section_80c"):
        updates["s80C"] = deductions["section_80c"]
    if deductions.get("section_80d"):
        updates["s80D"] = deductions["section_80d"]
    return {**form_data, **updates}


# ── ITD ERI Integration Routes ────────────────────────────────────────────────
from datetime import datetime
from fastapi import Request
from app.schemas.eri import (
    ERILoginRequest,
    ERILogoutRequest,
    ERIAddClientRequest,
    ERIValidateClientOtpRequest,
    ERIRegisterClientRequest,
    ERIValidateRegOtpRequest
)
from app.eri.client import eri_post
from app.eri.envelope import encrypt_password


def extract_auth_token(req: Request) -> Optional[str]:
    """Extracts authorization token from request headers (either Authorization Bearer or authToken)."""
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return req.headers.get("authToken")


@router.post("/api/v1/eri/login")
def login_eri(
    current_user: User = Depends(get_current_user),
):
    """Logs in ERI and establishes session with ITD.
    
    Cites: Docs/API_Login_v1.1.pdf Section 4.
    """
    from app.eri.login import eri_login
    
    try:
        res = eri_login()
        return {
            "success": True,
            "authToken": res.get("authToken"),
            "transactionId": res.get("transactionId"),
            "message": "Login successful"
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ERIApiError as exc:
        raise HTTPException(status_code=400, detail=f"ITD ERI Error [{exc.code}]: {exc.desc}")


@router.post("/api/v1/eri/logout")
def logout_eri(
    req: Request,
    current_user: User = Depends(get_current_user),
):
    """Terminates the ERI session with ITD.
    
    Cites: Docs/API_Login_v1.1.pdf Section 4.7.
    """
    from app.eri.login import eri_logout
    
    auth_token = extract_auth_token(req)
    if not auth_token:
        raise HTTPException(status_code=401, detail="authToken or Authorization header is required.")
        
    try:
        eri_logout(auth_token)
        return {
            "success": True,
            "message": "Logout successful"
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ERIApiError as exc:
        raise HTTPException(status_code=400, detail=f"ITD ERI Error [{exc.code}]: {exc.desc}")


@router.post("/api/v1/eri/add-client")
def eri_add_client_route(
    req: Request,
    request: ERIAddClientRequest,
    current_user: User = Depends(get_current_user),
):
    """Submits request to add registered taxpayer as client.
    
    Cites: Docs/API_AddClientFlow_v1.1.pdf Section 4.
    """
    from app.eri.add_client import addClient
    auth_token = extract_auth_token(req)
    if not auth_token:
        raise HTTPException(status_code=401, detail="authToken or Authorization header is required.")
        
    try:
        res = addClient(
            pan=request.pan,
            dateOfBirth=request.dateOfBirth,
            otpSourceFlag=request.otpSourceFlag,
            auth_token=auth_token
        )
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ERIApiError as exc:
        raise HTTPException(status_code=400, detail=f"ITD ERI Error [{exc.code}]: {exc.desc}")


@router.post("/api/v1/eri/validate-client-otp")
def eri_validate_client_otp_route(
    req: Request,
    request: ERIValidateClientOtpRequest,
    current_user: User = Depends(get_current_user),
):
    """Validates the OTP to accept add client request.
    
    Cites: Docs/API_AddClientFlow_v1.1.pdf Section 5.
    """
    from app.eri.add_client import validateClientOtp
    auth_token = extract_auth_token(req)
    if not auth_token:
        raise HTTPException(status_code=401, detail="authToken or Authorization header is required.")
        
    try:
        res = validateClientOtp(
            pan=request.pan,
            transactionId=request.transactionId,
            otpSourceFlag=request.otpSourceFlag,
            otp=request.otp,
            validUpto=request.validUpto,
            auth_token=auth_token
        )
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ERIApiError as exc:
        raise HTTPException(status_code=400, detail=f"ITD ERI Error [{exc.code}]: {exc.desc}")


@router.post("/api/v1/eri/register-client")
def eri_register_client_route(
    req: Request,
    request: ERIRegisterClientRequest,
    current_user: User = Depends(get_current_user),
):
    """Registers an unregistered individual taxpayer and adds them as ERI client.
    
    Cites: Docs/API_AddClientFlow_v1.1.pdf Section 6.
    """
    from app.eri.add_client import addRegisterClient
    auth_token = extract_auth_token(req)
    if not auth_token:
        raise HTTPException(status_code=401, detail="authToken or Authorization header is required.")
        
    try:
        res = addRegisterClient(
            pan=request.pan,
            residentialStatusCd=request.residentialStatusCd,
            firstName=request.firstName or "",
            lastName=request.lastName,
            midName=request.midName or "",
            dateOfBirth=request.dateOfBirth,
            userGender=request.userGender,
            priMobileNum=request.priMobileNum,
            isdCd=request.isdCd,
            priMobBelongsTo=request.priMobBelongsTo,
            priEmailRelationId=request.priEmailRelationId,
            priEmailId=request.priEmailId,
            addrLine1Txt=request.addrLine1Txt,
            addrLine2Txt=request.addrLine2Txt,
            addrLine3Txt=request.addrLine3Txt or "",
            addrLine4Txt=request.addrLine4Txt or "",
            addrLine5Txt=request.addrLine5Txt or "",
            pinCd=request.pinCd or "",
            zipCd=request.zipCd or "",
            stdCd=request.stdCd or "",
            countryCd=request.countryCd,
            landlineNo=request.landlineNo or "",
            stateCd=request.stateCd or "",
            foreignStateDesc=request.foreignStateDesc or "",
            auth_token=auth_token
        )
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ERIApiError as exc:
        raise HTTPException(status_code=400, detail=f"ITD ERI Error [{exc.code}]: {exc.desc}")


@router.post("/api/v1/eri/validate-reg-otp")
def eri_validate_reg_otp_route(
    req: Request,
    request: ERIValidateRegOtpRequest,
    current_user: User = Depends(get_current_user),
):
    """Validates registration OTP from taxpayer to complete registration and client addition.
    
    Cites: Docs/API_AddClientFlow_v1.1.pdf Section 7.
    """
    from app.eri.add_client import validateRegOtp
    auth_token = extract_auth_token(req)
    if not auth_token:
        raise HTTPException(status_code=401, detail="authToken or Authorization header is required.")
        
    try:
        res = validateRegOtp(
            pan=request.pan,
            smsTransactionId=request.smsTransactionId,
            emailTransactionId=request.emailTransactionId,
            mobileOtp=request.mobileOtp,
            emailOtp=request.emailOtp,
            validUpto=request.validUpto,
            auth_token=auth_token
        )
        return res
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ERIApiError as exc:
        raise HTTPException(status_code=400, detail=f"ITD ERI Error [{exc.code}]: {exc.desc}")

