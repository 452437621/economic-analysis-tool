"""Luoyang chart specs: candlesticks need a real high/low range."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.topics.luoyang.payload import _charts, _ohlc_usable

pytestmark = pytest.mark.unit


def _panel(flat: bool) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-02", periods=80, freq="B")
    close = np.linspace(10.0, 12.0, len(index))
    if flat:
        high = low = open_ = close
        volume = np.full(len(index), np.nan)
    else:
        open_ = close - 0.05
        high = close + 0.2
        low = close - 0.25
        volume = np.full(len(index), 1_000_000.0)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "close_raw": close, "volume": volume},
        index=index,
    )


def _charts_for(panel: pd.DataFrame) -> list[dict]:
    data = SimpleNamespace(panel=panel)
    return _charts(data, {}, {}, {}, {})


def test_ohlc_usable_detects_flat_bars():
    assert _ohlc_usable([[1.0, 1.0, 1.0, 1.0]] * 10) is False
    assert _ohlc_usable([[1.0, 1.2, 0.9, 1.3]] * 10) is True


def test_flat_ohlc_falls_back_to_close_line():
    chart = _charts_for(_panel(flat=True))[0]
    assert chart["kind"] == "line"
    assert chart["series"][0]["name"] == "收盘价"
    assert any(value is not None for value in chart["series"][0]["values"])
    assert chart["hasData"] is True
    assert "收盘价折线" in chart["subtitle"]


def test_real_ohlc_renders_candlesticks_with_volume():
    chart = _charts_for(_panel(flat=False))[0]
    assert chart["kind"] == "candlestick"
    first = chart["ohlc"][0]
    assert first[3] > first[2]
    volume = chart["series"][0]
    assert volume["type"] == "bar"
    assert any(value is not None for value in volume["values"])
