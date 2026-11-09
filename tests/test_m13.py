"""M13 tests: SHFE member position aggregation."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.ingest.providers.czce_positions import parse_rows as parse_czce_rows
from app.ingest.providers.shfe_positions import _aggregate, fetch_latest
from app.alerts import position_divergence_alerts
from app.main import app

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


def test_positions_api_structure():
    with TestClient(app) as client:
        payload = client.get("/api/positions").json()
    assert "data" in payload
    assert "trade_date" in payload


def test_position_divergence_alert():
    positions = [
        {"product": "au", "name": "黄金", "net_ratio": 0.375},
        {"product": "cu", "name": "铜", "net_ratio": -0.04},
        {"product": "sr", "name": "白糖", "net_ratio": -0.073},
    ]
    trends = {"AU": -3.2, "CU": -2.0, "SR": 4.1}
    alerts = position_divergence_alerts(positions, trends)
    titles = {alert["title"] for alert in alerts}
    assert "持仓背离：黄金" in titles
    assert "持仓背离：白糖" in titles
    assert all(alert["kind"] == "position_divergence" for alert in alerts)
    rows = [
        ("郑州商品交易所期货持仓排名表(2026-11-06)",),
        ("品种：白糖SR     日期：2026-11-06",),
        ("名次", "会员简称", "交易量（手）", "增减量", "会员简称", "持买仓量", "增减量", "会员简称", "持卖仓量", "增减量"),
        ("1", "中信期货", "1000", "10", "中信期货", "200", "5", "国泰君安", "150", "-3"),
        ("2", "国泰君安", "900", "20", "国泰君安", "100", "-2", "中信期货", "50", "4"),
        ("品种：棉花CF     日期：2026-11-06",),
        ("名次", "会员简称", "交易量（手）", "增减量", "会员简称", "持买仓量", "增减量", "会员简称", "持卖仓量", "增减量"),
        ("1", "东证期货", "500", "5", "东证期货", "80", "1", "广发期货", "90", "-1"),
    ]
    parsed = parse_czce_rows(rows)
    sugar = next(row for row in parsed if row["product"] == "sr")
    assert sugar["name"] == "白糖"
    assert sugar["long_pos"] == 300
    assert sugar["short_pos"] == 200
    assert sugar["net_pos"] == 100
    cotton = next(row for row in parsed if row["product"] == "cf")
    assert cotton["net_pos"] == -10
