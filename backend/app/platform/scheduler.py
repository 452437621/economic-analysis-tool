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


def _job_enabled(name: str) -> bool:
    """Job.enabled is the operator switch; missing rows default to enabled."""
    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == name))
        return True if job is None else bool(job.enabled)


def _collector(name: str):
    async def _run() -> None:
        from app.jobs.runner import run_job
        from app.platform.writelock import write_lock

        try:
            if not await asyncio.to_thread(_job_enabled, name):
                logger.info("scheduled job skipped (disabled): %s", name)
                return

            def _serialized() -> None:
                # 采集任务串行化：SQLite 只允许一个写者，并发写会让某一轮整轮失败
                with write_lock():
                    run_job(name)

            await asyncio.to_thread(_serialized)
        except Exception:  # pragma: no cover - defensive
            logger.exception("scheduled job failed: %s", name)

    return _run


def _register_collectors() -> None:
    now = datetime.now(CST)
    # 行情每分钟采一次：FX / 海外指数 / 夜盘期货全天在动，5 分钟一采会让总览
    # 的价格连续几分钟纹丝不动（store.upsert_quotes 内部对未变化的行情做了
    # 去重落库，所以提高频率不会把库里写满重复行）。
    scheduler.add_job(
        _collector("collect_quotes"),
        trigger=IntervalTrigger(seconds=60),
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
        # 美债/德债/日债/法债均按"收盘后发布"，NY Fed 的 SOFR 08:00 ET、EFFR 09:00 ET
        # 分别发布前一日数据；6 小时一采会让 EFFR 常常落后一个交易日（看起来像停更），
        # 改为一小时一采，最坏滞后 1 小时。
        trigger=IntervalTrigger(hours=1),
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
    scheduler.add_job(
        _collector("extract_events"),
        trigger=IntervalTrigger(seconds=1800),
        id="extract_events",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=now + timedelta(seconds=130),
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
    # EPIC-C 2.0：16:20 周期定位（在 analyze 16:10 之后、decide 16:30 之前），
    # 16:45 台账核对（周期快照就绪后核对 26 条原则与到期预测）。
    scheduler.add_job(
        _collector("cycle"),
        trigger=CronTrigger(hour=16, minute=20, timezone=CST),
        id="cycle_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _collector("ledger"),
        trigger=CronTrigger(hour=16, minute=45, timezone=CST),
        id="ledger_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    # 年表是数据即代码，只有数据集改动才需要重跑，放在周日并避让 backfill。
    scheduler.add_job(
        _collector("timeline"),
        trigger=CronTrigger(day_of_week="sun", hour=9, minute=30, timezone=CST),
        id="timeline_weekly",
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
    # 首次启动回补黄金监控指标（WGC/LBMA/CFTC/东财 + 派生），之后每日 16:40 更新
    scheduler.add_job(
        _collector("collect_gold"),
        trigger=DateTrigger(run_date=now + timedelta(seconds=45)),
        id="collect_gold_bootstrap",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _collector("collect_gold"),
        trigger=CronTrigger(hour=16, minute=40, timezone=CST),
        id="collect_gold",
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
    # 每周日盘前补全历史缺口 + 订正上游写坏的行情（与日线入库上限的调整配套）。
    # 放在周日 09:00：早于 weekly_review（10:00），先修数据再出周报。
    scheduler.add_job(
        _collector("backfill_history"),
        trigger=CronTrigger(day_of_week="sun", hour=9, minute=0, timezone=CST),
        id="backfill_history",
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
