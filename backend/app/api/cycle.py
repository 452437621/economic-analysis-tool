"""V2.0 周期引擎接口：状态、指标、历史、情景、预警。

读接口只读最近一次持久化的推导（不重算）；没有运行过时，GET /state 会懒触发一次
``run_cycle``，保证首次打开页面就有内容。写操作只有 POST /run。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cycle.config import load_config
from app.cycle.engine import run_cycle
from app.models.v2 import AnalysisRun, Derivation
from app.platform.db import get_session
from app.provenance.engine import aware

router = APIRouter(prefix="/api/v2/cycle", tags=["cycle"])

DERIVATION_CODES = {
    "state": "cycle.state.world",
    "scenarios": "cycle.scenarios",
    "sustainability": "cycle.sustainability.US",
    "world": "cycle.world.order",
    "alerts": "cycle.alerts",
    "analogs": "cycle.analogs",
    "history": "cycle.history",
}


def _iso(value) -> str | None:  # noqa: ANN001
    resolved = aware(value)
    return resolved.isoformat() if resolved else None


def _latest(session: Session, code: str) -> Derivation | None:
    return session.scalar(
        select(Derivation).where(Derivation.code == code).order_by(Derivation.asof.desc()).limit(1)
    )


def _payload(session: Session, code: str) -> dict | None:
    row = _latest(session, code)
    if row is None:
        return None
    return {
        "code": row.code,
        "claim": row.claim,
        "value": row.value,
        "confidence": row.confidence,
        "evidence_grade": row.evidence_grade,
        "asof": _iso(row.asof),
        "run_id": row.run_id,
        "method_id": row.method_id,
        "caveats": row.caveats or [],
        "falsifiers": row.falsifiers or [],
        "opposing": row.opposing or [],
        "inputs": row.inputs or [],
        "steps": row.steps or [],
        "rules_hit": row.rules_hit or [],
    }


def _state_payload(session: Session) -> dict:
    state = _payload(session, DERIVATION_CODES["state"])
    if state is None:
        run_cycle(session)
        state = _payload(session, DERIVATION_CODES["state"])
    if state is None:  # pragma: no cover - defensive
        raise HTTPException(status_code=503, detail="cycle engine produced no state")
    run = session.get(AnalysisRun, state["run_id"]) if state.get("run_id") else None
    extra = {
        key: _payload(session, code)
        for key, code in DERIVATION_CODES.items()
        if key != "state"
    }
    return {
        "asof": state["asof"],
        "run_id": state["run_id"],
        "status": run.status if run else None,
        "degraded": bool(run.degraded) if run else False,
        "degraded_reasons": (run.degraded_reasons or []) if run else [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "indicators": (state.get("value") or {}).get("readings") or [],
        **extra,
    }


@router.get("/state")
def get_state(session: Session = Depends(get_session)) -> dict:
    return _state_payload(session)


@router.get("/indicators")
def get_indicators(
    layer: str | None = Query(default=None, max_length=20),
    session: Session = Depends(get_session),
) -> dict:
    payload = _state_payload(session)
    items = payload.get("indicators") or []
    if layer:
        items = [item for item in items if item.get("layer") == layer]
    return {"items": items, "total": len(items), "asof": payload.get("asof")}


@router.get("/history")
def get_history(session: Session = Depends(get_session)) -> dict:
    payload = _payload(session, DERIVATION_CODES["history"])
    if payload is None:
        _state_payload(session)
        payload = _payload(session, DERIVATION_CODES["history"])
    if payload is None:
        raise HTTPException(status_code=404, detail="history not available")
    return payload


@router.get("/analogs")
def get_analogs(session: Session = Depends(get_session)) -> dict:
    payload = _payload(session, DERIVATION_CODES["analogs"])
    if payload is None:
        _state_payload(session)
        payload = _payload(session, DERIVATION_CODES["analogs"])
    if payload is None:
        raise HTTPException(status_code=404, detail="analogs not available")
    return payload


@router.get("/scenarios")
def get_scenarios(session: Session = Depends(get_session)) -> dict:
    payload = _payload(session, DERIVATION_CODES["scenarios"])
    if payload is None:
        _state_payload(session)
        payload = _payload(session, DERIVATION_CODES["scenarios"])
    if payload is None:
        raise HTTPException(status_code=404, detail="scenarios not available")
    return payload


@router.get("/alerts")
def get_alerts(session: Session = Depends(get_session)) -> dict:
    payload = _payload(session, DERIVATION_CODES["alerts"])
    if payload is None:
        _state_payload(session)
        payload = _payload(session, DERIVATION_CODES["alerts"])
    if payload is None:
        raise HTTPException(status_code=404, detail="alerts not available")
    return payload


@router.get("/config")
def get_config() -> dict:
    cfg = load_config()
    return {
        "version": (cfg.get("_meta") or {}).get("version"),
        "normalization": cfg.get("normalization"),
        "scores": cfg.get("scores"),
        "indicators": cfg.get("indicators"),
        "manual": cfg.get("manual"),
        "long_cycle": cfg.get("long_cycle"),
        "short_cycle": cfg.get("short_cycle"),
        "alerts": cfg.get("alerts"),
        "scenarios": cfg.get("scenarios"),
        "political_calendar": cfg.get("political_calendar"),
    }


@router.post("/run")
def post_run(session: Session = Depends(get_session)) -> dict:
    result = run_cycle(session)
    return {
        "ok": result.get("status") != "failed",
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "asof": result.get("asof"),
        "degraded_reasons": result.get("degraded_reasons") or [],
        "summary": {
            "long": (result.get("long_cycle") or {}).get("phase"),
            "short": (result.get("short_cycle") or {}).get("state"),
            "scenarios": [
                {"id": item["id"], "probability": item["probability"]}
                for item in (result.get("scenarios") or {}).get("scenarios", [])
            ],
            "alerts": (result.get("alerts") or {}).get("counts"),
            "analogs": (result.get("analogs") or {}).get("n"),
        },
    }
