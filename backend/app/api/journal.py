"""Trial journal API (M6): daily notes used by weekly review."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import JournalEntry
from app.platform.db import get_session

router = APIRouter(prefix="/api/journal", tags=["journal"])


class JournalIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    entry_date: date | None = None


@router.get("")
def list_entries(
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> dict:
    rows = session.scalars(
        select(JournalEntry).order_by(JournalEntry.entry_date.desc()).limit(limit)
    ).all()
    return {
        "data": [
            {
                "id": row.id,
                "entry_date": row.entry_date.isoformat(),
                "content": row.content,
                "updated_at": row.updated_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.post("")
def upsert_entry(payload: JournalIn, session: Session = Depends(get_session)) -> dict:
    entry_date = payload.entry_date or date.today()
    row = session.scalar(select(JournalEntry).where(JournalEntry.entry_date == entry_date))
    if row is None:
        row = JournalEntry(entry_date=entry_date, content=payload.content)
        session.add(row)
    else:
        row.content = payload.content
    session.commit()
    return {"id": row.id, "entry_date": row.entry_date.isoformat(), "saved": True}
