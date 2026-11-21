"""Single-source registry: unique names, chain references and facade identity."""

from __future__ import annotations

import pytest

from app.ingest import chains, collectors, pipeline, sources

pytestmark = pytest.mark.unit

SOURCE_ATTRS = [
    "SOURCE_SINA",
    "SOURCE_EM",
    "SOURCE_TENCENT",
    "SOURCE_TREASURY",
    "SOURCE_JGB",
    "SOURCE_ECB",
    "SOURCE_SHFE",
    "SOURCE_CZCE",
    "SOURCE_NYFED",
    "SOURCE_FRANKFURTER",
    "SOURCE_IMF",
    "SOURCE_WORLDBANK",
    "SOURCE_TREASURY_FISCAL",
    "SOURCE_FED_RESEARCH",
    "SOURCE_FRED",
]


def test_source_names_are_unique() -> None:
    defs = [getattr(sources, attr) for attr in SOURCE_ATTRS]
    assert len({conf["name"] for conf in defs}) == len(defs)


def test_sources_registry_holds_every_source_definition() -> None:
    assert len(sources.SOURCES) == len(SOURCE_ATTRS)
    values = list(sources.SOURCES.values())
    for attr in SOURCE_ATTRS:
        assert any(getattr(sources, attr) is value for value in values)
    for key, value in sources.SOURCES.items():
        assert isinstance(key, str) and key
        assert isinstance(value, dict)


def test_every_chain_source_resolves_to_registry_value() -> None:
    values = list(sources.SOURCES.values())
    for chain in chains.CHAINS.values():
        for conf in chain.sources:
            assert any(conf is value for value in values), (chain.id, conf["name"])


def test_pipeline_facade_identity_for_collectors() -> None:
    for name in (
        "collect_quotes",
        "collect_daily_bars",
        "collect_rates",
        "collect_macro",
        "collect_positions",
        "collect_calendar",
        "collect_news",
        "collect_bodies",
        "purge_binary_bodies",
        "extract_claims",
        "extract_claims_llm",
        "check_data_quality",
        "_guard_tail_bar",
    ):
        assert getattr(pipeline, name) is getattr(collectors, name)


def test_pipeline_reexports_news_feeds() -> None:
    assert pipeline.NEWS_FEEDS is sources.NEWS_FEEDS
    assert pipeline.NEWS_FEEDS_SLOW is sources.NEWS_FEEDS_SLOW
