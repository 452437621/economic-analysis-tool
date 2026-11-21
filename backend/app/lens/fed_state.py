"""Fed lens interpretation: stance, regime, put state and asset scores."""

from __future__ import annotations

from typing import Any

from app.cycle.market import Panel
from app.lens.common import (
    Reading,
    clamp,
    format_reading,
    last_value,
    metric_map,
    score_label,
)
from app.lens.fed_catalog import CATALOG
from app.lens.fed_readings import build_readings

# ── interpretation ─────────────────────────────────────────────────────


def _pct(value: float | None) -> float | None:
    return None if value is None else clamp(value, 0.0, 1.0)


def _mean(pairs: list[tuple[float, float]]) -> float | None:
    if not pairs:
        return None
    total = sum(weight for _, weight in pairs)
    if total <= 0:
        return None
    return sum(value * weight for value, weight in pairs) / total


def _stance_components(by_id: dict[str, Reading]) -> list[tuple[str, float, float]]:
    """(label, percentile, weight); higher percentile = tighter policy."""
    components: list[tuple[str, float, float]] = []
    real10 = _pct(by_id["fed.real10"].percentile)
    if real10 is not None:
        components.append(("实际利率", real10, 0.30))
    real_policy = _pct(by_id["fed.real_policy"].percentile)
    if real_policy is not None:
        components.append(("实际政策利率", real_policy, 0.20))
    fci = _pct(by_id["fed.fci"].percentile)
    if fci is not None:
        components.append(("金融条件", fci, 0.30))
    curve = _pct(by_id["fed.curve_2s10s"].percentile)
    if curve is not None:
        components.append(("期限利差（越平越紧）", 1.0 - curve, 0.20))
    return components


def _stance_label(score: int) -> str:
    if score <= 20:
        return "极松"
    if score <= 40:
        return "偏松"
    if score <= 60:
        return "中性"
    if score <= 80:
        return "偏紧"
    return "极紧"


def _quadrant(growth: float | None, inflation: float | None) -> dict[str, str]:
    if growth is None or inflation is None:
        return {"id": "unknown", "label": "数据不足", "note": "增长或通胀代理缺失，无法定位象限。"}
    if growth >= 0 and inflation >= 0:
        return {
            "id": "overheat",
            "label": "过热",
            "note": "增长与通胀同向向上：联储有理由维持紧缩，长久期与高估值最脆弱。",
        }
    if growth >= 0 and inflation < 0:
        return {
            "id": "reflation",
            "label": "复苏",
            "note": "增长改善、通胀回落：风险资产最舒服的象限。",
        }
    if growth < 0 and inflation >= 0:
        return {
            "id": "stagflation",
            "label": "滞胀",
            "note": "增长下行、通胀粘性：联储两难，黄金相对占优。",
        }
    return {
        "id": "deflation",
        "label": "衰退/通缩",
        "note": "增长与通胀同步走弱：降息交易与久期占优。",
    }


def _put_state(drawdown: float | None) -> dict[str, Any]:
    if drawdown is None:
        return {"id": "unknown", "label": "未知", "drawdown": None, "note": "缺标普序列。"}
    if drawdown >= 15:
        return {
            "id": "in_the_money",
            "label": "行权区",
            "drawdown": drawdown,
            "note": "回撤已达 15% 以上，联储救市的概率显著上升；但『先跌后救』意味着别抢第一根阳线。",
        }
    if drawdown >= 8:
        return {
            "id": "near",
            "label": "接近行权",
            "drawdown": drawdown,
            "note": "回撤 8–15%，官员表态会开始转向鸽派，市场会提前交易。",
        }
    return {
        "id": "far",
        "label": "远",
        "drawdown": drawdown,
        "note": "回撤不足 8%，联储没有被迫宽松的压力。",
    }


