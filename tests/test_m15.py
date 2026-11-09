"""M15 tests: rule-based event extraction and event alerts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.alerts import event_alerts
from app.knowledge.events import classify_document, match_instruments
from app.main import app


def test_classify_document_types():
    tar = classify_document("USTR Announces Tariff Action", "New tariffs on imports under Section 301.")
    assert tar is not None and tar["type"] == "trade"
    geo = classify_document("Red Sea shipping conflict escalates", "Military conflict continues.")
    assert geo is not None and geo["type"] == "geopolitical"
    data = classify_document("US CPI rises 3.1%", "Inflation data release.")
    assert data is not None and data["type"] == "data_release"
    assert classify_document("Company earnings", "Quarterly results beat estimates.") is None


def test_match_instruments():
    assert "AU" in match_instruments("Gold price rises as Fed cuts rates")
    assert "SC" in match_instruments("OPEC announces production cut")
    assert "CU" in match_instruments("Copper smelter outage in Chile")
    assert match_instruments("Sports news") == []


def test_event_alerts():
    alerts = event_alerts(
        [
            {"type": "trade", "title": "USTR tariff action", "instruments": ["AU", "CU"]},
            {"type": "data_release", "title": "CPI", "instruments": []},
        ]
    )
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "event"
    assert "USTR" in alerts[0]["title"]


def test_events_api_structure():
    with TestClient(app) as client:
        payload = client.get("/api/events?limit=5").json()
    assert "data" in payload
    for event in payload["data"]:
        assert {"id", "type", "title", "event_date", "instruments"} <= set(event)
