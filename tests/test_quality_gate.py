"""Global quality gate: unknown / degraded / blocked semantics (offline)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ingest import quality
from app.models.base import Base
from app.models.core import Instrument, MacroObs, MacroSeries, MarketBar, Quote
from app.platform.quality_gate import assess, confidence_factor

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "test" / "m0" / "quality-gate.db"


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


def _seed_fresh_data(db) -> Instrument:
    now = datetime.now(timezone.utc)
    instrument = Instrument(symbol="AU", name="黄金", asset_class="metal", active=True)
    db.add(instrument)
    db.flush()
    db.add(
        MarketBar(
            instrument_id=instrument.id,
            timeframe="1d",
            ts_utc=now,
            open=100,
            high=101,
            low=99,
            close=100.5,
        )
    )
    series = MacroSeries(code="US10Y", name="美债10年", unit="%", country="US", freq="d")
    db.add(series)
    db.flush()
    db.add(MacroObs(series_id=series.id, ts_utc=now, value=4.1))
    db.add(
        Quote(
            instrument_id=instrument.id,
            ts_utc=now,
            price=100.5,
            prev_close=100,
            change_pct=0.5,
        )
    )
    db.commit()
    return instrument


def test_no_quality_batch_is_unknown(session):
    gate = assess(session)
    assert gate["status"] == "unknown"
    assert gate["allow_action"] is False


def test_pass_gate_when_data_and_qc_are_fresh(session):
    _seed_fresh_data(session)
    row = quality.add_check(
        session,
        quality.new_batch_id(),
        kind="freshness",
        dataset="日线行情",
        passed=True,
        detail="ok",
        check_date=datetime.now(timezone.utc),
    )
    session.commit()
    gate = assess(session)
    assert row.batch_id
    assert gate["status"] == "ok"
    assert gate["allow_action"] is True
    assert 0.5 <= confidence_factor(gate) <= 1.0


def test_critical_failure_blocks(session):
    _seed_fresh_data(session)
    quality.add_check(
        session,
        quality.new_batch_id(),
        kind="freshness",
        dataset="日线行情",
        passed=False,
        severity="error",
        detail="停更",
        action_job="collect_daily_bars",
        check_date=datetime.now(timezone.utc) + timedelta(seconds=1),
    )
    session.commit()
    gate = assess(session)
    assert gate["status"] == "blocked"
    assert gate["allow_action"] is False
    assert gate["reasons"]


def test_warning_only_degrades(session):
    _seed_fresh_data(session)
    quality.add_check(
        session,
        quality.new_batch_id(),
        kind="freshness",
        dataset="官方新闻",
        passed=False,
        severity="warn",
        detail="新闻滞后",
        action_job="collect_news",
        check_date=datetime.now(timezone.utc) + timedelta(seconds=2),
    )
    session.commit()
    gate = assess(session)
    assert gate["status"] == "degraded"
    assert gate["allow_action"] is True
