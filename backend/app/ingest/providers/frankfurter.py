"""Frankfurter (ECB reference rates) daily FX history, free and keyless."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from app.ingest.contracts import Bar
from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

BASE = "https://api.frankfurter.app/{start}..{end}?from=USD&to=JPY,EUR,GBP,CAD,SEK,CHF"
SYMBOLS = ["USDJPY", "USDCAD", "USDSEK", "USDCHF", "EURUSD", "GBPUSD"]


def parse_rates(payload: dict) -> dict[str, list[Bar]]:
    rates = payload.get("rates") or {}
    result: dict[str, list[Bar]] = {symbol: [] for symbol in SYMBOLS}
    for day, row in rates.items():
        try:
            ts = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            jpy = float(row["JPY"])
            eur = float(row["EUR"])
            gbp = float(row["GBP"])
            cad = float(row["CAD"])
            sek = float(row["SEK"])
            chf = float(row["CHF"])
        except (KeyError, ValueError, TypeError):
            continue
        quotes = {
            "USDJPY": jpy,
            "USDCAD": cad,
            "USDSEK": sek,
            "USDCHF": chf,
            "EURUSD": 1 / eur if eur else None,
            "GBPUSD": 1 / gbp if gbp else None,
        }
        for symbol, close in quotes.items():
            if not close:
                continue
            result[symbol].append(
                Bar(ts=ts, open=close, high=close, low=close, close=close, volume=None)
            )
    for bars in result.values():
        bars.sort(key=lambda bar: bar.ts)
    return result


def fetch_daily(
    client: HttpClient,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, list[Bar]]:
    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=365 * 5))
    response = client.get(BASE.format(start=start_date.isoformat(), end=end_date.isoformat()))
    response.raise_for_status()
    result = parse_rates(response.json() or {})
    logger.info("frankfurter fx: %s", {symbol: len(bars) for symbol, bars in result.items()})
    return result
