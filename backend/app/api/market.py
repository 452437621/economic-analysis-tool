"""Market data, macro and news read APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import (
    Document,
    EconomicEvent,
    Instrument,
    MacroObs,
    MacroSeries,
    MarketBar,
    MemberPosition,
    PositionSnapshot,
    Quote,
    Source,
    SourceHealth,
)
from app.api.serializers import snapshot_payload
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
    """活跃标的 + 最新行情（含显示单位 unit、合约乘数、延迟信息）。"""
    return snapshot_payload(session)


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


@router.get("/positions")
def positions(session: Session = Depends(get_session)) -> dict:
    latest_date = session.scalar(select(func.max(PositionSnapshot.trade_date)))
    if latest_date is None:
        return {"data": [], "trade_date": None}
    rows = session.scalars(
        select(PositionSnapshot)
        .where(PositionSnapshot.trade_date == latest_date)
        .order_by(PositionSnapshot.net_pos.desc())
    ).all()
    return {
        "trade_date": latest_date.isoformat(),
        "data": [
            {
                "product": row.product,
                "name": row.name,
                "long_pos": row.long_pos,
                "short_pos": row.short_pos,
                "net_pos": row.net_pos,
                "net_ratio": row.net_ratio,
                "long_chg": row.long_chg,
                "short_chg": row.short_chg,
            }
            for row in rows
        ],
    }


@router.get("/positions/products")
def position_products(session: Session = Depends(get_session)) -> dict:
    """会员持仓可选的品种列表（供前端下拉框使用，避免从前端推测）。"""
    latest_date = session.scalar(select(func.max(PositionSnapshot.trade_date)))
    if latest_date is None:
        return {"trade_date": None, "data": []}
    rows = session.scalars(
        select(PositionSnapshot)
        .where(PositionSnapshot.trade_date == latest_date)
        .order_by(PositionSnapshot.product.asc())
    ).all()
    return {
        "trade_date": latest_date.isoformat(),
        "data": [{"product": row.product, "name": row.name} for row in rows],
    }


@router.get("/positions/members")
def position_members(
    product: str = Query(..., min_length=1, max_length=20),
    limit: int = Query(20, ge=1, le=20),
    session: Session = Depends(get_session),
) -> dict:
    code = product.strip().lower()
    latest_date = session.scalar(
        select(func.max(MemberPosition.trade_date)).where(MemberPosition.product == code)
    )
    if latest_date is None:
        return {"product": code, "trade_date": None, "data": []}
    rows = session.scalars(
        select(MemberPosition)
        .where(
            MemberPosition.product == code,
            MemberPosition.trade_date == latest_date,
            MemberPosition.rank <= limit,
        )
        .order_by(MemberPosition.side.asc(), MemberPosition.rank.asc())
    ).all()
    return {
        "product": code,
        "trade_date": latest_date.isoformat(),
        "data": [
            {
                "name": row.name,
                "side": row.side,
                "rank": row.rank,
                "member": row.member,
                "position": row.position,
                "change": row.change,
            }
            for row in rows
        ],
    }


@router.get("/calendar")
def calendar(
    days: int = Query(14, ge=1, le=60),
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
    country: str | None = Query(None, max_length=20),
    category: str | None = Query(None, max_length=40),
    importance_min: int | None = Query(None, ge=1, le=3),
    session: Session = Depends(get_session),
) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conditions = [
        EconomicEvent.ts_utc >= now - timedelta(hours=6),
        EconomicEvent.ts_utc <= now + timedelta(days=days),
    ]
    if country:
        conditions.append(EconomicEvent.country.like(f"%{country}%"))
    if category:
        conditions.append(EconomicEvent.category.like(f"%{category}%"))
    if importance_min is not None:
        conditions.append(EconomicEvent.importance >= importance_min)
    total = int(session.scalar(select(func.count()).select_from(EconomicEvent).where(*conditions)) or 0)
    rows = session.scalars(
        select(EconomicEvent)
        .where(*conditions)
        .order_by(EconomicEvent.ts_utc.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "data": [
            {
                "id": row.id,
                "ts": _iso(row.ts_utc),
                "name": row.name,
                "category": row.category,
                "country": row.country,
                "importance": row.importance,
            }
            for row in rows
        ],
        "meta": {"count": len(rows), "total": total, "days": days, "offset": offset},
    }


@router.get("/news")
def news(
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, description="title keyword"),
    source: str | None = Query(None, description="source name keyword"),
    tier: str | None = Query(None, description="source tier, e.g. S1"),
    since_days: int | None = Query(None, ge=1, le=3650, description="published within N days"),
    session: Session = Depends(get_session),
) -> dict:
    conditions: list = []
    if q:
        conditions.append(Document.title.like(f"%{q}%"))
    if source:
        conditions.append(Source.name.like(f"%{source}%"))
    if tier:
        conditions.append(Source.tier == tier)
    if since_days:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=since_days)
        conditions.append(func.coalesce(Document.published_at, Document.fetched_at) >= cutoff)
    base = (
        select(Document, Source)
        .join(Source, Document.source_id == Source.id, isouter=True)
    )
    count_stmt = select(func.count()).select_from(Document).join(
        Source, Document.source_id == Source.id, isouter=True
    )
    if conditions:
        base = base.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    total = int(session.scalar(count_stmt) or 0)
    rows = session.execute(
        base.order_by(func.coalesce(Document.published_at, Document.fetched_at).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "data": [
            {
                "id": document.id,
                "title": document.title,
                "url": document.url,
                "published_at": _iso(document.published_at or document.fetched_at),
                "source": source.name if source else None,
                "source_id": document.source_id,
                "tier": source.tier if source else None,
                "summary": (document.meta or {}).get("summary") if document.meta else None,
            }
            for document, source in rows
        ],
        "meta": {"count": len(rows), "total": total, "offset": offset},
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
