"""Golden_analysis signals folded into the gold score."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.gold.registry import INDICATORS
from app.gold.scoring import compute_gold_score
from app.gold.signals import (
    SIGNAL_META,
    build_signal_context,
    pct_rank_last,
    realized_vol,
    rsi,
    sma,
    unavailable_signals,
)
from tests.helpers import memory_db

pytestmark = [pytest.mark.unit, pytest.mark.db]


def test_unavailable_signals_keep_their_weights():
    items = unavailable_signals("测试", spec=None)
    assert len(items) == len(SIGNAL_META) == 6
    assert all(item["available"] is False for item in items)
    assert sum(item["weight"] for item in items) == pytest.approx(45.0)
    assert {item["code"] for item in items} == {meta[0] for meta in SIGNAL_META.values()}


def test_signal_context_on_empty_database_degrades_cleanly():
    _, factory = memory_db()
    with factory() as session:
        context = build_signal_context(session)
        assert context.available is False
        assert len(context.signals) == 6
        assert all(item["available"] is False for item in context.signals)
        assert context.notes


def test_gold_score_includes_signal_weights_in_denominator():
    _, factory = memory_db()
    with factory() as session:
        score = compute_gold_score(session)
    weighted = sum(1 for item in INDICATORS.values() if item.weight > 0)
    assert len(score["factors"]) == weighted
    assert len(score["signals"]) == 6
    assert -100 <= score["score"] <= 100
    assert score["combined"]["total_weight"] == pytest.approx(
        sum(item.weight for item in INDICATORS.values() if item.weight > 0) + 45.0
    )
    assert score["combined"]["coverage"] < 100
    assert score["signal_details"]


def test_signal_helpers_on_synthetic_series():
    series = pd.Series(np.linspace(100.0, 120.0, 80))
    assert sma(series, 5).iloc[-1] == pytest.approx(119.49, abs=0.1)
    assert 50 <= rsi(series, 14).iloc[-1] <= 100
    assert pct_rank_last(series) == 100.0
    returns = series.pct_change().dropna()
    assert realized_vol(returns, 20).iloc[-1] >= 0
