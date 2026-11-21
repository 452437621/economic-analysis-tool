"""Startup/periodic scheduling supervisor.

APScheduler drops cron occurrences while the process is down. The supervisor
compares each job with its planned period, replenishes data first, checks
whether the data is actually usable, and only then runs the overdue analysis
chain. If the data is not usable, downstream jobs are skipped with an explicit
``blocked_by`` reason instead of producing a confident but wrong verdict.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jobs.plan import (
    CST,
    GROUP_ORDER,
    JOB_PLANS,
    SUPERVISOR_SKIP,
    DueInfo,
    JobPlan,
    due_info,
)
from app.jobs.runner import run_job
from app.models.base import utcnow
from app.models.core import (
    Instrument,
    Job,
    JobRun,
    MacroObs,
    MacroSeries,
    MarketBar,
    Quote,
    ScheduleCheck,
)
from app.platform.config import settings
from app.platform.coverage import FRESH_DAYS_BY_FREQ
from app.platform.db import SessionLocal
from app.platform.writelock import write_lock

logger = logging.getLogger(__name__)

_CHECK_LOCK = threading.Lock()
STALE_RUN_MINUTES = 90
LOW_FREQ_DEFAULT = 45
REQUIRED_BARS = frozenset({"AU", "AG", "CU", "SC", "000300", "XAUUSD", "DXY", "SPX"})
CRITICAL_MACRO = frozenset({"US10Y", "US2Y", "US10Y_REAL", "EFFR", "SOFR", "CN10Y"})


class ScheduleBusy(RuntimeError):
    """Another schedule check is already running in this process."""


@dataclass
class Readiness:
    status: str
    reasons: list[dict] = field(default_factory=list)
    datasets: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"

    def as_dict(self) -> dict:
        return {"status": self.status, "reasons": self.reasons, "datasets": self.datasets}


def _aware(value: datetime | None, tz=timezone.utc) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value


def _cst(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(CST)
    return _aware(value).astimezone(CST)  # type: ignore[union-attr]


def _json_safe(value):
    """Make a supervisor report JSON-column safe (datetimes/paths -> str)."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _running_jobs(session: Session, now: datetime) -> set[str]:
    cutoff = now.astimezone(timezone.utc) - timedelta(minutes=STALE_RUN_MINUTES)
    rows = session.execute(
        select(JobRun.job_name)
        .where(JobRun.status == "running", JobRun.started_at >= cutoff)
        .distinct()
    ).all()
    return {row[0] for row in rows}


def _job_map(session: Session) -> dict[str, Job]:
    return {row.name: row for row in session.scalars(select(Job)).all()}


def schedule_status(session: Session, now: datetime | None = None) -> dict:
    """Live per-job schedule state used by the API and the supervisor."""
    current = _cst(now)
    now_utc = current.astimezone(timezone.utc)
    jobs = _job_map(session)
    running = _running_jobs(session, now_utc)
    rows: list[dict] = []
    for plan in JOB_PLANS.values():
        job = jobs.get(plan.name)
        enabled = True if job is None else bool(job.enabled)
        llm_gate = plan.name == "extract_claims_llm" and not settings.llm_available
        if llm_gate:
            enabled = False
        last_run = job.last_run_at if job else None
        info: DueInfo = due_info(
            plan,
            last_run,
            current,
            enabled=enabled,
            running=plan.name in running,
        )
        if llm_gate:
            info.reason = "LLM 未配置，跳过"
        rows.append(
            {
                "name": plan.name,
                "group": plan.group,
                "cron": plan.cron_label,
                "period_seconds": plan.period_seconds,
                "last_run_at": _iso(_aware(last_run)),
                "due_at": _iso(info.due_at),
                "overdue": info.overdue,
                "late_seconds": info.late_seconds,
                "action": info.action,
                "reason": info.reason,
                "depends_on": list(plan.depends_on),
                "critical": plan.critical,
                "data_requirements": list(plan.data_requirements),
                "enabled": enabled,
                "running": plan.name in running,
            }
        )
    rows.sort(key=lambda row: (GROUP_ORDER.get(row["group"], 99), JOB_PLANS[row["name"]].order))
    return {
        "as_of": _iso(now_utc),
        "timezone": settings.timezone,
        "summary": {
            "total": len(rows),
            "overdue": sum(1 for row in rows if row["overdue"]),
            "disabled": sum(1 for row in rows if not row["enabled"]),
            "running": sum(1 for row in rows if row["running"]),
        },
        "jobs": rows,
    }


