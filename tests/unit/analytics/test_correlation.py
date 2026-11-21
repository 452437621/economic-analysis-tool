"""M3 analytics unit tests: correlation snapshot."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.analytics.correlation import correlation_snapshot

pytestmark = pytest.mark.unit


def _prices(n: int = 320, seed: int = 7, drift: float = 0.0006) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    values = 100 * np.cumprod(1 + rng.normal(drift, 0.012, n))
    return pd.Series(values, index=dates)


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
