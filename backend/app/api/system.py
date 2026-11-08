"""System API: health, jobs, meta."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.core import (
    Claim,
    Document,
    Instrument,
    Job,
    JobRun,
    MacroObs,
    MarketBar,
    Quote,
    Thesis,
    TradePlan,
)
from app.platform.config import settings
from app.platform.db import get_session
from app.platform.scheduler import scheduler_snapshot

router = APIRouter(prefix="/api/system", tags=["system"])

_COUNTED = {
    "instruments": Instrument,
    "quotes": Quote,
    "market_bars": MarketBar,
    "macro_observations": MacroObs,
    "documents": Document,
    "claims": Claim,
    "theses": Thesis,
    "trade_plans": TradePlan,
}


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    db_ok = True
    db_error: str | None = None
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive
        db_ok = False
        db_error = str(exc)

    counts: dict[str, int] = {}
    if db_ok:
        for name, model in _COUNTED.items():
            counts[name] = int(session.scalar(select(func.count()).select_from(model)) or 0)

    local_now = datetime.now(ZoneInfo(settings.timezone))
    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.env,
        "time_utc": utcnow().isoformat(),
        "time_local": local_now.isoformat(),
        "timezone": settings.timezone,
        "database": {
            "ok": db_ok,
            "engine": "sqlite" if settings.db_url.startswith("sqlite") else "other",
            "error": db_error,
        },
        "scheduler": scheduler_snapshot(),
        "counts": counts,
    }


@router.get("/jobs")
def list_jobs(session: Session = Depends(get_session)) -> dict:
    rows = session.scalars(select(Job).order_by(Job.name)).all()
    return {
        "data": [
            {
                "name": row.name,
                "cron": row.cron,
                "enabled": row.enabled,
                "last_status": row.last_status,
                "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
                "last_error": row.last_error,
            }
            for row in rows
        ]
    }


@router.get("/job-runs")
def list_job_runs(limit: int = 20, session: Session = Depends(get_session)) -> dict:
    limit = max(1, min(limit, 200))
    rows = session.scalars(select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)).all()
    return {
        "data": [
            {
                "job_name": row.job_name,
                "status": row.status,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "detail": row.detail,
            }
            for row in rows
        ]
    }


@router.get("/meta")
def meta() -> dict:
    """Safe-to-expose configuration summary (never returns secrets)."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "timezone": settings.timezone,
        "llm_model": settings.llm_model,
        "llm_reasoner_model": settings.llm_reasoner_model,
        "llm_daily_budget_usd": settings.llm_daily_budget_usd,
        "data_dir": str(settings.data_dir),
    }
