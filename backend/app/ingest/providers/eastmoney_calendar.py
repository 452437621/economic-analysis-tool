"""Eastmoney financial calendar (RPT_CPH_FECALENDAR)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
CST = timezone(timedelta(hours=8))

HIGH_KEYWORDS = (
    "利率",
    "CPI",
    "PPI",
    "非农",
    "GDP",
    "PMI",
    "失业",
    "零售",
    "工业",
    "贸易",
    "M2",
    "社融",
    "议息",
)


def classify_importance(name: str) -> int:
    return 3 if any(keyword in name for keyword in HIGH_KEYWORDS) else 2


def fetch_calendar(
    client: HttpClient,
    start: date,
    end: date,
    page_size: int = 500,
    max_pages: int = 10,
) -> list[dict]:
    rows: list[dict] = []
    page = 1
    pages = 1
    while page <= pages and page <= max_pages:
        resp = client.get(
            URL,
            params={
                "reportName": "RPT_CPH_FECALENDAR",
                "columns": "ALL",
                "sortColumns": "START_DATE",
                "sortTypes": 1,
                "pageNumber": page,
                "pageSize": page_size,
                "filter": f"(START_DATE>='{start.isoformat()}')(START_DATE<='{end.isoformat()}')(FE_TYPE=\"经济数据\")",
            },
        )
        resp.raise_for_status()
        result = resp.json().get("result") or {}
        rows.extend(result.get("data") or [])
        pages = int(result.get("pages") or 1)
        page += 1

    events: list[dict] = []
    for row in rows:
        raw = (row.get("START_DATE") or "")[:19]
        try:
            local = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                local = datetime.strptime(raw[:10], "%Y-%m-%d")
            except ValueError:
                continue
        ts = local.replace(tzinfo=CST).astimezone(timezone.utc)
        name = (row.get("FE_NAME") or "").strip()
        if not name or "累计同比" in name:
            continue
        events.append(
            {
                "ts_utc": ts,
                "name": name,
                "category": (row.get("FE_TYPE") or "经济数据").strip(),
                "country": (row.get("CITY") or "").strip() or None,
                "importance": classify_importance(name),
                "source_code": str(row.get("FE_CODE") or ""),
            }
        )
    logger.info("eastmoney calendar: %s events", len(events))
    return events
