"""Topic registry loading, validation and cache semantics."""

from __future__ import annotations

import os

import pytest

from app.topics import config

pytestmark = pytest.mark.unit


def _write_registry(tmp_path, topics_yaml: str):
    config_path = tmp_path / "topics.yaml"
    params_dir = tmp_path / "topics"
    params_dir.mkdir()
    config_path.write_text(topics_yaml, encoding="utf-8")
    return config_path, params_dir


def _minimal(kind: str = "hero", topic_id: str = "t1") -> str:
    return f"""
version: 1
topics:
  - id: {topic_id}
    label: 测试专题
    adapter: gold
    sections:
      - {{id: conclusion, label: 结论, kind: {kind}}}
"""


def test_repository_registry_has_gold_and_luoyang():
    topics = config.list_topics()
    ids = [item.id for item in topics]
    assert ids == ["gold", "luoyang"]
    gold = config.get_topic("gold")
    assert gold is not None
    assert gold.signal_weights["fair_value"] == 12
    assert [section.kind for section in gold.sections][:2] == ["hero", "kpis"]

    luoyang = config.get_topic("luoyang")
    assert luoyang is not None
    assert luoyang.params["symbol"] == "603993"
    assert luoyang.params["position_defaults"]["buy_price"] > 0
    assert luoyang.params["score_weights"]["valuation"] == 30


def test_invalid_section_kind_raises(tmp_path, monkeypatch):
    config_path, params_dir = _write_registry(tmp_path, _minimal("nope"))
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "PARAMS_DIR", params_dir)
    config._load_cached.cache_clear()
    with pytest.raises(config.TopicConfigError):
        config.list_topics()


def test_duplicate_topic_ids_raise(tmp_path, monkeypatch):
    text = _minimal(topic_id="dup") + f"""
  - id: dup
    label: 重复
    adapter: gold
    sections:
      - {{id: conclusion, label: 结论, kind: hero}}
"""
    config_path, params_dir = _write_registry(tmp_path, text)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "PARAMS_DIR", params_dir)
    config._load_cached.cache_clear()
    with pytest.raises(config.TopicConfigError):
        config.list_topics()


def test_missing_registry_raises_topic_config_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(config, "PARAMS_DIR", tmp_path / "topics")
    config._load_cached.cache_clear()
    with pytest.raises(config.TopicConfigError):
        config.list_topics()


def test_params_edit_invalidates_cache(tmp_path, monkeypatch):
    config_path, params_dir = _write_registry(tmp_path, _minimal())
    params = params_dir / "t1.yaml"
    params.write_text("score_weights: {valuation: 10}\n", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "PARAMS_DIR", params_dir)
    config._load_cached.cache_clear()

    first = config.get_topic("t1")
    assert first is not None and first.params["score_weights"]["valuation"] == 10

    # Ensure the mtime changes even on coarse filesystems.
    stamp = params.stat().st_mtime + 5
    params.write_text("score_weights: {valuation: 20}\n", encoding="utf-8")
    os.utime(params, (stamp, stamp))

    second = config.get_topic("t1")
    assert second is not None and second.params["score_weights"]["valuation"] == 20


def test_signal_weights_must_be_numeric(tmp_path, monkeypatch):
    text = """
version: 1
topics:
  - id: t1
    label: 测试专题
    adapter: gold
    signal_weights: {trend: abc}
    sections:
      - {id: conclusion, label: 结论, kind: hero}
"""
    config_path, params_dir = _write_registry(tmp_path, text)
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(config, "PARAMS_DIR", params_dir)
    config._load_cached.cache_clear()
    with pytest.raises(config.TopicConfigError):
        config.list_topics()