def _fresh(ts: datetime | None, freq: str | None, now: datetime) -> bool:
    if ts is None:
        return False
    age_days = (now - _aware(ts)).days  # type: ignore[arg-type]
    window = FRESH_DAYS_BY_FREQ.get((freq or "m").lower(), LOW_FREQ_DEFAULT)
    return age_days <= window


def assess_readiness(session: Session, now: datetime | None = None) -> Readiness:
    """Can the local database support a meaningful analysis run right now?"""
    current = _cst(now).astimezone(timezone.utc)
    reasons: list[dict] = []

    bars_count = int(
        session.scalar(
            select(func.count()).select_from(MarketBar).where(MarketBar.timeframe == "1d")
        )
        or 0
    )
    bar_rows = session.execute(
        select(Instrument.symbol, func.max(MarketBar.ts_utc))
        .join(MarketBar, MarketBar.instrument_id == Instrument.id)
        .where(MarketBar.timeframe == "1d", Instrument.active.is_(True))
        .group_by(Instrument.id)
    ).all()
    bar_latest = {symbol: ts for symbol, ts in bar_rows if ts is not None}
    missing_bars = sorted(REQUIRED_BARS - set(bar_latest))
    stale_required = sorted(
        symbol
        for symbol, ts in bar_latest.items()
        if symbol in REQUIRED_BARS and (current - _aware(ts)).days > 10  # type: ignore[operator]
    )
    stale_bars = sorted(
        symbol
        for symbol, ts in bar_latest.items()
        if (current - _aware(ts)).days > 10  # type: ignore[operator]
    )
    latest_bar = max(bar_latest.values(), default=None)
    bar_age_days = (current - _aware(latest_bar)).days if latest_bar else None  # type: ignore[arg-type]
    bars_ok = (
        bars_count >= 1000
        and not missing_bars
        and not stale_required
        and (bar_age_days is not None and bar_age_days <= 10)
    )
    if not bars_ok:
        reasons.append(
            {
                "code": "readiness.daily_bars",
                "severity": "critical",
                "message": (
                    f"日线不完整：{bars_count} 根，关键标的缺失 {missing_bars or '无'}，"
                    f"最新 {bar_age_days if bar_age_days is not None else '无'} 天前"
                ),
                "action_job": "collect_daily_bars",
            }
        )

    macro_count = int(session.scalar(select(func.count()).select_from(MacroObs)) or 0)
    macro_rows = session.execute(
        select(MacroSeries.code, MacroSeries.freq, func.max(MacroObs.ts_utc))
        .outerjoin(MacroObs, MacroObs.series_id == MacroSeries.id)
        .group_by(MacroSeries.id)
    ).all()
    fresh_codes = {code for code, freq, ts in macro_rows if _fresh(ts, freq, current)}
    missing_macro = sorted(CRITICAL_MACRO - fresh_codes)
    fresh_ratio = len(fresh_codes) / len(macro_rows) if macro_rows else 0.0
    macro_ok = macro_count >= 500 and not missing_macro and fresh_ratio >= 0.5
    if not macro_ok:
        reasons.append(
            {
                "code": "readiness.macro",
                "severity": "critical",
                "message": (
                    f"宏观序列不足：{macro_count} 条，关键序列未更新 {missing_macro or '无'}，"
                    f"新鲜占比 {fresh_ratio * 100:.0f}%"
                ),
                "action_job": "collect_macro",
            }
        )

    quote_latest = session.scalar(select(func.max(Quote.ts_utc)))
    quote_age_days = (current - _aware(quote_latest)).days if quote_latest else None  # type: ignore[arg-type]
    quote_cutoff = current - timedelta(days=3)
    quote_recent = int(
        session.scalar(
            select(func.count(func.distinct(Quote.instrument_id))).where(Quote.ts_utc >= quote_cutoff)
        )
        or 0
    )
    quotes_ok = quote_age_days is not None and quote_age_days <= 3 and quote_recent >= 20
    if not quotes_ok:
        reasons.append(
            {
                "code": "readiness.quotes",
                "severity": "warn",
                "message": (
                    f"行情快照不足：最近 {quote_age_days if quote_age_days is not None else '无'} 天，"
                    f"近 3 天覆盖 {quote_recent} 个标的"
                ),
                "action_job": "collect_quotes",
            }
        )

    if not bars_ok or not macro_ok:
        status = "blocked"
    elif not quotes_ok or fresh_ratio < 0.8:
        status = "degraded"
    else:
        status = "ok"
    return Readiness(
        status=status,
        reasons=reasons,
        datasets={
            "daily_bars": {
                "status": "ok" if bars_ok else "blocked",
                "rows": bars_count,
                "missing_symbols": missing_bars,
                "stale_symbols": stale_bars[:20],
                "latest_age_days": bar_age_days,
            },
            "macro": {
                "status": "ok" if macro_ok else "blocked",
                "rows": macro_count,
                "series": len(macro_rows),
                "fresh_ratio": round(fresh_ratio, 3),
                "missing_codes": missing_macro,
            },
            "quotes": {
                "status": "ok" if quotes_ok else "degraded",
                "latest_age_days": quote_age_days,
                "symbols_3d": quote_recent,
            },
        },
    )


