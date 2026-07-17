import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User, Client, ClientITR
from app.schemas.clients import ClientCreate, ClientUpdate, ClientResponse, ClientYearResponse
from app.security.portal_crypto import encrypt_portal_password, decrypt_portal_password

router = APIRouter(prefix="/clients", tags=["clients"])

def parse_pan(pan: str):
    pan = pan.strip().upper()
    pan_re = re.compile(r'^[A-Z]{3}[PCHFATBLJG][A-Z][0-9]{4}[A-Z]$')
    if not pan_re.match(pan):
        return {"valid": False, "entityType": "Unknown", "entityDescription": "Unknown", "isIndividualOrHUF": False, "eligibleITRForms": [], "warnings": ["Invalid PAN format"]}
    
    char4 = pan[3]
    mapping = {
        'P': ('Individual', True, ["ITR-1", "ITR-4"]),
        'H': ('HUF (Hindu Undivided Family)', True, ["ITR-1", "ITR-4"]),
        'F': ('Firm', False, ["ITR-4"]),
        'C': ('Company', False, []),
        'A': ('AOP (Association of Persons)', False, []),
        'T': ('Trust', False, []),
        'B': ('BOI (Body of Individuals)', False, []),
        'L': ('Local Authority', False, []),
        'J': ('Artificial Juridical Person', False, []),
        'G': ('Government Agency', False, []),
    }
    
    desc, is_ind_huf, eligible = mapping.get(char4, ('Unknown', False, []))
    warnings = []
    if not is_ind_huf:
        warnings.append(f"Entity type '{desc}' is not an Individual or HUF. ITR-1/4 may not be eligible.")
        
    return {
        "pan": pan,
        "valid": True,
        "entityType": desc,
        "entityDescription": desc,
        "isIndividualOrHUF": is_ind_huf,
        "eligibleITRForms": eligible,
        "warnings": warnings
    }

@router.get("", response_model=List[ClientResponse])
def list_clients(
    search: Optional[str] = None,
    assessmentYear: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Client).filter(Client.user_id == current_user.id)
    if search:
        query = query.filter(
            (Client.name.ilike(f"%{search}%")) | (Client.pan.ilike(f"%{search}%"))
        )
    clients = query.all()
    
    response = []
    for client in clients:
        # Get years for this client
        itr_query = db.query(ClientITR).filter(ClientITR.client_id == client.id)
        if assessmentYear:
            itr_query = itr_query.filter(ClientITR.year == assessmentYear)
        if status_filter:
            itr_query = itr_query.filter(ClientITR.status == status_filter)
        itrs = itr_query.order_by(ClientITR.year.desc()).all()
        
        years_list = [
            ClientYearResponse(
                year=itr.year,
                itrType=itr.itr_type,
                status=itr.status
            )
            for itr in itrs
        ]
        
        # If no years found and assessmentYear is specified, we can return a default placeholder
        # so the UI can navigate. Or just leave it.
        if not years_list and assessmentYear:
            # Check if we should auto-create it or just display it as "Not Started"
            years_list.append(ClientYearResponse(year=assessmentYear, itrType="ITR-1", status="Not Started"))
        elif not years_list:
            # Default fallback for list view
            years_list.append(ClientYearResponse(year="2025-26", itrType="ITR-1", status="Not Started"))

        response.append(
            ClientResponse(
                id=client.id,
                pan=client.pan,
                name=client.name,
                email=client.email,
                mobile=client.mobile,
                aadhaar=client.aadhaar,
                dob=client.dob,
                years=years_list,
                createdAt=client.created_at,
                updatedAt=client.updated_at
            )
        )
    return response

