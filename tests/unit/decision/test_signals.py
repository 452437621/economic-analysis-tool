"""M4 decision layer unit tests: signal detection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.decision.signals import detect_signals

pytestmark = pytest.mark.unit


def test_breakout_signal_detected():
    values = list(np.linspace(100, 120, 120))
    values[-1] = 130.0  # break above prior 20d high
    series = pd.Series(values, index=pd.date_range("2025-01-01", periods=len(values), freq="B"))
    signals = detect_signals("TEST", series)
    assert any(s["type"] == "breakout" and s["direction"] == "long" for s in signals)
    breakout = next(s for s in signals if s["type"] == "breakout")
    assert breakout["strength"] > 0
    assert breakout["atr"] > 0
