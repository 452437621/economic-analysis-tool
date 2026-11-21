"""Song lens interpretation: dollar heart, phase, risks and asset scores."""

from __future__ import annotations

from typing import Any

from app.cycle.market import Panel
from app.lens.common import (
    Reading,
    clamp,
    drawdown_pct,
    format_reading,
    metric_map,
    percentile_last,
    score_label,
)
from app.lens.song_catalog import CATALOG
from app.lens.song_readings import build_readings

# ── interpretation ─────────────────────────────────────────────────────


def _heart(spread_bp: float | None, spike_bp: float | None) -> dict[str, Any]:
    if spread_bp is None:
        return {"id": "unknown", "label": "未知", "level_bp": None, "spike_bp": None, "note": "缺 SOFR/EFFR。"}
    level = spread_bp
    spike = spike_bp or 0.0
    if level > 15 or spike > 8:
        return {
            "id": "infarction",
            "label": "心肌梗塞",
            "level_bp": level,
            "spike_bp": spike,
            "note": "回购市场冻结：机构会卖一切换流动性，包括黄金；48 小时内先降贝塔，再谈抄底。",
        }
    if level > 8 or spike > 4:
        return {
            "id": "angina",
            "label": "心绞痛",
            "level_bp": level,
            "spike_bp": spike,
            "note": "脉冲式跳升：高估值资产（AI、白银、加密）先崩，现金与短债是临时避风港。",
        }
    if level > 3:
        return {
            "id": "murmur",
            "label": "心率杂音",
            "level_bp": level,
            "spike_bp": spike,
            "note": "小幅偏离：环流转暖的顶部特征，别再加杠杆。",
        }
    return {
        "id": "normal",
        "label": "正常",
        "level_bp": level,
        "spike_bp": spike,
        "note": "回购市场无摩擦，环流方向由汇率与实际利率决定。",
    }


def _phase(dxy_pct: float | None, real_chg: float | None, heart: dict[str, Any]) -> dict[str, Any]:
    if dxy_pct is None:
        return {"id": "unknown", "label": "未知", "note": "缺 DXY 分位。"}
    if dxy_pct < 0.35 and (real_chg is None or real_chg <= 0.1):
        phase = {
            "id": "hot",
            "label": "热环流",
            "note": "弱美元 + 实际利率不升：美元外溢，新兴市场/大宗/白银弹性最大。",
        }
    elif dxy_pct > 0.65 and (real_chg is None or real_chg >= -0.1):
        phase = {
            "id": "cold",
            "label": "冷环流",
            "note": "强美元 + 实际利率不降：资本回流美国，新兴市场汇率与高杠杆资产承压。",
        }
    else:
        phase = {
            "id": "transition",
            "label": "过渡",
            "note": "美元分位与实际利率方向不一致，潮汐处于换挡期。",
        }
    if heart.get("id") == "infarction":
        phase = {
            "id": "reversal",
            "label": "环流反转（心梗）",
            "note": "回购市场冻结会瞬间逆转环流方向：先卖一切，再分辨谁是避险资产。",
        }
    return phase


