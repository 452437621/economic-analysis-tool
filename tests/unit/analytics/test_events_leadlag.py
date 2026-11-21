"""Event-window returns and lead-lag correlation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.analytics.events import build_event_study
from app.analytics.leadlag import leadlag_pairs

pytestmark = pytest.mark.unit


def _closes(periods: int = 120) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=periods, freq="D")
    return pd.DataFrame(
        {
            "AU": np.linspace(100.0, 200.0, periods),
            "CU": np.linspace(50.0, 80.0, periods),
        },
        index=index,
    )


def test_event_study_forward_returns() -> None:
    closes = _closes()
    event_date = closes.index[10]
    result = build_event_study(
        closes,
        events=[{"date": event_date.strftime("%Y-%m-%d"), "name": "test", "type": "货币政策"}],
    )
    row = result["events"][0]
    expected = round((closes["AU"].iloc[30] / closes["AU"].iloc[10] - 1) * 100, 2)
    assert row["returns"]["AU_20d"] == expected
    assert "CU_60d" in row["returns"]
    assert result["aggregate"]["货币政策"]["AU_20d"]["n"] == 1


def test_event_study_missing_asset_and_horizon() -> None:
    closes = _closes(periods=15)
    result = build_event_study(
        closes,
        events=[{"date": closes.index[1].strftime("%Y-%m-%d"), "name": "short", "type": "t"}],
    )
    assert result["events"][0]["returns"] == {}
    assert result["aggregate"]["t"] == {}


def test_leadlag_detects_shifted_pair() -> None:
    rng = np.random.default_rng(7)
    base = pd.Series(rng.normal(0, 1, 300))
    frame = pd.DataFrame(
        {
            "LEAD": base,
            "FOLLOW": base.shift(2),
        }
    )
    frame = frame.dropna()
    result = leadlag_pairs(frame, max_lag=3, min_obs=50, top_n=3)
    assert result["pairs"]
    pair = result["pairs"][0]
    assert pair["a"] == "FOLLOW" or pair["b"] == "FOLLOW"
    assert abs(pair["lag_days"]) == 2
    assert pair["interpretation"] != "同步"


def test_leadlag_respects_top_n_and_min_obs() -> None:
    frame = pd.DataFrame({"A": range(30), "B": range(30), "C": range(30)})
    assert leadlag_pairs(frame, min_obs=100)["pairs"] == []
    grid = np.arange(1, 201, dtype=float)
    long = pd.DataFrame({"A": grid, "B": grid**1.1, "C": np.sin(grid)})
    assert len(leadlag_pairs(long, min_obs=50, top_n=1)["pairs"]) == 1
