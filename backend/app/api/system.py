"""System API: health, jobs, meta, scheduling and data quality."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ingest import quality
from app.jobs.repair import latest_repair, run_repair
from app.jobs.runner import JOBS, run_job_locked
from app.jobs.supervisor import (
    ScheduleBusy,
    latest_reports,
    schedule_status,
    run_schedule_check,
)
from app.models.base import utcnow
from app.models.core import (
    Brief,
    Claim,
    Document,
    DocumentBody,
    Instrument,
    Job,
    JobRun,
    MacroObs,
    MarketBar,
    Quote,
    ScheduleCheck,
    Thesis,
    TradePlan,
)
from app.platform.config import settings
from app.platform.coverage import (
    QUALITY_METHOD,
    data_quality_pct,
    job_health,
    latest_sync,
    series_coverage,
)
from app.platform.acceptance import build_acceptance
from app.platform.db import get_session
from app.platform.quality_gate import assess as assess_quality
from app.platform.scheduler import scheduler_snapshot
from app.platform.writelock import write_lock

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
        "llm_enabled": settings.llm_available,
    }


@router.get("/jobs")
def list_jobs(session: Session = Depends(get_session)) -> dict:
    rows = session.scalars(select(Job).order_by(Job.name)).all()
    # 每个任务的累计调度次数（执行历史条数），系统状态页点击次数弹框看明细。
    run_counts = dict(
        session.execute(select(JobRun.job_name, func.count()).group_by(JobRun.job_name)).all()
    )
    schedule = {row["name"]: row for row in schedule_status(session)["jobs"]}
    data = []
    for row in rows:
        plan = schedule.get(row.name) or {}
        data.append(
            {
                "name": row.name,
                "cron": row.cron,
                "description": row.description,
                "enabled": row.enabled,
                "last_status": row.last_status,
                "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
                "last_error": row.last_error,
                "run_count": int(run_counts.get(row.name, 0)),
                "group": plan.get("group"),
                "period_seconds": plan.get("period_seconds"),
                "due_at": plan.get("due_at"),
                "overdue": bool(plan.get("overdue")),
                "action": plan.get("action"),
                "overdue_reason": plan.get("reason"),
                "depends_on": plan.get("depends_on") or [],
                "critical": bool(plan.get("critical")),
            }
        )
    return {"data": data}


@router.get("/job-runs")
def list_job_runs(
    limit: int = 20,
    job_name: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    limit = max(1, min(limit, 200))
    stmt = select(JobRun)
    if job_name:
        stmt = stmt.where(JobRun.job_name == job_name)
    stmt = stmt.order_by(JobRun.started_at.desc()).limit(limit)
    rows = session.scalars(stmt).all()
    data = []
    for row in rows:
        duration_ms = None
        if row.started_at and row.finished_at:
            duration_ms = max(0, int((row.finished_at - row.started_at).total_seconds() * 1000))
        data.append(
            {
                "id": row.id,
                "job_name": row.job_name,
                "status": row.status,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "duration_ms": duration_ms,
                "detail": row.detail,
            }
        )
    return {"data": data}


@router.get("/schedule")
def schedule(session: Session = Depends(get_session)) -> dict:
    """Live per-job schedule state (period, due time, overdue, action)."""
    return schedule_status(session)


@router.get("/schedule-check")
def get_schedule_check(
    limit: int = 1,
    session: Session = Depends(get_session),
) -> dict:
    limit = max(1, min(limit, 20))
    return {
        "data": latest_reports(session, limit),
        "schedule": schedule_status(session),
    }


@router.get("/schedule-check/{check_id}")
def get_schedule_check_one(
    check_id: str,
    session: Session = Depends(get_session),
) -> dict:
    row = session.get(ScheduleCheck, check_id)
    if row is None:
        raise HTTPException(status_code=404, detail="schedule check not found")
    return {
        "id": row.id,
        "trigger": row.trigger,
        "status": row.status,
        "data_status": row.data_status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "report": row.report,
        "error": row.error,
    }


def _run_check_background(**kwargs) -> None:
    try:
        run_schedule_check(**kwargs)
    except ScheduleBusy:
        pass
    except Exception:  # pragma: no cover - background thread must not crash the app
        import logging

        logging.getLogger(__name__).exception("background schedule check failed")


@router.post("/schedule-check")
def post_schedule_check(payload: dict | None = Body(default=None)) -> dict:
    body = payload or {}
    wait = bool(body.get("wait", False))
    kwargs = {
        "trigger": str(body.get("trigger") or "manual"),
        "run_data": bool(body.get("run_data", True)),
        "run_downstream": bool(body.get("run_downstream", True)),
        "force": bool(body.get("force", False)),
        "dry_run": bool(body.get("dry_run", False)),
        "backoff_seconds": int(body.get("backoff_seconds", 0) or 0),
    }
    if wait:
        try:
            return run_schedule_check(**kwargs)
        except ScheduleBusy as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        # Probe the lock without blocking the request thread; the worker acquires it.
        from app.jobs import supervisor as supervisor_mod

        if supervisor_mod._CHECK_LOCK.locked():  # noqa: SLF001 - intentional quick probe
            raise HTTPException(status_code=409, detail="schedule check already running")
    except HTTPException:
        raise
    threading.Thread(target=_run_check_background, kwargs=kwargs, daemon=True).start()
    return {"accepted": True, "trigger": kwargs["trigger"]}


@router.post("/jobs/{name}/run")
def run_named_job(name: str, session: Session = Depends(get_session)) -> dict:
    if name not in JOBS:
        raise HTTPException(status_code=404, detail=f"unknown job: {name}")
    cutoff = utcnow() - timedelta(minutes=90)
    running = session.scalar(
        select(JobRun.id)
        .where(
            JobRun.job_name == name,
            JobRun.status == "running",
            JobRun.started_at >= cutoff,
        )
        .limit(1)
    )
    if running is not None:
        raise HTTPException(status_code=409, detail=f"{name} is already running")

    def _worker() -> None:
        try:
            run_job_locked(name)
        except Exception:  # pragma: no cover
            import logging

            logging.getLogger(__name__).exception("manual job failed: %s", name)

    threading.Thread(target=_worker, daemon=True).start()
    return {"accepted": True, "job": name}


@router.post("/data-quality/repair")
def repair_data(payload: dict | None = Body(default=None)) -> dict:
    body = payload or {}
    kwargs = {
        "recheck": bool(body.get("recheck", True)),
        "force": bool(body.get("force", False)),
        "max_jobs": body.get("max_actions"),
    }
    if bool(body.get("wait", False)):
        try:
            with write_lock(timeout=10):
                return run_repair(**kwargs)
        except TimeoutError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc

    def _worker() -> None:
        try:
            with write_lock():
                run_repair(**kwargs)
        except Exception:  # pragma: no cover
            import logging

            logging.getLogger(__name__).exception("background repair failed")

    threading.Thread(target=_worker, daemon=True).start()
    return {"accepted": True}


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
    batch_id, rows = quality.latest_batch(session)
    age = quality.batch_age_seconds(session)
    stale = age is None or age > 36 * 3600
    checks = list(rows)
    checks.sort(key=lambda check: (check.passed, check.kind, check.dataset, check.symbol or ""))
    return {
        "batch_id": batch_id,
        "checked_at": checks[0].check_date.isoformat() if checks else None,
        "age_seconds": int(age) if age is not None else None,
        "stale": stale,
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
                "severity": check.severity or ("info" if check.passed else "warn"),
                "cause": check.cause,
                "impact": check.impact,
                "remediation": check.remediation,
                "action_job": check.action_job,
            }
            for check in checks
        ],
        "summary": {
            "total": len(checks),
            "passed": sum(1 for check in checks if check.passed),
            "failed": sum(1 for check in checks if not check.passed),
            "unknown": 0 if checks else 1,
            "by_severity": quality.severity_counts(checks),
        },
        "repair": {
            "jobs": quality.remediation_jobs(checks),
            "last_run": latest_repair(session),
        },
    }


@router.get("/coverage")
def coverage(session: Session = Depends(get_session)) -> dict:
    """Data coverage headline for the V2.0 UI (never fails on an empty database)."""
    series_covered, series_total = series_coverage(session)
    jobs_ok, jobs_total = job_health(session)
    return {
        "data_quality_pct": data_quality_pct(series_covered, series_total, jobs_ok, jobs_total),
        "series_covered": series_covered,
        "series_total": series_total,
        "last_sync": latest_sync(session),
        "jobs_ok": jobs_ok,
        "jobs_total": jobs_total,
        "as_of": utcnow().isoformat(),
        "method": QUALITY_METHOD,
    }


@router.get("/quality-gate")
def quality_gate(domain: str | None = None, session: Session = Depends(get_session)) -> dict:
    """Global quality gate used by analysis/decision pages."""
    return assess_quality(session, domains=[domain] if domain else None)


@router.get("/acceptance")
def acceptance(session: Session = Depends(get_session)) -> dict:
    """Automated DoD/acceptance checks with detailed failure explanations."""
    return build_acceptance(session)
