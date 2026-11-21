"""M3 analytics unit tests: market wind score."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.analytics.wind import compute_wind

pytestmark = pytest.mark.unit


def _prices(n: int = 320, seed: int = 7, drift: float = 0.0006) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    values = 100 * np.cumprod(1 + rng.normal(drift, 0.012, n))
    return pd.Series(values, index=dates)


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