@router.post("", response_model=ClientResponse)
def create_client(
    payload: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check if client with PAN already exists for this user
    existing = db.query(Client).filter(Client.user_id == current_user.id, Client.pan == payload.pan).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Client with PAN {payload.pan} already exists."
        )
    encrypted_pw = None
    if payload.portal_password:
        encrypted_pw = encrypt_portal_password(payload.portal_password)

    client = Client(
        user_id=current_user.id,
        pan=payload.pan.upper(),
        name=payload.name,
        email=payload.email,
        mobile=payload.mobile,
        aadhaar=payload.aadhaar,
        dob=payload.dob,
        portal_password=encrypted_pw,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    
    # Auto-create a default ClientITR row for 2025-26
    default_itr = ClientITR(
        client_id=client.id,
        year="2025-26",
        itr_type="ITR-1",
        status="Not Started",
        form_data="{}",
        computed_result="{}"
    )
    db.add(default_itr)
    db.commit()
    
    years_list = [ClientYearResponse(year="2025-26", itrType="ITR-1", status="Not Started")]
    
    return ClientResponse(
        id=client.id,
        pan=client.pan,
        name=client.name,
        email=client.email,
        mobile=client.mobile,
        aadhaar=client.aadhaar,
        dob=client.dob,
        years=years_list,
        createdAt=client.created_at,
        updatedAt=client.updated_at
    )

@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
        
    itrs = db.query(ClientITR).filter(ClientITR.client_id == client.id).order_by(ClientITR.year.desc()).all()
    years_list = [
        ClientYearResponse(
            year=itr.year,
            itrType=itr.itr_type,
            status=itr.status
        )
        for itr in itrs
    ]
    if not years_list:
        years_list.append(ClientYearResponse(year="2025-26", itrType="ITR-1", status="Not Started"))

    return ClientResponse(
        id=client.id,
        pan=client.pan,
        name=client.name,
        email=client.email,
        mobile=client.mobile,
        aadhaar=client.aadhaar,
        dob=client.dob,
        years=years_list,
        createdAt=client.created_at,
        updatedAt=client.updated_at
    )

@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
        
    if payload.pan is not None:
        client.pan = payload.pan.upper()
    if payload.name is not None:
        client.name = payload.name
    if payload.email is not None:
        client.email = payload.email
    if payload.mobile is not None:
        client.mobile = payload.mobile
    if payload.aadhaar is not None:
        client.aadhaar = payload.aadhaar
    if payload.dob is not None:
        client.dob = payload.dob
    if payload.portal_password is not None:
        client.portal_password = encrypt_portal_password(payload.portal_password) if payload.portal_password else None
        
    db.commit()
    db.refresh(client)
    
    itrs = db.query(ClientITR).filter(ClientITR.client_id == client.id).order_by(ClientITR.year.desc()).all()
    years_list = [
        ClientYearResponse(
            year=itr.year,
            itrType=itr.itr_type,
            status=itr.status
        )
        for itr in itrs
    ]
    if not years_list:
        years_list.append(ClientYearResponse(year="2025-26", itrType="ITR-1", status="Not Started"))

    return ClientResponse(
        id=client.id,
        pan=client.pan,
        name=client.name,
        email=client.email,
        mobile=client.mobile,
        aadhaar=client.aadhaar,
        dob=client.dob,
        years=years_list,
        createdAt=client.created_at,
        updatedAt=client.updated_at
    )

@router.delete("/{client_id}")
def delete_client(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    db.delete(client)
    db.commit()
    return {"message": "Client deleted successfully."}

@router.get("/{client_id}/years")
def get_client_years(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
        
    itrs = db.query(ClientITR).filter(ClientITR.client_id == client.id).order_by(ClientITR.year.desc()).all()
    return [itr.year for itr in itrs] or ["2025-26"]

@router.get("/{client_id}/pan-analysis")
def get_client_pan_analysis(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    return parse_pan(client.pan)

@router.post("/{client_id}/itr-classification")
def classify_itr(
    client_id: int,
    income_profile: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Recommended ITR logic
    # If business income/professional income present -> ITR-4, else ITR-1
    has_business = income_profile.get("hasBusinessIncome", False) or income_profile.get("eligibleFor44AD", False)
    has_professional = income_profile.get("hasProfessionalIncome", False) or income_profile.get("eligibleFor44ADA", False)
    
    if has_business or has_professional:
        recommended = "ITR-4"
        reason = "Presumptive business/professional income (Section 44AD/44ADA) requires filing ITR-4."
    else:
        recommended = "ITR-1"
        reason = "Income from salary, one house property, and other sources (interest, etc.) is eligible for ITR-1."
        
    return {
        "recommendedForm": recommended,
        "classificationReason": reason
    }

def get_decrypted_portal_password(client_id: int, db: Session) -> Optional[str]:
    """
    Retrieve and decrypt the portal password for a given client ID.

    This is an internal helper for the automation module and is not exposed.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client or not client.portal_password:
        return None
    return decrypt_portal_password(client.portal_password)

