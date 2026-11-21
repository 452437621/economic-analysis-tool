"""M3 analytics unit tests: historical analogs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.analytics.analogs import find_analogs

pytestmark = pytest.mark.unit


def test_find_analogs_returns_matches():
    rng = np.random.default_rng(5)
    dates = pd.date_range("2022-01-07", periods=160, freq="W-FRI")
    state = pd.DataFrame(
        rng.normal(0, 1, (160, 5)),
        index=dates,
        columns=["US10Y", "US10Y_REAL", "US10Y_BE", "slope", "gold_mom"],
    )
    closes = pd.DataFrame(
        {
            "AU": 100 * np.cumprod(1 + rng.normal(0, 0.01, 160)),
            "CU": 100 * np.cumprod(1 + rng.normal(0, 0.01, 160)),
            "SC": 100 * np.cumprod(1 + rng.normal(0, 0.01, 160)),
            "000300": 100 * np.cumprod(1 + rng.normal(0, 0.01, 160)),
        },
        index=dates,
    )
    result = find_analogs(state, closes, top_n=3, min_gap_days=180)
    assert len(result["matches"]) == 3
    assert all("forward" in match for match in result["matches"])
