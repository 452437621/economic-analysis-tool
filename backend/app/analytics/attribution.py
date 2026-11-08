"""Return attribution: decompose an asset's recent move into driver contributions."""

from __future__ import annotations

import numpy as np
import pandas as pd


def decompose(
    asset_returns: pd.Series,
    drivers: pd.DataFrame,
    *,
    window: int = 120,
    contrib_days: int = 20,
) -> dict:
    frame = pd.concat([asset_returns.rename("asset"), drivers], axis=1).dropna().tail(window)
    if len(frame) < 40:
        return {}
    y = frame["asset"].to_numpy()
    columns = list(drivers.columns)
    x = np.column_stack([np.ones(len(frame)), frame[columns].to_numpy()])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    fitted = x @ beta
    ss_res = float(((y - fitted) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot else None

    recent = frame.tail(contrib_days)
    contributions = {
        column: float(beta[index + 1] * recent[column].sum())
        for index, column in enumerate(columns)
    }
    actual = float(recent["asset"].sum())
    return {
        "window": len(frame),
        "contrib_days": contrib_days,
        "betas": {column: round(float(beta[index + 1]), 4) for index, column in enumerate(columns)},
        "contributions_pct": {
            column: round(value * 100, 2) for column, value in contributions.items()
        },
        "actual_pct": round(actual * 100, 2),
        "residual_pct": round((actual - sum(contributions.values())) * 100, 2),
        "r2": round(r2, 3) if r2 is not None else None,
    }


def build_drivers(macro: pd.DataFrame) -> pd.DataFrame:
    drivers = pd.DataFrame(index=macro.index)
    if {"US10Y_REAL", "US10Y_BE", "US10Y", "US2Y"}.issubset(macro.columns):
        drivers["real_yield_chg"] = macro["US10Y_REAL"].diff()
        drivers["breakeven_chg"] = macro["US10Y_BE"].diff()
        drivers["curve_chg"] = (macro["US10Y"] - macro["US2Y"]).diff()
    return drivers
