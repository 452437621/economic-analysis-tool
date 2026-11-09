"""M18 tests: configurable watchlist API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.init_db import seed_instruments, seed_watchlist
from app.main import app
from app.platform.db import init_db


def _prepare():
    init_db()
    seed_instruments()
    seed_watchlist()


def test_watchlist_add_list_delete():
    _prepare()
    with TestClient(app) as client:
        candidates = client.get("/api/watchlist/candidates").json()["data"]
        assert candidates
        symbol = candidates[0]["symbol"]
        created = client.post(
            "/api/watchlist",
            json={"symbol": symbol, "group": "测试分组", "priority": 2},
        )
        assert created.status_code == 200
        rows = client.get("/api/watchlist").json()["data"]
        row = next(item for item in rows if item["symbol"] == symbol)
        assert row["group"] == "测试分组"
        assert row["priority"] == 2
        removed = client.delete(f"/api/watchlist/{symbol}")
        assert removed.status_code == 200
        rows_after = client.get("/api/watchlist").json()["data"]
        assert all(item["symbol"] != symbol for item in rows_after)


def test_watchlist_unknown_symbol():
    _prepare()
    with TestClient(app) as client:
        response = client.post("/api/watchlist", json={"symbol": "NOT_A_SYMBOL"})
        assert response.status_code == 404
