"""NY Fed SOFR/EFFR provider tests (pure parsing/spread)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.ingest.contracts import MacroPoint
from app.ingest.providers import nyfed


def test_nyfed_spread_from_common_days(monkeypatch):
    day1 = datetime(2026, 11, 5, tzinfo=timezone.utc)
    day2 = datetime(2026, 11, 6, tzinfo=timezone.utc)

    def fake_fetch(client, path, start_date, end_date):
        if path == "secured/sofr":
            return [
                MacroPoint(code="", ts=day1, value=3.90),
                MacroPoint(code="", ts=day2, value=3.89),
            ]
        return [
            MacroPoint(code="", ts=day1, value=3.88),
            MacroPoint(code="", ts=day2, value=3.88),
        ]

    monkeypatch.setattr(nyfed, "_fetch_series", fake_fetch)
    data = nyfed.fetch_rates(None)
    assert [point.code for point in data["SOFR"]] == ["SOFR", "SOFR"]
    assert [point.code for point in data["EFFR"]] == ["EFFR", "EFFR"]
    spread = data["SOFR_EFFR"]
    assert [round(point.value, 2) for point in spread] == [0.02, 0.01]
    assert all(point.code == "SOFR_EFFR" for point in spread)
