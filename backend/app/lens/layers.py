"""宏观层与微观层：把「人物透镜」下沉到可复用的两层结构。

用户要求「构建宏观、微观的经济分析逻辑」。这里的两层不是新的人，而是
所有透镜共用的**共同底座**：

* **宏观层（macro）**：增长、通胀、流动性、财政、融资压力、美元与曲线。
  它回答「这个经济体处在什么状态」，是每个透镜的输入。
* **微观层（micro）**：估值与趋势、跨资产比价、黄金微观结构（基差/溢价/
  租借/ETF）、持仓与汇率动量。它回答「价格已经定价到哪里」。

两层都产出与人物透镜同构的 ``readings / rules / scores``，于是合成器可以
对「宏观 × 微观 × 人物」做统一加权，而前端只需要一套渲染逻辑。
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from app.lens.common import build_reading, clamp, evaluate_rule, metric_map, round_opt, score_label
from app.lens.persona import TAIL_ROWS, evaluate_expression

log = logging.getLogger(__name__)

MACRO_READINGS: list[dict[str, Any]] = [
    {
        "id": "macro.growth_z",
        "label": "增长动能（铜金比 z）",
        "unit": "",
        "digits": 2,
        "expr": "z(CU / XAUUSD, 250)",
        "source": "沪铜 / 伦敦金现",
        "evidence": "E3",
        "note": "铜金比是市场对增长预期的即时投票，比宏观数据早 1–2 个季度。",
    },
    {
        "id": "macro.inflation_z",
        "label": "通胀预期 z",
        "unit": "",
        "digits": 2,
        "expr": "z(US10Y_BE, 250)",
        "source": "美国财政部 TIPS",
        "evidence": "E1",
        "note": "10 年期盈亏平衡通胀，市场定价的通胀中枢。",
    },
    {
        "id": "macro.real10",
        "label": "10 年期实际利率",
        "unit": "%",
        "digits": 2,
        "expr": "US10Y_REAL",
        "source": "美国财政部实际收益率曲线",
        "evidence": "E1",
    },
    {
        "id": "macro.real10_bp63",
        "label": "10 年期实际利率 3 个月变化",
        "unit": "bp",
        "digits": 0,
        "expr": "chg(US10Y_REAL, 63) * 100",
        "source": "美国财政部实际收益率曲线",
        "evidence": "E1",
    },
    {
        "id": "macro.net_liquidity",
        "label": "美元净流动性（Fed 资产−TGA−RRP）",
        "unit": "万亿美元",
        "digits": 2,
        "expr": "(US_FED_ASSETS - US_TGA - US_RRP_AMT) / 1e12",
        "source": "美联储 H.4.1 + NY Fed 逆回购",
        "evidence": "E1",
        "note": "德鲁肯米勒意义上的「净流动性」：私人部门手里的准备金，是风险资产的直接燃料。",
    },
    {
        "id": "macro.net_liquidity_pct",
        "label": "净流动性 13 周变化",
        "unit": "%",
        "digits": 1,
        "expr": "pct(US_FED_ASSETS - US_TGA - US_RRP_AMT, 91)",
        "source": "美联储 H.4.1 + NY Fed 逆回购",
        "evidence": "E1",
    },
    {
        "id": "macro.fiscal_impulse",
        "label": "财政脉冲（TTM 赤字/GDP）",
        "unit": "%",
        "digits": 1,
        "expr": "sum12(US_MTS_DEFICIT) / WB_US_GDP * 100",
        "source": "美国财政部 MTS + 世界银行",
        "evidence": "E2",
        "note": "TTM 口径：近 12 个月赤字合计 / 年度 GDP，消除单月季节性。",
    },
    {
        "id": "macro.interest_receipts",
        "label": "利息支出/财政收入（TTM）",
        "unit": "%",
        "digits": 1,
        "expr": "sum12(US_MTS_INTEREST) / sum12(US_MTS_RECEIPTS) * 100",
        "source": "美国财政部 MTS",
        "evidence": "E1",
    },
    {
        "id": "macro.funding_stress",
        "label": "融资市场压力（SOFR−EFFR）",
        "unit": "bp",
        "digits": 1,
        "expr": "SOFR_EFFR * 100",
        "source": "NY Fed",
        "evidence": "E1",
        "note": "回购市场的「心率杂音」：>15bp 意味着抵押品或准备金开始紧张。",
    },
    {
        "id": "macro.dxy_z",
        "label": "美元指数 z",
        "unit": "",
        "digits": 2,
        "expr": "z(DXY, 250)",
        "source": "美元指数",
        "evidence": "E1",
    },
    {
        "id": "macro.curve_30s10s",
        "label": "30Y−10Y 期限溢价",
        "unit": "bp",
        "digits": 0,
        "expr": "(US30Y - US10Y) * 100",
        "source": "美国财政部收益率曲线",
        "evidence": "E1",
    },
    {
        "id": "macro.curve_2s10s",
        "label": "10Y−2Y 利差",
        "unit": "bp",
        "digits": 0,
        "expr": "(US10Y - US2Y) * 100",
        "source": "美国财政部收益率曲线",
        "evidence": "E1",
    },
    {
        "id": "macro.m2_yoy",
        "label": "M2 同比",
        "unit": "%",
        "digits": 1,
        "expr": "yoy(US_M2)",
        "source": "美联储 H.6",
        "evidence": "E1",
        "note": "月频序列按日频前值填充，只做方向判断。",
    },
    {
        "id": "macro.cn_curve",
        "label": "中国 10Y−2Y 利差",
        "unit": "bp",
        "digits": 0,
        "expr": "(CN10Y - CN2Y) * 100",
        "source": "中国国债收益率",
        "evidence": "E1",
    },
]

MICRO_READINGS: list[dict[str, Any]] = [
    {
        "id": "micro.spx_dev200",
        "label": "标普偏离 200 日均线",
        "unit": "%",
        "digits": 1,
        "expr": "(SPX / ma(SPX, 200) - 1) * 100",
        "source": "标普 500",
        "evidence": "E1",
    },
    {
        "id": "micro.ndx_spx",
        "label": "纳指/标普比价",
        "unit": "",
        "digits": 3,
        "expr": "NDX / SPX",
        "source": "纳斯达克 100 / 标普 500",
        "evidence": "E1",
        "note": "集中度读数：比价越高，市场越依赖少数成长股。",
    },
    {
        "id": "micro.copper_gold_z",
        "label": "铜金比 z",
        "unit": "",
        "digits": 2,
        "expr": "z(CU / XAUUSD, 250)",
        "source": "沪铜 / 伦敦金现",
        "evidence": "E3",
    },
    {
        "id": "micro.oil_gold_z",
        "label": "油金比 z",
        "unit": "",
        "digits": 2,
        "expr": "z(BZ / XAUUSD, 250)",
        "source": "Brent / 伦敦金现",
        "evidence": "E3",
    },
    {
        "id": "micro.gold_silver",
        "label": "金银比",
        "unit": "",
        "digits": 1,
        "expr": "XAUUSD / SI",
        "source": "伦敦金现 / COMEX 白银",
        "evidence": "E1",
        "note": ">85 通常是白银相对便宜与风险偏好收缩同时出现的区间。",
    },
    {
        "id": "micro.comex_basis",
        "label": "COMEX 黄金基差",
        "unit": "%",
        "digits": 2,
        "expr": "COMEX_GOLD_BASIS_PCT",
        "source": "COMEX 库存与现货",
        "evidence": "E2",
    },
    {
        "id": "micro.cn_premium",
        "label": "中国黄金溢价",
        "unit": "%",
        "digits": 2,
        "expr": "CN_GOLD_PREMIUM_PCT",
        "source": "上海黄金交易所",
        "evidence": "E2",
    },
    {
        "id": "micro.gold_lease",
        "label": "黄金 3M 租借利率",
        "unit": "%",
        "digits": 2,
        "expr": "SGE_GOLD_LEASE_3M_PCT",
        "source": "上海黄金交易所",
        "evidence": "E2",
    },
    {
        "id": "micro.etf_flow",
        "label": "全球黄金 ETF 持仓 3 个月变化",
        "unit": "%",
        "digits": 1,
        "expr": "pct(ETF_GLOBAL_TONNES, 63)",
        "source": "全球黄金 ETF 持仓",
        "evidence": "E2",
    },
    {
        "id": "micro.cot_money_z",
        "label": "管理基金黄金净多 z",
        "unit": "",
        "digits": 2,
        "expr": "z(COT_MONEY_NET, 156)",
        "source": "CFTC 持仓报告",
        "evidence": "E2",
    },
    {
        "id": "micro.usdjpy_chg20",
        "label": "美元/日元 20 日变化",
        "unit": "%",
        "digits": 2,
        "expr": "pct(USDJPY, 20)",
        "source": "美元/日元",
        "evidence": "E1",
    },
    {
        "id": "micro.cnh_chg20",
        "label": "美元/离岸人民币 20 日变化",
        "unit": "%",
        "digits": 2,
        "expr": "pct(USDCNH, 20)",
        "source": "美元/离岸人民币",
        "evidence": "E1",
    },
    {
        "id": "micro.csi_mom20",
        "label": "沪深 300 20 日动量",
        "unit": "%",
        "digits": 2,
        "expr": "pct(000300, 20)",
        "source": "沪深 300",
        "evidence": "E1",
    },
    {
        "id": "micro.us30y_dev250",
        "label": "30 年期美债收益率分位",
        "unit": "",
        "digits": 1,
        "expr": "pctile(US30Y, 2500)",
        "source": "美国财政部收益率曲线",
        "evidence": "E1",
    },
]


def build_frame(panel, gold_extras: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    """面板 → 表达式求值用的宽表（尾部窗口 + 低频序列前值填充）。"""
    if panel is None or getattr(panel, "daily", None) is None or panel.daily.empty:
        return pd.DataFrame()
    frame = panel.daily.tail(TAIL_ROWS).copy()
    for code, series in (gold_extras or {}).items():
        if series is None or series.empty:
            continue
        data = pd.to_numeric(series, errors="coerce")
        index = pd.to_datetime(data.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_convert("UTC").tz_localize(None)
        data.index = index.normalize()
        data = data[~data.index.duplicated(keep="last")].sort_index()
        frame[str(code)] = data.reindex(frame.index).ffill(limit=40)
    # 宏观低频序列（月度/年度/周度）需要长前值填充，否则同一条序列在日频
    # 面板上只有发布当天有值，任何比值表达式都会塌成 NaN。
    return frame.ffill(limit=800)


def _metric(metrics: dict[str, dict[str, float | None]], key: str, field: str = "value") -> float | None:
    return (metrics.get(key) or {}).get(field)


def _direction(value: float | None, threshold: float, above: str, below: str) -> str:
    if value is None:
        return "数据不足"
    return above if value >= threshold else below


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
