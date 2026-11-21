"""Fed lens catalog: reading metadata and catalog-bound helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.lens.common import Reading, missing_from_catalog, reading_from_catalog

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
    return reading_from_catalog(_META, reading_id, series, **kwargs)


def _missing(reading_id: str) -> Reading:
    return missing_from_catalog(_META, reading_id)
