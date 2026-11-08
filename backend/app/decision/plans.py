"""Trade plan construction and risk checks (M4 v0)."""

from __future__ import annotations

from app.platform.config import settings


def size_position(
    equity: float,
    risk_pct: float,
    price: float,
    stop_price: float,
    contract_multiplier: float = 1.0,
) -> float:
    risk_amount = equity * risk_pct / 100.0
    per_unit = abs(price - stop_price) * contract_multiplier
    if per_unit <= 0:
        return 0.0
    return round(risk_amount / per_unit, 4)


def build_plan(signal: dict, equity: float | None = None, risk_pct: float | None = None) -> dict:
    equity = settings.account_equity if equity is None else equity
    risk_pct = settings.risk_per_trade_pct if risk_pct is None else risk_pct
    direction = 1 if signal["direction"] == "long" else -1
    price = float(signal["price"])
    atr = float(signal["atr"])
    stop = price - direction * 1.5 * atr
    target1 = price + direction * 2.0 * atr
    target2 = price + direction * 3.0 * atr
    size = size_position(equity, risk_pct, price, stop)
    stop_distance_pct = abs(price - stop) / price * 100

    checks = [
        {
            "rule": "单笔风险 ≤ 0.3%",
            "passed": risk_pct <= 0.3,
            "detail": f"risk_pct={risk_pct:.2f}%",
        },
        {
            "rule": "止损距离 ≤ 5%",
            "passed": stop_distance_pct <= 5.0,
            "detail": f"stop_distance={stop_distance_pct:.2f}%",
        },
        {
            "rule": "仓位 > 0",
            "passed": size > 0,
            "detail": f"size={size}",
        },
    ]

    return {
        "symbol": signal["symbol"],
        "side": signal["direction"],
        "entry_low": round(price * (1 - 0.003), 4),
        "entry_high": round(price * (1 + 0.003), 4),
        "stop": round(stop, 4),
        "targets": {"T1": round(target1, 4), "T2": round(target2, 4)},
        "size": size,
        "risk_pct": risk_pct,
        "time_stop_days": 3,
        "invalidation": (
            f"跌破 {stop:.4f} 止损；或入场后第 3 个交易日收盘未脱离成本区；"
            f"或信号逻辑被证伪（{signal['type']}）"
        ),
        "checks": checks,
        "signal": signal,
        "equity": equity,
    }
