"""Thesis lifecycle review: direction hit rate and age of active theses."""

from __future__ import annotations

from sqlalchemy import select

from app.models.core import Instrument, MarketBar, Thesis
from app.platform.db import SessionLocal


def summarize(records: list[dict]) -> dict:
    scored = [record for record in records if record.get("return_pct") is not None]
    if not scored:
        return {"count": len(records), "scored": 0, "hit_rate": None, "avg_return_pct": None, "records": records}
    hits = sum(1 for record in scored if record["hit"])
    return {
        "count": len(records),
        "scored": len(scored),
        "hit_rate": round(hits / len(scored), 3),
        "avg_return_pct": round(sum(record["return_pct"] for record in scored) / len(scored), 2),
        "records": records,
    }


def review_theses() -> dict:
    records: list[dict] = []
    with SessionLocal() as session:
        theses = session.scalars(select(Thesis).order_by(Thesis.created_at.desc())).all()
        instruments = {row.id: row for row in session.scalars(select(Instrument)).all()}
        for thesis in theses:
            instrument_id = (thesis.asset_ids or [None])[0]
            instrument = instruments.get(instrument_id) if instrument_id else None
            if instrument is None:
                continue
            first = session.scalar(
                select(MarketBar)
                .where(
                    MarketBar.instrument_id == instrument.id,
                    MarketBar.timeframe == "1d",
                    MarketBar.ts_utc >= thesis.created_at.replace(tzinfo=None),
                )
                .order_by(MarketBar.ts_utc.asc())
                .limit(1)
            )
            latest = session.scalar(
                select(MarketBar)
                .where(MarketBar.instrument_id == instrument.id, MarketBar.timeframe == "1d")
                .order_by(MarketBar.ts_utc.desc())
                .limit(1)
            )
            return_pct = None
            hit = None
            if first and latest and first.close:
                raw = (latest.close / first.close - 1) * 100
                signed = raw if thesis.direction == "long" else -raw
                return_pct = round(signed, 2)
                hit = signed > 0
            records.append(
                {
                    "id": thesis.id,
                    "symbol": instrument.symbol,
                    "title": thesis.title,
                    "direction": thesis.direction,
                    "status": thesis.status,
                    "return_pct": return_pct,
                    "hit": hit,
                    "since": thesis.created_at.date().isoformat(),
                }
            )
    return summarize(records)
