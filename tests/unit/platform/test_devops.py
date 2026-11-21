"""DevOps regression tests: job audit self-healing, job registry and backup retention."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta

import pytest
from sqlalchemy import select, text

from app import backup as backup_mod
from app.init_db import JOBS_DEFAULT, seed_jobs
from app.jobs import runner
from app.models.base import utcnow
from app.models.core import Job, JobRun
from app.platform.config import settings
from app.platform.db import SessionLocal, init_db

pytestmark = pytest.mark.unit


def _prepare() -> None:
    init_db()
    seed_jobs()


def _job(name: str) -> Job | None:
    with SessionLocal() as session:
        return session.scalar(select(Job).where(Job.name == name))


def test_stale_running_rows_become_interrupted():
    _prepare()
    with SessionLocal() as session:
        old = JobRun(job_name="collect_quotes", status="running", started_at=utcnow() - timedelta(days=1))
        fresh = JobRun(job_name="collect_quotes", status="running", started_at=utcnow())
        session.add_all([old, fresh])
        session.commit()
        old_id, fresh_id = old.id, fresh.id

    assert runner.reconcile_stale_runs(stale_minutes=60) >= 1
    with SessionLocal() as session:
        assert session.get(JobRun, old_id).status == "interrupted"
        assert session.get(JobRun, fresh_id).status == "running"  # genuinely in flight
        session.delete(session.get(JobRun, fresh_id))
        session.commit()


def test_reconcile_all_marks_every_running_row():
    _prepare()
    with SessionLocal() as session:
        row = JobRun(job_name="collect_news", status="running", started_at=utcnow())
        session.add(row)
        session.commit()
        row_id = row.id

    runner.reconcile_stale_runs(all_jobs=True)
    with SessionLocal() as session:
        assert session.get(JobRun, row_id).status == "interrupted"


def test_seed_jobs_covers_registry_and_keeps_operator_flag():
    _prepare()
    with SessionLocal() as session:
        names = {row.name for row in session.scalars(select(Job)).all()}
    assert set(runner.JOBS) <= names
    assert set(JOBS_DEFAULT) >= set(runner.JOBS)

    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == "collect_news"))
        job.enabled = False
        session.commit()
    seed_jobs()
    assert _job("collect_news").enabled is False

    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == "collect_news"))
        job.enabled = True
        session.commit()


def test_light_migrations_are_idempotent_and_one_shot():
    """Migrations must not re-run and must not fight a later operator toggle."""
    from app.platform.db import MIGRATIONS, _ensure_light_migrations

    init_db()
    _ensure_light_migrations()  # second call is a no-op
    with SessionLocal() as session:
        applied = {
            row[0]
            for row in session.execute(text("SELECT name FROM app_migrations"))
        }
    assert {name for name, _ in MIGRATIONS} <= applied

    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == "brief_premarket"))
        job.enabled = False
        session.commit()
    _ensure_light_migrations()  # migration already applied -> keeps the toggle
    assert _job("brief_premarket").enabled is False
    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == "brief_premarket"))
        job.enabled = True
        session.commit()


def test_backup_prunes_old_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    (tmp_path / "backup").mkdir()
    conn = sqlite3.connect(tmp_path / "epic.db")
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()
    for stamp in ("20260101-000000", "20260102-000000", "20260103-000000"):
        folder = tmp_path / "backup" / stamp
        folder.mkdir()
        (folder / "epic.db").write_bytes(b"x")

    dest = backup_mod.backup(keep=2)
    assert (dest / "epic.db").exists()
    remaining = sorted(p.name for p in (tmp_path / "backup").iterdir() if p.is_dir())
    assert len(remaining) == 2
    assert dest.name in remaining
    check = sqlite3.connect(dest / "epic.db")
    try:
        assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        check.close()


def test_job_run_records_json_detail():
    _prepare()
    result = runner.run_job("check_data_quality")
    # The shared test database may legitimately have stale/partial data; a
    # failed QC item is reported as degraded, not silently marked ok.
    assert result["status"] in {"ok", "degraded"}
    with SessionLocal() as session:
        row = session.scalars(
            select(JobRun)
            .where(JobRun.job_name == "check_data_quality")
            .order_by(JobRun.started_at.desc())
            .limit(1)
        ).first()
        assert json.loads(row.detail) is not None


def test_scheduler_respects_job_enabled_flag():
    from app.platform.scheduler import _job_enabled

    _prepare()
    assert _job_enabled("collect_news") is True
    assert _job_enabled("never-registered-job") is True  # unknown -> default on
    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == "collect_news"))
        job.enabled = False
        session.commit()
    assert _job_enabled("collect_news") is False
    with SessionLocal() as session:
        job = session.scalar(select(Job).where(Job.name == "collect_news"))
        job.enabled = True
        session.commit()
