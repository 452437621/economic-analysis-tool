"""Detected event APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Event, EventInstrument, Instrument
from app.platform.db import get_session

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(
    limit: int = Query(20, ge=1, le=100),
    type: str | None = Query(None),
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(Event).order_by(Event.event_date.desc()).limit(limit)
    if type:
        stmt = stmt.where(Event.type == type)
    events = session.scalars(stmt).all()
    event_ids = [row.id for row in events]
    links: dict[str, list[str]] = {}
    if event_ids:
        rows = session.execute(
            select(EventInstrument.event_id, Instrument.symbol)
            .join(Instrument, Instrument.id == EventInstrument.instrument_id)
            .where(EventInstrument.event_id.in_(event_ids))
        ).all()
        for event_id, symbol in rows:
            links.setdefault(event_id, []).append(symbol)
    return {
        "data": [
            {
                "id": row.id,
                "type": row.type,
                "subtype": row.subtype,
                "event_date": row.event_date.isoformat() if row.event_date else None,
                "title": row.title,
                "summary": row.summary,
                "instruments": links.get(row.id, []),
            }
            for row in events
        ]
    }
