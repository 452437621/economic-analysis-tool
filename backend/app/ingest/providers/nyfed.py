"""NY Fed reference rates: SOFR, EFFR and their spread (free, keyless JSON)."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

BASE = "https://markets.newyorkfed.org/api/rates/{path}/search.json"


def _fetch_series(
    client: HttpClient, path: str, start_date: date, end_date: date
) -> list[MacroPoint]:
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
            parsed = datetime.strptime(effective, "%Y-%m-%d").date()
            points.append(
                MacroPoint(
                    code="",
                    ts=datetime.combine(parsed, time.min, tzinfo=timezone.utc),
                    value=float(rate),
                )
            )
        except ValueError:
            continue
    points.sort(key=lambda point: point.ts)
    return points


def fetch_rates(
    client: HttpClient,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, list[MacroPoint]]:
    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=365 * 5))
    sofr = _fetch_series(client, "secured/sofr", start_date, end_date)
    effr = _fetch_series(client, "unsecured/effr", start_date, end_date)
    for point in sofr:
        point.code = "SOFR"
    for point in effr:
        point.code = "EFFR"
    effr_by_day = {point.ts.date(): point.value for point in effr}
    spread = [
        MacroPoint(code="SOFR_EFFR", ts=point.ts, value=round(point.value - effr_by_day[point.ts.date()], 4))
        for point in sofr
        if point.ts.date() in effr_by_day
    ]
    logger.info(
        "nyfed rates: SOFR=%s EFFR=%s spread=%s",
        len(sofr),
        len(effr),
        len(spread),
    )
    return {"SOFR": sofr, "EFFR": effr, "SOFR_EFFR": spread}
