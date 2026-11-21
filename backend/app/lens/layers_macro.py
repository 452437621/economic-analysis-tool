"""Macro layer: growth/inflation regime, liquidity, fiscal and funding."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.lens.common import (
    build_reading,
    clamp,
    evaluate_rule,
    metric_map,
    round_opt,
    score_label,
)
from app.lens.layers_catalog import MACRO_READINGS
from app.lens.layers_frame import _direction, _metric
from app.lens.persona_expression import evaluate_expression

_REGIMES = {
    (True, True): ("reflation", "再通胀", "增长与通胀同向向上，久期最难受。"),
    (True, False): ("goldilocks", "金发姑娘", "增长向上、通胀向下，风险资产最舒服。"),
    (False, True): ("stagflation", "滞胀", "增长下行、通胀上行，股债双杀。"),
    (False, False): ("deflation", "通缩压力", "增长与通胀同向向下，现金与长债占优。"),
}


def build_macro_layer(frame: pd.DataFrame, rules: list[dict] | None = None) -> dict[str, Any]:
    """宏观层：读数 + 状态 + 规则 + 七类资产评分。"""
    readings = [
        build_reading(
            str(item["id"]),
            str(item["label"]),
            evaluate_expression(str(item["expr"]), frame),
            unit=str(item.get("unit") or ""),
            digits=int(item.get("digits") or 2),
            source=str(item.get("source") or ""),
            evidence=str(item.get("evidence") or "E3"),
            note=str(item.get("note") or ""),
            missing_reason="该读数依赖的序列本地无数据",
        )
        for item in MACRO_READINGS
    ]
    metrics = metric_map(readings)
    growth = _metric(metrics, "macro.growth_z")
    inflation = _metric(metrics, "macro.inflation_z")
    regime_id, regime_label, regime_note = "unknown", "数据不足", ""
    if growth is not None and inflation is not None:
        regime_id, regime_label, regime_note = _REGIMES[(growth >= 0, inflation >= 0)]
    liquidity_pct = _metric(metrics, "macro.net_liquidity_pct")
    fiscal = _metric(metrics, "macro.fiscal_impulse")
    stress = _metric(metrics, "macro.funding_stress")
    real10 = _metric(metrics, "macro.real10")
    dxy_z = _metric(metrics, "macro.dxy_z")

    flags: list[str] = []
    if stress is not None and stress > 15:
        flags.append("融资市场紧张")
    if fiscal is not None and fiscal > 6:
        flags.append("财政主导")
    if real10 is not None and real10 > 2:
        flags.append("实际利率高企")
    if liquidity_pct is not None and liquidity_pct < -5:
        flags.append("净流动性收缩")

    liq = clamp((liquidity_pct or 0.0) / 10.0, -1.0, 1.0) or 0.0
    g = clamp((growth or 0.0) / 1.5, -1.0, 1.0) or 0.0
    i = clamp((inflation or 0.0) / 1.5, -1.0, 1.0) or 0.0
    r = clamp((real10 or 0.0) / 2.0, -1.0, 1.0) or 0.0
    d = clamp(dxy_z or 0.0, -1.5, 1.5) or 0.0
    fiscal_pressure = clamp(-(fiscal or 0.0) / 8.0, -1.0, 1.0) or 0.0
    raw_scores = {
        "us_equity": 0.55 * g + 0.25 * liq - 0.25 * r - 0.15 * d,
        "gold": 0.35 * (-r) + 0.25 * i + 0.20 * (-d) + 0.20 * fiscal_pressure,
        "silver": 0.35 * g + 0.25 * i + 0.20 * (-r) + 0.20 * liq,
        "usd": 0.45 * d + 0.30 * r - 0.25 * liq,
        "cn_equity": 0.45 * g + 0.30 * liq - 0.25 * d,
        "long_bond": -0.45 * i - 0.35 * g + 0.35 * (-r) + 0.20 * (-liq),
        "commodities": 0.45 * g + 0.30 * i + 0.25 * liq + 0.15 * d,
    }
    scores = {
        asset: {"score": round(float(clamp(value, -2.0, 2.0) or 0.0), 2), "label": score_label(clamp(value, -2.0, 2.0))}
        for asset, value in raw_scores.items()
    }

    evaluated = [evaluate_rule(rule, metrics) for rule in (rules or [])]
    return {
        "id": "macro",
        "name": "宏观层",
        "title": "增长 / 通胀 / 流动性 / 财政 / 融资 / 美元 / 曲线",
        "readings": [reading.as_dict() for reading in readings],
        "metrics": metrics,
        "rules": evaluated,
        "scores": scores,
        "catalog": {str(item["id"]): item for item in MACRO_READINGS},
        "state": {
            "regime": {"id": regime_id, "label": regime_label, "note": regime_note},
            "liquidity": {
                "value": round_opt(liquidity_pct, 1),
                "label": _direction(liquidity_pct, 2.0, "扩张", "收缩"),
            },
            "fiscal": {
                "value": round_opt(fiscal, 1),
                "label": _direction(fiscal, 6.0, "财政主导", "财政中性"),
            },
            "funding": {
                "value": round_opt(stress, 1),
                "label": _direction(stress, 8.0, "融资偏紧", "融资平稳"),
            },
            "flags": flags,
            "narrative": " ".join(
                text
                for text in (
                    f"宏观层判定为{regime_label}：{regime_note}",
                    f"净流动性 13 周变化 {round_opt(liquidity_pct, 1)}%，{_direction(liquidity_pct, 2.0, '扩张', '收缩')}。",
                    ("风险标记：" + "、".join(flags) + "。") if flags else "暂无宏观风险标记。",
                )
                if text
            ),
        },
    }
