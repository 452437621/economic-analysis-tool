"""Two-lens engine: compute readings, evaluate rules, synthesise, persist.

The engine is a pure "read local panel → compute → record" pipeline.  It never
fetches data, so a run is reproducible from the database snapshot and every
derivation carries the code hash of the lens modules that produced it.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cycle.market import Panel, load_panel
from app.lens import fed as fed_lens
from app.lens import layers as layer_builder
from app.lens import persona as persona_engine
from app.lens import position as position_engine
from app.lens import song as song_lens
from app.lens.common import evaluate_rule, load_gold_series, round_opt as _round, score_label
from app.models.v2 import Derivation, Forecast
from app.provenance.engine import RunRecorder, aware, new_id, record_observations

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "lens.yaml"
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


@lru_cache(maxsize=4)
def _load_config_cached(path: str, mtime: float) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_config() -> dict[str, Any]:
    stat = CONFIG_PATH.stat()
    return _load_config_cached(str(CONFIG_PATH), stat.st_mtime)


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


def run_lenses(session: Session, asof: datetime | None = None) -> dict[str, Any]:
    """Run both lenses, persist run/steps/derivations/rules/observations."""
    config = load_config()
    now = datetime.now(timezone.utc)
    today = (asof or now).date()
    rec = RunRecorder(session, kind="lens", subject="all", method_id=METHOD_ENGINE, code_version="lens-1.0")
    rec.start()
    try:
        with rec.step("load_panel", kind="fetch") as step:
            panel = load_panel(session)
            step.outputs = _panel_summary(panel)
            if panel.daily.empty:
                rec.degrade("lens.panel.empty", "本地面板为空：没有宏观序列或日线数据。", severity="critical")

        gold_metric = _gold_metric_loader(session)
        with rec.step("fed_readings", kind="compute") as step:
            fed_value = fed_lens.build_fed(panel)
            step.outputs = {
                "readings": len(fed_value["readings"]),
                "available": fed_value["state"]["coverage"]["available"],
                "stance": fed_value["state"]["stance"],
            }
            if fed_value["state"]["coverage"]["available"] < 8:
                rec.degrade("lens.fed.coverage", "美联储透镜可用读数不足 8 条。")

        with rec.step("song_readings", kind="compute") as step:
            song_value = song_lens.build_song(panel, gold_metric)
            step.outputs = {
                "readings": len(song_value["readings"]),
                "available": song_value["state"]["coverage"]["available"],
                "phase": song_value["state"]["phase"]["label"],
            }
            if song_value["state"]["coverage"]["available"] < 8:
                rec.degrade("lens.song.coverage", "宋鸿兵透镜可用读数不足 8 条。")

        with rec.step("macro_layer", kind="compute") as step:
            gold_extras = {code: gold_metric(code) for code in GOLD_COLUMNS}
            frame = layer_builder.build_frame(panel, gold_extras)
            macro_value = layer_builder.build_macro_layer(frame, config.get("macro_rules") or [])
            step.outputs = {
                "readings": len(macro_value["readings"]),
                "available": macro_value["state"].get("coverage", {}).get("available"),
                "regime": macro_value["state"]["regime"]["label"],
                "flags": len(macro_value["state"]["flags"]),
            }

        with rec.step("micro_layer", kind="compute") as step:
            micro_value = layer_builder.build_micro_layer(frame, config.get("micro_rules") or [])
            step.outputs = {
                "readings": len(micro_value["readings"]),
                "available": micro_value["state"].get("coverage", {}).get("available"),
                "crowding": len(micro_value["state"]["crowding"]),
            }

        with rec.step("persona_lenses", kind="compute") as step:
            personas = persona_engine.build_personas(frame)
            available = [
                {"id": item["id"], "name": item["name"], "lean": item["state"]["lean"],
                 "fired": item["state"]["fired_rules"]}
                for item in personas
            ]
            step.outputs = {"count": len(personas), "personas": available}
            if not personas:
                rec.degrade("lens.persona.none", "未发现 config/personas/*.yaml，人物透镜被跳过。")
            for item in personas:
                coverage = item["state"]["coverage"]
                if coverage.get("total") and coverage["available"] < coverage["total"] * 0.5:
                    rec.degrade(
                        f"lens.persona.{item['id']}.coverage",
                        f"{item['name']} 透镜可用读数不足一半（{coverage['available']}/{coverage['total']}）。",
                    )


            metrics: dict[str, dict[str, float | None]] = {
            **fed_value["metrics"],
            **song_value["metrics"],
            "fed.curve_cross_up": _curve_cross_up_metric(panel),
            "fed.put_distance": {
                "value": fed_value["state"]["fed_put"].get("distance_pct"),
                "chg": None,
                "z": None,
                "pct": None,
            },
        }

        with rec.step("evaluate_rules", kind="rules") as step:
            fed_rules = _evaluate_rules(config.get("fed_rules") or [], metrics)
            song_rules = _evaluate_rules(config.get("song_rules") or [], metrics)
            step.outputs = {
                "fed": {"total": len(fed_rules), "fired": sum(1 for rule in fed_rules if rule["fired"])},
                "song": {"total": len(song_rules), "fired": sum(1 for rule in song_rules if rule["fired"])},
            }
            _record_rule_hits(rec, fed_rules)
            _record_rule_hits(rec, song_rules)
            # 宏观层、微观层与人物透镜的命中规则同样写进 RuleHit，
            # 这样 /pipeline、预警台与证据抽屉能看到完整的规则证据链。
            _record_rule_hits(rec, macro_value.get("rules") or [])
            _record_rule_hits(rec, micro_value.get("rules") or [])
            for item in personas:
                _record_rule_hits(rec, item.get("rules") or [])

        with rec.step("synthesise", kind="compute") as step:
            cycle_context = _latest_cycle_context(session)
            lens_scores: dict[str, dict[str, float | None]] = {
                "fed": _lens_scores(fed_value),
                "song": _lens_scores(song_value),
                "macro": _lens_scores(macro_value),
                "micro": _lens_scores(micro_value),
            }
            lens_states: dict[str, dict[str, Any]] = {
                "fed": fed_value["state"],
                "song": song_value["state"],
                "macro": macro_value["state"],
                "micro": micro_value["state"],
            }
            for item in personas:
                lens_scores[item["id"]] = _lens_scores(item)
                lens_states[item["id"]] = item["state"]
            synth_value = _synthesis(lens_scores, panel, config, cycle_context, lens_states)
            synth_value["rule_metrics"] = metrics
            # 只读接口要能重建全部规则（含未命中/缺数据），因此把每层的 metrics
            # 与人物透镜摘要一并写进合成推导的 value。
            synth_value["layer_metrics"] = {
                "macro": macro_value["metrics"],
                "micro": micro_value["metrics"],
                "personas": {item["id"]: item["metrics"] for item in personas},
            }
            synth_value["personas"] = [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "title": item.get("title"),
                    "school": item.get("school"),
                    "key_question": item.get("key_question"),
                    "thesis": item.get("thesis"),
                    "state": item["state"],
                    "scores": item.get("scores"),
                    "readings": item.get("readings"),
                    "catalog": item.get("catalog"),
                }
                for item in personas
            ]
            step.outputs = {
                "lenses": synth_value["lens_count"],
                "consensus": synth_value["consensus_count"],
                "strong": synth_value["strong_count"],
                "divergences": len(synth_value["divergences"]),
                "confidence": synth_value["confidence"],
                "gross_weight_pct": synth_value["portfolio"]["gross_weight_pct"],
                "portfolio_risk_pct": synth_value["portfolio"]["portfolio_risk_pct"],
            }

        with rec.step("persist", kind="write") as step:
            fired_fed = [rule for rule in fed_rules if rule["fired"]]
            fired_song = [rule for rule in song_rules if rule["fired"]]
            fed_deriv = rec.derive(
                code="lens.fed.state",
                claim=(
                    f"美联储透镜：{fed_value['state']['stance_label']}"
                    f"（{fed_value['state']['stance'] if fed_value['state']['stance'] is not None else '—'}/100），"
                    f"{fed_value['state']['regime']['label']}，看跌期权{fed_value['state']['fed_put']['label']}"
                ),
                value=fed_value,
                confidence=_lens_confidence(fed_value),
                evidence_grade="E2",
                subject="lens.fed",
                method_id=METHOD_FED,
                inputs=["DXY", "US10Y_REAL", "US10Y_BE", "EFFR", "SOFR_EFFR", "SPX", "CU", "XAUUSD", "US10Y", "US2Y"],
                steps=_reading_steps(fed_value["readings"]),
                rules_hit=[
                    {"id": rule["id"], "message": rule["message"], "severity": rule["severity"]}
                    for rule in fired_fed
                ],
                caveats=[
                    "10Y 实际利率本地仅约 5 年历史，分位口径为 5 年而非 20 年。",
                    "HY OAS 与 M2 缺失，金融条件指数没有信用腿，灵敏度低于完整 FCI。",
                    "失业率为年度数据，仅作方向校验，不参与日频打分。",
                ],
                falsifiers=[
                    "若未来 3 个月实际利率下行 >50bp 而金价不涨，F1 的方向映射失效。",
                    "若标普回撤 ≥10% 但联储连续两次会议明确排除宽松，F6 失效（2022 年型）。",
                ],
                opposing=["2022 年式通胀二次上行会让联储放弃看跌期权，宽松交易失败。"],
            )
            song_deriv = rec.derive(
                code="lens.song.state",
                claim=(
                    f"宋鸿兵透镜：美元环流「{song_value['state']['phase']['label']}」，"
                    f"美元心脏「{song_value['state']['dollar_heart']['label']}」，"
                    f"黄金状态「{song_value['state']['gold_regime']['label']}」"
                ),
                value=song_value,
                confidence=_lens_confidence(song_value),
                evidence_grade="E3",
                subject="lens:song",
                method_id=METHOD_SONG,
                inputs=["DXY", "US10Y_REAL", "SOFR_EFFR", "US_FED_DEBT", "US_MTS_INTEREST", "US_MTS_RECEIPTS", "XAUUSD", "SI"],
                steps=_reading_steps(song_value["readings"]),
                rules_hit=[
                    {"id": rule["id"], "message": rule["message"], "severity": rule["severity"]}
                    for rule in fired_song
                ],
                caveats=[
                    "COMEX 白银库存缺失，S9（20 日 ≥5000 万盎司）无法计算，白银闪崩预警只能人工跟踪 CME。",
                    "美元外储份额（COFER）与 CIPS 未接入，去美元化只能用央行购金间接代理。",
                    "美国联邦债务本地仅约 3 个月日频，债务/GDP 的趋势判断需外部校准。",
                    "『三变六反』同时存在 30/60 年与 3/6 年两种口径，本工具只用其长周期方向，不做择时。",
                ],
                falsifiers=[
                    "若 SOFR−EFFR 回落至 5bp 以下且 DXY 250 日分位跌破 30%，冷环流判断失效。",
                    "若金银比 >85 持续 12 个月且继续上行，S10 的均值回归失效。",
                ],
                opposing=["美国例外论（AI 生产率）可让强美元与美股同涨，冷环流不必然杀估值。"],
            )
            macro_deriv = rec.derive(
                code="lens.macro.state",
                claim=(
                    f"宏观层：{macro_value['state']['regime']['label']}，"
                    f"流动性「{macro_value['state']['liquidity']['label']}」，"
                    f"财政「{macro_value['state']['fiscal']['label']}」"
                ),
                value=macro_value,
                confidence=_lens_confidence(macro_value),
                evidence_grade="E2",
                subject="lens.macro",
                method_id=METHOD_MACRO,
                inputs=[
                    "US10Y_REAL", "US10Y_BE", "US2Y", "US30Y", "DXY", "SOFR_EFFR",
                    "US_FED_ASSETS", "US_TGA", "US_RRP_AMT", "US_M2",
                    "US_MTS_DEFICIT", "US_MTS_INTEREST", "US_MTS_RECEIPTS", "WB_US_GDP",
                ],
                steps=_reading_steps(macro_value["readings"]),
                rules_hit=[
                    {"id": rule["id"], "message": rule["message"], "severity": rule["severity"]}
                    for rule in macro_value["rules"]
                    if rule["fired"]
                ],
                caveats=[
                    "净流动性 = 美联储总资产 − 财政部一般账户 − 隔夜逆回购，单位为万亿美元；周频。",
                    "赤字与利息为 TTM 口径，MTS 月度数据约 30 天滞后。",
                ],
                falsifiers=["若净流动性连续三个月回升而风险资产继续下跌，流动性主导假设失效。"],
                opposing=["财政脉冲与流动性可能同时为正却对应衰退，因为赤字本身是衰退的结果。"],
            )
            micro_deriv = rec.derive(
                code="lens.micro.state",
                claim=(
                    f"微观层：风险偏好「{micro_value['state']['risk_appetite']['label']}」，"
                    f"黄金微观评分 {(micro_value['state']['gold_micro'] or {}).get('score') or 0.0:+.2f}"
                ),
                value=micro_value,
                confidence=_lens_confidence(micro_value),
                evidence_grade="E2",
                subject="lens.micro",
                method_id=METHOD_MICRO,
                inputs=[
                    "SPX", "NDX", "XAUUSD", "SI", "HG", "CU", "BZ", "CL",
                    "CN_GOLD_PREMIUM_PCT", "COMEX_GOLD_BASIS_PCT", "SGE_GOLD_LEASE_3M_PCT",
                    "ETF_GLOBAL_TONNES", "COT_MONEY_NET", "USDCNH", "000300",
                ],
                steps=_reading_steps(micro_value["readings"]),
                rules_hit=[
                    {"id": rule["id"], "message": rule["message"], "severity": rule["severity"]}
                    for rule in micro_value["rules"]
                    if rule["fired"]
                ],
                caveats=[
                    "COMEX 白银库存缺失，实物挤兑只能看黄金基差与租借利率。",
                    "中国溢价为 SGE 对伦敦价差，受汇率与管制影响，不等于真实紧张度。",
                ],
                falsifiers=["若基差、溢价、租借三者同时回落而金价续涨，实物紧张叙事失效。"],
                opposing=["黄金的微观紧张经常是区域性的（上海/迪拜），不能直接外推到全球定价。"],
            )
            persona_derivs: dict[str, Any] = {}
            for item in personas:
                state = item["state"]
                persona_derivs[item["id"]] = rec.derive(
                    code=f"lens.persona.{item['id']}.state",
                    claim=(
                        f"{item['name']}透镜：倾向「{state['lean']['label']}」"
                        f"（{state['lean']['score']:+.2f}），命中 {len(state['fired_rules'])} 条规则"
                    ),
                    value={"state": state, "scores": item.get("scores"), "readings": item.get("readings")},
                    confidence=_lens_confidence(item),
                    evidence_grade="E3",
                    subject=f"lens.persona.{item['id']}",
                    method_id=METHOD_PERSONA,
                    inputs=[str(reading.get("source") or "") for reading in item.get("readings") or []][:24],
                    steps=_reading_steps(item.get("readings") or []),
                    rules_hit=[
                        {"id": rule["id"], "message": rule["message"], "severity": rule["severity"]}
                        for rule in item.get("rules") or []
                        if rule.get("fired")
                    ],                    caveats=[
                        "人物透镜是框架的机械化复刻，不是本人当前观点；规则阈值取自其公开表述与文本。",
                        "出处分级 E1–E4，含二手转述；未经本人确认。",
                    ],
                    falsifiers=[item["thesis"]] if item.get("thesis") else [],
                    opposing=["同一人物在不同周期可能给出相反判断，框架不是承诺。"],
                )
            ranked = [row for row in synth_value["assets"] if row.get("consensus") is not None]
            strongest = max(ranked, key=lambda row: abs(row["consensus"]), default=None)
            synth_deriv = rec.derive(
                code="lens.synthesis",
                claim=(
                    f"多透镜合成：{synth_value['consensus_count']} 项共振、"
                    f"{len(synth_value['divergences'])} 项分歧；"
                    + (
                        f"最强共识 {strongest['label']} {strongest['consensus']:+.2f}；"
                        if strongest
                        else "无可用共识；"
                    )
                    + (
                        f"组合建议总敞口 {synth_value['portfolio']['gross_weight_pct']:.0f}%、"
                        f"组合风险 {synth_value['portfolio']['portfolio_risk_pct']:.2f}%"
                    )
                ),
                value=synth_value,
                confidence=synth_value["confidence"],
                evidence_grade="E2",
                subject="lens:all",
                method_id=METHOD_SYNTHESIS,
                inputs=["lens.fed.state", "lens.song.state", "SPX", "XAUUSD", "SI", "DXY", "000300", "US30Y", "BZ"],
                steps=[
                    {"name": "fed_derivation", "id": fed_deriv.id},
                    {"name": "song_derivation", "id": song_deriv.id},
                    {"name": "macro_derivation", "id": macro_deriv.id},
                    {"name": "micro_derivation", "id": micro_deriv.id},
                    *[
                        {"name": f"persona_{persona_id}_derivation", "id": deriv.id}
                        for persona_id, deriv in persona_derivs.items()
                    ],
                ],
                rules_hit=[
                    {"id": rule["id"], "message": rule["message"], "severity": rule["severity"]}
                    for rule in fired_fed + fired_song
                ],
                caveats=[
                    f"合成为 {synth_value['lens_count']} 套透镜加权（权重见 config/lens.yaml 的 synthesis.weights），"
                    "缺某一透镜分数时只用其余透镜加权，不把缺失当 0。",
                    "规则命中是条件成立，不是方向保证；分歧项必须等催化剂。",
                    "仓位、止损与组合权重由风险预算推导（2×ATR 止损、单笔风险 ≤2%、组合风险 ≤6%），"
                    "以总权益为基准，与账户余额无关。",
                ],
                falsifiers=synth_value["outlook"]["invalidators"],
                opposing=["多套透镜可能同时犯同一个错：把美元流动性当成唯一自变量，低估财政/供给冲击。"],
                parents=[
                    fed_deriv.id,
                    song_deriv.id,
                    macro_deriv.id,
                    micro_deriv.id,
                    *[deriv.id for deriv in persona_derivs.values()],
                ],
            )
            step.outputs = {
                "derivations": [
                    fed_deriv.id,
                    song_deriv.id,
                    macro_deriv.id,
                    micro_deriv.id,
                    *[deriv.id for deriv in persona_derivs.values()],
                    synth_deriv.id,
                ]
            }

            data_gaps = _data_gaps(
                config,
                fed_value["readings"],
                song_value["readings"],
                macro_value["readings"],
                micro_value["readings"],
            )
            observations = record_observations(
                session,
                _observation_rows(
                    fed_value,
                    song_value,
                    synth_value,
                    today,
                    [("macro", macro_value), ("micro", micro_value)]
                    + [(item["id"], item) for item in personas],
                ),
            )
            step.outputs["observations"] = observations
            step.outputs["data_gaps"] = len(data_gaps)
        summary = {
            "fed": fed_value["state"]["stance_label"],
            "song": song_value["state"]["phase"]["label"],
            "heart": song_value["state"]["dollar_heart"]["label"],
            "macro": macro_value["state"]["regime"]["label"],
            "personas": len(personas),
            "lenses": synth_value["lens_count"],
            "consensus": synth_value["consensus_count"],
            "strong": synth_value["strong_count"],
            "divergences": len(synth_value["divergences"]),
            "warnings": len(synth_value["warnings"]),
            "derivations": [
                fed_deriv.id,
                song_deriv.id,
                macro_deriv.id,
                micro_deriv.id,
                *[deriv.id for deriv in persona_derivs.values()],
                synth_deriv.id,
            ],
        }
        run = rec.finish(summary=summary)
        session.commit()
        return {
            "run": {
                "id": run.id,
                "kind": run.kind,
                "subject": run.subject,
                "asof": aware(run.asof).isoformat() if run.asof else None,
                "status": run.status,
                "method_id": run.method_id,
                "code_version": run.code_version,
                "started_at": aware(run.started_at).isoformat() if run.started_at else None,
                "finished_at": aware(run.finished_at).isoformat() if run.finished_at else None,
                "duration_ms": run.duration_ms,
                "degraded": bool(run.degraded),
                "degraded_reasons": run.degraded_reasons or [],
                "summary": summary,
                "error": run.error,
            },
            "panel": _panel_summary(panel),
            "fed": fed_value,
            "song": song_value,
            "macro": macro_value,
            "micro": micro_value,
            "personas": personas,
            "synthesis": synth_value,
            "rules": {
                "fed": fed_rules,
                "song": song_rules,
                "macro": macro_value["rules"],
                "micro": micro_value["rules"],
                "personas": {item["id"]: item.get("rules") or [] for item in personas},
            },
            "data_gaps": data_gaps,
            "derivations": {
                "fed": fed_deriv,
                "song": song_deriv,
                "macro": macro_deriv,
                "micro": micro_deriv,
                "personas": persona_derivs,
                "synthesis": synth_deriv,
            },
            "config_version": config.get("version"),
        }
    except Exception as exc:  # noqa: BLE001 - 记录失败运行后继续抛出
        rec.fail(exc)
        session.commit()
        raise


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


def latest_state(session: Session) -> dict[str, Any] | None:
    """Return the latest persisted lens state without recomputing."""
    synthesis = session.scalar(
        select(Derivation)
        .where(Derivation.code == "lens.synthesis")
        .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
        .limit(1)
    )
    if synthesis is None:
        return None
    fed = session.scalar(
        select(Derivation)
        .where(Derivation.code == "lens.fed.state")
        .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
        .limit(1)
    )
    song = session.scalar(
        select(Derivation)
        .where(Derivation.code == "lens.song.state")
        .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
        .limit(1)
    )
    run = synthesis.run_id
    macro = _latest_derivation(session, "lens.macro.state")
    micro = _latest_derivation(session, "lens.micro.state")
    personas = list(
        session.scalars(
            select(Derivation)
            .where(Derivation.code.like("lens.persona.%.state"))
            .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
            .limit(40)
        ).all()
    )
    seen: dict[str, Derivation] = {}
    for row in personas:
        persona_id = row.code.removeprefix("lens.persona.").removesuffix(".state")
        seen.setdefault(persona_id, row)
    return {
        "run_id": run,
        "asof": aware(synthesis.asof).isoformat() if synthesis.asof else None,
        "fed": fed,
        "song": song,
        "macro": macro,
        "micro": micro,
        "personas": seen,
        "synthesis": synthesis,
    }


def _latest_derivation(session: Session, code: str) -> Derivation | None:
    return session.scalar(
        select(Derivation)
        .where(Derivation.code == code)
        .order_by(Derivation.asof.desc(), Derivation.created_at.desc())
        .limit(1)
    )


def latest_forecasts(session: Session, limit: int = 50, status: str | None = None) -> list[Forecast]:
    stmt = select(Forecast).where(Forecast.subject == "lens")
    if status:
        stmt = stmt.where(Forecast.status == status)
    return list(session.scalars(stmt.order_by(Forecast.made_at.desc()).limit(limit)).all())


def create_forecast(
    session: Session,
    *,
    asset: str,
    direction: str,
    horizon_days: int = 90,
    probability: float | None = None,
    notes: str | None = None,
    baseline_value: float | None = None,
    derivation_id: str | None = None,
    run_id: str | None = None,
) -> Forecast:
    if asset not in _ASSET_META:
        raise ValueError(f"unknown lens asset: {asset}")
    if direction not in {"up", "down", "flat"}:
        raise ValueError(f"invalid direction: {direction}")
    if not 1 <= int(horizon_days) <= 365:
        raise ValueError("horizon_days must be between 1 and 365")
    now = datetime.now(timezone.utc)
    row = Forecast(
        id=new_id(),
        run_id=run_id,
        derivation_id=derivation_id,
        code=f"lens.{asset}",
        subject="lens",
        direction=direction,
        horizon_days=int(horizon_days),
        made_at=now,
        target_date=(now + timedelta(days=int(horizon_days))).date(),
        probability=probability,
        method_id=METHOD_SYNTHESIS,
        status="open",
        baseline_value=baseline_value,
        notes=notes,
    )
    session.add(row)
    session.commit()
    return row


def forecast_payload(row: Forecast) -> dict[str, Any]:
    return {
        "id": row.id,
        "code": row.code,
        "asset": row.code.replace("lens.", "", 1),
        "subject": row.subject,
        "direction": row.direction,
        "horizon_days": row.horizon_days,
        "made_at": row.made_at.isoformat() if row.made_at else None,
        "target_date": row.target_date.isoformat() if row.target_date else None,
        "probability": row.probability,
        "point": row.point,
        "status": row.status,
        "baseline_value": row.baseline_value,
        "notes": row.notes,
        "derivation_id": row.derivation_id,
    }
