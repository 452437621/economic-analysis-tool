"""Tencent (qt.gtimg.cn) providers: fallback quotes and daily kline.

Used when Eastmoney's endpoints are unreachable; covers CN indices/A-shares,
US indices (usINX/usNDX/usDJI) and HSI.

Two kline endpoints are needed:

* ``fqkline/get`` — 前复权, used for A-shares/HSI (``sh000300,day,,,320,qfq``).
* ``kline/kline`` — raw, used for **US indices**: ``fqkline`` only ever returns
  the latest single bar for them, while ``kline/kline`` returns the full
  history (verified 320 bars for us.INX / us.NDX / us.DJI).

There is no DXY/USDCNH code here; those daily bars come from Sina's forex
service instead.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.ingest.contracts import Bar, Quote
from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

QT_HEADERS = {"Referer": "https://gu.qq.com/"}
QUOTE_URL = "https://qt.gtimg.cn/q="
FQ_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/kline/kline"

# v_sh600000="1~浦发银行~600000~10.78~10.40~10.45~964157~...~20261116161500~..."
_IDX_PRICE = 3
_IDX_PREV_CLOSE = 4
_IDX_OPEN = 5
_IDX_VOLUME = 6
_IDX_HIGH = 33
_IDX_LOW = 34


def _num(value) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_quote_line(line: str, symbol: str) -> Quote | None:
    """Parse one `v_sh600000="..."` payload segment."""
    if '="' not in line:
        return None
    body = line.split('="', 1)[1].rsplit('"', 1)[0]
    parts = body.split("~")
    if len(parts) < 35:
        return None
    price = _num(parts[_IDX_PRICE])
    if not price:
        return None
    return Quote(
        symbol=symbol,
        ts=datetime.now(timezone.utc),
        price=price,
        prev_close=_num(parts[_IDX_PREV_CLOSE]),
        open=_num(parts[_IDX_OPEN]),
        high=_num(parts[_IDX_HIGH]),
        low=_num(parts[_IDX_LOW]),
        volume=_num(parts[_IDX_VOLUME]),
        delay_sec=3,
    )


def parse_quotes(text: str, code_to_symbol: dict[str, str]) -> dict[str, Quote]:
    quotes: dict[str, Quote] = {}
    for segment in text.split(";"):
        segment = segment.strip()
        if not segment.startswith("v_"):
            continue
        code = segment[2:].split("=", 1)[0]
        symbol = code_to_symbol.get(code)
        if symbol is None:
            continue
        quote = parse_quote_line(segment, symbol)
        if quote is not None:
            quotes[symbol] = quote
    return quotes


def fetch_quotes(client: HttpClient, code_to_symbol: dict[str, str]) -> dict[str, Quote]:
    if not code_to_symbol:
        return {}
    resp = client.get(
        QUOTE_URL + ",".join(code_to_symbol),
        headers=QT_HEADERS,
    )
    resp.raise_for_status()
    # qt.gtimg.cn always answers in GBK and sometimes without a charset header.
    text = resp.content.decode("gbk", errors="replace")
    return parse_quotes(text, code_to_symbol)


def parse_kline(payload: dict, code: str) -> list[Bar]:
    data = payload.get("data") or {}
    node = data.get(code)
    if node is None:
        # Tencent renames some codes in the payload (usINX -> us.INX,
        # usDJI -> us.DJI); the response always carries a single symbol.
        keys = [key for key in data if key != "market"]
        node = data.get(keys[0]) if len(keys) == 1 else None
    rows = (node or {}).get("qfqday") or (node or {}).get("day") or []
    bars: list[Bar] = []
    for row in rows:
        if len(row) < 6:
            continue
        try:
            ts = datetime.strptime(str(row[0]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            bars.append(
                Bar(
                    ts=ts,
                    open=float(row[1]),
                    close=float(row[2]),
                    high=float(row[3]),
                    low=float(row[4]),
                    volume=float(row[5]) if row[5] not in (None, "") else None,
                )
            )
        except (ValueError, TypeError):
            continue
    bars.sort(key=lambda bar: bar.ts)
    return bars


def fetch_daily_kline(
    client: HttpClient, code: str, count: int = 320, *, adjust: bool = True
) -> list[Bar]:
    """Daily bars from Tencent.

    ``adjust=True`` uses the 前复权 endpoint (A-shares/HSI). US indices are
    index levels with nothing to adjust, and their data only lives on the raw
    endpoint, so they pass ``adjust=False``.
    """
    if adjust:
        url, param = FQ_KLINE_URL, f"{code},day,,,{count},qfq"
    else:
        url, param = KLINE_URL, f"{code},day,,,{count}"
    resp = client.get(url, headers=QT_HEADERS, params={"param": param})
    resp.raise_for_status()
    return parse_kline(resp.json(), code)
