"""Daily bar collection and the pre-persist tail guard."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from app.ingest import bars_quality, store
from app.ingest.collectors.quotes import _quote_symbols
from app.ingest.contracts import Bar
from app.ingest.http import HttpClient
from app.ingest.providers import eastmoney, frankfurter, sina, tencent
from app.ingest.sources import SOURCE_EM, SOURCE_FRANKFURTER, SOURCE_SINA, SOURCE_TENCENT
from app.ingest.symbols import (
    CN_FUTURES,
    EM_DAILY_SECID,
    EM_SECID,
    SINA_FX_DAILY,
    SINA_GLOBAL_FUTURES,
    TENCENT_KLINE,
    TENCENT_KLINE_RAW,
    TENCENT_SINGLE_BAR,
)
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


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
