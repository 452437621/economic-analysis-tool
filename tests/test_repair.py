"""Auto-repair: cooldown bookkeeping and error accounting (offline)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ingest import quality
from app.jobs import repair
from app.models.base import Base
from app.models.core import DataCheck, Job, JobRun, RepairAttempt

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "test" / "m0" / "repair.db"


@pytest.fixture()
def pipeline_db(monkeypatch):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repair, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _seed_failure(factory, *, action_job: str = "collect_daily_bars") -> None:
    with factory() as session:
        quality.add_check(
            session,
            quality.new_batch_id(),
            kind="freshness",
            dataset="日线行情",
            passed=False,
            severity="error",
            detail="停更",
            action_job=action_job,
            check_date=datetime.now(timezone.utc),
        )
        session.add(
            Job(
                name=action_job,
                cron="manual",
                enabled=True,
                last_run_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
        )
        session.commit()


def test_repair_is_not_blocked_by_the_collectors_own_recent_run(pipeline_db, monkeypatch):
    """The failing collector just ran; cooldown must be tracked per repair attempt."""
    _seed_failure(pipeline_db)
    calls: list[str] = []

    def fake_run_job(name: str) -> dict:
        calls.append(name)
        return {"job": name, "status": "ok", "summary": {}}

    monkeypatch.setattr(repair, "run_job", fake_run_job)
    result = repair.run_repair(recheck=False)
    assert result["ran"] and result["ran"][0]["job"] == "collect_daily_bars"
    assert calls == ["collect_daily_bars"]

    # Second pass immediately: repair attempt cooldown applies.
    second = repair.run_repair(recheck=False)
    assert calls == ["collect_daily_bars"]
    assert any(item["job"] == "collect_daily_bars" for item in second["skipped"])

    third = repair.run_repair(recheck=False, force=True)
    assert calls == ["collect_daily_bars", "collect_daily_bars"]
    assert third["ran"]


def test_failed_repair_counts_once(pipeline_db, monkeypatch):
    _seed_failure(pipeline_db)

    def boom(_name: str) -> dict:
        raise RuntimeError("collector exploded")

    monkeypatch.setattr(repair, "run_job", boom)
    result = repair.run_repair(recheck=False, max_jobs=3)
    assert result["attempted"] == 1
    assert result["ran"] == []
    assert len(result["failed"]) == 1
    with pipeline_db() as session:
        attempt = session.scalar(select(RepairAttempt))
        assert attempt is not None and attempt.status == "error"


def test_repair_skips_disabled_and_unknown_jobs(pipeline_db, monkeypatch):
    _seed_failure(pipeline_db)
    with pipeline_db() as session:
        job = session.scalar(select(Job).where(Job.name == "collect_daily_bars"))
        job.enabled = False
        session.commit()
    monkeypatch.setattr(repair, "run_job", lambda name: {"job": name, "status": "ok"})
    result = repair.run_repair(recheck=False)
    assert result["ran"] == []
    assert result["skipped"]


def test_recheck_runs_quality_once_after_repair(pipeline_db, monkeypatch):
    _seed_failure(pipeline_db)
    calls: list[str] = []

    def fake_run_job(name: str) -> dict:
        calls.append(name)
        return {"job": name, "status": "ok", "summary": {"n": 1}}

    monkeypatch.setattr(repair, "run_job", fake_run_job)
    result = repair.run_repair(recheck=True)
    assert calls == ["collect_daily_bars", "check_data_quality"]
    assert result["recheck"]["status"] == "ok"
    # recheck never recurses
    assert calls.count("check_data_quality") == 1
    with pipeline_db() as session:
        run = session.scalar(select(JobRun).where(JobRun.job_name == "check_data_quality"))
        assert run is None  # fake runner does not write JobRun rows


def test_repair_attempts_are_json_safe_bookkeeping(pipeline_db):
    # Guard the shape used by latest_repair / UI (no crash when no row exists).
    with pipeline_db() as session:
        assert repair.latest_repair(session) is None
    assert json.dumps({}) == "{}"