def _write_skipped(session: Session, name: str, now: datetime, reasons: list[dict], blocked_by: list[str]) -> None:
    detail = json.dumps(
        {"blocked_by": blocked_by, "reasons": reasons[:5]}, ensure_ascii=False, default=str
    )[:4000]
    session.add(
        JobRun(
            job_name=name,
            started_at=now,
            finished_at=now,
            status="skipped",
            detail=detail,
        )
    )


def _job_enabled(session: Session, name: str) -> bool:
    job = session.scalar(select(Job).where(Job.name == name))
    return True if job is None else bool(job.enabled)


def _job_last_run(session: Session, name: str) -> datetime | None:
    job = session.scalar(select(Job).where(Job.name == name))
    return job.last_run_at if job else None


def _execute_plan(plan: JobPlan, *, now_cst: datetime, force: bool, dry_run: bool) -> dict | None:
    """Re-check due state immediately before execution (another thread may have run it)."""
    now_utc = now_cst.astimezone(timezone.utc)
    with SessionLocal() as session:
        enabled = _job_enabled(session, plan.name)
        running = plan.name in _running_jobs(session, now_utc)
        info = due_info(
            plan,
            _job_last_run(session, plan.name),
            now_cst,
            enabled=enabled,
            running=running,
            force=force,
        )
        if not info.overdue:
            return None
    if dry_run:
        return {"name": plan.name, "status": "dry_run", "overdue": True, "reason": info.reason}
    started = time.perf_counter()
    with write_lock():
        result = run_job(plan.name)
    return {
        "name": plan.name,
        "status": result.get("status"),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "summary": result.get("summary"),
        "overdue": True,
        "reason": info.reason,
    }


def _readiness_retry_jobs(readiness: Readiness) -> list[str]:
    jobs: list[str] = []
    for reason in readiness.reasons:
        action = reason.get("action_job")
        if action and action not in jobs:
            jobs.append(action)
    return jobs


