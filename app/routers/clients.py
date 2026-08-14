import datetime
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User, Client, ClientITR
from app.schemas.clients import ClientCreate, ClientUpdate, ClientResponse, ClientYearResponse
from app.schemas.security.portal_crypto import encrypt_portal_password, decrypt_portal_password

router = APIRouter(prefix="/clients", tags=["clients"])


def resolve_owned_client(identifier: str | int, user_id: int, db: Session) -> Client:
    """Resolve an owned client by stable public ID or legacy integer ID."""
    identifier_text = str(identifier).strip()
    query = db.query(Client).filter(Client.user_id == user_id)
    if identifier_text.isdigit():
        query = query.filter(Client.id == int(identifier_text))
    else:
        query = query.filter(Client.public_id == identifier_text)
    client = query.first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


def ensure_client_active(client: Client) -> None:
    """Reject mutations against an archived client until it is restored."""
    if client.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CLIENT_ARCHIVED",
                "message": "Restore this client before making changes.",
                "clientId": client.public_id,
            },
        )


def client_years(client_id: int, db: Session) -> List[ClientYearResponse]:
    """Return persisted assessment years for a client, newest first."""
    itrs = (
        db.query(ClientITR)
        .filter(ClientITR.client_id == client_id)
        .order_by(ClientITR.year.desc())
        .all()
    )
    return [
        ClientYearResponse(year=itr.year, itrType=itr.itr_type, status=itr.status)
        for itr in itrs
    ]


def serialize_client(client: Client, db: Session, years: Optional[List[ClientYearResponse]] = None) -> ClientResponse:
    """Build the public client response without exposing portal credentials."""
    return ClientResponse(
        id=client.id,
        publicId=client.public_id,
        pan=client.pan,
        name=client.name,
        email=client.email,
        mobile=client.mobile,
        aadhaar=client.aadhaar,
        dob=client.dob,
        archived=client.archived_at is not None,
        archivedAt=client.archived_at,
        years=client_years(client.id, db) if years is None else years,
        createdAt=client.created_at,
        updatedAt=client.updated_at,
    )

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
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Client).filter(Client.user_id == current_user.id)
    if not include_archived:
        query = query.filter(Client.archived_at.is_(None))
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
            years_list.append(ClientYearResponse(year="2026-27", itrType="ITR-1", status="Not Started"))

        response.append(serialize_client(client, db, years_list))
    return response

@router.post("", response_model=ClientResponse)
def create_client(
    payload: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Preserve archived clients and their historical returns. Re-creation must
    # restore the original stable identity instead of allocating a new client.
    existing = (
        db.query(Client)
        .filter(Client.user_id == current_user.id, Client.pan == payload.pan)
        .first()
    )
    if existing:
        code = "CLIENT_ARCHIVED" if existing.archived_at is not None else "CLIENT_ALREADY_EXISTS"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": code,
                "message": "An archived client with this PAN can be restored."
                if existing.archived_at is not None
                else "A client with this PAN already exists.",
                "clientId": existing.public_id,
            },
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
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLIENT_ALREADY_EXISTS", "message": "A client with this PAN already exists."},
        ) from exc
    db.refresh(client)

    # Assessment-year workspaces are created only when the user starts a return.
    years_list: List[ClientYearResponse] = []
    return serialize_client(client, db, years_list)

@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = resolve_owned_client(client_id, current_user.id, db)
    return serialize_client(client, db)

@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: str,
    payload: ClientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = resolve_owned_client(client_id, current_user.id, db)
    ensure_client_active(client)

    if payload.pan is not None and payload.pan != client.pan:
        duplicate = (
            db.query(Client)
            .filter(
                Client.user_id == current_user.id,
                Client.pan == payload.pan,
                Client.id != client.id,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "PAN_ASSIGNED_TO_ANOTHER_CLIENT",
                    "message": "This PAN is already assigned to another client.",
                    "clientId": duplicate.public_id,
                },
            )
        client.pan = payload.pan
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
        
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLIENT_ALREADY_EXISTS", "message": "A client with this PAN already exists."},
        ) from exc
    db.refresh(client)
    return serialize_client(client, db)

@router.delete("/{client_id}")
def delete_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archive a client while preserving every historical return."""
    client = resolve_owned_client(client_id, current_user.id, db)
    if client.archived_at is None:
        client.archived_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
    return {"message": "Client archived successfully.", "clientId": client.public_id}


@router.post("/{client_id}/restore", response_model=ClientResponse)
def restore_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Restore an archived client under the same stable identity."""
    client = resolve_owned_client(client_id, current_user.id, db)
    if client.archived_at is not None:
        client.archived_at = None
        db.commit()
        db.refresh(client)
    return serialize_client(client, db)

@router.get("/{client_id}/years")
def get_client_years(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = resolve_owned_client(client_id, current_user.id, db)
        
    itrs = db.query(ClientITR).filter(ClientITR.client_id == client.id).order_by(ClientITR.year.desc()).all()
    return [itr.year for itr in itrs] or ["2026-27"]

@router.get("/{client_id}/pan-analysis")
def get_client_pan_analysis(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = resolve_owned_client(client_id, current_user.id, db)
    return parse_pan(client.pan)

@router.post("/{client_id}/itr-classification")
def classify_itr(
    client_id: str,
    income_profile: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resolve_owned_client(client_id, current_user.id, db)
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

def get_decrypted_portal_password(client_identifier: str | int, db: Session) -> Optional[str]:
    """Retrieve and decrypt a client's stored portal password.

    Args:
        client_identifier: Client public ID or legacy numeric database ID.
        db: Active SQLAlchemy database session.

    Returns:
        The decrypted password when present; otherwise ``None``.
    """
    identifier = str(client_identifier)
    client = db.query(Client).filter(Client.public_id == identifier).first()
    if client is None and identifier.isdigit():
        client = db.query(Client).filter(Client.id == int(identifier)).first()
    if not client or not client.portal_password:
        return None
    return decrypt_portal_password(client.portal_password)

