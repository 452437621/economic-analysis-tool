"""Collection pipelines: quotes, daily bars, US yields, official news."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.ingest import store
from app.ingest.contracts import Bar, Quote
from app.ingest.http import HttpClient
from app.ingest.providers import (
    czce,
    czce_positions,
    eastmoney,
    eastmoney_calendar,
    eastmoney_yield,
    ecb,
    frankfurter,
    jgb,
    nyfed,
    rss,
    shfe_positions,
    sina,
    sina_positions,
    treasury,
)
from app.ingest.providers.html_extract import extract_main_text
from app.ingest.symbols import (
    CN_FUTURES,
    EM_DAILY_SECID,
    EM_QUOTE_SECID,
    EM_SECID,
    SINA_FX,
    SINA_GLOBAL_FUTURES,
    SINA_HF,
    compute_dxy,
)
from app.knowledge.extract import extract_numeric_claims
from app.knowledge.store import save_claims
from app.models.core import (
    DataCheck,
    Document,
    DocumentBody,
    EconomicEvent,
    Instrument,
    MacroObs,
    MacroSeries,
    MarketBar,
    MemberPosition,
    PositionSnapshot,
    Quote as QuoteRow,
)
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
SOURCE_JGB = dict(
    name="日本财务省", kind="official", tier="S1", reliability=0.95, base_url="https://www.mof.go.jp"
)
SOURCE_ECB = dict(
    name="欧洲央行", kind="official", tier="S1", reliability=0.95, base_url="https://data.ecb.europa.eu"
)
SOURCE_SHFE = dict(
    name="上海期货交易所", kind="official", tier="S1", reliability=0.95, base_url="https://www.shfe.com.cn"
)
SOURCE_CZCE = dict(
    name="郑州商品交易所", kind="official", tier="S1", reliability=0.95, base_url="https://www.czce.com.cn"
)
SOURCE_NYFED = dict(
    name="纽约联储", kind="official", tier="S1", reliability=0.95, base_url="https://markets.newyorkfed.org"
)
SOURCE_FRANKFURTER = dict(
    name="Frankfurter(ECB参考汇率)", kind="market", tier="S2", reliability=0.9, base_url="https://api.frankfurter.app"
)

NEWS_FEEDS = [
    dict(name="美联储", url="https://www.federalreserve.gov/feeds/press_all.xml", kind="rss", tier="S1"),
    dict(name="欧洲央行", url="https://www.ecb.europa.eu/rss/press.html", kind="rss", tier="S1"),
    dict(name="日本央行", url="https://www.boj.or.jp/en/rss/whatsnew.xml", kind="rss", tier="S1"),
    dict(name="美国能源信息署", url="https://www.eia.gov/rss/todayinenergy.xml", kind="rss", tier="S1"),
    dict(name="美国贸易代表办公室", url="https://ustr.gov/rss.xml", kind="rss", tier="S1"),
]

# 体积大/更新慢的官方源，单独低频采集
NEWS_FEEDS_SLOW = [
    dict(name="国家统计局", url="https://www.stats.gov.cn/sj/zxfb/rss.xml", kind="rss", tier="S1"),
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
    "JP2Y": {"name": "日本国债2年", "unit": "%", "country": "JP"},
    "JP10Y": {"name": "日本国债10年", "unit": "%", "country": "JP"},
    "JP30Y": {"name": "日本国债30年", "unit": "%", "country": "JP"},
    "DE2Y": {"name": "德国国债2年", "unit": "%", "country": "DE"},
    "DE10Y": {"name": "德国国债10年", "unit": "%", "country": "DE"},
    "FR10Y": {"name": "法国国债10年（月度）", "unit": "%", "country": "FR"},
    "CN2Y": {"name": "中国国债2年", "unit": "%", "country": "CN"},
    "CN5Y": {"name": "中国国债5年", "unit": "%", "country": "CN"},
    "CN10Y": {"name": "中国国债10年", "unit": "%", "country": "CN"},
    "CN30Y": {"name": "中国国债30年", "unit": "%", "country": "CN"},
    "CN10Y2Y": {"name": "中国国债10年-2年利差", "unit": "pp", "country": "CN"},
    "SOFR": {"name": "担保隔夜融资利率(SOFR)", "unit": "%", "country": "US"},
    "EFFR": {"name": "联邦基金有效利率(EFFR)", "unit": "%", "country": "US"},
    "SOFR_EFFR": {"name": "SOFR-EFFR 利差", "unit": "pp", "country": "US"},
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

        # 3) FX + computed DXY proxy (fallback if Eastmoney DXY unavailable)
        dxy_price = None
        try:
            t0 = time.perf_counter()
            fx_quotes = sina.fetch_fx_quotes(client, SINA_FX)
            quotes = list(fx_quotes.values())
            dxy_price = compute_dxy({symbol: quote.price for symbol, quote in fx_quotes.items()})
            n = store.upsert_quotes(session, quotes, symbol_ids, sina_source.id)
            store.record_health(session, sina_source.id, ok=True, latency_ms=int((time.perf_counter() - t0) * 1000))
            stats["groups"]["fx"] = n
            stats["quotes"] += n
        except Exception as exc:  # noqa: BLE001
            logger.exception("fx quotes failed")
            store.record_health(session, sina_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"fx: {exc}")

        # 4) A-share / index / DXY / USDCNH via Eastmoney
        try:
            t0 = time.perf_counter()
            quotes = []
            for symbol, secid in {**EM_SECID, **EM_QUOTE_SECID}.items():
                quote = eastmoney.fetch_quote(client, secid, symbol)
                if quote:
                    quotes.append(quote)
            fetched = {quote.symbol for quote in quotes}
            if dxy_price and "DXY" not in fetched:
                quotes.append(Quote(symbol="DXY", ts=_now(), price=dxy_price, delay_sec=30))
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

        # Overseas futures / spot daily bars (Sina GlobalFuturesService)
        for symbol, code in SINA_GLOBAL_FUTURES.items():
            instrument_id = symbol_ids.get(symbol)
            if not instrument_id:
                continue
            try:
                bars = _latest(sina.fetch_global_daily(client, code), 2000)
                n = store.upsert_bars(session, instrument_id, "1d", bars, sina_source.id, delay_sec=900)
                stats["bars"] += n
                stats["symbols"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("global daily bars failed: %s", symbol)
                stats["errors"].append(f"{symbol}: {exc}")

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

        for symbol, secid in EM_DAILY_SECID.items():
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

        # FX daily history: Frankfurter (ECB reference rates)
        fx_source = store.get_source(session, **SOURCE_FRANKFURTER)
        try:
            fx_bars = frankfurter.fetch_daily(
                client, start_date=datetime.now(timezone.utc).date() - timedelta(days=365 * 5)
            )
            for symbol, bars in fx_bars.items():
                instrument_id = symbol_ids.get(symbol)
                if not instrument_id or not bars:
                    continue
                n = store.upsert_bars(session, instrument_id, "1d", _latest(bars, 2000), fx_source.id, delay_sec=0)
                stats["bars"] += n
                stats["symbols"] += 1
            store.record_health(session, fx_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("frankfurter fx failed")
            store.record_health(session, fx_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"fx: {exc}")

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

        # Japan MOF JGB yields
        jgb_source = store.get_source(session, **SOURCE_JGB)
        try:
            curves = jgb.fetch_rates(client, start_year=current_year - 4)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=jgb_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                )
                stats["points"] += n
                stats["series"] += 1
            store.record_health(session, jgb_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("jgb rates failed")
            store.record_health(session, jgb_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"jgb: {exc}")

        # ECB Germany benchmark yields
        ecb_source = store.get_source(session, **SOURCE_ECB)
        try:
            curves = ecb.fetch_rates(client, start_year=current_year - 4)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=ecb_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                )
                stats["points"] += n
                stats["series"] += 1
            store.record_health(session, ecb_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ecb rates failed")
            store.record_health(session, ecb_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"ecb: {exc}")

        # France 10Y convergence rate (ECB IRS, monthly)
        try:
            curves = ecb.fetch_france_rates(client, start_year=current_year - 4)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=ecb_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                )
                stats["points"] += n
                stats["series"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("ecb france rates failed")
            stats["errors"].append(f"ecb_fr: {exc}")

        # Eastmoney China (and US) treasury yields
        em_yield_source = store.get_source(session, **SOURCE_EM)
        try:
            curves = eastmoney_yield.fetch_rates(client, start_year=current_year - 4)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=em_yield_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                )
                stats["points"] += n
                stats["series"] += 1
            store.record_health(session, em_yield_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("eastmoney yields failed")
            store.record_health(session, em_yield_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"em_yield: {exc}")

        # NY Fed: SOFR / EFFR / spread
        nyfed_source = store.get_source(session, **SOURCE_NYFED)
        try:
            start = (datetime.now(timezone.utc).date() - timedelta(days=365 * 5))
            curves = nyfed.fetch_rates(client, start_date=start)
            for code, points in curves.items():
                meta = MACRO_SERIES_META.get(code, {})
                n = store.upsert_macro(
                    session,
                    code,
                    points,
                    source_id=nyfed_source.id,
                    name=meta.get("name"),
                    unit=meta.get("unit"),
                    country=meta.get("country"),
                )
                stats["points"] += n
                stats["series"] += 1
            store.record_health(session, nyfed_source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("nyfed rates failed")
            store.record_health(session, nyfed_source.id, ok=False, error=str(exc))
            stats["errors"].append(f"nyfed: {exc}")
        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_rates: %s", stats)
    return stats


def collect_positions() -> dict:
    """Fetch SHFE + CZCE member position rankings (top-20 long/short)."""
    started = time.perf_counter()
    stats: dict = {"trade_date": None, "products": 0, "errors": []}
    with HttpClient(min_interval=0.5) as client, SessionLocal() as session:
        for label, fetcher, source_conf in (
            ("shfe", shfe_positions.fetch_latest, SOURCE_SHFE),
            ("czce", czce_positions.fetch_latest, SOURCE_CZCE),
            ("sina", sina_positions.fetch_latest, SOURCE_SINA),
        ):
            source = store.get_source(session, **source_conf)
            try:
                report_date, rows = fetcher(client)
                if not report_date or not rows:
                    raise RuntimeError(f"no {label} position report available")
                for item in rows:
                    existing = session.scalar(
                        select(PositionSnapshot).where(
                            PositionSnapshot.trade_date == report_date,
                            PositionSnapshot.product == item["product"],
                        )
                    )
                    if existing is None:
                        existing = PositionSnapshot(
                            trade_date=report_date,
                            product=item["product"],
                            name=item["name"],
                        )
                        session.add(existing)
                    existing.name = item["name"]
                    existing.long_pos = item["long_pos"]
                    existing.short_pos = item["short_pos"]
                    existing.net_pos = item["net_pos"]
                    existing.net_ratio = item["net_ratio"]
                    existing.long_chg = item["long_chg"]
                    existing.short_chg = item["short_chg"]
                    session.execute(
                        delete(MemberPosition).where(
                            MemberPosition.trade_date == report_date,
                            MemberPosition.product == item["product"],
                        )
                    )
                    for member in item.get("members") or []:
                        if not member.get("member") or not member.get("rank"):
                            continue
                        session.add(
                            MemberPosition(
                                trade_date=report_date,
                                product=item["product"],
                                name=item["name"],
                                side=member["side"],
                                rank=int(member["rank"]),
                                member=str(member["member"]),
                                position=int(member.get("position") or 0),
                                change=int(member.get("change") or 0),
                            )
                        )
                session.commit()
                stats["products"] += len(rows)
                date_str = report_date.isoformat()
                stats["trade_date"] = max(stats["trade_date"], date_str) if stats["trade_date"] else date_str
                store.record_health(session, source.id, ok=True)
            except Exception as exc:  # noqa: BLE001
                logger.exception("%s positions failed", label)
                store.record_health(session, source.id, ok=False, error=str(exc))
                stats["errors"].append(f"{label}: {exc}")
    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_positions: %s", stats)
    return stats


def collect_calendar(days_ahead: int = 14, days_back: int = 180) -> dict:
    started = time.perf_counter()
    stats: dict = {"events": 0, "new": 0, "errors": []}
    now = datetime.now(timezone.utc)
    today = now.astimezone(timezone(timedelta(hours=8))).date()
    start = today - timedelta(days=days_back)
    end = today + timedelta(days=days_ahead)

    with HttpClient(min_interval=0.5) as client, SessionLocal() as session:
        source = store.get_source(session, **SOURCE_EM)
        try:
            events = eastmoney_calendar.fetch_calendar(client, start, end)
            existing = {
                (ts.replace(tzinfo=None) if ts.tzinfo else ts, name)
                for ts, name in session.execute(
                    select(EconomicEvent.ts_utc, EconomicEvent.name)
                ).all()
            }
            for event in events:
                naive_ts = event["ts_utc"].replace(tzinfo=None)
                if (naive_ts, event["name"]) in existing:
                    continue
                session.add(
                    EconomicEvent(
                        ts_utc=naive_ts,
                        name=event["name"],
                        category=event["category"],
                        country=event["country"],
                        importance=event["importance"],
                        source_code=event["source_code"],
                    )
                )
                existing.add((naive_ts, event["name"]))
                stats["new"] += 1
            cutoff = now.replace(tzinfo=None) - timedelta(days=365)
            session.execute(delete(EconomicEvent).where(EconomicEvent.ts_utc < cutoff))
            session.execute(delete(EconomicEvent).where(EconomicEvent.name.like("%累计同比%")))
            session.commit()
            stats["events"] = len(events)
            store.record_health(session, source.id, ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("calendar failed")
            store.record_health(session, source.id, ok=False, error=str(exc))
            stats["errors"].append(str(exc))
    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_calendar: %s", stats)
    return stats


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


def collect_bodies(limit: int = 20) -> dict:
    """Fetch full text of official documents and keep a content hash."""
    started = time.perf_counter()
    stats: dict = {"fetched": 0, "skipped": 0, "failed": 0, "errors": []}

    with HttpClient(min_interval=0.8) as client, SessionLocal() as session:
        documents = session.scalars(
            select(Document)
            .where(Document.body_status == "metadata")
            .order_by(func.coalesce(Document.published_at, Document.fetched_at).desc())
            .limit(limit)
        ).all()
        for document in documents:
            existing = session.scalar(
                select(DocumentBody).where(DocumentBody.document_id == document.id)
            )
            if existing is not None:
                document.body_status = "extracted"
                stats["skipped"] += 1
                continue
            try:
                resp = client.get(document.url)
                resp.raise_for_status()
                text = extract_main_text(resp.text)
                if len(text) < 80:
                    document.body_status = "no_body"
                    stats["skipped"] += 1
                    continue
                session.add(
                    DocumentBody(
                        document_id=document.id,
                        text=text,
                        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        word_count=len(text),
                    )
                )
                document.body_status = "extracted"
                stats["fetched"] += 1
                session.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("body fetch failed %s: %s", document.id, exc)
                document.body_status = "failed"
                stats["failed"] += 1
                stats["errors"].append(f"{document.id}: {exc}")
        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("collect_bodies: %s", stats)
    return stats


def extract_claims(limit: int = 30) -> dict:
    """Extract numeric claims + spans from stored bodies (rule-based v1)."""
    started = time.perf_counter()
    stats: dict = {"documents": 0, "claims": 0, "errors": []}

    with SessionLocal() as session:
        from app.models.core import Claim

        source_names = {
            row.id: row.name for row in session.scalars(select(store.Source)).all()
        }
        documents = session.scalars(
            select(Document)
            .where(Document.body_status == "extracted")
            .order_by(func.coalesce(Document.published_at, Document.fetched_at).desc())
            .limit(limit)
        ).all()
        for document in documents:
            body = session.scalar(
                select(DocumentBody).where(DocumentBody.document_id == document.id)
            )
            if body is None:
                document.body_status = "no_body"
                continue
            existing = session.scalar(
                select(func.count()).select_from(Claim).where(Claim.document_id == document.id)
            )
            if not existing:
                claims = extract_numeric_claims(
                    body.text, default_subject=source_names.get(document.source_id)
                )
                if claims:
                    stats["claims"] += save_claims(session, document, claims, method="rule")
            document.body_status = "claims_extracted"
            stats["documents"] += 1
            session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("extract_claims: %s", stats)
    return stats


def extract_claims_llm(limit: int = 8) -> dict:
    """LLM claim extraction (requires DEEPSEEK_API_KEY). Falls back cleanly."""
    from app.knowledge.llm_extract import extract_claims_with_llm
    from app.llm.client import LLMClient
    from app.models.core import Source

    client = LLMClient()
    if not client.available:
        return {"skipped": "no_api_key"}
    stats: dict = {"documents": 0, "claims": 0, "errors": []}

    with SessionLocal() as session:
        source_names = {row.id: row.name for row in session.scalars(select(Source)).all()}
        documents = session.scalars(
            select(Document)
            .where(Document.body_status.in_(["extracted", "claims_extracted"]))
            .order_by(func.coalesce(Document.published_at, Document.fetched_at).desc())
            .limit(limit * 3)
        ).all()
        processed = 0
        for document in documents:
            if processed >= limit:
                break
            meta = dict(document.meta or {})
            if meta.get("llm_extracted"):
                continue
            body = session.scalar(
                select(DocumentBody).where(DocumentBody.document_id == document.id)
            )
            if body is None:
                continue
            try:
                claims = extract_claims_with_llm(
                    client, body.text, default_subject=source_names.get(document.source_id)
                )
                if claims:
                    stats["claims"] += save_claims(session, document, claims, method="llm")
                meta["llm_extracted"] = True
                document.meta = meta
                session.commit()
                stats["documents"] += 1
                processed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("llm extraction failed for %s: %s", document.id, exc)
                session.rollback()
                stats["errors"].append(f"{document.id}: {exc}")
    return stats


def check_data_quality() -> dict:
    """Cross-check official CZCE daily quotes and dataset freshness."""
    started = time.perf_counter()
    stats: dict = {"checks": 0, "failed": 0, "errors": []}

    with HttpClient(min_interval=0.8) as client, SessionLocal() as session:
        for symbol in ("SR", "CF"):
            instrument = session.scalar(select(Instrument).where(Instrument.symbol == symbol))
            if instrument is None:
                continue
            bar = session.scalar(
                select(MarketBar)
                .where(MarketBar.instrument_id == instrument.id, MarketBar.timeframe == "1d")
                .order_by(MarketBar.ts_utc.desc())
                .limit(1)
            )
            if bar is None:
                continue
            try:
                rows = czce.fetch_daily(client, bar.ts_utc.date())
                main_contract = czce.main_contract(rows.get(symbol, []))
                expected = main_contract.close if main_contract else None
                actual = bar.close
                deviation = abs(actual - expected) / expected if expected else None
                passed = deviation is not None and deviation <= 0.002
                session.add(
                    DataCheck(
                        kind="reconcile",
                        dataset="CZCE官方日行情",
                        symbol=symbol,
                        expected=expected,
                        actual=actual,
                        deviation=deviation,
                        passed=passed,
                        detail=main_contract.code if main_contract else "未找到主力合约",
                    )
                )
                stats["checks"] += 1
                if not passed:
                    stats["failed"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("quality check failed %s: %s", symbol, exc)
                stats["errors"].append(f"{symbol}: {exc}")
            session.commit()

        now = _now()

        def freshness(dataset: str, latest, max_age_days: int) -> None:
            if latest is not None and latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            age = (now - latest).days if latest is not None else None
            passed = age is not None and age <= max_age_days
            session.add(
                DataCheck(
                    kind="freshness",
                    dataset=dataset,
                    check_date=now,
                    passed=passed,
                    detail=f"latest={latest.date() if latest else None}, age_days={age}",
                )
            )
            stats["checks"] += 1
            if not passed:
                stats["failed"] += 1

        freshness("国内期货日线", session.scalar(select(func.max(MarketBar.ts_utc))), 5)
        freshness("美债利率", session.scalar(select(func.max(MacroObs.ts_utc))), 10)
        freshness("行情快照", session.scalar(select(func.max(QuoteRow.ts_utc))), 1)
        freshness(
            "官方新闻",
            session.scalar(select(func.max(func.coalesce(Document.published_at, Document.fetched_at)))),
            3,
        )

        coverage = session.execute(
            select(Instrument.symbol, func.count(MarketBar.id))
            .outerjoin(
                MarketBar,
                (MarketBar.instrument_id == Instrument.id) & (MarketBar.timeframe == "1d"),
            )
            .where(Instrument.active.is_(True))
            .group_by(Instrument.id)
        ).all()
        missing = [symbol for symbol, count in coverage if count == 0]
        session.add(
            DataCheck(
                kind="coverage",
                dataset="启用标的日线覆盖",
                check_date=now,
                expected=len(coverage),
                actual=len(coverage) - len(missing),
                deviation=len(missing),
                passed=not missing,
                detail="缺失: " + ", ".join(missing) if missing else "全部启用标的均有日线",
            )
        )
        stats["checks"] += 1
        if missing:
            stats["failed"] += 1

        macro_coverage = session.execute(
            select(MacroSeries.code, func.count(MacroObs.id))
            .outerjoin(MacroObs, MacroObs.series_id == MacroSeries.id)
            .group_by(MacroSeries.id)
        ).all()
        missing_macro = [code for code, count in macro_coverage if count == 0]
        session.add(
            DataCheck(
                kind="coverage",
                dataset="宏观序列覆盖",
                check_date=now,
                expected=len(macro_coverage),
                actual=len(macro_coverage) - len(missing_macro),
                deviation=len(missing_macro),
                passed=not missing_macro,
                detail="缺失: " + ", ".join(missing_macro) if missing_macro else "全部宏观序列均有观测",
            )
        )
        stats["checks"] += 1
        if missing_macro:
            stats["failed"] += 1
        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("check_data_quality: %s", stats)
    return stats
