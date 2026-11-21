"""Thesis lifecycle review."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.decision.thesis_review import summarize
from app.main import app

pytestmark = pytest.mark.unit


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
