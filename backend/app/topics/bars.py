"""System daily-bar access for topic fallbacks.

The daily-bar collector keeps real OHLC and volume in ``market_bars``.  Topic
fallbacks used to read only the close column and duplicate it into open/high/
low, which renders as flat candles with no body or shadows.  This helper keeps
the fallback faithful to the source data.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Instrument, MarketBar


def load_bar_rows(session: Session, symbol: str) -> list[dict[str, Any]]:
    """Return 1d bars as ``{as_of, payload}`` rows ordered by date (ascending)."""
    rows = session.execute(
        select(
            MarketBar.ts_utc,
            MarketBar.open,
            MarketBar.high,
            MarketBar.low,
            MarketBar.close,
            MarketBar.volume,
        )
        .join(Instrument, Instrument.id == MarketBar.instrument_id)
        .where(Instrument.symbol == symbol, MarketBar.timeframe == "1d")
        .order_by(MarketBar.ts_utc)
    ).all()
    out: list[dict[str, Any]] = []
    for ts, open_, high, low, close, volume in rows:
        if open_ is None or high is None or low is None or close is None:
            continue
        out.append(
            {
                "as_of": ts.date(),
                "payload": {
                    "open": float(open_),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    # System bars are forward-adjusted; there is no raw close.
                    "close_raw": float(close),
                    "volume": float(volume) if volume is not None else None,
                },
            }
        )
    return out


def load_bar_frame(session: Session, symbol: str):
    """Same data as ``load_bar_rows`` but as a date-indexed DataFrame."""
    import pandas as pd

    rows = load_bar_rows(session, symbol)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame([{"as_of": item["as_of"], **item["payload"]} for item in rows])
    frame["as_of"] = pd.to_datetime(frame["as_of"], errors="coerce")
    frame = frame.dropna(subset=["as_of"]).set_index("as_of").sort_index()
    frame["pct_chg"] = frame["close"].pct_change() * 100
    return frame
