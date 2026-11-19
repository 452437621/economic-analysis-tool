"""启动补跑：应用停机期间错过的定点作业。

APScheduler 的 cron 触发在进程不在时会被直接丢弃（``coalesce=True`` 只合并同一
进程内的重复触发），因此应用整天没开时，premarket 简报、周期/台账等定点作业
永远补不上（``jobs.last_run_at`` 会一直停在上一次运行）。这里在启动后按
「今天该跑的时间点已过、当天还没有该作业的 ``JobRun``、且滞后未超过
``max_lag_hours``」补跑一次，同一作业同一天只补一次。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.jobs.runner import run_job
from app.models.core import Job, JobRun
from app.platform.config import settings
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

CST = ZoneInfo(settings.timezone)

# 只补定点作业；每分钟/每小时的采集类作业不在表内（漏一次无所谓，下一拍就会跑）。
CATCH_UP: dict[str, dict[str, int]] = {
    "brief_premarket": {"hour": 7, "minute": 30, "max_lag_hours": 20},
    "check_data_quality": {"hour": 15, "minute": 50, "max_lag_hours": 6},
    "analyze": {"hour": 16, "minute": 10, "max_lag_hours": 6},
    "cycle": {"hour": 16, "minute": 20, "max_lag_hours": 6},
    "lenses": {"hour": 16, "minute": 25, "max_lag_hours": 6},
    "decide": {"hour": 16, "minute": 30, "max_lag_hours": 6},
    "theses": {"hour": 16, "minute": 35, "max_lag_hours": 6},
    "collect_gold": {"hour": 16, "minute": 40, "max_lag_hours": 6},
    "ledger": {"hour": 16, "minute": 45, "max_lag_hours": 6},
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _scheduled_at(name: str, day: date) -> datetime:
    spec = CATCH_UP[name]
    return datetime.combine(day, time(spec["hour"], spec["minute"]), tzinfo=CST)


def _job_state(name: str) -> tuple[bool, datetime | None]:
    """返回 (是否启用, 上次运行时间)。Job 行缺失时按启用处理（与调度器一致）。"""
    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == name))
        if job is None:
            return True, None
        return bool(job.enabled), job.last_run_at


def _ran_today(name: str, day: date) -> bool:
    """当天（本地时区）是否已有该作业的 JobRun —— 避免重启后反复补跑。"""
    start = datetime.combine(day, time.min, tzinfo=CST).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    with SessionLocal() as session:
        found = session.scalar(
            select(JobRun.id)
            .where(JobRun.job_name == name)
            .where(JobRun.started_at >= start, JobRun.started_at < end)
            .limit(1)
        )
    return found is not None


def catch_up_jobs(*, now: datetime | None = None) -> list[str]:
    """补跑今天错过的定点作业，返回实际补跑的作业名列表。

    判定（对 ``CATCH_UP`` 里每个作业）：
    1. 今天该作业的计划时间点已过，且 ``now - 计划时间`` 不超过 ``max_lag_hours``；
    2. ``Job.enabled`` 未关闭；
    3. ``jobs.last_run_at`` 为空，或早于今天的计划时间点（说明今天还没正常跑过）；
    4. 今天还没有该作业的 ``JobRun``（同一天同一作业只补一次）。

    单个作业失败只记日志，不影响其它作业。
    """
    current = now or datetime.now(CST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=CST)
    today = current.date()
    caught: list[str] = []
    for name in CATCH_UP:
        try:
            scheduled = _scheduled_at(name, today)
            if current < scheduled:
                continue
            if current - scheduled > timedelta(hours=CATCH_UP[name]["max_lag_hours"]):
                continue
            enabled, last_run = _job_state(name)
            if not enabled:
                logger.info("catch-up skipped (disabled): %s", name)
                continue
            if last_run is not None and _as_utc(last_run).astimezone(CST) >= scheduled:
                continue
            if _ran_today(name, today):
                continue
            logger.info("catching up missed job: %s (scheduled %s)", name, scheduled.isoformat())
            result = run_job(name)
            caught.append(name)
            logger.info("catch-up job %s -> %s", name, result.get("status"))
        except Exception:  # noqa: BLE001 - 补跑是尽力而为，单点失败不影响其它作业
            logger.exception("catch-up failed for job: %s", name)
    return caught
