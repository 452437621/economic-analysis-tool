"""Signal backtest with costs and a simple walk-forward split."""

from __future__ import annotations

import pandas as pd

RULES = ("breakout", "momentum", "mean_reversion")
TRAIN_END = pd.Timestamp("2024-01-01")
DEFAULT_COST_PCT = 0.06  # round-trip commission + slippage, in percent


def _rule_series(series: pd.Series, rule: str, horizon: int) -> pd.Series:
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


def _stats(returns: pd.Series, cost_pct: float) -> dict:
    if len(returns) == 0:
        return {"count": 0}
    net = returns - cost_pct / 100.0
    wins = net[net > 0]
    losses = net[net <= 0]
    return {
        "count": int(len(net)),
        "hit_rate": round(float((net > 0).mean()), 3),
        "avg_return_pct": round(float(net.mean()) * 100, 2),
        "median_return_pct": round(float(net.median()) * 100, 2),
        "avg_win_pct": round(float(wins.mean()) * 100, 2) if len(wins) else None,
        "avg_loss_pct": round(float(losses.mean()) * 100, 2) if len(losses) else None,
        "profit_factor": (
            round(float(wins.sum() / abs(losses.sum())), 2)
            if len(losses) and losses.sum() != 0
            else None
        ),
    }


def backtest_rule(
    closes: pd.DataFrame,
    rule: str,
    horizon: int = 10,
    cost_pct: float = DEFAULT_COST_PCT,
) -> dict:
    returns: list[pd.Series] = []
    per_symbol = {}
    for symbol in closes.columns:
        signed = _rule_series(closes[symbol], rule, horizon)
        if len(signed) < 5:
            continue
        returns.append(signed)
        per_symbol[symbol] = round(float((signed - cost_pct / 100).mean()) * 100, 2)
    if not returns:
        return {"rule": rule, "horizon": horizon, "count": 0, "cost_pct": cost_pct}
    combined = pd.concat(returns)
    train = combined[combined.index < TRAIN_END]
    test = combined[combined.index >= TRAIN_END]
    payload = {
        "rule": rule,
        "horizon": horizon,
        "cost_pct": cost_pct,
        "by_symbol": per_symbol,
        **_stats(combined, cost_pct),
        "walk_forward": {
            "train": _stats(train, cost_pct),
            "test": _stats(test, cost_pct),
            "split": TRAIN_END.strftime("%Y-%m-%d"),
        },
    }
    return payload


def backtest_all(closes: pd.DataFrame, horizon: int = 10) -> dict[str, dict]:
    return {rule: backtest_rule(closes, rule, horizon) for rule in RULES}
