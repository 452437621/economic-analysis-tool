"""Shared lens engine helpers: assets, scoring, warnings and observations."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cycle.market import Panel
from app.lens.common import evaluate_rule, load_gold_series
from app.models.v2 import Derivation
from app.provenance.engine import RunRecorder

METHOD_ENGINE = "lens.engine.v1"
METHOD_FED = "lens.fed.v1"
METHOD_SONG = "lens.song.v1"
METHOD_SYNTHESIS = "lens.synthesis.v1"
METHOD_MACRO = "lens.macro.v1"
METHOD_MICRO = "lens.micro.v1"
METHOD_PERSONA = "lens.persona.v1"

# 表达式求值需要的黄金实物列（面板里没有，来自 gold_metrics）。
GOLD_COLUMNS: tuple[str, ...] = (
    "GOLD_PRICE_USD",
    "CN_GOLD_PREMIUM_PCT",
    "COMEX_GOLD_BASIS_PCT",
    "SGE_GOLD_LEASE_3M_PCT",
    "GOLD_LEASE_PROXY_PCT",
    "CB_GOLD_GLOBAL_TONNES",
    "CN_GOLD_RESERVES_USD",
    "ETF_GLOBAL_TONNES",
    "COMEX_GOLD_INVENTORY_TONNES",
    "LBMA_GOLD_TONNES",
    "LBMA_SILVER_TONNES",
    "COT_MONEY_NET",
    "COT_SWAP_NET",
    "MM_BANK_GOLD_NET",
    "SHFE_GOLD_STOCK_TONNES",
    "ETF_FLOW_1M_TONNES",
    "GOLD_MOM_20D_PCT",
)

ASSETS: list[dict[str, str]] = [
    {"id": "us_equity", "label": "美股（标普 500）", "symbol": "SPX", "unit": "点", "note": "评分方向=指数涨跌"},
    {"id": "gold", "label": "黄金（XAUUSD）", "symbol": "XAUUSD", "unit": "美元/盎司", "note": "评分方向=金价涨跌"},
    {"id": "silver", "label": "白银（COMEX）", "symbol": "SI", "unit": "美元/盎司", "note": "评分方向=银价涨跌"},
    {"id": "usd", "label": "美元指数", "symbol": "DXY", "unit": "", "note": "评分方向=美元涨跌"},
    {"id": "cn_equity", "label": "A 股（沪深 300）", "symbol": "000300", "unit": "点", "note": "评分方向=指数涨跌"},
    {"id": "long_bond", "label": "美国 30 年期国债", "symbol": "US30Y", "unit": "%", "note": "评分方向=债券价格（收益率下行）"},
    {"id": "commodities", "label": "大宗商品（Brent）", "symbol": "BZ", "unit": "美元/桶", "note": "评分方向=油价涨跌"},
]
_ASSET_META = {item["id"]: item for item in ASSETS}


def _gold_metric_loader(session: Session):
    return lambda code: load_gold_series(session, code)


def _panel_summary(panel: Panel) -> dict[str, Any]:
    def _fmt(value: Any) -> str | None:
        if value is None:
            return None
        return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)[:10]

    return {"first": _fmt(panel.first), "last": _fmt(panel.last), "columns": len(panel.columns), "rows": int(len(panel.daily))}


def _curve_cross_up_metric(panel: Panel) -> dict[str, float | None]:
    curve = panel.series("US10Y") - panel.series("US2Y")
    if curve.empty:
        return {"value": None, "chg": None, "z": None, "pct": None}
    prior_negative = (curve < 0).rolling("126D", min_periods=1).max().shift(1)
    latest_positive = bool(curve.dropna().iloc[-1] >= 0) if not curve.dropna().empty else False
    prior = prior_negative.dropna()
    crossed = latest_positive and (not prior.empty) and bool(prior.iloc[-1])
    return {"value": 1.0 if crossed else 0.0, "chg": None, "z": None, "pct": None}


def _rule_severity(rule: dict[str, Any]) -> str:
    severity = str(rule.get("severity") or "info")
    return severity if severity in {"info", "watch", "warn", "critical"} else "info"


def _evaluate_rules(
    rules: list[dict[str, Any]], metrics: dict[str, dict[str, float | None]]
) -> list[dict[str, Any]]:
    evaluated = []
    for rule in rules:
        result = evaluate_rule(rule, metrics)
        result["severity"] = _rule_severity(rule)
        evaluated.append(result)
    return evaluated


def _record_rule_hits(rec: RunRecorder, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fired = []
    for rule in rules:
        if not rule.get("fired"):
            continue
        rec.record_rule(
            f"lens.{rule['id']}",
            str(rule.get("message") or rule.get("name") or ""),
            severity=str(rule.get("severity") or "info"),
            inputs={"trace": rule.get("trace"), "assets": rule.get("assets")},
            fired=True,
        )
        fired.append(rule)
    return fired


def _last_close(panel: Panel, symbol: str) -> float | None:
    series = panel.series(symbol)
    if series.empty:
        return None
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.iloc[-1]) if not clean.empty else None


def _lens_scores(lens_value: dict[str, Any]) -> dict[str, float | None]:
    """把一份透镜的资产评分摊平成 ``{asset_id: score}``。

    人物透镜与宏观/微观层的评分在顶层 ``scores``；美联储与宋鸿兵透镜的评分在
    ``state.asset_scores``，这里两种结构都接受，避免主透镜被静默排除在合成之外。
    """
    state = lens_value.get("state") or {}
    scores = (
        lens_value.get("scores")
        or lens_value.get("asset_scores")
        or state.get("scores")
        or state.get("asset_scores")
        or {}
    )
    out: dict[str, float | None] = {}
    for asset in ASSETS:
        item = scores.get(asset["id"]) or {}
        value = item.get("score")
        out[asset["id"]] = float(value) if value is not None else None
    return out


def _lens_label(lens_id: str, states: dict[str, dict[str, Any]]) -> str:
    state = states.get(lens_id) or {}
    return str(state.get("name") or lens_id)


def _agreement_multi(contributions: dict[str, float], consensus: float | None) -> tuple[str, str]:
    """多透镜一致度：同向且最小 |score| 足够大才算共振。"""
    if not contributions:
        return "数据不足", "flat"
    values = list(contributions.values())
    positives = [value for value in values if value >= 0.25]
    negatives = [value for value in values if value <= -0.25]
    if len(contributions) == 1:
        agreement = "单一透镜"
    elif len(positives) == len(values) and len(values) >= 2:
        agreement = "共振多" if min(values) >= 0.25 else "弱信号"
    elif len(negatives) == len(values) and len(values) >= 2:
        agreement = "共振空" if max(values) <= -0.25 else "弱信号"
    elif positives and negatives and min(max(positives), abs(min(negatives))) >= 0.35:
        agreement = "分歧"
    else:
        agreement = "弱信号"
    if len(values) >= 3 and agreement in {"共振多", "共振空"} and abs(consensus or 0.0) >= 0.6:
        agreement = "共振强信号"
    if consensus is None or abs(consensus) < 0.25:
        direction = "flat"
    elif consensus > 0:
        direction = "up"
    else:
        direction = "down"
    return agreement, direction


def _agreement(fed: float | None, song: float | None, consensus: float | None) -> tuple[str, str]:
    if fed is None or song is None:
        return "数据不足", "flat"
    return _agreement_multi({"fed": fed, "song": song}, consensus)


def _advice(agreement: str, consensus: float | None, lens_count: int = 2) -> str:
    if agreement == "共振强信号":
        return "多数透镜同向且强度足够：可按共识方向建仓，分批而非一次性。"
    if agreement == "共振多":
        return "多数透镜同向偏多：回调分批，不追高；跌破关键位再重估。"
    if agreement == "共振空":
        return "多数透镜同向偏空：反弹减仓，等右侧确认，不接下跌中的刀。"
    if agreement == "分歧":
        return "透镜之间方向冲突：只做区间或观望，等催化剂落地，不要用单一透镜下注。"
    if agreement == "数据不足":
        return "数据不足：不产生信号。"
    if agreement == "单一透镜":
        return "只有一套透镜覆盖该资产：只能作为研究结论，不单独构成仓位。"
    return "弱信号：观察，不建仓。"


def _divergence_catalyst(asset_id: str) -> str:
    return {
        "gold": "实际利率与央行购金/秩序溢价，谁在定价",
        "silver": "实物挤兑（COMEX 库存）与工业需求，谁先转向",
        "us_equity": "金融条件收紧是否传导到信用利差",
        "usd": "美国例外论与降息预期，谁主导",
        "cn_equity": "美元环流方向与国内政策脉冲，谁更强",
        "long_bond": "长端期限溢价与衰退定价，谁更快",
        "commodities": "供给冲击与全球增长，谁主导",
    }.get(asset_id, "下一个数据窗口")



def _warning_list(
    fed_state: dict[str, Any],
    song_state: dict[str, Any],
    states: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    heart = song_state.get("dollar_heart") or {}
    if heart.get("id") in {"angina", "infarction"}:
        warnings.append(
            {
                "id": "heart",
                "severity": "critical" if heart.get("id") == "infarction" else "warn",
                "title": f"美元心脏：{heart.get('label')}",
                "detail": heart.get("note"),
            }
        )
    harvest = song_state.get("harvest_risk")
    if harvest is not None and harvest >= 65:
        warnings.append(
            {
                "id": "harvest",
                "severity": "warn" if harvest < 80 else "critical",
                "title": f"收割风险 {harvest}/100",
                "detail": "强美元、实际利率上行、新兴市场回撤与汇率贬值同时出现，冷环流防御优先。",
            }
        )
    debt_risk = song_state.get("debt_risk")
    if debt_risk is not None and debt_risk >= 60:
        warnings.append(
            {
                "id": "debt",
                "severity": "warn",
                "title": f"债务货币化风险 {debt_risk}/100",
                "detail": "债务/GDP、赤字、利息占比与长端利率同向恶化，黄金的秩序溢价有基本面支撑。",
            }
        )
    put = fed_state.get("fed_put") or {}
    if put.get("id") in {"near", "in_the_money"}:
        warnings.append(
            {
                "id": "fed_put",
                "severity": "warn" if put.get("id") == "near" else "critical",
                "title": f"美联储看跌期权：{put.get('label')}",
                "detail": put.get("note"),
            }
        )
    stance = fed_state.get("stance")
    if stance is not None and stance >= 80:
        warnings.append(
            {
                "id": "tight",
                "severity": "warn",
                "title": f"政策立场极紧（{stance}/100）",
                "detail": "实际利率、金融条件与曲线同时处于紧缩端，风险资产的估值分母没有缓冲。",
            }
        )
    # 新增：宏观层风险标记 + 人物透镜的 critical 规则统一进预警台。
    for lens_id, state in (states or {}).items():
        if lens_id in {"fed", "song"}:
            continue
        name = str(state.get("name") or lens_id)
        for flag in state.get("flags") or []:
            warnings.append(
                {
                    "id": f"{lens_id}.{flag}",
                    "severity": "warn",
                    "title": f"{name}：{flag}",
                    "detail": state.get("narrative") or "",
                }
            )
        for rule in state.get("fired") or []:
            if rule.get("severity") not in {"warn", "critical"}:
                continue
            warnings.append(
                {
                    "id": f"{lens_id}.{rule.get('id')}",
                    "severity": rule.get("severity"),
                    "title": f"{name}：{rule.get('name') or rule.get('id')}",
                    "detail": rule.get("message") or "",
                }
            )
    return warnings


def _latest_cycle_context(session: Session) -> dict[str, Any] | None:
    row = session.scalar(
        select(Derivation)
        .where(Derivation.code == "cycle.state.world")
        .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
        .limit(1)
    )
    if row is None or not isinstance(row.value, dict):
        return None
    value = row.value
    return {
        "asof": row.asof.date().isoformat() if row.asof else None,
        "long_cycle": value.get("long_cycle"),
        "short_cycle": value.get("short_cycle"),
        "liquidity": value.get("liquidity"),
        "political": value.get("political"),
        "caveat": "来自 EPIC 周期引擎，仅作背景，不参与透镜打分。",
    }


def _observation_rows(
    fed_value: dict[str, Any],
    song_value: dict[str, Any],
    synth: dict[str, Any],
    today: date,
    extra_lenses: list[tuple[str, dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lenses = [("fed", fed_value), ("song", song_value), *(extra_lenses or [])]
    for lens_name, value in lenses:
        for reading in value.get("readings") or []:
            if reading.get("value") is None:
                continue
            rows.append(
                {
                    "code": f"lens.{lens_name}.{reading['id'].split('.', 1)[-1]}",
                    "asof": today,
                    "vintage_date": today,
                    "value": reading["value"],
                    "unit": reading.get("unit"),
                    "source": reading.get("source"),
                    "evidence_grade": reading.get("evidence", "E3"),
                    "extra": {
                        "z": reading.get("z"),
                        "pct": reading.get("percentile"),
                        "chg": reading.get("change"),
                    },
                }
            )
        lean = ((value.get("state") or {}).get("lean") or {}).get("score")
        if lean is not None:
            rows.append(
                {
                    "code": f"lens.{lens_name}.lean",
                    "asof": today,
                    "vintage_date": today,
                    "value": float(lean),
                    "unit": "score",
                    "source": f"lens.{lens_name}",
                    "evidence_grade": "E3",
                    "extra": {"label": ((value.get("state") or {}).get("lean") or {}).get("label")},
                }
            )
    for row in synth.get("assets") or []:
        if row.get("consensus") is None:
            continue
        rows.append(
            {
                "code": f"lens.score.{row['id']}",
                "asof": today,
                "vintage_date": today,
                "value": row["consensus"],
                "unit": "score",
                "source": "lens.synthesis",
                "evidence_grade": "E3",
                "extra": {"fed": row["fed"], "song": row["song"], "agreement": row["agreement"]},
            }
        )
    return rows


def _lens_confidence(value: dict[str, Any]) -> float:
    coverage = value.get("state", {}).get("coverage") or {}
    ratio = coverage.get("available", 0) / max(1, coverage.get("total", 1))
    return round(min(0.85, 0.35 + 0.45 * ratio), 3)


def _reading_steps(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": reading["id"],
            "value": reading.get("value"),
            "z": reading.get("z"),
            "pct": reading.get("percentile"),
            "missing": reading.get("missing_reason"),
        }
        for reading in readings
    ]


def _data_gaps(
    config: dict[str, Any],
    *reading_groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gaps = list(config.get("data_gaps") or [])
    known = {gap.get("id") for gap in gaps}
    for readings in reading_groups:
        for reading in readings:
            if reading.get("value") is not None or reading.get("id") in known:
                continue
            gaps.append(
                {
                    "id": reading["id"],
                    "label": reading.get("label"),
                    "reason": reading.get("missing_reason") or "本地库缺该序列",
                    "impact": "读数缺失，UI 已标注为不可用。",
                }
            )
    return gaps
