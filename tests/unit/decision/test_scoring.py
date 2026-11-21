"""Prediction scoring against daily bars."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.decision import scoring
from app.models.core import Instrument, MarketBar, Prediction, TradePlan
from tests.helpers import make_db

pytestmark = pytest.mark.unit


def _seed(tmp_path, *, bars_from_offset: int = -12, target: float = 110.0, stop: float = 90.0):
    engine, factory = make_db(tmp_path)
    now = datetime.now(timezone.utc)
    with factory() as session:
        instrument = Instrument(symbol="AU", name="黄金", asset_class="metal", active=True)
        session.add(instrument)
        session.flush()
        plan = TradePlan(
            instrument_id=instrument.id,
            side="long",
            entry_low=100.0,
            entry_high=100.0,
            stop=stop,
            targets={"T1": target},
            status="confirmed",
        )
        session.add(plan)
        session.flush()
        prediction = Prediction(
            plan_id=plan.id,
            probability=0.7,
            horizon_days=10,
            made_at=now + timedelta(days=bars_from_offset),
            status="open",
        )
        session.add(prediction)
        for offset in range(0, 12):
            price = 100.0 + offset
            session.add(
                MarketBar(
                    instrument_id=instrument.id,
                    timeframe="1d",
                    ts_utc=now + timedelta(days=bars_from_offset + offset),
                    open=price,
                    high=price + 1,
                    low=price - 1,
                    close=price,
                )
            )
        session.commit()
        prediction_id = prediction.id
    return engine, factory, prediction_id


def test_target_hit_resolves_win(tmp_path, monkeypatch) -> None:
    engine, factory, prediction_id = _seed(tmp_path, target=104.0)
    try:
        monkeypatch.setattr(scoring, "SessionLocal", factory)
        result = scoring.score_predictions()
        with factory() as session:
            prediction = session.get(Prediction, prediction_id)
        assert result == {"resolved": 1, "skipped": 0}
        assert prediction.status == "resolved"
        assert prediction.brier == (0.7 - 1) ** 2
    finally:
        engine.dispose()


def test_stop_hit_resolves_loss(tmp_path, monkeypatch) -> None:
    engine, factory, prediction_id = _seed(tmp_path, bars_from_offset=-1, target=200.0, stop=99.5)
    try:
        monkeypatch.setattr(scoring, "SessionLocal", factory)
        result = scoring.score_predictions()
        with factory() as session:
            prediction = session.get(Prediction, prediction_id)
        assert result["resolved"] == 1
        assert prediction.brier == 0.7**2
    finally:
        engine.dispose()


def test_insufficient_bars_are_skipped(tmp_path, monkeypatch) -> None:
    engine, factory = make_db(tmp_path)
    try:
        now = datetime.now(timezone.utc)
        with factory() as session:
            instrument = Instrument(symbol="AU", name="黄金", asset_class="metal", active=True)
            session.add(instrument)
            session.flush()
            plan = TradePlan(instrument_id=instrument.id, side="long", entry_low=100, entry_high=100)
            session.add(plan)
            session.flush()
            session.add(
                Prediction(
                    plan_id=plan.id,
                    probability=0.5,
                    horizon_days=10,
                    made_at=now - timedelta(days=2),
                    status="open",
                )
            )
            session.add(
                MarketBar(
                    instrument_id=instrument.id,
                    timeframe="1d",
                    ts_utc=now,
                    open=100,
                    high=101,
                    low=99,
                    close=100,
                )
            )
            session.commit()
        monkeypatch.setattr(scoring, "SessionLocal", factory)
        assert scoring.score_predictions() == {"resolved": 0, "skipped": 1}
    finally:
        engine.dispose()


def test_missing_plan_is_skipped(tmp_path, monkeypatch) -> None:
    engine, factory = make_db(tmp_path)
    try:
        with factory() as session:
            session.add(Prediction(probability=0.5, horizon_days=10, status="open"))
            session.commit()
        monkeypatch.setattr(scoring, "SessionLocal", factory)
        assert scoring.score_predictions() == {"resolved": 0, "skipped": 1}
    finally:
        engine.dispose()
