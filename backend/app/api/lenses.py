"""多透镜 API：13 套框架（美联储 / 宋鸿兵 / 宏观层 / 微观层 / 九位人物）。

``GET /state`` 读取最近一次落库推导；无落库数据时懒运行一次，``refresh=true``
强制重算，``POST /run`` 显式重算。推导写入 ``lens.fed.state`` /
``lens.song.state`` / ``lens.macro.state`` / ``lens.micro.state`` /
``lens.persona.<id>.state`` / ``lens.synthesis``，读数写入 ``observations``
（``lens.<透镜>.<读数>`` / ``lens.score.*`` / ``lens.<透镜>.lean``），
规则命中写入 ``rule_hits``（``lens.F*`` / ``lens.S*`` / ``lens.M*`` /
``lens.P*`` / ``lens.<人物前缀>*``）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.serializers import derivation_payload, iso, run_payload
from app.lens.common import evaluate_rule
from app.lens.engine import (
    ASSETS,
    create_forecast,
    forecast_payload,
    latest_forecasts,
    latest_state,
    load_config,
    run_lenses,
)
from app.lens.persona import load_specs
from app.models.v2 import AnalysisRun, Derivation
from app.platform.db import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/lenses", tags=["lenses"])

ASSET_META = {row["id"]: row for row in ASSETS}


_iso = iso
_derivation_payload = derivation_payload


_run_payload = run_payload


def _persisted_rules(synth_value: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the full rule table from the persisted metrics (hits + misses)."""
    config = load_config()
    metrics = synth_value.get("rule_metrics") or {}
    layer_metrics = synth_value.get("layer_metrics") or {}
    roles: dict[str, Any] = {
        "fed": [evaluate_rule(rule, metrics) for rule in config.get("fed_rules", [])],
        "song": [evaluate_rule(rule, metrics) for rule in config.get("song_rules", [])],
        "macro": [evaluate_rule(rule, layer_metrics.get("macro") or metrics) for rule in config.get("macro_rules", [])],
        "micro": [evaluate_rule(rule, layer_metrics.get("micro") or metrics) for rule in config.get("micro_rules", [])],
    }
    personas: dict[str, Any] = {}
    for persona_id, persona_metrics in (layer_metrics.get("personas") or {}).items():
        spec = next((item for item in load_specs() if item.id == persona_id), None)
        if spec is None:
            continue
        personas[persona_id] = [evaluate_rule(rule, persona_metrics) for rule in spec.rules]
    roles["personas"] = personas
    return roles


def _lens_payload(value: dict[str, Any], derivation: Derivation | None) -> dict[str, Any]:
    payload = {
        "state": value.get("state") or {},
        "readings": value.get("readings") or [],
        "catalog": value.get("catalog") or [],
        "coverage": (value.get("state") or {}).get("coverage") or {},
        "scores": value.get("scores") or {},
    }
    if derivation is not None:
        payload["derivation"] = _derivation_payload(derivation)
        payload["method_id"] = derivation.method_id
    return payload


def _persona_payloads(synth_value: dict[str, Any]) -> list[dict[str, Any]]:
    """人物透镜：从落库的 synthesis 里恢复（只读），或直接用运行结果。"""
    stored = synth_value.get("personas")
    if isinstance(stored, list):
        return stored
    return []


def _persona_meta() -> dict[str, dict[str, Any]]:
    """人物透镜的静态元信息（名称/头衔/流派/核心问题/论点），来自 YAML 规格。"""
    return {
        spec.id: {
            "name": spec.name,
            "title": spec.title,
            "school": spec.school,
            "key_question": spec.key_question,
            "thesis": spec.thesis,
        }
        for spec in load_specs()
    }


def _persona_entry(
    persona_id: str,
    value: dict[str, Any],
    derivation: Derivation | None,
    meta: dict[str, Any],
) -> dict[str, Any]:
    """把 YAML 元信息与透镜运行值拼成对外的人物透镜结构。"""
    payload = _lens_payload(value, derivation)
    return {
        "id": persona_id,
        "name": meta.get("name") or value.get("name") or persona_id,
        "title": value.get("title") or meta.get("title"),
        "school": value.get("school") or meta.get("school"),
        "key_question": value.get("key_question") or meta.get("key_question"),
        "thesis": value.get("thesis") or meta.get("thesis"),
        **payload,
    }


