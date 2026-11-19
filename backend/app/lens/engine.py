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
from app.lens import song as song_lens
from app.lens.common import evaluate_rule, load_gold_series, score_label
from app.models.v2 import Derivation, Forecast
from app.provenance.engine import RunRecorder, new_id, record_observations

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "lens.yaml"
METHOD_ENGINE = "lens.engine.v1"
METHOD_FED = "lens.fed.v1"
METHOD_SONG = "lens.song.v1"
METHOD_SYNTHESIS = "lens.synthesis.v1"

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


def _synthesis(
    fed_state: dict[str, Any],
    song_state: dict[str, Any],
    panel: Panel,
    config: dict[str, Any],
    cycle_context: dict[str, Any] | None,
) -> dict[str, Any]:
    weights = (config.get("synthesis") or {}).get("weights") or {}
    weight_fed = float(weights.get("fed", 0.5))
    weight_song = float(weights.get("song", 0.5))
    total = weight_fed + weight_song or 1.0

    rows: list[dict[str, Any]] = []
    divergences: list[dict[str, Any]] = []
    for asset in ASSETS:
        asset_id = asset["id"]
        fed_score = (fed_state.get("asset_scores") or {}).get(asset_id, {}).get("score")
        song_score = (song_state.get("asset_scores") or {}).get(asset_id, {}).get("score")
        consensus = None
        if fed_score is not None and song_score is not None:
            consensus = round((weight_fed * fed_score + weight_song * song_score) / total, 2)
        agreement, direction = _agreement(fed_score, song_score, consensus)
        probability = None
        if consensus is not None:
            probability = round(min(0.78, 0.50 + 0.10 * abs(consensus)), 3)
        row = {
            "id": asset_id,
            "label": asset["label"],
            "symbol": asset["symbol"],
            "unit": asset["unit"],
            "note": asset["note"],
            "last": _round(_last_close(panel, asset["symbol"]), 3),
            "fed": fed_score,
            "song": song_score,
            "consensus": consensus,
            "label_consensus": score_label(consensus),
            "agreement": agreement,
            "direction": direction,
            "probability": probability,
            "advice": _advice(agreement, consensus),
        }
        rows.append(row)
        if agreement == "分歧":
            spread = _round((fed_score or 0.0) - (song_score or 0.0), 2)
            divergences.append(
                {
                    "asset": asset_id,
                    "label": asset["label"],
                    "fed": fed_score,
                    "song": song_score,
                    "spread": spread,
                    "reading": f"美联储 {fed_score:+.2f} / 宋鸿兵 {song_score:+.2f}" if fed_score is not None and song_score is not None else "读数不足",
                    "catalyst": _divergence_catalyst(asset_id),
                }
            )

    warnings = _warning_list(fed_state, song_state)

    consensus_count = sum(1 for row in rows if row["agreement"] in {"共振多", "共振空"})
    narrative = (
        f"合成结论：{consensus_count} 项资产两镜共振，{len(divergences)} 项分歧。"
        f"美联储透镜为「{fed_state.get('stance_label', '未知')}」/「{(fed_state.get('regime') or {}).get('label', '未知')}」，"
        f"宋鸿兵透镜为「{(song_state.get('phase') or {}).get('label', '未知')}」，"
        f"美元心脏「{(song_state.get('dollar_heart') or {}).get('label', '未知')}」。"
        "共振项是仓位的来源，分歧项是风险的来源；分歧未解决前，单一透镜的结论只能做研究，不能做仓位。"
    )

    outlook = _outlook(fed_state, song_state, rows, warnings)
    return {
        "assets": rows,
        "divergences": divergences,
        "warnings": warnings,
        "consensus_count": consensus_count,
        "narrative": narrative,
        "outlook": outlook,
        "cycle_context": cycle_context,
        "confidence": _synthesis_confidence(fed_state, song_state, rows),
    }


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _agreement(fed: float | None, song: float | None, consensus: float | None) -> tuple[str, str]:
    if fed is None or song is None:
        return "数据不足", "flat"
    if fed >= 0.25 and song >= 0.25:
        agreement = "共振多"
    elif fed <= -0.25 and song <= -0.25:
        agreement = "共振空"
    elif fed * song < 0 and min(abs(fed), abs(song)) >= 0.35:
        agreement = "分歧"
    else:
        agreement = "弱信号"
    if consensus is None or abs(consensus) < 0.25:
        direction = "flat"
    elif consensus > 0:
        direction = "up"
    else:
        direction = "down"
    return agreement, direction


def _advice(agreement: str, consensus: float | None) -> str:
    if agreement == "共振多":
        return "两镜同向偏多：回调分批，不追高；跌破关键位再重估。"
    if agreement == "共振空":
        return "两镜同向偏空：反弹减仓，等右侧确认，不接下跌中的刀。"
    if agreement == "分歧":
        return "两镜分歧：只做区间或观望，等催化剂落地，不要用单一透镜下注。"
    if agreement == "数据不足":
        return "数据不足：不产生信号。"
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


