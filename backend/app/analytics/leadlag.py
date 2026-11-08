"""Lead-lag cross-correlation between assets (daily returns)."""

from __future__ import annotations

import pandas as pd


def leadlag_pairs(
    closes: pd.DataFrame,
    *,
    max_lag: int = 5,
    min_obs: int = 120,
    top_n: int = 12,
) -> dict:
    returns = closes.pct_change().dropna(how="all")
    symbols = [column for column in returns.columns if returns[column].notna().sum() >= min_obs]
    pairs = []
    for index, left in enumerate(symbols):
        for right in symbols[index + 1 :]:
            base = returns[left].corr(returns[right])
            if pd.isna(base):
                continue
            best_corr = float(base)
            best_lag = 0
            for lag in range(1, max_lag + 1):
                left_lead = returns[left].corr(returns[right].shift(-lag))
                right_lead = returns[right].corr(returns[left].shift(-lag))
                if left_lead is not None and not pd.isna(left_lead) and abs(left_lead) > abs(best_corr):
                    best_corr, best_lag = float(left_lead), lag
                if right_lead is not None and not pd.isna(right_lead) and abs(right_lead) > abs(best_corr):
                    best_corr, best_lag = float(right_lead), -lag
            pairs.append(
                {
                    "a": left,
                    "b": right,
                    "same_day_corr": round(float(base), 3),
                    "best_corr": round(best_corr, 3),
                    "lag_days": best_lag,
                    "interpretation": (
                        f"{left} 领先 {right} {best_lag} 天"
                        if best_lag > 0
                        else f"{right} 领先 {left} {-best_lag} 天"
                        if best_lag < 0
                        else "同步"
                    ),
                }
            )
    pairs.sort(key=lambda item: abs(item["best_corr"]), reverse=True)
    return {
        "max_lag": max_lag,
        "pairs": pairs[:top_n],
        "note": "领先滞后基于历史相关，不等于因果；样本有限时不稳定。",
    }
