"""M5 tests: alerts and contract-aware position sizing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.alerts import compute_alerts
from app.decision.plans import build_plan, size_lots

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


def test_size_lots_contract_size():
    # 1000g/lot, 10 CNY stop -> 10,000 CNY risk per lot; 2500 risk budget -> 0.25 lot
    lots = size_lots(1_000_000, 0.25, price=500, stop_price=490, contract_size=1000)
    assert abs(lots - 0.25) < 1e-6


def test_build_plan_contract_checks():
    signal = {
        "symbol": "M",
        "type": "breakout",
        "direction": "long",
        "price": 3000.0,
        "atr": 20.0,
        "strength": 0.9,
        "note": "test",
        "params": {},
    }
    plan = build_plan(
        signal,
        spec={"contract_size": 10, "margin_pct": 0.08, "fee_per_lot": 1.5},
        equity=1_000_000,
        risk_pct=0.25,
    )
    assert plan["size"] >= 1
    assert plan["margin"] > 0
    assert plan["fee"] > 0
    assert all(check["passed"] for check in plan["checks"])
    assert plan["weight_pct"] > 0
    assert plan["stop_distance_pct"] > 0
    assert plan["risk_reward"] > 0


def test_build_plan_is_funding_agnostic():
    """昂贵合约只输出小数手，不再因「资金不足」被 0 手或拦截。"""
    signal = {
        "symbol": "AU",
        "type": "breakout",
        "direction": "long",
        "price": 900.0,
        "atr": 10.0,
        "strength": 0.9,
        "note": "test",
        "params": {},
    }
    expensive = build_plan(
        signal,
        spec={"contract_size": 1000, "margin_pct": 0.09, "fee_per_lot": 10},
        equity=1_000_000,
        risk_pct=0.25,
    )
    assert 0 < expensive["size"] < 1
    assert expensive["lots_int"] == 0
    assert "不足 1 整手" in expensive["sizing_note"]
    assert all(check["rule"] != "手数 ≥ 1" for check in expensive["checks"])
    assert all(check["passed"] for check in expensive["checks"])
    # 默认基准权益与显式权益只影响规模，不影响检查项语义
    default_plan = build_plan(signal, spec={"contract_size": 1000, "margin_pct": 0.09, "fee_per_lot": 10})
    assert default_plan["base_equity"] == 100_000.0
    assert default_plan["equity"] == default_plan["base_equity"]
    assert default_plan["size"] < expensive["size"]
    assert abs(default_plan["size"] * 10 - expensive["size"]) < 0.01
