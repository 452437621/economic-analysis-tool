"""CZCE official daily quotes (cross-check source for SR/CF)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.ingest.http import HttpClient

BASE_URL = "https://www.czce.com.cn/cn/DFSStaticFiles/Future/{year}/{date}/FutureDataDaily.txt"

CODE_RE = re.compile(r"^([A-Z]{1,2})(\d{3,4})$")


@dataclass(slots=True)
class CzceRow:
    code: str
    product: str
    prev_settle: float | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    settle: float | None
    volume: float | None
    open_interest: float | None
    oi_change: float | None


def _num(value: str) -> float | None:
    value = value.strip().replace(",", "")
    if not value or value in {"-", "--"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_daily(text: str) -> dict[str, list[CzceRow]]:
    """Parse CZCE daily txt into {product: [rows]}.

    Columns: 合约代码|昨结算|今开盘|最高价|最低价|今收盘|今结算|涨跌1|涨跌2|
             成交量(手)|持仓量|增减量|成交额(万元)|交割结算价
    """
    result: dict[str, list[CzceRow]] = {}
    for line in text.splitlines():
        if "|" not in line or "合约代码" in line:
            continue
        fields = [field.strip() for field in line.split("|")]
        if len(fields) < 11:
            continue
        match = CODE_RE.match(fields[0])
        if not match:
            continue
        row = CzceRow(
            code=fields[0],
            product=match.group(1),
            prev_settle=_num(fields[1]),
            open=_num(fields[2]),
            high=_num(fields[3]),
            low=_num(fields[4]),
            close=_num(fields[5]),
            settle=_num(fields[6]),
            volume=_num(fields[9]),
            open_interest=_num(fields[10]),
            oi_change=_num(fields[11]) if len(fields) > 11 else None,
        )
        result.setdefault(row.product, []).append(row)
    return result


def main_contract(rows: list[CzceRow]) -> CzceRow | None:
    """Return the contract with the largest open interest."""
    candidates = [row for row in rows if row.open_interest is not None]
    if not candidates:
        return None
    return max(candidates, key=lambda row: row.open_interest or 0)


def fetch_daily(client: HttpClient, trade_date) -> dict[str, list[CzceRow]]:  # noqa: ANN001
    url = BASE_URL.format(year=trade_date.year, date=trade_date.strftime("%Y%m%d"))
    resp = client.get(url)
    resp.raise_for_status()
    raw = resp.content
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gb18030", errors="replace")
    return parse_daily(text)


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
