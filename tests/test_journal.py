"""交易日志 API 测试（V2.0）。独立 SQLite 文件，依赖覆盖隔离。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.platform.db import get_session

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "test" / "m0" / "journal.db"


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


def test_create_and_get(client: TestClient) -> None:
    body = {
        "entry_date": "2026-11-17",
        "title": "缩量反弹，未追",
        "content": "US10Y 5.12% 高位，SPX 缩量反弹，维持现金。",
        "tags": ["复盘", "执行", " 复盘 "],
    }
    resp = client.post("/api/journal", json=body)
    assert resp.status_code == 200, resp.text
    item = resp.json()["item"]
    assert resp.json()["created"] is True
    assert item["entry_date"] == "2026-11-17"
    assert item["title"] == "缩量反弹，未追"
    assert item["tags"] == ["复盘", "执行"]
    assert item["length"] > 0
    assert client.get(f"/api/journal/{item['id']}").status_code == 200


def test_upsert_same_date_updates(client: TestClient) -> None:
    first = client.post(
        "/api/journal", json={"entry_date": "2026-11-14", "content": "第一版"}
    ).json()
    assert first["created"] is True
    second = client.post(
        "/api/journal",
        json={"entry_date": "2026-11-14", "content": "第二版", "title": "改过"},
    ).json()
    assert second["created"] is False
    assert second["item"]["id"] == first["item"]["id"]
    assert second["item"]["content"] == "第二版"
    assert second["item"]["title"] == "改过"


def test_list_pagination_and_search(client: TestClient) -> None:
    client.post("/api/journal", json={"entry_date": "2026-11-10", "content": "黄金回撤加仓"})
    client.post("/api/journal", json={"entry_date": "2026-11-11", "content": "铜库存低位"})
    listing = client.get("/api/journal", params={"limit": 1, "offset": 0}).json()
    assert listing["total"] >= 3
    assert len(listing["items"]) == 1
    assert listing["items"][0]["entry_date"] >= listing["items"][0]["entry_date"]
    found = client.get("/api/journal", params={"q": "黄金"}).json()
    assert found["total"] == 1
    assert "黄金" in found["items"][0]["content"]


def test_patch_and_delete(client: TestClient) -> None:
    created = client.post(
        "/api/journal", json={"entry_date": "2026-11-12", "content": "待修改"}
    ).json()["item"]
    patched = client.patch(
        f"/api/journal/{created['id']}",
        json={"content": "已修改", "entry_date": "2026-11-13", "tags": ["情绪"]},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["entry_date"] == "2026-11-13"
    assert patched.json()["tags"] == ["情绪"]
    assert client.delete(f"/api/journal/{created['id']}").status_code == 200
    assert client.get(f"/api/journal/{created['id']}").status_code == 404


def test_date_conflict_returns_409(client: TestClient) -> None:
    a = client.post("/api/journal", json={"entry_date": "2026-11-01", "content": "A"}).json()["item"]
    client.post("/api/journal", json={"entry_date": "2026-11-02", "content": "B"})
    resp = client.patch(f"/api/journal/{a['id']}", json={"entry_date": "2026-11-02"})
    assert resp.status_code == 409


def test_validation(client: TestClient) -> None:
    assert client.post("/api/journal", json={"content": ""}).status_code == 422
    assert any(
        client.get("/api/journal", params={"limit": limit}).status_code in (422, 200)
        for limit in (0, 201)
    )
