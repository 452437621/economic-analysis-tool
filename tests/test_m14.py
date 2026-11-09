"""M14 tests: new official feeds and RSS item cap."""

from __future__ import annotations

from app.ingest.pipeline import NEWS_FEEDS, NEWS_FEEDS_SLOW
from app.ingest.providers.rss import MAX_ITEMS, parse_feed

FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>test</title>
""" + b"".join(
    f"<item><title>Item {i}</title><link>https://example.com/{i}</link>"
    f"<pubDate>Mon, 09 Nov 2026 00:00:00 GMT</pubDate></item>".encode()
    for i in range(100)
) + b"""</channel></rss>"""


def test_parse_feed_caps_items():
    items = parse_feed(FEED, "测试源")
    assert len(items) == MAX_ITEMS
    assert items[0].title == "Item 0"


def test_official_feed_coverage():
    names = {feed["name"] for feed in NEWS_FEEDS}
    assert {"美联储", "欧洲央行", "日本央行", "美国能源信息署", "美国贸易代表办公室"} <= names
    assert any(feed["url"].startswith("https://www.stats.gov.cn") for feed in NEWS_FEEDS_SLOW)
