"""Shared API serializers.

Keeps snapshot / watchlist / macro / brief payloads identical across single
purpose endpoints and the composite ``/api/overview`` endpoint, and resolves
instrument display units in one place.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import (
    AnalyticsResult,
    Brief,
    Instrument,
    MacroObs,
    MacroSeries,
    MarketBar,
    Quote,
    WatchItem,
)
from app.platform.instrument_units import resolve_unit

ASSET_ORDER = ["metal", "energy", "black", "agri", "fx", "equity", "rate"]

#: 日报分组（历史 kind：手动/盘前/盘后）
DAILY_KINDS: tuple[str, ...] = ("manual", "premarket", "postmarket")
KIND_GROUPS: dict[str, tuple[str, ...]] = {
    "daily": DAILY_KINDS,
    "weekly": ("weekly",),
    "monthly": ("monthly",),
}


def iso(value: datetime | None) -> str | None:
    """Serialize DB datetimes as UTC ISO strings (SQLite returns naive values)."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def latest_quotes(session: Session) -> tuple[list[Instrument], dict[str, Quote]]:
    instruments = session.scalars(
        select(Instrument).where(Instrument.active.is_(True)).order_by(Instrument.symbol)
    ).all()
    rows = session.scalars(select(Quote).order_by(Quote.ts_utc.desc()).limit(3000)).all()
    latest: dict[str, Quote] = {}
    for row in rows:
        latest.setdefault(row.instrument_id, row)
    return instruments, latest


def snapshot_payload(
    session: Session,
    instruments: list[Instrument] | None = None,
    latest: dict[str, Quote] | None = None,
) -> dict:
    """Active instruments + latest quote, ordered by asset class (with display unit)."""
    if instruments is None or latest is None:
        instruments, latest = latest_quotes(session)
    now = datetime.now(timezone.utc)
    data = []
    for instrument in instruments:
        quote = latest.get(instrument.id)
        item = {
            "symbol": instrument.symbol,
            "name": instrument.name,
            "asset_class": instrument.asset_class,
            "exchange": instrument.exchange,
            "currency": instrument.currency,
            "unit": resolve_unit(instrument.symbol, instrument.extra),
            "contract_size": instrument.contract_size,
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
                    "ts": iso(ts),
                    "stale_sec": max(0, int((now - ts).total_seconds())),
                    "delay_sec": quote.delay_sec,
                    "source": quote.source_id and _source_name(session, quote.source_id),
                }
            )
        data.append(item)
    data.sort(
        key=lambda row: (
            ASSET_ORDER.index(row["asset_class"]) if row["asset_class"] in ASSET_ORDER else 99,
            row["symbol"],
        )
    )
    asof = max((row["ts"] for row in data if row.get("ts")), default=None)
    return {
        "data": data,
        "meta": {
            "asof": asof,
            "count": len(data),
            "with_quote": sum(1 for row in data if row.get("price") is not None),
        },
    }


def _source_name(session: Session, source_id: str) -> str | None:
    from app.models.core import Source  # local import keeps serializer import light

    source = session.get(Source, source_id)
    return source.name if source else None


def spark_batch(session: Session, instrument_ids: list[str], limit: int = 30) -> dict[str, list[float]]:
    """最近的日线收盘价（单条窗口函数查询，按标的批量返回）。"""
    if not instrument_ids:
        return {}
    ranked = (
        select(
            MarketBar.instrument_id,
            MarketBar.close,
            MarketBar.ts_utc,
            func.row_number()
            .over(partition_by=MarketBar.instrument_id, order_by=MarketBar.ts_utc.desc())
            .label("rn"),
        )
        .where(
            MarketBar.instrument_id.in_(instrument_ids),
            MarketBar.timeframe == "1d",
            MarketBar.close.is_not(None),
        )
        .subquery()
    )
    rows = session.execute(
        select(ranked.c.instrument_id, ranked.c.close, ranked.c.ts_utc)
        .where(ranked.c.rn <= limit)
        .order_by(ranked.c.instrument_id, ranked.c.ts_utc.asc())
    ).all()
    result: dict[str, list[float]] = {}
    for instrument_id, close, _ts in rows:
        result.setdefault(instrument_id, []).append(float(close))
    return result


