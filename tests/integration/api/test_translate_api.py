"""英文内容中文对照接口（/api/knowledge/translate）契约。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.knowledge import translate as tr
from app.main import app
from app.models.base import Base
from app.platform.db import get_session

pytestmark = [pytest.mark.integration, pytest.mark.api]

# 种子语料里真实存在的一条（PJM/ERCOT/SWPP 夏季峰值负荷），用来验种子命中。
SEED_SAMPLE = "PJM, ERCOT, and SWPP all set peak load records this summer"
SEED_SAMPLE_ZH = "峰值负荷"
CHINESE_SAMPLE = "10月份国民经济运行总体平稳、向新向优"
UNKNOWN_EN = "Quarterly calibration note nobody translated yet 8675309"


@pytest.fixture()
def client():
    """接口不需要业务表，但给一个内存库避免碰到真实 data/epic.db。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_session, None)
    engine.dispose()


@pytest.fixture()
def no_llm(monkeypatch):
    """当前环境通常没有 DEEPSEEK_API_KEY，这里显式关掉，避免测试打到外网。"""
    monkeypatch.setattr(tr, "_llm_available", lambda: False)


def test_translate_endpoint_shape(client, no_llm) -> None:
    response = client.post(
        "/api/knowledge/translate",
        json={"texts": [SEED_SAMPLE, CHINESE_SAMPLE, UNKNOWN_EN]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["translated"] == 2
    assert body["missing"] == 1
    assert len(body["items"]) == 3
    for item in body["items"]:
        assert set(item) == {"hash", "text", "zh", "source"}
        assert item["hash"] == tr.text_hash(item["text"])
        assert item["source"] in {"seed", "cache", "llm", "none"}
    by_text = {item["text"]: item for item in body["items"]}
    assert SEED_SAMPLE_ZH in by_text[SEED_SAMPLE]["zh"]
    assert by_text[UNKNOWN_EN]["zh"] is None
    assert by_text[UNKNOWN_EN]["source"] == "none"
    assert by_text[CHINESE_SAMPLE]["zh"] == tr.normalize(CHINESE_SAMPLE)


def test_translate_endpoint_caps_batch_and_accepts_empty(client, no_llm) -> None:
    capped = client.post(
        "/api/knowledge/translate",
        json={"texts": [f"bulk text number {index}" for index in range(tr.MAX_ITEMS + 10)]},
    )
    assert capped.status_code == 200
    assert capped.json()["total"] == tr.MAX_ITEMS

    empty = client.post("/api/knowledge/translate", json={"texts": []})
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "total": 0, "translated": 0, "missing": 0}


def test_translate_endpoint_tolerates_missing_body(client, no_llm) -> None:
    response = client.post("/api/knowledge/translate", json={})
    assert response.status_code == 200
    assert response.json()["total"] == 0
