"""
ITR computation and saved-return router.

All endpoints require a valid Bearer token (get_current_user dependency).

Endpoints:
  POST  /itr1/compute     — compute ITR-1 tax, return breakdown (no DB write)
  POST  /itr4/compute     — compute ITR-4 tax, return breakdown (no DB write)
  POST  /returns/save     — persist a computation result linked to current user
  GET   /returns          — list current user's saved returns (summary only)
  GET   /returns/{id}     — fetch one saved return in full (403 if not owner)
"""

import json
from dataclasses import asdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import SavedReturn, User
from app.engine.calculators.itr1 import compute as compute_itr1
from app.engine.calculators.itr3 import compute as compute_itr3
from app.engine.calculators.itr4 import compute as compute_itr4
from app.schemas.itr1 import ITR1Input
from app.schemas.itr3 import ITR3Input
from app.schemas.itr4 import ITR4Input
from app.schemas.itr_responses import (
    ITR1ComputeResponse,
    ITR3ComputeResponse,
    ITR4ComputeResponse,
    ReturnDetail,
    ReturnSummary,
    SaveRequest,
    SaveResponse,
)

router = APIRouter(tags=["itr"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _decimal_to_str(obj: object) -> object:
    """JSON-serialise Decimal values as strings to avoid float precision loss."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


# ---------------------------------------------------------------------------
# Compute endpoints (stateless — no DB write)
# ---------------------------------------------------------------------------

@router.post("/itr1/compute", response_model=ITR1ComputeResponse)
def itr1_compute(
    body: ITR1Input,
    current_user: User = Depends(get_current_user),
) -> ITR1ComputeResponse:
    """
    Run the ITR-1 tax engine and return the full breakdown.

    Raises HTTP 422 if the input is invalid (Pydantic validation).
    Raises HTTP 400 if the engine rejects the input (e.g. GTI > ₹50L).
    Does NOT persist anything to the database.
    """
    try:
        result = compute_itr1(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _build_itr1_response(result)


@router.post("/itr4/compute", response_model=ITR4ComputeResponse)
def itr4_compute(
    body: ITR4Input,
    current_user: User = Depends(get_current_user),
) -> ITR4ComputeResponse:
    """
    Run the ITR-4 tax engine and return the full breakdown.

    Raises HTTP 422 if the input is invalid (Pydantic validation).
    Raises HTTP 400 if the engine rejects the input (e.g. GTI > ₹50L).
    Does NOT persist anything to the database.
    """
    try:
        result = compute_itr4(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _build_itr4_response(result)


@router.post("/itr3/compute", response_model=ITR3ComputeResponse)
def itr3_compute(
    body: ITR3Input,
    current_user: User = Depends(get_current_user),
) -> ITR3ComputeResponse:
    """
    Run the ITR-3 tax engine and return the full breakdown.

    Raises HTTP 422 if the input is invalid (Pydantic validation).
    Does NOT persist anything to the database.
    """
    try:
        result = compute_itr3(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _build_itr3_response(result)


# ---------------------------------------------------------------------------
# Response builders (dataclass → Pydantic response with field-name mapping)
# ---------------------------------------------------------------------------

def _build_itr1_response(result) -> ITR1ComputeResponse:
    """Convert ITR1Result dataclass to the ITR1ComputeResponse Pydantic model.

    Field-name mappings:
      deductions_total  → deductions_chapter6a
      net_tax_liability → total_tax_payable
    """
    d = asdict(result)
    d["deductions_chapter6a"] = d.pop("deductions_total")
    d["total_tax_payable"] = d.pop("net_tax_liability")
    return ITR1ComputeResponse.model_validate(d)


def _build_itr4_response(result) -> ITR4ComputeResponse:
    """Convert ITR4Result dataclass to the ITR4ComputeResponse Pydantic model.

    Field-name mappings:
      presumptive_income → pgbp_income
      deductions_total   → deductions_chapter6a
      net_tax_liability  → total_tax_payable
    """
    d = asdict(result)
    d["pgbp_income"] = d.pop("presumptive_income")
    d["deductions_chapter6a"] = d.pop("deductions_total")
    d["total_tax_payable"] = d.pop("net_tax_liability")
    return ITR4ComputeResponse.model_validate(d)


def _build_itr3_response(result) -> ITR3ComputeResponse:
    """Convert ITR3Result dataclass to the ITR3ComputeResponse Pydantic model."""
    return ITR3ComputeResponse.model_validate(asdict(result))


# ---------------------------------------------------------------------------
# Persistence endpoints
# ---------------------------------------------------------------------------

@router.post("/returns/save", response_model=SaveResponse, status_code=status.HTTP_201_CREATED)
def save_return(
    body: SaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SaveResponse:
    """
    Persist a tax computation result for the authenticated user.

    Both input_data and computed_result are stored as JSON text blobs.
    Returns the id of the newly created row.
    """
    if body.itr_type not in ("ITR1", "ITR3", "ITR4"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="itr_type must be 'ITR1' or 'ITR4'.",
        )

    row = SavedReturn(
        user_id=current_user.id,
        itr_type=body.itr_type,
        input_data=json.dumps(body.input_data, default=_decimal_to_str),
        computed_result=json.dumps(body.computed_result, default=_decimal_to_str),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return SaveResponse(id=row.id)


@router.get("/returns", response_model=list[ReturnSummary])
def list_returns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReturnSummary]:
    """
    Return a lightweight list of all saved returns for the current user.

    Ordered most-recent first. Only id, itr_type and created_at are returned —
    full data is available via GET /returns/{id}.
    """
    rows = (
        db.query(SavedReturn)
        .filter(SavedReturn.user_id == current_user.id)
        .order_by(SavedReturn.created_at.desc())
        .all()
    )
    return [ReturnSummary.model_validate(r) for r in rows]


@router.get("/returns/{return_id}", response_model=ReturnDetail)
def get_return(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReturnDetail:
    """
    Fetch a single saved return by id.

    Returns HTTP 404 if the record does not exist.
    Returns HTTP 403 if the record belongs to a different user.
    input_data and computed_result are returned as parsed JSON objects.
    """
    row = db.get(SavedReturn, return_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found.")
    if row.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return ReturnDetail(
        id=row.id,
        itr_type=row.itr_type,
        input_data=json.loads(row.input_data),
        computed_result=json.loads(row.computed_result),
        created_at=row.created_at,
    )
