"""Job runner: executes collection pipelines with JobRun audit records.

Usage:
    python -m app.jobs.runner --list
    python -m app.jobs.runner --job collect_quotes
    python -m app.jobs.runner --all
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import timedelta

from sqlalchemy import select

from app.alerts import scan_alerts
from app.analytics.runner import run_analytics
from app.decision.runner import run_decision
from app.decision.scoring import score_predictions
from app.knowledge import events as event_mod
from app.decision.theses import generate_theses
from app.gold.runner import collect_gold
from app.ingest import pipeline
from app.ingest.backfill import run_backfill
from app.models.base import utcnow
from app.models.core import Job, JobRun
from app.narrative import brief as brief_mod
from app.narrative import monthly as monthly_mod
from app.narrative import weekly as weekly_mod
from app.platform.config import settings
from app.platform.db import SessionLocal
from app.platform.logging import setup_logging

logger = logging.getLogger(__name__)

# A CLI job killed by Ctrl+C / a restart leaves its row 'running'; after this
# long we consider it abandoned and rewrite it as 'interrupted'.
STALE_RUN_MINUTES = 90

def _run_cycle() -> dict:
    """V2.0 周期定位：跑一次完整 EPIC-C 2.0 管线，返回可审计的紧凑摘要。

    完整结果落库在 analysis_runs/analysis_steps/derivations，JobRun 只保留摘要，
    避免 64 KiB 的派生 JSON 把作业日志撑爆。
    """
    from app.cycle.engine import run_cycle

    with SessionLocal() as session:
        result = run_cycle(session)
    long_cycle = result.get("long_cycle") or {}
    short_cycle = result.get("short_cycle") or {}
    alerts = result.get("alerts") or {}
    analogs = result.get("analogs") or {}
    return {
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "asof": result.get("asof"),
        "long_cycle": long_cycle.get("phase"),
        "short_cycle": short_cycle.get("state"),
        "alerts_triggered": alerts.get("triggered"),
        "alerts_unknown": alerts.get("unknown"),
        "analogs": analogs.get("n"),
        "degraded_reasons": result.get("degraded_reasons"),
    }


def _run_timeline() -> dict:
    """把 1500–2026 年表与当下坐标重新入库（数据集改过之后由周日任务刷新）。"""
    from app.timeline.engine import run_timeline

    with SessionLocal() as session:
        result = run_timeline(session)
    return {
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "asof": result.get("asof"),
        "events": result.get("events"),
        "eras": result.get("eras"),
        "lessons": result.get("lessons"),
    }


def _run_ledger() -> dict:
    """原则核对 + 预测对账：命中/接近/不成立/缺数据四态与校准分桶。"""
    from app.ledger.engine import run_ledger

    with SessionLocal() as session:
        result = run_ledger(session)
    counts = result.get("counts") or {}
    calibration = result.get("calibration") or {}
    return {
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "asof": result.get("asof"),
        "principles_hit": counts.get("hit"),
        "principles_near": counts.get("near"),
        "principles_miss": counts.get("miss"),
        "principles_unknown": counts.get("unknown"),
        "brier": calibration.get("brier"),
        "degraded_reasons": result.get("degraded_reasons"),
    }


JOBS = {
    "collect_quotes": pipeline.collect_quotes,
    "collect_daily_bars": pipeline.collect_daily_bars,
    "backfill_history": run_backfill,
    "collect_rates": pipeline.collect_rates,
    "collect_calendar": pipeline.collect_calendar,
    "collect_positions": pipeline.collect_positions,
    "collect_news": pipeline.collect_news,
    "collect_news_slow": lambda: pipeline.collect_news(slow=True),
    "collect_gold": collect_gold,
    "collect_bodies": pipeline.collect_bodies,
    "extract_claims": pipeline.extract_claims,
    "extract_events": event_mod.extract_events,
    "extract_claims_llm": pipeline.extract_claims_llm,
    "check_data_quality": pipeline.check_data_quality,
    "analyze": run_analytics,
    "cycle": _run_cycle,
    "decide": run_decision,
    "theses": generate_theses,
    "score_predictions": score_predictions,
    "ledger": _run_ledger,
    "timeline": _run_timeline,
    "scan_alerts": scan_alerts,
    "brief_premarket": lambda: brief_mod.generate("premarket"),
    "brief_postmarket": lambda: brief_mod.generate("postmarket"),
    "brief_manual": lambda: brief_mod.generate("manual"),
    "weekly_review": weekly_mod.generate_weekly,
    "monthly_review": monthly_mod.generate_monthly,
}


def reconcile_stale_runs(*, all_jobs: bool = False, stale_minutes: int = STALE_RUN_MINUTES) -> int:
    """Mark abandoned 'running' rows as 'interrupted'.

    Runs interrupted by a process restart (or a killed CLI job) never reach the
    finalizer, so their rows would otherwise stay 'running' forever and make the
    dashboard look like jobs are still executing.
    """
    with SessionLocal() as session:
        stmt = select(JobRun).where(JobRun.status == "running")
        if not all_jobs:
            stmt = stmt.where(JobRun.started_at < utcnow() - timedelta(minutes=stale_minutes))
        rows = session.scalars(stmt).all()
        for row in rows:
            row.status = "interrupted"
            row.finished_at = utcnow()
            row.detail = json.dumps(
                {"error": "interrupted (process restart or forced stop)"}, ensure_ascii=False
            )
        if rows:
            session.commit()
            logger.warning("reconciled %s stale job runs", len(rows))
    return len(rows)


def run_job(name: str) -> dict:
    if name not in JOBS:
        raise KeyError(f"unknown job: {name}")

    # A killed run of the same job must not overlap its replacement in the UI.
    reconcile_stale_runs(stale_minutes=STALE_RUN_MINUTES)

    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == name))
        if job is None:
            job = Job(name=name, cron="manual", enabled=True)
            session.add(job)
            session.flush()
        run = JobRun(job_name=name, status="running")
        session.add(run)
        session.commit()
        run_id = run.id

    started = time.perf_counter()
    status = "ok"
    summary: dict = {}
    try:
        summary = JOBS[name]()
    except Exception as exc:  # noqa: BLE001
        status = "error"
        summary = {"error": str(exc)}
        logger.exception("job failed: %s", name)

    duration_ms = int((time.perf_counter() - started) * 1000)
    with SessionLocal() as session:
        run_row = session.get(JobRun, run_id)
        if run_row is not None:
            run_row.finished_at = utcnow()
            run_row.status = status
            run_row.detail = json.dumps(summary, ensure_ascii=False, default=str)[:4000]
        job_row = session.scalar(select(Job).where(Job.name == name))
        if job_row is not None:
            job_row.last_status = status
            job_row.last_run_at = utcnow()
            job_row.last_error = summary.get("error") if status == "error" else None
        session.commit()

    result = {"job": name, "status": status, "duration_ms": duration_ms, "summary": summary}
    logger.info("job %s -> %s (%sms)", name, status, duration_ms)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="EPIC job runner")
    parser.add_argument("--job", choices=sorted(JOBS), help="job name")
    parser.add_argument("--all", action="store_true", help="run all jobs in order")
    parser.add_argument("--list", action="store_true", help="list jobs")
    args = parser.parse_args()

    setup_logging(settings.log_path)
    if args.list:
        for name in JOBS:
            print(name)
        return

    names = list(JOBS) if args.all else ([args.job] if args.job else [])
    if not names:
        parser.print_help()
        return

    failures = 0
    for name in names:
        result = run_job(name)
        print(json.dumps(result, ensure_ascii=False, default=str))
        if result["status"] != "ok":
            failures += 1
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
