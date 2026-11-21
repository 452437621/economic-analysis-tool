"""Historical analog matching on a weekly macro/market state vector."""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_ASSETS = {
    "AU": "gold_mom",
    "CU": "copper_mom",
    "SC": "oil_mom",
    "000300": "equity_mom",
}


def build_state(closes: pd.DataFrame, macro: pd.DataFrame, max_weeks: int = 320) -> pd.DataFrame:
    weekly_closes = closes.resample("W-FRI").last()
    weekly_macro = macro.resample("W-FRI").last().reindex(weekly_closes.index).ffill()
    state = pd.DataFrame(index=weekly_closes.index)
    for code in ("US10Y", "US10Y_REAL", "US10Y_BE"):
        if code in weekly_macro.columns:
            state[code] = weekly_macro[code]
    if {"US10Y", "US2Y"}.issubset(weekly_macro.columns):
        state["slope"] = weekly_macro["US10Y"] - weekly_macro["US2Y"]
    momentum = weekly_closes.pct_change(4)
    for symbol, feature in FEATURE_ASSETS.items():
        if symbol in momentum.columns:
            state[feature] = momentum[symbol]
    return state.dropna().tail(max_weeks)


def find_asset_analogs(
    state: pd.DataFrame,
    closes: pd.DataFrame,
    *,
    top_n: int = 5,
    min_gap_days: int = 180,
) -> dict:
    """Weekly asset-state nearest-neighbour analogs (see ``cycle.analogs`` for monthly)."""
    if len(state) < 40:
        return {}
    z = (state - state.mean()) / state.std(ddof=0).replace(0, np.nan)
    z = z.dropna()
    if z.empty:
        return {}
    current = z.iloc[-1]
    cutoff = state.index[-1] - pd.Timedelta(days=min_gap_days)
    history = z[z.index <= cutoff]
    if history.empty:
        return {}
    distance = np.sqrt(((history - current) ** 2).mean(axis=1))
    picks = distance.nsmallest(top_n)

    weekly = closes.resample("W-FRI").last()
    matches = []
    for date, dist in picks.items():
        item = {"date": date.strftime("%Y-%m-%d"), "distance": round(float(dist), 3), "forward": {}}
        for asset in FEATURE_ASSETS:
            if asset not in weekly.columns or date not in weekly.index:
                continue
            series = weekly[asset]
            index = series.index.get_loc(date)
            for label, weeks in (("20d", 4), ("60d", 12)):
                if index + weeks < len(series) and series.iloc[index]:
                    item["forward"][f"{asset}_{label}"] = round(
                        float(series.iloc[index + weeks] / series.iloc[index] - 1) * 100, 2
                    )
        matches.append(item)
    return {
        "current_date": state.index[-1].strftime("%Y-%m-%d"),
        "features": list(state.columns),
        "matches": matches,
        "note": "历史类比仅作参照：样本有限，结构性变化可能使其失效。",
    }


# Backwards-compatible name (the cycle engine has a different analog API).
find_analogs = find_asset_analogs

__all__ = ["FEATURE_ASSETS", "build_state", "find_asset_analogs", "find_analogs"]