def _asset_scores(
    growth_z: float | None,
    inflation_z: float | None,
    real10_z: float | None,
    dxy_z: float | None,
    stance: int | None,
    put: dict[str, Any],
    gold_corr: float | None,
) -> dict[str, dict[str, Any]]:
    g = clamp(growth_z, -2, 2) or 0.0
    i = clamp(inflation_z, -2, 2) or 0.0
    r = clamp(real10_z, -2, 2) or 0.0
    d = clamp(dxy_z, -2, 2) or 0.0
    s = ((stance if stance is not None else 50) - 50) / 25.0
    easing = -s
    put_bonus = {"in_the_money": 1.0, "near": 0.5}.get(put.get("id", ""), 0.0)
    corr = clamp(gold_corr, -1, 1) or 0.0

    raw = {
        "us_equity": 0.70 * g + 0.50 * easing - 0.45 * r + 0.35 * put_bonus,
        "gold": -0.65 * r - 0.40 * d + 0.30 * put_bonus + 0.25 * i + 0.35 * corr,
        "silver": -0.75 * r - 0.45 * d + 0.30 * put_bonus + 0.20 * i + 0.55 * corr,
        "usd": 0.55 * r + 0.40 * s - 0.20 * g,
        "long_bond": -0.50 * g - 0.40 * i + 0.70 * easing,
        "cn_equity": -0.60 * d + 0.30 * g + 0.30 * easing,
        "commodities": 0.50 * g + 0.40 * i - 0.25 * d,
    }
    why = {
        "us_equity": "增长与宽松程度是分子，实际利率与强美元是分母；回撤越深，看跌期权越近。",
        "gold": "实际利率与实际利率相关性是核心；秩序风险（相关转正）会盖过利率。",
        "silver": "比黄金多一层工业属性与实际利率弹性，波动更大。",
        "usd": "实际利率与紧缩立场支撑美元，增长走弱则削弱。",
        "long_bond": "增长与通胀下行利多久期，宽松预期是第二引擎。",
        "cn_equity": "强美元抽走外部流动性；增长与宽松提供内部对冲。",
        "commodities": "增长与通胀同向利多商品，强美元是逆风。",
    }
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        score = round(clamp(value, -2, 2) or 0.0, 2)
        out[key] = {"score": score, "label": score_label(score), "why": why[key]}
    return out


def build_state(readings: list[Reading], panel: Panel) -> dict[str, Any]:
    by_id = {reading.id: reading for reading in readings}
    components = _stance_components(by_id)
    stance_pct = _mean([(component[1], component[2]) for component in components])
    stance = None if stance_pct is None else int(round(stance_pct * 100))

    growth_z = by_id["fed.growth"].z
    inflation_z = by_id["fed.inflation"].z
    real10_z = by_id["fed.real10"].z
    dxy_z = by_id["fed.dxy"].z
    put = _put_state(by_id["fed.spx_drawdown"].value)
    quadrant = _quadrant(growth_z, inflation_z)
    gold_corr = by_id["fed.gold_real_corr"].value

    spx = panel.series("SPX")
    high = float(spx.rolling("252D", min_periods=20).max().dropna().iloc[-1]) if not spx.empty else None
    strike = high * 0.85 if high else None
    current, _ = last_value(spx)
    distance = ((current / strike - 1) * 100) if current and strike else None

    if stance is None:
        policy_bias = "未知"
        cut_probability = None
    elif growth_z is not None and growth_z < -0.5 and (inflation_z or 0) < 0.8:
        policy_bias = "宽松倾向"
        cut_probability = clamp(0.45 + (-growth_z) * 0.12 + (50 - stance) / 200, 0.05, 0.9)
    elif inflation_z is not None and inflation_z > 0.8 and (growth_z or 0) > -0.5:
        policy_bias = "紧缩倾向"
        cut_probability = clamp(0.10 + (stance - 50) / 300, 0.02, 0.5)
    else:
        policy_bias = "观望"
        cut_probability = clamp(0.30 + (50 - stance) / 250, 0.05, 0.7)

    score = _asset_scores(growth_z, inflation_z, real10_z, dxy_z, stance, put, gold_corr)

    narrative = (
        f"美联储透镜读数：政策立场 {stance if stance is not None else '—'}/100（{_stance_label(stance) if stance is not None else '未知'}），"
        f"经济象限为「{quadrant['label']}」。"
        f"实际 10 年期利率 {format_reading(by_id['fed.real10'])}，2s10s {format_reading(by_id['fed.curve_2s10s'])}，"
        f"标普距高点回撤 {format_reading(by_id['fed.spx_drawdown'])}。"
        f"看跌期权状态：{put['label']}；政策倾向：{policy_bias}。"
    )

    return {
        "stance": stance,
        "stance_label": _stance_label(stance) if stance is not None else "未知",
        "stance_components": [
            {"label": label, "percentile": round(percentile, 3), "weight": weight}
            for label, percentile, weight in components
        ],
        "regime": quadrant,
        "fed_put": {
            **put,
            "strike": round(strike, 2) if strike else None,
            "spot": round(current, 2) if current else None,
            "distance_pct": round(distance, 2) if distance is not None else None,
        },
        "policy": {
            "bias": policy_bias,
            "cut_probability_3m": round(cut_probability, 3) if cut_probability is not None else None,
        },
        "asset_scores": score,
        "narrative": narrative,
        "coverage": {
            "available": sum(1 for reading in readings if reading.value is not None),
            "total": len(readings),
        },
    }


def build_fed(panel: Panel) -> dict[str, Any]:
    readings = build_readings(panel)
    state = build_state(readings, panel)
    return {
        "readings": [reading.as_dict() for reading in readings],
        "metrics": metric_map(readings),
        "state": state,
        "catalog": CATALOG,
    }
