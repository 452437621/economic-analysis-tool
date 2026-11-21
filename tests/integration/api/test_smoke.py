"""API smoke test: every read endpoint should answer without server errors."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = [pytest.mark.integration, pytest.mark.api]

STATIC_GETS = [
    "/api/system/health",
    "/api/system/meta",
    "/api/system/jobs",
    "/api/system/job-runs?limit=5",
    "/api/system/sources",
    "/api/system/data-quality",
    "/api/system/acceptance",
    "/api/overview",
    "/api/gold/overview",
    "/api/gold/providers",
    "/api/gold/series?code=COT_MONEY_NET&limit=5",
    "/api/market/snapshot",
    "/api/market/bars?symbol=AU&timeframe=1d&limit=10",
    "/api/macro/latest",
    "/api/macro/series?code=US10Y&limit=10",
    "/api/news?limit=5",
    "/api/news?q=the&limit=3",
    "/api/briefs?limit=5",
    "/api/briefs?kind=daily&limit=5",
    "/api/briefs?kind=weekly&limit=5",
    "/api/briefs/kinds",
    "/api/briefs/latest",
    "/api/briefs/latest?kind=daily",
    "/api/briefs/latest?kind=weekly",
    "/api/claims?limit=5",
    "/api/analytics/overview",
    "/api/analytics/wind",
    "/api/analytics/regimes",
    "/api/analytics/attribution",
    "/api/analytics/correlation",
    "/api/analytics/analogs",
    "/api/analytics/leadlag",
    "/api/analytics/events",
    "/api/analytics/calendar",
    "/api/analytics/indicators",
    "/api/decisions/summary",
    "/api/decisions/signals?limit=5",
    "/api/decisions/plans?limit=5",
    "/api/decisions/backtest",
    "/api/decisions/predictions?limit=5",
    "/api/decisions/review",
    "/api/theses?limit=5",
    "/api/theses/review",
    "/api/journal?limit=5",
    "/api/alerts?limit=5",
    "/api/events?limit=5",
    "/api/events?type=trade&q=United&limit=3",
    "/api/calendar?days=7&limit=10",
    "/api/calendar?country=%E7%BE%8E%E5%9B%BD&importance_min=2&limit=5",
    "/api/positions",
    "/api/positions/products",
    "/api/positions/members?product=au&limit=20",
    "/api/watchlist",
    "/api/watchlist/candidates",
]


def test_all_read_endpoints_do_not_500():
    failures = []
    with TestClient(app) as client:
        for path in STATIC_GETS:
            response = client.get(path)
            if response.status_code >= 500:
                failures.append((path, response.status_code, response.text[:120]))
        briefs = client.get("/api/briefs?limit=1").json().get("data") or []
        if briefs:
            brief_id = briefs[0]["id"]
            for suffix in ("", "/markdown", "/print"):
                response = client.get(f"/api/briefs/{brief_id}{suffix}")
                if response.status_code >= 500:
                    failures.append((f"/api/briefs/{brief_id}{suffix}", response.status_code, ""))
        news = client.get("/api/news?limit=1").json().get("data") or []
        if news:
            doc_id = news[0]["id"]
            for suffix in ("", "/evidence"):
                response = client.get(f"/api/documents/{doc_id}{suffix}")
                if response.status_code >= 500:
                    failures.append((f"/api/documents/{doc_id}{suffix}", response.status_code, ""))
        theses = client.get("/api/theses?limit=1").json().get("data") or []
        if theses:
            response = client.get(f"/api/theses/{theses[0]['id']}")
            if response.status_code >= 500:
                failures.append((f"/api/theses/{theses[0]['id']}", response.status_code, ""))
    assert not failures, failures


def test_write_endpoints_do_not_500():
    """Mutating endpoints must answer with 2xx/4xx, never a server error."""
    with TestClient(app) as client:
        cases = [
            ("post", "/api/journal", {"content": "smoke test journal entry"}),
            ("post", "/api/alerts/does-not-exist/ack", None),
            ("patch", "/api/theses/does-not-exist", {"posterior": 0.6}),
            ("post", "/api/watchlist", {"symbol": "NOT_A_SYMBOL"}),
            ("post", "/api/watchlist/reorder", {"symbols": ["NOT_A_SYMBOL"]}),
            ("post", "/api/watchlist/NOT_A_SYMBOL/move", {"direction": "up"}),
            ("delete", "/api/watchlist/NOT_A_SYMBOL", None),
        ]
        failures = []
        for method, path, body in cases:
            response = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
            if response.status_code >= 500:
                failures.append((method.upper(), path, response.status_code, response.text[:120]))
    assert not failures, failures


def test_missing_resources_return_404():
    with TestClient(app) as client:
        assert client.get("/api/briefs/unknown-id").status_code == 404
        assert client.get("/api/documents/unknown-id").status_code == 404
        assert client.get("/api/theses/unknown-id").status_code == 404
        assert client.get("/api/market/bars?symbol=NOPE&timeframe=1d").status_code == 404
        assert client.get("/api/macro/series?code=NOPE").status_code == 404
        assert client.get("/api/briefs/unknown-id/markdown").status_code == 404
        assert client.get("/api/briefs/unknown-id/print").status_code == 404
