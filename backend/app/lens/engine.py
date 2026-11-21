"""Two-lens engine: compute readings, evaluate rules, synthesise, persist.

The engine is a pure "read local panel → compute → record" pipeline.  It never
fetches data, so a run is reproducible from the database snapshot and every
derivation carries the code hash of the lens modules that produced it.

The orchestrator lives here; reusable pieces live in :mod:`app.lens.config`,
:mod:`app.lens.helpers`, :mod:`app.lens.synthesis` and :mod:`app.lens.state`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.cycle.market import load_panel
from app.lens import fed as fed_lens
from app.lens import layers as layer_builder
from app.lens import persona as persona_engine
from app.lens import position as position_engine
from app.lens import song as song_lens
from app.lens.config import CONFIG_PATH, _load_config_cached, load_config
from app.lens.helpers import (
    ASSETS,
    GOLD_COLUMNS,
    METHOD_ENGINE,
    METHOD_FED,
    METHOD_MACRO,
    METHOD_MICRO,
    METHOD_PERSONA,
    METHOD_SONG,
    METHOD_SYNTHESIS,
    _ASSET_META,
    _advice,
    _agreement,
    _agreement_multi,
    _curve_cross_up_metric,
    _data_gaps,
    _divergence_catalyst,
    _evaluate_rules,
    _gold_metric_loader,
    _last_close,
    _latest_cycle_context,
    _lens_confidence,
    _lens_label,
    _lens_scores,
    _observation_rows,
    _panel_summary,
    _reading_steps,
    _record_rule_hits,
    _rule_severity,
    _warning_list,
)
from app.lens.state import (
    _latest_derivation,
    create_forecast,
    forecast_payload,
    latest_forecasts,
    latest_state,
)
from app.lens.synthesis import _outlook, _synthesis, _synthesis_confidence
from app.platform.quality_gate import assess as assess_quality
from app.platform.quality_gate import confidence_factor
from app.provenance.engine import RunRecorder, aware, new_id, record_observations

logger = logging.getLogger(__name__)


def run_lenses(session: Session, asof: datetime | None = None) -> dict[str, Any]:
    """Run both lenses, persist run/steps/derivations/rules/observations."""
    config = load_config()
    now = datetime.now(timezone.utc)
    today = (asof or now).date()
    quality = assess_quality(session, now=now)
    rec = RunRecorder(session, kind="lens", subject="all", method_id=METHOD_ENGINE, code_version="lens-1.0")
    rec.start()
    if quality["status"] != "ok":
        rec.degrade(
            "lens.quality.gate",
            quality.get("caveat") or f"数据质量门控：{quality['status']}",
            severity="critical" if quality["status"] == "blocked" else "warn",
        )
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
            synth_value["quality"] = quality
            synth_value["actionable"] = bool(quality["allow_action"])
            synth_value["confidence"] = round(
                max(0.3, min(0.85, float(synth_value["confidence"]) * confidence_factor(quality))), 3
            )
            if quality["caveat"]:
                synth_value["quality_caveat"] = quality["caveat"]
            if quality["status"] == "blocked":
                portfolio = synth_value.get("portfolio") or {}
                portfolio["actionable"] = False
                portfolio["blocked_reason"] = quality["caveat"]
                synth_value["portfolio"] = portfolio
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
            "quality": quality,
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

__all__ = [
    "ASSETS",
    "CONFIG_PATH",
    "GOLD_COLUMNS",
    "METHOD_ENGINE",
    "METHOD_FED",
    "METHOD_MACRO",
    "METHOD_MICRO",
    "METHOD_PERSONA",
    "METHOD_SONG",
    "METHOD_SYNTHESIS",
    "RunRecorder",
    "_ASSET_META",
    "_advice",
    "_agreement",
    "_agreement_multi",
    "_curve_cross_up_metric",
    "_data_gaps",
    "_divergence_catalyst",
    "_evaluate_rules",
    "_gold_metric_loader",
    "_last_close",
    "_latest_cycle_context",
    "_latest_derivation",
    "_lens_confidence",
    "_lens_label",
    "_lens_scores",
    "_load_config_cached",
    "_observation_rows",
    "_outlook",
    "_panel_summary",
    "_reading_steps",
    "_record_rule_hits",
    "_rule_severity",
    "_synthesis",
    "_synthesis_confidence",
    "_warning_list",
    "assess_quality",
    "aware",
    "confidence_factor",
    "create_forecast",
    "fed_lens",
    "forecast_payload",
    "layer_builder",
    "latest_forecasts",
    "latest_state",
    "load_config",
    "load_panel",
    "logger",
    "new_id",
    "persona_engine",
    "position_engine",
    "record_observations",
    "run_lenses",
    "song_lens",
]