def _asset_scores(
    dxy_pct: float | None,
    real_chg: float | None,
    gold_corr: float | None,
    premium: float | None,
    reserves_yoy: float | None,
    gold_silver: float | None,
    copper_gold_z: float | None,
    usdcnh_chg: float | None,
    csi_spx_chg: float | None,
    heart: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    dxy_n = ((dxy_pct if dxy_pct is not None else 0.5) - 0.5) * 2
    rate_n = clamp((real_chg or 0.0) / 1.5, -1, 1) or 0.0
    cb_n = clamp((reserves_yoy or 0.0) / 10, -1, 1) or 0.0
    prem_n = clamp((premium or 0.0) / 3, -1, 1) or 0.0
    corr = clamp(gold_corr or 0.0, -1, 1) or 0.0
    entropy = 0.45 * corr + 0.30 * prem_n + 0.25 * cb_n
    risk_off = 1.0 if heart.get("id") in {"angina", "infarction"} else 0.0

    gold = 0.95 * entropy - 0.55 * dxy_n - 0.45 * rate_n
    silver = 1.15 * gold + 0.35 * clamp((gold_silver or 80) - 80, -20, 60) / 20 - 0.25 * risk_off
    usd = 0.60 * dxy_n + 0.40 * rate_n
    cn_equity = -0.70 * dxy_n - 0.30 * rate_n + 0.20 * clamp((csi_spx_chg or 0.0) / 10, -1, 1)
    commodities = -0.50 * dxy_n + 0.30 * clamp(copper_gold_z or 0.0, -1, 1)
    long_bond = -0.75 - 0.35 * rate_n + 0.25 * (1.0 if heart.get("id") == "normal" else -1.0)
    us_equity = -0.55 * dxy_n - 0.25 * rate_n - 0.20 * risk_off
    raw = {
        "us_equity": us_equity,
        "gold": gold,
        "silver": silver,
        "usd": usd,
        "long_bond": long_bond,
        "cn_equity": cn_equity,
        "commodities": commodities,
    }
    why = {
        "us_equity": "美元潮汐是估值的外部约束；心梗时先杀高估值，再谈基本面。",
        "gold": "秩序熵值（相关性转正 + 中国溢价 + 央行购金）压过实际利率。",
        "silver": "黄金的杠杆版，外加金银比均值回归与实物挤兑弹性。",
        "usd": "强美元=冷环流，实际利率上行是第二支撑。",
        "long_bond": "长周期入冬：只做交易性多头，不做趋势性多头。",
        "cn_equity": "热钱三段式的终点；美元环流逆转时『物极必反』。",
        "commodities": "热环流+弱美元利多，冷环流+强美元利空。",
    }
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        score = round(clamp(value, -2, 2) or 0.0, 2)
        out[key] = {"score": score, "label": score_label(score), "why": why[key]}
    return out


def build_state(readings: list[Reading], panel: Panel) -> dict[str, Any]:
    by_id = {reading.id: reading for reading in readings}
    spread = by_id["song.sofr_effr"].value
    spike = by_id["song.sofr_spike"].value
    heart = _heart(spread, spike)

    dxy_pct = (by_id["song.dxy_pct"].value or 0) / 100.0 if by_id["song.dxy_pct"].value is not None else None
    real_chg = by_id["song.real10"].change
    phase = _phase(dxy_pct, real_chg, heart)

    # Harvest risk: 0-100, weighted percentiles of the four stress legs.
    hsi = panel.series("HSI")
    hsi_dd = drawdown_pct(hsi)
    legs: list[tuple[float, float]] = []
    if dxy_pct is not None:
        legs.append((dxy_pct, 0.25))
    real_pct = by_id["song.real10"].percentile
    if real_pct is not None:
        legs.append((real_pct, 0.20))
    hsi_rank = percentile_last(hsi_dd, 1260, min_obs=120) if not hsi.empty else None
    if hsi_rank is not None:
        legs.append((hsi_rank, 0.20))
    cnh_rank = by_id["song.usdcnh"].percentile
    if cnh_rank is not None:
        legs.append((cnh_rank, 0.20))
    sofr_rank = by_id["song.sofr_effr"].percentile
    if sofr_rank is not None:
        legs.append((sofr_rank, 0.15))
    harvest = None
    if legs:
        total_weight = sum(weight for _, weight in legs)
        harvest = round(100 * sum(value * weight for value, weight in legs) / total_weight)

    debt_gdp = by_id["song.debt_gdp"].value
    deficit_gdp = by_id["song.deficit_gdp"].value
    interest_pct = by_id["song.interest_receipts"].value
    us30_chg = by_id["song.us10y"].change
    debt_parts: list[tuple[float, float]] = []
    if debt_gdp is not None:
        debt_parts.append((clamp((debt_gdp - 100) / 100, 0, 1) * 100, 0.35))
    if deficit_gdp is not None:
        debt_parts.append((clamp((deficit_gdp - 3) / 9, 0, 1) * 100, 0.25))
    if interest_pct is not None:
        debt_parts.append((clamp((interest_pct - 10) / 36, 0, 1) * 100, 0.25))
    if us30_chg is not None:
        debt_parts.append((clamp(us30_chg / 1.5, 0, 1) * 100, 0.15))
    debt_risk = None
    if debt_parts:
        weights = sum(weight for _, weight in debt_parts)
        debt_risk = round(sum(value * weight for value, weight in debt_parts) / weights)

    gold_silver = by_id["song.gold_silver"].value
    gold_corr = by_id["song.gold_corr"].value
    scores = _asset_scores(
        dxy_pct,
        real_chg,
        gold_corr,
        by_id["song.cn_premium"].value,
        by_id["song.cn_reserves_yoy"].value,
        gold_silver,
        by_id["song.copper_gold"].z,
        by_id["song.usdcnh"].change,
        by_id["song.csi_spx"].change,
        heart,
    )
    gold_score = scores["gold"]["score"]
    if gold_score >= 1.2:
        gold_regime = {"id": "strategic", "label": "战略配置", "note": "秩序熵值主导，回撤是加仓窗口而非趋势反转。"}
    elif gold_score >= 0.4:
        gold_regime = {"id": "accumulate", "label": "逢低配置", "note": "结构性多头未破，等实际利率或美元给出更好的价格。"}
    elif gold_score > -0.4:
        gold_regime = {"id": "trade", "label": "交易持有", "note": "多空逻辑相互抵消，只做区间交易。"}
    else:
        gold_regime = {"id": "avoid", "label": "回避", "note": "实际利率与美元同时施压，秩序溢价不足以对冲。"}

    narrative = (
        f"宋鸿兵透镜读数：美元环流处于「{phase['label']}」，美元 250 日分位 "
        f"{by_id['song.dxy_pct'].value if by_id['song.dxy_pct'].value is not None else '—'}%，"
        f"同比 {format_reading(by_id['song.dxy_yoy'])}。"
        f"『美元心脏』为{heart['label']}（SOFR−EFFR {spread if spread is not None else '—'}bp，5 日脉冲 {spike if spike is not None else '—'}bp）。"
        f"收割风险 {harvest if harvest is not None else '—'}/100，债务货币化风险 {debt_risk if debt_risk is not None else '—'}/100；"
        f"黄金状态：{gold_regime['label']}。"
    )

    return {
        "phase": phase,
        "dollar_heart": heart,
        "harvest_risk": harvest,
        "debt_risk": debt_risk,
        "gold_regime": gold_regime,
        "asset_scores": scores,
        "narrative": narrative,
        "coverage": {
            "available": sum(1 for reading in readings if reading.value is not None),
            "total": len(readings),
        },
    }


def build_song(panel: Panel, gold_metric) -> dict[str, Any]:
    readings = build_readings(panel, gold_metric)
    state = build_state(readings, panel)
    return {
        "readings": [reading.as_dict() for reading in readings],
        "metrics": metric_map(readings),
        "state": state,
        "catalog": CATALOG,
    }
