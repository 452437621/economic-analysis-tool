"""Eastmoney providers: A-share quote and daily kline."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from app.ingest.contracts import Bar, Quote
from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

EM_HEADERS = {"Referer": "https://quote.eastmoney.com/"}
QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
TRENDS_URL = "https://push2.eastmoney.com/api/qt/stock/trends2/get"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

QUOTE_FIELDS = "f43,f44,f45,f46,f47,f48,f57,f58,f60,f170"
TRENDS_FIELDS1 = "f1,f2,f3,f4,f5,f6,f7,f8"
TRENDS_FIELDS2 = "f51,f53"

# 实时快照接口（/api/qt/stock/get）会整段被对端直接掐断（RemoteProtocolError /
# curl 56），而同一台机器的分时接口（/api/qt/stock/trends2/get）仍然正常。主接口
# 失败后先熔断 5 分钟、直接走分时兜底，避免每个标的都白等一轮重试。
QUOTE_COOLDOWN_SEC = 300.0
_quote_down_until = 0.0
_quote_blocked_reason: str | None = None


def quote_api_blocked() -> bool:
    return time.monotonic() < _quote_down_until


def quote_blocked_reason() -> str | None:
    return _quote_blocked_reason if quote_api_blocked() else None


def _mark_quote_blocked(reason: str) -> None:
    global _quote_down_until, _quote_blocked_reason
    _quote_down_until = time.monotonic() + QUOTE_COOLDOWN_SEC
    _quote_blocked_reason = reason


def reset_quote_breaker() -> None:
    """Clear the snapshot-API circuit breaker (tests / manual recovery)."""
    global _quote_down_until, _quote_blocked_reason
    _quote_down_until = 0.0
    _quote_blocked_reason = None


def _scaled(value, divisor: float = 100.0) -> float | None:
    if value in (None, "-"):
        return None
    try:
        return float(value) / divisor
    except (TypeError, ValueError):
        return None


def _plain(value) -> float | None:
    if value in (None, "-", ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_quote(payload: dict, symbol: str) -> Quote | None:
    data = payload.get("data") or {}
    price = _scaled(data.get("f43"))
    if not price:
        return None
    return Quote(
        symbol=symbol,
        ts=datetime.now(timezone.utc),
        price=price,
        prev_close=_scaled(data.get("f60")),
        open=_scaled(data.get("f46")),
        high=_scaled(data.get("f44")),
        low=_scaled(data.get("f45")),
        volume=float(data["f47"]) if data.get("f47") not in (None, "-") else None,
        delay_sec=3,
    )


def parse_trend_quote(payload: dict, symbol: str) -> Quote | None:
    """Latest price from the intraday trend line (last point of trends2)."""
    data = payload.get("data") or {}
    trends = data.get("trends") or []
    price: float | None = None
    for line in reversed(trends):
        parts = str(line).split(",")
        if len(parts) < 2:
            continue
        price = _plain(parts[1])
        if price:
            break
    if not price:
        return None
    return Quote(
        symbol=symbol,
        ts=datetime.now(timezone.utc),
        price=price,
        prev_close=_plain(data.get("preClose")),
        delay_sec=60,
    )


def parse_kline(payload: dict) -> list[Bar]:
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    bars: list[Bar] = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            ts = datetime.strptime(parts[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            bars.append(
                Bar(
                    ts=ts,
                    open=float(parts[1]),
                    close=float(parts[2]),
                    high=float(parts[3]),
                    low=float(parts[4]),
                    volume=float(parts[5]) if parts[5] else None,
                )
            )
        except (ValueError, TypeError):
            continue
    bars.sort(key=lambda bar: bar.ts)
    return bars


def fetch_quote_via_trends(client: HttpClient, secid: str, symbol: str) -> Quote | None:
    resp = client.get(
        TRENDS_URL,
        headers=EM_HEADERS,
        params={
            "secid": secid,
            "fields1": TRENDS_FIELDS1,
            "fields2": TRENDS_FIELDS2,
            "ndays": "1",
            "iscr": "0",
            "iscca": "0",
        },
    )
    resp.raise_for_status()
    return parse_trend_quote(resp.json(), symbol)


def fetch_quote(client: HttpClient, secid: str, symbol: str) -> Quote | None:
    """Snapshot quote, falling back to the intraday trend line.

    The snapshot endpoint gets dropped by Eastmoney's edge for our IP while the
    intraday endpoint on the same host still answers, so the last trend point is
    a drop-in replacement for the latest price.
    """
    if not quote_api_blocked():
        try:
            resp = client.get(
                QUOTE_URL,
                headers=EM_HEADERS,
                params={"secid": secid, "fields": QUOTE_FIELDS},
                retries=1,
            )
            resp.raise_for_status()
            quote = parse_quote(resp.json(), symbol)
            if quote is not None:
                return quote
            logger.info("eastmoney snapshot empty for %s, using trends", symbol)
        except Exception as exc:  # noqa: BLE001 - 任何主接口失败都切分时兜底
            logger.warning("eastmoney snapshot blocked (%s): %s", symbol, exc)
            _mark_quote_blocked(f"{type(exc).__name__}: {exc}")
    return fetch_quote_via_trends(client, secid, symbol)


def fetch_daily_kline(
    client: HttpClient,
    secid: str,
    *,
    beg: str = "20190101",
    end: str = "20500101",
) -> list[Bar]:
    resp = client.get(
        KLINE_URL,
        headers=EM_HEADERS,
        params={
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "klt": "101",
            "fqt": "1",
            "beg": beg,
            "end": end,
        },
    )
    resp.raise_for_status()
    return parse_kline(resp.json())
