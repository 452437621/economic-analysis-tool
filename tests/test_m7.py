"""M7 tests: weekly review, journal API, acceptance checks, DXY coverage."""

from __future__ import annotations

from datetime import date, datetime

from fastapi.testclient import TestClient

from app.ingest.symbols import EM_DAILY_SECID
from app.main import app
from app.narrative.weekly import build_weekly_markdown


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


def test_journal_api_roundtrip():
    with TestClient(app) as client:
        resp = client.post("/api/journal", json={"content": "测试日志内容", "entry_date": "2026-11-09"})
        assert resp.status_code == 200
        assert resp.json()["saved"] is True
        listing = client.get("/api/journal?limit=5").json()["data"]
        assert any(entry["content"] == "测试日志内容" for entry in listing)


def test_acceptance_endpoint_structure():
    with TestClient(app) as client:
        payload = client.get("/api/system/acceptance").json()
    assert "checks" in payload and len(payload["checks"]) >= 10
    assert "counts" in payload
    assert isinstance(payload["passed"], bool)
    for check in payload["checks"]:
        assert {"name", "passed", "detail"} <= set(check)


def test_dxy_daily_coverage_configured():
    assert EM_DAILY_SECID.get("DXY") == "100.UDI"
    assert EM_DAILY_SECID.get("USDCNH") == "133.USDCNH"
    assert EM_DAILY_SECID.get("SPX") == "100.SPX"
    from app.ingest.symbols import SINA_HF

    assert SINA_HF.get("AL_LME") == "hf_AHD"
