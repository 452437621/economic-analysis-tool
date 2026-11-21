"""Topic freshness checks in the data-quality playbook."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ingest.collectors.quality import TOPIC_KEY_DATASETS, topic_freshness_findings
from app.topics import storage
from tests.helpers import memory_db

pytestmark = [pytest.mark.unit, pytest.mark.db]


def test_topic_freshness_flags_missing_and_fresh_datasets():
    _, factory = memory_db()
    with factory() as session:
        dataset = storage.ensure_dataset(session, topic_id="luoyang", dataset="price_daily")
        storage.upsert_rows(
            session,
            dataset,
            [{"as_of": storage.today_local(), "row_key": "default", "payload": {"close": 10.0}}],
        )
        findings = topic_freshness_findings(session, datetime.now(timezone.utc))

    by_dataset = {item["dataset"]: item for item in findings}
    assert set(by_dataset) == {f"专题:luoyang/{name}" for name in TOPIC_KEY_DATASETS}
    assert all(item["action_job"] == "collect_luoyang" for item in findings)
    assert by_dataset["专题:luoyang/price_daily"]["passed"] is True
    assert by_dataset["专题:luoyang/valuation_daily"]["passed"] is False
    assert "尚未采集" in by_dataset["专题:luoyang/valuation_daily"]["detail"]


def test_topic_freshness_never_raises(monkeypatch):
    from app.topics import config

    def boom(_topic_id):
        raise RuntimeError("registry broken")

    monkeypatch.setattr(config, "get_topic", boom)
    _, factory = memory_db()
    with factory() as session:
        findings = topic_freshness_findings(session, datetime.now(timezone.utc))
    assert len(findings) == 1
    assert findings[0]["passed"] is False
    assert findings[0]["dataset"] == "专题:luoyang"
