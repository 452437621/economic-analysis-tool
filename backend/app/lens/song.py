"""Song Hongbing / 《货币战争》 lens.

The lens is built around the one variable Song keeps returning to: the
*temperature of the dollar circulation*.  Assets are functions of that
temperature, and the temperature itself is read at two places:

* the dollar's external price (DXY percentile / momentum / real yields), and
* the dollar's "heart" — the repo market (SOFR vs EFFR, SOFR spikes).

A second, independent chain (debt monetisation + gold's entropy premium) is
kept separate on purpose: Song himself treats gold as the scale of *global
disorder*, not as a risk-on/risk-off asset.
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
    percentile_last,
    ratio,
    rolling_corr,
    score_label,
    ttm,
    z_series,
)

CATALOG: list[dict[str, Any]] = [
    {
        "id": "song.dxy",
        "label": "美元指数（DXY）",
        "unit": "",
        "digits": 2,
        "source": "DXY",
        "evidence": "E1",
        "note": "环流温度的第一读数；宋的框架里弱美元=热环流。",
    },
    {
        "id": "song.dxy_pct",
        "label": "DXY 250 日分位",
        "unit": "%",
        "digits": 0,
        "source": "DXY",
        "evidence": "E2",
        "note": "用分位而不是绝对水平，避免长期中枢漂移。",
    },
    {
        "id": "song.dxy_yoy",
        "label": "DXY 同比",
        "unit": "%",
        "digits": 1,
        "source": "DXY",
        "evidence": "E1",
        "note": "潮汐方向的主读数。",
    },
    {
        "id": "song.real10",
        "label": "10 年期实际利率",
        "unit": "%",
        "digits": 2,
        "source": "US10Y_REAL",
        "evidence": "E1",
        "note": "黄金的利率锚；秩序正常时有效，秩序危机时失效。",
    },
    {
        "id": "song.debt_gdp",
        "label": "美国联邦债务 / GDP",
        "unit": "%",
        "digits": 1,
        "source": "US_FED_DEBT / WB_US_GDP",
        "evidence": "E2",
        "note": "宋『2035 美元崩溃论』的分母；本库债务序列仅约 3 个月，趋势需外部数据。",
    },
    {
        "id": "song.deficit_gdp",
        "label": "美国财政赤字 / GDP（TTM）",
        "unit": "%",
        "digits": 2,
        "source": "US_MTS_DEFICIT / WB_US_GDP",
        "evidence": "E2",
        "note": "货币是欠条：赤字是美元供给的财政源头。",
    },
    {
        "id": "song.interest_receipts",
        "label": "联邦利息支出 / 财政收入（TTM）",
        "unit": "%",
        "digits": 1,
        "source": "US_MTS_INTEREST / US_MTS_RECEIPTS",
        "evidence": "E2",
        "note": "宋 2011 年模型的核心变量；46% 是其 2035 年终局阈值。",
    },
    {
        "id": "song.gold",
        "label": "黄金（XAUUSD）",
        "unit": "",
        "digits": 2,
        "source": "XAUUSD",
        "evidence": "E1",
        "note": "秩序熵值的计价器。",
    },
    {
        "id": "song.gold_silver",
        "label": "金银比",
        "unit": "",
        "digits": 1,
        "source": "XAUUSD / SI",
        "evidence": "E1",
        "note": "宋的历史锚是 16:1；高于 85 视为白银相对低估（但可能长期化）。",
    },
    {
        "id": "song.copper_gold",
        "label": "铜金比",
        "unit": "",
        "digits": 3,
        "source": "CU / XAUUSD",
        "evidence": "E2",
        "note": "增长与避险的跷跷板。",
    },
    {
        "id": "song.oil_gold",
        "label": "油金比",
        "unit": "",
        "digits": 3,
        "source": "BZ / XAUUSD",
        "evidence": "E2",
        "note": "通胀冲击与货币贬值谁在主导。",
    },
    {
        "id": "song.gold_corr",
        "label": "黄金与实际利率 252 日相关性",
        "unit": "",
        "digits": 2,
        "source": "XAUUSD / US10Y_REAL 日收益",
        "evidence": "E2",
        "note": "转正=『秩序溢价』模式，宋的黄金逻辑与利率脱钩。",
    },
    {
        "id": "song.cn_premium",
        "label": "中国黄金溢价",
        "unit": "%",
        "digits": 2,
        "source": "GoldMetric CN_GOLD_PREMIUM_PCT",
        "evidence": "E2",
        "note": "境内实物需求/管制溢价的温度计。",
    },
    {
        "id": "song.cn_reserves_yoy",
        "label": "中国央行黄金储备同比",
        "unit": "%",
        "digits": 1,
        "source": "GoldMetric CN_GOLD_RESERVES_USD",
        "evidence": "E1",
        "note": "去美元化的硬证据；月度数据。",
    },
    {
        "id": "song.cb_gold",
        "label": "全球央行黄金储备",
        "unit": "吨",
        "digits": 0,
        "source": "GoldMetric CB_GOLD_GLOBAL_TONNES",
        "evidence": "E1",
        "note": "季度数据；央行购金是宋黄金长牛的核心支柱。",
    },
    {
        "id": "song.comex_gold_flow",
        "label": "COMEX 黄金库存 20 日净流量",
        "unit": "吨",
        "digits": 1,
        "source": "GoldMetric COMEX_GOLD_INVENTORY_TONNES",
        "evidence": "E2",
        "note": "实物挤兑的黄金版；白银库存序列缺失（S9 无法计算）。",
    },
    {
        "id": "song.gold_lease",
        "label": "SGE 黄金 3 个月租借利率",
        "unit": "%",
        "digits": 2,
        "source": "GoldMetric SGE_GOLD_LEASE_3M_PCT",
        "evidence": "E2",
        "note": "实物紧张程度；宋的白银挤兑框架在黄金上的对应读数。",
    },
    {
        "id": "song.usdcnh",
        "label": "USDCNH",
        "unit": "",
        "digits": 3,
        "source": "USDCNH",
        "evidence": "E1",
        "note": "人民币汇率是热钱三段式的第二段。",
    },
    {
        "id": "song.em_relative",
        "label": "恒生 / 标普 相对强弱",
        "unit": "",
        "digits": 3,
        "source": "HSI / SPX",
        "evidence": "E2",
        "note": "新兴市场相对美国的资金流向。",
    },
    {
        "id": "song.csi_spx",
        "label": "沪深 300 / 标普 相对强弱",
        "unit": "",
        "digits": 3,
        "source": "000300 / SPX",
        "evidence": "E2",
        "note": "A 股热钱三段式的相对定价读数。",
    },
    {
        "id": "song.us10y",
        "label": "美国 10 年期国债收益率",
        "unit": "%",
        "digits": 2,
        "source": "US10Y",
        "evidence": "E1",
        "note": "『60 年大轮回』的读数；本库仅约 5 年历史，分位是 5 年分位。",
    },
    {
        "id": "song.us10y_pct",
        "label": "10Y 美债 5 年分位",
        "unit": "%",
        "digits": 0,
        "source": "US10Y",
        "evidence": "E2",
        "note": "60 年分位数据缺失，用 5 年分位代替并明确标注。",
    },
    {
        "id": "song.jp30y",
        "label": "日本 30 年期国债收益率",
        "unit": "%",
        "digits": 2,
        "source": "JP30Y",
        "evidence": "E1",
        "note": "欧美日国债同步入冬的第三个样本。",
    },
    {
        "id": "song.sofr_effr",
        "label": "SOFR − EFFR 利差",
        "unit": "bp",
        "digits": 1,
        "source": "SOFR / EFFR",
        "evidence": "E1",
        "note": "『美元心脏』的温度计。",
    },
    {
        "id": "song.sofr_spike",
        "label": "SOFR − EFFR 5 日脉冲",
        "unit": "bp",
        "digits": 1,
        "source": "SOFR / EFFR",
        "evidence": "E2",
        "note": "宋所说的『心绞痛』：脉冲式跳升比水平更重要。",
    },
    {
        "id": "song.dxy_us10y_corr",
        "label": "DXY 与 10Y 美债 60 日相关性",
        "unit": "",
        "digits": 2,
        "source": "DXY / US10Y 日收益",
        "evidence": "E2",
        "note": "2025-04-07 宋所称的『脱钩』；持续为负意味着避险锚迁移。",
    },
    {
        "id": "song.geo_divergence",
        "label": "油金背离（地缘溢价代理）",
        "unit": "σ",
        "digits": 2,
        "source": "BZ / XAUUSD 21 日收益 z 差",
        "evidence": "E4",
        "note": "油强金弱=避险被压制；2026-03 伊朗战争后的形态。",
    },
    {
        "id": "song.us_cpi",
        "label": "美国 CPI 同比（年度）",
        "unit": "%",
        "digits": 1,
        "source": "World Bank US CPI",
        "evidence": "E1",
        "note": "年度数据，只用于长周期校验。",
    },
    {
        "id": "song.reserve_share",
        "label": "美元全球外储份额",
        "unit": "%",
        "digits": 1,
        "source": "缺：IMF COFER",
        "evidence": "E0",
        "note": "去美元化斜率的关键分母，本地库缺失。",
    },
    {
        "id": "song.comex_silver",
        "label": "COMEX 白银库存 20 日净流出",
        "unit": "百万盎司",
        "digits": 1,
        "source": "缺：CME 白银库存",
        "evidence": "E0",
        "note": "宋 S9 规则（20 日 ≥5000 万盎司）直接依赖，本地库缺失。",
    },
    {
        "id": "song.cips",
        "label": "CIPS 日均处理金额",
        "unit": "亿元",
        "digits": 0,
        "source": "缺：CIPS 月报",
        "evidence": "E0",
        "note": "金融高边疆落地进度，需手工月更。",
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
    if code not in panel.daily.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(panel.daily[code], errors="coerce").ffill()


def _yoy_pct(series: pd.Series, periods: int | None = None) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    if periods is None:
        # daily series -> 252 observations; monthly/quarterly passed explicitly.
        periods = 252
    if len(clean) <= periods:
        return None
    base = float(clean.iloc[-1 - periods])
    if base == 0:
        return None
    return (float(clean.iloc[-1]) / base - 1.0) * 100.0


def build_readings(panel: Panel, gold_metric) -> list[Reading]:
    """``gold_metric`` is a callable ``code -> pd.Series`` bound to the session."""
    readings: list[Reading] = []
    dxy = panel.series("DXY")
    readings.append(_reading("song.dxy", dxy, change_days=63))

    dxy_pct = percentile_last(dxy, 252, min_obs=120)
    if dxy_pct is not None:
        readings.append(
            Reading(
                id="song.dxy_pct",
                label=_META["song.dxy_pct"]["label"],
                value=dxy_pct * 100,
                unit="%",
                digits=0,
                asof=last_value(dxy)[1],
                source=_META["song.dxy_pct"]["source"],
                evidence="E2",
                note=_META["song.dxy_pct"]["note"],
            )
        )
    else:
        readings.append(_missing("song.dxy_pct"))

    readings.append(
        Reading(
            id="song.dxy_yoy",
            label=_META["song.dxy_yoy"]["label"],
            value=_yoy_pct(dxy),
            unit="%",
            digits=1,
            asof=last_value(dxy)[1],
            source=_META["song.dxy_yoy"]["source"],
            evidence="E1",
            note=_META["song.dxy_yoy"]["note"],
        )
    )

    real10 = panel.series("US10Y_REAL")
    readings.append(_reading("song.real10", real10, change_days=252, change_label="1年"))

    gdp = _low_freq(panel, "WB_US_GDP")
    debt = _low_freq(panel, "US_FED_DEBT")
    if not gdp.empty and not debt.empty:
        debt_gdp = debt / gdp.where(gdp > 0) * 100
        readings.append(_reading("song.debt_gdp", debt_gdp, change_days=63, pct_window=2520))
    else:
        readings.append(_missing("song.debt_gdp"))

    deficit = _low_freq(panel, "US_MTS_DEFICIT")
    if not gdp.empty and not deficit.empty:
        deficit_gdp = ttm(deficit) / gdp.where(gdp > 0) * 100
        readings.append(_reading("song.deficit_gdp", deficit_gdp, change_days=63, pct_window=2520))
    else:
        readings.append(_missing("song.deficit_gdp"))

    interest = _low_freq(panel, "US_MTS_INTEREST")
    receipts = _low_freq(panel, "US_MTS_RECEIPTS")
    if not interest.empty and not receipts.empty:
        ratio_series = ttm(interest) / ttm(receipts).where(ttm(receipts) > 0) * 100
        readings.append(
            _reading("song.interest_receipts", ratio_series, change_days=63, pct_window=2520)
        )
    else:
        readings.append(_missing("song.interest_receipts"))

    gold = panel.series("XAUUSD")
    readings.append(_reading("song.gold", gold, change_days=252, change_label="1年"))
    readings.append(_reading("song.gold_silver", ratio(panel, "XAUUSD", "SI"), change_days=63))
    readings.append(_reading("song.copper_gold", ratio(panel, "CU", "XAUUSD"), change_days=126, change_label="6个月"))
    readings.append(_reading("song.oil_gold", ratio(panel, "BZ", "XAUUSD"), change_days=126, change_label="6个月"))
    readings.append(
        _reading(
            "song.gold_corr",
            rolling_corr(gold, real10, 252),
            change_days=63,
            pct_window=1260,
        )
    )

    premium = gold_metric("CN_GOLD_PREMIUM_PCT")
    readings.append(_reading("song.cn_premium", premium, change_days=63, pct_window=2520))

    reserves = gold_metric("CN_GOLD_RESERVES_USD")
    yoy = _yoy_pct(reserves, 12)
    if yoy is not None:
        readings.append(
            Reading(
                id="song.cn_reserves_yoy",
                label=_META["song.cn_reserves_yoy"]["label"],
                value=yoy,
                unit="%",
                digits=1,
                asof=last_value(reserves)[1],
                change=yoy,
                change_label="12个月",
                source=_META["song.cn_reserves_yoy"]["source"],
                evidence="E1",
                note=_META["song.cn_reserves_yoy"]["note"],
            )
        )
    else:
        readings.append(_missing("song.cn_reserves_yoy"))

    cb_gold = gold_metric("CB_GOLD_GLOBAL_TONNES")
    readings.append(_reading("song.cb_gold", cb_gold, change_days=365, change_label="4个季度"))

    comex = gold_metric("COMEX_GOLD_INVENTORY_TONNES")
    if not comex.empty and len(comex.dropna()) > 20:
        flow = comex.dropna() - comex.dropna().shift(20)
        readings.append(
            _reading("song.comex_gold_flow", flow, change_days=20, change_label="20日")
        )
    else:
        readings.append(_missing("song.comex_gold_flow"))

    lease = gold_metric("SGE_GOLD_LEASE_3M_PCT")
    readings.append(_reading("song.gold_lease", lease, change_days=63))

    readings.append(_reading("song.usdcnh", panel.series("USDCNH"), change_days=63))
    readings.append(
        _reading("song.em_relative", ratio(panel, "HSI", "SPX"), change_days=126, change_label="6个月")
    )
    readings.append(
        _reading("song.csi_spx", ratio(panel, "000300", "SPX"), change_days=126, change_label="6个月")
    )

    us10 = panel.series("US10Y")
    readings.append(_reading("song.us10y", us10, change_days=252, change_label="1年"))
    us10_pct = percentile_last(us10, 1260, min_obs=250)
    if us10_pct is not None:
        readings.append(
            Reading(
                id="song.us10y_pct",
                label=_META["song.us10y_pct"]["label"],
                value=us10_pct * 100,
                unit="%",
                digits=0,
                asof=last_value(us10)[1],
                source=_META["song.us10y_pct"]["source"],
                evidence="E2",
                note=_META["song.us10y_pct"]["note"],
            )
        )
    else:
        readings.append(_missing("song.us10y_pct"))

    readings.append(_reading("song.jp30y", panel.series("JP30Y"), change_days=252, change_label="1年"))

    spread = panel.series("SOFR_EFFR") * 100
    readings.append(_reading("song.sofr_effr", spread, change_days=21, change_label="1个月"))
    if not spread.empty:
        spike_series = spread - spread.shift(5)
        readings.append(
            _reading("song.sofr_spike", spike_series, change_days=21, change_label="1个月")
        )
    else:
        readings.append(_missing("song.sofr_spike"))

    corr = rolling_corr(panel.series("DXY"), us10, 60)
    readings.append(_reading("song.dxy_us10y_corr", corr, change_days=63, pct_window=1260))

    oil_ret = panel.series("BZ").pct_change(21, fill_method=None)
    gold_ret = gold.pct_change(21, fill_method=None)
    geo = z_series(oil_ret) - z_series(gold_ret)
    readings.append(_reading("song.geo_divergence", geo, change_days=21, change_label="1个月"))

    cpi = _low_freq(panel, "WB_US_CPI").dropna()
    readings.append(_reading("song.us_cpi", cpi, change_days=365, change_label="1年"))

    for missing_id in ("song.reserve_share", "song.comex_silver", "song.cips"):
        readings.append(_missing(missing_id))
    return readings


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
        f"同比 {_fmt(by_id['song.dxy_yoy'])}。"
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


def _fmt(reading: Reading) -> str:
    if reading.value is None:
        return "缺"
    suffix = reading.unit or ""
    return f"{reading.value:.{reading.digits}f}{suffix}"


def build_song(panel: Panel, gold_metric) -> dict[str, Any]:
    readings = build_readings(panel, gold_metric)
    state = build_state(readings, panel)
    return {
        "readings": [reading.as_dict() for reading in readings],
        "metrics": metric_map(readings),
        "state": state,
        "catalog": CATALOG,
    }
