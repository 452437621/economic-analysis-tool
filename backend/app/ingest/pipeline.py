"""Collection pipelines: quotes, daily bars, US yields, official news."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.ingest import bars_quality, continuity, store
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
    tencent,
    treasury,
)
from app.ingest.providers.html_extract import extract_main_text
from app.ingest.symbols import (
    CN_FUTURES,
    EM_DAILY_SECID,
    EM_QUOTE_SECID,
    EM_SECID,
    SINA_FX,
    SINA_FX_DAILY,
    SINA_GLOBAL_FUTURES,
    SINA_HF,
    TENCENT_KLINE,
    TENCENT_KLINE_RAW,
    TENCENT_QUOTE,
    TENCENT_QUOTE_PREFERRED,
    TENCENT_SINGLE_BAR,
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
SOURCE_TENCENT = dict(
    name="腾讯财经", kind="market", tier="S2", reliability=0.8, base_url="https://gu.qq.com"
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
    "FR10Y": {"name": "法国国债10年（月度）", "unit": "%", "country": "FR", "freq": "m"},
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


# 日线入库上限：与 /api/market/bars 的 limit 上限（3000）和前端「全部」一致，
# 否则历史弹窗拿到的深度会被采集端的截断悄悄削掉（新浪 CF0 有 5319 根）。
DAILY_BAR_LIMIT = 3000

# 末根与上一根收盘价偏离超过这个百分比，就认为上游给的是脏数据。
MAX_TAIL_MOVE_PCT = 25.0


def _guard_tail_bar(client: HttpClient, symbol: str, bars: list[Bar]) -> list[Bar]:
    """落库前拦掉「最新一根被上游写坏」的行情。

    实测腾讯原始端点 ``us.NDX`` 在 2026-11-16 返回 close=10.0（当日纳斯达克100
    实收 27197.15），这种点一旦入库，趋势图会出现断崖，而且每次重跑都会把它覆盖
    回来。处理顺序：先用单根接口订正；订正不了就丢掉这一根——宁可留一天缺口，
    也不能让假行情留在序列里（缺口会由 continuity 检查报出来）。
    """
    if len(bars) < 2 or not bars[-2].close or not bars[-1].close:
        return bars
    move = abs(bars[-1].close / bars[-2].close - 1.0) * 100.0
    if move <= MAX_TAIL_MOVE_PCT:
        return bars
    single_code = TENCENT_SINGLE_BAR.get(symbol)
    if single_code:
        try:
            single = tencent.fetch_daily_kline(client, single_code, adjust=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("single-bar fallback failed: %s (%s)", symbol, exc)
            single = []
        fresh = single[-1] if single else None
        if (
            fresh is not None
            and fresh.ts.date() == bars[-1].ts.date()
            and abs(fresh.close / bars[-2].close - 1.0) * 100.0 <= MAX_TAIL_MOVE_PCT
        ):
            logger.warning(
                "tail bar corrected: %s %s %s -> %s",
                symbol, bars[-1].ts.date(), bars[-1].close, fresh.close,
            )
            bars[-1] = Bar(
                ts=bars[-1].ts,
                open=fresh.open,
                high=fresh.high,
                low=fresh.low,
                close=fresh.close,
                volume=fresh.volume,
                open_interest=fresh.open_interest,
            )
            return bars
    logger.warning(
        "tail bar dropped: %s %s close=%s (%.1f%% vs prev)",
        symbol, bars[-1].ts.date(), bars[-1].close, move,
    )
    return bars[:-1]


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


def collect_daily_bars() -> dict:
    """Backfill/update daily bars: domestic futures (Sina) + A-share (Eastmoney)."""
    started = time.perf_counter()
    stats: dict = {
        "bars": 0,
        "symbols": 0,
        "tencent_fallback": 0,
        "tencent_daily": 0,
        "sina_fx_daily": 0,
        "errors": [],
    }

    with HttpClient(min_interval=0.4) as client, SessionLocal() as session:
        sina_source = store.get_source(session, **SOURCE_SINA)
        em_source = store.get_source(session, **SOURCE_EM)
        symbol_ids = _quote_symbols(session)

        sina_errors: list[str] = []
        for symbol, code in CN_FUTURES.items():
            instrument_id = symbol_ids.get(symbol)
            if not instrument_id:
                continue
            try:
                bars = _latest(sina.fetch_daily_continuous(client, code), DAILY_BAR_LIMIT)
                bars = bars_quality.drop_holiday_stubs(bars)
                n = store.upsert_bars(session, instrument_id, "1d", bars, sina_source.id, delay_sec=0)
                stats["bars"] += n
                stats["symbols"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("daily bars failed: %s", symbol)
                stats["errors"].append(f"{symbol}: {exc}")
                sina_errors.append(f"{symbol}: {exc}")

        # Overseas futures / spot daily bars (Sina GlobalFuturesService)
        for symbol, code in SINA_GLOBAL_FUTURES.items():
            instrument_id = symbol_ids.get(symbol)
            if not instrument_id:
                continue
            try:
                bars = _latest(sina.fetch_global_daily(client, code), DAILY_BAR_LIMIT)
                bars = bars_quality.drop_holiday_stubs(bars)
                n = store.upsert_bars(session, instrument_id, "1d", bars, sina_source.id, delay_sec=900)
                stats["bars"] += n
                stats["symbols"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("global daily bars failed: %s", symbol)
                stats["errors"].append(f"{symbol}: {exc}")
                sina_errors.append(f"{symbol}: {exc}")
        # 新浪的健康状态在全部新浪抓取（期货 + 外汇日线）结束后统一记录

        # 日线优先级链：排在前面且成功的来源优先落库，全链失败才记错。
        # - 美国指数（SPX/NDX/DJIA）走腾讯原始 K 线端点优先。东财在美股盘中会把当日
        #   未收盘的残根写进日线（2026-11-13 SPX 存 7520.77，实际收盘 7561.67），一旦
        #   东财端点停更，残根就永久固化，看起来像"数据停滞"。
        # - 美元指数/离岸人民币走新浪外汇日线优先。东财 K 线端点 push2his 长期不可达，
        #   而新浪 NewForexService 能直接给出 DXY/USDCNH 的完整日线。
        # - A股/恒生保持东财优先（口径最好），腾讯前复权端点兜底。
        em_errors: list[str] = []
        tencent_errors: list[str] = []
        sina_fx_errors: list[str] = []
        tencent_source = None
        for symbol, secid in {**EM_SECID, **EM_DAILY_SECID}.items():
            instrument_id = symbol_ids.get(symbol)
            if not instrument_id:
                continue
            bars = None
            source_id = em_source.id
            if symbol in TENCENT_KLINE_RAW:
                code = TENCENT_KLINE_RAW[symbol]
                try:
                    bars = _latest(tencent.fetch_daily_kline(client, code, adjust=False), DAILY_BAR_LIMIT)
                    bars = _guard_tail_bar(client, symbol, bars)
                    if tencent_source is None:
                        tencent_source = store.get_source(session, **SOURCE_TENCENT)
                    source_id = tencent_source.id
                    stats["tencent_daily"] += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("tencent raw daily kline failed: %s (%s)", symbol, exc)
                    tencent_errors.append(f"{symbol}: {exc}")
            elif symbol in SINA_FX_DAILY:
                code = SINA_FX_DAILY[symbol]
                try:
                    bars = _latest(sina.fetch_forex_daily(client, code), DAILY_BAR_LIMIT)
                    source_id = sina_source.id
                    stats["sina_fx_daily"] += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("sina forex daily failed: %s (%s)", symbol, exc)
                    sina_fx_errors.append(f"{symbol}: {exc}")
            if bars is None:
                try:
                    bars = _latest(eastmoney.fetch_daily_kline(client, secid), DAILY_BAR_LIMIT)
                    source_id = em_source.id
                except Exception as exc:  # noqa: BLE001
                    logger.exception("eastmoney daily kline failed: %s", symbol)
                    em_errors.append(f"{symbol}: {exc}")
                    code = TENCENT_KLINE.get(symbol)
                    if code is None:
                        stats["errors"].append(f"{symbol}: {exc}")
                        continue
                    try:
                        bars = _latest(tencent.fetch_daily_kline(client, code), DAILY_BAR_LIMIT)
                        if tencent_source is None:
                            tencent_source = store.get_source(session, **SOURCE_TENCENT)
                        source_id = tencent_source.id
                        stats["tencent_fallback"] += 1
                    except Exception as fallback_exc:  # noqa: BLE001
                        logger.exception("tencent daily kline failed: %s", symbol)
                        tencent_errors.append(f"{symbol}: {fallback_exc}")
                        stats["errors"].append(f"{symbol}: {fallback_exc}")
                        continue
            bars = bars_quality.drop_holiday_stubs(bars)
            n = store.upsert_bars(session, instrument_id, "1d", bars, source_id)
            stats["bars"] += n
            stats["symbols"] += 1

        # 东财日线端点（kline/get）可能被边缘风控单独丢弃，而实时报价（分时兜底）仍然
        # 可用；东财的健康状态由每 5 分钟一次的 collect_quotes 判定，这里不再覆盖，
        # 避免日线端点被拦时「东方财富」在健康页来回闪烁。
        if em_errors:
            stats["eastmoney_daily_failed"] = len(em_errors)
            logger.warning("eastmoney daily kline failed for %s symbols", len(em_errors))
        if tencent_source is not None:
            store.record_health(
                session,
                tencent_source.id,
                ok=not tencent_errors,
                error=("; ".join(tencent_errors))[:1000] if tencent_errors else None,
            )
        if sina_fx_errors:
            stats["errors"].append(f"sina fx daily: {', '.join(sina_fx_errors)}")
        # 每个来源只标记自己那部分结果，避免新浪的失败把东财记成失败（反之亦然）
        store.record_health(
            session,
            sina_source.id,
            ok=not (sina_errors or sina_fx_errors),
            error=("; ".join(sina_errors + sina_fx_errors))[:1000]
            if (sina_errors or sina_fx_errors)
            else None,
        )

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
                n = store.upsert_bars(session, instrument_id, "1d", bars_quality.drop_holiday_stubs(_latest(bars, DAILY_BAR_LIMIT)), fx_source.id, delay_sec=0)
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
                    freq=meta.get("freq"),
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
                    freq=meta.get("freq"),
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
                    freq=meta.get("freq"),
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
                    freq=meta.get("freq"),
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
                    freq=meta.get("freq"),
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
                    freq=meta.get("freq"),
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

        def freshness(dataset: str, latest, max_age_days: int, note: str | None = None) -> None:
            if latest is not None and latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            age = (now - latest).days if latest is not None else None
            if age is not None and age < 0:
                # 个别新闻源会给出「未来」时间戳（时区换算/预告稿），按当日算，
                # 否则页面会出现「距今-1天」这种看不懂的字样。
                age = 0
            passed = age is not None and age <= max_age_days
            detail = f"最新={latest.date() if latest else '无'}"
            if age is not None:
                detail += f", 距今{age}天"
            if not passed:
                detail += f", 超过{max_age_days}天阈值"
            if note:
                detail += f" ({note})"
            session.add(
                DataCheck(
                    kind="freshness",
                    dataset=dataset,
                    check_date=now,
                    passed=passed,
                    detail=detail,
                )
            )
            stats["checks"] += 1
            if not passed:
                stats["failed"] += 1

        # 日线：按标的逐条比对，避免"某个标的停更被全表最大值掩盖"。
        bar_max_age_days = 5
        bar_latest = session.execute(
            select(Instrument.symbol, func.max(MarketBar.ts_utc))
            .join(MarketBar, MarketBar.instrument_id == Instrument.id)
            .where(MarketBar.timeframe == "1d")
            .group_by(Instrument.id)
        ).all()
        if bar_latest:
            def _age(value):
                if value is None:
                    return None
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                return (now - value).days

            pairs = [(symbol, ts, _age(ts)) for symbol, ts in bar_latest]
            latest_ts = max((ts for _, ts, _ in pairs if ts is not None), default=None)
            stale = sorted(
                [
                    (symbol, ts, age)
                    for symbol, ts, age in pairs
                    if age is None or age > bar_max_age_days
                ],
                key=lambda item: (item[2] is not None, -(item[2] or 0)),
            )
            detail = f"最新={latest_ts.date() if latest_ts else '无'}, 标的{len(pairs)}个"
            if stale:
                detail += "; 滞后: " + ", ".join(
                    f"{symbol}:{ts.date() if ts else '无'}({age}天)" for symbol, ts, age in stale[:6]
                )
                if len(stale) > 6:
                    detail += f" 等{len(stale)}个"
            session.add(
                DataCheck(
                    kind="freshness",
                    dataset="日线行情",
                    check_date=now,
                    passed=not stale,
                    detail=detail,
                )
            )
            stats["checks"] += 1
            if stale:
                stats["failed"] += 1

        # 宏观序列：按序列频率给阈值（日频 5 天 / 周频 10 天 / 月频 70 天 / 季频 150 天），
        # 逐条检查——全表最大值会把"日债停在 10-30"这类单序列断更完全掩盖。
        # 月/季频阈值要留出官方发布滞后（如 ECB 法国10年 11-01 的观测要到 12 月初才发布）。
        freq_days = {"d": 5, "w": 10, "m": 70, "q": 150}
        macro_rows = session.execute(
            select(MacroSeries.code, MacroSeries.freq, func.max(MacroObs.ts_utc))
            .outerjoin(MacroObs, MacroObs.series_id == MacroSeries.id)
            .group_by(MacroSeries.id)
        ).all()
        if macro_rows:
            stale_macro: list[str] = []
            oldest = None
            for code, freq, ts in macro_rows:
                age = None
                if ts is not None:
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age = (now - ts).days
                limit = freq_days.get((freq or "d").lower(), 5)
                if age is None or age > limit:
                    stale_macro.append(f"{code}:{ts.date() if ts else '无'}({age}天, {freq}频)")
                if ts is not None and (oldest is None or ts < oldest):
                    oldest = ts
            detail = f"序列{len(macro_rows)}条, 最旧={oldest.date() if oldest else '无'}"
            if stale_macro:
                detail += "; 滞后: " + ", ".join(stale_macro[:8])
                if len(stale_macro) > 8:
                    detail += f" 等{len(stale_macro)}条"
            session.add(
                DataCheck(
                    kind="freshness",
                    dataset="宏观序列",
                    check_date=now,
                    passed=not stale_macro,
                    detail=detail,
                )
            )
            stats["checks"] += 1
            if stale_macro:
                stats["failed"] += 1

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

        # 历史连续性：不预置交易日历，用「同业共识」判断某个标的漏了哪天
        # （休市日不会被误判），趋势图缺一根或出现错误行情都会在这里暴露。
        for dataset, findings in (
            ("日线行情", continuity.daily_findings(session)),
            ("宏观序列", continuity.macro_findings(session)),
        ):
            known = continuity.missing_known_gaps(session) if dataset == "日线行情" else 0
            passed, problems, detail = continuity.summarize(findings, known_gaps=known)
            session.add(
                DataCheck(
                    kind="continuity",
                    dataset=f"{dataset}连续性",
                    check_date=now,
                    expected=len({item.subject for item in findings}),
                    actual=0,
                    deviation=problems,
                    passed=passed,
                    detail=detail,
                )
            )
            stats["checks"] += 1
            if not passed:
                stats["failed"] += 1

        # 分钟级行情快照只保留最近 N 天（EPIC_QUOTES_RETENTION_DAYS），
        # 一天清理一次把 SQLite 文件大小压回稳态。
        stats["quotes_pruned"] = store.prune_quotes(session)
        session.commit()

    stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    logger.info("check_data_quality: %s", stats)
    return stats
