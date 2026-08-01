import json
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User, Client, ClientITR
from app.routers.clients import ensure_client_active, resolve_owned_client

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
    # Simple validation rules
    errors = []
    warnings = []
    
    pan = payload.get("pan", "")
    if not pan:
        errors.append("PAN is required.")
    elif len(pan) != 10:
        errors.append("PAN must be exactly 10 characters.")
        
    name = payload.get("name", "")
    if not name:
        errors.append("Name is required.")
        
    dob = payload.get("dob", "")
    if not dob:
        errors.append("Date of Birth is required.")
        
    # Check caps for deductions
    basic = float(payload.get("basic", 0) or 0)
    s80c = sum(float(payload.get(k, 0) or 0) for k in ["s80C_epf", "s80C_ppf", "s80C_elss", "s80C_lic", "s80C_home"])
    if s80c > 150000:
        warnings.append("Total Section 80C deductions exceed the statutory limit of ₹1,50,000 and will be capped in calculation.")
        
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }

@router.get("/{year}/download")
def download_client_itr_json(
    client_id: str,
    year: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = resolve_owned_client(client_id, current_user.id, db)
        
    itr = db.query(ClientITR).filter(ClientITR.client_id == client.id, ClientITR.year == year).first()
    data = json.loads(itr.form_data) if itr else {}
    
    # Format according to CBDT json utility structure
    cbdt_format = {
        "ITR": {
            "Header": {
                "SubmissionSchemaVal": "ITR-1",
                "SchemaVerVal": "1.0",
                "FormName": itr.itr_type if itr else "ITR-1",
                "AssessmentYear": year
            },
            "PersonalInfo": {
                "AssesseeName": {
                    "SurNameOrOrgName": client.name
                },
                "PAN": client.pan,
                "DOB": client.dob
            },
            "TaxComputation": data
        }
    }
    
    return Response(
        content=json.dumps(cbdt_format, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=ITR_{client.pan}_{year}.json"}
    )

@router.get("/{year}/download-pdf")
def download_client_itr_pdf(
    client_id: str,
    year: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = resolve_owned_client(client_id, current_user.id, db)
        
    # Generate simple PDF
    pdf_data = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 50 >>\nstream\nBT /F1 12 Tf 70 800 Td (ITR Computation Report) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\n0000000212 00000 n\ntrailer\n<< /Size 5 >>\nstartxref\n312\n%%EOF"
    
    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=ITR_{client.pan}_{year}.pdf"}
    )
