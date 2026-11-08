"""Market wind: a simple risk-on / risk-off composite from price behaviour."""

from __future__ import annotations

import math

import pandas as pd

RISK_ASSETS = ["CU", "AL", "ZN", "NI", "SC", "000300", "603993"]


def compute_wind(closes: pd.DataFrame, macro: pd.DataFrame) -> dict:
    if closes.empty:
        return {}
    latest = closes.iloc[-1]
    ma60 = closes.rolling(60).mean().iloc[-1]
    available = [
        symbol
        for symbol in RISK_ASSETS
        if symbol in closes.columns and pd.notna(ma60.get(symbol)) and pd.notna(latest.get(symbol))
    ]
    breadth = float((latest[available] > ma60[available]).mean()) if available else 0.5
    momentum_20d = float(closes[available].pct_change(20).iloc[-1].mean()) if available else 0.0
    momentum_component = math.tanh(momentum_20d / 0.05) if available else 0.0

    rate_change = None
    rate_component = 0.0
    if "US10Y" in macro.columns:
        diff = macro["US10Y"].diff(20).iloc[-1]
        if pd.notna(diff):
            rate_change = float(diff)
            rate_component = math.tanh(-float(diff) / 0.5)

    score = 100 * (0.4 * (2 * breadth - 1) + 0.35 * momentum_component + 0.25 * rate_component)
    score = round(max(-100.0, min(100.0, score)), 1)
    if score >= 25:
        label = "进攻"
    elif score <= -25:
        label = "避险"
    else:
        label = "中性"

    return {
        "score": score,
        "label": label,
        "components": {
            "breadth_above_ma60": round(breadth, 3),
            "momentum_20d_avg_pct": round(momentum_20d * 100, 2),
            "us10y_change_20d_pp": round(rate_change, 3) if rate_change is not None else None,
            "risk_assets": available,
        },
        "asof": closes.index[-1].strftime("%Y-%m-%d"),
    }
