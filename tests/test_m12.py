"""M12 tests: monthly report builder and thesis lifecycle review."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.decision.thesis_review import summarize
from app.main import app
from app.narrative.monthly import build_monthly_markdown


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


def test_thesis_review_summarize():
    records = [
        {"return_pct": 2.0, "hit": True},
        {"return_pct": -1.0, "hit": False},
        {"return_pct": None, "hit": None},
    ]
    summary = summarize(records)
    assert summary["count"] == 3
    assert summary["scored"] == 2
    assert summary["hit_rate"] == 0.5
    assert summary["avg_return_pct"] == 0.5


def test_thesis_review_api():
    with TestClient(app) as client:
        payload = client.get("/api/theses/review").json()
    assert "count" in payload["data"]
    assert "scored" in payload["data"]
