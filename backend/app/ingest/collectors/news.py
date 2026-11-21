"""Official news feed collection."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from app.ingest import store
from app.ingest.http import HttpClient
from app.ingest.providers import rss
from app.ingest.sources import NEWS_FEEDS, NEWS_FEEDS_SLOW
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def collect_news(slow: bool = False) -> dict:
    started = time.perf_counter()
    stats: dict = {"documents": 0, "feeds": 0, "errors": []}
    feeds = NEWS_FEEDS_SLOW if slow else NEWS_FEEDS

    with HttpClient(min_interval=0.5) as client, SessionLocal() as session:
        for feed in feeds:
            source = store.get_source(
                session,
                feed["name"],
                kind="news",
                tier=feed["tier"],
                reliability=0.9,
                base_url=feed["url"],
            )
            try:
                if feed["kind"] == "rss":
                    items, raw = rss.fetch_feed(client, feed["url"], feed["name"])
                else:
                    items, raw = rss.fetch_html_news(client, feed["url"], feed["name"])
                suffix = "xml" if feed["kind"] == "rss" else "html"
                if not items:
                    raise RuntimeError("feed returned 0 items (parser may be outdated)")
                raw_path = store.save_raw(
                    feed["name"],
                    f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.{suffix}",
                    raw,
                )
                created = sum(1 for item in items if store.save_document(session, item, source.id, raw_path))
                stats["documents"] += created
                stats["feeds"] += 1
                store.record_health(session, source.id, ok=True)
            except Exception as exc:  # noqa: BLE001
                logger.exception("news feed failed: %s", feed["name"])
                store.record_health(session, source.id, ok=False, error=str(exc))
                stats["errors"].append(f"{feed['name']}: {exc}")
        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_news: %s", stats)
    return stats
