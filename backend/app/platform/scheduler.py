"""Background scheduler: heartbeat + data collection jobs."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.models.base import utcnow
from app.models.core import Job
from app.platform.config import settings
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

CST = ZoneInfo(settings.timezone)
scheduler = AsyncIOScheduler(timezone=CST)


def _heartbeat_sync() -> None:
    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == "heartbeat"))
        if job is None:
            job = Job(name="heartbeat", cron="every 60s", enabled=True)
            session.add(job)
        job.last_status = "ok"
        job.last_run_at = utcnow()
        job.last_error = None
        session.commit()


async def heartbeat_job() -> None:
    try:
        await asyncio.to_thread(_heartbeat_sync)
    except Exception:  # pragma: no cover - defensive
        logger.exception("heartbeat job failed")


def _collector(name: str):
    async def _run() -> None:
        from app.jobs.runner import run_job

        try:
            await asyncio.to_thread(run_job, name)
        except Exception:  # pragma: no cover - defensive
            logger.exception("scheduled job failed: %s", name)

    return _run


def _register_collectors() -> None:
    now = datetime.now(CST)
    scheduler.add_job(
        _collector("collect_quotes"),
        trigger=IntervalTrigger(seconds=300),
        id="collect_quotes",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now + timedelta(seconds=3),
    )
    scheduler.add_job(
        _collector("collect_news"),
        trigger=IntervalTrigger(seconds=180),
        id="collect_news",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now + timedelta(seconds=8),
    )
    scheduler.add_job(
        _collector("collect_news_slow"),
        trigger=CronTrigger(hour=8, minute=15, timezone=CST),
        id="collect_news_slow",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("collect_news_slow"),
        trigger=DateTrigger(run_date=now + timedelta(seconds=55)),
        id="collect_news_slow_bootstrap",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _collector("collect_rates"),
        trigger=IntervalTrigger(hours=6),
        id="collect_rates",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now + timedelta(seconds=15),
    )
    scheduler.add_job(
        _collector("collect_calendar"),
        trigger=IntervalTrigger(hours=6),
        id="collect_calendar",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now + timedelta(seconds=20),
    )
    scheduler.add_job(
        _collector("collect_positions"),
        trigger=CronTrigger(hour=15, minute=45, timezone=CST),
        id="collect_positions",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("collect_positions"),
        trigger=DateTrigger(run_date=now + timedelta(seconds=25)),
        id="collect_positions_bootstrap",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _collector("collect_bodies"),
        trigger=IntervalTrigger(seconds=600),
        id="collect_bodies",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now + timedelta(seconds=60),
    )
    scheduler.add_job(
        _collector("extract_claims"),
        trigger=IntervalTrigger(seconds=900),
        id="extract_claims",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now + timedelta(seconds=120),
    )
    if settings.llm_available:
        scheduler.add_job(
            _collector("extract_claims_llm"),
            trigger=IntervalTrigger(seconds=1200),
            id="extract_claims_llm",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=now + timedelta(seconds=180),
        )
    scheduler.add_job(
        _collector("check_data_quality"),
        trigger=CronTrigger(hour=15, minute=50, timezone=CST),
        id="check_data_quality",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("analyze"),
        trigger=CronTrigger(hour=16, minute=10, timezone=CST),
        id="analyze_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("analyze"),
        trigger=DateTrigger(run_date=now + timedelta(seconds=240)),
        id="analyze_bootstrap",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _collector("decide"),
        trigger=CronTrigger(hour=16, minute=30, timezone=CST),
        id="decide_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("decide"),
        trigger=DateTrigger(run_date=now + timedelta(seconds=300)),
        id="decide_bootstrap",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _collector("theses"),
        trigger=DateTrigger(run_date=now + timedelta(seconds=330)),
        id="theses_bootstrap",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _collector("theses"),
        trigger=CronTrigger(hour=16, minute=35, timezone=CST),
        id="theses_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("scan_alerts"),
        trigger=IntervalTrigger(seconds=300),
        id="scan_alerts",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now + timedelta(seconds=45),
    )
    scheduler.add_job(
        _collector("score_predictions"),
        trigger=CronTrigger(hour=17, minute=0, timezone=CST),
        id="score_predictions",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("brief_premarket"),
        trigger=CronTrigger(hour=7, minute=30, timezone=CST),
        id="brief_premarket",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("brief_postmarket"),
        trigger=CronTrigger(hour=21, minute=0, timezone=CST),
        id="brief_postmarket",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("weekly_review"),
        trigger=CronTrigger(day_of_week="sun", hour=10, minute=0, timezone=CST),
        id="weekly_review",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("monthly_review"),
        trigger=CronTrigger(day=1, hour=10, minute=0, timezone=CST),
        id="monthly_review",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    # 首次启动回补日线，之后按收盘时点更新
    scheduler.add_job(
        _collector("collect_daily_bars"),
        trigger=DateTrigger(run_date=now + timedelta(seconds=25)),
        id="collect_daily_bars_bootstrap",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _collector("collect_daily_bars"),
        trigger=CronTrigger(hour=15, minute=40, timezone=CST),
        id="collect_daily_bars_cn",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("collect_daily_bars"),
        trigger=CronTrigger(hour=6, minute=30, timezone=CST),
        id="collect_daily_bars_us",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        heartbeat_job,
        trigger=IntervalTrigger(seconds=60),
        id="heartbeat",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    if settings.env != "test":
        _register_collectors()
    scheduler.start()
    logger.info("scheduler started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")


def scheduler_snapshot() -> dict:
    jobs = []
    if scheduler.running:
        for job in scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
            )
    return {"running": scheduler.running, "jobs": jobs}
