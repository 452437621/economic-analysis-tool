"""Analytics read APIs (M3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import AnalyticsResult, Instrument
from app.platform.db import get_session

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _latest(session: Session, kind: str, subject: str | None = None) -> AnalyticsResult | None:
    stmt = select(AnalyticsResult).where(AnalyticsResult.kind == kind)
    if subject is not None:
        stmt = stmt.where(AnalyticsResult.subject == subject)
    return session.scalar(stmt.order_by(AnalyticsResult.asof.desc(), AnalyticsResult.created_at.desc()).limit(1))


def _all_latest(session: Session, kind: str) -> dict[str, dict]:
    rows = session.scalars(
        select(AnalyticsResult).where(AnalyticsResult.kind == kind).order_by(AnalyticsResult.asof.desc())
    ).all()
    latest: dict[str, AnalyticsResult] = {}
    for row in rows:
        latest.setdefault(row.subject, row)
    return {
        subject: {"asof": row.asof.isoformat(), "payload": row.payload}
        for subject, row in latest.items()
    }


@router.get("/overview")
def overview(session: Session = Depends(get_session)) -> dict:
    wind = _latest(session, "wind", "market")
    regimes = _all_latest(session, "regime")
    correlation = _latest(session, "correlation", "matrix")
    analogs = _latest(session, "analogs", "current")
    attribution = {
        symbol: payload for symbol, payload in _all_latest(session, "attribution").items()
    }
    indicators = _all_latest(session, "indicator")
    calendar_study = _latest(session, "calendar_study", "market")
    names = {
        row.symbol: row.name
        for row in session.scalars(select(Instrument)).all()
    }

    movers = []
    for symbol, item in indicators.items():
        payload = item["payload"] or {}
        change = payload.get("change_20d")
        if change is None:
            continue
        movers.append(
            {
                "symbol": symbol,
                "name": names.get(symbol, symbol),
                "change_20d": change,
                "trend": payload.get("trend"),
                "percentile_252": payload.get("percentile_252"),
                "vol20": payload.get("vol20_annual_pct"),
            }
        )
    movers.sort(key=lambda row: abs(row["change_20d"]), reverse=True)

    return {
        "wind": wind.payload if wind else None,
        "regimes": {country: item["payload"] for country, item in regimes.items()},
        "correlation": (
            {
                "window": correlation.payload.get("window"),
                "avg_abs_corr": correlation.payload.get("avg_abs_corr"),
                "top_pairs": (correlation.payload.get("top_pairs") or [])[:6],
            }
            if correlation
            else None
        ),
        "attribution": {symbol: item["payload"] for symbol, item in attribution.items()},
        "analogs": analogs.payload if analogs else None,
        "calendar_study": (
            {"asof": calendar_study.asof.isoformat(), **calendar_study.payload}
            if calendar_study
            else None
        ),
        "movers": movers[:8],
        "asof": indicators.get("AU", {}).get("asof") or (wind.asof.isoformat() if wind else None),
    }


@router.get("/indicators")
def indicators(
    symbol: str | None = Query(None),
    top: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    rows = _all_latest(session, "indicator")
    if symbol:
        if symbol not in rows:
            raise HTTPException(status_code=404, detail=f"no indicators for {symbol}")
        return {"data": [{"subject": symbol, **rows[symbol]}]}
    data = [{"subject": subject, **item} for subject, item in rows.items()]
    data.sort(key=lambda row: abs((row["payload"] or {}).get("change_20d") or 0), reverse=True)
    return {"data": data[:top]}


@router.get("/regimes")
def regimes(session: Session = Depends(get_session)) -> dict:
    data = _all_latest(session, "regime")
    return {"data": [{"country": country, **item} for country, item in data.items()]}


@router.get("/attribution")
def attribution(
    symbol: str | None = Query(None),
    session: Session = Depends(get_session),
) -> dict:
    data = _all_latest(session, "attribution")
    if symbol:
        if symbol not in data:
            raise HTTPException(status_code=404, detail=f"no attribution for {symbol}")
        return {"data": [{"subject": symbol, **data[symbol]}]}
    return {"data": [{"subject": subject, **item} for subject, item in data.items()]}


@router.get("/correlation")
def correlation(session: Session = Depends(get_session)) -> dict:
    row = _latest(session, "correlation", "matrix")
    if row is None:
        return {"data": None}
    return {"data": {"asof": row.asof.isoformat(), **row.payload}}


@router.get("/analogs")
def analogs(session: Session = Depends(get_session)) -> dict:
    row = _latest(session, "analogs", "current")
    if row is None:
        return {"data": None}
    return {"data": {"asof": row.asof.isoformat(), **row.payload}}


@router.get("/wind")
def wind(session: Session = Depends(get_session)) -> dict:
    row = _latest(session, "wind", "market")
    if row is None:
        return {"data": None}
    return {"data": {"asof": row.asof.isoformat(), **row.payload}}


@router.get("/leadlag")
def leadlag(session: Session = Depends(get_session)) -> dict:
    row = _latest(session, "leadlag", "pairs")
    if row is None:
        return {"data": None}
    return {"data": {"asof": row.asof.isoformat(), **row.payload}}


@router.get("/events")
def events(session: Session = Depends(get_session)) -> dict:
    row = _latest(session, "event_study", "library")
    if row is None:
        return {"data": None}
    return {"data": {"asof": row.asof.isoformat(), **row.payload}}


@router.get("/calendar")
def calendar(session: Session = Depends(get_session)) -> dict:
    row = _latest(session, "calendar_study", "market")
    if row is None:
        return {"data": None}
    return {"data": {"asof": row.asof.isoformat(), **row.payload}}
