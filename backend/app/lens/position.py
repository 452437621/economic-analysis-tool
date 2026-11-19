"""仓位、止损与组合权重：把资产方向翻译成可执行的决策说明。

这一层只做一件事——回答「方向有了，怎么下注」。所有参数都显式写出、可复算：

- **止损距离**：``2 × ATR%(14)``，夹在 1.5%–8% 之间（长债按收益率 bp 表达）；
- **单笔风险预算**：``1% × |共识分|``（0.3%–2%）；
- **仓位权重**：``风险预算 / 止损距离``，单资产上限 30%；
- **组合约束**：总敞口 ≤ 80%、组合风险（各仓位风险之和）≤ 6%，超限等比缩放。

权重以「总权益 = 100%」为基准，**与账户实际余额无关**；换算成金额时按自有权益等比缩放。
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

STOP_ATR_MULT = 2.0
MIN_STOP_PCT = 1.5
MAX_STOP_PCT = 8.0
BASE_RISK_PCT = 1.0
MIN_ASSET_RISK_PCT = 0.3
MAX_ASSET_RISK_PCT = 2.0
MAX_ASSET_WEIGHT_PCT = 30.0
MAX_GROSS_PCT = 80.0
MAX_PORTFOLIO_RISK_PCT = 6.0
MIN_SCORE = 0.25

#: 各资产的默认年化波动（%），在序列不足时兜底，避免「缺数据 → 不设止损」。
DEFAULT_VOL_PCT = {
    "us_equity": 16.0,
    "gold": 15.0,
    "silver": 26.0,
    "usd": 7.0,
    "cn_equity": 18.0,
    "long_bond": 8.0,
    "commodities": 30.0,
}

#: 长债的标的是收益率，止损用 bp 表达更贴近交易习惯。
BOND_YIELD_ASSETS = {"long_bond"}


def _series(panel: Any, symbol: str) -> pd.Series | None:
    try:
        series = panel.series(symbol)
    except Exception:  # noqa: BLE001 - 面板缺列时按缺数据处理
        return None
    if series is None:
        return None
    series = series.dropna()
    if len(series) < 5:
        return None
    return series


def realized_vol_pct(series: pd.Series | None, window: int = 20) -> float | None:
    """年化已实现波动（%）。"""
    if series is None or len(series) < 6:
        return None
    returns = series.pct_change().dropna().tail(window)
    if len(returns) < 5:
        return None
    daily = float(returns.std())
    if not math.isfinite(daily) or daily <= 0:
        return None
    return round(daily * math.sqrt(252) * 100, 2)


def atr_pct(series: pd.Series | None, window: int = 14) -> float | None:
    """平均真实波幅的近似值（%，用日线收盘的绝对值变动代替高低价）。"""
    if series is None or len(series) < 8:
        return None
    diffs = series.diff().abs().dropna().tail(window)
    last = float(series.iloc[-1])
    if not math.isfinite(last) or last == 0 or diffs.empty:
        return None
    value = float(diffs.mean()) / abs(last) * 100
    if not math.isfinite(value) or value <= 0:
        return None
    return round(value, 3)


def stop_distance_pct(asset_id: str, atr: float | None, vol: float | None) -> float:
    """止损距离（%）：2 倍 ATR，缺失时用波动率折算，再夹到 1.5%–8%。"""
    base: float | None = None
    if atr is not None:
        base = STOP_ATR_MULT * atr
    elif vol is not None:
        base = STOP_ATR_MULT * vol / math.sqrt(252)
    if base is None or not math.isfinite(base) or base <= 0:
        base = DEFAULT_VOL_PCT.get(asset_id, 15.0) / math.sqrt(252) * STOP_ATR_MULT / 4
    return round(min(max(base, MIN_STOP_PCT), MAX_STOP_PCT), 2)


def _side(direction: str, consensus: float | None) -> str:
    if direction in {"up", "down"}:
        return "long" if direction == "up" else "short"
    if consensus is None:
        return "flat"
    if consensus >= MIN_SCORE:
        return "long"
    if consensus <= -MIN_SCORE:
        return "short"
    return "flat"


def _label(side: str) -> str:
    return {"long": "做多", "short": "做空", "flat": "观望"}.get(side, side)


def build_asset_plan(row: dict[str, Any], panel: Any) -> dict[str, Any]:
    """单资产决策：止损、风险预算、仓位权重与一句话理由。"""
    asset_id = str(row["id"])
    consensus = row.get("consensus")
    side = _side(str(row.get("direction") or "flat"), consensus)
    series = _series(panel, str(row.get("symbol") or ""))
    vol = realized_vol_pct(series) or DEFAULT_VOL_PCT.get(asset_id)
    atr = atr_pct(series)
    stop_pct = stop_distance_pct(asset_id, atr, vol)
    last = row.get("last")

    if side == "flat":
        return {
            "actionable": False,
            "side": "flat",
            "side_label": _label("flat"),
            "stop_pct": stop_pct,
            "stop_level": None,
            "stop_note": "共识不足 0.25，不建仓；等方向明朗或分歧收敛后再评估。",
            "weight_pct": 0.0,
            "risk_pct": 0.0,
            "risk_at_pct": 0.0,
            "vol_pct": vol,
            "atr_pct": atr,
            "rationale": f"共识 {consensus if consensus is not None else '—'}，一致度「{row.get('agreement')}」→ 不建仓。",
        }

    strength = abs(float(consensus or 0.0))
    risk_pct = round(min(max(BASE_RISK_PCT * strength, MIN_ASSET_RISK_PCT), MAX_ASSET_RISK_PCT), 2)
    weight_pct = round(risk_pct / stop_pct * 100, 1)
    weight_pct = min(weight_pct, MAX_ASSET_WEIGHT_PCT)

    stop_level: float | None = None
    stop_note = ""
    if isinstance(last, (int, float)) and last:
        if asset_id in BOND_YIELD_ASSETS:
            bp = max(10.0, stop_pct / 100 * float(last) * 100)
            stop_level = round(float(last) + bp / 100, 3)
            stop_note = f"30 年期收益率上行约 {bp:.0f}bp 至 {stop_level:.2f}% 止损（债券价格反向）"
        elif side == "long":
            stop_level = round(float(last) * (1 - stop_pct / 100), 3)
            stop_note = f"自现价 {float(last):.3f} 下破 {stop_level:.3f}（−{stop_pct:.1f}%）止损"
        else:
            stop_level = round(float(last) * (1 + stop_pct / 100), 3)
            stop_note = f"自现价 {float(last):.3f} 上破 {stop_level:.3f}（+{stop_pct:.1f}%）止损"

    return {
        "actionable": True,
        "side": side,
        "side_label": _label(side),
        "stop_pct": stop_pct,
        "stop_level": stop_level,
        "stop_note": stop_note or f"按波动设 {stop_pct:.1f}% 止损",
        "weight_pct": weight_pct,
        "risk_pct": risk_pct,
        "risk_at_pct": round(weight_pct / 100 * stop_pct, 2),
        "vol_pct": vol,
        "atr_pct": atr,
        "rationale": (
            f"共识 {float(consensus or 0):+.2f}（{row.get('agreement')}）× "
            f"ATR {atr:.2f}% → 止损 {stop_pct:.1f}%、风险预算 {risk_pct:.2f}% → 权重 {weight_pct:.1f}%"
            if atr is not None
            else f"共识 {float(consensus or 0):+.2f} × 波动 {vol}% → 止损 {stop_pct:.1f}%、权重 {weight_pct:.1f}%"
        ),
    }


def build_portfolio(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """组合层：归一化权重、总敞口、组合风险与现金。"""
    plans = [(row, row.get("plan") or {}) for row in rows]
    active = [(row, plan) for row, plan in plans if plan.get("actionable")]
    long_w = sum(float(plan.get("weight_pct") or 0) for row, plan in active if plan.get("side") == "long")
    short_w = sum(float(plan.get("weight_pct") or 0) for row, plan in active if plan.get("side") == "short")
    gross = long_w + short_w
    scale = 1.0
    if gross > MAX_GROSS_PCT and gross > 0:
        scale = MAX_GROSS_PCT / gross
    risk_sum = sum(float(plan.get("weight_pct") or 0) * float(plan.get("stop_pct") or 0) / 100 for _, plan in active)
    risk_sum *= scale
    if risk_sum > MAX_PORTFOLIO_RISK_PCT and risk_sum > 0:
        risk_scale = MAX_PORTFOLIO_RISK_PCT / risk_sum
        scale *= risk_scale
        risk_sum = MAX_PORTFOLIO_RISK_PCT

    positions: list[dict[str, Any]] = []
    long_out = short_out = 0.0
    risk_out = 0.0
    for row, plan in active:
        # 向下取到 0.1%，避免四舍五入把总敞口推过上限。
        weight = math.floor(float(plan.get("weight_pct") or 0) * scale * 10) / 10
        if weight <= 0:
            plan["weight_pct"] = 0.0
            plan["risk_at_pct"] = 0.0
            continue
        plan["weight_pct"] = weight
        risk = round(weight / 100 * float(plan.get("stop_pct") or 0), 2)
        plan["risk_at_pct"] = risk
        risk_out += risk
        if plan.get("side") == "long":
            long_out += weight
        else:
            short_out += weight
        positions.append(
            {
                "asset": row["id"],
                "label": row["label"],
                "side": plan.get("side"),
                "side_label": plan.get("side_label"),
                "weight_pct": weight,
                "risk_pct": risk,
                "stop_pct": plan.get("stop_pct"),
                "stop_level": plan.get("stop_level"),
            }
        )

    gross_out = round(long_out + short_out, 1)
    return {
        "basis": "权重以总权益为 100% 计（与账户余额无关，按自有权益等比缩放）",
        "gross_weight_pct": gross_out,
        "long_weight_pct": round(long_out, 1),
        "short_weight_pct": round(short_out, 1),
        "net_weight_pct": round(long_out - short_out, 1),
        "cash_weight_pct": round(max(0.0, 100.0 - gross_out), 1),
        "portfolio_risk_pct": round(risk_out, 2),
        "max_loss_pct": round(risk_out, 2),
        "positions": positions,
        "scale_applied": round(scale, 3),
        "rules": [
            f"止损距离 = 2×ATR(14)，夹在 {MIN_STOP_PCT:.1f}%–{MAX_STOP_PCT:.1f}%",
            f"单笔风险预算 = {BASE_RISK_PCT:.0f}% × |共识分|，夹在 {MIN_ASSET_RISK_PCT}%–{MAX_ASSET_RISK_PCT}%",
            f"单资产权重上限 {MAX_ASSET_WEIGHT_PCT:.0f}%",
            f"总敞口上限 {MAX_GROSS_PCT:.0f}%、组合风险上限 {MAX_PORTFOLIO_RISK_PCT:.0f}%，超限等比缩放",
            f"共识 |分| < {MIN_SCORE} 一律观望（不建仓）",
        ],
        "note": (
            f"当前 {len(positions)} 个可执行方向，总敞口 {gross_out:.1f}%、"
            f"组合风险 {risk_out:.2f}%（全部止损同时触发的账面损失上限），现金 {max(0.0, 100.0 - gross_out):.1f}%。"
            "仓位是风险预算的结果，不是资金多少的结果；若自有权益与 100% 基准不同，等比例缩放即可。"
        ),
    }


def build_decisions(rows: list[dict[str, Any]], panel: Any) -> dict[str, Any]:
    """给每行资产挂上 ``plan``，并返回组合层说明。"""
    for row in rows:
        row["plan"] = build_asset_plan(row, panel)
    return build_portfolio(rows)
