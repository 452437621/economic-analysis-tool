"""Sina providers: domestic futures daily bars / quotes, overseas quotes, FX quotes."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.ingest.contracts import Bar, Quote
from app.ingest.http import HttpClient

CST = ZoneInfo("Asia/Shanghai")
SINA_REFERER = {"Referer": "https://finance.sina.com.cn"}
DAILY_URL = (
    "https://stock.finance.sina.com.cn/futures/api/jsonp.php/"
    "var%20_{code}=/InnerFuturesNewService.getDailyKLine?symbol={code}"
)
GLOBAL_DAILY_URL = (
    "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
    "var%20_{code}=/GlobalFuturesService.getGlobalFuturesDailyKLine?symbol={code}"
)
REALTIME_URL = "https://hq.sinajs.cn/list={codes}"


def _f(value: str | None) -> float | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value or value in {"-", "--"}:
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def _quote_payload(text: str) -> str:
    if '="' not in text:
        return ""
    return text.split('="', 1)[-1].rsplit('"', 1)[0]


def parse_daily_jsonp(text: str) -> list[Bar]:
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        rows = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    bars: list[Bar] = []
    for row in rows:
        try:
            ts = datetime.strptime(str(row["d"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            bars.append(
                Bar(
                    ts=ts,
                    open=float(row["o"]),
                    high=float(row["h"]),
                    low=float(row["l"]),
                    close=float(row["c"]),
                    volume=_f(row.get("v")),
                    open_interest=_f(row.get("p")),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    bars.sort(key=lambda bar: bar.ts)
    return bars


def parse_global_daily_jsonp(text: str) -> list[Bar]:
    """Parse Sina global futures daily K-line (date/open/high/low/close)."""
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        rows = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    bars: list[Bar] = []
    for row in rows:
        try:
            ts = datetime.strptime(str(row["date"]), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            bars.append(
                Bar(
                    ts=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=_f(row.get("volume")),
                    open_interest=_f(row.get("position")),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue
    bars.sort(key=lambda bar: bar.ts)
    return bars


def fetch_global_daily(client: HttpClient, code: str) -> list[Bar]:
    resp = client.get(GLOBAL_DAILY_URL.format(code=code), headers=SINA_REFERER)
    resp.raise_for_status()
    return parse_global_daily_jsonp(resp.content.decode("utf-8", errors="replace"))


def parse_domestic_quote(text: str, symbol: str) -> Quote | None:
    """Parse `hq_str_nf_XXX` (domestic futures continuous contract quote)."""
    fields = _quote_payload(text).split(",")
    if len(fields) < 18:
        return None
    date_str, time_str = fields[17].strip(), fields[1].strip().zfill(6)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        return None
    try:
        ts = datetime.strptime(date_str + time_str, "%Y-%m-%d%H%M%S").replace(tzinfo=CST)
    except ValueError:
        return None
    price = _f(fields[8]) or _f(fields[2])
    if price is None:
        return None
    return Quote(
        symbol=symbol,
        ts=ts.astimezone(timezone.utc),
        price=price,
        prev_close=_f(fields[10]),
        open=_f(fields[2]),
        high=_f(fields[3]),
        low=_f(fields[4]),
        volume=_f(fields[13]),
        open_interest=_f(fields[14]),
        bid=_f(fields[6]),
        ask=_f(fields[7]),
        delay_sec=3,
    )


def parse_overseas_quote(text: str, symbol: str) -> Quote | None:
    """Parse Sina `hf_` overseas futures / spot quote."""
    fields = _quote_payload(text).split(",")
    if len(fields) < 13:
        return None
    date_str, time_str = fields[12].strip(), fields[6].strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        return None
    try:
        ts = datetime.strptime(date_str + " " + time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
    except ValueError:
        return None
    price = _f(fields[0])
    if price is None:
        return None
    volume = _f(fields[14]) if len(fields) > 14 else None
    # LME 等品种的字段 8（昨结算）可能为 0，退回到字段 7 的昨收
    prev_close = _f(fields[8]) or (_f(fields[7]) if len(fields) > 7 else None)
    return Quote(
        symbol=symbol,
        ts=ts.astimezone(timezone.utc),
        price=price,
        prev_close=prev_close,
        open=_f(fields[9]),
        high=_f(fields[4]),
        low=_f(fields[5]),
        volume=volume,
        bid=_f(fields[2]),
        ask=_f(fields[3]),
        delay_sec=900,
    )


def parse_fx_quote(text: str, symbol: str) -> Quote | None:
    """Parse Sina `fx_` spot FX quote."""
    fields = _quote_payload(text).split(",")
    if len(fields) < 12:
        return None
    price = _f(fields[8])
    if price is None:
        return None
    change = _f(fields[11])
    prev_close = price - change if change is not None else None
    time_str = fields[0].strip()
    date_match = next(
        (f.strip() for f in fields if re.fullmatch(r"\d{4}-\d{2}-\d{2}", f.strip())), None
    )
    if date_match:
        date_str = date_match
    else:
        date_str = datetime.now(CST).strftime("%Y-%m-%d")
    try:
        ts = datetime.strptime(date_str + " " + time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
    except ValueError:
        ts = datetime.now(timezone.utc)
    return Quote(
        symbol=symbol,
        ts=ts.astimezone(timezone.utc),
        price=price,
        prev_close=prev_close,
        bid=_f(fields[1]),
        ask=_f(fields[2]),
        delay_sec=30,
    )


def fetch_daily_continuous(client: HttpClient, code: str) -> list[Bar]:
    resp = client.get(DAILY_URL.format(code=code), headers=SINA_REFERER)
    resp.raise_for_status()
    return parse_daily_jsonp(resp.content.decode("gbk", errors="replace"))


def fetch_domestic_quotes(client: HttpClient, codes: dict[str, str]) -> dict[str, Quote]:
    """Fetch quotes for several domestic continuous codes in one request."""
    lists = ",".join(f"nf_{code}" for code in codes.values())
    resp = client.get(REALTIME_URL.format(codes=lists), headers=SINA_REFERER)
    resp.raise_for_status()
    text = resp.content.decode("gb18030", errors="replace")
    result: dict[str, Quote] = {}
    for symbol, code in codes.items():
        marker = f'hq_str_nf_{code}="'
        start = text.find(marker)
        if start < 0:
            continue
        end = text.find('";', start)
        chunk = text[start : end + 2] if end > 0 else text[start:]
        quote = parse_domestic_quote(chunk, symbol)
        if quote:
            result[symbol] = quote
    return result


def fetch_overseas_quotes(client: HttpClient, codes: dict[str, str]) -> dict[str, Quote]:
    lists = ",".join(codes.values())
    resp = client.get(REALTIME_URL.format(codes=lists), headers=SINA_REFERER)
    resp.raise_for_status()
    text = resp.content.decode("gb18030", errors="replace")
    result: dict[str, Quote] = {}
    for symbol, code in codes.items():
        marker = f'hq_str_{code}="'
        start = text.find(marker)
        if start < 0:
            continue
        end = text.find('";', start)
        chunk = text[start : end + 2] if end > 0 else text[start:]
        quote = parse_overseas_quote(chunk, symbol)
        if quote:
            result[symbol] = quote
    return result


def fetch_fx_quotes(client: HttpClient, codes: dict[str, str]) -> dict[str, Quote]:
    lists = ",".join(codes.values())
    resp = client.get(REALTIME_URL.format(codes=lists), headers=SINA_REFERER)
    resp.raise_for_status()
    text = resp.content.decode("gb18030", errors="replace")
    result: dict[str, Quote] = {}
    for symbol, code in codes.items():
        marker = f'hq_str_{code}="'
        start = text.find(marker)
        if start < 0:
            continue
        end = text.find('";', start)
        chunk = text[start : end + 2] if end > 0 else text[start:]
        quote = parse_fx_quote(chunk, symbol)
        if quote:
            result[symbol] = quote
    return result
