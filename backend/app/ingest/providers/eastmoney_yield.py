"""Eastmoney China/US treasury yield report (RPTA_WEB_TREASURYYIELD)."""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone

from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
# 字段映射来自东财「中美国债收益率」页面 JS
FIELDS = {
    "CN2Y": "EMM00588704",
    "CN5Y": "EMM00166462",
    "CN10Y": "EMM00166466",
    "CN30Y": "EMM00166469",
    "CN10Y2Y": "EMM01276014",
}


def fetch_rates(client: HttpClient, start_year: int | None = None) -> dict[str, list[MacroPoint]]:
    start_year = start_year or (datetime.now().year - 4)
    resp = client.get(
        URL,
        params={
            "reportName": "RPTA_WEB_TREASURYYIELD",
            "columns": "ALL",
            "sortColumns": "SOLAR_DATE",
            "sortTypes": -1,
            "pageNumber": 1,
            "pageSize": 5000,
            "token": "894050c76af8597a853f5b408b759f5d",
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    rows = ((payload.get("result") or {}).get("data")) or []
    out: dict[str, list[MacroPoint]] = {code: [] for code in FIELDS}
    for row in reversed(rows):  # ascending dates
        raw_date = (row.get("SOLAR_DATE") or "")[:10]
        try:
            parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if parsed.year < start_year:
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
    logger.info("eastmoney yields: %s", {code: len(points) for code, points in out.items()})
    return out
