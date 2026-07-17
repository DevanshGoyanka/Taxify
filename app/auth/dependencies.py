"""
FastAPI dependency for authenticated endpoints.

Usage in a router:
    from app.auth.dependencies import get_current_user

    @router.get("/me")
    def me(user: User = Depends(get_current_user)):
        ...
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.db.database import get_db
from app.db.models import User

_bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate the Bearer token from the Authorization header.

    Returns the authenticated User ORM object.
    Raises HTTP 401 if the token is invalid or the user no longer exists.
    """
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
