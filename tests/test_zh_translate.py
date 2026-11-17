"""英文内容中文对照（/api/knowledge/translate + knowledge/translate.py）。

覆盖四件事：哈希规则稳定、中文文本直接原样返回、种子语料命中、LLM 不可用时降级为
``source="none"``；另外验证接口契约（200/形状/批量上限）以及配置 key 后「翻译 → 写缓存
→ 下次命中缓存」的双层链路。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.knowledge import translate as tr
from app.main import app
from app.models.base import Base
from app.platform.db import get_session

ROOT = Path(__file__).resolve().parents[1]
SEED_FILE = ROOT / "config" / "translations.zh.json"

# 种子语料里真实存在的一条（PJM/ERCOT/SWPP 夏季峰值负荷），用来验种子命中。
SEED_SAMPLE = "PJM, ERCOT, and SWPP all set peak load records this summer"
SEED_SAMPLE_ZH = "峰值负荷"
CHINESE_SAMPLE = "10月份国民经济运行总体平稳、向新向优"
UNKNOWN_EN = "Quarterly calibration note nobody translated yet 8675309"


@pytest.fixture()
def cache_file(tmp_path, monkeypatch):
    """把运行期缓存指向临时文件，绝不碰仓库里的 data/translations-cache.json。"""
    path = tmp_path / "translations-cache.json"
    monkeypatch.setattr(tr, "cache_path", lambda: path)
    monkeypatch.setattr(tr, "_CACHE_STATE", {"path": None, "mtime": None, "data": {}})
    return path


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


def test_hash_is_stable_across_whitespace_and_quotes() -> None:
    assert tr.text_hash("  Hello   World  ") == tr.text_hash("Hello World")
    assert tr.text_hash('"Hello World"') == tr.text_hash("Hello World")
    assert tr.text_hash("Hello World") != tr.text_hash("Hello Worlds")
    assert len(tr.text_hash("Hello World")) == 16
    assert tr.text_hash("") == tr.text_hash(None)


def test_hash_truncates_at_max_chars() -> None:
    long_text = "a" * (tr.MAX_CHARS + 500)
    assert tr.text_hash(long_text) == tr.text_hash("a" * tr.MAX_CHARS)
    assert len(tr.prepare(long_text)) == tr.MAX_CHARS


def test_chinese_text_returns_itself_without_llm(no_llm, monkeypatch) -> None:
    called: list[str] = []

    def fake_client():
        called.append("built")
        raise AssertionError("中文文本不应该触发 LLM 调用")

    monkeypatch.setattr(tr, "_new_client", fake_client)
    result = tr.translate([CHINESE_SAMPLE])
    entry = result[tr.text_hash(CHINESE_SAMPLE)]
    assert entry["source"] == "seed"
    assert entry["zh"] == tr.normalize(CHINESE_SAMPLE)
    assert called == []


def test_seed_corpus_is_wellformed() -> None:
    payload = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    items = payload["items"]
    assert len(items) >= 200
    for key, item in items.items():
        assert len(key) == 16 and all(ch in "0123456789abcdef" for ch in key)
        assert item["src"] == "seed"
        assert isinstance(item["zh"], str) and item["zh"].strip()
    assert isinstance(payload.get("glossary"), dict) and payload["glossary"]


def test_seed_lookup_hits(no_llm) -> None:
    result = tr.translate([SEED_SAMPLE])
    entry = result[tr.text_hash(SEED_SAMPLE)]
    assert entry["source"] == "seed"
    assert SEED_SAMPLE_ZH in str(entry["zh"])


def test_missing_text_without_llm_returns_none(no_llm, cache_file) -> None:
    result = tr.translate([UNKNOWN_EN])
    entry = result[tr.text_hash(UNKNOWN_EN)]
    assert entry == {"zh": None, "source": "none"}
    assert not cache_file.exists()


def test_llm_translation_writes_cache_and_next_call_hits_it(monkeypatch, cache_file) -> None:
    class FakeResult:
        text = "一条自动生成的中文译文"

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        def chat(self, messages, *, task, temperature, max_tokens):
            self.calls += 1
            assert task == "translate_zh"
            assert temperature == 0
            assert messages[-1]["content"] == UNKNOWN_EN
            return FakeResult()

    fake = FakeClient()
    monkeypatch.setattr(tr, "_llm_available", lambda: True)
    monkeypatch.setattr(tr, "_new_client", lambda: fake)

    first = tr.translate([UNKNOWN_EN])
    assert first[tr.text_hash(UNKNOWN_EN)] == {"zh": "一条自动生成的中文译文", "source": "llm"}
    assert fake.calls == 1

    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    assert payload["items"][tr.text_hash(UNKNOWN_EN)]["src"] == "llm"

    second = tr.translate([UNKNOWN_EN])
    assert second[tr.text_hash(UNKNOWN_EN)] == {"zh": "一条自动生成的中文译文", "source": "cache"}
    assert fake.calls == 1


def test_llm_failure_degrades_to_none(monkeypatch, cache_file) -> None:
    class BrokenClient:
        def chat(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(tr, "_llm_available", lambda: True)
    monkeypatch.setattr(tr, "_new_client", lambda: BrokenClient())
    result = tr.translate([UNKNOWN_EN])
    assert result[tr.text_hash(UNKNOWN_EN)] == {"zh": None, "source": "none"}


def test_translate_dedupes_and_caps_batch(no_llm) -> None:
    texts = ["Statement on Monetary Policy"] * 3
    result = tr.translate(texts)
    assert len(result) == 1

    bulk = [f"bulk text number {index}" for index in range(tr.MAX_ITEMS + 10)]
    assert len(tr.translate(bulk)) == tr.MAX_ITEMS


def test_translate_ignores_non_strings_and_blanks(no_llm) -> None:
    result = tr.translate(["   ", None, "", "Statement on Monetary Policy"])  # type: ignore[list-item]
    assert list(result) == [tr.text_hash("Statement on Monetary Policy")]


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
