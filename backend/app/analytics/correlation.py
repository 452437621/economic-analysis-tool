"""Cross-asset correlation snapshot and strongest / changing pairs."""

from __future__ import annotations

import numpy as np
import pandas as pd


def correlation_snapshot(closes: pd.DataFrame, window: int = 120, top_n: int = 10) -> dict:
    returns = closes.pct_change().dropna(how="all")
    returns = returns.tail(window)
    valid = [column for column in returns.columns if returns[column].notna().sum() >= 60]
    if len(valid) < 3:
        return {}
    corr = returns[valid].corr()

    pairs = []
    for i, left in enumerate(valid):
        for right in valid[i + 1 :]:
            value = corr.loc[left, right]
            if pd.isna(value):
                continue
            pairs.append({"a": left, "b": right, "corr": round(float(value), 3)})
    pairs.sort(key=lambda item: abs(item["corr"]), reverse=True)

    matrix = [
        [round(float(value), 3) if not pd.isna(value) else None for value in corr.loc[left].tolist()]
        for left in valid
    ]
    return {
        "window": window,
        "symbols": valid,
        "matrix": matrix,
        "top_pairs": pairs[:top_n],
        "avg_abs_corr": round(float(np.nanmean(np.abs(corr.to_numpy()))), 3),
    }
