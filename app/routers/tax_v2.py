"""Phase 2 canonical ITR-1 tax computation endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.db.models import User
from app.engine.filing_gateway_v2 import FilingGatewayV2Error, compute_canonical_itr1
from app.schemas.return_draft import ReturnDraft


router = APIRouter(prefix="/v2/tax-summary", tags=["tax_v2"])


@router.post("/compute")
def compute_tax_summary_v2(
    draft: ReturnDraft,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Compute a tax summary directly from a canonical ReturnDraft.

    Args:
        draft: Canonical typed return draft supplied as the direct JSON body.

    Returns:
        A legacy-headline-compatible summary plus structured breakdown/issues.

    Raises:
        HTTPException: With status 422 for mapping or computation failures.
    """
    try:
        return compute_canonical_itr1(draft).summary
    except FilingGatewayV2Error as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": exc.message, "errors": exc.errors},
        ) from exc
