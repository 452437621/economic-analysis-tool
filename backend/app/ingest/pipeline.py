"""Collection pipelines: quotes, daily bars, US yields, official news."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.ingest import store
from app.ingest.contracts import Bar, MacroPoint, Quote
from app.ingest.http import HttpClient
from app.ingest.providers import eastmoney, rss, sina, treasury
from app.ingest.symbols import CN_FUTURES, EM_SECID, SINA_FX, SINA_HF, compute_dxy
from app.models.core import Instrument, Quote as QuoteRow
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

SOURCE_SINA = dict(
    name="新浪财经", kind="market", tier="S2", reliability=0.85, base_url="https://finance.sina.com.cn"
)
SOURCE_EM = dict(
    name="东方财富", kind="market", tier="S2", reliability=0.85, base_url="https://quote.eastmoney.com"
)
SOURCE_TREASURY = dict(
    name="美国财政部", kind="official", tier="S1", reliability=0.95, base_url="https://home.treasury.gov"
)

NEWS_FEEDS = [
    dict(name="美联储", url="https://www.federalreserve.gov/feeds/press_all.xml", kind="rss", tier="S1"),
    dict(name="欧洲央行", url="https://www.ecb.europa.eu/rss/press.html", kind="rss", tier="S1"),
    dict(name="美国财政部", url="https://home.treasury.gov/news/press-releases", kind="html", tier="S1"),
]

MACRO_SERIES_META: dict[str, dict] = {
    "US2Y": {"name": "美债2年", "unit": "%", "country": "US"},
    "US5Y": {"name": "美债5年", "unit": "%", "country": "US"},
    "US10Y": {"name": "美债10年", "unit": "%", "country": "US"},
    "US30Y": {"name": "美债30年", "unit": "%", "country": "US"},
    "US5Y_REAL": {"name": "美债5年实际利率", "unit": "%", "country": "US"},
    "US10Y_REAL": {"name": "美债10年实际利率", "unit": "%", "country": "US"},
    "US5Y_BE": {"name": "5年盈亏平衡通胀", "unit": "%", "country": "US"},
    "US10Y_BE": {"name": "10年盈亏平衡通胀", "unit": "%", "country": "US"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _latest(bars: list[Bar], limit: int) -> list[Bar]:
    return bars[-limit:] if len(bars) > limit else bars


def _quote_symbols(session) -> dict[str, str]:
    rows = session.query(Instrument).filter(Instrument.active.is_(True)).all()
    return {row.symbol: row.id for row in rows}


def collect_quotes() -> dict:
    """Fetch real-time/delayed quotes across all configured sources."""
    started = time.perf_counter()
    stats: dict = {"quotes": 0, "groups": {}, "errors": []}

    with HttpClient(min_interval=0.2) as client, SessionLocal() as session:
        sina_source = store.get_source(session, **SOURCE_SINA)
        em_source = store.get_source(session, **SOURCE_EM)
        symbol_ids = _quote_symbols(session)

        # 1) domestic futures (realtime)
        try:
            t0 = time.perf_counter()
            quotes = list(sina.fetch_domestic_quotes(client, CN_FUTURES).values())
            n = store.upsert_quotes(session, quotes, symbol_ids, sina_source.id)
            store.record_health(session, sina_source.id, ok=True, latency_ms=int((time.perf_counter() - t0) * 1000))
            stats["groups"]["cn_futures"] = n
            stats["quotes"] += n
        except Exception as exc:  # noqa: BLE001
            logger.exception("domestic futures quotes failed")
            store.record_health(session, sina_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"cn_futures: {exc}")

        # 2) overseas futures / spot (delayed)
        try:
            t0 = time.perf_counter()
            quotes = list(sina.fetch_overseas_quotes(client, SINA_HF).values())
            n = store.upsert_quotes(session, quotes, symbol_ids, sina_source.id)
            store.record_health(session, sina_source.id, ok=True, latency_ms=int((time.perf_counter() - t0) * 1000))
            stats["groups"]["overseas"] = n
            stats["quotes"] += n
        except Exception as exc:  # noqa: BLE001
            logger.exception("overseas quotes failed")
            store.record_health(session, sina_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"overseas: {exc}")

        # 3) FX + computed DXY proxy
        try:
            t0 = time.perf_counter()
            fx_quotes = sina.fetch_fx_quotes(client, SINA_FX)
            quotes = list(fx_quotes.values())
            dxy_price = compute_dxy({symbol: quote.price for symbol, quote in fx_quotes.items()})
            if dxy_price:
                quotes.append(Quote(symbol="DXY", ts=_now(), price=dxy_price, delay_sec=30))
            n = store.upsert_quotes(session, quotes, symbol_ids, sina_source.id)
            store.record_health(session, sina_source.id, ok=True, latency_ms=int((time.perf_counter() - t0) * 1000))
            stats["groups"]["fx"] = n
            stats["quotes"] += n
        except Exception as exc:  # noqa: BLE001
            logger.exception("fx quotes failed")
            store.record_health(session, sina_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"fx: {exc}")

        # 4) A-share / index via Eastmoney
        try:
            t0 = time.perf_counter()
            quotes = []
            for symbol, secid in EM_SECID.items():
                quote = eastmoney.fetch_quote(client, secid, symbol)
                if quote:
                    quotes.append(quote)
            n = store.upsert_quotes(session, quotes, symbol_ids, em_source.id)
            store.record_health(session, em_source.id, ok=True, latency_ms=int((time.perf_counter() - t0) * 1000))
            stats["groups"]["cn_equity"] = n
            stats["quotes"] += n
        except Exception as exc:  # noqa: BLE001
            logger.exception("eastmoney quotes failed")
            store.record_health(session, em_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"cn_equity: {exc}")

        session.commit()
        # 快照历史保留 14 天，避免长期运行无限膨胀
        cutoff = _now() - timedelta(days=14)
        session.execute(delete(QuoteRow).where(QuoteRow.ts_utc < cutoff))
        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_quotes: %s", stats)
    return stats


def collect_daily_bars() -> dict:
    """Backfill/update daily bars: domestic futures (Sina) + A-share (Eastmoney)."""
    started = time.perf_counter()
    stats: dict = {"bars": 0, "symbols": 0, "errors": []}

    with HttpClient(min_interval=0.4) as client, SessionLocal() as session:
        sina_source = store.get_source(session, **SOURCE_SINA)
        em_source = store.get_source(session, **SOURCE_EM)
        symbol_ids = _quote_symbols(session)

        for symbol, code in CN_FUTURES.items():
            instrument_id = symbol_ids.get(symbol)
            if not instrument_id:
                continue
            try:
                bars = _latest(sina.fetch_daily_continuous(client, code), 2000)
                n = store.upsert_bars(session, instrument_id, "1d", bars, sina_source.id, delay_sec=0)
                stats["bars"] += n
                stats["symbols"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("daily bars failed: %s", symbol)
                stats["errors"].append(f"{symbol}: {exc}")
        store.record_health(session, sina_source.id, ok=not stats["errors"])

        for symbol, secid in EM_SECID.items():
            instrument_id = symbol_ids.get(symbol)
            if not instrument_id:
                continue
            try:
                bars = _latest(eastmoney.fetch_daily_kline(client, secid), 2000)
                n = store.upsert_bars(session, instrument_id, "1d", bars, em_source.id)
                stats["bars"] += n
                stats["symbols"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("daily kline failed: %s", symbol)
                stats["errors"].append(f"{symbol}: {exc}")
        store.record_health(session, em_source.id, ok=not stats["errors"])

        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_daily_bars: %s", stats)
    return stats


def collect_rates() -> dict:
    """Fetch US Treasury nominal/real curves (5 rolling years)."""
    started = time.perf_counter()
    stats: dict = {"points": 0, "series": 0, "errors": []}

    current_year = datetime.now(timezone.utc).year
    years = list(range(current_year - 4, current_year + 1))

    with HttpClient(min_interval=0.5) as client, SessionLocal() as session:
        treasury_source = store.get_source(session, **SOURCE_TREASURY)
        try:
            curves = treasury.fetch_curves(client, years)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=treasury_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                )
                stats["points"] += n
                stats["series"] += 1
            store.record_health(session, treasury_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("treasury rates failed")
            store.record_health(session, treasury_source.id, ok=False, error=str(exc))
            stats["errors"].append(str(exc))
        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_rates: %s", stats)
    return stats


def collect_news() -> dict:
    """Fetch official RSS/HTML feeds into the document store (title + metadata only)."""
    started = time.perf_counter()
    stats: dict = {"documents": 0, "feeds": 0, "errors": []}

    with HttpClient(min_interval=0.5) as client, SessionLocal() as session:
        for feed in NEWS_FEEDS:
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
