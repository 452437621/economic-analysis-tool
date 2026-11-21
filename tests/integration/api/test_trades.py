"""交易 API 测试（V2.0）：CRUD、分页筛选、汇总统计与统计页。

与 tests/test_journal.py 相同的独立 SQLite fixture：每个测试模块一个独立库文件，
通过 ``app.dependency_overrides[get_session]`` 隔离，不污染 data/epic.db。
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.platform.db import get_session
from tests.helpers import ROOT

pytestmark = [pytest.mark.integration, pytest.mark.api]

DB_PATH = ROOT / "data" / "test" / "m0" / "trades.db"

SUMMARY_KEYS = (
    "count",
    "closed",
    "open",
    "planned",
    "wins",
    "losses",
    "win_rate",
    "total_pnl",
    "avg_pnl",
    "avg_win",
    "avg_loss",
    "profit_factor",
    "avg_rr",
    "total_fee",
)

BASE_PAYLOAD = {
    "trade_date": "2026-11-17",
    "symbol": "AU",
    "name": "沪金",
    "asset_class": "futures",
    "direction": "long",
    "strategy": "趋势突破",
    "filled_qty": 1.0,
    "entry_price": 500.0,
    "exit_price": 505.0,
    "stop_price": 498.0,
    "target_price": 510.0,
    "margin": 1000.0,
    "fee": 2.0,
    "tags": ["趋势"],
}


@pytest.fixture(scope="module")
def client() -> TestClient:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.unlink(missing_ok=True)
    engine = create_engine(
        f"sqlite:///{DB_PATH.as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)
    engine.dispose()
    DB_PATH.unlink(missing_ok=True)


def _body(**overrides) -> dict:
    """完整字段的创建入参（可覆盖任意字段）。"""
    return {**BASE_PAYLOAD, **overrides}


def _minimal(**overrides) -> dict:
    """最小必填字段的创建入参，避免派生字段干扰统计断言。"""
    body = {
        "trade_date": "2026-11-17",
        "symbol": "X",
        "asset_class": "futures",
        "direction": "long",
    }
    body.update(overrides)
    return body


def _create(client: TestClient, **overrides) -> dict:
    resp = client.post("/api/trades", json=_body(**overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_minimal(client: TestClient, **overrides) -> dict:
    resp = client.post("/api/trades", json=_minimal(**overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_computes_derived_fields(client: TestClient) -> None:
    item = _create(
        client,
        symbol="600519",
        name="贵州茅台",
        asset_class="stock",
        strategy="趋势跟随",
        entry_price=10.0,
        exit_price=12.0,
        filled_qty=100.0,
        margin=1000.0,
        fee=5.0,
        stop_price=9.0,
        target_price=12.0,
        tags=[" 白马 ", "白酒", "白马", "x" * 40],
    )
    # 多单盈亏 = (12-10)*100 - 5；收益率 = 195/1000；盈亏比 = |12-10| / |10-9|
    assert item["pnl"] == pytest.approx(195.0)
    assert item["pnl_pct"] == pytest.approx(0.195)
    assert item["rr"] == pytest.approx(2.0)
    # planned_qty 缺省时用 filled_qty；status 缺省为 closed
    assert item["planned_qty"] == pytest.approx(100.0)
    assert item["filled_qty"] == pytest.approx(100.0)
    assert item["status"] == "closed"
    assert item["trade_date"] == "2026-11-17"
    assert item["id"] and len(item["id"]) == 32
    assert item["created_at"] and item["updated_at"]
    # 标签：去空白、去重、每个最长 16 字符、保持顺序
    assert item["tags"] == ["白马", "白酒", "x" * 16]
    # 字段顺序固定，前端按契约取值
    assert list(item.keys())[:5] == ["id", "trade_date", "symbol", "name", "asset_class"]


def test_create_short_direction_and_manual_pnl(client: TestClient) -> None:
    item = _create(
        client,
        symbol="RB",
        direction="short",
        entry_price=4000.0,
        exit_price=3900.0,
        filled_qty=2.0,
        fee=0.0,
        margin=8000.0,
        stop_price=4050.0,
        target_price=3850.0,
        planned_qty=None,
    )
    # 空单：方向取反
    assert item["pnl"] == pytest.approx(200.0)
    assert item["pnl_pct"] == pytest.approx(200.0 / 8000.0)
    # |3850-4000| / |4000-4050| = 3.0
    assert item["rr"] == pytest.approx(3.0)
    assert item["planned_qty"] == pytest.approx(2.0)

    manual = _create(client, symbol="AU", pnl=-33.0, pnl_pct=-0.5, rr=3.0)
    # 手工录入的派生字段优先，不被价格推导覆盖
    assert manual["pnl"] == pytest.approx(-33.0)
    assert manual["pnl_pct"] == pytest.approx(-0.5)
    assert manual["rr"] == pytest.approx(3.0)


def test_create_tags_limits(client: TestClient) -> None:
    tags = [f"tag-{index}" for index in range(10)]
    item = _create(client, symbol="TAGS", tags=tags)
    assert item["tags"] == tags[:8]


def test_list_pagination_and_sort(client: TestClient) -> None:
    for day in ("2026-09-01", "2026-10-15", "2026-11-02"):
        _create_minimal(client, symbol="PAGE", trade_date=day, pnl=10.0)

    first = client.get("/api/trades", params={"q": "PAGE", "limit": 2, "offset": 0})
    assert first.status_code == 200
    payload = first.json()
    assert payload["total"] == 3
    assert payload["limit"] == 2
    assert payload["offset"] == 0
    # 默认 trade_date desc
    assert [row["trade_date"] for row in payload["items"]] == ["2026-11-02", "2026-10-15"]

    second = client.get("/api/trades", params={"q": "PAGE", "limit": 2, "offset": 2}).json()
    assert [row["trade_date"] for row in second["items"]] == ["2026-09-01"]

    asc = client.get(
        "/api/trades", params={"q": "PAGE", "sort": "trade_date", "order": "asc"}
    ).json()
    assert [row["trade_date"] for row in asc["items"]] == [
        "2026-09-01",
        "2026-10-15",
        "2026-11-02",
    ]
    # 分页不影响 summary：统计的是筛选后的全部记录
    assert asc["summary"]["count"] == 3

    off_page = client.get("/api/trades", params={"q": "PAGE", "offset": 99}).json()
    assert off_page["items"] == []
    assert off_page["total"] == 3

    assert client.get("/api/trades", params={"limit": 0}).status_code == 422
    assert client.get("/api/trades", params={"limit": 201}).status_code == 422


def test_list_filters(client: TestClient) -> None:
    _create_minimal(
        client,
        symbol="FILT1",
        asset_class="futures",
        status="closed",
        direction="long",
        strategy="动量突破",
        plan_note="等待回踩不追高",
    )
    _create_minimal(
        client,
        symbol="FILT2",
        asset_class="stock",
        status="open",
        direction="long",
        strategy="价值回归",
        plan_note="分批建仓",
    )
    _create_minimal(
        client,
        symbol="FILT3",
        asset_class="futures",
        status="planned",
        direction="short",
        strategy="均值回归",
        review_note="执行有噪声",
    )

    futures = client.get("/api/trades", params={"q": "FILT", "asset_class": "futures"}).json()
    assert futures["total"] == 2
    assert {row["symbol"] for row in futures["items"]} == {"FILT1", "FILT3"}
    assert futures["summary"]["count"] == 2

    opened = client.get("/api/trades", params={"q": "FILT", "status": "open"}).json()
    assert opened["total"] == 1
    assert opened["items"][0]["symbol"] == "FILT2"

    shorted = client.get("/api/trades", params={"q": "FILT", "direction": "short"}).json()
    assert [row["symbol"] for row in shorted["items"]] == ["FILT3"]

    # q 覆盖 symbol / name / strategy / plan_note / review_note
    assert client.get("/api/trades", params={"q": "动量"}).json()["total"] == 1
    assert client.get("/api/trades", params={"q": "等待回踩"}).json()["total"] == 1
    assert client.get("/api/trades", params={"q": "执行有噪声"}).json()["total"] == 1

    ranged = client.get(
        "/api/trades",
        params={"q": "FILT", "date_from": "2026-11-18", "date_to": "2026-11-30"},
    ).json()
    assert ranged["total"] == 0
    ranged = client.get(
        "/api/trades",
        params={"q": "FILT", "date_from": "2026-11-17", "date_to": "2026-11-17"},
    ).json()
    assert ranged["total"] == 3


def test_list_summary_numbers(client: TestClient) -> None:
    _create_minimal(client, symbol="SUM-A", status="closed", pnl=200.0, fee=2.0, rr=2.0, margin=1000.0)
    _create_minimal(client, symbol="SUM-B", status="closed", pnl=-100.0, fee=3.0, rr=1.5, margin=1000.0)
    _create_minimal(client, symbol="SUM-C", status="closed", pnl=0.0, fee=1.0, rr=None)
    _create_minimal(client, symbol="SUM-D", status="open", fee=None, rr=None)

    payload = client.get("/api/trades", params={"q": "SUM"}).json()
    summary = payload["summary"]
    assert payload["total"] == 4
    assert summary["count"] == 4
    assert summary["closed"] == 3
    assert summary["open"] == 1
    assert summary["planned"] == 0
    # pnl=0 不计入胜负；win_rate 分母为已平仓数
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["win_rate"] == pytest.approx(1 / 3)
    assert summary["total_pnl"] == pytest.approx(100.0)
    assert summary["avg_pnl"] == pytest.approx(100.0 / 3)
    assert summary["avg_win"] == pytest.approx(200.0)
    assert summary["avg_loss"] == pytest.approx(-100.0)
    assert summary["profit_factor"] == pytest.approx(2.0)
    assert summary["avg_rr"] == pytest.approx(1.75)
    assert summary["total_fee"] == pytest.approx(6.0)

    # 无样本时数值项返回 0；没有亏损时 profit_factor 为 None（不是 0）
    empty = client.get("/api/trades", params={"q": "NO-SUCH-RECORD"}).json()["summary"]
    expected = {
        key: 0.0 if key not in ("count", "closed", "open", "planned", "wins", "losses") else 0
        for key in SUMMARY_KEYS
    }
    expected["profit_factor"] = None
    assert empty == expected


def test_get_single_and_404(client: TestClient) -> None:
    item = _create(client, symbol="GETME")
    fetched = client.get(f"/api/trades/{item['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == item["id"]
    assert fetched.json()["symbol"] == "GETME"

    missing = client.get("/api/trades/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "交易记录不存在"


def test_patch_partial_update_recomputes_pnl(client: TestClient) -> None:
    item = _create(
        client,
        symbol="PATCH",
        entry_price=10.0,
        exit_price=12.0,
        filled_qty=100.0,
        fee=0.0,
        margin=1000.0,
        stop_price=9.0,
        target_price=12.0,
    )
    assert item["pnl"] == pytest.approx(200.0)
    assert item["rr"] == pytest.approx(2.0)

    patched = client.patch(f"/api/trades/{item['id']}", json={"exit_price": 11.0})
    assert patched.status_code == 200
    body = patched.json()
    assert body["exit_price"] == pytest.approx(11.0)
    # 价格变化后自动重算 pnl / pnl_pct，未改动的字段保持
    assert body["pnl"] == pytest.approx(100.0)
    assert body["pnl_pct"] == pytest.approx(0.1)
    assert body["rr"] == pytest.approx(2.0)
    assert body["name"] == "沪金"

    patched = client.patch(f"/api/trades/{item['id']}", json={"margin": 500.0})
    assert patched.json()["pnl_pct"] == pytest.approx(0.2)

    patched = client.patch(
        f"/api/trades/{item['id']}",
        json={"pnl": -50.0, "status": "open", "review_note": "止损离场"},
    )
    body = patched.json()
    assert body["pnl"] == pytest.approx(-50.0)
    assert body["pnl_pct"] == pytest.approx(-0.1)
    assert body["status"] == "open"
    assert body["review_note"] == "止损离场"

    assert client.patch("/api/trades/does-not-exist", json={"status": "open"}).status_code == 404
    # 必填字段显式置空 / 非法枚举 → 422
    assert client.patch(f"/api/trades/{item['id']}", json={"trade_date": None}).status_code == 422
    assert client.patch(f"/api/trades/{item['id']}", json={"status": "done"}).status_code == 422


def test_delete_and_404(client: TestClient) -> None:
    item = _create_minimal(client, symbol="DELME")
    deleted = client.delete(f"/api/trades/{item['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "id": item["id"]}
    assert client.get(f"/api/trades/{item['id']}").status_code == 404
    assert client.delete(f"/api/trades/{item['id']}").status_code == 404


@pytest.mark.parametrize(
    ("field", "value"),
    [("asset_class", "fund"), ("direction", "sideways"), ("status", "done")],
)
def test_invalid_enum_422(client: TestClient, field: str, value: str) -> None:
    resp = client.post("/api/trades", json=_body(**{field: value}))
    assert resp.status_code == 422, resp.text


def test_missing_required_fields_422(client: TestClient) -> None:
    for field in ("trade_date", "symbol", "asset_class", "direction"):
        body = _minimal()
        body.pop(field)
        assert client.post("/api/trades", json=body).status_code == 422, field
    assert client.post("/api/trades", json={}).status_code == 422


def test_stats_matches_list_summary(client: TestClient) -> None:
    resp = client.get("/api/trades/stats")
    assert resp.status_code == 200
    stats = resp.json()

    listing = client.get("/api/trades", params={"limit": 200}).json()
    assert stats["count"] == listing["total"]
    for key in SUMMARY_KEYS:
        assert stats[key] == pytest.approx(listing["summary"][key]), key

    # 近 24 个月，按时间升序，最后一个是当前月
    months = [row["month"] for row in stats["by_month"]]
    assert len(months) == 24
    assert months[-1] == date.today().strftime("%Y-%m")
    assert months == sorted(months)
    assert sum(row["count"] for row in stats["by_month"]) == stats["count"]

    # by_asset_class 覆盖列表里出现的品种，计数与盈亏一致
    by_class = {row["asset_class"]: row for row in stats["by_asset_class"]}
    expected: dict[str, dict] = {}
    for row in listing["items"]:
        bucket = expected.setdefault(row["asset_class"], {"count": 0, "pnl": 0.0})
        bucket["count"] += 1
        if row["pnl"] is not None:
            bucket["pnl"] += row["pnl"]
    assert set(by_class) == set(expected)
    for asset_class, want in expected.items():
        assert by_class[asset_class]["count"] == want["count"]
        assert by_class[asset_class]["pnl"] == pytest.approx(want["pnl"])
        assert 0.0 <= by_class[asset_class]["win_rate"] <= 1.0
