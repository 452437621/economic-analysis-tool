"""ECB Data Portal: euro-area (Germany) government benchmark yields."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, time, timezone

from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

BASE = "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{series}"
SERIES = {"DE2Y": "SR_2Y", "DE10Y": "SR_10Y"}


def fetch_rates(client: HttpClient, start_year: int | None = None) -> dict[str, list[MacroPoint]]:
    start_year = start_year or (datetime.now().year - 4)
    out: dict[str, list[MacroPoint]] = {}
    for code, series_id in SERIES.items():
        url = BASE.format(series=series_id)
        resp = client.get(url, params={"format": "csvdata", "startPeriod": f"{start_year}-01-01"})
        resp.raise_for_status()
        text = resp.content.decode("utf-8", errors="replace")
        points: list[MacroPoint] = []
        for row in csv.DictReader(io.StringIO(text)):
            period = (row.get("TIME_PERIOD") or "").strip()
            value = (row.get("OBS_VALUE") or "").strip()
            if not period or not value:
                continue
            try:
                parsed = datetime.strptime(period, "%Y-%m-%d").date()
                points.append(
                    MacroPoint(
                        code=code,
                        ts=datetime.combine(parsed, time.min, tzinfo=timezone.utc),
                        value=float(value),
                    )
                )
            except ValueError:
                continue
        out[code] = points
    logger.info("ecb rates: %s", {code: len(points) for code, points in out.items()})
    return out
