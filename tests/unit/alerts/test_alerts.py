"""M5 tests: alert generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.alerts import compute_alerts

pytestmark = pytest.mark.unit

CST = timezone(timedelta(hours=8))


def test_compute_alerts():
    quotes = [
        {"symbol": "AU", "name": "沪金", "asset_class": "metal", "price": 900, "change_pct": 6.2, "stale_sec": 60, "delay_sec": 3},
        {"symbol": "CU", "name": "沪铜", "asset_class": "metal", "price": 100000, "change_pct": 1.0, "stale_sec": 60, "delay_sec": 3},
        {"symbol": "AG", "name": "沪银", "asset_class": "metal", "price": 12000, "change_pct": None, "stale_sec": 8 * 3600, "delay_sec": 3},
    ]
    data_checks = [{"dataset": "国内期货日线", "passed": False, "detail": "latest=None"}]
    plan_checks = [{"rule": "手数 ≥ 1", "passed": False, "detail": "lots=0"}]
    market_open = datetime(2026, 11, 9, 10, 0, tzinfo=CST)
    alerts = compute_alerts(quotes, data_checks, plan_checks, now=market_open)
    kinds = {alert["kind"] for alert in alerts}
    assert "price_move" in kinds
    assert "stale_quote" in kinds
    assert "data_check" in kinds
    assert "plan_risk" in kinds
    price_alert = next(alert for alert in alerts if alert["kind"] == "price_move")
    assert price_alert["level"] == "critical"  # >= 5%
