"""
FastAPI application entry point.

Startup sequence:
  1. Load environment variables from .env
  2. Create database tables (idempotent)
  3. Add CORS middleware (origin from FRONTEND_URL env var)
  4. Register global exception handlers (unified error shape)
  5. Start automation job worker
  6. Mount all routers
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # Must run before any import that reads os.environ

# ── Logging configuration ───────────────────────────────────────────────────
# Set up structured console logging so all taxify.* loggers produce
# timestamped, levelled output on stdout — visible in uvicorn logs and
# essential for diagnosing automation import failures.

LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    stream=sys.stdout,
)

# Set our application loggers to the configured level.
# DEBUG-level loggers produce very detailed step-by-step trace for
# automation jobs — enable per-module by setting TAXIFY_LOG_LEVEL=DEBUG.
_taxify_level = os.getenv("TAXIFY_LOG_LEVEL", "INFO").upper()
logging.getLogger("taxify").setLevel(getattr(logging, _taxify_level, logging.INFO))

# Quiet noisy third-party loggers
logging.getLogger("playwright").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user
from app.automation.job_worker import start_worker, stop_worker
from app.db.init_db import create_tables
from app.db.models import User

from app.routers import (
    auth as auth_router,
    itr as itr_router,
    clients as clients_router,
    client_itr as client_itr_router,
    integration as integration_router,
    pan as pan_router,
    tax as tax_router,
    dashboard as dashboard_router,
    automation as automation_router,
)
from app.schemas.auth import UserResponse


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables + launch background worker.  Shutdown: stop worker."""
    create_tables()
    start_worker()
    yield
    await stop_worker()


app = FastAPI(
    title="Indian ITR Filing API",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Accept multiple origins from env (comma-separated), with sensible dev defaults
_allowed_origins_raw = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
)
_allowed_origins = [o.strip() for o in _allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
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
    logger = logging.getLogger("taxify.main")
    logger.exception(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "An unexpected error occurred.",
        ),
    )


from app.routers import eri as eri_router

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router.router)
app.include_router(itr_router.router)
app.include_router(clients_router.router)
app.include_router(client_itr_router.router)
app.include_router(integration_router.router)
app.include_router(pan_router.router)
app.include_router(tax_router.router)
app.include_router(dashboard_router.router)
app.include_router(eri_router.router)
app.include_router(automation_router.router)

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
