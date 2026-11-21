"""FRED CSV backup provider (keyless).

FRED is used as a secondary path for US Treasury yields, money-market rates,
the Fed balance sheet and M2 when the primary official endpoints are
unreachable.  The CSV endpoint returns the full history; ``cosd`` limits it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient
from app.ingest.providers.errors import ProviderError


@dataclass(frozen=True)
class FredSeries:
    fred_id: str
    scale: float
    freq: str


#: Internal EPIC code -> FRED series. Scales convert FRED units to the units
#: stored locally (USD for balance-sheet items, % for yields/rates).
FRED_SERIES: dict[str, FredSeries] = {
    "US2Y": FredSeries("DGS2", 1.0, "d"),
    "US5Y": FredSeries("DGS5", 1.0, "d"),
    "US10Y": FredSeries("DGS10", 1.0, "d"),
    "US30Y": FredSeries("DGS30", 1.0, "d"),
    "US5Y_REAL": FredSeries("DFII5", 1.0, "d"),
    "US10Y_REAL": FredSeries("DFII10", 1.0, "d"),
    "US5Y_BE": FredSeries("T5YIE", 1.0, "d"),
    "US10Y_BE": FredSeries("T10YIE", 1.0, "d"),
    "SOFR": FredSeries("SOFR", 1.0, "d"),
    "EFFR": FredSeries("EFFR", 1.0, "d"),
    "US_FED_ASSETS": FredSeries("WALCL", 1e6, "w"),
    "US_FED_TREASURY": FredSeries("WSHOTSL", 1e6, "w"),
    "US_FED_MBS": FredSeries("WSHOMCB", 1e6, "w"),
    "US_FED_RESERVES": FredSeries("WRESBAL", 1e6, "w"),
    "US_TGA": FredSeries("WTREGEN", 1e9, "w"),
    "US_CURRENCY": FredSeries("WCURCIR", 1e9, "w"),
    "US_M1": FredSeries("M1SL", 1e9, "m"),
    "US_M2": FredSeries("M2SL", 1e9, "m"),
    "US_MONETARY_BASE": FredSeries("BOGMBASE", 1e9, "m"),
}

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def parse_series_csv(text: str, code: str, series: FredSeries) -> list[MacroPoint]:
    points: list[MacroPoint] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith(("observation_date", "date")):
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        raw_date, raw_value = parts[0], parts[1].strip().strip('"')
        if not raw_value or raw_value in {".", "NA", "null"}:
            continue
        try:
            day = date.fromisoformat(raw_date.strip().strip('"'))
            value = float(raw_value) * series.scale
        except (TypeError, ValueError):
            continue
        points.append(
            MacroPoint(code=code, ts=datetime(day.year, day.month, day.day, tzinfo=timezone.utc), value=value)
        )
    return points


def fetch_series(client: HttpClient, code: str, start_date: date | None = None) -> list[MacroPoint]:
    series = FRED_SERIES.get(code)
    if series is None:
        raise ProviderError(f"FRED code not mapped: {code}")
    params = {"id": series.fred_id}
    if start_date is not None:
        params["cosd"] = start_date.isoformat()
    try:
        resp = client.get(FRED_CSV_URL, params=params)
        resp.raise_for_status()
        points = parse_series_csv(resp.text, code, series)
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(f"FRED {series.fred_id} failed: {exc}") from exc
    if not points:
        raise ProviderError(f"FRED {series.fred_id} returned no observations")
    return points


def fetch_many(
    client: HttpClient, codes: list[str], start_date: date | None = None
) -> dict[str, list[MacroPoint]]:
    out: dict[str, list[MacroPoint]] = {}
    for code in codes:
        try:
            out[code] = fetch_series(client, code, start_date)
        except ProviderError:
            continue
    return out
