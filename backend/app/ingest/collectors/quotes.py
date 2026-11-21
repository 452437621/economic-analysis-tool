"""Real-time/delayed quote collection."""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from sqlalchemy import delete

from app.ingest import store
from app.ingest.collectors.support import _now
from app.ingest.contracts import Quote
from app.ingest.http import HttpClient
from app.ingest.providers import eastmoney, sina, tencent
from app.ingest.sources import SOURCE_EM, SOURCE_SINA, SOURCE_TENCENT
from app.ingest.symbols import (
    CN_FUTURES,
    EM_QUOTE_SECID,
    EM_SECID,
    SINA_FX,
    SINA_HF,
    TENCENT_QUOTE,
    TENCENT_QUOTE_PREFERRED,
    compute_dxy,
)
from app.models.core import Instrument, Quote as QuoteRow
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def _quote_symbols(session) -> dict[str, str]:
    rows = session.query(Instrument).filter(Instrument.active.is_(True)).all()
    return {row.symbol: row.id for row in rows}

def collect_quotes() -> dict:
    """Fetch real-time/delayed quotes across all configured sources."""
    started = time.perf_counter()
    stats: dict = {"quotes": 0, "skipped": 0, "groups": {}, "errors": []}

    with HttpClient(min_interval=0.2) as client, SessionLocal() as session:
        sina_source = store.get_source(session, **SOURCE_SINA)
        em_source = store.get_source(session, **SOURCE_EM)
        symbol_ids = _quote_symbols(session)

        # 1) domestic futures (realtime)
        try:
            t0 = time.perf_counter()
            quotes = list(sina.fetch_domestic_quotes(client, CN_FUTURES).values())
            n = store.upsert_quotes(session, quotes, symbol_ids, sina_source.id)
            stats["skipped"] += max(0, len(quotes) - n)
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
            stats["skipped"] += max(0, len(quotes) - n)
            store.record_health(session, sina_source.id, ok=True, latency_ms=int((time.perf_counter() - t0) * 1000))
            stats["groups"]["overseas"] = n
            stats["quotes"] += n
        except Exception as exc:  # noqa: BLE001
            logger.exception("overseas quotes failed")
            store.record_health(session, sina_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"overseas: {exc}")

        # 3) FX + computed DXY proxy (fallback if Eastmoney DXY unavailable)
        dxy_price = None
        try:
            t0 = time.perf_counter()
            fx_quotes = sina.fetch_fx_quotes(client, SINA_FX)
            quotes = list(fx_quotes.values())
            dxy_price = compute_dxy({symbol: quote.price for symbol, quote in fx_quotes.items()})
            n = store.upsert_quotes(session, quotes, symbol_ids, sina_source.id)
            stats["skipped"] += max(0, len(quotes) - n)
            store.record_health(session, sina_source.id, ok=True, latency_ms=int((time.perf_counter() - t0) * 1000))
            stats["groups"]["fx"] = n
            stats["quotes"] += n
        except Exception as exc:  # noqa: BLE001
            logger.exception("fx quotes failed")
            store.record_health(session, sina_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"fx: {exc}")

        # 4) A-share / index / DXY / USDCNH via Eastmoney (intraday-line fallback is
        #    inside eastmoney.fetch_quote), Tencent as last resort so that quotes keep
        #    updating even when Eastmoney's snapshot endpoint is blocked.
        try:
            t0 = time.perf_counter()
            quotes: list[Quote] = []
            em_failed: list[str] = []

            # 少数标的必须先走腾讯（东财同一 secid 指向的不是同一个指数，见
            # TENCENT_QUOTE_PREFERRED 的注释），取到后就不再打东财。
            preferred_ok: set[str] = set()
            if TENCENT_QUOTE_PREFERRED:
                preferred_codes = {
                    code: symbol for symbol, code in TENCENT_QUOTE_PREFERRED.items()
                }
                try:
                    prefetched = tencent.fetch_quotes(client, preferred_codes)
                except Exception as exc:  # noqa: BLE001 - 失败就退回东财
                    logger.warning("tencent preferred quotes failed: %s", exc)
                    prefetched = {}
                if prefetched:
                    tc_source = store.get_source(session, **SOURCE_TENCENT)
                    n = store.upsert_quotes(
                        session, list(prefetched.values()), symbol_ids, tc_source.id
                    )
                    stats["skipped"] += max(0, len(prefetched) - n)
                    stats["groups"]["tencent_preferred"] = n
                    stats["quotes"] += n
                    preferred_ok = set(prefetched)

            for symbol, secid in {**EM_SECID, **EM_QUOTE_SECID}.items():
                if symbol in preferred_ok:
                    continue
                try:
                    quote = eastmoney.fetch_quote(client, secid, symbol)
                except Exception as exc:  # noqa: BLE001 - 单个标的失败不拖垮整组
                    logger.warning("eastmoney quote failed: %s (%s)", symbol, exc)
                    quote = None
                if quote is None:
                    em_failed.append(symbol)
                    continue
                quotes.append(quote)
            fetched = {quote.symbol for quote in quotes}

            if em_failed:
                mapping = {
                    code: symbol for symbol, code in TENCENT_QUOTE.items() if symbol in em_failed
                }
                fallback: dict[str, Quote] = {}
                if mapping:
                    try:
                        fallback = tencent.fetch_quotes(client, mapping)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("tencent quote fallback failed: %s", exc)
                if fallback:
                    tc_source = store.get_source(session, **SOURCE_TENCENT)
                    n = store.upsert_quotes(
                        session, list(fallback.values()), symbol_ids, tc_source.id
                    )
                    stats["skipped"] += max(0, len(fallback) - n)
                    store.record_health(
                        session,
                        tc_source.id,
                        ok=True,
                        latency_ms=int((time.perf_counter() - t0) * 1000),
                    )
                    stats["groups"]["tencent_fallback"] = n
                    stats["quotes"] += n
                    fetched |= set(fallback)

            if dxy_price and "DXY" not in fetched:
                # 东财没有 DXY 时用新浪汇率合成的篮子指数兜底（属于新浪的派生值）
                dxy_proxy = [Quote(symbol="DXY", ts=_now(), price=dxy_price, delay_sec=30)]
                n = store.upsert_quotes(session, dxy_proxy, symbol_ids, sina_source.id)
                stats["skipped"] += max(0, len(dxy_proxy) - n)
                stats["groups"]["dxy_proxy"] = n
                stats["quotes"] += n

            n = store.upsert_quotes(session, quotes, symbol_ids, em_source.id)
            stats["skipped"] += max(0, len(quotes) - n)
            store.record_health(
                session,
                em_source.id,
                ok=not em_failed,
                latency_ms=int((time.perf_counter() - t0) * 1000),
                error=("quote failed: " + ", ".join(em_failed)) if em_failed else None,
            )
            stats["groups"]["cn_equity"] = n
            stats["quotes"] += n
            if em_failed:
                stats["errors"].append(f"cn_equity: {', '.join(em_failed)}")
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
