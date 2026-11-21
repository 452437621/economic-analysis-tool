"""Multi-lens synthesis: weights, consensus, divergences and outlook."""

from __future__ import annotations

from typing import Any

from app.cycle.market import Panel
from app.lens import position as position_engine
from app.lens.common import round_opt as _round, score_label
from app.lens.helpers import (
    ASSETS,
    _advice,
    _agreement_multi,
    _divergence_catalyst,
    _last_close,
    _lens_label,
    _warning_list,
)

def _synthesis(
    lens_scores: dict[str, dict[str, float | None]],
    panel: Panel,
    config: dict[str, Any],
    cycle_context: dict[str, Any] | None,
    lens_states: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """多透镜合成：按 config 权重加权，输出共识、分歧、预警与情景。

    ``lens_scores`` 是有序映射 ``{透镜 id: {资产 id: 分数}}``，包含 macro/micro
    两层与全部人物透镜。缺少某透镜分数的资产只用其余透镜加权，绝不把缺失当 0。
    """
    settings = config.get("synthesis") or {}
    weights: dict[str, float] = {
        str(key): float(value) for key, value in (settings.get("weights") or {}).items()
    }
    active = [(lens_id, scores) for lens_id, scores in lens_scores.items() if weights.get(lens_id, 0.0) > 0]
    if not active:
        active = list(lens_scores.items())
    states = lens_states or {}

    rows: list[dict[str, Any]] = []
    divergences: list[dict[str, Any]] = []
    for asset in ASSETS:
        asset_id = asset["id"]
        contributions: dict[str, float] = {}
        for lens_id, scores in active:
            value = scores.get(asset_id)
            if value is None:
                continue
            contributions[lens_id] = round(float(value), 2)
        weight_sum = sum(weights.get(lens_id, 1.0) for lens_id in contributions)
        consensus = None
        if contributions and weight_sum > 0:
            consensus = round(
                sum(weights.get(lens_id, 1.0) * value for lens_id, value in contributions.items()) / weight_sum,
                2,
            )
        fed_score = contributions.get("fed")
        song_score = contributions.get("song")
        agreement, direction = _agreement_multi(contributions, consensus)
        probability = None
        if consensus is not None:
            probability = round(min(0.78, 0.50 + 0.10 * abs(consensus)), 3)
        rows.append(
            {
                "id": asset_id,
                "label": asset["label"],
                "symbol": asset["symbol"],
                "unit": asset["unit"],
                "note": asset["note"],
                "last": _round(_last_close(panel, asset["symbol"]), 3),
                "fed": fed_score,
                "song": song_score,
                "scores": contributions,
                "lenses": len(contributions),
                "consensus": consensus,
                "label_consensus": score_label(consensus),
                "agreement": agreement,
                "direction": direction,
                "probability": probability,
                "advice": _advice(agreement, consensus, len(contributions)),
            }
        )
        if contributions:
            positives = {key: value for key, value in contributions.items() if value >= 0.35}
            negatives = {key: value for key, value in contributions.items() if value <= -0.35}
            if positives and negatives:
                bull = max(positives, key=lambda key: positives[key])
                bear = min(negatives, key=lambda key: negatives[key])
                divergences.append(
                    {
                        "asset": asset_id,
                        "label": asset["label"],
                        "fed": fed_score,
                        "song": song_score,
                        "spread": _round(contributions[bull] - contributions[bear], 2),
                        "reading": f"{_lens_label(bull, states)} {contributions[bull]:+.2f} / "
                        f"{_lens_label(bear, states)} {contributions[bear]:+.2f}",
                        "pair": [bull, bear],
                        "catalyst": _divergence_catalyst(asset_id),
                    }
                )

    warnings = _warning_list(states.get("fed") or {}, states.get("song") or {}, states)
    consensus_count = sum(1 for row in rows if row["agreement"] in {"共振多", "共振空"})
    strong = [row for row in rows if row["agreement"] == "共振强信号"]
    headline = {
        "fed": (states.get("fed") or {}).get("stance_label", "未知"),
        "song": ((states.get("song") or {}).get("phase") or {}).get("label", "未知"),
        "macro": ((states.get("macro") or {}).get("regime") or {}).get("label", "未知"),
        "micro": ((states.get("micro") or {}).get("risk_appetite") or {}).get("label", "未知"),
        "personas": sum(1 for key in states if key not in {"fed", "song", "macro", "micro"}),
    }
    narrative = (
        f"合成结论：{len(active)} 套透镜参与、{consensus_count} 项同向共振、{len(divergences)} 项方向冲突。"
        f"美联储「{headline['fed']}」、宋鸿兵「{headline['song']}」、宏观层「{headline['macro']}」、"
        f"微观层「{headline['micro']}」。"
        "同向项是仓位来源，冲突项是风险来源；冲突未解决前，单套透镜的结论只能做研究，不能做仓位。"
    )

    outlook = _outlook(states.get("fed") or {}, states.get("song") or {}, rows, warnings)
    portfolio = position_engine.build_decisions(rows, panel)
    return {
        "assets": rows,
        "portfolio": portfolio,
        "divergences": divergences,
        "warnings": warnings,
        "consensus_count": consensus_count,
        "strong_count": len(strong),
        "lens_count": len(active),
        "weights": {lens_id: weights.get(lens_id, 1.0) for lens_id, _ in active},
        "headline": headline,
        "narrative": narrative,
        "outlook": outlook,
        "cycle_context": cycle_context,
        "confidence": _synthesis_confidence(states.get("fed") or {}, states.get("song") or {}, rows, len(active)),
    }


def _outlook(
    fed_state: dict[str, Any],
    song_state: dict[str, Any],
    rows: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    strongest = sorted(
        [row for row in rows if row["consensus"] is not None],
        key=lambda row: abs(row["consensus"]),
        reverse=True,
    )[:3]
    base_case = (
        f"未来 3 个月基准情景：{fed_state.get('policy', {}).get('bias', '观望')} + "
        f"美元环流「{(song_state.get('phase') or {}).get('label', '未知')}」。"
        f"排序最高的三个信号是 "
        + "、".join(f"{row['label']}（{row['label_consensus']}）" for row in strongest)
        + "。"
    )
    return {
        "horizon_days": 90,
        "base_case": base_case,
        "bull_case": "上行风险：金融条件自行转松 + 美元环流转暖 + 回购摩擦消失，风险资产与白银弹性最大。",
        "bear_case": "下行风险：SOFR−EFFR 脉冲 + 强美元 + 长端利率上行同时出现，先杀高估值（AI、白银），再谈黄金的秩序溢价。",
        "triggers": warnings,
        "invalidators": [
            "若 10Y 实际利率在 3 个月内下行 >50bp 而金价不涨，则『实际利率→黄金』的映射失效。",
            "若 SOFR−EFFR 回落至 5bp 以下且 DXY 250 日分位跌破 30%，冷环流判断失效。",
            "若多数透镜连续 20 个交易日同向且资产价格反向，视为框架失效，需降权而不是加仓。",
        ],
    }


def _synthesis_confidence(
    fed_state: dict[str, Any],
    song_state: dict[str, Any],
    rows: list[dict[str, Any]],
    lens_count: int = 2,
) -> float:
    fed_cov = (fed_state.get("coverage") or {}).get("available", 0) / max(
        1, (fed_state.get("coverage") or {}).get("total", 1)
    )
    song_cov = (song_state.get("coverage") or {}).get("available", 0) / max(
        1, (song_state.get("coverage") or {}).get("total", 1)
    )
    agreement_ratio = sum(1 for row in rows if row["agreement"] in {"共振多", "共振空", "共振强信号"}) / max(
        1, len(rows)
    )
    breadth = min(1.0, lens_count / 6.0)
    return round(
        min(0.85, 0.20 + 0.20 * fed_cov + 0.15 * song_cov + 0.25 * agreement_ratio + 0.15 * breadth),
        3,
    )
