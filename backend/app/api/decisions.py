"""Decision APIs: signals, trade plans, risk checks, backtest, predictions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import AnalyticsResult, Instrument, PlanCheck, Prediction, Signal, TradePlan
from app.platform.db import get_session

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


def _names(session: Session) -> dict[str, str]:
    return {row.id: row.symbol for row in session.scalars(select(Instrument)).all()}


@router.get("/summary")
def summary(session: Session = Depends(get_session)) -> dict:
    names = _names(session)
    signals = session.scalars(select(Signal).order_by(Signal.strength.desc()).limit(12)).all()
    plans = session.scalars(
        select(TradePlan).where(TradePlan.status.in_(["draft", "confirmed", "executed"])).order_by(
            TradePlan.risk_pct.desc()
        ).limit(12)
    ).all()
    checks = session.scalars(select(PlanCheck)).all()
    backtests = session.scalars(
        select(AnalyticsResult).where(AnalyticsResult.kind == "signal_backtest").order_by(
            AnalyticsResult.asof.desc()
        )
    ).all()
    latest_backtest: dict[str, dict] = {}
    for row in backtests:
        latest_backtest.setdefault(row.subject, row.payload)
    open_predictions = session.scalar(
        select(func.count()).select_from(Prediction).where(Prediction.status == "open")
    ) or 0

    checks_by_plan: dict[str, list[dict]] = {}
    for check in checks:
        checks_by_plan.setdefault(check.plan_id, []).append(
            {"rule": check.rule, "passed": check.passed, "detail": check.detail}
        )

    return {
        "signals": [
            {
                "id": row.id,
                "symbol": names.get(row.instrument_id),
                "type": row.type,
                "direction": row.direction,
                "strength": row.strength,
                "note": row.note,
                "params": row.params,
                "ts": row.ts.isoformat(),
            }
            for row in signals
        ],
        "plans": [
            {
                "id": row.id,
                "symbol": names.get(row.instrument_id),
                "side": row.side,
                "entry_low": row.entry_low,
                "entry_high": row.entry_high,
                "stop": row.stop,
                "targets": row.targets,
                "size": row.size,
                "risk_pct": row.risk_pct,
                "time_stop_days": row.time_stop_days,
                "invalidation": row.invalidation,
                "status": row.status,
                "checks": checks_by_plan.get(row.id, []),
            }
            for row in plans
        ],
        "backtest": latest_backtest,
        "open_predictions": int(open_predictions),
        "counts": {"signals": len(signals), "plans": len(plans)},
    }


@router.get("/signals")
def list_signals(
    limit: int = Query(30, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict:
    names = _names(session)
    rows = session.scalars(select(Signal).order_by(Signal.strength.desc()).limit(limit)).all()
    return {
        "data": [
            {
                "id": row.id,
                "symbol": names.get(row.instrument_id),
                "type": row.type,
                "direction": row.direction,
                "strength": row.strength,
                "note": row.note,
                "ts": row.ts.isoformat(),
            }
            for row in rows
        ]
    }


@router.get("/plans")
def list_plans(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    names = _names(session)
    rows = session.scalars(
        select(TradePlan).order_by(TradePlan.created_at.desc()).limit(limit)
    ).all()
    plan_ids = [row.id for row in rows]
    checks = session.scalars(select(PlanCheck).where(PlanCheck.plan_id.in_(plan_ids))).all()
    by_plan: dict[str, list[dict]] = {}
    for check in checks:
        by_plan.setdefault(check.plan_id, []).append(
            {"rule": check.rule, "passed": check.passed, "detail": check.detail}
        )
    return {
        "data": [
            {
                "id": row.id,
                "symbol": names.get(row.instrument_id),
                "side": row.side,
                "entry_low": row.entry_low,
                "entry_high": row.entry_high,
                "stop": row.stop,
                "targets": row.targets,
                "size": row.size,
                "risk_pct": row.risk_pct,
                "time_stop_days": row.time_stop_days,
                "invalidation": row.invalidation,
                "status": row.status,
                "checks": by_plan.get(row.id, []),
            }
            for row in rows
        ]
    }


@router.get("/backtest")
def backtest(session: Session = Depends(get_session)) -> dict:
    rows = session.scalars(
        select(AnalyticsResult).where(AnalyticsResult.kind == "signal_backtest").order_by(
            AnalyticsResult.asof.desc()
        )
    ).all()
    latest: dict[str, dict] = {}
    for row in rows:
        latest.setdefault(row.subject, row.payload)
    return {"data": latest}


@router.get("/predictions")
def predictions(
    limit: int = Query(30, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict:
    rows = session.scalars(select(Prediction).order_by(Prediction.made_at.desc()).limit(limit)).all()
    return {
        "data": [
            {
                "id": row.id,
                "plan_id": row.plan_id,
                "probability": row.probability,
                "horizon_days": row.horizon_days,
                "status": row.status,
                "made_at": row.made_at.isoformat(),
                "brier": row.brier,
            }
            for row in rows
        ]
    }
