"""
Core security utilities: password hashing and JWT token management.

SECRET_KEY is read from the environment (loaded from .env via python-dotenv).
Tokens use HS256 and expire after 24 hours.
"""

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv()

SECRET_KEY: str = os.environ["SECRET_KEY"]   # raises KeyError immediately if missing
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*. Never store plaintext."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the *hashed* bcrypt digest."""
    return _pwd_context.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    """
    Create a signed JWT for *user_id* that expires in 24 hours.

    The payload contains:
      - sub: str(user_id)  — standard JWT subject claim
      - exp: UTC timestamp — expiry enforced by python-jose on decode
    """
    expire = datetime.now(tz=timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """
    Decode a JWT and return the user_id (int).

    Raises HTTP 401 if the token is invalid, expired, or missing the 'sub' claim.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub: str | None = payload.get("sub")
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject claim.",
            )
        return int(sub)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
