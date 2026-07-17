import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import User
from app.auth.security import hash_password, verify_password, create_access_token, decode_access_token
from app.routers.auth import signup, login
from app.schemas.auth import SignupRequest, LoginRequest

# Setup in-memory SQLite DB for testing auth
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

def test_password_hashing():
    pwd = "MySecretPassword123"
    hashed = hash_password(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong_password", hashed) is False

def test_jwt_tokens():
    token = create_access_token(42)
    decoded_user_id = decode_access_token(token)
    assert decoded_user_id == 42

def test_signup_and_login_flow(db):
    # 1. Signup
    signup_req = SignupRequest(email="newuser@example.com", password="SecurePassword123")
    signup_res = signup(signup_req, db=db)
    assert signup_res.access_token is not None
    assert signup_res.token_type == "bearer"
    
    # Verify user created in DB
    user = db.query(User).filter(User.email == "newuser@example.com").first()
    assert user is not None
    assert verify_password("SecurePassword123", user.hashed_password) is True
    
    # Try duplicate signup - should fail with 400
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        signup(signup_req, db=db)
    assert exc_info.value.status_code == 400
    assert "already registered" in exc_info.value.detail
    
    # 2. Login successfully
    login_req = LoginRequest(email="newuser@example.com", password="SecurePassword123")
    login_res = login(login_req, db=db)
    assert login_res.access_token is not None
    
    # Try login with incorrect password
    bad_login_req = LoginRequest(email="newuser@example.com", password="WrongPassword")
    with pytest.raises(HTTPException) as exc_info:
        login(bad_login_req, db=db)
    assert exc_info.value.status_code == 401
    
    # Try login with non-existent user
    non_existent_req = LoginRequest(email="notfound@example.com", password="Password123")
    with pytest.raises(HTTPException) as exc_info:
        login(non_existent_req, db=db)
    assert exc_info.value.status_code == 401
