"""Rule-based signals (M4 v0): breakout, momentum, mean reversion.

Pure functions over daily close series; no look-ahead beyond the last bar.
"""

from __future__ import annotations

import pandas as pd

TRADEABLE_FUTURES = ["AU", "AG", "CU", "AL", "ZN", "NI", "SC", "M", "I", "SR", "CF", "P"]
EQUITY = ["603993"]


def atr_like(series: pd.Series, window: int = 14) -> pd.Series:
    """Close-to-close absolute move as a simple ATR proxy."""
    return series.diff().abs().rolling(window).mean()


def detect_signals(symbol: str, series: pd.Series) -> list[dict]:
    clean = series.dropna()
    if len(clean) < 80:
        return []
    price = float(clean.iloc[-1])
    ma20 = float(clean.rolling(20).mean().iloc[-1])
    ma60 = float(clean.rolling(60).mean().iloc[-1])
    atr = float(atr_like(clean).iloc[-1])
    if not atr or pd.isna(atr):
        atr = price * 0.01
    prior_high = float(clean.shift(1).rolling(20).max().iloc[-1])
    prior_low = float(clean.shift(1).rolling(20).min().iloc[-1])
    std20 = float(clean.rolling(20).std().iloc[-1])
    signals: list[dict] = []

    if price > prior_high:
        signals.append(
            {
                "symbol": symbol,
                "type": "breakout",
                "direction": "long",
                "price": price,
                "atr": atr,
                "strength": round(min(1.0, (price - prior_high) / atr), 3),
                "note": f"突破前 20 日高点 {prior_high:.4f}",
                "params": {"prior_high": round(prior_high, 4), "ma60": round(ma60, 4)},
            }
        )
    elif price < prior_low:
        signals.append(
            {
                "symbol": symbol,
                "type": "breakout",
                "direction": "short",
                "price": price,
                "atr": atr,
                "strength": round(min(1.0, (prior_low - price) / atr), 3),
                "note": f"跌破前 20 日低点 {prior_low:.4f}",
                "params": {"prior_low": round(prior_low, 4), "ma60": round(ma60, 4)},
            }
        )

    if len(clean) > 61:
        ret60 = price / float(clean.iloc[-61]) - 1
        if ret60 > 0.05 and price > ma20:
            signals.append(
                {
                    "symbol": symbol,
                    "type": "momentum",
                    "direction": "long",
                    "price": price,
                    "atr": atr,
                    "strength": round(min(1.0, ret60 / 0.15), 3),
                    "note": f"60 日动量 {ret60 * 100:.1f}%，价格在 MA20 上方",
                    "params": {"ret60": round(ret60, 4), "ma20": round(ma20, 4)},
                }
            )
        elif ret60 < -0.05 and price < ma20:
            signals.append(
                {
                    "symbol": symbol,
                    "type": "momentum",
                    "direction": "short",
                    "price": price,
                    "atr": atr,
                    "strength": round(min(1.0, abs(ret60) / 0.15), 3),
                    "note": f"60 日动量 {ret60 * 100:.1f}%，价格在 MA20 下方",
                    "params": {"ret60": round(ret60, 4), "ma20": round(ma20, 4)},
                }
            )

    if std20 and not pd.isna(std20):
        z = (price - ma20) / std20
        if z > 2:
            signals.append(
                {
                    "symbol": symbol,
                    "type": "mean_reversion",
                    "direction": "short",
                    "price": price,
                    "atr": atr,
                    "strength": round(min(1.0, (z - 2) / 2 + 0.3), 3),
                    "note": f"偏离 MA20 {z:.1f}σ，均值回归偏空",
                    "params": {"z": round(float(z), 2)},
                }
            )
        elif z < -2:
            signals.append(
                {
                    "symbol": symbol,
                    "type": "mean_reversion",
                    "direction": "long",
                    "price": price,
                    "atr": atr,
                    "strength": round(min(1.0, (-z - 2) / 2 + 0.3), 3),
                    "note": f"偏离 MA20 {z:.1f}σ，均值回归偏多",
                    "params": {"z": round(float(z), 2)},
                }
            )
    return signals


def generate_all(closes: pd.DataFrame) -> list[dict]:
    signals: list[dict] = []
    for symbol in TRADEABLE_FUTURES + EQUITY:
        if symbol not in closes.columns:
            continue
        signals.extend(detect_signals(symbol, closes[symbol]))
    signals.sort(key=lambda item: item["strength"], reverse=True)
    return signals
