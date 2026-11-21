"""Decision review summary."""

from __future__ import annotations

import pytest

from app.decision.review import summarize

pytestmark = pytest.mark.unit


def test_review_summary():
    records = [
        {"probability": 0.55, "actual": 1.0, "brier": 0.2025},
        {"probability": 0.55, "actual": 0.0, "brier": 0.3025},
        {"probability": 0.65, "actual": 1.0, "brier": 0.1225},
    ]
    summary = summarize(records)
    assert summary["count"] == 3
    assert summary["hit_rate"] == round(2 / 3, 3)
    assert summary["brier"] > 0
    assert summary["calibration"]
