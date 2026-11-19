"""双透镜 API：美联储主席透镜 / 宋鸿兵透镜。

``GET /state`` 读取最近一次落库推导；无落库数据时懒运行一次，``refresh=true``
强制重算，``POST /run`` 显式重算。推导写入 ``lens.fed.state`` /
``lens.song.state`` / ``lens.synthesis``，读数写入 ``observations``
（``lens.fed.*`` / ``lens.song.*`` / ``lens.score.*``），规则命中写入
``rule_hits``（``lens.F*`` / ``lens.S*``）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
from app.models.v2 import AnalysisRun, Derivation
from app.platform.db import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/lenses", tags=["lenses"])

ASSET_META = {row["id"]: row for row in ASSETS}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _derivation_payload(row: Derivation) -> dict[str, Any]:
    return {
        "id": row.id,
        "code": row.code,
        "claim": row.claim,
        "value": row.value,
        "confidence": row.confidence,
        "evidence_grade": row.evidence_grade,
        "asof": _iso(row.asof),
        "run_id": row.run_id,
        "method_id": row.method_id,
        "inputs": row.inputs or [],
        "steps": row.steps or [],
        "rules_hit": row.rules_hit or [],
        "caveats": row.caveats or [],
        "falsifiers": row.falsifiers or [],
        "opposing": row.opposing or [],
    }


def _run_payload(row: AnalysisRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "subject": row.subject,
        "asof": _iso(row.asof),
        "status": row.status,
        "method_id": row.method_id,
        "code_version": row.code_version,
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "duration_ms": row.duration_ms,
        "degraded": row.degraded,
        "degraded_reasons": row.degraded_reasons or [],
        "summary": row.summary or {},
        "error": row.error,
    }


def _persisted_rules(synth_value: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Rebuild the full rule table from the persisted metrics (hits + misses)."""
    config = load_config()
    metrics = synth_value.get("rule_metrics") or {}
    return {
        "fed": [evaluate_rule(rule, metrics) for rule in config.get("fed_rules", [])],
        "song": [evaluate_rule(rule, metrics) for rule in config.get("song_rules", [])],
    }


def _lens_payload(value: dict[str, Any], derivation: Derivation) -> dict[str, Any]:
    return {
        "state": value.get("state") or {},
        "readings": value.get("readings") or [],
        "catalog": value.get("catalog") or [],
        "coverage": (value.get("state") or {}).get("coverage") or {},
        "derivation": _derivation_payload(derivation),
        "method_id": derivation.method_id,
    }


def _payload(
    *,
    asof: str | None,
    run: dict[str, Any] | None,
    fed: dict[str, Any],
    song: dict[str, Any],
    synthesis: dict[str, Any],
    rules: dict[str, list[dict[str, Any]]],
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
        "synthesis": synthesis,
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
    return _payload(
        asof=_iso(synth_row.asof),
        run=_run_payload(run) if run else None,
        fed=_lens_payload(fed_row.value or {}, fed_row),
        song=_lens_payload(song_row.value or {}, song_row),
        synthesis={**(synth_row.value or {}), "derivation": _derivation_payload(synth_row)},
        rules=_persisted_rules(synth_row.value or {}),
        data_gaps=config.get("data_gaps", []),
        config=config,
        confidence=synth_row.confidence,
        evidence_grade=synth_row.evidence_grade,
    )


def _payload_from_result(result: dict[str, Any]) -> dict[str, Any]:
    derivations = result["derivations"]
    return _payload(
        asof=result["run"].get("asof"),
        run=result["run"],
        fed=_lens_payload(result["fed"], derivations["fed"]),
        song=_lens_payload(result["song"], derivations["song"]),
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
        return _payload_from_persisted(session)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        return _payload_from_result(run_lenses(session))


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
        "你是 EPIC 双透镜的市场解读助手。只能基于给定的读数、规则命中与资产评分作答，"
        "不得编造数据；区分「事实/推断/未知」，引用规则编号（F*/S*）与证据等级；"
        "回答用中文，先给结论，再给三条以内的依据，最后给一条失效条件。"
    )
    question = payload.question or "请用 300 字以内解读当前双透镜状态，指出最重要的三个信号与一个风险。"
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
