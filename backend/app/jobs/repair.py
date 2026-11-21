"""Automatic repair job for failed data-quality checks.

The job reads the latest QC batch, maps failed checks to collectors, and runs
each collector at most once per cooldown window. Cooldown is tracked in
``repair_attempts`` — *not* ``Job.last_run_at`` — because the collector that
produced the bad data has just run and would otherwise always be "cooling down".

It assumes the caller already holds the process-wide SQLite write lock (the
scheduler wraps every job in it, and the manual API wraps this function
explicitly).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.ingest import quality
from app.jobs.runner import JOBS, run_job
from app.models.core import Job, JobRun, RepairAttempt
from app.platform.config import settings
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

RUNNING_MINUTES = 90


def _cooldown_until(last_attempt: datetime | None, minutes: int, now: datetime) -> datetime | None:
    if last_attempt is None:
        return None
    if last_attempt.tzinfo is None:
        last_attempt = last_attempt.replace(tzinfo=timezone.utc)
    until = last_attempt + timedelta(minutes=minutes)
    return until if until > now else None


def _running(session, name: str, now: datetime) -> bool:
    cutoff = now - timedelta(minutes=RUNNING_MINUTES)
    found = session.scalar(
        select(JobRun.id)
        .where(JobRun.job_name == name, JobRun.status == "running", JobRun.started_at >= cutoff)
        .limit(1)
    )
    return found is not None


def _last_attempt(session, name: str) -> datetime | None:
    row = session.scalar(
        select(RepairAttempt)
        .where(RepairAttempt.job_name == name)
        .order_by(RepairAttempt.attempted_at.desc())
        .limit(1)
    )
    return row.attempted_at if row is not None else None


def run_repair(
    *,
    recheck: bool = True,
    dry_run: bool = False,
    force: bool = False,
    max_jobs: int | None = None,
    now: datetime | None = None,
) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    result: dict = {
        "attempted": 0,
        "ran": [],
        "skipped": [],
        "failed": [],
        "recheck": None,
        "quality_before": None,
    }
    with SessionLocal() as session:
        checks = quality.failed_checks(session)
        result["quality_before"] = {
            "batch_id": quality.latest_batch(session)[0],
            "failed": len(checks),
            "by_severity": quality.severity_counts(checks),
        }
        jobs = quality.remediation_jobs(checks)
        if not settings.auto_repair_enabled and not force:
            result["skipped"].append({"job": "*", "reason": "自动修复已关闭"})
            return result
        limit = max_jobs or settings.auto_repair_max_actions
        for name in jobs:
            if result["attempted"] >= max(1, limit):
                result["skipped"].append({"job": name, "reason": f"超过单轮上限 {limit}"})
                continue
            if name not in JOBS:
                result["skipped"].append({"job": name, "reason": "不是已注册作业"})
                continue
            job = session.scalar(select(Job).where(Job.name == name))
            if job is not None and not job.enabled:
                result["skipped"].append({"job": name, "reason": "任务已禁用"})
                continue
            if _running(session, name, current):
                result["skipped"].append({"job": name, "reason": "任务仍在运行"})
                continue
            cooldown = _cooldown_until(
                _last_attempt(session, name),
                settings.auto_repair_cooldown_minutes,
                current,
            )
            if cooldown is not None and not force:
                result["skipped"].append(
                    {"job": name, "reason": f"冷却中至 {cooldown.isoformat()}"}
                )
                continue
            result["attempted"] += 1
            if dry_run:
                result["skipped"].append({"job": name, "reason": "dry_run"})
                continue
            attempt = RepairAttempt(job_name=name, attempted_at=current, status="running")
            session.add(attempt)
            session.commit()
            try:
                run = run_job(name)
                entry = {"job": name, "status": run.get("status"), "summary": run.get("summary")}
                attempt.status = "ok" if run.get("status") == "ok" else str(run.get("status") or "error")
                if run.get("status") == "error":
                    result["failed"].append(entry)
                else:
                    result["ran"].append(entry)
            except Exception as exc:  # noqa: BLE001 - one repair must not stop the rest
                logger.exception("repair job failed: %s", name)
                attempt.status = "error"
                result["failed"].append({"job": name, "error": str(exc)[:500]})
            session.commit()

    if recheck and (result["ran"] or result["failed"]) and not dry_run:
        try:
            recheck_result = run_job("check_data_quality")
            result["recheck"] = {
                "status": recheck_result.get("status"),
                "summary": recheck_result.get("summary"),
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("quality recheck failed")
            result["recheck"] = {"status": "error", "error": str(exc)[:500]}
    return result


def latest_repair(session) -> dict | None:
    row = session.scalar(
        select(JobRun)
        .where(JobRun.job_name == "repair_data")
        .order_by(JobRun.started_at.desc())
        .limit(1)
    )
    if row is None:
        return None
    return {
        "id": row.id,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "detail": row.detail,
    }