def _payload(
    *,
    asof: str | None,
    run: dict[str, Any] | None,
    fed: dict[str, Any],
    song: dict[str, Any],
    macro: dict[str, Any] | None,
    micro: dict[str, Any] | None,
    personas: list[dict[str, Any]],
    synthesis: dict[str, Any],
    rules: dict[str, Any],
    data_gaps: list[dict[str, Any]],
    config: dict[str, Any],
    confidence: float | None,
    evidence_grade: str | None,
) -> dict[str, Any]:
    return {
        "asof": asof,
        "run": run,
        "fed": fed,
        "song": song,
        "macro": macro,
        "micro": micro,
        "personas": personas,
        "synthesis": synthesis,
        "portfolio": synthesis.get("portfolio"),
        "rules": rules,
        "data_gaps": data_gaps,
        "disclaimer": config.get("disclaimer", ""),
        "config_version": config.get("version"),
        "confidence": confidence,
        "evidence_grade": evidence_grade,
    }


def _payload_from_persisted(session: Session) -> dict[str, Any]:
    state = latest_state(session)
    if state is None:
        raise HTTPException(status_code=404, detail="尚未运行过透镜；请先 POST /api/v2/lenses/run")
    fed_row: Derivation = state["fed"]
    song_row: Derivation = state["song"]
    synth_row: Derivation = state["synthesis"]
    run = session.get(AnalysisRun, state["run_id"]) if state["run_id"] else None
    config = load_config()
    synth_value = synth_row.value or {}
    macro_row = state.get("macro")
    micro_row = state.get("micro")
    persona_rows: dict[str, Derivation] = state.get("personas") or {}
    meta = _persona_meta()
    personas = [
        _persona_entry(persona_id, row.value or {}, row, meta.get(persona_id, {}))
        for persona_id, row in persona_rows.items()
    ]
    return _payload(
        asof=_iso(synth_row.asof),
        run=_run_payload(run) if run else None,
        fed=_lens_payload(fed_row.value or {}, fed_row),
        song=_lens_payload(song_row.value or {}, song_row),
        macro=_lens_payload(macro_row.value or {}, macro_row) if macro_row else None,
        micro=_lens_payload(micro_row.value or {}, micro_row) if micro_row else None,
        personas=personas or _persona_payloads(synth_value),
        synthesis={**synth_value, "derivation": _derivation_payload(synth_row)},
        rules=_persisted_rules(synth_value),
        data_gaps=config.get("data_gaps", []),
        config=config,
        confidence=synth_row.confidence,
        evidence_grade=synth_row.evidence_grade,
    )


def _payload_from_result(result: dict[str, Any]) -> dict[str, Any]:
    derivations = result["derivations"]
    persona_derivs: dict[str, Derivation] = derivations.get("personas") or {}
    meta = _persona_meta()
    personas = [
        _persona_entry(item["id"], item, persona_derivs.get(item["id"]), meta.get(item["id"], {}))
        for item in result.get("personas") or []
    ]
    return _payload(
        asof=result["run"].get("asof"),
        run=result["run"],
        fed=_lens_payload(result["fed"], derivations["fed"]),
        song=_lens_payload(result["song"], derivations["song"]),
        macro=_lens_payload(result["macro"], derivations.get("macro")) if result.get("macro") else None,
        micro=_lens_payload(result["micro"], derivations.get("micro")) if result.get("micro") else None,
        personas=personas,
        synthesis={**result["synthesis"], "derivation": _derivation_payload(derivations["synthesis"])},
        rules=result["rules"],
        data_gaps=result["data_gaps"],
        config=load_config(),
        confidence=derivations["synthesis"].confidence,
        evidence_grade=derivations["synthesis"].evidence_grade,
    )


