"""交易计划构建：以损定量 + 风控检查（M4 v0.2：与账户资金脱钩）。

设计原则（2026-11-19 调整）：

- 交易信号只回答「这笔交易值不值得做、按波动该怎么下注」，**不判断账户买不买得起**。
  因此仓位一律按固定基准权益 ``BASE_EQUITY`` 计算，输出小数手数（可信息性地给出整数手），
  不会因为「资金不足」把计划标成 0 手或拦截。
- 风控检查只保留与资金规模无关的规则：单笔风险上限、止损距离、组合权重上限、
  手续费占风险金额比例、名义杠杆上限。
- 止损、加减仓与失效条件仍是计划的一部分；账户层面的资金约束交给 ``/trades`` 与人工确认。
"""

from __future__ import annotations

import math

from app.platform.config import settings

#: 信号仓位的标准化基准权益（元）。所有手数、名义金额都按这个基准给出，
#: 实际下单时按「自有权益 / 基准权益」等比缩放即可，不需要改动信号结论。
BASE_EQUITY: float = 100_000.0

#: 单笔风险预算的硬上限（%），超过即视为风控不通过。
MAX_RISK_PCT: float = 0.3

#: 组合权重（名义金额 / 基准权益）上限（%）。
MAX_WEIGHT_PCT: float = 25.0

#: 名义杠杆（名义金额 / 基准权益）上限。
MAX_LEVERAGE: float = 5.0

#: 止损距离上限（%）。
MAX_STOP_PCT: float = 5.0


def size_position(
    equity: float,
    risk_pct: float,
    price: float,
    stop_price: float,
    contract_multiplier: float = 1.0,
) -> float:
    """按风险预算给出头寸规模（股/手/张，可为小数）。

    ``equity`` 在这里是*规模基准*，不是账户余额；资金是否充足不参与计算。
    """
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
    """按合约乘数换算的手数（可为小数，不做向下取整）。"""
    return size_position(equity, risk_pct, price, stop_price, contract_size)


def build_plan(
    signal: dict,
    spec: dict | None = None,
    equity: float | None = None,
    risk_pct: float | None = None,
) -> dict:
    """构建交易计划。

    ``equity`` 缺省取 :data:`BASE_EQUITY`（信号基准），显式传入时仅作为规模基准，
    不改变风控规则的可比性——这也是「信号不因资金不足而失效」的实现方式。
    """
    base_equity = BASE_EQUITY if equity is None else float(equity)
    risk_pct = settings.risk_per_trade_pct if risk_pct is None else float(risk_pct)
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

    raw_lots = size_lots(base_equity, risk_pct, price, stop, contract_size)
    lots = round(raw_lots, 4)
    lots_int = int(math.floor(raw_lots))
    notional = lots * contract_size * price
    margin = notional * margin_pct
    fee = lots * fee_per_lot + notional * commission_rate
    risk_amount = base_equity * risk_pct / 100.0
    stop_distance_pct = abs(price - stop) / price * 100
    weight_pct = notional / base_equity * 100 if base_equity > 0 else 0.0
    leverage = notional / base_equity if base_equity > 0 else 0.0
    reward1 = abs(target1 - price) * lots * contract_size
    risk_reward = (reward1 / risk_amount) if risk_amount > 0 else 0.0

    sizing_note = ""
    if lots_int < 1:
        sizing_note = (
            f"按基准权益 {base_equity:,.0f} 元计算为 {lots:.2f} 手（不足 1 整手）；"
            "可用迷你合约，或按自有权益等比缩小/放大，不构成信号失效。"
        )

    checks = [
        {
            "rule": f"单笔风险 ≤ {MAX_RISK_PCT}%",
            "passed": risk_pct <= MAX_RISK_PCT,
            "detail": f"risk_pct={risk_pct:.2f}%",
        },
        {
            "rule": f"止损距离 ≤ {MAX_STOP_PCT:.0f}%",
            "passed": stop_distance_pct <= MAX_STOP_PCT,
            "detail": f"stop_distance={stop_distance_pct:.2f}%",
        },
        {
            "rule": f"组合权重 ≤ {MAX_WEIGHT_PCT:.0f}%",
            "passed": weight_pct <= MAX_WEIGHT_PCT,
            "detail": f"weight={weight_pct:.2f}% (notional={notional:,.0f} / base={base_equity:,.0f})",
        },
        {
            "rule": f"名义杠杆 ≤ {MAX_LEVERAGE:.1f} 倍",
            "passed": leverage <= MAX_LEVERAGE,
            "detail": f"leverage={leverage:.2f}x",
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
        "lots_int": lots_int,
        "raw_lots": raw_lots,
        "contract_size": contract_size,
        "margin_pct": margin_pct,
        "notional": round(notional, 2),
        "margin": round(margin, 2),
        "fee": round(fee, 2),
        "risk_pct": risk_pct,
        "risk_amount": round(risk_amount, 2),
        "stop_distance_pct": round(stop_distance_pct, 3),
        "weight_pct": round(weight_pct, 2),
        "leverage": round(leverage, 3),
        "risk_reward": round(risk_reward, 2),
        "sizing_note": sizing_note,
        "time_stop_days": 3,
        "invalidation": (
            f"跌破 {stop:.4f} 止损；或入场后第 3 个交易日收盘未脱离成本区；"
            f"或信号逻辑被证伪（{signal['type']}）"
        ),
        "checks": checks,
        "signal": signal,
        "base_equity": base_equity,
        "equity": base_equity,  # 兼容旧字段名，含义已是规模基准
    }
