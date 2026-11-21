"""Analytics frame loading and alignment."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.analytics.data import MarketFrames, aligned, load_frames
from app.models.core import Instrument, MacroObs, MacroSeries, MarketBar
from tests.helpers import make_db

pytestmark = pytest.mark.unit


def _day(offset: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset)


def _instrument(session, symbol: str, name: str | None = None) -> Instrument:
    instrument = Instrument(
        symbol=symbol,
        name=name or symbol,
        asset_class="metal",
        active=True,
    )
    session.add(instrument)
    session.flush()
    return instrument


def _bar(session, instrument: Instrument, offset: int, close: float, oi: float | None = None) -> None:
    session.add(
        MarketBar(
            instrument_id=instrument.id,
            timeframe="1d",
            ts_utc=_day(offset),
            open=close,
            high=close,
            low=close,
            close=close,
            open_interest=oi,
        )
    )


def test_load_frames_builds_closes_macro_and_open_interest(tmp_path) -> None:
    engine, factory = make_db(tmp_path)
    try:
        with factory() as session:
            au = _instrument(session, "AU", "黄金")
            cu = _instrument(session, "CU", "铜")
            _bar(session, au, 0, 100.0, 10.0)
            _bar(session, au, 1, 101.0, 11.0)
            _bar(session, cu, 0, 50.0)
            series = MacroSeries(code="US10Y", name="美债10年", freq="d")
            session.add(series)
            session.flush()
            session.add_all(
                [
                    MacroObs(series_id=series.id, ts_utc=_day(0), value=4.1),
                    MacroObs(series_id=series.id, ts_utc=_day(1), value=4.2),
                ]
            )
            session.commit()

            frames = load_frames(session)
        assert set(frames.closes.columns) == {"AU", "CU"}
        assert list(frames.macro.columns) == ["US10Y"]
        assert list(frames.open_interest.columns) == ["AU"]
        assert frames.closes.loc[pd.Timestamp("2026-01-02"), "AU"] == 101.0
    finally:
        engine.dispose()


def test_load_frames_empty_database(tmp_path) -> None:
    engine, factory = make_db(tmp_path)
    try:
        with factory() as session:
            frames = load_frames(session)
        assert frames.closes.empty and frames.macro.empty and frames.open_interest.empty
    finally:
        engine.dispose()


def test_aligned_drops_rows_below_half_availability() -> None:
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    closes = pd.DataFrame(
        {
            "AU": [1.0, None, 3.0],
            "CU": [None, None, 4.0],
            "SC": [None, None, 5.0],
            "M": [None, None, 6.0],
        },
        index=index,
    )
    macro = pd.DataFrame({"US10Y": [4.0, 4.1, 4.2]}, index=index)
    frames = MarketFrames(closes=closes, macro=macro, open_interest=pd.DataFrame())
    result, macro_result = aligned(frames)
    assert list(result.index) == [index[2]]
    assert list(macro_result.index) == [index[2]]


def test_aligned_ffill_limit_is_seven_days() -> None:
    index = pd.date_range("2026-01-01", periods=12, freq="D")
    closes = pd.DataFrame({"AU": range(12)}, index=index, dtype=float)
    macro = pd.DataFrame({"US10Y": [4.0, 4.9]}, index=[index[0], index[9]])
    frames = MarketFrames(closes=closes, macro=macro, open_interest=pd.DataFrame())
    _, macro_result = aligned(frames)
    assert macro_result["US10Y"].iloc[7] == 4.0
    assert pd.isna(macro_result["US10Y"].iloc[8])
    assert macro_result["US10Y"].iloc[9] == 4.9
