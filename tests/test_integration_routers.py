import os
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("PORTAL_ENCRYPTION_KEY", "BF4X7PwLyjUJAZ68rDLJ7ba33LIeR5EyqS4CJkAyeAE=")

from app.db.database import Base
from app.db.models import User, Client, ClientITR
from app.routers.clients import (
    create_client,
    delete_client,
    list_clients,
    restore_client,
    update_client,
    get_decrypted_portal_password,
)
from app.routers.client_itr import get_client_itr, save_client_itr, validate_client_itr, download_client_itr_draft_json, generate_client_cbdt_json
from app.routers.tax import compute_tax_summary
from app.routers.dashboard import get_dashboard_stats

# Setup in-memory SQLite DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def current_user(db):
    user = User(email="test@example.com", hashed_password="hashedpassword")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def test_clients_crud_direct(db, current_user):
    # 1. Create client
    from app.schemas.clients import ClientCreate, ClientUpdate
    payload = ClientCreate(
        pan="ABCPD1234F",
        name="Jane Doe",
        email="jane@example.com",
        mobile="9876543210",
        dob="1990-01-01",
        aadhaar="123456789012"
    )
    client_res = create_client(payload, current_user=current_user, db=db)
    assert client_res.id is not None
    assert client_res.publicId
    assert client_res.name == "Jane Doe"
    
    # 2. Get list
    clients_list = list_clients(current_user=current_user, db=db)
    assert len(clients_list) == 1
    assert clients_list[0].pan == "ABCPD1234F"

    # 3. Update client
    update_payload = ClientUpdate(
        name="Jane Smith",
        email="janesmith@example.com"
    )
    updated_client = update_client(client_id=client_res.id, payload=update_payload, current_user=current_user, db=db)
    assert updated_client.name == "Jane Smith"
    assert updated_client.email == "janesmith@example.com"

    # 4. Archive client without deleting historical records
    legacy_id = client_res.id
    public_id = client_res.publicId
    historical_itr = ClientITR(
        client_id=legacy_id,
        year="2024-25",
        itr_type="ITR-1",
        status="Filed",
        form_data='{"pan":"ABCPD1234F"}',
        computed_result="{}",
    )
    db.add(historical_itr)
    db.commit()

    delete_res = delete_client(client_id=public_id, current_user=current_user, db=db)
    assert delete_res["message"] == "Client archived successfully."
    clients_list = list_clients(current_user=current_user, db=db)
    assert len(clients_list) == 0
    assert db.query(Client).filter(Client.id == legacy_id).first() is not None
    assert db.query(ClientITR).filter(ClientITR.client_id == legacy_id).count() == 1
    with pytest.raises(HTTPException) as archived_error:
        update_client(
            client_id=public_id,
            payload=ClientUpdate(name="Blocked Change"),
            current_user=current_user,
            db=db,
        )
    assert archived_error.value.status_code == 409

    # 5. Restore the same stable client identity
    restored = restore_client(client_id=public_id, current_user=current_user, db=db)
    assert restored.publicId == public_id
    assert restored.id == legacy_id
    clients_list = list_clients(current_user=current_user, db=db)
    assert len(clients_list) == 1

