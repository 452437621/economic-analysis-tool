"""M4 decision layer unit tests (signals, sizing, plans, backtest)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.decision.backtest import backtest_rule
from app.decision.plans import build_plan, size_position
from app.decision.signals import detect_signals


def _series(n: int = 160, drift: float = 0.002, seed: int = 3) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    values = 100 * np.cumprod(1 + rng.normal(drift, 0.006, n))
    return pd.Series(values, index=dates)


def test_breakout_signal_detected():
    values = list(np.linspace(100, 120, 120))
    values[-1] = 130.0  # break above prior 20d high
    series = pd.Series(values, index=pd.date_range("2025-01-01", periods=len(values), freq="B"))
    signals = detect_signals("TEST", series)
    assert any(s["type"] == "breakout" and s["direction"] == "long" for s in signals)
    breakout = next(s for s in signals if s["type"] == "breakout")
    assert breakout["strength"] > 0
    assert breakout["atr"] > 0


def test_position_sizing():
    size = size_position(1_000_000, 0.25, price=100, stop_price=95)
    assert abs(size - 500) < 1e-6
    assert size_position(1_000_000, 0.25, 100, 100) == 0


def test_plan_construction_and_checks():
    signal = {
        "symbol": "AU",
        "type": "breakout",
        "direction": "long",
        "price": 500.0,
        "atr": 10.0,
        "strength": 0.8,
        "note": "test",
        "params": {},
    }
    plan = build_plan(signal, equity=1_000_000, risk_pct=0.25)
    assert plan["side"] == "long"
    assert plan["stop"] < plan["entry_low"]
    assert plan["targets"]["T1"] > plan["entry_high"]
    assert plan["targets"]["T2"] > plan["targets"]["T1"]
    assert all(check["passed"] for check in plan["checks"])
    assert plan["size"] > 0


def test_backtest_rule_returns_stats():
    closes = pd.DataFrame({"X": _series(220, drift=0.001), "Y": _series(220, drift=0.002, seed=9)})
    result = backtest_rule(closes, "breakout", horizon=10)
    assert result["count"] >= 0
    if result["count"]:
        assert 0 <= result["hit_rate"] <= 1
        assert "avg_return_pct" in result
