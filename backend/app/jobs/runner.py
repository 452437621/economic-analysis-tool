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

from sqlalchemy import select

from app.alerts import scan_alerts
from app.analytics.runner import run_analytics
from app.decision.runner import run_decision
from app.decision.scoring import score_predictions
from app.decision.theses import generate_theses
from app.ingest import pipeline
from app.models.base import utcnow
from app.models.core import Job, JobRun
from app.narrative import brief as brief_mod
from app.narrative import monthly as monthly_mod
from app.narrative import weekly as weekly_mod
from app.platform.config import settings
from app.platform.db import SessionLocal
from app.platform.logging import setup_logging

logger = logging.getLogger(__name__)

JOBS = {
    "collect_quotes": pipeline.collect_quotes,
    "collect_daily_bars": pipeline.collect_daily_bars,
    "collect_rates": pipeline.collect_rates,
    "collect_calendar": pipeline.collect_calendar,
    "collect_positions": pipeline.collect_positions,
    "collect_news": pipeline.collect_news,
    "collect_bodies": pipeline.collect_bodies,
    "extract_claims": pipeline.extract_claims,
    "extract_claims_llm": pipeline.extract_claims_llm,
    "check_data_quality": pipeline.check_data_quality,
    "analyze": run_analytics,
    "decide": run_decision,
    "theses": generate_theses,
    "score_predictions": score_predictions,
    "scan_alerts": scan_alerts,
    "brief_premarket": lambda: brief_mod.generate("premarket"),
    "brief_postmarket": lambda: brief_mod.generate("postmarket"),
    "brief_manual": lambda: brief_mod.generate("manual"),
    "weekly_review": weekly_mod.generate_weekly,
    "monthly_review": monthly_mod.generate_monthly,
}


def run_job(name: str) -> dict:
    if name not in JOBS:
        raise KeyError(f"unknown job: {name}")

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
