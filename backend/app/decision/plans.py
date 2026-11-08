"""Trade plan construction and risk checks (M4 v0.1: contract specs + lots)."""

from __future__ import annotations

import math

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


def size_lots(
    equity: float,
    risk_pct: float,
    price: float,
    stop_price: float,
    contract_size: float,
) -> float:
    """Raw lot count (may be fractional) from risk budget and stop distance."""
    return size_position(equity, risk_pct, price, stop_price, contract_size)


def build_plan(
    signal: dict,
    spec: dict | None = None,
    equity: float | None = None,
    risk_pct: float | None = None,
) -> dict:
    equity = settings.account_equity if equity is None else equity
    risk_pct = settings.risk_per_trade_pct if risk_pct is None else risk_pct
    spec = spec or {}
    contract_size = float(spec.get("contract_size") or 1)
    margin_pct = float(spec.get("margin_pct") or 1.0)
    fee_per_lot = float(spec.get("fee_per_lot") or 0)
    commission_rate = float(spec.get("commission_rate") or 0)

    direction = 1 if signal["direction"] == "long" else -1
    price = float(signal["price"])
    atr = float(signal["atr"])
    stop = price - direction * 1.5 * atr
    target1 = price + direction * 2.0 * atr
    target2 = price + direction * 3.0 * atr

    raw_lots = size_lots(equity, risk_pct, price, stop, contract_size)
    lots = int(math.floor(raw_lots))
    notional = lots * contract_size * price
    margin = notional * margin_pct
    fee = lots * fee_per_lot + notional * commission_rate
    risk_amount = equity * risk_pct / 100.0
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
            "rule": "手数 ≥ 1",
            "passed": lots >= 1,
            "detail": f"raw_lots={raw_lots}, lots={lots}, contract_size={contract_size}",
        },
        {
            "rule": "保证金占用 ≤ 50% 权益",
            "passed": margin <= equity * 0.5,
            "detail": f"margin={margin:.0f} / equity={equity:.0f}",
        },
        {
            "rule": "手续费 ≤ 风险金额 20%",
            "passed": fee <= risk_amount * 0.2,
            "detail": f"fee={fee:.2f} / risk_amount={risk_amount:.2f}",
        },
    ]

    return {
        "symbol": signal["symbol"],
        "side": signal["direction"],
        "entry_low": round(price * (1 - 0.003), 4),
        "entry_high": round(price * (1 + 0.003), 4),
        "stop": round(stop, 4),
        "targets": {"T1": round(target1, 4), "T2": round(target2, 4)},
        "size": lots,
        "raw_lots": raw_lots,
        "contract_size": contract_size,
        "margin_pct": margin_pct,
        "notional": round(notional, 2),
        "margin": round(margin, 2),
        "fee": round(fee, 2),
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
