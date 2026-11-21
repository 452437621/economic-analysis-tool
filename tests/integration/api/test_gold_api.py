"""Gold monitoring API contracts."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.gold.registry import INDICATORS
from app.main import app

pytestmark = pytest.mark.unit


def test_gold_api_overview_and_manual_metric():
    with TestClient(app) as client:
        overview = client.get("/api/gold/overview")
        assert overview.status_code == 200
        payload = overview.json()
        assert set(payload) >= {"score", "series", "providers", "manual", "indicators", "categories"}
        expected_factors = sum(1 for item in INDICATORS.values() if item.weight > 0)
        assert len(payload["score"]["factors"]) == expected_factors
        assert len(payload["score"]["signals"]) == 6
        assert payload["score"]["signal_details"]
        assert -100 <= payload["score"]["combined"]["score"] <= 100
        assert payload["manual"], "manual indicator list should not be empty"

        series = client.get("/api/gold/series?code=COT_MONEY_NET&limit=5")
        assert series.status_code == 200
        assert series.json()["code"] == "COT_MONEY_NET"
        assert client.get("/api/gold/series?code=NOPE").status_code == 404

        saved = client.post(
            "/api/gold/metrics",
            json={"code": "BIS_GOLD_SWAP_USD", "value": 120.0, "as_of": "2026-11-01", "note": "test"},
        )
        assert saved.status_code == 200
        assert saved.json()["saved"] is True

        # 自动指标不允许手动写入
        rejected = client.post("/api/gold/metrics", json={"code": "ETF_GLOBAL_TONNES", "value": 1})
        assert rejected.status_code == 400
