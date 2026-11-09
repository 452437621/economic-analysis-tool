"""Watchlist APIs: configurable focus instruments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import AnalyticsResult, Instrument, Quote, WatchItem
from app.platform.db import get_session

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class WatchIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    group: str | None = Field(default=None, max_length=40)
    priority: int = Field(default=3, ge=1, le=5)
    note: str | None = Field(default=None, max_length=500)


class MoveIn(BaseModel):
    direction: str = Field(pattern="^(up|down)$")


def _latest_quotes(session: Session) -> dict[str, Quote]:
    latest: dict[str, Quote] = {}
    for row in session.scalars(select(Quote).order_by(Quote.ts_utc.desc()).limit(3000)).all():
        latest.setdefault(row.instrument_id, row)
    return latest


def _indicator_changes(session: Session) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in session.scalars(
        select(AnalyticsResult).where(AnalyticsResult.kind == "indicator")
    ).all():
        payload = row.payload or {}
        result[row.subject] = {
            "change_20d": payload.get("change_20d"),
            "trend": payload.get("trend"),
        }
    return result


@router.get("")
def list_watchlist(session: Session = Depends(get_session)) -> dict:
    items = session.execute(
        select(WatchItem, Instrument)
        .join(Instrument, Instrument.id == WatchItem.instrument_id)
        .order_by(
            WatchItem.sort_order.asc(),
            WatchItem.priority.asc(),
            Instrument.symbol.asc(),
        )
    ).all()
    quotes = _latest_quotes(session)
    indicators = _indicator_changes(session)
    data = []
    for item, instrument in items:
        quote = quotes.get(instrument.id)
        data.append(
            {
                "symbol": instrument.symbol,
                "name": instrument.name,
                "asset_class": instrument.asset_class,
                "group": item.group,
                "priority": item.priority,
                "sort_order": item.sort_order,
                "note": item.note,
                "price": quote.price if quote else None,
                "change_pct": quote.change_pct if quote else None,
                "quote_ts": quote.ts_utc.isoformat() if quote else None,
                "change_20d": indicators.get(instrument.symbol, {}).get("change_20d"),
                "trend": indicators.get(instrument.symbol, {}).get("trend"),
            }
        )
    return {"data": data}


@router.get("/candidates")
def candidates(session: Session = Depends(get_session)) -> dict:
    watched = {
        row.instrument_id for row in session.scalars(select(WatchItem)).all()
    }
    rows = session.scalars(
        select(Instrument).where(Instrument.active.is_(True)).order_by(Instrument.symbol)
    ).all()
    return {
        "data": [
            {
                "symbol": row.symbol,
                "name": row.name,
                "asset_class": row.asset_class,
                "watched": row.id in watched,
            }
            for row in rows
        ]
    }


@router.post("")
def add_watch(
    payload: WatchIn,
    session: Session = Depends(get_session),
) -> dict:
    instrument = session.scalar(select(Instrument).where(Instrument.symbol == payload.symbol))
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"instrument not found: {payload.symbol}")
    item = session.scalar(
        select(WatchItem).where(WatchItem.instrument_id == instrument.id)
    )
    if item is None:
        max_order = session.scalar(select(func.max(WatchItem.sort_order))) or 0
        item = WatchItem(instrument_id=instrument.id, sort_order=int(max_order) + 1)
        session.add(item)
    item.group = payload.group or item.group
    item.priority = payload.priority
    item.note = payload.note if payload.note is not None else item.note
    session.commit()
    return {"symbol": instrument.symbol, "saved": True, "priority": item.priority}


@router.post("/{symbol}/move")
def move_watch(
    symbol: str,
    payload: MoveIn,
    session: Session = Depends(get_session),
) -> dict:
    instrument = session.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"instrument not found: {symbol}")
    items = session.scalars(
        select(WatchItem).order_by(
            WatchItem.sort_order.asc(), WatchItem.priority.asc(), WatchItem.instrument_id.asc()
        )
    ).all()
    index = next(
        (i for i, item in enumerate(items) if item.instrument_id == instrument.id), None
    )
    if index is None:
        raise HTTPException(status_code=404, detail=f"not in watchlist: {symbol}")
    target = index - 1 if payload.direction == "up" else index + 1
    if target < 0 or target >= len(items):
        return {"symbol": symbol, "moved": False}
    items[index], items[target] = items[target], items[index]
    for order, item in enumerate(items):
        item.sort_order = order
    session.commit()
    return {"symbol": symbol, "moved": True}


@router.delete("/{symbol}")
def remove_watch(symbol: str, session: Session = Depends(get_session)) -> dict:
    instrument = session.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"instrument not found: {symbol}")
    item = session.scalar(
        select(WatchItem).where(WatchItem.instrument_id == instrument.id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"not in watchlist: {symbol}")
    session.delete(item)
    session.commit()
    return {"symbol": symbol, "removed": True}
