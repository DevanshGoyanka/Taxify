import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import User, Client, ClientITR
from app.routers.clients import create_client, list_clients
from app.routers.client_itr import get_client_itr, save_client_itr, validate_client_itr
from app.routers.tax import compute_tax_summary

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
    from app.schemas.clients import ClientCreate
    payload = ClientCreate(
        pan="ABCDE1234F",
        name="Jane Doe",
        email="jane@example.com",
        mobile="9876543210",
        dob="1990-01-01",
        aadhaar="123456789012"
    )
    client_res = create_client(payload, current_user=current_user, db=db)
    assert client_res.id is not None
    assert client_res.name == "Jane Doe"
    
    # 2. Get list
    clients_list = list_clients(current_user=current_user, db=db)
    assert len(clients_list) == 1
    assert clients_list[0].pan == "ABCDE1234F"

def test_client_itr_direct(db, current_user):
    # 1. Setup client
    client = Client(
        user_id=current_user.id,
        pan="ABCDE1234F",
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
    assert default_itr["pan"] == "ABCDE1234F"
    assert default_itr["name"] == "Jane Doe"
    
    # 3. Save ITR
    itr_payload = {
        "basic": 1200000.0,
        "da": 50000.0,
        "interestSB": 15000.0,
        "age": 35,
        "name": "Jane Doe",
        "pan": "ABCDE1234F",
        "dob": "1990-01-01"
    }
    save_res = save_client_itr(client_id=client.id, year="2025-26", payload=itr_payload, current_user=current_user, db=db)
    assert save_res["message"] == "ITR saved successfully"
    
    # 4. Fetch again (now it exists in DB)
    saved_itr = get_client_itr(client_id=client.id, year="2025-26", current_user=current_user, db=db)
    assert saved_itr["basic"] == 1200000.0
    
    # 5. Validate ITR
    val_res = validate_client_itr(client_id=client.id, year="2025-26", payload=itr_payload, current_user=current_user, db=db)
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
