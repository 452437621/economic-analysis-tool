"""M17 tests: deterministic driver ranking."""

from __future__ import annotations

import pytest

from app.analytics.drivers import rank_drivers

pytestmark = pytest.mark.unit


def test_rank_drivers_combines_inputs_and_sorts():
    wind = {"label": "避险", "score": -54.7, "components": {"us10y_change_20d_pp": 0.22}}
    indicators = {"DXY": {"change_20d": -2.5}, "AU": {"change_20d": -3.2}}
    positions = [{"product": "au", "name": "黄金", "net_ratio": 0.375}]
    events = [
        {"type": "trade", "title": "USTR tariff action"},
        {"type": "geopolitical", "title": "Red Sea conflict"},
    ]
    regimes = {"US": {"quadrant": "滞胀", "confidence": 0.37}}
    drivers = rank_drivers(wind, indicators, positions, events, regimes)
    names = [driver["name"] for driver in drivers]
    assert "市场风向" in names
    assert "美国利率" in names
    assert "美元" in names
    assert any(name.startswith("持仓背离") for name in names)
    assert "事件驱动" in names
    strengths = [driver["strength"] for driver in drivers]
    assert strengths == sorted(strengths, reverse=True)
    for driver in drivers:
        assert {"name", "direction", "strength", "evidence"} <= set(driver)


def test_rank_drivers_empty():
    assert rank_drivers(None, {}, [], []) == []
