"""Signal backtest: forward signed returns of each rule on daily bars."""

from __future__ import annotations

import pandas as pd

RULES = ("breakout", "momentum", "mean_reversion")


def _rule_series(series: pd.Series, rule: str, horizon: int) -> pd.Series:
    """Return signed forward returns where the rule triggers (index-aligned)."""
    clean = series.dropna()
    price = clean
    forward = price.shift(-horizon) / price - 1
    ma20 = price.rolling(20).mean()
    std20 = price.rolling(20).std()
    prior_high = price.shift(1).rolling(20).max()
    prior_low = price.shift(1).rolling(20).min()
    mom60 = price.pct_change(60)
    z = (price - ma20) / std20
    if rule == "breakout":
        long_mask = price > prior_high
        short_mask = price < prior_low
    elif rule == "momentum":
        long_mask = (mom60 > 0.05) & (price > ma20)
        short_mask = (mom60 < -0.05) & (price < ma20)
    elif rule == "mean_reversion":
        long_mask = z < -2
        short_mask = z > 2
    else:
        raise ValueError(f"unknown rule: {rule}")
    signed = pd.Series(index=price.index, dtype="float64")
    signed[long_mask] = forward[long_mask]
    signed[short_mask] = -forward[short_mask]
    return signed.dropna()


def backtest_rule(closes: pd.DataFrame, rule: str, horizon: int = 10) -> dict:
    returns: list[float] = []
    per_symbol = {}
    for symbol in closes.columns:
        signed = _rule_series(closes[symbol], rule, horizon)
        if len(signed) < 5:
            continue
        per_symbol[symbol] = round(float(signed.mean()) * 100, 2)
        returns.extend(signed.tolist())
    if not returns:
        return {"rule": rule, "horizon": horizon, "count": 0}
    series = pd.Series(returns)
    wins = series[series > 0]
    losses = series[series <= 0]
    return {
        "rule": rule,
        "horizon": horizon,
        "count": int(len(series)),
        "hit_rate": round(float((series > 0).mean()), 3),
        "avg_return_pct": round(float(series.mean()) * 100, 2),
        "median_return_pct": round(float(series.median()) * 100, 2),
        "avg_win_pct": round(float(wins.mean()) * 100, 2) if len(wins) else None,
        "avg_loss_pct": round(float(losses.mean()) * 100, 2) if len(losses) else None,
        "profit_factor": (
            round(float(wins.sum() / abs(losses.sum())), 2) if len(losses) and losses.sum() != 0 else None
        ),
        "by_symbol": per_symbol,
    }


def backtest_all(closes: pd.DataFrame, horizon: int = 10) -> dict[str, dict]:
    return {rule: backtest_rule(closes, rule, horizon) for rule in RULES}
