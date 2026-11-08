"""Eastmoney providers: A-share quote and daily kline."""

from __future__ import annotations

from datetime import datetime, timezone

from app.ingest.contracts import Bar, Quote
from app.ingest.http import HttpClient

EM_HEADERS = {"Referer": "https://quote.eastmoney.com/"}
QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

QUOTE_FIELDS = "f43,f44,f45,f46,f47,f48,f57,f58,f60,f170"


def _scaled(value, divisor: float = 100.0) -> float | None:
    if value in (None, "-"):
        return None
    try:
        return float(value) / divisor
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


def fetch_quote(client: HttpClient, secid: str, symbol: str) -> Quote | None:
    resp = client.get(
        QUOTE_URL,
        headers=EM_HEADERS,
        params={"secid": secid, "fields": QUOTE_FIELDS},
    )
    resp.raise_for_status()
    return parse_quote(resp.json(), symbol)


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