def _warning_list(fed_state: dict[str, Any], song_state: dict[str, Any]) -> list[dict[str, Any]]:
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
            "若两镜连续 20 个交易日同向且资产价格反向，视为框架失效，需降权而不是加仓。",
        ],
    }


def _synthesis_confidence(fed_state: dict[str, Any], song_state: dict[str, Any], rows: list[dict[str, Any]]) -> float:
    fed_cov = (fed_state.get("coverage") or {}).get("available", 0) / max(
        1, (fed_state.get("coverage") or {}).get("total", 1)
    )
    song_cov = (song_state.get("coverage") or {}).get("available", 0) / max(
        1, (song_state.get("coverage") or {}).get("total", 1)
    )
    agreement_ratio = sum(1 for row in rows if row["agreement"] in {"共振多", "共振空"}) / max(1, len(rows))
    return round(min(0.85, 0.30 + 0.25 * fed_cov + 0.20 * song_cov + 0.15 * agreement_ratio), 3)


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
    fed_value: dict[str, Any], song_value: dict[str, Any], synth: dict[str, Any], today: date
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lens_name, value in (("fed", fed_value), ("song", song_value)):
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

        with rec.step("synthesise", kind="compute") as step:
            cycle_context = _latest_cycle_context(session)
            synth_value = _synthesis(fed_value["state"], song_value["state"], panel, config, cycle_context)
            synth_value["rule_metrics"] = metrics
            step.outputs = {
                "consensus": synth_value["consensus_count"],
                "divergences": len(synth_value["divergences"]),
                "confidence": synth_value["confidence"],
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
            ranked = [row for row in synth_value["assets"] if row.get("consensus") is not None]
            strongest = max(ranked, key=lambda row: abs(row["consensus"]), default=None)
            synth_deriv = rec.derive(
                code="lens.synthesis",
                claim=(
                    f"双透镜合成：{synth_value['consensus_count']} 项共振、"
                    f"{len(synth_value['divergences'])} 项分歧；"
                    + (
                        f"最强共识 {strongest['label']} {strongest['consensus']:+.2f}"
                        if strongest
                        else "无可用共识"
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
                ],
                rules_hit=[
                    {"id": rule["id"], "message": rule["message"], "severity": rule["severity"]}
                    for rule in fired_fed + fired_song
                ],
                caveats=[
                    "合成采用两镜等权；权重写在 config/lens.yaml，改权重必须同步改文档。",
                    "规则命中是条件成立，不是方向保证；分歧项必须等催化剂。",
                ],
                falsifiers=synth_value["outlook"]["invalidators"],
                opposing=["两镜可能同时犯同一个错：把美元流动性当成唯一自变量，低估财政/供给冲击。"],
                parents=[fed_deriv.id, song_deriv.id],
            )
            step.outputs = {"derivations": [fed_deriv.id, song_deriv.id, synth_deriv.id]}

            data_gaps = _data_gaps(config, fed_value["readings"], song_value["readings"])
            observations = record_observations(session, _observation_rows(fed_value, song_value, synth_value, today))
            step.outputs["observations"] = observations
            step.outputs["data_gaps"] = len(data_gaps)
        summary = {
            "fed": fed_value["state"]["stance_label"],
            "song": song_value["state"]["phase"]["label"],
            "heart": song_value["state"]["dollar_heart"]["label"],
            "consensus": synth_value["consensus_count"],
            "divergences": len(synth_value["divergences"]),
            "warnings": len(_warning_list(fed_value["state"], song_value["state"])),
            "derivations": [fed_deriv.id, song_deriv.id, synth_deriv.id],
        }
        run = rec.finish(summary=summary)
        session.commit()
        return {
            "run": {
                "id": run.id,
                "kind": run.kind,
                "subject": run.subject,
                "asof": run.asof.isoformat() if run.asof else None,
                "status": run.status,
                "method_id": run.method_id,
                "code_version": run.code_version,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "duration_ms": run.duration_ms,
                "degraded": bool(run.degraded),
                "degraded_reasons": run.degraded_reasons or [],
                "summary": summary,
                "error": run.error,
            },
            "panel": _panel_summary(panel),
            "fed": fed_value,
            "song": song_value,
            "synthesis": synth_value,
            "rules": {"fed": fed_rules, "song": song_rules},
            "data_gaps": data_gaps,
            "derivations": {"fed": fed_deriv, "song": song_deriv, "synthesis": synth_deriv},
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
    config: dict[str, Any], fed_readings: list[dict[str, Any]], song_readings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    gaps = list(config.get("data_gaps") or [])
    known = {gap.get("id") for gap in gaps}
    for reading in list(fed_readings) + list(song_readings):
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
    return {
        "run_id": run,
        "asof": synthesis.asof.isoformat() if synthesis.asof else None,
        "fed": fed,
        "song": song,
        "synthesis": synthesis,
    }


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
