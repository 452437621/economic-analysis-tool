"""M3 analytics unit tests (pure functions, synthetic data)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.analytics.analogs import find_analogs
from app.analytics.attribution import decompose
from app.analytics.correlation import correlation_snapshot
from app.analytics.indicators import compute_indicators
from app.analytics.regime import classify_quadrant
from app.analytics.wind import compute_wind


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


def test_quadrant_classification():
    assert classify_quadrant(1.0, 1.0) == "过热"
    assert classify_quadrant(1.0, -1.0) == "复苏"
    assert classify_quadrant(-1.0, 1.0) == "滞胀"
    assert classify_quadrant(-1.0, -1.0) == "衰退"
    assert classify_quadrant(0.0, 0.0) == "过渡"


def test_decompose_recovers_betas():
    rng = np.random.default_rng(11)
    n = 200
    d1 = rng.normal(0, 0.01, n)
    d2 = rng.normal(0, 0.01, n)
    y = 2.0 * d1 - 1.0 * d2 + rng.normal(0, 0.0001, n)
    result = decompose(
        pd.Series(y),
        pd.DataFrame({"d1": d1, "d2": d2}),
        window=180,
        contrib_days=20,
    )
    assert abs(result["betas"]["d1"] - 2.0) < 0.05
    assert abs(result["betas"]["d2"] + 1.0) < 0.05
    assert result["r2"] > 0.99


def test_correlation_snapshot():
    closes = pd.DataFrame(
        {
            "AU": _prices(200, seed=1),
            "CU": _prices(200, seed=2),
            "SC": _prices(200, seed=3),
        }
    )
    snapshot = correlation_snapshot(closes, window=120)
    assert len(snapshot["symbols"]) == 3
    assert snapshot["top_pairs"]
    assert snapshot["avg_abs_corr"] is not None


def test_wind_score_range():
    closes = pd.DataFrame(
        {
            "CU": _prices(200, seed=1, drift=0.001),
            "SC": _prices(200, seed=2, drift=0.001),
            "000300": _prices(200, seed=3, drift=0.001),
        }
    )
    macro = pd.DataFrame({"US10Y": np.linspace(4.0, 4.3, len(closes))}, index=closes.index)
    wind = compute_wind(closes, macro)
    assert -100 <= wind["score"] <= 100
    assert wind["label"] in {"进攻", "中性", "避险"}
    assert wind["components"]["breadth_above_ma60"] is not None


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