@router.get("/state")
def get_state(
    refresh: bool = Query(False, description="true 时强制重算"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if refresh:
        return _payload_from_result(run_lenses(session))
    try:
        payload = _payload_from_persisted(session)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        return _payload_from_result(run_lenses(session))
    if payload.get("portfolio") is None:
        # 旧版推导没有仓位/组合权重（升级后首次打开），补算一次。
        return _payload_from_result(run_lenses(session))
    return payload


@router.post("/run")
def post_run(
    session: Session = Depends(get_session),
    asof: str | None = Query(None),
) -> dict[str, Any]:
    asof_date = None
    if asof:
        try:
            asof_date = datetime.fromisoformat(asof)
        except ValueError:
            raise HTTPException(status_code=422, detail="asof 需为 ISO 日期，例如 2026-11-18") from None
    try:
        result = run_lenses(session, asof=asof_date)
    except Exception:  # pragma: no cover - 运行期兜底，保留错误给前端
        logger.exception("lens run failed")
        raise HTTPException(status_code=500, detail="透镜运行失败，请查看服务端日志") from None
    return _payload_from_result(result)


class ForecastRequest(BaseModel):
    asset: str = Field(..., description="us_equity/gold/silver/usd/cn_equity/long_bond/commodities")
    direction: str = Field(..., pattern="^(up|down|flat)$")
    horizon_days: int = Field(90, ge=1, le=365)
    probability: float | None = Field(None, ge=0, le=1)
    baseline_value: float | None = None
    derivation_id: str | None = None
    notes: str | None = None


@router.get("/forecast-codes")
def get_forecast_codes() -> dict[str, Any]:
    return {
        "items": [
            {"code": f"lens.{key}", "asset": key, "label": row["label"], "symbol": row["symbol"]}
            for key, row in ASSET_META.items()
        ]
    }


@router.get("/forecasts")
def get_forecasts(
    status: Literal["open", "resolved"] | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    rows = latest_forecasts(session, limit=limit, status=status)
    items = [forecast_payload(row) for row in rows]
    return {
        "items": items,
        "open": [item for item in items if item["status"] == "open"],
        "resolved": [item for item in items if item["status"] != "open"],
    }


@router.post("/forecasts", status_code=201)
def post_forecast(
    payload: ForecastRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if payload.asset not in ASSET_META:
        raise HTTPException(status_code=422, detail=f"未知资产：{payload.asset}")
    derivation_id = payload.derivation_id
    if derivation_id is None:
        state = latest_state(session)
        if state and state["synthesis"] is not None:
            derivation_id = state["synthesis"].id
    row = create_forecast(
        session,
        asset=payload.asset,
        direction=payload.direction,
        horizon_days=payload.horizon_days,
        probability=payload.probability,
        baseline_value=payload.baseline_value,
        notes=payload.notes,
        derivation_id=derivation_id,
    )
    return forecast_payload(row)


@router.get("/ping")
def ping_llm() -> dict[str, Any]:
    from app.llm.client import LLMClient

    client = LLMClient()
    return {
        "available": client.available,
        "model": client.model,
        "budget_usd": client.budget_usd,
        "hint": None
        if client.available
        else "未配置 DEEPSEEK_API_KEY；透镜的读数、规则与综合评分不依赖 LLM，只有「AI 解读」需要。",
    }


class CommentaryRequest(BaseModel):
    question: str | None = Field(None, max_length=500)


def _commentary_context(state: dict[str, Any]) -> str:
    fed = state.get("fed") or {}
    song = state.get("song") or {}
    synth = state.get("synthesis") or {}
    lines = [
        f"综合共识：{synth.get('consensus_count')} 项共振 / {len(synth.get('divergences') or [])} 项分歧，"
        f"时间窗 {(synth.get('outlook') or {}).get('horizon_days')} 天",
        f"美联储透镜：{json.dumps(fed.get('state'), ensure_ascii=False)[:1500]}",
        f"美联储读数：{json.dumps(fed.get('readings'), ensure_ascii=False)[:1800]}",
        f"宋鸿兵透镜：{json.dumps(song.get('state'), ensure_ascii=False)[:1500]}",
        f"宋鸿兵读数：{json.dumps(song.get('readings'), ensure_ascii=False)[:1800]}",
        f"资产评分：{json.dumps(synth.get('assets'), ensure_ascii=False)[:1000]}",
        f"规则命中：{json.dumps(state.get('rules'), ensure_ascii=False)[:1800]}",
        f"数据缺口：{json.dumps(state.get('data_gaps'), ensure_ascii=False)[:700]}",
    ]
    return "\n".join(lines)


@router.post("/commentary")
def post_commentary(
    payload: CommentaryRequest,
    refresh: bool = Query(False),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    from app.llm.client import LLMBudgetExceeded, LLMClient, LLMUnavailable

    if refresh:
        state = _payload_from_result(run_lenses(session))
    else:
        try:
            state = _payload_from_persisted(session)
        except HTTPException:
            state = _payload_from_result(run_lenses(session))

    client = LLMClient()
    if not client.available:
        raise HTTPException(
            status_code=503,
            detail="未配置 DEEPSEEK_API_KEY：透镜的读数、规则与综合评分不依赖 LLM，只有这段解读需要。",
        )
    system = (
        "你是 EPIC 多透镜研判台的市场解读助手。只能基于给定的读数、规则命中与资产评分作答，"
        "不得编造数据；区分「事实/推断/未知」，引用规则编号（F*/S*/M*/P* 与人物的 DL/SD/HM/JG/EE/ZP/MP/RK/PA 前缀）"
        "与证据等级；回答用中文，先给结论，再给三条以内的依据，最后给一条失效条件。"
    )
    question = payload.question or "请用 300 字以内解读当前多透镜状态，指出最重要的三个信号与一个风险。"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{_commentary_context(state)}\n\n问题：{question}"},
    ]
    try:
        result = client.chat(messages, task="lens.commentary", temperature=0.2, max_tokens=900)
    except LLMUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return {
        "text": result.text,
        "model": result.model,
        "cached": result.cached,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost_usd": result.cost_usd,
    }
