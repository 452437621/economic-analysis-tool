"""V2.0 台账接口：原则库、预测登记、到期对账与校准。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger.engine import (
    FORECAST_CODES,
    METHOD,
    calibration_summary,
    register_forecast,
    run_ledger,
)
from app.ledger.principles import CATEGORY_LABELS, EVIDENCE_LABELS
from app.models.v2 import AnalysisRun, Derivation, Forecast, ForecastOutcome, PrincipleCheck
from app.platform.db import get_session
from app.provenance import aware, latest_derivations

router = APIRouter(prefix="/api/v2/ledger", tags=["ledger"])


class ForecastRequest(BaseModel):
    code: str = Field(..., description="预测对象，见 /forecasts/codes")
    direction: str = Field(..., description="up / down / flat")
    horizon_days: int = Field(30, ge=1, le=365)
    probability: float | None = Field(None, ge=0.0, le=1.0)
    point: float | None = None
    baseline_value: float | None = None
    notes: str | None = Field(None, max_length=500)


def _latest(session: Session, code: str) -> Derivation | None:
    rows = latest_derivations(session, code, limit=1)
    return rows[0] if rows else None


def _last_run(session: Session) -> AnalysisRun | None:
    return session.scalars(
        select(AnalysisRun)
        .where(AnalysisRun.kind == "ledger")
        .order_by(AnalysisRun.started_at.desc())
        .limit(1)
    ).first()


def _ensure(session: Session) -> AnalysisRun:
    run = _last_run(session)
    if run is None:
        run_ledger(session)
        run = _last_run(session)
    if run is None:
        raise HTTPException(status_code=503, detail="台账尚未就绪，请稍后重试")
    return run


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return aware(value).isoformat()


def _counts(session: Session, run_id: str) -> dict:
    rows = session.scalars(
        select(PrincipleCheck).where(PrincipleCheck.run_id == run_id)
    ).all()
    counts = {"hit": 0, "near": 0, "miss": 0, "unknown": 0}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    counts["total"] = len(rows)
    return counts


def _principle_items(session: Session, run_id: str) -> list[dict]:
    from app.models.v2 import Principle

    principles = session.scalars(select(Principle).order_by(Principle.id)).all()
    checks = {
        row.principle_id: row
        for row in session.scalars(
            select(PrincipleCheck).where(PrincipleCheck.run_id == run_id)
        ).all()
    }
    items: list[dict] = []
    for row in principles:
        check = checks.get(row.id)
        items.append(
            {
                "id": row.id,
                "category": row.category,
                "category_label": CATEGORY_LABELS.get(row.category, row.category),
                "name": row.name,
                "statement": row.statement,
                "evidence": row.evidence,
                "evidence_label": EVIDENCE_LABELS.get(row.evidence, row.evidence),
                "observable": row.observable,
                "signal": row.signal,
                "falsifier": row.falsifier,
                "grade": row.grade,
                "metric": row.metric,
                "op": row.op,
                "threshold": row.threshold,
                "near": row.near,
                "status": check.status if check else "unknown",
                "value": check.value if check else None,
                "note": check.note if check else "尚无核对记录",
                "checked_at": _iso(check.created_at) if check else None,
            }
        )
    return items


def _forecast_items(session: Session, status: str | None = None) -> list[dict]:
    stmt = select(Forecast).order_by(Forecast.target_date)
    if status in {"open", "resolved"}:
        stmt = stmt.where(Forecast.status == status)
    rows = session.scalars(stmt).all()
    outcomes = {
        row.forecast_id: row
        for row in session.scalars(select(ForecastOutcome)).all()
    }
    items: list[dict] = []
    for row in rows:
        outcome = outcomes.get(row.id)
        items.append(
            {
                "id": row.id,
                "code": row.code,
                "code_label": FORECAST_CODES.get(row.code, row.code),
                "subject": row.subject,
                "direction": row.direction,
                "horizon_days": row.horizon_days,
                "probability": row.probability,
                "point": row.point,
                "baseline_value": row.baseline_value,
                "status": row.status,
                "made_at": _iso(row.made_at),
                "target_date": aware(row.target_date).date().isoformat(),
                "notes": row.notes,
                "actual": outcome.actual if outcome else None,
                "hit": outcome.hit if outcome else None,
                "brier": outcome.brier if outcome else None,
                "resolved_at": _iso(outcome.resolved_at) if outcome else None,
            }
        )
    return items


@router.get("/overview")
def overview(session: Session = Depends(get_session)) -> dict:
    run = _ensure(session)
    state = _latest(session, "ledger.principles")
    calibration = _latest(session, "ledger.calibration")
    forecasts = _forecast_items(session)
    open_items = [item for item in forecasts if item["status"] == "open"]
    resolved_items = [item for item in forecasts if item["status"] == "resolved"]
    next_due = min((item["target_date"] for item in open_items), default=None)
    asof = _iso(run.started_at)[:10] if run.started_at else None
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "asof": asof,
        "run_id": run.id,
        "status": run.status,
        "degraded": bool(run.degraded),
        "degraded_reasons": run.degraded_reasons or [],
        "counts": _counts(session, run.id),
        "principles": _principle_items(session, run.id),
        "principles_claim": state.claim if state else None,
        "calibration": calibration.value if calibration else calibration_summary(session),
        "forecasts": {
            "open": len(open_items),
            "resolved": len(resolved_items),
            "next_due": next_due,
            "items": forecasts,
        },
        "forecast_codes": [
            {"code": code, "label": label} for code, label in FORECAST_CODES.items()
        ],
        "method_id": METHOD,
    }


@router.get("/principles")
def principles(session: Session = Depends(get_session)) -> dict:
    run = _ensure(session)
    items = _principle_items(session, run.id)
    return {
        "asof": _iso(run.started_at)[:10] if run.started_at else None,
        "run_id": run.id,
        "counts": _counts(session, run.id),
        "items": items,
        "categories": CATEGORY_LABELS,
    }


@router.get("/forecasts")
def forecasts(
    status: str | None = Query(None, pattern="^(open|resolved)$"),
    session: Session = Depends(get_session),
) -> dict:
    _ensure(session)
    items = _forecast_items(session, status)
    return {
        "total": len(items),
        "items": items,
        "codes": [{"code": code, "label": label} for code, label in FORECAST_CODES.items()],
    }


@router.get("/calibration")
def calibration(session: Session = Depends(get_session)) -> dict:
    run = _ensure(session)
    row = _latest(session, "ledger.calibration")
    return {
        "run_id": run.id,
        "calibration": row.value if row else calibration_summary(session),
        "claim": row.claim if row else None,
    }


@router.post("/forecasts")
def create_forecast(
    payload: ForecastRequest, session: Session = Depends(get_session)
) -> dict:
    row = register_forecast(
        session,
        code=payload.code,
        direction=payload.direction,
        horizon_days=payload.horizon_days,
        probability=payload.probability,
        point=payload.point,
        baseline_value=payload.baseline_value,
        notes=payload.notes,
    )
    session.commit()
    return {
        "ok": True,
        "id": row.id,
        "code": row.code,
        "direction": row.direction,
        "target_date": aware(row.target_date).date().isoformat(),
    }


@router.post("/run")
def run(session: Session = Depends(get_session)) -> dict:
    result = run_ledger(session)
    return {
        "ok": True,
        "run_id": result["run_id"],
        "status": result["status"],
        "asof": result["asof"],
        "counts": result["counts"],
        "calibration": {
            "n": result["calibration"]["n"],
            "brier": result["calibration"]["brier"],
        },
        "forecasts": len(result["forecasts"]),
    }
