"""RSS / HTML news providers (official sources)."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from app.ingest.contracts import NewsItem
from app.ingest.http import HttpClient

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
MAX_ITEMS = 80


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean(value: str | None, limit: int = 600) -> str | None:
    if not value:
        return None
    text = html.unescape(_TAG_RE.sub(" ", value))
    text = _WS_RE.sub(" ", text).strip()
    return text[:limit] if text else None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _children(element: ET.Element) -> dict[str, ET.Element]:
    return {_local(child.tag): child for child in element}


def parse_feed(xml_bytes: bytes, source: str) -> list[NewsItem]:
    root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
    items: list[NewsItem] = []

    if _local(root.tag) == "rss":
        channel = next((child for child in root if _local(child.tag) == "channel"), None)
        if channel is None:
            return []
        for item in channel:
            if _local(item.tag) != "item":
                continue
            fields = _children(item)
            title = _clean(fields["title"].text if "title" in fields else None)
            link = (fields["link"].text or "").strip() if "link" in fields else ""
            if not title or not link:
                continue
            items.append(
                NewsItem(
                    source=source,
                    url=link,
                    title=title,
                    published_at=_parse_date(fields["pubDate"].text if "pubDate" in fields else None),
                    summary=_clean(fields["description"].text if "description" in fields else None),
                    guid=(fields["guid"].text or "").strip() if "guid" in fields else None,
                )
            )
    elif _local(root.tag) == "feed":
        for entry in root:
            if _local(entry.tag) != "entry":
                continue
            fields = _children(entry)
            title = _clean(fields["title"].text if "title" in fields else None)
            link = ""
            if "link" in fields:
                link = fields["link"].attrib.get("href") or (fields["link"].text or "")
                link = link.strip()
            if not title or not link:
                continue
            published = None
            for key in ("published", "updated"):
                if key in fields:
                    published = _parse_date(fields[key].text)
                    if published:
                        break
            summary = None
            for key in ("summary", "content"):
                if key in fields:
                    summary = _clean(fields[key].text)
                    break
            items.append(NewsItem(source=source, url=link, title=title, published_at=published, summary=summary))
    return items[:MAX_ITEMS]


def fetch_feed(client: HttpClient, url: str, source: str) -> tuple[list[NewsItem], bytes]:
    resp = client.get(url)
    resp.raise_for_status()
    raw = resp.content
    return parse_feed(raw, source), raw


def parse_treasury_html(html_text: str, source: str = "美国财政部") -> list[NewsItem]:
    pattern = re.compile(
        r'<a[^>]+href="(/news/press-releases/[^"]+)"[^>]*>(.*?)</a>', re.S | re.I
    )
    seen: set[str] = set()
    items: list[NewsItem] = []
    for href, raw_title in pattern.findall(html_text):
        title = _clean(raw_title)
        if not title or len(title) < 10 or href in seen:
            continue
        seen.add(href)
        items.append(
            NewsItem(
                source=source,
                url="https://home.treasury.gov" + href,
                title=title,
            )
        )
    return items[:30]


def fetch_html_news(client: HttpClient, url: str, source: str) -> tuple[list[NewsItem], bytes]:
    resp = client.get(url)
    resp.raise_for_status()
    raw = resp.content
    return parse_treasury_html(raw.decode("utf-8", errors="replace"), source), raw
