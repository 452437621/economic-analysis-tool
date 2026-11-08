"""Market data, macro and news read APIs."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.core import (
    Document,
    Instrument,
    MacroObs,
    MacroSeries,
    MarketBar,
    Quote,
    Source,
    SourceHealth,
)
from app.platform.db import get_session

router = APIRouter(prefix="/api", tags=["market"])

ASSET_ORDER = ["metal", "energy", "black", "agri", "fx", "equity", "rate"]


def _iso(dt: datetime | None) -> str | None:
    """Serialize DB datetimes as UTC ISO strings (SQLite returns naive values)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _latest_quotes(session: Session) -> tuple[list[Instrument], dict[str, Quote]]:
    instruments = session.scalars(
        select(Instrument).where(Instrument.active.is_(True)).order_by(Instrument.symbol)
    ).all()
    rows = session.scalars(select(Quote).order_by(Quote.ts_utc.desc()).limit(3000)).all()
    latest: dict[str, Quote] = {}
    for row in rows:
        latest.setdefault(row.instrument_id, row)
    return instruments, latest


@router.get("/market/snapshot")
def snapshot(session: Session = Depends(get_session)) -> dict:
    instruments, latest = _latest_quotes(session)
    source_names = {row.id: row.name for row in session.scalars(select(Source)).all()}
    now = utcnow()
    data = []
    for instrument in instruments:
        quote = latest.get(instrument.id)
        item = {
            "symbol": instrument.symbol,
            "name": instrument.name,
            "asset_class": instrument.asset_class,
            "exchange": instrument.exchange,
            "currency": instrument.currency,
        }
        if quote is not None:
            ts = quote.ts_utc
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            item.update(
                {
                    "price": quote.price,
                    "change_pct": quote.change_pct,
                    "prev_close": quote.prev_close,
                    "ts": _iso(ts),
                    "stale_sec": max(0, int((now - ts).total_seconds())),
                    "delay_sec": quote.delay_sec,
                    "source": source_names.get(quote.source_id),
                }
            )
        data.append(item)
    data.sort(key=lambda row: (ASSET_ORDER.index(row["asset_class"]) if row["asset_class"] in ASSET_ORDER else 99, row["symbol"]))
    asof = max((row["ts"] for row in data if row.get("ts")), default=None)
    return {"data": data, "meta": {"asof": asof, "count": len(data), "with_quote": sum(1 for row in data if row.get("price"))}}


@router.get("/market/bars")
def bars(
    symbol: str = Query(..., description="instrument symbol, e.g. AU"),
    timeframe: str = Query("1d"),
    limit: int = Query(300, ge=1, le=3000),
    session: Session = Depends(get_session),
) -> dict:
    instrument = session.scalar(select(Instrument).where(Instrument.symbol == symbol))
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"instrument not found: {symbol}")
    rows = session.scalars(
        select(MarketBar)
        .where(MarketBar.instrument_id == instrument.id, MarketBar.timeframe == timeframe)
        .order_by(MarketBar.ts_utc.desc())
        .limit(limit)
    ).all()
    rows = list(reversed(rows))
    return {
        "symbol": symbol,
        "name": instrument.name,
        "timeframe": timeframe,
        "data": [
            {
                "ts": _iso(row.ts_utc),
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
                "open_interest": row.open_interest,
            }
            for row in rows
        ],
    }


@router.get("/macro/latest")
def macro_latest(session: Session = Depends(get_session)) -> dict:
    series_list = session.scalars(select(MacroSeries).order_by(MacroSeries.code)).all()
    data = []
    for series in series_list:
        obs = session.scalar(
            select(MacroObs)
            .where(MacroObs.series_id == series.id)
            .order_by(MacroObs.ts_utc.desc())
            .limit(1)
        )
        if obs is None:
            continue
        data.append(
            {
                "code": series.code,
                "name": series.name,
                "unit": series.unit,
                "value": obs.value,
                "ts": _iso(obs.ts_utc),
            }
        )
    return {"data": data}


@router.get("/macro/series")
def macro_series(
    code: str,
    limit: int = Query(500, ge=1, le=5000),
    session: Session = Depends(get_session),
) -> dict:
    series = session.scalar(select(MacroSeries).where(MacroSeries.code == code))
    if series is None:
        raise HTTPException(status_code=404, detail=f"series not found: {code}")
    rows = session.scalars(
        select(MacroObs)
        .where(MacroObs.series_id == series.id)
        .order_by(MacroObs.ts_utc.desc())
        .limit(limit)
    ).all()
    rows = list(reversed(rows))
    return {
        "code": code,
        "name": series.name,
        "unit": series.unit,
        "data": [{"ts": _iso(row.ts_utc), "value": row.value} for row in rows],
    }


@router.get("/news")
def news(
    limit: int = Query(30, ge=1, le=200),
    q: str | None = Query(None, description="title keyword"),
    session: Session = Depends(get_session),
) -> dict:
    stmt = (
        select(Document, Source)
        .join(Source, Document.source_id == Source.id, isouter=True)
        .order_by(func.coalesce(Document.published_at, Document.fetched_at).desc())
        .limit(limit)
    )
    if q:
        stmt = stmt.where(Document.title.like(f"%{q}%"))
    rows = session.execute(stmt).all()
    return {
        "data": [
            {
                "id": document.id,
                "title": document.title,
                "url": document.url,
                "published_at": _iso(document.published_at or document.fetched_at),
                "source": source.name if source else None,
                "tier": source.tier if source else None,
                "summary": (document.meta or {}).get("summary") if document.meta else None,
            }
            for document, source in rows
        ]
    }


@router.get("/system/sources")
def sources(session: Session = Depends(get_session)) -> dict:
    source_rows = session.scalars(select(Source).order_by(Source.name)).all()
    health_rows = session.scalars(
        select(SourceHealth).order_by(SourceHealth.ts.desc()).limit(500)
    ).all()
    latest_health: dict[str, SourceHealth] = {}
    for row in health_rows:
        latest_health.setdefault(row.source_id, row)
    doc_counts = dict(
        session.execute(select(Document.source_id, func.count()).group_by(Document.source_id)).all()
    )
    return {
        "data": [
            {
                "id": source.id,
                "name": source.name,
                "kind": source.kind,
                "tier": source.tier,
                "reliability": source.reliability,
                "base_url": source.base_url,
                "documents": int(doc_counts.get(source.id, 0)),
                "last_ok": latest_health[source.id].ok if source.id in latest_health else None,
                "last_check": _iso(latest_health[source.id].ts) if source.id in latest_health else None,
                "last_error": latest_health[source.id].error if source.id in latest_health else None,
            }
            for source in source_rows
        ]
    }
