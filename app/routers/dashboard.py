from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User, Client, ClientITR

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

class DashboardStatsResponse(BaseModel):
    total: int
    filed: int
    inProgress: int
    docPending: int
    watchList: int
    totalMismatches: int
    totalNotices: int

@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    ay: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not ay:
        ay = "2026-27"

    # Total clients for this user
    total_clients = db.query(Client).filter(Client.user_id == current_user.id).count()

    # Get status counts for the selected assessment year
    status_counts = db.query(ClientITR.status, func.count(ClientITR.id))\
        .join(Client, Client.id == ClientITR.client_id)\
        .filter(Client.user_id == current_user.id, ClientITR.year == ay)\
        .group_by(ClientITR.status)\
        .all()

    counts_dict = {status: count for status, count in status_counts}

    # Match exact UI status cases or handle potential variations
    # Frontend matches exactly: 'Filed', 'In Progress', 'Doc Pending', 'Mismatch'
    filed = counts_dict.get("Filed", 0) + counts_dict.get("FILED", 0)
    in_progress = counts_dict.get("In Progress", 0) + counts_dict.get("IN_PROGRESS", 0)
    doc_pending = counts_dict.get("Doc Pending", 0) + counts_dict.get("DOC_PENDING", 0)
    mismatch = counts_dict.get("Mismatch", 0) + counts_dict.get("MISMATCH", 0)

    return DashboardStatsResponse(
        total=total_clients,
        filed=filed,
        inProgress=in_progress,
        docPending=doc_pending,
        watchList=0,
        totalMismatches=mismatch,
        totalNotices=0,
    )
