"""QC batch grouping, symbol keys and remediation playbook (offline)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ingest import quality
from app.models.base import Base
from app.models.core import DataCheck

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "test" / "m0" / "quality-playbook.db"


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


def test_classify_czce_and_freshness():
    czce = quality.classify(kind="reconcile", dataset="CZCE官方日行情", passed=False)
    assert czce.severity == "error"
    assert czce.action_job == "collect_daily_bars"
    bars = quality.classify(kind="freshness", dataset="日线行情", passed=False)
    assert bars.action_job == "collect_daily_bars"
    macro = quality.classify(kind="freshness", dataset="宏观序列", passed=False, detail="US10Y")
    assert macro.severity == "error"
    assert macro.action_job == "collect_rates"
    passed = quality.classify(kind="freshness", dataset="日线行情", passed=True)
    assert passed.severity == "info" and passed.action_job is None


def test_batch_keeps_both_symbols_and_structured_fields(session):
    batch = quality.new_batch_id()
    quality.add_check(
        session,
        batch,
        kind="reconcile",
        dataset="CZCE官方日行情",
        symbol="SR",
        expected=6000,
        actual=6100,
        deviation=0.016,
        passed=False,
        detail="偏差超阈值",
    )
    quality.add_check(
        session,
        batch,
        kind="reconcile",
        dataset="CZCE官方日行情",
        symbol="CF",
        expected=15000,
        actual=15010,
        deviation=0.0007,
        passed=True,
    )
    session.commit()
    found_batch, rows = quality.latest_batch(session)
    assert found_batch == batch
    assert len(rows) == 2
    keys = {quality.check_key(row) for row in rows}
    assert keys == {"reconcile:CZCE官方日行情:SR", "reconcile:CZCE官方日行情:CF"}
    failed = [row for row in rows if not row.passed]
    assert failed[0].severity == "error"
    assert failed[0].cause and failed[0].impact and failed[0].remediation
    assert quality.remediation_jobs(rows) == ["collect_daily_bars"]


def test_latest_batch_ignores_previous_batch(session):
    first = quality.new_batch_id()
    quality.add_check(session, first, kind="freshness", dataset="日线行情", passed=False, detail="old")
    session.commit()
    second = quality.new_batch_id()
    quality.add_check(session, second, kind="freshness", dataset="日线行情", passed=True, detail="new")
    session.commit()
    batch, rows = quality.latest_batch(session)
    assert batch == second
    assert len(rows) == 1 and rows[0].passed is True
    all_rows = session.scalars(select(DataCheck)).all()
    assert len(all_rows) == 2
