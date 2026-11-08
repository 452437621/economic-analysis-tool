"""Market data frames for analytics: daily closes + macro series from SQLite."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Instrument, MacroSeries, MacroObs, MarketBar
from app.platform.db import SessionLocal

WATCHLIST = [
    "AU", "AG", "CU", "AL", "ZN", "NI", "SC", "M", "I", "SR", "CF", "P",
    "000300", "603993",
]


@dataclass
class MarketFrames:
    closes: pd.DataFrame
    macro: pd.DataFrame
    open_interest: pd.DataFrame


def _series_frame(rows: list[tuple[str, object, float]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows, columns=["key", "ts", "value"])
    frame["date"] = pd.to_datetime(frame["ts"], utc=True).dt.tz_convert(None).dt.normalize()
    frame = frame.drop_duplicates(subset=["key", "date"], keep="last")
    return frame.pivot(index="date", columns="key", values="value").sort_index()


def load_frames(session: Session | None = None) -> MarketFrames:
    own_session = session is None
    session = session or SessionLocal()
    try:
        symbols = {
            row.id: row.symbol
            for row in session.scalars(select(Instrument).where(Instrument.active.is_(True))).all()
        }
        bars = session.execute(
            select(
                MarketBar.instrument_id,
                MarketBar.ts_utc,
                MarketBar.close,
                MarketBar.open_interest,
            ).where(MarketBar.timeframe == "1d")
        ).all()
        closes_rows = [
            (symbols[instrument_id], ts, close)
            for instrument_id, ts, close, _ in bars
            if instrument_id in symbols
        ]
        oi_rows = [
            (symbols[instrument_id], ts, oi)
            for instrument_id, ts, _, oi in bars
            if instrument_id in symbols and oi is not None
        ]
        macro_rows = session.execute(
            select(MacroSeries.code, MacroObs.ts_utc, MacroObs.value).join(
                MacroObs, MacroObs.series_id == MacroSeries.id
            )
        ).all()

        return MarketFrames(
            closes=_series_frame(closes_rows),
            macro=_series_frame(macro_rows),
            open_interest=_series_frame(oi_rows),
        )
    finally:
        if own_session:
            session.close()


def aligned(frames: MarketFrames, symbols: list[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (asset closes, macro) on a common trading calendar.

    Forex/global indices can carry weekend or next-day bars while domestic
    futures are still closed; rows where fewer than half of the assets have
    data are dropped so indicators/wind do not read stale or NaN rows.
    """
    closes = frames.closes if symbols is None else frames.closes[[s for s in symbols if s in frames.closes]]
    closes = closes.copy()
    if len(closes) and len(closes.columns):
        required = max(1, int(len(closes.columns) * 0.5))
        keep = closes.notna().sum(axis=1) >= required
        closes = closes[keep]
    macro = frames.macro.reindex(closes.index, method="ffill", limit=7)
    return closes, macro
