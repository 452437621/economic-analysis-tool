"""Acceptance failures must be explicit, not vacuously green (offline)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ingest import quality
from app.models.base import Base
from app.platform.acceptance import build_acceptance

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "test" / "m0" / "acceptance.db"


@pytest.fixture()
def session():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        yield db
    engine.dispose()


def _check(payload: dict, check_id: str) -> dict:
    return next(item for item in payload["checks"] if item["id"] == check_id)


def test_empty_database_does_not_fake_quality_pass(session):
    payload = build_acceptance(session)
    assert payload["passed"] is False
    assert payload["status"] == "fail"
    quality_check = _check(payload, "quality.latest_batch")
    assert quality_check["status"] == "fail"
    assert quality_check["reason"]
    assert quality_check["action_job"] == "check_data_quality"
    assert payload["failed_summary"]["count"] >= 1
    # backwards compatibility
    for item in payload["checks"]:
        assert {"name", "passed", "detail"} <= set(item)


def test_failed_qc_carries_remediation_and_action(session):
    batch = quality.new_batch_id()
    quality.add_check(
        session,
        batch,
        kind="freshness",
        dataset="日线行情",
        passed=False,
        severity="error",
        detail="标的 AU 滞后 9 天",
        action_job="collect_daily_bars",
        check_date=datetime.now(timezone.utc),
    )
    session.commit()
    payload = build_acceptance(session)
    qc = _check(payload, "quality.failed")
    assert qc["status"] == "fail"
    assert qc["reason"] and "失败" in qc["reason"]
    assert qc["remediation"]
    assert qc["action_job"] == "repair_data"
    assert payload["failed_summary"]["failed"]


def test_scheduler_check_is_explicit(session):
    payload = build_acceptance(session)
    schedule = _check(payload, "scheduler.overdue")
    assert schedule["status"] in {"fail", "warn", "pass"}
    last = _check(payload, "scheduler.last_check")
    assert last["status"] == "fail" or last["reason"]


def test_failed_schedule_check_is_not_reported_as_pass(session):
    from datetime import datetime, timezone

    from app.models.core import ScheduleCheck

    now = datetime.now(timezone.utc)
    session.add(
        ScheduleCheck(
            trigger="manual",
            status="error",
            started_at=now,
            finished_at=now,
            error="boom",
        )
    )
    session.commit()
    payload = build_acceptance(session)
    last = _check(payload, "scheduler.last_check")
    assert last["status"] == "fail"
    assert last["reason"]
    assert payload["passed"] is False
