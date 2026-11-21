"""RSS feed parser and item cap tests (offline)."""

from __future__ import annotations

import pytest

from app.ingest.providers import rss
from app.ingest.providers.rss import MAX_ITEMS, parse_feed

pytestmark = pytest.mark.unit

RSS_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<title>FRB: Press Release</title>
<item>
  <title>Federal Reserve issues FOMC statement</title>
  <link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20261106a.htm</link>
  <guid>https://www.federalreserve.gov/x</guid>
  <pubDate>Fri, 06 Nov 2026 18:00:00 GMT</pubDate>
  <description>&lt;p&gt;Recent indicators suggest that economic activity has continued to expand.&lt;/p&gt;</description>
</item>
</channel></rss>"""

FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>test</title>
""" + b"".join(
    f"<item><title>Item {i}</title><link>https://example.com/{i}</link>"
    f"<pubDate>Mon, 09 Nov 2026 00:00:00 GMT</pubDate></item>".encode()
    for i in range(100)
) + b"""</channel></rss>"""


def test_rss_parse():
    items = rss.parse_feed(RSS_XML, "美联储")
    assert len(items) == 1
    item = items[0]
    assert item.title.startswith("Federal Reserve")
    assert item.published_at is not None
    assert item.published_at.tzinfo is not None
    assert "economic activity" in (item.summary or "")


def test_parse_feed_caps_items():
    items = parse_feed(FEED, "测试源")
    assert len(items) == MAX_ITEMS
    assert items[0].title == "Item 0"
