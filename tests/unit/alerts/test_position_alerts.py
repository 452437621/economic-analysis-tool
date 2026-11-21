"""Position divergence alert tests (offline)."""

from __future__ import annotations

import pytest

from app.alerts import position_divergence_alerts
from app.ingest.providers.czce_positions import parse_rows as parse_czce_rows

pytestmark = pytest.mark.unit


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
