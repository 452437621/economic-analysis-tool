"""Schedule registry and due-time logic (no database, no network)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.jobs.plan import (
    JOB_PLANS,
    due_info,
    latest_occurrence,
    validate_registry,
)

CST = ZoneInfo("Asia/Shanghai")


def _utc(year=2026, month=11, day=21, hour=9, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_registry_matches_job_runner():
    assert validate_registry() == []
    assert "repair_data" in JOB_PLANS
    assert "backfill_history" in JOB_PLANS


def test_fixed_time_job_runs_when_todays_occurrence_was_missed():
    plan = JOB_PLANS["analyze"]
    now = datetime(2026, 11, 21, 17, 0, tzinfo=CST)
    last = datetime(2026, 11, 20, 4, 0, tzinfo=timezone.utc)  # 12:00 CST yesterday
    info = due_info(plan, last, now)
    assert info.overdue is True
    assert info.action == "run"
    assert info.due_at is not None
    assert info.due_at.hour == 16 and info.due_at.minute == 10


def test_fixed_time_job_is_not_due_after_it_ran():
    plan = JOB_PLANS["analyze"]
    now = datetime(2026, 11, 21, 17, 0, tzinfo=CST)
    last = datetime(2026, 11, 21, 16, 11, tzinfo=CST)
    assert due_info(plan, last, now).overdue is False


def test_multi_trigger_uses_latest_occurrence():
    plan = JOB_PLANS["collect_daily_bars"]
    now = datetime(2026, 11, 21, 7, 0, tzinfo=CST)
    latest = latest_occurrence(plan, now)
    assert latest is not None
    assert (latest.hour, latest.minute) == (6, 30)


def test_interval_job_respects_grace_and_period():
    plan = JOB_PLANS["collect_quotes"]
    now = datetime(2026, 11, 21, 17, 0, tzinfo=CST)
    assert due_info(plan, now - timedelta(seconds=61), now).overdue is False
    assert due_info(plan, now - timedelta(minutes=5), now).overdue is True


def test_interval_job_never_run_is_due():
    plan = JOB_PLANS["collect_calendar"]
    now = datetime(2026, 11, 21, 17, 0, tzinfo=CST)
    info = due_info(plan, None, now)
    assert info.overdue is True
    assert info.reason == "从未运行"


def test_disabled_and_running_jobs_are_skipped():
    plan = JOB_PLANS["analyze"]
    now = datetime(2026, 11, 21, 17, 0, tzinfo=CST)
    assert due_info(plan, None, now, enabled=False).action == "skip_disabled"
    assert due_info(plan, None, now, running=True).action == "skip_running"


def test_weekly_and_monthly_occurrences():
    weekly = JOB_PLANS["weekly_review"]
    now = datetime(2026, 11, 21, 17, 0, tzinfo=CST)  # Saturday
    occurred = latest_occurrence(weekly, now)
    assert occurred is not None and occurred.weekday() == 6
    monthly = JOB_PLANS["monthly_review"]
    occurred = latest_occurrence(monthly, now)
    assert occurred is not None and occurred.day == 1


def test_startup_flag_for_heavy_jobs():
    assert JOB_PLANS["backfill_history"].startup is False
    assert JOB_PLANS["timeline"].startup is False
    assert JOB_PLANS["analyze"].startup is True
