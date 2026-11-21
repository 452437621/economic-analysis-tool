"""M18 tests: configurable watchlist API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.init_db import seed_instruments, seed_watchlist
from app.main import app
from app.platform.db import init_db

pytestmark = [pytest.mark.integration, pytest.mark.api]


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


def test_watchlist_move_order():
    _prepare()
    with TestClient(app) as client:
        rows = client.get("/api/watchlist").json()["data"]
        assert len(rows) >= 2
        first, second = rows[0]["symbol"], rows[1]["symbol"]
        moved = client.post(f"/api/watchlist/{first}/move", json={"direction": "down"})
        assert moved.status_code == 200
        assert moved.json()["moved"] is True
        after = client.get("/api/watchlist").json()["data"]
        assert after[0]["symbol"] == second
        assert after[1]["symbol"] == first
        # move back up to restore
        client.post(f"/api/watchlist/{first}/move", json={"direction": "up"})
        restored = client.get("/api/watchlist").json()["data"]
        assert restored[0]["symbol"] == first


def test_watchlist_reorder_batch():
    _prepare()
    with TestClient(app) as client:
        rows = client.get("/api/watchlist").json()["data"]
        symbols = [row["symbol"] for row in rows]
        assert len(symbols) >= 2
        reversed_symbols = list(reversed(symbols))
        saved = client.post("/api/watchlist/reorder", json={"symbols": reversed_symbols})
        assert saved.status_code == 200
        assert saved.json()["order"] == reversed_symbols
        after = client.get("/api/watchlist").json()["data"]
        assert [row["symbol"] for row in after] == reversed_symbols
        # restore original order
        client.post("/api/watchlist/reorder", json={"symbols": symbols})
        restored = client.get("/api/watchlist").json()["data"]
        assert [row["symbol"] for row in restored] == symbols
