"""M4 decision layer unit tests: rule backtesting."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.decision.backtest import backtest_rule

pytestmark = pytest.mark.unit


def _series(n: int = 160, drift: float = 0.002, seed: int = 3) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    values = 100 * np.cumprod(1 + rng.normal(drift, 0.006, n))
    return pd.Series(values, index=dates)


def test_backtest_rule_returns_stats():
    closes = pd.DataFrame({"X": _series(220, drift=0.001), "Y": _series(220, drift=0.002, seed=9)})
    result = backtest_rule(closes, "breakout", horizon=10)
    assert result["count"] >= 0
    if result["count"]:
        assert 0 <= result["hit_rate"] <= 1
        assert "avg_return_pct" in result
