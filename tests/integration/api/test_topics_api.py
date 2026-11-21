"""Topic research API contracts."""

from __future__ import annotations

import pytest

from app.api import topics as topics_api
from tests.helpers import api_client, memory_db

pytestmark = [pytest.mark.integration, pytest.mark.api]


@pytest.fixture(autouse=True)
def _clear_overview_cache():
    topics_api._overview_cache.clear()
    yield
    topics_api._overview_cache.clear()


def test_topic_registry_and_gold_overview():
    _, factory = memory_db()
    with api_client(factory) as client:
        registry = client.get("/api/topics")
        assert registry.status_code == 200
        payload = registry.json()
        assert [item["id"] for item in payload["data"]] == ["gold", "luoyang"]
        assert payload["config_version"]

        overview = client.get("/api/topics/gold/overview", params={"series_limit": 60})
        assert overview.status_code == 200
        body = overview.json()
        assert {"meta", "hero", "sections"} <= set(body)
        kinds = {section["kind"] for section in body["sections"]}
        assert {"hero", "kpis", "factors", "charts", "table", "sources", "health", "methodology"} <= kinds
        signals = next(section for section in body["sections"] if section["id"] == "signals")
        assert len(signals["data"]["rows"]) == 12
        score = body["hero"]["score"]
        assert score is None or -100 <= score <= 100


def test_luoyang_overview_is_empty_but_200():
    _, factory = memory_db()
    with api_client(factory) as client:
        response = client.get("/api/topics/luoyang/overview", params={"series_limit": 60})
        assert response.status_code == 200
        body = response.json()
        assert body["hero"]["label"] == "数据不足"
        assert body["hero"]["score"] is None
        kinds = {section["kind"] for section in body["sections"]}
        assert {"hero", "kpis", "charts", "table", "valuation", "scenarios", "events", "position", "health"} <= kinds
        assert body["verdict"]["headline"]


def test_position_roundtrip_and_validation():
    _, factory = memory_db()
    with api_client(factory) as client:
        current = client.get("/api/topics/luoyang/position")
        assert current.status_code == 200
        defaults = current.json()["defaults"]
        assert defaults["buy_price"] > 0
        assert "add_prices" in defaults and "add_ratios" in defaults

        saved = client.put(
            "/api/topics/luoyang/position",
            json={
                "buy_price": 12.5,
                "buy_date": "2026-03",
                "shares_lots": 2,
                "dividends": [{"date": "2026-05-27", "per_share": 0.2}],
                "add_prices": [10.0, 9.5],
                "add_ratios": [0.25, 0.5],
            },
        )
        assert saved.status_code == 200
        effective = saved.json()["effective"]
        assert effective["buy_price"] == 12.5
        assert effective["add_prices"] == [10.0, 9.5]

        reread = client.get("/api/topics/luoyang/position").json()
        assert reread["overrides"]["buy_price"] == 12.5

        assert client.put("/api/topics/luoyang/position", json={"buy_price": 0}).status_code == 422
        assert client.put("/api/topics/luoyang/position", json={"unknown": 1}).status_code == 422
        assert client.put("/api/topics/luoyang/position", json={"buy_date": "2026-13"}).status_code == 422


def test_unknown_topic_is_404():
    _, factory = memory_db()
    with api_client(factory) as client:
        assert client.get("/api/topics/nope/overview").status_code == 404
        assert client.get("/api/topics/nope/position").status_code == 404
        assert client.post("/api/topics/nope/refresh").status_code == 404


def test_refresh_runs_the_configured_job(monkeypatch):
    called: list[str] = []

    def fake_run(job: str):
        called.append(job)
        return {"ok": True}

    monkeypatch.setattr("app.jobs.runner.run_job_locked", fake_run)
    _, factory = memory_db()
    with api_client(factory) as client:
        response = client.post("/api/topics/luoyang/refresh")
        assert response.status_code == 200
        assert response.json()["accepted"] is True
        assert response.json()["job"] == "collect_luoyang"
    assert called == ["collect_luoyang"]
