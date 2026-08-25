"""Persistence helpers for the shared filing lifecycle."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import FilingRecord


def upsert_filing_record(
    *,
    db: Session,
    client_id: int,
    user_id: int,
    assessment_year: str,
    itr_type: str,
    eri_mode: str,
    eri_environment: str,
    **updates: Any,
) -> FilingRecord:
    """Insert or update the unique client/AY/form filing record."""
    row = (
        db.query(FilingRecord)
        .filter(
            FilingRecord.client_id == client_id,
            FilingRecord.assessment_year == assessment_year,
            FilingRecord.itr_type == itr_type,
        )
        .first()
    )
    if row is None:
        row = FilingRecord(
            client_id=client_id,
            user_id=user_id,
            assessment_year=assessment_year,
            itr_type=itr_type,
            eri_mode=eri_mode,
            eri_environment=eri_environment,
        )
        db.add(row)
    else:
        row.user_id = user_id
        row.eri_mode = eri_mode
        row.eri_environment = eri_environment

    for name, value in updates.items():
        if name == "portal_result" and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, default=str)
        if hasattr(row, name):
            setattr(row, name, value)
    db.commit()
    db.refresh(row)
    return row
