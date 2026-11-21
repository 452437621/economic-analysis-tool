"""SHFE member position aggregation tests (offline)."""

from __future__ import annotations

from datetime import date

import pytest

from app.ingest.providers.shfe_positions import _aggregate, fetch_latest

pytestmark = pytest.mark.unit

ROWS = [
    {"INSTRUMENTID": "cuall", "RANK": -1, "CJ1": 900, "CJ2": 40, "CJ3": 40},
    {"INSTRUMENTID": "cu2612", "RANK": 1, "CJ1": 500, "CJ2": 40, "CJ3": 30, "CJ2_CHG": -2, "CJ3_CHG": 1},
    {"INSTRUMENTID": "cu2612", "RANK": 2, "CJ1": 300, "CJ2": 5, "CJ3": 3, "CJ2_CHG": 1, "CJ3_CHG": 1},
    {"INSTRUMENTID": "cu2701", "RANK": 1, "CJ1": 100, "CJ2": 9, "CJ3": 9, "CJ2_CHG": 0, "CJ3_CHG": 0},
    {"INSTRUMENTID": "au2612", "RANK": 1, "CJ1": 200, "CJ2": 50, "CJ3": 80, "CJ2_CHG": -3, "CJ3_CHG": 4},
]


def test_aggregate_positions_uses_dominant_contract_top20():
    rows = _aggregate(ROWS)
    copper = next(row for row in rows if row["product"] == "cu")
    assert copper["contract"] == "CU2612"
    assert copper["long_pos"] == 45
    assert copper["short_pos"] == 33
    assert copper["net_pos"] == 12
    assert copper["net_ratio"] == round(12 / 78, 4)
    assert copper["long_chg"] == -1
    assert copper["short_chg"] == 2
    assert any(
        member["side"] == "long" and member["rank"] == 1 and member["position"] == 40
        for member in copper["members"]
    )
    assert len(copper["members"]) == 4
    gold = next(row for row in rows if row["product"] == "au")
    assert gold["net_pos"] == -30


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeClient:
    def get(self, url: str) -> FakeResponse:
        if "20261106" in url:
            return FakeResponse(200, {"report_date": "20261106", "o_cursor": ROWS})
        return FakeResponse(404)


def test_fetch_latest_skips_weekend_and_missing_days():
    report_date, rows = fetch_latest(FakeClient(), today=date(2026, 11, 9))  # type: ignore[arg-type]
    assert report_date == date(2026, 11, 6)
    assert len(rows) == 2
