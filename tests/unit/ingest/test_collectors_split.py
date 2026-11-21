"""The pipeline facade must re-export the exact collector implementations."""

from __future__ import annotations

import pytest

from app.ingest import collectors, macro_meta, pipeline, sources
from app.ingest.collectors import bars, bodies, calendar, claims, macro, news, positions, quality
from app.ingest.collectors import quotes, rates

pytestmark = pytest.mark.unit

COLLECTORS = [
    (quotes, "collect_quotes"),
    (bars, "collect_daily_bars"),
    (rates, "collect_rates"),
    (macro, "collect_macro"),
    (positions, "collect_positions"),
    (calendar, "collect_calendar"),
    (news, "collect_news"),
    (bodies, "collect_bodies"),
    (bodies, "purge_binary_bodies"),
    (claims, "extract_claims"),
    (claims, "extract_claims_llm"),
    (quality, "check_data_quality"),
    (bars, "_guard_tail_bar"),
]


@pytest.mark.parametrize(("module", "name"), COLLECTORS)
def test_pipeline_function_is_collector_implementation(module, name) -> None:
    assert getattr(pipeline, name) is getattr(module, name)
    assert getattr(collectors, name) is getattr(module, name)


def test_pipeline_constants_are_registry_objects() -> None:
    assert pipeline.MACRO_SERIES_META is macro_meta.MACRO_SERIES_META
    assert pipeline.IMF_ANNUAL_SERIES is macro_meta.IMF_ANNUAL_SERIES
    assert pipeline.WORLDBANK_ANNUAL_SERIES is macro_meta.WORLDBANK_ANNUAL_SERIES
    assert pipeline.MTS_LINE_SERIES is macro_meta.MTS_LINE_SERIES
    assert pipeline.NEWS_FEEDS is sources.NEWS_FEEDS
    assert pipeline.NEWS_FEEDS_SLOW is sources.NEWS_FEEDS_SLOW
    assert pipeline.DAILY_BAR_LIMIT is bars.DAILY_BAR_LIMIT
    assert pipeline.MAX_TAIL_MOVE_PCT is bars.MAX_TAIL_MOVE_PCT


def test_pipeline_source_constants_are_registry_objects() -> None:
    for name in sources.__all__:
        if name.startswith("SOURCE_"):
            assert getattr(pipeline, name) is getattr(sources, name)
