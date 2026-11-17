"""Japan MOF JGB interest rates (official CSV, daily, 1974-present).

Two files are published:

* ``jgbcme.csv`` — the *current fiscal year* only, refreshed every business day.
  Small (~1 KB) and always up to date.
* ``historical/jgbcme_all.csv`` — the full archive (~1.2 MB). It is refreshed
  with a lag, so it can trail the current-year file by days or weeks.

We fetch the current-year file first (it is what makes the series "live") and
then merge the archive on top when the caller asked for a longer window. The
archive is best-effort: a slow or failing download must not cost us the fresh
data.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, time, timedelta, timezone

from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate"
CUR_URL = f"{BASE_URL}/jgbcme.csv"
HIST_URL = f"{BASE_URL}/historical/jgbcme_all.csv"
# csv columns: Date,1Y,2Y,...,10Y,...,30Y,40Y -> indexes in row including date
SERIES = {"JP2Y": 2, "JP10Y": 10, "JP30Y": 14}


def _rows(text: str) -> dict[date, list[str]]:
    """Parse a MOF CSV into ``{date: row}``; header/notes are skipped."""
    out: dict[date, list[str]] = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 15:
            continue
        try:
            parsed = datetime.strptime(row[0].strip(), "%Y/%m/%d").date()
        except ValueError:
            continue
        out[parsed] = row
    return out


def _download(client: HttpClient, url: str) -> dict[date, list[str]]:
    resp = client.get(url)
    resp.raise_for_status()
    return _rows(resp.content.decode("utf-8", errors="replace"))


# The archive is 1.2 MB and only needed to backfill past years; once a process
# has seen it there is no reason to re-download it on every (hourly) run.
_HIST_CACHE: tuple[datetime, dict[date, list[str]]] | None = None
_HIST_TTL = timedelta(hours=24)


def _historical(client: HttpClient) -> dict[date, list[str]]:
    global _HIST_CACHE
    now = datetime.now(timezone.utc)
    if _HIST_CACHE is not None and now - _HIST_CACHE[0] < _HIST_TTL:
        return _HIST_CACHE[1]
    rows = _download(client, HIST_URL)
    _HIST_CACHE = (now, rows)
    return rows


def fetch_rates(client: HttpClient, start_year: int | None = None) -> dict[str, list[MacroPoint]]:
    start_year = start_year or (datetime.now(timezone.utc).year - 4)
    merged: dict[date, list[str]] = {}

    # Fresh current-fiscal-year file first: this is the only source that keeps
    # Japan up to date, so it must not depend on the archive download.
    cur_ok = False
    try:
        merged.update(_download(client, CUR_URL))
        cur_ok = True
    except Exception:  # noqa: BLE001
        logger.warning("jgb current-year csv failed", exc_info=True)

    try:
        merged.update(_historical(client))
    except Exception:  # noqa: BLE001
        logger.warning("jgb historical csv failed", exc_info=True)

    if not cur_ok and not merged:
        raise RuntimeError("jgb: both current-year and historical csv failed")

    out: dict[str, list[MacroPoint]] = {code: [] for code in SERIES}
    for parsed in sorted(merged):
        if parsed.year < start_year:
            continue
        row = merged[parsed]
        ts = datetime.combine(parsed, time.min, tzinfo=timezone.utc)
        for code, index in SERIES.items():
            try:
                value = float(row[index])
            except (IndexError, TypeError, ValueError):
                continue
            out[code].append(MacroPoint(code=code, ts=ts, value=value))
    logger.info("jgb rates: %s", {code: len(points) for code, points in out.items()})
    return out
