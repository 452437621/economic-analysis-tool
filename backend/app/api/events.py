"""Detected event APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Event, EventInstrument, Instrument
from app.platform.db import get_session

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    type: str | None = Query(None),
    q: str | None = Query(None, description="title keyword"),
    instrument: str | None = Query(None, description="related instrument symbol"),
    session: Session = Depends(get_session),
) -> dict:
    conditions = []
    if type:
        conditions.append(Event.type == type)
    if q:
        conditions.append(Event.title.like(f"%{q}%"))
    if instrument:
        subquery = (
            select(EventInstrument.event_id)
            .join(Instrument, Instrument.id == EventInstrument.instrument_id)
            .where(Instrument.symbol == instrument.upper())
        )
        conditions.append(Event.id.in_(subquery))

    count_stmt = select(func.count()).select_from(Event)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = int(session.scalar(count_stmt) or 0)

    stmt = select(Event).order_by(Event.event_date.desc())
    if conditions:
        stmt = stmt.where(*conditions)
    events = session.scalars(stmt.offset(offset).limit(limit)).all()
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
                "impact": row.impact,
                "instruments": links.get(row.id, []),
                # 事件 → 证据链：source_ids 即原始 document id（前端可打开证据抽屉）
                "document_id": (row.source_ids or [None])[0] if row.source_ids else None,
                "document_ids": list(row.source_ids or []),
            }
            for row in events
        ],
        "meta": {"count": len(events), "total": total, "offset": offset},
    }
