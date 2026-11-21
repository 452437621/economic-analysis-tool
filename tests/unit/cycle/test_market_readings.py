"""Cycle panel loading, expression evaluation and compass readings."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.cycle.market import Panel, eval_expression, load_panel, zscore
from app.cycle.readings import SPECS, build_readings
from app.models.core import Instrument, MacroObs, MacroSeries, MarketBar
from tests.helpers import make_db

pytestmark = pytest.mark.unit


def _day(offset: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset)


def _add_macro(session, code: str, values: list[float]) -> None:
    series = MacroSeries(code=code, name=code, freq="d")
    session.add(series)
    session.flush()
    session.add_all(
        MacroObs(series_id=series.id, ts_utc=_day(index), value=value)
        for index, value in enumerate(values)
    )


def _add_bars(session, symbol: str, values: list[float]) -> None:
    instrument = Instrument(symbol=symbol, name=symbol, asset_class="metal", active=True)
    session.add(instrument)
    session.flush()
    session.add_all(
        MarketBar(
            instrument_id=instrument.id,
            timeframe="1d",
            ts_utc=_day(index),
            open=value,
            high=value,
            low=value,
            close=value,
        )
        for index, value in enumerate(values)
    )


def _seeded(tmp_path):
    engine, factory = make_db(tmp_path)
    with factory() as session:
        _add_macro(session, "US10Y", [4.0 + index / 100 for index in range(70)])
        _add_macro(session, "US2Y", [3.5 + index / 100 for index in range(70)])
        _add_bars(session, "XAUUSD", [2000.0 + index for index in range(70)])
        _add_bars(session, "SI", [25.0 + index / 100 for index in range(70)])
        _add_bars(session, "HG", [4.0 + index / 100 for index in range(70)])
        _add_bars(session, "DXY", [100.0 + index / 100 for index in range(70)])
        session.commit()
    return engine, factory


def test_load_panel_and_eval_expression(tmp_path) -> None:
    engine, factory = _seeded(tmp_path)
    try:
        with factory() as session:
            panel = load_panel(session)
        assert {"US10Y", "US2Y", "XAUUSD", "SI", "HG", "DXY"}.issubset(panel.daily.columns)
        assert panel.first == "2026-01-01"
        assert panel.last == "2026-03-11"
        spread = eval_expression(panel, "US10Y - US2Y")
        assert len(spread) == len(panel.daily)
        assert abs(spread.iloc[-1] - 0.5) < 1e-9
    finally:
        engine.dispose()


def test_eval_expression_handles_numeric_column_names(tmp_path) -> None:
    panel = Panel(
        daily=pd.DataFrame({"000300": [1.0, 2.0], "US10Y": [4.0, 4.2]}, index=pd.date_range("2026-01-01", periods=2))
    )
    result = eval_expression(panel, "000300 / US10Y")
    assert result.iloc[0] == 0.25


def test_eval_expression_rejects_unknown_column() -> None:
    panel = Panel(daily=pd.DataFrame({"US10Y": [4.0]}))
    result = eval_expression(panel, "NOPE * 2")
    assert result.empty


def test_zscore_clips_and_handles_constant_series() -> None:
    index = pd.date_range("2020-01-01", periods=600, freq="D")
    trending = pd.Series(range(600), index=index, dtype="float64")
    result = zscore(trending, window_days=2520, min_obs=250, clip=3.5)
    assert result.iloc[-1] <= 3.5
    constant = pd.Series([1.0] * 600, index=index)
    assert zscore(constant, min_obs=250).isna().all()


def test_build_readings_has_values_and_explicit_missing(tmp_path) -> None:
    engine, factory = _seeded(tmp_path)
    try:
        with factory() as session:
            result = build_readings(session)
        by_id = {item["id"]: item for item in result["items"]}
        assert result["total"] == len(SPECS) == 8
        assert by_id["us10y"]["missing"] is False
        assert by_id["us10y"]["value"] == 4.69
        assert by_id["us10y"]["z"] is not None
        assert len(by_id["gold"]["spark"]) == 30
        assert by_id["cn_us_spread"]["missing"] is True
        assert "CN10Y" in by_id["cn_us_spread"]["reason"]
    finally:
        engine.dispose()
