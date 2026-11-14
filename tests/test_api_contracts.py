"""Contract tests for the frontend-facing API gaps filled in V1.2.

Covers: instrument units, composite overview, brief kind groups + history,
news/event/calendar filters, event→document evidence links, position products
and watchlist inline editing.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _assert_page_meta(payload: dict) -> None:
    meta = payload.get("meta") or {}
    assert isinstance(meta.get("count"), int)
    assert isinstance(meta.get("total"), int)
    assert meta["total"] >= meta["count"] >= 0


def test_snapshot_exposes_units_and_contract_size():
    with TestClient(app) as client:
        payload = client.get("/api/market/snapshot").json()
        rows = payload["data"]
        assert rows, "snapshot should contain seeded instruments"
        by_symbol = {row["symbol"]: row for row in rows}
        for symbol in ("AU", "AG", "CU", "SC", "GC", "DXY", "000300", "603993"):
            if symbol not in by_symbol:
                continue
            assert by_symbol[symbol].get("unit"), f"{symbol} missing display unit"
            assert "contract_size" in by_symbol[symbol]
        assert by_symbol.get("AU", {}).get("unit") == "元/克"
        assert by_symbol.get("GC", {}).get("unit") == "美元/盎司"
        assert by_symbol.get("000300", {}).get("unit") == "点"


def test_overview_composite_payload():
    with TestClient(app) as client:
        payload = client.get("/api/overview").json()
        for key in ("asof", "health", "brief", "snapshot", "watchlist", "macro", "alerts", "calendar", "jobs"):
            assert key in payload, f"overview missing {key}"
        assert payload["health"]["status"] in {"ok", "degraded"}
        assert "counts" in payload["health"]
        assert "latest" in payload["macro"] and "sparks" in payload["macro"]
        assert isinstance(payload["alerts"]["unread"], int)
        assert {"total", "failed", "scheduler_running", "next_run"} <= set(payload["jobs"])
        # watchlist rows carry unit + (when present) sparkline closes
        for row in payload["watchlist"]["data"]:
            assert "unit" in row
            assert isinstance(row.get("spark", []), list)


def test_brief_kind_groups_and_history():
    with TestClient(app) as client:
        kinds = client.get("/api/briefs/kinds").json()["data"]
        assert {"kinds", "groups"} <= set(kinds)
        assert {"daily", "weekly", "monthly"} <= set(kinds["groups"])

        daily = client.get("/api/briefs?kind=daily&limit=5").json()
        _assert_page_meta(daily)
        for row in daily["data"]:
            assert row["kind"] in {"manual", "premarket", "postmarket"}

        latest = client.get("/api/briefs/latest?kind=daily").json()
        assert "neighbors" in latest
        assert {"previous_id", "next_id"} <= set(latest["neighbors"])
        if latest["data"]:
            assert latest["data"]["kind"] in {"manual", "premarket", "postmarket"}

        # exact kind filtering still works
        weekly = client.get("/api/briefs?kind=weekly&limit=5").json()
        _assert_page_meta(weekly)
        for row in weekly["data"]:
            assert row["kind"] == "weekly"


def test_news_filters_return_meta():
    with TestClient(app) as client:
        payload = client.get("/api/news?q=the&limit=3").json()
        _assert_page_meta(payload)
        page = client.get("/api/news?limit=5&offset=0").json()
        _assert_page_meta(page)
        if page["data"]:
            assert "source_id" in page["data"][0]


def test_event_document_link_and_filters():
    with TestClient(app) as client:
        payload = client.get("/api/events?limit=5").json()
        _assert_page_meta(payload)
        for row in payload["data"]:
            assert "document_id" in row
            assert isinstance(row.get("document_ids"), list)
        filtered = client.get("/api/events?type=trade&limit=5").json()
        _assert_page_meta(filtered)
        for row in filtered["data"]:
            assert row["type"] == "trade"


def test_alerts_meta_reports_unread_total():
    with TestClient(app) as client:
        payload = client.get("/api/alerts?limit=5").json()
        assert isinstance(payload["data"], list)
        meta = payload["meta"]
        assert isinstance(meta["count"], int)
        assert isinstance(meta["unread"], int)
        assert meta["unread"] >= meta["count"] or meta["unread"] == 0


def test_calendar_filters_and_meta():
    with TestClient(app) as client:
        payload = client.get("/api/calendar?days=14&limit=5").json()
        _assert_page_meta(payload)
        assert "days" in payload["meta"]
        high = client.get("/api/calendar?days=14&importance_min=2&limit=10").json()
        _assert_page_meta(high)
        for row in high["data"]:
            assert row["importance"] >= 2


def test_position_products_endpoint():
    with TestClient(app) as client:
        payload = client.get("/api/positions/products").json()
        assert "trade_date" in payload
        assert isinstance(payload["data"], list)
        for row in payload["data"]:
            assert "product" in row and "name" in row


def test_watchlist_patch_updates_fields():
    with TestClient(app) as client:
        watchlist = client.get("/api/watchlist").json()["data"]
        if not watchlist:
            return  # 测试库可能没有自选（依赖 config 种子）
        symbol = watchlist[0]["symbol"]
        original_priority = watchlist[0]["priority"]
        response = client.patch(
            f"/api/watchlist/{symbol}",
            json={"group": "契约测试", "priority": 5, "note": "v1.2 contract"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["saved"] is True
        assert body["priority"] == 5
        assert body["group"] == "契约测试"

        refreshed = {row["symbol"]: row for row in client.get("/api/watchlist").json()["data"]}
        assert refreshed[symbol]["priority"] == 5
        assert refreshed[symbol]["group"] == "契约测试"

        # 还原，避免影响其它测试
        client.patch(f"/api/watchlist/{symbol}", json={"priority": original_priority, "group": None, "note": None})


def test_watchlist_patch_unknown_symbol_404():
    with TestClient(app) as client:
        response = client.patch("/api/watchlist/NOT_A_SYMBOL", json={"priority": 2})
        assert response.status_code == 404
