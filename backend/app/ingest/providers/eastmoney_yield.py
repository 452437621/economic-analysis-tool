"""Eastmoney China/US treasury yield report (RPTA_WEB_TREASURYYIELD)."""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone

from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
# 报表一次最多给 500 行，全量历史要翻页（与页面脚本一致）。
PAGE_SIZE = 500
MAX_PAGES = 40
# 字段映射来自东财「中美国债收益率」页面 JS
FIELDS = {
    "CN2Y": "EMM00588704",
    "CN5Y": "EMM00166462",
    "CN10Y": "EMM00166466",
    "CN30Y": "EMM00166469",
    "CN10Y2Y": "EMM01276014",
}


def fetch_rates(client: HttpClient, start_year: int | None = None) -> dict[str, list[MacroPoint]]:
    """按页拉取「中美国债收益率」报表，直到早于 ``start_year`` 或没有更多数据。

    报表返回的是全量历史（实测 9389 行 / 19 页，一页 500 行封顶：只请求第 1 页
    会让中国国债收益率只从 2024-12 开始，历史趋势图看起来「突然从某天开始」）。
    """
    start_year = start_year or (datetime.now(timezone.utc).year - 4)
    out: dict[str, list[MacroPoint]] = {code: [] for code in FIELDS}
    for page in range(1, MAX_PAGES + 1):
        resp = client.get(
            URL,
            params={
                "reportName": "RPTA_WEB_TREASURYYIELD",
                "columns": "ALL",
                "sortColumns": "SOLAR_DATE",
                "sortTypes": -1,
                "pageNumber": page,
                "pageSize": PAGE_SIZE,
                "token": "894050c76af8597a853f5b408b759f5d",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        result = payload.get("result") or {}
        rows = result.get("data") or []
        if not rows:
            break
        total_pages = result.get("pages")
        reached_old = False
        for row in reversed(rows):  # ascending dates within the page
            raw_date = (row.get("SOLAR_DATE") or "")[:10]
            try:
                parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                continue
            if parsed.year < start_year:
                reached_old = True
                continue
            ts = datetime.combine(parsed, time.min, tzinfo=timezone.utc)
            for code, field in FIELDS.items():
                value = row.get(field)
                if value is None:
                    continue
                try:
                    out[code].append(MacroPoint(code=code, ts=ts, value=float(value)))
                except (TypeError, ValueError):
                    continue
        # 报表自带总页数：够了就停，省掉一次「空页探测」请求。
        if reached_old or (total_pages and page >= int(total_pages)):
            break
    logger.info("eastmoney yields: %s", {code: len(points) for code, points in out.items()})
    # 报表按日期倒序分页返回，翻页后整体是「新→旧→更旧」，统一按时间升序输出。
    return {code: sorted(points, key=lambda point: point.ts) for code, points in out.items()}
