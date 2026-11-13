"""Price-based indicators for one daily series."""

from __future__ import annotations

import math

import pandas as pd


def _pct(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods:
        return None
    return float(series.iloc[-1] / series.iloc[-1 - periods] - 1.0) * 100


def compute_indicators(
    symbol: str, series: pd.Series, oi: pd.Series | None = None
) -> dict:
    clean = series.dropna()
    if len(clean) < 30:
        return {}
    close = float(clean.iloc[-1])
    ret = clean.pct_change().dropna()

    def ma(period: int) -> float | None:
        return float(clean.rolling(period).mean().iloc[-1]) if len(clean) >= period else None

    ma20, ma60, ma200 = ma(20), ma(60), ma(200)
    vol20 = float(ret.tail(20).std() * math.sqrt(252) * 100) if len(ret) >= 20 else None
    window252 = clean.tail(252)
    percentile = float((window252 <= close).mean() * 100) if len(window252) >= 60 else None

    trend = "mixed"
    if ma20 and ma60:
        if close > ma20 > ma60:
            trend = "up"
        elif close < ma20 < ma60:
            trend = "down"

    oi_change_5d = None
    if oi is not None and len(oi.dropna()) > 5:
        clean_oi = oi.dropna()
        oi_change_5d = float(clean_oi.iloc[-1] / clean_oi.iloc[-6] - 1.0) * 100

    return {
        "symbol": symbol,
        "close": round(close, 4),
        "change_1d": round(_pct(clean, 1) or 0.0, 2),
        "change_5d": round(_pct(clean, 5) or 0.0, 2),
        "change_20d": round(_pct(clean, 20) or 0.0, 2),
        "change_60d": round(_pct(clean, 60) or 0.0, 2),
        "ma20": round(ma20, 4) if ma20 else None,
        "ma60": round(ma60, 4) if ma60 else None,
        "dist_ma20_pct": round((close / ma20 - 1) * 100, 2) if ma20 else None,
        "dist_ma60_pct": round((close / ma60 - 1) * 100, 2) if ma60 else None,
        "vol20_annual_pct": round(vol20, 2) if vol20 is not None else None,
        "percentile_252": round(percentile, 1) if percentile is not None else None,
        "trend": trend,
        "oi_change_5d": round(oi_change_5d, 2) if oi_change_5d is not None else None,
        "asof": clean.index[-1].strftime("%Y-%m-%d"),
    }
