"""Weekly review markdown builder."""

from __future__ import annotations

from datetime import date

import pytest

from app.narrative.weekly import build_weekly_markdown

pytestmark = pytest.mark.unit


def test_weekly_markdown_builder():
    stats = {
        "briefs": 5,
        "signals": 3,
        "plans": 2,
        "alerts_total": 4,
        "alerts_critical": 1,
        "alerts_warn": 3,
        "resolved": 0,
        "brier": None,
        "hit_rate": None,
        "data_checks_failed": 0,
        "analytics": 30,
        "wind_label": "避险",
        "wind_score": -54.7,
        "movers": [{"symbol": "AU", "change_20d": -4.2, "trend": "down"}],
    }
    text = build_weekly_markdown(stats, date(2026, 11, 3), date(2026, 11, 9), "今日没有追高。")
    assert "周度复盘" in text
    assert "避险" in text
    assert "今日没有追高" in text
    assert "Brier" in text