def test_client_itr_direct(db, current_user):
    # 1. Setup client
    client = Client(
        user_id=current_user.id,
        pan="ABCPD1234F",
        name="Jane Doe",
        email="jane@example.com",
        mobile="9876543210",
        dob="1990-01-01",
        aadhaar="123456789012"
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    
    # 2. Get default ITR (no row in DB yet)
    default_itr = get_client_itr(client_id=client.id, year="2025-26", current_user=current_user, db=db)
    assert default_itr["pan"] == "ABCPD1234F"
    assert default_itr["name"] == "Jane Doe"
    
    # 3. Save ITR
    itr_payload = {
        "basic": 1200000.0,
        "da": 50000.0,
        "interestSB": 15000.0,
        "age": 35,
        "name": "Jane Doe",
        "pan": "ABCPD1234F",
        "dob": "1990-01-01"
    }
    save_res = save_client_itr(client_id=client.public_id, year="2025-26", payload=itr_payload, current_user=current_user, db=db)
    assert save_res["message"] == "ITR saved successfully"
    
    # 4. Fetch again (now it exists in DB)
    saved_itr = get_client_itr(client_id=client.public_id, year="2025-26", current_user=current_user, db=db)
    assert saved_itr["basic"] == 1200000.0
    
    # 5. Validate ITR
    val_res = validate_client_itr(client_id=client.public_id, year="2025-26", payload=itr_payload, current_user=current_user, db=db)
    assert val_res["valid"] is True
    assert len(val_res["errors"]) == 0

def test_tax_compute_direct(current_user):
    payload = {
        "age": 35,
        "basic": 1200000.0,
        "da": 50000.0,
        "interestSB": 15000.0,
        "dividends": 10000.0,
        "s80C_epf": 80000.0,
        "s80C_ppf": 50000.0,
        "hpType": "self",
        "homeLoanInt": 0.0
    }
    res = compute_tax_summary(payload=payload, regime="NEW", current_user=current_user)
    assert res["grossSalary"] == 1250000.0
    assert res["totalIncome"] == 1200000.0

def test_dashboard_stats_direct(db, current_user):
    # 1. Setup client
    from app.schemas.clients import ClientCreate
    payload = ClientCreate(
        pan="ABCPD1234F",
        name="Jane Doe",
        email="jane@example.com",
        mobile="9876543210",
        dob="1990-01-01",
        aadhaar="123456789012"
    )
    client_res = create_client(payload, current_user=current_user, db=db)
    assert client_res.id is not None
    
    # Get stats
    stats = get_dashboard_stats(ay="2025-26", current_user=current_user, db=db)
    assert stats.total == 1
    assert stats.filed == 0
    assert stats.inProgress == 0
    assert stats.docPending == 0
    assert stats.totalMismatches == 0

def test_portal_password_crypto_and_response(db, current_user):
    from app.schemas.clients import ClientCreate
    # 1. Create client with portal password
    payload = ClientCreate(
        pan="ABCPD1234F",
        name="Jane Doe",
        email="jane@example.com",
        mobile="9876543210",
        dob="1990-01-01",
        aadhaar="123456789012",
        portal_password="MySecretPassword123"
    )
    client_res = create_client(payload, current_user=current_user, db=db)
    assert client_res.id is not None

    # Verify that the response model DOES NOT contain portal_password
    assert not hasattr(client_res, "portal_password")

    # 2. Query DB directly to verify it is encrypted
    db_client = db.query(Client).filter(Client.id == client_res.id).first()
    assert db_client.portal_password is not None
    assert db_client.portal_password != "MySecretPassword123"

    # 3. Decrypt and check matches original
    decrypted = get_decrypted_portal_password(client_res.id, db=db)
    assert decrypted == "MySecretPassword123"

    # 4. Verify list_clients does not expose portal_password
    clients_list = list_clients(current_user=current_user, db=db)
    assert len(clients_list) == 1
    assert not hasattr(clients_list[0], "portal_password")


# ---------------------------------------------------------------------------
# Phase 0: Form preservation on save, ITR-3 block, and draft export safety
# ---------------------------------------------------------------------------

def _make_phase0_client(db, current_user):
    client = Client(
        user_id=current_user.id,
        pan="EPPPG3078Q",
        name="PhaseZero Tester",
        email="phase0@test.com",
        mobile="9999999999",
        dob="1990-01-01",
        aadhaar="999999999999",
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def test_save_preserves_selected_form(db, current_user):
    client = _make_phase0_client(db, current_user)
    for form in ("ITR-1", "ITR-2", "ITR-3", "ITR-4"):
        payload = {
            "form": form,
            "itrForm": form,
            "basic": 500000,
            "name": client.name,
            "pan": client.pan,
            "dob": client.dob,
        }
        save_client_itr(client_id=client.public_id, year="2026-27", payload=payload, current_user=current_user, db=db)
        itr = db.query(ClientITR).filter(ClientITR.client_id == client.id, ClientITR.year == "2026-27").first()
        assert itr is not None, f"ITR row missing for {form}"
        assert itr.itr_type == form, f"Saved {form} but stored {itr.itr_type}"


def test_save_infers_itr4_when_business_data_and_no_form(db, current_user):
    client = _make_phase0_client(db, current_user)
    payload = {
        "bizTurnover": 1000000,
        "bizPresumptive": "44AD",
        "basic": 500000,
        "name": client.name,
        "pan": client.pan,
        "dob": client.dob,
    }
    save_client_itr(client_id=client.public_id, year="2026-27", payload=payload, current_user=current_user, db=db)
    itr = db.query(ClientITR).filter(ClientITR.client_id == client.id, ClientITR.year == "2026-27").first()
    assert itr.itr_type == "ITR-4"


def test_save_infers_itr1_when_no_business_data_and_no_form(db, current_user):
    client = _make_phase0_client(db, current_user)
    payload = {
        "basic": 500000,
        "interestSB": 10000,
        "name": client.name,
        "pan": client.pan,
        "dob": client.dob,
    }
    save_client_itr(client_id=client.public_id, year="2026-27", payload=payload, current_user=current_user, db=db)
    itr = db.query(ClientITR).filter(ClientITR.client_id == client.id, ClientITR.year == "2026-27").first()
    assert itr.itr_type == "ITR-1"


def test_draft_json_download_blocked_for_itr3(db, current_user):
    client = _make_phase0_client(db, current_user)
    save_client_itr(
        client_id=client.public_id,
        year="2026-27",
        payload={
            "form": "ITR-3",
            "itrForm": "ITR-3",
            "basic": 500000,
            "name": client.name,
            "pan": client.pan,
            "dob": client.dob,
        },
        current_user=current_user,
        db=db,
    )
    with pytest.raises(HTTPException) as exc_info:
        download_client_itr_draft_json(
            client_id=client.public_id,
            year="2026-27",
            current_user=current_user,
            db=db,
        )
    assert exc_info.value.status_code == 422


def test_draft_json_download_allows_itr1(db, current_user):
    client = _make_phase0_client(db, current_user)
    payload = {
        "form": "ITR-1",
        "itrForm": "ITR-1",
        "basic": 500000,
        "name": client.name,
        "pan": client.pan,
        "dob": client.dob,
    }
    save_client_itr(client_id=client.public_id, year="2026-27", payload=payload, current_user=current_user, db=db)
    response = download_client_itr_draft_json(
        client_id=client.public_id,
        year="2026-27",
        current_user=current_user,
        db=db,
    )
    assert response.status_code == 200
    import json
    data = json.loads(response.body)
    assert data.get("form") == "ITR-1"
    assert "Draft" in response.headers.get("content-disposition", "")


# ---------------------------------------------------------------------------
# Phase 1: canonical filing gateway
# ---------------------------------------------------------------------------

def test_cbdt_gateway_blocks_itr3(db, current_user):
    """The canonical filing gateway must fail closed for unsupported ITR-3."""
    client = _make_phase0_client(db, current_user)
    save_client_itr(
        client_id=client.public_id,
        year="2026-27",
        payload={
            "form": "ITR-3",
            "itrForm": "ITR-3",
            "assessmentYear": "2026-27",
            "basic": 500000,
            "name": client.name,
            "pan": client.pan,
            "dob": client.dob,
        },
        current_user=current_user,
        db=db,
    )
    with pytest.raises(HTTPException) as exc_info:
        generate_client_cbdt_json(
            client_id=client.public_id,
            year="2026-27",
            current_user=current_user,
            db=db,
        )
    assert exc_info.value.status_code == 422
    assert "ITR-3" in str(exc_info.value.detail)


def test_cbdt_gateway_blocks_incomplete_itr2(db, current_user):
    """ITR-2 export must fail closed until its canonical mapper is complete."""
    client = _make_phase0_client(db, current_user)
    save_client_itr(
        client_id=client.public_id,
        year="2026-27",
        payload={
            "form": "ITR-2",
            "itrForm": "ITR-2",
            "assessmentYear": "2026-27",
            "basic": 500000,
            "name": client.name,
            "pan": client.pan,
            "dob": client.dob,
        },
        current_user=current_user,
        db=db,
    )
    with pytest.raises(HTTPException) as exc_info:
        generate_client_cbdt_json(
            client_id=client.public_id,
            year="2026-27",
            current_user=current_user,
            db=db,
        )
    assert exc_info.value.status_code == 422
    assert "ITR-2" in str(exc_info.value.detail)


def test_filing_gateway_requires_form(db, current_user):
    """The filing gateway must reject a saved draft with no recognized form."""
    from app.engine.filing_gateway import FilingGatewayError, generate_filing_artifact

    with pytest.raises(FilingGatewayError) as exc_info:
        generate_filing_artifact(
            flat_draft={"assessmentYear": "2026-27"},
            user=current_user,
            db=db,
            include_official_json=True,
        )
    assert "Unsupported or missing ITR form" in str(exc_info.value)
