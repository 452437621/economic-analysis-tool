"""Monthly report markdown builder."""

from __future__ import annotations

from datetime import date

import pytest

from app.narrative.monthly import build_monthly_markdown

pytestmark = pytest.mark.unit


def test_monthly_markdown_builder():
    stats = {
        "briefs": 12,
        "signals": 20,
        "plans": 8,
        "alerts_total": 30,
        "alerts_critical": 4,
        "alerts_warn": 12,
        "resolved": 0,
        "brier": None,
        "hit_rate": None,
        "theses": 4,
        "thesis_hit_rate": 0.5,
        "data_checks_failed": 0,
        "calendar_events": 180,
        "wind_label": "避险",
        "wind_score": -54.7,
        "movers": [{"symbol": "AU", "change_20d": -4.2, "trend": "down"}],
    }
    text = build_monthly_markdown(stats, date(2026, 11, 1), date(2026, 11, 30))
    assert "月复盘" in text
    assert "方向命中率 0.5" in text
    assert "避险" in text
    assert "本月校准清单" in text
