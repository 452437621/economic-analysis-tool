"""Japan MOF JGB interest rates (official CSV, daily, 1974-present)."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, time, timezone

from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

HIST_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
# csv columns: Date,1Y,2Y,...,10Y,...,30Y,40Y -> indexes in row including date
SERIES = {"JP2Y": 2, "JP10Y": 10, "JP30Y": 14}


def fetch_rates(client: HttpClient, start_year: int | None = None) -> dict[str, list[MacroPoint]]:
    start_year = start_year or (datetime.now(timezone.utc).year - 4)
    resp = client.get(HIST_URL)
    resp.raise_for_status()
    text = resp.content.decode("utf-8", errors="replace")
    out: dict[str, list[MacroPoint]] = {code: [] for code in SERIES}
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 15:
            continue
        try:
            parsed = datetime.strptime(row[0].strip(), "%Y/%m/%d").date()
        except ValueError:
            continue
        if parsed.year < start_year:
            continue
        ts = datetime.combine(parsed, time.min, tzinfo=timezone.utc)
        for code, index in SERIES.items():
            try:
                value = float(row[index])
            except (TypeError, ValueError):
                continue
            out[code].append(MacroPoint(code=code, ts=ts, value=value))
    logger.info("jgb rates: %s", {code: len(points) for code, points in out.items()})
    return out
