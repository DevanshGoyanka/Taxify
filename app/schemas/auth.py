"""
Pydantic schemas for authentication request and response bodies.
"""

from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    """Body for POST /auth/signup."""
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """Body for POST /auth/login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Returned by both signup and login on success."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Returned by GET /me."""
    id: int
    email: str