def watchlist_payload(
    session: Session,
    with_spark: bool = False,
    latest: dict[str, Quote] | None = None,
) -> dict:
    items = session.execute(
        select(WatchItem, Instrument)
        .join(Instrument, Instrument.id == WatchItem.instrument_id)
        .order_by(
            WatchItem.sort_order.asc(),
            WatchItem.priority.asc(),
            Instrument.symbol.asc(),
        )
    ).all()
    if latest is None:
        _, latest = latest_quotes(session)
    indicators: dict[str, dict] = {}
    for row in session.scalars(
        select(AnalyticsResult).where(AnalyticsResult.kind == "indicator")
    ).all():
        payload = row.payload or {}
        indicators[row.subject] = {
            "change_20d": payload.get("change_20d"),
            "trend": payload.get("trend"),
        }
    sparks = (
        spark_batch(session, [instrument.id for _, instrument in items])
        if with_spark
        else {}
    )
    data = []
    for item, instrument in items:
        quote = latest.get(instrument.id)
        row = {
            "symbol": instrument.symbol,
            "name": instrument.name,
            "asset_class": instrument.asset_class,
            "unit": resolve_unit(instrument.symbol, instrument.extra),
            "group": item.group,
            "priority": item.priority,
            "sort_order": item.sort_order,
            "note": item.note,
            "price": quote.price if quote else None,
            "change_pct": quote.change_pct if quote else None,
            "quote_ts": iso(quote.ts_utc) if quote else None,
            "change_20d": indicators.get(instrument.symbol, {}).get("change_20d"),
            "trend": indicators.get(instrument.symbol, {}).get("trend"),
        }
        if with_spark:
            row["spark"] = sparks.get(instrument.id, [])
        data.append(row)
    return {"data": data}


def macro_latest_rows(session: Session) -> list[dict]:
    series_list = session.scalars(select(MacroSeries).order_by(MacroSeries.code)).all()
    ranked = (
        select(
            MacroObs.series_id,
            MacroObs.value,
            MacroObs.ts_utc,
            func.row_number()
            .over(partition_by=MacroObs.series_id, order_by=MacroObs.ts_utc.desc())
            .label("rn"),
        )
        .subquery()
    )
    rows = session.execute(
        select(ranked.c.series_id, ranked.c.value, ranked.c.ts_utc).where(ranked.c.rn == 1)
    ).all()
    latest = {series_id: (value, ts) for series_id, value, ts in rows}
    data = []
    for series in series_list:
        hit = latest.get(series.id)
        if hit is None:
            continue
        value, ts = hit
        data.append(
            {
                "code": series.code,
                "name": series.name,
                "unit": series.unit,
                "value": value,
                "ts": iso(ts),
            }
        )
    return data


def macro_sparks(session: Session, codes: list[str], limit: int = 45) -> dict[str, list[float]]:
    if not codes:
        return {}
    series = {
        row.code: row.id
        for row in session.scalars(select(MacroSeries).where(MacroSeries.code.in_(codes))).all()
    }
    if not series:
        return {}
    id_to_code = {series_id: code for code, series_id in series.items()}
    ranked = (
        select(
            MacroObs.series_id,
            MacroObs.value,
            MacroObs.ts_utc,
            func.row_number()
            .over(partition_by=MacroObs.series_id, order_by=MacroObs.ts_utc.desc())
            .label("rn"),
        )
        .where(MacroObs.series_id.in_(list(series.values())))
        .subquery()
    )
    rows = session.execute(
        select(ranked.c.series_id, ranked.c.value, ranked.c.ts_utc)
        .where(ranked.c.rn <= limit)
        .order_by(ranked.c.series_id, ranked.c.ts_utc.asc())
    ).all()
    result: dict[str, list[float]] = {}
    for series_id, value, _ts in rows:
        code = id_to_code.get(series_id)
        if code is None or value is None:
            continue
        result.setdefault(code, []).append(float(value))
    return result


def brief_payload(brief: Brief) -> dict:
    return {
        "id": brief.id,
        "kind": brief.kind,
        "trade_date": brief.trade_date.isoformat(),
        "created_at": iso(brief.created_at),
        "markdown": brief.markdown,
        "meta": brief.meta,
    }


def brief_summary(brief: Brief) -> dict:
    return {
        "id": brief.id,
        "kind": brief.kind,
        "trade_date": brief.trade_date.isoformat(),
        "created_at": iso(brief.created_at),
        "chars": len(brief.markdown or ""),
    }


def kind_filter(kind: str | None) -> tuple[str, ...] | None:
    """Map ``daily`` / ``weekly`` / ``monthly`` groups to concrete brief kinds."""
    if not kind:
        return None
    if kind in KIND_GROUPS:
        return KIND_GROUPS[kind]
    return (kind,)
