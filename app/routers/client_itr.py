import json
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User, Client, ClientITR
from app.routers.clients import ensure_client_active, resolve_owned_client
from app.routers.tax import compute_tax_summary

router = APIRouter(prefix="/clients/{client_id}/itr", tags=["client_itr"])

@router.get("/{year}")
def get_client_itr(
    client_id: str,
    year: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify client ownership
    client = resolve_owned_client(client_id, current_user.id, db)
        
    itr = db.query(ClientITR).filter(ClientITR.client_id == client.id, ClientITR.year == year).first()
    if not itr:
        # Return default values based on client info
        return {
            "name": client.name,
            "pan": client.pan,
            "email": client.email,
            "mobile": client.mobile,
            "aadhaar": client.aadhaar,
            "dob": client.dob,
        }
    return json.loads(itr.form_data)

@router.put("/{year}")
def save_client_itr(
    client_id: str,
    year: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify client ownership
    client = resolve_owned_client(client_id, current_user.id, db)
    ensure_client_active(client)
        
    itr = db.query(ClientITR).filter(ClientITR.client_id == client.id, ClientITR.year == year).first()
    
    # Determine ITR Form type
    # If business turnover/profit is present, or a presumptive scheme is selected, it's ITR-4, else ITR-1
    biz_turnover = payload.get("bizTurnover", 0)
    bp_profit = payload.get("bpNetProfit", 0)
    is_itr4 = (biz_turnover and float(biz_turnover) > 0) or (bp_profit and float(bp_profit) > 0)
    itr_type = "ITR-4" if is_itr4 else "ITR-1"
    
    if not itr:
        itr = ClientITR(
            client_id=client.id,
            year=year,
            itr_type=itr_type,
            status="In Progress",
            form_data=json.dumps(payload),
            computed_result="{}"
        )
        db.add(itr)
    else:
        itr.form_data = json.dumps(payload)
        itr.itr_type = itr_type
        itr.status = "In Progress"
        
    db.commit()
    return {"message": "ITR saved successfully", "itr_type": itr_type}

@router.post("/{year}/validate")
def validate_client_itr(
    client_id: str,
    year: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validate a client ITR payload via the canonical compute-tax engine.

    This endpoint delegates to ``compute_tax_summary``, which runs the full
    CBDT Category-A input and calculation validation before computation.  It
    does NOT reimplement validation rules; the canonical engine is the single
    source of truth.
    """
    # Verify client ownership (also ensures the client is active).
    client = resolve_owned_client(client_id, current_user.id, db)
    ensure_client_active(client)

    # Surface basic identity errors first (these are not engine concerns).
    errors: list[str] = []
    pan = payload.get("pan", "") or client.pan
    if not pan:
        errors.append("PAN is required.")
    elif len(str(pan)) != 10:
        errors.append("PAN must be exactly 10 characters.")

    if not (payload.get("name", "") or client.name):
        errors.append("Name is required.")
    if not (payload.get("dob", "") or client.dob):
        errors.append("Date of Birth is required.")

    warnings: list[str] = []

    # If identity checks pass, delegate the tax/CBDT validation to the engine.
    if not errors:
        regime = str(payload.get("taxRegime", payload.get("regime", "NEW"))).upper()
        # Force the assessment year so the engine applies AY 2026-27 rules.
        engine_payload = dict(payload)
        engine_payload["assessmentYear"] = "2026-27"
        try:
            compute_tax_summary(
                payload=engine_payload,
                regime=regime,
                current_user=current_user,
            )
        except HTTPException as exc:
            detail = exc.detail
            if isinstance(detail, dict):
                msg = detail.get("message", "")
                errs = detail.get("errors", [])
                if msg:
                    errors.append(str(msg))
                if isinstance(errs, list):
                    for e in errs:
                        errors.append(str(e))
            else:
                errors.append(str(detail))
        # No exception ⇒ the engine accepted the input and calculation.

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }

@router.get("/{year}/download")
def download_client_itr_json(
    client_id: str,
    year: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download the stored ITR form data as JSON.

    The stored ``form_data`` blob is returned as-is.  Generation of the
    official CBDT ITD-compliant JSON is handled by the canonical
    ``/itr1/compute-json`` (or ``/itr4/compute-json``) endpoint, which runs
    the typed engine and ``build_itr1_json``.  This legacy endpoint must not
    emit a hand-rolled CBDT structure that diverges from the official schema.
    """
    client = resolve_owned_client(client_id, current_user.id, db)

    itr = db.query(ClientITR).filter(ClientITR.client_id == client.id, ClientITR.year == year).first()
    data = json.loads(itr.form_data) if itr else {}

    return Response(
        content=json.dumps(data, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=ITR_{client.pan}_{year}.json"},
    )

@router.get("/{year}/download-pdf")
def download_client_itr_pdf(
    client_id: str,
    year: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a simple PDF snapshot of the stored ITR form data.

    A full CBDT-compliant PDF should be generated from the canonical engine
    result.  This endpoint renders a lightweight summary from the stored
    form_data; it does not fabricate tax figures.
    """
    client = resolve_owned_client(client_id, current_user.id, db)

    itr = db.query(ClientITR).filter(ClientITR.client_id == client.id, ClientITR.year == year).first()
    data = json.loads(itr.form_data) if itr else {}

    # Build a minimal valid single-page PDF with the client/return summary.
    import io

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        # reportlab unavailable — fall back to a minimal valid PDF shell.
        pdf_data = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << >> /Contents 4 0 R >>\nendobj\n"
            b"4 0 obj\n<< /Length 50 >>\nstream\nBT /F1 12 Tf 70 800 Td "
            b"(ITR Computation Report) Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n"
            b"0000000111 00000 n\n0000000212 00000 n\ntrailer\n<< /Size 5 >>\n"
            b"startxref\n312\n%%EOF"
        )
    else:
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 50, f"ITR Computation Report — {client.name}")
        c.setFont("Helvetica", 10)
        y = height - 80
        c.drawString(50, y, f"PAN: {client.pan or 'N/A'}    Year: {year}    Form: {itr.itr_type if itr else 'ITR-1'}")
        y -= 25
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Stored Form Summary")
        y -= 18
        c.setFont("Helvetica", 9)
        for key, val in list(data.items())[:40]:
            if y < 60:
                break
            c.drawString(60, y, f"{key}: {val}")
            y -= 14
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(
            50, 40,
            "This is a summary snapshot. Use the canonical compute-json endpoint for the official CBDT JSON.",
        )
        c.showPage()
        c.save()
        pdf_data = buf.getvalue()

    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=ITR_{client.pan}_{year}.pdf"},
    )