def _overdue_names(status: dict, groups: set[str], *, startup: bool) -> list[str]:
    names: list[str] = []
    for row in status["jobs"]:
        if row["group"] not in groups or not row["overdue"]:
            continue
        if row["name"] in SUPERVISOR_SKIP:
            continue
        plan = JOB_PLANS.get(row["name"])
        if plan is None:
            continue
        if startup and not plan.startup:
            continue
        names.append(row["name"])
    names.sort(key=lambda name: (GROUP_ORDER.get(JOB_PLANS[name].group, 99), JOB_PLANS[name].order))
    return names


def run_schedule_check(
    *,
    trigger: str = "manual",
    run_data: bool = True,
    run_downstream: bool = True,
    force: bool = False,
    dry_run: bool = False,
    backoff_seconds: int = 0,
    now: datetime | None = None,
) -> dict:
    """Run the scheduling self-check, optionally executing overdue jobs."""
    if not _CHECK_LOCK.acquire(blocking=False):
        raise ScheduleBusy("another schedule check is already running")
    current = _cst(now)
    now_utc = current.astimezone(timezone.utc)
    check_id: str | None = None
    report: dict = {
        "trigger": trigger,
        "started_at": _iso(now_utc),
        "dry_run": dry_run,
        "readiness": None,
        "jobs": [],
        "retries": [],
        "blocked": [],
    }
    try:
        if not dry_run:
            # Creating the audit row must live inside the try: a transient SQLite
            # lock here must not leak the check lock for the rest of the process.
            with SessionLocal() as session:
                row = ScheduleCheck(
                    trigger=trigger,
                    status="running",
                    data_status=None,
                    started_at=now_utc,
                )
                session.add(row)
                session.commit()
                check_id = row.id
        if run_data:
            with SessionLocal() as session:
                status = schedule_status(session, current)
            data_names = _overdue_names(status, {"data", "quality"}, startup=trigger == "startup")
            for name in data_names:
                plan = JOB_PLANS[name]
                try:
                    result = _execute_plan(
                        plan, now_cst=current, force=force, dry_run=dry_run
                    )
                except Exception as exc:  # noqa: BLE001 - one job must not kill the check
                    logger.exception("schedule data job failed: %s", name)
                    result = {"name": name, "status": "error", "reason": str(exc)[:500]}
                if result is not None:
                    report["jobs"].append(result)

        with SessionLocal() as session:
            readiness = assess_readiness(session, current)
        report["readiness"] = readiness.as_dict()

        if run_data and readiness.blocked and not dry_run:
            for name in _readiness_retry_jobs(readiness):
                if name not in JOB_PLANS or name in SUPERVISOR_SKIP:
                    continue
                plan = JOB_PLANS[name]
                previous = next(
                    (item for item in report["jobs"] if item.get("name") == name), None
                )
                if previous is not None and previous.get("status") == "ok":
                    continue
                if backoff_seconds > 0:
                    time.sleep(backoff_seconds)
                try:
                    result = _execute_plan(
                        plan, now_cst=current, force=True, dry_run=dry_run
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("schedule retry failed: %s", name)
                    result = {"name": name, "status": "error", "reason": str(exc)[:500]}
                if result is not None:
                    report["retries"].append(result)
                    report["jobs"].append(result)
            with SessionLocal() as session:
                readiness = assess_readiness(session, current)
            report["readiness"] = readiness.as_dict()

        if run_downstream:
            with SessionLocal() as session:
                status = schedule_status(session, current)
            downstream = _overdue_names(
                status, {"derive", "analysis", "decision", "report", "system"}, startup=trigger == "startup"
            )
            failed = {
                item["name"]
                for item in report["jobs"]
                if item.get("status") in {"error", "degraded", "skipped"}
            }
            with SessionLocal() as session:
                if readiness.blocked:
                    reasons = readiness.reasons
                    for name in downstream:
                        if not dry_run:
                            _write_skipped(session, name, now_utc, reasons, ["readiness"])
                        report["blocked"].append(
                            {"name": name, "blocked_by": ["readiness"], "reasons": reasons}
                        )
                    if not dry_run:
                        session.commit()
                else:
                    for name in downstream:
                        plan = JOB_PLANS[name]
                        blocked_by = [dep for dep in plan.depends_on if dep in failed]
                        if blocked_by:
                            if not dry_run:
                                _write_skipped(
                                    session,
                                    name,
                                    now_utc,
                                    [{"code": "dependency", "message": "上游作业失败或跳过"}],
                                    blocked_by,
                                )
                            report["blocked"].append({"name": name, "blocked_by": blocked_by})
                            # A blocked job must also block its own dependents,
                            # otherwise e.g. cycle/lenses run after analyze was skipped.
                            failed.add(name)
                            continue
                        if not dry_run:
                            session.commit()
                        try:
                            result = _execute_plan(
                                plan, now_cst=current, force=force, dry_run=dry_run
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.exception("schedule downstream job failed: %s", name)
                            result = {"name": name, "status": "error", "reason": str(exc)[:500]}
                        if result is not None:
                            report["jobs"].append(result)
                            if result.get("status") in {"error", "degraded", "skipped"}:
                                failed.add(name)
                    if not dry_run:
                        session.commit()

        errors = [
            item
            for item in report["jobs"]
            if item.get("status") in {"error", "degraded", "skipped"}
        ]
        if readiness.blocked:
            status_value = "blocked"
        elif errors:
            status_value = "degraded"
        else:
            status_value = "ok"
        report["status"] = status_value
        report["finished_at"] = _iso(datetime.now(timezone.utc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("schedule check failed")
        report["status"] = "error"
        report["error"] = str(exc)[:1000]
        report["finished_at"] = _iso(datetime.now(timezone.utc))
        if check_id and not dry_run:
            with SessionLocal() as session:
                row = session.get(ScheduleCheck, check_id)
                if row is not None:
                    row.status = "error"
                    row.finished_at = utcnow()
                    row.error = report["error"]
                    row.report = _json_safe(report)
                    session.commit()
        raise
    finally:
        try:
            if check_id and not dry_run:
                with SessionLocal() as session:
                    row = session.get(ScheduleCheck, check_id)
                    if row is not None:
                        row.status = str(report.get("status") or "error")
                        row.data_status = (report.get("readiness") or {}).get("status")
                        row.finished_at = row.finished_at or utcnow()
                        row.report = _json_safe(report)
                        session.commit()
        finally:
            # An audit-write failure must never leave the process-wide lock held.
            _CHECK_LOCK.release()
    return report


def catch_up_jobs(now: datetime | None = None) -> list[str]:
    """Compatibility wrapper: startup catch-up returns executed job names."""
    report = run_schedule_check(trigger="startup", now=now)
    return [
        str(item["name"])
        for item in report.get("jobs") or []
        if item.get("status") not in {"skipped", "dry_run"}
    ]


def latest_reports(session: Session, limit: int = 1) -> list[dict]:
    rows = session.scalars(
        select(ScheduleCheck).order_by(ScheduleCheck.started_at.desc()).limit(max(1, limit))
    ).all()
    return [
        {
            "id": row.id,
            "trigger": row.trigger,
            "status": row.status,
            "data_status": row.data_status,
            "started_at": _iso(_aware(row.started_at)),
            "finished_at": _iso(_aware(row.finished_at)),
            "report": row.report,
            "error": row.error,
        }
        for row in rows
    ]


def reconcile_stale_checks(stale_minutes: int = STALE_RUN_MINUTES) -> int:
    """Mark a schedule check abandoned by a killed process as interrupted."""
    cutoff = utcnow() - timedelta(minutes=stale_minutes)
    with SessionLocal() as session:
        rows = session.scalars(
            select(ScheduleCheck).where(
                ScheduleCheck.status == "running", ScheduleCheck.started_at < cutoff
            )
        ).all()
        for row in rows:
            row.status = "interrupted"
            row.finished_at = utcnow()
            row.error = "interrupted (process restart or forced stop)"
        if rows:
            session.commit()
    return len(rows)


def as_readiness_dict(readiness: Readiness) -> dict:
    return asdict(readiness)
