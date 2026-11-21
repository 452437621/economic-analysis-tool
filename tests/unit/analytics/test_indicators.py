"""M3 analytics unit tests: technical indicators."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.analytics.indicators import compute_indicators

pytestmark = pytest.mark.unit


def _prices(n: int = 320, seed: int = 7, drift: float = 0.0006) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    values = 100 * np.cumprod(1 + rng.normal(drift, 0.012, n))
    return pd.Series(values, index=dates)


def test_indicators_basic():
    series = _prices()
    indicator = compute_indicators("TEST", series)
    assert indicator["close"] == round(float(series.iloc[-1]), 4)
    assert indicator["change_20d"] is not None
    assert indicator["trend"] in {"up", "down", "mixed"}
    assert 0 <= indicator["percentile_252"] <= 100
