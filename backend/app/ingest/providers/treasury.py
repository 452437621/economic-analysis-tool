"""US Treasury daily yield curves (nominal + real) as free, keyless CSV."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from app.ingest.contracts import MacroPoint
from app.ingest.http import HttpClient

BASE_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
)

NOMINAL_COLUMNS = {
    "US2Y": "2 Yr",
    "US5Y": "5 Yr",
    "US10Y": "10 Yr",
    "US30Y": "30 Yr",
}
REAL_COLUMNS = {
    "US5Y_REAL": "5 YR",
    "US10Y_REAL": "10 YR",
}


def _parse_date(value: str) -> datetime | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_curve_csv(text: str, columns: dict[str, str]) -> dict[str, list[MacroPoint]]:
    reader = csv.DictReader(io.StringIO(text))
    result: dict[str, list[MacroPoint]] = {code: [] for code in columns}
    for row in reader:
        ts = _parse_date(row.get("Date", ""))
        if ts is None:
            continue
        for code, column in columns.items():
            raw = row.get(column)
            if raw in (None, ""):
                continue
            try:
                result[code].append(MacroPoint(code=code, ts=ts, value=float(raw)))
            except ValueError:
                continue
    for points in result.values():
        points.sort(key=lambda point: point.ts)
    return result


def add_breakevens(curves: dict[str, list[MacroPoint]]) -> None:
    """Add breakeven inflation = nominal - real, paired by date."""
    for tenor in ("5Y", "10Y"):
        nominal = {p.ts: p.value for p in curves.get(f"US{tenor}", [])}
        real = {p.ts: p.value for p in curves.get(f"US{tenor}_REAL", [])}
        code = f"US{tenor}_BE"
        curves[code] = [
            MacroPoint(code=code, ts=ts, value=round(nominal[ts] - real[ts], 3))
            for ts in sorted(set(nominal) & set(real))
        ]


def fetch_curves(client: HttpClient, years: list[int]) -> dict[str, list[MacroPoint]]:
    result: dict[str, list[MacroPoint]] = {}
    for year in years:
        for kind, columns in (("nominal", NOMINAL_COLUMNS), ("real", REAL_COLUMNS)):
            resp = client.get(
                BASE_URL.format(year=year),
                params={
                    "type": f"daily_treasury_{'yield' if kind == 'nominal' else 'real_yield'}_curve",
                    "field_tdr_date_value": str(year),
                    "page": "",
                    "_format": "csv",
                },
            )
            resp.raise_for_status()
            curves = parse_curve_csv(resp.text, columns)
            for code, points in curves.items():
                result.setdefault(code, []).extend(points)
    add_breakevens(result)
    for code in result:
        result[code].sort(key=lambda point: point.ts)
    return result
