"""NY Fed 货币市场管道：TGCR / BGCR / OBFR 与隔夜逆回购（RRP）规模。

``markets.newyorkfed.org`` 的参考利率接口与 SOFR/EFFR 同构（``refRates`` 数组）；
RRP 走 ``rp/reverserepo/propositions``，每个营业日可能多笔操作，按
``operationDate`` 汇总 ``totalAmtAccepted``（美元）。

这几条序列是「美元心脏」监测的核心：SOFR−EFFR 之外，TGCR/BGCR 与 RRP 余额
能区分「准备金充裕」与「抵押品短缺」两种截然不同的紧缩。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

BASE = "https://markets.newyorkfed.org/api/rates/{path}/search.json"
RRP_URL = "https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json"

RATE_PATHS: dict[str, str] = {
    "secured/tgcr": "US_TGCR",
    "secured/bgcr": "US_BGCR",
    "unsecured/obfr": "US_OBFR",
}


def _rate_series(client: HttpClient, path: str, start_date: date, end_date: date) -> list[MacroPoint]:
    response = client.get(
        BASE.format(path=path),
        params={"startDate": start_date.isoformat(), "endDate": end_date.isoformat()},
    )
    response.raise_for_status()
    rows = (response.json() or {}).get("refRates") or []
    points: list[MacroPoint] = []
    for row in rows:
        effective = row.get("effectiveDate")
        rate = row.get("percentRate")
        if not effective or rate is None:
            continue
        try:
            parsed = datetime.strptime(effective, "%Y-%m-%d")
        except ValueError:
            continue
        points.append(
            MacroPoint(
                code="",
                ts=parsed.replace(tzinfo=timezone.utc),
                value=float(rate),
            )
        )
    points.sort(key=lambda point: point.ts)
    return points


def _rrp_series(client: HttpClient, start_date: date, end_date: date) -> list[MacroPoint]:
    response = client.get(
        RRP_URL,
        params={"startDate": start_date.isoformat(), "endDate": end_date.isoformat()},
    )
    response.raise_for_status()
    payload = response.json() or {}
    operations = (payload.get("repo") or {}).get("operations") or []
    by_day: dict[str, float] = {}
    for row in operations:
        day = row.get("operationDate")
        amount = row.get("totalAmtAccepted")
        if not day or amount is None:
            continue
        try:
            by_day[day] = by_day.get(day, 0.0) + float(amount)
        except (TypeError, ValueError):
            continue
    points: list[MacroPoint] = []
    for day, amount in sorted(by_day.items()):
        try:
            parsed = datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            continue
        points.append(
            MacroPoint(
                code="US_RRP_AMT",
                ts=parsed.replace(tzinfo=timezone.utc),
                value=round(amount, 2),
            )
        )
    return points


def fetch_money(
    client: HttpClient,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, list[MacroPoint]]:
    """TGCR/BGCR/OBFR 与 RRP 规模；任一失败只影响自身（由调用方 try/except）。"""
    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=365 * 5))
    result: dict[str, list[MacroPoint]] = {}
    for path, code in RATE_PATHS.items():
        points = _rate_series(client, path, start_date, end_date)
        for point in points:
            point.code = code
        result[code] = points
    result["US_RRP_AMT"] = _rrp_series(client, start_date, end_date)
    logger.info(
        "nyfed money: TGCR=%s BGCR=%s OBFR=%s RRP=%s",
        len(result.get("US_TGCR", [])),
        len(result.get("US_BGCR", [])),
        len(result.get("US_OBFR", [])),
        len(result.get("US_RRP_AMT", [])),
    )
    return result
