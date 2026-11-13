"""Market-implied cycle regimes (US / China) from available series.

Caveat: official growth/inflation data is not yet integrated (BLS 403), so the
scores are market-implied proxies. They are deliberately labelled as such.
"""

from __future__ import annotations

import math

import pandas as pd


def _z_last(series: pd.Series, window: int = 250) -> float:
    clean = series.dropna()
    if len(clean) < 30:
        return 0.0
    window = min(window, len(clean))
    mean = float(clean.tail(window).mean())
    std = float(clean.tail(window).std())
    if std == 0 or math.isnan(std):
        return 0.0
    return float((clean.iloc[-1] - mean) / std)


def _score(z: float) -> float:
    return round(50 + 50 * math.tanh(z / 1.5), 1)


def classify_quadrant(growth: float, inflation: float) -> str:
    if growth >= 0.15 and inflation >= 0.15:
        return "过热"
    if growth >= 0.15 and inflation <= -0.15:
        return "复苏"
    if growth <= -0.15 and inflation >= 0.15:
        return "滞胀"
    if growth <= -0.15 and inflation <= -0.15:
        return "衰退"
    return "过渡"


def _mom(series: pd.Series, periods: int) -> pd.Series:
    return series.pct_change(periods)


def compute_regimes(closes: pd.DataFrame, macro: pd.DataFrame) -> dict[str, dict]:
    if closes.empty or macro.empty:
        return {}

    result: dict[str, dict] = {}

    # US: curve slope + copper/gold + breakevens + oil momentum
    us_growth = 0.0
    us_inflation = 0.0
    if {"US10Y", "US2Y"}.issubset(macro.columns):
        slope = macro["US10Y"] - macro["US2Y"]
        us_growth += 0.6 * _z_last(slope)
    if {"CU", "AU"}.issubset(closes.columns):
        copper_gold = closes["CU"] / closes["AU"]
        us_growth += 0.4 * _z_last(_mom(copper_gold, 60))
    if "US10Y_BE" in macro.columns:
        us_inflation += 0.6 * _z_last(macro["US10Y_BE"])
    if "SC" in closes.columns:
        us_inflation += 0.4 * _z_last(_mom(closes["SC"], 60))
    liquidity = 0.0
    if "US10Y_REAL" in macro.columns:
        liquidity -= _z_last(macro["US10Y_REAL"])
    result["US"] = {
        "country": "US",
        "growth_score": _score(us_growth),
        "inflation_score": _score(us_inflation),
        "liquidity_score": _score(liquidity),
        "growth_z": round(us_growth, 3),
        "inflation_z": round(us_inflation, 3),
        "quadrant": classify_quadrant(us_growth, us_inflation),
        "confidence": 0.4,
        "method": "市场隐含（收益率曲线、铜金比、盈亏平衡、油价、实际利率）",
    }

    # China: industrial metals + iron ore + A-share; oil/agri for inflation
    cn_growth = 0.0
    weights = {"CU": 0.4, "I": 0.3, "000300": 0.3}
    for symbol, weight in weights.items():
        if symbol in closes.columns:
            cn_growth += weight * _z_last(_mom(closes[symbol], 60))
    cn_inflation = 0.0
    inflation_weights = {"SC": 0.5, "M": 0.3, "P": 0.2}
    for symbol, weight in inflation_weights.items():
        if symbol in closes.columns:
            cn_inflation += weight * _z_last(_mom(closes[symbol], 60))
    cn_liquidity = 0.0
    if "000300" in closes.columns:
        cn_liquidity += _z_last(_mom(closes["000300"], 20))
    result["CN"] = {
        "country": "CN",
        "growth_score": _score(cn_growth),
        "inflation_score": _score(cn_inflation),
        "liquidity_score": _score(cn_liquidity),
        "growth_z": round(cn_growth, 3),
        "inflation_z": round(cn_inflation, 3),
        "quadrant": classify_quadrant(cn_growth, cn_inflation),
        "confidence": 0.35,
        "method": "市场隐含（铜/铁矿/股指动量、油/豆粕/棕油、股指流动性代理）",
    }
    return result
