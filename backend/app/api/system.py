"""System API: health, jobs, meta."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.core import (
    Alert,
    AnalyticsResult,
    Brief,
    Claim,
    DataCheck,
    Document,
    DocumentBody,
    EconomicEvent,
    Instrument,
    Job,
    JobRun,
    MacroObs,
    MarketBar,
    Quote,
    Signal,
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
    "document_bodies": DocumentBody,
    "claims": Claim,
    "briefs": Brief,
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


@router.get("/data-quality")
def data_quality(session: Session = Depends(get_session)) -> dict:
    checks = session.scalars(
        select(DataCheck).order_by(DataCheck.check_date.desc()).limit(80)
    ).all()
    latest_by_dataset: dict[str, DataCheck] = {}
    for check in checks:
        key = f"{check.kind}:{check.dataset}"
        latest_by_dataset.setdefault(key, check)
    return {
        "data": [
            {
                "kind": check.kind,
                "dataset": check.dataset,
                "symbol": check.symbol,
                "check_date": check.check_date.isoformat(),
                "expected": check.expected,
                "actual": check.actual,
                "deviation": check.deviation,
                "passed": check.passed,
                "detail": check.detail,
            }
            for check in latest_by_dataset.values()
        ],
        "summary": {
            "total": len(latest_by_dataset),
            "passed": sum(1 for check in latest_by_dataset.values() if check.passed),
            "failed": sum(1 for check in latest_by_dataset.values() if not check.passed),
        },
    }


@router.get("/acceptance")
def acceptance(session: Session = Depends(get_session)) -> dict:
    """Automated DoD/acceptance checks (V0.x)."""
    counts = {
        "instruments": int(session.scalar(select(func.count()).select_from(Instrument)) or 0),
        "market_bars": int(session.scalar(select(func.count()).select_from(MarketBar)) or 0),
        "quotes": int(session.scalar(select(func.count()).select_from(Quote)) or 0),
        "macro": int(session.scalar(select(func.count()).select_from(MacroObs)) or 0),
        "calendar": int(session.scalar(select(func.count()).select_from(EconomicEvent)) or 0),
        "documents": int(session.scalar(select(func.count()).select_from(Document)) or 0),
        "bodies": int(session.scalar(select(func.count()).select_from(DocumentBody)) or 0),
        "claims": int(session.scalar(select(func.count()).select_from(Claim)) or 0),
        "briefs": int(session.scalar(select(func.count()).select_from(Brief)) or 0),
        "analytics": int(session.scalar(select(func.count()).select_from(AnalyticsResult)) or 0),
        "signals": int(session.scalar(select(func.count()).select_from(Signal)) or 0),
        "plans": int(session.scalar(select(func.count()).select_from(TradePlan)) or 0),
        "alerts": int(session.scalar(select(func.count()).select_from(Alert)) or 0),
    }
    checks_rows = session.scalars(
        select(DataCheck).order_by(DataCheck.check_date.desc()).limit(80)
    ).all()
    latest: dict[str, DataCheck] = {}
    for check in checks_rows:
        latest.setdefault(f"{check.kind}:{check.dataset}", check)
    quality_failed = sum(1 for check in latest.values() if not check.passed)

    checks = [
        {"name": "行情标的 ≥ 20", "passed": counts["instruments"] >= 20, "detail": counts["instruments"]},
        {"name": "日线 ≥ 10,000", "passed": counts["market_bars"] >= 10000, "detail": counts["market_bars"]},
        {"name": "行情快照 ≥ 20", "passed": counts["quotes"] >= 20, "detail": counts["quotes"]},
        {"name": "宏观观测 ≥ 1,000", "passed": counts["macro"] >= 1000, "detail": counts["macro"]},
        {"name": "财经日历 ≥ 20", "passed": counts["calendar"] >= 20, "detail": counts["calendar"]},
        {"name": "新闻 ≥ 10", "passed": counts["documents"] >= 10, "detail": counts["documents"]},
        {"name": "正文 ≥ 10", "passed": counts["bodies"] >= 10, "detail": counts["bodies"]},
        {"name": "断言 ≥ 50", "passed": counts["claims"] >= 50, "detail": counts["claims"]},
        {"name": "简报 ≥ 1", "passed": counts["briefs"] >= 1, "detail": counts["briefs"]},
        {"name": "分析结果 ≥ 10", "passed": counts["analytics"] >= 10, "detail": counts["analytics"]},
        {"name": "信号 ≥ 1", "passed": counts["signals"] >= 1, "detail": counts["signals"]},
        {"name": "计划 ≥ 1", "passed": counts["plans"] >= 1, "detail": counts["plans"]},
        {"name": "数据质检全部通过", "passed": quality_failed == 0, "detail": f"failed={quality_failed}"},
    ]
    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "counts": counts,
    }
