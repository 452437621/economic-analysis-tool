"""Greenspan-lineage Fed lens.

The lens is deliberately *not* a Taylor-rule replica.  It encodes the three
things the Greenspan/Bernanke/Yellen/Powell lineage actually reacts to:

1. the real cost of money (real policy rate + real long yield),
2. the financial-conditions loop (the "Greenspan put"),
3. the growth/inflation quadrant that decides whether the Fed can look through
   an inflation print or has to defend credibility.

Readings are levels/ratios computed from the local panel; the interpretive layer
(stance score, regime, put proximity, asset tilts) is a transparent weighted
average whose weights are printed in ``config/lens.yaml``.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.cycle.market import Panel
from app.lens.common import (
    Reading,
    build_reading,
    clamp,
    drawdown_pct,
    last_value,
    metric_map,
    ratio,
    rolling_corr,
    score_label,
    z_series,
)

CATALOG: list[dict[str, Any]] = [
    {
        "id": "fed.effr",
        "label": "联邦基金有效利率（EFFR）",
        "unit": "%",
        "digits": 2,
        "source": "NY Fed / FRED EFFR",
        "evidence": "E1",
        "note": "政策利率的实际成交价，比目标区间更贴近市场。",
    },
    {
        "id": "fed.real_policy",
        "label": "实际政策利率（EFFR − 10Y 盈亏平衡）",
        "unit": "%",
        "digits": 2,
        "source": "EFFR / US10Y_BE",
        "evidence": "E2",
        "note": "格林斯潘式『实际资金成本』的日频代理。",
    },
    {
        "id": "fed.real10",
        "label": "10 年期实际利率（TIPS）",
        "unit": "%",
        "digits": 2,
        "source": "US10Y_REAL",
        "evidence": "E1",
        "note": "黄金与长久期资产的机会成本锚。",
    },
    {
        "id": "fed.real5",
        "label": "5 年期实际利率",
        "unit": "%",
        "digits": 2,
        "source": "US5Y_REAL",
        "evidence": "E1",
        "note": "对政策路径更敏感的中段实际利率。",
    },
    {
        "id": "fed.curve_2s10s",
        "label": "2s10s 期限利差",
        "unit": "bp",
        "digits": 0,
        "source": "US10Y − US2Y",
        "evidence": "E1",
        "note": "倒挂是紧缩末段的经典信号，转正往往伴随衰退确认。",
    },
    {
        "id": "fed.curve_5s30s",
        "label": "5s30s 期限利差",
        "unit": "bp",
        "digits": 0,
        "source": "US30Y − US5Y",
        "evidence": "E1",
        "note": "长端期限溢价的粗略代理。",
    },
    {
        "id": "fed.be10",
        "label": "10 年期盈亏平衡通胀",
        "unit": "%",
        "digits": 2,
        "source": "US10Y_BE",
        "evidence": "E2",
        "note": "市场定价的通胀预期，联储信誉的实时投票。",
    },
    {
        "id": "fed.be5",
        "label": "5 年期盈亏平衡通胀",
        "unit": "%",
        "digits": 2,
        "source": "US5Y_BE",
        "evidence": "E2",
        "note": "更贴近当前政策周期的通胀预期。",
    },
    {
        "id": "fed.sofr_effr",
        "label": "SOFR − EFFR 利差",
        "unit": "bp",
        "digits": 1,
        "source": "SOFR / EFFR",
        "evidence": "E1",
        "note": "回购市场相对政策利率的摩擦，融资压力的第一现场。",
    },
    {
        "id": "fed.dxy",
        "label": "美元指数（DXY）",
        "unit": "",
        "digits": 2,
        "source": "DXY",
        "evidence": "E1",
        "note": "金融条件的外部腿；强美元本身就在替联储紧缩。",
    },
    {
        "id": "fed.fci",
        "label": "金融条件指数（FCI，正=紧）",
        "unit": "σ",
        "digits": 2,
        "source": "SPX / DXY / US10Y_REAL / SOFR_EFFR 合成",
        "evidence": "E2",
        "note": "股指、美元、实际利率与融资利差的等权 z 分数。",
    },
    {
        "id": "fed.growth",
        "label": "增长代理（铜金比 z）",
        "unit": "σ",
        "digits": 2,
        "source": "CU / XAUUSD",
        "evidence": "E2",
        "note": "铜是增长、金是避险，比值是市场对增长的实时定价。",
    },
    {
        "id": "fed.inflation",
        "label": "通胀代理（盈亏平衡 z）",
        "unit": "σ",
        "digits": 2,
        "source": "US10Y_BE",
        "evidence": "E2",
        "note": "用市场通胀预期代替滞后的 CPI。",
    },
    {
        "id": "fed.spx_drawdown",
        "label": "标普 500 距 52 周高点回撤",
        "unit": "%",
        "digits": 1,
        "source": "SPX",
        "evidence": "E1",
        "note": "越大越接近『联储看跌期权』的行权区。",
    },
    {
        "id": "fed.spx_valuation",
        "label": "股指 / GDP 估值代理",
        "unit": "",
        "digits": 1,
        "source": "SPX / WB_US_GDP ×1e12",
        "evidence": "E4",
        "note": "不是市值/GDP，只是同向的粗略代理，用分位而非绝对值。",
    },
    {
        "id": "fed.ndx_ratio",
        "label": "纳指 / 标普 相对强弱",
        "unit": "",
        "digits": 3,
        "source": "NDX / SPX",
        "evidence": "E1",
        "note": "AI/科技拥挤度的代理；极端值意味着反转弹性大。",
    },
    {
        "id": "fed.gold_real_corr",
        "label": "黄金与实际利率 252 日相关性",
        "unit": "",
        "digits": 2,
        "source": "XAUUSD / US10Y_REAL 日收益",
        "evidence": "E2",
        "note": "正常为负；转正说明黄金在按『秩序风险』而非利率定价。",
    },
    {
        "id": "fed.unemployment",
        "label": "美国失业率（年度）",
        "unit": "%",
        "digits": 1,
        "source": "World Bank US unemployment",
        "evidence": "E1",
        "note": "年度数据，仅用于方向校验，不参与日频打分。",
    },
    {
        "id": "fed.payload",
        "label": "财政脉冲 / 赤字扩张",
        "unit": "",
        "digits": 2,
        "source": "缺：美国联邦赤字高频序列",
        "evidence": "E0",
        "note": "本地库有月度 MTS 赤字，但无季度财政脉冲口径。",
    },
    {
        "id": "fed.hy_oas",
        "label": "高收益债利差（HY OAS）",
        "unit": "bp",
        "digits": 0,
        "source": "缺：ICE BofA HY OAS",
        "evidence": "E0",
        "note": "信用市场是金融条件最灵敏的腿，本地库暂无。",
    },
    {
        "id": "fed.m2",
        "label": "M2 同比",
        "unit": "%",
        "digits": 1,
        "source": "缺：FRED M2SL",
        "evidence": "E0",
        "note": "货币数量论口径；伯南克-格林斯潘都强调其信号有限。",
    },
]

_META = {item["id"]: item for item in CATALOG}


def _reading(reading_id: str, series: pd.Series, **kwargs: Any) -> Reading:
    meta = _META[reading_id]
    kwargs.pop("digits", None)
    kwargs.pop("unit", None)
    return build_reading(
        reading_id,
        meta["label"],
        series,
        unit=meta.get("unit", ""),
        digits=int(meta.get("digits", 2)),
        source=meta.get("source", ""),
        evidence=meta.get("evidence", "E3"),
        note=meta.get("note", ""),
        **kwargs,
    )


def _missing(reading_id: str) -> Reading:
    meta = _META[reading_id]
    return Reading(
        id=reading_id,
        label=meta["label"],
        unit=meta.get("unit", ""),
        digits=int(meta.get("digits", 2)),
        source=meta.get("source", ""),
        evidence=meta.get("evidence", "E3"),
        note=meta.get("note", ""),
        missing_reason="本地库缺该序列，需新增数据源",
    )


def _low_freq(panel: Panel, code: str) -> pd.Series:
    """Low-frequency macro column carried forward to the next release."""
    if code not in panel.daily.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(panel.daily[code], errors="coerce").ffill()


def _composite(panel: Panel) -> pd.Series:
    spx = panel.series("SPX")
    dxy = panel.series("DXY")
    real10 = panel.series("US10Y_REAL")
    sofr_spread = panel.series("SOFR_EFFR")
    parts: list[pd.Series] = []
    if not spx.empty:
        parts.append(-z_series(spx.pct_change(63, fill_method=None)))
    if not dxy.empty:
        parts.append(z_series(dxy.pct_change(63, fill_method=None)))
    if not real10.empty:
        parts.append(z_series(real10.diff(63)))
    if not sofr_spread.empty:
        parts.append(z_series(sofr_spread))
    if not parts:
        return pd.Series(dtype="float64")
    frame = pd.concat(parts, axis=1)
    fci = frame.mean(axis=1, skipna=True)
    return fci.where(frame.notna().sum(axis=1) >= 2)


def build_readings(panel: Panel) -> list[Reading]:
    readings: list[Reading] = []
    effr = panel.series("EFFR")
    be10 = panel.series("US10Y_BE")
    real10 = panel.series("US10Y_REAL")
    us10 = panel.series("US10Y")
    us2 = panel.series("US2Y")
    us5 = panel.series("US5Y")
    us30 = panel.series("US30Y")

    readings.append(_reading("fed.effr", effr, change_days=63))
    readings.append(_reading("fed.real_policy", effr - be10, change_days=63))
    readings.append(_reading("fed.real10", real10, change_days=63))
    readings.append(_reading("fed.real5", panel.series("US5Y_REAL"), change_days=63))
    readings.append(_reading("fed.curve_2s10s", (us10 - us2) * 100, change_days=63))
    readings.append(_reading("fed.curve_5s30s", (us30 - us5) * 100, change_days=63))
    readings.append(_reading("fed.be10", be10, change_days=63))
    readings.append(_reading("fed.be5", panel.series("US5Y_BE"), change_days=63))
    readings.append(
        _reading("fed.sofr_effr", panel.series("SOFR_EFFR") * 100, change_days=21, change_label="1个月")
    )
    readings.append(_reading("fed.dxy", panel.series("DXY"), change_days=63))

    fci = _composite(panel)
    readings.append(_reading("fed.fci", fci, change_days=63, z_window=1260))

    copper_gold = ratio(panel, "CU", "XAUUSD")
    readings.append(_reading("fed.growth", z_series(copper_gold), change_days=63, digits=2))
    readings.append(_reading("fed.inflation", z_series(be10), change_days=63, digits=2))

    spx = panel.series("SPX")
    readings.append(
        _reading("fed.spx_drawdown", drawdown_pct(spx), change_days=21, change_label="1个月", digits=1)
    )

    gdp = _low_freq(panel, "WB_US_GDP")
    valuation = (spx / gdp.where(gdp > 0) * 1e12) if not spx.empty and not gdp.empty else pd.Series(dtype="float64")
    readings.append(_reading("fed.spx_valuation", valuation, change_days=252, change_label="1年", pct_window=2520))

    readings.append(_reading("fed.ndx_ratio", ratio(panel, "NDX", "SPX"), change_days=63))
    readings.append(
        _reading(
            "fed.gold_real_corr",
            rolling_corr(panel.series("XAUUSD"), real10, 252),
            change_days=63,
            pct_window=1260,
        )
    )

    unemployment = _low_freq(panel, "WB_US_UNEMPLOYMENT").dropna()
    if len(unemployment) > 4:
        unemployment = unemployment.copy()
        # annual series: a 4-observation change is the 12-month change.
        change = float(unemployment.iloc[-1] - unemployment.iloc[-5]) if len(unemployment) >= 5 else None
        last, asof = last_value(unemployment)
        readings.append(
            Reading(
                id="fed.unemployment",
                label=_META["fed.unemployment"]["label"],
                value=last,
                unit="%",
                digits=1,
                asof=asof,
                change=change,
                change_label="12个月",
                source=_META["fed.unemployment"]["source"],
                evidence="E1",
                note=_META["fed.unemployment"]["note"],
            )
        )
    else:
        readings.append(_missing("fed.unemployment"))

    for missing_id in ("fed.payload", "fed.hy_oas", "fed.m2"):
        readings.append(_missing(missing_id))
    return readings


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
        f"实际 10 年期利率 {_fmt(by_id['fed.real10'])}，2s10s {_fmt(by_id['fed.curve_2s10s'])}，"
        f"标普距高点回撤 {_fmt(by_id['fed.spx_drawdown'])}。"
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


def _fmt(reading: Reading) -> str:
    if reading.value is None:
        return "缺"
    suffix = reading.unit or ""
    return f"{reading.value:.{reading.digits}f}{suffix}"


def build_fed(panel: Panel) -> dict[str, Any]:
    readings = build_readings(panel)
    state = build_state(readings, panel)
    return {
        "readings": [reading.as_dict() for reading in readings],
        "metrics": metric_map(readings),
        "state": state,
        "catalog": CATALOG,
    }
