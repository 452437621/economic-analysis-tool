"""Background scheduler: in-process jobs (heartbeat now, collectors/analysis later)."""

from __future__ import annotations

import asyncio
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.models.base import utcnow
from app.models.core import Job
from app.platform.config import settings
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))


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
    scheduler.start()
    logger.info("scheduler started (heartbeat every 60s)")


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
