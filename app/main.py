"""
FastAPI application entry point.

Startup sequence:
  1. Load environment variables from .env
  2. Create database tables (idempotent)
  3. Add CORS middleware (origin from FRONTEND_URL env var)
  4. Register global exception handlers (unified error shape)
  5. Mount all routers
"""

import os

from dotenv import load_dotenv

load_dotenv()  # Must run before any import that reads os.environ

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user
from app.db.init_db import create_tables
from app.db.models import User
from app.routers import auth as auth_router
from app.routers import itr as itr_router
from app.schemas.auth import UserResponse

app = FastAPI(title="Indian ITR Filing API", version="1.0.0")

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Unified error shape  { error: true, message: "...", status_code: N }
# ---------------------------------------------------------------------------

def _error_body(status_code: int, message: str) -> dict:
    """Build the standard error response body."""
    return {"error": True, "message": message, "status_code": status_code}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert every HTTPException into the unified error shape."""
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.status_code, exc.detail),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Convert Pydantic 422 validation errors into the unified error shape.

    Concatenates all field error messages into one readable string so the
    frontend gets a single 'message' field rather than a nested errors list.
    """
    messages = []
    for error in exc.errors():
        loc = " -> ".join(str(p) for p in error["loc"] if p != "body")
        messages.append(f"{loc}: {error['msg']}" if loc else error["msg"])
    human = "; ".join(messages)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body(status.HTTP_422_UNPROCESSABLE_ENTITY, human),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler — returns 500 in the unified error shape."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "An unexpected error occurred.",
        ),
    )

# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------

create_tables()

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router.router)
app.include_router(itr_router.router)

# ---------------------------------------------------------------------------
# Standalone endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
def health_check() -> dict:
    """Return a simple alive signal. No auth required."""
    return {"status": "ok"}


@app.get("/me", response_model=UserResponse, tags=["auth"])
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Return the authenticated user's id and email.

    The frontend calls this on app load to verify that the stored JWT is
    still valid and to retrieve the user's identity. Returns 401 if the
    token is missing, expired, or invalid.
    """
    return UserResponse(id=current_user.id, email=current_user.email)
