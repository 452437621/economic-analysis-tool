"""Official news feed coverage checks."""

from __future__ import annotations

import pytest

from app.ingest.pipeline import NEWS_FEEDS, NEWS_FEEDS_SLOW

pytestmark = pytest.mark.unit


def test_official_feed_coverage():
    names = {feed["name"] for feed in NEWS_FEEDS}
    assert {"美联储", "欧洲央行", "日本央行", "美国能源信息署", "美国贸易代表办公室"} <= names
    assert any(feed["url"].startswith("https://www.stats.gov.cn") for feed in NEWS_FEEDS_SLOW)
