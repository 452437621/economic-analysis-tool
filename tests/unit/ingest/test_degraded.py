"""Degradation tests: failures should be contained, recorded and recoverable."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import alerts
from app.ingest import pipeline
from app.ingest.collectors import news as news_collector
from app.models.core import Source, SourceHealth
from app.platform.db import SessionLocal, init_db

pytestmark = [pytest.mark.unit, pytest.mark.db]


@pytest.fixture(autouse=True)
def _ensure_schema():
    """The shared EPIC test DB must exist before collect_news records health."""
    init_db()


def test_collect_news_marks_failed_source(monkeypatch):
    """A feed returning zero items must be recorded as a failure, not silently ignored."""
    monkeypatch.setattr(
        news_collector,
        "NEWS_FEEDS",
        [dict(name="故障测试源", url="https://example.invalid/rss", kind="rss", tier="S1")],
    )
    monkeypatch.setattr(pipeline.rss, "fetch_feed", lambda *args, **kwargs: ([], b"<rss/>"))
    stats = pipeline.collect_news()
    assert stats["documents"] == 0
    assert stats["feeds"] == 0
    assert len(stats["errors"]) == 1
    with SessionLocal() as session:
        source = session.scalar(select(Source).where(Source.name == "故障测试源"))
        assert source is not None
        health = session.scalar(
            select(SourceHealth)
            .where(SourceHealth.source_id == source.id)
            .order_by(SourceHealth.ts.desc())
        )
        assert health is not None
        assert health.ok is False


def test_alerts_tolerate_missing_fields():
    assert alerts.compute_alerts([], [], []) == []
    events = [{"name": None, "country": None, "importance": 3}]
    assert alerts.calendar_alerts(events) == []
    positions = [{"product": "unknown", "net_ratio": None}]
    assert alerts.position_divergence_alerts(positions, {}) == []


def test_event_alerts_skip_non_high_impact():
    assert alerts.event_alerts([{"type": "data_release", "title": "CPI"}]) == []


def test_llm_extraction_is_skipped_without_key(monkeypatch):
    from app.ingest import pipeline as ingest_pipeline
    from app.llm.client import LLMClient

    monkeypatch.setattr(LLMClient, "available", property(lambda self: False))
    result = ingest_pipeline.extract_claims_llm()
    assert result == {"skipped": "no_api_key"}
