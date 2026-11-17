"""历史数据补全：按缺口日期回补官方日线，并订正上游错误行情。

分三层职责：

* :func:`clean_holiday_stubs` 清掉历史里已经入库的「休市伪日线」——新浪在休市日
  会补一根假 K 线（开高低复制前一日、成交量复制或置 0），它不会让曲线断开，却会
  污染共识交易日、把正常标的误报成缺数据。
* :func:`fill_bar_gaps`   只补「共识交易日里确实缺的那几天」——郑商所（CZCE）
  提供逐日官方结算文件，能精确补回 CF/SR 这类数据源漏掉的交易日。其它交易所
  没有这类可回溯的公开文件（上期所 kx 归档文件只保留最近一批，2022 年的
  返回 404；大商所必须 POST 表单），因此只报缺口不臆造数据。
* :func:`repair_outliers` 上游偶尔把别的证券行情串到某天（实测腾讯 ``us.NDX``
  在 2026-11-16 给了 close=10.0，而当天纳斯达克100 收 27197.15）。这类点会
  让趋势图出现断崖，必须订正：先问腾讯「单根接口」拿当日正确收盘，订正不了
  就删掉这根脏数据，宁可留缺口也不能留假行情。

这些函数都不发起写事务外部依赖，调用方用 ``write_lock()`` 串行化。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ingest import bars_quality, continuity, store
from app.ingest.contracts import Bar
from app.ingest.http import HttpClient
from app.ingest.providers import czce, tencent
from app.ingest.symbols import TENCENT_SINGLE_BAR
from app.models.core import Instrument, MarketBar
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)


def _source_defs() -> tuple[dict, dict]:
    """复用 pipeline 里的源定义（name 相同的 source 会被 get_source 直接复用）。"""
    from app.ingest.pipeline import SOURCE_CZCE, SOURCE_TENCENT

    return SOURCE_CZCE, SOURCE_TENCENT

# 郑商所品种：官方逐日文件能回补历史缺口。
CZCE_PRODUCTS = ("CF", "SR")

# 末根/脏点订正时允许的最大偏离（与 continuity 的异常阈值保持一致）。
MAX_MOVE = 0.25


def _bar_from_czce(rows: list[czce.CzceRow], day: date) -> Bar | None:
    """把郑商所某品种某日的合约行聚成一根日线（取持仓量最大的主力合约）。"""
    main = czce.main_contract(rows)
    if main is None or not main.close:
        return None
    ts = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return Bar(
        ts=ts,
        open=main.open or main.close,
        high=main.high or main.close,
        low=main.low or main.close,
        close=main.close,
        volume=main.volume,
        open_interest=main.open_interest,
    )


def fill_bar_gaps(session: Session, client: HttpClient, *, max_days_per_symbol: int = 60) -> dict:
    """按共识缺口回补官方日线（当前只覆盖郑商所品种）。"""
    stats: dict = {"filled": 0, "symbols": 0, "attempted": 0, "unfillable": [], "errors": []}
    findings = continuity.daily_findings(session)
    gaps = [item for item in findings if item.issue == "gap"]
    if not gaps:
        return stats

    source = store.get_source(session, **_source_defs()[0])
    for finding in gaps:
        symbol = finding.subject
        if symbol not in CZCE_PRODUCTS:
            stats["unfillable"].append({"symbol": symbol, "count": len(finding.missing),
                                        "reason": "无逐日可回溯的官方文件"})
            continue
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == symbol))
        if instrument is None:
            continue
        filled = 0
        for day in finding.missing[:max_days_per_symbol]:
            stats["attempted"] += 1
            try:
                rows = czce.fetch_daily(client, day)
            except Exception as exc:  # noqa: BLE001
                logger.warning("czce backfill failed %s %s: %s", symbol, day, exc)
                stats["errors"].append(f"{symbol} {day}: {exc}")
                continue
            bar = _bar_from_czce(rows.get(symbol, []), day)
            if bar is None:
                continue
            store.upsert_bars(session, instrument.id, "1d", [bar], source.id)
            filled += 1
        if filled:
            stats["filled"] += filled
            stats["symbols"] += 1
        if len(finding.missing) > max_days_per_symbol:
            stats["unfillable"].append({"symbol": symbol, "count": len(finding.missing) - max_days_per_symbol,
                                        "reason": "超过单次回补上限"})
        session.commit()
    logger.info("fill_bar_gaps: %s", stats)
    return stats


def repair_outliers(session: Session, client: HttpClient) -> dict:
    """订正最近一段时间的错误行情（串码/脏数据），订正不了就删除该点。"""
    stats: dict = {"repaired": 0, "dropped": 0, "checked": 0, "errors": []}
    series = continuity.load_daily_bars(session)
    today = datetime.now(timezone.utc).date()
    horizon = today - timedelta(days=continuity.OUTLIER_LOOKBACK_DAYS)
    tencent_source = store.get_source(session, **_source_defs()[1])

    for symbol, rows in series.items():
        if symbol not in TENCENT_SINGLE_BAR:
            continue
        instrument = session.scalar(select(Instrument).where(Instrument.symbol == symbol))
        if instrument is None:
            continue
        for (prev_day, _po, _ph, _pl, prev_close), (day, _o, _h, _l, close) in zip(rows, rows[1:]):
            if day < horizon or not prev_close or not close:
                continue
            if abs(close / prev_close - 1.0) * 100.0 <= continuity.OUTLIER_PCT:
                continue
            stats["checked"] += 1
            try:
                single = tencent.fetch_daily_kline(client, TENCENT_SINGLE_BAR[symbol], adjust=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("single-bar repair failed %s: %s", symbol, exc)
                stats["errors"].append(f"{symbol}: {exc}")
                single = []
            fresh = single[-1] if single else None
            ts = datetime.combine(day, time.min, tzinfo=timezone.utc)
            # 单根接口只给「当日」一根：只有日期对得上才能拿来订正历史脏点，
            # 否则等于把今天的行情写到别的日期上。
            if (
                fresh is not None
                and fresh.ts.date() == day
                and abs(fresh.close / prev_close - 1.0) * 100.0 <= continuity.OUTLIER_PCT
            ):
                bar = Bar(
                    ts=ts,
                    open=fresh.open,
                    high=fresh.high,
                    low=fresh.low,
                    close=fresh.close,
                    volume=fresh.volume,
                    open_interest=fresh.open_interest,
                )
                store.upsert_bars(session, instrument.id, "1d", [bar], tencent_source.id)
                stats["repaired"] += 1
                logger.warning(
                    "repaired corrupt bar %s %s: %s -> %s", symbol, day.isoformat(), close, fresh.close
                )
            else:
                session.execute(
                    delete(MarketBar).where(
                        MarketBar.instrument_id == instrument.id,
                        MarketBar.timeframe == "1d",
                        MarketBar.ts_utc == ts,
                    )
                )
                stats["dropped"] += 1
                logger.warning("dropped corrupt bar %s %s close=%s", symbol, day.isoformat(), close)
            session.commit()
    logger.info("repair_outliers: %s", stats)
    return stats


def clean_holiday_stubs(session: Session) -> dict:
    """清掉历史里已经入库的休市伪日线（:mod:`app.ingest.bars_quality`）。

    新浪在休市日会补一根假 K 线（开高低复制前一日、成交量复制或置 0）。它不会让
    曲线断开，却会污染「共识交易日」，把正常标的误报成缺数据，所以历史存量也要清，
    并且清完之后再跑连续性检查。
    """
    stats: dict = {"stubs": 0, "symbols": 0, "checked": 0}
    rows = session.execute(
        select(
            Instrument.id,
            Instrument.symbol,
            MarketBar.ts_utc,
            MarketBar.open,
            MarketBar.high,
            MarketBar.low,
            MarketBar.close,
            MarketBar.volume,
        )
        .join(Instrument, Instrument.id == MarketBar.instrument_id)
        .where(MarketBar.timeframe == "1d")
        .order_by(Instrument.symbol, MarketBar.ts_utc)
    ).all()

    by_symbol: dict[str, dict] = {}
    for instrument_id, symbol, ts, open_, high, low, close, volume in rows:
        group = by_symbol.setdefault(symbol, {"instrument_id": instrument_id, "items": []})
        group["items"].append((ts, (open_, high, low, close, volume)))

    for symbol, group in by_symbol.items():
        instrument_id = group["instrument_id"]
        single_print = bars_quality.is_single_print_series([item[1] for item in group["items"]])
        prev = None
        removed = 0
        for ts, current in group["items"]:
            stats["checked"] += 1
            if prev is not None and bars_quality.is_holiday_stub(
                current, prev, series_is_single_print=single_print
            ):
                session.execute(
                    delete(MarketBar).where(
                        MarketBar.instrument_id == instrument_id,
                        MarketBar.timeframe == "1d",
                        MarketBar.ts_utc == ts,
                    )
                )
                removed += 1
                continue
            prev = current
        if removed:
            stats["stubs"] += removed
            stats["symbols"] += 1
            logger.info("removed %s holiday stub bars from %s", removed, symbol)
            session.commit()
    logger.info("clean_holiday_stubs: %s", stats)
    return stats


def run_backfill() -> dict:
    """清伪日线 + 补全历史数据 + 订正脏点（供 job 调用）。"""
    with HttpClient(min_interval=0.5) as client, SessionLocal() as session:
        cleaned = clean_holiday_stubs(session)
        repaired = repair_outliers(session, client)
        filled = fill_bar_gaps(session, client)
    result = {"stubs": cleaned, "repair": repaired, "fill": filled}
    logger.info("run_backfill: %s", result)
    return result
