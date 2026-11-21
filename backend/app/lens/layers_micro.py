"""Micro layer: trend, cross-asset ratios, gold microstructure and crowding."""

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
from app.lens.layers_catalog import MICRO_READINGS
from app.lens.layers_frame import _direction, _metric
from app.lens.persona_expression import evaluate_expression

def build_micro_layer(frame: pd.DataFrame, rules: list[dict] | None = None) -> dict[str, Any]:
    """微观层：价格与持仓结构，回答「已经定价了多少」。"""
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
        for item in MICRO_READINGS
    ]
    metrics = metric_map(readings)
    spx_dev = _metric(metrics, "micro.spx_dev200")
    ndx_ratio = _metric(metrics, "micro.ndx_spx")
    gold_silver = _metric(metrics, "micro.gold_silver")
    basis = _metric(metrics, "micro.comex_basis")
    premium = _metric(metrics, "micro.cn_premium")
    lease = _metric(metrics, "micro.gold_lease")
    etf = _metric(metrics, "micro.etf_flow")
    cot = _metric(metrics, "micro.cot_money_z")
    csi = _metric(metrics, "micro.csi_mom20")
    usdjpy = _metric(metrics, "micro.usdjpy_chg20")
    copper = _metric(metrics, "micro.copper_gold_z")
    dev250 = _metric(metrics, "micro.us30y_dev250")

    gold_micro = clamp(
        0.35 * (clamp((basis or 0.0) / 0.9, -1.5, 1.5) or 0.0)
        + 0.30 * (clamp((premium or 0.0) / 2.0, -1.5, 1.5) or 0.0)
        + 0.20 * (clamp((lease or 0.0) / 1.5, -1.5, 1.5) or 0.0)
        + 0.15 * (clamp((etf or 0.0) / 5.0, -1.5, 1.5) or 0.0),
        -2.0,
        2.0,
    ) or 0.0
    trend = clamp((spx_dev or 0.0) / 5.0, -1.5, 1.5) or 0.0
    positioning = clamp(-(cot or 0.0) / 2.0, -1.5, 1.5) or 0.0
    ndx_excess = clamp(((ndx_ratio if ndx_ratio is not None else 20.0) - 20.0) / 5.0, -1.5, 1.5) or 0.0
    silver_cheap = clamp((85.0 - (gold_silver or 85.0)) / 15.0, -1.5, 1.5) or 0.0
    bond_expensive = clamp(((dev250 if dev250 is not None else 50.0) - 50.0) / 25.0, -1.5, 1.5) or 0.0
    raw_scores = {
        "us_equity": 0.60 * trend + 0.25 * ndx_excess,
        "gold": 0.65 * gold_micro + 0.35 * positioning,
        "silver": 0.55 * gold_micro + 0.45 * silver_cheap,
        "usd": -0.35 * ((usdjpy or 0.0) / 2.0) - 0.25 * ((premium or 0.0) / 2.0),
        "cn_equity": 0.60 * (clamp((csi or 0.0) / 4.0, -1.5, 1.5) or 0.0) + 0.25 * (clamp(copper or 0.0, -1.5, 1.5) or 0.0),
        "long_bond": -0.55 * bond_expensive,
        "commodities": 0.55 * (clamp(copper or 0.0, -1.5, 1.5) or 0.0) + 0.15 * (clamp((gold_silver or 85.0) / 85.0 - 1, -1.0, 1.0) or 0.0),
    }
    scores = {
        asset: {"score": round(float(clamp(value, -2.0, 2.0) or 0.0), 2), "label": score_label(clamp(value, -2.0, 2.0))}
        for asset, value in raw_scores.items()
    }

    crowding: list[str] = []
    if ndx_ratio is not None and ndx_ratio >= 20:
        crowding.append("成长股集中度高")
    if cot is not None and cot >= 1.5:
        crowding.append("黄金多头拥挤")
    if gold_silver is not None and gold_silver > 85:
        crowding.append("金银比高位")
    if basis is not None and basis >= 0.9:
        crowding.append("COMEX 基差分裂")
    if premium is not None and premium >= 2.0:
        crowding.append("中国溢价异常")

    evaluated = [evaluate_rule(rule, metrics) for rule in (rules or [])]
    return {
        "id": "micro",
        "name": "微观层",
        "title": "趋势 / 比价 / 黄金微观结构 / 持仓 / 汇率动量",
        "readings": [reading.as_dict() for reading in readings],
        "metrics": metrics,
        "rules": evaluated,
        "scores": scores,
        "catalog": {str(item["id"]): item for item in MICRO_READINGS},
        "state": {
            "gold_micro": {"score": round(gold_micro, 2), "label": score_label(gold_micro)},
            "risk_appetite": {
                "spx_dev200": round_opt(spx_dev, 1),
                "label": _direction(spx_dev, 0.0, "风险偏好偏强", "风险偏好偏弱"),
            },
            "crowding": crowding,
            "narrative": " ".join(
                text
                for text in (
                    f"标普偏离 200 日均线 {round_opt(spx_dev, 1)}%，纳指/标普比价 {round_opt(ndx_ratio, 3)}。",
                    f"黄金微观结构评分 {round(gold_micro, 2)}（{score_label(gold_micro)}），金银比 {round_opt(gold_silver, 1)}。",
                    ("拥挤度提示：" + "、".join(crowding) + "。") if crowding else "未检测到明显拥挤。",
                )
                if text
            ),
        },
    }
